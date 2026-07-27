from transform.apply import apply


def emit():
    """Stage 3. Publishes the normalised payload."""
    return {"published": apply()}
