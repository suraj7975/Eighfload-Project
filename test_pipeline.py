import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.normalize import normalize_phone, normalize_date_to_yyyymm, canonicalize_skill, normalize_email
from pipeline.extract_csv import extract_csv
from pipeline.extract_ats_json import extract_ats_json
from pipeline.run import run_pipeline
from pipeline.project import DEFAULT_CONFIG, project, MissingRequiredFieldError

SAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")


class TestNormalize(unittest.TestCase):
    def test_phone_local_india(self):
        v, ok = normalize_phone("98765 43210")
        self.assertTrue(ok)
        self.assertEqual(v, "+919876543210")

    def test_phone_already_e164(self):
        v, ok = normalize_phone("+91 9876543210")
        self.assertTrue(ok)
        self.assertEqual(v, "+919876543210")

    def test_phone_garbage(self):
        v, ok = normalize_phone("call me maybe")
        self.assertFalse(ok)
        self.assertIsNone(v)

    def test_date_month_year(self):
        v, ok = normalize_date_to_yyyymm("Jun 2019")
        self.assertTrue(ok)
        self.assertEqual(v, "2019-06")

    def test_date_present(self):
        v, ok = normalize_date_to_yyyymm("Present")
        self.assertEqual(v, "present")

    def test_date_garbage(self):
        v, ok = normalize_date_to_yyyymm("a long time ago")
        self.assertFalse(ok)

    def test_skill_alias(self):
        self.assertEqual(canonicalize_skill("js"), "JavaScript")
        self.assertEqual(canonicalize_skill("Python"), "Python")

    def test_email_extracts_from_noise(self):
        v, ok = normalize_email("contact me at Foo.Bar@Example.com please")
        self.assertTrue(ok)
        self.assertEqual(v, "foo.bar@example.com")


class TestExtractRobustness(unittest.TestCase):
    def test_csv_missing_file_returns_empty(self):
        self.assertEqual(extract_csv("/nonexistent/path.csv"), [])

    def test_ats_json_garbage_returns_empty(self):
        garbage_path = os.path.join(SAMPLES, "garbage_ats.json")
        self.assertEqual(extract_ats_json(garbage_path), [])

    def test_csv_blank_rows_skipped(self):
        recs = extract_csv(os.path.join(SAMPLES, "recruiter.csv"))
        # 2 good rows + 1 garbage-but-named row; the fully-blank row is skipped
        names = [r.full_name.value for r in recs if r.full_name]
        self.assertIn("Priya Sharma", names)
        self.assertIn("Rohit Mehta", names)


class TestMergeAndPipeline(unittest.TestCase):
    def test_cross_source_merge_by_email(self):
        result = run_pipeline([
            os.path.join(SAMPLES, "recruiter.csv"),
            os.path.join(SAMPLES, "ats.json"),
            os.path.join(SAMPLES, "resume_priya.docx"),
        ])
        priya = next(p for p in result["profiles"] if p["full_name"] == "Priya Sharma")
        # email present from csv+ats+resume should collapse into one profile
        self.assertEqual(len(priya["emails"]), 1)
        # experience merged from both csv (current co) and ats (full history)
        companies = {e["company"] for e in priya["experience"]}
        self.assertIn("Acme Corp", companies)
        self.assertIn("Beta Labs", companies)
        # links only available from resume
        self.assertTrue(priya["links"]["linkedin"])

    def test_garbage_source_does_not_crash_run(self):
        result = run_pipeline([
            os.path.join(SAMPLES, "garbage_ats.json"),
            os.path.join(SAMPLES, "garbage.csv"),
            "/totally/missing/file.pdf",
        ])
        self.assertEqual(result["profiles"], [])
        self.assertTrue(len(result["skipped_inputs"]) >= 1)

    def test_unrecognized_extension_is_skipped_not_crashed(self):
        result = run_pipeline([os.path.join(SAMPLES, "recruiter.csv"), "/etc/hostname.xyz"])
        reasons = [r for _, r in result["skipped_inputs"]]
        self.assertTrue(any("unrecognized" in r for r in reasons))


class TestProjection(unittest.TestCase):
    def test_required_missing_errors_when_configured(self):
        profile = {"candidate_id": "x", "full_name": None, "emails": []}
        config = {
            "fields": [{"path": "full_name", "from": "full_name", "type": "string", "required": True}],
            "on_missing": "error",
            "include_confidence": False,
            "include_provenance": False,
        }
        with self.assertRaises(MissingRequiredFieldError):
            project(profile, config)

    def test_omit_drops_missing_optional_fields(self):
        profile = {"candidate_id": "x", "full_name": "A", "headline": None}
        config = {
            "fields": [
                {"path": "full_name", "from": "full_name", "type": "string", "required": True},
                {"path": "headline", "from": "headline", "type": "string"},
            ],
            "on_missing": "omit",
            "include_confidence": False,
            "include_provenance": False,
        }
        out, warnings = project(profile, config)
        self.assertNotIn("headline", out)
        self.assertEqual(out["full_name"], "A")


if __name__ == "__main__":
    unittest.main()
