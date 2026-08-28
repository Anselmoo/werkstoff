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

            if tool_name in EDIT_TOOLS:
                target = relative(cwd, tool_input.get("file_path") or "")
                patterns = beat.get("paths")
            elif tool_name in DISPATCH_TOOLS:
                target = dispatch_target(tool_input)
                patterns = beat.get("skills")
            else:
                continue

            if not matches(target, patterns):
                continue

            marker = beat.get("require")
            if not isinstance(marker, str) or not marker:
                continue
            marker_path = marker if os.path.isabs(marker) else os.path.join(cwd, marker)
            if os.path.exists(marker_path):
                continue

            beat_id = beat.get("id") or "unnamed beat"
            reason = beat.get("reason") or "this beat has not run yet"
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
