"""Structured extractor: ATS JSON blob. Field names intentionally differ
from our canonical schema (e.g. 'candidate_name', 'contact.email_address')
to demonstrate field remapping at the extraction layer."""
import json
from pipeline.models import RawRecord, ProvenancedValue
from pipeline.normalize import normalize_email, normalize_phone, normalize_date_to_yyyymm, canonicalize_skill


def _get(d, *path):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def extract_ats_json(path: str):
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []  # garbage source -> no record, never invented

    blobs = data if isinstance(data, list) else [data]

    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        rec = RawRecord(source="ats_json", candidate_key="")

        name = _get(blob, "candidate_name") or blob.get("name")
        if name:
            rec.full_name = ProvenancedValue(name, "ats_json", "direct", 0.9)

        email_raw = _get(blob, "contact", "email_address") or blob.get("email")
        if email_raw:
            email, ok = normalize_email(email_raw)
            if ok:
                rec.emails.append(ProvenancedValue(email, "ats_json", "direct", 0.95))
            else:
                rec.errors.append(f"unparseable email: {email_raw!r}")

        phone_raw = _get(blob, "contact", "phone_number") or blob.get("phone")
        if phone_raw:
            phone, ok = normalize_phone(phone_raw)
            if ok:
                rec.phones.append(ProvenancedValue(phone, "ats_json", "e164", 0.85))
            else:
                rec.errors.append(f"unparseable phone: {phone_raw!r}")

        loc = blob.get("location") or {}
        if isinstance(loc, dict) and (loc.get("city") or loc.get("country")):
            rec.location = ProvenancedValue(
                {"city": loc.get("city"), "region": loc.get("state") or loc.get("region"),
                 "country": loc.get("country")},
                "ats_json", "direct", 0.7,
            )

        for job in blob.get("work_history") or []:
            if not isinstance(job, dict):
                continue
            start, _ = normalize_date_to_yyyymm(job.get("start_date") or "")
            end, _ = normalize_date_to_yyyymm(job.get("end_date") or "")
            rec.experience.append(ProvenancedValue(
                {"company": job.get("employer"), "title": job.get("role"),
                 "start": start, "end": end, "summary": job.get("description")},
                "ats_json", "direct", 0.75,
            ))

        for sk in blob.get("skill_tags") or []:
            if isinstance(sk, str) and sk.strip():
                canon = canonicalize_skill(sk)
                if canon:
                    rec.skills.append(ProvenancedValue(canon, "ats_json", "direct", 0.6))

        yoe = blob.get("years_of_experience")
        if isinstance(yoe, (int, float)):
            rec.years_experience = ProvenancedValue(yoe, "ats_json", "direct", 0.8)

        rec.candidate_key = (rec.emails[0].value if rec.emails else
                              (name.lower().strip() if name else f"ats-row-{len(records)}"))
        records.append(rec)

    return records
