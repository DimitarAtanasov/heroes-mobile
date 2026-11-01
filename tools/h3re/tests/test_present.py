import json
import os
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from h3re import battle as B  # noqa: E402
from h3re import present as P  # noqa: E402
from test_battle import golden_setup, scripted_choice, cr, ss  # noqa: E402


class FailRng:
    def chance(self, *a):
        raise AssertionError("presenter drew from the RNG")

    def randint(self, *a):
        raise AssertionError("presenter drew from the RNG")

    def __getattr__(self, name):
        raise AssertionError("presenter touched the RNG: " + name)


def golden_states():
    """Golden scenario states at several points of play (including the end)."""
    rng = B.battle_rng(12345, "golden")
    state = golden_setup()
    out = [state]
    state, _ = B.apply(state, B.Begin(), rng)
    out.append(state)
    for i in range(400):
        if state.winner is not None:
            break
        state, _ = B.apply(state, scripted_choice(state), rng)
        if i % 5 == 0 or state.winner is not None:
            out.append(state)
    return out


def synthetic_states():
    big = cr("big", speed=6, double_wide=True, hp=20)
    arch = cr("arch", speed=5, shots=4, hp=8)
    fly = cr("fly", speed=9, flyer=True)
    a = B.create_battle("syn", [ss(big, 5, pos=(3, 5)), ss(arch, 9, pos=(2, 2))],
                        [ss(fly, 4, pos=(5, 5)), ss(cr("t"), 7, pos=(14, 8))],
                        obstacles=[(4, 4), (4, 5)])
    started, _ = B.apply(a, B.Begin(), B.battle_rng(1, "syn"))
    return [a, started]


def all_states():
    return golden_states() + synthetic_states()


def walk(d):
    if isinstance(d, dict):
        for k, v in d.items():
            assert isinstance(k, str)
            yield from walk(v)
    elif isinstance(d, list):
        for v in d:
            yield from walk(v)
    else:
        yield d


class PresentTest(unittest.TestCase):
    def test_states_cover_scenarios(self):
        self.assertGreater(len(golden_states()), 5)

    def test_pure_no_rng_no_mutation_deterministic(self):
        for st in all_states():
            h0 = B.state_hash(st)
            v1 = P.view(st)
            v2 = P.view(st)
            self.assertEqual(B.state_hash(st), h0)
            self.assertEqual(v1, v2)
            self.assertEqual(P.view_json(st), P.view_json(st))
            P.candidate_commands(st, (3, 5))
            self.assertEqual(B.state_hash(st), h0)

    def test_no_rng_draw_even_if_module_rng_called(self):
        # view takes no rng; guard that it does not reach derive_stream draws
        # by making the Rng class explode on any attribute use.
        from h3re import rng as R
        orig = R.derive_stream
        R.derive_stream = lambda *a, **k: FailRng()
        try:
            for st in all_states():
                P.view(st)
        finally:
            R.derive_stream = orig

    def test_canonical_json_ints_only(self):
        for st in all_states():
            v = P.view(st)
            text = P.view_json(st)
            self.assertEqual(json.loads(text), v)
            self.assertEqual(text, json.dumps(json.loads(text), sort_keys=True,
                                              separators=(",", ":")))
            for leaf in walk(v):
                self.assertNotIsInstance(leaf, float)
                self.assertTrue(leaf is None or isinstance(leaf, (bool, int, str)))
            self.assertEqual(v["view_version"], P.VIEW_VERSION)

    def test_grid_and_stacks(self):
        for st in all_states():
            v = P.view(st)
            rows = v["grid"]["rows"]
            self.assertEqual(len(rows), 11)
            self.assertTrue(all(len(r) == 17 for r in rows))
            for s in v["stacks"]:
                for c in s["cells"]:
                    cell = rows[c[1]][c[0]]
                    if s["alive"]:
                        self.assertEqual(cell["stack"], s["id"])
                self.assertEqual(len(s["cells"]), 2 if s["double_wide"] else 1)
            for o in st.obstacles:
                self.assertTrue(rows[o[1]][o[0]]["obstacle"])
            occupied = sum(1 for r in rows for c in r if c["stack"] is not None)
            self.assertEqual(occupied, sum(len(s["cells"]) for s in v["stacks"] if s["alive"]))

    def test_queue(self):
        for st in all_states():
            v = P.view(st)
            self.assertEqual([q["stack"] for q in v["queue"]], list(B.round_order(st)))
            act = [q for q in v["queue"] if q["status"] == "active"]
            if v["phase"] == "active" and st.active is not None:
                self.assertEqual([q["stack"] for q in act], [st.active])
                self.assertEqual(v["queue"][[q["stack"] for q in v["queue"]].index(st.active)]["status"], "active")
            else:
                self.assertEqual(act, [])

    def test_every_legal_command_appears_exactly_once(self):
        for st in all_states():
            v = P.view(st)
            acts = v["actions"]
            seen = [e["command"] for e in acts["global"]]
            for h in acts["by_hex"]:
                if h["move"]:
                    seen.append(h["move"]["command"])
                if h["target"]:
                    if h["target"]["shoot"]:
                        seen.append(h["target"]["shoot"]["command"])
                    seen.extend(a["command"] for a in h["target"]["attacks"])
            expect = [P.command_to_dict(c) for c in B.legal_commands(st)]
            key = lambda d: json.dumps(d, sort_keys=True)  # noqa: E731
            self.assertEqual(sorted(map(key, seen)), sorted(map(key, expect)))
            self.assertEqual(len(seen), len(set(map(key, seen))))

    def test_previews_match_strike_preview(self):
        n = 0
        for st in all_states():
            v = P.view(st)
            for h in v["actions"]["by_hex"]:
                t = h["target"]
                if not t:
                    continue
                if t["shoot"]:
                    p = B.strike_preview(st, st.active, t["stack"], True)
                    self.assertEqual(t["shoot"]["preview"],
                                     {"floor": p.floor, "expected": p.expected, "ceiling": p.ceiling})
                    n += 1
                for a in t["attacks"]:
                    p = B.strike_preview(st, st.active, t["stack"], False)
                    self.assertEqual(a["preview"]["expected"], p.expected)
                    self.assertLessEqual(a["preview"]["floor"], a["preview"]["expected"])
                    self.assertLessEqual(a["preview"]["expected"], a["preview"]["ceiling"])
                    n += 1
        self.assertGreater(n, 0)

    def test_candidate_helper(self):
        n = 0
        for st in all_states():
            if st.winner is not None or st.active is None:
                continue
            legal = B.legal_commands(st)
            for r in range(B.HEIGHT):
                for c in range(B.WIDTH):
                    got = P.candidate_commands(st, (c, r))
                    for cmd in got:
                        self.assertIn(cmd, legal)
                    n += len(got)
                    ent = P.candidate_actions(st, (c, r))
                    self.assertEqual(ent is None, not got)
            # both cells of a double-wide target give the same candidates
            for s in st.stacks:
                if s.alive and s.creature.double_wide and s.side != st.stacks[st.active].side:
                    heads = [P.candidate_commands(st, x) for x in B.cells(s)]
                    self.assertEqual(heads[0], heads[1])
            # union of candidates covers every Move/Attack/Shoot
            allc = set()
            for r in range(B.HEIGHT):
                for c in range(B.WIDTH):
                    allc.update(P.candidate_commands(st, (c, r)))
            want = {c for c in legal if not isinstance(c, (B.Wait, B.Defend, B.Begin))}
            self.assertEqual(allc, want)
        self.assertGreater(n, 0)

    def test_not_started_and_over(self):
        st = golden_setup()
        v = P.view(st)
        self.assertEqual(v["phase"], "not_started")
        self.assertEqual(v["actions"]["global"], [{"command": {"type": "begin"}}])
        end = golden_states()[-1]
        self.assertEqual(P.view(end)["phase"], "over")
        self.assertEqual(P.view(end)["actions"], {"global": [], "by_hex": []})

    def test_shooter_adjacent_hides_shoot(self):
        arch = cr("arch", shots=3)
        st = B.create_battle("adj", [ss(arch, 5, pos=(7, 5))], [ss(cr("t"), 5, pos=(8, 5))])
        st, _ = B.apply(st, B.Begin(), B.battle_rng(1, "adj"))
        for h in P.view(st)["actions"]["by_hex"]:
            if h["target"]:
                self.assertIsNone(h["target"]["shoot"])


if __name__ == "__main__":
    unittest.main()
