#!/usr/bin/env python3
"""Measure whether a documented prompt actually fires the skill it names -- in a fresh process.

usage: trigger_probe.py --model MODEL (--only ID ... | --all) [--repeats N] [--arm isolated|installed]
                        [--index docs/prompt-index.md] [--routing analysis/nacharbeit/routing.json]
                        [--out DIR] [--max-budget-usd X] [--dry-run]
       trigger_probe.py --selftest

nacharbeit's routing simulation asks a haiku model which component a DESCRIPTION
would route to. That is a proxy. This asks the real question -- does the prompt
fire the skill -- by running it headless, one cell per prompt x repeat, through
subrun.py (the same single-cell executor arbeitsplan's matrix uses, vendored
here): clean box, isolation sentinel, auth preflight, stream-json transcript.
This script is argv assembly plus a summary. It is not a second engine.

Per prompt the verdict is computed from the cells that ran FAIRLY:
  fired      the named skill fired in every measured repeat
  captured   another skill fired first -- the one that captured it is named
  silent     no skill fired at all
  UNSTABLE   measured repeats disagree; a finding, never a retry trigger
  UNMEASURED no repeat ran fairly (auth, sentinel, empty output): no rate at all

Four limits, stated here rather than discovered:
  * COST. ~$0.34 per cell was measured. --only is the default; --all is opt-in and
    --dry-run prints the cell count and the estimate first.
  * N >= 2. One repeat cannot separate a fix from noise; --repeats 1 is refused.
  * The ARM decides the question. `isolated` (only this plugin, via --plugin-dir,
    in a clean box) asks "does it fire at all". `installed` (the real installation)
    asks "does it win where users are" -- a misroute to a sibling is an installed fact.
  * The TIER is recorded with every rate. haiku and sonnet route differently
    (measured 3/14 vs 8/14 on one prompt set); a rate without its model is not a rate.

--routing compares the probe against the simulation on the probed prompts, which is
what turns the simulation's 0.8 floor from a proxy's self-consistency into its
agreement with reality.

Exit: 0 every probed prompt fired; 1 any captured/silent/UNSTABLE; 2 usage error or
nothing measured.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

COST_PER_CELL = 0.34  # USD, measured on the 2026-09 sweeps; an estimate, never a quote
MIN_PYTHON = (3, 11)


def parse_index(text: str) -> list:
    """`"<prompt>"` followed by `> Triggers \\`<id>\\`` under a `## <plugin>` heading."""
    out, plugin, pending = [], None, None
    for ln in text.splitlines():
        if ln.startswith("## "):
            plugin = ln[3:].strip()
            pending = None
            continue
        m = re.match(r'^"(.+)"$', ln.strip())
        if m:
            pending = m.group(1)
            continue
        t = re.match(r"^> Triggers `([^`]+)`", ln)
        if t and pending is not None:
            out.append({"id": f"{plugin}:{t.group(1)}:{len(out) + 1:03d}", "plugin": plugin,
                        "expected": t.group(1), "prompt": pending})
            pending = None
    return out


def select(entries: list, only: list, take_all: bool) -> list:
    if take_all:
        return entries
    picked = [e for e in entries if e["expected"] in only or e["id"] in only]
    missing = [o for o in only if not any(e["expected"] == o or e["id"] == o for e in entries)]
    if missing:
        raise SystemExit(f"--only names no documented prompt: {missing}")
    return picked


def bare(name: str) -> str:
    return name.split(":", 1)[1] if ":" in name else name


def cell_config(entry: dict, rep: int, model: str, arm: str, plugins_root: Path,
                claude_bin: str, budget: float | None) -> dict:
    argv = [claude_bin, "-p", entry["prompt"], "--model", model, "--permission-mode", "plan",
            "--output-format", "json", "--strict-mcp-config"]
    plugin_dirs = []
    if arm == "isolated":
        pd = (plugins_root / entry["plugin"]).resolve()
        argv += ["--setting-sources", "project", "--plugin-dir", str(pd)]
        plugin_dirs = [str(pd)]
    return {
        "label": f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', entry['id'])}__{model}__{arm}__{rep}",
        "argv": argv, "case": entry["id"], "model": model, "plugin_state": arm, "repeat": rep,
        "ablation": arm, "plugin_dirs": plugin_dirs, "transcript": True,
        # expect_skills stays empty ON PURPOSE: subrun decides only whether the cell ran
        # FAIRLY. Whether the right skill fired is decided below on normalised names,
        # because a transcript may report `plugin:skill` where the index says `skill`.
        "expect_skills": [], "forbid_skills": [], "max_budget_usd": budget,
        "timeout_s": 600,
    }


def verdict(entry: dict, cells: list) -> dict:
    fair = [c for c in cells if c.get("outcome") in ("PASS", "FAIL", "DENIED")]
    per = []
    for c in fair:
        fired = [bare(s) for s in c.get("skills_fired") or []]
        if entry["expected"] in fired and (not fired or fired[0] == entry["expected"]):
            per.append(("fired", None))
        elif fired:
            per.append(("captured", fired[0]))
        else:
            per.append(("silent", None))
    base = {"id": entry["id"], "expected": entry["expected"], "prompt": entry["prompt"],
            "measured": len(fair), "cells": len(cells),
            "cost_usd": round(sum(c.get("cost_usd") or 0 for c in cells), 4)}
    if not per:
        reasons = sorted({c.get("unmeasured_reason") or "unknown" for c in cells})
        return {**base, "verdict": "UNMEASURED", "reasons": reasons}
    kinds = {k for k, _ in per}
    if len(set(per)) > 1:
        return {**base, "verdict": "UNSTABLE", "observed": [f"{k}{':' + w if w else ''}" for k, w in per]}
    k, w = per[0]
    return {**base, "verdict": k, **({"capturedBy": w} if w else {}), "rate": f"{len(per)}/{len(per)}",
            "kinds": sorted(kinds)}


def compare_routing(results: list, routing: dict) -> dict:
    """Agreement of the haiku simulation with the probe, on the prompts both saw.

    The simulation's winners are keyed by its own prompt ids; join on prompt TEXT.
    """
    by_text = {}
    for m in routing.get("misrouted") or []:
        by_text[m.get("text")] = m.get("got")
    agree = total = 0
    rows = []
    for r in results:
        if r["verdict"] not in ("fired", "captured", "silent"):
            continue
        sim = by_text.get(r["prompt"], r["expected"])  # not misrouted by the simulation => it said expected
        real = r["expected"] if r["verdict"] == "fired" else r.get("capturedBy")
        total += 1
        agree += int(bare(sim or "") == (real or ""))
        rows.append({"id": r["id"], "simulation": sim, "probe": real})
    return {"compared": total, "agree": agree, "agreement": round(agree / total, 3) if total else None, "rows": rows}


def run(args) -> int:
    import subrun  # vendored copy of tools/subrun/subrun.py

    entries = select(parse_index(Path(args.index).read_text(encoding="utf-8")), args.only, args.all)
    cells = [(e, rep) for e in entries for rep in range(1, args.repeats + 1)]
    est = round(len(cells) * COST_PER_CELL, 2)
    print(f"trigger probe — {len(entries)} prompt(s) x {args.repeats} repeat(s) = {len(cells)} cell(s), "
          f"model {args.model}, arm {args.arm}; estimate ~${est} at ${COST_PER_CELL}/cell")
    claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"
    if args.dry_run:
        for e, rep in cells:
            print("  " + " ".join(cell_config(e, rep, args.model, args.arm, Path(args.plugins_root), claude, args.max_budget_usd)["argv"][:3])[:150])
        print("dry run -- nothing spent")
        return 0
    out = Path(args.out or tempfile.mkdtemp(prefix="trigger-probe-"))
    (out / "cells").mkdir(parents=True, exist_ok=True)
    results = []
    for e in entries:
        got = []
        for rep in range(1, args.repeats + 1):
            cfg = cell_config(e, rep, args.model, args.arm, Path(args.plugins_root), claude, args.max_budget_usd)
            path = out / "cells" / f"{cfg['label']}.json"
            try:
                cell = subrun.run_one_cell(cfg, path)
            except (subrun.AuthError, subrun.ConfigError, SystemExit) as exc:
                # The environment, not the fix: nothing was measured, so exit 2 --
                # never 1, which would blame the description for a logged-out CLI.
                print(f"REFUSED before any cell ran: {exc}", file=sys.stderr)
                return 2
            path.write_text(json.dumps(cell, indent=1))
            got.append(cell)
        results.append(verdict(e, got))
        r = results[-1]
        print(f"  {r['verdict']:<10} {r['expected']:<32} measured {r['measured']}/{r['cells']}"
              + (f"  captured by {r['capturedBy']}" if r.get("capturedBy") else ""))
    summary = {"model": args.model, "arm": args.arm, "repeats": args.repeats, "results": results,
               "unmeasured": sum(r["verdict"] == "UNMEASURED" for r in results),
               "cost_usd": round(sum(r["cost_usd"] for r in results), 4)}
    if args.routing:
        summary["routingAgreement"] = compare_routing(results, json.loads(Path(args.routing).read_text(encoding="utf-8")))
        ra = summary["routingAgreement"]
        print(f"simulation vs probe: {ra['agree']}/{ra['compared']} agree"
              + (f" ({ra['agreement']:.2f})" if ra["agreement"] is not None else ""))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(f"{summary['unmeasured']} prompt(s) unmeasured (excluded from every rate); spent ${summary['cost_usd']}; wrote {out}/summary.json")
    measured = [r for r in results if r["verdict"] != "UNMEASURED"]
    if not measured:
        return 2
    return 0 if all(r["verdict"] == "fired" for r in measured) else 1


def selftest() -> int:
    fails = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    idx = '## demo\n\n##### x\n\n````prompt\n"do the thing"\n````\n\n> Triggers `demo-do` — does it.\n\n"stray quote with no trigger"\n\n## other\n"help me"\n> Triggers `other-help` — helps.\n'
    es = parse_index(idx)
    ok("parses prompt + trigger + plugin", [(e["plugin"], e["expected"], e["prompt"]) for e in es]
       == [("demo", "demo-do", "do the thing"), ("other", "other-help", "help me")])
    ok("a quote with no trigger is not a prompt", not any(e["prompt"].startswith("stray") for e in es))
    ok("--only selects by skill id", [e["expected"] for e in select(es, ["other-help"], False)] == ["other-help"])
    try:
        select(es, ["nope"], False)
        ok("--only naming nothing is refused", False)
    except SystemExit:
        ok("--only naming nothing is refused", True)

    cfg = cell_config(es[0], 1, "haiku", "isolated", Path("plugins"), "claude", 0.5)
    ok("isolated arm: --plugin-dir for the prompt's own plugin", "--plugin-dir" in cfg["argv"] and cfg["argv"][cfg["argv"].index("--plugin-dir") + 1].endswith("plugins/demo"))
    ok("the model is explicit in argv", cfg["argv"][cfg["argv"].index("--model") + 1] == "haiku")
    ok("subrun gets no expect_skills (the probe decides on normalised names)", cfg["expect_skills"] == [])
    ok("installed arm adds no --plugin-dir", "--plugin-dir" not in cell_config(es[0], 1, "haiku", "installed", Path("plugins"), "claude", None)["argv"])

    e = es[0]
    c = lambda outcome, fired, **k: {"outcome": outcome, "skills_fired": fired, "cost_usd": 0.3, **k}  # noqa: E731
    ok("fired: namespaced name normalised", verdict(e, [c("PASS", ["demo:demo-do"]), c("PASS", ["demo-do"])])["verdict"] == "fired")
    v = verdict(e, [c("PASS", ["other:other-help", "demo:demo-do"]), c("PASS", ["other-help"])])
    ok("captured: the first skill wins, and is named", v["verdict"] == "captured" and v["capturedBy"] == "other-help")
    ok("silent: nothing fired", verdict(e, [c("PASS", []), c("PASS", [])])["verdict"] == "silent")
    ok("UNSTABLE: repeats disagree", verdict(e, [c("PASS", ["demo-do"]), c("PASS", [])])["verdict"] == "UNSTABLE")
    v = verdict(e, [c("UNMEASURED", [], unmeasured_reason="auth"), c("PASS", ["demo-do"])])
    ok("an unmeasured repeat leaves the denominator", v["verdict"] == "fired" and v["measured"] == 1)
    ok("no fair repeat is UNMEASURED, with reasons",
       verdict(e, [c("UNMEASURED", [], unmeasured_reason="auth")])["verdict"] == "UNMEASURED")

    res = [verdict(e, [c("PASS", ["other-help"]), c("PASS", ["other-help"])])]
    ra = compare_routing(res, {"misrouted": [{"text": "do the thing", "got": "other-help"}]})
    ok("routing agreement: a simulated misroute the probe confirms agrees", ra == {**ra, "compared": 1, "agree": 1})
    ra = compare_routing(res, {"misrouted": []})
    ok("routing agreement: a simulation that said 'fine' disagrees with a real capture", ra["agree"] == 0)

    ok("--repeats 1 is refused", main(["--model", "haiku", "--only", "demo-do", "--repeats", "1"]) == 2)
    ok("no --model is refused (a rate without its tier is not a rate)", main(["--only", "demo-do"]) == 2)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("trigger_probe selftest passed")
    return 0


def main(argv: list) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"trigger_probe needs Python >= 3.11; this is {sys.version.split()[0]}", file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser(prog="trigger_probe.py", description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--model", help="haiku | sonnet | opus | a full id -- required, recorded with every rate")
    ap.add_argument("--only", action="append", default=[], help="a skill id or prompt id (repeatable); the default scope")
    ap.add_argument("--all", action="store_true", help="every documented prompt -- opt-in, it costs real money")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--arm", choices=["isolated", "installed"], default="isolated")
    ap.add_argument("--index", default="docs/prompt-index.md")
    ap.add_argument("--plugins-root", default="plugins")
    ap.add_argument("--routing", help="a review's routing.json to compare the simulation against")
    ap.add_argument("--out")
    ap.add_argument("--max-budget-usd", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if a.selftest:
        return selftest()
    if not a.model:
        print("--model is required: a rate without its tier is not a rate", file=sys.stderr)
        return 2
    if a.repeats < 2:
        print("--repeats must be >= 2: one repeat cannot separate a fix from noise", file=sys.stderr)
        return 2
    if not a.only and not a.all:
        print("name what to probe with --only (the default scope), or pass --all deliberately", file=sys.stderr)
        return 2
    return run(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
