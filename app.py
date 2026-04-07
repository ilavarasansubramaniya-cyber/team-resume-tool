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

# --- API Setup ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Sidebar ---
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Sister Company", ["W3G", "Synectics", "ProTouch"])
contact_info = st.sidebar.text_input("Enter Reference/Phone Number", value="123-456-7890")

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
        Reformat this resume into: Summary:, Skills:, Education:, Licensed CPA:, Work Experience:.
        - Use 'Company/Degree | Date' format for jobs and education.
        - Ensure NO numbers before headers.
        TEXT: {raw_text}
        """
        response = model.generate_content(prompt)
        st.session_state.edited_content = response.text.replace("**", "")

if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Edit Window:", value=st.session_state.edited_content, height=400)

    if st.button("Download Final Word Doc"):
        doc = docx.Document()
        
        # --- 1. TOP BORDER FRAME ---
        if os.path.exists("Frame PNG.jpg"):
            # This spans the top of the page
            doc.add_picture("Frame PNG.jpg", width=Inches(6.5))
        
        # --- 2. LOGO AND CONTACT DETAILS (TOP RIGHT) ---
        # Create a table for alignment
        head_table = doc.add_table(rows=1, cols=2)
        head_table.width = Inches(6.5)
        
        # Right Cell: Logo then Contact Details below it
        cell_right = head_table.rows[0].cells[1]
        p_right = cell_right.paragraphs[0]
        p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # Add Logo
        logo_path = logo_map[company_choice]
        if os.path.exists(logo_path):
            p_right.add_run().add_picture(logo_path, width=Inches(1.5))
        
        # Add Contact Detail line immediately below logo
        p_contact = cell_right.add_paragraph()
        p_contact.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_contact = p_contact.add_run(f"Ref: {contact_info}")
        run_contact.font.size = Pt(10)
        run_contact.bold = True

        # --- 3. CONTENT FORMATTING ---
        headers = ["Summary:", "Skills:", "Education:", "Licensed CPA:", "Work Experience:"]
        current_section = ""

        lines = st.session_state.edited_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue

            # Header Styling (Black, Bold, Space Before & After)
            if any(h in line for h in headers):
                current_section = line
                doc.add_paragraph() # 1 line space before
                p = doc.add_paragraph()
                p.paragraph_format.keep_with_next = True
                run = p.add_run(line)
                run.bold = True
                run.font.size = Pt(12)
                run.font.color.rgb = RGBColor(0, 0, 0)
                doc.add_paragraph() # 1 line space after
                continue

            # Skills logic: split by pipe to new lines
            if "Skills:" in current_section and "|" in line:
                for s in line.split("|"):
                    doc.add_paragraph(s.strip(), style='List Bullet')
            
            # Education/Work logic: Date only to the right
            elif "|" in line:
                row_table = doc.add_table(rows=1, cols=2)
                row_table.width = Inches(6.5)
                parts = line.split("|")
                
                # Left: Company/Title
                row_table.rows[0].cells[0].paragraphs[0].add_run(parts[0].strip()).bold = True
                # Right: Date Range
                p_date = row_table.rows[0].cells[1].paragraphs[0]
                p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p_date.add_run(parts[1].strip()).italic = True
            
            else:
                doc.add_paragraph(line)

        # --- 4. BOTTOM INTERVIEW CALL ---
        doc.add_paragraph() 
        doc.add_paragraph() 
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_text = p_foot.add_run(f"If you would like to interview this candidate, please call {contact_info}")
        f_text.bold = True
        f_text.font.color.rgb = RGBColor(0, 51, 153)

        # Buffer & Download
        buf = io.BytesIO()
        doc.save(buf)
        st.download_button("Download Final Resume", buf.getvalue(), f"Resume_{company_choice}.docx")
