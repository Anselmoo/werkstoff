#!/usr/bin/env python3
"""PreToolUse guard for demo.

Usage: fed a PreToolUse JSON event on stdin by the runtime.
Exit: 0 allow; 2 deny.
"""
import json
import os
import sys


def deny(reason):
    print(json.dumps({"systemMessage": reason}))
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def main():
    if os.environ.get("DEMO_DISABLE_GUARD") == "1":
        sys.exit(0)
    try:
        event = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    cwd = event.get("cwd") or os.getcwd()
    if not os.path.isdir(os.path.join(cwd, ".demo")):
        sys.exit(0)
    try:
        tool_input = event.get("tool_input") or {}
        paths = [tool_input.get("file_path")] if isinstance(tool_input.get("file_path"), str) else []
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            paths += [e.get("file_path") for e in edits if isinstance(e, dict)]
        plural = tool_input.get("file_paths")
        if isinstance(plural, list):
            paths += [p for p in plural if isinstance(p, str)]
        if not paths:
            deny("demo: no determinable path; set DEMO_DISABLE_GUARD=1 to bypass")
        for p in paths:
            if p and p.endswith(".generated.md"):
                deny("demo: generated files are frozen during review; set DEMO_DISABLE_GUARD=1 to bypass")
    except SystemExit:
        raise
    except Exception as exc:
        deny(f"demo: guard could not evaluate ({exc}); set DEMO_DISABLE_GUARD=1 to bypass")
    sys.exit(0)


if __name__ == "__main__":
    main()
