#!/usr/bin/env python3
"""Prove every RECORDED-RED fixture actually goes red, and only for its rule.

usage: test_red_fixtures.py [--root plugins/arbeitsplan] [--baseline SHA]

A "recorded-red" rule is a validator this tree ADDED that rejects a spec HEAD
compiled clean. compile_spec.RED_RULES names each such rule id -> the issue
that motivated it; fixtures/red/MANIFEST.json names, per entry, which
committed fixture proves it. This script is the calibration for that claim:

  * every RED_RULES id has >= 1 manifest entry -- a rule with no fixture is
    red for a reason nothing can demonstrate
  * every manifest entry's rule maps to its declared issue in RED_RULES
  * for each entry: run THIS TREE's compiler (subprocess, never imported --
    testing one candidate must never load another's code) with the entry's
    args against its fixture. The exit code must equal expect.exit (default
    1, and never 0 -- a "recorded-red" case that passes proves nothing), a
    REJECTED/WARNING line must carry '[<rule>]', and NO REJECTED/WARNING line
    may be unkeyed (carry no id RED_RULES recognises) -- an unkeyed line means
    the fixture went red for some OTHER reason, which is red for the wrong
    reason and proves nothing about the rule under test

--baseline SHA additionally `git archive`s that commit's plugins/arbeitsplan
into a scratch directory and asserts every fixture compiles CLEAN there (exit
0) -- the "HEAD accepted this" half of the claim, checked against the real
commit rather than assumed true forever. Skipped by default (no baseline arg):
CI runs a shallow checkout with no history to archive from.

compile_spec.py --selftest calls run_checks() itself (without --baseline) and
fails if it does, so a red fixture that stopped going red cannot hide behind a
green `compile_spec.py --selftest` reported on its own.

Exit: 0 every fixture behaves as recorded, 1 otherwise, 2 bad input.
STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # plugins/arbeitsplan
RULE_TAG = re.compile(r"\[(AP-[A-Z0-9-]+)\]")


def _red_rules(scripts_dir: Path) -> dict:
    """compile_spec.RED_RULES, read by a subprocess -- never imported directly,
    so this check can run standalone (it is also imported BY compile_spec.py,
    and importing compile_spec back from here would be circular)."""
    code = ("import json,sys; sys.path.insert(0, sys.argv[1]); import compile_spec as c; "
            "print(json.dumps(getattr(c, 'RED_RULES', None)))")
    r = subprocess.run([sys.executable, "-c", code, str(scripts_dir)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise ValueError(f"cannot read compile_spec.RED_RULES: {r.stderr.strip()[-300:]}")
    got = json.loads(r.stdout.strip().splitlines()[-1])
    if not isinstance(got, dict):
        raise ValueError("compile_spec.RED_RULES is absent or not a dict")
    return {str(k): int(v) for k, v in got.items()}


def _compile(compiler: Path, fixture: Path, args: list) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(compiler), "--spec", str(fixture), *args],
                          capture_output=True, text=True, timeout=120)


def run_checks(root: Path, baseline: str | None = None) -> list:
    """`root` is plugins/arbeitsplan. Returns a list of failure strings; an
    empty list means every fixture behaved as recorded."""
    fails: list = []
    scripts = root / "scripts"
    red_dir = scripts / "fixtures" / "red"
    compiler = scripts / "compile_spec.py"

    try:
        manifest = json.loads((red_dir / "MANIFEST.json").read_text(encoding="utf-8"))
        entries = manifest["entries"]
        assert isinstance(entries, list) and entries
    except (OSError, ValueError, KeyError, AssertionError) as exc:
        return [f"no readable fixtures/red/MANIFEST.json with a non-empty 'entries' list ({exc})"]

    try:
        rules = _red_rules(scripts)
    except ValueError as exc:
        return [str(exc)]

    for rid in rules:
        if not any(e.get("rule") == rid for e in entries):
            fails.append(f"RED_RULES has {rid!r} with no manifest entry -- it does not count "
                         "as recorded-red")
    for e in entries:
        rid, issue = e.get("rule"), e.get("issue")
        if rules.get(rid) != issue:
            fails.append(f"{e.get('fixture')}: rule {rid!r} does not map to issue {issue} in "
                         "RED_RULES")

    for e in entries:
        rid, fx = e.get("rule"), red_dir / str(e.get("fixture"))
        args, expect = list(e.get("args") or []), e.get("expect") or {}
        tag = f"{rid} {e.get('fixture')}"
        if not fx.is_file():
            fails.append(f"{tag}: fixture file missing")
            continue
        after = _compile(compiler, fx, args)
        want_exit = expect.get("exit", 1)
        lines = [ln for ln in after.stderr.splitlines() if ln.startswith(("REJECTED", "WARNING"))]
        tagged = [ln for ln in lines if f"[{rid}]" in ln]
        unkeyed = [ln for ln in lines if not any(t in rules for t in RULE_TAG.findall(ln))]
        if after.returncode != want_exit or after.returncode == 0:
            fails.append(f"{tag}: exit {after.returncode}, expected {want_exit} (nonzero)")
        if not tagged:
            fails.append(f"{tag}: no REJECTED/WARNING line carries [{rid}]: "
                         f"{after.stderr.strip()[-400:]}")
        if unkeyed:
            fails.append(f"{tag}: red for an unkeyed reason: {unkeyed[:3]}")
        stderr_re = expect.get("stderrRe")
        if stderr_re and not re.search(stderr_re, after.stderr):
            fails.append(f"{tag}: stderr does not match {stderr_re!r}")

    if baseline:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            repo_root = root.parent.parent  # plugins/arbeitsplan -> plugins -> repo root
            try:
                arch = subprocess.run(["git", "archive", baseline, "plugins/arbeitsplan"],
                                      capture_output=True, cwd=repo_root, check=True, timeout=60)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                return [*fails, f"--baseline {baseline}: could not git archive it ({exc})"]
            subprocess.run(["tar", "-x", "-C", str(tmpdir)], input=arch.stdout, check=True)
            head_compiler = tmpdir / "plugins" / "arbeitsplan" / "scripts" / "compile_spec.py"
            for e in entries:
                fx = red_dir / str(e.get("fixture"))
                if not fx.is_file():
                    continue
                head = _compile(head_compiler, fx, [])
                if head.returncode != 0:
                    fails.append(f"{e.get('fixture')}: baseline {baseline} did NOT accept it "
                                 f"(exit {head.returncode}) -- not a gap the baseline had: "
                                 f"{head.stderr.strip()[-300:]}")
    return fails


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="test_red_fixtures.py",
                                     description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--root", default=str(ROOT), help="plugins/arbeitsplan (default: this checkout's)")
    parser.add_argument("--baseline", help="a commit-ish; asserts every fixture compiled clean there")
    args = parser.parse_args(argv)

    fails = run_checks(Path(args.root), args.baseline)
    for f in fails:
        print(f"  FAIL {f}")
    if fails:
        print(f"\nFAILED ({len(fails)})")
        return 1
    print("all recorded-red fixtures behave as recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
