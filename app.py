import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os
from PIL import Image 

# --- 1. Page Setup & Professional Styling ---
st.set_page_config(page_title="ResumePro | AI Formatter", layout="wide", page_icon="📄")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; border: none; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #28a745; color: white; border: none; font-weight: bold; }
    div[data-testid="stExpander"] { border: 1px solid #dee2e6; border-radius: 10px; background-color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI Configuration ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("API Key missing. Please set GEMINI_API_KEY in Streamlit Secrets.")

# --- 3. Initialization ---
if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""
if 'usage_data' not in st.session_state:
    st.session_state.usage_data = None

# --- 4. Sidebar: Control Center ---
with st.sidebar:
    st.title("🚀 Control Center")
    
    with st.expander("🏢 BRANDING & ID", expanded=True):
        company_choice = st.selectbox("Company Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        document_title = st.text_input("Document Title (Middle Header)", value="RESUME")
    
    with st.expander("⚙️ AI CONFIGURATION", expanded=True):
        include_summary = st.checkbox("Generate AI Summary", value=True)
        st.caption("Uncheck to save tokens if a summary is not needed.")

    with st.expander("🔄 SECTION REORDER (JUMBLE)", expanded=True):
        default_order = ["SUMMARY:", "EXPERIENCE:", "EDUCATION:", "SKILLS:", "PROJECTS:", "CERTIFICATIONS:", "TOOLS:"]
        header_order = st.multiselect(
            "Drag & Drop sequence:",
            options=default_order,
            default=["SUMMARY:", "EXPERIENCE:", "EDUCATION:", "SKILLS:"]
        )

# --- 5. Helper Functions ---
UNIFORM_SPACE = Pt(12) # Uniform spacing for sections and entries

def set_arial_font(doc):
    """Forces the document's default font to Arial."""
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(11)

def get_sections_dict(text):
    """Parses text into a dictionary based on ALL CAPS headers for easy reordering."""
    sections = {}
    current_header = None
    for line in text.split('\n'):
        clean = line.strip()
        if not clean: continue
        
        # Detect Header (ALL CAPS ending in colon)
        if clean.isupper() and clean.endswith(":"):
            current_header = clean
            sections[current_header] = []
        elif current_header:
            sections[current_header].append(clean)
    return sections

# --- 6. Main UI & AI Generation ---
st.subheader("📄 Professional Resume Formatter")
uploaded_file = st.file_uploader("Upload Source Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])

# TOKEN SAVING: API only called when this button is clicked
if uploaded_file and st.button("✨ Generate Professional Draft"):
    with st.status("AI is analyzing and formatting...", expanded=True) as status:
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            summary_prompt = "ALWAYS generate a 'SUMMARY:' section at the beginning." if include_summary else "DO NOT generate a summary section."
            
            prompt = f"""
            Reformat this resume keeping ONLY its original sections. 
            Change all headers to ALL CAPS and end them with a colon.
            {summary_prompt}
            For Work Experience/Education, use: 'Company Name/University | Date Range'.
            Ensure the Job Title/Degree is on the very next line below the Company/University.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date.
            For Skills, Tools, Technical Tools, and Certifications, put each item on a new line.
            Do not put numbers before headers or bolding (**) in the text.
            """
            
            # Read Input
            input_data = None
            if uploaded_file.type == "application/pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                input_data = prompt + "\nTEXT:\n" + "".join([p.extract_text() for p in reader.pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc_file = docx.Document(uploaded_file)
                input_data = prompt + "\nTEXT:\n" + "\n".join([p.text for p in doc_file.paragraphs])
            else: # Image
                input_data = [prompt, Image.open(uploaded_file)]
            
            response = model.generate_content(input_data)
            
            # Save AI output to session state
            st.session_state.original_ai_output = response.text.replace("**", "")
            st.session_state.usage_data = response.usage_metadata
            
            status.update(label="Draft Ready!", state="complete", expanded=False)
            st.toast("AI Processing Complete!", icon="✅")
            
        except Exception as e:
            st.error(f"Error: {e}")

# --- 7. Editor & Document Builder ---
if st.session_state.original_ai_output:
    tab1, tab2 = st.tabs(["🖋️ Document Editor", "📊 Token Usage"])
    
    with tab1:
        # Live text editor: Changes here are instantly reflected in the downloaded doc
        edited_text = st.text_area("Final Polish (Make manual edits here before downloading):", 
                                   value=st.session_state.original_ai_output, height=450)
    
    with tab2:
        if st.session_state.usage_data:
            c1, c2, c3 = st.columns(3)
            c1.metric("Prompt Tokens", st.session_state.usage_data.prompt_token_count)
            c2.metric("Response Tokens", st.session_state.usage_data.candidates_token_count)
            c3.metric("Total Tokens Used", st.session_state.usage_data.total_token_count)
            st.caption("Editing text or reordering sections below does NOT consume additional tokens.")

    # --- BUILD THE WORD DOCUMENT (Runs dynamically in memory) ---
    template_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
    t_path = os.path.join(os.path.dirname(__file__), template_map.get(company_choice, ""))
    doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()
    set_arial_font(doc)

    # 1. Top Right Contact Info
    p_top = doc.add_paragraph()
    p_top.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_c = p_top.add_run(f"If you would like to interview this\ncandidate, please call {contact_number}")
    run_c.bold, run_c.font.size, run_c.font.name = True, Pt(11), 'Arial'

    # 2. Dynamic Title (Centered)
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = p_title.add_run(document_title.upper())
    run_t.bold, run_t.font.size, run_t.font.name = True, Pt(16), 'Arial'
    p_title.paragraph_format.space_after = UNIFORM_SPACE

    # 3. Process Content Based on 'Jumble' Order
    content_dict = get_sections_dict(edited_text)
    bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]

    for header in header_order:
        if header in content_dict:
            # Add Header
            h_para = doc.add_paragraph()
            h_para.paragraph_format.space_before = UNIFORM_SPACE
            h_run = h_para.add_run(header)
            h_run.bold, h_run.font.size, h_run.font.name = True, Pt(12), 'Arial'

            last_was_company = False
            for line in content_dict[header]:
                
                # Bullet Points
                if any(bh in header for bh in bullet_headers):
                    p_b = doc.add_paragraph(f"• {line.lstrip('*-• ')}")
                    p_b.paragraph_format.left_indent = Inches(0.25)
                    p_b.paragraph_format.space_after = Pt(0)
                    for run in p_b.runs: 
                        run.font.name = 'Arial'
                
                # Experience/Education Entries
                elif "|" in line:
                    # Maintain uniform spacing between entries
                    doc.add_paragraph().paragraph_format.space_before = UNIFORM_SPACE
                    
                    table = doc.add_table(rows=1, cols=2)
                    table.autofit = False
                    c_l, c_r = table.rows[0].cells[0], table.rows[0].cells[1]
                    c_l.width, c_r.width = Inches(5.0), Inches(2.0)
                    
                    parts = line.split("|")
                    c_run = c_l.paragraphs[0].add_run(parts[0].strip().upper())
                    c_run.bold, c_run.font.name = True, 'Arial' # Bold Company
                    
                    p_date = c_r.paragraphs[0]
                    p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    r_d = p_date.add_run(parts[-1].strip())
                    r_d.italic, r_d.font.size, r_d.font.name = True, Pt(10), 'Arial'
                    
                    last_was_company = True
                
                # Body Text / Job Titles
                else:
                    p_body = doc.add_paragraph()
                    if last_was_company:
                        run_j = p_body.add_run(line.title())
                        run_j.bold, run_j.font.name = False, 'Arial' # Job Title Not Bold
                        p_body.paragraph_format.space_after = Pt(8) # Space after Job Title
                        last_was_company = False
                    else:
                        run_txt = p_body.add_run(line)
                        run_txt.font.name = 'Arial'
                        p_body.paragraph_format.space_after = Pt(4)

    # --- 8. Download Button ---
    buf = io.BytesIO()
    doc.save(buf)
    st.divider()
    st.download_button(
        label=f"📥 Download Formatted {company_choice} Resume",
        data=buf.getvalue(),
        file_name=f"{document_title}_{company_choice}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
