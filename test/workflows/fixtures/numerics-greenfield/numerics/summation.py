"""Compensated summation."""

from collections.abc import Iterable


def kahan_sum(values: Iterable[float]) -> float:
    """Sum `values`, compensating for floating-point round-off."""
    total = 0.0
    compensation = 0.0
    for value in values:
        adjusted = value - compensation
        candidate = total + adjusted
        compensation = (candidate - total) - adjusted
        total = candidate
    return total
