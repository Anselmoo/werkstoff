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

Hardening after run ap-2026-09-26-889c's land review, which reproduced six
ways the above still removed a live install:

- prune FAILS CLOSED PER PLUGIN. A plugin is prunable only when every entry
  names an absolute, existing installPath that resolves inside
  `<cache_root>/<plugin>/`. An entry with no installPath, a relative or `~`
  one, one that no longer exists, or one resolving elsewhere makes the
  plugin's liveness unknown, and an unknown is skipped, never guessed at.
- Nothing ANY registry entry names -- under any key, any marketplace, even a
  legacy key with no `@` -- is removed. That set is compared by
  (st_dev, st_ino), so a bind-mount alias or a case-folding filesystem cannot
  make a live directory look like a different one.
- The marketplace name must itself be a safe path component.
- `apply_prune` trusts nothing the plan computed: immediately before each
  removal it re-reads the registry, re-derives the protected set and the
  cache root, and proves the path is a real directory, reached through no
  symlink, at exactly `<cache_root>/<plugin>/<version>`, and not protected.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

REGISTRY_REL_PATH = Path("plugins") / "installed_plugins.json"
CACHE_REL_PATH = Path("plugins") / "cache"
DEFAULT_CLAUDE_DIRNAME = ".claude"
CLAUDE_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"


class CacheError(RuntimeError):
    """An expected failure resolving the registry or the cache: missing,
    unparseable, non-UTF-8, duplicate-keyed, not a regular file, or an unsafe
    marketplace name. Callers report this as a one-line error, never a
    traceback."""


class _DuplicateKeyError(ValueError):
    """A JSON object names the same key twice; `json` would silently keep one."""


Identity = tuple[int, int]


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
    live_unknown: str | None = None


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


def _component_key(part: str) -> tuple[tuple[int, int | str], ...]:
    """A dot-separated version component's sort key, split into digit and
    non-digit runs so 'rc10' sorts after 'rc9' and '10' after '9'. Each run is
    tagged (0, int) or (1, str), so an int is never compared with a str."""
    return tuple(
        (0, int(run)) if run.isdigit() else (1, run) for run in re.findall(r"\d+|\D+", part)
    )


def version_key(version: str) -> tuple:
    """Numeric dot components; a pre-release ('1.0.0-rc1') sorts after every
    lower release and before its own release, and its own tags compare
    numerically too ('rc.10' after 'rc.2')."""
    release, _, pre = version.partition("-")
    release_key = tuple(_component_key(part) for part in release.split("."))
    pre_key = tuple(_component_key(part) for part in pre.split(".")) if pre else ()
    return (release_key, 0 if pre else 1, pre_key)


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
        mode = path.stat().st_mode
    except OSError as exc:
        raise CacheError(f"cannot read installed_plugins.json: {exc}") from exc
    if not stat.S_ISREG(mode):
        # A FIFO would block the read forever; a directory or device is not a registry.
        raise CacheError(f"installed_plugins.json is not a regular file: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CacheError(f"cannot read installed_plugins.json: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CacheError(f"installed_plugins.json is not valid UTF-8: {exc}") from exc
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except _DuplicateKeyError as exc:
        raise CacheError(f"installed_plugins.json names a key twice: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CacheError(f"installed_plugins.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CacheError("installed_plugins.json does not contain a JSON object")
    return data


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    """`json` keeps only the last of two equal keys; a live install named by the
    first would silently vanish from the live set. Refuse instead."""
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(repr(key))
        result[key] = value
    return result


def _identity(path: Path) -> Identity | None:
    """(st_dev, st_ino) of what `path` names, following symlinks; None if it
    cannot be stat'd (missing, a loop, permission)."""
    try:
        st = path.stat()
    except (OSError, RuntimeError, ValueError):
        return None
    return (st.st_dev, st.st_ino)


def _all_entries(registry: dict) -> list[tuple[str, dict]]:
    """(key, entry) for EVERY entry under EVERY key -- any marketplace, a legacy
    key with no `@`, a list or a single object."""
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        return []
    found = []
    for key, entries in plugins.items():
        items = entries if isinstance(entries, list) else [entries]
        found.extend((str(key), e) for e in items if isinstance(e, dict))
    return found


def protected_identities(registry: dict, claude_dir: Path, cache_root: Path) -> set[Identity]:
    """Everything any registry entry could mean as a live install, by identity.
    Deliberately generous: a relative installPath is taken both against the
    claude dir and the current directory, `~` is expanded, and an entry with
    no installPath protects the directory its version would name. Protecting
    too much only means a stale copy survives; protecting too little deletes a
    live one."""
    candidates: list[Path] = []
    for key, entry in _all_entries(registry):
        install_path = entry.get("installPath")
        if isinstance(install_path, str) and install_path:
            raw = Path(install_path)
            if install_path.startswith("~"):
                candidates.append(raw.expanduser())
            elif raw.is_absolute():
                candidates.append(raw)
            else:
                candidates.extend([claude_dir / raw, Path.cwd() / raw])
        version = entry.get("version")
        name = key.partition("@")[0]
        if isinstance(version, str) and _safe_component(version) and _safe_component(name):
            candidates.append(cache_root / name / version)
    return {ident for p in candidates if (ident := _identity(p)) is not None}


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


def _live_dir(entry: dict, cache_root: Path, plugin: str) -> tuple[Path | None, str | None]:
    """(live directory, why it is unusable) for one entry.

    The directory is the entry's installPath resolved on disk, and it must be
    absolute, exist, and resolve to exactly `<cache_root>/<plugin>/<dir>`.
    Anything else is returned as a reason instead, which makes the plugin's
    liveness unknown -- prune then skips the plugin rather than guess. An
    entry WITHOUT installPath names its `version` directory for doctor's
    display (resolved, so a symlinked version dir is followed), but is still
    unusable for prune: a version string never stands in for a path."""
    install_path = entry.get("installPath")
    plugin_dir = cache_root / plugin
    if install_path is None or install_path == "":
        version = entry.get("version")
        if isinstance(version, str) and _safe_component(version):
            try:
                resolved = (plugin_dir / version).resolve(strict=True)
            except (OSError, RuntimeError):
                return None, f"entry has no installPath and {version!r} is not cached"
            if resolved.parent == plugin_dir:
                return resolved, "entry has no installPath"
        return None, "entry has no installPath"
    if not isinstance(install_path, str):
        return None, f"installPath is not a string: {install_path!r}"
    if not Path(install_path).is_absolute():
        return None, f"installPath is not absolute: {install_path}"
    try:
        resolved = Path(install_path).resolve(strict=True)
    except (OSError, RuntimeError):
        return None, f"installPath does not exist: {install_path}"
    if resolved.parent != plugin_dir:
        return None, f"installPath is outside {plugin_dir}: {install_path}"
    return resolved, None


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


@dataclass(frozen=True)
class _World:
    """The canonical inputs `doctor` and `prune` both build their answer from."""

    cache_root: Path
    live_map: dict[str, list[Path]]
    unusable: dict[str, str]
    cached_map: dict[str, list[Path]]
    protected: set[Identity]


def cache_root_for(claude_dir: Path, marketplace_name: str) -> Path:
    """`realpath(<claude_dir>/plugins/cache/<marketplace>)`. Raises CacheError
    when the marketplace name could name anything but one directory."""
    if not _safe_component(marketplace_name):
        raise CacheError(f"unsafe marketplace name in marketplace.json: {marketplace_name!r}")
    return (claude_dir / CACHE_REL_PATH / marketplace_name).resolve()


def _world(claude_dir: Path, marketplace_name: str) -> _World:
    """Read the registry and the cache once. Raises CacheError if the registry
    cannot be read or the marketplace name is unsafe."""
    cache_root = cache_root_for(claude_dir, marketplace_name)
    registry = load_registry(claude_dir)
    live_map: dict[str, list[Path]] = {}
    unusable: dict[str, str] = {}
    for plugin, entries in _live_entries_by_plugin(registry, marketplace_name).items():
        dirs = []
        for entry in entries:
            live, why = _live_dir(entry, cache_root, plugin)
            if live is not None:
                dirs.append(live)
            if why is not None and plugin not in unusable:
                unusable[plugin] = why
        live_map[plugin] = dirs
    return _World(
        cache_root=cache_root,
        live_map=live_map,
        unusable=unusable,
        cached_map=scan_cache(cache_root),
        protected=protected_identities(registry, claude_dir, cache_root),
    )


def build_doctor_report(
    claude_dir: Path, marketplace_name: str, marketplace_plugin_names: frozenset[str]
) -> tuple[list[PluginReport], int]:
    """Every plugin found either in the cache or in the marketplace, read-only.

    Returns (reports sorted by name, total size in bytes across the whole
    cache root)."""
    world = _world(claude_dir, marketplace_name)
    live_map, cached_map = world.live_map, world.cached_map
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
                live_unknown=world.unusable.get(name),
            )
        )
    return reports, total


def build_prune_plan(
    claude_dir: Path, marketplace_name: str, keep: int
) -> tuple[list[RemovalPlan], list[tuple[str, str]]]:
    """(plan, skipped). The plan is every stale, non-protected cached version
    directory of an INSTALLED plugin -- one with at least one entry under this
    marketplace -- keeping the `keep` newest. `skipped` names each installed
    plugin whose liveness is unknown, with why; nothing of it is planned. An
    uninstalled plugin's cache, and anything any registry entry names, is
    never a candidate."""
    world = _world(claude_dir, marketplace_name)
    plan: list[RemovalPlan] = []
    skipped: list[tuple[str, str]] = []
    for plugin in sorted(world.live_map):
        if plugin in world.unusable:
            skipped.append((plugin, world.unusable[plugin]))
            continue
        non_live = sorted(
            (p for p in world.cached_map.get(plugin, []) if _identity(p) not in world.protected),
            key=lambda p: version_key(p.name),
        )
        stale = non_live[:-keep] if keep > 0 else list(non_live)
        plan.extend(RemovalPlan(plugin=plugin, version=p.name, path=p) for p in stale)
    return plan, skipped


def _refusal(item: RemovalPlan, cache_root: Path, protected: set[Identity]) -> str | None:
    """Why `item` must not be removed right now, or None. Checked on the live
    filesystem, never on what the plan believed."""
    if not (_safe_component(item.plugin) and _safe_component(item.version)):
        return "unsafe plugin or version name"
    plugin_dir = cache_root / item.plugin
    target = plugin_dir / item.version
    for step in (plugin_dir, target):
        try:
            mode = step.lstat().st_mode
        except OSError:
            return f"{step} is gone"
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            return f"{step} is not a real directory"
    if target.resolve() != target or Path(item.path).resolve() != target:
        return f"{item.path} does not resolve to {target}"
    if _identity(target) in protected:
        return "a registry entry names it live"
    return None


def apply_prune(
    plan: list[RemovalPlan], claude_dir: Path, marketplace_name: str
) -> tuple[list[RemovalPlan], list[tuple[RemovalPlan, str]]]:
    """Remove every planned directory that still proves safe to remove.

    Trusts nothing the plan computed: the registry is re-read, and the cache
    root and protected set are re-derived, then each path is re-proved
    immediately before its removal (see `_refusal`). A path already gone is
    skipped -- not removed, not a failure. Returns (removed, failures); the
    caller decides the exit code from `failures`. Raises CacheError if the
    registry has become unreadable."""
    cache_root = cache_root_for(claude_dir, marketplace_name)
    removed: list[RemovalPlan] = []
    failures: list[tuple[RemovalPlan, str]] = []
    for item in plan:
        if not item.path.exists() and not item.path.is_symlink():
            continue
        registry = load_registry(claude_dir)
        why = _refusal(item, cache_root, protected_identities(registry, claude_dir, cache_root))
        if why is not None:
            failures.append((item, f"refused: {why}"))
            continue
        try:
            shutil.rmtree(item.path)
        except OSError as exc:
            failures.append((item, str(exc)))
        else:
            removed.append(item)
    return removed, failures
