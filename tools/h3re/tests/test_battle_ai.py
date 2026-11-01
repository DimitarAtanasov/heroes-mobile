import os
import random
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import battle as B  # noqa: E402
from h3re import battle_ai as AI  # noqa: E402

FOOT = B.Creature("foot", 6, 5, 2, 4, 10, 5)
FAST = B.Creature("fast", 8, 6, 3, 5, 15, 7, flyer=True)
ARCH = B.Creature("arch", 6, 3, 2, 4, 8, 4, shots=12)
BIG = B.Creature("big", 10, 9, 5, 9, 40, 4, double_wide=True)


def scenario(seed_id):
    army = lambda: [B.StackSetup(FOOT, 20, morale=1), B.StackSetup(ARCH, 15, luck=1),
                    B.StackSetup(FAST, 8), B.StackSetup(BIG, 3)]
    return B.create_battle("g%s" % seed_id, army(), army(),
                           obstacles=((8, 4), (8, 5), (8, 6)))


def play(seed, choosers, limit=500):
    """choosers: {side: fn(state)->cmd}. Returns (state, command count)."""
    state = scenario(seed)
    rng = B.battle_rng(seed, "g%s" % seed)
    state, _ = B.apply(state, B.Begin(), rng)
    n = 0
    while state.winner is None and n < limit:
        cmd = choosers[state.stacks[state.active].side](state)
        state, _ = B.apply(state, cmd, rng)
        n += 1
    return state, n


class BattleAiTest(unittest.TestCase):
    def test_always_legal(self):
        for seed in range(10):
            ai = AI.GreedyAI(seed)
            state = scenario(seed)
            rng = B.battle_rng(seed, "g%s" % seed)
            state, _ = B.apply(state, B.Begin(), rng)
            for _ in range(200):
                if state.winner is not None:
                    break
                legal = B.legal_commands(state)
                for cmd in (AI.choose(state), ai.choose(state)):
                    self.assertIn(cmd, legal)
                state, _ = B.apply(state, ai.choose(state), rng)

    def test_begin_and_pure_choose(self):
        s = scenario(0)
        self.assertEqual(AI.choose(s), B.Begin())
        s, _ = B.apply(s, B.Begin(), B.battle_rng(0, "g0"))
        before = B.state_hash(s)
        AI.choose(s)
        self.assertEqual(before, B.state_hash(s))

    def test_ai_derives_only_ai_streams(self):
        # Record every stream the AI derives (it must only ever use "ai:*"
        # domains, never the battle stream) and the identity of those streams.
        calls = []
        real = AI.derive_stream

        def spy(master_seed, domain, ident=""):
            calls.append((master_seed, domain, ident))
            return real(master_seed, domain, ident)

        battle_stream_state = None
        AI.derive_stream = spy
        try:
            for seed in (0, 3):
                state = scenario(seed)
                brng = B.battle_rng(seed, "g%s" % seed)
                state, _ = B.apply(state, B.Begin(), brng)
                battle_stream_state = (brng.state, brng.inc)
                ai = AI.GreedyAI(seed)
                for _ in range(30):
                    if state.winner is not None:
                        break
                    cmds = (AI.choose(state), ai.choose(state))
                    # Choosing never advances the battle stream.
                    self.assertEqual((brng.state, brng.inc), battle_stream_state)
                    state, _ = B.apply(state, cmds[1], brng)
                    battle_stream_state = (brng.state, brng.inc)
        finally:
            AI.derive_stream = real
        self.assertTrue(calls, "AI never derived a stream (tie-break path untested)")
        for _, domain, ident in calls:
            self.assertRegex(domain, r"^ai:[01]$")
            self.assertFalse(domain.startswith("battle"), domain)
            self.assertEqual(ident, "")

    def test_ai_does_not_use_the_battle_rng_object(self):
        # The AI API takes no rng; a state that carries one would still not be
        # consulted. Guard against importing the battle stream constructor.
        self.assertFalse(hasattr(AI, "battle_rng"))
        self.assertFalse(hasattr(AI, "Pcg32"))

    def test_side_mismatch_raises(self):
        s, _ = B.apply(scenario(0), B.Begin(), B.battle_rng(0, "g0"))
        other = 1 - s.stacks[s.active].side
        with self.assertRaises(ValueError):
            AI.choose(s, other)

    def test_ai_vs_ai_finishes(self):
        for seed in range(100):
            ais = {0: AI.GreedyAI(seed), 1: AI.GreedyAI(seed + 1000)}
            state, n = play(seed, {s: ais[s].choose for s in (0, 1)})
            self.assertIsNotNone(state.winner, "seed %d unfinished" % seed)
            self.assertLessEqual(n, 500)

    def test_stateless_ai_vs_ai_finishes(self):
        for seed in range(20):
            state, n = play(seed, {0: AI.choose, 1: AI.choose})
            self.assertIsNotNone(state.winner, "seed %d unfinished" % seed)

    def test_deterministic(self):
        for seed in (1, 7, 42):
            hashes = []
            for _ in range(2):
                ais = {0: AI.GreedyAI(seed), 1: AI.GreedyAI(seed + 1)}
                state, _ = play(seed, {s: ais[s].choose for s in (0, 1)})
                hashes.append(B.state_hash(state))
            self.assertEqual(hashes[0], hashes[1])

    def test_preview_is_the_shared_function(self):
        # No local copy: the AI's estimate is strike_preview's EXPECTED value
        # and lies in [floor, ceiling] of the pipeline execution runs.
        from h3re import rules
        for seed in range(5):
            st, _ = B.apply(scenario(seed), B.Begin(), B.battle_rng(seed, "g%s" % seed))
            for a in st.stacks:
                for d in st.stacks:
                    if a.side == d.side:
                        continue
                    for ranged in (False, True):
                        p = B.strike_preview(st, a.id, d.id, ranged)
                        e = AI._preview(st, a, d, ranged)
                        self.assertEqual(e, p.expected)
                        self.assertTrue(p.floor <= e <= p.ceiling)
                        self.assertEqual(e, rules.resolve_damage(
                            B.strike_context(st, a, d, ranged),
                            rules.RollPolicy.EXPECTED).damage)

    def test_beats_random(self):
        wins = 0
        for seed in range(50):
            rnd = random.Random(seed)
            rand = lambda st: rnd.choice(B.legal_commands(st))
            ai = AI.GreedyAI(seed)
            side = seed % 2  # alternate which side the AI plays
            choosers = {side: ai.choose, 1 - side: rand}
            state, _ = play(seed, choosers)
            wins += state.winner == side
        print("greedy win rate vs random: %d/50" % wins)
        self.assertGreaterEqual(wins, 35)


if __name__ == "__main__":
    unittest.main()
