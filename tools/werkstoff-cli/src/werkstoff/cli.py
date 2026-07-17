"""Thin Typer entry point for the werkstoff plugin installer.

Only argument parsing, calling into core.py, output formatting, and
exit-code mapping belong here — no business rules.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.padding import Padding

from werkstoff import core

app = typer.Typer(
    no_args_is_help=True,
    help="Install and manage this repo's Claude Code plugins by driving the claude CLI.",
)

console = Console(no_color=bool(os.environ.get("NO_COLOR")))
err_console = Console(stderr=True, no_color=bool(os.environ.get("NO_COLOR")))

DESCRIPTION_PREVIEW_CHARS = 160


def _preview(text: str, limit: int = DESCRIPTION_PREVIEW_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


REPO_OPTION = typer.Option(
    None,
    "--repo",
    envvar="WERKSTOFF_REPO",
    help="Path to the werkstoff repo (default: search upward from the current directory).",
)


def _resolve_marketplace(repo: Path | None) -> core.Marketplace:
    try:
        repo_root = repo.resolve() if repo else core.find_repo_root()
        return core.load_marketplace(repo_root)
    except core.WerkstoffError as exc:
        err_console.print(f"error: {exc}")
        raise typer.Exit(code=1) from exc


@app.command("list")
def list_plugins(
    repo: Path | None = REPO_OPTION,
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """List every plugin available in the werkstoff marketplace."""
    marketplace = _resolve_marketplace(repo)
    if json_output:
        payload = [
            {
                "name": p.name,
                "description": p.description,
                "source": p.source,
                "category": p.category,
            }
            for p in marketplace.plugins
        ]
        typer.echo(json.dumps(payload))
        return
    console.print(
        f"[bold]{marketplace.name}[/bold] — {len(marketplace.plugins)} plugins "
        f"[dim](--json for full descriptions)[/dim]\n"
    )
    for plugin in marketplace.plugins:
        category = f" [dim]({plugin.category})[/dim]" if plugin.category else ""
        console.print(f"[bold cyan]●[/bold cyan] [bold]{plugin.name}[/bold]{category}")
        console.print(Padding(_preview(plugin.description), (0, 0, 1, 2)))


INSTALL_NAMES_ARGUMENT = typer.Argument(None, help="Plugins to install (default: all).")


@app.command()
def install(
    plugin_names: list[str] | None = INSTALL_NAMES_ARGUMENT,
    scope: str = typer.Option("user", "--scope", help="Install scope: user, project, or local."),
    repo: Path | None = REPO_OPTION,
    no_input: bool = typer.Option(
        False, "--no-input", help="Never prompt; install all without confirmation."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Add the werkstoff marketplace (if needed) and install the given plugins."""
    if scope not in core.VALID_SCOPES:
        err_console.print(
            f"error: --scope must be one of {', '.join(sorted(core.VALID_SCOPES))} (got {scope!r})"
        )
        raise typer.Exit(code=2)

    marketplace = _resolve_marketplace(repo)
    names = tuple(plugin_names or ())

    unknown = core.unknown_plugin_names(marketplace, names)
    if unknown:
        err_console.print(f"error: unknown plugin(s): {', '.join(unknown)}")
        raise typer.Exit(code=2)

    if not names and not no_input:
        count = len(marketplace.plugins)
        if not typer.confirm(f"Install all {count} plugins from '{marketplace.name}'?", err=True):
            raise typer.Exit(code=1)

    try:
        installed = core.install_plugins(marketplace, names, scope=scope)
    except core.WerkstoffError as exc:
        err_console.print(f"error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps({"installed": installed, "marketplace": marketplace.name}))
    else:
        for name in installed:
            console.print(f"[green]installed[/green] {name}@{marketplace.name}")


@app.command()
def update(repo: Path | None = REPO_OPTION) -> None:
    """Refresh the werkstoff marketplace cache so local plugin edits are picked up."""
    marketplace = _resolve_marketplace(repo)
    try:
        core.update_marketplace(marketplace)
    except core.WerkstoffError as exc:
        err_console.print(f"error: {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]updated[/green] {marketplace.name}")


if __name__ == "__main__":
    app()
