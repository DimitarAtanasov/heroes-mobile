"""Tests for h3re.roster using synthetic tables only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from h3re.content import ContentResult, parse_creatures  # noqa: E402
from h3re.roster import battle_roster  # noqa: E402
from tests.test_content import build, row  # noqa: E402


def names(roster):
    return [c["name"] for c in roster]


class RosterTests(unittest.TestCase):
    def test_no_fixed_damage_left_out_weak_kept_file_order(self):
        res = parse_creatures(build([
            row("Norm", lo=2, hi=4),
            row("Wisp", lo=0, hi=0),
            row("Weak", lo=0, hi=3)]))
        self.assertEqual(res.no_fixed_damage, frozenset({"Wisp"}))
        self.assertEqual(names(battle_roster(res)), ["Norm", "Weak"])

    def test_roster_entries_are_the_content_creatures(self):
        res = parse_creatures(build([row("Norm"), row("Wisp", lo=0, hi=0)]))
        self.assertEqual(battle_roster(res), [res.creatures[0]])

    def test_empty_content_gives_empty_roster(self):
        # parse_creatures refuses a table with no rows, so build the result directly.
        res = ContentResult(creatures=(), extras={}, unknown=())
        self.assertEqual(battle_roster(res), [])

    def test_only_no_fixed_damage_gives_empty_roster(self):
        res = parse_creatures(build([row("Wisp", lo=0, hi=0)]))
        self.assertEqual(battle_roster(res), [])

    def test_order_equals_file_order(self):
        res = parse_creatures(build([
            row("Zed"), row("Wisp", lo=0, hi=0), row("Alp", lo=0, hi=2), row("Mid")]))
        self.assertEqual(names(battle_roster(res)), ["Zed", "Alp", "Mid"])


if __name__ == "__main__":
    unittest.main()
