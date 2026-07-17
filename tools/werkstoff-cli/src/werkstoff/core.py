"""Business logic for the werkstoff plugin installer.

Zero CLI-framework imports — every function here must import and run cleanly
from a plain Python REPL. Argument parsing, output formatting, and exit-code
mapping live in cli.py instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MARKETPLACE_REL_PATH = Path(".claude-plugin/marketplace.json")
DEFAULT_SCOPE = "user"
VALID_SCOPES = frozenset({"user", "project", "local"})

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class WerkstoffError(RuntimeError):
    """Raised for any expected failure: missing repo, bad manifest, missing
    claude CLI, or a failed subprocess call."""


@dataclass(frozen=True)
class Plugin:
    name: str
    description: str
    source: str
    category: str | None = None


@dataclass(frozen=True)
class Marketplace:
    name: str
    root: Path
    plugins: tuple[Plugin, ...]

    def plugin(self, name: str) -> Plugin:
        for candidate in self.plugins:
            if candidate.name == name:
                return candidate
        known = ", ".join(p.name for p in self.plugins)
        raise WerkstoffError(f"unknown plugin '{name}' (known: {known})")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (default: cwd) for a directory containing
    .claude-plugin/marketplace.json."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / MARKETPLACE_REL_PATH).is_file():
            return candidate
    raise WerkstoffError(
        "no .claude-plugin/marketplace.json found in this directory or any "
        "parent; pass --repo or set WERKSTOFF_REPO"
    )


def load_marketplace(repo_root: Path) -> Marketplace:
    manifest_path = repo_root / MARKETPLACE_REL_PATH
    try:
        raw = json.loads(manifest_path.read_text())
    except FileNotFoundError as exc:
        raise WerkstoffError(f"marketplace manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise WerkstoffError(
            f"marketplace manifest is not valid JSON: {manifest_path} ({exc})"
        ) from exc

    try:
        name = raw["name"]
        plugins = tuple(
            Plugin(
                name=entry["name"],
                description=entry.get("description", ""),
                source=entry["source"],
                category=entry.get("category"),
            )
            for entry in raw["plugins"]
        )
    except KeyError as exc:
        raise WerkstoffError(f"marketplace manifest missing required field: {exc}") from exc

    return Marketplace(name=name, root=repo_root, plugins=plugins)


def unknown_plugin_names(marketplace: Marketplace, names: tuple[str, ...]) -> list[str]:
    known = {p.name for p in marketplace.plugins}
    return [n for n in names if n not in known]


def ensure_claude_cli() -> str:
    path = shutil.which("claude")
    if path is None:
        raise WerkstoffError("the 'claude' CLI was not found on PATH")
    return path


def _run(argv: list[str], run: Runner) -> subprocess.CompletedProcess[str]:
    result = run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(no output)"
        raise WerkstoffError(f"`{' '.join(argv)}` failed (exit {result.returncode}): {stderr}")
    return result


def add_marketplace(
    marketplace: Marketplace, run: Runner = subprocess.run
) -> subprocess.CompletedProcess[str]:
    claude = ensure_claude_cli()
    return _run([claude, "plugin", "marketplace", "add", str(marketplace.root)], run)


def update_marketplace(
    marketplace: Marketplace, run: Runner = subprocess.run
) -> subprocess.CompletedProcess[str]:
    claude = ensure_claude_cli()
    return _run([claude, "plugin", "marketplace", "update", marketplace.name], run)


def install_plugin(
    marketplace: Marketplace,
    plugin_name: str,
    scope: str = DEFAULT_SCOPE,
    run: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    plugin = marketplace.plugin(plugin_name)  # validates the name first
    claude = ensure_claude_cli()
    return _run(
        [claude, "plugin", "install", f"{plugin.name}@{marketplace.name}", "--scope", scope],
        run,
    )


def install_plugins(
    marketplace: Marketplace,
    plugin_names: tuple[str, ...],
    scope: str = DEFAULT_SCOPE,
    run: Runner = subprocess.run,
) -> list[str]:
    """Add/refresh the marketplace, then install each named plugin (all
    plugins if `plugin_names` is empty). Returns the installed names in
    the order they were installed."""
    names = plugin_names or tuple(p.name for p in marketplace.plugins)
    add_marketplace(marketplace, run=run)
    update_marketplace(marketplace, run=run)
    for name in names:
        install_plugin(marketplace, name, scope=scope, run=run)
    return list(names)
