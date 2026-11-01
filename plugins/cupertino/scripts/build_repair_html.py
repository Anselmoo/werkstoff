#!/usr/bin/env python3
"""Render a cupertino-repair run as assets/repair-viewer.html: the proof that a change is done.

usage: build_repair_html.py [-h] (--run RUN_ID | --report FILE) [--out FILE] [--selftest]

  --run     read .cupertino/repair/<run>/verdict.json and embed its before/after/diff
            screenshots as data URIs; writes .cupertino/repair/<run>/repair-report.html
  --report  a report already in the viewer's shape (the committed demo:
            scripts/fixtures/repair-demo.json)

The page leads with the verdict in words, then the proof (PROVEN / PARTLY PROVEN /
NOT PROVEN, checks, what this does not prove, what waits for a person), then every
change attributed to the approved item that allowed it -- an unattributed change is
listed as a finding, not hidden in a diff -- then before/after per web check.

Rendered through the vendored report kit (scripts/report_kit.py). Exit: 0 written;
1 selftest failed; 2 could not read an input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from report_kit import KitError, render  # noqa: E402

ASSETS = HERE.parent / "assets"
TEMPLATE = ASSETS / "repair-viewer.html"
FIXTURE = HERE / "fixtures" / "repair-demo.json"
PROOF = {"done": "PROVEN", "partial": "PARTLY PROVEN", "regressed": "NOT PROVEN"}
TONE = {"done": "ok", "partial": "warn", "regressed": "bad"}


def _data_uri(path: Path) -> str | None:
    if not path.is_file():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def shape(verdict: dict, rdir: Path | None = None) -> dict:
    """verdict.json -> the viewer's shape. With rdir, screenshots are embedded."""
    v = verdict["verdict"]
    checks = verdict["checks"]
    na = [c for c in checks if c["state"] == "na"]
    findings = []
    for c in verdict.get("outOfScope", []):
        findings.append({"id": "scope-" + c["path"], "severity": "blocker", "rule": "OUT-OF-SCOPE",
                         "claim": f"{c['path']} was {c['change']} but {c['problem']}", "file": c["path"],
                         "fix": "Restore it, or add an item for it, re-show the changeset and approve again.",
                         "tags": {"kind": "scope"}})
    for r in verdict.get("consoleRegressions", []):
        findings.append({"id": "console-" + r["check"], "severity": "major", "rule": "NEW-CONSOLE-ERROR",
                         "claim": f"{r['check']}: console errors went from {r['before']} to {r['after']}",
                         "quote": "\n".join(r["new"]), "tags": {"kind": "console"}})
    for c in checks:
        if c["state"] == "fail":
            sev = "blocker" if c["group"] == "mustPreserve" else "major"
            findings.append({"id": f"{c['group']}-{c['id']}", "severity": sev, "rule": c["group"],
                             "claim": f"{c['criterion']} -- failed", "fix": None,
                             "evidence": [{"label": f"{c['kind']} probe", "detail": c["detail"]}],
                             "tags": {"kind": c["group"]}})
    for iid in verdict.get("itemsWithNoEffect", []):
        findings.append({"id": "noop-" + iid, "severity": "minor", "rule": "NO-EFFECT",
                         "claim": f"approved item {iid} changed no file", "tags": {"kind": "changeset"}})

    shots = []
    if rdir is not None:
        for c in checks:
            if c["kind"] != "web" or not c.get("after"):
                continue
            stem = Path(c["after"]).stem
            shots.append({"label": f"{c['group']} {c['id']}: {c['criterion']}",
                          "before": _data_uri(rdir / "baseline" / (c.get("before") or "")) if c.get("before") else None,
                          "after": _data_uri(rdir / "after" / c["after"]),
                          "diff": _data_uri(rdir / "after" / f"{stem}-diff.png"),
                          "note": c["detail"] + (f" -- pixel difference {c['metrics']['pixelDiffPct']}%"
                                                 if "pixelDiffPct" in c.get("metrics", {}) else "")})
    deleted = [c for c in verdict.get("changes", []) if c["change"] == "removed"]
    needs = ["Read the changes table and confirm each matches what you asked for."]
    if verdict.get("nonGoals"):
        needs.append("Confirm none of the non-goals happened: " + "; ".join(verdict["nonGoals"]))
    if verdict.get("halt"):
        needs.insert(0, "Three rounds ended without `done`: choose restore, or widen the objective.")
    return {
        "runId": verdict["runId"], "round": verdict["round"], "verdict": v,
        "headline": verdict["objective"],
        "glance": {
            "verdict": {"done": "Done", "partial": "Partly done", "regressed": "Regressed"}[v] + " -- "
                       + (verdict["reasons"][0] if verdict["reasons"] else "every check passes and every change is accounted for."),
            "tone": TONE[v],
            "stats": [
                {"label": "Acceptance", "value": f"{verdict['acceptance']['pass']} / {verdict['acceptance']['total']}",
                 "note": "criteria met", "bad": verdict["acceptance"]["pass"] < verdict["acceptance"]["total"]},
                {"label": "Preserved", "value": f"{verdict['mustPreserve']['pass']} / {verdict['mustPreserve']['total']}",
                 "note": "must-not-break checks", "bad": verdict["mustPreserve"]["pass"] < verdict["mustPreserve"]["total"]},
                {"label": "Out of scope", "value": str(len(verdict.get("outOfScope", []))),
                 "note": "changes no item allowed", "bad": bool(verdict.get("outOfScope"))},
                {"label": "Deleted", "value": str(len(deleted)), "note": "restorable from trash/"},
            ],
            "next": {"command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/repair_state.py end" if v == "done"
                     else "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify.py",
                     "why": "Close the run." if v == "done" else "Re-verify after the next approved change."},
        },
        "proof": {"verdict": PROOF[v], "headline": f"Round {verdict['round']}.",
                  "checks": [{"label": f"{c['group']} {c['id']}: {c['criterion']}", "state": c["state"], "detail": c["detail"]} for c in checks],
                  "notProven": [f"{c['criterion']} -- {c['detail']}" for c in na]
                  + (["Rendering in browsers other than Chromium."] if any(c["kind"] == "web" for c in checks) else []),
                  "needsPerson": needs},
        "findings": findings,
        "changes": [{"path": c["path"], "change": c["change"], "items": ", ".join(c["items"]) or "--",
                     "state": "fail" if c.get("problem") else "pass"} for c in verdict.get("changes", [])],
        "changeset": [{"id": i["id"], "op": i["op"], "paths": ", ".join(i["paths"]), "rationale": i.get("rationale", "")}
                      for i in verdict.get("changeset", [])],
        "beforeAfter": shots,
    }


def build_report(root: Path, run_id: str) -> Path:
    rdir = root / ".cupertino" / "repair" / run_id
    report = shape(json.loads((rdir / "verdict.json").read_text(encoding="utf-8")), rdir)
    out = rdir / "repair-report.html"
    out.write_text(render(TEMPLATE.read_text(encoding="utf-8"), ASSETS, report), encoding="utf-8")
    return out


def selftest() -> int:
    fails: list[str] = []

    def ok(name: str, cond: bool, extra: str = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + extra}")
        if not cond:
            fails.append(name)

    demo = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else None
    ok("committed demo fixture exists", demo is not None, str(FIXTURE))
    if demo is None:
        print("\nSELFTEST FAILED")
        return 1
    html = render(TEMPLATE.read_text(encoding="utf-8"), ASSETS, demo)
    ok("kit and tokens inlined", "<!--__REPORT_KIT__-->" not in html and "const RK" in html and "--bg" in html)
    ok("data island filled", "@@DATA@@" not in html and '"verdict"' in html)
    ok("static title and h1 agree", "<title>cupertino — repair report</title>" in html
       and "<h1>cupertino — repair report</h1>" in html)
    ok("CSP is default-src 'none'", "default-src 'none'" in html)
    ok("static verdict and legend exist", 'class="verdict' in html and 'class="legend' in html)
    ok("no innerHTML", "innerHTML" not in TEMPLATE.read_text(encoding="utf-8"))
    ok("demo shows the failure the route exists for (an out-of-scope change)",
       any(f.get("rule") == "OUT-OF-SCOPE" for f in demo["findings"]))
    ok("demo shows a delete", any(c["change"] == "removed" for c in demo["changes"]))
    ok("demo carries a before/after image", bool(demo["beforeAfter"]) and demo["beforeAfter"][0].get("before"))
    sample = {"runId": "r", "round": 3, "verdict": "regressed", "halt": True, "reasons": ["a mustPreserve check fails"],
              "objective": "the KPI row fits at 390 px", "nonGoals": ["no redesign"],
              "acceptance": {"pass": 1, "total": 1}, "mustPreserve": {"pass": 0, "total": 1},
              "checks": [{"group": "mustPreserve", "id": "P1", "criterion": "dark mode", "kind": "web", "state": "fail",
                          "detail": "pixel difference 9%", "metrics": {}, "after": "x.png"},
                         {"group": "acceptance", "id": "A1", "criterion": "fits", "kind": "command", "state": "na",
                          "detail": "not run: x", "metrics": {}}],
              "consoleRegressions": [], "changes": [{"path": "a.css", "change": "modified", "items": []}],
              "outOfScope": [{"path": "a.css", "change": "modified", "items": [], "problem": "no approved item names this change"}],
              "itemsWithNoEffect": ["I2"], "changeset": [{"id": "I2", "op": "modify", "paths": ["b.css"], "rationale": "r"}]}
    s = shape(sample)
    ok("regressed maps to NOT PROVEN", s["proof"]["verdict"] == "NOT PROVEN")
    ok("an out-of-scope change becomes a blocker finding", any(f["rule"] == "OUT-OF-SCOPE" and f["severity"] == "blocker" for f in s["findings"]))
    ok("a failing preserve check becomes a blocker finding", any(f["rule"] == "mustPreserve" and f["severity"] == "blocker" for f in s["findings"]))
    ok("a not-run check is listed under what is not proven", any("not run" in t for t in s["proof"]["notProven"]))
    ok("halt asks a person first", s["proof"]["needsPerson"][0].startswith("Three rounds"))
    ok("a no-op item is reported", any(f["rule"] == "NO-EFFECT" for f in s["findings"]))
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("selftest passed")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="build_repair_html.py", description="Render a cupertino-repair run.",
                                     epilog="exit 0 written, 1 selftest failed, 2 could not read an input")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--run")
    src.add_argument("--report")
    parser.add_argument("--out")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        if args.run:
            from repair_lib import project_root
            out = build_report(project_root(), args.run)
        elif args.report:
            report = json.loads(Path(args.report).read_text(encoding="utf-8"))
            out = Path(args.out) if args.out else TEMPLATE.with_name("repair-report.html")
            out.write_text(render(TEMPLATE.read_text(encoding="utf-8"), ASSETS, report), encoding="utf-8")
        else:
            parser.error("one of --run or --report is required unless --selftest is given")
    except (OSError, ValueError, KeyError, KitError) as err:
        print(f"build_repair_html: {err}", file=sys.stderr)
        return 2
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
