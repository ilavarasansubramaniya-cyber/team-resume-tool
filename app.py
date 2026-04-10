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
        document_name  = st.text_input("Name", placeholder="Enter candidate name")

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
    """
    Parse AI text into {HEADER: [lines]}.
    Main headers  : ALL CAPS ending with colon  →  CORE SKILLS:
    Sub-headers   : lines starting with ##       →  ##Technical skills:
    Sub-headers are stored as-is so the renderer can detect and style them.
    Drops known skills-section noise artefacts.
    """
    sections, current_header = {}, None
    for line in text.split("\n"):
        clean = line.strip()
        if not clean:
            continue
        # Main section header — ALL CAPS + ends with colon
        if clean.isupper() and clean.endswith(":"):
            current_header = clean
            sections[current_header] = []
        elif current_header:
            # Drop table/software artefacts
            if "SKILL" in current_header.upper() and any(
                x in clean.lower() for x in ["software", "table", "the following"]
            ):
                continue
            sections[current_header].append(clean)
    return sections


def _replace_in_para(p, targets: dict):
    """
    Replace tokens inside a paragraph preserving run formatting.
    Merges all run text first so split tokens like '[' + 'CONTACT_NUMBER' + ']'
    are always found. Result goes into first run; others are cleared.
    """
    if not p.runs:
        return
    full_text = "".join(r.text for r in p.runs)
    if not any(tok in full_text for tok in targets):
        return
    new_text = full_text
    for token, val in targets.items():
        new_text = new_text.replace(token, val)
    if new_text == full_text:
        return
    p.runs[0].text = new_text
    for run in p.runs[1:]:
        run.text = ""


def _scan_element_for_placeholders(element, targets: dict):
    """
    Recursively scan ANY XML element for <w:t> nodes and replace tokens.
    This catches text inside floating text boxes (w:txbxContent), drawing
    shapes, and any other container that normal paragraph/table iteration misses.
    Uses raw XML so nothing is ever skipped regardless of nesting depth.
    """
    from docx.oxml.ns import qn as _qn
    W_T = _qn("w:t")
    # Collect all <w:t> elements anywhere in this element tree
    for wt in element.iter(W_T):
        text = wt.text or ""
        if not any(tok in text for tok in targets):
            continue
        new_text = text
        for token, val in targets.items():
            new_text = new_text.replace(token, val)
        wt.text = new_text

    # Also handle tokens split across sibling <w:t> nodes within the same <w:r>
    # by scanning all <w:p> ancestors and merging runs there too
    W_P = _qn("w:p")
    W_R = _qn("w:r")
    for wp in element.iter(W_P):
        runs = wp.findall(f".//{W_R}")
        full = "".join((r.find(W_T).text or "") if r.find(W_T) is not None else "" for r in runs)
        if not any(tok in full for tok in targets):
            continue
        new_full = full
        for token, val in targets.items():
            new_full = new_full.replace(token, val)
        if new_full == full:
            continue
        # Write back into first w:t of the paragraph, blank the rest
        first_wt = None
        for r in runs:
            wt = r.find(W_T)
            if wt is None:
                continue
            if first_wt is None:
                first_wt = wt
                first_wt.text = new_full
            else:
                wt.text = ""


def replace_all_placeholders(doc, contact: str, title: str, name: str):
    """
    Replace [CONTACT_NUMBER], [DOCUMENT_TITLE] and [NAME] everywhere —
    including inside floating text boxes in headers/footers which the
    standard python-docx .paragraphs iterator completely misses.
    """
    targets = {
        "[CONTACT_NUMBER]": contact,
        "[DOCUMENT_TITLE]": title,
        "[NAME]":           name,
    }

    # Scan every section header and footer element tree in full (catches textboxes)
    for section in doc.sections:
        for part in [section.header, section.footer]:
            _scan_element_for_placeholders(part._element, targets)

    # Scan the main document body element tree in full
    _scan_element_for_placeholders(doc.element.body, targets)


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


# Date keywords used to distinguish "Company | Date" lines from
# job titles that happen to contain a pipe character.
_DATE_KEYWORDS = (
    "present", "current", "now",
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
    "january","february","march","april","june","july",
    "august","september","october","november","december",
)
_DATE_DIGITS_RE = __import__("re").compile(r"\b(19|20)\d{2}\b")


def is_company_date_line(line: str) -> bool:
    """
    Return True only when the part AFTER the last '|' looks like a date range.
    e.g. 'Acme Corp | Jan 2020 - Present'  → True
         'Manager | Team Lead'              → False  (job title with pipe)
         'CPA | Auditing & Accounting'      → False  (education degree with pipe)
    """
    if "|" not in line:
        return False
    after_last_pipe = line.split("|")[-1].strip().lower()
    # Contains a 4-digit year (1900-2099) → it's a date
    if _DATE_DIGITS_RE.search(after_last_pipe):
        return True
    # Contains a month name or 'present' → it's a date
    if any(kw in after_last_pipe for kw in _DATE_KEYWORDS):
        return True
    return False


def _make_two_col_table(doc, total_dxa=8510, date_dxa=2200):
    """
    Invisible 2-column fixed-layout table.
    Default widths match A4 page with 1700 DXA margins (11910 - 3400 = 8510).
    date_dxa=2200 fits 'Sep 2020 - Present' at 10.5pt comfortably.
    """
    from docx.oxml.ns import qn as _qn
    from docx.oxml import OxmlElement as _OE

    content_dxa = total_dxa - date_dxa

    tbl = doc.add_table(rows=1, cols=2)
    tbl.autofit = False

    # ── Fixed table layout — prevents Word redistributing column widths ───
    tblPr = tbl._tbl.tblPr

    tblLayout = _OE("w:tblLayout")
    tblLayout.set(_qn("w:type"), "fixed")
    tblPr.append(tblLayout)

    # ── Lock total table width ────────────────────────────────────────────
    tblW = tblPr.find(_qn("w:tblW"))
    if tblW is None:
        tblW = _OE("w:tblW"); tblPr.append(tblW)
    tblW.set(_qn("w:w"),    str(total_dxa))
    tblW.set(_qn("w:type"), "dxa")

    # ── Remove all borders ────────────────────────────────────────────────
    tblBorders = _OE("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = _OE(f"w:{side}")
        b.set(_qn("w:val"),  "none")
        b.set(_qn("w:sz"),   "0")
        b.set(_qn("w:space"),"0")
        b.set(_qn("w:color"),"auto")
        tblBorders.append(b)
    tblPr.append(tblBorders)

    # ── Define grid columns ───────────────────────────────────────────────
    tblGrid = _OE("w:tblGrid")
    for dxa in (content_dxa, date_dxa):
        gc = _OE("w:gridCol"); gc.set(_qn("w:w"), str(dxa))
        tblGrid.append(gc)
    tbl._tbl.insert(1, tblGrid)   # insert after tblPr

    return tbl, content_dxa, date_dxa


def _lock_cell(cell, dxa):
    """Set explicit DXA width on a cell so Word never overrides it."""
    from docx.oxml.ns import qn as _qn
    from docx.oxml import OxmlElement as _OE
    tcPr = cell._tc.get_or_add_tcPr()
    tcW  = tcPr.find(_qn("w:tcW"))
    if tcW is None:
        tcW = _OE("w:tcW"); tcPr.append(tcW)
    tcW.set(_qn("w:w"),    str(dxa))
    tcW.set(_qn("w:type"), "dxa")


def _no_wrap_cell(cell):
    """
    Prevent cell content from wrapping onto a second line.
    Applied to every date cell so the date stays on one line always.
    """
    from docx.oxml.ns import qn as _qn
    from docx.oxml import OxmlElement as _OE
    tcPr = cell._tc.get_or_add_tcPr()
    nw   = _OE("w:noWrap")
    tcPr.append(nw)


def add_experience_row(doc, company_part: str, date_part: str, job_title: str):
    """
    2-row fixed-layout table:
      Row 1: COMPANY (bold UPPER, left)    | Date (italic, LEFT, no-wrap)
      Row 2: Job title (bold, left)        | [empty, no-wrap]

    Fixed layout + explicit DXA widths ensure dates ALWAYS start at the
    same column and NEVER wrap — regardless of content length.
    """
    TOTAL = 8510    # A4 body: 11910 - 1700*2 margins
    DATE  = 2200    # 1.53" — fits "Sep 2020 - Present" at 10.5pt
    CONT  = TOTAL - DATE

    tbl, _, _ = _make_two_col_table(doc, total_dxa=TOTAL, date_dxa=DATE)

    # The table was created with 1 row — add a second
    from docx.oxml import OxmlElement as _OE
    from docx.oxml.ns import qn as _qn
    tr2 = _OE("w:tr"); tbl._tbl.append(tr2)
    for dxa in (CONT, DATE):
        tc = _OE("w:tc")
        tcPr = _OE("w:tcPr"); tcW = _OE("w:tcW")
        tcW.set(_qn("w:w"), str(dxa)); tcW.set(_qn("w:type"), "dxa")
        tcPr.append(tcW); tc.append(tcPr)
        p = _OE("w:p"); tc.append(p); tr2.append(tc)

    r0c0, r0c1 = tbl.rows[0].cells
    r1c0, r1c1 = tbl.rows[1].cells

    # Lock every cell width
    for cell, dxa in [(r0c0, CONT), (r0c1, DATE), (r1c0, CONT), (r1c1, DATE)]:
        _lock_cell(cell, dxa)

    # No-wrap on date cells (must be set BEFORE adding text)
    _no_wrap_cell(r0c1)
    _no_wrap_cell(r1c1)

    # Row 1: Company | Date
    _base_run(r0c0.paragraphs[0], company_part.strip().upper(), bold=True)
    r0c1.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
    _base_run(r0c1.paragraphs[0], date_part.strip(), italic=True)

    # Row 2: Job title | empty
    _base_run(r1c0.paragraphs[0], sentence_case(job_title), bold=True)

    # Spacing
    for p in (r0c0.paragraphs[0], r0c1.paragraphs[0]):
        p.paragraph_format.space_before = Pt(SP)
        p.paragraph_format.space_after  = Pt(2)
    for p in (r1c0.paragraphs[0], r1c1.paragraphs[0]):
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(SP)

    return tbl


def add_education_row(doc, degree_part: str, date_part: str, institution: str = ""):
    """
    2-row fixed-layout table (same widths as experience so dates align):
      Row 1: DEGREE (bold ALL CAPS, left)          | Date (italic, LEFT, no-wrap)
      Row 2: Institution (unbold, sentence case)    | [empty, no-wrap]

    Degree is ALL CAPS bold.
    Institution is sentence case, not bold, starting on the line below.
    Date column is identical to experience — all dates line up across the doc.
    """
    TOTAL = 8510
    DATE  = 2200
    CONT  = TOTAL - DATE

    rows_needed = 2 if institution else 1
    tbl, _, _ = _make_two_col_table(doc, total_dxa=TOTAL, date_dxa=DATE)

    from docx.oxml import OxmlElement as _OE
    from docx.oxml.ns import qn as _qn

    if rows_needed == 2:
        tr2 = _OE("w:tr"); tbl._tbl.append(tr2)
        for dxa in (CONT, DATE):
            tc = _OE("w:tc")
            tcPr = _OE("w:tcPr"); tcW = _OE("w:tcW")
            tcW.set(_qn("w:w"), str(dxa)); tcW.set(_qn("w:type"), "dxa")
            tcPr.append(tcW); tc.append(tcPr)
            p = _OE("w:p"); tc.append(p); tr2.append(tc)

    r0c0, r0c1 = tbl.rows[0].cells
    _lock_cell(r0c0, CONT);  _lock_cell(r0c1, DATE)
    _no_wrap_cell(r0c1)   # set BEFORE adding text

    # Row 1: Degree ALL CAPS bold | Date italic LEFT no-wrap
    _base_run(r0c0.paragraphs[0], degree_part.strip().upper(), bold=True)
    r0c1.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
    _base_run(r0c1.paragraphs[0], date_part.strip(), italic=True)

    r0c0.paragraphs[0].paragraph_format.space_before = Pt(4)
    r0c0.paragraphs[0].paragraph_format.space_after  = Pt(2)
    r0c1.paragraphs[0].paragraph_format.space_before = Pt(4)
    r0c1.paragraphs[0].paragraph_format.space_after  = Pt(2)

    if institution:
        r1c0, r1c1 = tbl.rows[1].cells
        _lock_cell(r1c0, CONT); _lock_cell(r1c1, DATE)
        _no_wrap_cell(r1c1)   # set BEFORE adding text

        # Row 2: Institution unbold sentence case | empty
        _base_run(r1c0.paragraphs[0], sentence_case(institution.strip()), bold=False)
        r1c0.paragraphs[0].paragraph_format.space_before = Pt(0)
        r1c0.paragraphs[0].paragraph_format.space_after  = Pt(SP)
        r1c1.paragraphs[0].paragraph_format.space_before = Pt(0)
        r1c1.paragraphs[0].paragraph_format.space_after  = Pt(SP)

    return tbl


def set_keep_with_next(paragraph):
    """
    Set keepWithNext on a paragraph via XML so Word moves the whole
    block to the next page if it would otherwise start on the last line.
    """
    pPr = paragraph._element.get_or_add_pPr()
    kwn = OxmlElement("w:keepWithNext")
    pPr.append(kwn)


def set_keep_together(paragraph):
    """
    Set keepLines on a paragraph so its lines are never split across pages.
    """
    pPr = paragraph._element.get_or_add_pPr()
    kl = OxmlElement("w:keepLines")
    pPr.append(kl)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Main Content Area
# ─────────────────────────────────────────────────────────────────────────────
st.title("Professional Resume Artisan")
uploaded_file = st.file_uploader("Drop Resume", type=["pdf", "docx", "png", "jpg", "jpeg"])
generate_btn  = st.button("✨ START AI TRANSFORMATION")

if uploaded_file and generate_btn:
    with st.status("🛠️ Re-architecting Content...", expanded=True):
        try:
            model = genai.GenerativeModel(MODEL_NAME)

            # ── Extract raw content from file ────────────────────────────────
            st.write("📄 Reading resume...")
            if uploaded_file.type == "application/pdf":
                raw = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_file).pages])
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                raw = "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
            else:
                raw = Image.open(uploaded_file)

            # ── STAGE 1: Deep understanding ──────────────────────────────────
            st.write("🧠 Reading and understanding resume deeply...")

            understanding_prompt = """
You are an expert resume analyst. Before doing anything else, READ THE ENTIRE
RESUME from top to bottom, understand its full structure, every section, every
role, every qualification. Only after fully understanding it, produce the
structured output below.

═══════════════════════════════════════════════════════
STEP 1 — UNDERSTAND THE STRUCTURE
═══════════════════════════════════════════════════════
Identify every section in the resume — common ones include:
  Summary / Objective / Profile
  Experience / Work History / Employment
  Education / Academic Background / Qualifications
  Certifications / Licenses / Accreditations
  Skills / Core Competencies / Technical Skills / Professional Skills
  Tools / Technologies / Software
  Projects / Publications / Awards / Languages / etc.

IMPORTANT — SHARED SECTIONS:
Some resumes combine two topics under one heading, such as:
  "Education and Certifications", "Skills and Tools",
  "Certifications and Licenses", "Education and Professional Development"
When you see this, SPLIT them into TWO separate ALL-CAPS headers.
Example: "EDUCATION AND CERTIFICATIONS:" → write as:
  EDUCATION:
  (all education entries)
  CERTIFICATIONS:
  (all certification entries)

IMPORTANT — SKILLS WITH SUB-CATEGORIES:
If the resume lists skills under sub-categories like:
  Technical Skills: Python, SQL, Azure
  Professional Skills: Leadership, Communication
  Soft Skills: ...
Then preserve those sub-categories. Write the main header as CORE SKILLS:
and use indented sub-headers like:
  ##Technical skills:
  (skills listed as bullets)
  ##Professional skills:
  (skills listed as bullets)
The ## prefix marks a sub-header — do NOT use ## for main section headers.

═══════════════════════════════════════════════════════
STEP 2 — STRIP ALL PERSONAL / CONTACT INFORMATION
═══════════════════════════════════════════════════════
Remove completely — do NOT include anywhere in output:
  - Candidate full name
  - Phone numbers (any format)
  - Email addresses
  - LinkedIn, GitHub, portfolio, or any URLs
  - Home address, city, state, zip, country of residence
  - Any line that exists solely to identify the person

═══════════════════════════════════════════════════════
STEP 3 — STRUCTURE THE OUTPUT
═══════════════════════════════════════════════════════
Return a clean plain-text structured resume using these rules:

SECTION HEADERS:
  - ALL CAPS ending with a colon: EXPERIENCE:  EDUCATION:  CORE SKILLS:
  - Use EXPERIENCE: (never "Work History / Education" or combined labels)
  - Each main header on its own line

SUB-HEADERS (skills sub-categories only):
  - Prefix with ## and title case: ##Technical skills:
  - On its own line, directly inside the main section

EXPERIENCE ENTRIES:
  - Line 1: Company Name | Date Range
  - Line 2: Job Title  (on its own line, below company)
  - Lines 3+: bullet points starting with •
  - Every description line MUST start with • (never leave description unbulleted)
  - Job descriptions are plain text — NO bold, no asterisks, no markdown

DATE RANGE RULES (critical):
  - Format: Mon YYYY - Mon YYYY   or   Mon YYYY - Present
  - Use ONLY the first 3 letters of any month: Jan Feb Mar Apr May Jun
    Jul Aug Sep Oct Nov Dec
  - If BOTH month AND year are given: Jan 2020 - Mar 2023
  - If ONLY year is given: 2020 - 2023  (do NOT invent a month)
  - If NO date is given at all: leave the date field completely EMPTY
    (do NOT write "Date Unknown", "N/A", or any placeholder)
  - The entire date range must fit on one line — never split across two lines

EDUCATION ENTRIES:
  - Line 1: Degree Name | Date  (date only if actually present in the resume)
  - Line 2: Institution Name  (on its own line below the degree)
  - If no date: Degree Name | (leave after pipe empty, or omit pipe if no date)

CERTIFICATIONS:
  - Certification Name | Date  (if date present)
  - Issuing body on the next line (if present)
  - If no date: just the certification name, no pipe

BULLETS:
  - Every job description point MUST start with •
  - Never leave a description line without a bullet
  - No bold, no asterisks, no markdown inside bullet text

GENERAL:
  - No markdown formatting anywhere (no **, no *, no #, no ---)
  - No mention of "Table", "Software" as content artefacts
  - No fabrication — only use information present in the original resume
  - No contact details anywhere in the output

Now read the resume completely, understand every section, then produce the
fully structured output:
"""

            stage1_response = model.generate_content(
                [understanding_prompt, raw] if not isinstance(raw, str)
                else [understanding_prompt, f"RESUME TEXT:\n{raw}"]
            )
            understood_resume = stage1_response.text.replace("**", "").strip()

            # ── STAGE 2: Polish and enforce all formatting rules ──────────────
            st.write("✨ Polishing and finalising...")

            sum_p = (
                f"Write or improve the SUMMARY: section using these focus points: "
                f"{custom_points}. If no focus points given, craft a strong "
                f"executive summary from the candidate's experience and skills."
            ) if include_summary else "Do NOT add, change, or remove any SUMMARY: section."

            priv_p = (
                "CONFIDENTIALITY RULE: Replace every employer/company name with "
                "'[CONFIDENTIAL]'. Apply this to every experience entry without exception."
            ) if make_confidential else ""

            reformat_prompt = f"""
You are a professional resume formatter. The resume below has already been
read and structured. Your job is to do a final quality pass — enforce every
formatting rule precisely and improve bullet point language.

{sum_p}
{priv_p}

FORMATTING RULES — enforce every single one:

1. SECTION HEADERS — ALL CAPS ending with colon. One per line.
   Valid examples: SUMMARY:  EXPERIENCE:  EDUCATION:  CORE SKILLS:
   CERTIFICATIONS:  TOOLS:  PROJECTS:

2. SUB-HEADERS (inside skills/tools sections only):
   Keep lines starting with ## exactly as-is: ##Technical skills:
   These are sub-headers — do NOT convert them to main headers.

3. EXPERIENCE ENTRIES — strict two-line format:
   Line 1: COMPANY NAME | Date Range
   Line 2: Job Title
   Then bullet points. Never put company and job title on the same line.

4. JOB DESCRIPTIONS — every single description line MUST:
   - Start with a bullet: •
   - Be plain text — NO bold, no asterisks, no markdown
   - Be action-oriented and results-focused
   - Never be left unbulleted even if the original had no bullet

5. DATE RANGE — strict format:
   - Use 3-letter month abbreviations only: Jan Feb Mar Apr May Jun
     Jul Aug Sep Oct Nov Dec
   - Format: Mon YYYY - Mon YYYY   OR   Mon YYYY - Present
   - Year only (if no month in resume): 2019 - 2022
   - NO date in resume: leave the date portion completely blank
     (NEVER write "Date Unknown", "N/A", "Present" if not stated)
   - The entire date range must fit on ONE line — never wrap

6. EDUCATION — Line 1: Degree | Date (blank after | if no date)
   Line 2: Institution

7. CERTIFICATIONS — Name | Date (if date given), institution on next line

8. BULLETS in all sections:
   - Must start with •
   - No bold, no asterisks, no markdown

9. NO fabrication — do not add experience, dates, or qualifications
   not present in the resume below.

10. NO contact details — no name, phone, email, address, or URLs.

11. Return ONLY the final resume text. No commentary, no preamble.

RESUME TO FINALISE:
{understood_resume}
"""

            stage2_response = model.generate_content(reformat_prompt)
            st.session_state.original_ai_output = (
                stage2_response.text
                .replace("**", "")
                .replace("__", "")
                .strip()
            )
            st.write("✅ Done!")

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

        replace_all_placeholders(doc, contact_number, document_name, document_name)

        # ── CLEAR EMPTY TEMPLATE BODY PARAGRAPHS ─────────────────────────────
        # The template body contains placeholder empty paragraphs that push
        # content to mid-page. Remove every trailing empty paragraph from the
        # body so resume content starts immediately after the template header.
        from docx.oxml.ns import qn as _qn
        body = doc.element.body
        # Remove empty paragraphs at the END of the body (before sectPr)
        # We keep going until we hit a non-empty paragraph or a table.
        while True:
            # Last child before sectPr
            children = [c for c in body if c.tag != _qn('w:sectPr')]
            if not children:
                break
            last = children[-1]
            # If it's a paragraph with no text content, remove it
            if last.tag == _qn('w:p'):
                text = "".join(t.text or "" for t in last.iter(_qn('w:t')))
                if not text.strip():
                    body.remove(last)
                    continue
            break

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
            set_keep_with_next(hp)   # XML-level keep — pushes to next page if on last line
            _base_run(hp, h, bold=True, size_pt=11)

            # ── Section Content ───────────────────────────────────────────────
            lines = current_sections[h]
            i = 0

            while i < len(lines):
                line = lines[i]

                # ════════════════════════════════════════════════════════════
                # LIST SECTIONS  (Skills / Certifications / Tools / etc.)
                #   • Lines starting with ## are sub-headers (e.g. ##Technical skills:)
                #   • '|' splits into individual items, each its own bullet
                #   • Everything sentence case, never bold
                # ════════════════════════════════════════════════════════════
                if is_list:
                    if line.startswith("##"):
                        # Sub-header — render as small bold label, not a bullet
                        sub_text = line.lstrip("#").strip()
                        sp = doc.add_paragraph()
                        sp.paragraph_format.space_before = Pt(SP)
                        sp.paragraph_format.space_after  = Pt(3)
                        sp.paragraph_format.keep_with_next = True
                        r = sp.add_run(sentence_case(sub_text))
                        r.bold      = True
                        r.font.name = "Arial"
                        r.font.size = Pt(10.5)
                    elif "|" in line and not is_company_date_line(line):
                        # '|' = multiple skill items on one line → split into bullets
                        for seg in split_by_pipe(line):
                            add_bullet(doc, sentence_case(seg), bold=False)
                    else:
                        add_bullet(doc, sentence_case(line), bold=False)
                    i += 1

                # ════════════════════════════════════════════════════════════
                # EXPERIENCE
                #   Company | Date  +  next line = Job Title
                #   → 2-row table: row1=company+date, row2=job title
                #   All description bullets → plain text, never bold
                # ════════════════════════════════════════════════════════════
                elif is_exp:
                    if is_company_date_line(line):
                        # ── Company | Date row ────────────────────────────────
                        parts       = line.split("|")
                        company_str = parts[0].strip()
                        date_str    = parts[-1].strip()
                        # Peek ahead for the job title (may itself contain '|')
                        job_title = ""
                        if i + 1 < len(lines) and not is_company_date_line(lines[i + 1]):
                            job_title = lines[i + 1]
                            i += 1   # consume the title line
                        # Anchor paragraph — keep_with_next pushes whole block
                        anchor = doc.add_paragraph()
                        anchor.paragraph_format.space_before   = Pt(0)
                        anchor.paragraph_format.space_after    = Pt(0)
                        anchor.paragraph_format.keep_with_next = True
                        set_keep_with_next(anchor)
                        add_experience_row(doc, company_str, date_str, job_title)
                    else:
                        # All non-company-date lines in experience are descriptions
                        # → always render as unbold bullet regardless of prefix
                        clean_line = line.lstrip("•*-– ").strip()
                        add_bullet(doc, sentence_case(clean_line), bold=False)
                    i += 1

                # ════════════════════════════════════════════════════════════
                # EDUCATION
                #   Degree | Date  →  bold degree + italic date  (row 1)
                #   Institution    →  unbold, same line structure  (row 2)
                #   Both rows in ONE table so degree and institution are
                #   vertically aligned and never split across pages.
                # ════════════════════════════════════════════════════════════
                elif is_edu:
                    if is_company_date_line(line):
                        parts      = line.split("|")
                        degree_str = parts[0].strip()
                        date_str   = parts[-1].strip()
                        # Peek ahead for institution line
                        institution = ""
                        if i + 1 < len(lines) and not is_company_date_line(lines[i + 1]):
                            institution = lines[i + 1]
                            i += 1   # consume institution line
                        # Anchor paragraph keeps whole block together
                        anchor = doc.add_paragraph()
                        anchor.paragraph_format.space_before   = Pt(0)
                        anchor.paragraph_format.space_after    = Pt(0)
                        anchor.paragraph_format.keep_with_next = True
                        set_keep_with_next(anchor)
                        add_education_row(doc, degree_str, date_str, institution)
                    else:
                        # Stray line in education → plain, sentence case
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
        file_name = f"{document_name.strip().upper()}.docx" if document_name.strip() else "RESUME.docx"
        st.download_button(
            label=f"📥 DOWNLOAD {company_choice} DOCX",
            data=buf.getvalue(),
            file_name=file_name,
        )
