#!/usr/bin/env python3
"""Render assets/design-viewer.html: a workflow design, and the run it became, as a graph.

usage: build_design_html.py (--design FILE [--state FILE] [--workflow FILE] [--preflight FILE]
                             | --workflow FILE | --bundle FILE) [--out FILE]
       build_design_html.py --selftest

A design table answers, per node, WHAT it does, WHERE it runs, WHEN (depends_on, a human
gate between runs) and HOW (kind, model, write scope, command). As a table that is a list
of rows; the thing a reader needs to see -- which rows run side by side, which two of
them may write the same file, where a human gate cuts the run in two, where the last run
stopped -- is a graph. So the page draws one.

WHY A HAND-WRITTEN LAYOUT AND NO LIBRARY. Longest-path layering (a node sits one column
right of its deepest dependency, so an edge never points backwards) is twenty lines, and
it is what plugins/lehre/assets/doctrine-viewer.html's drawDag already does. A design has
tens of nodes, not thousands; a force layout would move them on every render, and the
vendored d3 subset would be the only reason this plugin carried it.

EVERYTHING ON THE PAGE IS COMPUTED HERE, from the inputs, by the code that decides it:
  * rejections -- design_spec.validate_design, the validator compile_spec.py --design runs
  * write-scope overlaps -- land_candidate.scopes_overlap, over CONCURRENT rows only
  * toolchains -- design_spec.toolchains_used; installed or not comes from --preflight
    (arbeitsplan-preflight's results, {toolchain: true|false}). This script never probes
    one itself: a page whose verdict depends on the machine that rendered it is not a
    report. Absent means "not probed", and the page says so
  * node status -- the state helper's `show` output (--state), never guessed: a node the
    state does not record is shown as not recorded, not as done
  * the compiled workflow's rejections -- compile_spec.validate against the live pattern index
  * the verdict sentence itself, so the selftest can hold it to the data

Exit: 0 written, 2 could not read an input.
STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_spec
import design_spec
import land_candidate

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
TEMPLATE = PLUGIN / "assets" / "design-viewer.html"
TOKENS = PLUGIN / "assets" / "tokens.css"
FIXTURE = HERE / "fixtures" / "design-demo.json"
TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
DATA_MARKER = "/*__DESIGN_DATA__*/"
NODE_ERR = re.compile(r"\Anode (\S+): (.*)\Z", re.S)
RULE = re.compile(r"\[(AP-[A-Z0-9-]+)\]")


def render(report: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if TOKENS.is_file():
        tpl = tpl.replace(TOKENS_MARKER, "<style>\n" + TOKENS.read_text(encoding="utf-8")
                          + "\n</style>")
    payload = json.dumps(report, indent=2)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(DATA_MARKER, "const DESIGN = " + payload + ";")


# --- the design ----------------------------------------------------------------------

def _overlaps(design: dict) -> list:
    """Concurrent rows of one wave whose write scopes may meet -- the same test
    the validator applies, kept as pairs so the page can draw them."""
    nodes = {n["id"]: n for n in design.get("nodes") or [] if isinstance(n, dict) and "id" in n}
    anc = {nid: design_spec._ancestors(nid, nodes) for nid in nodes}
    out = []
    waves = sorted({n["wave"] for n in nodes.values() if isinstance(n.get("wave"), int)})
    for w in waves:
        rows = [nid for nid, n in nodes.items() if n.get("wave") == w and n.get("kind") == "agent"]
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a in anc[b] or b in anc[a]:
                    continue
                pairs = land_candidate.scopes_overlap(nodes[a].get("writeScope") or [],
                                                      nodes[b].get("writeScope") or [])
                if pairs:
                    out.append({"wave": w, "a": a, "b": b, "globs": list(pairs[0])})
    return out


def _status(n: dict, state: dict | None) -> str | None:
    """What the state records about one node, or None when it records nothing."""
    if state is None:
        return None
    nid, kind, wave = n["id"], n.get("kind"), n.get("wave")
    waves = state.get("waves") or {}
    wave_done = isinstance(wave, int) and (waves.get(str(wave)) or {}).get("status") == "done"
    if kind == "human-gate":
        return "approved" if (state.get("approvals") or {}).get(nid) else "pending"
    if isinstance((n.get("script") or {}).get("author"), dict):
        return ((state.get("steps") or {}).get(nid) or {}).get("status") or "missing"
    if kind == "merge-gate" and isinstance(wave, int):
        runs = [g for key, g in (state.get("gates") or {}).items()
                if key.split(":", 1)[0] == str(wave) and isinstance(g, dict)]
        if wave_done:
            return "green"
        return "red" if any(g.get("green") is False for g in runs) else "pending"
    if kind == "agent" and isinstance(wave, int):
        return "done" if wave_done or nid in (state.get("builders") or {}) else "pending"
    return None


def collect_design(design: dict, state: dict | None, preflight: dict | None) -> dict:
    errors, warnings = design_spec.validate_design(design)
    by_node: dict = {}
    general = []
    for e in errors:
        m = NODE_ERR.match(e)
        if m:
            by_node.setdefault(m.group(1), []).append(m.group(2))
        else:
            general.append(e)
    nodes = []
    for n in design.get("nodes") or []:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str):
            continue
        sc = n.get("script") if isinstance(n.get("script"), dict) else {}
        author = sc.get("author") if isinstance(sc.get("author"), dict) else None
        nodes.append({
            "id": n["id"], "kind": n.get("kind"), "role": n.get("role"), "goal": n.get("goal"),
            "wave": n.get("wave") if isinstance(n.get("wave"), int) else None,
            "where": n.get("where"), "model": n.get("model"), "effort": n.get("effort"),
            "agentType": n.get("agentType"), "skills": n.get("skills"), "tools": n.get("tools"),
            "depends_on": [d for d in n.get("depends_on") or [] if isinstance(d, str)],
            "writeScope": n.get("writeScope"), "inputs": n.get("inputs"),
            "when": n.get("when"), "swarm": n.get("swarm"),
            "referee": n.get("referee") if isinstance(n.get("referee"), dict) else None,
            "runtime": sc.get("runtime"), "command": sc.get("command"),
            "steps": [st.get("command") for st in (n.get("steps") or n.get("acceptance") or [])
                      if isinstance(st, dict)],
            "authored": ({"model": author.get("model"), "purpose": author.get("purpose"),
                          "sample": author.get("sample")} if author else None),
            "rejections": by_node.get(n["id"], []),
            "status": _status(n, state),
        })
    probes = design_spec.toolchains_used(design)
    tc = [{"name": name, "probe": probe,
           "installed": None if preflight is None else preflight.get(name)}
          for name, probe in sorted(probes.items())]
    red = []
    if state is not None:
        for key, g in sorted((state.get("gates") or {}).items()):
            if isinstance(g, dict) and g.get("green") is False:
                wave = key.split(":", 1)[0]
                gate = next((n["id"] for n in nodes if n["kind"] == "merge-gate"
                             and str(n["wave"]) == wave), key)
                red.append({"gate": gate, "stage": key, "findings": g.get("findings") or []})
    integ = design.get("integration") if isinstance(design.get("integration"), dict) else {}
    return {
        "name": design.get("name"), "runId": design.get("runId"),
        "problemRef": design.get("problemRef"), "sha256": design_spec.design_hash(design),
        "integration": {"branch": integ.get("branch"), "target": integ.get("target")},
        "gates": [g.get("command") for g in design.get("gates") or [] if isinstance(g, dict)],
        "offLimits": design.get("offLimits") or [],
        "nodes": nodes, "rejections": errors, "general": general, "warnings": warnings,
        "overlaps": _overlaps(design), "toolchains": tc,
        "state": None if state is None else {"redGates": red,
                                             "wavesDone": sorted(k for k, v in (
                                                 state.get("waves") or {}).items()
                                                 if (v or {}).get("status") == "done")},
    }


# --- the compiled workflow ------------------------------------------------------------

def collect_workflow(spec: dict) -> dict:
    try:
        accepted, rejected = compile_spec.catalog_patterns(PLUGIN)
        errors, warnings = compile_spec.validate(spec, accepted, rejected)
    except (ValueError, OSError) as exc:
        errors, warnings = [f"could not validate: {exc}"], []
    phases = [p for p in spec.get("phases") or [] if isinstance(p, dict)]
    by_marker = {p.get("marker"): p.get("id") for p in phases if p.get("marker")}
    out = []
    for i, p in enumerate(phases):
        prefix = f"phases[{i}] ({p.get('id')}): "  # compile_spec.validate's own spelling
        out.append({
            "id": p.get("id"), "kind": p.get("kind"), "pattern": p.get("pattern"),
            "modelTier": p.get("modelTier"), "writes": p.get("writes"),
            "agentType": p.get("agentType"), "mode": p.get("mode"),
            "fanOut": p.get("fanOut"),
            "requires": p.get("requires") or [], "marker": p.get("marker"),
            "depends_on": [by_marker[r] for r in p.get("requires") or [] if r in by_marker],
            "command": (p.get("script") or {}).get("command") if isinstance(p.get("script"),
                                                                            dict) else None,
            "rejections": [e[len(prefix):] for e in errors if e.startswith(prefix)],
        })
    budget = spec.get("budget") if isinstance(spec.get("budget"), dict) else {}
    return {"runId": spec.get("runId"), "problem": spec.get("problem"),
            "totalDispatches": budget.get("totalDispatches"), "phases": out,
            "rejections": errors, "warnings": warnings}


# --- the verdict ------------------------------------------------------------------------

def _names(items: list) -> str:
    return ", ".join(items[:-1]) + (" and " if len(items) > 1 else "") + items[-1] \
        if items else ""


def verdict(report: dict) -> str:
    """One paragraph, worst news first. Every clause is a fact the page shows --
    and no count: the tiles carry the numbers, and a number printed twice is a
    number that can disagree with itself (report-viewer standard, R2)."""
    d, wf = report.get("design"), report.get("workflow")
    parts = []
    if d:
        if d["rejections"]:
            ov = d["overlaps"]
            clause = "This design does not validate"
            if ov:
                clause += (f": concurrent rows {ov[0]['a']} and {ov[0]['b']} of wave "
                           f"{ov[0]['wave']} may both write {ov[0]['globs'][1]}, and a merge "
                           "that hopes is not a plan")
            parts.append(clause + ".")
        missing = [t["name"] for t in d["toolchains"] if t["installed"] is False]
        unprobed = [t["name"] for t in d["toolchains"] if t["installed"] is None]
        if missing:
            parts.append(f"{_names(missing)} {'is' if len(missing) == 1 else 'are'} not "
                         "installed here, so a step that needs it cannot run.")
        st = d.get("state")
        if st and st["redGates"]:
            g = st["redGates"][-1]
            srcs = sorted({f.get("source") for f in g["findings"] if f.get("source")})
            parts.append(f"The last run stopped RED at {g['gate']}"
                         + (f" ({', '.join(srcs)} finding)" if srcs else "")
                         + f"; {d['integration']['target']} did not move.")
        steps = [n for n in d["nodes"] if n["authored"] and n["status"] not in (None,
                                                                               "verified")]
        if st and steps:
            parts.append("Authored step(s) " + _names([f"{n['id']} ({n['status']})"
                                                       for n in steps])
                         + " will be written and verified on the next launch.")
        if not parts:
            done = st["wavesDone"] if st else []
            parts.append("Ready: the design validates" + (
                "" if unprobed else ", and every toolchain it names is installed") + (
                f"; waves {', '.join(done)} are done" if done else "") + ".")
        if unprobed and not missing:
            parts.append(f"Toolchain(s) {_names(unprobed)} were not probed: run "
                         "arbeitsplan-preflight before trusting that.")
    if wf:
        parts.append(f"The compiled workflow {wf['runId']} "
                     + ("is rejected by the compiler." if wf["rejections"] else "validates."))
    return " ".join(parts) or "Nothing to show: give --design, --workflow or --bundle."


def collect(design: dict | None = None, state: dict | None = None, workflow: dict | None = None,
            preflight: dict | None = None, synthetic: bool = False,
            generated: str | None = None) -> dict:
    report = {"kind": "design-report/1", "synthetic": synthetic,
              "generated": generated or datetime.datetime.now(datetime.UTC).strftime(
                  "%Y-%m-%d %H:%M UTC"),
              "design": collect_design(design, state, preflight) if design else None,
              "workflow": collect_workflow(workflow) if workflow else None}
    report["verdict"] = verdict(report)
    return report


def load_bundle(path: Path) -> dict:
    """A committed demo: {design, state, preflight, workflow}; a string value is a
    path relative to the bundle, so a fixture that already exists is not copied."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for key in ("design", "state", "preflight", "workflow"):
        val = raw.get(key)
        out[key] = (json.loads((path.parent / val).read_text(encoding="utf-8"))
                    if isinstance(val, str) else val)
    out["synthetic"] = bool(raw.get("synthetic"))
    out["generated"] = raw.get("generated")
    return out


# --- selftest -----------------------------------------------------------------------------

def selftest() -> int:
    fails: list = []

    def ok(name: str, cond: bool, detail: object = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)
            if detail != "":
                print(f"       {str(detail)[:300]}")

    try:
        bundle = load_bundle(FIXTURE)
    except (OSError, ValueError) as exc:
        print(f"  FAIL the demo bundle is unreadable: {exc}")
        return 1
    demo = collect(**bundle)
    html = render(demo)
    ok("tokens marker replaced", TOKENS_MARKER not in html and "--bg" in html)
    ok("data marker replaced", DATA_MARKER not in html and "const DESIGN" in html)
    ok("static h1 matches the title", "<title>arbeitsplan — workflow design</title>" in html
       and "<h1>arbeitsplan — workflow design</h1>" in html)
    ok("CSP is default-src 'none'", "default-src 'none'" in html)
    ok("no network fetches", 'src="http' not in html and 'href="http' not in html)
    ok("a static verdict element exists", 'class="verdict"' in html)
    ok("a static legend exists", 'class="legend"' in html)
    ok("no innerHTML assignment", "innerHTML" not in html and "insertAdjacentHTML" not in html)
    ok("the demo is labelled synthetic", demo["synthetic"] is True)

    d = demo["design"]
    kinds = {n["kind"] for n in d["nodes"]}
    # `referee` is a node kind a design may use, but a swarm row's blind referee
    # is that row's `referee` field -- the demo shows it there (w1-parse, swarm 2).
    ok("the demo shows every node kind a wave design dispatches",
       {"agent", "script", "merge-gate", "human-gate"} <= kinds, kinds)
    ok("the demo shows a swarm row", any(n["swarm"] and n["swarm"] > 1 for n in d["nodes"]))
    ok("the demo shows a write-scope overlap, from the validator",
       d["overlaps"] and any("[AP-WAVE-SCOPE-OVERLAP]" in e for e in d["rejections"]), d)
    ok("the demo shows a missing toolchain", any(t["installed"] is False
                                                 for t in d["toolchains"]), d["toolchains"])
    ok("the demo shows a red gate from the state", d["state"] and d["state"]["redGates"])
    ok("the demo shows an authored step that is not yet verified",
       any(n["authored"] and n["status"] != "verified" for n in d["nodes"]))
    ok("the demo shows a verified authored step",
       any(n["authored"] and n["status"] == "verified" for n in d["nodes"]))
    ok("the demo carries a compiled workflow", demo["workflow"] and demo["workflow"]["phases"])
    ok("the verdict names the overlap, the missing toolchain and the red gate",
       all(s in demo["verdict"] for s in ("does not validate", "not installed", "RED at")),
       demo["verdict"])

    # collect() on real inputs, not only on the committed demo.
    good = json.loads((HERE / "fixtures" / "design" / "waves.design.json").read_text())
    clean = collect(good, preflight={"go": True, "python": True})
    ok("a clean design with every toolchain installed reads Ready",
       clean["verdict"].startswith("Ready: the design validates, and every toolchain"),
       clean["verdict"])
    ok("without state, no node claims a status",
       all(n["status"] is None for n in clean["design"]["nodes"]))
    unprobed = collect(good)
    ok("unprobed toolchains are said to be unprobed, never installed",
       "were not probed" in unprobed["verdict"]
       and all(t["installed"] is None for t in unprobed["design"]["toolchains"]),
       unprobed["verdict"])
    state = {"waves": {"1": {"status": "done", "integrationSha": "I1"}},
             "builders": {"w1-parse": {}, "w1-render": {}, "w2-cli": {}},
             "gates": {"1:0": {"green": True}, "2:0": {"green": False, "findings": [
                 {"gate": "test", "source": "primary-only", "exit": 1}]}}}
    ran = collect(good, state=state, preflight={"go": True, "python": True})
    st = {n["id"]: n["status"] for n in ran["design"]["nodes"]}
    ok("state: a done wave's rows and gate read done and green",
       st["w1-parse"] == "done" and st["gate-1"] == "green", st)
    ok("state: a red gate reads red, and its wave's recorded row reads done",
       st["gate-2"] == "red" and st["w2-cli"] == "done", st)
    ok("state: a node the state does not record reads as not recorded",
       st["smoke"] is None and st["preflight"] is None, st)
    ok("state: the verdict names the red gate and its primary-only finding",
       "RED at gate-2 (primary-only finding)" in ran["verdict"], ran["verdict"])
    bad = json.loads(json.dumps(good))
    next(n for n in bad["nodes"] if n["id"] == "w1-render")["writeScope"] = ["internal/**"]
    over = collect(bad)
    ok("an overlap is computed for concurrent rows only, from land_candidate",
       over["design"]["overlaps"] and over["design"]["overlaps"][0]["a"] in ("w1-parse",
                                                                             "w1-render"),
       over["design"]["overlaps"])
    ok("a rejection is attached to the node it names",
       any(n["rejections"] for n in over["design"]["nodes"] if n["id"] == "w1-render")
       or any("wave 1" in e for e in over["design"]["general"]), over["design"])
    wf = collect(workflow=json.loads((HERE / "fixtures" / "six-phase.workflow.json").read_text()))
    ok("a compiled workflow's phases are chained by requires -> marker",
       any(p["depends_on"] for p in wf["workflow"]["phases"]), wf["workflow"]["phases"])
    broken = json.loads((HERE / "fixtures" / "six-phase.workflow.json").read_text())
    broken["phases"][2]["fanOut"] = "many"
    wf_bad = collect(workflow=broken)["workflow"]
    ok("a compiled workflow's rejection is attached to the phase it names",
       wf_bad["phases"][2]["rejections"] and wf_bad["rejections"], wf_bad["phases"][2])
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"selftest passed ({len(d['nodes'])} demo nodes rendered)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="build_design_html.py",
        description="Render an arbeitsplan design (and its run, and its compiled workflow) as "
                    "a graph with a verdict.",
        epilog="exit 0 written, 2 could not read an input")
    parser.add_argument("--design", help="design.json, or an installed <name>.plan.json")
    parser.add_argument("--state", help="the output of `<name>_state.py show`")
    parser.add_argument("--workflow", help="a compiled workflow.json")
    parser.add_argument("--preflight", help="{toolchain: true|false} from arbeitsplan-preflight")
    parser.add_argument("--bundle", help="a committed demo bundle (scripts/fixtures/design-demo.json)")
    parser.add_argument("--out", help="default: design-report.html next to --design, or ./")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    try:
        if args.bundle:
            inputs = load_bundle(Path(args.bundle))
        elif args.design or args.workflow:
            def read(p):
                return json.loads(Path(p).read_text(encoding="utf-8")) if p else None
            inputs = {"design": read(args.design), "state": read(args.state),
                      "workflow": read(args.workflow), "preflight": read(args.preflight)}
        else:
            parser.error("one of --design, --workflow or --bundle is required")
    except (OSError, ValueError) as exc:
        print(f"cannot read an input: {exc}", file=sys.stderr)
        return 2
    report = collect(**inputs)
    anchor = args.design or args.workflow
    out = Path(args.out) if args.out else (Path(anchor).parent if anchor else Path()) \
        / "design-report.html"
    out.write_text(render(report), encoding="utf-8")
    print(f"wrote {out}\n{report['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
