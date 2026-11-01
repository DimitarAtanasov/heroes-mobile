"""Tests for h3re.content using synthetic tables only."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from h3re import datapack  # noqa: E402
from h3re.content import ContentError, load_creatures, load_mapping, parse_creatures  # noqa: E402

HEAD = [["Creature table"], ["Singular", "Plural", "Wood", "Mercury"]]


def row(name, hp=10, speed=4, att=5, de=4, lo=1, hi=3, shots=0, abil="", sp=0, plural="Xs"):
    cost = ["0", "0", "0", "0", "0", "0", "100"]
    nums = [50, 60, 7, 0, hp, speed, att, de, lo, hi, shots, sp, 1, 5]
    return [name, plural] + cost + [str(n) for n in nums] + ["long text", abil]


def build(rows, head=HEAD):
    return ("\r\n".join("\t".join(r) for r in head + rows) + "\r\n").encode("cp1252")


class ContentTests(unittest.TestCase):
    def test_basic_and_validation(self):
        res = parse_creatures(build([
            row("Zork", hp=20, shots=8, abil="Flying, Double Attack"),
            row("Blip", abil="")]))
        self.assertEqual([c["name"] for c in res.creatures], ["Blip", "Zork"])
        z = res.creatures[1]
        self.assertEqual((z["hp"], z["shots"], z["flyer"], z["strikes_twice"]), (20, 8, True, True))
        self.assertNotIn("shots", res.creatures[0])
        self.assertEqual(res.extras["Zork"]["cost_gold"], 100)
        self.assertEqual(res.extras["Zork"]["growth"], 7)
        self.assertEqual(res.unknown, ())
        datapack._check_creatures({"schema_version": 1, "creatures": list(res.creatures)})

    def test_unknown_reported_known_ignored(self):
        res = parse_creatures(build([row("Zork", abil="Flying, Spits Glitter, Shooter")]))
        self.assertEqual(res.unknown, ((3, "Zork", "Spits Glitter"),))
        self.assertTrue(res.creatures[0]["flyer"])

    def test_roe_no_spell_points(self):
        r = row("Zork")
        del r[9 + 11]  # spell points column
        res = parse_creatures(build([r]), roe=True)
        self.assertEqual(res.creatures[0]["hp"], 10)

    def test_plural2_header(self):
        head = [["x"], ["Singular", "Plural", "Plural2", "Wood"]]
        r = row("Zork")
        r.insert(1, "Zorkish")
        res = parse_creatures(build([r], head))
        self.assertEqual(res.creatures[0]["name"], "Zork")
        self.assertEqual(res.extras["Zork"]["plural"], "Xs")

    def test_blank_rows_skipped(self):
        res = parse_creatures(build([[""], row("Zork"), ["", "x"]]))
        self.assertEqual(len(res.creatures), 1)

    def test_errors_name_row_and_column(self):
        cases = [
            (row("Zork", hp=0), "row 3"),
            (row("Zork", lo=9, hi=2), "row 3"),
        ]
        for r, frag in cases:
            with self.assertRaises(ContentError) as cm:
                parse_creatures(build([r]))
            self.assertIn(frag, str(cm.exception))
        bad = row("Zork")
        bad[13] = "abc"  # hp
        with self.assertRaises(ContentError) as cm:
            parse_creatures(build([bad]))
        self.assertIn("row 3, column 'hp'", str(cm.exception))
        short = row("Zork")[:14]
        with self.assertRaises(ContentError) as cm:
            parse_creatures(build([short]))
        self.assertIn("column 'speed'", str(cm.exception))
        with self.assertRaises(ContentError) as cm:
            parse_creatures(build([row("A"), row("A")]))
        self.assertIn("row 4", str(cm.exception))
        self.assertIn("duplicate", str(cm.exception))

    def test_bad_header_and_empty(self):
        with self.assertRaises(ContentError):
            parse_creatures(build([row("A")], [["x"], ["Name", "Foo"]]))
        with self.assertRaises(ContentError):
            parse_creatures(build([]))
        with self.assertRaises(ContentError):
            parse_creatures(b"\xff\xfe\x81", encoding="utf-8")

    def test_mapping_flags_valid(self):
        m = load_mapping()
        flags = set(datapack._CR_FLAGS)
        self.assertTrue(all(v is None or v in flags for v in m["ability_flags"].values()))
        bad = dict(m, ability_flags={"x": "teleports"})
        import json, tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            p.write_text(json.dumps(bad))
            with self.assertRaises(ContentError):
                load_mapping(p)

    def test_load_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.txt"
            p.write_bytes(build([row("Zork")]))
            self.assertEqual(load_creatures(p).creatures[0]["name"], "Zork")
        with self.assertRaises(ContentError):
            load_creatures(Path(d) / "missing.txt")


DATA_DIR = os.environ.get("H3_DATA_DIR")


@unittest.skipUnless(DATA_DIR, "H3_DATA_DIR not set; real-game-file tests are optional")
class RealCrtraitsTest(unittest.TestCase):
    def test_every_row_resolves(self):
        found = [p for p in Path(DATA_DIR).rglob("*") if p.name.lower() == "crtraits.txt"]
        if not found:
            self.skipTest("no CRTRAITS.TXT under H3_DATA_DIR")
        try:
            res = load_creatures(found[0])
        except ContentError as e:
            self.fail("CRTRAITS.TXT did not resolve: %s" % str(e)[:120])
        self.assertGreater(len(res.creatures), 0)
        self.assertEqual(len(res.extras), len(res.creatures))
        for c in res.creatures:
            self.assertGreaterEqual(c["hp"], 1)
            self.assertLessEqual(c["dmg_min"], c["dmg_max"])
        # unknown abilities are reported, not fatal; assert only the count is a number
        self.assertGreaterEqual(len(res.unknown), 0)


if __name__ == "__main__":
    unittest.main()
