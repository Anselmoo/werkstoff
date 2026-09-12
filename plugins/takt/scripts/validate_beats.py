#!/usr/bin/env python3
"""Validate a .claude/takt.local.md beat declaration.

takt's guard is deliberately forgiving about a malformed beat: a beat that
gates nothing is silently skipped, because refusing to evaluate the other
beats because one is wrong would be worse. That forgiveness is correct at
runtime and dangerous at authoring time -- and it became more dangerous the
moment declarations started being GENERATED (arbeitsplan compiles them), since
a generator bug produces a file that looks enforced and enforces nothing.

This script is the authoring-time counterpart: it reports what the guard
tolerates. It never edits the file.

usage: validate_beats.py [-h] [--selftest] [declaration]

Exit: 0 clean, 1 errors found, 2 the file could not be read at all.

  python3 plugins/takt/scripts/validate_beats.py .claude/takt.local.md
  python3 plugins/takt/scripts/validate_beats.py --selftest

STDLIB ONLY -- it must run under a bare system python3, for the same reason
the guard hand-rolls its own parsing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
DISPATCH_TOOLS = ("Skill", "Task", "Agent")
KNOWN_TOOLS = set(EDIT_TOOLS) | set(DISPATCH_TOOLS)
# `(?!\.+\Z)` rejects a runId that is nothing but dots. Without it "." matched,
# and <root>/<runId> then normalises to <root> itself -- a run whose state aliases
# the unnamespaced directory and every other run's stale files, which is exactly
# the isolation runId exists to provide. ".." was already blocked; "." was not.
RUN_ID_RE = re.compile(r"\A(?!\.+\Z)(?!.*\.\.)[A-Za-z0-9._-]{1,64}\Z")


def load(path: Path) -> dict:
    """Mirror takt_guard.load_declaration's parsing exactly: first fenced json
    block, found by string search, never regex."""
    text = path.read_text(encoding="utf-8")
    start = text.find("```json")
    if start == -1:
        raise ValueError("no fenced ```json block -- takt reads nothing from this file")
    body_start = text.index("\n", start) + 1
    end = text.find("```", body_start)
    if end == -1:
        raise ValueError("unterminated ```json fence")
    return json.loads(text[body_start:end])


def validate(decl: dict) -> list:
    errors: list = []

    def err(where: str, msg: str) -> None:
        errors.append(f"{where}: {msg}")

    run_id = decl.get("runId", "")
    if run_id is None:
        run_id = ""
    if not isinstance(run_id, str):
        err("runId", "must be a string -- the guard denies every call otherwise")
        run_id = ""
    elif run_id and not RUN_ID_RE.match(run_id):
        err("runId", f"{run_id!r} is not [A-Za-z0-9._-]{{1,64}} without '..' -- "
                     "it becomes a path component, so the guard denies every call")

    beats = decl.get("beats")
    if not isinstance(beats, list):
        err("beats", "missing or not a list -- takt enforces nothing")
        return errors
    if not beats:
        err("beats", "empty -- the declaration file makes takt live but gates nothing")

    seen_ids = set()
    for i, beat in enumerate(beats):
        where = f"beats[{i}]"
        if not isinstance(beat, dict):
            err(where, "not an object -- silently skipped by the guard")
            continue

        beat_id = beat.get("id")
        if not isinstance(beat_id, str) or not beat_id:
            err(where, "no 'id' -- denials will say 'unnamed beat'")
        else:
            where = f"beats[{i}] ({beat_id})"
            if beat_id in seen_ids:
                err(where, "duplicate id")
            seen_ids.add(beat_id)

        tools = beat.get("tools")
        if tools is None or (isinstance(tools, list) and not tools):
            tools = list(EDIT_TOOLS)  # the guard's own default
        elif not isinstance(tools, list):
            err(where, "'tools' is not a list -- the guard falls back to edit tools")
            tools = list(EDIT_TOOLS)
        unknown = [t for t in tools if t not in KNOWN_TOOLS]
        if unknown:
            err(where, f"unknown tool name(s) {unknown} -- these never match, so the beat is inert")

        gates_edits = any(t in EDIT_TOOLS for t in tools)
        gates_dispatch = any(t in DISPATCH_TOOLS for t in tools)
        paths = beat.get("paths")
        skills = beat.get("skills")
        has_paths = isinstance(paths, list) and bool(paths)
        has_skills = isinstance(skills, list) and bool(skills)

        # THE likeliest generator bug: a beat the guard silently skips.
        if gates_edits and not has_paths and not gates_dispatch:
            err(where, "gates edit tools but has no non-empty 'paths' -- silently skipped")
        if gates_dispatch and not has_skills and not gates_edits:
            err(where, "gates dispatch tools but has no non-empty 'skills' -- silently skipped")
        if gates_edits and gates_dispatch and not has_paths and not has_skills:
            err(where, "has neither 'paths' nor 'skills' -- silently skipped")

        require = beat.get("require")
        if not isinstance(require, str) or not require:
            err(where, "no 'require' marker -- the guard allows the call unconditionally")
        else:
            # Mirror takt_guard.marker_path_for exactly. These two are supposed
            # to agree, and when they drifted the validator rejected output the
            # guard handles correctly -- a validator that disagrees with the
            # thing it validates is worse than none, because it is believed.
            normalized = require.replace("\\", "/")
            if require.startswith("/"):
                err(where, "'require' is absolute -- it ignores runId namespacing entirely")
            elif normalized == ".takt" or normalized.startswith(".takt/"):
                pass  # repo-level marker: deliberately NOT namespaced, runId or not
            elif run_id and "/" in require:
                err(where, f"'require' {require!r} has a '/' but does not start with '.takt/', "
                           f"so it resolves to .takt/{run_id}/{require}. Use a bare name for a "
                           f"per-run marker, or '.takt/<name>' for a repo-level one")

        rk = beat.get("requireKind")
        if rk is not None and rk not in ("file", "dir", "any"):
            err(where, f"'requireKind' {rk!r} must be 'file', 'dir' or 'any' -- the guard "
                       f"raises on anything else, and a raise after opt-in DENIES")

        if not beat.get("reason"):
            err(where, "no 'reason' -- the denial will not say why")

    return errors


SELFTEST_CASES = [
    ("clean, no runId", {"beats": [
        {"id": "a", "tools": ["Edit"], "paths": ["*.tsx"], "require": ".takt/x", "reason": "r"}]}, 0),
    ("clean, with runId", {"runId": "ap-1", "beats": [
        {"id": "a", "tools": ["Skill"], "skills": ["s-*"], "require": "built", "reason": "r"}]}, 0),
    ("beat gating nothing", {"beats": [
        {"id": "a", "tools": ["Edit"], "require": ".takt/x", "reason": "r"}]}, 1),
    ("dispatch beat with no skills", {"beats": [
        {"id": "a", "tools": ["Skill"], "require": "x", "reason": "r"}]}, 1),
    ("no require", {"beats": [
        {"id": "a", "tools": ["Edit"], "paths": ["*.tsx"], "reason": "r"}]}, 1),
    ("bad runId", {"runId": "../esc", "beats": [
        {"id": "a", "tools": ["Edit"], "paths": ["*"], "require": "x", "reason": "r"}]}, 1),
    ("unknown tool", {"beats": [
        {"id": "a", "tools": ["Frobnicate"], "paths": ["*"], "require": "x", "reason": "r"}]}, 1),
    ("duplicate ids", {"beats": [
        {"id": "a", "tools": ["Edit"], "paths": ["*"], "require": "x", "reason": "r"},
        {"id": "a", "tools": ["Edit"], "paths": ["*"], "require": "y", "reason": "r"}]}, 1),
    ("repo-level .takt/ marker under a runId is FINE", {"runId": "ap-1", "beats": [
        {"id": "a", "tools": ["Skill"], "skills": ["s"], "require": ".takt/built", "reason": "r"}]}, 0),
    ("a non-.takt slash under a runId is still flagged", {"runId": "ap-1", "beats": [
        {"id": "a", "tools": ["Skill"], "skills": ["s"], "require": "sub/dir/built", "reason": "r"}]}, 1),
    ("requireKind file is accepted", {"beats": [
        {"id": "a", "tools": ["Skill"], "skills": ["s"], "require": "x", "requireKind": "file", "reason": "r"}]}, 0),
    ("requireKind omitted is accepted (backward compatible)", {"beats": [
        {"id": "a", "tools": ["Skill"], "skills": ["s"], "require": "x", "reason": "r"}]}, 0),
    ("requireKind nonsense is rejected", {"beats": [
        {"id": "a", "tools": ["Skill"], "skills": ["s"], "require": "x", "requireKind": "socket", "reason": "r"}]}, 1),
    ("mixed per-run and repo-level in one declaration", {"runId": "ap-1", "beats": [
        {"id": "a", "tools": ["Skill"], "skills": ["s"], "require": "built", "reason": "r"},
        {"id": "b", "tools": ["Skill"], "skills": ["t"], "require": ".takt/council-done", "reason": "r"}]}, 0),
    ("empty beats", {"beats": []}, 1),
    ("no reason", {"beats": [
        {"id": "a", "tools": ["Edit"], "paths": ["*"], "require": "x"}]}, 1),
]


def selftest() -> int:
    failures = []
    for name, decl, want_errors in SELFTEST_CASES:
        got = validate(decl)
        ok = (len(got) > 0) == (want_errors > 0)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {len(got)} error(s)")
        if not ok:
            failures.append(name)
            for e in got:
                print(f"        {e}")
    # The fenced-block parser is part of the contract too.
    with tempfile.TemporaryDirectory() as raw:
        f = Path(raw) / "takt.local.md"
        f.write_text("# no fence here\n")
        try:
            load(f)
            print("  FAIL missing fence should raise")
            failures.append("missing fence")
        except ValueError:
            print("  ok   missing ```json fence raises")
    print()
    if failures:
        print(f"SELFTEST FAILED ({len(failures)}): " + ", ".join(failures))
        return 1
    print(f"selftest passed ({len(SELFTEST_CASES)} declarations + parser)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_beats.py",
        description="Validate a .claude/takt.local.md beat declaration. "
        "Reports what takt's guard silently tolerates -- a beat gating no paths "
        "or no skills is skipped at runtime, which is the likeliest bug in a "
        "generated declaration. Never edits the file.",
        epilog="exit 0 clean, 1 errors found, 2 the file could not be read at all",
    )
    parser.add_argument(
        "declaration", nargs="?",
        help="path to the declaration (usually .claude/takt.local.md)",
    )
    parser.add_argument(
        "--selftest", action="store_true",
        help="run the planted-defect selftest instead of validating a file",
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.declaration:
        parser.error("a declaration path is required unless --selftest is given")
    path = Path(args.declaration)
    try:
        decl = load(path)
    except FileNotFoundError:
        print(f"{path}: no such file", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        return 2
    errors = validate(decl)
    if not errors:
        n = len(decl.get("beats") or [])
        run_id = decl.get("runId") or "(none)"
        print(f"{path}: OK -- {n} beat(s), runId {run_id}")
        return 0
    for e in errors:
        print(f"{path}: {e}", file=sys.stderr)
    print(f"{path}: {len(errors)} error(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
