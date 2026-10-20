#!/usr/bin/env python3
"""PreToolUse guard for lockstep.

Usage: fed a PreToolUse JSON event on stdin by the runtime.
Exit: 0 allow; 2 deny (with the hookSpecificOutput JSON on stdout).
"""
import json
import os
import sys

ESCAPE = "set LOCKSTEP_DISABLE_GUARD=1 to bypass this guard"


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def allow():
    sys.exit(0)


def targets(tool_input):
    found = []
    single = tool_input.get("file_path")
    if isinstance(single, str) and single:
        found.append(single)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        found += [e.get("file_path") for e in edits if isinstance(e, dict) and isinstance(e.get("file_path"), str)]
    plural = tool_input.get("file_paths")
    if isinstance(plural, list):
        found += [p for p in plural if isinstance(p, str)]
    return found


def main():
    if os.environ.get("LOCKSTEP_DISABLE_GUARD") == "1":
        allow()
    try:
        event = json.load(sys.stdin)
    except ValueError:
        allow()
    cwd = event.get("cwd") or os.getcwd()
    # Gate whenever analysis/lockstep/ exists — whenever analysis/lockstep/ exists a beat run is in progress somewhere in this session.
    if not os.path.isdir(os.path.join(cwd, "analysis", "lockstep")):
        allow()
    beats_file = os.path.join(cwd, ".lockstep", "beats.yaml")
    try:
        tool_input = event.get("tool_input") or {}
        paths = targets(tool_input)
        if not paths:
            return 0  # no path, nothing to gate
        for p in paths:
            if p.endswith(".generated.md"):
                deny("this write runs ahead of its beat; finish the beat first. " + ESCAPE)
    except SystemExit:
        raise
    except Exception as exc:
        deny(f"lockstep: guard could not evaluate ({exc}). " + ESCAPE)
    allow()


if __name__ == "__main__":
    main()
