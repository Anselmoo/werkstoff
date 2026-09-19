#!/usr/bin/env python3
"""Fail when workflows/run.js's output schemas and references/candidate-contract.md disagree.

usage: check_contract_sync.py [--selftest]

run.js holds four JSON Schemas as literals (INVENTORY, CANDIDATE, REFEREE, SINGLE);
candidate-contract.md shows each as a fenced example. Nothing compared them, so a
field added to one was a field the other silently lacked -- a builder told to
return a key the referee's documentation never mentions.

The schemas are read by EVALUATING run.js's top section in node (everything
before its first line of control flow), never by regex over source: a regex that
misreads a nested `properties` reports agreement it never checked. The reference
side is the first ```json block under each section heading. Compared against the
live files, never a snapshot -- a snapshot taken while both already disagreed
stays green forever, which shipped once in this repo (`69f438a`).

Exit: 0 in sync, 1 drift, 2 an input could not be read (never reported as a pass).
STDLIB ONLY, plus `node` on PATH.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIRS = {
    "INVENTORY_SCHEMA": "## Inventory output",
    "CANDIDATE_SCHEMA": "## Builder output",
    "REFEREE_SCHEMA": "## Referee output",
    "SINGLE_SCHEMA": "## Single-writer output",
}
CUT = "const opts = normalizeArgs(args)"
# The top section of run.js, evaluated with its `export` stripped, then asked to
# hand back the schema constants. Values arrive through argv, never interpolated.
NODE = (
    'const s=require("fs").readFileSync(process.argv[1],"utf8");'
    'const cut=s.indexOf(process.argv[2]);if(cut<0){console.error("marker not found");process.exit(2)}'
    'const names=JSON.parse(process.argv[3]);'
    'const body=s.slice(0,cut).replace(/^export\\s+(?=const\\s+meta\\b)/m,"")+'
    '"\\nreturn {"+names.join(",")+"}";'
    'process.stdout.write(JSON.stringify(new Function(body)()))'
)


class Unreadable(Exception):
    pass


def schemas(run_js: Path) -> dict:
    node = shutil.which("node")
    if not node:
        raise Unreadable("node is not on PATH; the schemas cannot be evaluated")
    r = subprocess.run([node, "-e", NODE, str(run_js), CUT, json.dumps(list(PAIRS))],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Unreadable(f"evaluating {run_js.name} failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def examples(ref: Path) -> dict:
    text = ref.read_text(encoding="utf-8")
    out = {}
    for name, heading in PAIRS.items():
        i = text.find(heading + "\n")
        if i < 0:
            raise Unreadable(f"{ref.name} has no {heading!r} section")
        m = re.compile(r"```json\n(.*?)\n```", re.S).search(text, i)
        nxt = text.find("\n## ", i + len(heading))
        if not m or (nxt >= 0 and m.start() > nxt):
            raise Unreadable(f"{ref.name}: {heading!r} has no ```json block of its own")
        try:
            out[name] = json.loads(m.group(1))
        except ValueError as exc:
            raise Unreadable(f"{ref.name}: the example under {heading!r} is not JSON ({exc})") from exc
    return out


def compare(sch: dict, ex: dict) -> list:
    drift = []
    for name, heading in PAIRS.items():
        props = set((sch.get(name) or {}).get("properties", {}))
        required = set((sch.get(name) or {}).get("required", []))
        shown = set(ex[name])
        for k in sorted(props - shown):
            drift.append(f"{name}.{k} is in run.js but missing from {heading!r}")
        for k in sorted(shown - props):
            drift.append(f"{heading!r} shows {k!r}, which {name} does not declare")
        for k in sorted(required - shown):
            drift.append(f"{name} REQUIRES {k!r}, and {heading!r} does not show it")
    return drift


def selftest() -> int:
    sch = {"CANDIDATE_SCHEMA": {"properties": {"a": {}, "b": {}}, "required": ["a"]}}
    base = {n: {} for n in PAIRS}
    cases = [
        ("identical sides", {"CANDIDATE_SCHEMA": {"a": 1, "b": 2}}, 0),
        ("key only in run.js", {"CANDIDATE_SCHEMA": {"a": 1}}, 1),
        ("key only in the reference", {"CANDIDATE_SCHEMA": {"a": 1, "b": 2, "c": 3}}, 1),
        ("required key missing from the example", {"CANDIDATE_SCHEMA": {"b": 2}}, 2),
    ]
    fails = []
    for name, ex, want in cases:
        got = [d for d in compare({**{n: {} for n in PAIRS}, **sch}, {**base, **ex}) if "CANDIDATE" in d]
        ok = len(got) == want
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {len(got)} drift line(s)")
        if not ok:
            fails.append(name)
    # And the live pair must agree, or the selftest is calibrating an instrument
    # whose real verdict is already red.
    try:
        live = compare(schemas(ROOT / "workflows" / "run.js"), examples(ROOT / "references" / "candidate-contract.md"))
        ok = not live
        print(f"  {'ok  ' if ok else 'FAIL'} live run.js vs candidate-contract.md: {len(live)} drift line(s)")
        if not ok:
            fails.append("live")
    except Unreadable as exc:
        print(f"  FAIL live comparison could not run: {exc}")
        fails.append("live unreadable")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("check_contract_sync selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="check_contract_sync.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        drift = compare(schemas(ROOT / "workflows" / "run.js"), examples(ROOT / "references" / "candidate-contract.md"))
    except Unreadable as exc:
        print(f"ERROR: {exc} -- the check did not run, so it cannot report a pass", file=sys.stderr)
        return 2
    if drift:
        for d in drift:
            print(f"DRIFT {d}")
        return 1
    print(f"in sync: {len(PAIRS)} schemas match their examples in references/candidate-contract.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
