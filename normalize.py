"""Normalization helpers. Deterministic, no network calls."""
import re
import datetime

# --- Phones --------------------------------------------------------------

# Minimal, dependency-free E.164 normalizer. We support a small set of
# explicit country hints (default: India, since most sample data here is
# India-based recruiting) and fall back to "best effort" digit cleanup.
_DEFAULT_COUNTRY_CODE = "91"  # India

_COUNTRY_LENS = {
    "1": 10,    # US/Canada
    "91": 10,   # India
    "44": 10,   # UK
}


def normalize_phone(raw: str, default_country_code: str = _DEFAULT_COUNTRY_CODE):
    """Best-effort E.164 normalization. Returns (value, ok) where ok=False
    means we couldn't confidently normalize (caller should lower confidence
    or drop it, never invent digits)."""
    if not raw:
        return None, False
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        cc_and_rest = digits[1:]
        # try known country codes longest-first
        for cc in sorted(_COUNTRY_LENS, key=len, reverse=True):
            if cc_and_rest.startswith(cc):
                rest = cc_and_rest[len(cc):]
                if len(rest) == _COUNTRY_LENS[cc]:
                    return f"+{cc}{rest}", True
        # unknown country code but well-formed-ish
        if 8 <= len(cc_and_rest) <= 15:
            return f"+{cc_and_rest}", True
        return None, False
    digits_only = re.sub(r"\D", "", digits)
    expected_len = _COUNTRY_LENS.get(default_country_code, 10)
    if len(digits_only) == expected_len:
        return f"+{default_country_code}{digits_only}", True
    if len(digits_only) == expected_len + len(default_country_code) and digits_only.startswith(default_country_code):
        return f"+{digits_only}", True
    return None, False


# --- Dates -----------------------------------------------------------------

_MONTHS = {
    "jan": "01", "january": "01", "feb": "02", "february": "02", "mar": "03",
    "march": "03", "apr": "04", "april": "04", "may": "05", "jun": "06",
    "june": "06", "jul": "07", "july": "07", "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09", "oct": "10", "october": "10",
    "nov": "11", "november": "11", "dec": "12", "december": "12",
}


def normalize_date_to_yyyymm(raw: str):
    """Normalize a free-text date to YYYY-MM. Returns (value, ok).
    Recognizes 'present'/'current' as a sentinel -> returns ('present', True).
    Never guesses a month/year that isn't present in the source."""
    if not raw:
        return None, False
    s = raw.strip()
    if re.fullmatch(r"(?i)present|current|now|ongoing", s):
        return "present", True
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m:
        return s, True
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return f"{s}-01", True  # year-only: month unknown, flagged by caller as lower confidence
    m = re.match(r"(?i)([a-zA-Z]+)\.?\s+(\d{4})", s)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            return f"{m.group(2)}-{mon}", True
    m = re.match(r"(\d{1,2})/(\d{4})", s)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}", True
    return None, False


# --- Skills ------------------------------------------------------------

# Small canonicalization map. Real system would use a larger taxonomy;
# this demonstrates the mechanism (alias -> canonical name).
_SKILL_ALIASES = {
    "js": "JavaScript", "javascript": "JavaScript", "node": "Node.js",
    "nodejs": "Node.js", "node.js": "Node.js", "py": "Python", "python": "Python",
    "python3": "Python", "react": "React", "reactjs": "React", "react.js": "React",
    "golang": "Go", "go": "Go", "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "ml": "Machine Learning",
    "machine learning": "Machine Learning", "tf": "TensorFlow", "tensorflow": "TensorFlow",
    "aws": "AWS", "amazon web services": "AWS", "sql": "SQL", "c++": "C++",
    "java": "Java", "typescript": "TypeScript", "ts": "TypeScript",
    "docker": "Docker", "django": "Django", "flask": "Flask", "git": "Git",
    "rest api": "REST APIs", "rest apis": "REST APIs", "graphql": "GraphQL",
}


def canonicalize_skill(raw: str):
    if not raw:
        return None
    key = raw.strip().lower().strip(".,")
    if not key:
        return None
    return _SKILL_ALIASES.get(key, raw.strip().title() if key.islower() else raw.strip())


# --- Country / location -----------------------------------------------------

_COUNTRY_ISO = {
    "india": "IN", "united states": "US", "usa": "US", "u.s.a.": "US", "us": "US",
    "united kingdom": "GB", "uk": "GB", "canada": "CA", "germany": "DE",
    "singapore": "SG", "australia": "AU",
}


def normalize_country(raw: str):
    if not raw:
        return None
    key = raw.strip().lower()
    if len(raw.strip()) == 2 and raw.strip().isalpha():
        return raw.strip().upper()
    return _COUNTRY_ISO.get(key, None)  # unknown -> None rather than guessing


# --- Email -------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def normalize_email(raw: str):
    if not raw:
        return None, False
    m = _EMAIL_RE.search(raw)
    if not m:
        return None, False
    return m.group(0).strip().lower(), True
