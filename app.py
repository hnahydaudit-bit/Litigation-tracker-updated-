import streamlit as st
import pandas as pd
import fitz
import google.generativeai as genai
import tempfile
import os
import json
import re

# ================= CONFIG =================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(
    page_title="GST Litigation Tracker",
    page_icon="📂",
    layout="wide"
)

st.title("📂 GST Litigation Tracker")
st.caption("Accurate extraction of GST notice metadata + issues")

# ================= HELPERS =================

def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def extract_metadata(text, source):
    prompt = f"""
Extract GST notice metadata.

Return ONLY one JSON object with these keys:
- Entity Name
- GSTIN
- Type of Notice / Order (System Update)
- Description
- Ref ID
- Date Of Issuance
- Due Date
- Case ID
- Notice Type
- Financial Year
- Total Demand Amount as per Notice
- DIN No
- Officer Name
- Designation
- Area Division

Rules:
- If not found, leave blank
- No assumptions
- Return ONLY valid JSON

Document:
{text}
"""

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    raw = response.candidates[0].content.parts[0].text

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}

    try:
        data = json.loads(match.group(0))
    except:
        data = {}

    data["Source"] = source
    return data

def extract_issues_and_tax(text):
    prompt = f"""
You are a GST litigation expert.

Extract ALL issues / discrepancies / allegations in the notice.
Each issue must be separate.

For EACH issue extract:
- Issue
- Tax Amount

Rules:
- Do NOT merge issues
- Do NOT infer
- Scan annexures and tables
- Return ONLY valid JSON array

Format:
[
  {{
    "issue": "...",
    "tax_amount": "..."
  }}
]

Document:
{text}
"""

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    raw = response.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return ""

    try:
        issues = json.loads(match.group(0))
    except:
        return ""

    formatted = []
    for i, item in enumerate(issues, 1):
        issue = item.get("issue", "").strip()
        tax = item.get("tax_amount", "").strip()
        formatted.append(f"{i}. {issue}\n   Tax Amount: {tax}")

    return "\n\n".join(formatted)

# ================= UI =================

uploaded_files = st.file_uploader(
    "📤 Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info("⏳ Processing notices…")

    rows = []

    for file in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file.read())
            path = tmp.name

        text = extract_text_from_pdf(path)
        os.remove(path)

        meta = extract_metadata(text[:8000], file.name)
        issues = extract_issues_and_tax(text[:12000])

        meta["Issues & Tax Amounts"] = issues
        rows.append(meta)

    df = pd.DataFrame(rows)

    # Column order
    ordered_cols = [
        "Entity Name",
        "GSTIN",
        "Type of Notice / Order (System Update)",
        "Description",
        "Issues & Tax Amounts",
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
        "Source"
    ]

    df = df.reindex(columns=ordered_cols)

    st.success("✅ Extraction completed")
    st.dataframe(df, use_container_width=True)

    output = "GST_Litigation_Tracker.xlsx"
    df.to_excel(output, index=False)

    with open(output, "rb") as f:
        st.download_button(
            "📥 Download Excel",
            data=f,
            file_name=output,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
