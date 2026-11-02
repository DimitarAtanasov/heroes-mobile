import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import adventure as A  # noqa: E402
from h3re import town as T  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_town as VT  # noqa: E402

PINNED = "0360ce8861ca3b4a12f8210f0d8111b57c328becb8c433d41c59d6a6d257aae7"   # test_town.GoldenTest.PINNED
GROWTH_PINNED = "b4108c58f2e6e95cbaa19fbfb7694e66a74067558840c614cbffc71c96549322"
CONTENT_HASH_PREFIX = "629836f9f419a851"
CAP = 2 ** 31 - 1
_DOC = None


def doc():
    global _DOC
    if _DOC is None:
        _DOC = VT.generate()[VT.FILE]
    return _DOC


def _floats(x):
    if isinstance(x, float):
        return True
    if isinstance(x, dict):
        return any(_floats(v) for v in x.values())
    if isinstance(x, list):
        return any(_floats(v) for v in x)
    return False


def _steps():
    for t in doc()["traces"]:
        for s in t["steps"]:
            yield t, s


def _err(e):
    return {"kind": type(e).__name__, "message": str(e)}


class NoRng:
    def __getattr__(self, name):
        raise AssertionError("rng used: %s" % name)


def _cmd(c):
    return T.NewDay() if c["type"] == "NewDay" else T.Build(c["player"], c["town"], c["building"])


class VectorsTownTest(unittest.TestCase):
    def test_shape_and_no_floats(self):
        d = doc()
        self.assertEqual(d["format"], 1)
        self.assertFalse(_floats(d))
        self.assertEqual(set(d), {"format", "packs", "pack_valid", "pack_invalid", "policies", "weekly_growth",
                                  "streams", "create", "traces", "queries", "states", "golden"})
        self.assertGreaterEqual(len(d["traces"]), 70)
        self.assertGreaterEqual(len(d["pack_invalid"]), 200)
        self.assertGreaterEqual(len(d["pack_valid"]), 30)
        self.assertGreaterEqual(len(d["states"]), 80)
        self.assertGreaterEqual(len(d["create"]), 150)
        self.assertGreaterEqual(len(d["weekly_growth"]), 1000)

    def test_deterministic(self):
        self.assertEqual(V._dump(VT.generate()[VT.FILE]), V._dump(doc()))

    def test_on_disk_vector_is_current(self):
        path = os.path.join(V.DEFAULT_OUT, VT.FILE)
        self.assertTrue(os.path.exists(path), "town.json missing: run python3 -m h3re.vectors_town")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), V._dump(doc()))

    def test_no_python_random(self):
        with open(VT.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("import random", src)
        self.assertNotIn("from random", src)

    def test_source_is_ascii(self):
        # invisible and non-ASCII characters are written as escapes so a reviewer can see them
        with open(VT.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertEqual([c for c in src if ord(c) > 0x7e or (ord(c) < 0x20 and c != "\n")], [])

    def test_golden_pins(self):
        g = doc()["golden"]
        self.assertEqual(g["hash"], PINNED)
        self.assertEqual(g["growth_digest"], GROWTH_PINNED)
        self.assertEqual(g["content_hash"][:16], CONTENT_HASH_PREFIX)
        self.assertEqual((g["day"], g["events"]), (8, 24))
        self.assertEqual(g["pools"], [["north:dwelling1", 0, 23], ["north:dwelling2", 0, 10], ["south:dwelling1", 0, 13],
                                      ["south:dwelling2", 0, 9], ["east:dwelling1", 0, 17], ["east:dwelling2", 0, 7]])
        with open(os.path.join(VT.D._REPO_DIR, "towns_test.json"), encoding="utf-8") as f:
            self.assertEqual(doc()["packs"]["test"], f.read())

    def test_packs_are_all_valid_and_valid_cases_hash(self):
        for name, text in doc()["packs"].items():
            self.assertIsNone(VT._run_pack(text)[0], name)
        by = {c["name"]: c for c in doc()["pack_valid"]}
        for c in doc()["pack_valid"]:
            err, content = VT._run_pack(c["text"])
            self.assertIsNone(err, c["name"])
            self.assertEqual(T.content_hash(content), c["hash"], c["name"])
            if "same_hash_as" in c:
                self.assertEqual(c["hash"], by[c["same_hash_as"]]["hash"], c["name"])
        self.assertEqual(by["test-file"]["hash"][:16], CONTENT_HASH_PREFIX)
        self.assertNotEqual(by["growth-bonus-unreduced"]["hash"], by["test-file"]["hash"])
        self.assertIn("resources-at-cap", by)
        self.assertIn("growth-bonus-at-cap", by)

    def test_invalid_packs_reproduce_and_cover_every_category(self):
        cats = set()
        for c in doc()["pack_invalid"]:
            err, _ = VT._run_pack(c["text"])
            self.assertEqual(err, c["message"], c["name"])
            self.assertEqual(VT.classify_pack(err), c["category"], c["name"])
            cats.add(c["category"])
        self.assertEqual(cats, {"invalid_json", "duplicate_key", "float", "type", "unknown_key", "missing_key", "range",
                                "length", "schema_version", "empty", "duplicate_name", "unknown_building", "upgrade",
                                "cycle", "player_unique", "dwelling", "horde"})

    def test_every_pack_rejection_message_is_covered(self):
        needles = ("expected object", "unknown key(s)", "missing key(s)", "unsupported", "out of range",
                   "expected integer, got bool", "expected integer, got str", "expected integer, got NoneType",
                   "expected integer, got list", "expected integer, got dict", "expected array", "expected boolean",
                   "must not be empty", "expected non-empty string", "requires: duplicate entry", "duplicate building",
                   "duplicate faction", "unknown building", "must also be required", "upgraded by more than one",
                   "requirement cycle", "is also on a building it requires", "a dwelling needs a fort",
                   "a dwelling upgrades only a dwelling of its level", "more than one base dwelling",
                   "only a dwelling may upgrade a dwelling", "has no dwelling", "expected 2 items",
                   "floats are not allowed", "duplicate key", "invalid JSON", "towns.factions[1]", ".growth_bonus[",
                   ".dwelling.", ".horde.", ".income.", ".cost.")
        msgs = [c["message"] for c in doc()["pack_invalid"]]
        for n in needles:
            self.assertTrue(any(n in m for m in msgs), n)

    def test_policy_and_weekly_cases(self):
        errs = [c for c in doc()["policies"] if "message" in c]
        self.assertGreaterEqual(len(errs), 15)
        for c in doc()["weekly_growth"]:
            try:
                r = T.weekly_growth(c["base"], tuple(c["bonus"]), c["horde"], T.TownPolicy(c["mode"]))
            except ZeroDivisionError as e:
                self.assertEqual(c["error"], _err(e))
            else:
                self.assertEqual(c["result"], r)
        self.assertEqual(sum(1 for c in doc()["weekly_growth"] if "error" in c), 6)

    def test_create_cases_reproduce(self):
        msgs = set()
        for c in doc()["create"]:
            try:
                s = T.create_game(c["game_id"], VT.CONTENT[c["pack"]], VT._mk_players(c["players"]),
                                  VT._mk_towns(c["towns"]), T.TownPolicy(**c["policy"]))
            except ValueError as e:
                self.assertEqual(c["error"], _err(e), c["name"])
                msgs.add(str(e).split(":")[0][:30])
                continue
            self.assertEqual(c["hash"], T.state_hash(s), c["name"])
            self.assertEqual(c["canonical"], T.canonical(s).decode("ascii"))
        self.assertGreaterEqual(len(msgs), 12)
        names = {c["name"] for c in doc()["create"]}
        for n in ("resource-gold-true", "resource-gems-false", "town-owner-true", "town-built-string", "owner-huge",
                  "game-id-none", "unique-two-in-one-town", "treasury-at-cap", "players-empty"):
            self.assertIn(n, names)

    def test_streams_reproduce(self):
        for c in doc()["streams"]:
            r = T.town_rng(c["seed"], c["game_id"])
            self.assertEqual(r.state, c["state"])
            self.assertEqual([r.range(0, 1000) for _ in range(3)] + [r.range(0, CAP), r.range(0, 1 << 32)], c["draws"])
            self.assertEqual(r.state, c["after"])

    def test_traces_replay_in_python(self):
        for t in doc()["traces"]:
            s = T.create_game(t["game_id"], VT.CONTENT[t["pack"]], VT._mk_players(t["players"]), VT._mk_towns(t["towns"]),
                              T.TownPolicy(**t["policy"]))
            rng = T.town_rng(t["seed"], t["game_id"])
            self.assertEqual((T.state_hash(s), rng.state), (t["initial_hash"], t["initial_rng"]), t["name"])
            for i, st in enumerate(t["steps"]):
                before = (T.state_hash(s), rng.state)
                if "error" in st:
                    with self.assertRaises((T.IllegalCommand, KeyError)) as cm:
                        T.apply(s, _cmd(st["cmd"]), rng)
                    self.assertEqual(st["error"], _err(cm.exception), (t["name"], i))
                    self.assertEqual((T.state_hash(s), rng.state), before)
                else:
                    s, ev = T.apply(s, _cmd(st["cmd"]), rng)
                    self.assertEqual([VT._ev(e) for e in ev], st["events"], (t["name"], i))
                self.assertEqual((T.state_hash(s), rng.state), (st["hash"], st["rng"]), (t["name"], i))
            self.assertEqual(T.canonical(s).decode("ascii"), t["final_canonical"])

    def test_illegal_steps_leave_hash_and_stream_unchanged(self):
        n = 0
        for t in doc()["traces"]:
            prev = (t["initial_hash"], t["initial_rng"])
            for st in t["steps"]:
                if "error" in st:
                    n += 1
                    self.assertEqual((st["hash"], st["rng"]), prev)
                prev = (st["hash"], st["rng"])
            self.assertEqual(t["initial_rng"], prev[1], t["name"])      # the stream is never touched
        self.assertGreaterEqual(n, 500)

    def test_queries_reproduce(self):
        n = 0
        for t in doc()["traces"][::5]:
            s = T.create_game(t["game_id"], VT.CONTENT[t["pack"]], VT._mk_players(t["players"]), VT._mk_towns(t["towns"]),
                              T.TownPolicy(**t["policy"]))
            for q in t["initial_queries"]:
                self.assertEqual(VT._q(s, q["fn"], *q["args"]), q)
                n += 1
        self.assertGreater(n, 100)
        errs = [c["query"]["error"]["kind"] for c in doc()["queries"] if "error" in c["query"]]
        self.assertEqual(set(errs), {"IllegalCommand", "KeyError"})

    def test_hand_built_states(self):
        kinds = set()
        for c in doc()["states"]:
            text = json.dumps(c["state"], sort_keys=True, separators=(",", ":")).encode("ascii")
            self.assertEqual(hashlib.sha256(text).hexdigest(), c["hash"], c["name"])
            self.assertEqual(c["rng_after"], c["rng_before"], c["name"])
            if "error" in c:
                kinds.add(c["error"]["kind"])
                self.assertNotIn("hash_after", c)
            elif "cmd" in c:
                self.assertIn("hash_after", c)
            for q in c["queries"]:
                if "error" in q:
                    kinds.add("q:" + q["error"]["kind"])
        self.assertEqual(kinds, {"IllegalCommand", "KeyError", "q:KeyError", "q:ZeroDivisionError"})

    def test_hand_built_edge_cases_are_present(self):
        names = {c["name"] for c in doc()["states"]}
        for n in ("duplicate-town-ids-both-get-the-building", "two-active-dwellings-one-level", "zero-denominator-active",
                  "unknown-faction-build-elsewhere-unique-escapes-as-key-error", "big-day-newday", "built-today-flag",
                  "unicode-sorts-by-code-point-on-build"):
            self.assertIn(n, names)

    def test_python_core_never_touches_the_stream(self):
        s = T.create_game("g", VT.CONTENT["test"], [A.Resources(gold=10 ** 5)], [T.TownSetup("t", "faction.fernwood", 0)])
        T.apply(s, T.Build(0, "t", "hall.1"), NoRng())
        T.apply(s, T.NewDay(), NoRng())


if __name__ == "__main__":
    unittest.main()
