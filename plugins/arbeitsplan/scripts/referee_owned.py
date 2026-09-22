#!/usr/bin/env python3
"""Baseline and re-check a run's refereeOwned artifacts by content, not by trust.

usage: referee_owned.py {record,verify,selftest} --run RUNID [--root DIR] [--tree DIR]

`refereeOwned` (#77) names paths a referee-fixture phase writes before any
candidate exists. `land_candidate.py` already refuses a diff that TOUCHES one;
this script is the other half -- "delivering such an artifact immutably, so its
identity is checkable rather than asserted" (the issue's own proposed fix). A
guard that only refuses a proposed edit says nothing about a write that reached
the artifact some other way (a `Bash` shell-out the guard's matcher does not
cover, for instance). Recording the sha256 once and re-checking it later closes
that gap by evidence rather than by assumption.

  record --run R [--root analysis/arbeitsplan]
      cwd = repo root. Reads refereeOwned from <root>/R/workflow.json, hashes
      every path (sha256), and writes <root>/R/referee_owned.json ONCE
      (O_CREAT|O_EXCL). A second record for the same run is REFUSED: the
      baseline is taken at creation, never re-taken to accommodate a later
      change -- that would let a run quietly re-baseline over evidence of
      exactly the mutation this script exists to catch. A refereeOwned path
      that does not exist yet is REFUSED by name; record after the
      referee-fixture phase has produced it, never before.

  verify --run R [--tree DIR] [--root analysis/arbeitsplan]
      Re-hashes every recorded path under DIR (default: cwd) and compares
      against the record. Exit 0 iff every path still matches. A mismatch or a
      missing path is REFUSED, naming the path. No record at all is refused
      too -- never inferred as "nothing to check".

Exit: 0 ok, 1 refused, 2 bad input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


def expand_referee_owned(owned: list, base: Path) -> list:
    """Every refereeOwned entry, resolved to a concrete relative path (posix
    form) under `base`. A glob (contains '*', '?' or '[') is expanded with
    `Path.glob`; an entry that expands to nothing is carried through AS ITSELF
    so the caller can refuse it by the name the spec actually used, rather than
    silently hashing zero files and reporting success over nothing."""
    out = []
    for raw in owned:
        if any(ch in raw for ch in "*?["):
            matched = sorted(
                p.relative_to(base).as_posix() for p in base.glob(raw) if p.is_file()
            )
            out.extend(matched or [raw])
        else:
            out.append(raw)
    return out


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cmd_record(root: Path, run_id: str) -> int:
    spec_path = root / run_id / "workflow.json"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"no spec at {spec_path}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"{spec_path} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    owned = spec.get("refereeOwned") or []
    if not owned:
        print(f"REFUSED: {spec_path} declares no refereeOwned paths; nothing to record.",
              file=sys.stderr)
        return 1

    record_path = root / run_id / "referee_owned.json"
    if record_path.exists():
        print(f"REFUSED: {record_path} already exists. A run's referee-owned artifacts are "
              "hashed ONCE, at creation -- a second record would let something already "
              "reachable by a candidate re-baseline itself over whatever it changed.",
              file=sys.stderr)
        return 1

    base = Path.cwd()
    candidates = expand_referee_owned(owned, base)
    missing = [c for c in candidates if not (base / c).is_file()]
    if missing:
        print(f"REFUSED: refereeOwned path(s) do not exist yet: {missing}. Record after the "
              "referee-fixture phase has produced them, never before.", file=sys.stderr)
        return 1

    hashed = {c: hash_file(base / c) for c in candidates}
    record_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(record_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        print(f"REFUSED: {record_path} already exists (race).", file=sys.stderr)
        return 1
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"runId": run_id, "paths": hashed}, fh, indent=2)
        fh.write("\n")
    print(f"recorded sha256 for {len(hashed)} refereeOwned path(s) of run {run_id!r}")
    return 0


def cmd_verify(root: Path, run_id: str, tree: Path) -> int:
    record_path = root / run_id / "referee_owned.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"REFUSED: no record at {record_path}. Nothing was ever baselined for run "
              f"{run_id!r} -- run 'record' first; a missing record is never read as a pass.",
              file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"REFUSED: {record_path} is unreadable ({exc}).", file=sys.stderr)
        return 1

    paths = record.get("paths")
    if not isinstance(paths, dict) or not paths:
        print(f"REFUSED: {record_path} carries no 'paths'; there is nothing to check.",
              file=sys.stderr)
        return 1

    bad = []
    for rel, want in paths.items():
        p = tree / rel
        if not p.is_file():
            bad.append(f"{rel}: missing")
            continue
        got = hash_file(p)
        if got != want:
            bad.append(f"{rel}: sha256 mismatch (recorded {want[:12]}, now {got[:12]})")
    if bad:
        for b in bad:
            print(f"REJECTED referee_owned: {b}", file=sys.stderr)
        return 1
    print(f"verified {len(paths)} refereeOwned path(s) of run {run_id!r}: unchanged")
    return 0


def selftest() -> int:
    fails: list = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as raw:
        cwd = Path.cwd()
        try:
            os.chdir(raw)
            tmp = Path(raw)
            (tmp / "oracle").mkdir()
            (tmp / "oracle" / "spec.txt").write_text("the oracle\n")
            run_dir = tmp / "analysis" / "arbeitsplan" / "ap-t-selftest"
            run_dir.mkdir(parents=True)
            (run_dir / "workflow.json").write_text(json.dumps(
                {"refereeOwned": ["oracle/spec.txt"]}))

            ok("verify with no record refuses",
               cmd_verify(Path("analysis/arbeitsplan"), "ap-t-selftest", tmp) != 0)
            ok("record succeeds",
               cmd_record(Path("analysis/arbeitsplan"), "ap-t-selftest") == 0)
            ok("a second record is refused",
               cmd_record(Path("analysis/arbeitsplan"), "ap-t-selftest") != 0)
            ok("verify on the untouched tree passes",
               cmd_verify(Path("analysis/arbeitsplan"), "ap-t-selftest", tmp) == 0)
            (tmp / "oracle" / "spec.txt").write_text("mutated\n")
            ok("verify detects a mutation",
               cmd_verify(Path("analysis/arbeitsplan"), "ap-t-selftest", tmp) != 0)

            run2 = tmp / "analysis" / "arbeitsplan" / "ap-t-missing"
            run2.mkdir(parents=True)
            (run2 / "workflow.json").write_text(json.dumps(
                {"refereeOwned": ["oracle/absent.txt"]}))
            ok("record refuses a refereeOwned path that does not exist",
               cmd_record(Path("analysis/arbeitsplan"), "ap-t-missing") != 0)

            ok("expand_referee_owned passes literal paths through unchanged",
               expand_referee_owned(["oracle/spec.txt"], tmp) == ["oracle/spec.txt"])
            ok("expand_referee_owned expands a glob to its matches",
               expand_referee_owned(["oracle/*.txt"], tmp) == ["oracle/spec.txt"])
        finally:
            os.chdir(cwd)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("referee_owned selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="referee_owned.py",
        description="Baseline and re-check an arbeitsplan run's refereeOwned artifacts by "
                    "sha256, so a candidate that reached one is detected rather than assumed "
                    "impossible.",
        epilog="exit 0 ok, 1 refused, 2 bad input",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="hash and baseline every refereeOwned path, once")
    rec.add_argument("--run", required=True)
    rec.add_argument("--root", default="analysis/arbeitsplan")

    ver = sub.add_parser("verify", help="re-hash the recorded paths and compare")
    ver.add_argument("--run", required=True)
    ver.add_argument("--root", default="analysis/arbeitsplan")
    ver.add_argument("--tree", help="directory to verify against (default: cwd)")

    sub.add_parser("selftest", help="planted-defect selftest")

    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    root = Path(args.root)
    if args.cmd == "record":
        return cmd_record(root, args.run)
    tree = Path(args.tree) if args.tree else Path.cwd()
    return cmd_verify(root, args.run, tree)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
