import streamlit as st
import PyPDF2
import docx
import io
import google.generativeai as genai
import os

# Set up the webpage
st.set_page_config(page_title="Resume Formatter", page_icon="📄")
st.title("📄 One-Click Resume Formatter")
st.write("Upload a messy PDF resume, and we'll format it perfectly into a Word Document!")

# Securely get the API key
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    # We are using 'gemini-pro' as it is the most stable name
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error("Missing API Key. Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

uploaded_file = st.file_uploader("Upload your Before Resume (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Format My Resume"):
        with st.spinner("AI is re-writing your resume..."):
            try:
                # 1. Read the PDF
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = ""
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        raw_text += text

                # 2. Ask the AI to format it
                prompt = f"""
                You are a professional resume writer. Reformat the following text into a clean, 
                professional resume. 
                
                STRICT STRUCTURE TO FOLLOW:
                - Name at the top
                - Summary Section
                - Skills Section (Bullet points)
                - Education Section
                - Licenses Section
                - Work Experience Section (Company, Title, Dates, and clear Bullet Points)
                
                Text to format:
                {raw_text}
                """
                
                response = model.generate_content(prompt)
                
                if response.text:
                    formatted_text = response.text

                    # 3. Create a Word Document
                    doc = docx.Document()
                    for line in formatted_text.split('\n'):
                        doc.add_paragraph(line)
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    st.success("Done! Your resume is ready.")
                    
                    # 4. Download button
                    st.download_button(
                        label="Download Formatted Resume (.docx)",
                        data=bio.getvalue(),
                        file_name="Formatted_Resume.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                else:
                    st.error("The AI couldn't read the text. Try a different PDF.")
            
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Tip: Make sure your Gemini API key is active in Google AI Studio.")
