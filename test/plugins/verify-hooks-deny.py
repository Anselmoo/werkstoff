#!/usr/bin/env python3
"""Gate 2b — a declared hook must actually DENY, not merely exist.

Requirement 6 in the generator asks for a PreToolUse hook. It reliably produces
the artifact and not the behavior: of three generated hooks, all three had a
well-formed hooks.json and a deny() with the right exit code and JSON shape, and
two of them allowed a violating write. One shipped hooks.json with no script at
all — and was reported as a success, because the check was `[ -f hooks.json ]`.

That is the same gap as "the rule exists" vs "the rule runs", one level down.
Existence is cheap to generate and cheap to check; firing is neither. So this
gate does the only thing that settles it: resolve the command the hooks.json
actually declares, feed it a crafted violating event on stdin, and require
exit 2.

Four failure modes it separates, because they need different fixes:

    no-hook       nothing declared            -> requirement 6 produced nothing
    malformed     hooks.json unparseable      -> shape bug
    missing       declares a script not there -> declaration without implementation
    inert         script runs, allows anyway  -> logic bug (the common one)

Also checks the inverse, which matters more than it looks: a hook MUST allow
when the repo does not use that plugin. A hook that denies everywhere would
police every unrelated repository on the machine.

Usage:
    verify-hooks-deny.py <plugin-dir> [...] [--violating-fixture DIR]
Exit: 0 if every declared hook denies the violating case and allows the inert
case; 1 otherwise. A plugin with no hook is reported, not failed — not every
plugin has an action to gate (advisory plugins genuinely cannot).
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_VIOLATING = "test/plugins/fixtures/ledger-missing-blast-radius"


def declared_commands(plugin: Path) -> tuple[list[list[str]], str | None]:
    """Every PreToolUse command hooks.json declares, with ${CLAUDE_PLUGIN_ROOT} resolved."""
    j = plugin / "hooks/hooks.json"
    if not j.is_file():
        return [], "no-hook"
    try:
        d = json.loads(j.read_text())
        entries = d["hooks"]["PreToolUse"]
    except Exception as e:
        return [], f"malformed ({type(e).__name__})"
    cmds = []
    for entry in entries:
        for h in entry.get("hooks", []):
            if h.get("type") != "command":
                # A "prompt" hook asks a model to decide, which is the
                # model-mediated path a hook exists to replace.
                return [], 'declares type="prompt" — not enforcement'
            raw = h.get("command", "")
            cmds.append([w.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin.resolve()))
                         for w in shlex.split(raw)])
    return cmds, None


def probe(cmd: list[str], cwd: str, path: str = "src/api.py") -> tuple[int, str]:
    payload = json.dumps({"cwd": cwd, "tool_name": "Edit",
                          "tool_input": {"file_path": path, "content": "x = 1\n"}})
    try:
        r = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as e:
        return -1, f"{type(e).__name__}: {e}"
    return r.returncode, (r.stderr or r.stdout)[:160].replace("\n", " ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify declared hooks actually deny.")
    ap.add_argument("plugin_dirs", nargs="+", type=Path)
    ap.add_argument("--violating-fixture", default=DEFAULT_VIOLATING,
                    help="a repo state the hook is supposed to refuse edits in")
    args = ap.parse_args(argv)

    violating = str(Path(args.violating_fixture).resolve())
    if not Path(violating).is_dir():
        print(f"ERROR: violating fixture not found: {violating}", file=sys.stderr)
        return 2

    bad = 0
    print(f"{'plugin':<15}{'script':<26}{'violating':<12}{'unrelated':<12}verdict")
    print("-" * 82)
    with tempfile.TemporaryDirectory() as inert:
        for plugin in args.plugin_dirs:
            cmds, err = declared_commands(plugin)
            if err == "no-hook":
                print(f"{plugin.name:<15}{'—':<26}{'—':<12}{'—':<12}no hook declared")
                continue
            if err:
                print(f"{plugin.name:<15}{'—':<26}{'—':<12}{'—':<12}FAIL: {err}")
                bad += 1
                continue
            for cmd in cmds:
                script = Path(cmd[-1])
                if not script.is_file():
                    print(f"{plugin.name:<15}{script.name:<26}{'—':<12}{'—':<12}"
                          f"FAIL: declared script does not exist")
                    bad += 1
                    continue
                rc_v, msg = probe(cmd, violating)
                rc_i, _ = probe(cmd, inert)
                ok = (rc_v == 2) and (rc_i == 0)
                if not ok:
                    bad += 1
                why = ("ok" if ok else
                       "FAIL: allows a violating edit" if rc_v != 2 else
                       "FAIL: denies in an unrelated repo")
                print(f"{plugin.name:<15}{script.name:<26}{('exit ' + str(rc_v)):<12}"
                      f"{('exit ' + str(rc_i)):<12}{why}")
                if not ok and msg:
                    print(f"{'':<15}{'':<26}{msg[:70]}")

    print()
    print("A hook is enforcement only if it denies the violation AND stays inert")
    print("elsewhere. Exit 2 on the violating case is the whole point; anything")
    print("else is a well-shaped file that does nothing.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
