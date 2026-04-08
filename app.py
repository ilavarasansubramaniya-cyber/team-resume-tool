import streamlit as st
import PyPDF2
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image

# --- Page Setup ---
st.set_page_config(page_title="Professional Resume Formatter", layout="wide")

# --- AI Configuration ---
try:
    # Set your GEMINI_API_KEY in the Streamlit Cloud "Secrets" tab
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("API Key not found. Please set GEMINI_API_KEY in Streamlit Secrets.")

# --- Sidebar Configuration ---
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="123-456-7890")

# Map choice to the template files you uploaded to GitHub
template_map = {
    "W3G": "w3g_template.docx",
    "Synectics": "synectics_template.docx",
    "ProTouch": "protouch_template.docx"
}

# --- Global Settings ---
UNIFORM_SPACE = Pt(10)

# --- Main App Interface ---
st.title("📄 Professional Resume Formatter")
st.markdown(f"Currently formatting for: **{company_choice}**")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

# File uploader for 800 employees (Supports PDF, Word, and OCR for Images)
uploaded_file = st.file_uploader("Upload Resume (PDF, DOCX, or Image)", type=["pdf", "docx", "png", "jpg", "jpeg"])

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Gemini AI is analyzing and reformatting..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = """
            Reformat this resume keeping ONLY its original sections, but change the headers to ALL CAPS and end them with a colon.
            ALWAYS generate a 'SUMMARY:' section at the very beginning.
            For Work Experience/Education, use: 'Company Name/Degree | Date Range'.
            Ensure the Job Title/Role is on the very next line below the Company.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date. DO NOT use it anywhere else.
            For Skills, Tools, Technical Tools, and Certifications, put each item on a new line.
            Do not put numbers before headers.
            """

            # Extraction Logic
            input_data = None
            if uploaded_file.type == "application/pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = "".join([p.extract_text() for p in reader.pages])
                input_data = prompt + f"\nTEXT:\n{raw_text}"
            
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc_input = docx.Document(uploaded_file)
                raw_text = "\n".join([para.text for para in doc_input.paragraphs])
                input_data = prompt + f"\nTEXT:\n{raw_text}"
            
            elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
                img = Image.open(uploaded_file)
                input_data = [prompt, img]

            if input_data:
                try:
                    response = model.generate_content(input_data)
                    # Clean up bold markers from AI
                    st.session_state.edited_content = response.text.replace("**", "")
                except Exception as ai_err:
                    if "429" in str(ai_err):
                        st.error("⚠️ Server Busy (Quota Reached). Please wait 15 seconds and try again.")
                    else:
                        st.error(f"AI Error: {ai_err}")
            
        except Exception as e:
            st.error(f"Extraction Error: {e}")

# --- Editing and Downloading Section ---
if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Review/Edit AI Output:", value=st.session_state.edited_content, height=400)
    include_summary = st.checkbox("Include Summary Section", value=True)

    if st.button("Apply Template & Download"):
        t_file = template_map.get(company_choice)
        
        # Absolute path ensure the file is found on GitHub
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, t_file)

        if os.path.exists(template_path):
            doc = docx.Document(template_path)
        else:
            st.warning(f"Template {t_file} not found in repo. Creating blank doc.")
            doc = docx.Document()

        current_section = ""
        bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]
        skip_mode = False

        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

            # Section Headers
            if line.isupper() and line.endswith(":"):
                current_section = line
                if "SUMMARY" in line and not include_summary:
                    skip_mode = True
                    continue
                skip_mode = False
                
                p = doc.add_paragraph()
                p.paragraph_format.space_before = UNIFORM_SPACE
                run = p.add_run(line)
                run.bold, run.font.size = True, Pt(12)
                continue

            if skip_mode: continue

            # Bullet points (Fixed: Manual bullets to prevent KeyError)
            if any(bh in current_section for bh in bullet_headers):
                clean_line = line.lstrip("*-• ")
                p_b = doc.add_paragraph(f"• {clean_line}")
                p_b.paragraph_format.left_indent = Inches(0.25)
                p_b.paragraph_format.space_after = Pt(2)
            
            # Company | Date Logic
            elif "|" in line:
                parts = line.split("|")
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.add_run(parts[0].strip().upper()).bold = True
                
                # Use tab for alignment (ensure your template has a right-tab stop)
                run_d = p.add_run(f"\t{parts[1].strip()}")
                run_d.italic, run_d.font.size = True, Pt(10)
            
            else:
                p_body = doc.add_paragraph(line)
                p_body.paragraph_format.space_after = Pt(4)

        # Footer logic (Contact Number)
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_run = p_foot.add_run(f"\nIf you would like to interview this candidate
