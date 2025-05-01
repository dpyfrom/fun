import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="PDF to Excel Converter", layout="centered")

st.title("📄 PDF to Excel Converter")

uploaded_file = st.file_uploader("Upload a PDF file with tables", type="pdf")

if uploaded_file is not None:
    st.success("PDF uploaded successfully!")
    
    all_tables = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for i, page in enumerate(pdf.pages):
            st.write(f"🔍 Processing page {i + 1}")
            tables = page.extract_tables()
            for table in tables:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

    if all_tables:
        combined_df = pd.concat(all_tables, ignore_index=True)
        st.dataframe(combined_df)

        # Save to Excel in memory
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            combined_df.to_excel(writer, index=False, sheet_name="ExtractedData")

        st.download_button(
            label="📥 Download Excel File",
            data=excel_buffer.getvalue(),
            file_name="converted_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No tables found in the PDF.")
