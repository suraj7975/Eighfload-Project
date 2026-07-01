"""Merge a group of RawRecords (all believed to be the same person) into
one canonical profile.

Conflict policy: for single-value fields, pick the candidate value with
the highest (source_trust * extractor_confidence) score; ties broken by
source priority order. Source trust reflects how reliable a *source type*
is in general (structured > unstructured), separate from the per-field
extraction confidence already on each ProvenancedValue.
"""
import hashlib
from pipeline.normalize import normalize_country

SOURCE_TRUST = {
    "ats_json": 1.00,
    "csv": 0.95,
    "resume": 0.75,
    "notes": 0.55,
}


def _score(pv):
    return SOURCE_TRUST.get(pv.source, 0.5) * pv.confidence


def _pick_best(values):
    """values: list[ProvenancedValue] for the same scalar field across
    sources. Returns the winning ProvenancedValue, or None."""
    if not values:
        return None
    return max(values, key=_score)


def _dedupe_list(values, key_fn):
    """For list fields (emails, phones, skills): keep one ProvenancedValue
    per unique key, preferring the highest score; also keep a record of
    all sources that mentioned it."""
    best = {}
    sources = {}
    for v in values:
        k = key_fn(v.value)
        sources.setdefault(k, set()).add(v.source)
        if k not in best or _score(v) > _score(best[k]):
            best[k] = v
    return best, sources


def merge_group(group, candidate_id_seed):
    provenance = []

    def record_prov(field, pv, method=None):
        provenance.append({"field": field, "source": pv.source, "method": method or pv.method})

    # --- full_name ---
    name_candidates = [r.full_name for r in group if r.full_name]
    best_name = _pick_best(name_candidates)
    full_name = best_name.value if best_name else None
    if best_name:
        record_prov("full_name", best_name)

    # --- emails (list, deduped) ---
    all_emails = [e for r in group for e in r.emails]
    best_emails, email_sources = _dedupe_list(all_emails, lambda v: v)
    emails = sorted(best_emails.keys(), key=lambda k: -_score(best_emails[k]))
    for k in emails:
        record_prov("emails", best_emails[k])

    # --- phones (list, deduped) ---
    all_phones = [p for r in group for p in r.phones]
    best_phones, phone_sources = _dedupe_list(all_phones, lambda v: v)
    phones = sorted(best_phones.keys(), key=lambda k: -_score(best_phones[k]))
    for k in phones:
        record_prov("phones", best_phones[k])

    # --- location ---
    loc_candidates = [r.location for r in group if r.location]
    best_loc = _pick_best(loc_candidates)
    location = None
    if best_loc:
        v = dict(best_loc.value)
        if v.get("country"):
            iso = normalize_country(v["country"])
            v["country"] = iso  # None if we can't confidently map it -> honestly empty
        location = v
        record_prov("location", best_loc)

    # --- links ---
    links = {"linkedin": None, "github": None, "portfolio": None, "other": []}
    link_candidates = {}
    for r in group:
        for name, pv in r.links.items():
            link_candidates.setdefault(name, []).append(pv)
    for name in ("linkedin", "github", "portfolio"):
        best = _pick_best(link_candidates.get(name, []))
        if best:
            links[name] = best.value
            record_prov(f"links.{name}", best)
    for pv in link_candidates.get("other", []):
        links["other"].append(pv.value)
        record_prov("links.other", pv)

    # --- headline ---
    headline_candidates = [r.headline for r in group if r.headline]
    best_headline = _pick_best(headline_candidates)
    headline = best_headline.value if best_headline else None
    if best_headline:
        record_prov("headline", best_headline)

    # --- years_experience ---
    yoe_candidates = [r.years_experience for r in group if r.years_experience]
    best_yoe = _pick_best(yoe_candidates)
    years_experience = best_yoe.value if best_yoe else None
    if best_yoe:
        record_prov("years_experience", best_yoe)

    # --- skills (union across sources, with confidence boosted by corroboration) ---
    all_skills = [s for r in group for s in r.skills]
    best_skills, skill_sources = _dedupe_list(all_skills, lambda v: v)
    skills = []
    for k in sorted(best_skills.keys(), key=lambda k: (-len(skill_sources[k]), -_score(best_skills[k]))):
        pv = best_skills[k]
        corroboration = len(skill_sources[k])
        conf = min(0.99, _score(pv) + 0.1 * (corroboration - 1))
        skills.append({"name": k, "confidence": round(conf, 2), "sources": sorted(skill_sources[k])})
        record_prov("skills", pv)

    # --- experience (union, naive de-dup by company+title) ---
    all_exp = [e for r in group for e in r.experience]
    exp_best, exp_sources = _dedupe_list(
        all_exp, lambda v: ((v.get("company") or "").lower(), (v.get("title") or "").lower())
    )
    experience = []
    for k in sorted(exp_best.keys(), key=lambda k: -_score(exp_best[k])):
        pv = exp_best[k]
        experience.append(dict(pv.value))
        record_prov("experience", pv)

    # --- education (union, naive de-dup by institution) ---
    all_edu = [e for r in group for e in r.education]
    edu_best, edu_sources = _dedupe_list(all_edu, lambda v: (v.get("institution") or "").lower())
    education = []
    for k in sorted(edu_best.keys(), key=lambda k: -_score(edu_best[k])):
        pv = edu_best[k]
        education.append(dict(pv.value))
        record_prov("education", pv)

    # --- overall confidence: weighted avg of all field scores that exist ---
    all_scored = (
        ([best_name] if best_name else []) + list(best_emails.values()) +
        list(best_phones.values()) + ([best_loc] if best_loc else []) +
        ([best_headline] if best_headline else []) + ([best_yoe] if best_yoe else []) +
        list(best_skills.values()) + list(exp_best.values()) + list(edu_best.values())
    )
    overall_confidence = round(sum(_score(p) for p in all_scored) / len(all_scored), 2) if all_scored else 0.0

    candidate_id = "cand_" + hashlib.sha1(candidate_id_seed.encode()).hexdigest()[:10]

    profile = {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "emails": emails,
        "phones": phones,
        "location": location or {"city": None, "region": None, "country": None},
        "links": links,
        "headline": headline,
        "years_experience": years_experience,
        "skills": skills,
        "experience": experience,
        "education": education,
        "provenance": provenance,
        "overall_confidence": overall_confidence,
    }
    return profile
