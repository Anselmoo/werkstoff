"""Deliberately assertion-free test, for quality-assertion-audit's fixture."""

from calculator import add


def test_add_does_not_raise():
    # Executes add() for coverage, but never checks the actual return
    # value (should be 5) — a mutation flipping + to - or introducing an
    # off-by-one would still pass this test.
    result = add(2, 3)
    assert result is not None
