import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from h3re import rng, rules  # noqa: E402
from h3re.rng import Pcg32, RngStreams, derive_stream  # noqa: E402


class TestPcg32(unittest.TestCase):
    def test_published_vectors(self):
        g = Pcg32(42, 54)
        got = [g.next_u32() for _ in range(6)]
        self.assertEqual(
            got,
            [0xA15C02B7, 0x7B47F409, 0xBA1D3330, 0x83D2F293, 0xBFA4784B, 0xCBED606E],
        )

    def test_golden_pinned(self):
        s = derive_stream(12345, "battle:7", "a")
        self.assertEqual(
            [s.next_u32() for _ in range(6)],
            [2149677332, 3965108465, 3718880003, 1076319833, 4168643118, 2903600694],
        )
        g = Pcg32(1, 1)
        self.assertEqual([g.randint(1, 6) for _ in range(12)],
                         [2, 3, 2, 6, 1, 4, 3, 4, 3, 4, 2, 2])

    def test_range_bounds_and_errors(self):
        g = Pcg32(7, 7)
        for _ in range(500):
            self.assertIn(g.range(3, 8), range(3, 8))
            self.assertIn(g.randint(-2, 2), range(-2, 3))
        self.assertEqual(g.randint(5, 5), 5)
        with self.assertRaises(ValueError):
            g.range(4, 4)

    def test_rejection_sampling_no_bias(self):
        # span 6 -> threshold (2**32 - 6) % 6 == 4: draws 0..3 are rejected.
        span = 6
        threshold = ((1 << 32) - span) % span
        self.assertEqual(threshold, 4)
        g = Pcg32(1, 1)
        with mock.patch.object(Pcg32, "next_u32", side_effect=[0, 1, 3, 4, 9]):
            self.assertEqual(g.range(0, span), 4)  # 0,1,3 rejected; 4 % 6
        with mock.patch.object(Pcg32, "next_u32", side_effect=[2, 5]) as m:
            self.assertEqual(g.range(10, 16), 10 + 5 % 6)
            self.assertEqual(m.call_count, 2)
        # Exhaustive over the accepted draws: every residue equally likely.
        counts = [0] * span
        for r in range(threshold, threshold + 6 * 100):
            counts[r % span] += 1
        self.assertEqual(len(set(counts)), 1)

    def test_chance(self):
        g = Pcg32(3, 3)
        self.assertFalse(g.chance(0, 5))
        self.assertTrue(g.chance(5, 5))
        n = sum(g.chance(1, 4) for _ in range(4000))
        self.assertTrue(800 < n < 1200)
        with mock.patch.object(Pcg32, "next_u32", side_effect=[12, 13]):
            self.assertTrue(g.chance(3, 10))   # 12%10=2 < 3
            self.assertFalse(g.chance(3, 10))  # 13%10=3 !< 3

    def test_streams(self):
        a1 = derive_stream(99, "battle:1", "x")
        a2 = derive_stream(99, "battle:1", "x")
        self.assertEqual([a1.next_u32() for _ in range(8)],
                         [a2.next_u32() for _ in range(8)])
        variants = [
            derive_stream(99, "battle:2", "x"),
            derive_stream(99, "battle:1", "y"),
            derive_stream(100, "battle:1", "x"),
            derive_stream(99, "map-gen"),
        ]
        base = [derive_stream(99, "battle:1", "x").next_u32() for _ in range(8)]
        for v in variants:
            self.assertNotEqual([v.next_u32() for _ in range(8)], base)
        # Drawing from one stream does not affect another.
        f = RngStreams(5)
        s1, s2 = f.stream("ai", "1"), f.stream("weekly")
        ref = f.stream("weekly")
        for _ in range(100):
            s1.next_u32()
        self.assertEqual([s2.next_u32() for _ in range(5)],
                         [ref.next_u32() for _ in range(5)])
        # Field boundaries are unambiguous.
        self.assertNotEqual(derive_stream(1, "ab", "c").state,
                            derive_stream(1, "a", "bc").state)

    def test_rules_compat(self):
        g = Pcg32(11, 2)
        d = rules.base_damage(12, 3, 7, g)
        self.assertTrue(isinstance(d, int) and d > 0)


if __name__ == "__main__":
    unittest.main()
