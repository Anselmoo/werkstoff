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
with what `git diff` shows for the same paths afterwards -- files the diff
created included (applied_diff); when they differ it
carries `divergedFrom`, so a correction made at landing is recorded rather than
leaving candidates/<id>.json describing a diff that is not what landed.

`--apply` also gates on MEASUREMENT (#76): for every checked criterion of the run's
acceptance (phases/contract.json over workflow.json, the same precedence
reconcile.py's `acceptance()` reads), this candidate must own at least one
`execute_tool` event -- `detail.candidate == this candidate` -- recorded by
`reconcile.py --run-checks --candidate --tree`, and its LATEST measured exits for
every element must agree with what `candidates/<id>.json` itself reported FOR THAT
CRITERION ID. A criterion with no such event (unmeasured), or one whose reported
exit(s) actually disagree with what was measured for its id (contradicted), refuses
the landing -- naming `reconcile.py` and `--run-checks` as the remedy. Another
candidate's measurement never counts: the field checked is `detail.candidate`, not
"this criterion was measured by somebody". An honestly reported failure (reported
non-zero, measured the same non-zero) is NOT refused here -- this gate is
"unmeasured or contradicted", nothing more; a referee's `accepted` verdict already
decided whether a failing criterion still lands.

(#76 amendment) A contradiction is a REPORTED exit that disagrees with the measured
one -- `contradicts()` below is the one comparator both this gate and reconcile.py's
`measure_candidate()` call, so they cannot diverge again. Two things that are NOT
contradictions: the builder's own spelling of the command (grouping is by criterion
id only -- the measured side always uses the contract's own command, so a builder's
relative path, placeholder or comment never becomes a lookup key), and a criterion
the builder never reported at all (an empty reported list carries no claim, so there
is nothing to disagree with; it still needs its own measurement or the criterion
stays "missing", never "contradicted").

Every refusal this script makes is also RECORDED: an `execute_tool land_candidate`
event, status `refuted`, node_id the candidate -- so a rejected landing is as
visible in run.jsonl as an accepted one always was.

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
import time
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


class CheckShapeError(ValueError):
    """Raised by checks_of() when `check` is neither None, a non-empty string,
    nor a non-empty list of non-empty strings."""


def checks_of(check: object) -> list:
    """Normalize an acceptance criterion's `check` field (#81) to an ordered list
    of shell commands, each run independently via /bin/sh; a criterion passes
    only when every element exits 0.

    THE normalizer: compile_spec.py imports this for validation (AP-CHECK-SHAPE)
    and --probe-checks, reconcile.py imports it for measure(), and workflows/run.js
    carries its own copy (checksOf) for the same reason it cannot import Python --
    but all readers agree on the same three legal shapes because they all trace
    back to the rule written here.

    * `None` (the key absent or explicitly null) -- no runnable check. Returns [].
    * a non-empty string -- one command. Returns [check].
    * a non-empty list whose every element is a non-empty string -- returns
      list(check) unchanged, each element run independently.

    Anything else (a number, an object, an empty string, an empty list, or a
    list containing a non-string or empty-string element) raises CheckShapeError
    with a message naming what was wrong; the caller decides what that means.
    """
    if check is None:
        return []
    if isinstance(check, str):
        if not check.strip():
            raise CheckShapeError("an empty string carries no command")
        return [check]
    if isinstance(check, list):
        if not check:
            raise CheckShapeError("an empty list carries no command")
        if not all(isinstance(c, str) and c.strip() for c in check):
            raise CheckShapeError("every element of a check list must be a non-empty string")
        return list(check)
    raise CheckShapeError(
        f"must be a string, a non-empty list of strings, or null; got {type(check).__name__}")


def contradicts(reported_exits: list, measured_exits: list) -> bool:
    """THE ONE comparator for #76: a contradiction is a REPORTED exit that disagrees
    with the measured one, nothing else. `measurement_refusal()` below and
    reconcile.py's `measure_candidate()` both call this instead of comparing the
    lists themselves, so the two gates cannot drift apart again.

    `reported_exits == []` means the builder made no claim about this criterion at
    all (an id it never listed in its own `checks[]`) -- unreported is not a lie,
    so there is nothing to contradict; the criterion still needs its own
    measurement, or it stays "missing" to whichever caller tracks that. Any other
    `reported_exits` is compared to `measured_exits` ordered, element by element:
    an all-zero array report with one measured failing element is still a
    contradiction, and a genuinely different single exit still is too.
    """
    if reported_exits == []:
        return False
    return reported_exits != measured_exits


def applied_diff(paths: list, cwd: str | None = None) -> str:
    """What landed at `paths`, as a diff -- INCLUDING files the candidate created.

    `git apply` leaves a new file untracked, so a plain `git diff -- paths` omits
    it, and landing_record() then reported every added line as `onlyRecorded`: a
    divergence that never happened (run ap-2026-09-22-6cb2: 16 new files, 40
    lines, all 23 paths byte-identical to the winner). Untracked paths are diffed
    against /dev/null with --no-index, which reads the working tree and never
    touches the index -- `git add -N` would fix the comparison by staging, and
    landing stages nothing.
    """
    tracked = subprocess.run(["git", "diff", "--", *paths], capture_output=True,
                             text=True, cwd=cwd).stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--", *paths],
                               capture_output=True, text=True, cwd=cwd).stdout.splitlines()
    # --no-index exits 1 whenever the two sides differ, which for a new file is
    # always; the exit code carries nothing here, the output is the result.
    created = [subprocess.run(["git", "diff", "--no-index", "--", "/dev/null", p],
                              capture_output=True, text=True, cwd=cwd).stdout
               for p in untracked]
    return tracked + "".join(created)


def _selftest_landing_in_a_repo() -> list:
    """A real --apply, in a throwaway repo, of a diff that edits one file and
    CREATES another. The recorded-vs-landed comparison only goes wrong once git
    is involved, so it is tested through git rather than through literals."""
    import tempfile
    fails = []
    diff = ("diff --git a/src/a.txt b/src/a.txt\n--- a/src/a.txt\n+++ b/src/a.txt\n"
            "@@ -1 +1 @@\n-old\n+new\n"
            "diff --git a/src/new.txt b/src/new.txt\nnew file mode 100644\n"
            "--- /dev/null\n+++ b/src/new.txt\n@@ -0,0 +1,2 @@\n+created\n+by the candidate\n")
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "src").mkdir()
        (repo / "src" / "a.txt").write_text("old\n")
        (repo / ".gitignore").write_text("/analysis/\n")
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(cmd, cwd=repo, capture_output=True, check=True)
        run = repo / "analysis" / "arbeitsplan" / "r1"
        for sub in ("candidates", "referee"):
            (run / sub).mkdir(parents=True)
        (run / "workflow.json").write_text(json.dumps({"runId": "r1", "writeScope": ["src/**"]}))
        (run / "candidates" / "c1.json").write_text(json.dumps({"measured": True, "diff": diff}))
        (run / "referee" / "c1.json").write_text(json.dumps({"verdict": "accepted"}))
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--run", "r1",
                            "--candidate", "c1", "--apply"], cwd=repo, capture_output=True, text=True)
        landed = run / "landed.json"
        rec = json.loads(landed.read_text()) if landed.is_file() else None
        for name, ok in [
            ("a diff that creates a file lands", r.returncode == 0 and rec is not None),
            ("...and is NOT recorded as divergedFrom", rec is not None and "divergedFrom" not in rec),
        ]:
            print(f"  {'ok  ' if ok else 'FAIL'} landing in a repo: {name}"
                  + ("" if ok else f" -- exit {r.returncode}: {r.stderr.strip()[-200:]}"))
            if not ok:
                fails.append(name)
        # A correction made AFTER apply, to the created file, is a genuine
        # divergence and must still be recorded -- the fix must not blind it.
        (repo / "src" / "new.txt").write_text("created\nand then edited at landing\n")
        again = landing_record("r1", "c1", diff, applied_diff(["src/a.txt", "src/new.txt"], cwd=str(repo)),
                               ["src/a.txt", "src/new.txt"])
        ok = "divergedFrom" in again
        print(f"  {'ok  ' if ok else 'FAIL'} landing in a repo: a new file edited after apply "
              f"IS recorded as divergedFrom")
        if not ok:
            fails.append("new file edited after apply is recorded")
    return fails


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def acceptance_criteria(run_dir: Path) -> list:
    """The run's acceptance, same precedence reconcile.py's `acceptance()` reads:
    a CONTRACT phase's `phases/contract.json` when one ran, `workflow.json`
    otherwise. Kept local rather than imported -- reconcile.py already imports
    THIS module (for `checks_of`), so the reverse import would be circular at
    module load time."""
    contract = _read_json(run_dir / "phases" / "contract.json")
    if contract and isinstance(contract.get("acceptance"), list):
        return contract["acceptance"]
    spec = _read_json(run_dir / "workflow.json") or {}
    return (spec.get("problem") or {}).get("acceptance") or []


def measured_elements(run: run_record.Run, candidate_id: str, criterion_id: str) -> dict:
    """The LATEST measured exit per command, for `criterion_id`, recorded under
    `detail.candidate == candidate_id` -- never another candidate's. Events are
    read in file order, so a later re-measurement overwrites an earlier one."""
    out: dict = {}
    for e in run.events():
        if not str(e.get("span", "")).startswith("execute_tool "):
            continue
        detail = e.get("detail") or {}
        if e.get("node_id") != criterion_id or detail.get("candidate") != candidate_id:
            continue
        cmd = detail.get("command")
        if cmd is not None:
            out[cmd] = detail.get("exit")
    return out


def measurement_refusal(run: run_record.Run, candidate_id: str, candidate: dict) -> str | None:
    """None when every checked criterion is both measured for THIS candidate and
    agrees with what `candidate` (the parsed candidates/<id>.json) reported;
    otherwise a refusal message naming reconcile.py --run-checks as the remedy.

    (#76 amendment) Reported exits are grouped by CRITERION ID ONLY -- never keyed
    by the builder's own command string, which the builder is free to spell however
    it likes (a relative path, a placeholder, a comment). Measured exits are read
    in `checks_of(crit["check"])` order, i.e. the contract's own command spelling,
    since that is the only spelling `measured_elements()` was ever recorded under.
    `contradicts()` is the one place the two lists are compared, so this gate and
    reconcile.py's `measure_candidate()` cannot disagree about what counts.
    """
    reported_by_id: dict = {}
    for r in candidate.get("checks") or []:
        if isinstance(r, dict):
            reported_by_id.setdefault(r.get("id"), []).append(r.get("exit"))
    missing, contradicted = [], []
    for crit in acceptance_criteria(run.dir):
        cid = crit.get("id")
        try:
            cmds = checks_of(crit.get("check"))
        except CheckShapeError:
            continue  # a malformed check is compile_spec's AP-CHECK-SHAPE to catch, not this gate's
        if not cmds:
            continue
        measured = measured_elements(run, candidate_id, cid)
        if any(cmd not in measured for cmd in cmds):
            missing.append(cid)
            continue
        measured_exits = [measured[cmd] for cmd in cmds]
        reported_exits = reported_by_id.get(cid, [])
        if contradicts(reported_exits, measured_exits):
            contradicted.append(cid)
    missing, contradicted = sorted(set(missing)), sorted(set(contradicted))
    if not missing and not contradicted:
        return None
    parts = []
    if missing:
        parts.append(f"unmeasured criterion/a(s) {missing}")
    if contradicted:
        parts.append(f"contradicted criterion/a(s) {contradicted} (reported vs. measured disagree)")
    return (
        f"REFUSED: {candidate_id} has {' and '.join(parts)}. Measure this candidate's own tree "
        f"first: reconcile.py --run <runId> --run-checks --candidate {candidate_id} --tree "
        "<candidate's worktree>. Another candidate's measurement never unlocks this one, and an "
        "honestly-reported failure is not refused here -- only unmeasured or contradicted is."
    )


def record_refusal(run_id: str, candidate_id: str, message: str) -> None:
    """Every refusal is recorded, not just an accepted landing (previously the
    only outcome run.jsonl ever carried). Best-effort: a run whose record cannot
    be opened still refuses the landing on stderr; it just cannot also log it."""
    try:
        run = run_record.open_run("arbeitsplan", run_id)
        run.append({"trace_id": run_id,
                    "span_id": f"{run_id}.land_candidate.{candidate_id}.refused.{time.time_ns()}",
                    "parent_span_id": f"{run_id}.root", "span": "execute_tool land_candidate",
                    "node_id": candidate_id, "status": "refuted",
                    "detail": {"reason": message[:500]}})
    except run_record.RecordError:
        pass


def refuse(run_id: str, candidate_id: str, message: str) -> int:
    print(message, file=sys.stderr)
    record_refusal(run_id, candidate_id, message)
    return 1


def _selftest_measurement_gate() -> list:
    """measurement_refusal() (#76), unit-level: unmeasured, contradicted, honestly
    failing, and another candidate's measurement never counting -- in-process
    against a throwaway run.jsonl, no subprocess needed for this part."""
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as raw:
        cwd = Path.cwd()
        try:
            os.chdir(raw)
            run = run_record.open_run("arbeitsplan", "r-gate")
            (run.dir / "workflow.json").write_text(json.dumps({"problem": {"acceptance": [
                {"id": "a1", "criterion": "c", "check": "true"},
                {"id": "a2", "criterion": "c2", "check": "false"}]}}))

            report = {"checks": [{"id": "a1", "command": "true", "exit": 0},
                                  {"id": "a2", "command": "false", "exit": 1}]}
            ok0 = measurement_refusal(run, "c1", report) is not None
            print(f"  {'ok  ' if ok0 else 'FAIL'} measurement gate: no measurement at all -> refused")
            if not ok0:
                fails.append("no measurement at all")

            def measure_evt(cid: str, crit: str, cmd: str, exit_code: int) -> None:
                run.append({"trace_id": "r-gate", "span_id": f"r-gate.{cid}.{crit}.{cmd}.{exit_code}.{time.time_ns()}",
                            "parent_span_id": "r-gate.root", "span": f"execute_tool {crit}",
                            "node_id": crit, "status": "accepted" if exit_code == 0 else "refuted",
                            "detail": {"id": crit, "candidate": cid, "command": cmd, "exit": exit_code}})

            measure_evt("c1", "a1", "true", 0)
            measure_evt("c1", "a2", "false", 1)  # matches report: honestly failing
            ok1 = measurement_refusal(run, "c1", report) is None
            print(f"  {'ok  ' if ok1 else 'FAIL'} measurement gate: fully measured, honest -> not refused")
            if not ok1:
                fails.append("fully measured honest")

            report_lying = {"checks": [{"id": "a1", "command": "true", "exit": 0},
                                        {"id": "a2", "command": "false", "exit": 0}]}  # lied: claims a2 passed
            ok2 = measurement_refusal(run, "c1", report_lying) is not None
            print(f"  {'ok  ' if ok2 else 'FAIL'} measurement gate: measured but contradicted -> refused")
            if not ok2:
                fails.append("contradicted")

            ok3 = measurement_refusal(run, "c2", report) is not None
            print(f"  {'ok  ' if ok3 else 'FAIL'} measurement gate: c1's measurement does not cover c2")
            if not ok3:
                fails.append("another candidate's measurement does not unlock")

            measure_evt("c1", "a2", "false", 0)  # a LATER re-measurement, now agreeing with the lie
            ok4 = measurement_refusal(run, "c1", report_lying) is None
            print(f"  {'ok  ' if ok4 else 'FAIL'} measurement gate: the LATEST measurement wins over a stale one")
            if not ok4:
                fails.append("latest measurement wins")

            # (#76 amendment) a different command spelling for the same id is not a
            # contradiction -- comparison is by criterion id only.
            report_diff_spelling = {"checks": [
                {"id": "a1", "command": "cd /tmp && true  # the builder's own spelling", "exit": 0},
                {"id": "a2", "command": "false", "exit": 0}]}  # both agree with the last measured exits
            ok5 = measurement_refusal(run, "c1", report_diff_spelling) is None
            print(f"  {'ok  ' if ok5 else 'FAIL'} measurement gate: a different command spelling "
                  "for the same id is not a contradiction")
            if not ok5:
                fails.append("different command spelling is not a contradiction")

            # an unreported criterion (measured, but absent from the builder's own
            # checks[]) is not a contradiction either -- it is unreported, not a lie.
            report_partial = {"checks": [{"id": "a1", "command": "true", "exit": 0}]}  # a2 never reported
            ok6 = measurement_refusal(run, "c1", report_partial) is None
            print(f"  {'ok  ' if ok6 else 'FAIL'} measurement gate: an unreported (but measured) "
                  "criterion is not a contradiction")
            if not ok6:
                fails.append("unreported criterion is not a contradiction")
        finally:
            os.chdir(cwd)
    return fails


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
        contradicts_cases = [
            ("an unreported criterion (empty reported list) is never a contradiction",
                [], [1], False),
            ("a matching scalar report is not a contradiction", [0], [0], False),
            ("a disagreeing scalar report IS a contradiction", [1], [0], True),
            ("a matching array report is not a contradiction", [0, 0], [0, 0], False),
            ("an all-zero array report with one failing element IS a contradiction",
                [0, 0], [0, 1], True),
        ]
        for name, reported, measured, want in contradicts_cases:
            got = contradicts(reported, measured)
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} contradicts {name}: {got}")
            if not ok:
                fails.append(name)
        checks_of_cases = [
            ("null -> no runnable check", None, []),
            ("a non-empty string -> one command", "true", ["true"]),
            ("a non-empty list -> every element, in order", ["true", "pytest -q x"],
                ["true", "pytest -q x"]),
        ]
        for name, check, want in checks_of_cases:
            got = checks_of(check)
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} checks_of {name}: {got}")
            if not ok:
                fails.append(name)
        checks_of_rejects = [
            ("an int", 42), ("an object", {}), ("an empty string", ""),
            ("an empty list", []), ("a list with an empty string", [""]),
            ("a list with a non-string element", ["true", 3]),
        ]
        for name, check in checks_of_rejects:
            try:
                checks_of(check)
                ok = False
            except CheckShapeError:
                ok = True
            print(f"  {'ok  ' if ok else 'FAIL'} checks_of rejects {name}")
            if not ok:
                fails.append(f"checks_of rejects {name}")
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
        fails += _selftest_landing_in_a_repo()
        fails += _selftest_measurement_gate()
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
        return refuse(args.run, args.candidate,
                      f"REFUSED: {args.candidate} is unmeasured -- it was never fairly tried, so "
                      "there is nothing to land.")

    # The workflow's landing allowlist lived only in run.js, so THIS entry point
    # would apply a rejected -- or never judged -- diff. The referee record is
    # the authority, and `accepted` is an allowlist: `rejected` and
    # `cannot_judge` are never collapsed into each other, and a missing record
    # is not read as consent.
    verdict_path = Path(args.root) / args.run / "referee" / f"{args.candidate}.json"
    try:
        referee = json.loads(verdict_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return refuse(args.run, args.candidate,
                      f"REFUSED: no referee record at {verdict_path}. A candidate nothing judged "
                      "is not an accepted candidate; run the referee pass before landing.")
    except ValueError as exc:
        return refuse(args.run, args.candidate,
                      f"REFUSED: the referee record at {verdict_path} is unreadable ({exc}). "
                      "Refusing rather than landing on an unverifiable verdict.")
    seen = referee.get("verdict")
    if seen != "accepted":
        return refuse(args.run, args.candidate,
                      f"REFUSED: {args.candidate}'s referee verdict is {seen!r}, and only "
                      "'accepted' lands. 'rejected' says the candidate is wrong; 'cannot_judge' "
                      "says nothing is known, which points at the criteria rather than the "
                      "candidate. Neither is consent.")

    # #76: unmeasured-or-contradicted, gated on THIS candidate's own recorded
    # execute_tool events -- never on another candidate's, and never blocking an
    # honestly-reported failure a referee already accepted alongside.
    try:
        run = run_record.open_run("arbeitsplan", args.run)
        refusal = measurement_refusal(run, args.candidate, candidate)
    except run_record.RecordError as exc:
        return refuse(args.run, args.candidate,
                      f"REFUSED: the run record cannot be read ({exc}); measurement cannot be "
                      "verified, so this candidate is not landed.")
    if refusal:
        return refuse(args.run, args.candidate, refusal)

    diff = candidate.get("diff") or ""
    if not diff.strip():
        return refuse(args.run, args.candidate, f"REFUSED: {args.candidate} carries no diff.")

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
        return refuse(args.run, args.candidate,
                      f"REFUSED: {args.candidate} touches refereeOwned path(s) {owned_touch}. "
                      "These are written once, before any candidate exists, by a referee-fixture "
                      "phase, and are subtracted from every fan-out phase's effective write scope. "
                      "A diff that reaches one anyway is refused rather than landed, whether or not "
                      "the guard should have stopped it earlier.")

    out_of_scope = [p for p in diff_paths if not in_scope(p, scope)]
    if out_of_scope:
        return refuse(args.run, args.candidate,
                      f"REFUSED: {args.candidate} touches {out_of_scope} outside the declared "
                      f"writeScope {scope}. The scope is the contract this candidate was "
                      "dispatched under.")

    check = subprocess.run(["git", "apply", "--check", "-"], input=diff,
                           capture_output=True, text=True)
    if check.returncode != 0:
        return refuse(args.run, args.candidate,
                      f"REFUSED: {args.candidate}'s diff does not apply cleanly.\n"
                      f"{check.stderr.strip()}\n"
                      "Not retrying with --3way: the tree moved under this candidate, so it was "
                      "measured against a state that no longer exists and its referee verdict no "
                      "longer means what it said. Re-run the phase against the current tree.")

    if not args.apply:
        print(f"{args.candidate} would apply cleanly, {len(diff_paths)} path(s), "
              "all in scope (not applied; pass --apply)")
        return 0

    applied = subprocess.run(["git", "apply", "-"], input=diff, capture_output=True, text=True)
    if applied.returncode != 0:
        return refuse(args.run, args.candidate,
                      f"REFUSED: apply failed after a clean --check: {applied.stderr.strip()}")

    paths = paths_in_diff(diff)
    rec = landing_record(args.run, args.candidate, diff, applied_diff(paths), paths)
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
