import json
import shutil
from pathlib import Path

import pytest

from werkstoff import cache


def test_version_key_numeric_order_not_lexical() -> None:
    versions = ["0.9.1", "0.10.0", "0.6.0"]
    assert sorted(versions, key=cache.version_key) == ["0.6.0", "0.9.1", "0.10.0"]


def test_version_key_prerelease_sorts_before_its_release() -> None:
    versions = ["1.0.0", "1.0.0-rc1", "0.9.0"]
    assert sorted(versions, key=cache.version_key) == ["0.9.0", "1.0.0-rc1", "1.0.0"]


def test_version_key_never_crashes_on_a_non_numeric_component() -> None:
    # A git-sha directory name sorted alongside real versions must not raise.
    sorted(["abc1234", "0.5.0", "1.2.3"], key=cache.version_key)


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b"])
def test_safe_component_rejects_unsafe_names(bad: str) -> None:
    assert cache._safe_component(bad) is False


def test_safe_component_accepts_an_ordinary_name() -> None:
    assert cache._safe_component("andon") is True
    assert cache._safe_component("0.8.0") is True


def test_resolve_claude_dir_defaults_to_home_dotclaude(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert cache.resolve_claude_dir(None) == (tmp_path / ".claude").resolve()


def test_resolve_claude_dir_prefers_explicit_over_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "env-dir"))
    explicit = tmp_path / "explicit-dir"
    assert cache.resolve_claude_dir(explicit) == explicit.resolve()


def test_resolve_claude_dir_falls_back_to_env(monkeypatch, tmp_path) -> None:
    env_dir = tmp_path / "env-dir"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(env_dir))
    assert cache.resolve_claude_dir(None) == env_dir.resolve()


def test_resolve_claude_dir_resolves_a_relative_path(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    assert cache.resolve_claude_dir("claude-home") == (tmp_path / "claude-home").resolve()


def test_load_registry_missing_file_raises_cache_error(tmp_path) -> None:
    with pytest.raises(cache.CacheError, match="installed_plugins.json"):
        cache.load_registry(tmp_path)


def test_load_registry_garbled_json_raises_cache_error(tmp_path) -> None:
    reg = tmp_path / cache.REGISTRY_REL_PATH
    reg.parent.mkdir(parents=True)
    reg.write_text("{not json")
    with pytest.raises(cache.CacheError, match="installed_plugins.json"):
        cache.load_registry(tmp_path)


def test_load_registry_non_utf8_raises_cache_error(tmp_path) -> None:
    reg = tmp_path / cache.REGISTRY_REL_PATH
    reg.parent.mkdir(parents=True)
    reg.write_bytes(b"\xff\xfe{")
    with pytest.raises(cache.CacheError, match="installed_plugins.json"):
        cache.load_registry(tmp_path)


def test_load_registry_parses_a_valid_file(tmp_path) -> None:
    reg = tmp_path / cache.REGISTRY_REL_PATH
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"version": 2, "plugins": {}}))
    assert cache.load_registry(tmp_path) == {"version": 2, "plugins": {}}


def test_own_entries_drops_unsafe_names_and_other_marketplaces() -> None:
    registry = {
        "plugins": {
            "andon@werkstoff": [{"scope": "user", "installPath": "/x", "version": "1"}],
            "andon@other": [{"scope": "user", "installPath": "/y", "version": "2"}],
            "..@werkstoff": [{"scope": "user", "installPath": "/z", "version": "9"}],
            "a/b@werkstoff": [{"scope": "user", "installPath": "/w", "version": "9"}],
            "@werkstoff": [{"scope": "user", "installPath": "/v", "version": "9"}],
            "noatsign": [{"scope": "user", "installPath": "/u", "version": "9"}],
            "an\x00don@werkstoff": [{"scope": "user", "installPath": "/t", "version": "9"}],
        }
    }
    by_plugin = cache._own_entries(registry, "werkstoff")
    assert set(by_plugin) == {"andon"}
    assert len(by_plugin["andon"]) == 1


def test_scan_cache_skips_symlinked_plugin_and_version_dirs(tmp_path) -> None:
    root = tmp_path / "cache"
    (root / "andon" / "1.0.0").mkdir(parents=True)
    (root / "andon" / "1.1.0").mkdir(parents=True)
    real_elsewhere = tmp_path / "elsewhere"
    real_elsewhere.mkdir()
    (root / "andon" / "linked").symlink_to(real_elsewhere, target_is_directory=True)
    (root / "ghost").symlink_to(real_elsewhere, target_is_directory=True)

    found = cache.scan_cache(root)

    assert set(found) == {"andon"}
    assert {p.name for p in found["andon"]} == {"1.0.0", "1.1.0"}


def test_scan_cache_on_a_missing_root_returns_empty(tmp_path) -> None:
    assert cache.scan_cache(tmp_path / "does-not-exist") == {}


def _install(root: Path, plugin: str, version: str) -> Path:
    vdir = root / plugin / version
    vdir.mkdir(parents=True)
    (vdir / "f.txt").write_bytes(b"x" * 10)
    return vdir


def _write_registry(claude: Path, live: dict[str, str], marketplace: str = "werkstoff") -> None:
    cache_root = claude / "plugins" / "cache" / marketplace
    registry = {
        "version": 2,
        "plugins": {
            f"{name}@{marketplace}": [
                {
                    "scope": "user",
                    "installPath": str(cache_root / name / version),
                    "version": version,
                }
            ]
            for name, version in live.items()
        },
    }
    reg_path = claude / cache.REGISTRY_REL_PATH
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(registry))


def test_build_doctor_report_marks_not_in_marketplace_and_live_not_newest(tmp_path) -> None:
    claude = tmp_path / "claude"
    root = claude / "plugins" / "cache" / "werkstoff"
    _install(root, "andon", "0.1.0")
    _install(root, "andon", "0.2.0")
    _install(root, "orphan", "0.4.0")
    _write_registry(claude, {"andon": "0.1.0"})

    reports, total = cache.build_doctor_report(claude, "werkstoff", frozenset({"andon"}))
    by_name = {r.name: r for r in reports}

    andon = by_name["andon"]
    assert andon.live == "0.1.0"
    assert andon.cached == ("0.1.0", "0.2.0")
    assert andon.live_not_newest is True
    assert andon.not_in_marketplace is False

    orphan = by_name["orphan"]
    assert orphan.live is None
    assert orphan.not_in_marketplace is True

    assert total == andon.size_bytes + orphan.size_bytes


def test_build_prune_plan_leaves_an_uninstalled_plugins_cache_alone(tmp_path) -> None:
    claude = tmp_path / "claude"
    root = claude / "plugins" / "cache" / "werkstoff"
    _install(root, "andon", "0.1.0")
    _install(root, "andon", "0.2.0")
    _install(root, "orphan", "0.4.0")
    _write_registry(claude, {"andon": "0.2.0"})

    plan, skipped = cache.build_prune_plan(claude, "werkstoff", keep=0)

    assert {(p.plugin, p.version) for p in plan} == {("andon", "0.1.0")}
    assert skipped == []


def test_apply_prune_removes_planned_paths_and_skips_already_gone(tmp_path) -> None:
    claude = tmp_path / "claude"
    root = claude / "plugins" / "cache" / "werkstoff"
    stale = _install(root, "andon", "0.1.0")
    _install(root, "andon", "0.2.0")
    _write_registry(claude, {"andon": "0.2.0"})
    already_gone = cache.RemovalPlan(plugin="andon", version="ghost", path=root / "andon" / "ghost")
    plan = [cache.RemovalPlan(plugin="andon", version="0.1.0", path=stale), already_gone]

    removed, failures = cache.apply_prune(plan, claude, "werkstoff")

    assert not stale.exists()
    assert removed == [plan[0]]
    assert failures == []


# --- apply-time re-proof: the plan is computed first, the filesystem may change after ---


def _planned(tmp_path: Path) -> tuple[Path, Path, list[cache.RemovalPlan]]:
    claude = tmp_path / "claude"
    root = claude / "plugins" / "cache" / "werkstoff"
    _install(root, "andon", "0.9.0")
    _install(root, "andon", "1.0.0")
    _write_registry(claude, {"andon": "1.0.0"})
    plan, skipped = cache.build_prune_plan(claude, "werkstoff", keep=0)
    assert [(i.plugin, i.version) for i in plan] == [("andon", "0.9.0")]
    assert skipped == []
    return claude, root, plan


def test_apply_refuses_a_version_that_became_live_after_planning(tmp_path) -> None:
    claude, root, plan = _planned(tmp_path)
    # A concurrent `claude plugin install --scope project` lands between plan and apply.
    reg_path = claude / cache.REGISTRY_REL_PATH
    registry = json.loads(reg_path.read_text())
    registry["plugins"]["andon@werkstoff"].append(
        {"scope": "project", "installPath": str(root / "andon" / "0.9.0"), "version": "0.9.0"}
    )
    reg_path.write_text(json.dumps(registry))

    removed, failures = cache.apply_prune(plan, claude, "werkstoff")

    assert removed == []
    assert [why for _, why in failures] == ["refused: a registry entry names it live"]
    assert (root / "andon" / "0.9.0").is_dir()


def test_apply_refuses_a_plugin_dir_swapped_for_a_symlink_after_planning(tmp_path) -> None:
    claude, root, plan = _planned(tmp_path)
    outside = tmp_path / "outside" / "andon"
    shutil.move(str(root / "andon"), outside)
    (root / "andon").symlink_to(outside, target_is_directory=True)

    removed, failures = cache.apply_prune(plan, claude, "werkstoff")

    assert removed == []
    assert len(failures) == 1 and failures[0][1].startswith("refused:")
    assert (outside / "0.9.0").is_dir(), "removed through a symlinked plugin dir"


def test_apply_refuses_when_the_registry_became_unreadable(tmp_path) -> None:
    claude, root, plan = _planned(tmp_path)
    (claude / cache.REGISTRY_REL_PATH).write_text("{not json")

    removed, failures = cache.apply_prune(plan, claude, "werkstoff")

    assert removed == []
    assert [i for i, _ in failures] == plan
    assert all("installed_plugins.json" in why for _, why in failures)
    assert (root / "andon" / "0.9.0").is_dir()


def test_apply_reports_what_it_removed_before_the_registry_broke(tmp_path, monkeypatch) -> None:
    claude = tmp_path / "claude"
    root = claude / "plugins" / "cache" / "werkstoff"
    for v in ("0.7.0", "0.8.0", "1.0.0"):
        _install(root, "andon", v)
    _write_registry(claude, {"andon": "1.0.0"})
    plan, _ = cache.build_prune_plan(claude, "werkstoff", keep=0)
    assert [i.version for i in plan] == ["0.7.0", "0.8.0"]
    real = cache._remove_verified

    def remove_then_break(cache_root, item, ids):
        real(cache_root, item, ids)
        (claude / cache.REGISTRY_REL_PATH).write_text("{not json")

    monkeypatch.setattr(cache, "_remove_verified", remove_then_break)
    removed, failures = cache.apply_prune(plan, claude, "werkstoff")

    assert [i.version for i in removed] == ["0.7.0"]
    assert [i.version for i, _ in failures] == ["0.8.0"]
    assert (root / "andon" / "0.8.0").is_dir()


def test_apply_refuses_when_the_cache_root_changed_since_planning(tmp_path) -> None:
    claude, root, plan = _planned(tmp_path)
    moved = tmp_path / "old-werkstoff"
    shutil.move(str(root), moved)
    shutil.copytree(moved, root, symlinks=True)

    removed, failures = cache.apply_prune(plan, claude, "werkstoff")

    assert removed == []
    assert failures and "cache root changed" in failures[0][1]


def test_remove_verified_refuses_a_plugin_dir_swapped_after_the_check(tmp_path) -> None:
    claude, root, plan = _planned(tmp_path)
    cache_root = cache.cache_root_for(claude, "werkstoff")
    protected = cache.protected_for(cache.load_registry(claude), claude, cache_root)
    why, ids = cache._refusal(plan[0], cache_root, protected)
    assert why is None and ids is not None
    # The swap lands in the window between the check and the removal.
    victim = tmp_path / "victim" / "andon"
    shutil.move(str(root / "andon"), tmp_path / "real-andon")
    victim.mkdir(parents=True)
    (victim / "0.9.0").mkdir()
    (root / "andon").symlink_to(victim, target_is_directory=True)

    with pytest.raises(OSError):
        cache._remove_verified(cache_root, plan[0], ids)
    assert (victim / "0.9.0").is_dir(), "followed a plugin dir swapped for a symlink"


def test_prerelease_tags_compare_numerically() -> None:
    tags = ["1.0.0-rc.10", "1.0.0-rc9", "1.0.0-rc.2", "1.0.0", "1.0.0-rc10"]
    assert sorted(tags, key=cache.version_key) == [
        "1.0.0-rc.2",
        "1.0.0-rc.10",
        "1.0.0-rc9",
        "1.0.0-rc10",
        "1.0.0",
    ]


def test_remove_verified_refuses_a_plugin_dir_renamed_away_after_the_check(tmp_path) -> None:
    claude, root, plan = _planned(tmp_path)
    cache_root = cache.cache_root_for(claude, "werkstoff")
    protected = cache.protected_for(cache.load_registry(claude), claude, cache_root)
    why, ids = cache._refusal(plan[0], cache_root, protected)
    assert why is None and ids is not None
    # A REAL directory (not a symlink, so O_NOFOLLOW alone passes it) takes the
    # checked plugin dir's name between the check and the removal.
    (root / "andon").rename(tmp_path / "checked-andon")
    impostor = root / "andon"
    (impostor / "0.9.0").mkdir(parents=True)
    (impostor / "0.9.0" / "precious").write_text("x")

    with pytest.raises(OSError, match="changed after it was checked"):
        cache._remove_verified(cache_root, plan[0], ids)
    assert (impostor / "0.9.0" / "precious").is_file()
