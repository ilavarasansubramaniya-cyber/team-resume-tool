import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os

# --- Page Setup ---
st.set_page_config(page_title="Executive Resume Builder", layout="wide")

# --- AI Configuration ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Sidebar for company and contact info
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Sister Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="123-456-7890")

logo_map = {"W3G": "w3g.png", "Synectics": "synectics.jpg", "ProTouch": "protouch.png"}

# --- Main App Interface ---
st.title("📄 Professional Resume Builder")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload PDF Resume", type="pdf")

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Analyzing and formatting with Gemini 1.5 Flash..."):
        try:
            # Attempting to initialize the model
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            reader = PyPDF2.PdfReader(uploaded_file)
            raw_text = "".join([p.extract_text() for p in reader.pages])
            
            prompt = f"""
            Reformat this resume into these EXACT sections: SUMMARY:, SKILLS:, EDUCATION:, LICENSED CPA:, WORK EXPERIENCE:.
            - All headers must be in ALL CAPS.
            - For Work Experience/Education, use the format: 'Company Name/Degree | Date Range'
            - Ensure the Job Title is on the very next line.
            - No numbers before headers.
            TEXT: {raw_text}
            """
            response = model.generate_content(prompt)
            st.session_state.edited_content = response.text.replace("**", "")
        
        except Exception as e:
            # Fallback for "NotFound" errors by trying the full model path
            try:
                model = genai.GenerativeModel('models/gemini-1.5-flash')
                response = model.generate_content(prompt)
                st.session_state.edited_content = response.text.replace("**", "")
            except Exception as e2:
                st.error(f"AI Connection Error: {e2}. Please ensure your GEMINI_API_KEY is valid in Streamlit Secrets.")

if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Edit Window:", value=st.session_state.edited_content, height=450)

    if st.button("Download Final Word Doc"):
        doc = docx.Document()
        
        # --- 1. PAGE MARGINS ---
        section = doc.sections[0]
        section.top_margin = Inches(0.4) 
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

        # --- 2. LOGO AND TOP-RIGHT CONTACT ---
        head_table = doc.add_table(rows=1, cols=2)
        head_table.width = Inches(7.0)
        cell_right = head_table.rows[0].cells[1]
        p_right = cell_right.paragraphs[0]
        p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        logo_path = logo_map.get(company_choice)
        if logo_path and os.path.exists(logo_path):
            p_right.add_run().add_picture(logo_path, width=Inches(2.5))
        
        p_contact = cell_right.add_paragraph()
        p_contact.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_contact.paragraph_format.space_before = Pt(0)
        run_c = p_contact.add_run(f"If you would like to interview this\ncandidate, please call {contact_number}")
        run_c.font.size = Pt(11)
        run_c.bold = True

        # --- 3. CENTERED "RESUME" TITLE ---
        res_p = doc.add_paragraph()
        res_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        res_run = res_p.add_run("RESUME")
        res_run.bold = True
        res_run.font.size = Pt(16)
        res_p.paragraph_format.space_before = Pt(12)
        res_p.paragraph_format.space_after = Pt(12)

        # --- 4. CONTENT FORMATTING ---
        headers = ["SUMMARY:", "SKILLS:", "EDUCATION:", "LICENSED CPA:", "WORK EXPERIENCE:"]
        current_section = ""
        last_line_was_table = False

        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

            # Header Styling: BOLD, CAPS, 6pt (0.5 line) space
            if any(h in line.upper() for h in headers):
                current_section = line.upper()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6) 
                p.paragraph_format.space_after = Pt(6)  
                p.paragraph_format.keep_with_next = True
                run = p.add_run(line.upper()) 
                run.bold = True
                run.font.size = Pt(12)
                last_line_was_table = False
                continue

            # SKILLS: Keep original text
            if "SKILLS:" in current_section:
                doc.add_paragraph(line)
            
            # WORK/EDUCATION: Table layout for Date Alignment
            elif "|" in line:
                # Spacer before new entry (6pt matches header space)
                p_spacer = doc.add_paragraph()
                p_spacer.paragraph_format.space_before = Pt(6)
                
                row_table = doc.add_table(rows=1, cols=2)
                row_table.width = Inches(7.0)
                parts = line.split("|")
                
                # Left: Company/Degree (BOLD & CAPS)
                row_table.rows[0].cells[0].paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                
                # Right: Date Range (BOLD & ITALIC)
                p_d = row_table.rows[0].cells[1].paragraphs[0]
                p_d.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                run_date = p_d.add_run(parts[1].strip())
                run_date.bold = True
                run_date.italic = True
                
                last_line_was_table = True 
            
            else:
                p_body = doc.add_paragraph()
                # Job Title: BOLD & CAPS
                if last_line_was_table and "WORK EXPERIENCE:" in current_section:
                    run_job = p_body.add_run(line.upper()) 
                    run_job.bold = True
                    last_line_was_table = False
                else:
                    p_body.add_run(line)
                p_body.paragraph_format.space_after = Pt(2)

        # --- 5. BOTTOM FOOTER ---
        doc.add_paragraph()
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_text = p_foot.add_run(f"If you would like to interview this candidate, please call {contact_number}")
        f_text.bold = True
        f_text.font.color.rgb = RGBColor(0, 51, 153)

        buf = io.BytesIO()
        doc.save(buf)
        st.success("Download Ready!")
        st.download_button(
            label="Download Final Word Document",
            data=buf.getvalue(),
            file_name=f"Formatted_Resume_{company_choice}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
