#!/usr/bin/env python3
"""Guard against plugin-group drift between .rrt.toml and the release workflows.

Adding a plugin means adding its name to four separate lists, three of which
nothing ever compared against anything. That drift has now shipped twice:

    #46  fix(ci): plugin-release and auto-version-bump missing takt group
    #51  the identical omission for lehre, caught by review rather than by CI

Both times the symptom is silent until a release: `plugin-release.yml` exits 1
with "Unknown plugin group '<name>'" on a `<name>-vX.Y.Z` tag, and
`auto-version-bump.yml` simply never matches the group, so a changed plugin is
skipped with no error at all. The second failure mode is the worse one -- it
looks like nothing happened because nothing did.

What it checks, for every plugin found on disk under `plugins/*/.claude-plugin/
plugin.json`:

    1. `.rrt.toml` declares a `[[tool.rrt.version_groups]]` named for it.
    2. `.rrt.toml` declares a `[[tool.rrt.field_targets]]` sourcing its
       plugin.json description.
    3. `.github/workflows/plugin-release.yml`'s tag allowlist accepts it.
    4. `.github/workflows/auto-version-bump.yml`'s changed-group matcher
       has a `^plugins/<name>/` grep for it.

and the reverse of each: a name in any of those lists with no plugin directory
behind it is a stale entry, and is reported as a failure rather than ignored.

THE PLUGIN LIST IS DERIVED FROM THE FILESYSTEM EVERY RUN, NEVER HARDCODED. A
hardcoded list here would be exactly the kind of drift this tool exists to
catch -- the same reasoning `lint-plugin-authors.py` states for itself.

NOT CHECKED HERE: `.claude-plugin/marketplace.json` membership, which
`lint-plugin-authors.py` already verifies bidirectionally. Two checks asserting
one fact is how they drift apart.

FAILS LOUDLY IF IT CANNOT FIND WHAT IT PARSES. If a workflow is restructured so
the allowlist or the matcher block is no longer recognisable, that raises rather
than quietly finding zero names and reporting success -- a guard predicated on
its own input existing is not a guard.

Usage:
    python3 test/plugins/lint-release-wiring.py
Exit: 0 every plugin is wired into all four lists; 1 otherwise.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RRT_TOML = REPO_ROOT / ".rrt.toml"
RELEASE_WF = REPO_ROOT / ".github/workflows/plugin-release.yml"
BUMP_WF = REPO_ROOT / ".github/workflows/auto-version-bump.yml"

#: Plugin/group names in this repo. Explicit class, never a dot-star: a pattern
#: loose enough to match anything is a pattern that silently matches the wrong
#: thing, and this file exists because of silent matching.
NAME = r"[A-Za-z0-9][A-Za-z0-9._-]*"


class WiringLintError(Exception):
    """A structural problem that must fail loudly rather than return empty."""


def plugins_on_disk() -> set[str]:
    found = {p.parent.parent.name for p in REPO_ROOT.glob("plugins/*/.claude-plugin/plugin.json")}
    if not found:
        raise WiringLintError(
            "no plugins found under plugins/*/.claude-plugin/plugin.json -- "
            "refusing to report success on an empty set"
        )
    return found


def rrt_groups_and_field_targets() -> tuple[set[str], set[str]]:
    with RRT_TOML.open("rb") as handle:
        data = tomllib.load(handle)
    rrt = data.get("tool", {}).get("rrt", {})

    # Only PLUGIN groups belong in this comparison, and which ones those are is
    # derived from each group's own version_targets path rather than assumed:
    # `werkstoff-cli` is a legitimate version group whose target is
    # tools/werkstoff-cli/pyproject.toml, and treating every group as a plugin
    # made this check fail on a clean tree. Its own calibration caught that.
    groups: set[str] = set()
    for group in rrt.get("version_groups", []):
        name = group.get("name")
        if not name:
            continue
        paths = [t.get("path", "") for t in group.get("version_targets", [])]
        if any(p.startswith("plugins/") for p in paths):
            groups.add(name)
    if not groups:
        raise WiringLintError(
            f"{RRT_TOML.name} declares no version_groups targeting plugins/ -- "
            f"refusing to report success on an empty set"
        )

    # field_targets are keyed by their source path, so derive the plugin name
    # from the path rather than trusting a separate name field to agree.
    targets: set[str] = set()
    for entry in rrt.get("field_targets", []):
        source = entry.get("source", "")
        match = re.fullmatch(rf"plugins/({NAME})/\.claude-plugin/plugin\.json", source)
        if match:
            targets.add(match.group(1))
    return groups, targets


def release_allowlist() -> set[str]:
    """The `case "$GROUP" in <a>|<b>|...)` allowlist in plugin-release.yml."""
    text = RELEASE_WF.read_text(encoding="utf-8")
    if "Unknown plugin group" not in text:
        raise WiringLintError(
            f"{RELEASE_WF.name} no longer contains the 'Unknown plugin group' guard this "
            f"check parses; the workflow was restructured and this check must be updated"
        )
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.endswith(") ;;") or "|" not in stripped:
            continue
        alts = stripped.split(")", 1)[0].split("|")
        names = {a.strip() for a in alts if re.fullmatch(NAME, a.strip())}
        if names:
            return names
    raise WiringLintError(
        f"{RELEASE_WF.name}: could not locate the plugin-group case allowlist "
        f"(a line of the form '<a>|<b>|...) ;;')"
    )


def bump_matchers() -> set[str]:
    """Every `^plugins/<name>/` grep in auto-version-bump.yml's matcher block."""
    text = BUMP_WF.read_text(encoding="utf-8")
    names = set(re.findall(rf"\^plugins/({NAME})/", text))
    if not names:
        raise WiringLintError(
            f"{BUMP_WF.name}: found no '^plugins/<name>/' matchers; the changed-group "
            f"block was restructured and this check must be updated"
        )
    return names


def main() -> int:
    try:
        disk = plugins_on_disk()
        groups, field_targets = rrt_groups_and_field_targets()
        release = release_allowlist()
        bump = bump_matchers()
    except (WiringLintError, OSError, tomllib.TOMLDecodeError) as exc:
        print(f"lint-release-wiring: {exc}", file=sys.stderr)
        return 1

    lists = [
        ("`.rrt.toml` version_groups", groups),
        ("`.rrt.toml` field_targets", field_targets),
        (f"{RELEASE_WF.name} tag allowlist", release),
        (f"{BUMP_WF.name} changed-group matcher", bump),
    ]

    failures: list[str] = []
    for label, names in lists:
        for missing in sorted(disk - names):
            failures.append(f"  plugins/{missing}/ exists but is MISSING from {label}")
        for stale in sorted(names - disk):
            failures.append(f"  {label} names '{stale}', which has no plugins/{stale}/ directory")

    if failures:
        print(f"{len(failures)} release-wiring problem(s):")
        print("\n".join(failures))
        print(
            "\nAdding a plugin means adding it to all four lists. Two releases have already "
            "shipped with one of them missing (#46 for takt, #51 for lehre); a missing "
            "auto-version-bump matcher in particular fails silently, skipping the group."
        )
        return 1

    print(
        f"checked {len(disk)} plugin(s) against 4 release-wiring list(s): 0 failure(s) "
        f"({', '.join(sorted(disk))})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
