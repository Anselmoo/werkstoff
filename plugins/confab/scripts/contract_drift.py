#!/usr/bin/env python3
"""confab-contract-drift writer/validator.

The mismatch analysis itself (comparing a declared type hint / signature /
docstring / schema against actual call-site and handler usage) is done by
the contract-auditor agent in Find and Verify phases. This script is the
enforcement layer:

  * rule contract-drift-verification-default-on: verification runs UNLESS
    --skip-verification is passed as an explicit CLI flag (Python's
    store_true default is False, so simply not passing the flag can never
    accidentally skip verification — there is no ambiguous "empty string
    means yes" path). When the flag is absent, --verify-json is required
    and argparse refuses to run without it.
  * rule shared-finding-schema (checkpoint 2 of 5): every finding is run
    through lib.schema.validate_finding before it can reach the report.
  * confidence-to-severity mapping is enforced here rather than left to
    the agent's prose: High confidence always maps to High severity.

Usage:
    python3 contract_drift.py <repo_root> --find-json <path>
        [--verify-json <path>] [--skip-verification]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402
from lib.schema import InvalidFindingError, validate_finding  # noqa: E402

DOMAIN = "contract_drift"

CONFIDENCE_TO_SEVERITY = {"High": "High", "Medium": "Medium", "Low": "Low"}


def load_findings(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw.get("findings", raw) if isinstance(raw, dict) else raw


def reconcile(find_findings: list, verify_findings) -> list:
    if verify_findings is None:
        return find_findings
    verified_evidence = {f.get("evidence") for f in verify_findings if f.get("confirmed", True)}
    return [f for f in find_findings if f.get("evidence") in verified_evidence]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--find-json", required=True)
    parser.add_argument("--verify-json", default=None)
    parser.add_argument("--skip-verification", action="store_true")  # default False
    args = parser.parse_args()

    if not args.skip_verification and not args.verify_json:
        parser.error(
            "--verify-json is required unless --skip-verification is explicitly passed "
            "(rule: contract-drift-verification-default-on)"
        )

    repo_root = os.path.abspath(args.repo_root)
    find_findings = load_findings(args.find_json)
    verify_findings = load_findings(args.verify_json) if args.verify_json else None
    survivors = reconcile(find_findings, verify_findings)

    clean_findings = []
    for f in survivors:
        f = dict(f)
        if "confidence" in f:
            mapped = CONFIDENCE_TO_SEVERITY.get(f["confidence"])
            if mapped:
                f["severity"] = mapped  # rule: confidence mapped to severity
        if not f.get("declaredLocation") or not f.get("actualUsageLocation"):
            print(f"WARNING: dropping finding missing declared/actual usage location: {f}", file=sys.stderr)
            continue
        try:
            validate_finding(f, domain=DOMAIN)
        except InvalidFindingError as exc:
            print(f"WARNING: dropping invalid finding: {exc}", file=sys.stderr)
            continue
        clean_findings.append(f)

    verification_ran = not args.skip_verification

    summary = {
        "domain": DOMAIN,
        "verificationRan": verification_ran,
        "findings": clean_findings,
    }

    summary_path = safe_output_path(repo_root, "contract_drift_summary.json")
    ensure_parent_dir(summary_path)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)

    lines = [
        "# confab Contract Drift",
        "",
        f"Verification phase ran: {verification_ran}",
        "",
        "| Severity | Title | Declared | Actual Usage | Fixability |",
        "|---|---|---|---|---|",
    ]
    for f in clean_findings:
        lines.append(
            f"| {f['severity']} | {f['title']} | {f['declaredLocation']} | {f['actualUsageLocation']} | {f['fixability']} |"
        )
    lines.append("")

    report_path = safe_output_path(repo_root, "reports/CONTRACT_DRIFT.md")
    ensure_parent_dir(report_path)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(json.dumps({"summary_path": summary_path, "report_path": report_path, "findingCount": len(clean_findings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
