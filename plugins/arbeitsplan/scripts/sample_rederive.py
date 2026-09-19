#!/usr/bin/env python3
"""Pick which partitions of a map-reduce-disjoint phase get re-derived -- in code.

usage: sample_rederive.py --spec workflow.json --phase ID | --selftest

A re-derivation checks an extraction by running it again, blind, and comparing.
Which partitions get checked must not be chosen by any party whose work is being
checked, so the sample is a pure function of the spec: `reDerive.samplePct`,
`reDerive.seed` and the phase's `sources`. The in-session backend calls this;
workflows/run.js carries the same generator (mulberry32 + Fisher-Yates), and the
selftest evaluates run.js's own copy in node and demands identical samples, so
the two backends cannot pick different partitions for the same spec.

Exit: 0 printed the sample, 1 the phase cannot be sampled, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

M32 = 0xFFFFFFFF
MIN_PYTHON = (3, 11)  # checked at runtime; a script runs under whatever python3 is on PATH


def _imul(a: int, b: int) -> int:
    """JavaScript's Math.imul: 32-bit signed multiply, returned unsigned here."""
    return (a * b) & M32


def mulberry32(seed: int):
    s = seed & M32

    def nxt() -> float:
        nonlocal s
        s = (s + 0x6D2B79F5) & M32
        t = s
        t = _imul(t ^ (t >> 15), t | 1)
        t = (t ^ ((t + _imul(t ^ (t >> 7), t | 61)) & M32)) & M32
        return ((t ^ (t >> 14)) & M32) / 4294967296

    return nxt


def sample_indices(n: int, pct: int, seed: int) -> list:
    k = max(1, math.ceil(n * pct / 100))
    rnd = mulberry32(seed)
    idx = list(range(n))
    for i in range(n - 1, 0, -1):
        j = math.floor(rnd() * (i + 1))
        idx[i], idx[j] = idx[j], idx[i]
    return sorted(idx[:k])


def _js_samples(cases: list) -> list | None:
    """run.js's own sampleIndices, evaluated in node. None when node is absent."""
    node = shutil.which("node")
    if not node:
        return None
    run_js = Path(__file__).resolve().parent.parent / "workflows" / "run.js"
    code = (
        'const s=require("fs").readFileSync(process.argv[1],"utf8");'
        'const a=s.indexOf("function mulberry32");const b=s.indexOf("const opts = normalizeArgs(args)");'
        'const f=new Function(s.slice(a,b)+"\\nreturn sampleIndices")();'
        'process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map(c=>f(...c))))'
    )
    r = subprocess.run([node, "-e", code, str(run_js), json.dumps(cases)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"evaluating run.js's sampleIndices failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def selftest() -> int:
    cases = [[4, 25, 7], [4, 100, 1], [10, 30, 42], [16, 10, 123456789], [1, 1, 0], [9, 50, 4294967295]]
    fails = []
    py = [sample_indices(*c) for c in cases]
    for (n, pct, _), got in zip(cases, py, strict=True):
        ok = len(got) == max(1, math.ceil(n * pct / 100)) and len(set(got)) == len(got) and all(0 <= i < n for i in got)
        print(f"  {'ok  ' if ok else 'FAIL'} n={n} pct={pct}: {got}")
        if not ok:
            fails.append(f"shape n={n}")
    ok = sample_indices(10, 30, 42) == sample_indices(10, 30, 42)
    print(f"  {'ok  ' if ok else 'FAIL'} the same seed gives the same sample")
    if not ok:
        fails.append("determinism")
    js = _js_samples(cases)
    if js is None:
        print("  FAIL node is not on PATH, so agreement with run.js was NOT checked")
        fails.append("no node")
    else:
        ok = js == py
        print(f"  {'ok  ' if ok else 'FAIL'} run.js's sampleIndices agrees on all {len(cases)} cases")
        if not ok:
            print(f"       python {py}\n       run.js {js}")
            fails.append("cross-language agreement")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("sample_rederive selftest passed")
    return 0


def main(argv: list) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"sample_rederive needs Python >= 3.11; this is {sys.version.split()[0]}", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(prog="sample_rederive.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--spec")
    parser.add_argument("--phase")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.spec or not args.phase:
        parser.error("--spec and --phase are required unless --selftest is given")
    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {args.spec}: {exc}", file=sys.stderr)
        return 2
    ph = next((p for p in spec.get("phases", []) if p.get("id") == args.phase), None)
    rd = (ph or {}).get("reDerive")
    sources = (ph or {}).get("sources")
    if not ph or not isinstance(rd, dict) or not isinstance(sources, list) or not sources:
        print(f"phase {args.phase!r} has no reDerive and sources to sample; nothing is inferred",
              file=sys.stderr)
        return 1
    picked = sample_indices(len(sources), rd["samplePct"], rd["seed"])
    print(json.dumps({"phase": args.phase, "rederive": [sources[i] for i in picked], "indices": picked}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
