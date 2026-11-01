import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import defimg as D  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_def as VD  # noqa: E402

_OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                    "android", "sim", "src", "test", "resources", "vectors"))


class DefVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = VD.generate()[VD.FILE]
        cls.cases = {c["name"]: c for c in cls.doc["cases"]}

    def test_deterministic_and_small(self):
        again = VD.generate()
        self.assertEqual(V._dump(again), V._dump(VD.generate()))
        self.assertLess(len(V._dump(again)), 4 * 1024 * 1024)

    def test_committed_file_matches(self):
        p = os.path.join(_OUT, VD.FILE)
        if not os.path.exists(p):
            self.skipTest("vector file not generated")
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), V._dump(VD.generate()[VD.FILE]))

    def test_coverage(self):
        c = self.cases
        ok = [x for x in c.values() if "ok" in x]
        err = [x for x in c.values() if "error" in x]
        self.assertGreater(len(ok), 100)
        self.assertGreater(len(err), 40)
        fmts = {f["fmt"] for x in ok for b in x["ok"]["blocks"] for f in b["frames"]}
        self.assertEqual(fmts, {0, 1, 2, 3})
        for n in ("legacy_fmt1_0", "shared_offsets_multi_block", "special_palette_variant_1",
                  "budget_15", "rle_two_bombs_default_budget", "fmt3_w40_floor_stride"):
            self.assertIn(n, c)
        self.assertEqual(c["budget_15"]["error"], "DefError")
        self.assertIn("ok", c["budget_exact_16"])
        self.assertEqual(self.doc["truncations"][0][1], "error")
        self.assertEqual(self.doc["truncations"][-1][1], "ok")

    def test_cases_replay_against_python(self):
        for c in self.doc["cases"]:
            data = bytes.fromhex(c["hex"])
            mp = c.get("max_pixels")
            try:
                d = D.parse_def(data) if mp is None else D.parse_def(data, max_pixels=mp)
            except D.DefError:
                self.assertIn("error", c, c["name"])
                continue
            self.assertIn("ok", c, c["name"])
            self.assertEqual(sum(len(b.frames) for b in d.blocks),
                             sum(len(b["frames"]) for b in c["ok"]["blocks"]))

    def test_legacy_and_alpha_values(self):
        f = self.cases["legacy_fmt1_0"]["ok"]["blocks"][0]["frames"][0]
        self.assertEqual((f["x"], f["y"], f["width"], f["height"]), (0, 0, 5, 4))
        sp = self.cases["special_palette_variant_0"]["ok"]["blocks"][0]["frames"][0]
        alphas = [bytes.fromhex(sp["rgba_hex"])[i * 4 + 3] for i in range(10)]
        self.assertEqual(alphas, [0, 64, 64, 128, 128, 255, 128, 64, 255, 255])


if __name__ == "__main__":
    unittest.main()
