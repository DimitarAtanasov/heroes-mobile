import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import vector_cache  # noqa: E402

from h3re import battle as B  # noqa: E402
from h3re import soak  # noqa: E402
from h3re import vectors_battle as VB  # noqa: E402
from h3re.rng import derive_stream  # noqa: E402


def _t(v):
    return tuple(_t(x) for x in v) if isinstance(v, list) else v


def state_from_json(text):
    """Rebuild a BattleState from its canonical text (test helper, inverse of canonical)."""
    d = json.loads(text)
    pol = B.BattlePolicy(**{k: _t(v) for k, v in d["policy"].items()})
    stacks = []
    for s in d["stacks"]:
        cr = B.Creature(**{k: _t(v) for k, v in s["creature"].items()})
        stacks.append(B.Stack(**dict({k: _t(v) for k, v in s.items()}, creature=cr)))
    heroes = tuple(None if h is None else B.Hero(**h) for h in d["heroes"])
    rest = {k: _t(v) for k, v in d.items() if k not in ("policy", "stacks", "heroes")}
    return B.BattleState(policy=pol, stacks=tuple(stacks), heroes=heroes, **rest)


def stream_at(case, skip):
    sc = case["scenario"]
    g = derive_stream(sc["master_seed"], sc["stream_domain"], sc["stream_id"])
    for _ in range(skip):
        g.next_u32()
    return g


class TestBattleVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = vector_cache.module_doc(VB)
        cls.doc = cls.out[VB.FILE]
        cls.cases = {c["name"]: c for c in cls.doc["cases"]}

    def test_generation_is_deterministic(self):
        vector_cache.assert_module_deterministic(self, VB)

    def test_is_json_serialisable_and_non_trivial(self):
        doc = self.doc
        json.dumps(doc)
        self.assertGreaterEqual(len(doc["cases"]), 10)
        steps = [s for c in doc["cases"] for s in c["steps"]]
        self.assertGreaterEqual(len(steps), 1000)
        # Every command and event type occurs in the playouts.
        cmds = {s["command"]["type"] for s in steps}
        self.assertEqual(cmds, {c.__name__ for c in VB.COMMANDS})
        evs = {e["type"] for s in steps for e in s["events"]}
        self.assertEqual(evs, {e.__name__ for e in VB.EVENTS})
        # Non-default policies are exercised and states change from step to step.
        self.assertGreaterEqual({c["scenario"]["policy"] for c in doc["cases"]},
                                {"default", "alt-order", "vcmi-like", "strict"})
        for c in doc["cases"]:
            hashes = [c["initial"]["sha256"]] + [s["sha256"] for s in c["steps"]]
            self.assertGreater(len(set(hashes)), 3, c["name"])

    def test_slice2_cases_are_kept(self):
        # The slice-2 playouts (586 steps) come first, unchanged in name and length.
        names = ["golden"] + ["%s-%d" % (p, s) for p, seeds in VB.PLAYOUTS for s in seeds]
        got = [c["name"] for c in self.doc["cases"][:len(names)]]
        self.assertEqual(got, names)
        self.assertEqual(sum(len(c["steps"]) for c in self.doc["cases"][:len(names)]), 586)

    def test_every_tie_and_wait_policy_is_played(self):
        pols = [json.loads(c["initial"]["canonical"])["policy"] for c in self.doc["cases"]]
        self.assertEqual({p["speed_tie"] for p in pols}, set(B._SPEED_TIES))
        self.assertEqual({p["wait_order"] for p in pols}, set(B._WAIT_ORDERS))

    def test_hashes_match_canonical_text(self):
        for c in self.doc["cases"]:
            for s in [c["initial"]] + c["steps"]:
                self.assertEqual(hashlib.sha256(s["canonical"].encode("ascii")).hexdigest(),
                                 s["sha256"])

    def test_golden_scripted_ends_at_the_pinned_hash(self):
        from test_battle import GoldenTest
        last = self.cases["golden-scripted"]["steps"][-1]
        self.assertEqual(last["sha256"], GoldenTest.PINNED)

    def test_stream_positions_are_consistent(self):
        for c in self.doc["cases"]:
            self.assertEqual(c["scenario"]["stream_domain"], "battle:" + c["scenario"]["battle_id"])
            u = 0
            for s in c["steps"]:
                self.assertEqual(s["rng_u32_before"], u, c["name"])
                u += s["rng_u32"]
                self.assertEqual(stream_at(c, u).state, s["rng_state_after"])
                self.assertIn(s["stage"], "ABC")

    def test_each_step_replays_from_its_own_stream_position(self):
        # What the Kotlin test does, run on the oracle itself.
        for c in self.doc["cases"]:
            prev = c["initial"]["canonical"]
            for i, s in enumerate(c["steps"]):
                state = state_from_json(prev)
                self.assertEqual(B.canonical(state).decode("ascii"), prev)
                g = stream_at(c, s["rng_u32_before"])
                new, events = B.apply(state, soak.decode_command("battle", s["command"]), g)
                self.assertEqual(B.state_hash(new), s["sha256"], "%s step %d" % (c["name"], i))
                self.assertEqual([VB._event_dict(e) for e in events], s["events"])
                self.assertEqual(g.state, s["rng_state_after"])
                prev = s["canonical"]

    def test_stages_cover_each_kind(self):
        steps = [s for c in self.doc["cases"] for s in c["steps"]]
        stages = {k: sum(1 for s in steps if s["stage"] == k) for k in "ABC"}
        self.assertTrue(all(v >= 150 for v in stages.values()), stages)
        for s in steps:
            calls = s["rng_calls"]
            if s["stage"] in "AB":
                self.assertEqual(calls["luck"] + calls["morale"], 0)
            if s["stage"] == "A":
                self.assertNotIn(s["command"]["type"], ("Attack", "Shoot"))

    def test_illegal_cases_raise_without_touching_state_or_stream(self):
        ill = self.doc["illegal_cases"]
        self.assertGreaterEqual(len(ill), 1000)
        self.assertEqual({x["error"] for x in ill}, {"IllegalCommand", "PackMismatch"})
        for x in ill:
            c = self.cases[x["case"]]
            text = (c["initial"]["canonical"] if x["after_step"] < 0
                    else c["steps"][x["after_step"]]["canonical"])
            state = state_from_json(text)
            if x["rules_hash"] is not None:
                state = B.replace(state, rules_hash=x["rules_hash"])
            g = stream_at(c, x["rng_u32_before"])
            before, h = g.state, B.state_hash(state)
            with self.assertRaises(B.IllegalCommand) as cm:
                B.apply(state, soak.decode_command("battle", x["command"]), g)
            self.assertEqual(type(cm.exception).__name__, x["error"])
            self.assertEqual(str(cm.exception), x["message"])
            self.assertEqual(g.state, before)
            self.assertEqual(B.state_hash(state), h)

    def _records(self):
        for c in self.doc["cases"]:
            yield c, c["initial"], None
            prev = c["initial"]
            for s in c["steps"]:
                yield c, s, prev
                prev = s

    def test_legal_lists_and_previews_match_the_oracle(self):
        n = 0
        for c, rec, _ in self._records():
            state = state_from_json(rec["canonical"])
            g = stream_at(c, 0)
            before = g.state
            legal = B.legal_commands(state)
            self.assertEqual(rec["legal"], [VB._jsonable(soak.encode_command(x)) for x in legal])
            self.assertEqual(rec["legal"], VB._legal_block(state)["legal"])
            self.assertEqual(g.state, before)
            self.assertEqual(B.state_hash(state), rec["sha256"])
            seen = []
            for p in rec["previews"]:
                pv = B.strike_preview(state, p["attacker"], p["target"], p["ranged"])
                self.assertEqual((p["floor"], p["expected"], p["ceiling"]),
                                 (pv.floor, pv.expected, pv.ceiling))
                self.assertLessEqual(pv.floor, pv.expected)
                self.assertLessEqual(pv.expected, pv.ceiling)
                ctx = B.strike_context(state, state.stacks[p["attacker"]],
                                       state.stacks[p["target"]], p["ranged"])
                self.assertEqual(p["ctx"], VB._jsonable(B.asdict(ctx)))
                seen.append((p["attacker"], p["target"], p["ranged"]))
                n += 1
            want = []
            for x in legal:
                if isinstance(x, (B.Attack, B.Shoot)):
                    k = (x.stack, x.target, isinstance(x, B.Shoot))
                    if k not in want:
                        want.append(k)
            self.assertEqual(seen, want)
        self.assertGreaterEqual(n, 3000)

    def test_every_recorded_command_is_in_the_previous_legal_list(self):
        checked = 0
        for c, rec, prev in self._records():
            if prev is None:
                continue
            self.assertIn(rec["command"], prev["legal"], c["name"])
            checked += 1
        self.assertGreaterEqual(checked, 1400)

    def test_illegal_cases_are_absent_from_the_legal_list(self):
        for x in self.doc["illegal_cases"]:
            if x["rules_hash"] is not None:
                continue
            c = self.cases[x["case"]]
            rec = c["initial"] if x["after_step"] < 0 else c["steps"][x["after_step"]]
            self.assertNotIn(x["command"], rec["legal"])

    def test_legal_lists_cover_every_command_kind(self):
        kinds = {x["type"] for _, r, _ in self._records() for x in r["legal"]}
        self.assertEqual(kinds, {c.__name__ for c in VB.COMMANDS})
        self.assertTrue(any(x["type"] == "Attack" and x["from_hex"] is not None
                            for _, r, _ in self._records() for x in r["legal"]))
        self.assertTrue(any(p["ranged"] for _, r, _ in self._records() for p in r["previews"]))

    def test_unit_shapes_covered(self):
        two_hex = shooter = flyer = one_hex = False
        flags = set()
        for c in self.doc["cases"]:
            st = json.loads(c["initial"]["canonical"])
            for s in st["stacks"]:
                cr = s["creature"]
                two_hex |= cr["double_wide"]
                one_hex |= not cr["double_wide"]
                shooter |= cr["shots"] > 0
                flyer |= cr["flyer"]
                flags |= {k for k, v in cr.items() if v is True}
                if cr["hates"]:
                    flags.add("hates")
        self.assertTrue(two_hex and one_hex and shooter and flyer)
        self.assertEqual(flags, {"flyer", "double_wide", "no_enemy_retaliation",
                                 "unlimited_retaliation", "no_melee_penalty", "no_range_penalty",
                                 "strikes_twice", "shoots_twice", "no_morale", "hates"})


if __name__ == "__main__":
    unittest.main()


class TestContractEdgeVectors(unittest.TestCase):
    """ADR-0008 caps and policy validation, as recorded for the Kotlin parser."""

    @classmethod
    def setUpClass(cls):
        cls.doc = vector_cache.module_doc(VB)[VB.FILE]

    def test_policy_rejects_cover_every_audited_field(self):
        cases = self.doc["policy_reject_cases"]
        fields = {c["field"] for c in cases}
        for f in ("speed_tie", "row_offset", "defend_bonus_den", "bad_morale_table",
                  "range_penalty_beyond", "placement_rows", "wait_order", "range_origin",
                  "defend_bonus_rounding", "defend_bonus_num", "defend_bonus_min"):
            self.assertIn(f, fields)
        base = dict(json.loads(json.dumps(__import__("dataclasses").asdict(B.DEFAULT_POLICY))))
        for c in cases:
            kw = dict(base)
            kw[c["field"]] = c["value"]
            with self.assertRaises(ValueError) as cm:
                B.BattlePolicy(**kw)
            self.assertEqual(str(cm.exception), c["message"])

    def test_state_rejects_are_refused_with_the_recorded_message(self):
        cases = self.doc["state_reject_cases"]
        self.assertGreaterEqual(len(cases), 25)
        labels = {c["label"] for c in cases}
        self.assertIn("count x dmg_max above cap", labels)
        self.assertIn("count x hp above cap", labels)
        for (label, bad), c in zip(VB._state_mutations(VB.cap_setup()), cases):
            self.assertEqual(label, c["label"])
            self.assertEqual(B.canonical(bad).decode("ascii"), c["canonical"])
            with self.assertRaises(ValueError) as cm:
                B.check_state(bad)
            self.assertEqual(str(cm.exception), c["message"])

    def test_cap_case_deals_more_than_int_damage(self):
        cap = next(c for c in self.doc["cases"] if c["name"] == "cap")
        dmg = [e["damage"] for s in cap["steps"] for e in s["events"]
               if e["type"] == "DamageDealt"]
        self.assertTrue(dmg)
        self.assertGreater(max(dmg), (1 << 31) - 1)
