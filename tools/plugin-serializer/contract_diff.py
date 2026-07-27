#!/usr/bin/env python3
"""Gate 3b — did the rebuild keep the contracts a user depends on?

The capability diff compares components: does every skill and agent still
exist. That passes a rebuild which kept all 16 skills, found every seeded
defect, and wrote its reports to `.self-assess/` instead of the documented
`analysis/self-assess/**`. Content correct, location wrong, every gate green.

The cause was upstream: the behavior extraction abstracted the path into
`<output_dir>/UI_AUDIT.md` and never defined `<output_dir>`, so the generator
invented one. Reasonable of it — the placeholder looked like an obligation and
carried none.

A path a user reads, scripts against, or has already got a directory full of is
contract, not implementation. So is a settings file name, a config key, an
environment variable. This compares those between a source plugin and its
rebuild, and reports what moved.

Deliberately reports rather than hard-fails on additions: a rebuild may write
something new. A REMOVED or MOVED contract is the failure.

Usage:
    contract_diff.py <source-plugin-dir> <rebuilt-plugin-dir>
    contract_diff.py <prior-version-dir> plugins/self-assess
Exit: 0 if no contract was moved or lost, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# An artifact a user reads or scripts against: a report/state file under a
# directory, e.g. analysis/self-assess/UI_AUDIT.md or .confab/reports/X.json
ARTIFACT = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+[A-Za-z0-9_.-]+\.(?:md|json|jsonl|toml|yaml|yml|db|sqlite))")
# A settings/config file the user is told to create.
SETTINGS = re.compile(r"(?<![\w/.-])(\.claude/[\w.-]+\.(?:md|json|toml|yaml|yml))")
# Environment variables the plugin reads.
ENVVAR = re.compile(r"(?:\$\{?|os\.environ(?:\.get)?[\[(][\"']|process\.env\.)([A-Z][A-Z0-9_]{3,})")

# Paths that say nothing about the plugin's own contract.
NOISE = re.compile(
    r"^(?:\.github/|node_modules/|\.git/|docs?/|references?/|examples?/|test|scripts?/[\w-]+\.py$)"
    r"|(?:^|/)(?:README|CHANGELOG|LICENSE|SKILL|plugin)\.(?:md|json)$"
    r"|^(?:skills|agents|workflows|hooks|commands)/",
    re.IGNORECASE,
)
ENV_NOISE = {"CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "NO_COLOR", "PATH", "HOME",
             "UNTRUSTED", "SKILL", "TODO", "NOTE", "WARNING", "IMPORTANT", "MUST",
             "ALWAYS", "NEVER", "PASS", "FAIL", "ERROR", "JSON", "YAML", "HTTP"}


def harvest(root: Path) -> dict[str, set[str]]:
    """Contract-shaped strings appearing in a plugin's instructions."""
    text = []
    for sub in ("skills", "agents", "commands", "hooks", "workflows", "scripts"):
        d = root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix in {".md", ".js", ".py", ".json"}:
                text.append(p.read_text(encoding="utf-8", errors="replace"))
    blob = "\n".join(text)

    artifacts = {m for m in ARTIFACT.findall(blob) if not NOISE.search(m)}
    # Reduce to the directory that owns them — that is the contract users see.
    dirs = {m.rsplit("/", 1)[0] for m in artifacts}
    dirs = {d for d in dirs if "." not in d.rsplit("/", 1)[-1] or d.startswith(".")}
    dirs -= {".circleci", ".github", ".git"}
    return {
        "output_dirs": {d for d in dirs if not NOISE.search(d)},
        "settings_files": set(SETTINGS.findall(blob)),
        "env_vars": {e for e in ENVVAR.findall(blob) if e not in ENV_NOISE and "_" in e},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare user-facing contracts between two plugin versions.")
    ap.add_argument("source", type=Path)
    ap.add_argument("rebuilt", type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    for d in (args.source, args.rebuilt):
        if not d.is_dir():
            print(f"ERROR: not a directory: {d}", file=sys.stderr)
            return 2

    a, b = harvest(args.source), harvest(args.rebuilt)
    lost_total = 0
    print(f"contract diff: {args.source} -> {args.rebuilt}")
    for kind in ("output_dirs", "settings_files", "env_vars"):
        lost = sorted(a[kind] - b[kind])
        added = sorted(b[kind] - a[kind])
        if not lost and not added and args.quiet:
            continue
        print(f"\n  {kind}")
        for x in sorted(a[kind] & b[kind]):
            print(f"    kept    {x}")
        for x in lost:
            print(f"    LOST    {x}")
        for x in added:
            print(f"    added   {x}")
        lost_total += len(lost)

    print()
    if lost_total:
        print(f"FAIL: {lost_total} contract(s) present in the source and absent from the "
              f"rebuild.\nA user with an existing directory, script or config key pointed "
              f"at one of these\nsilently gets nothing. Content-level tests will not catch "
              f"it — they check what\nwas found, not where it was written.")
    else:
        print("ok: no user-facing contract was lost.")
    return 1 if lost_total else 0


if __name__ == "__main__":
    sys.exit(main())
