import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re

# 🔑 Configure Gemini
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
You are a GST litigation expert AI.

For each document, extract details STRICTLY from the text.
Do NOT guess or create dummy data.
If something is not available, leave it blank.

Return a JSON ARRAY. Each object must contain:

- Entity Name
- GSTIN
- Type of Notice / Order (System Update)
- Description (1–2 line overall summary)
- Issues & Amounts (Point-wise)  
  → List each issue separately in short points  
  → Mention corresponding Tax / Interest / Penalty for each issue  
  → Keep it readable and concise
- Ref ID
- Date Of Issuance
- Due Date
- Case ID
- Notice Type (ASMT-10 / ADT-01 / SCN / Appeal etc.)
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

IMPORTANT:
- Issues & Amounts must be factual and extracted from notice
- Use numbered points
- Return ONLY valid JSON
- No explanation text

DOCUMENTS:
{json.dumps(batch_texts, indent=2)}
"""

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)

    text = response.candidates[0].content.parts[0].text
    match = re.search(r"\[.*\]", text, re.DOTALL)

    if not match:
        return []

    try:
        return json.loads(match.group(0))
    except:
        return []


# ---------- Streamlit UI ----------

uploaded_files = st.file_uploader(
    "📤 Upload your GST Notice PDFs",
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
        os.remove(tmp_path)

        if text.strip():
            batch_texts.append({
                "Source": uploaded.name,
                "Text": text[:6000]  # safe limit
            })

    results = extract_with_ai(batch_texts)

    columns = [
        "Entity Name",
        "GSTIN",
        "Type of Notice / Order (System Update)",
        "Description",
        "Issues & Amounts (Point-wise)",
        "Ref ID",
        "Date Of Issuance",
        "Due Date",
        "Case ID",
        "Notice Type",
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

    st.success("🎉 Excel summary generated successfully")
    st.dataframe(df, use_container_width=True)

    out_path = "litigation_tracker_output.xlsx"
    df.to_excel(out_path, index=False)

    with open(out_path, "rb") as f:
        st.download_button(
            "📥 Download Excel Summary",
            data=f,
            file_name="Litigation_Tracker_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
