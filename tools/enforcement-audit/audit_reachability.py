#!/usr/bin/env python3
"""Gate 2b — is each guard actually REACHABLE, or only described?

Gate 2 asks whether a guard exists. That is not the same question. The rebuilt
andon defines `advance_guard`, which raises on every andon-rule condition — and
`skills/andon-loop/SKILL.md` reaches it with the sentence "run
`andon_rules.advance_guard(...)`". A sentence naming a function is not a call.
The model has to notice it and choose to shell out, which is exactly the
prose-enforcement failure the rebuild existed to remove, relocated one level up
from the rule to its call site.

Two ways a guard is genuinely reachable, and the second one matters:

  direct   the function is named inside a fenced code block the model is told
           to run  (`python3 -c '... R.assert_blast_radius_tag(...)'`)
  module   its containing script is invoked as an entry point in a fenced block
           (`python3 scripts/verify_scaffold.py <dir>`) — every function that
           run reaches counts, without being named

Missing the `module` case makes this tool badly wrong: a first version scored
cli-scaffold 0/23 reachable when in fact its skills invoke verify_scaffold.py,
lang_router.py and write_scope.py directly, so all 23 were reachable. Counting
identifiers instead of call paths understates a well-wired plugin and would
have sent me editing a plugin that had no problem.

Usage: audit_reachability.py <plugin-dir> [...]
Exit: 0 if every guard is reachable, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GUARD_DEF = re.compile(r"^def\s+((?:assert|check|validate|verify|resolve|require|ensure|guard)_\w+|\w*_guard)\s*\(", re.M)
FENCED = re.compile(r"```.*?```", re.S)


def instruction_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for sub in ("skills", "agents", "commands"):
        out += sorted((root / sub).rglob("*.md"))
    return out


def audit(root: Path) -> dict:
    guards: dict[str, str] = {}
    for p in sorted((root / "scripts").glob("*.py")):
        if p.name.startswith("test_"):
            continue
        for m in GUARD_DEF.finditer(p.read_text(encoding="utf-8", errors="replace")):
            guards[m.group(1)] = p.name

    blocks: list[str] = []
    for p in instruction_files(root):
        blocks += FENCED.findall(p.read_text(encoding="utf-8", errors="replace"))
    # Also treat a workflow script as executable context: the Workflow tool runs
    # it deterministically, which is the ONLY non-model-mediated path available.
    wf = "".join(p.read_text(encoding="utf-8", errors="replace") for p in (root / "workflows").glob("*.js")) \
        if (root / "workflows").is_dir() else ""
    blob = "\n".join(blocks)

    invoked_modules = {m for m in {g for g in guards.values()} if re.search(rf"\b{re.escape(m)}\b", blob)}

    prose_text = "\n".join(
        FENCED.sub("", p.read_text(encoding="utf-8", errors="replace")) for p in instruction_files(root))

    rows = []
    for fn, mod in sorted(guards.items()):
        if re.search(rf"\b{re.escape(fn)}\b", blob) or re.search(rf"\b{re.escape(fn)}\b", wf):
            kind, how = "reachable", "direct call in a runnable block"
        elif mod in invoked_modules:
            kind, how = "reachable", f"via `{mod}` invoked as an entry point"
        elif re.search(rf"\b{re.escape(fn)}\b", prose_text):
            kind, how = "PROSE-ONLY", "named in a sentence — the model must choose to run it"
        else:
            kind, how = "unreferenced", "defined but never mentioned"
        rows.append({"guard": fn, "module": mod, "reachability": kind, "how": how})
    return {"plugin": root.name, "guards": rows,
            "totals": {k: sum(1 for r in rows if r["reachability"] == k)
                       for k in ("reachable", "PROSE-ONLY", "unreferenced")}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0] if __doc__ else "")
    ap.add_argument("plugin_dirs", nargs="+", type=Path)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--strict", action="store_true", help="exit 1 unless every guard is reachable")
    args = ap.parse_args(argv)

    reports, ok = [], True
    for d in args.plugin_dirs:
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            return 2
        r = audit(d)
        reports.append(r)
        if r["totals"]["PROSE-ONLY"] or r["totals"]["unreferenced"]:
            ok = False

    if args.format == "json":
        print(json.dumps(reports, indent=2))
    else:
        for r in reports:
            t = r["totals"]
            print(f"\n══ {r['plugin']}   reachable={t['reachable']}  "
                  f"prose-only={t['PROSE-ONLY']}  unreferenced={t['unreferenced']}")
            for g in r["guards"]:
                if g["reachability"] != "reachable":
                    print(f"   [{g['reachability']:<12}] {g['guard']:<32} {g['how']}")
        print("\nA guard the model must be persuaded to call is not enforcement.")
    return 0 if (ok or not args.strict) else 1


if __name__ == "__main__":
    sys.exit(main())
