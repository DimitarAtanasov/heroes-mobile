import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import vector_cache  # noqa: E402
from h3re import battle as B  # noqa: E402
from h3re import datapack as D  # noqa: E402
from h3re import rules as R  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_pack as VP  # noqa: E402


class PackVectorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = vector_cache.module_doc(VP)[VP.FILE]

    def test_deterministic(self):
        vector_cache.assert_module_deterministic(self, VP)

    def test_shipped_hashes_match_loaded_packs(self):
        s = self.doc["shipped"]
        self.assertEqual(s["rules"]["hash"], R.RULES_HASH)
        self.assertEqual(s["policy"]["hash"], B.POLICY_HASH)
        self.assertEqual(s["pack_hash"], D.load_dir(D._REPO_DIR).content_hash)

    def test_counts_and_categories(self):
        self.assertGreaterEqual(len(self.doc["valid"]), 30)
        self.assertGreaterEqual(len(self.doc["invalid"]), 500)
        cats = {c["category"] for c in self.doc["invalid"]}
        self.assertEqual(cats, {
            "invalid_json", "duplicate_key", "float", "type", "unknown_key", "missing_key", "range",
            "length", "enum", "schema_version", "table", "distinct", "dmg_order", "duplicate_name",
            "unknown_creature", "empty"})

    def test_every_invalid_case_fails_in_python(self):
        for c in self.doc["invalid"]:
            msg, _ = VP.run(c["kind"], c["text"])
            self.assertEqual(msg, c["message"], c["id"])
            self.assertEqual(VP.classify(msg), c["category"], c["id"])

    def test_valid_cases_hash_as_declared(self):
        shipped = self.doc["shipped"]
        rc = D._check_rules(D._loads(VP.read_base("rules"), "rules.json"))
        for v in self.doc["valid"]:
            _, h = VP.parsed_and_hash(v["kind"], v["text"], rc)
            self.assertEqual(h, v["hash"], v["id"])
            if v.get("same_hash_as") == "shipped":
                self.assertEqual(h, shipped[v["kind"]]["hash"], v["id"])

    def test_committed_file_is_current(self):
        path = os.path.join(V.DEFAULT_OUT, VP.FILE)
        if not os.path.exists(path):
            self.skipTest("vectors not generated")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), V._dump(self.doc))


if __name__ == "__main__":
    unittest.main()
