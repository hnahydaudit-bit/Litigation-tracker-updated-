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

# ================= HELPER FUNCTIONS =================

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def detect_notice_type(text):
    """Rule-based detection for MAX accuracy"""
    t = text.upper()

    patterns = [
        ("ASMT-10", r"ASMT[\s\-]*10"),
        ("DRC-01", r"DRC[\s\-]*01"),
        ("DRC-01A", r"DRC[\s\-]*01A"),
        ("ADT-01", r"ADT[\s\-]*01"),
        ("SCN", r"SHOW CAUSE NOTICE|SCN"),
        ("APPEAL", r"APPEAL"),
        ("ORDER", r"ORDER")
    ]

    for label, pattern in patterns:
        if re.search(pattern, t):
            return label

    return ""  # leave blank if truly not found

def extract_with_ai(batch_texts):
    prompt = f"""
You are a GST litigation expert.

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

STRICT INSTRUCTIONS:

1. Extract values ONLY if explicitly present.
2. Do NOT guess or infer missing data.
3. Description must be 1–2 lines and cover ALL issues collectively.
4. Issues & Amounts must include ALL issues, numbered, issue-wise,
   with TAX amount only (Indian numbering format).
5. All amounts must be EXACTLY as mentioned in notice.
6. Return ONLY valid JSON.

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

# ================= STREAMLIT UI =================

uploaded_files = st.file_uploader(
    "📤 Upload your GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info("⏳ Processing… Please wait.")
    batch_texts = []
    notice_type_map = {}

    for uploaded in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        text = extract_text_from_pdf(tmp_path)
        os.remove(tmp_path)

        # Rule-based notice type detection
        notice_type_map[uploaded.name] = detect_notice_type(text)

        batch_texts.append({
            "Source": uploaded.name,
            "Text": text
        })

    results = extract_with_ai(batch_texts)

    # 🔥 OVERRIDE notice type if AI missed it
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
