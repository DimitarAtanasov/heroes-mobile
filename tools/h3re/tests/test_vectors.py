import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from h3re import battle as B  # noqa: E402
from h3re import vectors as V  # noqa: E402
import vector_cache  # noqa: E402


class TestVectors(unittest.TestCase):
    def test_generation_is_deterministic(self):
        self.assertEqual(V.generate(), vector_cache.fresh_all())

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

    def test_rules_vectors_cover_required_cases(self):
        doc = json.loads(V.generate()["rules.json"])
        sections = ("attack_defense", "base_damage", "damage_from_base", "resolve",
                    "resolve_seeded", "preview", "luck_chance", "good_morale_chance",
                    "bad_morale_chance", "penalties")
        self.assertGreaterEqual(sum(len(doc[k]) for k in sections), 300)
        stacks = {c["ctx"]["count"] for c in doc["resolve"]}
        for n in (1, 10, 11, 1000):
            self.assertIn(n, stacks)
        self.assertIn(1, {c["damage"] for c in doc["resolve"] if "damage" in c})
        self.assertTrue(any(a["attack"] - a["defense"] == 60 for a in doc["attack_defense"]))
        self.assertTrue(any(a["attack"] - a["defense"] == -28 for a in doc["attack_defense"]))
        self.assertTrue(any("error" in c for c in doc["base_damage"]))
        self.assertTrue(any("error" in c for c in doc["resolve"]))
        self.assertTrue(all(isinstance(c["state_after"], int) for c in doc["resolve_seeded"]
                            if "error" not in c))

    def test_rules_pack_matches_data_file(self):
        # Compare with the raw file as loaded (independent of rules.py's Fraction arithmetic).
        from fractions import Fraction
        from h3re import datapack
        with open(os.path.join(datapack.LOADED_DIR, "rules.json"), encoding="utf-8") as f:
            raw = json.load(f)
        pack = json.loads(V.generate()["rules.json"])["pack"]

        def pr(x):
            fr = Fraction(*x)
            return [fr.numerator, fr.denominator]

        for k in ("ad_bonus_cap", "ad_bonus_per_point", "da_penalty_cap", "da_penalty_per_point",
                  "half", "hate_bonus", "luck_bonus"):
            self.assertEqual(pack[k], pr(raw[k]), k)
        for k in ("archery", "armorer", "offense"):
            self.assertEqual(pack[k], [pr(r) for r in raw[k]], k)
        for k in ("bad_morale_numerators", "vcmi_bad_morale_numerators", "morale_die"):
            self.assertEqual(pack[k], raw[k], k)

    def test_hex_vectors_cover_required_cases(self):
        doc = json.loads(V.generate()["hex.json"])
        self.assertEqual({n["row_offset"] for n in doc["neighbours"]}, {"even", "odd"})
        self.assertEqual(len(doc["neighbours"]), 2 * 17 * 11)
        for off in ("even", "odd"):
            self.assertEqual(len(doc["distance"][off]), (17 * 11) ** 2)
        r = doc["reach"]
        self.assertGreaterEqual(len(r), 500)
        self.assertTrue(any(c["flyer"] for c in r))
        self.assertTrue(any(c["double_wide"] for c in r))
        self.assertTrue(any(c["edge_columns_walkable"] for c in r))
        self.assertTrue(any(not o["alive"] for c in r for o in c["others"]))
        self.assertTrue(any(c["reachable"] == [] for c in r))
        for c in r:
            self.assertEqual(len(c["reachable"]), len(c["paths"]))
            for h, p in zip(c["reachable"], c["paths"]):
                self.assertEqual(p[-1], h)

    def test_hex_vectors_agree_with_public_geometry(self):
        doc = json.loads(V.generate()["hex.json"])
        a, b = (3, 2), (12, 9)
        i = (a[1] * 17 + a[0]) * 187 + (b[1] * 17 + b[0])
        self.assertEqual(doc["distance"]["even"][i], B.hex_distance(a, b, "even"))
        self.assertEqual(doc["distance"]["odd"][i], B.hex_distance(a, b, "odd"))


if __name__ == "__main__":
    unittest.main()
