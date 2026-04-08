import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import zipfile
import shutil
import os
import re
import tempfile
import copy
from lxml import etree
import google.generativeai as genai
from PIL import Image

# ── Page Setup ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Professional Resume Formatter", layout="wide")

# ── AI Configuration ──────────────────────────────────────────────────────────
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🏢 Branding & ID")
company_choice = st.sidebar.selectbox("Select Company", ["Synectics", "W3G", "ProTouch"])
contact_number = st.sidebar.text_input("Enter Contact Number", value="(773)-257-0648")

# Map each company to its .dotx template file
template_map = {
    "Synectics": "Synectics.dotx",
    "W3G":       "w3g.dotx",       # add your other templates here
    "ProTouch":  "protouch.dotx",
}

# ── Constants ─────────────────────────────────────────────────────────────────
UNIFORM_SPACE = Pt(8)
BULLET_HEADERS = ["SKILL", "TOOL", "CERTIFICATION", "TECHNICAL"]

# Word XML namespace map (used when building body XML)
W_NS  = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"


# ── Helper: build document body XML from formatted text ───────────────────────
def build_body_xml(formatted_text: str, include_summary: bool) -> str:
    """
    Converts the AI-formatted plain text into Word XML paragraphs.
    Returns the inner content (paragraphs only) as an XML string to be
    injected into document.xml <w:body>.
    """
    nsmap = W_NS  # shorthand

    def _run(text, bold=False, italic=False, size_pt=None, font=None):
        rpr_parts = []
        if font:
            rpr_parts.append(f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>')
        if bold:
            rpr_parts.append("<w:b/>")
        if italic:
            rpr_parts.append("<w:i/>")
        if size_pt:
            rpr_parts.append(f'<w:sz w:val="{int(size_pt*2)}"/>')
        rpr = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        space = ' xml:space="preserve"' if text != text.strip() or text.startswith(" ") or text.endswith(" ") else ""
        return f'<w:r>{rpr}<w:t{space}>{safe}</w:t></w:r>'

    def _para(content_xml, style=None, align=None, space_after_pt=8,
              indent_left=None, indent_hanging=None):
        ppr_parts = []
        if style:
            ppr_parts.append(f'<w:pStyle w:val="{style}"/>')
        if align:
            ppr_parts.append(f'<w:jc w:val="{align}"/>')
        sp = int(space_after_pt * 20)
        ppr_parts.append(f'<w:spacing w:after="{sp}" w:before="0"/>')
        if indent_left is not None:
            hang = f' w:hanging="{indent_hanging}"' if indent_hanging else ""
            ppr_parts.append(f'<w:ind w:left="{indent_left}"{hang}/>')
        ppr = f"<w:pPr>{''.join(ppr_parts)}</w:pPr>"
        return f"<w:p>{ppr}{content_xml}</w:p>"

    def _bullet_para(text):
        # Use numId=5 (bullet) from template's numbering.xml
        ppr = (
            '<w:pPr>'
            '<w:pStyle w:val="ListParagraph"/>'
            '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr>'
            f'<w:spacing w:after="{int(UNIFORM_SPACE.pt*20)}" w:before="0"/>'
            '</w:pPr>'
        )
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<w:p>{ppr}<w:r><w:t>{safe}</w:t></w:r></w:p>'

    paragraphs_xml = []
    current_section = ""
    last_was_company = False
    skip_mode = False

    for line in formatted_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # ── Section header (ALL CAPS ending with colon) ──────────────────────
        if line.isupper() and line.endswith(":"):
            current_section = line
            if "SUMMARY" in line and not include_summary:
                skip_mode = True
                continue
            else:
                skip_mode = False

            # Underlined bold heading
            ppr = (
                '<w:pPr>'
                f'<w:spacing w:after="{int(UNIFORM_SPACE.pt*20)}" w:before="120"/>'
                '</w:pPr>'
            )
            rpr = '<w:rPr><w:b/><w:u w:val="single"/><w:sz w:val="24"/></w:rPr>'
            safe = line.replace("&", "&amp;")
            paragraphs_xml.append(
                f'<w:p>{ppr}<w:r>{rpr}<w:t>{safe}</w:t></w:r></w:p>'
            )
            last_was_company = False
            continue

        if skip_mode:
            continue

        # ── Bullet items for Skills / Tools / Certifications ─────────────────
        if any(bh in current_section for bh in BULLET_HEADERS):
            clean = line.lstrip("*-• ").strip()
            if clean:
                paragraphs_xml.append(_bullet_para(clean))
            continue

        # ── Company | Date row (two-column table) ─────────────────────────────
        if "|" in line:
            parts = line.split("|", 1)
            company_text = parts[0].strip().upper()
            date_text    = parts[1].strip()

            # Build a borderless 2-col table, full content width
            # Content width: page 11910 twips - left margin 1080 - right margin 880 = 9950 twips
            col1_w = 6400   # ~4.4"
            col2_w = 3550   # ~2.5"

            tbl_xml = (
                '<w:tbl>'
                '<w:tblPr>'
                '<w:tblStyle w:val="TableNormal"/>'
                f'<w:tblW w:w="{col1_w + col2_w}" w:type="dxa"/>'
                '<w:tblBorders>'
                '<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                '<w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                '<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
                '</w:tblBorders>'
                '<w:tblCellMar>'
                '<w:top w:w="0" w:type="dxa"/>'
                '<w:bottom w:w="60" w:type="dxa"/>'
                '</w:tblCellMar>'
                '</w:tblPr>'
                f'<w:tblGrid><w:gridCol w:w="{col1_w}"/><w:gridCol w:w="{col2_w}"/></w:tblGrid>'
                '<w:tr>'
                f'<w:tc><w:tcPr><w:tcW w:w="{col1_w}" w:type="dxa"/></w:tcPr>'
                '<w:p><w:pPr><w:spacing w:after="0" w:before="0"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:sz w:val="20"/></w:rPr>'
                f'<w:t>{company_text.replace("&","&amp;")}</w:t></w:r></w:p></w:tc>'
                f'<w:tc><w:tcPr><w:tcW w:w="{col2_w}" w:type="dxa"/></w:tcPr>'
                '<w:p><w:pPr><w:jc w:val="right"/><w:spacing w:after="0" w:before="0"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:i/><w:sz w:val="20"/></w:rPr>'
                f'<w:t>{date_text.replace("&","&amp;")}</w:t></w:r></w:p></w:tc>'
                '</w:tr>'
                '</w:tbl>'
            )
            paragraphs_xml.append(tbl_xml)
            last_was_company = True
            continue

        # ── Job title line (line immediately after company | date) ────────────
        if last_was_company:
            ppr = (
                '<w:pPr>'
                '<w:pStyle w:val="BodyText"/>'
                f'<w:spacing w:after="{int(UNIFORM_SPACE.pt*20)}" w:before="0"/>'
                '</w:pPr>'
            )
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            paragraphs_xml.append(
                f'<w:p>{ppr}'
                f'<w:r><w:rPr><w:i/><w:sz w:val="20"/></w:rPr>'
                f'<w:t>{safe}</w:t></w:r></w:p>'
            )
            last_was_company = False
            continue

        # ── Regular body line ─────────────────────────────────────────────────
        ppr = (
            '<w:pPr>'
            '<w:pStyle w:val="BodyText"/>'
            f'<w:spacing w:after="{int(UNIFORM_SPACE.pt*20)}" w:before="0"/>'
            '</w:pPr>'
        )
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        paragraphs_xml.append(f'<w:p>{ppr}<w:r><w:t>{safe}</w:t></w:r></w:p>')

    return "\n".join(paragraphs_xml)


# ── Core: build final .docx from template ─────────────────────────────────────
def build_docx_from_template(
    template_path: str,
    formatted_text: str,
    contact_number: str,
    include_summary: bool,
) -> bytes:
    """
    1. Copies the .dotx template into a temp dir
    2. Replaces the phone number in header1.xml
    3. Replaces the document body with formatted resume content
    4. Repacks into a .docx and returns bytes
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # ── Unzip the template ────────────────────────────────────────────────
        with zipfile.ZipFile(template_path, "r") as z:
            z.extractall(tmpdir)

        # ── 1. Update phone number in header ─────────────────────────────────
        header_path = os.path.join(tmpdir, "word", "header1.xml")
        with open(header_path, "r", encoding="utf-8") as f:
            header_xml = f.read()

        # The original number is split across multiple <w:r> runs.
        # Replace the entire fragmented section with a clean single run.
        old_phone_fragment = (
            '(</w:t></w:r>'
            '<w:r w:rsidR="0086303F" w:rsidRPr="0086303F">'
            '<w:rPr><w:b/><w:bCs/></w:rPr><w:t>773)</w:t></w:r>'
            '<w:r w:rsidR="0086303F"><w:rPr><w:b/><w:bCs/></w:rPr>'
            '<w:t>-</w:t></w:r>'
            '<w:r w:rsidR="0086303F" w:rsidRPr="0086303F">'
            '<w:rPr><w:b/><w:bCs/></w:rPr><w:t>257-0648</w:t></w:r>'
        )
        safe_number = contact_number.replace("&", "&amp;").replace("<", "&lt;")
        new_phone_fragment = f'{safe_number}</w:t></w:r>'
        header_xml = header_xml.replace(old_phone_fragment, new_phone_fragment)

        with open(header_path, "w", encoding="utf-8") as f:
            f.write(header_xml)

        # ── 2. Build new document body ────────────────────────────────────────
        doc_path = os.path.join(tmpdir, "word", "document.xml")
        with open(doc_path, "r", encoding="utf-8") as f:
            doc_xml = f.read()

        # Generate resume paragraphs XML
        resume_xml = build_body_xml(formatted_text, include_summary)

        # Replace the existing <w:body> content (keep <w:sectPr> intact)
        # Extract the sectPr (section/page layout properties) from the original
        sect_match = re.search(r'(<w:sectPr\b.*?</w:sectPr>)', doc_xml, re.DOTALL)
        sect_xml = sect_match.group(1) if sect_match else ""

        # Rebuild body: new content + original sectPr
        new_body = f"<w:body>{resume_xml}{sect_xml}</w:body>"

        # Replace the entire body in the document XML
        new_doc_xml = re.sub(r'<w:body>.*</w:body>', new_body, doc_xml, flags=re.DOTALL)

        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(new_doc_xml)

        # ── 3. Change content type from template (.dotx) to document (.docx) ──
        ct_path = os.path.join(tmpdir, "[Content_Types].xml")
        with open(ct_path, "r", encoding="utf-8") as f:
            ct_xml = f.read()
        ct_xml = ct_xml.replace(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        )
        with open(ct_path, "w", encoding="utf-8") as f:
            f.write(ct_xml)

        # ── 4. Repack into .docx ──────────────────────────────────────────────
        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(tmpdir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    arcname = os.path.relpath(fpath, tmpdir)
                    zout.write(fpath, arcname)

        return out_buf.getvalue()


# ── Main App ──────────────────────────────────────────────────────────────────
st.title("📄 Professional Resume Formatter")

if "edited_content" not in st.session_state:
    st.session_state.edited_content = ""

uploaded_file = st.file_uploader(
    "Upload Resume", type=["pdf", "docx", "png", "jpg", "jpeg"]
)

if uploaded_file and st.button("Generate AI Draft"):
    with st.spinner("Analyzing and formatting with Gemini 2.5 Flash..."):
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")

            prompt = """
            Reformat this resume keeping ONLY its original sections, but change the headers to ALL CAPS and end them with a colon.
            ALWAYS generate a 'SUMMARY:' section at the very beginning.
            For Work Experience/Education, use: 'Company Name/Degree | Date Range'.
            Ensure the Job Title/Role is on the very next line below the Company.
            CRITICAL RULE: ONLY use the '|' symbol to separate the Company/Degree and the Date. DO NOT use '|' anywhere else.
            If there are multiple job titles (e.g. 'Manager | Lead'), combine them with a hyphen (e.g. 'Manager - Lead').
            For Skills, Tools, Technical Tools, and Certifications, put each item on a new line.
            Do not put numbers before headers.
            """

            input_data = None

            if uploaded_file.type == "application/pdf":
                reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = "".join([p.extract_text() for p in reader.pages])
                input_data = prompt + f"\nTEXT:\n{raw_text}"

            elif "wordprocessingml" in uploaded_file.type:
                doc_file = docx.Document(uploaded_file)
                raw_text = "\n".join([para.text for para in doc_file.paragraphs])
                input_data = prompt + f"\nTEXT:\n{raw_text}"

            elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
                img = Image.open(uploaded_file)
                input_data = [prompt, img]

            if input_data:
                response = model.generate_content(input_data)
                st.session_state.edited_content = response.text.replace("**", "")
            else:
                st.error("Unsupported file type.")

        except Exception as e:
            st.error(f"AI Error: {e}")

# ── Edit & Download ────────────────────────────────────────────────────────────
if st.session_state.edited_content:
    st.session_state.edited_content = st.text_area(
        "Edit Window:",
        value=st.session_state.edited_content,
        height=450,
    )
    include_summary = st.checkbox(
        "Include AI-Generated Summary in Final Resume", value=True
    )

    if st.button("Generate Final Word Doc"):
        template_path = template_map.get(company_choice)

        if not template_path or not os.path.exists(template_path):
            st.error(
                f"Template file '{template_path}' not found. "
                "Please place the .dotx template files in the same folder as app.py."
            )
        else:
            with st.spinner("Building document from template..."):
                try:
                    docx_bytes = build_docx_from_template(
                        template_path=template_path,
                        formatted_text=st.session_state.edited_content,
                        contact_number=contact_number,
                        include_summary=include_summary,
                    )
                    st.success("✅ Document generated with full Synectics branding!")
                    st.download_button(
                        label="⬇️ Download Final Word Document",
                        data=docx_bytes,
                        file_name=f"Formatted_Resume_{company_choice}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                except Exception as e:
                    st.error(f"Document generation error: {e}")
                    raise e
