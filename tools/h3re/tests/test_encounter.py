"""Tests for adventure <-> battle integration (docs/specs/encounter.md)."""

import json
import os
import random
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import adventure as A  # noqa: E402
from h3re import battle as B  # noqa: E402
from h3re import encounter as E  # noqa: E402
from h3re import rules  # noqa: E402
from h3re.rng import derive_stream  # noqa: E402

import test_adventure as TA  # noqa: E402
import test_battle as TB  # noqa: E402

CREATURES = (
    B.Creature("pike", 4, 5, 1, 3, 10, 4),
    B.Creature("archer", 6, 3, 2, 3, 10, 4, shots=12),
    B.Creature("wolf", 7, 5, 2, 5, 15, 8, strikes_twice=True),
    B.Creature("gnoll", 6, 7, 2, 4, 13, 6, double_wide=True, hates=("pike",)),
    B.Creature("statue", 1, 1, 1, 1, 50, 0),     # speed 0: can never close in
)
SPEED = {c.name: c.speed for c in CREATURES}
SEED = 2026


def army(*parts):
    return tuple(A.ArmySlot(n, SPEED[n], k) for n, k in parts)


def flat_grid(w=8, h=4):
    return A.Grid(w, h, tuple(A.Tile("grass") for _ in range(w * h)))


def setup(policy=E.DEFAULT_POLICY, **kw):
    return E.EncounterSetup(CREATURES, policy=policy, **kw)


def golden_game(policy=E.DEFAULT_POLICY, reverse_inputs=False):
    heroes = (
        A.HeroSetup(0, (1, 1), army(("pike", 30), ("archer", 20))),
        A.HeroSetup(0, (4, 2), army(("wolf", 6))),
        A.HeroSetup(1, (6, 1), army(("gnoll", 12), ("pike", 10))),
        A.HeroSetup(1, (7, 3), army(("pike", 25), ("archer", 6))),
    )
    guards = (A.Guard("wolves", (2, 1), army(("wolf", 8))),
              A.Guard("camp", (6, 3), army(("gnoll", 20))))
    creatures = CREATURES
    if reverse_inputs:      # guard and creature order must not matter
        guards, creatures = guards[::-1], creatures[::-1]
    return A.create_game("enc", flat_grid(), (A.Player(), A.Player()), heroes,
                         guards=guards,
                         encounter=E.EncounterSetup(creatures, policy=policy))


GOLDEN_SCRIPT = (
    A.Begin(),
    A.Attack(0, "wolves"), A.Move(1, (5, 1)), A.Attack(1, 2), A.EndTurn(0),
    A.Attack(3, "camp"), A.Move(2, (2, 1)), A.Attack(2, 0), A.EndTurn(1),
    A.Move(0, (3, 1)), A.EndTurn(0), A.EndTurn(1),
)


def step(state, cmd, seed=SEED):
    return A.apply(state, cmd, E.stream_for(seed, state, cmd))


def play(state, script=GOLDEN_SCRIPT, seed=SEED):
    trace = []
    for cmd in script:
        state, ev = step(state, cmd, seed)
        trace.append(ev)
    return state, trace


def fought(trace):
    return [e for ev in trace for e in ev if isinstance(e, E.BattleFought)]


class Untouchable:
    """Any use of the stream fails the test."""

    def __getattr__(self, name):
        raise AssertionError("rng used: %s" % name)


class GoldenTest(unittest.TestCase):
    # Derivation (docs/specs/encounter.md section 7): golden_game() with the
    # default EncounterPolicy and BattlePolicy, master seed 2026, every
    # command's stream from encounter.stream_for, GOLDEN_SCRIPT applied in
    # order; the pin is adventure.state_hash of the final state.
    PINNED = "512b53ca56c4c5611e718b4b23129984ab5a3c0f6e0de4a7feb48c620568bd60"

    def test_golden_hash(self):
        s, trace = play(golden_game())
        self.assertEqual(A.state_hash(s), self.PINNED)
        self.assertEqual(s.day, 3)
        self.assertEqual(s.battles, 4)
        self.assertEqual([f.winner for f in fought(trace)],
                         [B.ATTACKER, B.DEFENDER, B.DEFENDER, B.DEFENDER])
        self.assertEqual(s.heroes[0].army, army(("pike", 24), ("archer", 18)))
        self.assertEqual([h.pos for h in s.heroes], [(3, 1), None, None, None])
        self.assertEqual(s.guards, (A.Guard("camp", (6, 3), army(("gnoll", 12))),))

    def test_replay_is_deterministic(self):
        s1, t1 = play(golden_game())
        s2, t2 = play(golden_game())
        self.assertEqual(A.canonical(s1), A.canonical(s2))
        self.assertEqual(t1, t2)
        s3, _ = play(golden_game(), seed=SEED + 1)
        self.assertNotEqual(A.state_hash(s1), A.state_hash(s3))

    def test_existing_goldens_unchanged(self):
        s, _ = TA.play_days(TA.golden_setup())
        self.assertEqual(A.state_hash(s), TA.GoldenTest.PINNED)
        self.assertEqual(TA.GoldenTest.PINNED,
                         "179c570020d05be9a53c265a76517a4bb9f398c92f37d19485d30f804f703420")
        b, _ = TB.play(TB.golden_setup(), B.battle_rng(12345, "golden"), TB.scripted_choice)
        self.assertEqual(B.state_hash(b), TB.GoldenTest.PINNED)
        self.assertEqual(TB.GoldenTest.PINNED,
                         "fbe9015bde1b6e5c165c08fc1604f98ea7c3cdf09cc38528ec2fda496f040e2b")


class StreamTest(unittest.TestCase):
    def test_battle_stream_name_and_ids(self):
        s = A.apply(golden_game(), A.Begin(), Untouchable())[0]
        self.assertEqual(E.battle_id(s), "enc:1")
        a = E.stream_for(7, s, A.Attack(0, "wolves"))
        b = derive_stream(7, "battle:enc:1")
        self.assertEqual([a.next_u32() for _ in range(4)], [b.next_u32() for _ in range(4)])
        c = E.stream_for(7, s, A.EndTurn(0))
        d = derive_stream(7, "adventure:enc")
        self.assertEqual([c.next_u32() for _ in range(4)], [d.next_u32() for _ in range(4)])
        _, trace = play(golden_game())
        self.assertEqual([f.battle_id for f in fought(trace)],
                         ["enc:1", "enc:2", "enc:3", "enc:4"])

    def test_log_replays_on_the_named_stream(self):
        # The event's command log, replayed on battle:<id> from the same seed,
        # reproduces the final battle hash: the battle drew only from it.
        s = golden_game()
        for cmd in GOLDEN_SCRIPT:
            if isinstance(cmd, A.Attack):
                bs = E.build_battle(s, cmd)
                rng = B.battle_rng(SEED, bs.battle_id)
                s, ev = step(s, cmd)
                f = ev[0]
                for bc in f.log:
                    bs, _ = B.apply(bs, bc, rng)
                self.assertEqual(B.state_hash(bs), f.battle_hash)
                self.assertEqual(bs.winner, f.winner)
            else:
                s, _ = step(s, cmd)

    def test_other_commands_never_draw(self):
        s = golden_game()
        for cmd in GOLDEN_SCRIPT:
            if isinstance(cmd, A.Attack):
                s, _ = step(s, cmd)
            else:
                s, _ = A.apply(s, cmd, Untouchable())


class BuildBattleTest(unittest.TestCase):
    def started(self, policy=E.DEFAULT_POLICY):
        return A.apply(golden_game(policy), A.Begin(), Untouchable())[0]

    def test_stacks_mirror_the_armies(self):
        s = self.started()
        bs = E.build_battle(s, A.Attack(0, "wolves"))
        self.assertEqual(bs.battle_id, "enc:1")
        self.assertEqual([(x.side, x.slot, x.creature.name, x.count) for x in bs.stacks],
                         [(0, 0, "pike", 30), (0, 1, "archer", 20), (1, 0, "wolf", 8)])
        self.assertEqual(bs.heroes, (B.Hero(), None))
        self.assertEqual(bs.policy, B.DEFAULT_POLICY)
        self.assertEqual([x.pos for x in bs.stacks], [(1, 2), (1, 8), (15, 5)])
        s2 = A.apply(s, A.Move(1, (5, 1)), Untouchable())[0]
        self.assertEqual(E.build_battle(s2, A.Attack(1, 2)).heroes, (B.Hero(), B.Hero()))

    def test_slot_mapping_by_slot(self):
        s = self.started(E.EncounterPolicy(slot_mapping="by_slot"))
        bs = E.build_battle(s, A.Attack(0, "wolves"))
        rows = B.DEFAULT_POLICY.placement_rows[6]
        self.assertEqual([x.pos for x in bs.stacks], [(1, rows[0]), (1, rows[1]), (15, rows[0])])
        s2 = A.apply(s, A.Move(1, (5, 1)), Untouchable())[0]
        gn = E.build_battle(s2, A.Attack(1, 2)).stacks[1]      # two-hex defender
        self.assertEqual((gn.creature.name, gn.pos), ("gnoll", (14, rows[0])))

    def test_build_is_pure(self):
        s = self.started()
        canon = A.canonical(s)
        E.build_battle(s, A.Attack(0, "wolves"))
        self.assertEqual(A.canonical(s), canon)


class OutcomeTest(unittest.TestCase):
    def test_survivors_flow_back_per_slot(self):
        s = A.apply(golden_game(), A.Begin(), Untouchable())[0]
        cmd = A.Attack(0, "wolves")
        bs = E.build_battle(s, cmd)
        end, _, _ = E.fight(bs, B.battle_rng(SEED, bs.battle_id), 100)
        s2, ev = step(s, cmd)
        counts = [x.count for x in end.stacks if x.side == B.ATTACKER]
        self.assertEqual([a.count for a in s2.heroes[0].army], [c for c in counts if c])
        self.assertIn(E.ArmyChanged(0, s2.heroes[0].army), ev)

    def test_dead_slot_drops_out_and_order_kept(self):
        s = A.apply(golden_game(), A.Begin(), Untouchable())[0]
        foe = army(("pike", 1), ("wolf", 1), ("statue", 1))
        s = replace(s, heroes=(s.heroes[0], s.heroes[1],
                               replace(s.heroes[2], pos=(2, 2), army=foe), s.heroes[3]))
        bs = E.build_battle(s, A.Attack(0, 2))
        stacks = list(bs.stacks)
        stacks[3] = replace(stacks[3], count=0, top_hp=0)        # the wolf slot dies
        end = replace(bs, stacks=tuple(stacks))
        self.assertEqual(E._survivors(foe, end, B.DEFENDER),
                         army(("pike", 1), ("statue", 1)))

    def test_removed_hero(self):
        s, _ = play(golden_game(), GOLDEN_SCRIPT[:4])           # hero 1 lost to hero 2
        h = s.heroes[1]
        self.assertEqual((h.pos, h.army, h.mp, h.mp_max), (None, (), 0, 0))
        self.assertEqual(A.reachable(s, 1), {})
        self.assertIsNone(A.find_path(s, 1, (0, 0)))
        for cmd in (A.Move(1, (5, 2)), A.Attack(1, 2)):
            with self.assertRaises(A.IllegalCommand):
                A.apply(s, cmd, Untouchable())
        s, ev = A.apply(s, A.EndTurn(0), Untouchable())
        with self.assertRaises(A.IllegalCommand):                # cannot be attacked
            A.apply(s, A.Attack(2, 1), Untouchable())            # hero 2 is next to (5, 1)
        self.assertIn((5, 1), A.reachable(s, 2))                 # its tile is free
        s, ev = A.apply(s, A.EndTurn(1), Untouchable())          # p0's next turn
        self.assertNotIn(A.MovementReset(1, 0), ev)
        self.assertEqual([e.hero for e in ev if isinstance(e, A.MovementReset)], [0])

    def test_guard_win_keeps_survivors_attacker_removed(self):
        s, trace = play(golden_game(), GOLDEN_SCRIPT[:6])
        self.assertEqual(trace[-1][1:], (E.HeroDefeated(3),
                                         E.ArmyChanged("camp", army(("gnoll", 12)))))

    def test_guards_block_movement(self):
        s = A.apply(golden_game(), A.Begin(), Untouchable())[0]
        self.assertNotIn((2, 1), A.reachable(s, 0))
        with self.assertRaises(A.IllegalCommand):
            A.apply(s, A.Move(0, (2, 1)), Untouchable())

    def test_loser_fate_winner_takes_tile(self):
        pol = E.EncounterPolicy(loser_fate="winner_takes_tile")
        a, ta = play(golden_game(), GOLDEN_SCRIPT[:2])
        b, tb = play(golden_game(pol), GOLDEN_SCRIPT[:2])
        self.assertEqual(a.heroes[0].pos, (1, 1))
        self.assertEqual(b.heroes[0].pos, (2, 1))
        mp = b.heroes[0].mp
        self.assertEqual(tb[-1][-1], A.HeroMoved(0, ((1, 1), (2, 1)), 0, mp))
        self.assertEqual(a.heroes[0].mp, mp)
        # A defending winner stays put under either fate.
        c, _ = play(golden_game(pol), GOLDEN_SCRIPT[:4])
        self.assertEqual(c.heroes[2].pos, (6, 1))

    def test_policy_is_in_the_hash(self):
        for pol in (E.EncounterPolicy(loser_fate="winner_takes_tile"),
                    E.EncounterPolicy(slot_mapping="by_slot"),
                    E.EncounterPolicy(round_limit=50)):
            with self.subTest(policy=pol):
                self.assertNotEqual(A.state_hash(golden_game()), A.state_hash(golden_game(pol)))

    def test_round_limit_draw(self):
        g = A.create_game("draw", flat_grid(), (A.Player(), A.Player()),
                          (A.HeroSetup(0, (1, 1), army(("statue", 3))),
                           A.HeroSetup(1, (2, 1), army(("statue", 4)))),
                          encounter=setup(E.EncounterPolicy(round_limit=3)))
        s = A.apply(g, A.Begin(), Untouchable())[0]
        s2, ev = step(s, A.Attack(0, 1))
        self.assertEqual((ev[0].winner, ev[0].rounds), (None, 3))
        self.assertEqual(len(ev), 1)                             # nobody changed
        self.assertEqual(s2.heroes, s.heroes)
        self.assertEqual(s2.battles, 1)
        self.assertEqual(E.battle_id(s2), "draw:2")              # next battle, new stream


class IllegalTest(unittest.TestCase):
    def setUp(self):
        self.s = A.apply(golden_game(), A.Begin(), Untouchable())[0]

    def assertIllegal(self, state, cmd):
        canon = A.canonical(state)
        with self.assertRaises(A.IllegalCommand):
            A.apply(state, cmd, Untouchable())
        self.assertEqual(A.canonical(state), canon)

    def test_rejected_before_any_draw(self):
        s = self.s
        for cmd in (A.Attack(0, "nope"), A.Attack(0, 0), A.Attack(0, 1),        # own heroes
                    A.Attack(0, 2), A.Attack(0, "camp"),                         # not adjacent
                    A.Attack(2, 0), A.Attack(9, "wolves"), A.Attack(True, "wolves"),
                    A.Attack(0, True), A.Attack(0, 2.0), A.Attack(0, None),
                    A.Attack(0, ["wolves"]), A.Attack(None, "wolves")):
            with self.subTest(cmd=cmd):
                self.assertIllegal(s, cmd)

    def test_not_started_and_not_enabled(self):
        self.assertIllegal(golden_game(), A.Attack(0, "wolves"))
        g = A.create_game("x", flat_grid(), (A.Player(), A.Player()),
                          (A.HeroSetup(0, (1, 1), army(("pike", 1))),
                           A.HeroSetup(1, (2, 1), army(("pike", 1)))))
        self.assertIllegal(A.apply(g, A.Begin(), Untouchable())[0], A.Attack(0, 1))

    def test_rules_pack_mismatch(self):
        other = replace(self.s, encounter=replace(self.s.encounter, rules_hash="0" * 64))
        self.assertIllegal(other, A.Attack(0, "wolves"))

    def test_content_mismatch(self):
        bad = replace(self.s, guards=(A.Guard("camp", (6, 3), army(("gnoll", 20))),
                                      A.Guard("wolves", (2, 1), (A.ArmySlot("wolf", 7, 8),))))
        self.assertIllegal(bad, A.Attack(0, "wolves"))

    def test_diagonal_rules_apply_to_adjacency(self):
        g = A.create_game("d", flat_grid(), (A.Player(), A.Player()),
                          (A.HeroSetup(0, (1, 1), army(("pike", 1))),
                           A.HeroSetup(1, (2, 2), army(("pike", 1)))),
                          policy=A.AdventurePolicy(diagonal_moves=False), encounter=setup())
        self.assertIllegal(A.apply(g, A.Begin(), Untouchable())[0], A.Attack(0, 1))


class SetupValidationTest(unittest.TestCase):
    def test_create_game_checks(self):
        players = (A.Player(), A.Player())
        hero = (A.HeroSetup(0, (1, 1), army(("pike", 1))),)
        cases = [
            dict(heroes=(A.HeroSetup(0, (1, 1), (A.ArmySlot("ghost", 4, 1),)),),
                 encounter=setup()),
            dict(heroes=(A.HeroSetup(0, (1, 1), (A.ArmySlot("pike", 5, 1),)),),
                 encounter=setup()),
            dict(heroes=hero, guards=(A.Guard("g", (1, 1), army(("pike", 1))),)),
            dict(heroes=hero, guards=(A.Guard("g", (3, 1), army(("pike", 1))),
                                      A.Guard("g", (4, 1), army(("pike", 1))))),
            dict(heroes=hero, guards=(A.Guard(3, (3, 1), army(("pike", 1))),)),
            dict(heroes=hero, guards=(A.Guard("g", (3, 1), ()),)),
            dict(heroes=hero, encounter="not a setup"),
        ]
        for kw in cases:
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    A.create_game("v", flat_grid(), players, guards=kw.get("guards", ()),
                                  heroes=kw["heroes"], encounter=kw.get("encounter"))

    def test_setup_and_policy_checks(self):
        with self.assertRaises(ValueError):
            E.EncounterSetup(CREATURES + (CREATURES[0],))
        with self.assertRaises(ValueError):
            E.EncounterSetup(("pike",))
        for kw in (dict(loser_fate="x"), dict(slot_mapping="x"), dict(round_limit=0),
                   dict(round_limit=True)):
            with self.assertRaises(ValueError):
                E.EncounterPolicy(**kw)

    def test_setup_is_canonical(self):
        self.assertEqual(E.EncounterSetup(CREATURES),
                         E.EncounterSetup(tuple(reversed(CREATURES))))
        self.assertEqual(A.state_hash(golden_game()),
                         A.state_hash(golden_game(reverse_inputs=True)))

    def test_new_fields_omitted_at_default(self):
        plain = TA.golden_setup()
        data = json.loads(A.canonical(plain))
        for name in ("guards", "encounter", "battles"):
            self.assertNotIn(name, data)
        data = json.loads(A.canonical(golden_game()))
        self.assertIn("guards", data)
        self.assertEqual(data["encounter"]["rules_hash"], rules.RULES_HASH)
        self.assertNotIn("battles", data)


class PropertyTest(unittest.TestCase):
    POLICIES = (E.DEFAULT_POLICY,
                E.EncounterPolicy(loser_fate="winner_takes_tile", slot_mapping="by_slot"),
                E.EncounterPolicy(round_limit=4))

    def playout(self, seed):
        chooser = random.Random(seed)
        state = A.apply(golden_game(self.POLICIES[seed % 3]), A.Begin(), Untouchable())[0]
        trace = []
        for _ in range(40):
            on_map = [h for h in state.heroes if h.pos is not None]
            tiles = [h.pos for h in on_map] + [g.pos for g in state.guards]
            self.assertEqual(len(tiles), len(set(tiles)))
            for h in state.heroes:
                self.assertEqual(h.pos is None, h.army == ())
            for unit in on_map + list(state.guards):
                self.assertTrue(all(a.count > 0 for a in unit.army))
            A.canonical(state)                                   # stays serialisable
            mine = [h for h in on_map if h.owner == state.current]
            targets = [h.id for h in on_map if h.owner != state.current] + \
                [g.id for g in state.guards]
            options = [A.Attack(h.id, t) for h in mine for t in targets]
            options += [A.Move(h.id, t) for h in mine for t in sorted(A.reachable(state, h.id))]
            cmd = chooser.choice(options) if options and chooser.random() < 0.85 \
                else A.EndTurn(state.current)
            canon = A.canonical(state)
            try:
                state, ev = step(state, cmd, seed)
                trace.append(ev)
            except A.IllegalCommand:                             # e.g. not adjacent
                self.assertEqual(A.canonical(state), canon)
        return state, trace

    def test_random_playouts(self):
        battles = 0
        for seed in range(6):
            state, trace = self.playout(seed)
            battles += state.battles
            again, trace2 = self.playout(seed)
            self.assertEqual(A.canonical(state), A.canonical(again))
            self.assertEqual(trace, trace2)
        self.assertGreater(battles, 3)


if __name__ == "__main__":
    unittest.main()
