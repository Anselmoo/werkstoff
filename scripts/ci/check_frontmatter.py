#!/usr/bin/env python3
"""Validate YAML frontmatter on every plugins/*/skills/*/SKILL.md and
plugins/*/agents/*.md file: must parse as YAML and include name+description.
Tier-1 static check (this repo's CLAUDE.md convention) -- no API calls,
runs anywhere Python 3 + PyYAML are available, same one-liner check every
SDD task brief in this repo already runs by hand, now automated."""
from __future__ import annotations

import glob
import sys

import yaml

REQUIRED_KEYS = {"name", "description"}


def check_file(path: str) -> list[str]:
    text = open(path, encoding="utf-8").read()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return [f"{path}: no YAML frontmatter block found"]
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        return [f"{path}: invalid YAML frontmatter -- {exc}"]
    if not isinstance(frontmatter, dict):
        return [f"{path}: frontmatter did not parse to a mapping"]
    missing = REQUIRED_KEYS - frontmatter.keys()
    if missing:
        return [f"{path}: missing required frontmatter key(s): {sorted(missing)}"]
    return []


def main() -> int:
    paths = sorted(
        glob.glob("plugins/*/skills/*/SKILL.md") + glob.glob("plugins/*/agents/*.md")
    )
    if not paths:
        print("No SKILL.md/agent files found -- check the glob patterns.")
        return 1

    all_errors: list[str] = []
    for path in paths:
        all_errors.extend(check_file(path))

    if all_errors:
        for err in all_errors:
            print(f"FAIL: {err}")
        print(f"\n{len(all_errors)} error(s) across {len(paths)} file(s) checked.")
        return 1

    print(f"All {len(paths)} SKILL.md/agent frontmatter file(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
