#!/usr/bin/env python3
"""PreToolUse hook: deny an edit or a dispatch that runs ahead of its beat.

Several skills in this marketplace declare where in a build they belong --
cupertino-council says "before writing any code ... never after",
compass-clarify-scope says "before any work begins". A declaration in prose is
honored on the order of 1 run in 3 (see the enforcement ladder in this repo's
CLAUDE.md); a PreToolUse hook of type "command" is invoked every time. This
hook is the difference between a documented beat order and an enforced one.

Contract (Claude Code's PreToolUse hook protocol):
  - stdin: JSON with at least {"cwd": ..., "tool_name": ..., "tool_input": {...}}
  - to ALLOW: exit 0
  - to DENY: exit code 2, reason on stderr, AND stdout JSON of exactly
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
         "permissionDecision": "deny", "permissionDecisionReason": "<why>"}}
    Both are required -- omitting hookSpecificOutput.hookEventName or using
    "systemMessage" instead of "permissionDecisionReason" makes the runtime
    silently ignore the deny. That exact mistake has shipped in this plugin
    family before and was caught only by test/plugins/verify-hooks-deny.py --
    run it after touching this file.

Inertness: a repository that has not declared beats (no .claude/takt.local.md)
is allowed immediately, before the tool call is even inspected, so this never
polices an unrelated project. Fail-closed: once that file is confirmed to
exist, any internal error denies rather than silently allowing, with the
escape hatch named in the message.

Matching is fnmatch, never regex. Every silent-failure regex form this repo has
been burned by -- [^.]{0,80} that cannot span a dotted filename, [^\n] in a
bracket expression, \b next to a non-word character -- is a regex-only failure
mode, and a glob cannot express any of them.

Declaring beats -- .claude/takt.local.md, one fenced json block:

    ```json
    {
      "beats": [
        {
          "id": "ui-before-council",
          "tools": ["Write", "Edit", "MultiEdit"],
          "paths": ["*.tsx", "*.jsx", "*.vue", "*.svelte", "src/ui/*"],
          "require": ".takt/council-done",
          "reason": "cupertino-council runs before UI code, never after."
        }
      ]
    }
    ```

A beat matches on `paths` (for Write/Edit/MultiEdit) or on `skills` (for
Skill/Task/Agent). It denies when its `require` marker does not yet exist.
Whatever performs the beat creates that marker; nothing here writes files.

An edit payload may name more than one file -- a MultiEdit does not reliably
carry a single top-level `file_path` -- so every path the payload exposes is
collected (`file_path`, `edits[].file_path`, `file_paths`) and the beat is
violated if ANY of them is gated. If a beat gates the current edit tool but no
path can be determined at all, the call is DENIED rather than allowed: an edit
that cannot be checked against a gate the repository opted into is exactly the
silent bypass this hook exists to prevent. The same rule applies to dispatches --
a Skill/Task/Agent call whose name cannot be determined is denied by a beat that
gates dispatches, for identical reasons.
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from typing import NoReturn

SETTINGS = os.path.join(".claude", "takt.local.md")
ESCAPE_HATCH = (
    "set TAKT_DISABLE_GUARD=1 to bypass this guard, create the required marker "
    "once the beat has actually run, or remove .claude/takt.local.md if this "
    "repository no longer declares beats"
)
EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
DISPATCH_TOOLS = ("Skill", "Task", "Agent")


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


def load_beats(settings_path: str) -> list:
    """Read the first fenced json block. String search, not regex -- a regex
    over a fence is one of the forms that fails silently on odd whitespace."""
    with open(settings_path, "r", encoding="utf-8") as handle:
        text = handle.read()
    start = text.find("```json")
    if start == -1:
        return []
    body_start = text.index("\n", start) + 1
    end = text.find("```", body_start)
    if end == -1:
        return []
    parsed = json.loads(text[body_start:end])
    beats = parsed.get("beats", [])
    return beats if isinstance(beats, list) else []


def relative(cwd: str, path: str) -> str:
    """Repo-relative posix form, so a glob written as src/ui/* matches whether
    the tool reported an absolute or a relative path."""
    if not path:
        return ""
    candidate = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        rel = os.path.relpath(os.path.normpath(candidate), os.path.normpath(cwd))
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def matches(target: str, patterns) -> bool:
    if not target or not isinstance(patterns, list):
        return False
    base = target.rsplit("/", 1)[-1]
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        if fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(base, pattern):
            return True
    return False


def first_match(targets, patterns):
    """The first target matching any pattern, or None. An edit payload can name
    several files; a beat is violated if ANY of them is gated."""
    for target in targets:
        if matches(target, patterns):
            return target
    return None


def edit_targets(cwd: str, tool_input: dict) -> list:
    """Every file path an edit payload names, repo-relative.

    A MultiEdit payload does not reliably carry a single top-level `file_path`.
    This repository already records that shape in
    `plugins/self-assess/hooks/guard_target_edit.py`, which allows when it cannot
    find one -- defensible there, because that hook is scope-checking. takt is
    fail-closed, so it gathers every path the payload does expose, and its caller
    denies rather than allows when the set comes back empty.
    """
    found = []
    single = tool_input.get("file_path")
    if isinstance(single, str) and single:
        found.append(single)

    # `isinstance(..., list)` rather than a truthiness check: iterating a STRING
    # yields characters, every one of which is a non-empty str, which would fill
    # `found` with junk that matches no glob -- and, worse, would make the set
    # non-empty so the caller's fail-closed branch never fires. A malformed
    # payload must look empty here, not look full.
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


def dispatch_target(tool_input: dict) -> str:
    for key in ("skill", "subagent_type", "name", "agent", "command"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def main() -> NoReturn:
    if os.environ.get("TAKT_DISABLE_GUARD") == "1":
        allow()

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        allow()  # not a payload this hook can read; never police what it cannot parse

    cwd = event.get("cwd") or os.getcwd()
    settings_path = os.path.join(cwd, SETTINGS)
    if not os.path.isfile(settings_path):
        allow()  # inert: this repository has not declared any beats

    # Past this point the repository opted in, so errors deny rather than allow.
    try:
        tool_name = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        beats = load_beats(settings_path)
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            tools = beat.get("tools")
            if not isinstance(tools, list) or not tools:
                tools = list(EDIT_TOOLS)
            if tool_name not in tools:
                continue

            beat_id = beat.get("id") or "unnamed beat"
            reason = beat.get("reason") or "this beat has not run yet"

            if tool_name in EDIT_TOOLS:
                patterns = beat.get("paths")
                if not isinstance(patterns, list) or not patterns:
                    continue  # this beat does not gate file edits
                targets = edit_targets(cwd, tool_input)
                if not targets:
                    # Fail closed. An edit whose targets cannot be determined
                    # cannot be checked against this beat, and allowing it would
                    # be a silent bypass of a gate the repository opted into.
                    deny(
                        f"takt: beat '{beat_id}' gates {tool_name}, but the payload "
                        f"carried no determinable file path, so the beat could not be "
                        f"evaluated. Refusing rather than allowing an unchecked edit. "
                        f"{ESCAPE_HATCH}"
                    )
                target = first_match(targets, patterns)
            elif tool_name in DISPATCH_TOOLS:
                patterns = beat.get("skills")
                if not isinstance(patterns, list) or not patterns:
                    continue  # this beat does not gate dispatches
                name = dispatch_target(tool_input)
                if not name:
                    # Same rule as the edit side: a dispatch that cannot be
                    # identified cannot be checked against a beat that gates it.
                    deny(
                        f"takt: beat '{beat_id}' gates {tool_name}, but the payload "
                        f"carried no determinable skill or agent name, so the beat "
                        f"could not be evaluated. Refusing rather than allowing an "
                        f"unchecked dispatch. {ESCAPE_HATCH}"
                    )
                target = first_match([name], patterns)
            else:
                continue

            if target is None:
                continue

            marker = beat.get("require")
            if not isinstance(marker, str) or not marker:
                continue
            marker_path = marker if os.path.isabs(marker) else os.path.join(cwd, marker)
            if os.path.exists(marker_path):
                continue

            deny(
                f"takt: '{target}' runs ahead of beat '{beat_id}'. {reason} "
                f"Required marker '{marker}' does not exist. {ESCAPE_HATCH}"
            )
    except SystemExit:
        raise
    except Exception as exc:  # fail-closed, per the module docstring
        deny(
            f"takt: beat declaration could not be evaluated "
            f"({type(exc).__name__}: {exc}). Refusing rather than allowing an "
            f"unchecked call. {ESCAPE_HATCH}"
        )

    allow()


if __name__ == "__main__":
    main()
