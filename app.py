import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json

# ================= CONFIG =================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

generation_config = {
    "temperature": 0.2,   # allow light reasoning
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

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

# ================= PDF TEXT EXTRACTION =================
def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

# 🔧 CLEAN TEXT (CRITICAL)
def clean_text(text):
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text

# ================= AI EXTRACTION =================
def extract_notice_details(text, source):
    prompt = f"""
You are a GST litigation expert.

Extract details from the notice text below.
Extract values if they are clearly mentioned or reasonably identifiable.
Do NOT guess missing information.

Return ONLY valid JSON in this structure:

{{
  "Entity Name": "",
  "GSTIN": "",
  "Notice Type": "",
  "Section / Rule": "",
  "Financial Year": "",
  "Date Of Issuance": "",
  "Due Date": "",
  "Tax Amount": "",
  "Interest": "",
  "Penalty": "",
  "Quick Summary": "",
  "Source": "{source}"
}}

Quick Summary:
- 1–2 lines explaining why the notice is issued

Notice Text:
{text}
"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            raise ValueError("No JSON")

        return json.loads(raw[start:end + 1])

    except Exception:
        return {}

# ================= UI =================
uploaded_files = st.file_uploader(
    "📤 Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

results = []

# Empty row template (never allow blank output)
def empty_row(source):
    return {
        "Entity Name": "",
        "GSTIN": "",
        "Notice Type": "",
        "Section / Rule": "",
        "Financial Year": "",
        "Date Of Issuance": "",
        "Due Date": "",
        "Tax Amount": "",
        "Interest": "",
        "Penalty": "",
        "Quick Summary": "Manual review required",
        "Source": source
    }

if uploaded_files:
    with st.spinner("Extracting notice details..."):
        for file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name

            raw_text = extract_text_from_pdf(tmp_path)
            os.remove(tmp_path)

            if raw_text:
                text = clean_text(raw_text)
                extracted = extract_notice_details(text[:7000], file.name)

                if not extracted:
                    st.warning(f"⚠️ Manual review required for {file.name}")
                    extracted = empty_row(file.name)

                results.append(extracted)

            else:
                st.warning(f"⚠️ No readable text in {file.name}")
                results.append(empty_row(file.name))

# ================= OUTPUT =================
if results:
    columns = [
        "Entity Name",
        "GSTIN",
        "Notice Type",
        "Section / Rule",
        "Financial Year",
        "Date Of Issuance",
        "Due Date",
        "Tax Amount",
        "Interest",
        "Penalty",
        "Quick Summary",
        "Source"
    ]

    df = pd.DataFrame(results, columns=columns)

    st.success("✅ Processing completed")
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
