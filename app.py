import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image 

# --- 1. UI Config ---
st.set_page_config(page_title="ResumePro Elite", layout="wide", page_icon="💎")

# --- 2. AI Engine Config ---
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

# --- 3. Sidebar ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    with st.expander("🏢 BRANDING", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        # Logic: Default to RESUME if empty
        raw_title = st.text_input("Document Title", placeholder="RESUME")
        document_title = raw_title.strip().upper() if raw_title.strip() else "RESUME"
    
    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_points = st.text_area("Custom Points", placeholder="Leadership, ROI...")
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# --- 4. Logic Functions ---
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

def replace_placeholder_in_doc(doc, placeholder, replacement):
    for p in doc.paragraphs:
        if placeholder in p.text:
            for run in p.runs:
                run.text = run.text.replace(placeholder, replacement)
                run.font.name = 'Arial'
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if placeholder in p.text:
                        p.text = p.text.replace(placeholder, replacement)
                        for run in p.runs: run.font.name = 'Arial'

# --- 5. Main Hero Section ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Drop Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])
generate_btn = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🛠️ Re-architecting Content...", expanded=True):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            sum_p = f"Generate 'SUMMARY:' focusing on: {custom_points}" if include_summary else "No summary."
            priv_p = "CRITICAL: Replace employer names with '[CONFIDENTIAL]'." if make_confidential else ""

            prompt = f"""
            TASK: Reformat this resume into professional text.
            1. Headers: ALL CAPS ending in colon.
            2. {sum_p}
            3. {priv_p}
            4. Experience/Education: 'Company/School | Date Range' (Keep dates on one line).
            5. Job Title: On next line.
            6. Skills: One per line.
            7. Formatting: No bolding (**) in raw text.
            """
            
            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            else:
                raw = Image.open(uploaded_file)
            
            input_content = [prompt, raw] if not isinstance(raw, str) else [prompt, f"TEXT:\n{raw}"]
            response = model.generate_content(input_content)
            st.session_state.original_ai_output = response.text.replace("**", "")
            st.balloons()
        except Exception as e:
            st.error(f"System Error: {e}")

# --- 6. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")
    content_dict = get_sections_dict(st.session_state.original_ai_output)
    header_order = st.sidebar.multiselect("Reorder Sections:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    c_edit, c_preview = st.columns([1.5, 1])
    with c_edit:
        final_text = st.text_area("Live Editor:", value=st.session_state.original_ai_output, height=600)
    
    with c_preview:
        st.markdown("#### ✅ Finalize")
        
        # Template Selection
        t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
        t_path = t_map.get(company_choice)
        doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()

        # Apply Global Arial
        style = doc.styles['Normal']
        style.font.name, style.font.size = 'Arial', Pt(10.5)

        replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)
        replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title)

        new_content = get_sections_dict(final_text)
        for h in header_order:
            if h in new_content:
                # --- HEADER SPACING & PREVENTION ---
                hp = doc.add_paragraph()
                hp.paragraph_format.space_before = Pt(18) # Uniform space before header
                hp.paragraph_format.space_after = Pt(6)   # Uniform space after header
                hp.paragraph_format.keep_with_next = True # Push to next page if it's the last line
                
                hr = hp.add_run(h)
                hr.bold, hr.font.name, hr.font.size = True, 'Arial', Pt(11)
                
                is_skills = "SKILL" in h.upper()
                
                for line in new_content[h]:
                    if "|" in line:
                        # Professional Table for Uniform Width (Prevents date wrapping)
                        tbl = doc.add_table(rows=1, cols=2)
                        tbl.autofit = False
                        cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
                        cl.width, cr.width = Inches(5.1), Inches(1.9) # Fixed width for single-line dates
                        
                        parts = line.split("|")
                        p_left = cl.paragraphs[0]
                        run_l = p_left.add_run(parts[0].strip().upper())
                        run_l.bold, run_l.font.name = True, 'Arial'
                        
                        p_right = cr.paragraphs[0]
                        p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        run_r = p_right.add_run(parts[-1].strip())
                        run_r.italic, run_r.font.name = True, 'Arial'
                    
                    elif is_skills:
                        p = doc.add_paragraph()
                        p.paragraph_format.left_indent = Inches(0.25)
                        p.add_run(f"•\t{line}").font.name = 'Arial'
                        p.paragraph_format.space_after = Pt(2)
                    
                    else:
                        p = doc.add_paragraph()
                        p.paragraph_format.space_after = Pt(4) # Uniform paragraph spacing
                        p.add_run(line).font.name = 'Arial'

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(label=f"📥 DOWNLOAD {company_choice} DOCX", data=buf.getvalue(), file_name=f"{document_title}.docx")
