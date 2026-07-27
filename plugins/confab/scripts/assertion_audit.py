#!/usr/bin/env python3
"""confab-assertion-audit writer/validator.

The actual mutation reasoning (proposing plausible mutations, judging
whether tests would catch them) is done by the assertion-auditor agent —
that is inherently a judgment task, not something a stdlib script should
attempt. This script is the enforcement layer around that judgment:

  * rule assertion-audit-verification-mandatory: there is NO
    --skip-verification flag anywhere in this CLI. The capability to skip
    does not exist in code, so it cannot be exercised by a setting.
    --verify-json is a REQUIRED argument; argparse itself refuses to run
    without it.
  * rule assertion-fixability-always-advisory: enforced by
    lib.schema.validate_finding (domain="assertion_audit"), plus this
    script forces every finding's fixability to "advisory" defensively
    even though the validator would already reject anything else — belt
    and suspenders on a rule that must never regress.
  * rule tool-source-labeling: every finding must carry toolSource, and
    the Markdown report renders real-tool and llm-reasoned findings in
    two clearly separated sections — never one blended table.

Usage:
    python3 assertion_audit.py <repo_root> --find-json <path> --verify-json <path>
        [--requested-tool <name>]

--find-json: JSON {"findings": [...]} from the Find-phase agent dispatch.
--verify-json: JSON {"findings": [...]} from the mandatory Verify-phase
    agent dispatch (a second, independent assertion-auditor invocation in
    Verify mode). Only findings present in verify-json's confirmed list
    are written to the report; the Find-phase list alone is never enough.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.constants import TOOL_SOURCE_LLM, VALID_TOOL_SOURCES  # noqa: E402
from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402
from lib.schema import InvalidFindingError, validate_finding  # noqa: E402

DOMAIN = "assertion_audit"


def load_findings(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw.get("findings", raw) if isinstance(raw, dict) else raw


def reconcile(find_findings: list, verify_findings: list) -> list:
    """A finding only survives into the report if the mandatory Verify
    phase confirmed it. Verify-phase findings are matched to Find-phase
    findings by evidence (file:line); a verify finding with no matching
    Find-phase evidence is dropped as spurious rather than silently kept.
    """
    verified_evidence = {f.get("evidence") for f in verify_findings if f.get("confirmed", True)}
    survivors = [f for f in find_findings if f.get("evidence") in verified_evidence]
    return survivors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--find-json", required=True)
    parser.add_argument("--verify-json", required=True)  # no default -> cannot be omitted
    parser.add_argument("--requested-tool", default=None)
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)

    find_findings = load_findings(args.find_json)
    verify_findings = load_findings(args.verify_json)
    survivors = reconcile(find_findings, verify_findings)

    clean_findings = []
    for f in survivors:
        f = dict(f)
        f["fixability"] = "advisory"  # rule: assertion-fixability-always-advisory
        if "toolSource" not in f:
            print(f"WARNING: dropping finding missing toolSource: {f}", file=sys.stderr)
            continue
        if f["toolSource"] not in VALID_TOOL_SOURCES:
            print(f"WARNING: dropping finding with invalid toolSource={f['toolSource']!r}", file=sys.stderr)
            continue
        if args.requested_tool and f["toolSource"] == TOOL_SOURCE_LLM and not f.get("fallbackReason"):
            print(
                f"WARNING: dropping finding: requested-tool={args.requested_tool!r} was named but "
                f"finding fell back to llm-reasoned without an explicit fallbackReason: {f}",
                file=sys.stderr,
            )
            continue
        try:
            validate_finding(f, domain=DOMAIN)
        except InvalidFindingError as exc:
            print(f"WARNING: dropping invalid finding: {exc}", file=sys.stderr)
            continue
        clean_findings.append(f)

    summary = {
        "domain": DOMAIN,
        "verificationRan": True,  # structurally always true: --verify-json is required
        "requestedTool": args.requested_tool,
        "findings": clean_findings,
    }

    summary_path = safe_output_path(repo_root, "assertion_audit_summary.json")
    ensure_parent_dir(summary_path)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)

    real_tool_findings = [f for f in clean_findings if f["toolSource"] == "real-tool"]
    llm_findings = [f for f in clean_findings if f["toolSource"] == "llm-reasoned"]

    lines = ["# confab Assertion Audit", "", "Verification phase: mandatory, always ran.", ""]
    if args.requested_tool:
        lines.append(f"Requested mutation tool: `{args.requested_tool}`")
        lines.append("")

    def render_table(findings, heading):
        out = [f"## {heading}", ""]
        if not findings:
            out.append("_none_")
            out.append("")
            return out
        out += ["| Severity | Title | Evidence | Fixability |", "|---|---|---|---|"]
        for f in findings:
            out.append(f"| {f['severity']} | {f['title']} | {f['evidence']} | {f['fixability']} |")
        out.append("")
        return out

    # rule tool-source-labeling: two sections, never one blended table.
    lines += render_table(real_tool_findings, "Findings from real mutation tool (real-tool)")
    lines += render_table(llm_findings, "Findings from LLM-reasoned mutation analysis (llm-reasoned)")

    report_path = safe_output_path(repo_root, "reports/ASSERTION_AUDIT.md")
    ensure_parent_dir(report_path)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(json.dumps({"summary_path": summary_path, "report_path": report_path, "findingCount": len(clean_findings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
