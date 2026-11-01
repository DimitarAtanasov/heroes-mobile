import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json  # noqa: E402
import tempfile  # noqa: E402

from h3re import bisect_tool as T  # noqa: E402
from h3re import soak  # noqa: E402


class BisectTest(unittest.TestCase):
    def run_pair(self, kind, seed, perturb):
        cmds, _ = soak.generate_log(kind, seed)
        return T.bisect(kind, seed, cmds, None, kind, seed, cmds, perturb)

    def test_identical(self):
        self.assertIsNone(self.run_pair("battle", 4, None))

    def test_rng_perturbation_reports_step_and_field(self):
        rep = self.run_pair("battle", 4, ("rng", 5))
        self.assertIsNotNone(rep)
        self.assertGreaterEqual(rep["step"], 5)
        self.assertTrue(rep["fields"])
        self.assertTrue(rep["fields"][0][0].startswith("stacks["))

    def test_drop_perturbation_adventure(self):
        rep = self.run_pair("adventure", 1, ("drop", 3))
        self.assertEqual(rep["step"], 3)
        paths = [f[0] for f in rep["fields"]]
        self.assertIn("current", paths)

    def test_diff_states(self):
        d = T.diff_states({"a": [1, 2], "b": 1}, {"a": [1, 3], "c": 2})
        self.assertEqual(d, [("a[1]", 2, 3), ("b", 1, "<absent>"), ("c", "<absent>", 2)])

    def test_two_log_files(self):
        cmds, _ = soak.generate_log("battle", 2)
        with tempfile.TemporaryDirectory() as d:
            pa, pb = d + "/a.json", d + "/b.json"
            with open(pa, "w") as f:
                json.dump(T.dump_log("battle", 2, cmds), f)
            with open(pb, "w") as f:
                json.dump(T.dump_log("battle", 2, cmds[:-2]), f)
            self.assertEqual(T.main([pa, pa]), 0)
            self.assertEqual(T.main([pa, pb]), 1)

    def test_cli_seed_mode(self):
        self.assertEqual(T.main(["--kind", "battle", "--seed", "4"]), 0)
        self.assertEqual(T.main(["--kind", "battle", "--seed", "4",
                                 "--perturb", "rng@2"]), 1)


if __name__ == "__main__":
    unittest.main()
