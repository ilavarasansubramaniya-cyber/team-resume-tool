import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import os
import base64
from openai import OpenAI

# --- 1. Grand UI Config ---
st.set_page_config(page_title="ResumePro Elite", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }

    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.4);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.2);
    }

    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.5em;
        background: linear-gradient(45deg, #007bff, #6610f2);
        color: white; font-weight: bold; border: none;
        transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0, 123, 255, 0.3);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 123, 255, 0.5);
    }

    .stDownloadButton>button {
        width: 100%; border-radius: 12px; height: 3.5em;
        background: linear-gradient(45deg, #28a745, #20c997);
        color: white; border: none;
        box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
    }

    div[data-testid="stExpander"] {
        background: white; border-radius: 15px; border: none;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Groq Client Setup ---
# In your Streamlit secrets.toml, add:
#   GROQ_API_KEY = "your-key-from-console.groq.com"
try:
    client = OpenAI(
        api_key=st.secrets["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1"
    )
except Exception as e:
    st.error("GROQ_API_KEY missing in Streamlit Secrets. Get your free key at console.groq.com")
    st.stop()

# Llama 4 Scout — supports both text AND image input (vision + text-to-text)
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# --- 3. Session State ---
if "original_ai_output" not in st.session_state:
    st.session_state.original_ai_output = ""
if "usage_data" not in st.session_state:
    st.session_state.usage_data = None

# --- 4. Groq Inference Function ---
def call_llama4(prompt_text: str, image_bytes: bytes = None, image_mime: str = None):
    """
    Calls Llama 4 Scout via Groq's OpenAI-compatible API.
    Supports both plain text and image inputs.
    Returns (response_text, usage_dict)
    """
    messages_content = []

    # Add image if provided (PNG/JPG resume upload)
    if image_bytes and image_mime:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        messages_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_mime};base64,{b64}"
            }
        })

    # Always add the text prompt
    messages_content.append({
        "type": "text",
        "text": prompt_text
    })

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": messages_content}],
        max_tokens=4096,
        temperature=0.3,   # Low temp = consistent, structured formatting output
    )

    output_text = response.choices[0].message.content
    usage = {
        "inputTokens": response.usage.prompt_tokens,
        "outputTokens": response.usage.completion_tokens,
        "totalTokens": response.usage.total_tokens,
    }
    return output_text, usage


# --- 5. Sidebar ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    st.write("🤖 AI Engine: Llama 4 Scout (Groq)")

    with st.expander("🏢 BRANDING & IDENTITY", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        document_title = st.text_input("Document Title", value="RESUME")

    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_summary_points = st.text_area(
            "Custom Points to Develop",
            placeholder="e.g. Focus on leadership and ROI...",
            disabled=not include_summary
        )
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# --- 6. Helper Functions (unchanged) ---
def set_arial_font(doc):
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Arial"
    font.size = Pt(11)

def get_sections_dict(text):
    sections, current_header = {}, None
    for line in text.split("\n"):
        clean = line.strip()
        if not clean:
            continue
        if clean.isupper() and clean.endswith(":"):
            current_header = clean
            sections[current_header] = []
        elif current_header:
            sections[current_header].append(clean)
    return sections

def replace_placeholder_in_doc(doc, placeholder, replacement):
    for p in doc.paragraphs:
        if placeholder in p.text:
            for run in p.runs:
                run.text = run.text.replace(placeholder, replacement)
    for section in doc.sections:
        for header in [section.header, section.first_page_header]:
            if header:
                for p in header.paragraphs:
                    if placeholder in p.text:
                        for run in p.runs:
                            run.text = run.text.replace(placeholder, replacement)

# --- 7. Main UI ---
st.title("Professional Resume Artisan")
st.markdown("### Elevate your candidate presentation with AI-driven precision.")

col1, col2 = st.columns([2, 1])
with col1:
    uploaded_file = st.file_uploader(
        "Drop Resume (PDF, DOCX, or Image)",
        type=["pdf", "docx", "png", "jpg", "jpeg"]
    )
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("✨ START AI TRANSFORMATION")

# --- 8. AI Transformation ---
if uploaded_file and generate_btn:
    with st.status("🚀 Transforming Content...", expanded=True) as status:
        try:
            # Build prompt
            sum_p = "DO NOT generate a summary."
            if include_summary:
                sum_p = (
                    f"ALWAYS generate a 'SUMMARY:' section. "
                    f"Professionally develop these points into the narrative: '{custom_summary_points}'"
                )

            priv_p = (
                "CRITICAL: Replace ALL employer names in the Work Experience section "
                "with exactly '[CONFIDENTIAL]'."
                if make_confidential else ""
            )

            prompt = f"""
Reformat this resume perfectly.
Headers: ALL CAPS ending in colon.
{sum_p}
{priv_p}
Experience/Education: 'Company/University | Date Range'.
Job Title on very next line. ONLY use '|' for date separation.
One skill/tool per line. No bolding (**) or numbers.
"""

            image_bytes, image_mime = None, None

            if uploaded_file.type == "application/pdf":
                raw = "".join(
                    [p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages]
                )
                full_prompt = f"{prompt}\nTEXT:\n{raw}"

            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
                full_prompt = f"{prompt}\nTEXT:\n{raw}"

            else:
                # Image resume — pass raw bytes directly (Llama 4 Scout is vision-capable)
                image_bytes = uploaded_file.read()
                image_mime = uploaded_file.type   # e.g. "image/png"
                full_prompt = prompt

            # Call Llama 4 Scout via Groq
            output_text, usage = call_llama4(full_prompt, image_bytes, image_mime)

            st.session_state.original_ai_output = output_text.replace("**", "")
            st.session_state.usage_data = usage

            status.update(label="Transformation Complete!", state="complete", expanded=False)
            st.balloons()

        except Exception as e:
            st.error(f"System Error: {e}")

# --- 9. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")
    content_dict = get_sections_dict(st.session_state.original_ai_output)

    with st.sidebar:
        with st.expander("🔄 DYNAMIC JUMBLE", expanded=True):
            header_order = st.multiselect(
                "Reorder Sections:",
                options=list(content_dict.keys()),
                default=list(content_dict.keys())
            )

        # Token usage display
        if st.session_state.usage_data:
            with st.expander("📊 TOKEN USAGE", expanded=False):
                usage = st.session_state.usage_data
                st.metric("Input tokens",  usage.get("inputTokens", "—"))
                st.metric("Output tokens", usage.get("outputTokens", "—"))
                st.metric("Total tokens",  usage.get("totalTokens", "—"))

    c_edit, c_preview = st.columns([1.5, 1])

    with c_edit:
        st.markdown("#### 🖋️ Live Editor")
        final_text = st.text_area(
            "Refine AI Output:",
            value=st.session_state.original_ai_output,
            height=500,
            label_visibility="collapsed"
        )

    with c_preview:
        st.markdown("#### ✅ Final Steps")
        st.success("Transformation Complete!")
        st.info("Review your changes. The order in the sidebar will be reflected in the final document.")

        # Build DOCX
        t_map = {
            "W3G": "w3g_template.docx",
            "Synectics": "synectics_template.docx",
            "ProTouch": "protouch_template.docx"
        }
        t_path = os.path.join(os.path.dirname(__file__), t_map.get(company_choice, ""))
        doc = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()
        set_arial_font(doc)
        replace_placeholder_in_doc(doc, "[CONTACT_NUMBER]", contact_number)
        replace_placeholder_in_doc(doc, "[DOCUMENT_TITLE]", document_title.upper())

        new_content = get_sections_dict(final_text)
        for h in header_order:
            if h in new_content:
                hp = doc.add_paragraph()
                hp.paragraph_format.space_before = Pt(12)
                hr = hp.add_run(h)
                hr.bold = True
                hr.font.size = Pt(12)
                hr.font.name = "Arial"

                last_comp = False
                for line in new_content[h]:
                    if "|" in line:
                        doc.add_paragraph().paragraph_format.space_before = Pt(12)
                        tbl = doc.add_table(rows=1, cols=2)
                        tbl.autofit = False
                        cl = tbl.rows[0].cells[0]
                        cr = tbl.rows[0].cells[1]
                        cl.width = Inches(5.0)
                        cr.width = Inches(2.0)
                        parts = line.split("|")
                        cl.paragraphs[0].add_run(parts[0].strip().upper()).bold = True
                        p_dt = cr.paragraphs[0]
                        p_dt.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        rd = p_dt.add_run(parts[-1].strip())
                        rd.italic = True
                        rd.font.size = Pt(10)
                        rd.font.name = "Arial"
                        last_comp = True
                    else:
                        pb = doc.add_paragraph()
                        if last_comp:
                            rj = pb.add_run(line.title())
                            rj.font.name = "Arial"
                            pb.paragraph_format.space_after = Pt(8)
                            last_comp = False
                        else:
                            rt = pb.add_run(line)
                            rt.font.name = "Arial"
                            pb.paragraph_format.space_after = Pt(4)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(
            label=f"📥 DOWNLOAD {company_choice.upper()} DOCX",
            data=buf.getvalue(),
            file_name=f"{document_title}_{company_choice}.docx"
        )
