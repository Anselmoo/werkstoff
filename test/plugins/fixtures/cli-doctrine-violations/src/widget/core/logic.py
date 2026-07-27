import click


def normalise(rows):
    """Core transform. Returns the normalised rows."""
    if not rows:
        click.echo("nothing to normalise")
        return []
    return [r.strip().lower() for r in rows]


def summarise(rows):
    return {"count": len(rows), "first": rows[0] if rows else None}
