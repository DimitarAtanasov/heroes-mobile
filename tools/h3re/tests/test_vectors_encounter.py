import hashlib
import json
import os
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import test_adventure as TA  # noqa: E402
import test_encounter as TE  # noqa: E402
import vector_cache  # noqa: E402

from h3re import adventure as A  # noqa: E402
from h3re import battle as B  # noqa: E402
from h3re import encounter as E  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_encounter as VE  # noqa: E402
from h3re.rng import derive_stream  # noqa: E402

ENC_PIN = "512b53ca56c4c5611e718b4b23129984ab5a3c0f6e0de4a7feb48c620568bd60"
ADV_PIN = "179c570020d05be9a53c265a76517a4bb9f398c92f37d19485d30f804f703420"


def _floats(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(_floats(v) for v in x.values())
    if isinstance(x, list):
        return any(_floats(v) for v in x)
    return False


class VectorsEncounterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = vector_cache.module_doc(VE)[VE.FILE]
        cls.cases = {c["name"]: c for c in cls.doc["cases"]}

    def test_shape_and_no_floats(self):
        d = self.doc
        self.assertEqual(d["format"], 1)
        self.assertFalse(_floats(d))
        self.assertEqual(set(d), {"format", "description", "packs", "constants", "cases", "variants",
                                  "check_game", "setups", "auto_cases", "streams", "golden"})
        self.assertGreaterEqual(len(d["cases"]), 25)
        self.assertGreaterEqual(sum(len(c["steps"]) for c in d["cases"]), 700)
        self.assertGreaterEqual(len(d["variants"]), 25)
        self.assertGreaterEqual(len(d["auto_cases"]), 300)
        self.assertGreaterEqual(len(d["setups"]), 45)
        self.assertGreaterEqual(len(d["check_game"]), 14)

    def test_deterministic(self):
        if "vectors_encounter" in V.EXTRA_VECTOR_MODULES:
            vector_cache.assert_module_deterministic(self, VE)
        else:
            self.assertEqual(V._dump(VE.generate()[VE.FILE]), V._dump(self.doc))

    def test_on_disk_vector_is_current(self):
        path = os.path.join(V.DEFAULT_OUT, VE.FILE)
        self.assertTrue(os.path.exists(path), "encounter.json missing: run python3 -m h3re.vectors_encounter")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), V._dump(self.doc))

    def test_no_python_random(self):
        with open(VE.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("import random", src)
        self.assertNotIn("from random", src)

    def test_goldens(self):
        g = self.doc["golden"]
        self.assertEqual(g["hash"], ENC_PIN)
        self.assertEqual(g["pin"], ENC_PIN)
        self.assertEqual(TE.GoldenTest.PINNED, ENC_PIN)
        self.assertEqual((g["day"], g["battles"]), (3, 4))
        self.assertEqual(g["winners"], [B.ATTACKER, B.DEFENDER, B.DEFENDER, B.DEFENDER])
        self.assertEqual(self.cases["golden"]["steps"][-1]["sha256"], ENC_PIN)
        s, _ = TE.play(TE.golden_game())
        self.assertEqual(A.state_hash(s), ENC_PIN)
        a, _ = TA.play_days(TA.golden_setup())
        self.assertEqual(A.state_hash(a), ADV_PIN)

    def test_games_equal_the_test_suite_games(self):
        self.assertEqual(A.canonical(VE.golden_game()), A.canonical(TE.golden_game()))
        self.assertEqual(VE.GOLDEN_SCRIPT, TE.GOLDEN_SCRIPT)
        self.assertEqual(VE.CREATURES, TE.CREATURES)

    def test_steps_hash_to_their_text(self):
        for c in self.doc["cases"]:
            texts = [c["initial"]["canonical"]]
            self.assertEqual(hashlib.sha256(texts[0].encode("ascii")).hexdigest(), c["initial"]["sha256"])
            for s in c["steps"]:
                if "canonical" in s:
                    self.assertEqual(hashlib.sha256(s["canonical"].encode("ascii")).hexdigest(), s["sha256"])
                    texts.append(s["canonical"])
                else:
                    self.assertIn("error", s)
            self.assertGreater(len(set(texts)), 2, c["name"])

    def test_coverage(self):
        steps = [s for c in self.doc["cases"] for s in c["steps"]]
        ev = {e["type"] for s in steps for e in s.get("events", [])}
        self.assertTrue({"BattleFought", "ArmyChanged", "HeroDefeated", "GuardDefeated", "HeroMoved"} <= ev)
        fought = [e for s in steps for e in s.get("events", []) if e["type"] == "BattleFought"]
        self.assertGreaterEqual(len(fought), 100)
        self.assertEqual({e["winner"] for e in fought}, {0, 1, None})
        self.assertTrue(any(isinstance(e["target"], str) for e in fought))
        self.assertTrue(any(isinstance(e["target"], int) for e in fought))
        # a limited battle ends at its round limit with no winner
        self.assertTrue(any(e["winner"] is None and e["rounds"] in (1, 3, 4, 100) for e in fought))
        self.assertGreaterEqual(len({e["rounds"] for e in fought}), 5)
        # the battle logs use every command kind the auto-combat picks
        kinds = {c["type"] for e in fought for c in e["log"]}
        self.assertTrue({"Begin", "Move", "Attack", "Defend"} <= kinds)
        msgs = {s["error"] for s in steps if "error" in s}
        for want in ("game not started", "hero does not belong to the current player",
                     "hero is not on the map", "no such hero", "no such target hero",
                     "target hero is not on the map", "cannot attack an own hero", "no such guard",
                     "target is not next to the hero", "target must be a hero id or a guard id",
                     "battles are not enabled in this game"):
            self.assertIn(want, msgs)
        # both streams are exercised
        self.assertEqual({s["stream"] for s in steps}, {"battle", "adventure"})
        self.assertTrue(all("battle_sha256" in s for s in steps if s["stream"] == "battle" and "canonical" in s))

    def test_cases_replay_and_battle_logs_replay_on_the_named_stream(self):
        games = VE.all_games()
        self.assertEqual(set(games), set(self.cases))
        for name, (state, seed) in games.items():
            c = self.cases[name]
            self.assertEqual(A.canonical(state).decode("ascii"), c["initial"]["canonical"], name)
            for s in c["steps"]:
                cmd = VE.decode(s["command"])
                rng = E.stream_for(seed, state, cmd)
                if "error" in s:
                    with self.assertRaises(A.IllegalCommand) as cm:
                        A.apply(state, cmd, rng)
                    self.assertEqual(str(cm.exception), s["error"])
                    self.assertEqual([rng.state, rng.inc], s["rng_after"])
                    continue
                if isinstance(cmd, A.Attack):
                    bs = E.build_battle(state, cmd)
                    self.assertEqual(B.state_hash(bs), s["battle_sha256"])
                    f = s["events"][0]
                    brng = B.battle_rng(seed, bs.battle_id)
                    for bc in f["log"]:
                        bs, _ = B.apply(bs, VE.decode_battle(bc), brng)
                    self.assertEqual(B.state_hash(bs), f["battle_hash"])
                    self.assertEqual(bs.winner, f["winner"])
                state, _ = A.apply(state, cmd, rng)
                self.assertEqual(A.state_hash(state), s["sha256"])
                self.assertEqual([rng.state, rng.inc], s["rng_after"])

    def test_adventure_stream_is_never_drawn(self):
        for c in self.doc["cases"]:
            for s in c["steps"]:
                if s["stream"] == "adventure":
                    g = derive_stream(c["seed"], "adventure:%s" % c["game_id"])
                    self.assertEqual(s["rng_after"], [g.state, g.inc], c["name"])

    def test_variants_cover_every_rejection(self):
        msgs = set()
        ok = 0
        for v in self.doc["variants"]:
            self.assertEqual(hashlib.sha256(v["canonical"].encode("ascii")).hexdigest(), v["sha256"])
            for a in v["attempts"]:
                if "error" in a:
                    msgs.add(a["error"])
                else:
                    ok += 1
        self.assertGreaterEqual(ok, 10)
        for want in ("battles are not enabled in this game", "game not started",
                     "game rules_hash 0000000000000000000000000000000000000000000000000000000000000000 "
                     "differs from the local rules pack %s" % E.rules.RULES_HASH,
                     "no content for creature 'ghost'", "no content for creature 'wolf'",
                     "battle cannot be set up: invalid damage range",
                     "battle cannot be set up: invalid stack setup",
                     "battle cannot be set up: stack 0 cannot be placed at (1, 99)",
                     "battle cannot be set up: stack 1 cannot be placed at (1, 5)",
                     "battle cannot be set up: count x dmg_max exceeds 2**31-1",
                     "battle cannot be set up: count x hp exceeds 2**31-1",
                     "battle cannot be set up: defense sum out of range"):
            self.assertIn(want, msgs)

    def test_check_game_cases(self):
        errs = [c["error"] for c in self.doc["check_game"]]
        self.assertGreaterEqual(sum(e is None for e in errs), 3)
        self.assertIn("hero 2: no creature 'ghost' with speed 4 in the setup", errs)
        self.assertIn("guard 'camp': no creature 'ghost' with speed 4 in the setup", errs)
        self.assertTrue(any(e and e.startswith("guard \"o'k\"") for e in errs))

    def test_setup_cases(self):
        by = {c["name"]: c for c in self.doc["setups"]}
        self.assertEqual(by["default"]["canonical"], json.dumps(
            VE.jsonable(VE.setup_of(VE.CREATURES)), sort_keys=True, separators=(",", ":")))
        self.assertEqual(by["creatures-reversed"]["canonical"], by["default"]["canonical"])
        self.assertEqual(by["duplicate-creature"]["error"], "duplicate creature name")
        self.assertEqual(by["policy-loser_fate-'x'"]["error"], "bad loser_fate")
        self.assertEqual(by["policy-round_limit-True"]["error"], "round_limit must be an int >= 1")
        self.assertEqual(by["order-policy-before-duplicate"]["error"], "bad loser_fate")
        self.assertEqual(by["order-battle-policy-before-duplicate"]["error"], "bad speed_tie")
        self.assertIsNone(by["policy-round_limit-4611686018427387904"]["error"])
        uni = json.loads(by["creatures-unicode-unsorted"]["canonical"])
        self.assertEqual([c["name"] for c in uni["creatures"]], list(VE.UNI_NAMES))

    def test_auto_cases(self):
        kinds = {a["command"]["type"] for a in self.doc["auto_cases"]}
        self.assertEqual(kinds, {"Begin", "Move", "Attack", "Shoot", "Defend"})
        stalls = [a for a in self.doc["auto_cases"] if a["stall"]]
        self.assertGreaterEqual(len(stalls), 5)
        self.assertTrue(all(a["command"]["type"] == "Defend" for a in stalls))
        for a in self.doc["auto_cases"][::25]:
            self.assertEqual(hashlib.sha256(a["battle"].encode("ascii")).hexdigest(), a["sha256"])

    def test_streams(self):
        for s in self.doc["streams"]:
            self.assertEqual(s["battle_id"], json.loads(s["canonical"])["game_id"] + ":" +
                             str(json.loads(s["canonical"]).get("battles", 0) + 1))
            g = derive_stream(s["seed"], "battle:%s" % s["battle_id"])
            self.assertEqual(s["battle_draws"], [g.next_u32() for _ in range(4)])

    def test_reverse_inputs_and_round_limit(self):
        a, _ = TE.play(VE.golden_game())
        b, _ = TE.play(VE.golden_game(reverse_inputs=True))
        self.assertEqual(A.canonical(a), A.canonical(b))
        s = A.apply(VE.draw_game(E.EncounterPolicy(round_limit=3)), A.Begin(), TE.Untouchable())[0]
        s2, ev = TE.step(s, A.Attack(0, 1))
        self.assertEqual((ev[0].winner, ev[0].rounds), (None, 3))
        self.assertEqual(replace(s2, battles=0).heroes, s.heroes)


if __name__ == "__main__":
    unittest.main()
