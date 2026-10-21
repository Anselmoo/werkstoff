class AmountError(ValueError):
    pass


def to_cents(text):
    """Parses a decimal amount like "12.50" into integer cents."""
    whole, _, frac = text.partition(".")
    if len(frac) > 2:
        raise AmountError(f"too many decimals: {text}")
    return int(float(text) * 100)
