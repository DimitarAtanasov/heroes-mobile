import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import vector_cache  # noqa: E402
from h3re import vectors_present as VP  # noqa: E402


class VectorsPresentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = vector_cache.module_doc(VP)

    def test_shape_and_determinism(self):
        vector_cache.assert_module_deterministic(self, VP)
        self.assertEqual(list(self.out), ["present.json"])
        doc = self.out["present.json"]
        self.assertEqual(doc["view_version"], 2)
        self.assertGreaterEqual(len(doc["cases"]), 30)
        names = [c["name"] for c in doc["cases"]]
        self.assertEqual(len(names), len(set(names)))
        states = [e for c in doc["cases"] for e in c["states"]]
        self.assertGreaterEqual(len(states), 1300)
        self.assertEqual([e["index"] for e in doc["cases"][0]["states"]],
                         list(range(len(doc["cases"][0]["states"]))))

    def test_texts_hash_and_are_canonical(self):
        n = 0
        for c in self.out["present.json"]["cases"]:
            for e in c["states"]:
                self.assertEqual(len(e["view_sha256"]), 64)
                text = e.get("view_json")
                if text is None:
                    continue
                n += 1
                self.assertEqual(hashlib.sha256(text.encode("ascii")).hexdigest(),
                                 e["view_sha256"])
                self.assertEqual(text, json.dumps(json.loads(text), sort_keys=True,
                                                  separators=(",", ":")))
        self.assertGreaterEqual(n, 150)

    def test_taps_present(self):
        listed = sum(len(e["taps"]) for c in self.out["present.json"]["cases"]
                     for e in c["states"] if "taps" in e)
        self.assertGreater(listed, 20000)


if __name__ == "__main__":
    unittest.main()
