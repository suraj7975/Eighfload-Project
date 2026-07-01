"""Unstructured extractor: resume files (PDF or DOCX).

Resumes are free text, so extraction here is heuristic/regex-based and
gets lower confidence than structured sources. We never fabricate a
field that isn't textually present.
"""
import re
import os
from pipeline.models import RawRecord, ProvenancedValue
from pipeline.normalize import normalize_email, normalize_phone, canonicalize_skill

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s().]{7,}\d)")
_LINKEDIN_RE = re.compile(r"(https?://)?(www\.)?linkedin\.com/in/[A-Za-z0-9\-_/]+", re.I)
_GITHUB_RE = re.compile(r"(https?://)?(www\.)?github\.com/[A-Za-z0-9\-_/]+", re.I)

_SKILL_SECTION_RE = re.compile(r"(?im)^\s*(skills|technical skills|technologies)\s*:?\s*$")
_EDU_SECTION_RE = re.compile(r"(?im)^\s*(education)\s*:?\s*$")
_EXP_SECTION_RE = re.compile(r"(?im)^\s*(experience|work experience|employment)\s*:?\s*$")


def _read_text(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        import pdfplumber
        text = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                text.append(t)
        return "\n".join(text)
    if ext in (".docx",):
        import docx
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError(f"unsupported resume format: {ext}")


def _extract_section(text, start_re, all_section_res):
    m = start_re.search(text)
    if not m:
        return None
    start = m.end()
    # find earliest next-section start after this one
    end = len(text)
    for r in all_section_res:
        m2 = r.search(text, start)
        if m2 and m2.start() < end:
            end = m2.start()
    return text[start:end].strip()


def extract_resume(path: str):
    try:
        text = _read_text(path)
    except Exception:
        return []  # unreadable/garbage file -> no record, not a crash

    if not text or not text.strip():
        return []

    rec = RawRecord(source="resume", candidate_key="")

    # Name heuristic: first non-empty line, if it looks like a name (no @, digits, etc.)
    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    if first_line and not _EMAIL_RE.search(first_line) and not re.search(r"\d", first_line) and len(first_line.split()) <= 5:
        rec.full_name = ProvenancedValue(first_line, "resume", "heuristic:first_line", 0.5)

    email_m = _EMAIL_RE.search(text)
    if email_m:
        email, ok = normalize_email(email_m.group(0))
        if ok:
            rec.emails.append(ProvenancedValue(email, "resume", "regex", 0.8))

    phone_m = _PHONE_RE.search(text)
    if phone_m:
        phone, ok = normalize_phone(phone_m.group(0))
        if ok:
            rec.phones.append(ProvenancedValue(phone, "resume", "regex+e164", 0.55))

    li = _LINKEDIN_RE.search(text)
    if li:
        url = li.group(0)
        if not url.startswith("http"):
            url = "https://" + url
        rec.links["linkedin"] = ProvenancedValue(url, "resume", "regex", 0.8)

    gh = _GITHUB_RE.search(text)
    if gh:
        url = gh.group(0)
        if not url.startswith("http"):
            url = "https://" + url
        rec.links["github"] = ProvenancedValue(url, "resume", "regex", 0.8)

    section_res = [_SKILL_SECTION_RE, _EDU_SECTION_RE, _EXP_SECTION_RE]
    skills_block = _extract_section(text, _SKILL_SECTION_RE, section_res)
    if skills_block:
        for raw in re.split(r"[,\n•|]", skills_block):
            sk = canonicalize_skill(raw)
            if sk and len(sk) < 40:
                rec.skills.append(ProvenancedValue(sk, "resume", "section:skills", 0.55))

    edu_block = _extract_section(text, _EDU_SECTION_RE, section_res)
    if edu_block:
        for line in [l.strip() for l in edu_block.splitlines() if l.strip()][:5]:
            yr = re.search(r"(19|20)\d{2}", line)
            rec.education.append(ProvenancedValue(
                {"institution": line, "degree": None, "field": None,
                 "end_year": int(yr.group(0)) if yr else None},
                "resume", "heuristic:line", 0.4,
            ))

    rec.candidate_key = (rec.emails[0].value if rec.emails else
                          (rec.full_name.value.lower() if rec.full_name else os.path.basename(path)))
    return [rec]
