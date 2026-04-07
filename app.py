import streamlit as st
import PyPDF2
import docx
import io
import google.generativeai as genai

st.set_page_config(page_title="Resume Formatter", page_icon="📄")
st.title("📄 One-Click Resume Formatter")

# Verify the Secret exists
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please add your new API key to Streamlit Secrets.")
    st.stop()

# Connect to Google AI
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

uploaded_file = st.file_uploader("Upload Before Resume (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Format My Resume"):
        with st.spinner("AI is re-formatting..."):
            try:
                # 1. Read PDF Text
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = ""
                for page in reader.pages:
                    raw_text += page.extract_text() or ""

                # 2. Command the AI to match your specific 'After' format
                # We specifically request the headers from your example 
                prompt = f"""
                Reformat the following resume text. 
                Use these exact sections in this order:
                - Summary:
                - Skills:
                - Education:
                - Licensed CPA:
                - Work Experience:

                Use the contact info provided in the text. 
                Ensure dates are aligned to the right like a professional resume.
                Remove all 'Source' markers or page numbers.
                
                TEXT TO FORMAT:
                {raw_text}
                """
                
                response = model.generate_content(prompt)
                
                # 3. Generate Word Doc
                doc = docx.Document()
                # Remove AI markdown stars
                clean_text = response.text.replace('**', '').replace('__', '')
                
                for line in clean_text.split('\n'):
                    doc.add_paragraph(line)
                
                # Save to download buffer
                output = io.BytesIO()
                doc.save(output)
                
                st.success("Formatting Successful!")
                st.download_button(
                    label="Download Your Word Resume",
                    data=output.getvalue(),
                    file_name="Formatted_Resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            except Exception as e:
                st.error(f"Error: {e}")
