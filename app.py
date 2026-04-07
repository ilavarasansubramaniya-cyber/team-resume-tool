import streamlit as st
import PyPDF2
import docx
import io
import google.generativeai as genai

st.set_page_config(page_title="Resume Formatter", page_icon="📄")
st.title("📄 One-Click Resume Formatter")
st.write("Upload a PDF to instantly format it into a professional Word document.")

# API Setup with multiple fallback models
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    
    # We list potential models to try in order of reliability
    model_names = ['gemini-1.5-flash-latest', 'gemini-1.5-pro-latest', 'gemini-pro']
    
    # Try to find which one your key supports
    model = None
    for name in model_names:
        try:
            temp_model = genai.GenerativeModel(name)
            # Test it briefly
            temp_model.generate_content("test", generation_config={"max_output_tokens": 1})
            model = temp_model
            break 
        except:
            continue

    if not model:
        st.error("Could not connect to any Gemini models. Please check your API key at aistudio.google.com")
        st.stop()

except Exception as e:
    st.error("API Key Missing: Add GEMINI_API_KEY to your Streamlit Secrets.")
    st.stop()

uploaded_file = st.file_uploader("Upload Before Resume (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Format My Resume"):
        with st.spinner("Re-writing resume..."):
            try:
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = ""
                for page in pdf_reader.pages:
                    raw_text += page.extract_text() or ""

                # Prompt designed to match your 'After' document exactly
                prompt = f"""
                Reformat the following resume text. 
                Use these exact headers in this order:
                1. Name (Just the name)
                2. Summary: (Professional paragraph)
                3. Skills: (List of core competencies)
                4. Education: (Degree, Date, and Institution)
                5. Licensed CPA: (License details)
                6. Work Experience: (Company, Title, Date range, and Bullet Points)

                Remove all page numbers or 'Source' tags. 
                Make it clean and professional.
                
                RESUME DATA:
                {raw_text}
                """
                
                response = model.generate_content(prompt)
                
                if response.text:
                    doc = docx.Document()
                    # Clean up markdown stars
                    text = response.text.replace('**', '').replace('__', '')
                    
                    for line in text.split('\n'):
                        doc.add_paragraph(line)
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    st.success("Formatting Complete!")
                    st.download_button(
                        label="Download Word Document",
                        data=bio.getvalue(),
                        file_name="Formatted_Resume.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            except Exception as e:
                st.error(f"Error: {str(e)}")
