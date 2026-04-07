import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os

# --- Page Setup ---
st.set_page_config(page_title="Resume Formatter Pro", layout="wide")

# --- API Setup (Gemini 2.5 Flash) ---
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
# Using the specific Gemini 2.5 Flash model name
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Sidebar: Company Branding ---
st.sidebar.title("🏢 Company Branding")
company_choice = st.sidebar.selectbox(
    "Select Logo to Apply:",
    ["W3G", "Synectics", "ProTouch"]
)

logo_map = {
    "W3G": "w3g.png",
    "Synectics": "synectics.jpg",
    "ProTouch": "protouch.png"
}

# --- Main App Interface ---
st.title("📄 One-Click Resume Formatter")
st.write(f"Currently Formatting for: **{company_choice}**")

# Initialize session state so text stays in the box when you edit it
if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload 'Before' Resume (PDF)", type="pdf")

if uploaded_file:
    if st.button("Step 1: Generate AI Draft"):
        with st.spinner("AI is analyzing and reformatting..."):
            # Read PDF
            reader = PyPDF2.PdfReader(uploaded_file)
            raw_text = "".join([p.extract_text() for p in reader.pages])
            
            # AI Prompt tuned to your REFERENCE RESUME.docx
            prompt = f"""
            Act as a professional resume editor. Reformat the following text to match this EXACT structure:
            1. Summary: (A concise paragraph)
            2. Skills: (A clean list)
            3. Education: (Degree, Date, and Institution)
            4. Licensed CPA: (License details)
            5. Work Experience: (Company, Dates, Title, and Bullet Points)
            
            Format dates to be on the same line as the Company/Degree.
            The target branding is {company_choice}.
            
            TEXT TO REFORMAT:
            {raw_text}
            """
            response = model.generate_content(prompt)
            st.session_state.edited_content = response.text.replace("**", "")

# --- Step 2: Preview and Edit Window ---
if st.session_state.edited_content:
    st.subheader("Step 2: Preview & Live Edit")
    st.info("You can edit the text directly in the box below before downloading.")
    
    # This is the interactive window you asked for
    st.session_state.edited_content = st.text_area(
        "Resume Content", 
        value=st.session_state.edited_content, 
        height=500
    )

    # --- Step 3: Create Branded Word Doc ---
    if st.button("Step 3: Download Branded Word Doc"):
        doc = docx.Document()
        
        # Add Logo to the Top Right (Matching Reference)
        logo_file = logo_map[company_choice]
        if os.path.exists(logo_file):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = p.add_run()
            run.add_picture(logo_file, width=Inches(1.8))
        else:
            st.warning(f"Note: {logo_file} not found in GitHub. Formatting text only.")

        # Add Content with Blue Headers (Matching Reference)
        for line in st.session_state.edited_content.split('\n'):
            p = doc.add_paragraph()
            
            # Identify Headers to apply Blue/Bold style
            headers = ["Summary:", "Skills:", "Education:", "Licensed CPA:", "Work Experience:"]
            if any(h in line for h in headers):
                run = p.add_run(line)
                run.bold = True
                run.font.color.rgb = RGBColor(0, 51, 153) # Dark Blue from Reference
                run.font.size = Pt(12)
                p.paragraph_format.space_before = Pt(12)
            else:
                p.add_run(line)
                p.paragraph_format.space_after = Pt(2)
        
        # Buffer for download
        target = io.BytesIO()
        doc.save(target)
        
        st.success(f"Final Resume for {company_choice} is ready!")
        st.download_button(
            label="⬇️ Download Final Word Document",
            data=target.getvalue(),
            file_name=f"Formatted_Resume_{company_choice}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
else:
    st.info("Upload a resume and click 'Generate' to begin.")
