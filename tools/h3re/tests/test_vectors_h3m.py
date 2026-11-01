"""Tests for the H3M header conformance vectors (synthetic data only)."""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import vector_cache  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_h3m as M  # noqa: E402
from h3re.h3m import H3mError, parse_h3m  # noqa: E402

MAX_VECTOR_BYTES = 5 * 1024 * 1024


class H3mVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = vector_cache.module_doc(M)
        cls.cases = cls.generated[M.VECTOR_FILE]["cases"]

    def data_of(self, c, blobs):
        if "hex" in c:
            blobs[c["name"]] = bytes.fromhex(c["hex"])
            return blobs[c["name"]]
        return blobs[c["of"]][:c["cut"]]

    def test_generation_is_deterministic(self):
        # Compared against a direct regeneration, so the test does not depend on the module
        # being wired into vectors.EXTRA_VECTOR_MODULES yet (the lead wires it).
        again = M.generate()
        self.assertEqual(set(again), set(self.generated))
        for name, doc in again.items():
            self.assertEqual(V._dump(doc), V._dump(self.generated[name]), name)

    def test_committed_file_matches_fresh_generation(self):
        # Regenerate with `cd tools/h3re && python3 -m h3re.vectors` once the module is wired.
        for name, obj in self.generated.items():
            path = os.path.join(V.DEFAULT_OUT, name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), V._dump(obj), name)

    def test_file_is_canonical_ascii_json_and_small(self):
        for name, obj in self.generated.items():
            data = V._dump(obj)
            self.assertLess(len(data), MAX_VECTOR_BYTES, name)
            text = data.decode("ascii")
            self.assertEqual(text, json.dumps(json.loads(text), sort_keys=True,
                                              separators=(",", ":")) + "\n", name)

    def test_names_unique_and_counts(self):
        names = [c["name"] for c in self.cases]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 1500)
        ok = sum(1 for c in self.cases if c["expect"]["ok"])
        self.assertGreaterEqual(ok, 200)
        self.assertGreaterEqual(len(names) - ok, 1000)

    def test_required_categories_present(self):
        names = {c["name"] for c in self.cases}
        for required in (
                "roe_default_36", "ab_default_72_two_levels", "sod_default_36", "chr_default_36",
                "wog_default_72", "sod_victory_10_position", "sod_victory_10", "roe_victory_10",
                "sod_predefined_all_fields", "hota_0x20", "bad_version_0x99", "sod_trailing_bytes_ignored",
                "size_bound_0", "size_bound_1", "size_bound_1024", "size_bound_1025",
                "gz_multi_member", "gz_trailing_junk", "gz_bomb_64mib", "sod_placeholder_count_bomb",
                "sod_rumor_count_bomb", "sod_player_hero_count_bomb", "gz_member_bad_hcrc"):
            self.assertIn(required, names)
        for t in range(11):
            self.assertIn(f"sod_victory_{t}", names)
        for tag in ("roe", "ab", "sod"):
            base = next(c for c in self.cases if c["name"] == f"cut_{tag}_base")
            n = len(bytes.fromhex(base["hex"]))
            cuts = [c for c in self.cases if c["name"].startswith(f"cut_{tag}_at_")]
            self.assertEqual(len(cuts), n)
            for c in cuts:
                self.assertFalse(c["expect"]["ok"], c["name"])

    def test_every_victory_type_parsed_with_its_fields(self):
        by = {c["name"]: c for c in self.cases}
        for tag in ("roe", "sod"):
            for t in range(11):
                v = by[f"{tag}_victory_{t}"]["expect"]["header"]["victory"]
                self.assertEqual(v["type"], t)
        self.assertEqual(by["sod_victory_10"]["expect"]["header"]["victory"]["pos"], [5, 6, 1])
        self.assertEqual(by["sod_victory_10"]["expect"]["header"]["victory"]["artifact"], 0x2A)

    def test_expectations_match_reference_reader(self):
        blobs = {}
        for c in self.cases:
            data = self.data_of(c, blobs)
            try:
                h = parse_h3m(data)
            except H3mError as e:
                self.assertEqual(c["expect"]["ok"], False, c["name"])
                self.assertEqual(bool(c["expect"].get("hota")), "HotA" in str(e), c["name"])
                continue
            self.assertTrue(c["expect"]["ok"], c["name"])
            self.assertEqual(c["expect"]["header"], M.dump_header(h), c["name"])

    def test_small_maps_carry_raw_tiles_large_maps_only_hash(self):
        by = {c["name"]: c for c in self.cases}
        self.assertIn("raw", by["sod_tiny_2x2"]["expect"]["header"]["tiles"])
        self.assertNotIn("raw", by["sod_default_36"]["expect"]["header"]["tiles"])


if __name__ == "__main__":
    unittest.main()
