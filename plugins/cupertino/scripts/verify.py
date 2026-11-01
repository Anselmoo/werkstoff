#!/usr/bin/env python3
"""Decide whether a repair is done: re-run every baseline probe, compare, attribute every change.

usage: verify.py [-h] [--run RUN_ID] [--no-report]

Repeats baseline.py's observations into after/ and judges each check against its
baseline observation. Then it accounts for every file in scope that changed: a change
no approved item names is an OUT-OF-SCOPE change, which is a regression even if every
check passes -- "fixed it but broke something else" is exactly the failure this
route exists to catch.

Verdict (written to verdict.json, appended to verdicts.jsonl):
  done       every acceptance and mustPreserve check passes, nothing "not run",
             no out-of-scope change, no new console error
  regressed  a mustPreserve check fails, a file changed outside the changeset, a
             deleted file is not in the trash manifest, or a page logs more console
             errors than at baseline
  partial    anything else -- including any check that could not run here. A check
             that did not run is never counted as a pass.

Rounds: three verdicts that are not `done` make the third one HALT. The skill then
offers to restore (apply_delete.py --restore, git checkout of the changed paths) or
to widen the objective with the user -- never a fourth blind attempt.

Also renders .cupertino/repair/<run>/repair-report.html (build_repair_html.py).

Exit: 0 done; 1 partial or regressed (see verdict.json); 2 refused (no run, unapproved, item still active).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probes  # noqa: E402
from baseline import all_checks, snapshot  # noqa: E402
from repair_lib import (  # noqa: E402
    WRITE_OPS,
    RepairError,
    active_run,
    approved_changeset,
    check_objective_frozen,
    project_root,
    read_json,
    run_dir,
    write_json,
)

MAX_ROUNDS = 3


def attribute(base_files: dict, after_files: dict, changeset: dict, trash: dict) -> dict:
    added = sorted(set(after_files) - set(base_files))
    removed = sorted(set(base_files) - set(after_files))
    modified = sorted(p for p in set(base_files) & set(after_files) if base_files[p] != after_files[p])
    owner = {}
    for item in changeset["items"]:
        for p in item["paths"]:
            owner.setdefault(Path(p).as_posix(), []).append(item)
    trashed = {e["path"] for e in trash.get("entries", []) if not e.get("restored")}
    changes, out_of_scope = [], []
    for kind, paths in (("added", added), ("modified", modified), ("removed", removed)):
        for p in paths:
            items = owner.get(p, [])
            ok_ops = ("delete",) if kind == "removed" else WRITE_OPS
            match = [i["id"] for i in items if i["op"] in ok_ops]
            entry = {"path": p, "change": kind, "items": match}
            if kind == "removed" and match and p not in trashed:
                entry["problem"] = "removed without apply_delete.py -- not restorable"
            if not match:
                entry["problem"] = "no approved item names this change"
            changes.append(entry)
            if "problem" in entry:
                out_of_scope.append(entry)
    untouched = [i["id"] for i in changeset["items"] if i["op"] in (*WRITE_OPS, "delete")
                 and not any(c["path"] in [Path(p).as_posix() for p in i["paths"]] for c in changes)]
    return {"changes": changes, "outOfScope": out_of_scope, "itemsWithNoEffect": untouched}


def verify(root: Path, run_id: str) -> dict:
    rdir = run_dir(root, run_id)
    # First: grading against an objective the baseline never measured is the worst outcome.
    check_objective_frozen(root, run_id)
    changeset = approved_changeset(root, run_id)
    if (rdir / "active-item").is_file():
        raise RepairError(f"item {(rdir / 'active-item').read_text(encoding='utf-8').strip()} is still active -- finish-item it first")
    objective = read_json(rdir / "objective.json")
    base = read_json(rdir / "baseline" / "baseline.json")
    # A run that crashes from here on must leave NO verdict, not the previous round's:
    # `repair_state.py end` accepts whatever verdict.json it finds, and a stale `done`
    # read as this round's result is exactly the failed-run trap CLAUDE.md names.
    (rdir / "verdict.json").unlink(missing_ok=True)
    after = snapshot(root, objective, rdir / "after")
    write_json(rdir / "after" / "after.json", after)

    checks, console_regressions = [], []
    for group, cid, check in all_checks(objective):
        label = f"{group}-{cid}"
        b, a = base["observations"].get(label), after["observations"][label]
        result = probes.judge(check, a, b, rdir / "after", rdir / "baseline")
        crit = next(c["criterion"] for c in objective[group] if c["id"] == cid)
        checks.append({"group": group, "id": cid, "criterion": crit, "kind": check["kind"], **result,
                       "before": (b or {}).get("screenshot"), "after": a.get("screenshot")})
        if check["kind"] == "web" and b and b.get("driver") == "playwright" and a.get("driver") == "playwright":
            nb = len(b.get("consoleErrors", [])) + len(b.get("failedRequests", []))
            na = len(a.get("consoleErrors", [])) + len(a.get("failedRequests", []))
            if na > nb:
                console_regressions.append({"check": label, "before": nb, "after": na,
                                            "new": (a.get("consoleErrors", []) + a.get("failedRequests", []))[:5]})

    trash_path = rdir / "trash" / "manifest.json"
    attribution = attribute(base["files"], after["files"], changeset,
                            read_json(trash_path) if trash_path.is_file() else {})
    acc = [c for c in checks if c["group"] == "acceptance"]
    pres = [c for c in checks if c["group"] == "mustPreserve"]
    reasons = []
    if any(c["state"] == "fail" for c in pres):
        reasons.append("a mustPreserve check fails")
    if attribution["outOfScope"]:
        reasons.append(f"{len(attribution['outOfScope'])} change(s) outside the approved changeset")
    if console_regressions:
        reasons.append("new console errors since the baseline")
    if reasons:
        verdict = "regressed"
    elif all(c["state"] == "pass" for c in checks):
        verdict = "done"
    else:
        verdict = "partial"
        reasons.extend(f"{c['group']} {c['id']}: {c['state']} -- {c['detail']}" for c in checks if c["state"] != "pass")

    history = rdir / "verdicts.jsonl"
    prior = history.read_text(encoding="utf-8").splitlines() if history.is_file() else []
    rnd = len(prior) + 1
    halt = verdict != "done" and rnd >= MAX_ROUNDS
    result = {
        "runId": run_id, "round": rnd, "verdict": verdict, "halt": halt, "reasons": reasons,
        "objective": objective["objective"], "nonGoals": objective.get("nonGoals", []),
        "acceptance": {"pass": sum(c["state"] == "pass" for c in acc), "total": len(acc)},
        "mustPreserve": {"pass": sum(c["state"] == "pass" for c in pres), "total": len(pres)},
        "checks": checks, "consoleRegressions": console_regressions, **attribution,
        "changeset": changeset["items"], "at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    write_json(rdir / "verdict.json", result)
    with history.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"round": rnd, "verdict": verdict, "at": result["at"]}) + "\n")
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="verify.py", description="Re-run every probe, compare to the baseline, attribute every change.",
                                     epilog="exit 0 done, 1 partial or regressed, 2 refused")
    parser.add_argument("--run", help="run id (default: the active run)")
    parser.add_argument("--no-report", action="store_true", help="skip rendering repair-report.html")
    args = parser.parse_args(argv)
    root = project_root()
    try:
        run_id = args.run or active_run(root)
        if not run_id:
            raise RepairError("no repair run is active")
        result = verify(root, run_id)
    except RepairError as err:
        print(f"verify: {err}", file=sys.stderr)
        return 2
    report = None
    if not args.no_report:
        from build_repair_html import build_report
        report = build_report(root, run_id)
    print(json.dumps({"runId": run_id, "round": result["round"], "verdict": result["verdict"], "halt": result["halt"],
                      "reasons": result["reasons"], "report": str(report) if report else None}, indent=2))
    if result["halt"]:
        print(f"HALT: {MAX_ROUNDS} rounds without `done`. Offer the user: restore (apply_delete.py --restore and "
              "`git checkout -- <changed paths>`), or widen the objective together. Do not attempt a fourth round.",
              file=sys.stderr)
    return 0 if result["verdict"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
