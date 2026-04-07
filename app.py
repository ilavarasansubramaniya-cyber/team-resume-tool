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

# --- API Setup ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Sidebar ---
st.sidebar.title("🏢 Selection & ID")
company_choice = st.sidebar.selectbox("Select Sister Company", ["W3G", "Synectics", "ProTouch"])
company_id = st.sidebar.text_input("Enter Company Number/ID", value="12345")

logo_map = {"W3G": "w3g.png", "Synectics": "synectics.jpg", "ProTouch": "protouch.png"}

# --- Main App ---
st.title("📄 Professional Resume Builder")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload PDF Resume", type="pdf")

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Processing..."):
        reader = PyPDF2.PdfReader(uploaded_file)
        raw_text = "".join([p.extract_text() for p in reader.pages])
        
        prompt = f"""
        Reformat this resume into these exact sections: Summary:, Skills:, Education:, Licensed CPA:, Work Experience:.
        - NO numbers before headers.
        - For Education/Work Experience: Use 'Company/Degree | Date' format.
        - For Skills: List them clearly.
        TEXT: {raw_text}
        """
        response = model.generate_content(prompt)
        st.session_state.edited_content = response.text.replace("**", "")

if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Live Preview & Edit Window:", value=st.session_state.edited_content, height=450)

    if st.button("Download Final Branded Word Doc"):
        doc = docx.Document()
        
        # 1. HEADER DESIGN (BLUE LINE & LOGO)
        # Top Blue Border Line
        p_border = doc.add_paragraph()
        run_border = p_border.add_run("__________________________________________________________________________________________")
        run_border.font.color.rgb = RGBColor(0, 51, 153) # Royal Blue
        run_border.bold = True

        # Header Table (ID and Logo)
        table_hdr = doc.add_table(rows=1, cols=2)
        table_hdr.width = Inches(6.5)
        
        # Reference ID
        p_id = table_hdr.rows[0].cells[0].paragraphs[0]
        run_id = p_id.add_run(f"Reference ID: {company_id}")
        run_id.font.size = Pt(10)
        run_id.font.name = 'Arial'

        # Logo on the Right
        p_logo = table_hdr.rows[0].cells[1].paragraphs[0]
        p_logo.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        logo_path = logo_map[company_choice]
        if os.path.exists(logo_path):
            p_logo.add_run().add_picture(logo_path, width=Inches(1.4))

        doc.add_paragraph() # Space after header

        # 2. CONTENT FORMATTING
        headers = ["Summary:", "Skills:", "Education:", "Licensed CPA:", "Work Experience:"]
        current_section = ""

        lines = st.session_state.edited_content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue

            # Header Detection
            is_header = False
            for h in headers:
                if h in line:
                    current_section = h
                    is_header = True
                    p = doc.add_paragraph()
                    # Page Break Logic: keep header with next paragraph
                    p.paragraph_format.keep_with_next = True 
                    p.paragraph_format.space_before = Pt(18)
                    run = p.add_run(line)
                    run.bold = True
                    run.font.size = Pt(12)
                    run.font.color.rgb = RGBColor(0, 0, 0) # Black headers
                    break
            
            if is_header: continue

            # Skills logic: Pipe character (|) creates a new line
            if "Skills:" in current_section and "|" in line:
                for skill in line.split("|"):
                    doc.add_paragraph(skill.strip(), style='List Bullet')
            
            # Education/Work Logic: Pipe character (|) pushes date to Right
            elif "|" in line:
                table_row = doc.add_table(rows=1, cols=2)
                table_row.width = Inches(6.5)
                parts = line.split("|")
                
                # Left: Title/Company
                c_left = table_row.rows[0].cells[0].paragraphs[0]
                run_l = c_left.add_run(parts[0].strip())
                run_l.bold = True
                
                # Right: Date
                c_right = table_row.rows[0].cells[1].paragraphs[0]
                c_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                run_r = c_right.add_run(parts[1].strip())
                run_r.italic = True
                
                # Space after entry
                doc.add_paragraph().paragraph_format.space_after = Pt(4)

            else:
                p_body = doc.add_paragraph(line)
                p_body.paragraph_format.space_after = Pt(2)

        # 3. FOOTER (Optional light line)
        section = doc.sections[0]
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_run = footer.add_run("________________________________________________")
        f_run.font.color.rgb = RGBColor(200, 200, 200)

        # Save & Download
        buf = io.BytesIO()
        doc.save(buf)
        st.success("Successfully reformatted!")
        st.download_button("Download Final Resume", buf.getvalue(), f"Branded_Resume_{company_choice}.docx")
