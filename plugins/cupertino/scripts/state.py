#!/usr/bin/env python3
"""Manages the cupertino plugin's on-disk state markers under `.cupertino/`.

`.cupertino/` (relative to the current project root) is the plugin's own
artifact directory. Its mere existence is also what makes hooks/pretooluse_guard.py
active at all -- see the "inert unless used" rule there. Do not point this at
any other directory; nothing else in the plugin will look for state there.

Subcommands (all print JSON, all exit 0 on success / 1 on failure):
  init                          create .cupertino/ if absent
  set <flag> [value]            write .cupertino/flags/<flag>  (default value: "1")
  clear <flag>                  remove .cupertino/flags/<flag>
  check <flag>                  exit 0 + {"set": true}  if present, else {"set": false}
  path                          print the resolved state dir (for debugging)
"""
import json
import os
import sys

STATE_DIR_NAME = ".cupertino"


def state_dir():
    # Resolve the project root exactly the way hooks/pretooluse_guard.py does
    # (CLAUDE_PROJECT_DIR first, os.getcwd() as fallback) so a skill running
    # this script and the hook reading its output never disagree about where
    # ".cupertino/" actually is.
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.join(root, STATE_DIR_NAME)


def flags_dir():
    return os.path.join(state_dir(), "flags")


def _ok(payload):
    print(json.dumps(payload))
    sys.exit(0)


def _fail(msg):
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(1)


def cmd_init():
    os.makedirs(flags_dir(), exist_ok=True)
    _ok({"ok": True, "path": state_dir()})


def cmd_set(flag, value="1"):
    if not flag or any(c in flag for c in ("/", "..", "\0")):
        _fail(f"invalid flag name: {flag!r}")
    os.makedirs(flags_dir(), exist_ok=True)
    with open(os.path.join(flags_dir(), flag), "w") as f:
        f.write(value)
    _ok({"ok": True, "flag": flag, "value": value})


def cmd_clear(flag):
    if not flag or any(c in flag for c in ("/", "..", "\0")):
        _fail(f"invalid flag name: {flag!r}")
    path = os.path.join(flags_dir(), flag)
    if os.path.exists(path):
        os.remove(path)
    _ok({"ok": True, "flag": flag, "cleared": True})


def cmd_check(flag):
    path = os.path.join(flags_dir(), flag)
    if os.path.exists(path):
        with open(path) as f:
            value = f.read()
        _ok({"ok": True, "set": True, "value": value})
    else:
        _ok({"ok": True, "set": False})


def main():
    args = sys.argv[1:]
    if not args:
        _fail("usage: state.py <init|set|clear|check|path> [flag] [value]")
    cmd = args[0]
    if cmd == "init":
        cmd_init()
    elif cmd == "set":
        cmd_set(args[1] if len(args) > 1 else "", args[2] if len(args) > 2 else "1")
    elif cmd == "clear":
        cmd_clear(args[1] if len(args) > 1 else "")
    elif cmd == "check":
        cmd_check(args[1] if len(args) > 1 else "")
    elif cmd == "path":
        _ok({"ok": True, "path": state_dir()})
    else:
        _fail(f"unknown subcommand: {cmd}")


if __name__ == "__main__":
    main()
