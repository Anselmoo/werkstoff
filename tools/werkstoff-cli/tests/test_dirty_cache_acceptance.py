"""Acceptance for `werkstoff doctor` / `werkstoff prune` (#89), judged on a DIRTY cache.

An empty plugin cache proves nothing about a prune: a no-op passes, a prune that
deletes the live version passes, a lexical version sort passes. So every test here
first builds a cache that is deliberately dirtied with the cases that separate a
correct implementation from a plausible one, and asserts the dirt is present before
grading anything:

    andon      0.8.0 0.10.2 0.11.1   live 0.12.0   ordinary stale versions (and a second
               0.12.0                              lexical trap); 0.8.0 holds a directory
                                                   AND a file symlink escaping the cache
    cupertino  0.6.0 0.9.1 0.10.0    live 0.10.0   lexical-sort trap: "0.9.1" > "0.10.0"
    takt       0.1.0 0.2.0           live 0.1.0    half-applied upgrade: live is not newest
    compass    0.4.0 0.9.0           not installed, not in the marketplace: an orphan

Interface under test (frozen before any implementation existed):

    werkstoff doctor [--claude-dir DIR] [--repo REPO] [--json]
    werkstoff prune  [--claude-dir DIR] [--repo REPO] [--keep N=1] [--apply] [--json]

    claude dir: --claude-dir, else $CLAUDE_CONFIG_DIR, else ~/.claude
    registry:   <dir>/plugins/installed_plugins.json
    cache:      <dir>/plugins/cache/<marketplace>/<plugin>/<version>/

    live set:   for plugin P, EVERY entry (every scope) under the registry key
                "P@<this marketplace>"; keys naming another marketplace are ignored.
                A cached version directory is live iff its path equals one of those
                entries' installPath; only an entry WITHOUT installPath falls back to
                its "version" naming the directory. Version strings never override a
                path: a git-sha directory registered as version "1.0.0" is still live.
    version order: numeric dot components; a pre-release ("1.0.0-rc1") sorts after
                every lower release and before its own release.

    doctor --json -> {"marketplace", "totalSizeBytes",
                      "plugins": [{"name", "live", "liveVersions", "cached", "sizeBytes",
                                   "notInMarketplace", "liveNotNewest"}]}
        cached        every cached version directory, ascending by version order
        liveVersions  every live directory name, ascending; [] when not installed
        live          the newest of liveVersions, or null
        liveNotNewest a cached version newer than the newest live one exists
        sizeBytes     sum of st_size of regular files; symlinks neither followed nor counted
    prune --json  -> {"apply", "keep", "remove": [{"plugin", "version", "path"}]}
        remove     installed plugins only; never ANY live directory; keeps the N newest
                   non-live versions; an uninstalled plugin's cache is left alone
        --keep < 0 -> a usage error (exit 2), nothing removed
    prune FAILS CLOSED PER PLUGIN: a plugin is prunable only when EVERY one of its entries
        names an absolute, existing installPath resolving inside
        realpath(cache/<marketplace>)/<plugin>/ -- otherwise its liveness is unknown and it
        is skipped, never guessed at (an entry with no installPath, a relative or "~"
        installPath, one that no longer exists). Nothing that ANY registry entry names,
        under any key or marketplace, is ever removed; identity is (st_dev, st_ino), not
        spelling. The marketplace name must itself be a safe path component. `prune --apply
        --json` adds "removed" and "failed" (what actually happened, not the plan).
    a missing, unparseable, undecodable (non-UTF-8), duplicate-keyed or non-regular-file
        registry -> exit 1 with a one-line
        error naming installed_plugins.json and no traceback, for doctor and prune alike;
        prune removes nothing (the live set is a gating value; it is never inferred)

    THE INVARIANT (what every case below is an instance of), after any `prune --apply`:
        every directory the registry names as live still exists, and every path that
        disappeared lies, after resolving symlinks, strictly inside
        realpath(<claude-dir>/plugins/cache/<marketplace>)/<plugin>/<version>.
    Identity is therefore decided on RESOLVED paths, on both sides: a relative
    --claude-dir, or one reached through a symlink alias, is the same cache, whichever
    spelling the registry recorded. A registry key's plugin name that is empty, "." or
    "..", or contains a path separator, never names a directory. Nothing is pruned
    through a symlink -- neither a symlinked version dir nor a symlinked plugin dir.

The registry-shape cases (multi-scope installs, another marketplace's key, an
installPath that is not the version string) were added after a first run: both of its
candidates passed every case above and still scheduled LIVE installs for deletion in
those shapes. A contract that never states them is a contract that permits them. A
second run then passed every stated shape and deleted live installs through path
SPELLING instead (a relative or aliased claude dir, "..", a symlinked plugin dir) -- so
the contract now states the invariant itself, and those tests check outcomes, not
mechanisms.

This file sits outside every candidate's write scope on purpose: an instrument the
thing it grades can edit is not an instrument.
"""

import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from werkstoff.cli import app

runner = CliRunner(
    env={
        "COLUMNS": "80",
        "NO_COLOR": "1",
        "GITHUB_ACTIONS": "",
        "FORCE_COLOR": "",
        "CLICOLOR_FORCE": "",
        "CLAUDE_CONFIG_DIR": "",
    }
)

CACHED = {
    "andon": ["0.8.0", "0.10.2", "0.11.1", "0.12.0"],
    "cupertino": ["0.6.0", "0.9.1", "0.10.0"],
    "takt": ["0.1.0", "0.2.0"],
    "compass": ["0.4.0", "0.9.0"],
}
LIVE = {"andon": "0.12.0", "cupertino": "0.10.0", "takt": "0.1.0"}
MARKETPLACE_PLUGINS = ["andon", "cupertino", "takt", "befund"]


def _write_marketplace(root: Path) -> Path:
    manifest_dir = root / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    plugins = [
        {"name": n, "description": "d", "source": f"./plugins/{n}"} for n in MARKETPLACE_PLUGINS
    ]
    (manifest_dir / "marketplace.json").write_text(
        json.dumps({"name": "werkstoff", "plugins": plugins})
    )
    return root


def _plant_version(vdir: Path, name: str, version: str) -> None:
    (vdir / ".claude-plugin").mkdir(parents=True)
    (vdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": name, "version": version})
    )
    (vdir / "hooks").mkdir()
    (vdir / "hooks" / "guard.py").write_text(f"# {name} {version}\n" + "x = 1\n" * 50)
    # Stale bytecode, exactly what #88 describes leaking into installed copies.
    (vdir / "scripts" / "__pycache__").mkdir(parents=True)
    (vdir / "scripts" / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"\0" * 777)


def _regular_bytes(root: Path) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            p = Path(dirpath) / f
            if not p.is_symlink():
                total += p.lstat().st_size
    return total


def _snapshot(root: Path) -> dict[str, tuple[int, int, bool]]:
    snap = {}
    for dirpath, dirs, files in os.walk(root):
        for name in dirs + files:
            p = Path(dirpath) / name
            st = p.lstat()
            snap[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns, p.is_symlink())
    return snap


@pytest.fixture
def dirty(tmp_path: Path) -> dict:
    claude = tmp_path / "claude-home"
    cache = claude / "plugins" / "cache" / "werkstoff"
    for name, versions in CACHED.items():
        for version in versions:
            _plant_version(cache / name / version, name, version)

    # A symlink inside a stale version pointing OUT of the cache, at a large file.
    # A prune that follows it deletes something it does not own; a size that
    # follows it over-reports by a megabyte.
    sentinel = tmp_path / "outside" / "precious"
    sentinel.mkdir(parents=True)
    (sentinel / "keep-me.bin").write_bytes(b"\1" * 1_000_000)
    (cache / "andon" / "0.8.0" / "escape").symlink_to(sentinel, target_is_directory=True)
    (cache / "andon" / "0.8.0" / "escape.bin").symlink_to(sentinel / "keep-me.bin")

    registry = {
        "version": 2,
        "plugins": {
            f"{name}@werkstoff": [
                {
                    "scope": "user",
                    "installPath": str(cache / name / version),
                    "version": version,
                }
            ]
            for name, version in LIVE.items()
        },
    }
    (claude / "plugins" / "installed_plugins.json").write_text(json.dumps(registry))
    repo = _write_marketplace(tmp_path / "repo")

    # The dirt must be there before anything is graded -- an empty cache proves nothing.
    stale = [
        v for n, vs in CACHED.items() for v in vs if (cache / n / v).is_dir() and LIVE.get(n) != v
    ]
    assert len(stale) >= 6, stale
    assert _regular_bytes(cache) > 0
    assert (cache / "andon" / "0.8.0" / "escape").is_symlink()

    return {"claude": claude, "cache": cache, "repo": repo, "sentinel": sentinel}


def _invoke(d: dict, *args: str) -> tuple[int, str]:
    argv = [args[0], "--claude-dir", str(d["claude"]), "--repo", str(d["repo"]), *args[1:]]
    result = runner.invoke(app, argv)
    return result.exit_code, result.output


def _json(d: dict, *args: str) -> dict:
    code, out = _invoke(d, *args, "--json")
    assert code == 0, f"exit {code}: {out}"
    return json.loads(out)


def _removed(cache: Path) -> set[str]:
    return {f"{n}/{v}" for n, vs in CACHED.items() for v in vs if not (cache / n / v).exists()}


def _plugin(report: dict, name: str) -> dict:
    matches = [p for p in report["plugins"] if p["name"] == name]
    assert len(matches) == 1, f"{name} not reported exactly once: {report['plugins']}"
    return matches[0]


def test_doctor_reports_the_dirt_and_changes_nothing(dirty) -> None:
    before = _snapshot(dirty["claude"])
    report = _json(dirty, "doctor")
    assert _snapshot(dirty["claude"]) == before, "doctor must be read-only"

    andon = _plugin(report, "andon")
    assert andon["live"] == "0.12.0"
    assert andon["cached"] == ["0.8.0", "0.10.2", "0.11.1", "0.12.0"]
    assert andon["liveNotNewest"] is False
    assert andon["notInMarketplace"] is False
    # Exact: regular files only, the symlinked megabyte neither followed nor counted.
    assert andon["sizeBytes"] == _regular_bytes(dirty["cache"] / "andon")

    cupertino = _plugin(report, "cupertino")
    assert cupertino["cached"] == ["0.6.0", "0.9.1", "0.10.0"], "numeric order, not lexical"
    assert cupertino["liveNotNewest"] is False, "0.10.0 IS the newest -- lexical sort says not"

    takt = _plugin(report, "takt")
    assert takt["live"] == "0.1.0"
    assert takt["liveNotNewest"] is True, "a newer 0.2.0 is cached: a half-applied upgrade"

    compass = _plugin(report, "compass")
    assert compass["notInMarketplace"] is True
    assert compass["live"] is None

    assert report["totalSizeBytes"] == _regular_bytes(dirty["cache"])


def test_doctor_human_output_names_the_problems(dirty) -> None:
    code, out = _invoke(dirty, "doctor")
    assert code == 0, out
    for needle in ("andon", "cupertino", "takt", "compass", "0.12.0"):
        assert needle in out, f"{needle!r} missing from doctor output:\n{out}"


def test_prune_is_a_dry_run_by_default(dirty) -> None:
    before = _snapshot(dirty["claude"])
    plan = _json(dirty, "prune")
    assert _snapshot(dirty["claude"]) == before, "prune without --apply must touch nothing"
    assert plan["apply"] is False
    assert plan["keep"] == 1
    assert {f"{r['plugin']}/{r['version']}" for r in plan["remove"]} == {
        "andon/0.8.0",
        "andon/0.10.2",
        "cupertino/0.6.0",
    }

    code, out = _invoke(dirty, "prune")
    assert code == 0, out
    assert "0.8.0" in out and "0.6.0" in out
    assert "--apply" in out, "a dry run must say how to act on it"


def test_prune_apply_keep_1_removes_exactly_the_stale_tail(dirty) -> None:
    plan = _json(dirty, "prune", "--apply")
    assert plan["apply"] is True
    assert _removed(dirty["cache"]) == {"andon/0.8.0", "andon/0.10.2", "cupertino/0.6.0"}

    for name, live in LIVE.items():
        assert (dirty["cache"] / name / live).is_dir(), f"live {name} {live} was removed"
    assert (dirty["cache"] / "takt" / "0.2.0").is_dir(), "newest non-live kept under --keep 1"
    assert (dirty["cache"] / "compass" / "0.4.0").is_dir(), "uninstalled orphan left alone"
    assert (dirty["sentinel"] / "keep-me.bin").is_file(), "prune followed a symlink out"


def test_prune_apply_keep_0_removes_every_non_live_installed_version(dirty) -> None:
    code, out = _invoke(dirty, "prune", "--apply", "--keep", "0")
    assert code == 0, out
    assert _removed(dirty["cache"]) == {
        "andon/0.8.0",
        "andon/0.10.2",
        "andon/0.11.1",
        "cupertino/0.6.0",
        "cupertino/0.9.1",
        "takt/0.2.0",
    }
    for name, live in LIVE.items():
        assert (dirty["cache"] / name / live).is_dir()
    assert (dirty["cache"] / "compass" / "0.9.0").is_dir()
    assert (dirty["sentinel"] / "keep-me.bin").is_file()


def test_prune_keep_2_keeps_the_two_newest_non_live(dirty) -> None:
    plan = _json(dirty, "prune", "--keep", "2")
    assert plan["keep"] == 2
    assert {f"{r['plugin']}/{r['version']}" for r in plan["remove"]} == {"andon/0.8.0"}


@pytest.mark.parametrize("registry", ["missing", "garbled"])
def test_prune_fails_closed_without_a_readable_registry(dirty, registry) -> None:
    reg = dirty["claude"] / "plugins" / "installed_plugins.json"
    if registry == "missing":
        reg.unlink()
    else:
        reg.write_text("{not json")
    before = _snapshot(dirty["claude"])
    code, out = _invoke(dirty, "prune", "--apply", "--keep", "0")
    # Exit 1 (a refusal), not 2 (a usage error) and not 0 (a guess at the live set).
    assert code == 1, f"exit {code}; prune must refuse without a readable registry:\n{out}"
    assert "installed_plugins.json" in out, f"the refusal must name its cause:\n{out}"
    assert _snapshot(dirty["claude"]) == before, "a refused prune removed something"


def test_claude_config_dir_env_is_honoured(dirty) -> None:
    result = CliRunner(
        env={"CLAUDE_CONFIG_DIR": str(dirty["claude"]), "NO_COLOR": "1", "COLUMNS": "80"}
    ).invoke(app, ["doctor", "--repo", str(dirty["repo"]), "--json"])
    assert result.exit_code == 0, result.output
    assert _plugin(json.loads(result.output), "andon")["live"] == "0.12.0"


# --- registry shapes: each one scheduled a live install for deletion in a first run ---


def _shape(tmp_path: Path, cached: list[tuple[str, str, str]], registry: dict) -> dict:
    """A minimal cache of `(marketplace, plugin, dir)` plus a registry whose entries are
    `{key: [(scope, dir, version)]}`, installPath pointing at `<mkt>/<plugin>/<dir>`."""
    claude = tmp_path / "claude-home"
    root = claude / "plugins" / "cache"
    for mkt, name, vdir in cached:
        _plant_version(root / mkt / name / vdir, name, vdir)
    plugins = {}
    for key, entries in registry.items():
        name, _, mkt = key.partition("@")
        plugins[key] = [
            {"scope": scope, "installPath": str(root / mkt / name / vdir), "version": version}
            for scope, vdir, version in entries
        ]
    (claude / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": plugins})
    )
    repo = _write_marketplace(tmp_path / "repo")
    return {"claude": claude, "cache": root / "werkstoff", "root": root, "repo": repo}


def _plan(d: dict, keep: str) -> set[str]:
    return {f"{r['plugin']}/{r['version']}" for r in _json(d, "prune", "--keep", keep)["remove"]}


def test_every_scope_is_live(tmp_path) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("0.8.0", "0.9.0", "1.0.0")],
        {"andon@werkstoff": [("user", "1.0.0", "1.0.0"), ("project", "0.9.0", "0.9.0")]},
    )
    assert _plan(d, "0") == {"andon/0.8.0"}, "a project-scope install is live too"
    andon = _plugin(_json(d, "doctor"), "andon")
    assert andon["liveVersions"] == ["0.9.0", "1.0.0"]
    assert andon["live"] == "1.0.0"
    code, out = _invoke(d, "prune", "--apply", "--keep", "0")
    assert code == 0, out
    assert (d["cache"] / "andon" / "0.9.0").is_dir()
    assert not (d["cache"] / "andon" / "0.8.0").exists()


def test_another_marketplaces_key_never_defines_this_live_set(tmp_path) -> None:
    cached = [
        ("werkstoff", "andon", "0.5.0"),
        ("werkstoff", "andon", "1.0.0"),
        ("other", "andon", "2.0.0"),
    ]
    # The other marketplace's key is listed FIRST, where a first-entry-wins read takes it.
    both = {
        "andon@other": [("user", "2.0.0", "2.0.0")],
        "andon@werkstoff": [("user", "1.0.0", "1.0.0")],
    }
    d = _shape(tmp_path / "both", cached, both)
    assert _plan(d, "0") == {"andon/0.5.0"}
    assert _plugin(_json(d, "doctor"), "andon")["live"] == "1.0.0"

    only_other = {"andon@other": [("user", "2.0.0", "2.0.0")]}
    d = _shape(tmp_path / "other-only", cached, only_other)
    assert _plan(d, "0") == set(), "andon is not installed from THIS marketplace: leave it"
    assert _plugin(_json(d, "doctor"), "andon")["live"] is None
    code, out = _invoke(d, "prune", "--apply", "--keep", "0")
    assert code == 0, out
    assert (d["root"] / "other" / "andon" / "2.0.0").is_dir(), "another marketplace's cache"


def test_live_is_the_install_path_not_the_version_string(tmp_path) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", "abc1234"), ("werkstoff", "andon", "0.5.0")],
        {"andon@werkstoff": [("user", "abc1234", "1.0.0")]},
    )
    assert _plan(d, "0") == {"andon/0.5.0"}, "the registered installPath IS the live copy"
    assert _plugin(_json(d, "doctor"), "andon")["live"] == "abc1234"


def test_a_prerelease_sorts_before_its_release(tmp_path) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("1.0.0", "2.0.0", "1.0.0-rc1", "0.9.0")],
        {"andon@werkstoff": [("user", "2.0.0", "2.0.0")]},
    )
    andon = _plugin(_json(d, "doctor"), "andon")
    assert andon["cached"] == ["0.9.0", "1.0.0-rc1", "1.0.0", "2.0.0"]
    assert andon["liveNotNewest"] is False, "an rc of an OLDER release is not newer"
    assert _plan(d, "1") == {"andon/0.9.0", "andon/1.0.0-rc1"}


def test_negative_keep_is_a_usage_error(dirty) -> None:
    # Exit 2 is also what an unknown COMMAND returns, so first prove prune exists and
    # accepts --keep at all -- otherwise this passes against a CLI with no prune.
    assert _json(dirty, "prune", "--keep", "0")["keep"] == 0
    before = _snapshot(dirty["claude"])
    code, out = _invoke(dirty, "prune", "--apply", "--keep", "-1")
    assert code == 2, f"exit {code}; --keep -1 must be refused as usage, not run:\n{out}"
    assert _snapshot(dirty["claude"]) == before


@pytest.mark.parametrize("registry", ["missing", "garbled"])
def test_doctor_without_a_readable_registry_fails_in_one_line(dirty, registry) -> None:
    reg = dirty["claude"] / "plugins" / "installed_plugins.json"
    if registry == "missing":
        reg.unlink()
    else:
        reg.write_text("{not json")
    result = runner.invoke(
        app, ["doctor", "--claude-dir", str(dirty["claude"]), "--repo", str(dirty["repo"])]
    )
    assert result.exit_code == 1, f"exit {result.exit_code}:\n{result.output}"
    assert "installed_plugins.json" in result.output
    assert "Traceback" not in result.output, f"doctor crashed:\n{result.output}"
    # A clean refusal is typer.Exit (SystemExit); anything else escaped the handler.
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(
        result.exception
    )


# --- the invariant, not another shape: found by run ap-2026-09-26-889b's land phase ---
#
# Enumerating registry shapes twice produced two candidates that passed every shape and
# still deleted live installs through the SPELLING of a path: a relative --claude-dir, a
# symlink alias for the claude dir, a registry key naming "..", a symlinked plugin dir.
# These tests state the invariant directly and check it after every --apply:
#
#   every directory the registry names as live (resolved) still exists, and every path
#   that disappeared lies, after resolving symlinks, strictly inside
#   realpath(<claude-dir>/plugins/cache/<marketplace>)/<plugin>/<version>.


def _live_dirs(claude: Path) -> set[Path]:
    data = json.loads((claude / "plugins" / "installed_plugins.json").read_text())
    return {
        Path(os.path.realpath(e["installPath"]))
        for key, entries in data["plugins"].items()
        if key.endswith("@werkstoff")
        for e in entries
    }


def _all_paths(root: Path) -> set[Path]:
    found = set()
    for dirpath, dirs, files in os.walk(root):
        for name in dirs + files:
            found.add(Path(dirpath) / name)
    return found


def _assert_invariant(world: Path, before: set[Path], claude_real: Path) -> set[str]:
    """Return the removed <plugin>/<version> set after checking the invariant."""
    cache_real = Path(os.path.realpath(claude_real / "plugins" / "cache" / "werkstoff"))
    for live in _live_dirs(claude_real):
        assert live.is_dir(), f"a LIVE install was removed: {live}"
    gone = before - _all_paths(world)
    removed_versions = set()
    for path in gone:
        # Every vanished path must be inside some <cache>/<plugin>/<version> subtree, and
        # its parent chain inside the cache must be real directories, never symlinks.
        rel = Path(os.path.realpath(path.parent)).relative_to(cache_real) / path.name
        assert len(rel.parts) >= 2, f"removed a path that is not inside a version dir: {path}"
        removed_versions.add("/".join(rel.parts[:2]))
    return removed_versions


def _apply(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    old = Path.cwd()
    try:
        if cwd is not None:
            os.chdir(cwd)
        result = runner.invoke(app, ["prune", *args, "--apply", "--keep", "0"])
    finally:
        os.chdir(old)
    return result.exit_code, result.output


EXPECTED_KEEP_0 = {
    "andon/0.8.0",
    "andon/0.10.2",
    "andon/0.11.1",
    "cupertino/0.6.0",
    "cupertino/0.9.1",
    "takt/0.2.0",
}


def test_a_relative_claude_dir_is_the_same_cache(dirty, tmp_path) -> None:
    before = _all_paths(tmp_path)
    rel = os.path.relpath(dirty["claude"], tmp_path)
    code, out = _apply(["--claude-dir", rel, "--repo", str(dirty["repo"])], cwd=tmp_path)
    assert code == 0, out
    assert _assert_invariant(tmp_path, before, dirty["claude"]) == EXPECTED_KEEP_0


@pytest.mark.parametrize("registry_spelling", ["real", "alias"])
def test_a_symlinked_claude_dir_is_the_same_cache(dirty, tmp_path, registry_spelling) -> None:
    alias = tmp_path / "dotfiles-alias"
    alias.symlink_to(dirty["claude"], target_is_directory=True)
    if registry_spelling == "alias":
        # The registry recorded the alias spelling; the command is given the real path.
        reg = dirty["claude"] / "plugins" / "installed_plugins.json"
        data = json.loads(reg.read_text())
        for entries in data["plugins"].values():
            for e in entries:
                e["installPath"] = e["installPath"].replace(str(dirty["claude"]), str(alias))
        reg.write_text(json.dumps(data))
        given = dirty["claude"]
    else:
        given = alias
    before = _all_paths(tmp_path)
    code, out = _apply(["--claude-dir", str(given), "--repo", str(dirty["repo"])])
    assert code == 0, out
    assert _assert_invariant(tmp_path, before, dirty["claude"]) == EXPECTED_KEEP_0


@pytest.mark.parametrize(
    "bad_key", ["../../..@werkstoff", "..@werkstoff", "a/b@werkstoff", "@werkstoff"]
)
def test_a_registry_key_never_steers_a_removal_out_of_the_cache(dirty, tmp_path, bad_key) -> None:
    reg = dirty["claude"] / "plugins" / "installed_plugins.json"
    data = json.loads(reg.read_text())
    data["plugins"][bad_key] = [
        {"scope": "user", "installPath": str(dirty["cache"] / "andon" / "0.12.0"), "version": "9"}
    ]
    reg.write_text(json.dumps(data))
    (dirty["claude"] / "projects" / "keep").mkdir(parents=True)
    before = _all_paths(tmp_path)
    code, out = _apply(["--claude-dir", str(dirty["claude"]), "--repo", str(dirty["repo"])])
    # Refusing the whole registry (exit 1) is acceptable; acting outside the cache is not.
    assert code in (0, 1), out
    removed = _assert_invariant(tmp_path, before, dirty["claude"])
    assert removed <= EXPECTED_KEEP_0, f"removed beyond the stale set: {removed - EXPECTED_KEEP_0}"
    assert (dirty["claude"] / "projects" / "keep").is_dir()


def test_a_symlinked_plugin_dir_is_never_pruned_through(dirty, tmp_path) -> None:
    elsewhere = tmp_path / "elsewhere" / "cupertino-real"
    shutil.move(str(dirty["cache"] / "cupertino"), elsewhere)
    (dirty["cache"] / "cupertino").symlink_to(elsewhere, target_is_directory=True)
    before = _all_paths(tmp_path)
    code, out = _apply(["--claude-dir", str(dirty["claude"]), "--repo", str(dirty["repo"])])
    assert code in (0, 1), out
    for v in ("0.6.0", "0.9.1", "0.10.0"):
        assert (elsewhere / v).is_dir(), f"pruned through a symlinked plugin dir: {v}"
    gone = before - _all_paths(tmp_path)
    assert not any(elsewhere in p.parents for p in gone)


@pytest.mark.parametrize("command", ["doctor", "prune"])
def test_an_undecodable_registry_fails_in_one_line(dirty, command) -> None:
    (dirty["claude"] / "plugins" / "installed_plugins.json").write_bytes(b"\xff\xfe{")
    before = _snapshot(dirty["claude"])
    extra = ["--apply"] if command == "prune" else []
    result = runner.invoke(
        app,
        [command, "--claude-dir", str(dirty["claude"]), "--repo", str(dirty["repo"]), *extra],
    )
    assert result.exit_code == 1, result.output
    assert "installed_plugins.json" in result.output
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert _snapshot(dirty["claude"]) == before


# --- hardening: what run ap-2026-09-26-889c's land phase reproduced against its winner ---
#
# Each case below broke THE INVARIANT (or the one-line error contract) in a candidate that
# passed everything above. The rule they add: prune FAILS CLOSED PER PLUGIN. A plugin is
# prunable only when every one of its entries names an absolute, existing installPath that
# resolves inside realpath(cache/<marketplace>)/<plugin>/; otherwise its liveness is
# unknown and the plugin is skipped, never guessed at. And nothing any registry entry
# names -- under any key, in any marketplace -- is ever removed, compared by (st_dev,
# st_ino), not by spelling.


def _registry_with(d: dict, extra: dict) -> None:
    reg = d["claude"] / "plugins" / "installed_plugins.json"
    data = json.loads(reg.read_text())
    data["plugins"].update(extra)
    reg.write_text(json.dumps(data))


def test_an_entry_without_installpath_over_a_symlinked_version_dir(tmp_path) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("1.0.0-real", "2.0.0", "3.0.0")],
        {"andon@werkstoff": []},
    )
    andon = d["cache"] / "andon"
    (andon / "1.0.0").symlink_to(andon / "1.0.0-real", target_is_directory=True)
    _registry_with(d, {"andon@werkstoff": [{"scope": "user", "version": "1.0.0"}]})
    code, out = _apply(["--claude-dir", str(d["claude"]), "--repo", str(d["repo"])])
    assert code in (0, 1), out
    assert (andon / "1.0.0-real").is_dir(), "the live install's real directory was removed"


@pytest.mark.parametrize("spelling", ["relative", "tilde", "missing-on-disk"])
def test_an_unusable_installpath_skips_the_plugin(tmp_path, spelling) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("0.9.0", "1.0.0")],
        {"andon@werkstoff": []},
    )
    install = {
        "relative": "plugins/cache/werkstoff/andon/0.9.0",
        "tilde": "~/.claude/plugins/cache/werkstoff/andon/0.9.0",
        "missing-on-disk": "/nonexistent/olduser/.claude/plugins/cache/werkstoff/andon/0.9.0",
    }[spelling]
    _registry_with(
        d, {"andon@werkstoff": [{"scope": "user", "installPath": install, "version": "0.9.0"}]}
    )
    # Run from the claude dir too: a cwd-relative resolution would then "match".
    for cwd in (tmp_path, d["claude"]):
        code, out = _apply(["--claude-dir", str(d["claude"]), "--repo", str(d["repo"])], cwd)
        assert code in (0, 1), out
        assert (d["cache"] / "andon" / "0.9.0").is_dir(), f"{spelling}: live 0.9.0 removed"
        assert (d["cache"] / "andon" / "1.0.0").is_dir(), f"{spelling}: liveness is unknown"


@pytest.mark.parametrize("other_key", ["andon@werkstoff-dev", "zeugnis@werkstoff", "andon"])
def test_nothing_any_registry_entry_names_is_removed(tmp_path, other_key) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("0.9.0", "1.0.0")],
        {"andon@werkstoff": [("user", "1.0.0", "1.0.0")]},
    )
    live_elsewhere = str(d["cache"] / "andon" / "0.9.0")
    _registry_with(
        d, {other_key: [{"scope": "project", "installPath": live_elsewhere, "version": "0.9.0"}]}
    )
    code, out = _apply(["--claude-dir", str(d["claude"]), "--repo", str(d["repo"])])
    assert code in (0, 1), out
    assert (d["cache"] / "andon" / "0.9.0").is_dir(), f"{other_key!r} names 0.9.0 live"


def test_an_unsafe_marketplace_name_is_refused(tmp_path) -> None:
    d = _shape(
        tmp_path,
        [("othermkt", "foo", "1.0.0"), ("werkstoff", "andon", "1.0.0")],
        {"foo@othermkt": [("user", "1.0.0", "1.0.0")]},
    )
    (d["repo"] / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "..", "plugins": []})
    )
    _registry_with(d, {"cache@..": [{"scope": "user", "installPath": "/nowhere", "version": "1"}]})
    before = _all_paths(tmp_path)
    code, out = _apply(["--claude-dir", str(d["claude"]), "--repo", str(d["repo"])])
    assert code != 0, f"prune ran under marketplace name '..':\n{out}"
    assert _all_paths(tmp_path) == before


def test_duplicate_registry_keys_are_refused(tmp_path) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("0.9.0", "1.0.0")],
        {"andon@werkstoff": [("user", "1.0.0", "1.0.0")]},
    )
    first = json.dumps([{"scope": "project", "installPath": str(d["cache"] / "andon" / "0.9.0")}])
    second = json.dumps([{"scope": "user", "installPath": str(d["cache"] / "andon" / "1.0.0")}])
    reg = d["claude"] / "plugins" / "installed_plugins.json"
    reg.write_text(
        f'{{"version": 2, "plugins": {{"andon@werkstoff": {first}, "andon@werkstoff": {second}}}}}'
    )
    before = _all_paths(tmp_path)
    code, out = _apply(["--claude-dir", str(d["claude"]), "--repo", str(d["repo"])])
    assert code == 1, f"exit {code}: a registry naming a key twice is ambiguous:\n{out}"
    assert "installed_plugins.json" in out
    assert _all_paths(tmp_path) == before


@pytest.mark.parametrize("bad", ["object", "loop"])
def test_a_malformed_installpath_never_tracebacks(tmp_path, bad) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("0.9.0", "1.0.0")],
        {"andon@werkstoff": []},
    )
    if bad == "object":
        install = {"not": "a string"}
    else:
        loop = tmp_path / "loop"
        loop.symlink_to(loop)
        install = str(loop / "x")
    _registry_with(d, {"andon@werkstoff": [{"scope": "user", "installPath": install}]})
    for command in ("doctor", "prune"):
        result = runner.invoke(
            app, [command, "--claude-dir", str(d["claude"]), "--repo", str(d["repo"]), "--json"]
        )
        assert "Traceback" not in result.output, result.output
        assert result.exception is None or isinstance(result.exception, SystemExit), repr(
            result.exception
        )
    assert (d["cache"] / "andon" / "0.9.0").is_dir()


def test_a_registry_that_is_not_a_regular_file_is_refused(dirty) -> None:
    import threading

    reg = dirty["claude"] / "plugins" / "installed_plugins.json"
    reg.unlink()
    os.mkfifo(reg)
    outcome = {}

    def run() -> None:
        r = runner.invoke(
            app, ["doctor", "--claude-dir", str(dirty["claude"]), "--repo", str(dirty["repo"])]
        )
        outcome["code"], outcome["out"] = r.exit_code, r.output

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=10)
    if t.is_alive():
        # Unblock the reader so the test process can exit, then fail.
        with reg.open("w") as fh:
            fh.write("{}")
        pytest.fail("doctor blocked reading a FIFO registry")
    assert outcome["code"] == 1, outcome
    assert "installed_plugins.json" in outcome["out"]


def test_apply_json_reports_what_was_removed(dirty) -> None:
    payload = _json(dirty, "prune", "--apply", "--keep", "1")
    removed = {f"{r['plugin']}/{r['version']}" for r in payload["removed"]}
    assert removed == _removed(dirty["cache"]) == {"andon/0.8.0", "andon/0.10.2", "cupertino/0.6.0"}
    assert payload["failed"] == []


def test_prerelease_tags_compare_numerically(tmp_path) -> None:
    d = _shape(
        tmp_path,
        [("werkstoff", "andon", v) for v in ("1.0.0-rc.10", "1.0.0-rc.2", "1.0.0-rc.9", "1.0.0")],
        {"andon@werkstoff": [("user", "1.0.0", "1.0.0")]},
    )
    andon = _plugin(_json(d, "doctor"), "andon")
    assert andon["cached"] == ["1.0.0-rc.2", "1.0.0-rc.9", "1.0.0-rc.10", "1.0.0"]
    assert _plan(d, "1") == {"andon/1.0.0-rc.2", "andon/1.0.0-rc.9"}
