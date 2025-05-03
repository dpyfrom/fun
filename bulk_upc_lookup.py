
# bulk_upc_lookup.py

"""
Streamlit app – Bulk UPC Lookup

Features
--------
• Paste a list of UPC codes (comma / space / newline‑separated) **or** upload a CSV / Excel file.  
• Uses the BarcodeLookup API to retrieve the first matching product for each UPC.  
• Shows a progress bar while querying and outputs a table with:
    UPC • API title • brand • category • status
• Download the results as Excel or CSV.

Requirements
------------
pip install streamlit pandas requests openpyxl

Run
----
streamlit run bulk_upc_lookup.py
"""

import io, re, time, requests, pandas as pd, streamlit as st
from datetime import datetime

st.set_page_config(page_title="Bulk UPC Lookup", layout="wide")
st.title("🔎 Bulk UPC Lookup")

DEFAULT_KEY = "wnwemdtewjdp2gjtpqgneqe8o2u9x5"
API_URL = "https://api.barcodelookup.com/v3/products"

# Sidebar
st.sidebar.header("Settings")
api_key = st.sidebar.text_input("BarcodeLookup API Key", value=DEFAULT_KEY, type="password")
delay = st.sidebar.number_input("Delay between requests (seconds)", min_value=0.0, max_value=5.0, value=0.25, step=0.05)
st.sidebar.markdown("—")

# Input area
st.subheader("1️⃣  Provide UPC list")

col1, col2 = st.columns(2)
with col1:
    upc_text = st.text_area("Paste UPC codes here (any separator)", height=250)
with col2:
    uploaded_file = st.file_uploader("...or upload CSV/Excel containing a UPC column", type=["csv", "xls", "xlsx"])

def extract_upcs(text: str):
    """Return a list of 8‑14 digit numbers found in text."""
    return re.findall(r"\b\d{8,14}\b", text)

# Load UPCs
upc_list = []

if upc_text.strip():
    upc_list.extend(extract_upcs(upc_text))

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df_in = pd.read_csv(uploaded_file, dtype=str, engine="python", on_bad_lines="skip")
        else:
            df_in = pd.read_excel(uploaded_file, dtype=str)
        # Look for a column containing "upc"
        upc_col = None
        for col in df_in.columns:
            if "upc" in col.lower():
                upc_col = col
                break
        if upc_col:
            upc_list.extend(df_in[upc_col].dropna().astype(str).tolist())
            st.success(f"Loaded {len(df_in)} rows from {uploaded_file.name}. Found {df_in[upc_col].notna().sum()} UPCs.")
        else:
            st.warning("No column containing 'UPC' found in the uploaded file.")
    except Exception as e:
        st.error(f"Error reading file: {e}")

# Remove duplicates while preserving order
seen = set()
upc_unique = []
for u in upc_list:
    if u not in seen:
        seen.add(u)
        upc_unique.append(u)

st.write(f"**Total UPCs to query:** {len(upc_unique)}")

# Query button
if upc_unique and st.button("🔍 Look up UPCs"):
    rows = []
    progress = st.progress(0.0, text="Starting…")
    for idx, upc in enumerate(upc_unique, start=1):
        entry = {"UPC": upc, "API_Title": "", "Brand": "", "Category": "", "Status": ""}
        try:
            resp = requests.get(API_URL, params=dict(barcode=upc, key=api_key), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            prods = data.get("products", [])
            if prods:
                p = prods[0]
                entry["API_Title"] = p.get("title", "")
                entry["Brand"] = p.get("brand", "")
                entry["Category"] = p.get("category", "")
                entry["Status"] = "OK"
            else:
                entry["Status"] = "NOT FOUND"
        except Exception as e:
            entry["Status"] = f"ERROR: {e}"
        rows.append(entry)
        progress.progress(idx / len(upc_unique), text=f"{idx}/{len(upc_unique)} complete")
        time.sleep(delay)
    progress.empty()

    df_out = pd.DataFrame(rows)
    st.success("Lookup finished!")
    st.dataframe(df_out, use_container_width=True)

    # Download buttons
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_data = df_out.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv_data, file_name=f"upc_lookup_{ts}.csv", mime="text/csv")

    excel_bytes = io.BytesIO()
    with pd.ExcelWriter(excel_bytes, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Results")
    st.download_button("⬇️ Download Excel", excel_bytes.getvalue(),
                       file_name=f"upc_lookup_{ts}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
