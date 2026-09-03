#!/usr/bin/env python3
"""lehre's deterministic instrument: validate a ruleset, sweep a tree, close a unit.

    python3 lehre_cli.py validate  [--ruleset .lehre/ruleset.json]
    python3 lehre_cli.py gauge     [--root .] [--json] [--severity blocking|advisory|all]
    python3 lehre_cli.py close     <unit-id>       # writes .lehre/units/<id>.done
    python3 lehre_cli.py status    [--json]

Why a script and not skill prose: the same evaluator the PreToolUse hook uses
decides here, so a sweep and a denial can never disagree about one rule. A
skill that re-reasoned the rules in prose would produce a second, drifting
opinion -- which is the failure this plugin exists to remove, reintroduced one
level up.

Exit codes are a frozen contract:
    0  clean -- and for `gauge` that means BOTH no violations at the requested
       severity AND nothing left unevaluated
    1  the sweep did not come back clean: violations found, or a file could not
       be judged
    2  the ruleset itself is unusable (schema error, missing file)

Why an unevaluated file exits 1: a file that would not parse was not judged, and
CI reading exit 0 would record a rule as holding over a file the rule never
reached. That is a lucky pass reported as a real one -- the same shape as every
other silent failure this plugin guards against. The two cases stay
distinguishable in the output and in the JSON; they are merged only in the exit
code, where the single question is "did this sweep come back clean".
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lehre_core as core  # noqa: E402

EXIT_OK, EXIT_VIOLATIONS, EXIT_UNUSABLE = 0, 1, 2

#: Directories never worth sweeping. Skipped by exact name at any depth.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
             ".ruff_cache", ".pytest_cache", "dist", "build", ".lehre", ".tox", ".idea"}


def default_ruleset(root: str) -> str:
    return os.path.join(root, ".lehre", "ruleset.json")


def load_or_die(path: str) -> dict:
    if not os.path.isfile(path):
        print(f"lehre: no ruleset at {path}. Run lehre-codify first.", file=sys.stderr)
        sys.exit(EXIT_UNUSABLE)
    try:
        return core.load_ruleset(path)
    except (core.RulesetError, json.JSONDecodeError, ValueError) as exc:
        # Loud, never a degraded empty ruleset: a schema error that becomes
        # "no rules" is a doctrine that disables itself on a typo.
        print(f"lehre: ruleset is unusable -- {exc}", file=sys.stderr)
        sys.exit(EXIT_UNUSABLE)


def walk_files(root: str) -> tuple[list[str], list[str]]:
    """Every tracked-looking file, repo-relative, AND the directories that could
    not be read.

    os.walk, not Path.glob: glob swallows PermissionError on an unreadable
    directory and reports "nothing found", which is row four of CLAUDE.md's
    silent-defect table. os.walk surfaces the error through onerror.

    The problem list is RETURNED rather than only printed, because a warning on
    stderr that leaves the exit code at 0 is the same defect one level up: CI
    reads the exit code, not the warning, and would record a clean sweep over a
    tree the sweep never finished reading. The caller folds it into both the exit
    code and the JSON, exactly as it already does for unparseable files.
    """
    problems: list[str] = []

    def onerror(exc: OSError) -> None:
        problems.append(str(exc))

    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            found.append(core.relative(root, os.path.join(dirpath, name)))
    if problems:
        print(f"lehre: {len(problems)} director{'y' if len(problems) == 1 else 'ies'} "
              f"could not be read; the sweep below is INCOMPLETE:", file=sys.stderr)
        for problem in problems[:5]:
            print(f"  {problem}", file=sys.stderr)
    return sorted(found), problems


def read_text(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def run_linter(rule: dict, root: str, paths: list[str]) -> list[core.Violation]:
    """Gauge-tier check: run the declared argv and read its exit code.

    Never `shell=True`. The command is an argv list precisely so a rule cannot
    smuggle a shell metacharacter into an enforcement path.
    """
    targets = [p for p in paths if core.matches(p, rule["check"]["paths"])]
    if not targets:
        return []
    argv = list(rule["check"]["command"]) + targets
    try:
        proc = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        print(f"lehre: rule {rule['id']} names linter {argv[0]!r}, which is not installed. "
              f"Reporting as UNEVALUATED, not as clean.", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print(f"lehre: rule {rule['id']}'s linter timed out. UNEVALUATED, not clean.", file=sys.stderr)
        return []
    if proc.returncode == 0:
        return []
    detail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = detail[0][:160] if detail else f"{argv[0]} exited {proc.returncode}"
    return [core.Violation(rule["id"], rule["severity"], targets[0], None, summary, rule["rationale"])]


def cmd_validate(args) -> int:
    data = load_or_die(args.ruleset)
    hook_tier = sum(1 for r in data["rules"] if r["enforcement"] == "hook")
    blocking = sum(1 for r in data["rules"] if r["severity"] == "blocking")
    enforced = sum(1 for r in data["rules"] if r["severity"] == "blocking" and r["enforcement"] == "hook")
    print(f"ruleset OK: {len(data['rules'])} rule(s), {len(data['units'])} unit(s), mode={data['mode']}")
    print(f"  blocking: {blocking}   hook-tier: {hook_tier}   denied at write time: {enforced}")
    if blocking - enforced:
        print(f"  note: {blocking - enforced} blocking rule(s) are gauge-tier (linter checks). "
              f"They fail a sweep and CI, but do NOT deny a write.")
    judged = sum(1 for r in data["rules"] if r["enforcement"] == "judgement")
    if judged:
        print(f"  note: {judged} rule(s) are judgement-tier -- no machine can decide them. "
              f"lehre-gauge reports them for violation-auditor; they never deny and never "
              f"fail a sweep on their own.")
    by_mode: dict[str, int] = {}
    for rule in data["rules"]:
        by_mode[rule["sourceMode"]] = by_mode.get(rule["sourceMode"], 0) + 1
    print("  provenance: " + ", ".join(f"{k}={v}" for k, v in sorted(by_mode.items())))
    return EXIT_OK


def cmd_gauge(args) -> int:
    root = os.path.abspath(args.root)
    data = load_or_die(args.ruleset or default_ruleset(root))
    paths, unreadable = walk_files(root)
    wanted = data["rules"] if args.severity == "all" else [
        r for r in data["rules"] if r["severity"] == args.severity]

    violations: list[core.Violation] = []
    unparseable: list[str] = []
    content_cache: dict[str, str | None] = {}
    judgement: list[dict] = []
    for rule in wanted:
        if rule["check"]["kind"] == "judgement":
            # Not evaluable by anything here. Collected and REPORTED so the caller
            # can dispatch violation-auditor on it -- never silently skipped, which
            # is how a rule nobody checked becomes a rule counted as passing.
            targets = [pth for pth in paths if core.matches(pth, rule["check"]["paths"])]
            judgement.append({"rule_id": rule["id"], "asks": rule["check"]["asks"],
                              "rationale": rule["rationale"], "paths": rule["check"]["paths"],
                              "matching_files": targets})
            continue
        if rule["check"]["kind"] == "linter":
            violations.extend(run_linter(rule, root, paths))
            continue
        needs_content = rule["check"]["kind"] in ("python-import", "python-construct")
        for path in paths:
            if not core.matches(path, rule["check"]["paths"]):
                continue
            content = None
            if needs_content:
                if path not in content_cache:
                    content_cache[path] = read_text(os.path.join(root, path))
                content = content_cache[path]
                if content is None:
                    continue
            try:
                violations.extend(core.evaluate_file(rule, path, content))
            except core.UnparseablePython:
                # Reported separately: "could not be judged" is not "clean",
                # and collapsing the two is how a sweep quietly under-reports.
                unparseable.append(f"{path} (rule {rule['id']})")

    if args.json:
        print(json.dumps({
            "violations": [v.as_dict() for v in violations],
            "unevaluated_unparseable": sorted(set(unparseable)),
            "unreadable_directories": unreadable,
            "needs_judgement_pass": judgement,
            "sweep_complete": not unreadable,
            "files_swept": len(paths),
            "rules_applied": len(wanted),
        }, indent=2))
    else:
        for violation in violations:
            print(violation)
        for item in sorted(set(unparseable)):
            print(f"[UNEVALUATED] {item} -- would not parse, so the rule could not be decided")
        for item in judgement:
            print(f"[JUDGEMENT] {item['rule_id']} -- not machine-checkable; "
                  f"{len(item['matching_files'])} file(s) in scope. Asks: {item['asks']}")
        blocking = sum(1 for v in violations if v.severity == "blocking")
        print(f"\n{len(violations)} violation(s) ({blocking} blocking) across {len(paths)} file(s); "
              f"{len(set(unparseable))} file(s) could not be evaluated"
              + (f"; {len(unreadable)} director(y/ies) UNREADABLE -- sweep INCOMPLETE"
                 if unreadable else "")
              + (f"; {len(judgement)} rule(s) need a judgement pass (dispatch violation-auditor)"
                 if judgement else ""))
    return EXIT_VIOLATIONS if (violations or unparseable or unreadable) else EXIT_OK


def cmd_close(args) -> int:
    root = os.path.abspath(args.root)
    data = load_or_die(args.ruleset or default_ruleset(root))
    unit_ids = {u["id"] for u in data["units"]}
    if args.unit not in unit_ids:
        print(f"lehre: no unit {args.unit!r}. Declared units: {sorted(unit_ids)}", file=sys.stderr)
        return EXIT_UNUSABLE
    marker = core.unit_done_marker(root, args.unit)
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("closed by lehre-validate\n")
    print(f"unit {args.unit!r} closed; writes into units depending on it are now permitted")
    return EXIT_OK


def cmd_status(args) -> int:
    root = os.path.abspath(args.root)
    data = load_or_die(args.ruleset or default_ruleset(root))
    rows = []
    for unit in data["units"]:
        done = os.path.exists(core.unit_done_marker(root, unit["id"]))
        pending = core.blocking_dependencies(root, unit)
        rows.append({"id": unit["id"], "validated": done,
                     "blocked_by": pending,
                     "state": "validated" if done else ("blocked" if pending else "ready")})
    if args.json:
        print(json.dumps({"mode": data["mode"], "units": rows,
                          "rules": len(data["rules"])}, indent=2))
    else:
        print(f"mode={data['mode']}  rules={len(data['rules'])}")
        for row in rows:
            suffix = f" (blocked by {', '.join(row['blocked_by'])})" if row["blocked_by"] else ""
            print(f"  [{'x' if row['validated'] else ' '}] {row['id']:<24} {row['state']}{suffix}")
    return EXIT_OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="lehre_cli.py",
                                     description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--ruleset", default=None, help="path to ruleset.json")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="check the ruleset parses and report its enforcement tiers")
    gauge = sub.add_parser("gauge", help="sweep the tree for violations")
    gauge.add_argument("--json", action="store_true")
    gauge.add_argument("--severity", choices=["blocking", "advisory", "all"], default="all")
    close = sub.add_parser("close", help="mark a unit validated (writes its done-marker)")
    close.add_argument("unit")
    status = sub.add_parser("status", help="show unit build state")
    status.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.ruleset is None:
        args.ruleset = default_ruleset(os.path.abspath(args.root))
    return {"validate": cmd_validate, "gauge": cmd_gauge,
            "close": cmd_close, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
