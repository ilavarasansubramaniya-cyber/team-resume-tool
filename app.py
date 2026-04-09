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
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: #007bff; color: white; font-weight: bold; border: none; }
    .stDownloadButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: #28a745; color: white; border: none; }
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
    company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
    contact_number = st.text_input("Contact Number", value="123-456-7890")
    document_title = st.text_input("Document Title", value="RESUME")
    make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=True)

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
    for p in doc.paragraphs:
        if placeholder in p.text:
            for run in p.runs: run.text = run.text.replace(placeholder, replacement)
    for section in doc.sections:
        for header in [section.header, section.first_page_header]:
            if header:
                for p in header.paragraphs:
                    if placeholder in p.text:
                        for run in p.runs: run.text = run.text.replace(placeholder, replacement)

# --- 5. AI Transformation ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Upload Source Resume", type=["pdf", "docx"])

if uploaded_file and st.button("✨ START AI TRANSFORMATION"):
    with st.status("🚀 Processing with Llama 4 Scout..."):
        try:
            redaction_p = "MANDATORY: Replace ALL company names with '[CONFIDENTIAL]'." if make_confidential else ""
            system_prompt = f"""
            {redaction_p}
            1. Headers: ALL CAPS ending in a colon (e.g. CORE SKILLS:, EXPERIENCE:).
            2. Experience Line 1: 'Company | Date Range'.
            3. Experience Line 2: 'Job Title'.
            4. Body text: Return simple lines of text. NO markdown (**, *, -).
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

# --- 6. Editing & Formatting ---
if st.session_state.original_ai_output:
    st.markdown("---")
    
    # 1. Editor Window (Must be at top for easy access)
    final_text = st.text_area("🖋️ Edit Content Below:", value=st.session_state.original_ai_output, height=400)
    
    # 2. Reorder (Simplified Multi-select)
    content_dict = get_sections_dict(final_text)
    header_order = st.multiselect("📋 Reorder Headers:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    # 3. Document Build
    t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
    t_path = os.path.join(os.path.dirname(__file__), t_map.get(company_choice, ""))
    doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()
    set_arial_font(doc)

    # Global Placeholder Replacement
    replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title.upper())
    replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)

    for h in header_order:
        # Header Styling
        hp = doc.add_paragraph()
        hp.paragraph_format.space_before, hp.paragraph_format.space_after = Pt(14), Pt(10)
        hp.add_run(h).bold = True
        
        is_bullet_section = any(x in h for x in ["SKILL", "CERT", "TOOL", "SOFTWARE", "TECH", "EXPERIENCE", "WORK"])
        last_was_header_line = False

        for line in content_dict[h]:
            clean_line = line.strip().lstrip('*-• ')
            if not clean_line: continue

            # Date Range / Company Line
            if "|" in line:
                doc.add_paragraph().paragraph_format.space_before = Pt(8)
                tbl = doc.add_table(rows=1, cols=2)
                tbl.autofit = False
                cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
                parts = line.split("|")
                cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                cr.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                cr.paragraphs[0].add_run(parts[-1].strip()).italic = True
                last_was_header_line = True
            
            # Job Title Line
            elif last_was_header_line:
                p = doc.add_paragraph(clean_line.title())
                p.paragraph_format.space_after = Pt(4)
                last_was_header_line = False
            
            # Bullet point Logic (Applied to Skills, Software, and Experience Responsibilities)
            elif is_bullet_section:
                p = doc.add_paragraph()
                p.add_run(f"• {clean_line}")
                p.paragraph_format.left_indent = Inches(0.4)
                p.paragraph_format.first_line_indent = Inches(-0.2)
                p.paragraph_format.space_after = Pt(2)
            
            # Standard Text
            else:
                doc.add_paragraph(clean_line).paragraph_format.space_after = Pt(4)

    buf = io.BytesIO()
    doc.save(buf)
    st.download_button(label=f"📥 Download {document_title}.docx", data=buf.getvalue(), file_name=f"{document_title}.docx")
