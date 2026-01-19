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
    page_title="GST Litigation Tracker",
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

# ---------------- AI EXTRACTION (ONE CALL PER PDF) ----------------
def extract_notice_details(text, source):
    prompt = f"""
You are a GST litigation expert.

Extract details ONLY from the notice text below.
Do NOT assume, infer, or fabricate any value.
If information is not available, leave it blank.

Return ONLY valid JSON in the exact structure:

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

RULES for "Issues & Tax Amounts":
- Extract ALL issues / discrepancies / allegations mentioned
- Each issue must be on a NEW LINE
- Mention only TAX amount (ignore interest & penalty)
- Do NOT merge issues
- Do NOT summarise
- If amount not available, mention issue without amount
- Format strictly as:

Issue 1 – <issue description> – ₹amount  
Issue 2 – <issue description> – ₹amount

Notice Text:
{text}
"""

    model = genai.GenerativeModel("gemini-pro")
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
    with st.spinner("Extracting notice details..."):
        for file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name

            text = extract_text_from_pdf(tmp_path)
            os.remove(tmp_path)

            if text:
                # HARD LIMIT → prevents quota issues
                extracted = extract_notice_details(text[:6000], file.name)
                if extracted:
                    results.append(extracted)

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

        st.success("✅ Extraction completed successfully")
        st.dataframe(df, use_container_width=True)

        output_file = "Litigation_Tracker_Output.xlsx"
        df.to_excel(output_file, index=False)

        with open(output_file, "rb") as f:
            st.download_button(
                "📥 Download Excel",
                f,
                file_name="Litigation_Tracker_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


