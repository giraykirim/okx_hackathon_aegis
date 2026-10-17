"""Offline regression tests for public spot analysis; no network or model required."""
import math
import unittest
from spot_research import closed, returns, correlation


def candle(ts, close='100', confirm='1'):
    return [str(ts), close, close, close, close, '1', '100', '100', confirm]


class SpotTests(unittest.TestCase):
    def test_unfinished_excluded(self):
        self.assertEqual(closed([candle(0), candle(60000, confirm='0')], 60), {0: 100.0})

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            closed([candle(0), candle(0)], 60)

    def test_invalid_price_rejected(self):
        for value in ('NaN', '-1', 'inf', '0'):
            with self.assertRaises(ValueError):
                closed([candle(0, value)], 60)

    def test_gaps_not_bridged(self):
        self.assertEqual(returns({0: 100, 120000: 110}, 60), {})

    def test_contiguous_log_returns(self):
        self.assertAlmostEqual(returns({0: 100, 60000: 110}, 60)[60000], math.log(1.1))

    def test_correlations(self):
        self.assertAlmostEqual(correlation([1,2,3], [3,2,1]), -1)
        self.assertIsNone(correlation([1,1,1], [1,2,3]))

    def test_alignment_required(self):
        with self.assertRaises(ValueError):
            closed([candle(1)], 60)


if __name__ == '__main__':
    unittest.main()
