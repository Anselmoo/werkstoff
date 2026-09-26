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
    """One `prune` row: a stale, non-live cached version directory, bound to
    the identity the cache root had when it was planned."""

    plugin: str
    version: str
    path: Path
    root_id: Identity | None = None


@dataclass(frozen=True)
class Protected:
    """Everything any registry entry could mean as a live install: resolved
    paths (to refuse a target that CONTAINS one) and (st_dev, st_ino)
    identities (to refuse one reached through an alias or a bind mount)."""

    paths: frozenset[Path]
    ids: frozenset[Identity]
    ancestors: frozenset[Path] = frozenset()


_RESOLVE_ERRORS = (OSError, RuntimeError, ValueError)


def resolve_claude_dir(claude_dir: Path | str | None) -> Path:
    """--claude-dir, else $CLAUDE_CONFIG_DIR, else ~/.claude -- realpath'd
    immediately, whether it was given relative, absolute, or via a symlink
    alias. `Path.resolve()` is used deliberately (not `os.path.normpath`):
    this boundary WANTS symlinks followed, unlike the lexical-only guards
    documented in the root CLAUDE.md. Raises CacheError for a path that
    cannot be resolved at all (a symlink loop, a NUL byte)."""
    if claude_dir:
        chosen = Path(claude_dir)
    else:
        env_value = os.environ.get(CLAUDE_CONFIG_DIR_ENV)
        chosen = Path(env_value) if env_value else Path.home() / DEFAULT_CLAUDE_DIRNAME
    try:
        return chosen.resolve()
    except _RESOLVE_ERRORS as exc:
        raise CacheError(f"cannot resolve the claude dir {str(chosen)!r}: {exc}") from exc


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


def _safe_component(name: object) -> bool:
    """A path component that is safe to join onto a directory: a non-empty
    string, not `.`/`..`, with no path separator and no NUL. Anything else
    never names a directory -- it is dropped at the boundary, before any
    `Path(...)` join happens."""
    return (
        isinstance(name, str)
        and bool(name)
        and name not in {".", ".."}
        and not any(ch in name for ch in "/\\\0")
    )


def _read_registry_bytes(claude_dir: Path) -> bytes:
    """The registry file's raw bytes, refusing anything but a regular file (a
    FIFO would block the read forever; a directory or device is no registry)."""
    path = claude_dir / REGISTRY_REL_PATH
    try:
        mode = path.stat().st_mode
    except _RESOLVE_ERRORS as exc:
        raise CacheError(f"cannot read installed_plugins.json: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise CacheError(f"installed_plugins.json is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CacheError(f"cannot read installed_plugins.json: {exc}") from exc


def _parse_registry(raw: bytes) -> dict:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CacheError(f"installed_plugins.json is not valid UTF-8: {exc}") from exc
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except _DuplicateKeyError as exc:
        raise CacheError(f"installed_plugins.json names a key twice: {exc}") from exc
    except (ValueError, RecursionError) as exc:
        # JSONDecodeError is a ValueError; so is an integer past Python's digit
        # limit. Absurd nesting raises RecursionError. All are "not a registry".
        raise CacheError(
            f"installed_plugins.json is not valid JSON: {type(exc).__name__}: {str(exc)[:120]}"
        ) from exc
    if not isinstance(data, dict):
        raise CacheError("installed_plugins.json does not contain a JSON object")
    return data


def load_registry(claude_dir: Path) -> dict:
    """Parse `<claude_dir>/plugins/installed_plugins.json`.

    Raises CacheError -- a one-line message naming the file, no traceback --
    when it is missing, not a regular file, not UTF-8, not JSON, absurdly
    nested, or names a key twice."""
    return _parse_registry(_read_registry_bytes(claude_dir))


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
    cannot be stat'd (missing, a loop, a NUL, permission)."""
    try:
        st = path.stat()
    except _RESOLVE_ERRORS:
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


def _interpretations(
    entry_key: str, entry: dict, bases: list[Path], cache_root: Path
) -> list[Path]:
    """Every path an entry could mean. Deliberately generous: a relative
    installPath is taken against every base, `~` is expanded, and an entry
    with no installPath protects the directory its version would name."""
    found: list[Path] = []
    install_path = entry.get("installPath")
    if isinstance(install_path, str) and install_path:
        try:
            raw = Path(install_path)
            if install_path.startswith("~"):
                found.append(raw.expanduser())
            elif raw.is_absolute():
                found.append(raw)
            else:
                found.extend(base / raw for base in bases)
        except _RESOLVE_ERRORS:
            pass
    version = entry.get("version")
    name = entry_key.partition("@")[0]
    if _safe_component(version) and _safe_component(name):
        found.append(cache_root / name / version)
    return found


def protected_for(registry: dict, claude_dir: Path, cache_root: Path) -> Protected:
    """Everything any registry entry could mean as a live install. Protecting
    too much only means a stale copy survives; protecting too little deletes a
    live one. Relative installPaths are tried against the claude dir, the
    registry's own directory, and the current directory."""
    bases = [claude_dir, claude_dir / REGISTRY_REL_PATH.parent]
    for base in (Path.cwd, Path.home):
        try:
            bases.append(base())
        except (OSError, RuntimeError, KeyError):
            pass  # a deleted cwd or an unknown home is simply one base fewer
    paths: set[Path] = set()
    ids: set[Identity] = set()
    for key, entry in _all_entries(registry):
        for candidate in _interpretations(key, entry, bases, cache_root):
            try:
                resolved = candidate.resolve(strict=True)
                st = resolved.stat()
            except _RESOLVE_ERRORS:
                continue
            paths.add(resolved)
            ids.add((st.st_dev, st.st_ino))
            paths.update(_version_dirs_on_the_way(candidate, resolved, cache_root))
    ancestors = {parent for path in paths for parent in path.parents}
    return Protected(paths=frozenset(paths), ids=frozenset(ids), ancestors=frozenset(ancestors))


def _version_dirs_on_the_way(candidate: Path, resolved: Path, cache_root: Path) -> set[Path]:
    """Every cached version dir the entry's own SPELLING passes through.

    `<cache>/andon/0.8.0/../0.12.0`, or `<cache>/andon/0.8.0/cur` where `cur`
    links elsewhere, resolves to a live directory -- but it stops resolving
    the moment 0.8.0 is removed, and the registry names the spelling, not the
    resolution. So each prefix of the spelling is resolved, and every
    `<cache>/<plugin>/<version>` it lands in is protected too. The common
    case -- a spelling that is already its own resolution -- is skipped."""
    absolute = Path(os.path.abspath(candidate))
    # os.path.abspath collapses ".." lexically, which is exactly what must
    # NOT be trusted here; the check below compares against the raw parts.
    if ".." not in candidate.parts and absolute == resolved:
        return set()
    found: set[Path] = set()
    prefix = Path(candidate.anchor) if candidate.is_absolute() else Path()
    for part in candidate.parts[1 if candidate.is_absolute() else 0 :]:
        prefix = prefix / part
        try:
            step = prefix.resolve(strict=True)
        except _RESOLVE_ERRORS:
            break
        if cache_root in step.parents:
            rel = step.relative_to(cache_root).parts
            if len(rel) >= 2:
                found.add(cache_root / rel[0] / rel[1])
    return found


def protected_identities(registry: dict, claude_dir: Path, cache_root: Path) -> set[Identity]:
    """The identity half of `protected_for`, for callers that only compare ids."""
    return set(protected_for(registry, claude_dir, cache_root).ids)


def _own_entries(registry: dict, marketplace: str) -> dict[str, object]:
    """The raw value under every `<plugin>@<marketplace>` key, by validated
    plugin name. A key naming another marketplace, or a plugin name that is
    not a safe path component, is dropped here."""
    plugins = registry.get("plugins")
    if not isinstance(plugins, dict):
        return {}
    by_plugin: dict[str, object] = {}
    for key, entries in plugins.items():
        if not isinstance(key, str) or "@" not in key:
            continue
        name, _, mkt = key.partition("@")
        if mkt == marketplace and _safe_component(name):
            by_plugin[name] = entries
    return by_plugin


def _version_fallback(version: object, plugin_dir: Path) -> tuple[Path | None, str]:
    """An entry with no installPath: the directory its version names, for
    doctor's display only -- the reason is always set, so prune skips it."""
    if _safe_component(version):
        try:
            resolved = (plugin_dir / str(version)).resolve(strict=True)
        except _RESOLVE_ERRORS:
            return None, f"entry has no installPath and {version!r} is not cached"
        if resolved.parent == plugin_dir and resolved.is_dir():
            return resolved, "entry has no installPath"
    return None, "entry has no installPath"


def _live_dir(entry: object, cache_root: Path, plugin: str) -> tuple[Path | None, str | None]:
    """(live directory, why it is unusable) for one entry.

    The directory is the entry's installPath resolved on disk, and it must be
    absolute, exist, BE A DIRECTORY, and resolve to exactly
    `<cache_root>/<plugin>/<dir>`. Anything else is returned as a reason
    instead, which makes the plugin's liveness unknown -- prune then skips
    the plugin rather than guess. An entry WITHOUT installPath names its
    `version` directory for doctor's display (resolved, so a symlinked
    version dir is followed), but is still unusable for prune: a version
    string never stands in for a path."""
    if not isinstance(entry, dict):
        return None, f"registry entry is not an object: {entry!r}"[:160]
    install_path = entry.get("installPath")
    plugin_dir = cache_root / plugin
    if install_path is None or install_path == "":
        return _version_fallback(entry.get("version"), plugin_dir)
    if not isinstance(install_path, str):
        return None, f"installPath is not a string: {install_path!r}"[:160]
    try:
        if not Path(install_path).is_absolute():
            return None, f"installPath is not absolute: {install_path!r}"
        resolved = Path(install_path).resolve(strict=True)
        is_dir = resolved.is_dir()
    except _RESOLVE_ERRORS:
        return None, f"installPath does not resolve: {install_path!r}"
    if resolved.parent != plugin_dir:
        return None, f"installPath is outside {plugin_dir}: {install_path!r}"
    if not is_dir:
        return None, f"installPath is not a directory: {install_path!r}"
    return resolved, None


def scan_cache(cache_root: Path) -> dict[str, list[Path]]:
    """Every real (non-symlink) version directory under every real
    (non-symlink) plugin directory of `cache_root`. Raises CacheError if a
    directory cannot be listed -- an unreadable cache is not an empty one."""
    try:
        return _scan_cache(cache_root)
    except OSError as exc:
        raise CacheError(f"cannot read the plugin cache: {exc}") from exc


def _scan_cache(cache_root: Path) -> dict[str, list[Path]]:
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
    protected: Protected


def cache_root_for(claude_dir: Path, marketplace_name: object) -> Path:
    """`realpath(<claude_dir>/plugins/cache/<marketplace>)`. Raises CacheError
    when the marketplace name could name anything but one directory, or the
    path cannot be resolved."""
    if not _safe_component(marketplace_name):
        raise CacheError(f"unsafe marketplace name in marketplace.json: {marketplace_name!r}")
    try:
        return (claude_dir / CACHE_REL_PATH / str(marketplace_name)).resolve()
    except _RESOLVE_ERRORS as exc:
        raise CacheError(f"cannot resolve the plugin cache: {exc}") from exc


def _plugin_liveness(
    entries: object, cache_root: Path, plugin: str
) -> tuple[list[Path], str | None]:
    """(live dirs, why liveness is unknown). An installed plugin must PROVE a
    live directory: an empty entry list, a non-list, or any entry that is not
    usable leaves its liveness unknown."""
    if not isinstance(entries, list) or not entries:
        return [], "no usable registry entry"
    dirs: list[Path] = []
    why: str | None = None
    for entry in entries:
        live, reason = _live_dir(entry, cache_root, plugin)
        if live is not None:
            dirs.append(live)
        if reason is not None and why is None:
            why = reason
    if why is None and not dirs:
        why = "no live directory proven"
    return dirs, why


def _world(claude_dir: Path, marketplace_name: str) -> _World:
    """Read the registry and the cache once. Raises CacheError if the registry
    cannot be read or the marketplace name is unsafe."""
    cache_root = cache_root_for(claude_dir, marketplace_name)
    registry = load_registry(claude_dir)
    live_map: dict[str, list[Path]] = {}
    unusable: dict[str, str] = {}
    for plugin, entries in _own_entries(registry, marketplace_name).items():
        dirs, why = _plugin_liveness(entries, cache_root, plugin)
        live_map[plugin] = dirs
        if why is not None:
            unusable[plugin] = why
    return _World(
        cache_root=cache_root,
        live_map=live_map,
        unusable=unusable,
        cached_map=scan_cache(cache_root),
        protected=protected_for(registry, claude_dir, cache_root),
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
    never a candidate. Every row is bound to the cache root's identity."""
    world = _world(claude_dir, marketplace_name)
    root_id = _identity(world.cache_root)
    plan: list[RemovalPlan] = []
    skipped: list[tuple[str, str]] = []
    for plugin in sorted(world.live_map):
        if plugin in world.unusable:
            skipped.append((plugin, world.unusable[plugin]))
            continue
        non_live = []
        for p in world.cached_map.get(plugin, []):
            if _identity(p) in world.protected.ids:
                continue
            why = _contents_refusal(p, world.protected)
            if why is not None:
                skipped.append((plugin, f"keeping {p.name}: {why}"))
                continue
            non_live.append(p)
        non_live.sort(key=lambda p: version_key(p.name))
        stale = non_live[:-keep] if keep > 0 else list(non_live)
        plan.extend(
            RemovalPlan(plugin=plugin, version=p.name, path=p, root_id=root_id) for p in stale
        )
    return plan, skipped


def _mount_points() -> list[Path]:
    """Every mount point this process can see (Linux), bind mounts included --
    a same-filesystem bind mount shares st_dev with its parent, so comparing
    devices alone cannot find it. Empty where /proc is unavailable."""
    try:
        raw = Path("/proc/self/mountinfo").read_bytes()
    except OSError:
        return []
    points = []
    for line in raw.splitlines():
        fields = line.split(b" ")
        if len(fields) > 4:
            unescaped = re.sub(rb"\\([0-7]{3})", lambda m: bytes([int(m[1], 8)]), fields[4])
            # fsdecode, not a lossy decode: a non-UTF-8 mount point must compare
            # equal to the same bytes held in a Path (surrogateescape).
            points.append(Path(os.fsdecode(unescaped)))
    return points


def _nesting_refusal(target: Path, protected: Protected) -> str | None:
    """A registry entry naming the target, something inside it, or a directory
    above it (other than its own plugin dir) makes it off-limits."""
    if target in protected.paths or target in protected.ancestors:
        return "a registry entry names it, or something inside it"
    for parent in target.parents:
        if parent in protected.paths and parent != target.parent:
            return f"a registry entry names {parent}, which contains it"
    for mount in _mount_points():
        if mount == target or target in mount.parents:
            return f"{mount} is a mount point inside it"
    return None


def _contents_refusal(target: Path, protected: Protected) -> str | None:
    """Refuse a target whose subtree holds something live or crosses a mount:
    `rmtree` would delete a nested live install along with its parent, and it
    walks straight into a mount point. Walks without following symlinks."""
    why = _nesting_refusal(target, protected)
    if why is not None:
        return why
    try:
        root_dev = target.lstat().st_dev
    except OSError as exc:
        return f"cannot stat {target}: {exc}"
    unreadable: list[OSError] = []
    for dirpath, dirnames, filenames in target.walk(on_error=unreadable.append):
        if unreadable:
            return f"cannot read inside {target}: {unreadable[0]}"
        for name in dirnames + filenames:
            try:
                st = (dirpath / name).lstat()
            except OSError as exc:
                return f"cannot stat {dirpath / name}: {exc}"
            if st.st_dev != root_dev:
                return f"{dirpath / name} is on another device"
            if (st.st_dev, st.st_ino) in protected.ids:
                return f"{dirpath / name} is live"
    if unreadable:
        return f"cannot read inside {target}: {unreadable[0]}"
    return None


def _refusal(
    item: RemovalPlan, cache_root: Path, protected: Protected
) -> tuple[str | None, tuple[Identity, Identity] | None]:
    """(why `item` must not be removed right now, or None; the (plugin dir,
    version dir) identities that were verified). Checked on the live
    filesystem, never on what the plan believed."""
    if not (_safe_component(item.plugin) and _safe_component(item.version)):
        return "unsafe plugin or version name", None
    if item.root_id is not None and _identity(cache_root) != item.root_id:
        return "the cache root changed since planning", None
    plugin_dir = cache_root / item.plugin
    target = plugin_dir / item.version
    ids: list[Identity] = []
    for step in (plugin_dir, target):
        try:
            st = step.lstat()
        except OSError:
            return f"{step} is gone", None
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            return f"{step} is not a real directory", None
        ids.append((st.st_dev, st.st_ino))
    if target.resolve() != target or Path(item.path).resolve() != target:
        return f"{item.path} does not resolve to {target}", None
    if ids[1] in protected.ids:
        return "a registry entry names it live", None
    why = _contents_refusal(target, protected)
    if why is not None:
        return why, None
    return None, (ids[0], ids[1])


def _remove_verified(cache_root: Path, item: RemovalPlan, ids: tuple[Identity, Identity]) -> None:
    """Remove `<cache_root>/<plugin>/<version>` through directory fds opened
    with O_NOFOLLOW and checked against the identities `_refusal` verified, so
    a plugin dir swapped for a symlink after the check is never followed.
    `shutil.rmtree(..., dir_fd=)` then removes the version dir relative to
    that verified fd without following symlinks inside it."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(cache_root, flags)
    try:
        plugin_fd = os.open(item.plugin, flags, dir_fd=root_fd)
        try:
            pst = os.fstat(plugin_fd)
            if (pst.st_dev, pst.st_ino) != ids[0]:
                raise OSError(f"refused: {item.plugin} changed after it was checked")
            vst = os.stat(item.version, dir_fd=plugin_fd, follow_symlinks=False)
            if not stat.S_ISDIR(vst.st_mode) or (vst.st_dev, vst.st_ino) != ids[1]:
                raise OSError(f"refused: {item.version} changed after it was checked")
            shutil.rmtree(item.version, dir_fd=plugin_fd)
        finally:
            os.close(plugin_fd)
    finally:
        os.close(root_fd)


def apply_prune(
    plan: list[RemovalPlan], claude_dir: Path, marketplace_name: str
) -> tuple[list[RemovalPlan], list[tuple[RemovalPlan, str]]]:
    """Remove every planned directory that still proves safe to remove.

    Trusts nothing the plan computed: before EACH removal the registry is
    re-read (and the protected set re-derived whenever its bytes changed), the
    cache root is checked against the identity the plan was bound to, and the
    path is re-proved (see `_refusal`); removal then goes through verified
    directory fds (see `_remove_verified`). A path already gone is skipped --
    not removed, not a failure. If the registry becomes unreadable mid-run,
    every remaining item fails with that reason and what was already removed
    is still returned. Returns (removed, failures)."""
    removed: list[RemovalPlan] = []
    failures: list[tuple[RemovalPlan, str]] = []
    try:
        cache_root = cache_root_for(claude_dir, marketplace_name)
    except CacheError as exc:
        return removed, [(item, f"refused: {exc}") for item in plan]
    seen: bytes | None = None
    protected = Protected(paths=frozenset(), ids=frozenset())
    for index, item in enumerate(plan):
        try:
            if not item.path.exists() and not item.path.is_symlink():
                continue
        except OSError as exc:
            failures.append((item, f"refused: cannot stat {item.path}: {exc}"))
            continue
        try:
            raw = _read_registry_bytes(claude_dir)
            if raw != seen:
                protected = protected_for(_parse_registry(raw), claude_dir, cache_root)
                seen = raw
        except CacheError as exc:
            failures.extend((rest, f"refused: {exc}") for rest in plan[index:])
            break
        why, ids = _refusal(item, cache_root, protected)
        if why is not None or ids is None:
            failures.append((item, f"refused: {why}"))
            continue
        try:
            _remove_verified(cache_root, item, ids)
        except (OSError, RecursionError) as exc:
            # shutil.rmtree recurses; a pathologically deep tree raises
            # RecursionError after a partial removal. Report it, keep going.
            failures.append((item, f"{type(exc).__name__}: {str(exc)[:200]}"))
        else:
            removed.append(item)
    return removed, failures
