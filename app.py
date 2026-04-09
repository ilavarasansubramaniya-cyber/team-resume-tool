import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import io
import google.generativeai as genai
import os
from PIL import Image

# --- 1. UI Config ---
st.set_page_config(page_title="ResumePro Elite", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: #007bff; color: white; font-weight: bold; border: none; }
    .stDownloadButton>button { width: 100%; border-radius: 12px; height: 3.5em; background: #28a745; color: white; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI Engine Config ---
MODEL_NAME = "gemini-2.5-flash-lite"

try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("API Key missing in Streamlit Secrets.")
except Exception as e:
    st.error(f"Setup Error: {e}")

if 'original_ai_output' not in st.session_state:
    st.session_state.original_ai_output = ""

# --- 3. Sidebar ---
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    with st.expander("🏢 BRANDING", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        raw_title = st.text_input("Document Title", placeholder="Enter Name or Title")
        document_title = raw_title.strip().upper() if raw_title.strip() else "RESUME"

    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary = st.checkbox("Develop Executive Summary", value=True)
        custom_points = st.text_area("Custom Points", placeholder="Leadership, ROI...")
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# ── Spacing constants ─────────────────────────────────────────────────────────
SECTION_SPACE_PT   = 10   # uniform space before & after every section header
JOB_BLOCK_SPACE_PT = 10   # space above each Company | Date table row
LINE_PT            = 12   # 1 line ≈ 12 pt  (used for page-boundary spacing)

# --- 4. Helper / Logic Functions ---

def get_sections_dict(text):
    """Parses AI text into {HEADER: [lines]}, filtering skills-section noise."""
    sections, current_header = {}, None
    for line in text.split('\n'):
        clean = line.strip()
        if not clean:
            continue
        if clean.isupper() and clean.endswith(":"):
            current_header = clean
            sections[current_header] = []
        elif current_header:
            if "SKILL" in current_header.upper() and any(
                x in clean.lower() for x in ["software", "table", "the following"]
            ):
                continue
            sections[current_header].append(clean)
    return sections


def replace_all_placeholders(doc, contact, title):
    """Replace [CONTACT_NUMBER] and [DOCUMENT_TITLE] everywhere in the doc."""
    for section in doc.sections:
        for part in [section.header, section.footer]:
            for p in part.paragraphs:
                if "[CONTACT_NUMBER]" in p.text:
                    p.text = p.text.replace("[CONTACT_NUMBER]", contact)
                if "[DOCUMENT_TITLE]" in p.text:
                    p.text = p.text.replace("[DOCUMENT_TITLE]", title)
    for p in doc.paragraphs:
        if "[CONTACT_NUMBER]" in p.text:
            p.text = p.text.replace("[CONTACT_NUMBER]", contact)
        if "[DOCUMENT_TITLE]" in p.text:
            p.text = p.text.replace("[DOCUMENT_TITLE]", title)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if "[CONTACT_NUMBER]" in p.text:
                        p.text = p.text.replace("[CONTACT_NUMBER]", contact)
                    if "[DOCUMENT_TITLE]" in p.text:
                        p.text = p.text.replace("[DOCUMENT_TITLE]", title)


# ── Section-type detectors ────────────────────────────────────────────────────
def _is_list_section(h):
    """Skills / Certifications / Tools / Technologies → bullet list, lowercase."""
    return any(kw in h.upper() for kw in ["SKILL", "CERTIF", "TOOL", "TECHNOLOG", "COMPETENC"])

def _is_exp_section(h):
    return "EXPERIENCE" in h.upper()

def _is_edu_section(h):
    return "EDUCATION" in h.upper()

def _is_summ_section(h):
    return "SUMMARY" in h.upper()


# ── Content writers ───────────────────────────────────────────────────────────
def add_bullet(doc, text, bold=False):
    """Add a bullet line. bold=False → descriptions and skills are never bold."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent       = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.15)
    p.paragraph_format.space_after       = Pt(3)
    clean = text.lstrip('•*-– ').strip()
    run = p.add_run(f"•  {clean}")
    run.bold      = bold
    run.font.name = 'Arial'
    run.font.size = Pt(10.5)
    return p


def add_job_table(doc, line):
    """
    'Company | Date'  →  2-column table.
    Left: bold company name (UPPER).  Right: italic date (right-aligned).
    Space of JOB_BLOCK_SPACE_PT above the row.
    """
    tbl = doc.add_table(rows=1, cols=2)
    tbl.autofit = False
    cl, cr = tbl.rows[0].cells[0], tbl.rows[0].cells[1]
    cl.width, cr.width = Inches(5.1), Inches(1.9)

    parts = line.split("|")
    co_run = cl.paragraphs[0].add_run(parts[0].strip().upper())
    co_run.bold      = True
    co_run.font.name = 'Arial'
    co_run.font.size = Pt(10.5)

    p_right = cr.paragraphs[0]
    p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    dt_run = p_right.add_run(parts[-1].strip())
    dt_run.italic    = True
    dt_run.font.name = 'Arial'
    dt_run.font.size = Pt(10.5)

    cl.paragraphs[0].paragraph_format.space_before = Pt(JOB_BLOCK_SPACE_PT)
    cr.paragraphs[0].paragraph_format.space_before = Pt(JOB_BLOCK_SPACE_PT)
    return tbl


def split_by_pipe(line):
    """
    For list sections: split on '|' so each segment becomes its own bullet.
    e.g. 'Tax Planning | GAAP | Auditing' → ['Tax Planning','GAAP','Auditing']
    """
    return [seg.strip() for seg in line.split("|") if seg.strip()]


# --- 5. Main Content Area ---
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Drop Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])
generate_btn  = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🛠️ Re-architecting Content...", expanded=True):
        try:
            model  = genai.GenerativeModel(MODEL_NAME)
            sum_p  = f"Generate 'SUMMARY:' using: {custom_points}" if include_summary else "No summary."
            priv_p = "CRITICAL: Replace employer names with '[CONFIDENTIAL]'." if make_confidential else ""

            prompt = f"""
            TASK: Reformat this resume.
            Headers: ALL CAPS ending in colon.
            {sum_p}
            {priv_p}
            Experience/Education: 'Company/School | Date Range' (One line).
            Job Title: Next line.
            Descriptions: Bullet points. No mention of 'Table' or 'Software' artifacts.
            """

            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            else:
                raw = Image.open(uploaded_file)

            response = model.generate_content(
                [prompt, raw] if not isinstance(raw, str) else [prompt, f"TEXT:\n{raw}"]
            )
            st.session_state.original_ai_output = response.text.replace("**", "")
        except Exception as e:
            st.error(f"System Error: {e}")

# --- 6. Editor & Export ---
if st.session_state.original_ai_output:
    st.markdown("---")

    c_edit, c_preview = st.columns([1.5, 1])
    with c_edit:
        st.markdown("#### 🖋️ Live Editor")
        final_text = st.text_area(
            "Content Control:",
            value=st.session_state.original_ai_output,
            height=600,
            label_visibility="collapsed"
        )

    current_sections = get_sections_dict(final_text)

    with st.sidebar:
        st.markdown("---")
        header_order = st.multiselect(
            "Reorder Sections:",
            options=list(current_sections.keys()),
            default=list(current_sections.keys())
        )

    with c_preview:
        st.subheader("✅ Finalize")

        t_map  = {"W3G": "w3g_template.docx", "Synectics": "synectics_template.docx", "ProTouch": "protouch_template.docx"}
        t_path = t_map.get(company_choice)
        doc    = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()

        # Global default font
        style = doc.styles['Normal']
        style.font.name = 'Arial'
        style.font.size = Pt(10.5)

        # Replace any [DOCUMENT_TITLE] / [CONTACT_NUMBER] in template
        replace_all_placeholders(doc, contact_number, document_title)

        # ── DOCUMENT TITLE ────────────────────────────────────────────────────
        # Bold, ALL CAPS, centered at the very top of the first page
        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_p.paragraph_format.space_before = Pt(0)
        title_p.paragraph_format.space_after  = Pt(14)
        t_run = title_p.add_run(document_title.upper())
        t_run.bold      = True
        t_run.font.name = 'Arial'
        t_run.font.size = Pt(14)

        # ── SECTION LOOP ──────────────────────────────────────────────────────
        for h in header_order:
            if h not in current_sections:
                continue

            is_list = _is_list_section(h)
            is_exp  = _is_exp_section(h)
            is_edu  = _is_edu_section(h)
            is_summ = _is_summ_section(h)
            is_job  = is_exp or is_edu

            # ── Section Header ────────────────────────────────────────────────
            hp = doc.add_paragraph()
            hp.paragraph_format.space_before   = Pt(SECTION_SPACE_PT)  # space BEFORE header
            hp.paragraph_format.space_after    = Pt(SECTION_SPACE_PT)  # space AFTER header
            hp.paragraph_format.keep_with_next = True
            hr = hp.add_run(h)
            hr.bold      = True
            hr.font.name = 'Arial'
            hr.font.size = Pt(11)

            # ── Section Content ───────────────────────────────────────────────
            lines = current_sections[h]
            i = 0
            while i < len(lines):
                line = lines[i]

                # ════════════════════════════════════════════════════════════
                # LIST SECTIONS  (Skills / Certifications / Tools)
                #   • '|' inside a line = separate items → each on its own line
                #   • All lowercase, never bold
                # ════════════════════════════════════════════════════════════
                if is_list:
                    if "|" in line:
                        for seg in split_by_pipe(line):
                            add_bullet(doc, seg.lower(), bold=False)
                    else:
                        add_bullet(doc, line.lower(), bold=False)

                # ════════════════════════════════════════════════════════════
                # EXPERIENCE / EDUCATION
                # ════════════════════════════════════════════════════════════
                elif is_job:

                    if "|" in line:
                        # ── Company | Date row ────────────────────────────
                        add_job_table(doc, line)

                    elif i > 0 and "|" in lines[i - 1]:
                        # ── Title line (immediately after Company|Date) ───
                        p = doc.add_paragraph()
                        p.paragraph_format.space_before = Pt(4)
                        p.paragraph_format.space_after  = Pt(4)
                        run = p.add_run(line.title())   # title case (mixed caps)
                        run.bold      = True            # bold for job title / degree
                        run.font.name = 'Arial'
                        run.font.size = Pt(10.5)

                        # Education sub-lines (institution, location) after the
                        # degree/title line → handled as unbold plain text below
                        # via the edu-institution branch (i+1 onward).

                    elif is_edu:
                        # ── Institution / location lines in Education ─────
                        # These are NOT the degree line (handled above), so unbold
                        p = doc.add_paragraph()
                        p.paragraph_format.space_after = Pt(3)
                        run = p.add_run(line)
                        run.bold      = False
                        run.font.name = 'Arial'
                        run.font.size = Pt(10.5)

                    else:
                        # ── Job description bullet ────────────────────────
                        add_bullet(doc, line, bold=False)   # never bold

                # ════════════════════════════════════════════════════════════
                # SUMMARY
                # ════════════════════════════════════════════════════════════
                elif is_summ:
                    p = doc.add_paragraph(line)
                    p.paragraph_format.space_after = Pt(SECTION_SPACE_PT)

                # ════════════════════════════════════════════════════════════
                # EVERYTHING ELSE  → bullet, lowercase, not bold
                # ════════════════════════════════════════════════════════════
                else:
                    add_bullet(doc, line.lower(), bold=False)

                i += 1

            # Small trailing spacer after experience / education sections
            if is_job:
                spacer = doc.add_paragraph()
                spacer.paragraph_format.space_before = Pt(0)
                spacer.paragraph_format.space_after  = Pt(SECTION_SPACE_PT)

        # ── END-OF-DOCUMENT spacer ────────────────────────────────────────────
        doc.add_paragraph().paragraph_format.space_before = Pt(24)

        # ── PAGE BREAK SPACING ────────────────────────────────────────────────
        # Walk every paragraph; wherever Word inserted a hard page-break run,
        # ensure 1 line (12 pt) of space before that paragraph (= end of page)
        # and 1 line after it (= start of next page).
        # This also covers section headers that Word naturally pushes to a new
        # page: their space_before is already SECTION_SPACE_PT; we upgrade it
        # to LINE_PT only if it already has a page-break attribute.
        for p in doc.paragraphs:
            for run in p.runs:
                for br in run._element.findall(qn('w:br')):
                    if br.get(qn('w:type')) == 'page':
                        p.paragraph_format.space_before = Pt(LINE_PT)
                        p.paragraph_format.space_after  = Pt(LINE_PT)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(
            label=f"📥 DOWNLOAD {company_choice} DOCX",
            data=buf.getvalue(),
            file_name=f"{document_title}.docx"
        )
