
# product_to_upc_lookup.py

"""
Streamlit app – Bulk PRODUCT ➜ UPC Lookup

Features
--------
• Paste product descriptions one‑per‑line **or** upload CSV/Excel with a 'Product' column.  
• Queries BarcodeLookup API search endpoint to fetch best‑match UPC.  
• Shows status & optional match‐score.  
• Export results to CSV or Excel.

Setup
-----
pip install streamlit pandas requests openpyxl

Run
---
streamlit run product_to_upc_lookup.py
"""

import io, re, time, requests, pandas as pd, streamlit as st
from datetime import datetime
from difflib import SequenceMatcher

st.set_page_config(page_title="Product → UPC Bulk Lookup", layout="wide")
st.title("🔁 Product → UPC Bulk Lookup")

DEFAULT_KEY = "wnwemdtewjdp2gjtpqgneqe8o2u9x5"
API_URL = "https://api.barcodelookup.com/v3/products"

# Sidebar
st.sidebar.header("Settings")
api_key = st.sidebar.text_input("BarcodeLookup API Key", value=DEFAULT_KEY, type="password")
delay = st.sidebar.number_input("Delay between requests (seconds)", min_value=0.0, max_value=5.0, value=0.4, step=0.05)
results_per_query = st.sidebar.slider("Results fetched per product", 1, 10, 3)

# Input area
st.subheader("1️⃣  Provide product list")

col1, col2 = st.columns(2)
with col1:
    prod_text = st.text_area("Paste product descriptions (one per line)", height=250)
with col2:
    up_file = st.file_uploader("…or upload CSV/Excel with a 'Product' column", type=["csv", "xls", "xlsx"])

products = []

if prod_text.strip():
    products.extend([p.strip() for p in prod_text.strip().splitlines() if p.strip()])

if up_file is not None:
    try:
        if up_file.name.lower().endswith(".csv"):
            df_in = pd.read_csv(up_file, dtype=str, engine="python", on_bad_lines="skip")
        else:
            df_in = pd.read_excel(up_file, dtype=str)
        prod_col = None
        for col in df_in.columns:
            if "product" in col.lower() or "description" in col.lower():
                prod_col = col
                break
        if prod_col:
            products.extend(df_in[prod_col].dropna().astype(str).tolist())
            st.success(f"Loaded {len(df_in)} rows from {up_file.name}. Found {df_in[prod_col].notna().sum()} products.")
        else:
            st.warning("No product/description column found in the uploaded file.")
    except Exception as e:
        st.error(f"Error reading file: {e}")

# Deduplicate (preserve order)
seen = set()
prod_unique = []
for p in products:
    if p not in seen:
        seen.add(p)
        prod_unique.append(p)

st.write(f"**Total products to query:** {len(prod_unique)}")

def best_match(title, query):
    """Return a similarity ratio 0..1 between API title and query."""
    return SequenceMatcher(None, query.lower(), title.lower()).ratio()

# Query button
if prod_unique and st.button("🔍 Find UPCs"):
    rows = []
    progress = st.progress(0.0, text="Starting…")
    for idx, query in enumerate(prod_unique, start=1):
        entry = {
            "Product_Query": query,
            "UPC": "",
            "API_Title": "",
            "Brand": "",
            "Category": "",
            "Score": 0.0,
            "Status": "",
        }
        try:
            resp = requests.get(
                API_URL,
                params=dict(search=query, key=api_key, formatted="n", page=1),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            prods = data.get("products", [])[:results_per_query]
            if prods:
                # pick best by similarity
                best = max(prods, key=lambda p: best_match(p.get("title", ""), query))
                entry["UPC"] = best.get("barcode", "")
                entry["API_Title"] = best.get("title", "")
                entry["Brand"] = best.get("brand", "")
                entry["Category"] = best.get("category", "")
                entry["Score"] = round(best_match(best.get("title", ""), query), 3)
                entry["Status"] = "OK"
            else:
                entry["Status"] = "NOT FOUND"
        except Exception as e:
            entry["Status"] = f"ERROR: {e}"
        rows.append(entry)
        progress.progress(idx / len(prod_unique), text=f"{idx}/{len(prod_unique)} complete")
        time.sleep(delay)
    progress.empty()

    df_out = pd.DataFrame(rows)
    st.success("Lookup finished!")
    st.dataframe(df_out, use_container_width=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_bytes = df_out.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv_bytes, file_name=f"prod2upc_{ts}.csv", mime="text/csv")

    excel_io = io.BytesIO()
    with pd.ExcelWriter(excel_io, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Results")
    st.download_button(
        "⬇️ Download Excel",
        excel_io.getvalue(),
        file_name=f"prod2upc_{ts}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
