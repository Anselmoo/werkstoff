import json
import subprocess
from pathlib import Path

import pytest

from werkstoff import core


def _write_marketplace(tmp_path: Path, plugins: list[dict]) -> Path:
    manifest_dir = tmp_path / ".claude-plugin"
    manifest_dir.mkdir()
    (manifest_dir / "marketplace.json").write_text(
        json.dumps({"name": "werkstoff", "plugins": plugins})
    )
    return tmp_path


def _fake_run(returncode: int = 0):
    calls: list[list[str]] = []

    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout="", stderr="boom")

    return run, calls


def test_find_repo_root_walks_upward(tmp_path):
    repo = _write_marketplace(tmp_path, [])
    nested = repo / "plugins" / "example"
    nested.mkdir(parents=True)
    assert core.find_repo_root(nested) == repo


def test_find_repo_root_raises_when_not_found(tmp_path):
    with pytest.raises(core.WerkstoffError):
        core.find_repo_root(tmp_path)


def test_load_marketplace_parses_plugins(tmp_path):
    repo = _write_marketplace(
        tmp_path,
        [
            {
                "name": "self-assess",
                "description": "d",
                "source": "./plugins/self-assess",
                "category": "development",
            }
        ],
    )
    marketplace = core.load_marketplace(repo)
    assert marketplace.name == "werkstoff"
    assert marketplace.plugins[0].name == "self-assess"
    assert marketplace.plugins[0].category == "development"


def test_load_marketplace_rejects_invalid_json(tmp_path):
    manifest_dir = tmp_path / ".claude-plugin"
    manifest_dir.mkdir()
    (manifest_dir / "marketplace.json").write_text("{not json")
    with pytest.raises(core.WerkstoffError):
        core.load_marketplace(tmp_path)


def test_load_marketplace_rejects_missing_field(tmp_path):
    manifest_dir = tmp_path / ".claude-plugin"
    manifest_dir.mkdir()
    (manifest_dir / "marketplace.json").write_text(
        json.dumps({"name": "werkstoff", "plugins": [{"name": "x"}]})
    )
    with pytest.raises(core.WerkstoffError):
        core.load_marketplace(tmp_path)


def test_marketplace_plugin_raises_on_unknown_name(tmp_path):
    repo = _write_marketplace(
        tmp_path, [{"name": "self-assess", "description": "d", "source": "./plugins/self-assess"}]
    )
    marketplace = core.load_marketplace(repo)
    with pytest.raises(core.WerkstoffError):
        marketplace.plugin("does-not-exist")


def test_unknown_plugin_names_filters_known(tmp_path):
    repo = _write_marketplace(
        tmp_path, [{"name": "self-assess", "description": "d", "source": "./plugins/self-assess"}]
    )
    marketplace = core.load_marketplace(repo)
    assert core.unknown_plugin_names(marketplace, ("self-assess", "ghost")) == ["ghost"]
    assert core.unknown_plugin_names(marketplace, ()) == []


def test_install_plugins_adds_updates_and_installs_each(tmp_path, monkeypatch):
    monkeypatch.setattr(core.shutil, "which", lambda name: "/usr/bin/claude")
    repo = _write_marketplace(
        tmp_path,
        [
            {"name": "self-assess", "description": "d", "source": "./plugins/self-assess"},
            {"name": "quality", "description": "d", "source": "./plugins/quality"},
        ],
    )
    marketplace = core.load_marketplace(repo)
    run, calls = _fake_run()

    installed = core.install_plugins(marketplace, (), scope="user", run=run)

    assert installed == ["self-assess", "quality"]
    assert calls[0][1:5] == ["plugin", "marketplace", "add", str(repo)]
    assert calls[1][1:5] == ["plugin", "marketplace", "update", "werkstoff"]
    assert calls[2][1:4] == ["plugin", "install", "self-assess@werkstoff"]
    assert calls[3][1:4] == ["plugin", "install", "quality@werkstoff"]


def test_install_plugins_honors_explicit_subset(tmp_path, monkeypatch):
    monkeypatch.setattr(core.shutil, "which", lambda name: "/usr/bin/claude")
    repo = _write_marketplace(
        tmp_path,
        [
            {"name": "self-assess", "description": "d", "source": "./plugins/self-assess"},
            {"name": "quality", "description": "d", "source": "./plugins/quality"},
        ],
    )
    marketplace = core.load_marketplace(repo)
    run, calls = _fake_run()

    installed = core.install_plugins(marketplace, ("quality",), scope="project", run=run)

    assert installed == ["quality"]
    assert calls[2][1:4] == ["plugin", "install", "quality@werkstoff"]
    assert calls[2][4:6] == ["--scope", "project"]


def test_install_plugin_rejects_unknown_name(tmp_path):
    repo = _write_marketplace(
        tmp_path, [{"name": "self-assess", "description": "d", "source": "./plugins/self-assess"}]
    )
    marketplace = core.load_marketplace(repo)
    run, _ = _fake_run()
    with pytest.raises(core.WerkstoffError):
        core.install_plugin(marketplace, "does-not-exist", run=run)


def test_ensure_claude_cli_raises_when_missing(monkeypatch):
    monkeypatch.setattr(core.shutil, "which", lambda name: None)
    with pytest.raises(core.WerkstoffError):
        core.ensure_claude_cli()


def test_run_raises_on_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(core.shutil, "which", lambda name: "/usr/bin/claude")
    repo = _write_marketplace(
        tmp_path, [{"name": "self-assess", "description": "d", "source": "./plugins/self-assess"}]
    )
    marketplace = core.load_marketplace(repo)
    run, _ = _fake_run(returncode=1)
    with pytest.raises(core.WerkstoffError, match="boom"):
        core.add_marketplace(marketplace, run=run)
