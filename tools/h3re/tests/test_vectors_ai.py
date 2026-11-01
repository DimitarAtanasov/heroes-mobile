import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from h3re import battle as B  # noqa: E402
from h3re import battle_ai  # noqa: E402
from h3re import soak  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_ai as VA  # noqa: E402
import vector_cache  # noqa: E402
from test_vectors_battle import state_from_json  # noqa: E402

_DOC = None


def doc():
    global _DOC
    if _DOC is None:
        _DOC = vector_cache.module_doc(VA)[VA.FILE]
    return _DOC


def _floats(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(_floats(v) for v in x.values())
    if isinstance(x, list):
        return any(_floats(v) for v in x)
    return False


class VectorsAiTest(unittest.TestCase):
    def test_shape_and_no_floats(self):
        d = doc()
        self.assertEqual(d["format"], 1)
        self.assertFalse(_floats(d))
        self.assertGreaterEqual(len(d["games"]), 60)
        for g in d["games"]:
            self.assertEqual(g["steps"][0]["stateful"], {"type": "Begin"})
            self.assertEqual(g["final"]["steps"], len(g["steps"]))

    def test_coverage(self):
        seen = set()
        for g in doc()["games"]:
            for s in g["steps"]:
                seen.add((s["defends_before"], s["stateful"]["type"]))
                seen.add(s["stateless"]["type"])
        for want in ((2, "Wait"), (1, "Defend"), (0, "Defend"), (2, "Move"), (0, "Shoot"),
                     (0, "Attack"), "Wait", "Defend"):
            self.assertIn(want, seen)
        self.assertTrue(any(g["final"]["winner"] is not None for g in doc()["games"]))

    def test_recorded_choices_replay_in_python(self):
        n = 0
        for g in doc()["games"]:
            for s in g["steps"]:
                if "canonical" not in s:
                    continue
                state = state_from_json(s["canonical"])
                self.assertEqual(B.state_hash(state), s["sha256"])
                got = json.loads(json.dumps(soak.encode_command(battle_ai.choose(state))))
                self.assertEqual(got, s["stateless"])
                n += 1
        self.assertGreater(n, 300)

    def test_defend_cap_in_records(self):
        for g in doc()["games"]:
            run = {0: 0, 1: 0}
            for s in g["steps"]:
                if s["side"] is None:
                    continue
                self.assertEqual(s["defends_before"], run[s["side"]], g["name"])
                run[s["side"]] = run[s["side"]] + 1 if s["stateful"]["type"] == "Defend" else 0
                self.assertLessEqual(run[s["side"]], battle_ai.MAX_DEFENDS)

    def test_on_disk_vector_is_current(self):
        path = os.path.join(V.DEFAULT_OUT, VA.FILE)
        if not os.path.exists(path):
            self.skipTest("vector file not generated yet")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), V._dump(doc()))


if __name__ == "__main__":
    unittest.main()
