import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re

# ---------------- CONFIG ----------------
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(
    page_title="Litigation Tracker",
    page_icon="📂",
    layout="wide"
)

st.title("📂 GST Litigation Tracker")

# ---------------- PDF TEXT EXTRACTION ----------------
def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

# ---------------- AI EXTRACTION (SINGLE CALL) ----------------
def extract_notice_details(text, source):
    prompt = f"""
You are a GST litigation expert.

Extract details ONLY from the notice text provided.
Do NOT assume or fabricate anything.
If a field is not available, leave it blank.

Return ONLY valid JSON in the following structure:

{{
  "Entity Name": "",
  "GSTIN": "",
  "Type of Notice / Order (System Update)": "",
  "Description": "",
  "Issues & Tax Amounts": "",
  "Ref ID": "",
  "Date Of Issuance": "",
  "Due Date": "",
  "Case ID": "",
  "Notice Type (ASMT-10 or ADT-01 / SCN / Appeal)": "",
  "Financial Year": "",
  "Total Demand Amount as per Notice": "",
  "DIN No": "",
  "Officer Name": "",
  "Designation": "",
  "Area Division": "",
  "Tax Amount": "",
  "Interest": "",
  "Penalty": "",
  "Source": "{source}"
}}

IMPORTANT RULES for "Issues & Tax Amounts":
- List ALL issues / discrepancies / allegations mentioned in the notice
- Each issue on a new line
- Mention corresponding TAX amount if available
- Do NOT include interest or penalty
- Do NOT merge issues
- Format exactly like:

Issue 1 – <short issue description> – ₹amount  
Issue 2 – <short issue description> – ₹amount

Notice Text:
{text}
"""

    model = genai.GenerativeModel("models/gemini-1.5-flash")
    response = model.generate_content(prompt)

    raw = response.text
    match = re.search(r"\{.*\}", raw, re.DOTALL)

    if not match:
        return {}

    try:
        return json.loads(match.group(0))
    except:
        return {}

# ---------------- UI ----------------
uploaded_files = st.file_uploader(
    "📤 Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

results = []

if uploaded_files:
    with st.spinner("Extracting details..."):
        for file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                path = tmp.name

            text = extract_text_from_pdf(path)
            os.remove(path)

            if text:
                # HARD LIMIT to avoid quota issues
                data = extract_notice_details(text[:6000], file.name)
                if data:
                    results.append(data)

    if results:
        columns = [
            "Entity Name",
            "GSTIN",
            "Type of Notice / Order (System Update)",
            "Description",
            "Issues & Tax Amounts",
            "Ref ID",
            "Date Of Issuance",
            "Due Date",
            "Case ID",
            "Notice Type (ASMT-10 or ADT-01 / SCN / Appeal)",
            "Financial Year",
            "Total Demand Amount as per Notice",
            "DIN No",
            "Officer Name",
            "Designation",
            "Area Division",
            "Tax Amount",
            "Interest",
            "Penalty",
            "Source"
        ]

        df = pd.DataFrame(results, columns=columns)

        st.success("✅ Extraction completed")
        st.dataframe(df, use_container_width=True)

        # Download Excel
        out_file = "Litigation_Tracker_Output.xlsx"
        df.to_excel(out_file, index=False)

        with open(out_file, "rb") as f:
            st.download_button(
                "📥 Download Excel",
                f,
                file_name="Litigation_Tracker_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

