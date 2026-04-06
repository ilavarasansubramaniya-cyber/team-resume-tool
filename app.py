import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader

# 1. Setup Page Config
st.set_page_config(page_title="Team Resume Re-Framer", page_icon="📄")

# 2. Sidebar for API Key (Team members can use one shared key)
# For a "Zero Cost" shareable tool, you can hardcode the key or use Streamlit Secrets
API_KEY = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else ""

if not API_KEY:
    API_KEY = st.sidebar.text_input("Enter Gemini API Key", type="password")

if API_KEY:
    genai.configure(api_key=API_KEY)
    # Temporary debug code
st.write("Available models for your key:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        st.write(m.name)
    model = genai.GenerativeModel('gemini-3-flash')

    st.title("📄 Team Resume Reformatter")
    st.info("Upload a raw PDF resume to convert it into our official team template.")

    uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf")

    if uploaded_file:
        with st.spinner("Reading and Reformatting..."):
            # Extract Text
            reader = PdfReader(uploaded_file)
            raw_text = ""
            for page in reader.pages:
                raw_text += page.extract_text()

            # Define YOUR specific template here
            prompt = f"""
            You are a professional resume parser. Take the raw text below and 
            reformat it strictly into this Markdown template:

            # [FULL NAME]
            **Contact:** [Email] | [Phone] | [LinkedIn URL]
            
            ### PROFESSIONAL SUMMARY
            [Write a 3-line summary based on their experience]

            ### KEY STRENGTHS
            * [Strength 1] | [Strength 2] | [Strength 3]

            ### EXPERIENCE
            [For each job, use this format:]
            **[Job Title]** | [Company Name] | [Dates]
            - [High-impact bullet point]
            - [High-impact bullet point]

            ### EDUCATION
            [Degree] - [University]

            ---
            RAW TEXT TO PARSE:
            {raw_text}
            """

            # Get Result from AI
            response = model.generate_content(prompt)
            
            st.success("Done!")
            st.markdown("---")
            st.markdown(response.text)
            
            # Allow team to copy-paste or download
            st.download_button("Download Text Version", response.text, file_name="formatted_resume.txt")
else:
    st.warning("Please enter the API Key in the sidebar to start.")
