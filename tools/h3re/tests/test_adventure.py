import os
import random
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import adventure as A  # noqa: E402

_TERR = {"d": "dirt", "g": "grass", "l": "lava", "u": "subterranean",
         "r": "rough", "s": "sand", "n": "snow", "w": "swamp",
         "~": "water", "#": "rock"}
_ROAD = {".": "none", "1": "dirt", "2": "gravel", "3": "cobblestone"}


def grid(terrain, roads=None, blocked=()):
    """Grid from text rows; ``roads`` rows use . 1 2 3; ``blocked`` = tiles."""
    h, w = len(terrain), len(terrain[0])
    roads = roads or ["." * w] * h
    tiles = []
    for y in range(h):
        for x in range(w):
            tiles.append(A.Tile(_TERR[terrain[y][x]], _ROAD[roads[y][x]],
                                (x, y) in blocked))
    return A.Grid(w, h, tuple(tiles))


def army(*speeds):
    return tuple(A.ArmySlot("c%d" % i, s, 10) for i, s in enumerate(speeds))


def game(g, heroes=None, players=None, pools=(), policy=A.DEFAULT_POLICY):
    players = players or (A.Player(),)
    heroes = heroes or (A.HeroSetup(0, (0, 0), army(5)),)
    return A.create_game("t", g, players, heroes, pools, policy)


def started(*a, **kw):
    s, _ = A.apply(game(*a, **kw), A.Begin(), NoRng())
    return s


class NoRng:
    """The adventure core must not draw randomness yet."""

    def __getattr__(self, name):
        raise AssertionError("rng used: %s" % name)


class MovementPointsTest(unittest.TestCase):
    def test_speed_table(self):
        table = {1: 1500, 3: 1500, 4: 1560, 5: 1630, 6: 1700, 7: 1760,
                 8: 1830, 9: 1900, 10: 1960, 11: 2000, 20: 2000}
        for spd, mp in table.items():
            self.assertEqual(A.base_movement(army(spd)), mp, spd)

    def test_slowest_stack_counts(self):
        self.assertEqual(A.base_movement(army(11, 4, 9)), 1560)

    def test_logistics(self):
        h = A.Hero(0, 0, (0, 0), army(5), 1, 0, 0, 0, False)
        self.assertEqual([A.max_movement(replace(h, logistics=lv)) for lv in range(4)],
                         [1630, 1793, 1956, 2119])
        self.assertEqual(A.max_movement(replace(h, army=army(4), logistics=1)), 1716)
        self.assertEqual(A.max_movement(replace(h, army=army(12), logistics=3)), 2600)

    def test_movement_reset_daily_no_carry_over(self):
        s = started(grid(["ggg"]))
        self.assertEqual(s.heroes[0].mp, 1630)
        s, _ = A.apply(s, A.Move(0, (1, 0)), NoRng())
        self.assertEqual(s.heroes[0].mp, 1530)
        s, ev = A.apply(s, A.EndTurn(0), NoRng())
        self.assertEqual(s.heroes[0].mp, 1630)
        self.assertIn(A.MovementReset(0, 1630), ev)


class StepCostTest(unittest.TestCase):
    def test_terrain_costs(self):
        # the SOURCE tile prices the step (VCMI cross-check)
        for code, cost in (("d", 100), ("g", 100), ("l", 100), ("u", 100),
                           ("r", 125), ("s", 150), ("n", 150), ("w", 175)):
            g = grid([code + "g"])
            self.assertEqual(A.step_cost(g, (0, 0), (1, 0)), cost, code)
            self.assertEqual(A.find_path(game(g), 0, (1, 0)), (cost, ((0, 0), (1, 0))))
        self.assertEqual(A.step_cost(grid(["gw"]), (0, 0), (1, 0)), 100)

    def test_roads(self):
        g = grid(["sss"], ["111"])
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0)), 75)
        self.assertEqual(A.find_path(game(g), 0, (2, 0))[0], 150)
        for r, cost in (("2", 65), ("3", 50)):
            self.assertEqual(A.step_cost(grid(["ss"], [r + r]), (0, 0), (1, 0)), cost)
        # a road on one tile only gives no discount
        self.assertEqual(A.step_cost(grid(["ss"], [".3"]), (0, 0), (1, 0)), 150)
        self.assertEqual(A.step_cost(grid(["ss"], ["3."]), (0, 0), (1, 0)), 150)

    def test_impassable(self):
        g = grid(["g~#g"], blocked={(3, 0)})
        self.assertIsNone(A.step_cost(g, (0, 0), (1, 0)))
        self.assertIsNone(A.find_path(game(g), 0, (2, 0)))
        self.assertIsNone(A.find_path(game(g), 0, (3, 0)))

    def test_diagonal_cost(self):
        g = grid(["wg", "gg"])
        self.assertEqual(A.step_cost(g, (0, 0), (1, 1)), 247)   # floor(175*sqrt2)
        self.assertEqual(A.step_cost(g, (1, 0), (0, 1)), 141)
        for code, want in (("g", 141), ("r", 176), ("s", 212), ("w", 247)):
            self.assertEqual(A.step_cost(grid([code + "g", "gg"]), (0, 0), (1, 1)), want)
        for r, want in (("1", 106), ("2", 91), ("3", 70)):
            self.assertEqual(A.step_cost(grid(["gg", "gg"], [r * 2] * 2), (0, 0), (1, 1)), want)

    def test_sqrt2_is_exact_floor(self):
        for c in range(1, 5000):
            d = A._diagonal(c, A.DEFAULT_POLICY)
            self.assertTrue(d * d <= 2 * c * c < (d + 1) * (d + 1))

    def test_pathfinding_is_flat_with_floor(self):
        def costs(code):
            g = grid([code + "g", "gg"])
            return [A.step_cost(g, (0, 0), (1, 0), pf) for pf in range(4)]
        self.assertEqual(costs("w"), [175, 150, 125, 100])
        self.assertEqual(costs("s"), [150, 125, 100, 100])
        self.assertEqual(costs("r"), [125, 100, 100, 100])
        self.assertEqual(costs("g"), [100, 100, 100, 100])
        # applied before the diagonal factor
        g = grid(["wg", "gg"])
        self.assertEqual(A.step_cost(g, (0, 0), (1, 1), 3), 141)
        self.assertEqual(A.step_cost(g, (0, 0), (1, 1), 1), 212)
        # roads are not affected
        self.assertEqual(A.step_cost(grid(["ww"], ["11"]), (0, 0), (1, 0), 3), 75)

    def test_path_prefers_road_detour(self):
        g = grid(["gsssg", "ggggg"], ["3...3", "33333"])
        cost, path = A.find_path(game(g), 0, (4, 0))
        # straight over sand: 100 + 3*150 = 550; diagonal onto the road row and
        # back: 70 + 2*50 + 70 = 240
        self.assertEqual(cost, 70 + 50 * 2 + 70)
        self.assertEqual(path, ((0, 0), (1, 1), (2, 1), (3, 1), (4, 0)))

    def test_deterministic_tie_break(self):
        g = grid(["ggg", "ggg", "ggg"])
        p = A.DEFAULT_POLICY
        pol = replace(p, diagonal_moves=False)
        cost, path = A.find_path(game(g, policy=pol), 0, (1, 1))
        self.assertEqual(cost, 200)
        # two equal paths (via (1,0) or (0,1)): the lexicographically smaller wins
        self.assertEqual(path, ((0, 0), (0, 1), (1, 1)))

    def test_other_heroes_block(self):
        g = grid(["ggg"])
        heroes = (A.HeroSetup(0, (0, 0), army(5)), A.HeroSetup(0, (1, 0), army(5)))
        s = started(g, heroes=heroes)
        self.assertIsNone(A.find_path(s, 0, (2, 0)))


class PolicyTest(unittest.TestCase):
    def test_road_cost_table(self):
        g = grid(["gggg"], ["1233"])
        self.assertEqual([A.step_cost(g, (i, 0), (i + 1, 0)) for i in range(3)],
                         [75, 65, 50])
        pol = replace(A.DEFAULT_POLICY,
                      road_cost=(("cobblestone", 50), ("dirt", 50), ("gravel", 50)))
        self.assertEqual([A.step_cost(g, (i, 0), (i + 1, 0), policy=pol) for i in range(3)],
                         [50, 50, 50])

    def test_road_needs_both(self):
        g = grid(["ss"], [".1"])
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0)), 150)
        pol = replace(A.DEFAULT_POLICY, road_needs_both=False)
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0), policy=pol), 75)

    def test_road_rate_from(self):
        g = grid(["ss"], ["13"])
        rates = []
        for mode in ("source", "dest", "max"):
            pol = replace(A.DEFAULT_POLICY, road_rate_from=mode)
            rates.append(A.step_cost(g, (0, 0), (1, 0), policy=pol))
        self.assertEqual(rates, [75, 50, 75])

    def test_cost_from_dest(self):
        g = grid(["wg"])
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0)), 175)
        pol = replace(A.DEFAULT_POLICY, cost_from="dest")
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0), policy=pol), 100)

    def test_diagonal_ratio_mode(self):
        g = grid(["gg", "gg"])
        for num, den, mode, want in ((141, 100, "floor", 141), (142, 100, "floor", 142),
                                     (1414, 1000, "ceil", 142), (1414, 1000, "nearest", 141)):
            pol = replace(A.DEFAULT_POLICY, diagonal_mode="ratio", diagonal_num=num,
                          diagonal_den=den, diagonal_rounding=mode)
            self.assertEqual(A.step_cost(g, (0, 0), (1, 1), policy=pol), want)
        g2 = grid(["rg", "gg"])
        old = replace(A.DEFAULT_POLICY, diagonal_mode="ratio")
        ceil = replace(old, diagonal_rounding="ceil")
        self.assertEqual(A.step_cost(g2, (0, 0), (1, 1), policy=old), 176)    # 176.25
        self.assertEqual(A.step_cost(g2, (0, 0), (1, 1), policy=ceil), 177)
        g3 = grid(["wg", "gg"])           # ratio 141/100 gives 246, sqrt2 gives 247
        self.assertEqual(A.step_cost(g3, (0, 0), (1, 1), policy=old), 246)

    def test_no_diagonals(self):
        g = grid(["gg", "gg"])
        pol = replace(A.DEFAULT_POLICY, diagonal_moves=False)
        self.assertIsNone(A.step_cost(g, (0, 0), (1, 1), policy=pol))
        self.assertEqual(A.find_path(game(g, policy=pol), 0, (1, 1))[0], 200)
        self.assertEqual(A.find_path(game(g), 0, (1, 1))[0], 141)

    def test_corner_cut(self):
        g = grid(["g#", "#g"])
        self.assertEqual(A.find_path(game(g), 0, (1, 1))[0], 141)
        pol = replace(A.DEFAULT_POLICY, diagonal_corner_cut=False)
        self.assertIsNone(A.find_path(game(g, policy=pol), 0, (1, 1)))

    def test_last_step(self):
        # speed 5 -> 1630 points; sand costs 150 per step (source tile).
        g = grid(["s" * 14])
        far = (11, 0)
        D = A.DEFAULT_POLICY
        raw = replace(D, zero_remainder=False)
        base = started(g, policy=raw)
        r = A.reachable(base, 0)
        self.assertEqual(r[(10, 0)][0], 1500)
        self.assertNotIn(far, r)               # 130 left < 150: step refused

        # zero remainder: the 10th step leaves 130 < 150, so it takes all 280
        z = started(g)
        r = A.reachable(z, 0)
        self.assertEqual(r[(9, 0)][0], 1350)
        self.assertEqual(r[(10, 0)][0], 1630)
        self.assertNotIn(far, r)
        s, ev = A.apply(z, A.Move(0, (10, 0)), NoRng())
        self.assertEqual(s.heroes[0].mp, 0)
        self.assertEqual(ev[-1].mp_left, 0)

        anyp = started(g, policy=replace(raw, last_step="allow_if_any"))
        self.assertEqual(A.reachable(anyp, 0)[far][0], 1630)   # takes the 130 left
        with self.assertRaises(A.IllegalCommand):
            A.apply(base, A.Move(0, far), NoRng())

        fresh = started(g, policy=replace(raw, last_step="allow_if_fresh"))
        self.assertNotIn(far, A.reachable(fresh, 0))
        # a hero that has not moved today may always take one step
        poor = grid(["w" * 20])
        heroes = (A.HeroSetup(0, (0, 0), army(5)),)
        f2 = started(poor, heroes=heroes,
                     policy=replace(raw, last_step="allow_if_fresh"))
        f2 = replace(f2, heroes=(replace(f2.heroes[0], mp=100),))
        self.assertEqual(A.reachable(f2, 0)[(1, 0)][0], 100)
        moved = replace(f2, heroes=(replace(f2.heroes[0], moved_today=True),))
        self.assertEqual(A.reachable(moved, 0), {})

    def test_diagonal_exception(self):
        g = grid(["ss", "ss"])            # orthogonal 150, diagonal 212
        raw = replace(A.DEFAULT_POLICY, zero_remainder=False)
        for exc, want in ((True, {(1, 0): 150, (0, 1): 150, (1, 1): 200}),
                          (False, {(1, 0): 150, (0, 1): 150})):
            s = started(g, policy=replace(raw, diagonal_exception=exc))
            s = replace(s, heroes=(replace(s.heroes[0], mp=200),))
            self.assertEqual({t: c for t, (c, _) in A.reachable(s, 0).items()}, want)
        # 140 left does not cover the orthogonal cost of 150: no exception
        s = started(g, policy=raw)
        s = replace(s, heroes=(replace(s.heroes[0], mp=140),))
        self.assertEqual(A.reachable(s, 0), {})

    def test_pathfinding_percent_mode(self):
        g = grid(["rg"])
        pct = replace(A.DEFAULT_POLICY, pathfinding_mode="percent")
        ceil = replace(pct, pathfinding_rounding="ceil")
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0), 1, pct), 119)   # cut 6.25 -> 6
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0), 1, ceil), 118)
        w = grid(["wg"])
        self.assertEqual([A.step_cost(w, (0, 0), (1, 0), pf, pct) for pf in range(4)],
                         [175, 157, 138, 119])
        nopf = replace(pct, pathfinding_pct=(0, 0, 0, 0))
        self.assertEqual(A.step_cost(g, (0, 0), (1, 0), 3, nopf), 125)
        flat0 = replace(A.DEFAULT_POLICY, pathfinding_flat=(0, 0, 0, 0))
        self.assertEqual(A.step_cost(w, (0, 0), (1, 0), 3, flat0), 175)

    def test_income_on_first_day(self):
        players = (A.Player(mines=("gold_mine",)),)
        s = started(grid(["g"]), players=players)
        self.assertEqual(s.players[0].resources, A.Resources())
        pol = replace(A.DEFAULT_POLICY, income_on_first_day=True)
        s = started(grid(["g"]), players=players, policy=pol)
        self.assertEqual(s.players[0].resources, A.Resources(gold=1000))

    def test_bad_policy_rejected(self):
        for kw in ({"cost_from": "x"}, {"last_step": "x"}, {"diagonal_rounding": "x"},
                   {"diagonal_den": 0}, {"pathfinding_pct": (0, 1)},
                   {"road_rate_from": "x"}, {"diagonal_mode": "x"},
                   {"pathfinding_mode": "x"}, {"pathfinding_flat": (0, 1)},
                   {"move_cost_floor": 0},
                   {"road_cost": (("dirt", 50),)}):
            with self.assertRaises(ValueError):
                A.AdventurePolicy(**kw)


class RoadCostCanonicalTest(unittest.TestCase):
    def test_order_is_normalised_so_hash_is_stable(self):
        a = A.AdventurePolicy(road_cost=(("cobblestone", 50), ("dirt", 75), ("gravel", 65)))
        b = A.AdventurePolicy(road_cost=(("gravel", 65), ("cobblestone", 50), ("dirt", 75)))
        c = A.AdventurePolicy(road_cost=[["dirt", 75], ["gravel", 65], ["cobblestone", 50]])
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(b.road_cost, tuple(sorted(b.road_cost)))
        self.assertEqual(a, A.DEFAULT_POLICY)
        sa = started(grid(["g"]), policy=a)
        sb = started(grid(["g"]), policy=b)
        self.assertEqual(A.state_hash(sa), A.state_hash(sb))

    def test_duplicate_road_rejected(self):
        for cost in (
                (("cobblestone", 50), ("dirt", 75), ("gravel", 65), ("dirt", 10)),
                (("cobblestone", 50), ("dirt", 75), ("dirt", 75)),
                (("cobblestone", 50), ("cobblestone", 50), ("dirt", 75), ("gravel", 65))):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                A.AdventurePolicy(road_cost=cost)

    def test_malformed_entries_rejected(self):
        for cost in ((("cobblestone", 50), ("dirt", 75), ("gravel", 65, 1)),
                     (("cobblestone", 50), ("dirt", 75), ("gravel", 0)),
                     (("cobblestone", 50), ("dirt", 75), ("gravel", "65")),
                     (("cobblestone", 50), ("dirt", 75), ("mud", 65))):
            with self.assertRaises(ValueError, msg=cost):
                A.AdventurePolicy(road_cost=cost)

    def test_different_costs_still_change_the_hash(self):
        other = A.AdventurePolicy(road_cost=(("dirt", 50), ("gravel", 65), ("cobblestone", 50)))
        self.assertNotEqual(A.state_hash(started(grid(["g"]), policy=other)),
                            A.state_hash(started(grid(["g"]))))


class TickTest(unittest.TestCase):
    def setUp(self):
        self.players = (
            A.Player(A.Resources(gold=500), ("gold_mine", "sawmill", "gem_pond"),
                     A.Resources(gold=500)),
            A.Player(mines=("ore_pit",)),
        )
        heroes = (A.HeroSetup(0, (0, 0), army(5)), A.HeroSetup(1, (2, 0), army(9)))
        self.pools = (A.GrowthPool("castle.pikeman", 14, 14), A.GrowthPool("map.dw", 0, 3))
        self.s = started(grid(["ggg"]), heroes=heroes, players=self.players, pools=self.pools)

    def end_day(self, s):
        evs = []
        for p in range(len(s.players)):
            s, ev = A.apply(s, A.EndTurn(p), NoRng())
            evs.extend(ev)
        return s, evs

    def test_daily_income(self):
        self.assertEqual(A.daily_income(self.players[0]),
                         A.Resources(gold=1500, wood=2, gems=1))
        s, ev = self.end_day(self.s)
        self.assertEqual(s.day, 2)
        self.assertEqual(s.players[0].resources, A.Resources(gold=2000, wood=2, gems=1))
        self.assertEqual(s.players[1].resources, A.Resources())   # not its turn yet
        s, ev = A.apply(s, A.EndTurn(0), NoRng())
        self.assertEqual(s.players[1].resources, A.Resources(ore=2))
        self.assertEqual(ev, (A.TurnEnded(0), A.TurnStarted(1, 2),
                              A.IncomeReceived(1, A.Resources(ore=2)),
                              A.MovementReset(1, 1900)))

    def test_week_rollover(self):
        s = self.s
        grew = []
        for _ in range(28):
            s, ev = self.end_day(s)
            grew.extend(e for e in ev if isinstance(e, (A.WeekStarted, A.PoolGrew)))
        self.assertEqual(s.day, 29)
        self.assertEqual(A.calendar(29), (5, 1, 2))
        weeks = [e for e in grew if isinstance(e, A.WeekStarted)]
        self.assertEqual([(w.week, w.month, w.new_month) for w in weeks],
                         [(2, 1, False), (3, 1, False), (4, 1, False), (5, 2, True)])
        self.assertEqual(s.pools, (A.GrowthPool("castle.pikeman", 14 + 4 * 14, 14),
                                   A.GrowthPool("map.dw", 12, 3)))
        # week 2 starts on day 8, before player 0's turn
        s7 = self.s
        for _ in range(6):
            s7, _ = self.end_day(s7)
        self.assertEqual(s7.day, 7)
        s8, ev = self.end_day(s7)
        tail = tuple(ev[ev.index(A.TurnEnded(1)) + 1:])
        self.assertEqual(tail[:5], (A.DayStarted(8, 2, 1, 1), A.WeekStarted(2, 1, False),
                                    A.PoolGrew("castle.pikeman", 14, 28),
                                    A.PoolGrew("map.dw", 3, 3), A.TurnStarted(0, 8)))
        self.assertEqual(s8.players[0].resources.gold, 500 + 7 * 1500)

    def test_turn_order_enforced(self):
        with self.assertRaises(A.IllegalCommand):
            A.apply(self.s, A.EndTurn(1), NoRng())
        with self.assertRaises(A.IllegalCommand):
            A.apply(self.s, A.Move(1, (1, 0)), NoRng())
        with self.assertRaises(A.IllegalCommand):
            A.apply(self.s, A.Begin(), NoRng())
        with self.assertRaises(A.IllegalCommand):
            A.apply(game(grid(["g"])), A.EndTurn(0), NoRng())


GOLDEN_TERRAIN = [
    "gggrrsssnnww~~gg",
    "gdddrrsssnnw~ggg",
    "ggud#rrssnnww~gg",
    "llud#rrsssnnwwgg",
    "lluu#rrsssnnwwwg",
    "gggggggggggggggg",
    "wwwwssssrrrrdddd",
    "gggggggggggggggg",
]
GOLDEN_ROADS = [
    "1111............",
    "...1............",
    "...1............",
    "...222222222....",
    "...........2....",
    "...........33333",
    "................",
    "................",
]


def golden_setup(policy=A.DEFAULT_POLICY):
    g = grid(GOLDEN_TERRAIN, GOLDEN_ROADS, blocked={(9, 7), (10, 6)})
    players = (
        A.Player(A.Resources(gold=7500, wood=10, ore=10), ("gold_mine", "sawmill"),
                 A.Resources(gold=500)),
        A.Player(A.Resources(gold=5000), ("ore_pit", "crystal_cavern")),
    )
    heroes = (
        A.HeroSetup(0, (0, 0), army(4, 6), logistics=1),
        A.HeroSetup(0, (0, 7), army(7), pathfinding=2),
        A.HeroSetup(1, (15, 5), army(5, 11), logistics=3, pathfinding=1),
    )
    pools = (A.GrowthPool("a", 10, 10), A.GrowthPool("b", 0, 2))
    return A.create_game("golden", g, players, heroes, pools, policy)


WAYPOINTS = {0: ((15, 7), (2, 3), (14, 1), (0, 0)),
             1: ((15, 0), (8, 6), (1, 2), (0, 7)),
             2: ((0, 4), (11, 0), (6, 7), (15, 5))}


def scripted_turn(state):
    """Each hero of the current player walks toward today's waypoint as far
    as today allows (along the planned multi-day path)."""
    events = []
    for h in state.heroes:
        if h.owner != state.current:
            continue
        target = WAYPOINTS[h.id][state.day % 4]
        if h.pos == target:
            continue
        plan = A.find_path(state, h.id, target)
        if plan is None:
            continue
        reach = A.reachable(state, h.id)
        dest = None
        for t in plan[1][1:]:
            if t in reach:
                dest = t
        if dest is not None:
            state, ev = A.apply(state, A.Move(h.id, dest), NoRng())
            events.append(ev)
    state, ev = A.apply(state, A.EndTurn(state.current), NoRng())
    events.append(ev)
    return state, events


def play_days(state, days=14):
    trace = []
    state, ev = A.apply(state, A.Begin(), NoRng())
    trace.append(ev)
    while state.day <= days:
        state, evs = scripted_turn(state)
        trace.extend(evs)
    return state, trace


class GoldenTest(unittest.TestCase):
    # Pinned: changing rules, policy defaults or the canonical form changes
    # this hash and must be a deliberate, reviewed change.
    # History: e859fff5... (draft v1 defaults) -> 179c5700... (VCMI cross-check
    # defaults: source-tile pricing, roads 75/65/50 on both tiles, flat
    # Pathfinding, exact floor(sqrt2) diagonals, last-step rules). See
    # docs/specs/adventure.md section 6.
    PINNED = "179c570020d05be9a53c265a76517a4bb9f398c92f37d19485d30f804f703420"

    def test_replay_is_deterministic(self):
        s1, t1 = play_days(golden_setup())
        s2, t2 = play_days(golden_setup())
        self.assertEqual(s1.day, 15)
        self.assertEqual(A.state_hash(s1), A.state_hash(s2))
        self.assertEqual(t1, t2)
        moves = [e for ev in t1 for e in ev if isinstance(e, A.HeroMoved)]
        self.assertGreater(len(moves), 20)

    def test_golden_hash(self):
        s, _ = play_days(golden_setup())
        self.assertEqual(A.state_hash(s), self.PINNED)
        self.assertEqual(s.pools, (A.GrowthPool("a", 30, 10), A.GrowthPool("b", 4, 2)))
        self.assertEqual(s.players[0].resources,
                         A.Resources(gold=7500 + 14 * 1500, wood=10 + 14 * 2, ore=10))
        self.assertEqual(s.players[1].resources, A.Resources(gold=5000, ore=26, crystal=13))

    def test_policy_changes_outcome(self):
        a, ta = play_days(golden_setup())
        b, tb = play_days(golden_setup(replace(A.DEFAULT_POLICY, diagonal_moves=False)))
        self.assertNotEqual(A.state_hash(a), A.state_hash(b))
        self.assertNotEqual(ta, tb)       # different paths, not just the policy

    def test_stream_name(self):
        from h3re.rng import derive_stream
        a, b = A.adventure_rng(7, "x"), derive_stream(7, "adventure:x")
        self.assertEqual([a.next_u32() for _ in range(4)], [b.next_u32() for _ in range(4)])


POLICIES = [
    A.DEFAULT_POLICY,
    A.AdventurePolicy(last_step="allow_if_any", diagonal_corner_cut=False,
                      cost_from="dest", road_needs_both=False, road_rate_from="max",
                      diagonal_mode="ratio", diagonal_rounding="ceil",
                      zero_remainder=False, diagonal_exception=False,
                      pathfinding_mode="percent",
                      road_cost=(("cobblestone", 50), ("dirt", 50), ("gravel", 50))),
    A.AdventurePolicy(last_step="allow_if_fresh", diagonal_moves=False,
                      pathfinding_mode="percent", pathfinding_rounding="nearest",
                      income_on_first_day=True),
]


class PropertyTest(unittest.TestCase):
    def test_random_playouts(self):
        for seed in range(9):
            pol = POLICIES[seed % 3]
            chooser = random.Random(seed)
            state, _ = A.apply(golden_setup(pol), A.Begin(), NoRng())
            for _ in range(250):
                self.assertTrue(all(h.mp >= 0 for h in state.heroes))
                self.assertTrue(all(h.mp <= h.mp_max for h in state.heroes))
                pos = [h.pos for h in state.heroes]
                self.assertEqual(len(pos), len(set(pos)))
                self.assertTrue(all(state.grid.passable(p) for p in pos))
                mine = [h for h in state.heroes if h.owner == state.current]
                options = [(h.id, t) for h in mine for t in sorted(A.reachable(state, h.id))]
                if options and chooser.random() < 0.8:
                    hid, t = chooser.choice(options)
                    before = state.heroes[hid].mp
                    cost = A.reachable(state, hid)[t][0]
                    state, ev = A.apply(state, A.Move(hid, t), NoRng())
                    self.assertEqual(state.heroes[hid].mp, before - cost)
                    self.assertGreater(cost, 0)
                else:
                    state, _ = A.apply(state, A.EndTurn(state.current), NoRng())
                # illegal command leaves state untouched
                canon = A.canonical(state)
                with self.assertRaises(A.IllegalCommand):
                    A.apply(state, A.EndTurn(state.current + 1), NoRng())
                self.assertEqual(A.canonical(state), canon)

    def test_same_inputs_same_outputs(self):
        for pol in POLICIES:
            runs = [play_days(golden_setup(pol), 6) for _ in range(2)]
            self.assertEqual(A.canonical(runs[0][0]), A.canonical(runs[1][0]))
            self.assertEqual(runs[0][1], runs[1][1])

    def test_reachable_matches_find_path_when_affordable(self):
        s, _ = A.apply(golden_setup(), A.Begin(), NoRng())
        for hid in (0, 1):
            for t, (cost, path) in A.reachable(s, hid).items():
                # no step can hit the zero-remainder rule if 2 * (dearest step, 247) is spare
                if cost + 494 <= s.heroes[hid].mp:
                    self.assertEqual(A.find_path(s, hid, t), (cost, path))
                steps = [A.step_cost(s.grid, a, b, s.heroes[hid].pathfinding)
                         for a, b in zip(path, path[1:])]
                # only the last step may be adjusted by the last-step rules
                self.assertLessEqual(sum(steps[:-1]), cost)

    def test_state_is_immutable(self):
        s = golden_setup()
        with self.assertRaises(Exception):
            s.day = 3
        with self.assertRaises(Exception):
            s.heroes[0].mp = 5


class MalformedDestTest(unittest.TestCase):
    """A Move dest that is not a pair of ints is an IllegalCommand, not a
    TypeError; the state is untouched and the RNG is never used."""

    def test_bad_dest(self):
        s = started(grid(["ggg", "ggg"]))
        canon = A.canonical(s)
        for bad in (5, None, "ab", (1,), (1, 0, 0), ([1], 0), (1.0, 0), (True, 0), {1: 0}):
            with self.subTest(dest=bad):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, A.Move(0, bad), NoRng())
                self.assertEqual(A.canonical(s), canon)

    def test_list_still_accepted(self):
        s = started(grid(["ggg", "ggg"]))
        a, _ = A.apply(s, A.Move(0, [1, 0]), NoRng())
        b, _ = A.apply(s, A.Move(0, (1, 0)), NoRng())
        self.assertEqual(A.canonical(a), A.canonical(b))


class CommandInputTypeTest(unittest.TestCase):
    """Gap (1): every coordinate/pair/id input of an adventure command is
    rejected with IllegalCommand when it is a float, bool, string, None, wrong
    length or has non-int elements. State and RNG untouched."""

    BAD_PAIRS = ((2.0, 5), (2, 5.0), (True, 5), (1, True), (False, 0), (1, 0, 0), (1,), (),
                 (None, 0), (0, None), ("1", 0), ("ab",), "ab", "10", b"ab", None, 5, 2.0,
                 True, ([1], 0), ((1,), 0), {1: 0}, {1, 0}, [1.0, 0], [True, 0], [1], [1, 0, 0])

    def _s(self):
        return started(grid(["ggg", "ggg"]))

    def test_move_dest_rejected(self):
        s = self._s()
        canon, h = A.canonical(s), A.state_hash(s)
        for bad in self.BAD_PAIRS:
            with self.subTest(dest=bad):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, A.Move(0, bad), NoRng())
                self.assertEqual(A.canonical(s), canon)
                self.assertEqual(A.state_hash(s), h)

    def test_move_dest_rejected_even_when_equal_to_a_tile(self):
        # (1.0, 0) == (1, 0) and (True, 0) == (1, 0): equality must not admit them
        s = self._s()
        self.assertIn((1, 0), A.reachable(s, 0))
        for bad in ((1.0, 0), (1, 0.0), (True, 0), (1, False), [1.0, 0]):
            with self.subTest(dest=bad):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, A.Move(0, bad), NoRng())

    def test_find_path_does_not_crash_on_good_tile(self):
        self.assertIsNotNone(A.find_path(self._s(), 0, (1, 0)))

    def test_move_hero_id_types(self):
        s = started(grid(["ggg", "ggg"]),
                    heroes=(A.HeroSetup(0, (0, 0), army(5)), A.HeroSetup(0, (0, 1), army(5))))
        canon = A.canonical(s)
        for bad in (0.0, 1.0, "0", None, (0,), -1, 2, 99):
            with self.subTest(hero=bad):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, A.Move(bad, (1, 0)), NoRng())
                self.assertEqual(A.canonical(s), canon)

    def test_move_bool_hero_id_rejected(self):
        # True == 1 and isinstance(True, int): hero 1 must not be reachable by True
        s = started(grid(["ggg", "ggg"]),
                    heroes=(A.HeroSetup(0, (0, 0), army(5)), A.HeroSetup(0, (0, 1), army(5))))
        for bad in (True, False):
            with self.subTest(hero=bad):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, A.Move(bad, (1, 0)), NoRng())

    def test_endturn_player_types(self):
        s = self._s()
        canon = A.canonical(s)
        for bad in (None, "0", (0,), 1, -1, 99):
            with self.subTest(player=bad):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, A.EndTurn(bad), NoRng())
                self.assertEqual(A.canonical(s), canon)

    def test_endturn_float_player_rejected(self):
        s = self._s()
        with self.assertRaises(A.IllegalCommand):
            A.apply(s, A.EndTurn(0.0), NoRng())

    def test_endturn_bool_player_rejected(self):
        s = self._s()
        with self.assertRaises(A.IllegalCommand):
            A.apply(s, A.EndTurn(False), NoRng())

    def test_attack_inputs_rejected_before_any_draw(self):
        s = self._s()
        canon = A.canonical(s)
        for hero, target in ((0.0, 1), (True, 1), (None, 1), ("0", 1), (0, 1.0), (0, None),
                             (0, (1, 0)), (0, True)):
            with self.subTest(hero=hero, target=target):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, A.Attack(hero, target), NoRng())
                self.assertEqual(A.canonical(s), canon)

    def test_unknown_command_rejected(self):
        s = self._s()
        for bad in (None, 5, "Move", (0, (1, 0))):
            with self.subTest(cmd=bad):
                with self.assertRaises(A.IllegalCommand):
                    A.apply(s, bad, NoRng())


class IntSub(int):
    """Stands in for numpy.int64 and friends: an int subclass, == its value."""


class FloatSub(float):
    pass


# values that compare equal to a small int id or are not an int at all
BAD_IDS = (True, False, 0.0, 1.0, FloatSub(0.0), "0", "1", b"0", None, (0,), [0],
           IntSub(0), IntSub(1))


class StrictIntFieldsTest(unittest.TestCase):
    """Every integer command field must satisfy ``type(v) is int``: bool,
    float, str, None and int subclasses raise IllegalCommand before any state
    or RNG change. The golden adventure hash does not move."""

    def _s(self):
        return started(grid(["ggg", "ggg"]),
                       heroes=(A.HeroSetup(0, (0, 0), army(5)), A.HeroSetup(0, (0, 1), army(5))))

    def _rejected(self, s, cmd):
        canon, h = A.canonical(s), A.state_hash(s)
        with self.assertRaises(A.IllegalCommand):
            A.apply(s, cmd, NoRng())
        self.assertEqual(A.canonical(s), canon)
        self.assertEqual(A.state_hash(s), h)

    def test_move_hero(self):
        s = self._s()
        for bad in BAD_IDS:
            with self.subTest(hero=bad):
                self._rejected(s, A.Move(bad, (2, 0)))

    def test_move_dest_elements(self):
        s = self._s()
        for bad in BAD_IDS:
            for dest in ((bad, 0), (1, bad), [bad, 0], [1, bad]):
                with self.subTest(dest=dest):
                    self._rejected(s, A.Move(0, dest))

    def test_endturn_player(self):
        s = self._s()
        for bad in BAD_IDS:
            with self.subTest(player=bad):
                self._rejected(s, A.EndTurn(bad))
        # also when the bad value equals the value of a second player's turn
        s2, _ = A.apply(started(grid(["ggg"]), players=(A.Player(), A.Player())),
                        A.EndTurn(0), NoRng())
        self.assertEqual(s2.current, 1)
        for bad in (True, 1.0, IntSub(1), "1"):
            with self.subTest(player=bad):
                self._rejected(s2, A.EndTurn(bad))

    def test_attack_hero_and_target(self):
        s = self._s()
        for bad in BAD_IDS:
            with self.subTest(hero=bad):
                self._rejected(s, A.Attack(bad, 1))
            with self.subTest(target=bad):
                self._rejected(s, A.Attack(0, bad))

    def test_plain_ints_still_work(self):
        s = self._s()
        s1, _ = A.apply(s, A.Move(1, (2, 1)), NoRng())
        self.assertEqual(s1.heroes[1].pos, (2, 1))
        s2, _ = A.apply(s1, A.EndTurn(0), NoRng())
        self.assertEqual(s2.day, 2)

    def test_adventure_golden_unchanged(self):
        self.assertEqual(GoldenTest.PINNED,
                         "179c570020d05be9a53c265a76517a4bb9f398c92f37d19485d30f804f703420")
        s, _ = play_days(golden_setup())
        self.assertEqual(A.state_hash(s), GoldenTest.PINNED)


if __name__ == "__main__":
    unittest.main()
