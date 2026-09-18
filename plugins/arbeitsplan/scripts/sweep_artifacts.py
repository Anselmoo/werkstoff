#!/usr/bin/env python3
"""List -- and only with --apply, remove -- the leftovers of finished arbeitsplan runs.

usage: sweep_artifacts.py [--proposal FILE] [--apply] [--selftest]

Nothing pruned analysis/arbeitsplan/<runId>/, .arbeitsplan/<runId>/c*/ worktrees
or .takt/<runId>/ markers, so every run left all three behind. This sweeps them,
under three rules:

  * DRY RUN BY DEFAULT. Without --apply it prints what it would remove and
    touches nothing.
  * The RECORD decides, never a guess. A run is sweepable only when its run.jsonl
    says it ended: complete.json exists, or a FAILED-<stamp>.json does. A run with
    an open phase, a pending plan node, or no record at all is KEPT and named --
    an unreadable record is never read as "finished".
  * A proposal NARROWS, never widens. The cleaner agent proposes paths with
    evidence; with --proposal, only paths that are both proposed AND eligible here
    are removed, and every disagreement is printed. A model's proposal alone
    never removes anything.

Exit: 0 ok (including "nothing to sweep"), 1 --apply failed partway, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_record  # vendored copy of tools/run-record/run_record.py


def survey(root: Path) -> tuple:
    """(eligible paths with reasons, kept runs with reasons)."""
    eligible, kept = [], []
    runs = root / "analysis" / "arbeitsplan"
    for d in sorted(p for p in runs.glob("*") if p.is_dir()) if runs.is_dir() else []:
        rid = d.name
        if not (d / "run.jsonl").is_file():
            kept.append((rid, "no run.jsonl -- nothing proves it ended"))
            continue
        try:
            st = run_record.open_run("arbeitsplan", rid, root).status()
        except run_record.RecordError as exc:
            kept.append((rid, f"record unreadable ({exc}) -- never read as finished"))
            continue
        if not (st["finished"] or st["failed"]):
            kept.append((rid, f"not ended: next is {st['next']['kind']}"))
            continue
        why = "complete.json" if st["finished"] else st["failed"][-1]
        eligible.append((d, f"run {rid} ended ({why})"))
        for extra in (root / ".arbeitsplan" / rid, root / ".takt" / rid):
            if extra.exists():
                eligible.append((extra, f"belongs to ended run {rid}"))
    return eligible, kept


def remove(path: Path, root: Path) -> None:
    if path.parts[-2:-1] == (".arbeitsplan",) or ".arbeitsplan" in path.parts:
        for wt in sorted(path.glob("c*")):
            subprocess.run(["git", "-C", str(root), "worktree", "remove", "--force", str(wt)],
                           capture_output=True, text=True)
    if path.exists():
        shutil.rmtree(path)


def selftest() -> int:
    fails = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)

        def ev(rid: str, node: str, status: str) -> dict:
            return {"trace_id": rid, "span_id": f"{rid}.{node}.{status}", "parent_span_id": f"{rid}.root",
                    "span": f"phase {node}", "node_id": node, "status": status}

        done = run_record.open_run("arbeitsplan", "ap-done", root)
        done.append(ev("ap-done", "build", "opened"))
        done.append(ev("ap-done", "build", "closed"))
        done.finish({"landed": "c1"})
        (root / ".arbeitsplan" / "ap-done" / "c2").mkdir(parents=True)
        (root / ".takt" / "ap-done").mkdir(parents=True)
        live = run_record.open_run("arbeitsplan", "ap-live", root)
        live.append(ev("ap-live", "build", "opened"))
        refused = run_record.open_run("arbeitsplan", "ap-refused", root)
        refused.refuse("spec edited after compile")
        (root / "analysis" / "arbeitsplan" / "ap-norecord").mkdir(parents=True)

        eligible, kept = survey(root)
        paths = {p.relative_to(root).as_posix() for p, _ in eligible}
        ok("a finished run is eligible with its worktrees and markers",
           {"analysis/arbeitsplan/ap-done", ".arbeitsplan/ap-done", ".takt/ap-done"} <= paths)
        ok("a refused run is eligible", "analysis/arbeitsplan/ap-refused" in paths)
        ok("a run with an open phase is kept", any(r == "ap-live" for r, _ in kept))
        ok("a run with no record is kept", any(r == "ap-norecord" for r, _ in kept))
        ok("nothing live is eligible", not any("ap-live" in p or "ap-norecord" in p for p in paths))

        rc = main(["--root", str(root)])
        ok("a dry run removes nothing", rc == 0 and (root / "analysis/arbeitsplan/ap-done").exists())

        prop = root / "proposal.json"
        prop.write_text(json.dumps({"remove": [
            {"path": "analysis/arbeitsplan/ap-done"}, {"path": "analysis/arbeitsplan/ap-live"}]}))
        rc = main(["--root", str(root), "--proposal", str(prop), "--apply"])
        ok("apply removes only proposed AND eligible paths",
           rc == 0 and not (root / "analysis/arbeitsplan/ap-done").exists()
           and (root / "analysis/arbeitsplan/ap-live").exists()
           and (root / "analysis/arbeitsplan/ap-refused").exists())
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("sweep_artifacts selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="sweep_artifacts.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--proposal", help="the cleaner agent's JSON; narrows the sweep, never widens it")
    parser.add_argument("--apply", action="store_true", help="actually remove; default is a dry run")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    root = Path(args.root).resolve()
    eligible, kept = survey(root)
    if args.proposal:
        try:
            wanted = {e["path"] for e in json.loads(Path(args.proposal).read_text(encoding="utf-8"))["remove"]}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"cannot read the proposal {args.proposal}: {exc}", file=sys.stderr)
            return 2
        rel = {p.relative_to(root).as_posix(): (p, why) for p, why in eligible}
        for w in sorted(wanted - set(rel)):
            print(f"  NOT REMOVED  {w}  -- proposed, but the record does not show it ended")
        eligible = [rel[w] for w in sorted(wanted & set(rel))]
    for rid, why in kept:
        print(f"  keep   analysis/arbeitsplan/{rid}  -- {why}")
    if not eligible:
        print("nothing to sweep")
        return 0
    for p, why in eligible:
        print(f"  {'remove' if args.apply else 'would remove'}  {p.relative_to(root).as_posix()}  -- {why}")
    if not args.apply:
        print(f"{len(eligible)} path(s); dry run -- nothing touched. Pass --apply to remove them.")
        return 0
    failed = 0
    for p, _ in eligible:
        try:
            remove(p, root)
        except OSError as exc:
            failed += 1
            print(f"  FAILED {p}: {exc}", file=sys.stderr)
    print(f"removed {len(eligible) - failed} of {len(eligible)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
