#!/usr/bin/env python3
"""Apply exactly one candidate's diff to the shared tree.

usage: land_candidate.py [-h] --run RUNID --candidate ID [--apply] [--selftest]

This is the only place in arbeitsplan that writes to the working tree, and it
applies ONE diff. The losers are deleted, never merged -- which is why a merge
conflict cannot occur here at all. If this script ever grows a second diff, that
property is gone.

It refuses rather than forcing:
  * a diff that does not apply cleanly is a refusal, not a --3way retry. The
    tree moved under the candidate, so the candidate was measured against a
    state that no longer exists and its referee verdict no longer means what it
    said.
  * a diff touching a path outside the run's writeScope is a refusal. The scope
    is the contract every candidate was dispatched under.

Exit: 0 applied, 1 refused, 2 bad input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path


def paths_in_diff(diff: str) -> list:
    """Every path a unified diff touches, from its +++/--- headers."""
    found = []
    for line in diff.splitlines():
        m = re.match(r"^(?:\+\+\+|---) (?:[ab]/)?(.+)$", line)
        if m and m.group(1) != "/dev/null":
            found.append(m.group(1).strip())
    return sorted(set(found))


def in_scope(path: str, scope: list) -> bool:
    base = path.rsplit("/", 1)[-1]
    for raw in scope:
        pattern = raw.replace("**/", "*/").replace("**", "*")
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(base, pattern):
            return True
    return False


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="land_candidate.py",
        description="Apply exactly one arbeitsplan candidate's diff to the shared tree. "
                    "Refuses a diff that does not apply cleanly or that leaves the "
                    "declared writeScope.",
        epilog="exit 0 applied, 1 refused, 2 bad input",
    )
    parser.add_argument("--run", help="runId")
    parser.add_argument("--candidate", help="candidate id, e.g. c2")
    parser.add_argument("--root", default="analysis/arbeitsplan")
    parser.add_argument("--apply", action="store_true",
                        help="actually apply; without it the checks run and nothing is written")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        fails = []
        cases = [
            ("plain paths", "--- a/src/x.py\n+++ b/src/x.py\n", ["src/x.py"]),
            ("new file", "--- /dev/null\n+++ b/src/new.py\n", ["src/new.py"]),
            ("two files", "--- a/a.py\n+++ b/a.py\n--- a/b.py\n+++ b/b.py\n", ["a.py", "b.py"]),
        ]
        for name, diff, want in cases:
            got = paths_in_diff(diff)
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: {got}")
            if not ok:
                fails.append(name)
        scope_cases = [
            ("glob with **", "src/api/limits/x.py", ["src/api/**"], True),
            ("literal file", "tests/test_x.py", ["tests/test_x.py"], True),
            ("outside scope", "src/secrets.py", ["src/api/**"], False),
            ("basename match", "x.py", ["*.py"], True),
        ]
        for name, path, scope, want in scope_cases:
            got = in_scope(path, scope)
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} scope {name}: {got}")
            if not ok:
                fails.append(name)
        print()
        if fails:
            print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
            return 1
        print("selftest passed")
        return 0

    if not args.run or not args.candidate:
        parser.error("--run and --candidate are required unless --selftest is given")

    spec_path = Path(args.root) / args.run / "workflow.json"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"no spec at {spec_path}", file=sys.stderr)
        return 2

    result_path = Path(args.root) / args.run / "candidates" / f"{args.candidate}.json"
    try:
        candidate = json.loads(result_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"no candidate result at {result_path}", file=sys.stderr)
        return 2

    if not candidate.get("measured"):
        print(f"REFUSED: {args.candidate} is unmeasured -- it was never fairly tried, so "
              "there is nothing to land.", file=sys.stderr)
        return 1

    # The workflow's landing allowlist lived only in run.js, so THIS entry point
    # would apply a rejected -- or never judged -- diff. The referee record is
    # the authority, and `accepted` is an allowlist: `rejected` and
    # `cannot_judge` are never collapsed into each other, and a missing record
    # is not read as consent.
    verdict_path = Path(args.root) / args.run / "referee" / f"{args.candidate}.json"
    try:
        referee = json.loads(verdict_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"REFUSED: no referee record at {verdict_path}. A candidate nothing judged "
              "is not an accepted candidate; run the referee pass before landing.",
              file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"REFUSED: the referee record at {verdict_path} is unreadable ({exc}). "
              "Refusing rather than landing on an unverifiable verdict.", file=sys.stderr)
        return 1
    seen = referee.get("verdict")
    if seen != "accepted":
        print(f"REFUSED: {args.candidate}'s referee verdict is {seen!r}, and only "
              "'accepted' lands. 'rejected' says the candidate is wrong; 'cannot_judge' "
              "says nothing is known, which points at the criteria rather than the "
              "candidate. Neither is consent.", file=sys.stderr)
        return 1

    diff = candidate.get("diff") or ""
    if not diff.strip():
        print(f"REFUSED: {args.candidate} carries no diff.", file=sys.stderr)
        return 1

    scope = spec["writeScope"]
    out_of_scope = [p for p in paths_in_diff(diff) if not in_scope(p, scope)]
    if out_of_scope:
        print(f"REFUSED: {args.candidate} touches {out_of_scope} outside the declared "
              f"writeScope {scope}. The scope is the contract this candidate was "
              "dispatched under.", file=sys.stderr)
        return 1

    check = subprocess.run(["git", "apply", "--check", "-"], input=diff,
                           capture_output=True, text=True)
    if check.returncode != 0:
        print(f"REFUSED: {args.candidate}'s diff does not apply cleanly.\n"
              f"{check.stderr.strip()}\n"
              "Not retrying with --3way: the tree moved under this candidate, so it was "
              "measured against a state that no longer exists and its referee verdict no "
              "longer means what it said. Re-run the phase against the current tree.",
              file=sys.stderr)
        return 1

    if not args.apply:
        print(f"{args.candidate} would apply cleanly, {len(paths_in_diff(diff))} path(s), "
              "all in scope (not applied; pass --apply)")
        return 0

    applied = subprocess.run(["git", "apply", "-"], input=diff, capture_output=True, text=True)
    if applied.returncode != 0:
        print(f"REFUSED: apply failed after a clean --check: {applied.stderr.strip()}",
              file=sys.stderr)
        return 1

    print(f"landed {args.candidate}: {', '.join(paths_in_diff(diff))}")
    print("Nothing was merged. Delete the losing worktrees with:")
    print(f"  python3 plugins/arbeitsplan/scripts/worktree_pool.py destroy --run {args.run} "
          f"--keep {args.candidate}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
