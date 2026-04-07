import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import io
import google.generativeai as genai
import os

# --- Page Setup ---
st.set_page_config(page_title="Executive Resume Formatter", layout="wide")

# --- API Setup ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Sidebar: Branding ---
st.sidebar.title("🏢 Company Branding")
company_choice = st.sidebar.selectbox("Select Sister Company", ["W3G", "Synectics", "ProTouch"])

logo_map = {
    "W3G": "w3g.png",
    "Synectics": "synectics.jpg",
    "ProTouch": "protouch.png"
}

# --- Main Interface ---
st.title("📄 Executive Resume Builder")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload PDF Resume", type="pdf")

if uploaded_file:
    if st.button("Step 1: Generate AI Draft"):
        with st.spinner("Styling your resume..."):
            reader = PyPDF2.PdfReader(uploaded_file)
            raw_text = "".join([p.extract_text() for p in reader.pages])
            
            prompt = f"""
            Reformat this resume text into a professional, high-end format.
            - Use these headers: Summary:, Skills:, Education:, Licensed CPA:, Work Experience:.
            - Important: Separate Company/Degree names from Dates using a '|' symbol so I can format them (e.g. 'Deloitte | 1996 - 2003').
            - Do not include numbers before headers.
            - Ensure the tone is executive and clean.
            TEXT: {raw_text}
            """
            response = model.generate_content(prompt)
            st.session_state.edited_content = response.text.replace("**", "")

if st.session_state.edited_content:
    st.subheader("Step 2: Preview & Edit")
    st.session_state.edited_content = st.text_area("Edit text here:", value=st.session_state.edited_content, height=450)

    if st.button("Step 3: Download Appealing Word Doc"):
        doc = docx.Document()
        
        # --- 1. Top Logo (Right Aligned) ---
        logo_file = logo_map[company_choice]
        if os.path.exists(logo_file):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = p.add_run()
            run.add_picture(logo_file, width=Inches(1.6))

        # --- 2. Content Formatting ---
        headers = ["Summary:", "Skills:", "Education:", "Licensed CPA:", "Work Experience:"]
        
        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

            # Header Style
            if any(h in line for h in headers):
                p = doc.add_paragraph()
                run = p.add_run(line)
                run.bold = True
                run.font.color.rgb = RGBColor(0, 51, 153) # Professional Blue
                run.font.size = Pt(12)
                # Subtle underline effect
                p.paragraph_format.space_before = Pt(12)
            
            # Date Alignment (Look for the | separator)
            elif "|" in line:
                table = doc.add_table(rows=1, cols=2)
                table.width = Inches(6.5)
                cells = table.rows[0].cells
                parts = line.split("|")
                
                # Left side (Company/Degree)
                p_left = cells[0].paragraphs[0]
                run_l = p_left.add_run(parts[0].strip())
                run_l.bold = True
                
                # Right side (Date)
                p_right = cells[1].paragraphs[0]
                p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                run_r = p_right.add_run(parts[1].strip())
                run_r.italic = True
            
            # Standard Body Text
            else:
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(2)

        # --- 3. Bottom Footer Line ---
        section = doc.sections[0]
        footer = section.footer
        p_foot = footer.paragraphs[0]
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_foot = p_foot.add_run("__________________________________________________________________")
        run_foot.font.color.rgb = RGBColor(200, 200, 200) # Light gray line

        # Save
        target = io.BytesIO()
        doc.save(target)
        st.success("Resume Polished! Ready for download.")
        st.download_button("Download Styled Resume", target.getvalue(), f"{company_choice}_Professional.docx")
