import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image 

# --- Page Setup ---
st.set_page_config(page_title="ResumePro | AI Formatter", layout="wide", page_icon="📄")

# --- AI Configuration ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("API Key missing. Please set GEMINI_API_KEY in Streamlit Secrets.")

# --- Initialization ---
if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""

# --- Sidebar: Control Center ---
with st.sidebar:
    st.title("🚀 Control Center")
    with st.expander("🏢 BRANDING & ID", expanded=True):
        company_choice = st.selectbox("Company Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        document_title = st.text_input("Document Title", value="RESUME")
    
    with st.expander("⚙️ AI CONFIGURATION", expanded=True):
        include_summary = st.checkbox("Generate AI Summary", value=True)
        custom_summary_points = st.text_area("Extra Summary Points", placeholder="e.g. Focus on leadership...", disabled=not include_summary)
        make_confidential = st.checkbox("Mask Company Names [CONFIDENTIAL]", value=False)

# --- Helper Functions ---
UNIFORM_SPACE = Pt(12) 

def set_arial_font(doc):
    style = doc.styles['Normal']
    font = style.font
    font.name, font.size = 'Arial', Pt(11)

def get_sections_dict(text):
    sections, current_header = {}, None
    for line in text.split('\n'):
        clean = line.strip()
        if not clean: continue
        if clean.isupper() and clean.endswith(":"):
            current_header = clean
            sections[current_header] = []
        elif current_header:
            sections[current_header].append(clean)
    return sections

def replace_placeholder_in_doc(doc, placeholder, replacement):
    for p in doc.paragraphs:
        if placeholder in p.text:
            for run in p.runs: run.text = run.text.replace(placeholder, replacement)
    for section in doc.sections:
        for header in [section.header, section.first_page_header]:
            if header:
                for p in header.paragraphs:
                    if placeholder in p.text:
                        for run in p.runs: run.text = run.text.replace(placeholder, replacement)

# --- Main UI ---
st.subheader("📄 Professional Resume Formatter")
uploaded_file = st.file_uploader("Upload Source Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])

if uploaded_file and st.button("✨ Generate Professional Draft"):
    with st.status("AI is analyzing and formatting...", expanded=True) as status:
        try:
            # UPDATED: Changed model name to gemini-2.5-flash
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            sum_p = "DO NOT generate a summary section."
            if include_summary:
                sum_p = f"ALWAYS generate a 'SUMMARY:' section. Professionally develop these points into the narrative: {custom_summary_points}"
            
            priv_p = "CRITICAL: Replace ALL employer names in the Work Experience section with exactly '[CONFIDENTIAL]'." if make_confidential else ""

            prompt = f"""
            Reformat this resume keeping ONLY original sections. 
            Headers: ALL CAPS ending in colon.
            {sum_p}
            {priv_p}
            Work Exp/Education: 'Company/University | Date Range'. Job Title on next line.
            ONLY use '|' for date separation. Skills/Tools: one per line. No bolding/numbers.
            """
            
            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
                input_data = f"{prompt}\nTEXT:\n{raw}"
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
                input_data = f"{prompt}\nTEXT:\n{raw}"
            else:
                input_data = [prompt, Image.open(uploaded_file)]
            
            response = model.generate_content(input_data)
            st.session_state.original_ai_output = response.text.replace("**", "")
            status.update(label="Draft Ready!", state="complete", expanded=False)
        except Exception as e:
            st.error(f"Error: {e}")

# --- Document Builder ---
if st.session_state.original_ai_output:
    final_text = st.text_area("Final Polish:", value=st.session_state.original_ai_output, height=400)
    content_dict = get_sections_dict(final_text)
    
    header_order = st.multiselect("Reorder Sections:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
    t_path = os.path.join(os.path.dirname(__file__), t_map.get(company_choice, ""))
    doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()
    set_arial_font(doc)
    replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)
    replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title.upper())

    for h in header_order:
        if h in content_dict:
            hp = doc.add_paragraph()
            hp.paragraph_format.space_before = UNIFORM_SPACE
            hr = hp.add_run(h)
            hr.bold, hr.font.size, hr.font.name = True, Pt(12), 'Arial'
            
            last_was_company = False
            for line in content_dict[h]:
                if "|" in line:
                    doc.add_paragraph().paragraph_format.space_before = Pt(12)
                    tbl = doc.add_table(rows=1, cols=2)
                    tbl.autofit = False
                    cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
                    cl.width, cr.width = Inches(5.0), Inches(2.0)
                    parts = line.split("|")
                    cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                    p_dt = cr.paragraphs[0]
                    p_dt.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    rd = p_dt.add_run(parts[-1].strip())
                    rd.italic, rd.font.size, rd.font.name = True, Pt(10), 'Arial'
                    last_was_company = True
                else:
                    pb = doc.add_paragraph()
                    if last_was_company:
                        rj = pb.add_run(line.title())
                        rj.font.name = 'Arial'
                        pb.paragraph_format.space_after = Pt(8)
                        last_was_company = False
                    else:
                        rt = pb.add_run(line)
                        rt.font.name = 'Arial'
                        pb.paragraph_format.space_after = Pt(4)

    buf = io.BytesIO()
    doc.save(buf)
    st.download_button(label="📥 Download Resume", data=buf.getvalue(), file_name=f"{document_title}.docx")
