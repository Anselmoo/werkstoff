#!/usr/bin/env python3
"""PreToolUse hook: while a nacharbeit fix pass is in flight, deny every edit the
pass did not authorize and every git state change.

A fix pass edits other plugins' files. Nothing in a PreToolUse payload says which
agent issued an edit (see docs/orchestration/references/hazards.md, "Why a hook
cannot tell whose edit it is"), so the guard gates on a PER-DISPATCH LOCK, never on
repo-level state: build_fix_args.py writes <state>/fix_scope.json naming every file
the pass may touch with its tier, and post_fix_check.py --release-lock deletes it.
Between those two moments this hook refuses:

  - a Write/Edit/MultiEdit whose target is not in the lock (or cannot be determined);
  - a Write/Edit/MultiEdit to a file the lock lists as opus- or human-tier — those
    entries are surfaced for a person, never auto-applied;
  - a Bash command that changes git state (commit, push, reset, checkout, ...) — a
    half-applied pass must never be committed by the pass itself.

Contract (Claude Code's PreToolUse hook protocol):
  - stdin: JSON with at least {"cwd": ..., "tool_name": ..., "tool_input": {...}}
  - to ALLOW: exit 0
  - to DENY: exit code 2, reason on stderr, AND stdout JSON of exactly
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
         "permissionDecision": "deny", "permissionDecisionReason": "<why>"}}
    Both are required -- omitting hookSpecificOutput.hookEventName or using
    "systemMessage" instead of "permissionDecisionReason" makes the runtime
    silently ignore the deny. Run test_nacharbeit_guard.py after touching this file.

Inertness: no lock file, no opinion -- the call is allowed before it is inspected,
so this never polices a repository that is not mid-fix. Fail-closed: once the lock
exists, any internal error denies rather than silently allowing, with the escape
hatch named. A stale lock therefore denies, which is the safe direction; the
nacharbeit-status skill reports one older than six hours with the release command.

Matching is exact path equality after normalisation, never regex and never glob:
the lock lists files, not patterns.

Usage: invoked by Claude Code with the PreToolUse event on stdin; set
NACHARBEIT_STATE_DIR to relocate the lock (default analysis/nacharbeit).
Exit: 0 allow; 2 deny.
"""

from __future__ import annotations

import json
import os
import sys
from typing import NoReturn

DEFAULT_STATE_DIR = os.path.join("analysis", "nacharbeit")
LOCK_NAME = "fix_scope.json"
ESCAPE_HATCH = (
    "set NACHARBEIT_DISABLE_GUARD=1 to bypass this guard for one call, or release the "
    "lock with `python3 plugins/nacharbeit/scripts/post_fix_check.py --release-lock` "
    "once the fix pass has finished"
)
EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
APPLY_TIERS = ("haiku", "sonnet")
GIT_STATE_VERBS = {
    "commit", "push", "reset", "checkout", "switch", "rebase", "merge", "stash", "clean",
    "add", "rm", "mv", "tag", "cherry-pick", "am", "apply", "restore", "revert", "branch",
}
GH_STATE_VERBS = {("pr", "create"), ("pr", "merge"), ("pr", "close"), ("release", "create")}


def deny(reason: str) -> NoReturn:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def allow() -> NoReturn:
    sys.exit(0)


def relative(cwd: str, path: str) -> str:
    """Repo-relative posix form, so the lock's `plugins/x/SKILL.md` matches whether the
    tool reported an absolute or a relative path."""
    if not path:
        return ""
    candidate = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        rel = os.path.relpath(os.path.normpath(candidate), os.path.normpath(cwd))
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def edit_targets(cwd: str, tool_input: dict) -> list:
    """Every file path an edit payload names, repo-relative.

    Collected the way plugins/takt/hooks/takt_guard.py collects them: `file_path`,
    `edits[].file_path`, `file_paths`. The `isinstance(..., list)` checks are
    load-bearing -- iterating a STRING yields characters, which would fill the set
    with junk so the caller's fail-closed branch never fires.
    """
    found = []
    single = tool_input.get("file_path")
    if isinstance(single, str) and single:
        found.append(single)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for entry in edits:
            if isinstance(entry, dict):
                path = entry.get("file_path")
                if isinstance(path, str) and path:
                    found.append(path)
    plural = tool_input.get("file_paths")
    if isinstance(plural, list):
        for path in plural:
            if isinstance(path, str) and path:
                found.append(path)
    return [relative(cwd, path) for path in found]


def bash_changes_git_state(command: str) -> str | None:
    """The offending `git <verb>` / `gh <noun> <verb>` if the command changes git state.

    Tokenised on whitespace and the shell separators ; && || |, so `a && git push` is
    caught; a redirect-based bypass is documented, not gated (as lehre does)."""
    if not isinstance(command, str):
        return None
    flat = command
    for sep in (";", "&&", "||", "|", "\n"):
        flat = flat.replace(sep, " ")
    toks = flat.split()
    for i, tok in enumerate(toks):
        base = tok.rsplit("/", 1)[-1]
        if base == "git":
            rest = [t for t in toks[i + 1:] if not t.startswith("-")]
            if rest and rest[0] in GIT_STATE_VERBS:
                return f"git {rest[0]}"
        if base == "gh":
            rest = [t for t in toks[i + 1:] if not t.startswith("-")]
            if len(rest) >= 2 and (rest[0], rest[1]) in GH_STATE_VERBS:
                return f"gh {rest[0]} {rest[1]}"
    return None


def main() -> NoReturn:
    if os.environ.get("NACHARBEIT_DISABLE_GUARD") == "1":
        allow()

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()  # not a payload this hook can read; never police what it cannot parse

    cwd = event.get("cwd") or os.getcwd()
    state_dir = os.environ.get("NACHARBEIT_STATE_DIR") or DEFAULT_STATE_DIR
    lock_path = state_dir if os.path.isabs(state_dir) else os.path.join(cwd, state_dir)
    lock_path = os.path.join(lock_path, LOCK_NAME)
    if not os.path.isfile(lock_path):
        allow()  # inert: no fix pass is in flight in this repository

    # Past this point a fix pass opened the lock, so errors deny rather than allow.
    try:
        tool_name = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}
        with open(lock_path, "r", encoding="utf-8") as handle:
            lock = json.load(handle)
        files = lock.get("files")
        if not isinstance(files, dict):
            deny(f"nacharbeit: the fix lock at {relative(cwd, lock_path)} has no `files` map, so no edit can be checked against it. Refusing rather than allowing an unchecked edit. {ESCAPE_HATCH}")
        state_rel = relative(cwd, os.path.dirname(lock_path)).rstrip("/") + "/"

        if tool_name in EDIT_TOOLS:
            targets = edit_targets(cwd, tool_input)
            if not targets:
                deny(f"nacharbeit: a fix pass is in flight and this {tool_name} carried no determinable file path, so it cannot be checked against the fix lock. Refusing rather than allowing an unchecked edit. {ESCAPE_HATCH}")
            for target in targets:
                if target.startswith(state_rel):
                    continue  # the session must be able to save the workflow's return value
                tier = files.get(target)
                if tier is None:
                    deny(f"nacharbeit: '{target}' is not in the fix scope; a fix pass is in flight and may only edit the files its lock names. {ESCAPE_HATCH}")
                if tier not in APPLY_TIERS:
                    deny(f"nacharbeit: '{target}' is a {tier}-tier item; opus- and human-tier findings are surfaced for a person and never auto-applied. {ESCAPE_HATCH}")
        elif tool_name == "Bash":
            verb = bash_changes_git_state(tool_input.get("command"))
            if verb:
                deny(f"nacharbeit: `{verb}` changes git state while a fix pass is in flight; finish and check the pass first, then commit by hand. {ESCAPE_HATCH}")
    except SystemExit:
        raise
    except Exception as exc:  # fail-closed, per the module docstring
        deny(
            f"nacharbeit: the fix lock could not be evaluated "
            f"({type(exc).__name__}: {exc}). Refusing rather than allowing an "
            f"unchecked call. {ESCAPE_HATCH}"
        )

    allow()


if __name__ == "__main__":
    main()
