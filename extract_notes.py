"""Unstructured extractor: recruiter notes (.txt) - free text scribbles.
Lowest-confidence source: we only pull what we can regex with reasonable
certainty (email, phone, explicit 'N years experience' mentions, skill
mentions when prefixed by a recognizable cue like 'knows' / 'skills:')."""
import re
from pipeline.models import RawRecord, ProvenancedValue
from pipeline.normalize import normalize_email, normalize_phone, canonicalize_skill

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\-\s().]{7,}\d)")
_YOE_RE = re.compile(r"(\d{1,2})\s*\+?\s*years?\s*(of\s*)?experience", re.I)
_SKILLS_CUE_RE = re.compile(r"(?i)(?:skills|knows|familiar with|strong in)\s*[:\-]?\s*(.+)")


def extract_notes(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return []
    except Exception:
        return []

    if not text.strip():
        return []

    rec = RawRecord(source="notes", candidate_key="")

    email_m = _EMAIL_RE.search(text)
    if email_m:
        email, ok = normalize_email(email_m.group(0))
        if ok:
            rec.emails.append(ProvenancedValue(email, "notes", "regex", 0.6))

    phone_m = _PHONE_RE.search(text)
    if phone_m:
        phone, ok = normalize_phone(phone_m.group(0))
        if ok:
            rec.phones.append(ProvenancedValue(phone, "notes", "regex+e164", 0.4))

    yoe_m = _YOE_RE.search(text)
    if yoe_m:
        rec.years_experience = ProvenancedValue(int(yoe_m.group(1)), "notes", "regex", 0.5)

    sk_m = _SKILLS_CUE_RE.search(text)
    if sk_m:
        for raw in re.split(r"[,/]| and ", sk_m.group(1)):
            sk = canonicalize_skill(raw.strip().rstrip(".!"))
            if sk and len(sk) < 40:
                rec.skills.append(ProvenancedValue(sk, "notes", "regex:cue", 0.4))

    # Free-text headline: first sentence, only if short and name not required here.
    first_sentence = text.strip().split(".")[0].strip()
    if first_sentence and len(first_sentence) < 120:
        rec.headline = ProvenancedValue(first_sentence, "notes", "heuristic:first_sentence", 0.3)

    rec.candidate_key = rec.emails[0].value if rec.emails else f"notes-{hash(text) & 0xffff}"
    return [rec]
