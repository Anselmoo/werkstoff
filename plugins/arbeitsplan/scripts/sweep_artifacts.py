#!/usr/bin/env python3
"""List -- and only with --apply, remove -- the leftovers of finished arbeitsplan runs.

usage: sweep_artifacts.py [--proposal FILE] [--apply] [--selftest]

Nothing pruned analysis/arbeitsplan/<runId>/, the git worktrees under .arbeitsplan/<runId>/
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

A dirty candidate worktree (tracked changes, or untracked non-ignored files -- a
rejected candidate's own uncommitted state) is never just discarded (#80):
`worktree_pool.preserve_then_remove` -- the ONE place under scripts/ that calls
`git worktree remove` -- commits it to `kept/<runId>-<cid>` first. A clean worktree
gets no `kept/` branch. Every `arbeitsplan/<runId>/<cid>` candidate branch is deleted
alongside its worktree (this script never did that before). Worktrees are ENUMERATED
from `git worktree list`, never globbed by name: a worktree `create` did not name is
preserved like any other, and a branch that is not this run's candidate branch (a
user's branch, a base branch) is never deleted. FAIL CLOSED: if
preservation cannot write, that worktree and its branch are left exactly in place
and `--apply` exits 1.

Exit: 0 ok (including "nothing to sweep"), 1 --apply failed partway (including a
fail-closed preservation), 2 bad input.
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
import worktree_pool  # preserve_then_remove/is_dirty: the ONE `git worktree remove` seam (#80)


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


def plan_candidate_removals(root: Path, path: Path, run_id: str) -> list:
    """Read-only: per git worktree registered under a `.arbeitsplan/<run_id>` path --
    whatever it is named -- what a preservation would do, for the dry-run listing.
    Calls only `git worktree list` and `git status`, never `add`/`commit`/`branch`,
    so a dry run truly touches nothing."""
    out = []
    for wt in worktree_pool.worktrees_under(root, path):
        cid = wt["path"].name
        dirty = worktree_pool.is_dirty(wt["path"])
        cand = worktree_pool.is_candidate_branch(run_id, wt["branch"])
        out.append({
            "cid": cid, "dirty": dirty,
            "kept_branch": f"kept/{run_id}-{cid}" if dirty else None,
            "branch": wt["branch"] if cand else None,
            "branch_kept": None if cand else wt["branch"],
        })
    return out


def remove(path: Path, root: Path) -> bool:
    """Remove `path`. Returns False (and leaves `path` untouched) when it is a
    `.arbeitsplan/<runId>` worktree root and at least one of its worktrees could not
    be preserved -- or could not even be enumerated -- fail closed (#80): a
    partially-preserved run is not rmtree'd out from under its own kept/ branch or
    its still-dirty sibling worktrees.

    Every REGISTERED worktree under the path goes through preserve_then_remove,
    whatever it is named; only what is left afterwards is rmtree'd."""
    if ".arbeitsplan" in path.parts:
        run_id = path.name
        try:
            worktrees = worktree_pool.worktrees_under(root, path)
        except worktree_pool.WorktreeListError as exc:
            print(f"  FAILED {path}: {exc}; nothing removed", file=sys.stderr)
            return False
        all_ok = True
        for wt in worktrees:
            result = worktree_pool.preserve_then_remove(root, run_id, wt["path"].name, wt["path"], wt["branch"])
            if not result["ok"]:
                all_ok = False
                print(f"  FAILED to preserve {wt['path'].name}: {result['error']}", file=sys.stderr)
            elif result["branchKept"]:
                print(f"  {wt['path'].name}: branch {result['branchKept']} left -- not a candidate branch of {run_id}")
        if not all_ok:
            return False
    if path.exists():
        shutil.rmtree(path)
    return True


def _selftest_real_worktrees() -> list:
    """Through git, with worktrees `create` would never name: every registered
    worktree is found and preserved, whatever its name, and only this run's candidate
    branches are deleted."""
    fails = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} worktrees: {name}" + ("" if cond or not detail else f" -- {detail}"))
        if not cond:
            fails.append(name)

    def git(repo: Path, *a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                              capture_output=True, text=True)

    rid = "ap-t-names"
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "f.txt").write_text("base\n")
        (root / ".gitignore").write_text("/analysis/\n/.arbeitsplan/\n")
        for a in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "base")):
            git(root, *a)
        wt = root / ".arbeitsplan" / rid
        git(root, "worktree", "add", "-q", "-b", f"arbeitsplan/{rid}/c1", str(wt / "c1"))
        git(root, "worktree", "add", "-q", "-b", f"arbeitsplan/{rid}/fix", str(wt / "fix"))
        git(root, "worktree", "add", "-q", "-b", "feature/mine", str(wt / "scratch"))
        (wt / "c1" / "u.txt").write_text("c1 work\n")
        (wt / "fix" / "f.txt").write_text("fix work\n")
        (wt / "fix" / "n.txt").write_text("fix untracked\n")
        run = run_record.open_run("arbeitsplan", rid, root)
        run.append({"trace_id": rid, "span_id": f"{rid}.b.o", "parent_span_id": f"{rid}.root",
                    "span": "phase build", "node_id": "build", "status": "opened"})
        run.append({"trace_id": rid, "span_id": f"{rid}.b.c", "parent_span_id": f"{rid}.root",
                    "span": "phase build", "node_id": "build", "status": "closed"})
        run.finish({"landed": "c1"})

        plan = {i["cid"]: i for i in plan_candidate_removals(root, wt, rid)}
        ok("the dry-run plan sees every registered worktree, not only c*", set(plan) == {"c1", "fix", "scratch"},
           str(sorted(plan)))
        ok("the plan preserves the dirty non-c* worktree", plan.get("fix", {}).get("kept_branch") == f"kept/{rid}-fix")
        ok("the plan leaves a branch that is not this run's candidate branch",
           plan.get("scratch", {}).get("branch") is None and plan.get("scratch", {}).get("branch_kept") == "feature/mine")

        prop = root / "proposal.json"
        prop.write_text(json.dumps({"remove": [{"path": f".arbeitsplan/{rid}"}]}))
        rc = main(["--root", str(root), "--proposal", str(prop), "--apply"])
        ok("--apply succeeds", rc == 0)
        ok("the non-c* worktree's tracked change is on kept/<run>-fix",
           git(root, "show", f"kept/{rid}-fix:f.txt").stdout == "fix work\n")
        ok("...and its untracked file too", git(root, "show", f"kept/{rid}-fix:n.txt").stdout == "fix untracked\n")
        ok("c1 is preserved as before", git(root, "show", f"kept/{rid}-c1:u.txt").stdout == "c1 work\n")
        branches = git(root, "branch", "--list", f"arbeitsplan/{rid}/*").stdout.split()
        ok("every candidate branch of the run is deleted, the non-c* one included", branches == [], str(branches))
        ok("a branch that is not this run's is never deleted",
           git(root, "rev-parse", "--verify", "-q", "feature/mine").returncode == 0)
        # Asked of git directly, not through worktrees_under() -- the function under test
        # must not be the instrument that grades it.
        listed = [ln for ln in git(root, "worktree", "list", "--porcelain").stdout.splitlines()
                  if ln.startswith("worktree ") and "/.arbeitsplan/" in ln]
        ok("no worktree is left registered under .arbeitsplan (no dangling metadata)", listed == [], str(listed))
        ok("the run's worktree directory is gone", not wt.exists())
    return fails


def selftest() -> int:
    fails = _selftest_real_worktrees()

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
        if not args.apply and ".arbeitsplan" in p.parts:
            try:
                plan = plan_candidate_removals(root, p, p.name)
            except worktree_pool.WorktreeListError as exc:
                print(f"    cannot list its worktrees ({exc}); --apply would remove nothing here")
                plan = []
            for info in plan:
                if info["dirty"]:
                    print(f"    would preserve {info['cid']}'s dirty state on {info['kept_branch']}")
                if info["branch"]:
                    print(f"    would delete branch {info['branch']}")
                elif info["branch_kept"]:
                    print(f"    would leave branch {info['branch_kept']} (not a candidate branch of {p.name})")
    if not args.apply:
        print(f"{len(eligible)} path(s); dry run -- nothing touched. Pass --apply to remove them.")
        return 0
    failed = 0
    for p, _ in eligible:
        try:
            if not remove(p, root):
                failed += 1
        except OSError as exc:
            failed += 1
            print(f"  FAILED {p}: {exc}", file=sys.stderr)
    print(f"removed {len(eligible) - failed} of {len(eligible)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
