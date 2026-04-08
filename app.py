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
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Sidebar for company and contact info
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="123-456-7890")

# Template Mapping (Ensure these files are in your GitHub repo)
template_map = {
    "W3G": "w3g_template.docx",
    "Synectics": "synectics_template.docx",
    "ProTouch": "protouch_template.docx"
}

# --- GLOBAL UNIFORM SPACING ---
UNIFORM_SPACE = Pt(10) 

# --- Main App Interface ---
st.title("📄 Professional Resume Formatter")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Analyzing and formatting with Gemini 2.5 Flash..."):
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = """
            Reformat this resume keeping ONLY its original sections, but change the headers to ALL CAPS and end them with a colon.
            ALWAYS generate a 'SUMMARY:' section at the very beginning.
            For Work Experience/Education, use: 'Company Name/Degree | Date Range'.
            Ensure the Job Title/Role is on the very next line below the Company.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date. DO NOT use '|' anywhere else. If there are multiple job titles (e.g. 'Manager | Lead'), combine them with a hyphen (e.g. 'Manager - Lead') so it is read as one single job title.
            For Skills, Tools, Technical Tools, and Certifications, put each item on a new line.
            Do not put numbers before headers.
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
            else:
                st.error("Unsupported file type.")
                
        except Exception as e:
            st.error(f"AI Error: {e}")

if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Edit Window:", value=st.session_state.edited_content, height=450)
    include_summary = st.checkbox("Include AI-Generated Summary in Final Resume", value=True)

    if st.button("Download Final Word Doc"):
        # --- LOAD TEMPLATE ---
        t_file = template_map.get(company_choice)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, t_file)

        if os.path.exists(template_path):
            doc = docx.Document(template_path)
        else:
            st.warning(f"Template {t_file} not found. Using blank document.")
            doc = docx.Document()

        # --- LOGO LOGIC REMOVED (Handled by Template) ---

        # --- CONTENT FORMATTING ---
        current_section = ""
        last_line_was_company = False
        skip_mode = False
        bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]

        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

            if line.isupper() and line.endswith(":"):
                current_section = line
                if "SUMMARY" in line and not include_summary:
                    skip_mode = True
                    continue
                else:
                    skip_mode = False

                p = doc.add_paragraph()
                p.paragraph_format.space_before = UNIFORM_SPACE
                p.paragraph_format.space_after = Pt(6)
                run = p.add_run(line) 
                run.bold, run.font.size = True, Pt(12)
                last_line_was_company = False
                continue
                
            if skip_mode: continue

            # Manual Bullet Logic (Avoids KeyError)
            if any(bh in current_section for bh in bullet_headers):
                clean_line = line.lstrip("*-• ").strip()
                if clean_line:
                    p_bullet = doc.add_paragraph(f"• {clean_line}")
                    p_bullet.paragraph_format.left_indent = Inches(0.25)
                    p_bullet.paragraph_format.space_after = Pt(2)
                continue
            
            # Experience/Education Table
            elif "|" in line:
                row_table = doc.add_table(rows=1, cols=2)
                row_table.autofit = False
                cell_left, cell_right = row_table.rows[0].cells[0], row_table.rows[0].cells[1]
                cell_left.width, cell_right.width = Inches(4.8), Inches(2.2)
                
                parts = line.split("|")
                p_l = cell_left.paragraphs[0]
                run_comp = p_l.add_run(parts[0].strip().upper())
                run_comp.bold = True
                
                p_d = cell_right.paragraphs[0]
                p_d.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                date_text = parts[-1].strip() 
                run_date = p_d.add_run(date_text)
                run_date.bold, run_date.italic, run_date.font.size = True, True, Pt(10)
                last_line_was_company = True 
            
            else:
                p_body = doc.add_paragraph()
                p_body.paragraph_format.space_after = Pt(4)
                if last_line_was_company:
                    run_job = p_body.add_run(line.title())
                    run_job.bold = True # Bolded job titles per previous preference
                    last_line_was_company = False
                else:
                    p_body.add_run(line)

        # --- FOOTER ---
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_line = f"\nIf you would like to interview this candidate, please call {contact_number}"
        f_text = p_foot.add_run(footer_line)
        f_text.bold, f_text.font.color.rgb = True, RGBColor(0, 51, 153)

        buf = io.BytesIO()
        doc.save(buf)
        st.success(f"Format applied to {company_choice} template!")
        st.download_button(
            label="Download Final Word Document",
            data=buf.getvalue(),
            file_name=f"Formatted_Resume_{company_choice}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
