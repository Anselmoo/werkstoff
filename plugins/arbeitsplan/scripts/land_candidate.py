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

After applying it RECORDS the landing: landed.json (written once) and a
`landed` event in run.jsonl. landed.json compares the candidate's recorded hunks
with what `git diff` shows for the same paths afterwards; when they differ it
carries `divergedFrom`, so a correction made at landing is recorded rather than
leaving candidates/<id>.json describing a diff that is not what landed.

Exit: 0 applied, 1 refused, 2 bad input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_record  # vendored copy of tools/run-record/run_record.py


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


def subtract_referee_owned(scope: list, referee_owned: list) -> list:
    """`writeScope` minus `refereeOwned` -- the ONE place this subtraction is
    computed. compile_spec.py's AP-REFOWNED-OUTSIDE-SCOPE rejection calls this
    (per referee-owned path, against the full scope) to decide whether that path
    is reachable through `writeScope` at all; worktree_pool.py calls it to open a
    fan-out phase's lock with a NARROWED scope, so a candidate's writable tree
    never lexically contains a referee-owned path in the first place. Landing
    itself does not call this: `main()` refuses a referee-owned touch directly,
    by `in_scope()`, so its refusal names the path rather than an already-edited
    scope list.

    `fnmatch` has no negation, so there is no narrower glob to hand back in place
    of a dropped entry -- inventing one would be exactly the "never infer a
    missing gating value" mistake this plugin refuses everywhere else. A scope
    entry is dropped outright whenever it overlaps a referee-owned path or glob,
    in either direction (the referee-owned entry falls inside the scope glob, or
    the scope glob is itself named by a referee-owned glob).
    """
    if not referee_owned:
        return list(scope)
    keep = []
    for s in scope:
        overlaps = any(in_scope(ro, [s]) or in_scope(s, [ro]) for ro in referee_owned)
        if not overlaps:
            keep.append(s)
    return keep


def hunk_body(diff: str) -> list:
    """The +/- lines of a diff, headers and context dropped: what a comparison
    of two diffs of the same paths should agree on regardless of index lines,
    hunk offsets or context width."""
    return [ln for ln in diff.splitlines()
            if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]


def landing_record(run_id: str, candidate_id: str, recorded: str, applied: str, paths: list) -> dict:
    rec = {
        "runId": run_id, "candidate": candidate_id, "paths": paths,
        "recordedSha256": hashlib.sha256("\n".join(hunk_body(recorded)).encode()).hexdigest(),
        "appliedSha256": hashlib.sha256("\n".join(hunk_body(applied)).encode()).hexdigest(),
    }
    if rec["recordedSha256"] != rec["appliedSha256"]:
        rec["divergedFrom"] = {
            "candidate": candidate_id,
            "onlyRecorded": [ln for ln in hunk_body(recorded) if ln not in hunk_body(applied)][:40],
            "onlyApplied": [ln for ln in hunk_body(applied) if ln not in hunk_body(recorded)][:40],
        }
    return rec


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
        rec_diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n"
        same = "diff --git a/x.py b/x.py\nindex 1..2\n--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-old\n+new\n"
        edited = same.replace("+new", "+newer")
        for name, applied, want_div in [("identical hunks, different headers", same, False),
                                         ("a correction at landing", edited, True)]:
            got = "divergedFrom" in landing_record("r", "c1", rec_diff, applied, ["x.py"])
            ok = got == want_div
            print(f"  {'ok  ' if ok else 'FAIL'} landing record: {name} -> diverged={got}")
            if not ok:
                fails.append(name)
        for name, path, scope, want in scope_cases:
            got = in_scope(path, scope)
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} scope {name}: {got}")
            if not ok:
                fails.append(name)
        subtract_cases = [
            ("no refereeOwned leaves scope untouched",
                ["src/**", "oracle/**"], [], ["src/**", "oracle/**"]),
            ("a glob containing the owned path is dropped whole",
                ["src/**", "oracle/**"], ["oracle/spec.txt"], ["src/**"]),
            ("an owned path with no overlapping scope entry drops nothing",
                ["src/**"], ["oracle/spec.txt"], ["src/**"]),
            ("a literal scope entry equal to the owned path is dropped",
                ["oracle/spec.txt", "src/**"], ["oracle/spec.txt"], ["src/**"]),
        ]
        for name, scope, owned, want in subtract_cases:
            got = subtract_referee_owned(scope, owned)
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} subtract {name}: {got}")
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
    diff_paths = paths_in_diff(diff)

    # refereeOwned (#77): paths a referee-fixture phase wrote before any candidate
    # existed. Checked BEFORE the ordinary scope refusal below, and separately from
    # it, so the message always names 'refereeOwned' rather than folding into the
    # generic "outside writeScope" wording -- these paths are typically INSIDE
    # writeScope (that is what makes them reachable at all without this check).
    referee_owned = spec.get("refereeOwned") or []
    owned_touch = [p for p in diff_paths if in_scope(p, referee_owned)]
    if owned_touch:
        print(f"REFUSED: {args.candidate} touches refereeOwned path(s) {owned_touch}. "
              "These are written once, before any candidate exists, by a referee-fixture "
              "phase, and are subtracted from every fan-out phase's effective write scope. "
              "A diff that reaches one anyway is refused rather than landed, whether or not "
              "the guard should have stopped it earlier.", file=sys.stderr)
        return 1

    out_of_scope = [p for p in diff_paths if not in_scope(p, scope)]
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
        print(f"{args.candidate} would apply cleanly, {len(diff_paths)} path(s), "
              "all in scope (not applied; pass --apply)")
        return 0

    applied = subprocess.run(["git", "apply", "-"], input=diff, capture_output=True, text=True)
    if applied.returncode != 0:
        print(f"REFUSED: apply failed after a clean --check: {applied.stderr.strip()}",
              file=sys.stderr)
        return 1

    paths = paths_in_diff(diff)
    after = subprocess.run(["git", "diff", "--", *paths], capture_output=True, text=True).stdout
    rec = landing_record(args.run, args.candidate, diff, after, paths)
    landed = Path(args.root) / args.run / "landed.json"
    try:
        fd = os.open(landed, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        print(f"WARNING: {landed} already exists; a run lands exactly once, so this second "
              "landing is recorded only as an event.", file=sys.stderr)
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
    try:
        run = run_record.open_run("arbeitsplan", args.run)
        run.append({"trace_id": args.run, "span_id": f"{args.run}.landed.{args.candidate}",
                    "parent_span_id": f"{args.run}.root", "span": "execute_tool land_candidate",
                    "node_id": args.candidate, "status": "accepted",
                    "detail": {"paths": paths, "diverged": "divergedFrom" in rec}})
    except run_record.RecordError as exc:
        print(f"WARNING: landed, but the event could not be recorded: {exc}", file=sys.stderr)
    if "divergedFrom" in rec:
        print(f"NOTE: what landed differs from candidates/{args.candidate}.json; recorded as "
              f"divergedFrom in {landed}")
    print(f"landed {args.candidate}: {', '.join(paths)}")
    print("Nothing was merged. Delete the losing worktrees with:")
    print(f"  python3 plugins/arbeitsplan/scripts/worktree_pool.py destroy --run {args.run} "
          f"--keep {args.candidate}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
