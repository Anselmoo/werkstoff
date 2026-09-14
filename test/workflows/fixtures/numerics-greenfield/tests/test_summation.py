import unittest

from numerics import kahan_sum


class TestKahanSum(unittest.TestCase):
    def test_compensates_round_off(self):
        values = [1.0, 1e-16, 1e-16, 1e-16]
        self.assertGreater(kahan_sum(values), 1.0)

    def test_empty_is_zero(self):
        self.assertEqual(kahan_sum([]), 0.0)
