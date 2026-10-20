from extract.run import extract


def build():
    """Builds the per-row report. Iterates the payload's rows positionally."""
    payload = extract()
    return [r["id"] for r in payload["rows"]]
