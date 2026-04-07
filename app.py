import streamlit as st
import PyPDF2
import docx
import io
import google.generativeai as genai
import os

# Set up the webpage
st.title("📄 One-Click Resume Formatter")
st.write("Upload a messy PDF resume, and we'll format it perfectly into a Word Document!")

# Get the API key securely
api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

uploaded_file = st.file_uploader("Upload your Before Resume (PDF)", type="pdf")

if uploaded_file is not None:
    if st.button("Format My Resume"):
        with st.spinner("Reading and formatting... Please wait."):
            # 1. Read the PDF
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            raw_text = ""
            for page in pdf_reader.pages:
                raw_text += page.extract_text()

            # 2. Ask the AI to format it
            prompt = f"""
            Take the following messy resume text and format it cleanly. 
            Organize it strictly into these sections: 
            1. Name at the top
            2. Summary: (A brief paragraph)
            3. Skills: (A clean list)
            4. Education: (Degree, Date, Institution)
            5. Licenses/Certifications: (If applicable)
            6. Work Experience: (Company, Dates, Title, and bullet points of duties)

            Do not add any fake information. Just reorganize this text:
            {raw_text}
            """

            response = model.generate_content(prompt)
            formatted_text = response.text

            # 3. Create a Word Document
            doc = docx.Document()
            for line in formatted_text.split('\n'):
                doc.add_paragraph(line)

            # Save doc to memory
            bio = io.BytesIO()
            doc.save(bio)

            st.success("Resume formatted successfully!")

            # 4. Give the user a download button
            st.download_button(
                label="Download Formatted Resume (.docx)",
                data=bio.getvalue(),
                file_name="Formatted_Resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
