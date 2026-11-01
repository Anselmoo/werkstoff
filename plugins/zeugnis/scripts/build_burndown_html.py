#!/usr/bin/env python3
"""Renders zeugnis's ledger.json pass history as a self-contained HTML
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

When zeugnis-mutation-harden has written analysis/zeugnis/mutation_harden_summary.json,
a third tab shows its per-module mutation score before and after; see
build_mutation.

Usage:
    build_burndown_html.py <repo_root> --template <path> --d3 <path> --tokens <path> [--out <path>]
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.ledger import load_ledger  # noqa: E402
from lib.paths import ensure_parent_dir, safe_output_path  # noqa: E402
from report_kit import render  # noqa: E402


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
        "mutation": build_mutation(repo_root),
    }


def build_mutation(repo_root):
    """The Mutation tab's data, from zeugnis-mutation-harden's summary (issue
    #142), or None when no mutation run has been reported -- the tab is then
    not shown at all, so a ledger-only report renders exactly as before.

    What the tab draws is copied whole: per-module counts and scores before
    and after (including the score without equivalents), each shard's sources,
    tests, exclusions and baseline state, every kill with the test and the proof
    file that justify it, every still-alive mutant with its location, category
    and fixability, the equivalents with their reasons and basis, and the
    rejected claims. A summary
    that exists but cannot be read is not silently treated as "no run": it
    becomes {"error": ...} and the tab says so (report-viewer-standard S4).
    """
    path = safe_output_path(repo_root, "mutation_harden_summary.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            summary = json.load(fh)
        keep = ("killed", "survived", "noTests", "notChecked", "timeout", "suspicious", "skipped", "segfault",
                "caughtByTypeCheck", "interrupted", "score", "equivalent", "scoreExcludingEquivalent")
        return {
            "runId": summary["runId"],
            "tool": summary.get("tool"),
            "complete": bool(summary["complete"]),
            "generatedAt": summary.get("generatedAt"),
            "shards": [{"shard": s["shard"], "baselineComplete": s["baselineComplete"],
                        "baselineState": s.get("baselineState"),
                        "remeasureComplete": s.get("remeasureComplete"),
                        "sources": s.get("sources", []), "tests": s.get("tests", []),
                        "exclusions": [{"glob": x.get("glob"), "reason": x.get("reason")} for x in s.get("exclusions", [])]}
                       for s in summary["shards"]],
            "modules": [{"module": m["module"],
                         "before": {k: m["before"].get(k) for k in keep if k in m["before"]},
                         "after": {k: m["after"].get(k) for k in keep if k in m["after"]},
                         "unreached": m.get("unreached", 0)} for m in summary["modules"]],
            # A module row opens to these: what the proven tests killed, and
            # what the tool still reports alive.
            "kills": [{"mutantId": k["mutantId"], "module": k["module"], "test": k.get("test"), "proof": k.get("proof")}
                      for k in summary.get("kills", [])],
            "alive": [{"mutantId": f["mutantId"], "module": f.get("module") or f["evidence"].split(":")[0],
                       "evidence": f["evidence"], "category": f.get("category"), "state": f.get("state"),
                       "severity": f.get("severity"), "fixability": f.get("fixability")}
                      for f in summary.get("findings", [])],
            "equivalents": [{"mutantId": e["mutantId"], "module": e["module"], "reason": e["reason"],
                             "basis": e.get("basis")}
                            for e in summary.get("equivalents", [])],
            "rejected": [{"mutantId": r["mutantId"], "state": r["state"], "reason": r.get("reason", "")}
                         for r in summary.get("rejected", [])],
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"error": f"analysis/zeugnis/mutation_harden_summary.json is unreadable ({type(exc).__name__}: {exc})"}


def render_html(template_path, d3_path, tokens_path, burndown):
    template_path = Path(template_path)
    tpl = template_path.read_text(encoding="utf-8")
    d3_marker = "<!--__D3_SUBSET__-->"
    if d3_marker not in tpl:
        raise ValueError(f"D3 injection marker not found in {template_path}")
    tpl = tpl.replace(d3_marker, Path(d3_path).read_text(encoding="utf-8"))
    # report_kit.render() inlines the design tokens and the report kit, and
    # puts the data in a JSON island with < > & escaped (S3's first barrier;
    # the template's textContent-only DOM is the second).
    return render(tpl, template_path.parent, burndown, tokens=Path(tokens_path))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--template", required=True)
    parser.add_argument("--d3", required=True, help="path to the vendored inline-d3.html snippet")
    parser.add_argument("--tokens", required=True, help="path to the vendored tokens.css snippet")
    parser.add_argument("--out", help="defaults to analysis/zeugnis/reports/BURNDOWN.html")
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
