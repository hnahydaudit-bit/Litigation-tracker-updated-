import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re

# 🔑 Configure Gemini API
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 🎨 Page setup
st.set_page_config(page_title="LITIGATION TRACKER", page_icon="📂")
st.title("📂 GST LITIGATION TRACKER")

# ---------- Helper Functions ----------

def extract_text_from_pdf(file_path):
    """Extract text from PDF using PyMuPDF"""
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()


def extract_with_ai(batch_texts):
    """Extract litigation details including issue-wise amounts"""

    prompt = f"""
You are a senior GST litigation expert.

For EACH document, extract details and return a JSON ARRAY.
Each document must be ONE JSON object.

Fields to extract:
- Entity Name
- GSTIN
- Type of Notice / Order
- Description (brief 2–3 line summary)
- Issues & Amounts (Issue-wise)
- Ref ID
- Date Of Issuance
- Due Date
- Case ID
- Notice Type
- Financial Year
- Total Demand Amount
- DIN No
- Officer Name
- Designation
- Area Division
- Tax Amount
- Interest
- Penalty
- Source

🔥 CRITICAL INSTRUCTION FOR "Issues & Amounts (Issue-wise)" 🔥
- Identify EACH issue / allegation / discrepancy
- Extract corresponding amount for EACH issue
- Return ALL issues in ONE STRING using this EXACT format:

1. <Issue description> – ₹<amount>
2. <Issue description> – ₹<amount>

- If issue-wise breakup is NOT available, write:
"Issue-wise breakup not mentioned in notice"

Rules:
- Do NOT guess or invent data
- Leave blank if genuinely unavailable
- Return ONLY valid JSON
- No explanations, no markdown

Documents:
{json.dumps(batch_texts, indent=2)}
"""

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)

    try:
        raw_text = response.candidates[0].content.parts[0].text
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        return json.loads(match.group(0)) if match else []
    except Exception:
        return []

# ---------- Streamlit UI ----------

uploaded_files = st.file_uploader(
    "📤 Upload GST Notice / Order PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info("⏳ Processing notices… please wait")

    batch_texts = []

    for uploaded in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        extracted_text = extract_text_from_pdf(tmp_path)
        batch_texts.append({
            "Source": uploaded.name,
            "Text": extracted_text[:6000]  # safety limit
        })

        os.remove(tmp_path)

    results = extract_with_ai(batch_texts)

    # ✅ Column order (Issues & Amounts AFTER Description)
    columns = [
        "Entity Name",
        "GSTIN",
        "Type of Notice / Order",
        "Description",
        "Issues & Amounts (Issue-wise)",
        "Ref ID",
        "Date Of Issuance",
        "Due Date",
        "Case ID",
        "Notice Type",
        "Financial Year",
        "Total Demand Amount",
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

    # Download Excel
    output_file = "Litigation_Tracker_Output.xlsx"
    df.to_excel(output_file, index=False)

    with open(output_file, "rb") as f:
        st.download_button(
            label="📥 Download Excel",
            data=f,
            file_name="Litigation_Tracker_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
