"""Structured extractor: Recruiter CSV export."""
import csv
from pipeline.models import RawRecord, ProvenancedValue
from pipeline.normalize import normalize_email, normalize_phone


def extract_csv(path: str):
    """Reads a recruiter CSV with columns: name, email, phone,
    current_company, title (header names are matched case-insensitively;
    missing columns are tolerated). One row -> one RawRecord."""
    records = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return records
            field_map = {fn.strip().lower(): fn for fn in reader.fieldnames}

            def get(row, key):
                fn = field_map.get(key)
                return (row.get(fn) or "").strip() if fn else ""

            for row in reader:
                name = get(row, "name")
                email_raw = get(row, "email")
                phone_raw = get(row, "phone")
                company = get(row, "current_company")
                title = get(row, "title")

                if not any([name, email_raw, phone_raw]):
                    continue  # fully blank row, skip rather than emit a junk record

                rec = RawRecord(source="csv", candidate_key="")
                if name:
                    rec.full_name = ProvenancedValue(name, "csv", "direct", 0.9)

                if email_raw:
                    email, ok = normalize_email(email_raw)
                    if ok:
                        rec.emails.append(ProvenancedValue(email, "csv", "direct", 0.95))
                    else:
                        rec.errors.append(f"unparseable email: {email_raw!r}")

                if phone_raw:
                    phone, ok = normalize_phone(phone_raw)
                    if ok:
                        rec.phones.append(ProvenancedValue(phone, "csv", "e164", 0.85))
                    else:
                        rec.errors.append(f"unparseable phone: {phone_raw!r}")

                if company or title:
                    rec.experience.append(ProvenancedValue(
                        {"company": company or None, "title": title or None,
                         "start": None, "end": "present" if (company or title) else None,
                         "summary": None},
                        "csv", "direct", 0.7,
                    ))

                rec.candidate_key = (rec.emails[0].value if rec.emails else
                                      (name.lower().strip() if name else f"csv-row-{len(records)}"))
                records.append(rec)
    except FileNotFoundError:
        return []
    except Exception as e:
        # Malformed CSV must not crash the run.
        return []
    return records
