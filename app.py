import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
import io
import google.generativeai as genai
import os

# --- Page Setup ---
st.set_page_config(page_title="Executive Resume Builder", layout="wide")

# --- API Setup ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Sidebar ---
st.sidebar.title("Branding & ID")
company_choice = st.sidebar.selectbox("Select Sister Company", ["W3G", "Synectics", "ProTouch"])
company_id = st.sidebar.text_input("Enter Company Number/ID", value="12345")

logo_map = {"W3G": "w3g.png", "Synectics": "synectics.jpg", "ProTouch": "protouch.png"}

# --- Main App ---
st.title("📄 Executive Resume Formatter")
if 'edited_content' not in st.session_state: st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file and st.button("Generate Draft"):
    with st.spinner("Styling..."):
        reader = PyPDF2.PdfReader(uploaded_file)
        raw_text = "".join([p.extract_text() for p in reader.pages])
        prompt = f"Reformat this resume. Headers: Summary, Skills, Education, Licensed CPA, Work Experience. Use 'Company | Date' for jobs/education. For Skills, put items separated by '|' on new lines. TEXT: {raw_text}"
        st.session_state.edited_content = model.generate_content(prompt).text.replace("**", "")

if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Edit:", value=st.session_state.edited_content, height=400)

    if st.button("Download Word Doc"):
        doc = docx.Document()
        
        # 1. BLUE HEADER DESIGN
        p_hdr = doc.add_paragraph()
        run_hdr = p_hdr.add_run("__________________________________________________________________________________________")
        run_hdr.font.color.rgb = RGBColor(0, 51, 153)
        
        # Table for ID and Logo
        table = doc.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = f"Ref ID: {company_id}"
        if os.path.exists(logo_map[company_choice]):
            p_logo = table.rows[0].cells[1].paragraphs[0]
            p_logo.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p_logo.add_run().add_picture(logo_map[company_choice], width=Inches(1.2))

        # 2. CONTENT FORMATTING
        headers = ["Summary", "Skills", "Education", "Licensed CPA", "Work Experience"]
        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue
            
            # Header check
            if any(h in line for h in headers):
                p = doc.add_paragraph()
                p.paragraph_format.page_break_before = True # Force next page if near bottom
                run = p.add_run(line.replace(":", ""))
                run.bold = True
                run.font.size = Pt(13)
            
            # Skills exception
            elif "Skills" in current_section and "|" in line:
                for s in line.split("|"): doc.add_paragraph(s.strip(), style='List Bullet')
            
            # Work/Edu table
            elif "|" in line:
                t = doc.add_table(rows=1, cols=2)
                parts = line.split("|")
                t.rows[0].cells[0].text = parts[0].strip()
                t.rows[0].cells[1].text = parts[1].strip()
                t.rows[0].cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            else:
                doc.add_paragraph(line)

        # Save
        target = io.BytesIO()
        doc.save(target)
        st.download_button("Download", target.getvalue(), "Resume.docx")
