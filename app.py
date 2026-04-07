import streamlit as st
import PyPDF2
import docx
import io
import google.generativeai as genai

# Setup
st.set_page_config(page_title="Resume Formatter", page_icon="📄")
st.title("📄 One-Click Resume Formatter")

# API Configuration
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Setup Error: Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Using the most stable 'latest' version name
model = genai.GenerativeModel('gemini-1.5-flash-latest')

uploaded_file = st.file_uploader("Upload Before Resume (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Format My Resume"):
        with st.spinner("AI is re-writing your resume..."):
            try:
                # 1. Read the PDF
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = ""
                for page in pdf_reader.pages:
                    raw_text += page.extract_text() or ""

                # 2. Advanced Prompt to match your 'After' document style
                prompt = f"""
                Reformat the following resume text into a professional structure. 
                STRICTLY use these exact headers in this order:
                
                1. Name (Center this at the top)
                2. Summary: (Professional paragraph)
                3. Skills: (A clean list)
                4. Education: (Degree, Date, and Institution)
                5. Licensed CPA: (Include active licenses and states)
                6. Work Experience: (Company Name, Dates, Title, and Bullet Points)
                
                Remove any 'Source' tags or page numbers.
                
                RESUME DATA:
                {raw_text}
                """
                
                response = model.generate_content(prompt)
                
                if response.text:
                    # 3. Create Word Document
                    doc = docx.Document()
                    # Remove markdown bolding from AI response for a clean Word look
                    clean_output = response.text.replace('**', '').replace('__', '')
                    
                    for line in clean_output.split('\n'):
                        doc.add_paragraph(line)
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    st.success("Formatting Complete!")
                    st.download_button(
                        label="Download Formatted Resume (.docx)",
                        data=bio.getvalue(),
                        file_name="Formatted_Resume.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            except Exception as e:
                st.error(f"Error: {str(e)}")
