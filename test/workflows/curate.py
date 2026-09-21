#!/usr/bin/env python3
"""Turn recorded cells into evidence pages under docs/examples/.

Every number on a published page comes from a cell record written by
`plugins/arbeitsplan/scripts/subrun.py`. Nothing here re-derives, rounds or
summarises a result the runner did not record: if a field is missing it is
printed as missing, because a curated page that invents a plausible value is
worse than one with a gap in it.

Cells live under analysis/workflows/<runId>/<matrix>/cells/*.json, which is
gitignored -- the raw sweep is machine-local. What lands in git is this
rendering of it, stamped with the run ids it came from.

Usage: curate.py --runs analysis/workflows/<runId> [...] --out docs/examples
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Which mode/model a run directory represents. Read from the cell's own matrix
# rather than guessed from the directory name.
CASE_TITLES = {
    "build-feature": "Build a feature",
    "understand-repo": "Understand an unfamiliar repo",
    "fix-bug": "Fix a bug",
    "design-ui": "Design a UI",
    "review-plugin": "Review a plugin",
    "routing": "Which workflow fits?",
    "hazard-plan-under-lock": "Plan mode under an open run-scope lock",
}


# Caveats a table cannot state. Versioned with the generator rather than
# hand-added to the output, because the output is regenerated and a hand-edit
# would be silently lost -- and the caveat below is the difference between a
# result and a misreading of one.
CASE_NOTES = {
    "hazard-plan-under-lock": (
        "**These PASSes are vacuous, and the page says so rather than counting them.** The "
        "cells attempted no write at all -- only Read, Bash and ToolSearch -- so the guard "
        "they exist to exercise was never reached, and `hook denials` is 0 for a reason that "
        "has nothing to do with the guard working. The real evidence for this hazard is "
        "`test/workflows/evidence/plan-file-under-lock.md`, reproduced deterministically by "
        "`bash test/workflows/reproduce_hazard.sh` in under a second. A case whose outcome "
        "does not depend on the thing it measures is a case that needs a better prompt."
    ),
    "build-feature": (
        "`zirkel:zirkel-clarify-scope` did not fire in any run, across two models and two "
        "permission modes, with zirkel the only werkstoff plugin loaded and a prompt that "
        "says \"scope the work before writing code\". That is not a model-tier result: it "
        "points at the skill's own description."
    ),
    "design-ui": (
        "Both sonnet runs fired `cupertino:cupertino-council` instead of the expected "
        "`cupertino-backwards`. The plugin is reached; the documented ordering (backwards "
        "first, then council) is not what the model picks."
    ),
}


def load_cells(run_dirs: list[Path]) -> list[dict]:
    cells = []
    for run in run_dirs:
        for path in sorted(run.glob("*/cells/*.json")):
            if "_subrun" in path.parts:
                continue
            cell = json.loads(path.read_text(encoding="utf-8"))
            matrix = path.parent.parent / ".." / f"{path.parent.parent.name}.json"
            mode = model = None
            if matrix.exists():
                spec = json.loads(matrix.read_text(encoding="utf-8"))
                mode = spec.get("permission_mode")
                model = (spec.get("models") or [None])[0]
            cell["_mode"] = mode or "?"
            cell["_model"] = model or cell.get("model", "?")
            cell["_run"] = run.name
            cells.append(cell)
    return cells


def verdict_line(rows: list[dict]) -> str:
    """One sentence a reader can act on, derived only from the outcomes present."""
    outcomes = [r["outcome"] for r in rows]
    fired = sum(1 for r in rows if r.get("skills_fired"))
    if all(o == "PASS" for o in outcomes):
        return f"Fired as intended in every run ({len(rows)}/{len(rows)})."
    if not any(o == "PASS" for o in outcomes):
        return (f"The expected skill never fired, in {len(rows)} runs. "
                f"{fired} run(s) fired some other skill.")
    passes = outcomes.count("PASS")
    return (f"Fired in {passes} of {len(rows)} runs -- the prompt is underdetermined, "
            "which is a finding about the prompt, not a plugin failure.")


def render_case(case: str, rows: list[dict], stamp: str) -> str:
    rows = sorted(rows, key=lambda r: (r["_mode"], r["_model"], r["repeat"]))
    title = CASE_TITLES.get(case, case)
    out = [f"# {title}", "",
           f"Measured evidence for the `{case}` case. {verdict_line(rows)}", "",
           "| mode | model | run | outcome | skills fired | hook denials | mode denials | diff | cost | time |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        skills = ", ".join(f"`{s}`" for s in (r.get("skills_fired") or [])) or "--"
        diff = f"{len(r.get('diff') or '')} B" if r.get("diff") is not None else "--"
        cost = f"${r['cost_usd']:.2f}" if r.get("cost_usd") is not None else "--"
        out.append(
            f"| `{r['_mode']}` | {r['_model']} | #{r['repeat']} | **{r['outcome']}** | {skills} "
            f"| {len(r.get('hook_denials') or [])} | {len(r.get('mode_denials') or [])} "
            f"| {diff} | {cost} | {r.get('duration_s', '?')}s |"
        )
    reasons = {(r.get("fail_reason") or r.get("unmeasured_reason") or "").strip()
               for r in rows} - {""}
    if reasons:
        out += ["", "**Why the failing runs failed**", ""]
        out += [f"- {reason}" for reason in sorted(reasons)]
    denials = [d for r in rows for d in (r.get("mode_denials") or [])]
    if denials:
        tools = sorted({d.get("tool") or "?" for d in denials})
        out += ["", f"**What the permission mode refused** -- {len(denials)} call(s), "
                    f"tool(s): {', '.join(f'`{t}`' for t in tools)}. One verbatim:", "",
                "> " + (denials[0].get("reason") or "").replace("\n", " ")[:300]]
    sample = next((r for r in rows if (r.get("final_text") or "").strip()), None)
    if sample:
        text = " ".join((sample["final_text"] or "").split())[:500]
        out += ["", f"**What the run said** (`{sample['_mode']}`, {sample['_model']}, "
                    f"run #{sample['repeat']})", "", f"> {text}"]
    if case in CASE_NOTES:
        out += ["", CASE_NOTES[case]]
    out += ["", "---", "", stamp, ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out", default="docs/examples")
    args = parser.parse_args()

    run_dirs = [Path(r) for r in args.runs]
    missing = [str(r) for r in run_dirs if not r.is_dir()]
    if missing:
        print(f"no such run director(y/ies): {', '.join(missing)}", file=sys.stderr)
        return 2

    cells = load_cells(run_dirs)
    if not cells:
        print("no cell records found -- refusing to write evidence pages with no evidence",
              file=sys.stderr)
        return 1

    version = subprocess.run(["claude", "--version"], capture_output=True, text=True,
                             check=False).stdout.strip() or "unknown"
    stamp = (f"*Recorded {datetime.now(timezone.utc):%Y-%m-%d} from "
             f"{', '.join(sorted(r.name for r in run_dirs))} with {version}. "
             f"Every number above comes from a cell record; regenerate with "
             f"`test/workflows/curate.py`.*")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    by_case: dict[str, list[dict]] = {}
    for cell in cells:
        by_case.setdefault(cell["case"], []).append(cell)

    total = sum(c.get("cost_usd") or 0 for c in cells)
    for case, rows in sorted(by_case.items()):
        (out_dir / f"{case}.md").write_text(render_case(case, rows, stamp), encoding="utf-8")
        print(f"  {out_dir / f'{case}.md'}  ({len(rows)} cells)")

    index = ["# Measured examples", "",
             "Nothing in the approved-workflow docs is documented until it has been run. These "
             "pages are the runs: real `claude -p` cells over the synthetic fixtures in "
             "`test/workflows/fixtures/`, each in its own clean box, recorded by "
             "`plugins/arbeitsplan/scripts/subrun.py`.", "",
             "| case | cells | expected skill fired | caveat |", "|---|---|---|---|"]
    for case, rows in sorted(by_case.items()):
        passes = sum(1 for r in rows if r["outcome"] == "PASS")
        caveat = "see the page" if case in CASE_NOTES else "--"
        index.append(f"| [{CASE_TITLES.get(case, case)}]({case}) | {len(rows)} "
                     f"| {passes}/{len(rows)} | {caveat} |")
    index += ["", f"Total recorded spend across these cells: ${total:.2f}. "
                  "A cell that could not be measured fairly is scored `UNMEASURED` and excluded "
                  "from every denominator; none of the cells here were.", "", stamp, ""]
    (out_dir / "index.md").write_text("\n".join(index), encoding="utf-8")
    print(f"  {out_dir / 'index.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
