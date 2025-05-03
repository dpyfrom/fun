
# streamlit_upc_verifier.py

"""
Streamlit app to verify a list of UPC codes using the BarcodeLookup API.
Steps:
    1. Upload a CSV (or paste table) with columns: Description, Provided_UPC
    2. Enter your API key (prefilled for convenience)
    3. Click "Verify" – the app calls the API, shows progress, and displays a table
    4. Download the results as an Excel file

Requirements:
    pip install streamlit pandas requests openpyxl
Run locally with:
    streamlit run streamlit_upc_verifier.py
"""

import re, time, io, requests, pandas as pd, streamlit as st
from datetime import datetime

st.set_page_config(page_title="UPC Verifier", layout="wide")

st.title("🛒 UPC Code Verifier")

# Sidebar controls
st.sidebar.header("Settings")

# API key input (prefilled but editable)
api_key = st.sidebar.text_input(
    "BarcodeLookup API Key",
    value="wnwemdtewjdp2gjtpqgneqe8o2u9x5",
    type="password",
)

rate_delay = st.sidebar.number_input(
    "Delay between requests (seconds)",
    min_value=0.0,
    max_value=5.0,
    value=0.35,
    step=0.05,
    help="Increase if you hit API rate limits.",
)

uploaded_file = st.file_uploader(
    "Upload CSV with two columns: **Description**, **Provided_UPC**",
    type=["csv"],
)

def words(s: str):
    return re.findall(r"[A-Za-z0-9']+", s.lower())

API_URL = "https://api.barcodelookup.com/v3/products"

def verify_row(row, key, delay):
    upc = str(row["Provided_UPC"]).strip()
    row["API_Product_Name"] = ""
    row["Verified_UPC"] = ""
    row["Match"] = False

    if not upc.isdigit():
        return row

    try:
        resp = requests.get(API_URL, params=dict(barcode=upc, key=key), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        products = data.get("products", [])
        if products:
            title = products[0].get("title", "")
            row["API_Product_Name"] = title
            row["Verified_UPC"] = upc
            descr_words = set(words(row["Description"]))
            title_words = set(words(title))
            row["Match"] = descr_words.issubset(title_words)
    except Exception as e:
        row["API_Product_Name"] = f"ERROR: {e}"

    time.sleep(delay)
    return row

if uploaded_file is not None:
    df_input = pd.read_csv(uploaded_file, dtype=str).fillna("")
    st.write("### Preview of uploaded data", df_input.head())

    if st.button("🔍 Verify UPCs"):
        progress = st.progress(0.0, text="Starting verification…")
        results = []
        total = len(df_input)

        for i, (_, row) in enumerate(df_input.iterrows(), start=1):
            row = verify_row(row, api_key, rate_delay)
            results.append(row)
            progress.progress(i / total, text=f"Processing {i}/{total}")

        progress.empty()
        df_out = pd.DataFrame(results)
        st.success("Verification complete!")

        st.write("### Results", df_out)

        # Prepare Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_out.to_excel(writer, sheet_name="Verified", index=False)
        excel_data = output.getvalue()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Excel",
            data=excel_data,
            file_name=f"verified_upc_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.markdown(
    """---  
    **Tip:** If your list exceeds the free API rate limit (≈100–150 requests/day),  
    split the CSV into smaller chunks or use a larger `Delay between requests`.  
    """
)
