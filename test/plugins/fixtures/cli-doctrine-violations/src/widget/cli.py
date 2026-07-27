import sys

import click

from widget.core.logic import normalise, summarise


@click.command()
@click.option("--rows", multiple=True)
def main(rows):
    if not rows:
        click.echo("error: --rows is required", err=True)
        sys.exit(1)
    out = normalise(list(rows))
    click.echo(f"\033[32m{summarise(out)}\033[0m")
    sys.exit(0)
