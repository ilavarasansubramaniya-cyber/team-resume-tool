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

# Custom CSS for UI styling
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
# Ensure this matches the newest Gemini 2.5 identifiers
MODEL_NAME = "gemini-2.5-flash-lite"

try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("API Key missing in Streamlit Secrets.")
except Exception as e:
    st.error(f"Setup Error: {e}")

if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""

# --- 3. Sidebar Control ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    with st.expander("🏢 BRANDING", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        document_title = st.text_input("Document Title", value="RESUME")
    
    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_points = st.text_area("Custom Points", placeholder="Leadership, ROI...")
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# --- 4. Helper Functions ---
def get_sections_dict(text):
    sections, current_header = {}, "GENERAL"
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

def set_arial_font(doc):
    style = doc.styles['Normal']
    style.font.name, style.font.size = 'Arial', Pt(11)

# --- 5. Main Hero Section ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Drop Resume (PDF, DOCX, or Image)", type=["pdf", "docx", "png", "jpg", "jpeg"])
generate_btn = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🛠️ Re-architecting with Gemini 2.5 Flash-Lite...", expanded=True) as status:
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            
            # Logic Construction
            sum_p = "DO NOT generate a summary."
            if include_summary:
                sum_p = f"ALWAYS generate a 'SUMMARY:' section. Develop these points: '{custom_points}'"
            
            priv_p = ""
            if make_confidential:
                priv_p = ("CRITICAL: Identify all employer/company names in the Work Experience section. "
                          "Replace every instance with the text '[CONFIDENTIAL]'. Do not leave original names.")

            prompt = f"""
            TASK: Reformat this resume.
            Headers: ALL CAPS ending in colon.
            {sum_p}
            {priv_p}
            Experience/Education: 'Company or School | Date Range'.
            Job Title: On the very next line.
            Skills: One item per line. No bolding (**) or numbers.
            """
            
            # Extraction logic
            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
                response = model.generate_content([prompt, f"TEXT:\n{raw}"])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
                response = model.generate_content([prompt, f"TEXT:\n{raw}"])
            else:
                response = model.generate_content([prompt, Image.open(uploaded_file)])
            
            st.session_state.original_ai_output = response.text.replace("**", "")
            status.update(label="Transformation Complete!", state="complete", expanded=False)
            st.balloons()
        except Exception as e:
            st.error(f"System Error: {e}")

# --- 6. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")
    content_dict = get_sections_dict(st.session_state.original_ai_output)
    
    with st.sidebar:
        header_order = st.multiselect("Reorder Sections:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    c_edit, c_preview = st.columns([1.5, 1])
    with c_edit:
        st.markdown("#### 🖋️ Live Editor")
        final_text = st.text_area("Final Output Edit:", value=st.session_state.original_ai_output, height=600, label_visibility="collapsed")
    
    with c_preview:
        st.markdown("#### ✅ Final Steps")
        
        # Security Tip - Fixed Syntax Error Here
        if make_confidential:
            st.info("💡 Pro-tip: Double-check the redactions in the editor before downloading.")
            
        st.success("Transformation Ready!")

        # Document Generation
        doc = docx.Document()
        set_arial_font(doc)
        
        # Processing sections based on sidebar order
        new_content = get_sections_dict(final_text)
        for h in header_order:
            if h in new_content:
                hp = doc.add_paragraph()
                hr = hp.add_run(h)
                hr.bold, hr.font.size = True, Pt(12)
                
                last_comp = False
                for line in new_content[h]:
                    if "|" in line:
                        tbl = doc.add_table(rows=1, cols=2)
                        cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
                        parts = line.split("|")
                        cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                        cr.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        cr.paragraphs[0].add_run(parts[-1].strip()).italic = True
                        last_comp = True
                    else:
                        pb = doc.add_paragraph(line)
                        last_comp = False

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(label=f"📥 DOWNLOAD {company_choice} DOCX", 
                            data=buf.getvalue(), 
                            file_name=f"{document_title}.docx")
