import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re

# 🔑 Configure Gemini (USE SAME MODEL AS WORKING PROJECT)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 🎨 Page setup
st.set_page_config(page_title="LITIGATION TRACKER", page_icon="📂")
st.title("📂 LITIGATION TRACKER")

# ---------- Helper Functions ----------

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def extract_with_ai(batch_texts):
    prompt = f"""
You are an expert in GST litigation notices.

For EACH document below, return ONE JSON object.
Return a JSON ARRAY (list of objects).

Fields required:

- Entity Name
- GSTIN
- Type of Notice / Order (System Update)
- Description
- Issues & Amounts
- Ref ID
- Date Of Issuance
- Due Date
- Case ID
- Notice Type (ASMT-10 or ADT-01 / SCN / Appeal)
- Financial Year
- Total Demand Amount as per Notice
- DIN No
- Officer Name
- Designation
- Area Division
- Tax Amount
- Interest
- Penalty
- Source

Rules for "Issues & Amounts":
- List each issue mentioned in the notice
- Each issue on a new line
- Mention TAX amount for each issue if available
- Ignore interest and penalty
- If amount not available, write "Amount not specified"
- Do NOT summarise
- Do NOT merge issues

Other rules:
- If a field is not found, leave it blank
- Return ONLY valid JSON
- No explanations

Documents:
{json.dumps(batch_texts, indent=2)}
"""

    # ✅ USE THE SAME WORKING MODEL
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)

    raw_text = response.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        return []

    try:
        return json.loads(match.group(0))
    except:
        return []

# ---------- Streamlit UI ----------

uploaded_files = st.file_uploader(
    "📤 Upload your Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info("⏳ Processing... please wait.")
    batch_texts = []

    for uploaded in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        text = extract_text_from_pdf(tmp_path)

        batch_texts.append({
            "Source": uploaded.name,
            "Text": text
        })

        os.remove(tmp_path)

    results = extract_with_ai(batch_texts)

    columns = [
        "Entity Name",
        "GSTIN",
        "Type of Notice / Order (System Update)",
        "Description",
        "Issues & Amounts",
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

    st.success("🎉 Your Excel file is ready!")
    st.dataframe(df, use_container_width=True)

    out_path = "litigation_tracker_output.xlsx"
    df.to_excel(out_path, index=False)

    with open(out_path, "rb") as f:
        st.download_button(
            label="📥 Download your Excel",
            data=f,
            file_name="Litigation_Tracker_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
