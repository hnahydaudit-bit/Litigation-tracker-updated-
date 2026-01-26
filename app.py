import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re

# 🔑 Configure Gemini (same working model & key)
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

CRITICAL INSTRUCTIONS (FOLLOW STRICTLY):

1️⃣ Description (VERY IMPORTANT)
- Keep this SHORT and HIGH-LEVEL
- Maximum 1–2 lines
- Purpose: give an OVERALL IDEA of why the notice is issued
- Do NOT list issues here
- Do NOT include amounts here
Example:
"Notice issued for alleged ITC irregularities and turnover mismatch for FY 2021-22."

2️⃣ Issues & Amounts (EXHAUSTIVE LIST)
- Extract ALL issues / discrepancies / allegations mentioned ANYWHERE in the notice
  (including annexures, tables, explanations, observations)
- Do NOT skip minor issues
- Each issue MUST be captured separately

Formatting rules for Issues & Amounts:
- Number each issue as:
  1. Issue description – ₹amount
  2. Issue description – ₹amount
- Each issue on a NEW LINE
- Mention ONLY the TAX amount for that issue
- Ignore interest and penalty for issue-wise breakup
- If tax amount is not explicitly mentioned, write:
  "Amount not specified"
- Do NOT merge issues
- Do NOT summarise or paraphrase
- Capture wording as close to notice language as possible

3️⃣ Accuracy & formatting rules
- Tax Amount, Interest and Penalty must be extracted EXACTLY as mentioned
- Do NOT calculate, estimate, infer, round, or modify figures
- All monetary amounts MUST be formatted in INDIAN NUMBERING SYSTEM
  Example: ₹12345678 → ₹1,23,45,678
- If a value is not available, leave it blank

4️⃣ General rules
- Return ONLY valid JSON
- No explanations, no markdown, no comments

Documents:
{json.dumps(batch_texts, indent=2)}
"""

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
