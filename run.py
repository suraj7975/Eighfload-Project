"""End-to-end orchestration."""
import os
import json
from pipeline.extract_csv import extract_csv
from pipeline.extract_ats_json import extract_ats_json
from pipeline.extract_resume import extract_resume
from pipeline.extract_notes import extract_notes
from pipeline.match import group_records
from pipeline.merge import merge_group
from pipeline.project import project, DEFAULT_CONFIG
from pipeline.validate import validate

_EXTENSION_DETECTORS = {
    ".csv": ("csv", extract_csv),
    ".json": ("ats_json", extract_ats_json),
    ".pdf": ("resume", extract_resume),
    ".docx": ("resume", extract_resume),
    ".txt": ("notes", extract_notes),
}


def detect_and_extract(paths):
    """Step: detect source type by extension/content, then extract.
    A missing or unreadable file degrades to zero records rather than
    crashing the run (extractors already swallow their own errors)."""
    all_records = []
    skipped = []
    for path in paths:
        ext = os.path.splitext(path)[1].lower()
        entry = _EXTENSION_DETECTORS.get(ext)
        if not entry:
            skipped.append((path, "unrecognized file type"))
            continue
        if not os.path.exists(path):
            skipped.append((path, "file not found"))
            continue
        _, extractor = entry
        try:
            recs = extractor(path)
        except Exception as e:
            skipped.append((path, f"extractor error: {e}"))
            recs = []
        all_records.extend(recs)
    return all_records, skipped


def run_pipeline(paths, config=None):
    """Runs the full pipeline over a list of input file paths.
    Returns dict with: profiles (raw canonical), outputs (projected,
    validated), warnings, skipped_inputs."""
    config = config or DEFAULT_CONFIG
    records, skipped = detect_and_extract(paths)

    groups = group_records(records)

    profiles = []
    for i, group in enumerate(groups):
        seed = group[0].candidate_key or f"group-{i}"
        profile = merge_group(group, candidate_id_seed=seed)
        profiles.append(profile)

    outputs = []
    all_warnings = []
    for profile in profiles:
        out, warnings = project(profile, config)
        errors = validate(out, config)
        all_warnings.extend(f"[{profile['candidate_id']}] {w}" for w in warnings)
        all_warnings.extend(f"[{profile['candidate_id']}] VALIDATION: {e}" for e in errors)
        outputs.append(out)

    return {
        "profiles": profiles,
        "outputs": outputs,
        "warnings": all_warnings,
        "skipped_inputs": skipped,
    }


def load_config(path):
    if not path:
        return DEFAULT_CONFIG
    with open(path, encoding="utf-8") as f:
        return json.load(f)
