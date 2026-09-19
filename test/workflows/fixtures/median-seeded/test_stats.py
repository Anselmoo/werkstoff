import unittest

from stats import median


class TestMedian(unittest.TestCase):
    def test_odd_length(self):
        self.assertEqual(median([3, 1, 2]), 2.0)

    def test_even_length_is_the_mean_of_the_middle_two(self):
        self.assertEqual(median([1, 2, 3, 4]), 2.5)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            median([])
