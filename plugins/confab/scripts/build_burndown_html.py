#!/usr/bin/env python3
"""Renders confab's ledger.json pass history as a self-contained HTML
burndown chart -- separate from status_dashboard.py's existing
findings-dashboard.html (a current-snapshot staleness/next-action view),
purely additive alongside it.

ledger.json's "passes" array (appended once per pass by lib.ledger.record_pass)
is the only place pass-over-pass history actually exists; "findings" only
carries each finding's CURRENT status, not when it was opened. So the chart
built here is: closed / fixOrDraftOutcomes per pass (exact, from "passes"),
a cumulative-closed line derived from it, and a findings-by-status /
findings-by-domain snapshot from "findings" as of now. It does not claim a
"still open at pass N" curve, because that data was never persisted -- see
lib/ledger.py's record_pass and upsert_finding for the exact fields kept.

Usage:
    build_burndown_html.py <repo_root> --template <path> --d3 <path> --tokens <path> [--out <path>]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.ledger import load_ledger  # noqa: E402
from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402


def build_burndown(repo_root):
    ledger = load_ledger(repo_root)
    passes = ledger.get("passes", [])

    cumulative = 0
    pass_series = []
    for p in passes:
        cumulative += p.get("closed", 0)
        pass_series.append({
            "passNumber": p["passNumber"],
            "domain": p.get("domain"),
            "closed": p.get("closed", 0),
            "fixOrDraftOutcomes": p.get("fixOrDraftOutcomes", 0),
            "cumulativeClosed": cumulative,
        })

    findings = ledger.get("findings", {})
    by_status = {"open": 0, "closed": 0, "escalated": 0}
    by_domain = {}
    finding_list = []
    for finding_id, f in findings.items():
        status = f.get("status", "open")
        if status in by_status:
            by_status[status] += 1
        domain = f.get("domain", "(unknown)")
        by_domain[domain] = by_domain.get(domain, 0) + 1
        finding_list.append({
            "id": finding_id,
            "status": status,
            "domain": domain,
            "category": f.get("category"),
            "severity": f.get("severity"),
            "evidence": f.get("evidence"),
            "reopenCount": f.get("reopenCount", 0),
        })

    return {
        "totalPasses": ledger.get("totalPasses", 0),
        "totalFindingsEver": len(findings),
        "findings": finding_list,
        "passes": pass_series,
        "byStatus": by_status,
        "byDomain": by_domain,
    }


def render_html(template_path, d3_path, tokens_path, burndown):
    tpl = open(template_path, encoding="utf-8").read()

    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(d3_marker, open(d3_path, encoding="utf-8").read())

    tokens_marker = "/*__TOKENS__*/"
    if tokens_marker not in tpl:
        raise ValueError(f"tokens injection marker not found in {template_path}")
    tpl = tpl.replace(tokens_marker, open(tokens_path, encoding="utf-8").read())

    data_marker = "/*__BURNDOWN_DATA__*/ null"
    if data_marker not in tpl:
        raise ValueError(f"injection marker not found in {template_path}")
    data = json.dumps(burndown)
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(data_marker, "/*__BURNDOWN_DATA__*/ " + data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored tokens.css snippet")
    parser.add_argument("--out", help="defaults to analysis/confab/reports/BURNDOWN.html")
    args = parser.parse_args(argv)

    burndown = build_burndown(args.repo_root)

    out_path = args.out or safe_output_path(args.repo_root, "reports/BURNDOWN.html")
    ensure_parent_dir(out_path)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(args.template, args.d3, args.tokens, burndown))

    print(json.dumps({"burndownPath": out_path, "totalPasses": burndown["totalPasses"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
