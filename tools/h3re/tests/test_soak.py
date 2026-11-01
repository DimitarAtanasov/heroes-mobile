import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import adventure as A  # noqa: E402
from h3re import soak  # noqa: E402


class SoakTest(unittest.TestCase):
    def test_battles_and_adventures_pass(self):
        self.assertEqual(soak.soak(3, max_steps=120), [])

    def test_logs_are_reproducible(self):
        for kind in soak.KINDS:
            a = soak.generate_log(kind, 3)
            b = soak.generate_log(kind, 3)
            self.assertEqual(a[1], b[1])
            self.assertGreater(len(a[0]), 1)

    def test_command_roundtrip(self):
        for kind in soak.KINDS:
            cmds, tr = soak.generate_log(kind, 2, 60)
            back = [soak.decode_command(kind, soak.encode_command(c)) for c in cmds]
            self.assertEqual(back, cmds)
            self.assertEqual(soak.trace(kind, 2, back), tr)

    def test_different_seeds_differ(self):
        self.assertNotEqual(soak.generate_log("battle", 1)[1],
                            soak.generate_log("battle", 2)[1])

    def test_detects_injected_nondeterminism(self):
        # A hidden counter makes the second live run differ from the first.
        orig = A.apply
        calls = {"n": 0}

        def flaky(state, cmd, rng=None):
            s, e = orig(state, cmd, rng)
            calls["n"] += 1
            if calls["n"] > 30 and isinstance(cmd, A.EndTurn):
                e = e + ("noise%d" % calls["n"],)
            return s, e

        A.apply = flaky
        try:
            with self.assertRaises(soak.Divergence):
                soak.check_seed("adventure", 0, 100)
        finally:
            A.apply = orig

    def test_cli(self):
        self.assertEqual(soak.main(["--games", "2", "-q"]), 0)


if __name__ == "__main__":
    unittest.main()
