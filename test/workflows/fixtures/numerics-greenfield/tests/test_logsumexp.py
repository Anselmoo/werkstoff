"""The wanted feature. Fails until numerics.logsumexp exists."""

import math
import unittest

from numerics import logsumexp


class TestLogSumExp(unittest.TestCase):
    def test_matches_naive_on_small_values(self):
        values = [0.1, 0.2, 0.3]
        naive = math.log(sum(math.exp(v) for v in values))
        self.assertAlmostEqual(logsumexp(values), naive, places=12)

    def test_does_not_overflow_on_large_values(self):
        self.assertAlmostEqual(logsumexp([1000.0, 1000.0]), 1000.0 + math.log(2), places=9)

    def test_single_value(self):
        self.assertAlmostEqual(logsumexp([42.0]), 42.0, places=12)
