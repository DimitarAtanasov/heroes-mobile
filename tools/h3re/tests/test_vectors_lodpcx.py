"""Tests for the LOD and PCX conformance vectors (synthetic data only)."""

import io
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import vector_cache  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_lodpcx as L  # noqa: E402
from h3re.lod import LodArchive, LodFormatError  # noqa: E402
from h3re.pcx import parse_pcx  # noqa: E402

MAX_VECTOR_BYTES = 3 * 1024 * 1024


class LodPcxVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = vector_cache.module_doc(L)

    def lod_cases(self):
        return self.generated[L.LOD_FILE]["cases"]

    def pcx_cases(self):
        return self.generated[L.PCX_FILE]["cases"]

    def test_generation_is_deterministic(self):
        vector_cache.assert_module_deterministic(self, L)

    def test_committed_files_match_fresh_generation(self):
        # Failure means the generator changed without the vector files being rewritten.
        # Regenerate with `cd tools/h3re && python3 -m h3re.vectors` and review the diff.
        out = V.DEFAULT_OUT
        for name, obj in self.generated.items():
            path = os.path.join(out, name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), V._dump(obj), name)

    def test_files_are_canonical_ascii_json_and_small(self):
        for name, obj in self.generated.items():
            data = V._dump(obj)
            self.assertLess(len(data), MAX_VECTOR_BYTES, name)
            text = data.decode("ascii")
            self.assertEqual(text, json.dumps(json.loads(text), sort_keys=True,
                                              separators=(",", ":")) + "\n", name)

    def test_lod_cases_cover_required_categories(self):
        names = {c["name"] for c in self.lod_cases()}
        for required in ("bad_magic", "empty_file", "count_u32_max", "count_over_cap",
                         "count_bomb_small_file", "raw_offset_past_end",
                         "offset_and_size_u32_overflow", "packed_size_past_end",
                         "empty_name_rejected", "corrupt_zlib_not_zlib",
                         "zlib_declared_size_too_small", "zlib_declared_size_too_large",
                         "zlib_truncated_stream", "zlib_bad_adler32",
                         "zlib_preset_dictionary_rejected", "zlib_expansion_capped",
                         "duplicate_last_wins_lenient", "duplicate_strict_rejected",
                         "duplicate_keeps_first_position", "valid_empty_archive"):
            self.assertIn(required, names)

    def test_every_proper_prefix_of_base_archive_is_a_case(self):
        base = next(c for c in self.lod_cases() if c["name"] == "valid_base_archive")
        size = len(bytes.fromhex(base["hex"]))
        prefixes = [c for c in self.lod_cases() if c["name"].startswith("truncated_base_at_")]
        self.assertEqual(len(prefixes), size)
        for c in prefixes:
            self.assertEqual(c["expect"], {"open": "LodFormatError"}, c["name"])

    def test_expectations_match_reference_reader(self):
        for c in self.lod_cases():
            blob = bytes.fromhex(c["hex"])
            try:
                arc = LodArchive(io.BytesIO(blob), len(blob), strict=c["strict"])
            except LodFormatError:
                self.assertEqual(c["expect"], {"open": "LodFormatError"}, c["name"])
                continue
            with arc:
                self.assertEqual(c["expect"]["list"], arc.list(), c["name"])
                for m in c["expect"]["members"]:
                    self.assertEqual(arc.read(m["lookup"]) if "data" in m else None,
                                     bytes.fromhex(m["data"]) if "data" in m else None,
                                     c["name"])

    def test_lookup_is_lowercase_of_stored_name(self):
        for c in self.lod_cases():
            for m in c["expect"].get("members", []):
                self.assertEqual(m["lookup"], m["name"].lower(), c["name"])

    def test_pcx_expectations_match_reference_parser(self):
        for c in self.pcx_cases():
            blob = bytes.fromhex(c["hex"])
            try:
                img = parse_pcx(blob)
            except Exception:
                self.assertEqual(c["expect"], {"ok": False, "error": "PcxError"}, c["name"])
                continue
            self.assertTrue(c["expect"]["ok"], c["name"])
            self.assertEqual(c["expect"]["rgb"], img.to_rgb().hex(), c["name"])
            self.assertEqual(c["expect"]["mode"], img.mode, c["name"])

    def test_pcx_cases_cover_palette_and_mode_rules(self):
        names = {c["name"] for c in self.pcx_cases()}
        for required in ("indexed_2x2_valid", "bgr24_2x2_valid",
                         "indexed_gap_before_palette_tolerated",
                         "indexed_trailing_bytes_shift_palette", "indexed_width_cap_8192x1",
                         "width_over_cap", "height_over_cap", "zero_dimensions",
                         "size_matches_neither_mode"):
            self.assertIn(required, names)
        for c in self.pcx_cases():
            if c["expect"]["ok"]:
                pal = c["expect"]["palette"]
                if c["expect"]["mode"] == "indexed":
                    self.assertEqual(len(bytes.fromhex(pal)), 768, c["name"])
                else:
                    self.assertIsNone(pal, c["name"])


if __name__ == "__main__":
    unittest.main()
