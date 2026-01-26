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

st.set_page_config(page_title="LITIGATION TRACKER", page_icon="📂")
st.title("📂 LITIGATION TRACKER")

# ================= HELPERS =================

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def detect_notice_type(text):
    t = text.upper()
    patterns = [
        ("ASMT-10", r"ASMT[\s\-]*10"),
        ("DRC-01A", r"DRC[\s\-]*01A"),
        ("DRC-01", r"DRC[\s\-]*01"),
        ("ADT-01", r"ADT[\s\-]*01"),
        ("SCN", r"SHOW\s+CAUSE\s+NOTICE|SCN"),
        ("APPEAL", r"APPEAL"),
        ("ORDER", r"\bORDER\b")
    ]
    for label, pat in patterns:
        if re.search(pat, t):
            return label
    return ""

def extract_with_ai(batch_texts):
    prompt = f"""
You are a GST litigation expert.

For EACH document below, return ONE JSON object.
Return a JSON ARRAY.

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

🔥 CRITICAL – DO NOT VIOLATE THESE RULES 🔥

1️⃣ Issues & Amounts (ABSOLUTELY EXHAUSTIVE)
- Extract **EVERY issue mentioned in the notice**
- This includes:
  - main allegations
  - minor discrepancies
  - procedural lapses
  - annexure points
  - table-wise issues
  - explanatory paragraphs
- Do NOT filter
- Do NOT prioritise
- Do NOT club
- Do NOT summarise
- Do NOT omit minor issues

2️⃣ Wording
- Use wording as close as possible to the notice
- Do NOT paraphrase
- Do NOT generalise

3️⃣ Formatting for Issues & Amounts
- Number issues as:
  1. <issue text> – ₹amount
  2. <issue text> – ₹amount
- Each issue on a NEW LINE
- Mention ONLY TAX amount for that issue
- Ignore interest and penalty here
- If amount not mentioned, write exactly:
  "Amount not specified"
- All amounts must be in INDIAN NUMBERING SYSTEM

4️⃣ Description
- 1–2 lines only
- Must collectively reflect ALL issues
- High-level umbrella summary
- No amounts
- No issue-wise listing

5️⃣ Accuracy
- Tax Amount, Interest, Penalty must be extracted EXACTLY as written
- No calculation
- No inference
- No rounding
- If not explicitly present, leave blank

6️⃣ Output rules
- Return ONLY valid JSON
- No markdown
- No explanations

Documents:
{json.dumps(batch_texts, indent=2)}
"""

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)

    raw = response.candidates[0].content.parts[0].text
    match = re.search(r"\[.*\]", raw, re.DOTALL)

    if not match:
        return []

    try:
        return json.loads(match.group(0))
    except:
        return []

# ================= UI =================

uploaded_files = st.file_uploader(
    "📤 Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info("⏳ Processing… please wait.")
    batch_texts = []
    notice_type_map = {}

    for uploaded in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        text = extract_text_from_pdf(tmp_path)
        os.remove(tmp_path)

        notice_type_map[uploaded.name] = detect_notice_type(text)

        batch_texts.append({
            "Source": uploaded.name,
            "Text": text
        })

    results = extract_with_ai(batch_texts)

    # Override notice type if AI missed it
    for row in results:
        src = row.get("Source", "")
        if not row.get("Notice Type (ASMT-10 or ADT-01 / SCN / Appeal)"):
            row["Notice Type (ASMT-10 or ADT-01 / SCN / Appeal)"] = notice_type_map.get(src, "")

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

    st.success("✅ Extraction completed")
    st.dataframe(df, use_container_width=True)

    out_file = "litigation_tracker_output.xlsx"
    df.to_excel(out_file, index=False)

    with open(out_file, "rb") as f:
        st.download_button(
            "📥 Download Excel",
            f,
            file_name="Litigation_Tracker_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
