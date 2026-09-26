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

    doctor --json -> {"marketplace", "totalSizeBytes",
                      "plugins": [{"name", "live", "cached", "sizeBytes",
                                   "notInMarketplace", "liveNotNewest"}]}
        cached     every cached version, ascending by numeric version order
        sizeBytes  sum of st_size of regular files; symlinks neither followed nor counted
    prune --json  -> {"apply", "keep", "remove": [{"plugin", "version", "path"}]}
        remove     installed plugins only; never the live version; keeps the N newest
                   non-live versions; an uninstalled plugin's cache is left alone
        a missing or unparseable registry -> exit 1 naming installed_plugins.json,
        nothing removed (the live set is a gating value; it is never inferred)

This file sits outside every candidate's write scope on purpose: an instrument the
thing it grades can edit is not an instrument.
"""

import json
import os
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
