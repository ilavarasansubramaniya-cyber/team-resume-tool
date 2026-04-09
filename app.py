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

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: #007bff; color: white; font-weight: bold; border: none; }
    .stDownloadButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: #28a745; color: white; border: none; }
    </style>
    """, unsafe_allow_html=True)

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
        raw_title = st.text_input("Document Title", placeholder="Enter Name or Title")
        document_title = raw_title.strip().upper() if raw_title.strip() else "RESUME"
    
    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_points = st.text_area("Custom Points", placeholder="Leadership, ROI...")
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# --- 4. Logic Functions ---
def get_sections_dict(text):
    """Parses text. Discards 'Software' or 'Table' noise from Skills section."""
    sections, current_header = {}, None
    for line in text.split('\n'):
        clean = line.strip()
        if not clean: continue
        if clean.isupper() and clean.endswith(":"):
            current_header = clean
            sections[current_header] = []
        elif current_header:
            if "SKILL" in current_header.upper() and any(x in clean.lower() for x in ["software", "table", "the following"]):
                continue
            sections[current_header].append(clean)
    return sections

def replace_all_placeholders(doc, contact, title):
    """Aggressive replacement of placeholders in all parts of the document."""
    for section in doc.sections:
        for part in [section.header, section.footer]:
            for p in part.paragraphs:
                if "[CONTACT_NUMBER]" in p.text: p.text = p.text.replace("[CONTACT_NUMBER]", contact)
                if "[DOCUMENT_TITLE]" in p.text: p.text = p.text.replace("[DOCUMENT_TITLE]", title)
    
    for p in doc.paragraphs:
        if "[CONTACT_NUMBER]" in p.text: p.text = p.text.replace("[CONTACT_NUMBER]", contact)
        if "[DOCUMENT_TITLE]" in p.text: p.text = p.text.replace("[DOCUMENT_TITLE]", title)
    
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if "[CONTACT_NUMBER]" in p.text: p.text = p.text.replace("[CONTACT_NUMBER]", contact)
                    if "[DOCUMENT_TITLE]" in p.text: p.text = p.text.replace("[DOCUMENT_TITLE]", title)

# Consistent spacing constant (matches space between Summary and Skills)
SECTION_SPACE_PT = 10   # space after header / before next section block
JOB_BLOCK_SPACE_PT = 10 # space between job blocks (same rhythm)

def add_job_table(doc, line):
    """
    Adds a Company | Date row as a 2-column table.
    Returns the table so caller can set spacing after it.
    """
    tbl = doc.add_table(rows=1, cols=2)
    tbl.autofit = False
    cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
    cl.width, cr.width = Inches(5.1), Inches(1.9)
    parts = line.split("|")
    cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
    p_right = cr.paragraphs[0]
    p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_right.add_run(parts[-1].strip()).italic = True
    # Space BEFORE each job block (top of the company | date row)
    cl.paragraphs[0].paragraph_format.space_before = Pt(JOB_BLOCK_SPACE_PT)
    cr.paragraphs[0].paragraph_format.space_before = Pt(JOB_BLOCK_SPACE_PT)
    return tbl

# --- 5. Main Content Area ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Drop Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])
generate_btn = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🛠️ Re-architecting Content...", expanded=True):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            sum_p = f"Generate 'SUMMARY:' using: {custom_points}" if include_summary else "No summary."
            priv_p = "CRITICAL: Replace employer names with '[CONFIDENTIAL]'." if make_confidential else ""

            prompt = f"""
            TASK: Reformat this resume.
            Headers: ALL CAPS ending in colon.
            {sum_p}
            {priv_p}
            Experience/Education: 'Company/School | Date Range' (One line).
            Job Title: Next line.
            Descriptions: Bullet points. No mention of 'Table' or 'Software' artifacts.
            """
            
            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            else:
                raw = Image.open(uploaded_file)
            
            response = model.generate_content([prompt, raw] if not isinstance(raw, str) else [prompt, f"TEXT:\n{raw}"])
            st.session_state.original_ai_output = response.text.replace("**", "")
        except Exception as e:
            st.error(f"System Error: {e}")

# --- 6. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")
    
    c_edit, c_preview = st.columns([1.5, 1])
    with c_edit:
        st.markdown("#### 🖋️ Live Editor")
        final_text = st.text_area("Content Control:", value=st.session_state.original_ai_output, height=600, label_visibility="collapsed")

    current_sections = get_sections_dict(final_text)
    
    with st.sidebar:
        st.markdown("---")
        header_order = st.multiselect("Reorder Sections:", options=list(current_sections.keys()), default=list(current_sections.keys()))

    with c_preview:
        st.subheader("✅ Finalize")
        
        t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
        t_path = t_map.get(company_choice)
        doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()

        # Global Formatting
        style = doc.styles['Normal']
        style.font.name, style.font.size = 'Arial', Pt(10.5)

        replace_all_placeholders(doc, contact_number, document_title)

        # Space at the START of resume content (after branding header)
        doc.add_paragraph().paragraph_format.space_after = Pt(24)

        for h in header_order:
            if h not in current_sections:
                continue

            is_skills   = "SKILL"      in h.upper()
            is_summary  = "SUMMARY"    in h.upper()
            is_exp      = "EXPERIENCE" in h.upper()
            is_edu      = "EDUCATION"  in h.upper()
            is_job_section = is_exp or is_edu

            # ── SECTION HEADER ──────────────────────────────────────────────
            # Space BEFORE the header (same 10 pt used everywhere)
            hp = doc.add_paragraph()
            hp.paragraph_format.space_before = Pt(SECTION_SPACE_PT)
            hp.paragraph_format.space_after  = Pt(SECTION_SPACE_PT)   # space AFTER header
            hp.paragraph_format.keep_with_next = True
            hr = hp.add_run(h)
            hr.bold, hr.font.name, hr.font.size = True, 'Arial', Pt(11)

            # ── SECTION CONTENT ──────────────────────────────────────────────
            lines = current_sections[h]
            i = 0
            while i < len(lines):
                line = lines[i]

                # ── Company | Date  →  job block header ──
                if "|" in line:
                    add_job_table(doc, line)

                # ── Job Title line (follows a | line in experience/education) ──
                elif is_job_section and i > 0 and "|" in lines[i - 1]:
                    p = doc.add_paragraph()
                    # Space BETWEEN job title and job descriptions below it
                    p.paragraph_format.space_before = Pt(4)
                    p.paragraph_format.space_after  = Pt(4)
                    run = p.add_run(line)
                    run.bold      = True
                    run.font.name = 'Arial'
                    run.font.size = Pt(10.5)

                # ── Summary paragraph ──
                elif is_summary:
                    p = doc.add_paragraph(line)
                    p.paragraph_format.space_after = Pt(SECTION_SPACE_PT)

                # ── Bullet point  (skills, long lines, or bullet-prefixed lines) ──
                elif is_skills or len(line) > 60 or line.startswith(("•", "*", "-")):
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent        = Inches(0.25)
                    p.paragraph_format.first_line_indent  = Inches(-0.15)
                    p.paragraph_format.space_after        = Pt(3)
                    run = p.add_run(f"•\t{line.lstrip('•*- ').strip()}")
                    run.bold      = False          # ← FIX: descriptions NOT bold
                    run.font.name = 'Arial'

                # ── Short non-summary, non-bullet line ──
                else:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_after = Pt(2)
                    run = p.add_run(line)
                    run.bold      = True
                    run.font.name = 'Arial'

                i += 1

            # Space AFTER the last item in a job section (before next header's space_before kicks in)
            if is_job_section:
                spacer = doc.add_paragraph()
                spacer.paragraph_format.space_before = Pt(0)
                spacer.paragraph_format.space_after  = Pt(SECTION_SPACE_PT)

        # Space at the END of the resume
        doc.add_paragraph().paragraph_format.space_before = Pt(24)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(
            label=f"📥 DOWNLOAD {company_choice} DOCX",
            data=buf.getvalue(),
            file_name=f"{document_title}.docx"
        )
