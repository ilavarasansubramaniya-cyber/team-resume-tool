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

def replace_placeholder_in_doc(doc, placeholder, replacement):
    """Deep search and replace for template placeholders."""
    for p in doc.paragraphs:
        if placeholder in p.text:
            for run in p.runs:
                run.text = run.text.replace(placeholder, replacement)
    # Check tables (often used in headers)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if placeholder in p.text:
                        p.text = p.text.replace(placeholder, replacement)

# --- 5. Main Hero Section ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Drop Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])
generate_btn = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🛠️ Processing...", expanded=True):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            sum_p = f"ALWAYS generate a 'SUMMARY:' section focusing on: {custom_points}" if include_summary else "No summary."
            priv_p = "CRITICAL: Replace all employer names with '[CONFIDENTIAL]'." if make_confidential else ""

            prompt = f"""
            TASK: Reformat this resume.
            Headers: ALL CAPS ending in colon (e.g. SKILLS:).
            {sum_p}
            {priv_p}
            Experience/Education: 'Company or School | Date Range'.
            Job Title: Next line after company.
            Skills: One per line.
            """
            
            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            else:
                raw = Image.open(uploaded_file)
            
            response = model.generate_content([prompt, raw] if not isinstance(raw, str) else [prompt, f"TEXT:\n{raw}"])
            st.session_state.original_ai_output = response.text.replace("**", "")
            st.balloons()
        except Exception as e:
            st.error(f"Error: {e}")

# --- 6. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")
    content_dict = get_sections_dict(st.session_state.original_ai_output)
    header_order = st.sidebar.multiselect("Reorder Sections:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    c_edit, c_preview = st.columns([1.5, 1])
    with c_edit:
        final_text = st.text_area("Live Editor:", value=st.session_state.original_ai_output, height=600)
    
    with c_preview:
        st.subheader("✅ Export Settings")
        if make_confidential:
            st.info("💡 Pro-tip: Double-check the redactions in the editor before downloading.")

        # --- Template Loading Logic ---
        t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
        t_path = t_map.get(company_choice)
        
        if os.path.exists(t_path):
            doc = docx.Document(t_path)
            st.write(f"✔️ Using {company_choice} Template")
        else:
            doc = docx.Document()
            st.warning("⚠️ Template file not found. Generating standard document.")

        # Replace Placeholders
        replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)
        replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title.upper())

        # Body Build
        new_content = get_sections_dict(final_text)
        for h in header_order:
            if h in new_content:
                # Add Header
                hp = doc.add_paragraph()
                hp.paragraph_format.space_before = Pt(12)
                hr = hp.add_run(h)
                hr.bold, hr.font.name, hr.font.size = True, 'Arial', Pt(12)
                
                is_skills = "SKILL" in h.upper()
                last_comp = False
                
                for line in new_content[h]:
                    if "|" in line:
                        # Professional Table for Experience/Education
                        tbl = doc.add_table(rows=1, cols=2)
                        tbl.autofit = False
                        cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
                        cl.width, cr.width = Inches(5.0), Inches(2.0)
                        parts = line.split("|")
                        cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                        cr.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        cr.paragraphs[0].add_run(parts[-1].strip()).italic = True
                        last_comp = True
                    elif is_skills:
                        # Add as Bullet Points
                        p = doc.add_paragraph(line, style='List Bullet')
                        p.paragraph_format.space_after = Pt(2)
                    else:
                        # Standard Text
                        p = doc.add_paragraph(line)
                        if last_comp:
                            p.paragraph_format.space_after = Pt(8)
                            last_comp = False

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(label=f"📥 DOWNLOAD {company_choice} DOCX", 
                            data=buf.getvalue(), 
                            file_name=f"{document_title}_{company_choice}.docx")
