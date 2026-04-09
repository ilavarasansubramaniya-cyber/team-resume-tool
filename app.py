import streamlit as st
from streamlit_lottie import st_lottie
import requests
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image 

# --- 1. Grand UI Config & Animations ---
st.set_page_config(page_title="ResumePro Elite", layout="wide", page_icon="💎")

def load_lottieurl(url: str):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

# Load Animations with fallback logic
lottie_ai = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_gssu2dkm.json")
lottie_success = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_xl3s9at1.json")

# Custom CSS for "Grand" Glassmorphism Look
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    
    /* Glassmorphism Sidebar */
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.4);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    /* Grand Buttons */
    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.5em;
        background: linear-gradient(45deg, #007bff, #6610f2);
        color: white; font-weight: bold; border: none;
        transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0, 123, 255, 0.3);
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0, 123, 255, 0.5); }
    
    .stDownloadButton>button {
        width: 100%; border-radius: 12px; height: 3.5em;
        background: linear-gradient(45deg, #28a745, #20c997);
        color: white; border: none; box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
    }

    /* Card Styling */
    div[data-testid="stExpander"] {
        background: white; border-radius: 15px; border: none;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI & Session Logic ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("API Key missing in Streamlit Secrets.")

if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""
if 'usage_data' not in st.session_state:
    st.session_state.usage_data = None

# --- 3. Sidebar Control Center ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    if lottie_ai:
        st_lottie(lottie_ai, height=120, key="ai_icon")
    else:
        st.write("🤖 AI Engine Active")
    
    with st.expander("🏢 BRANDING & IDENTITY", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        document_title = st.text_input("Document Title", value="RESUME")
    
    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_summary_points = st.text_area("Custom Points to Develop", 
                                            placeholder="e.g. Focus on leadership and ROI...", 
                                            disabled=not include_summary)
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
    for p in doc.paragraphs:
        if placeholder in p.text:
            for run in p.runs: run.text = run.text.replace(placeholder, replacement)
    for section in doc.sections:
        for header in [section.header, section.first_page_header]:
            if header:
                for p in header.paragraphs:
                    if placeholder in p.text:
                        for run in p.runs: run.text = run.text.replace(placeholder, replacement)

# --- 5. Main Hero Section ---
st.title("Professional Resume Artisan")
st.markdown("### Elevate your candidate presentation with AI-driven precision.")

col1, col2 = st.columns([2, 1])
with col1:
    uploaded_file = st.file_uploader("Drop Resume (PDF, DOCX, or Image)", type=["pdf", "docx", "png", "jpg", "jpeg"])
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🚀 Transforming Content...", expanded=True) as status:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # AI Logic construction
            sum_p = "DO NOT generate a summary."
            if include_summary:
                sum_p = f"ALWAYS generate a 'SUMMARY:' section. Professionally develop these points into the narrative: '{custom_summary_points}'"
            
            priv_p = "CRITICAL: Replace ALL employer names in the Work Experience section with exactly '[CONFIDENTIAL]'." if make_confidential else ""

            prompt = f"""
            Reformat this resume perfectly. 
            Headers: ALL CAPS ending in colon.
            {sum_p}
            {priv_p}
            Experience/Education: 'Company/University | Date Range'.
            Job Title on very next line. ONLY use '|' for date separation.
            One skill/tool per line. No bolding (**) or numbers.
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
            st.session_state.usage_data = response.usage_metadata
            status.update(label="Transformation Complete!", state="complete", expanded=False)
            st.balloons()
        except Exception as e:
            st.error(f"System Error: {e}")

# --- 6. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")
    content_dict = get_sections_dict(st.session_state.original_ai_output)
    
    with st.sidebar:
        with st.expander("🔄 DYNAMIC JUMBLE", expanded=True):
            header_order = st.multiselect("Reorder Sections:", options=list(content_dict.keys()), default=list(content_dict.keys()))

    c_edit, c_preview = st.columns([1.5, 1])
    with c_edit:
        st.markdown("#### 🖋️ Live Editor")
        final_text = st.text_area("Refine AI Output:", value=st.session_state.original_ai_output, height=500, label_visibility="collapsed")
    
    with c_preview:
        st.markdown("#### ✅ Final Steps")
        if lottie_success:
            st_lottie(lottie_success, height=200, key="success_icon")
        else:
            st.success("Transformation Complete!")
            
        st.info("Review your changes. The order in the sidebar will be reflected in the final document.")
        
        # Build Document
        t_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
        t_path = os.path.join(os.path.dirname(__file__), t_map.get(company_choice, ""))
        doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()
        set_arial_font(doc)
        replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)
        replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title.upper())

        # Body Build Logic
        new_content = get_sections_dict(final_text)
        for h in header_order:
            if h in new_content:
                hp = doc.add_paragraph()
                hp.paragraph_format.space_before = Pt(12)
                hr = hp.add_run(h)
                hr.bold, hr.font.size, hr.font.name = True, Pt(12), 'Arial'
                
                last_comp = False
                for line in new_content[h]:
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
                        last_comp = True
                    else:
                        pb = doc.add_paragraph()
                        if last_comp:
                            rj = pb.add_run(line.title())
                            rj.font.name = 'Arial'
                            pb.paragraph_format.space_after = Pt(8)
                            last_comp = False
                        else:
                            rt = pb.add_run(line)
                            rt.font.name = 'Arial'
                            pb.paragraph_format.space_after = Pt(4)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(label=f"📥 DOWNLOAD {company_choice.upper()} DOCX", 
                           data=buf.getvalue(), 
                           file_name=f"{document_title}_{company_choice}.docx")
