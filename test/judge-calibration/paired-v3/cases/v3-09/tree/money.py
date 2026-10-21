import re

_AMOUNT = re.compile(r"-?[0-9]{1,18}(\.[0-9]{1,2})?")


def to_cents(text):
    """'12.34' -> 1234"""
    if not _AMOUNT.fullmatch(text):
        raise ValueError(f"not an amount: {text!r}")
    return round(float(text) * 100)
