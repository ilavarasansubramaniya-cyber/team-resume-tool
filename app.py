import streamlit as st
import PyPDF2
import docx
import io
import google.generativeai as genai

st.set_page_config(page_title="Resume Formatter", page_icon="📄")
st.title("📄 One-Click Resume Formatter")

# API Setup
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please add your API key to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Simplified model selection
model = genai.GenerativeModel('gemini-1.5-flash')

uploaded_file = st.file_uploader("Upload Before Resume (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Format My Resume"):
        with st.spinner("Processing..."):
            try:
                # 1. Get Text
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = ""
                for page in reader.pages:
                    raw_text += page.extract_text() or ""

                # 2. Format with AI
                # This prompt is tuned to your 'After' document [cite: 95-118]
                prompt = f"""
                Reformat this resume into these exact sections:
                Summary, Skills, Education, Licensed CPA, and Work Experience.
                Use a professional tone. Remove any page numbers or 'Source' labels.
                
                RESUME TEXT:
                {raw_text}
                """
                
                response = model.generate_content(prompt)
                
                # 3. Build Word File
                doc = docx.Document()
                clean_text = response.text.replace('**', '') # Clean bold markers
                
                for line in clean_text.split('\n'):
                    doc.add_paragraph(line)
                
                output = io.BytesIO()
                doc.save(output)
                
                st.success("Ready for download!")
                st.download_button(
                    label="Download Formatted Resume (.docx)",
                    data=output.getvalue(),
                    file_name="Formatted_Resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            except Exception as e:
                st.error(f"Something went wrong: {e}")
