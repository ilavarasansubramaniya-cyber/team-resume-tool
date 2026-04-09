import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
from groq import Groq
import os

# --- 1. UI Config ---
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

# --- 2. Groq Config ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error(f"Groq API Key Error: {e}")

if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""

# --- 3. Sidebar ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    with st.expander("🏢 BRANDING & IDENTITY", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        document_title = st.text_input("Document Title", value="RESUME")
    
    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_summary_points = st.text_area("Custom Points to Develop", placeholder="e.g. ROI metrics...")
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# --- 4. Helper Functions ---
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
    found = False
    for p in doc.paragraphs:
        if placeholder in p.text:
            found = True
            for run in p.runs: run.text = run.text.replace(placeholder, replacement)
    for section in doc.sections:
        for header in [section.header, section.first_page_header]:
            if header:
                for p in header.paragraphs:
                    if placeholder in p.text:
                        found = True
                        for run in p.runs: run.text = run.text.replace(placeholder, replacement)
    return found

# --- 5. Main AI Processing ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Upload Source Resume", type=["pdf", "docx"])

if uploaded_file and st.button("✨ START AI TRANSFORMATION"):
    with st.status("🚀 Processing with Llama 4 Scout...", expanded=True):
        try:
            summary_p = f"Create a 'SUMMARY:' section based on: {custom_summary_points}" if include_summary else "No summary."
            
            redaction_p = ""
            if make_confidential:
                redaction_p = """
                MANDATORY CONFIDENTIALITY RULE: You MUST redact all employer/company names from the entire output.
                Replace ALL occurrences of actual company names with exactly '[CONFIDENTIAL]'.
                If a company name is inside a line like 'Company Name, Location', it becomes '[CONFIDENTIAL], Location'.
                """

            system_prompt = f"""
            {redaction_p}
            1. Headers: ALL CAPS ending in a colon (e.g., EXPERIENCE:, SKILLS:, CERTIFICATIONS:).
            2. {summary_p}
            3. Experience/Education Line 1: 'Company/University | Date Range'.
            4. Experience/Education Line 2: The Job Title or Degree.
            5. Skills, Tools, Certifications: Output each item on a new line. Do NOT output your own bullet points (like - or *), the system will add them automatically.
            6. Do not use markdown (**, *) anywhere.
            7. Responsibilities under a Job Title must be separate lines of text. Do NOT output bullet symbols or numbering.
            """
            
            if uploaded_file.type == "application/pdf":
                raw_text = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            else:
                raw_text = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": raw_text}],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.0
            )
            st.session_state.original_ai_output = response.choices[0].message.content.replace("**", "")
        except Exception as e:
            st.error(f"API Error: {e}")

# --- 6. Document Generation ---
if st.session_state.original_ai_output:
    final_text = st.text_area("Final Polish:", value=st.session_state.original_ai_output, height=400)
    
    t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
    t_path = os.path.join(os.path.dirname(__file__), t_map.get(company_choice, ""))
    doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()
    set_arial_font(doc)

    if not replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title.upper()):
        t_p = doc.add_paragraph()
        t_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        t_run = t_p.add_run(document_title.upper())
        t_run.bold, t_run.font.size = True, Pt(16)

    replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)

    content_dict = get_sections_dict(final_text)
    header_order = st.multiselect("Reorder Sections:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    for h in header_order:
        hp = doc.add_paragraph()
        hp.paragraph_format.space_before = Pt(14)
        hp.paragraph_format.space_after = Pt(12)
        hp.add_run(h).bold = True
        
        # Determine section type
        is_experience = any(x in h for x in ["EXPERIENCE", "WORK", "HISTORY", "EMPLOYMENT"])
        is_list_section = any(x in h for x in ["SKILL", "CERTIFICATION", "TOOL", "TECHNICAL"])
        
        last_was_header_line = False 
        last_was_title_line = False 

        for line in content_dict[h]:
            # Clean AI-generated bullets just in case it ignores the prompt
            clean_line = line.strip().lstrip('*-• ')
            if not clean_line: continue

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
                p_dt.add_run(parts[-1].strip()).italic = True
                last_was_header_line = True
            elif last_was_header_line:
                p = doc.add_paragraph()
                p.add_run(clean_line.title())
                p.paragraph_format.space_after = Pt(4)
                last_was_header_line = False
                last_was_title_line = True
            
            # --- BULLET POINT LOGIC FOR BOTH EXPERIENCE AND SKILLS/CERTS ---
            elif (is_experience and not last_was_header_line) or is_list_section:
                p = doc.add_paragraph()
                p.add_run(f"• {clean_line}")
                p.paragraph_format.left_indent = Inches(0.4)
                p.paragraph_format.first_line_indent = Inches(-0.2)
                p.paragraph_format.space_after = Pt(2)
            
            else:
                p_body = doc.add_paragraph(clean_line)
                p_body.paragraph_format.space_after = Pt(4)
                last_was_title_line = False

    buf = io.BytesIO()
    doc.save(buf)
    st.download_button(label="📥 Download Final Resume", data=buf.getvalue(), file_name=f"{document_title}.docx")
