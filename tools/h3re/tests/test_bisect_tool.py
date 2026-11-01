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


class BisectPolicyTest(unittest.TestCase):
    def _diverging(self):
        for seed in range(1, 40):
            cmds, _ = soak.generate_log("battle", seed)
            pa, _ = T.resolve_policy("battle", "default")
            pb, _ = T.resolve_policy("battle", "alt-order")
            rep = T.bisect("battle", seed, cmds, None, "battle", seed, cmds, None, pa, pb)
            if rep:
                return seed, cmds, rep
        self.fail("no seed diverges between default and alt-order")

    def test_same_log_two_policies_diverges_at_reported_step(self):
        seed, cmds, rep = self._diverging()
        self.assertGreaterEqual(rep["step"], 0)
        self.assertLess(rep["step"], len(cmds) + 1)
        with tempfile.TemporaryDirectory() as d:
            pa = d + "/a.json"
            with open(pa, "w") as f:
                json.dump(T.dump_log("battle", seed, cmds), f)
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = T.main([pa, pa, "--policy-b", "alt-order"])
            out = buf.getvalue()
            self.assertEqual(rc, 1)
            self.assertIn("policy A: default", out)
            self.assertIn("policy B: alt-order", out)
            self.assertIn("first divergence at step %d" % rep["step"], out)
            # same policy on both sides: no divergence
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(T.main([pa, pa, "--policy", "alt-order"]), 0)

    def test_seed_mode_policy_b(self):
        seed, _, rep = self._diverging()
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(T.main(["--kind", "battle", "--seed", str(seed),
                                     "--policy-b", "alt-order"]), 1)
            self.assertEqual(T.main(["--kind", "battle", "--seed", str(seed),
                                     "--policy", "alt-order"]), 0)

    def test_unknown_field_and_name_rejected(self):
        with self.assertRaises(ValueError):
            T.resolve_policy("battle", None, {"no_such_field": 1})
        with self.assertRaises(ValueError):
            T.resolve_policy("battle", "nope")
        with self.assertRaises(ValueError):
            T.resolve_policy("adventure", None, {"row_offset": "odd"})
        import io
        import contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                T.main(["--kind", "battle", "--seed", "1",
                        "--override", '{"bogus": 1}'])

    def test_override_forms(self):
        self.assertEqual(T.parse_overrides('{"row_offset": "odd"}'), {"row_offset": "odd"})
        self.assertEqual(T.parse_overrides("row_offset=odd;edge_columns_walkable=true"),
                         {"row_offset": "odd", "edge_columns_walkable": True})
        self.assertEqual(T.parse_overrides(None), {})
        pol, spec = T.resolve_policy("battle", "default", {"row_offset": "odd"})
        self.assertEqual(pol.row_offset, "odd")
        self.assertEqual(spec, {"name": "default", "fields": {"row_offset": "odd"}})

    def test_header_round_trip(self):
        cmds, _ = soak.generate_log("battle", 3)
        spec = {"name": "alt-order", "fields": {"row_offset": "even"}}
        with tempfile.TemporaryDirectory() as d:
            p = d + "/l.json"
            with open(p, "w") as f:
                json.dump(T.dump_log("battle", 3, cmds, spec), f)
            k, sd, c, h = T.load_log_ex(p)
            self.assertEqual((k, sd, h), ("battle", 3, spec))
            self.assertEqual(c, cmds)
            self.assertEqual(T.load_log(p), ("battle", 3, cmds))
            # no header when no policy: old format preserved
            self.assertNotIn("policy", T.dump_log("battle", 3, cmds))
            with open(p, "w") as f:
                json.dump(T.dump_log("battle", 3, cmds), f)
            self.assertIsNone(T.load_log_ex(p)[3])
            bad = T.dump_log("battle", 3, cmds, {"name": None, "fields": {"zzz": 1}})
            bad["policy"] = {"name": None, "fields": {"zzz": 1}}
            with open(p, "w") as f:
                json.dump(bad, f)
            with self.assertRaises(ValueError):
                T.load_log_ex(p)

    def test_header_policy_used_and_emit(self):
        seed, cmds, rep = self._diverging()
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as d:
            pa, pb = d + "/a.json", d + "/b.json"
            with open(pa, "w") as f:
                json.dump(T.dump_log("battle", seed, cmds, {"name": "alt-order", "fields": {}}), f)
            with open(pb, "w") as f:
                json.dump(T.dump_log("battle", seed, cmds), f)
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(T.main([pa, pb]), 1)
            self.assertIn("policy A: alt-order", buf.getvalue())
            em = d + "/e.json"
            with contextlib.redirect_stdout(io.StringIO()):
                T.main(["--kind", "battle", "--seed", str(seed), "--policy", "alt-order",
                        "--emit", em])
            self.assertEqual(T.load_log_ex(em)[3]["name"], "alt-order")


if __name__ == "__main__":
    unittest.main()
