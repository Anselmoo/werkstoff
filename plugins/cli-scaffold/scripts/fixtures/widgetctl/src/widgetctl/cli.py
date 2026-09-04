"""Thin entry point: parses flags, calls core, maps errors to exit codes."""

import json
import sys

import click

from . import core, inventory


@click.command()
@click.argument("widget_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.option("--no-input", is_flag=True, help="Never prompt.")
@click.option("--verbose", is_flag=True, help="Diagnostics to stderr.")
def main(widget_id, as_json, no_input, verbose):
    """Inspect and list widgets."""
    widgets = inventory.load("inventory.json")
    try:
        result = core.describe(widgets, widget_id) if widget_id else widgets
    except core.WidgetNotFound as exc:
        print(f"widgetctl: no such widget: {exc}", file=sys.stderr)
        sys.exit(core.EXIT_RUNTIME)
    if verbose:
        print("widgetctl: ok", file=sys.stderr)
    print(json.dumps(result) if as_json else result)
    sys.exit(core.EXIT_OK)
