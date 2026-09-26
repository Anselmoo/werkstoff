"""Canonical resolution of the plugin cache and its install registry (#89).

Everything resolves ONCE at the boundary: the claude dir becomes a real path
immediately, every registry entry's `installPath` is resolved the same way, and
the cache scan itself yields only real (non-symlink) plugin and version
directories under the canonical cache root. Downstream code -- the doctor
report, the prune plan, and `apply_prune` -- works only with those canonical
values and plain equality; it never re-derives or re-resolves a path, and it
never compares by spelling.

That is the whole point: identity is decided on RESOLVED paths, on both sides.
A relative `--claude-dir`, or one reached through a symlink alias, names the
same cache as its canonical spelling. A registry key's plugin name that is
empty, `.`, `..`, or contains a path separator is dropped here, at the
boundary, and never reaches a `Path(...)` join. Nothing downstream can widen
that back out.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

REGISTRY_REL_PATH = Path("plugins") / "installed_plugins.json"
CACHE_REL_PATH = Path("plugins") / "cache"
DEFAULT_CLAUDE_DIRNAME = ".claude"
CLAUDE_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"


class CacheError(RuntimeError):
    """An expected failure resolving the registry: missing, unparseable, or
    non-UTF-8. Callers report this as a one-line error, never a traceback."""


@dataclass(frozen=True)
class PluginReport:
    """One `doctor` row: a plugin's live/cached state under this marketplace."""

    name: str
    live: str | None
    live_versions: tuple[str, ...]
    cached: tuple[str, ...]
    size_bytes: int
    not_in_marketplace: bool
    live_not_newest: bool


@dataclass(frozen=True)
class RemovalPlan:
    """One `prune` row: a stale, non-live cached version directory."""

    plugin: str
    version: str
    path: Path


def resolve_claude_dir(claude_dir: Path | str | None) -> Path:
    """--claude-dir, else $CLAUDE_CONFIG_DIR, else ~/.claude -- realpath'd
    immediately, whether it was given relative, absolute, or via a symlink
    alias. `Path.resolve()` is used deliberately (not `os.path.normpath`):
    this boundary WANTS symlinks followed, unlike the lexical-only guards
    documented in the root CLAUDE.md."""
    if claude_dir:
        chosen = Path(claude_dir)
    else:
        env_value = os.environ.get(CLAUDE_CONFIG_DIR_ENV)
        chosen = Path(env_value) if env_value else Path.home() / DEFAULT_CLAUDE_DIRNAME
    return chosen.resolve()


def _component_key(part: str) -> tuple[int, int | str]:
    """A dot-separated version component's sort key: numeric components
    compare as ints; anything else compares as a string, and the two never
    mix at the same position (comparisons only happen tag-to-tag)."""
    return (0, int(part)) if part.isdigit() else (1, part)


def version_key(version: str) -> tuple:
    """Numeric dot components; a pre-release ('1.0.0-rc1') sorts after every
    lower release and before its own release."""
    release, _, pre = version.partition("-")
    release_key = tuple(_component_key(part) for part in release.split("."))
    return (release_key, 0 if pre else 1, pre)


def _safe_component(name: str | None) -> bool:
    """A path component that is safe to join onto a directory: not empty,
    not `.`/`..`, and contains no path separator. Anything else never names
    a directory -- it is dropped at the boundary, before any `Path(...)`
    join happens."""
    return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name


def load_registry(claude_dir: Path) -> dict:
    """Parse `<claude_dir>/plugins/installed_plugins.json`.

    Raises CacheError -- a one-line message naming the file, no traceback --
    when it is missing, unparseable, or not valid UTF-8."""
    path = claude_dir / REGISTRY_REL_PATH
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CacheError(f"cannot read installed_plugins.json: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CacheError(f"installed_plugins.json is not valid UTF-8: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CacheError(f"installed_plugins.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CacheError("installed_plugins.json does not contain a JSON object")
    return data


def _live_entries_by_plugin(registry: dict, marketplace: str) -> dict[str, list[dict]]:
    """Every entry (every scope) under `<plugin>@<marketplace>`, keyed by a
    validated plugin name. A key naming another marketplace, or a plugin name
    that is empty, `.`, `..`, or contains a path separator, is dropped here."""
    by_plugin: dict[str, list[dict]] = {}
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        return by_plugin
    for key, entries in plugins.items():
        if not isinstance(key, str) or "@" not in key:
            continue
        name, _, mkt = key.partition("@")
        if mkt != marketplace or not _safe_component(name):
            continue
        if not isinstance(entries, list):
            continue
        by_plugin.setdefault(name, []).extend(e for e in entries if isinstance(e, dict))
    return by_plugin


def _live_dir(entry: dict, cache_root: Path, plugin: str) -> Path | None:
    """The resolved, real directory this entry names live. An `installPath`
    is realpath'd, whatever spelling it was recorded under; only an entry
    WITHOUT one falls back to its `version` string naming a directory under
    the plugin's cache root -- a version string never overrides a path."""
    install_path = entry.get("installPath")
    if install_path:
        return Path(install_path).resolve()
    version = entry.get("version")
    if isinstance(version, str) and _safe_component(version):
        return cache_root / plugin / version
    return None


def scan_cache(cache_root: Path) -> dict[str, list[Path]]:
    """Every real (non-symlink) version directory under every real
    (non-symlink) plugin directory of `cache_root`. A symlinked plugin dir or
    a symlinked version dir is skipped outright -- never yielded as a
    candidate for anything downstream, including removal."""
    found: dict[str, list[Path]] = {}
    if not cache_root.is_dir():
        return found
    for plugin_dir in sorted(cache_root.iterdir()):
        if plugin_dir.is_symlink() or not plugin_dir.is_dir():
            continue
        found[plugin_dir.name] = sorted(
            v for v in plugin_dir.iterdir() if v.is_dir() and not v.is_symlink()
        )
    return found


def _regular_bytes(root: Path) -> int:
    """Sum of `st_size` of regular files under `root`, recursively. A
    symlink is neither followed nor counted, matching the invariant that a
    cache's reported size must not include what a symlink merely points at."""
    if not root.is_dir():
        return 0
    total = 0
    for dirpath, _dirnames, filenames in root.walk():
        for fname in filenames:
            candidate = dirpath / fname
            if not candidate.is_symlink():
                total += candidate.lstat().st_size
    return total


def _world(
    claude_dir: Path, marketplace_name: str
) -> tuple[Path, dict[str, list[Path]], dict[str, list[Path]]]:
    """(cache_root, live_map, cached_map) -- the canonical inputs `doctor`
    and `prune` both build their answer from. Raises CacheError if the
    registry cannot be read."""
    registry = load_registry(claude_dir)
    cache_root = (claude_dir / CACHE_REL_PATH / marketplace_name).resolve()
    live_by_plugin = _live_entries_by_plugin(registry, marketplace_name)
    live_map: dict[str, list[Path]] = {}
    for plugin, entries in live_by_plugin.items():
        dirs = [d for e in entries if (d := _live_dir(e, cache_root, plugin)) is not None]
        if dirs:
            live_map[plugin] = dirs
    cached_map = scan_cache(cache_root)
    return cache_root, live_map, cached_map


def build_doctor_report(
    claude_dir: Path, marketplace_name: str, marketplace_plugin_names: frozenset[str]
) -> tuple[list[PluginReport], int]:
    """Every plugin found either in the cache or in the marketplace, read-only.

    Returns (reports sorted by name, total size in bytes across the whole
    cache root)."""
    cache_root, live_map, cached_map = _world(claude_dir, marketplace_name)
    names = set(cached_map) | set(marketplace_plugin_names) | set(live_map)
    reports = []
    total = 0
    for name in sorted(names):
        cached_paths = cached_map.get(name, [])
        cached_versions = tuple(sorted((p.name for p in cached_paths), key=version_key))
        live_paths = live_map.get(name, [])
        live_versions = tuple(sorted({p.name for p in live_paths}, key=version_key))
        live = live_versions[-1] if live_versions else None
        live_not_newest = (
            bool(cached_versions)
            and live is not None
            and (version_key(cached_versions[-1]) > version_key(live))
        )
        size_bytes = sum(_regular_bytes(p) for p in cached_paths)
        total += size_bytes
        reports.append(
            PluginReport(
                name=name,
                live=live,
                live_versions=live_versions,
                cached=cached_versions,
                size_bytes=size_bytes,
                not_in_marketplace=name not in marketplace_plugin_names,
                live_not_newest=live_not_newest,
            )
        )
    return reports, total


def build_prune_plan(claude_dir: Path, marketplace_name: str, keep: int) -> list[RemovalPlan]:
    """Every stale, non-live cached version directory of an INSTALLED
    plugin -- one with at least one live entry under this marketplace --
    keeping the `keep` newest non-live versions. An uninstalled plugin's
    cache, and every live directory, is never a candidate."""
    _cache_root, live_map, cached_map = _world(claude_dir, marketplace_name)
    plan: list[RemovalPlan] = []
    for plugin, live_paths in live_map.items():
        cached_paths = cached_map.get(plugin, [])
        if not cached_paths:
            continue
        live_set = set(live_paths)
        non_live = sorted(
            (p for p in cached_paths if p not in live_set), key=lambda p: version_key(p.name)
        )
        stale = non_live[:-keep] if keep > 0 else list(non_live)
        plan.extend(RemovalPlan(plugin=plugin, version=p.name, path=p) for p in stale)
    return plan


def apply_prune(
    plan: list[RemovalPlan],
) -> tuple[list[RemovalPlan], list[tuple[RemovalPlan, OSError]]]:
    """Remove every planned directory. A path already gone (a race, or a
    second run) is skipped -- not counted as removed, not a failure. Returns
    (removed, failures); the caller decides the exit code from `failures`."""
    removed: list[RemovalPlan] = []
    failures: list[tuple[RemovalPlan, OSError]] = []
    for item in plan:
        if not item.path.exists():
            continue
        try:
            shutil.rmtree(item.path)
        except OSError as exc:
            failures.append((item, exc))
        else:
            removed.append(item)
    return removed, failures
