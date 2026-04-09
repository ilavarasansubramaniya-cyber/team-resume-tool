import streamlit as st
import PyPDF2
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import io
import google.generativeai as genai
import os
from PIL import Image

# ─────────────────────────────────────────────────────────────────────────────
# 1. UI Config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ResumePro Elite", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }

    /* Primary action button */
    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.5em;
        background: #007bff; color: white; font-weight: bold; border: none;
    }

    /* Download button */
    .stDownloadButton>button {
        width: 100%; border-radius: 12px; height: 3.5em;
        background: #28a745; color: white; border: none;
    }

    /* ── SAVE HINT BANNER ── */
    .save-hint {
        background: #fff3cd;
        border: 2px solid #ffc107;
        border-radius: 10px;
        padding: 10px 16px;
        font-size: 15px;
        font-weight: 700;
        color: #7d4e00;
        text-align: center;
        margin-bottom: 8px;
        letter-spacing: 0.3px;
    }
    .save-hint kbd {
        background: #343a40;
        color: #fff;
        border-radius: 5px;
        padding: 2px 7px;
        font-size: 13px;
        font-family: monospace;
        margin: 0 2px;
    }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 2. AI Engine Config
# ─────────────────────────────────────────────────────────────────────────────
MODEL_NAME = "gemini-2.5-flash-lite"

try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("API Key missing in Streamlit Secrets.")
except Exception as e:
    st.error(f"Setup Error: {e}")

if "original_ai_output" not in st.session_state:
    st.session_state.original_ai_output = ""

# ─────────────────────────────────────────────────────────────────────────────
# 3. Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 💎 Elite Control")
    with st.expander("🏢 BRANDING", expanded=True):
        company_choice = st.selectbox("Select Template", ["W3G", "Synectics", "ProTouch"])
        contact_number = st.text_input("Contact Number", value="123-456-7890")
        raw_title      = st.text_input("Document Title", placeholder="Enter Name or Title")
        document_title = raw_title.strip().upper() if raw_title.strip() else "RESUME"

    with st.expander("🧠 AI ENGINE SETTINGS", expanded=True):
        include_summary  = st.checkbox("Develop Executive Summary", value=True)
        custom_points    = st.text_area("Custom Points", placeholder="Leadership, ROI...")
        make_confidential = st.checkbox("Anonymize Employers [CONFIDENTIAL]", value=False)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Spacing constants  (all uniform — one value rules them all)
# ─────────────────────────────────────────────────────────────────────────────
SP = 8          # Pt — the single uniform spacing unit used everywhere
TWO_LINE_PT = 24  # 2 lines ≈ 24 pt  (page-boundary spacing)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Helper / Logic Functions
# ─────────────────────────────────────────────────────────────────────────────

def sentence_case(text: str) -> str:
    """
    Capitalise ONLY the very first character, leave everything else untouched.
    Acronyms like GAAP, IRS, CPA, QuickBooks stay intact.
    e.g. 'tax planning & GAAP'  -> 'Tax planning & GAAP'
         'FULL-CYCLE ACCOUNTING' -> 'FULL-CYCLE ACCOUNTING'  (skills keep caps)
    """
    t = text.strip()
    if not t:
        return t
    return t[0].upper() + t[1:]


def get_sections_dict(text: str) -> dict:
    """Parse AI text into {HEADER: [lines]}, dropping skills-section noise."""
    sections, current_header = {}, None
    for line in text.split("\n"):
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


def replace_all_placeholders(doc, contact: str, title: str):
    """Replace [CONTACT_NUMBER] and [DOCUMENT_TITLE] everywhere in the doc."""
    targets = {"[CONTACT_NUMBER]": contact, "[DOCUMENT_TITLE]": title}
    for section in doc.sections:
        for part in [section.header, section.footer]:
            for p in part.paragraphs:
                for token, val in targets.items():
                    if token in p.text:
                        p.text = p.text.replace(token, val)
    for p in doc.paragraphs:
        for token, val in targets.items():
            if token in p.text:
                p.text = p.text.replace(token, val)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for token, val in targets.items():
                        if token in p.text:
                            p.text = p.text.replace(token, val)


# ── Section-type detectors ────────────────────────────────────────────────────
def _is_list_section(h: str) -> bool:
    return any(kw in h.upper() for kw in
               ["SKILL", "CERTIF", "TOOL", "TECHNOLOG", "COMPETENC"])

def _is_exp_section(h: str) -> bool:
    return "EXPERIENCE" in h.upper()

def _is_edu_section(h: str) -> bool:
    return "EDUCATION" in h.upper()

def _is_summ_section(h: str) -> bool:
    return "SUMMARY" in h.upper()


# ── Content writers ───────────────────────────────────────────────────────────
def _base_run(p, text: str, bold=False, italic=False, size_pt=10.5):
    run = p.add_run(text)
    run.bold      = bold
    run.italic    = italic
    run.font.name = "Arial"
    run.font.size = Pt(size_pt)
    return run


def add_bullet(doc, text: str, bold=False):
    """Single bullet line. Never bold by default."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent       = Inches(0.25)
    p.paragraph_format.first_line_indent = Inches(-0.15)
    p.paragraph_format.space_before      = Pt(0)
    p.paragraph_format.space_after       = Pt(SP)
    clean = text.lstrip("•*-– ").strip()
    _base_run(p, f"•  {clean}", bold=bold)
    return p


def add_spacer(doc, before=0, after=SP):
    """Empty paragraph used purely for spacing."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after  = Pt(after)
    return p


def split_by_pipe(line: str):
    """'A | B | C' → ['A', 'B', 'C']"""
    return [seg.strip() for seg in line.split("|") if seg.strip()]


def add_experience_row(doc, company_part: str, date_part: str, job_title: str):
    """
    Layout (2-row table, 2 fixed-width columns):
      Row 1:  COMPANY NAME (bold, left)  |  Date range (italic, right-aligned)
      Row 2:  Job title (bold, left)     |  [empty — keeps date column fixed]

    Fixed column widths guarantee ALL date ranges end on the exact same
    right-hand margin regardless of their text length.
    Col widths: 5.5" (content) + 1.5" (date) = 7" (standard body width)
    """
    DATE_COL = Inches(1.5)
    CONTENT_COL = Inches(5.5)

    tbl = doc.add_table(rows=2, cols=2)
    tbl.autofit = False

    r0c0, r0c1 = tbl.rows[0].cells   # company row
    r1c0, r1c1 = tbl.rows[1].cells   # job title row

    # Fixed column widths on every cell
    for cell, w in [(r0c0, CONTENT_COL), (r0c1, DATE_COL),
                    (r1c0, CONTENT_COL), (r1c1, DATE_COL)]:
        cell.width = w

    # Row 1 left — COMPANY bold UPPER
    _base_run(r0c0.paragraphs[0], company_part.strip().upper(), bold=True)

    # Row 1 right — Date italic, RIGHT-aligned
    r0c1.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _base_run(r0c1.paragraphs[0], date_part.strip(), italic=True)

    # Row 2 left — Job title bold, sentence case
    _base_run(r1c0.paragraphs[0], sentence_case(job_title), bold=True)

    # Row 2 right — empty (keeps column structure intact)
    r1c1.paragraphs[0].text = ""

    # Spacing: SP before the block (top row only), tight gap between rows
    r0c0.paragraphs[0].paragraph_format.space_before = Pt(SP)
    r0c1.paragraphs[0].paragraph_format.space_before = Pt(SP)
    r0c0.paragraphs[0].paragraph_format.space_after  = Pt(2)
    r0c1.paragraphs[0].paragraph_format.space_after  = Pt(2)
    r1c0.paragraphs[0].paragraph_format.space_before = Pt(0)
    r1c1.paragraphs[0].paragraph_format.space_before = Pt(0)
    r1c0.paragraphs[0].paragraph_format.space_after  = Pt(SP)
    r1c1.paragraphs[0].paragraph_format.space_after  = Pt(SP)

    return tbl


def add_education_row(doc, degree_part: str, date_part: str):
    """
    Render  Degree (bold, left)  |  Date (italic, right-aligned)
    Same fixed column widths as experience rows so ALL dates line up.
    Col widths: 5.5" (content) + 1.5" (date) = 7"
    """
    DATE_COL    = Inches(1.5)
    CONTENT_COL = Inches(5.5)

    tbl = doc.add_table(rows=1, cols=2)
    tbl.autofit = False
    cl, cr = tbl.rows[0].cells

    cl.width = CONTENT_COL
    cr.width = DATE_COL

    # Degree — bold, sentence case
    _base_run(cl.paragraphs[0], sentence_case(degree_part.strip()), bold=True)

    # Date — italic, right-aligned
    cr.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _base_run(cr.paragraphs[0], date_part.strip(), italic=True)

    cl.paragraphs[0].paragraph_format.space_before = Pt(SP)
    cr.paragraphs[0].paragraph_format.space_before = Pt(SP)
    cl.paragraphs[0].paragraph_format.space_after  = Pt(SP)
    cr.paragraphs[0].paragraph_format.space_after  = Pt(SP)

    return tbl


# ─────────────────────────────────────────────────────────────────────────────
# 6. Main Content Area
# ─────────────────────────────────────────────────────────────────────────────
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
            TASK: Reformat this resume exactly as instructed.
            - Section headers: ALL CAPS ending in colon (e.g. EXPERIENCE:).
            - Use EXPERIENCE: (not Experience/Education) for work history.
            - {sum_p}
            - {priv_p}
            - Experience: 'Company | Date Range' on one line, THEN job title on the very next line.
            - Education: 'Degree | Date Range' on one line, THEN institution on the very next line.
            - All descriptions: bullet points starting with •
            - No mention of 'Table' or 'Software' artifacts.
            """

            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            else:
                raw = Image.open(uploaded_file)

            response = model.generate_content(
                [prompt, raw] if not isinstance(raw, str)
                else [prompt, f"TEXT:\n{raw}"]
            )
            st.session_state.original_ai_output = response.text.replace("**", "")
        except Exception as e:
            st.error(f"System Error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# 7. Editor & Export
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.original_ai_output:
    st.markdown("---")

    c_edit, c_preview = st.columns([1.5, 1])

    with c_edit:
        # ── Visible save hint ───────────────────────────────────────────────
        st.markdown(
            '<div class="save-hint">'
            '💾 Press <kbd>Ctrl</kbd> + <kbd>Enter</kbd> to apply your edits'
            ' before downloading'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("#### 🖋️ Live Editor")
        final_text = st.text_area(
            "Content Control:",
            value=st.session_state.original_ai_output,
            height=580,
            label_visibility="collapsed",
            help="Edit content here, then press Ctrl+Enter to apply changes.",
        )

    current_sections = get_sections_dict(final_text)

    with st.sidebar:
        st.markdown("---")
        header_order = st.multiselect(
            "Reorder Sections:",
            options=list(current_sections.keys()),
            default=list(current_sections.keys()),
        )

    with c_preview:
        st.subheader("✅ Finalize & Download")

        t_map  = {
            "W3G":      "w3g_template.docx",
            "Synectics": "synectics_template.docx",
            "ProTouch": "protouch_template.docx",
        }
        t_path = t_map.get(company_choice)
        doc    = docx.Document(t_path) if os.path.exists(t_path) else docx.Document()

        # Global default font
        style           = doc.styles["Normal"]
        style.font.name = "Arial"
        style.font.size = Pt(10.5)

        replace_all_placeholders(doc, contact_number, document_title)

        # ── DOCUMENT TITLE  (bold, ALL CAPS, centred, top of page 1) ─────────
        title_p = doc.add_paragraph()
        title_p.alignment                    = WD_ALIGN_PARAGRAPH.CENTER
        title_p.paragraph_format.space_before = Pt(0)
        title_p.paragraph_format.space_after  = Pt(SP * 2)
        t_run = title_p.add_run(document_title.upper())
        t_run.bold      = True
        t_run.font.name = "Arial"
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
            hp.paragraph_format.space_before   = Pt(SP)
            hp.paragraph_format.space_after    = Pt(SP)
            hp.paragraph_format.keep_with_next = True
            _base_run(hp, h, bold=True, size_pt=11)

            # ── Section Content ───────────────────────────────────────────────
            lines = current_sections[h]
            i = 0

            while i < len(lines):
                line = lines[i]

                # ════════════════════════════════════════════════════════════
                # LIST SECTIONS  (Skills / Certifications / Tools / etc.)
                #   • '|' splits into individual items, each its own bullet
                #   • Sentence case (first letter cap, rest lower)
                #   • Never bold
                # ════════════════════════════════════════════════════════════
                if is_list:
                    if "|" in line:
                        for seg in split_by_pipe(line):
                            add_bullet(doc, sentence_case(seg), bold=False)
                    else:
                        add_bullet(doc, sentence_case(line), bold=False)
                    i += 1

                # ════════════════════════════════════════════════════════════
                # EXPERIENCE
                #   Company | Date  +  next line = Job Title
                #   → rendered as a single 3-column row (same line)
                # ════════════════════════════════════════════════════════════
                elif is_exp:
                    if "|" in line:
                        parts       = line.split("|")
                        company_str = parts[0].strip()
                        date_str    = parts[-1].strip()
                        # Peek ahead for the job title
                        job_title = ""
                        if i + 1 < len(lines) and "|" not in lines[i + 1]:
                            job_title = lines[i + 1]
                            i += 1   # consume the title line
                        add_experience_row(doc, company_str, date_str, job_title)
                    else:
                        # Job description bullet — sentence case, not bold
                        add_bullet(doc, sentence_case(line), bold=False)
                    i += 1

                # ════════════════════════════════════════════════════════════
                # EDUCATION
                #   Degree | Date  →  bold degree, italic date, same line
                #   Next line = institution — unbold plain text
                # ════════════════════════════════════════════════════════════
                elif is_edu:
                    if "|" in line:
                        parts      = line.split("|")
                        degree_str = parts[0].strip()
                        date_str   = parts[-1].strip()
                        add_education_row(doc, degree_str, date_str)
                        # Institution line(s) follow: unbold, sentence case
                        while i + 1 < len(lines) and "|" not in lines[i + 1]:
                            i += 1
                            inst_p = doc.add_paragraph()
                            inst_p.paragraph_format.space_before = Pt(0)
                            inst_p.paragraph_format.space_after  = Pt(SP)
                            _base_run(inst_p, sentence_case(lines[i]),
                                      bold=False)
                    else:
                        # Any stray line in education → plain, sentence case
                        p = doc.add_paragraph()
                        p.paragraph_format.space_after = Pt(SP)
                        _base_run(p, sentence_case(line), bold=False)
                    i += 1

                # ════════════════════════════════════════════════════════════
                # SUMMARY
                # ════════════════════════════════════════════════════════════
                elif is_summ:
                    p = doc.add_paragraph()
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after  = Pt(SP)
                    _base_run(p, sentence_case(line), bold=False)
                    i += 1

                # ════════════════════════════════════════════════════════════
                # EVERYTHING ELSE  → bullet, sentence case, not bold
                # ════════════════════════════════════════════════════════════
                else:
                    add_bullet(doc, sentence_case(line), bold=False)
                    i += 1

            # Trailing spacer after every section (uniform)
            add_spacer(doc, before=0, after=SP)

        # ── END-OF-DOCUMENT spacer ────────────────────────────────────────────
        add_spacer(doc, before=SP, after=SP)

        # ── PAGE BREAK SPACING ────────────────────────────────────────────────
        # For every hard page-break run: add 2 lines (24 pt) BEFORE the break
        # paragraph (= end of the outgoing page) and 2 lines AFTER it
        # (= start of the incoming page).  First page is unaffected because
        # title_p has space_before = 0.
        for p in doc.paragraphs:
            for run in p.runs:
                for br in run._element.findall(qn("w:br")):
                    if br.get(qn("w:type")) == "page":
                        p.paragraph_format.space_before = Pt(TWO_LINE_PT)
                        p.paragraph_format.space_after  = Pt(TWO_LINE_PT)

        buf = io.BytesIO()
        doc.save(buf)
        st.download_button(
            label=f"📥 DOWNLOAD {company_choice} DOCX",
            data=buf.getvalue(),
            file_name=f"{document_title}.docx",
        )
