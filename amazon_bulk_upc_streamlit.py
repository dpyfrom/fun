
# amazon_bulk_upc_streamlit.py

"""
Streamlit app – Bulk Amazon.com Product ➜ UPC Lookup
----------------------------------------------------
Uses the **Amazon Product Advertising API (PA‑API v5)** to search Amazon.com
for each product description you provide and returns the first item's UPC/EAN.

Requirements
------------
pip install streamlit pandas amazon-paapi openpyxl

You MUST have valid PA‑API credentials:
  • AWS Access Key ID
  • AWS Secret Key
  • Associate Tag (Amazon affiliate tag)

Steps
-----
1. Obtain PA‑API credentials from https://affiliate-program.amazon.com/.
2. Run:  streamlit run amazon_bulk_upc_streamlit.py
3. Paste or upload your product list, set credentials in the sidebar, click **Search**.
4. Download the UPC results as CSV/Excel.

Notes
-----
• Max 1 request/sec & 8640 requests/day (PA‑API limit).  
  The slider lets you adjust delay between calls.
• UPC/EAN is returned if Amazon exposes it via `item_info.external_ids.upc`/
  `ean_list`. Some items may not list a UPC; in that case you'll see “N/A”.
• For large batches consider running overnight (or cache results).

"""

import io, time, pandas as pd, streamlit as st
from datetime import datetime
from amazon_paapi import AmazonAPI, AmazonException

# Streamlit page settings
st.set_page_config(page_title="Amazon Bulk UPC Lookup", layout="wide")
st.title("📦 Amazon Bulk UPC Lookup")

# Sidebar: credentials & settings
st.sidebar.header("Amazon PA‑API Credentials")
access_key = st.sidebar.text_input("Access Key ID", type="password")
secret_key = st.sidebar.text_input("Secret Access Key", type="password")
associate_tag = st.sidebar.text_input("Associate Tag")
delay_sec = st.sidebar.number_input("Delay between requests (sec)", 0.0, 2.0, 1.0, 0.1)
max_items = st.sidebar.slider("Items to examine per query", 1, 5, 1)

# Input area
st.subheader("1️⃣  Provide product list")
col1, col2 = st.columns(2)
with col1:
    prod_text = st.text_area("Paste product descriptions (one per line)", height=250)
with col2:
    up_file = st.file_uploader("…or upload CSV/Excel with a Product column", type=["csv", "xls", "xlsx"])

products = []

if prod_text.strip():
    products += [p.strip() for p in prod_text.strip().splitlines() if p.strip()]

if up_file:
    try:
        if up_file.name.lower().endswith(".csv"):
            df_in = pd.read_csv(up_file, dtype=str, engine="python", on_bad_lines="skip")
        else:
            df_in = pd.read_excel(up_file, dtype=str)
        prod_col = next((c for c in df_in.columns if "product" in c.lower() or "description" in c.lower()), None)
        if prod_col:
            products += df_in[prod_col].dropna().astype(str).tolist()
            st.success(f"{df_in.shape[0]} rows loaded; {df_in[prod_col].notna().sum()} products detected.")
        else:
            st.error("No 'product' column found.")
    except Exception as e:
        st.error(f"File read error: {e}")

# Deduplicate while preserving order
seen = set()
prod_unique = [p for p in products if not (p in seen or seen.add(p))]

st.write(f"**Total unique queries:** {len(prod_unique)}")

def get_upc_from_item(item):
    """Return UPC/EAN if present in PA‑API item, else ''"""
    try:
        ex_ids = item.item_info.external_ids
        if ex_ids and ex_ids.upc_list:
            return ex_ids.upc_list[0]
        if ex_ids and ex_ids.ean_list:
            return ex_ids.ean_list[0]
    except AttributeError:
        pass
    return ""

# Run lookup
if prod_unique and st.button("🔍 Search Amazon"):
    if not (access_key and secret_key and associate_tag):
        st.error("Please enter all PA‑API credentials in the sidebar.")
        st.stop()

    amazon = AmazonAPI(access_key, secret_key, associate_tag, "US")
    rows = []
    bar = st.progress(0.0)

    for idx, query in enumerate(prod_unique, start=1):
        entry = {
            "Product_Query": query,
            "UPC": "",
            "ASIN": "",
            "Title": "",
            "Brand": "",
            "Score": 0.0,
            "Status": "NOT FOUND",
        }
        try:
            results = amazon.search_items(keywords=query, search_index="All",
                                          item_count=max_items, resources=["ItemInfo.ExternalIds",
                                                                           "ItemInfo.Title",
                                                                           "ItemInfo.ProductInfo",
                                                                           "ItemInfo.ByLineInfo"])
            if results.items:
                best_item = results.items[0]
                upc = get_upc_from_item(best_item)
                entry.update(
                    UPC=upc if upc else "N/A",
                    ASIN=best_item.asin,
                    Title=best_item.item_info.title.display_value,
                    Brand=(best_item.item_info.by_line_info.brand.display_value
                           if best_item.item_info.by_line_info and best_item.item_info.by_line_info.brand else ""),
                    Score=results.search_results.total_result_count,
                    Status="OK" if upc else "NO UPC",
                )
        except AmazonException as e:
            entry["Status"] = f"ERROR: {e}"

        rows.append(entry)
        bar.progress(idx / len(prod_unique))
        time.sleep(delay_sec)

    bar.empty()
    df_out = pd.DataFrame(rows)
    st.dataframe(df_out, use_container_width=True)
    st.success("Lookup finished!")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_b = df_out.to_csv(index=False).encode()
    st.download_button("⬇️ CSV", csv_b, file_name=f"amazon_upc_{ts}.csv", mime="text/csv")

    excel_io = io.BytesIO()
    with pd.ExcelWriter(excel_io, engine="openpyxl") as w:
        df_out.to_excel(w, index=False, sheet_name="Results")
    st.download_button("⬇️ Excel", excel_io.getvalue(),
                       file_name=f"amazon_upc_{ts}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
