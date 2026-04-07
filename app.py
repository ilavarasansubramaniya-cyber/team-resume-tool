import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import google.generativeai as genai
import os

# --- Page Config ---
st.set_page_config(page_title="Corporate Resume Builder", layout="wide")

# --- UI Styling ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_base_code=True)

# --- API Setup ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- Sidebar: Company Selection ---
st.sidebar.title("🏢 Branding Settings")
company_choice = st.sidebar.selectbox(
    "Select Sister Company",
    ["W3G", "Synectics", "ProTouch"]
)

# Mapping logos to filenames (Make sure these are uploaded to your GitHub)
logo_map = {
    "W3G": "w3g.png",
    "Synectics": "synectics.jpg",
    "ProTouch": "protouch.png"
}

# --- Step 1: Upload & Process ---
st.title("📄 One-Click Professional Formatter")
uploaded_file = st.file_uploader("Upload 'Before' Resume (PDF)", type="pdf")

# Initialize session state for the editor
if 'resume_content' not in st.session_state:
    st.session_state.resume_content = ""

if uploaded_file:
    if st.button("Step 1: Generate AI Draft"):
        with st.spinner("Extracting and Reformatting..."):
            reader = PyPDF2.PdfReader(uploaded_file)
            raw_text = "".join([p.extract_text() for p in reader.pages])
            
            prompt = f"""
            Reformat this resume to match a high-end executive template.
            Use these EXACT headers: Summary:, Skills:, Education:, Licensed CPA:, Work Experience:.
            
            Formatting Rules:
            - Put the candidate's Name at the very top.
            - For Work Experience and Education, put the Dates on the same line as the Company/Degree.
            - Clean up bullet points.
            - Current Company for this output is {company_choice}.
            
            TEXT: {raw_text}
            """
            response = model.generate_content(prompt)
            st.session_state.resume_content = response.text.replace("**", "")

# --- Step 2: Live Editor ---
if st.session_state.resume_content:
    st.subheader("Step 2: Preview & Edit Window")
    st.caption("Edit the text below. What you see is what will be saved to Word.")
    
    # The Editor
    edited_text = st.text_area(
        label="Final Content Editor",
        value=st.session_state.resume_content,
        height=450
    )

    # --- Step 3: Export to Word ---
    if st.button("Step 3: Export to Branded Word Doc"):
        doc = docx.Document()
        
        # Add Logo if file exists
        logo_path = logo_map[company_choice]
        if os.path.exists(logo_path):
            doc.add_picture(logo_path, width=Inches(1.5))
            last_p = doc.paragraphs[-1]
            last_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Process the edited text into the Word Doc
        lines = edited_text.split('\n')
        for line in lines:
            if any(header in line for header in ["Summary:", "Skills:", "Education:", "Licensed CPA:", "Work Experience:"]):
                # Style Headers (Blue and Bold)
                p = doc.add_paragraph()
                run = p.add_run(line)
                run.bold = True
                run.font.size = Pt(12)
                run.font.color.rgb = RGBColor(0, 51, 153) # Dark Blue
                # Add a bottom border (Simplified as a line)
                p.paragraph_format.space_before = Pt(12)
            else:
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(2)

        # Save and Download
        target = io.BytesIO()
        doc.save(target)
        st.success(f"Successfully branded for {company_choice}!")
        st.download_button(
            label="⬇️ Download Final Resume",
            data=target.getvalue(),
            file_name=f"Formatted_Resume_{company_choice}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

else:
    st.info("Upload a resume and click 'Generate' to begin.")
