import streamlit as st
import PyPDF2
import docx
import io
import google.generativeai as genai

# Page Setup
st.set_page_config(page_title="Resume Formatter", page_icon="📄")
st.title("📄 One-Click Resume Formatter")
st.write("Upload a messy PDF, and we'll format it into a professional Word Doc!")

# API Configuration
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    # Updated to the most current, high-speed model
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("Setup Error: Please check your Streamlit Secrets for the GEMINI_API_KEY.")
    st.stop()

uploaded_file = st.file_uploader("Upload your Before Resume (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Format My Resume"):
        with st.spinner("AI is analyzing and re-writing..."):
            try:
                # 1. Extract Text from PDF
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = ""
                for page in pdf_reader.pages:
                    content = page.extract_text()
                    if content:
                        raw_text += content

                # 2. AI Formatting Prompt
                prompt = f"""
                Reformat the following resume text into a professional structure. 
                Use these specific sections: Summary, Skills, Education, Licensed CPA, and Work Experience.
                Ensure the Work Experience is in reverse chronological order.
                
                RESUME TEXT:
                {raw_text}
                """
                
                # Generate content
                response = model.generate_content(prompt)
                
                if response.text:
                    # 3. Create Word Document
                    doc = docx.Document()
                    # Add a title
                    doc.add_heading('Formatted Resume', 0)
                    
                    for line in response.text.split('\n'):
                        # Clean up AI markdown stars if present
                        clean_line = line.replace('**', '').replace('__', '')
                        doc.add_paragraph(clean_line)
                    
                    # Save to memory
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    st.success("Success! Your resume has been reformatted.")
                    
                    # 4. Download
                    st.download_button(
                        label="Download Formatted Resume (.docx)",
                        data=bio.getvalue(),
                        file_name="Formatted_Resume.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            
            except Exception as e:
                st.error(f"AI Connection Error: {str(e)}")
                st.info("Check if your API key is correct in the Streamlit 'Secrets' setting.")
