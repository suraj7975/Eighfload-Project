#!/usr/bin/env python3
"""CLI for the Multi-Source Candidate Data Transformer.

Usage:
  python cli.py --inputs samples/recruiter.csv samples/ats.json samples/resume.pdf samples/notes.txt
  python cli.py --inputs samples/*.csv samples/*.json --config configs/custom_config.json
  python cli.py --inputs samples/recruiter.csv --out outputs/result.json
"""
import argparse
import json
import sys
from pipeline.run import run_pipeline, load_config


def main():
    ap = argparse.ArgumentParser(description="Multi-Source Candidate Data Transformer")
    ap.add_argument("--inputs", nargs="+", required=True, help="Paths to source files (csv/json/pdf/docx/txt)")
    ap.add_argument("--config", default=None, help="Path to a runtime projection config JSON (default: full schema)")
    ap.add_argument("--out", default=None, help="Write JSON output here instead of stdout")
    ap.add_argument("--pretty", action="store_true", default=True)
    args = ap.parse_args()

    config = load_config(args.config)
    result = run_pipeline(args.inputs, config)

    payload = result["outputs"] if len(result["outputs"]) != 1 else result["outputs"][0]
    text = json.dumps(payload, indent=2, default=str)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {len(result['outputs'])} profile(s) to {args.out}", file=sys.stderr)
    else:
        print(text)

    if result["skipped_inputs"]:
        print("\n--- Skipped inputs ---", file=sys.stderr)
        for path, reason in result["skipped_inputs"]:
            print(f"  {path}: {reason}", file=sys.stderr)

    if result["warnings"]:
        print("\n--- Warnings ---", file=sys.stderr)
        for w in result["warnings"]:
            print(f"  {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
