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

from werkstoff import cache, core

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


CLAUDE_DIR_OPTION = typer.Option(
    None,
    "--claude-dir",
    help="Path to the Claude config dir (default: $CLAUDE_CONFIG_DIR, else ~/.claude).",
)
KEEP_OPTION = typer.Option(
    1, "--keep", min=0, help="Newest non-live cached versions to keep per plugin."
)


def _human_size(num_bytes: int) -> str:
    """Bytes as a short human-readable size (KB/MB/GB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _plugin_payload(report: cache.PluginReport) -> dict:
    return {
        "name": report.name,
        "live": report.live,
        "liveVersions": list(report.live_versions),
        "cached": list(report.cached),
        "sizeBytes": report.size_bytes,
        "notInMarketplace": report.not_in_marketplace,
        "liveNotNewest": report.live_not_newest,
        "liveUnknown": report.live_unknown,
    }


def _print_doctor_report(reports: list[cache.PluginReport], total: int) -> None:
    if not reports:
        console.print("[dim]no plugins found in the marketplace or the cache[/dim]")
        return
    for report in reports:
        bits = [f"live {report.live}" if report.live else "not installed"]
        if report.not_in_marketplace:
            bits.append("[yellow]not in marketplace[/yellow]")
        bits.append(f"cached {len(report.cached)}")
        if report.live_unknown:
            bits.append(f"[red]live unknown, prune skips it: {report.live_unknown}[/red]")
        if report.live_not_newest:
            bits.append(f"[yellow]newer cached: {report.cached[-1]}[/yellow]")
        bits.append(_human_size(report.size_bytes))
        console.print(f"[bold]{report.name}[/bold]  " + "  ".join(bits))
    console.print(f"\n{len(reports)} plugin(s), {_human_size(total)} total")


def _print_skipped(skipped: list[tuple[str, str]]) -> None:
    for plugin, why in skipped:
        console.print(f"  skip {plugin}  -- liveness unknown, nothing pruned: {why}")


def _print_prune_dry_run(plan: list[cache.RemovalPlan], skipped: list[tuple[str, str]]) -> None:
    _print_skipped(skipped)
    if not plan:
        console.print("nothing to prune")
        return
    for item in plan:
        console.print(f"  would remove {item.path}  -- stale, kept beyond --keep")
    console.print(f"{len(plan)} path(s); dry run -- nothing touched. Pass --apply to remove them.")


def _print_prune_apply(
    plan: list[cache.RemovalPlan],
    skipped: list[tuple[str, str]],
    removed: list[cache.RemovalPlan],
    failures: list[tuple[cache.RemovalPlan, str]],
) -> None:
    _print_skipped(skipped)
    for item in removed:
        console.print(f"  remove {item.path}")
    for item, why in failures:
        err_console.print(f"  FAILED {item.path}: {why}")
    console.print(f"removed {len(removed)} of {len(plan)}")


def _item_payload(item: cache.RemovalPlan) -> dict:
    return {"plugin": item.plugin, "version": item.version, "path": str(item.path)}


def _prune_payload(
    apply: bool,
    keep: int,
    planned: tuple[list[cache.RemovalPlan], list[tuple[str, str]]],
    outcome: tuple[list[cache.RemovalPlan], list[tuple[cache.RemovalPlan, str]]],
) -> dict:
    """`remove` is the plan; `removed` and `failed` are what --apply actually did."""
    plan, skipped = planned
    removed, failures = outcome
    return {
        "apply": apply,
        "keep": keep,
        "remove": [_item_payload(i) for i in plan],
        "skipped": [{"plugin": p, "reason": why} for p, why in skipped],
        "removed": [_item_payload(i) for i in removed],
        "failed": [dict(_item_payload(i), reason=why) for i, why in failures],
    }


@app.command()
def doctor(
    claude_dir: Path | None = CLAUDE_DIR_OPTION,
    repo: Path | None = REPO_OPTION,
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Report every cached plugin version against the installed-plugins registry.

    Read-only: never writes to the registry or the cache."""
    marketplace = _resolve_marketplace(repo)
    resolved_claude_dir = cache.resolve_claude_dir(claude_dir)
    marketplace_names = frozenset(p.name for p in marketplace.plugins)
    try:
        reports, total = cache.build_doctor_report(
            resolved_claude_dir, marketplace.name, marketplace_names
        )
    except cache.CacheError as exc:
        err_console.print(f"error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        payload = {
            "marketplace": marketplace.name,
            "totalSizeBytes": total,
            "plugins": [_plugin_payload(r) for r in reports],
        }
        typer.echo(json.dumps(payload))
        return
    _print_doctor_report(reports, total)


@app.command()
def prune(
    claude_dir: Path | None = CLAUDE_DIR_OPTION,
    repo: Path | None = REPO_OPTION,
    keep: int = KEEP_OPTION,
    apply: bool = typer.Option(False, "--apply", help="Actually remove; default is a dry run."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """List, and with --apply remove, stale non-live cached plugin versions.

    Dry run by default. Never removes a live directory, an uninstalled
    plugin's cache, or anything reached through a symlink."""
    marketplace = _resolve_marketplace(repo)
    resolved_claude_dir = cache.resolve_claude_dir(claude_dir)
    removed: list[cache.RemovalPlan] = []
    failures: list[tuple[cache.RemovalPlan, str]] = []
    try:
        plan, skipped = cache.build_prune_plan(resolved_claude_dir, marketplace.name, keep)
        if apply:
            removed, failures = cache.apply_prune(plan, resolved_claude_dir, marketplace.name)
    except cache.CacheError as exc:
        err_console.print(f"error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(_prune_payload(apply, keep, (plan, skipped), (removed, failures))))
    elif apply:
        _print_prune_apply(plan, skipped, removed, failures)
    else:
        _print_prune_dry_run(plan, skipped)

    if failures:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
