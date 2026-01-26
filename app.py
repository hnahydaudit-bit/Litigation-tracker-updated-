import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json

# ================== CONFIG ==================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

generation_config = {
    "temperature": 0,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

# ✅ Create model ONCE (NO safety_settings → avoids KeyError)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

st.set_page_config(
    page_title="GST Litigation Tracker",
    page_icon="📂",
    layout="wide"
)

st.title("📂 GST Litigation Tracker")

# ================== PDF TEXT EXTRACTION ==================
def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

# ================== AI EXTRACTION ==================
def extract_notice_details(text, source):
    prompt = f"""
You are a GST litigation expert.

Extract details ONLY from the notice text below.
Do NOT assume, infer, or fabricate any value.
If information is not available, leave it blank.

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

Notice Text:
{text}
"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            raise ValueError("No JSON in response")

        return json.loads(raw[start:end + 1])

    except Exception:
        st.warning(f"⚠️ AI extraction failed for {source}")
        return {}

# ================== UI ==================
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

        df.to_excel("Litigation_Tracker_Output.xlsx", index=False)

        with open("Litigation_Tracker_Output.xlsx", "rb") as f:
            st.download_button(
                "📥 Download Excel",
                f,
                file_name="Litigation_Tracker_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("No structured data could be extracted from the uploaded PDFs.")
