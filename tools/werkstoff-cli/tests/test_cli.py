import json
from pathlib import Path

from typer.testing import CliRunner

from werkstoff.cli import app

# Rich/Typer's --help rendering wraps to the terminal width, which makes
# the snapshot below flaky across machines/CI unless pinned explicitly —
# CliRunner(env=...) sets COLUMNS for the duration of each invoke.
runner = CliRunner(env={"COLUMNS": "80"})


def _write_marketplace(tmp_path: Path) -> Path:
    manifest_dir = tmp_path / ".claude-plugin"
    manifest_dir.mkdir()
    (manifest_dir / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "werkstoff",
                "plugins": [
                    {
                        "name": "self-assess",
                        "description": "d",
                        "source": "./plugins/self-assess",
                    },
                ],
            }
        )
    )
    return tmp_path


def test_help_snapshot(snapshot) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert result.output == snapshot


def test_list_json(tmp_path) -> None:
    repo = _write_marketplace(tmp_path)
    result = runner.invoke(app, ["list", "--repo", str(repo), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["name"] == "self-assess"


def test_list_missing_repo_exits_1(tmp_path) -> None:
    result = runner.invoke(app, ["list", "--repo", str(tmp_path)])
    assert result.exit_code == 1


def test_install_unknown_plugin_exits_2(tmp_path) -> None:
    repo = _write_marketplace(tmp_path)
    result = runner.invoke(app, ["install", "does-not-exist", "--repo", str(repo), "--no-input"])
    assert result.exit_code == 2


def test_install_bad_scope_exits_2(tmp_path) -> None:
    repo = _write_marketplace(tmp_path)
    result = runner.invoke(app, ["install", "self-assess", "--repo", str(repo), "--scope", "bogus"])
    assert result.exit_code == 2
