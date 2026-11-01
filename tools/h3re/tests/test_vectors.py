import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import battle as B  # noqa: E402
from h3re import vectors as V  # noqa: E402


class TestVectors(unittest.TestCase):
    def test_generation_is_deterministic(self):
        self.assertEqual(V.generate(), V.generate())

    def test_committed_files_match_fresh_generation(self):
        # Failure means Python changed (or vectors were not regenerated):
        # run `cd tools/h3re && python3 -m h3re.vectors` and review the diff.
        self.assertEqual(V.check(V.DEFAULT_OUT), [])

    def test_files_are_canonical_ascii_json(self):
        for name, data in V.generate().items():
            text = data.decode("ascii")
            self.assertTrue(text.endswith("\n"), name)
            obj = json.loads(text)
            again = json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"
            self.assertEqual(text, again, name)

    def test_state_vectors_hash_their_canonical_bytes(self):
        import hashlib
        doc = json.loads(V.generate()["state_hash.json"])
        for c in doc["cases"]:
            self.assertEqual(hashlib.sha256(c["canonical"].encode("ascii")).hexdigest(), c["sha256"])
        self.assertEqual(doc["cases"][0]["sha256"], B.state_hash(V.golden_setup()))

    def test_published_pcg_vector_present(self):
        doc = json.loads(V.generate()["rng.json"])
        self.assertEqual(doc["published"]["u32"][0], 0xA15C02B7)
        self.assertEqual(doc["pcg32_u32"][0]["u32"][:6], doc["published"]["u32"])


if __name__ == "__main__":
    unittest.main()
