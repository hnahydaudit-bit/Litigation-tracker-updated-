import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re

# 🔑 Configure Gemini (API key from Streamlit Cloud secrets)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 🎨 Page setup
st.set_page_config(page_title="LITIGATION TRACKER", page_icon="📂")
st.title("📂 LITIGATION TRACKER")

# ---------- Helper Functions ----------

def extract_text_from_pdf(file_path):
    """Extract text from PDF using PyMuPDF."""
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def extract_with_ai(batch_texts):
    """Send all extracted texts at once to Gemini and ask for structured fields."""
    prompt = f"""
You are an expert in GST litigation and departmental notices.

For EACH document below, extract the following fields and return
a JSON ARRAY (list of objects).

Required keys for EACH object:

- Entity Name
- GSTIN
- Type of Notice / Order (System Update)
- Description
- Issues & Amounts
- Ref ID
- Date Of Issuance
- Due Date
- Case ID
- Notice Type (ASMT-10 or ADT - 01 / SCN or Appeal)
- Financial Year
- Total Demand Amount as per Notice
- DIN No
- Officer Name
- Designation
- Area Division
- Tax Amount
- Interest
- Penalty
- Source  (file name)

VERY IMPORTANT RULES for "Issues & Amounts":
- Extract ALL issues / discrepancies / allegations mentioned in the notice
- Each issue must be on a NEW LINE
- Mention ONLY the TAX amount for each issue (ignore interest & penalty)
- If tax amount is not mentioned for an issue, write "Amount not specified"
- Do NOT merge multiple issues
- Do NOT summarise or paraphrase issues
- Format strictly as:

Issue 1 – <issue description> – ₹amount  
Issue 2 – <issue description> – ₹amount  

Other Rules:
- If a field is not found, leave it blank
- Do NOT assume or guess values
- Return ONLY valid JSON (no explanations, no markdown)

Documents:
{json.dumps(batch_texts, indent=2)}
"""

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    resp = model.generate_content(prompt)

    # Extract raw text response
    data = resp.candidates[0].content.parts[0].text

    # Extract JSON array safely
    match = re.search(r"\[.*\]", data, re.DOTALL)
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

    # Collect all texts first
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

    # One AI call for all PDFs
    results = extract_with_ai(batch_texts)

    # Fixed column order (UPDATED)
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
        "Notice Type (ASMT-10 or ADT - 01 / SCN or Appeal)",
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

    # ✅ Success message
    st.success("🎉 Your Excel file is ready!")

    st.dataframe(df, use_container_width=True)

    # Download Excel
    out_path = "litigation_tracker_output.xlsx"
    df.to_excel(out_path, index=False)

    with open(out_path, "rb") as f:
        st.download_button(
            label="📥 Download your Excel",
            data=f,
            file_name="Litigation_Tracker_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
