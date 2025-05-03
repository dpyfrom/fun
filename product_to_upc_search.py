
# product_to_upc_search.py

"""
Improved Streamlit app – Product ➜ UPC (uses *search* parameter)

Changelog
---------
• Switches to `search=<product>` query (no 'formatted' flag) per latest API doc.  
• Option to fetch multiple pages until a UPC is found (checkbox).  
• Lets user narrow by optional brand parameter (column or sidebar input).  
• Robust JSON / HTTP error handling + 429 wait‑and‑retry.

Setup
-----
pip install streamlit pandas requests openpyxl
streamlit run product_to_upc_search.py
"""

import io, re, time, requests, pandas as pd, streamlit as st
from datetime import datetime
from difflib import SequenceMatcher

st.set_page_config(page_title="Product → UPC Lookup (Search API)", layout="wide")
st.title("🔁 Product → UPC Lookup (BarcodeLookup *search* endpoint)")

DEFAULT_KEY = "wnwemdtewjdp2gjtpqgneqe8o2u9x5"
API_URL = "https://api.barcodelookup.com/v3/products"

# Sidebar
st.sidebar.header("Settings")
api_key = st.sidebar.text_input("API Key", value=DEFAULT_KEY, type="password")
delay = st.sidebar.number_input("Delay between requests (seconds)", 0.0, 5.0, 0.4, 0.05)
pages_to_scan = st.sidebar.slider("Max pages per product", 1, 5, 1)
result_cap = st.sidebar.slider("Max results per page", 1, 10, 5)
req_brand = st.sidebar.text_input("Filter: Brand (optional)")

# Input
st.subheader("1️⃣  Enter product list")
col1, col2 = st.columns(2)
with col1:
    prod_text = st.text_area("Paste product descriptions (one per line)", height=240)
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
            st.success(f"{df_in.shape[0]} rows loaded; {df_in[prod_col].notna().sum()} products found.")
        else:
            st.error("No 'product' column detected.")
    except Exception as e:
        st.error(f"File read error: {e}")

# dedupe
seen = set()
prod_unique = [p for p in products if not (p in seen or seen.add(p))]

st.write(f"**Total unique queries:** {len(prod_unique)}")

def sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def fetch_products(query, brand_filter):
    """Generator: yield products across pages until max pages or API empty."""
    for page in range(1, pages_to_scan + 1):
        params = dict(search=query, key=api_key, page=page)
        if brand_filter:
            params["brand"] = brand_filter
        r = requests.get(API_URL, params=params, timeout=10)
        if r.status_code == 429:  # rate limit
            wait = int(r.headers.get("Retry-After", 2))
            time.sleep(wait + 0.5)
            r = requests.get(API_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        for p in data.get("products", [])[:result_cap]:
            yield p
        if not data.get("products"):
            break  # no more results

if prod_unique and st.button("🔍 Lookup UPCs"):
    rows = []
    prog = st.progress(0.0)
    for idx, q in enumerate(prod_unique, start=1):
        best_entry = {
            "Product_Query": q,
            "UPC": "",
            "API_Title": "",
            "Brand": "",
            "Category": "",
            "Score": 0.0,
            "Status": "NOT FOUND",
        }
        try:
            for p in fetch_products(q, req_brand):
                score = sim(p.get("title", ""), q)
                if score > best_entry["Score"]:
                    best_entry.update(
                        UPC=p.get("barcode", ""),
                        API_Title=p.get("title", ""),
                        Brand=p.get("brand", ""),
                        Category=p.get("category", ""),
                        Score=round(score, 3),
                        Status="OK",
                    )
                if best_entry["Score"] >= 0.95:
                    break  # good enough
        except Exception as e:
            best_entry["Status"] = f"ERROR: {e}"

        rows.append(best_entry)
        prog.progress(idx / len(prod_unique))
        time.sleep(delay)
    prog.empty()

    df_out = pd.DataFrame(rows)
    st.dataframe(df_out, use_container_width=True)
    st.success("Done!")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_b = df_out.to_csv(index=False).encode()
    st.download_button("⬇️ CSV", csv_b, file_name=f"prod2upc_{ts}.csv", mime="text/csv")
    xio = io.BytesIO()
    with pd.ExcelWriter(xio, engine="openpyxl") as w:
        df_out.to_excel(w, index=False, sheet_name="Results")
    st.download_button("⬇️ Excel", xio.getvalue(), file_name=f"prod2upc_{ts}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
