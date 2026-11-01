import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import vectors_battle as VB  # noqa: E402


class TestBattleVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = VB.generate()

    def test_generation_is_deterministic(self):
        self.assertEqual(self.out, VB.generate())

    def test_is_json_serialisable_and_non_trivial(self):
        doc = self.out[VB.FILE]
        json.dumps(doc)
        self.assertGreaterEqual(len(doc["cases"]), 10)
        steps = [s for c in doc["cases"] for s in c["steps"]]
        self.assertGreaterEqual(len(steps), 300)
        # Every command and event type occurs in the playouts.
        cmds = {s["command"]["type"] for s in steps}
        self.assertEqual(cmds, {c.__name__ for c in VB.COMMANDS})
        evs = {e["type"] for s in steps for e in s["events"]}
        self.assertEqual(evs, {e.__name__ for e in VB.EVENTS})
        # Non-default policies are exercised and states change from step to step.
        self.assertGreaterEqual({c["scenario"]["policy"] for c in doc["cases"]},
                                {"default", "alt-order", "vcmi-like", "strict"})
        for c in doc["cases"]:
            hashes = [c["initial"]["sha256"]] + [s["sha256"] for s in c["steps"]]
            self.assertGreater(len(set(hashes)), 3, c["name"])

    def test_hashes_match_canonical_text(self):
        for c in self.out[VB.FILE]["cases"]:
            for s in [c["initial"]] + c["steps"]:
                self.assertEqual(hashlib.sha256(s["canonical"].encode("ascii")).hexdigest(),
                                 s["sha256"])

    def test_unit_shapes_covered(self):
        two_hex = shooter = flyer = one_hex = False
        for c in self.out[VB.FILE]["cases"]:
            st = json.loads(c["initial"]["canonical"])
            for s in st["stacks"]:
                cr = s["creature"]
                two_hex |= cr["double_wide"]
                one_hex |= not cr["double_wide"]
                shooter |= cr["shots"] > 0
                flyer |= cr["flyer"]
        self.assertTrue(two_hex and one_hex and shooter and flyer)


if __name__ == "__main__":
    unittest.main()
