import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from h3re import vectors_txt as V

VEC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                       "android", "sim", "src", "test", "resources", "vectors"))


def _dump(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


class VectorsTxtTest(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(_dump(V.generate()["txt.json"]), _dump(V.generate()["txt.json"]))

    def test_shape_and_coverage(self):
        g = V.generate()
        self.assertEqual(set(g), {"txt.json", "content.json"})
        txt, con = g["txt.json"]["cases"], g["content.json"]["cases"]
        self.assertGreaterEqual(len(txt), 300)
        self.assertGreaterEqual(len(con), 40)
        names = [c["name"] for c in txt]
        self.assertEqual(len(names), len(set(names)))
        cats = {c["error"] for c in txt if "error" in c}
        self.assertEqual(cats, {"header_rows", "too_large", "too_many_lines",
                                "unknown_encoding", "decode"})
        ccats = {c["error"]["category"] for c in con if "error" in c}
        self.assertTrue({"table", "header", "missing_cell", "empty_cell", "not_integer",
                         "schema", "duplicate", "no_rows"} <= ccats)
        self.assertTrue(any(c["expect"]["unknown"] for c in con if "expect" in c))

    def test_bare_lf_is_data_in_vectors(self):
        c = next(c for c in V.generate()["txt.json"]["cases"] if c["name"] == "bare_lf_is_data")
        self.assertEqual(c["expect"]["rows"], [["a\nb", "c"], ["d"]])

    def test_committed_files_fresh(self):
        for name, obj in V.generate().items():
            p = os.path.join(VEC_DIR, name)
            if not os.path.exists(p):
                self.skipTest("vectors not generated: " + name)
            with open(p, "rb") as f:
                self.assertEqual(f.read(), _dump(obj), name)


if __name__ == "__main__":
    unittest.main()
