import streamlit as st
import PyPDF2
import docx
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image # Keeping this only for OCR support of JPG/PNG resumes

# --- Page Setup ---
st.set_page_config(page_title="Professional Resume Formatter", layout="wide")

# --- AI Configuration ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("API Key not found. Please set GEMINI_API_KEY in Streamlit Secrets.")

# --- Sidebar Configuration ---
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="123-456-7890")

# Template Mapping (Ensure these filenames match your GitHub exactly)
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

uploaded_file = st.file_uploader("Upload Resume (PDF, DOCX, or Image)", type=["pdf", "docx", "png", "jpg", "jpeg"])

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Gemini 2.5 Flash is analyzing your document..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = """
            Reformat this resume keeping ONLY its original sections, but change the headers to ALL CAPS and end them with a colon.
            ALWAYS generate a 'SUMMARY:' section at the very beginning.
            For Work Experience/Education, use: 'Company Name/Degree | Date Range'.
            Ensure the Job Title/Role is on the very next line below the Company.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date. 
            For Skills, Tools, Technical Tools, and Certifications, put each item on a new line.
            Do not put numbers before headers.
            """

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
                    st.session_state.edited_content = response.text.replace("**", "")
                except Exception as ai_err:
                    if "429" in str(ai_err):
                        st.error("⚠️ Server Busy: Quota limit reached. Wait 15 seconds and try again.")
                    else:
                        st.error(f"AI Error: {ai_err}")
            
        except Exception as e:
            st.error(f"Extraction Error: {e}")

# --- Editing and Downloading Section ---
if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Review AI Output:", value=st.session_state.edited_content, height=400)
    include_summary = st.checkbox("Include Summary Section", value=True)

    if st.button("Apply to Company Template & Download"):
        t_file = template_map.get(company_choice)
        
        # Absolute path check for GitHub deployment
        base_path = os.path.dirname(__file__)
        full_template_path = os.path.join(base_path, t_file)

        if os.path.exists(full_template_path):
            doc = docx.Document(full_template_path)
        else:
            st.warning(f"Template '{t_file}' not found in directory. Using blank document.")
            doc = docx.Document()

        current_section = ""
        bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]
        skip_mode = False

        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

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

            if any(bh in current_section for bh in bullet_headers):
                p_b = doc.add_paragraph(line.lstrip("*-• "), style='List Bullet')
                p_b.paragraph_format.space_after = Pt(2)
            
            elif "|" in line:
                parts = line.split("|")
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.add_run(parts[0].strip().upper()).bold = True
                
                # Right-aligned date
                run_d = p.add_run(f"\t{parts[1].strip()}")
                run_d.italic, run_d.font.size = True, Pt(10)
            
            else:
                doc.add_paragraph(line).paragraph_format.space_after = Pt(4)

        # Blue Footer for Contact
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_run = p_foot.add_run(f"\nIf you would like to interview this candidate, please call {contact_number}")
        f_run.bold = True
        f_run.font.color.rgb = RGBColor(0, 51, 153)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(
            label=f"Download Final {company_choice} Resume",
            data=buf.getvalue(),
            file_name=f"Formatted_{company_choice}_Resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
