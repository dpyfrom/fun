
# amazon_bulk_upc_streamlit_v2.py

"""
Streamlit app – Amazon Bulk Product → UPC Lookup
=================================================
✓ Handles **either** `amazon-paapi` **or** `python-amazon-paapi` client library.
✓ Bulk input (paste or file upload) and one‑click CSV/Excel export.

------------------------------------------------
Install one of the two PA‑API libraries first:

    pip install amazon-paapi
    #   or
    pip install python-amazon-paapi

Then run:

    streamlit run amazon_bulk_upc_streamlit_v2.py
"""

import io, time, pandas as pd, streamlit as st
from datetime import datetime

# --------- Dynamic import: support both PA‑API client libs -------------
ClientLib = None
try:
    from amazon_paapi import AmazonAPI as _AmazonAPI, AmazonException as _AmazonExc
    ClientLib = "amazon-paapi"
except ModuleNotFoundError:
    try:
        from amazon.paapi import AmazonApi as _AmazonAPI
        from amazon.paapi import AmazonApiException as _AmazonExc
        ClientLib = "python-amazon-paapi"
    except ModuleNotFoundError:
        st.error("Neither 'amazon-paapi' nor 'python-amazon-paapi' is installed. "
                 "Run `pip install amazon-paapi` or `pip install python-amazon-paapi` "
                 "and restart the app.")
        st.stop()

AmazonAPI = _AmazonAPI
AmazonException = _AmazonExc

# -------------------- Streamlit UI -------------------------------------
st.set_page_config(page_title="Amazon Bulk UPC Lookup", layout="wide")
st.title("📦 Amazon Bulk UPC Lookup")

st.sidebar.header("Amazon PA‑API Credentials")
access_key = st.sidebar.text_input("Access Key ID", type="password")
secret_key = st.sidebar.text_input("Secret Access Key", type="password")
associate_tag = st.sidebar.text_input("Associate Tag")
delay_sec = st.sidebar.number_input("Delay between requests (sec)", 0.0, 2.0, 1.0, 0.1)
max_items = st.sidebar.slider("Items to examine per query", 1, 5, 1)
st.sidebar.caption(f"Using client library: **{ClientLib}**")

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
        # auto-detect product column
        prod_col = next((c for c in df_in.columns if "product" in c.lower() or "description" in c.lower()), None)
        if prod_col:
            products += df_in[prod_col].dropna().astype(str).tolist()
            st.success(f"Loaded {df_in.shape[0]} rows; {df_in[prod_col].notna().sum()} product strings detected.")
        else:
            st.warning("No column containing 'product' or 'description' found.")
    except Exception as e:
        st.error(f"File read error: {e}")

# Deduplicate while preserving order
seen = set()
prod_unique = [p for p in products if not (p in seen or seen.add(p))]

st.write(f"**Total unique queries:** {len(prod_unique)}")

def get_upc_from_item(item):
    """Return UPC/EAN if present in PA‑API item object."""
    # amazon-paapi client
    if ClientLib == "amazon-paapi":
        ext = item.item_info.external_ids if item.item_info else None
        if ext:
            if ext.upc_list:
                return ext.upc_list[0]
            if ext.ean_list:
                return ext.ean_list[0]
    # python-amazon-paapi client – attributes are camelCase
    elif ClientLib == "python-amazon-paapi":
        ext = getattr(item.item_info, "external_ids", None)
        if ext:
            upc_list = getattr(ext, "upc_list", None)
            if upc_list:
                return upc_list[0]
            ean_list = getattr(ext, "ean_list", None)
            if ean_list:
                return ean_list[0]
    return ""

if prod_unique and st.button("🔍 Search Amazon"):
    if not (access_key and secret_key and associate_tag):
        st.error("Please fill in all PA‑API credentials.")
        st.stop()

    # Instantiate client
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
            "Status": "NOT FOUND",
        }
        try:
            results = amazon.search_items(
                keywords=query,
                search_index="All",
                item_count=max_items,
                resources=[
                    "ItemInfo.ExternalIds",
                    "ItemInfo.Title",
                    "ItemInfo.ByLineInfo",
                ],
            )
            items = results.items if hasattr(results, "items") else results
            if items:
                best = items[0]
                entry["ASIN"] = best.asin
                entry["Title"] = best.item_info.title.display_value if best.item_info and best.item_info.title else ""
                entry["Brand"] = (
                    best.item_info.by_line_info.brand.display_value
                    if best.item_info and best.item_info.by_line_info and best.item_info.by_line_info.brand
                    else ""
                )
                upc = get_upc_from_item(best)
                entry["UPC"] = upc if upc else "N/A"
                entry["Status"] = "OK" if upc else "NO UPC"
        except AmazonException as e:
            entry["Status"] = f"ERROR: {str(e)[:120]}"
        except Exception as e:
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
