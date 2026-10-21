from extract.run import extract


def dump():
    """Exports the payload's identifier. Addresses rows by field name."""
    payload = extract()
    return payload["rows"]["id"]
