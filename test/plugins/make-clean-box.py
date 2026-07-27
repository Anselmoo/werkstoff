#!/usr/bin/env python3
"""Emit a settings JSON that isolates a `claude --print` run to ONE plugin dir.

Why this exists — the pilot's third and worst contamination. `--plugin-dir X`
*adds* a plugin; it does not remove anything already installed. On this machine
that meant every test run also loaded:

  * 33 user-scope installed plugins, including `andon@werkstoff` v0.2.0 — a
    near-copy of the very plugin under test
  * ~/.claude/skills/andon-loop/SKILL.md — a 22 KB personal skill containing
    the same reopen-three-times thrash rule the oracle asserts

It was caught because Arm C PASSED `armc-thrash` while quoting a rule Arm C's
own SKILL.md does not contain. The quote came from the installed legacy plugin.

This contamination is NOT a constant that cancels out across arms. The
contaminant is itself an andon-loop implementation, so it *supplies* the
capability the weaker arm is missing — inflating Arm C specifically. Any A/B/C
comparison run without this isolation is measuring the union of the arm and the
ambient environment, not the arm.

Two levers, both non-destructive and per-run (nothing in ~/.claude is modified):
  * enabledPlugins: <id>: false   — for every installed plugin
  * skillOverrides: <name>: off   — for every personal skill in ~/.claude/skills

`--plugin-dir` content survives both, which is exactly what we want.

(`strictPluginOnlyCustomization` looks like the intended lever but had no effect
when passed via --settings here, so skillOverrides is used instead.)

Usage: make-clean-box.py <out.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOME = Path.home()


def installed_plugin_ids() -> list[str]:
    p = HOME / ".claude/plugins/installed_plugins.json"
    if not p.is_file():
        return []
    ids: set[str] = set()

    def walk(o: object) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if "@" in str(k):
                    ids.add(str(k))
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(json.loads(p.read_text()))
    return sorted(ids)


def personal_skill_names() -> list[str]:
    d = HOME / ".claude/skills"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    plugins = installed_plugin_ids()
    skills = personal_skill_names()
    cfg = {
        "enabledPlugins": {i: False for i in plugins},
        "skillOverrides": {s: "off" for s in skills},
    }
    Path(argv[1]).write_text(json.dumps(cfg, indent=1))
    print(f"clean box: {len(plugins)} plugins disabled, {len(skills)} personal skills off",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
