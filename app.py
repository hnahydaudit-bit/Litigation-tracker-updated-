import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
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
st.caption("AI-assisted extraction of Issues & Tax Amounts from GST Notices")

# ================= HELPERS =================

def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def extract_issues_and_tax(text, source_name):
    """
    Extract ALL issues and corresponding tax amounts.
    """
    prompt = f"""
You are a GST litigation expert.

Extract ALL issues / allegations / discrepancies mentioned in the notice below.
Each issue must be separate (do NOT merge).
Scan the entire document including annexures, tables and statements.

For EACH issue, extract:
- Issue (short, clear description)
- Tax Amount related ONLY to that issue

Rules:
- Do NOT summarise or club issues
- Do NOT infer amounts
- If amount not mentioned for an issue, leave it blank
- Return ONLY valid JSON
- Currency should be exactly as in notice

Return format (JSON array):
[
  {{
    "issue": "...",
    "tax_amount": "..."
  }}
]

Document text:
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

    # Format into ONE cell
    formatted = []
    for idx, item in enumerate(issues, 1):
        issue = item.get("issue", "").strip()
        tax = item.get("tax_amount", "").strip()
        line = f"{idx}. {issue}\n   Tax Amount: {tax}"
        formatted.append(line)

    return "\n\n".join(formatted)

# ================= UI =================

uploaded_files = st.file_uploader(
    "📤 Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info("⏳ Extracting issues and tax amounts… Please wait")

    records = []

    for file in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file.read())
            path = tmp.name

        text = extract_text_from_pdf(path)
        os.remove(path)

        issues_tax = extract_issues_and_tax(text[:12000], file.name)

        records.append({
            "Source File": file.name,
            "Issues & Tax Amounts": issues_tax
        })

    df = pd.DataFrame(records)

    st.success("✅ Extraction completed")

    st.dataframe(df, use_container_width=True)

    # Excel download
    output_file = "GST_Litigation_Issues_Tax.xlsx"
    df.to_excel(output_file, index=False)

    with open(output_file, "rb") as f:
        st.download_button(
            "📥 Download Excel",
            data=f,
            file_name=output_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

