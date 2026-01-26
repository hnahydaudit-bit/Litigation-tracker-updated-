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
You are an expert in GST litigation notices.

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

VERY IMPORTANT INSTRUCTIONS:

1️⃣ Issues & Amounts (THIS IS CRITICAL)
- Capture ALL issues mentioned in the notice (major + minor)
- SIMPLIFY the wording into short, clear phrases
- Do NOT copy long paragraphs
- Do NOT explain
- Do NOT add legal language

FORMAT STRICTLY AS:
1. <short issue description> – ₹amount
2. <short issue description> – ₹amount

Rules:
- One issue per line
- MUST be numbered
- Mention ONLY TAX amount
- Ignore interest & penalty here
- If amount is not mentioned, write:
  "Amount not specified"
- Use Indian numbering format for amounts

2️⃣ Description
- 1–2 lines only
- High-level summary covering ALL issues collectively
- No amounts
- No issue-wise listing

3️⃣ Accuracy
- Tax Amount, Interest, Penalty must be EXACTLY as mentioned
- Do NOT calculate or infer
- Leave blank if not explicitly present

4️⃣ Output rules
- Return ONLY valid JSON
- No markdown, no explanations

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

# ---------- Streamlit UI ----------

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
