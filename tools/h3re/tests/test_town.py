"""Tests for the town core (tools/h3re/h3re/town.py, docs/specs/town.md)."""

import copy
import hashlib
import json
import os
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import adventure as A  # noqa: E402
from h3re import town as T  # noqa: E402
from h3re.datapack import DataPackError  # noqa: E402

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                    "data", "towns_test.json"))
R = A.Resources


def raw():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


CONTENT = T.load_town_pack(DATA)


class NoRng:
    """The town core is not random: any draw is a bug."""

    def __getattr__(self, name):
        raise AssertionError("rng used: %s" % name)


RICH = R(gold=100000, wood=200, ore=200, mercury=20, sulfur=20, crystal=20, gems=20)


def game(towns=None, players=(RICH,), policy=T.DEFAULT_POLICY):
    towns = towns or (T.TownSetup("t1", "faction.fernwood", 0, ("hall.1",)),)
    return T.create_game("g", CONTENT, players, towns, policy)


def build(s, town, bld, player=0):
    return T.apply(s, T.Build(player, town, bld), NoRng())


def build_days(s, town, blds, player=0):
    """Build each building on its own day."""
    for b in blds:
        s, _ = build(s, town, b, player)
        s, _ = T.apply(s, T.NewDay(), NoRng())
    return s


class PackTest(unittest.TestCase):
    def test_test_pack_loads_sorted(self):
        self.assertEqual([f.id for f in CONTENT.factions],
                         ["faction.fernwood", "faction.saltmarsh"])
        ids = [b.id for b in CONTENT.factions[0].buildings]
        self.assertEqual(ids, sorted(ids))
        den = T.find_building(CONTENT, "faction.fernwood", "den.1")
        self.assertEqual((den.dwelling_level, den.creature, den.base_growth), (1, "cr.bramblet", 13))
        self.assertEqual(T.find_building(CONTENT, "faction.fernwood", "keep.2").growth_bonus, (1, 2))
        self.assertEqual(T.find_building(CONTENT, "faction.fernwood", "hall.2").requires,
                         ("hall.1", "market"))

    def test_hash_ignores_formatting(self):
        a = T.parse_town_pack(raw())
        d = raw()
        d["factions"].reverse()
        d["factions"][0]["buildings"].reverse()
        self.assertEqual(T.content_hash(a), T.content_hash(T.parse_town_pack(d)))
        self.assertEqual(T.content_hash(a), T.content_hash(CONTENT))

    def _bad(self, mutate, needle):
        d = raw()
        mutate(d)
        with self.assertRaises(DataPackError) as cm:
            T.parse_town_pack(d)
        self.assertIn(needle, str(cm.exception))

    def _fern(self, d, bid):
        return next(b for b in d["factions"][0]["buildings"] if b["id"] == bid)

    def test_rejects_bad_content(self):
        self._bad(lambda d: self._fern(d, "market")["requires"].append("nope"), "unknown")
        self._bad(lambda d: self._fern(d, "hall.1")["requires"].append("hall.2"), "cycle")
        self._bad(lambda d: self._fern(d, "market").update(colour=1), "unknown key")
        self._bad(lambda d: self._fern(d, "market")["cost"].update(gold=-1), "out of range")
        self._bad(lambda d: self._fern(d, "market")["cost"].update(silver=1), "unknown key")
        self._bad(lambda d: self._fern(d, "den.1").update(requires=[]), "fort")
        self._bad(lambda d: self._fern(d, "den.1u").update(requires=["den.1"], upgrades="market"),
                  "upgrades")
        self._bad(lambda d: self._fern(d, "nest.2")["dwelling"].update(level=1), "level 1")
        self._bad(lambda d: self._fern(d, "keep.2").update(growth_bonus=[1, 0]), "out of range")
        self._bad(lambda d: d["factions"][0]["buildings"].append(
            copy.deepcopy(self._fern(d, "market"))), "duplicate")
        self._bad(lambda d: self._fern(d, "hive")["horde"].update(level=7), "horde")
        self._bad(lambda d: d.update(schema_version=2), "schema_version")

    def test_unique_tag_cannot_deadlock_a_chain(self):
        # hall.4 requires hall.3: both tagged would make hall.4 unbuildable
        self._bad(lambda d: self._fern(d, "hall.3").update(player_unique="capital"),
                  "player_unique")
        self._bad(lambda d: self._fern(d, "hall.2").update(player_unique="capital"),
                  "capital")

    def test_floats_rejected_from_file(self):
        import tempfile
        text = json.dumps(raw()).replace('"base_growth": 13', '"base_growth": 13.0', 1)
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "t.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            with self.assertRaises(DataPackError) as cm:
                T.load_town_pack(p)
        self.assertIn("float", str(cm.exception))


class BuildTest(unittest.TestCase):
    def test_build_pays_cost_and_records(self):
        s = game()
        s2, ev = build(s, "t1", "market")
        self.assertEqual(s2.towns[0].built, ("hall.1", "market"))
        self.assertTrue(s2.towns[0].built_today)
        left = R(gold=99500, wood=195, ore=200, mercury=20, sulfur=20, crystal=20, gems=20)
        self.assertEqual(s2.players[0], left)
        self.assertEqual(ev, (T.BuildingBuilt("t1", "market", 0, R(gold=500, wood=5), left),))

    def test_one_build_per_day(self):
        s, _ = build(game(), "t1", "market")
        with self.assertRaisesRegex(T.IllegalCommand, "already built today"):
            build(s, "t1", "keep.1")
        s, ev = T.apply(s, T.NewDay(), NoRng())
        self.assertEqual(ev, (T.TownDayStarted(2),))
        self.assertFalse(s.towns[0].built_today)
        s, _ = build(s, "t1", "keep.1")
        self.assertEqual(s.towns[0].built, ("hall.1", "keep.1", "market"))

    def test_one_build_per_town_not_per_player(self):
        s = game(towns=(T.TownSetup("t1", "faction.fernwood", 0, ("hall.1",)),
                        T.TownSetup("t2", "faction.saltmarsh", 0, ("hall.1",))))
        s, _ = build(s, "t1", "market")
        s, _ = build(s, "t2", "hall.2")
        self.assertEqual(s.towns[1].built, ("hall.1", "hall.2"))

    def test_prerequisites(self):
        s = game()
        with self.assertRaisesRegex(T.IllegalCommand, "missing hall.2, keep.1"):
            build(s, "t1", "hall.3")
        self.assertEqual(T.missing_requirements(s, "t1", "hall.3"), ("hall.2", "keep.1"))
        with self.assertRaisesRegex(T.IllegalCommand, "missing keep.1"):
            build(s, "t1", "den.1")      # dwellings need a fort [documented]

    def test_resource_check(self):
        s = game(players=(R(gold=4999, wood=20, ore=20),))
        with self.assertRaisesRegex(T.IllegalCommand, "cannot afford"):
            build(s, "t1", "keep.1")
        s = game(players=(R(gold=5000, wood=20, ore=20),))
        s, _ = build(s, "t1", "keep.1")
        self.assertEqual(s.players[0], R())

    def test_other_illegal_commands(self):
        s = game(players=(RICH, RICH))
        for cmd, msg in ((T.Build(1, "t1", "market"), "does not own"),
                         (T.Build(0, "tx", "market"), "no such town"),
                         (T.Build(0, "t1", "nope"), "no such building"),
                         (T.Build(0, "t1", "hall.1"), "already built"),
                         (T.Build(5, "t1", "market"), "no such player"),
                         (object(), "unknown command")):
            with self.subTest(msg=msg):
                canon = T.canonical(s)
                with self.assertRaisesRegex(T.IllegalCommand, msg):
                    T.apply(s, cmd, NoRng())
                self.assertEqual(T.canonical(s), canon)

    def test_player_unique_building(self):
        top = ("hall.1", "market", "hall.2", "keep.1", "hall.3", "keep.2", "keep.3")
        s = game(towns=(T.TownSetup("t1", "faction.fernwood", 0, top),
                        T.TownSetup("t2", "faction.saltmarsh", 0,
                                    ("hall.1", "hall.2", "wall.1", "hall.3", "wall.2", "wall.3")),
                        T.TownSetup("t3", "faction.fernwood", 1, top)),
                 players=(RICH, RICH))
        s, _ = build(s, "t1", "hall.4")
        with self.assertRaisesRegex(T.IllegalCommand, "capital"):
            build(s, "t2", "hall.4")
        s, _ = build(s, "t3", "hall.4", player=1)    # another player may have one
        with self.assertRaisesRegex(ValueError, "capital"):
            game(towns=(T.TownSetup("a", "faction.fernwood", 0, top + ("hall.4",)),
                        T.TownSetup("b", "faction.fernwood", 0, top + ("hall.4",))))

    def _two_capitals(self):
        """A pack where a second, unrelated building carries the capital tag."""
        d = raw()
        d["factions"][0]["buildings"].append(
            {"id": "monument", "cost": {"gold": 1}, "requires": ["hall.1"],
             "player_unique": "capital"})
        return T.parse_town_pack(d)

    def test_unique_tag_holds_inside_one_town(self):
        content = self._two_capitals()
        top = ("hall.1", "market", "hall.2", "keep.1", "hall.3", "keep.2", "keep.3")
        setup = (T.TownSetup("t1", "faction.fernwood", 0, top),)
        for first, second in (("hall.4", "monument"), ("monument", "hall.4")):
            with self.subTest(first=first):
                s = T.create_game("g", content, (RICH,), (T.TownSetup(
                    "t1", "faction.fernwood", 0, top + (first,)),))
                canon = T.canonical(s)
                with self.assertRaisesRegex(T.IllegalCommand, "capital"):
                    T.apply(s, T.Build(0, "t1", second), NoRng())
                self.assertEqual(T.canonical(s), canon)
        with self.assertRaisesRegex(ValueError, "capital"):
            T.create_game("g", content, (RICH,), (T.TownSetup(
                "t1", "faction.fernwood", 0, top + ("hall.4", "monument")),))
        # an unrelated tag-free building and another player are unaffected
        T.create_game("g", content, (RICH, RICH), (
            T.TownSetup("a", "faction.fernwood", 0, top + ("hall.4",)),
            T.TownSetup("b", "faction.fernwood", 1, top + ("monument",))))
        T.apply(T.create_game("g", content, (RICH,), setup), T.Build(0, "t1", "monument"),
                NoRng())

    def test_create_game_rejects_non_int_inputs(self):
        def make(players=(RICH,), towns=None):
            return T.create_game("g", CONTENT, players, towns or (
                T.TownSetup("t1", "faction.fernwood", 0, ("hall.1",)),))

        ok = {n: 1 for n in A.RESOURCE_NAMES}
        for bad in (1.0, True, False, "1", None, 2 ** 31):
            for name in A.RESOURCE_NAMES:
                with self.subTest(field=name, value=bad):
                    with self.assertRaisesRegex(ValueError, "resources"):
                        make(players=(R(**dict(ok, **{name: bad})),))
        # float 0.0 and bool False compare equal to 0 but must not enter canonical()
        with self.assertRaises(ValueError):
            make(players=(R(gold=0.0),))
        with self.assertRaises(ValueError):
            make(players=(R(gold=False),))
        for players in ((), [], ((1, 2, 3, 4, 5, 6, 7),), (object(),), (None,)):
            with self.subTest(players=players), self.assertRaises(ValueError):
                make(players=players)
        # int subclasses are not ints either
        class MyInt(int):
            pass
        with self.assertRaises(ValueError):
            make(players=(R(gold=MyInt(5)),))
        make(players=(R(gold=2 ** 31 - 1),))               # the cap is allowed

        for owner in (0.0, False, True, "0", None):
            with self.subTest(owner=owner), self.assertRaisesRegex(ValueError, "owner"):
                make(towns=(T.TownSetup("t1", "faction.fernwood", owner, ()),))
        for setup in (T.TownSetup(1, "faction.fernwood", 0, ()),
                      T.TownSetup("t1", 5, 0, ()),
                      T.TownSetup("t1", "faction.fernwood", 0, "hall.1"),
                      T.TownSetup("t1", "faction.fernwood", 0, ("hall.1", 5)),
                      ("t1", "faction.fernwood", 0, ()), None):
            with self.subTest(setup=setup), self.assertRaises(ValueError):
                make(towns=(setup,))
        with self.assertRaises(ValueError):
            make(towns=T.TownSetup("t1", "faction.fernwood", 0, ()))   # not a sequence

    def test_state_holds_only_plain_ints(self):
        s = game()
        self.assertTrue(all(type(getattr(p, n)) is int for p in s.players
                            for n in A.RESOURCE_NAMES))
        self.assertIs(type(s.towns[0].owner), int)

    def test_create_validates(self):
        for towns, msg in (
                ((T.TownSetup("t", "faction.none", 0, ()),), "faction"),
                ((T.TownSetup("t", "faction.fernwood", 3, ()),), "owner"),
                ((T.TownSetup("t", "faction.fernwood", 0, ("market",)),), "requires"),
                ((T.TownSetup("t", "faction.fernwood", 0, ("zzz",)),), "unknown"),
                ((T.TownSetup("t", "faction.fernwood", 0, ()),
                  T.TownSetup("t", "faction.fernwood", 0, ())), "duplicate")):
            with self.subTest(msg=msg), self.assertRaisesRegex(ValueError, msg):
                game(towns=towns)
        with self.assertRaisesRegex(ValueError, "resources"):
            game(players=(R(gold=-1),))

    def test_built_is_sorted_whatever_the_setup_order(self):
        a = game(towns=(T.TownSetup("t1", "faction.fernwood", 0, ("market", "hall.1")),))
        b = game(towns=(T.TownSetup("t1", "faction.fernwood", 0, ("hall.1", "market")),))
        self.assertEqual(T.state_hash(a), T.state_hash(b))
        self.assertEqual(a.towns[0].built, ("hall.1", "market"))


class IncomeTest(unittest.TestCase):
    def test_upgrade_supersedes_income(self):
        s = game()
        self.assertEqual(T.town_income(s, "t1"), R(gold=500))
        s = build_days(s, "t1", ["market", "hall.2"])
        self.assertEqual(T.active_buildings(s, "t1"), ("hall.2", "market"))
        self.assertEqual(T.town_income(s, "t1"), R(gold=1000))

    def test_player_income_sums_owned_towns(self):
        s = game(towns=(T.TownSetup("t1", "faction.fernwood", 0, ("hall.1",)),
                        T.TownSetup("t2", "faction.saltmarsh", 0, ("hall.1", "hall.2")),
                        T.TownSetup("t3", "faction.saltmarsh", 1, ("hall.1",))),
                 players=(RICH, RICH))
        self.assertEqual(T.player_income(s, 0), R(gold=1500))
        self.assertEqual(T.player_income(s, 1), R(gold=500))


FULL = ("hall.1", "keep.1", "den.1", "nest.2", "grove.3")


class GrowthTest(unittest.TestCase):
    def pools(self, built, policy=T.DEFAULT_POLICY, current=()):
        s = game(towns=(T.TownSetup("t1", "faction.fernwood", 0, built),), policy=policy)
        return T.growth_pools(s, "t1", current)

    def test_formula(self):
        # growth = base + round(base * castle_bonus) + horde   (rules.md 4)
        self.assertEqual(T.weekly_growth(13, (0, 1), 0), 13)
        self.assertEqual(T.weekly_growth(13, (1, 2), 0), 19)       # floor(6.5) = 6
        self.assertEqual(T.weekly_growth(13, (1, 1), 4), 30)
        self.assertEqual(T.weekly_growth(7, (1, 2), 0, T.TownPolicy("ceil")), 11)
        self.assertEqual(T.weekly_growth(7, (1, 2), 0, T.TownPolicy("nearest")), 11)
        self.assertEqual(T.weekly_growth(8, (1, 2), 0, T.TownPolicy("ceil")), 12)

    def test_pools_shape_and_values(self):
        p = self.pools(FULL)
        self.assertTrue(all(type(x) is A.GrowthPool for x in p))
        self.assertEqual(p, (A.GrowthPool("t1:dwelling1", 0, 13),
                             A.GrowthPool("t1:dwelling2", 0, 7),
                             A.GrowthPool("t1:dwelling3", 0, 5)))

    def test_citadel_rounding_policy(self):
        built = FULL + ("keep.2",)
        want = {"floor": (19, 10, 7), "ceil": (20, 11, 8), "nearest": (20, 11, 8)}
        for mode, growth in want.items():
            with self.subTest(mode=mode):
                got = tuple(x.growth for x in self.pools(built, T.TownPolicy(mode)))
                self.assertEqual(got, growth)

    def test_castle_not_cumulative_and_horde(self):
        built = FULL + ("keep.2", "keep.3", "hive")
        self.assertEqual(tuple(x.growth for x in self.pools(built)), (13 + 13 + 4, 14, 10))

    def test_upgraded_dwelling_shares_the_level_pool(self):
        p = self.pools(FULL + ("market", "den.1u"))
        self.assertEqual(p[0], A.GrowthPool("t1:dwelling1", 0, 13))
        self.assertEqual(len(p), 3)
        self.assertEqual(T.dwellings(game(towns=(T.TownSetup(
            "t1", "faction.fernwood", 0, FULL + ("market", "den.1u")),)), "t1")[0],
            (1, "cr.bramblet_elder", 13))

    def test_horde_without_dwelling_adds_no_pool(self):
        self.assertEqual(self.pools(("hall.1", "keep.1")), ())

    def test_available_carries_over(self):
        cur = (A.GrowthPool("t1:dwelling2", 9, 99), A.GrowthPool("other", 4, 1))
        p = self.pools(FULL, current=cur)
        self.assertEqual([x.available for x in p], [0, 9, 0])

    def test_pools_feed_the_adventure_week(self):
        s = game(towns=(T.TownSetup("t1", "faction.fernwood", 0, FULL + ("keep.2",)),))
        pools = T.growth_pools(s, "t1")
        g = A.Grid(2, 1, (A.Tile("grass"), A.Tile("grass")))
        adv = A.create_game("a", g, (A.Player(),),
                            (A.HeroSetup(0, (0, 0), (A.ArmySlot("c", 5, 1),)),), pools)
        adv, _ = A.apply(adv, A.Begin(), NoRng())
        for _ in range(7):
            adv, _ = A.apply(adv, A.EndTurn(0), NoRng())
        self.assertEqual(adv.day, 8)
        self.assertEqual([p.available for p in adv.pools], [19, 10, 7])


GOLDEN_TOWNS = (T.TownSetup("north", "faction.fernwood", 0, ("hall.1",)),
                T.TownSetup("south", "faction.saltmarsh", 1, ("hall.1",)),
                T.TownSetup("east", "faction.fernwood", 1, ("hall.1", "keep.1")))
GOLDEN_PLAYERS = (R(gold=30000, wood=60, ore=60, mercury=4, gems=2),
                  R(gold=25000, wood=20, ore=50, mercury=2, sulfur=5))
# One entry per day: (player, town, building) builds, in order, then NewDay.
GOLDEN_SCRIPT = (
    ((0, "north", "keep.1"), (1, "south", "wall.1"), (1, "east", "den.1")),
    ((0, "north", "den.1"), (1, "south", "pool.1"), (1, "east", "nest.2")),
    ((0, "north", "market"), (1, "south", "hall.2"), (1, "east", "hive")),
    ((0, "north", "keep.2"), (1, "south", "reef.2"), (1, "east", "market")),
    ((0, "north", "hive"), (1, "south", "wall.2")),
    ((0, "north", "nest.2"), (1, "east", "den.1u")),
    ((0, "north", "hall.2"),),
)


def golden_run(policy=T.DEFAULT_POLICY):
    s = T.create_game("golden", CONTENT, GOLDEN_PLAYERS, GOLDEN_TOWNS, policy)
    trace = []
    for day in GOLDEN_SCRIPT:
        for p, t, b in day:
            s, ev = T.apply(s, T.Build(p, t, b), NoRng())
            trace.append(ev)
        s, ev = T.apply(s, T.NewDay(), NoRng())
        trace.append(ev)
    pools = tuple(p for t in s.towns for p in T.growth_pools(s, t.id))
    return s, trace, pools


GROWTH_MODES = ("floor", "ceil", "nearest")


def growth_digest(modes=GROWTH_MODES):
    """SHA-256 of the canonical JSON of the golden run's growth pools under each
    citadel_rounding mode (town.md section 7): [[mode, [[id, available, growth], ...]], ...]."""
    out = []
    for mode in GROWTH_MODES:
        _, _, pools = golden_run(T.TownPolicy(citadel_rounding=modes[GROWTH_MODES.index(mode)]))
        out.append([mode, [[p.id, p.available, p.growth] for p in pools]])
    text = json.dumps(out, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GoldenTest(unittest.TestCase):
    # Second pin: growth pools under all three rounding modes (town.md section 7).
    GROWTH_PINNED = "b4108c58f2e6e95cbaa19fbfb7694e66a74067558840c614cbffc71c96549322"
    # First pin of the town core (not a re-pin). Derivation: docs/specs/town.md
    # section 7. Covers content (data/towns_test.json), policy and state.
    PINNED = "0360ce8861ca3b4a12f8210f0d8111b57c328becb8c433d41c59d6a6d257aae7"
    CONTENT_HASH = "629836f9f419a851"   # prefix of content_hash(data/towns_test.json)

    def test_content_hash_prefix(self):
        # if this moves, the test pack changed: that moves PINNED too
        self.assertEqual(T.content_hash(CONTENT)[:16], self.CONTENT_HASH)

    def test_golden_hash(self):
        s, _, pools = golden_run()
        self.assertEqual(s.day, 8)
        self.assertEqual(s.players, (
            R(gold=30000 - 5000 - 400 - 500 - 2500 - 1000 - 1000 - 2500,
              wood=60 - 20 - 5 - 5, ore=60 - 20 - 5 - 5, mercury=2, gems=2),
            R(gold=25000 - 5000 - 400 - 300 - 1000 - 2500 - 1000 - 800 - 500 - 2500 - 900,
              wood=20 - 5 - 5 - 5, ore=50 - 20 - 5 - 3 - 5, sulfur=5)))
        self.assertEqual(pools, (
            A.GrowthPool("north:dwelling1", 0, 13 + 6 + 4),
            A.GrowthPool("north:dwelling2", 0, 7 + 3),
            A.GrowthPool("south:dwelling1", 0, 9 + 4),
            A.GrowthPool("south:dwelling2", 0, 6 + 3),
            A.GrowthPool("east:dwelling1", 0, 13 + 4),
            A.GrowthPool("east:dwelling2", 0, 7)))
        self.assertEqual(T.state_hash(s), self.PINNED)

    def test_growth_pools_digest(self):
        # Second pin (first pin of this digest, not a re-pin): docs/specs/town.md
        # section 7. It covers the rounding modes and horde handling, which the
        # state hash does not (growth is a query, not state).
        self.assertEqual(growth_digest(), self.GROWTH_PINNED)

    def test_growth_digest_reacts_to_rounding_and_horde_mistakes(self):
        base = growth_digest()
        # a wrong rounding mode changes it
        self.assertNotEqual(growth_digest(modes=("ceil", "ceil", "nearest")), base)
        self.assertNotEqual(growth_digest(modes=("floor", "floor", "floor")), base)
        # scaling the horde by the castle bonus (a plausible mistake) changes it
        real = T.weekly_growth

        def scaled(base_growth, bonus, horde, policy=T.DEFAULT_POLICY):
            return (real(base_growth, bonus, 0, policy)
                    + T._round_castle_bonus(horde, T.Fraction(*bonus), policy.citadel_rounding)
                    + horde)
        T.weekly_growth = scaled
        try:
            self.assertNotEqual(growth_digest(), base)
        finally:
            T.weekly_growth = real
        self.assertEqual(growth_digest(), base)

    def test_replay_is_deterministic(self):
        a, ta, pa = golden_run()
        b, tb, pb = golden_run()
        self.assertEqual(T.canonical(a), T.canonical(b))
        self.assertEqual((ta, pa), (tb, pb))

    def test_policy_is_in_the_hash_and_changes_growth(self):
        a, _, pa = golden_run()
        b, _, pb = golden_run(T.TownPolicy(citadel_rounding="ceil"))
        self.assertNotEqual(T.state_hash(a), T.state_hash(b))
        self.assertNotEqual(pa, pb)

    def test_content_is_in_the_hash(self):
        d = raw()
        d["factions"][0]["buildings"][0]["income"]["gold"] = 501
        s = T.create_game("golden", T.parse_town_pack(d), GOLDEN_PLAYERS, GOLDEN_TOWNS)
        self.assertNotEqual(T.state_hash(s), T.state_hash(
            T.create_game("golden", CONTENT, GOLDEN_PLAYERS, GOLDEN_TOWNS)))

    def test_stream_name(self):
        from h3re.rng import derive_stream
        a, b = T.town_rng(7, "x"), derive_stream(7, "town:x")
        self.assertEqual([a.next_u32() for _ in range(3)], [b.next_u32() for _ in range(3)])

    def test_state_is_immutable(self):
        s = game()
        with self.assertRaises(Exception):
            s.day = 3
        with self.assertRaises(Exception):
            s.towns[0].built_today = True


if __name__ == "__main__":
    unittest.main()
