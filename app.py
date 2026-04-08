import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image 

# --- Page Setup ---
st.set_page_config(page_title="Professional Resume Formatter", layout="wide")

# --- AI Configuration ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("API Key not found. Please set GEMINI_API_KEY in Streamlit Secrets.")

# Sidebar for company and contact info
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="123-456-7890")

# Template Mapping
template_map = {
    "W3G": "w3g_template.docx",
    "Synectics": "synectics_template.docx",
    "ProTouch": "protouch_template.docx"
}

# --- GLOBAL SETTINGS ---
UNIFORM_SPACE = Pt(10) # Used for sections and between entries

# --- Helper Function: Set Font to Arial ---
def set_arial_font(doc):
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(11)
    for section in doc.sections:
        for footer in [section.footer, section.header]:
            for paragraph in footer.paragraphs:
                for run in paragraph.runs:
                    run.font.name = 'Arial'

# --- Main App Interface ---
st.title("📄 Professional Resume Formatter")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Analyzing and formatting with Gemini..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            prompt = """
            Reformat this resume keeping ONLY its original sections, but change the headers to ALL CAPS and end them with a colon.
            ALWAYS generate a 'SUMMARY:' section at the very beginning.
            For Work Experience/Education, use: 'Company Name/University | Date Range'.
            Ensure the Job Title/Degree is on the very next line below the Company/University.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date.
            For Skills, Tools, Technical Tools, and Certifications, put each item on a new line.
            Do not put numbers before headers or bolding (**) in the text.
            """
            
            input_data = None
            if uploaded_file.type == "application/pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = "".join([p.extract_text() for p in reader.pages])
                input_data = prompt + f"\nTEXT:\n{raw_text}"
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc_file = docx.Document(uploaded_file)
                raw_text = "\n".join([para.text for para in doc_file.paragraphs])
                input_data = prompt + f"\nTEXT:\n{raw_text}"
            elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
                img = Image.open(uploaded_file)
                input_data = [prompt, img]
            
            if input_data:
                response = model.generate_content(input_data)
                st.session_state.edited_content = response.text.replace("**", "")
        except Exception as e:
            st.error(f"AI Error: {e}")

# --- Editing and Single Download Button Section ---
if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Edit Window:", value=st.session_state.edited_content, height=450)
    include_summary = st.checkbox("Include AI Summary", value=True)

    # Prepare the Word Document in memory whenever the text is updated
    t_file = template_map.get(company_choice)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, t_file)

    doc = docx.Document(template_path) if os.path.exists(template_path) else docx.Document()
    set_arial_font(doc)

    current_section = ""
    last_line_was_company = False
    skip_mode = False
    bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]

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
            run.bold, run.font.size, run.font.name = True, Pt(12), 'Arial'
            last_line_was_company = False
            continue
            
        if skip_mode: continue

        # Manual Bullets (Arial)
        if any(bh in current_section for bh in bullet_headers):
            p_bullet = doc.add_paragraph(f"• {line.lstrip('*-• ')}")
            p_bullet.paragraph_format.left_indent = Inches(0.25)
            for run in p_bullet.runs: run.font.name = 'Arial'
            continue
        
        # Experience/Education Entry (Company | Date)
        elif "|" in line:
            # Space before the entry (same as section spacing)
            spacer_p = doc.add_paragraph()
            spacer_p.paragraph_format.space_before = UNIFORM_SPACE
            
            row_table = doc.add_table(rows=1, cols=2)
            row_table.autofit = False
            cell_left, cell_right = row_table.rows[0].cells[0], row_table.rows[0].cells[1]
            cell_left.width, cell_right.width = Inches(5.0), Inches(2.0)
            
            parts = line.split("|")
            p_l = cell_left.paragraphs[0]
            run_comp = p_l.add_run(parts[0].strip().upper())
            run_comp.bold, run_comp.font.name = True, 'Arial'
            
            p_d = cell_right.paragraphs[0]
            p_d.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run_date = p_d.add_run(parts[-1].strip())
            run_date.italic, run_date.font.name, run_date.font.size = True, 'Arial', Pt(10)
            last_line_was_company = True 
        
        # Job Title / Body Text
        else:
            p_body = doc.add_paragraph()
            if last_line_was_company:
                run_job = p_body.add_run(line.title())
                run_job.bold = False # Job Title not bold
                run_job.font.name = 'Arial'
                # Space AFTER Job Title before description starts
                p_body.paragraph_format.space_after = Pt(8) 
                last_line_was_company = False
            else:
                run_text = p_body.add_run(line)
                run_text.font.name = 'Arial'
                p_body.paragraph_format.space_after = Pt(4)

    # Save to buffer for the download button
    buf = io.BytesIO()
    doc.save(buf)

    # THE SINGLE DOWNLOAD BUTTON
    st.download_button(
        label=f"📥 Download Final {company_choice} Resume",
        data=buf.getvalue(),
        file_name=f"{company_choice}_Formatted_Resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
