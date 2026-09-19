"""Descriptive statistics."""


def median(values: list) -> float:
    """Return the median of `values`."""
    if not values:
        raise ValueError("median of an empty sample is undefined")
    ordered = sorted(values)
    middle = len(ordered) // 2
    return float(ordered[middle])
