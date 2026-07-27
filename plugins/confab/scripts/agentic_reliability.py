#!/usr/bin/env python3
"""confab-agentic-reliability writer/validator.

Finding generation is the agentic-reliability-auditor agent's job (Read,
Glob, Grep only — it cannot write or modify files, enforced structurally
by its tool grant in agents/agentic-reliability-auditor.md). This script
enforces:

  * rule agentic-reliability-four-categories: lib.schema.validate_finding
    rejects any category outside AGENTIC_RELIABILITY_CATEGORIES for this
    domain.
  * rule agentic-reliability-verification-default-on: same
    required-unless-explicit-flag pattern as contract_drift.py.
  * only excessive-tool-grant findings may carry fixability="fixable";
    validate_finding already rejects any other category claiming fixable.
  * trivial-scope exceptions (a Bash-tool grant on a two-line utility
    skill, say) are written to a separate section of the report rather
    than folded into the findings table, so they never inflate the
    finding count.

Usage:
    python3 agentic_reliability.py <repo_root> --find-json <path>
        [--verify-json <path>] [--skip-verification]
        [--trivial-exceptions-json <path>]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import AGENTIC_RELIABILITY_CATEGORIES  # noqa: E402
from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402
from lib.schema import InvalidFindingError, validate_finding  # noqa: E402

DOMAIN = "agentic_reliability"


def load_json_list(path):
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw.get("findings", raw) if isinstance(raw, dict) else raw


def reconcile(find_findings, verify_findings):
    if verify_findings is None:
        return find_findings
    verified_evidence = {f.get("evidence") for f in verify_findings if f.get("confirmed", True)}
    return [f for f in find_findings if f.get("evidence") in verified_evidence]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--find-json", required=True)
    parser.add_argument("--verify-json", default=None)
    parser.add_argument("--skip-verification", action="store_true")
    parser.add_argument("--trivial-exceptions-json", default=None)
    args = parser.parse_args()

    if not args.skip_verification and not args.verify_json:
        parser.error(
            "--verify-json is required unless --skip-verification is explicitly passed "
            "(rule: agentic-reliability-verification-default-on)"
        )

    repo_root = os.path.abspath(args.repo_root)
    find_findings = load_json_list(args.find_json) or []
    verify_findings = load_json_list(args.verify_json)
    survivors = reconcile(find_findings, verify_findings)

    clean_findings = []
    by_category = {c: 0 for c in AGENTIC_RELIABILITY_CATEGORIES}
    for f in survivors:
        f = dict(f)
        try:
            validate_finding(f, domain=DOMAIN)
        except InvalidFindingError as exc:
            print(f"WARNING: dropping invalid finding: {exc}", file=sys.stderr)
            continue
        clean_findings.append(f)
        by_category[f["category"]] += 1

    trivial_exceptions = load_json_list(args.trivial_exceptions_json) or []

    verification_ran = not args.skip_verification

    summary = {
        "domain": DOMAIN,
        "verificationRan": verification_ran,
        "categoryCounts": by_category,
        "findings": clean_findings,
    }

    summary_path = safe_output_path(repo_root, "agentic_reliability_summary.json")
    ensure_parent_dir(summary_path)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)

    lines = ["# confab Agentic Reliability", "", f"Verification phase ran: {verification_ran}", ""]
    for category in AGENTIC_RELIABILITY_CATEGORIES:
        cat_findings = [f for f in clean_findings if f["category"] == category]
        lines.append(f"## {category} ({len(cat_findings)})")
        lines.append("")
        if not cat_findings:
            lines.append("_none_")
            lines.append("")
            continue
        lines += ["| Severity | Title | Evidence | Fixability |", "|---|---|---|---|"]
        for f in cat_findings:
            lines.append(f"| {f['severity']} | {f['title']} | {f['evidence']} | {f['fixability']} |")
        lines.append("")

    lines.append("## Trivial-scope exceptions (documented separately, not counted as findings)")
    lines.append("")
    if not trivial_exceptions:
        lines.append("_none_")
    else:
        lines += ["| Evidence | Reason |", "|---|---|"]
        for exc in trivial_exceptions:
            lines.append(f"| {exc.get('evidence', '?')} | {exc.get('reason', '?')} |")
    lines.append("")

    report_path = safe_output_path(repo_root, "reports/AGENTIC_RELIABILITY.md")
    ensure_parent_dir(report_path)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(json.dumps({"summary_path": summary_path, "report_path": report_path, "findingCount": len(clean_findings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
