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
        raw_title = st.text_input("Document Title", placeholder="RESUME")
        document_title = raw_title.strip().upper() if raw_title.strip() else "RESUME"
    
    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_points = st.text_area("Custom Points", placeholder="Leadership, ROI...")
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# --- 4. Logic Functions ---
def get_sections_dict(text):
    """Parses text into a dictionary based on UPPERCASE HEADERS ending in colons."""
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
            for run in p.runs:
                run.text = run.text.replace(placeholder, replacement)
                run.font.name = 'Arial'

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
            TASK: Reformat this resume.
            1. Headers: ALL CAPS ending in colon (e.g. SKILLS:).
            2. {sum_p}
            3. {priv_p}
            4. Experience/Education: 'Company/School | Date Range' (Dates MUST be on one line).
            5. Job Title: Next line after company.
            6. Descriptions: Bullet points.
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
    
    # Live Sync: Parse the current state of the text area
    c_edit, c_preview = st.columns([1.5, 1])
    
    with c_edit:
        st.markdown("#### 🖋️ Live Editor")
        final_text = st.text_area("Final Content Control:", value=st.session_state.original_ai_output, height=600, label_visibility="collapsed")

    # Update sections based on what is currently in the Live Editor
    current_sections = get_sections_dict(final_text)
    
    with st.sidebar:
        st.markdown("---")
        # If a header is deleted in final_text, it disappears from this list automatically
        header_order = st.multiselect("Reorder Active Sections:", 
                                      options=list(current_sections.keys()), 
                                      default=list(current_sections.keys()))

    with c_preview:
        st.markdown("#### ✅ Finalize")
        
        t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
        t_path = t_map.get(company_choice)
        doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()

        # Global Font Setting
        style = doc.styles['Normal']
        style.font.name, style.font.size = 'Arial', Pt(10.5)

        replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)
        replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title)

        # Body Generation with Uniform Spacing
        for h in header_order:
            if h in current_sections:
                # Standardized Header Spacing (Matches Summary-to-Skills gap)
                hp = doc.add_paragraph()
                hp.paragraph_format.space_before = Pt(18) 
                hp.paragraph_format.space_after = Pt(10)
                hp.paragraph_format.keep_with_next = True
                
                hr = hp.add_run(h)
                hr.bold, hr.font.name, hr.font.size = True, 'Arial', Pt(11)
                
                is_list_section = any(x in h.upper() for x in ["SKILL", "SUMMARY", "EXPERIENCE", "EDUCATION"])

                for line in current_sections[h]:
                    if "|" in line:
                        # Job Entry Table: Forces Dates to stay on one line
                        tbl = doc.add_table(rows=1, cols=2)
                        tbl.autofit = False
                        cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
                        cl.width, cr.width = Inches(5.1), Inches(1.9)
                        parts = line.split("|")
                        cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                        p_right = cr.paragraphs[0]
                        p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        p_right.add_run(parts[-1].strip()).italic = True
                        tbl.rows[0].cells[0].paragraphs[0].paragraph_format.space_before = Pt(10) # Uniform gap between jobs
                    
                    elif len(line) < 60 and (line.isupper() or any(char.isdigit() for char in line) == False):
                        # Job Title Logic
                        p = doc.add_paragraph()
                        p.paragraph_format.space_after = Pt(4)
                        p.add_run(line).bold = True
                    
                    else:
                        # Bulleted Content (Description/Skills/Summary)
                        p = doc.add_paragraph()
                        p.paragraph_format.left_indent = Inches(0.25)
                        p.paragraph_format.first_line_indent = Inches(-0.15)
                        p.paragraph_format.space_after = Pt(3)
                        p.add_run(f"•\t{line}").font.name = 'Arial'

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(label=f"📥 DOWNLOAD {company_choice} DOCX", data=buf.getvalue(), file_name=f"{document_title}.docx")
