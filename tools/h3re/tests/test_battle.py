import os
import random
import sys
import unittest
from collections import deque
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import battle as B  # noqa: E402
from h3re import rules  # noqa: E402


def cr(name="c", attack=5, defense=5, dmg=(2, 2), hp=10, speed=5, **kw):
    return B.Creature(name, attack, defense, dmg[0], dmg[1], hp, speed, **kw)


def ss(creature, count=10, **kw):
    return B.StackSetup(creature, count, **kw)


class ScriptRng:
    """Stub stream: scripted chance() results, randint returns the minimum."""

    def __init__(self, chances=()):
        self.chances = list(chances)
        self.calls = 0

    def chance(self, num, den):
        self.calls += 1
        return self.chances.pop(0) if self.chances else False

    def randint(self, lo, hi):
        self.calls += 1
        return lo


def begin(state, rng=None):
    rng = rng or ScriptRng()
    return B.apply(state, B.Begin(), rng)


class GeometryTest(unittest.TestCase):
    def test_default_parity_is_even(self):
        # VCMI cross-check #1 (clear): even rows sit half a hex to the right.
        self.assertEqual(B.DEFAULT_POLICY.row_offset, "even")
        self.assertEqual(B.DEFAULT_ROW_OFFSET, "even")

    def test_neighbour_table_odd_rows_shifted(self):
        table = {
            (5, 4): ((4, 3), (4, 4), (4, 5), (5, 3), (5, 5), (6, 4)),
            (5, 5): ((4, 5), (5, 4), (5, 6), (6, 4), (6, 5), (6, 6)),
            (0, 0): ((0, 1), (1, 0)),
            (16, 10): ((15, 9), (15, 10), (16, 9)),
            (0, 1): ((0, 0), (0, 2), (1, 0), (1, 1), (1, 2)),
            (16, 1): ((15, 1), (16, 0), (16, 2)),
        }
        for h, expected in table.items():
            self.assertEqual(B.neighbours(h, "odd"), expected, h)

    def test_neighbour_table_even_rows_shifted(self):
        # Even row: upper neighbours at col and col+1; odd row: col-1 and col.
        table = {
            (5, 4): ((4, 4), (5, 3), (5, 5), (6, 3), (6, 4), (6, 5)),
            (5, 5): ((4, 4), (4, 5), (4, 6), (5, 4), (5, 6), (6, 5)),
            (0, 0): ((0, 1), (1, 0), (1, 1)),
            (16, 10): ((15, 10), (16, 9)),
            (0, 1): ((0, 0), (0, 2), (1, 1)),
            (16, 1): ((15, 0), (15, 1), (15, 2), (16, 0), (16, 2)),
        }
        for h, expected in table.items():
            self.assertEqual(B.neighbours(h), expected, h)
            self.assertEqual(B.neighbours(h, "even"), expected, h)

    def test_neighbours_symmetric(self):
        for off in ("odd", "even"):
            for r in range(B.HEIGHT):
                for c in range(B.WIDTH):
                    ns = B.neighbours((c, r), off)
                    self.assertLessEqual(len(ns), 6)
                    for n in ns:
                        self.assertIn((c, r), B.neighbours(n, off))

    def test_distance_table(self):
        odd = [
            ((0, 0), (0, 0), 0), ((0, 0), (1, 0), 1), ((0, 0), (0, 1), 1),
            ((0, 0), (1, 1), 2), ((0, 0), (1, 2), 2), ((0, 0), (0, 10), 10),
            ((0, 0), (5, 10), 10), ((0, 0), (6, 10), 11), ((0, 0), (16, 0), 16),
            ((0, 0), (16, 10), 21), ((0, 10), (16, 0), 21), ((5, 5), (6, 4), 1), ((5, 5), (4, 4), 2),
            ((1, 5), (15, 5), 14),
        ]
        even = [
            ((0, 0), (0, 0), 0), ((0, 0), (1, 0), 1), ((0, 0), (0, 1), 1),
            ((0, 0), (1, 1), 1), ((0, 0), (1, 2), 2), ((0, 0), (0, 10), 10),
            ((0, 0), (5, 10), 10), ((0, 0), (6, 10), 11), ((0, 0), (16, 0), 16),
            ((0, 0), (16, 10), 21), ((0, 10), (16, 0), 21), ((5, 5), (6, 4), 2), ((5, 5), (4, 4), 1),
            ((1, 5), (15, 5), 14), ((1, 4), (2, 3), 1), ((2, 5), (1, 4), 1),
        ]
        for off, table in (("odd", odd), ("even", even)):
            for a, b, d in table:
                self.assertEqual(B.hex_distance(a, b, off), d, (off, a, b))
                self.assertEqual(B.hex_distance(b, a, off), d, (off, b, a))
        for a, b, d in even:
            self.assertEqual(B.hex_distance(a, b), d, (a, b))

    def test_distance_matches_bfs(self):
        for off in ("odd", "even"):
            for start in ((0, 0), (8, 5), (16, 10), (3, 7)):
                dist = {start: 0}
                q = deque([start])
                while q:
                    h = q.popleft()
                    for n in B.neighbours(h, off):
                        if n not in dist:
                            dist[n] = dist[h] + 1
                            q.append(n)
                self.assertEqual(len(dist), B.WIDTH * B.HEIGHT)
                for h, d in dist.items():
                    self.assertEqual(B.hex_distance(start, h, off), d)


class SetupTest(unittest.TestCase):
    def test_default_placement_and_two_hex(self):
        st = B.create_battle("p", [ss(cr(double_wide=True)), ss(cr())],
                             [ss(cr(double_wide=True)), ss(cr())])
        a0, a1, d0, d1 = st.stacks
        self.assertEqual(B.cells(a0), ((2, 2), (1, 2)))
        self.assertEqual(B.cells(a1), ((1, 8),))
        self.assertEqual(B.cells(d0), ((14, 2), (15, 2)))
        self.assertEqual(B.cells(d1), ((15, 8),))

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            B.create_battle("p", [ss(cr(), pos=(5, 5))], [ss(cr(), pos=(5, 5))])
        with self.assertRaises(ValueError):
            B.create_battle("p", [ss(cr(), pos=(5, 5))], [ss(cr())], obstacles=[(5, 5)])
        with self.assertRaises(ValueError):  # war-machine column
            B.create_battle("p", [ss(cr(), pos=(0, 5))], [ss(cr())])

    def test_policy_validation(self):
        with self.assertRaises(ValueError):
            B.BattlePolicy(wait_order="random")


class MovementTest(unittest.TestCase):
    def state(self, attacker, obstacles=(), pos=(4, 5), policy=B.DEFAULT_POLICY):
        return B.create_battle("m", [ss(attacker, pos=pos)], [ss(cr(speed=1), pos=(15, 0))],
                               obstacles=obstacles, policy=policy)

    def test_open_field(self):
        st = self.state(cr(speed=1), pos=(8, 5))
        self.assertEqual(B.reachable(st, 0), B.neighbours((8, 5)))
        st = self.state(cr(speed=2), pos=(8, 5))
        self.assertEqual(len(B.reachable(st, 0)), 18)

    def test_wall_blocks_walker_not_flyer(self):
        wall = [(5, r) for r in range(1, 11)]
        walker = self.state(cr(speed=3), wall)
        self.assertNotIn((6, 5), B.reachable(walker, 0))
        self.assertTrue(all(h[0] < 5 for h in B.reachable(walker, 0)))
        flyer = self.state(cr(speed=2, flyer=True), wall)
        reach = B.reachable(flyer, 0)
        self.assertIn((6, 5), reach)
        self.assertNotIn((5, 5), reach)  # cannot end on an obstacle
        self.assertTrue(all(B.hex_distance((4, 5), h) <= 2 for h in reach))

    def test_detour_around_obstacles(self):
        # Wall with a gap at row 0: path from (4,1) to (6,1) must go via row 0.
        wall = [(5, r) for r in range(1, 11)]
        st = self.state(cr(speed=4), wall, pos=(4, 1))
        self.assertIn((6, 1), B.reachable(st, 0))
        st = self.state(cr(speed=2), wall, pos=(4, 1))
        self.assertNotIn((6, 1), B.reachable(st, 0))

    def test_stacks_block(self):
        st = B.create_battle("m", [ss(cr(speed=1), pos=(8, 5))],
                             [ss(cr(), pos=(9, 5))])
        self.assertNotIn((9, 5), B.reachable(st, 0))

    def test_two_hex_needs_both_cells(self):
        st = self.state(cr(speed=1, double_wide=True), obstacles=[(4, 4)], pos=(5, 5))
        reach = B.reachable(st, 0)
        # head (5,4) would put the tail on the obstacle (4,4)
        self.assertNotIn((5, 4), reach)
        self.assertIn((5, 6), reach)   # even parity: (5,5)'s lower-right neighbour
        self.assertIn((4, 5), reach)  # step back: tail onto (3,5)
        st = self.state(cr(speed=1, double_wide=True), pos=(2, 5))
        self.assertNotIn((1, 5), B.reachable(st, 0))  # tail in edge column

    def test_edge_columns_policy(self):
        pol = B.BattlePolicy(edge_columns_walkable=True)
        st = self.state(cr(speed=1), pos=(1, 5), policy=pol)
        self.assertIn((0, 5), B.reachable(st, 0))
        st = self.state(cr(speed=1), pos=(1, 5))
        self.assertNotIn((0, 5), B.reachable(st, 0))

    def test_move_command_and_illegal(self):
        st, _ = begin(self.state(cr(speed=3)))
        self.assertEqual(st.active, 0)
        st2, ev = B.apply(st, B.Move(0, (7, 5)), ScriptRng())
        self.assertEqual(st2.stacks[0].pos, (7, 5))
        moved = [e for e in ev if isinstance(e, B.Moved)][0]
        self.assertEqual(moved.path[0], (4, 5))
        self.assertEqual(moved.path[-1], (7, 5))
        self.assertEqual(len(moved.path), 4)
        rng = ScriptRng()
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Move(0, (8, 5)), rng)
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Move(1, (14, 0)), rng)
        self.assertEqual(rng.calls, 0)
        self.assertEqual(st.stacks[0].pos, (4, 5))


def four(speeds, policy=B.DEFAULT_POLICY, morale=0):
    a = [ss(cr("a%d" % i, speed=s), morale=morale) for i, s in enumerate(speeds[:2])]
    d = [ss(cr("d%d" % i, speed=s), morale=morale) for i, s in enumerate(speeds[2:])]
    return B.create_battle("q", a, d, policy=policy)


class QueueTest(unittest.TestCase):
    def test_descending_speed(self):
        st, _ = begin(four([6, 4, 6, 5]))
        self.assertEqual(B.turn_order(st), (0, 2, 3, 1))

    def test_tie_policies(self):
        st, _ = begin(four([6, 6, 6, 6]))
        self.assertEqual(B.turn_order(st), (0, 1, 2, 3))
        st, _ = begin(four([6, 6, 6, 6], B.BattlePolicy(speed_tie="alternate")))
        self.assertEqual(B.turn_order(st), (0, 2, 1, 3))

    def run_wait(self, policy):
        st, _ = begin(four([7, 4, 6, 5], policy))
        rng = ScriptRng()
        st, _ = B.apply(st, B.Wait(0), rng)   # a0 waits
        st, _ = B.apply(st, B.Wait(2), rng)   # d0 waits
        self.assertEqual(B.turn_order(st)[:2], (3, 1))
        st, _ = B.apply(st, B.Defend(3), rng)
        st, _ = B.apply(st, B.Defend(1), rng)
        order = B.turn_order(st)
        self.assertEqual(B.round_order(st)[:2], (3, 1))
        return st, order

    def test_wait_phase_reverse_speed(self):
        st, order = self.run_wait(B.DEFAULT_POLICY)
        self.assertEqual(order, (2, 0))
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Wait(2), ScriptRng())  # cannot wait twice
        st, ev = B.apply(st, B.Defend(2), ScriptRng())
        self.assertEqual(ev[-1], B.TurnStarted(0, "wait", False))
        st, ev = B.apply(st, B.Defend(0), ScriptRng())
        self.assertIn(B.RoundStarted(2), ev)
        self.assertEqual(st.round, 2)
        self.assertEqual(B.turn_order(st), (0, 2, 3, 1))

    def test_wait_phase_other_policies(self):
        _, order = self.run_wait(B.BattlePolicy(wait_order="speed"))
        self.assertEqual(order, (0, 2))
        _, order = self.run_wait(B.BattlePolicy(wait_order="fifo"))
        self.assertEqual(order, (0, 2))

    def test_defend_bonus_and_expiry(self):
        st, _ = begin(four([7, 4, 6, 5]))
        st, ev = B.apply(st, B.Defend(0), ScriptRng())
        self.assertTrue(st.stacks[0].defending)
        self.assertIn(B.Defended(0), ev)
        for sid in (2, 3, 1):
            st, _ = B.apply(st, B.Defend(sid), ScriptRng())
        # New round: stack 0 is active again, its defend bonus has expired.
        self.assertEqual(st.active, 0)
        self.assertFalse(st.stacks[0].defending)
        self.assertTrue(st.stacks[1].defending)

    def test_defend_bonus_values(self):
        st = four([5, 5, 5, 5])
        for d, exp in ((0, 1), (4, 1), (7, 1), (10, 2), (12, 2), (15, 3)):
            s = replace(st.stacks[0], creature=cr(defense=d))
            self.assertEqual(B.defend_bonus(st, s), exp, d)
        ceil = replace(st, policy=B.BattlePolicy(defend_bonus_rounding="ceil"))
        s = replace(st.stacks[0], creature=cr(defense=12))
        self.assertEqual(B.defend_bonus(ceil, s), 3)
        hero = replace(st, heroes=(B.Hero(defense=3), None))
        s = replace(st.stacks[0], creature=cr(defense=7))
        self.assertEqual(B.defend_bonus(hero, s), 2)


class MoraleTest(unittest.TestCase):
    def test_bad_morale_freezes(self):
        st, ev = begin(four([7, 4, 6, 5], morale=-3), ScriptRng([True, False]))
        self.assertIn(B.MoraleFrozen(0), ev)
        self.assertEqual(st.active, 2)
        self.assertEqual(st.done, (0,))

    def test_good_morale_extra_action(self):
        st, _ = begin(four([7, 4, 6, 5], morale=3), ScriptRng([True]))
        self.assertTrue(st.morale_pending)
        st, ev = B.apply(st, B.Move(0, (2, 2)), ScriptRng())
        self.assertIn(B.MoraleBoost(0), ev)
        self.assertEqual(st.active, 0)
        self.assertTrue(st.bonus_turn)
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Wait(0), ScriptRng())
        # no repeat by default: next action ends the turn without a roll for 0
        st, ev = B.apply(st, B.Move(0, (3, 2)), ScriptRng([True]))
        self.assertNotIn(B.MoraleBoost(0), ev)
        self.assertEqual(st.active, 2)
        self.assertEqual(B.round_order(st), (0, 2, 3, 1))

    def test_no_good_morale_after_defend_or_wait_by_default(self):
        for cmd in (B.Defend(0), B.Wait(0)):
            st, _ = begin(four([7, 4, 6, 5], morale=3), ScriptRng([True]))
            st, ev = B.apply(st, cmd, ScriptRng())
            self.assertNotIn(B.MoraleBoost(0), ev)
        pol = B.BattlePolicy(good_morale_after_defend=True)
        st, _ = begin(four([7, 4, 6, 5], pol, morale=3), ScriptRng([True]))
        st, ev = B.apply(st, B.Defend(0), ScriptRng())
        self.assertIn(B.MoraleBoost(0), ev)

    def test_no_morale_flag(self):
        st = B.create_battle("n", [ss(cr(no_morale=True), morale=-3)], [ss(cr())])
        rng = ScriptRng([True])
        st, ev = begin(st, rng)
        self.assertEqual(rng.calls, 0)
        self.assertNotIn(B.MoraleFrozen(0), ev)


class CombatTest(unittest.TestCase):
    def setup(self, **kw):
        a0 = ss(cr("a0", speed=7, dmg=(3, 3), hp=100), count=4, pos=(7, 5))
        a1 = ss(cr("a1", speed=6, dmg=(3, 3), hp=100), count=4, pos=(8, 6))
        t = ss(cr("t", speed=5, dmg=(2, 2), hp=1000), count=5, pos=(8, 5))
        d1 = ss(cr("d1", speed=4), pos=(15, 0))
        st, _ = begin(B.create_battle("c", [a0, a1], [t, d1], **kw))
        return st

    def test_damage_via_rules_and_retaliation_once_per_round(self):
        st = self.setup()
        st, ev = B.apply(st, B.Attack(0, 2), ScriptRng())
        dmg = [e for e in ev if isinstance(e, B.DamageDealt)]
        self.assertEqual(dmg[0], B.DamageDealt(0, 2, rules.damage_from_base(12, 5, 5), 0, False, False))
        self.assertEqual(dmg[1], B.DamageDealt(2, 0, 10, 0, False, True))
        self.assertEqual(st.stacks[2].retaliations, 0)
        st, ev = B.apply(st, B.Attack(1, 2), ScriptRng())
        self.assertEqual(len([e for e in ev if isinstance(e, B.DamageDealt)]), 1)
        st, _ = B.apply(st, B.Defend(2), ScriptRng())
        st, ev = B.apply(st, B.Defend(3), ScriptRng())
        self.assertEqual(st.round, 2)
        self.assertEqual(st.stacks[2].retaliations, 1)
        # Defending target: defend bonus = max(1, 5//5) = 1 -> D 6 vs A 5.
        st, ev = B.apply(st, B.Attack(0, 2), ScriptRng())
        dmg = [e for e in ev if isinstance(e, B.DamageDealt)]
        self.assertEqual(dmg[0].damage, rules.damage_from_base(12, 5, 6))
        self.assertTrue(dmg[1].retaliation)

    def test_hero_and_skills(self):
        st = self.setup(heroes=(B.Hero(attack=4, offense=3), B.Hero(armorer=2)))
        st, ev = B.apply(st, B.Attack(0, 2), ScriptRng())
        dmg = [e for e in ev if isinstance(e, B.DamageDealt)]
        self.assertEqual(dmg[0].damage,
                         rules.damage_from_base(12, 9, 5, offense=3, armorer=2))

    def test_move_and_attack(self):
        a = ss(cr("a", speed=5, dmg=(1, 1), hp=10), count=1, pos=(3, 5))
        d = ss(cr("d", speed=1, hp=10), count=1, pos=(8, 5))
        st, _ = begin(B.create_battle("ma", [a], [d]))
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Attack(0, 1), ScriptRng())          # not adjacent
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Attack(0, 1, (5, 5)), ScriptRng())  # hex not adjacent
        st, ev = B.apply(st, B.Attack(0, 1, (7, 5)), ScriptRng())
        self.assertEqual(st.stacks[0].pos, (7, 5))
        self.assertIsInstance(ev[0], B.Moved)

    def test_kill_ends_battle(self):
        a = ss(cr("a", speed=5, dmg=(5, 5), hp=10), count=10, pos=(7, 5))
        d = ss(cr("d", speed=1, hp=10), count=2, pos=(8, 5))
        st, _ = begin(B.create_battle("k", [a], [d]))
        st, ev = B.apply(st, B.Attack(0, 1), ScriptRng())
        self.assertIn(B.UnitDied(1), ev)
        self.assertEqual(ev[-1], B.BattleEnded(B.ATTACKER))
        self.assertEqual(st.winner, B.ATTACKER)
        self.assertEqual(st.stacks[1].count, 0)
        self.assertEqual(B.legal_commands(st), ())
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Defend(0), ScriptRng())

    def test_shooting(self):
        archer = cr("arch", speed=5, dmg=(2, 2), hp=10, shots=3)
        far = B.create_battle("s", [ss(archer, count=10, pos=(1, 5))],
                              [ss(cr("t", hp=100), count=5, pos=(13, 5))])
        st, _ = begin(far)
        st, ev = B.apply(st, B.Shoot(0, 1), ScriptRng())
        d = [e for e in ev if isinstance(e, B.DamageDealt)]
        self.assertEqual(len(d), 1)  # never retaliated
        self.assertEqual(d[0].damage, rules.damage_from_base(20, 5, 5, ranged=True,
                                                             range_penalty=True))
        self.assertEqual(st.stacks[0].shots, 2)
        pol = B.BattlePolicy(range_penalty_beyond=12)
        st, _ = begin(replace(far, policy=pol))
        st, ev = B.apply(st, B.Shoot(0, 1), ScriptRng())
        self.assertEqual(ev[0].damage, 20)

    def test_adjacent_shooter_must_melee_with_penalty(self):
        archer = cr("arch", speed=5, dmg=(2, 2), hp=10, shots=3)
        st, _ = begin(B.create_battle("s", [ss(archer, count=10, pos=(7, 5))],
                                      [ss(cr("t", hp=100), count=5, pos=(8, 5))]))
        with self.assertRaises(B.IllegalCommand):
            B.apply(st, B.Shoot(0, 1), ScriptRng())
        st, ev = B.apply(st, B.Attack(0, 1), ScriptRng())
        self.assertEqual(ev[0].damage, rules.damage_from_base(20, 5, 5, melee_penalty=True))

    def test_luck(self):
        a = ss(cr("a", speed=5, dmg=(1, 1), hp=10), count=10, luck=2, pos=(7, 5))
        d = ss(cr("d", speed=1, hp=1000), count=1, pos=(8, 5))
        st, _ = begin(B.create_battle("l", [a], [d]))
        st2, ev = B.apply(st, B.Attack(0, 1), ScriptRng([True]))
        self.assertIn(B.LuckRolled(0, True), ev)
        self.assertEqual([e for e in ev if isinstance(e, B.DamageDealt)][0].damage, 20)
        # Bad luck is off by default: negative luck draws nothing.
        a = replace(a, luck=-2)
        st, _ = begin(B.create_battle("l", [a], [d]))
        rng = ScriptRng([True])
        _, ev = B.apply(st, B.Attack(0, 1), rng)
        self.assertEqual(ev[0].damage, 10)
        st, _ = begin(B.create_battle("l", [a], [d], policy=B.BattlePolicy(bad_luck=True)))
        _, ev = B.apply(st, B.Attack(0, 1), ScriptRng([True]))
        self.assertIn(B.LuckRolled(0, False), ev)
        self.assertEqual([e for e in ev if isinstance(e, B.DamageDealt)][0].damage, 5)


def golden_setup():
    pike = cr("pikeman", attack=4, defense=5, dmg=(1, 3), hp=10, speed=4)
    archer = cr("archer", attack=6, defense=3, dmg=(2, 3), hp=10, speed=4, shots=12)
    wolf = cr("wolf", attack=7, defense=5, dmg=(2, 5), hp=15, speed=8, strikes_twice=True)
    gnoll = cr("gnoll", attack=6, defense=7, dmg=(2, 4), hp=13, speed=6,
               double_wide=True, hates=("pikeman",))
    return B.create_battle(
        "golden",
        [ss(pike, 30, morale=1, luck=1), ss(archer, 20, morale=2)],
        [ss(wolf, 15, morale=-1, luck=2), ss(gnoll, 25, morale=1)],
        obstacles=[(7, 3), (8, 5), (9, 7), (6, 8)],
        heroes=(B.Hero(attack=2, defense=1, offense=1, archery=2), B.Hero(defense=2, armorer=1)),
    )


def scripted_choice(state):
    """Deterministic scripted player: shoot > attack > advance > defend."""
    cmds = B.legal_commands(state)
    for kind in (B.Shoot, B.Attack):
        hits = [c for c in cmds if isinstance(c, kind)]
        if hits:
            return hits[0]
    me = state.stacks[state.active]
    enemies = [s for s in state.stacks if s.alive and s.side != me.side]
    moves = [c for c in cmds if isinstance(c, B.Move)]
    if moves:
        return min(moves, key=lambda c: (min(B.hex_distance(c.dest, e.pos) for e in enemies),
                                         c.dest))
    return B.Defend(me.id)


def play(state, rng, chooser, limit=400):
    trace = []
    state, ev = B.apply(state, B.Begin(), rng)
    trace.append(ev)
    for _ in range(limit):
        if state.winner is not None:
            break
        state, ev = B.apply(state, chooser(state), rng)
        trace.append(ev)
    return state, trace


class GoldenTest(unittest.TestCase):
    # Pinned: changing rules, draw order, policy defaults or the canonical
    # form changes this hash and must be a deliberate, reviewed change.
    # Re-pinned 2026-11-01 (one reviewed change, see battle.md section 10):
    # row_offset "odd" -> "even", the wait-activation morale split, and the
    # canonical form now carrying every policy field plus ``last_side``.
    PINNED = "2191ae97fb22c8d15389d3e54c1a1eb6569a8d53630e0af647bd4ca97ca0d67d"

    def test_replay_is_deterministic(self):
        s1, t1 = play(golden_setup(), B.battle_rng(12345, "golden"), scripted_choice)
        s2, t2 = play(golden_setup(), B.battle_rng(12345, "golden"), scripted_choice)
        self.assertIsNotNone(s1.winner)
        self.assertEqual(B.state_hash(s1), B.state_hash(s2))
        self.assertEqual(t1, t2)
        s3, _ = play(golden_setup(), B.battle_rng(54321, "golden"), scripted_choice)
        self.assertNotEqual(B.canonical(s1), B.canonical(s3))

    def test_golden_hash(self):
        s, _ = play(golden_setup(), B.battle_rng(12345, "golden"), scripted_choice)
        self.assertEqual(B.state_hash(s), self.PINNED)

    def test_stream_name(self):
        a = B.battle_rng(7, "x")
        from h3re.rng import derive_stream
        b = derive_stream(7, "battle:x")
        self.assertEqual([a.next_u32() for _ in range(4)], [b.next_u32() for _ in range(4)])


def total_hp(s):
    return 0 if s.count == 0 else (s.count - 1) * s.creature.hp + s.top_hp


class PropertyTest(unittest.TestCase):
    def check_invariants(self, state):
        living = sorted(s.id for s in state.stacks if s.alive)
        for s in state.stacks:
            self.assertGreaterEqual(s.count, 0)
            if s.count:
                self.assertTrue(0 < s.top_hp <= s.creature.hp)
            else:
                self.assertEqual(s.top_hp, 0)
            self.assertGreaterEqual(s.shots, 0)
        ro = B.round_order(state)
        self.assertEqual(len(ro), len(set(ro)))
        if state.winner is None:
            self.assertEqual(sorted(ro), living)
            self.assertIn(state.active, living)
            self.assertEqual(B.turn_order(state)[0], state.active)
        occ = [c for s in state.stacks if s.alive for c in B.cells(s)]
        self.assertEqual(len(occ), len(set(occ)))
        self.assertFalse(set(occ) & set(state.obstacles))

    def test_random_playouts(self):
        policies = [B.DEFAULT_POLICY,
                    B.BattlePolicy(speed_tie="alternate", wait_order="fifo",
                                   good_morale_after_wait=True,
                                   good_morale_after_defend=True,
                                   repeat_good_morale=True, bad_luck=True,
                                   row_offset="odd", edge_columns_walkable=True),
                    B.BattlePolicy(speed_tie="alternate_last_mover",
                                   wait_order="slow_first_alternate",
                                   bad_morale_on_wait_activation=True,
                                   good_morale_on_wait_activation=False,
                                   bad_morale_table=rules.VCMI_BAD_MORALE_NUMERATORS,
                                   range_origin="any_cell")]
        for seed in range(12):
            pol = policies[seed % 3]
            base = replace(golden_setup(), policy=pol)
            chooser_rng = random.Random(seed)
            rng = B.battle_rng(seed, "prop")
            state, _ = B.apply(base, B.Begin(), rng)
            self.check_invariants(state)
            for _ in range(300):
                if state.winner is not None:
                    break
                cmds = B.legal_commands(state)
                self.assertTrue(cmds)
                before = [total_hp(s) for s in state.stacks]
                state, _ = B.apply(state, chooser_rng.choice(cmds), rng)
                after = [total_hp(s) for s in state.stacks]
                self.assertTrue(all(b >= a for a, b in zip(after, before)))
                self.check_invariants(state)
            # illegal commands never change state nor consume RNG
            if state.winner is None:
                probe = ScriptRng()
                other = next(s.id for s in state.stacks if s.id != state.active)
                with self.assertRaises(B.IllegalCommand):
                    B.apply(state, B.Defend(other), probe)
                self.assertEqual(probe.calls, 0)

    def test_state_is_immutable(self):
        st = golden_setup()
        with self.assertRaises(Exception):
            st.round = 5
        with self.assertRaises(Exception):
            st.stacks[0].count = 0

class IllegalCommandNoRngTest(unittest.TestCase):
    def assert_illegal(self, state, cmd):
        probe = ScriptRng()
        with self.assertRaises(B.IllegalCommand):
            B.apply(state, cmd, probe)
        self.assertEqual(probe.calls, 0)

    def two_v_two(self):
        a = cr("a", speed=7, shots=5)
        b = cr("b", speed=3)
        st = B.create_battle("ill", [ss(a, 5), ss(b, 5)], [ss(b, 5), ss(b, 5)])
        state, _ = begin(st)
        return state

    def test_move_to_unreachable_hex(self):
        state = self.two_v_two()
        me = state.stacks[state.active]
        far = (16, 10) if me.pos != (16, 10) else (0, 0)
        self.assertNotIn(far, B.reachable(state, me.id))
        self.assert_illegal(state, B.Move(me.id, far))
        obstacle_state = replace(state, obstacles=state.obstacles + ((7, 3),))
        self.assert_illegal(obstacle_state, B.Move(me.id, (7, 3)))

    def test_shoot_with_enemy_adjacent(self):
        state = self.two_v_two()
        me = state.stacks[state.active]
        self.assertTrue(me.creature.shooter)
        enemy = next(s for s in state.stacks if s.side != me.side)
        free = next(h for h in B.neighbours(me.pos)
                    if all(h not in B.cells(s) for s in state.stacks if s.alive))
        stacks = list(state.stacks)
        stacks[enemy.id] = replace(enemy, pos=free)
        adj = replace(state, stacks=tuple(stacks))
        self.assert_illegal(adj, B.Shoot(me.id, enemy.id))

    def test_wait_twice(self):
        c = cr("w", speed=5)
        st = B.create_battle("w2", [ss(c, 5)], [ss(c, 5)])
        state, _ = begin(st)
        first = state.active
        state, _ = B.apply(state, B.Wait(first), ScriptRng())
        other = state.active
        self.assertNotEqual(other, first)
        state, _ = B.apply(state, B.Defend(other), ScriptRng())
        self.assertEqual(state.active, first)
        self.assert_illegal(state, B.Wait(first))

    def test_dead_target(self):
        state = self.two_v_two()
        me = state.stacks[state.active]
        enemy = next(s for s in state.stacks if s.side != me.side)
        stacks = list(state.stacks)
        stacks[enemy.id] = replace(enemy, count=0)
        dead = replace(state, stacks=tuple(stacks))
        self.assert_illegal(dead, B.Attack(me.id, enemy.id))
        self.assert_illegal(dead, B.Shoot(me.id, enemy.id))


class RecordingRng(ScriptRng):
    """ScriptRng that also records every chance(num, den) asked."""

    def __init__(self, chances=()):
        super().__init__(chances)
        self.asked = []

    def chance(self, num, den):
        self.asked.append((num, den))
        return super().chance(num, den)


class WaitActivationMoraleTest(unittest.TestCase):
    """bad_/good_morale_on_wait_activation (replace the deprecated
    morale_roll_on_wait_activation; VCMI cross-check #4)."""

    def calls_at_wait_activation(self, morale, **pol):
        c = cr("m", speed=5)
        st = B.create_battle("wm", [ss(c, 5, morale=morale)], [ss(c, 5)],
                             policy=B.BattlePolicy(**pol))
        rng = ScriptRng()
        state, _ = B.apply(st, B.Begin(), rng)
        self.assertEqual(state.active, 0)
        state, _ = B.apply(state, B.Wait(0), rng)
        self.assertEqual(state.active, 1)
        before = rng.calls
        state, _ = B.apply(state, B.Defend(1), rng)
        self.assertEqual(state.active, 0)
        self.assertIn(0, state.waited)
        return rng.calls - before

    def test_defaults(self):
        self.assertFalse(B.DEFAULT_POLICY.bad_morale_on_wait_activation)
        self.assertTrue(B.DEFAULT_POLICY.good_morale_on_wait_activation)
        self.assertFalse(hasattr(B.DEFAULT_POLICY, "morale_roll_on_wait_activation"))

    def test_bad_roll_skipped_by_default(self):
        self.assertEqual(self.calls_at_wait_activation(-1), 0)
        self.assertEqual(self.calls_at_wait_activation(
            -1, bad_morale_on_wait_activation=True), 1)

    def test_good_roll_kept_by_default(self):
        self.assertEqual(self.calls_at_wait_activation(1), 1)
        self.assertEqual(self.calls_at_wait_activation(
            1, good_morale_on_wait_activation=False), 0)

    def test_good_morale_fires_after_wait_phase_action(self):
        c = cr("m", speed=5)
        st = B.create_battle("wm", [ss(c, 5, morale=3)], [ss(c, 5)])
        state, _ = B.apply(st, B.Begin(), ScriptRng([False]))
        state, _ = B.apply(state, B.Wait(0), ScriptRng())
        state, ev = B.apply(state, B.Defend(1), ScriptRng([True]))
        self.assertEqual(ev[-1], B.TurnStarted(0, "wait", False))
        self.assertTrue(state.morale_pending)
        self.assertEqual(state.stacks[0].pos, (1, 5))
        state, ev = B.apply(state, B.Move(0, (1, 6)), ScriptRng())
        self.assertIn(B.MoraleBoost(0), ev)
        self.assertTrue(state.bonus_turn)

    def test_canonical_carries_new_fields(self):
        a = B.create_battle("h", [ss(cr(), 3)], [ss(cr(), 3)])
        b = B.create_battle("h", [ss(cr(), 3)], [ss(cr(), 3)],
                            policy=B.BattlePolicy(bad_morale_on_wait_activation=True))
        c = B.create_battle("h", [ss(cr(), 3)], [ss(cr(), 3)],
                            policy=B.BattlePolicy(bad_morale_on_wait_activation=False,
                                                  good_morale_on_wait_activation=True,
                                                  bad_morale_table=[1, 2, 3]))
        self.assertNotEqual(B.state_hash(a), B.state_hash(b))
        # Explicit default values (a list is normalised to a tuple) hash the same.
        self.assertEqual(B.canonical(a), B.canonical(c))
        for key in (b'"bad_morale_on_wait_activation":false',
                    b'"good_morale_on_wait_activation":true',
                    b'"bad_morale_table":[1,2,3]', b'"range_origin":"head"',
                    b'"last_side":null'):
            self.assertIn(key, B.canonical(a))
        self.assertNotIn(b"morale_roll_on_wait", B.canonical(a))


class LastMoverOrderTest(unittest.TestCase):
    """speed_tie="alternate_last_mover", wait_order="slow_first_alternate"
    (VCMI cross-check #5/#6; options pending rules.md 9.4)."""

    def test_tie_after_faster_attacker(self):
        # a0 (speed 7, attacker) acts first; then the speed-6 tie a1/d0.
        # Last-mover rule: the attacker acted last, so d0 leads. The old
        # "alternate" mode re-ranks the remaining stacks and gives a1 first.
        for tie, expected in (("attacker_first", (1, 2, 3)),
                              ("alternate", (1, 2, 3)),
                              ("alternate_last_mover", (2, 1, 3))):
            st, _ = begin(four([7, 6, 6, 5], B.BattlePolicy(speed_tie=tie)))
            self.assertEqual(st.active, 0)
            st, _ = B.apply(st, B.Defend(0), ScriptRng())
            self.assertEqual(B.turn_order(st), expected, tie)

    def play_round(self, st):
        seen = []
        start = st.round
        while st.round == start:
            seen.append(st.active)
            st, _ = B.apply(st, B.Defend(st.active), ScriptRng())
        return st, tuple(seen)

    def test_alternation_carries_across_rounds(self):
        c = cr("x", speed=6)
        pol = B.BattlePolicy(speed_tie="alternate_last_mover")
        st = B.create_battle("lm", [ss(c), ss(c), ss(c)], [ss(c), ss(c)], policy=pol)
        st, _ = begin(st)
        self.assertEqual(st.last_side, B.ATTACKER)
        predicted = B.turn_order(st)
        self.assertEqual(predicted, (0, 3, 1, 4, 2))
        st, seen = self.play_round(st)
        self.assertEqual(seen, predicted)
        # Round 1 ended with an attacker, so the defender leads round 2.
        self.assertEqual(B.turn_order(st), (3, 0, 4, 1, 2))
        st, seen = self.play_round(st)
        self.assertEqual(seen, (3, 0, 4, 1, 2))

    def wait_phase(self, policy):
        st, _ = begin(four([6, 6, 6, 5], policy))
        rng = ScriptRng()
        st, _ = B.apply(st, B.Wait(0), rng)
        st, _ = B.apply(st, B.Defend(1), rng)
        st, _ = B.apply(st, B.Wait(2), rng)
        st, _ = B.apply(st, B.Defend(3), rng)  # defender acted last
        return B.turn_order(st)

    def test_slow_first_alternate(self):
        self.assertEqual(self.wait_phase(B.DEFAULT_POLICY), (2, 0))
        pol = B.BattlePolicy(wait_order="slow_first_alternate")
        self.assertEqual(self.wait_phase(pol), (0, 2))
        # Ascending speed; lower slot first within a side.
        st, _ = begin(four([7, 4, 6, 5], pol))
        for sid in (0, 2, 3, 1):
            st, _ = B.apply(st, B.Wait(sid), ScriptRng())
        self.assertEqual(B.turn_order(st), (1, 3, 2, 0))

    def test_validation(self):
        with self.assertRaises(ValueError):
            B.BattlePolicy(speed_tie="random")
        with self.assertRaises(ValueError):
            B.BattlePolicy(wait_order="slow_first")


class BadMoraleTableTest(unittest.TestCase):
    def test_default_and_vcmi_table(self):
        self.assertEqual(B.DEFAULT_POLICY.bad_morale_table, (1, 2, 3))
        for table, want in (((1, 2, 3), (1, 12)), ((2, 4, 6), (1, 6))):  # 2/24, 4/24
            pol = B.BattlePolicy(bad_morale_table=table)
            rng = RecordingRng([True])
            st, ev = begin(four([7, 4, 6, 5], pol, morale=-2), rng)
            self.assertEqual(rng.asked[0], want)
            self.assertIn(B.MoraleFrozen(0), ev)

    def test_validation(self):
        for bad in ((1, 2), (1, 2, 30), (3, 2, 1), (1, -1, 2), (1, 2, True)):
            with self.assertRaises(ValueError, msg=bad):
                B.BattlePolicy(bad_morale_table=bad)


class RangeOriginTest(unittest.TestCase):
    def shot(self, origin):
        archer = cr("arch", speed=9, dmg=(2, 2), hp=10, shots=3, double_wide=True)
        # Attacker head (13,5), tail (12,5); target behind it at (1,5):
        # head distance 12, tail distance 11.
        st = B.create_battle(
            "ro", [ss(archer, count=10, pos=(13, 5))],
            [ss(cr("t", hp=100), count=5, pos=(1, 5))],
            policy=B.BattlePolicy(range_penalty_beyond=11, range_origin=origin))
        st, _ = begin(st)
        _, ev = B.apply(st, B.Shoot(0, 1), ScriptRng())
        return [e for e in ev if isinstance(e, B.DamageDealt)][0].damage

    def test_head_vs_any_cell(self):
        self.assertEqual(B.DEFAULT_POLICY.range_origin, "head")
        self.assertEqual(self.shot("head"), 10)      # 12 > 11: penalty
        self.assertEqual(self.shot("any_cell"), 20)  # tail at 11: none
        with self.assertRaises(ValueError):
            B.BattlePolicy(range_origin="tail")


class PreviewLawTest(unittest.TestCase):
    """Every executed strike lies in strike_preview's [floor, ceiling]."""

    def _check(self, setup, seed, chooser):
        rng = B.battle_rng(seed, "golden")
        state, _ = B.apply(setup, B.Begin(), rng)
        checked = 0
        for _ in range(400):
            if state.winner is not None:
                break
            cmd = chooser(state)
            prev = None
            if isinstance(cmd, (B.Attack, B.Shoot)):
                prev = B.strike_preview(state, cmd.stack, cmd.target,
                                        isinstance(cmd, B.Shoot))
            state, ev = B.apply(state, cmd, rng)
            if prev is not None:
                first = [e for e in ev if isinstance(e, B.DamageDealt)][0]
                self.assertTrue(prev.floor <= first.damage <= prev.ceiling,
                                (seed, cmd, prev, first))
                checked += 1
        return checked

    def test_golden_strikes_within_preview(self):
        n = 0
        for seed in range(40):
            n += self._check(golden_setup(), seed, scripted_choice)
            n += self._check(replace(golden_setup(), policy=B.BattlePolicy(bad_luck=True)),
                             seed, scripted_choice)
        self.assertGreater(n, 100)

    def test_random_commands_within_preview(self):
        n = 0
        for seed in range(40):
            r = random.Random(seed)
            n += self._check(golden_setup(), seed, lambda s: r.choice(B.legal_commands(s)))
        self.assertGreater(n, 20)

if __name__ == "__main__":
    unittest.main()
