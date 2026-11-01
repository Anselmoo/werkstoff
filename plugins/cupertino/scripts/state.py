#!/usr/bin/env python3
"""Manage cupertino's on-disk state markers under `.cupertino/flags/`.

usage: state.py [-h] {init,set,clear,check,path} [flag] [value]

  init                 create .cupertino/ (this is also what makes hooks/pretooluse_guard.py live)
  set FLAG [VALUE]     write .cupertino/flags/FLAG (default value "1")
  clear FLAG           remove .cupertino/flags/FLAG
  check FLAG           print {"set": true|false}
  path                 print the resolved state directory

The project root is resolved by repair_lib.project_root(), the same function the
guard uses. They used to disagree -- this script read CLAUDE_PROJECT_DIR while the
guard read the hook payload's cwd -- so a flag could be written where the guard
never looked.

Every subcommand prints JSON. Exit: 0 ok; 1 refused (invalid flag name); 2 bad usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_lib import project_root, state_dir  # noqa: E402


def _valid(flag: str) -> bool:
    return bool(flag) and not any(c in flag for c in ("/", "\\", "..", "\0"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="state.py", description="Manage cupertino's .cupertino/flags/ markers.",
                                     epilog="exit 0 ok, 1 refused, 2 bad usage")
    parser.add_argument("cmd", choices=("init", "set", "clear", "check", "path"))
    parser.add_argument("flag", nargs="?", default="")
    parser.add_argument("value", nargs="?", default="1")
    args = parser.parse_args(argv)

    sdir = state_dir(project_root())
    flags = sdir / "flags"
    if args.cmd == "init":
        flags.mkdir(parents=True, exist_ok=True)
        out = {"ok": True, "path": str(sdir)}
    elif args.cmd == "path":
        out = {"ok": True, "path": str(sdir)}
    elif not _valid(args.flag):
        print(json.dumps({"ok": False, "error": f"invalid flag name: {args.flag!r}"}))
        return 1
    elif args.cmd == "set":
        flags.mkdir(parents=True, exist_ok=True)
        (flags / args.flag).write_text(args.value, encoding="utf-8")
        out = {"ok": True, "flag": args.flag, "value": args.value}
    elif args.cmd == "clear":
        (flags / args.flag).unlink(missing_ok=True)
        out = {"ok": True, "flag": args.flag, "cleared": True}
    else:
        path = flags / args.flag
        out = {"ok": True, "set": True, "value": path.read_text(encoding="utf-8")} if path.is_file() else {"ok": True, "set": False}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
