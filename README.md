# Multi-Source Candidate Data Transformer

Turns messy candidate data from multiple sources into one clean, canonical,
traceable profile per candidate.

## Sources implemented

- **Structured**: Recruiter CSV export, ATS JSON blob (different field names, remapped at extraction)
- **Unstructured**: Resume files (PDF/DOCX, regex+heuristic extraction), Recruiter notes (.txt, free text)

## How to run

```bash
pip install -r requirements.txt

# Default schema, all sample sources, prints JSON to stdout
python3 cli.py --inputs samples/recruiter.csv samples/ats.json samples/resume_priya.docx samples/notes_anjali.txt

# Write to a file
python3 cli.py --inputs samples/recruiter.csv samples/ats.json --out outputs/default_output.json

# Custom projection config (subset/rename/normalize fields)
python3 cli.py --inputs samples/recruiter.csv samples/ats.json samples/resume_priya.docx samples/notes_anjali.txt \
  --config configs/custom_config.json --out outputs/custom_output.json

# Run tests
python3 -m unittest discover -s tests -v
```

`--inputs` accepts any mix of `.csv`, `.json`, `.pdf`, `.docx`, `.txt` files; source
type is auto-detected by extension. Missing/garbage files are skipped (reported as
warnings on stderr), never crash the run.

## Pipeline

`detect → extract → normalize → match/merge → confidence → project → validate`

1. **Detect** — file extension picks the extractor (`pipeline/run.py`).
2. **Extract** — each source has its own extractor (`extract_csv.py`,
   `extract_ats_json.py`, `extract_resume.py`, `extract_notes.py`) that pulls out
   candidate fields as `ProvenancedValue`s (value + source + method + confidence).
   Structured sources get higher base confidence than free-text ones.
3. **Normalize** — `pipeline/normalize.py`: phones → E.164 (best-effort,
   defaults to India when no country code given, never guesses if it can't),
   dates → `YYYY-MM` (or the `"present"` sentinel), skills → a small canonical
   alias map, country → ISO-3166 alpha-2 (left null rather than guessed if unknown).
4. **Match/Merge** — `pipeline/match.py` groups records from different sources
   into the same candidate via union-find over shared keys: exact email match,
   then exact phone match, then exact lowercased name match (weakest, used only
   when no stronger signal exists). `pipeline/merge.py` then reconciles fields:
   scalar fields take the highest `(source_trust × extraction_confidence)`
   value; list fields (emails, phones, skills) are de-duplicated and union'd,
   with skills' confidence boosted when multiple sources corroborate the same skill.
5. **Confidence** — every field carries provenance; `overall_confidence` is the
   mean of the merged scores. Source trust order: ATS JSON > CSV > resume > notes.
6. **Project** — `pipeline/project.py` reshapes the canonical record per a
   runtime JSON config: select a field subset, rename/remap via a `from` path
   (e.g. `emails[0]`, `skills[].name`), toggle provenance/confidence,
   and choose `on_missing: null | omit | error`. The internal canonical record
   is never mutated by this step.
7. **Validate** — `pipeline/validate.py` checks the projected output against
   the field types declared in the same config before returning it.

## Canonical schema

See `configs/custom_config.json` for a config example, and `pipeline/project.py`
`DEFAULT_CONFIG` for the full default schema (matches the assignment's table:
`candidate_id, full_name, emails, phones, location, links, headline,
years_experience, skills, experience, education, provenance, overall_confidence`).

## Edge cases handled

- Missing/empty/malformed source files (CSV, JSON) → skipped with a warning, not a crash.
- Fully blank CSV rows → skipped rather than emitted as an empty candidate.
- Unparseable phone/email → left out (with an extraction-time note), never invented.
- Same person across sources with conflicting values (e.g. CSV says "current
  company: Acme", ATS gives full work history) → merged with the
  higher-trust/higher-confidence value winning per field, not silently overwritten.
- Required field missing in a custom projection → configurable behavior
  (`null`/`omit`/`error`) rather than one hardcoded choice.
- Unknown country names → left `null` instead of guessing an ISO code.

## What's deliberately left out / descoped

- LinkedIn/GitHub live API fetching (we only parse links if present in
  resumes/CSV; no live network calls in this environment).
- A learned/fuzzy name-matching model for identity resolution — we use exact
  email > exact phone > exact lowercased name, which is deterministic and
  explainable but will under-merge near-duplicate names with no shared
  email/phone (flagged in the design doc as a known gap).
- A full resume parser (e.g. layout-aware section detection) — current
  extraction is regex/heuristic-based, sufficient for the sample resumes but
  not a production-grade resume parser.
- A real skills taxonomy/ontology — `normalize.py` ships a small illustrative
  alias map; a production system would back this with a maintained taxonomy.

## Files

```
cli.py                 # CLI entrypoint
pipeline/
  models.py             # RawRecord / ProvenancedValue dataclasses
  normalize.py           # phone/date/skill/country/email normalization
  extract_csv.py          # structured: recruiter CSV
  extract_ats_json.py     # structured: ATS JSON (remapped field names)
  extract_resume.py        # unstructured: resume PDF/DOCX
  extract_notes.py          # unstructured: recruiter notes .txt
  match.py                   # identity resolution (union-find)
  merge.py                    # conflict resolution + confidence + provenance
  project.py                   # config-driven output projection
  validate.py                   # schema validation of projected output
  run.py                         # orchestrates the full pipeline
samples/                # sample inputs incl. garbage/edge-case files
configs/custom_config.json  # example runtime config from the assignment
tests/test_pipeline.py  # unit tests
outputs/                # example generated outputs (default + custom config)
```
