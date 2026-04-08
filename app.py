import streamlit as st
import PyPDF2
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
from huggingface_hub import InferenceClient # NEW: Hugging Face Client
import os
from PIL import Image
import base64

# --- Page Setup ---
st.set_page_config(page_title="Professional Resume Formatter", layout="wide")

# --- Hugging Face Configuration ---
# Set your model here. Llama-3-8B or Mistral-7B-v0.3 are great for formatting.
MODEL_ID = "meta-llama/Meta-Llama-3-8B-Instruct" 

try:
    # Change secret name to HF_TOKEN in your Streamlit dashboard
    client = InferenceClient(api_key=st.secrets["HF_TOKEN"])
except Exception:
    st.error("Hugging Face Token not found. Please set HF_TOKEN in Streamlit Secrets.")

# --- Sidebar ---
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="123-456-7890")

template_map = {"W3G": "w3g_template.docx", "Synectics": "synectics.jpg", "ProTouch": "protouch.png"}

# --- Main App ---
st.title("📄 Professional Resume Formatter (HF Edition)")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Hugging Face model is processing..."):
        try:
            # Formatting Instructions
            prompt = f"""
            Reformat this resume keeping ONLY its original sections, but change the headers to ALL CAPS and end them with a colon.
            ALWAYS generate a 'SUMMARY:' section at the very beginning.
            For Work Experience/Education, use: 'Company Name/Degree | Date Range'.
            Ensure the Job Title/Role is on the very next line below the Company.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date. DO NOT use '|' anywhere else.
            For Skills, Tools, Technical Tools, and Certifications, put each item on a new line.
            Do not put numbers before headers.
            """

            # Text Extraction
            raw_text = ""
            if uploaded_file.type == "application/pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = "".join([p.extract_text() for p in reader.pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc_in = docx.Document(uploaded_file)
                raw_text = "\n".join([p.text for p in doc_in.paragraphs])
            else:
                st.error("Image support requires specialized Vision models on HF. Please upload PDF or DOCX.")
                st.stop()

            # --- HUGGING FACE API CALL ---
            messages = [{"role": "user", "content": f"{prompt}\n\nRESUME TEXT:\n{raw_text}"}]
            
            response = ""
            for message in client.chat_completion(
                model=MODEL_ID,
                messages=messages,
                max_tokens=2500,
                stream=True
            ):
                response += message.choices[0].delta.content or ""
            
            st.session_state.edited_content = response.replace("**", "")
            
        except Exception as e:
            st.error(f"HF Error: {e}")

# --- Review and Word Generation ---
if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Review Output:", value=st.session_state.edited_content, height=400)
    
    if st.button("Apply Template & Download"):
        # Use existing template logic
        t_file = f"{company_choice.lower()}_template.docx"
        doc = docx.Document(t_file) if os.path.exists(t_file) else docx.Document()

        current_section = ""
        bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]

        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

            if line.isupper() and line.endswith(":"):
                current_section = line
                p = doc.add_paragraph()
                run = p.add_run(line)
                run.bold, run.font.size = True, Pt(12)
                continue

            if any(bh in current_section for bh in bullet_headers):
                doc.add_paragraph(line.lstrip("*-• "), style='List Bullet')
            elif "|" in line:
                parts = line.split("|")
                p = doc.add_paragraph()
                p.add_run(parts[0].strip().upper()).bold = True
                p.add_run(f"\t{parts[1].strip()}").italic = True
            else:
                doc.add_paragraph(line)

        # Footer
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_run = p_foot.add_run(f"\nIf you would like to interview this candidate, please call {contact_number}")
        f_run.bold, f_run.font.color.rgb = True, RGBColor(0, 51, 153)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button("Download Resume", buf.getvalue(), f"{company_choice}_Resume.docx")
