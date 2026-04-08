import streamlit as st
import PyPDF2
import docx
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
from huggingface_hub import InferenceClient
import os

# --- Page Setup ---
st.set_page_config(page_title="Professional Resume Formatter", layout="wide")

# --- HF Configuration ---
# Llama-3-8B is excellent for formatting and logic.
MODEL_ID = "meta-llama/Meta-Llama-3-8B-Instruct" 

try:
    # Ensure you have "HF_TOKEN" added in your Streamlit Secrets
    client = InferenceClient(api_key=st.secrets["HF_TOKEN"])
except Exception:
    st.error("HF_TOKEN missing in Secrets. Please add your Hugging Face API key.")

# --- Sidebar ---
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Company", ["W3G", "Synectics", "ProTouch"])
contact_number = st.sidebar.text_input("Contact Number", value="123-456-7890")

# --- Main Interface ---
st.title("📄 Professional Resume Formatter")

if 'edited_content' not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx"])

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("AI is reformatting..."):
        try:
            # 1. Extract Text
            raw_text = ""
            if uploaded_file.type == "application/pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = "".join([p.extract_text() for p in reader.pages])
            else:
                doc_in = docx.Document(uploaded_file)
                raw_text = "\n".join([p.text for p in doc_in.paragraphs])

            # 2. Build Prompt
            prompt = f"""
            Reformat this resume keeping ONLY its original sections, but change the headers to ALL CAPS and end them with a colon.
            ALWAYS generate a 'SUMMARY:' section at the very beginning.
            For Work Experience/Education, use: 'Company Name/Degree | Date Range'.
            Ensure the Job Title/Role is on the very next line below the Company.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date. DO NOT use '|' anywhere else. 
            If there are multiple job titles (e.g. 'Manager | Lead'), combine them with a hyphen (e.g. 'Manager - Lead').
            For Skills, Tools, and Certifications, put each item on a new line.
            RESUME TEXT:
            {raw_text}
            """

            # 3. FIXED STREAMING LOGIC (Prevents IndexError)
            messages = [{"role": "user", "content": prompt}]
            response_text = ""
            
            # Use the streaming iterator safely
            stream = client.chat_completion(
                model=MODEL_ID,
                messages=messages,
                max_tokens=3000,
                stream=True
            )

            for chunk in stream:
                # Check if the chunk has choices and content before accessing index [0]
                if chunk.choices and len(chunk.choices) > 0:
                    content = chunk.choices[0].delta.content
                    if content:
                        response_text += content
            
            st.session_state.edited_content = response_text.replace("**", "")
            
        except Exception as e:
            st.error(f"Processing Error: {e}")

# --- Formatting & Download Section ---
if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area("Edit Window:", value=st.session_state.edited_content, height=400)
    
    if st.button("Apply Template & Download"):
        # Map choice to template file on GitHub
        template_map = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch.docx"}
        t_file = template_map.get(company_choice)
        
        doc = docx.Document(t_file) if os.path.exists(t_file) else docx.Document()

        current_section = ""
        bullet_headers = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]

        for line in st.session_state.edited_content.split('\n'):
            line = line.strip()
            if not line: continue

            if line.isupper() and line.endswith(":"):
                current_section = line
                p = doc.add_paragraph()
                run = p.add_run(line)
                run.bold, run.font.size = True, Pt(12)
                continue

            if any(bh in current_section for bh in bullet_headers):
                doc.add_paragraph(line.lstrip("*-• "), style='List Bullet')
            elif "|" in line:
                parts = line.split("|")
                p = doc.add_paragraph()
                p.add_run(parts[0].strip().upper()).bold = True
                p.add_run(f"\t{parts[1].strip()}").italic = True
            else:
                doc.add_paragraph(line)

        # Footer
        p_foot = doc.add_paragraph()
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f_run = p_foot.add_run(f"\nIf you would like to interview this candidate, please call {contact_number}")
        f_run.bold, f_run.font.color.rgb = True, RGBColor(0, 51, 153)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(f"Download {company_choice} Resume", buf.getvalue(), f"{company_choice}_Resume.docx")
