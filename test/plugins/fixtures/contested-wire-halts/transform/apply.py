from extract.run import extract


def apply():
    """Stage 2. Normalises the extracted payload for downstream stages."""
    payload = extract()
    return [r for r in payload["records"]]
