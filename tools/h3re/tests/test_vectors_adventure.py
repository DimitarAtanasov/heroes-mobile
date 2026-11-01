import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import vector_cache  # noqa: E402

from h3re import adventure as A  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_adventure as VA  # noqa: E402

GOLDEN_PIN = "179c570020d05be9a53c265a76517a4bb9f398c92f37d19485d30f804f703420"


class TestAdventureVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = vector_cache.module_doc(VA)[VA.FILE]
        cls.cases = {c["name"]: c for c in cls.doc["cases"]}

    def test_generation_is_deterministic(self):
        # Until the lead wires the module into vectors.EXTRA_VECTOR_MODULES, compare against an
        # independent second generation directly.
        if "vectors_adventure" in V.EXTRA_VECTOR_MODULES:
            vector_cache.assert_module_deterministic(self, VA)
        else:
            self.assertEqual(V._dump(VA.generate()[VA.FILE]), V._dump(self.doc))

    def test_non_trivial_and_covering(self):
        steps = [s for c in self.doc["cases"] for s in c["steps"]]
        self.assertGreaterEqual(len(self.doc["cases"]), 20)
        self.assertGreaterEqual(len(steps), 1000)
        self.assertEqual({s["command"]["type"] for s in steps}, {c.__name__ for c in VA.COMMANDS})
        self.assertEqual({e["type"] for s in steps for e in s["events"]},
                         {e.__name__ for e in VA.EVENTS})
        pols = {c["policy"] for c in self.doc["cases"]}
        self.assertEqual(pols, {n for n, _ in VA._policies()})
        self.assertGreaterEqual(len(self.doc["illegal_cases"]), 500)

    def test_golden_reproduces_the_pin(self):
        last = self.cases["golden"]["steps"][-1]
        self.assertEqual(last["sha256"], GOLDEN_PIN)
        self.assertEqual(json.loads(last["canonical"])["day"], 15)

    def test_steps_match_the_reference(self):
        for c in self.doc["cases"]:
            texts = [c["initial"]["canonical"]] + [s["canonical"] for s in c["steps"]]
            for t, s in zip(texts[1:], c["steps"]):
                self.assertEqual(hashlib.sha256(t.encode("ascii")).hexdigest(), s["sha256"])
            self.assertGreater(len(set(texts)), 3, c["name"])

    def test_illegal_cases_are_rejected_by_python(self):
        msgs = {ic["message"] for ic in self.doc["illegal_cases"]}
        for want in ("game already started", "game not started", "no such hero",
                     "hero does not belong to the current player",
                     "destination not reachable today", "not player True's turn",
                     "not a tile: 'ab'"):
            self.assertIn(want, msgs)

    def test_constants_mirror_the_module(self):
        k = self.doc["constants"]
        self.assertEqual(k["terrain_cost"], A.TERRAIN_COST)
        self.assertEqual(k["speed_mp"], list(A._SPEED_MP))
        self.assertEqual(k["logistics_pct"], list(A.LOGISTICS_PCT))


if __name__ == "__main__":
    unittest.main()
