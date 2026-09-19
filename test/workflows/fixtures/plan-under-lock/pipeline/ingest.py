"""Stage 1: read raw records."""


def ingest(rows: list) -> list:
    return [dict(row) for row in rows]
