import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
from groq import Groq
import os
from PIL import Image 

# --- 1. Grand UI Config ---
st.set_page_config(page_title="ResumePro Elite", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    [data-testid="stSidebar"] { background-color: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); border-right: 1px solid rgba(255, 255, 255, 0.2); }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: linear-gradient(45deg, #007bff, #6610f2); color: white; font-weight: bold; border: none; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0, 123, 255, 0.3); }
    .stDownloadButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: linear-gradient(45deg, #28a745, #20c997); color: white; border: none; box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3); }
    div[data-testid="stExpander"] { background: white; border-radius: 15px; border: none; box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Groq Configuration ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error(f"Groq API Key Error: {e}")

if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""

# --- 3. Sidebar Control Center ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    st.write("🚀 Llama 4 Scout Engine")
    
    with st.expander("🏢 BRANDING & IDENTITY", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        document_title = st.text_input("Document Title", value="RESUME")
    
    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_summary_points = st.text_area("Custom Points to Develop", placeholder="e.g. Focus on leadership...", disabled=not include_summary)
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

# --- 5. Main UI & AI Call ---
st.title("Professional Resume Artisan")

uploaded_file = st.file_uploader("Upload Source Resume", type=["pdf", "docx"])
generate_btn = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🚀 Processing with Llama 4 Scout...", expanded=True) as status:
        try:
            sum_p = "DO NOT generate a summary."
            if include_summary:
                sum_p = f"ALWAYS generate a 'SUMMARY:' section. Develop these points into a narrative: '{custom_summary_points}'"
            
            priv_p = ""
            if make_confidential:
                priv_p = "MANDATORY: Anonymize the resume. Replace every single occurrence of an employer or company name with exactly '[CONFIDENTIAL]'. Do not show any company names."

            system_prompt = f"""
            You are an elite Resume Architect. Reformat the provided text exactly as follows:
            1. Headers: ALL CAPS ending with a colon (e.g., EXPERIENCE:).
            2. {sum_p}
            3. {priv_p}
            4. Work/Education Line 1: 'Company or University | Date Range'.
            5. Work/Education Line 2: The Job Title or Degree.
            6. CRITICAL: Use the '|' symbol ONLY for the Date Range line.
            7. For Skills and Certifications: List each item on a new line.
            8. NO markdown bolding (**) or numbering.
            """
            
            if uploaded_file.type == "application/pdf":
                raw_text = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            else:
                raw_text = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            
            chat_completion = client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": raw_text}],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.1,
            )
            
            st.session_state.original_ai_output = chat_completion.choices[0].message.content.replace("**", "")
            status.update(label="Complete!", state="complete")
        except Exception as e:
            st.error(f"API Error: {e}")

# --- 6. Editor & Export Logic ---
if st.session_state.original_ai_output:
    st.markdown("---")
    content_dict = get_sections_dict(st.session_state.original_ai_output)
    
    with st.sidebar:
        with st.expander("🔄 DYNAMIC JUMBLE", expanded=True):
            header_order = st.multiselect("Reorder Sections:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    final_text = st.text_area("Final Polish:", value=st.session_state.original_ai_output, height=450)
    
    # Building the DOCX
    t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
    t_path = os.path.join(os.path.dirname(__file__), t_map.get(company_choice, ""))
    doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()
    set_arial_font(doc)

    # 1. Handle Missing Title
    title_found = replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title.upper())
    if not title_found:
        t_para = doc.add_paragraph()
        t_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        t_run = t_para.add_run(document_title.upper())
        t_run.bold, t_run.font.size = True, Pt(16)

    replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)

    # 2. Re-establish Bullet Points Logic
    bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]
    new_content = get_sections_dict(final_text)

    for h in header_order:
        if h in new_content:
            hp = doc.add_paragraph()
            hp.paragraph_format.space_before = Pt(12)
            hr = hp.add_run(h)
            hr.bold, hr.font.size = True, Pt(12)
            
            last_comp = False
            for line in new_content[h]:
                # Bullet Logic
                if any(bh in h for bh in bullet_headers):
                    p_b = doc.add_paragraph(f"• {line.lstrip('*-• ')}")
                    p_b.paragraph_format.left_indent = Inches(0.25)
                    p_b.paragraph_format.space_after = Pt(0)
                
                # Table Logic (Date ranges)
                elif "|" in line:
                    doc.add_paragraph().paragraph_format.space_before = Pt(8)
                    tbl = doc.add_table(rows=1, cols=2)
                    tbl.autofit = False
                    cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
                    cl.width, cr.width = Inches(5.0), Inches(2.0)
                    parts = line.split("|")
                    cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                    p_dt = cr.paragraphs[0]
                    p_dt.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    rd = p_dt.add_run(parts[-1].strip())
                    rd.italic, rd.font.size = True, Pt(10)
                    last_comp = True
                
                # Body Text Logic
                else:
                    pb = doc.add_paragraph()
                    if last_comp:
                        pb.add_run(line.title()).bold = False
                        pb.paragraph_format.space_after = Pt(8)
                        last_comp = False
                    else:
                        pb.add_run(line)
                        pb.paragraph_format.space_after = Pt(4)

    buf = io.BytesIO()
    doc.save(buf)
    st.download_button(label="📥 Download Final Resume", data=buf.getvalue(), file_name=f"{document_title}.docx")
