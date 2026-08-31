#!/usr/bin/env python3
"""Guard against plugin author-attribution drift between per-plugin manifests
and the root marketplace manifest.

`.claude-plugin/marketplace.json` is the source of truth for who authored
each of werkstoff's plugins, and credits "Anselm Hahn" correctly for all of
them. But the Claude Code plugin UI displays the *per-plugin* manifest's
`author` field on each plugin's card
(`plugins/<name>/.claude-plugin/plugin.json`), not the marketplace entry --
and three of those manifests were found still carrying scaffold placeholders
("andon plugin" / "confab contributors" / "self-assess contributors", each
paired with `noreply@example.com` or missing `author.email` entirely) left
over from whatever generator first created them. Nothing caught that drift
because nothing compared the two files. This is that comparison, run as a
static check so the drift cannot silently return.

What it checks, per plugin found on disk under `plugins/*/.claude-plugin/`:
    1. Every plugin directory has a matching entry in marketplace.json, and
       vice versa. A plugin present on disk but absent from marketplace.json
       is a failure, not a skip -- so is a marketplace entry with no plugin
       directory. Silent skips are the failure mode this repo documents most
       often (see CLAUDE.md's defect table).
    2. Each plugin.json declares an `author` key at all, with a non-empty
       `author.name`.
    3. `author.name` in plugin.json agrees, by exact string equality, with
       `author.name` in that plugin's marketplace.json entry. `email` vs
       `url` is an allowed variation (codebase-consistency legitimately uses
       `url` instead of `email`) -- only `name` is compared for equality.
    4. Neither file's `author.email`, wherever it appears, is the scaffold
       placeholder `noreply@example.com`.
    5. Neither file's `author.name`, wherever it appears, matches the shape
       "<plugin-name> plugin" or "<plugin-name> contributors" (case
       insensitive), the two placeholder shapes actually found in this repo.

The plugin list is derived from the filesystem (`plugins/*/.claude-plugin/
plugin.json`) every run, never hardcoded -- a hardcoded list here would be
exactly the kind of drift this tool exists to catch elsewhere.

House style, matched from tools/catalog-validator/validate_catalog.py:
collect every failure across every file rather than stopping at the first
one, raise a named exception class for anything that must fail loudly
instead of returning a partial/empty result, and print one summary line
stating how many manifests were checked.

Usage:
    python3 test/plugins/lint-plugin-authors.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeGuard

REPO = Path(__file__).resolve().parents[2]
PLUGINS_DIR = REPO / "plugins"
MARKETPLACE_PATH = REPO / ".claude-plugin" / "marketplace.json"

PLACEHOLDER_EMAIL = "noreply@example.com"


class PluginAuthorLintError(RuntimeError):
    """Raised for anything that must fail loudly rather than silently under-report."""


@dataclass
class LintReport:
    failures: list[str] = field(default_factory=list)
    manifests_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def _is_nonempty_str(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())


def load_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PluginAuthorLintError(f"{path}: cannot read: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PluginAuthorLintError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PluginAuthorLintError(f"{path}: expected a JSON object at the top level")
    return data


def discover_plugin_manifests(plugins_dir: Path) -> dict[str, Path]:
    """Map plugin directory name -> its plugin.json path, derived live from
    the filesystem every run. Never hardcoded -- see module docstring.
    """
    if not plugins_dir.is_dir():
        raise PluginAuthorLintError(f"no plugins directory found at {plugins_dir}")
    found: dict[str, Path] = {}
    for child in sorted(plugins_dir.iterdir()):
        if not child.is_dir():
            continue
        manifest = child / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            found[child.name] = manifest
    return found


def load_marketplace_entries(marketplace_path: Path) -> dict[str, dict]:
    if not marketplace_path.is_file():
        raise PluginAuthorLintError(f"{marketplace_path}: not found")
    data = load_json(marketplace_path)
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        raise PluginAuthorLintError(f"{marketplace_path}: expected a 'plugins' list")
    entries: dict[str, dict] = {}
    for entry in plugins:
        if isinstance(entry, dict) and _is_nonempty_str(entry.get("name")):
            entries[entry["name"]] = entry
    return entries


# --------------------------------------------------------------------------
# Placeholder / drift checks
# --------------------------------------------------------------------------


def is_placeholder_name(name: str, plugin_dir_name: str) -> bool:
    lowered = name.strip().lower()
    plugin_lower = plugin_dir_name.strip().lower()
    return lowered in {f"{plugin_lower} plugin", f"{plugin_lower} contributors"}


def check_author(author: object, source: str, plugin_dir_name: str) -> list[str]:
    """Check one author block (from either plugin.json or a marketplace
    entry) for a missing name, a placeholder name shape, or a placeholder
    email -- independent of the cross-file name-equality check.
    """
    failures: list[str] = []
    if not isinstance(author, dict):
        failures.append(f"{source}: missing or malformed 'author' key")
        return failures

    name = author.get("name")
    if not _is_nonempty_str(name):
        failures.append(f"{source}: 'author.name' is missing or empty")
    elif is_placeholder_name(name, plugin_dir_name):
        failures.append(f"{source}: 'author.name' is a scaffold placeholder: '{name}'")

    email = author.get("email")
    if isinstance(email, str) and email.strip().lower() == PLACEHOLDER_EMAIL:
        failures.append(f"{source}: 'author.email' is the scaffold placeholder '{PLACEHOLDER_EMAIL}'")

    return failures


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def lint() -> LintReport:
    report = LintReport()
    plugin_manifests = discover_plugin_manifests(PLUGINS_DIR)
    marketplace_entries = load_marketplace_entries(MARKETPLACE_PATH)
    marketplace_rel = MARKETPLACE_PATH.relative_to(REPO)

    disk_names = set(plugin_manifests)
    marketplace_names = set(marketplace_entries)

    for name in sorted(disk_names - marketplace_names):
        report.failures.append(
            f"plugins/{name}: present on disk but has no entry in {marketplace_rel}"
        )
    for name in sorted(marketplace_names - disk_names):
        report.failures.append(
            f"{marketplace_rel}: entry '{name}' has no corresponding "
            f"plugins/{name}/.claude-plugin/plugin.json"
        )

    for name in sorted(disk_names & marketplace_names):
        manifest_path = plugin_manifests[name]
        rel_manifest = manifest_path.relative_to(REPO)
        report.manifests_checked += 1

        manifest = load_json(manifest_path)
        plugin_author = manifest.get("author")
        market_author = marketplace_entries[name].get("author")

        report.failures.extend(check_author(plugin_author, str(rel_manifest), name))
        report.failures.extend(
            check_author(market_author, f"{marketplace_rel} (plugin '{name}')", name)
        )

        if isinstance(plugin_author, dict) and isinstance(market_author, dict):
            plugin_name_value = plugin_author.get("name")
            market_name_value = market_author.get("name")
            if (
                _is_nonempty_str(plugin_name_value)
                and _is_nonempty_str(market_name_value)
                and plugin_name_value != market_name_value
            ):
                report.failures.append(
                    f"{rel_manifest}: author.name '{plugin_name_value}' disagrees with "
                    f"{marketplace_rel}'s '{market_name_value}' for plugin '{name}'"
                )

    return report


def render_report(report: LintReport) -> str:
    lines = list(report.failures)
    lines.append(
        f"checked {report.manifests_checked} plugin manifest(s) against "
        f"{MARKETPLACE_PATH.relative_to(REPO)}: {len(report.failures)} failure(s)"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        report = lint()
    except PluginAuthorLintError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = render_report(report)
    if report.ok:
        print(output)
        return 0
    print(output, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
