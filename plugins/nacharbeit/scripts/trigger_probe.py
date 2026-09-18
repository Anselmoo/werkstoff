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
                claude_bin: str, budget: float | None, fixture: str | None = None) -> dict:
    argv = [claude_bin, "-p", entry["prompt"], "--model", model, "--permission-mode", "plan",
            "--output-format", "json", "--strict-mcp-config"]
    plugin_dirs = []
    if arm == "isolated":
        pd = (plugins_root / entry["plugin"]).resolve()
        argv += ["--setting-sources", "project", "--plugin-dir", str(pd)]
        plugin_dirs = [str(pd)]
    elif arm == "werkstoff":
        # Every plugin under plugins_root, in a clean box: the same competition the
        # routing simulation's corpus models. `isolated` (one plugin) and `installed`
        # (the whole machine) each measure a different question than the simulation.
        plugin_dirs = sorted(str(d.resolve()) for d in plugins_root.iterdir() if (d / ".claude-plugin").is_dir())
        argv += ["--setting-sources", "project"]
        for d in plugin_dirs:
            argv += ["--plugin-dir", d]
    return {
        "label": f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', entry['id'])}__{model}__{arm}__{rep}",
        "argv": argv, "case": entry["id"], "model": model, "plugin_state": arm, "repeat": rep,
        "ablation": "installed" if arm == "installed" else "isolated", "plugin_dirs": plugin_dirs, "transcript": True,
        # expect_skills stays empty ON PURPOSE: subrun decides only whether the cell ran
        # FAIRLY. Whether the right skill fired is decided below on normalised names,
        # because a transcript may report `plugin:skill` where the index says `skill`.
        "expect_skills": [], "forbid_skills": [], "max_budget_usd": budget,
        "timeout_s": 600,
        # subrun copies the fixture into the cell's own temp dir and git-inits it. An
        # EMPTY cwd was measured to decide the verdict: 21 of 23 prompts went silent
        # because the model ran `ls`, found nothing, and asked instead of acting.
        **({"fixture": fixture} if fixture else {}),
    }


def compose_fixture(mounts: list, dest: Path) -> Path:
    """Build one probe repository from `sub=dir` mounts (`.` is the root).

    Composed at run time from the committed academic fixtures rather than committed
    as a second copy, so the probe repo cannot drift from the fixtures it is made of.
    Generated noise (__pycache__, .pyc) is left out.
    """
    dest.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")
    for m in mounts:
        sub, _, src = m.partition("=")
        if not src or not Path(src).is_dir():
            raise SystemExit(f"--mount {m!r}: expected SUB=DIR with an existing DIR")
        target = dest if sub in (".", "") else dest / sub
        shutil.copytree(src, target, dirs_exist_ok=True, ignore=ignore)
    return dest


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
    # Conditional agreement: only prompts where the probe saw SOME skill fire. The
    # simulation always picks a component; silence is a thing it cannot express, so
    # counting silent prompts against it measures the difference between the two
    # questions, not the simulation's accuracy.
    fired_rows = [row for row in rows if row["probe"]]
    fired_agree = sum(1 for row in fired_rows if bare(row["simulation"] or "") == row["probe"])
    return {"compared": total, "agree": agree, "agreement": round(agree / total, 3) if total else None,
            "firedCompared": len(fired_rows), "firedAgree": fired_agree,
            "firedAgreement": round(fired_agree / len(fired_rows), 3) if fired_rows else None,
            "rows": rows}


def run(args) -> int:
    import subrun  # vendored copy of tools/subrun/subrun.py

    entries = parse_index(Path(args.index).read_text(encoding="utf-8"))
    if args.prompts:
        wanted = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
        missing = [w for w in wanted if not any(e["prompt"] == w for e in entries)]
        if missing:
            raise SystemExit(f"--prompts names text no documented prompt has: {missing[:3]}")
        entries = [e for e in entries if e["prompt"] in wanted]
    else:
        entries = select(entries, args.only, args.all)
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
    fixture = None
    if args.mount:
        fixture = str(compose_fixture(args.mount, out / "fixture").resolve())
        print(f"fixture: composed {len(args.mount)} mount(s) into {fixture}; every cell gets its own git-initialised copy")
    results = []
    for e in entries:
        got = []
        for rep in range(1, args.repeats + 1):
            cfg = cell_config(e, rep, args.model, args.arm, Path(args.plugins_root), claude, args.max_budget_usd, fixture)
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
    summary = {"model": args.model, "arm": args.arm, "repeats": args.repeats, "mounts": args.mount or [], "results": results,
               "unmeasured": sum(r["verdict"] == "UNMEASURED" for r in results),
               "cost_usd": round(sum(r["cost_usd"] for r in results), 4)}
    if args.routing:
        summary["routingAgreement"] = compare_routing(results, json.loads(Path(args.routing).read_text(encoding="utf-8")))
        ra = summary["routingAgreement"]
        print(f"simulation vs probe: {ra['agree']}/{ra['compared']} agree"
              + (f" ({ra['agreement']:.2f})" if ra["agreement"] is not None else "")
              + f"; where a skill fired: {ra['firedAgree']}/{ra['firedCompared']}")
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
    with tempfile.TemporaryDirectory() as raw:
        for n in ("demo", "other", "not-a-plugin"):
            (Path(raw) / n).mkdir()
        for n in ("demo", "other"):
            (Path(raw) / n / ".claude-plugin").mkdir()
        w = cell_config(es[0], 1, "haiku", "werkstoff", Path(raw), "claude", None)
        ok("werkstoff arm: every plugin, nothing else, in a clean box",
           w["argv"].count("--plugin-dir") == 2 and w["ablation"] == "isolated" and len(w["plugin_dirs"]) == 2)
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

    with tempfile.TemporaryDirectory() as raw:
        a_dir, b_dir = Path(raw) / "a", Path(raw) / "b"
        (a_dir / "__pycache__").mkdir(parents=True)
        (a_dir / "README.md").write_text("root")
        (a_dir / "__pycache__" / "x.pyc").write_text("noise")
        b_dir.mkdir()
        (b_dir / "index.html").write_text("<p>")
        fx = compose_fixture([f".={a_dir}", f"ui={b_dir}"], Path(raw) / "fx")
        ok("compose: root and sub mounts, pycache left out",
           (fx / "README.md").is_file() and (fx / "ui" / "index.html").is_file() and not (fx / "__pycache__").exists())
        ok("a fixture reaches the cell config", cell_config(es[0], 1, "haiku", "isolated", Path("plugins"), "claude", None, str(fx))["fixture"] == str(fx))

    res = [verdict(e, [c("PASS", ["other-help"]), c("PASS", ["other-help"])])]
    ra = compare_routing(res, {"misrouted": [{"text": "do the thing", "got": "other-help"}]})
    ok("routing agreement: a simulated misroute the probe confirms agrees", ra == {**ra, "compared": 1, "agree": 1})
    ra = compare_routing(res, {"misrouted": []})
    ok("routing agreement: a simulation that said 'fine' disagrees with a real capture", ra["agree"] == 0)
    silent = verdict(e, [c("PASS", []), c("PASS", [])])
    ra = compare_routing([silent, verdict(e, [c("PASS", ["demo-do"]), c("PASS", ["demo-do"])])], {"misrouted": []})
    ok("conditional agreement ignores silent prompts", ra["firedCompared"] == 1 and ra["firedAgree"] == 1 and ra["agree"] == 1)

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
    ap.add_argument("--prompts", help="a JSON list of exact prompt texts -- a sample chosen outside the prober")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--arm", choices=["isolated", "werkstoff", "installed"], default="isolated")
    ap.add_argument("--index", default="docs/prompt-index.md")
    ap.add_argument("--plugins-root", default="plugins")
    ap.add_argument("--routing", help="a review's routing.json to compare the simulation against")
    ap.add_argument("--mount", action="append", default=[], metavar="SUB=DIR",
                    help="compose a probe repository from fixture dirs (`.=DIR` for the root); repeatable")
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
    if not a.only and not a.all and not a.prompts:
        print("name what to probe with --only (the default scope), or pass --all deliberately", file=sys.stderr)
        return 2
    return run(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
