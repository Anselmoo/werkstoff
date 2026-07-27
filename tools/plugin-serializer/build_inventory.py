#!/usr/bin/env python3
"""Compute a plugin's capability inventory from the filesystem. No LLM.

This file exists to be boring and unfoolable. It is the ground truth the
capability-diff gate compares a regenerated plugin against, so it must not be
produced by the same kind of process that might drop a capability. If an LLM
wrote the inventory and also wrote the rebuild, an omission in the rebuild
could be matched by the same omission in the inventory and the gate would pass
a plugin that silently lost a skill.

The inventory is deliberately NOT given to the generator. Feeding it back in
would re-anchor the clean-room build on legacy's structure — the very thing
serializing to behavior-only JSON is meant to avoid. It goes to the gate only.

Emits ids and counts, nothing about behavior:
  skills[]     — id (frontmatter `name`, else directory name), path
  agents[]     — id (frontmatter `name`, else filename stem), path
  workflows[]  — filename
  commands[]   — filename stem
  scripts[]    — filename (vendored ones flagged, since they are not the
                 plugin's own capability and a rebuild need not reproduce them)

Usage: build_inventory.py <plugin-dir> [-o out.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VENDORED = {"build_symbol_index.py", "test_build_symbol_index.py", "migrate-query-symbol.js"}


def frontmatter_name(path: Path) -> str | None:
    """Read `name:` from a markdown file's YAML frontmatter, without PyYAML."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    m = re.search(r"^name:\s*(.+?)\s*$", parts[1], re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("'\"")


def build(plugin_dir: Path) -> dict:
    skills = []
    for sk in sorted((plugin_dir / "skills").glob("*/SKILL.md")):
        skills.append({"id": frontmatter_name(sk) or sk.parent.name,
                       "path": str(sk.relative_to(plugin_dir))})

    agents = []
    for ag in sorted((plugin_dir / "agents").glob("*.md")):
        agents.append({"id": frontmatter_name(ag) or ag.stem,
                       "path": str(ag.relative_to(plugin_dir))})

    workflows = sorted(p.name for p in (plugin_dir / "workflows").glob("*.js"))
    commands = sorted(p.stem for p in (plugin_dir / "commands").glob("*.md"))

    scripts = []
    for s in sorted((plugin_dir / "scripts").glob("*")):
        if s.is_file():
            scripts.append({"name": s.name, "vendored": s.name in VENDORED})

    manifest = plugin_dir / ".claude-plugin/plugin.json"
    name = json.loads(manifest.read_text())["name"] if manifest.is_file() else plugin_dir.name

    return {
        "plugin": name,
        "source_dir": str(plugin_dir),
        "skills": skills,
        "agents": agents,
        "workflows": workflows,
        "commands": commands,
        "scripts": scripts,
        "counts": {
            "skills": len(skills), "agents": len(agents),
            "workflows": len(workflows), "commands": len(commands),
            "scripts_own": sum(1 for s in scripts if not s["vendored"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0] if __doc__ else "")
    ap.add_argument("plugin_dir", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)

    if not args.plugin_dir.is_dir():
        print(f"ERROR: not a directory: {args.plugin_dir}", file=sys.stderr)
        return 2
    inv = build(args.plugin_dir)
    text = json.dumps(inv, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"{inv['plugin']}: " + ", ".join(f"{k}={v}" for k, v in inv["counts"].items()),
              file=sys.stderr)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
