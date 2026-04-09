import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image 

# --- 1. Grand UI Config ---
st.set_page_config(page_title="ResumePro Elite", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    [data-testid="stSidebar"] { background-color: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: linear-gradient(45deg, #007bff, #6610f2); color: white; font-weight: bold; border: none; }
    .stDownloadButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: linear-gradient(45deg, #28a745, #20c997); color: white; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI Engine Config ---
# Updated for Gemini 2.5 Flash-Lite
MODEL_NAME = "gemini-2.5-flash-lite"

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets.")

if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""

# --- 3. Sidebar ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    with st.expander("🏢 BRANDING", expanded=True):
        company_choice = st.selectbox("Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact", value="123-456-7890")
        document_title = st.text_input("Doc Title", value="RESUME")
    
    with st.expander("🧠 AI SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_points = st.text_area("Custom Points", placeholder="Leadership, ROI...")
        make_confidential = st.checkbox("Redact Employers [CONFIDENTIAL]", value=False)

# --- 4. Logic Functions ---
def get_sections_dict(text):
    sections, current_header = {}, "UNRESOLVED"
    for line in text.split('\n'):
        clean = line.strip()
        if not clean: continue
        if clean.isupper() and clean.endswith(":"):
            current_header = clean
            sections[current_header] = []
        elif current_header:
            if current_header not in sections: sections[current_header] = []
            sections[current_header].append(clean)
    return sections

def set_doc_styling(doc, contact, title):
    style = doc.styles['Normal']
    style.font.name, style.font.size = 'Arial', Pt(11)
    # Placeholder replacement logic
    for p in doc.paragraphs:
        if "[CONTACT_NUMBER]" in p.text:
            p.text = p.text.replace("[CONTACT_NUMBER]", contact)
        if "[DOCUMENT_TITLE]" in p.text:
            p.text = p.text.replace("[DOCUMENT_TITLE]", title.upper())

# --- 5. Main Hero Section ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Upload File", type=["pdf", "docx", "png", "jpg", "jpeg"])
generate_btn = st.button("✨ EXECUTE AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🛠️ Running Gemini 2.5 Flash-Lite...", expanded=True) as status:
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            
            # Construct strict prompts for Lite model efficiency
            redaction_prompt = ""
            if make_confidential:
                redaction_prompt = (
                    "CRITICAL: Identify every Company/Employer name in the Experience section. "
                    "Replace every instance with the text '[CONFIDENTIAL]'. Do not leave names visible."
                )

            summary_prompt = "DO NOT write a summary."
            if include_summary:
                summary_prompt = f"Create a 'SUMMARY:' section incorporating: {custom_points}"

            prompt = f"""
            TASK: Reformat the provided resume into a structured text format.
            1. All Headers must be UPPERCASE and end with a colon.
            2. {summary_prompt}
            3. {redaction_prompt}
            4. Education/Work: Format exactly as 'Entity Name | Date Range'.
            5. Job Titles must be on the line immediately following the Entity Name.
            6. Skills: One item per line. No bullet points or bolding.
            """

            # Handle File Types
            if uploaded_file.type == "application/pdf":
                raw_text = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
                response = model.generate_content([prompt, f"RESUME TEXT:\n{raw_text}"])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw_text = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
                response = model.generate_content([prompt, f"RESUME TEXT:\n{raw_text}"])
            else:
                response = model.generate_content([prompt, Image.open(uploaded_file)])

            st.session_state.original_ai_output = response.text.replace("**", "")
            status.update(label="Complete!", state="complete", expanded=False)
            st.balloons()
        except Exception as e:
            st.error(f"Engine Error: {e}")

# --- 6. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")
    content_dict = get_sections_dict(st.session_state.original_ai_output)
    
    with st.sidebar:
        header_order = st.multiselect("Reorder:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    c_edit, c_preview = st.columns([1.5, 1])
    with c_edit:
        st.subheader("🖋️ Live Editor")
        final_text = st.text_area("Final Polish", value=st.session_state.original_ai_output, height=500, label_visibility="collapsed")
    
    with c_preview:
        st.subheader("✅ Finalize")
        if make_confidential:
            st.info("💡 Pro-tip:
