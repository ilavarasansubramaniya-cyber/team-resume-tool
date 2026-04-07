import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os

# --- Page Setup ---
st.set_page_config(page_title="Executive Resume Formatter", layout="wide")

# --- AI Configuration ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Sidebar Controls ---
st.sidebar.title("🏢 Selection & ID")
company_choice = st.sidebar.selectbox("Select Sister Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="123-456-7890")

logo_map = {"W3G": "w3g.png", "Synectics": "synectics.jpg", "ProTouch": "protouch.png"}

# --- Main Interface ---
st.title("📄 Professional Resume Builder")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload PDF Resume", type="pdf")

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Reformatting data..."):
        reader = PyPDF2.PdfReader(uploaded_file)
        raw_text = "".join([p.extract_text() for p in reader.pages])
        
        # Explicit instructions for AI formatting
        prompt = f"""
        Reformat this resume into these EXACT sections: SUMMARY:, SKILLS:, EDUCATION:, LICENSED CPA:, WORK EXPERIENCE:.
        - All headers must be in ALL CAPS.
        - For Work Experience, use the format: 'Company Name | Date Range'
        - Ensure the Job Title is on the very next line.
        - No numbers before headers.
        TEXT: {raw_text}
        """
        response = model.generate_content(prompt)
        st.session_state.edited_content = response.text.replace("**", "")

if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Edit Window:", value=st.session_state.edited_content, height=450)

    if st.button("Download Final Word Doc"):
        doc = docx.Document()
        
        # --- 1. TOP-RIGHT BRANDING ---
        head_table = doc.add_table(rows=1, cols=2)
        head_table.width = Inches(6.5)
        cell_right = head_table.rows[0].cells[1]
        p_right = cell_right.paragraphs[0]
        p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # Large Logo
        logo_path = logo_map[company_choice]
        if os.path.exists(logo_path):
            p_right.add_run().add_picture(logo_path, width=Inches(2.5))
        
        # Interview Call-to-Action
        p_contact = cell_right.add_paragraph()
        p_contact.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_c = p_contact.add_run(f"If you would like to interview this\ncandidate, please call {contact_number}")
        run_c.font.size = Pt(9)
        run_c.italic = True

        # --- 2. CENTERED "RESUME" TITLE ---
        res_p = doc.add_paragraph()
        res_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        res_run = res_p.add_run("RESUME")
        res_run.bold = True
        res_run.font.size = Pt(16)
        res_p.paragraph_format.space_after = Pt(12)

        # --- 3. CONTENT FORMATTING ---
        headers = ["SUMMARY:", "SKILLS:", "EDUCATION:", "LICENSED CPA:", "WORK EXPERIENCE:"]
        current_section = ""
        last_line_was_company = False

        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

            # Header Styling: BOLD, CAPS, 0.5 line space (6pt)
            if any(h in line.upper() for h in headers):
                current_section = line.upper()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6) 
                p.paragraph_format.space_after = Pt(6)  
                p.paragraph_format.keep_with_next = True
                run = p.add_run(line.upper())
                run.bold = True
                run.font.size = Pt(12)
                last_line_was_company = False
                continue

            # Skills logic: Use bullet points
            if "SKILLS:" in current_section and "|" in line:
                for s in line.split("|"):
                    doc.add_paragraph(s.strip(), style='List Bullet')
            
            # Company | Date Logic: BOLD, CAPS
            elif "|" in line:
                row_table = doc.add_table(rows=1, cols=2)
                row_table.width = Inches(6.5)
                parts = line.split("|")
                # Company Name in CAPS & BOLD
                comp_run = row_table.rows[0].cells[0].paragraphs[0].add_run(parts[0].strip().upper())
                comp_run.bold = True
                # Date on Right (Italic)
                p_d = row_table.rows[0].cells[1].paragraphs[0]
                p_d.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p_d.add_run(parts[1].strip()).italic = True
                last_line_was_company = True 
            
            else:
                p_body = doc.add_paragraph()
                # If following a company line, this is the Job Title: BOLD & CAPS
                if last_line_was_company and "WORK EXPERIENCE:" in current_section:
                    run_job = p_body.add_run(line.upper())
                    run_job.bold = True
                    last_line_was_company = False
                else:
                    p_body.add_run(line)
                p_body.paragraph_format.space_after = Pt(2)

        # --- 4. BOTTOM FOOTER ---
        doc.add_paragraph()
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_text = p_foot.add_run(f"If you would like to interview this candidate, please call {contact_number}")
        f_text.bold = True
        f_text.font.color.rgb = RGBColor(0, 51, 153)

        # Finalize
        buf = io.BytesIO()
        doc.save(buf)
        st.success("Resume Polished and Ready!")
        st.download_button("Download Final Resume", buf.getvalue(), f"Formatted_Resume.docx")
