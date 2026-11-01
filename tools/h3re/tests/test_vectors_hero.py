import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import hero as H  # noqa: E402
from h3re import vectors as V  # noqa: E402
from h3re import vectors_hero as VH  # noqa: E402

PINNED = "f18f5ebb1e249b9b4f35d707add6b89a01b19310554a723d3b048a19583022f9"   # test_hero.GoldenTest
CONTENT_HASH_PREFIX = "2720746c773ed8ad"
CAP = 2 ** 31 - 1
_DOC = None


def doc():
    global _DOC
    if _DOC is None:
        _DOC = VH.generate()[VH.FILE]
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


class VectorsHeroTest(unittest.TestCase):
    def test_shape_and_no_floats(self):
        d = doc()
        self.assertEqual(d["format"], 1)
        self.assertFalse(_floats(d))
        self.assertEqual(set(d), {"format", "packs", "pack_valid", "pack_invalid", "level_for_xp",
                                  "policies", "create", "streams", "traces", "offer_sweep", "states",
                                  "golden"})
        self.assertGreaterEqual(len(d["traces"]), 100)
        self.assertGreaterEqual(len(d["pack_invalid"]), 150)
        self.assertGreaterEqual(len(d["pack_valid"]), 15)
        self.assertGreaterEqual(len(d["states"]), 80)
        self.assertGreaterEqual(len(d["offer_sweep"]), 300)

    def test_deterministic(self):
        self.assertEqual(V._dump(VH.generate()[VH.FILE]), V._dump(doc()))

    def test_on_disk_vector_is_current(self):
        path = os.path.join(V.DEFAULT_OUT, VH.FILE)
        self.assertTrue(os.path.exists(path), "hero.json missing: run python3 -m h3re.vectors_hero")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), V._dump(doc()))

    def test_no_python_random(self):
        with open(VH.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("import random", src)
        self.assertNotIn("from random", src)

    def test_golden_and_content_hash(self):
        g = doc()["golden"]
        self.assertEqual(g["hash"], PINNED)
        self.assertEqual(g["content_hash"][:16], CONTENT_HASH_PREFIX)
        self.assertEqual((g["level"], g["xp"], g["events"], g["primary"]), (12, 26499, 49, [7, 5, 4, 1]))
        with open(os.path.join(VH.D._REPO_DIR, "hero_test.json"), encoding="utf-8") as f:
            self.assertEqual(doc()["packs"]["test"], f.read())

    def test_packs_are_all_valid_and_valid_cases_hash(self):
        for name, text in doc()["packs"].items():
            self.assertIsNone(VH._run_pack(text)[0], name)
        by = {c["name"]: c for c in doc()["pack_valid"]}
        for c in doc()["pack_valid"]:
            err, content = VH._run_pack(c["text"])
            self.assertIsNone(err, c["name"])
            self.assertEqual(H.content_hash(content), c["hash"], c["name"])
            if "same_hash_as" in c:
                self.assertEqual(c["hash"], by[c["same_hash_as"]]["hash"])
        self.assertEqual(by["test-file"]["hash"][:16], CONTENT_HASH_PREFIX)
        # boundary: totals exactly at the cap are accepted
        self.assertIn("totals-at-cap", by)
        self.assertIn("single-weight-at-cap", by)

    def test_invalid_packs_reproduce_and_cover_every_category(self):
        cats = set()
        for c in doc()["pack_invalid"]:
            err, _ = VH._run_pack(c["text"])
            self.assertEqual(err, c["message"], c["name"])
            self.assertEqual(VH.classify_pack(err), c["category"], c["name"])
            cats.add(c["category"])
        self.assertEqual(cats, {"invalid_json", "duplicate_key", "float", "type", "unknown_key",
                                "missing_key", "range", "length", "schema_version", "table", "empty",
                                "duplicate_name", "total"})

    def test_every_pack_rejection_message_is_covered(self):
        needles = ("expected object", "unknown key(s)", "missing key(s)", "unsupported", "out of range",
                   "expected integer, got bool", "expected integer, got str", "expected integer, got NoneType",
                   "expected integer, got list", "expected integer, got dict", "expected array",
                   "must not be empty", "must start at 0", "must be strictly increasing",
                   "expected non-empty string", "duplicate skill", "duplicate class",
                   "weights must have a positive total", "weight total", "expected 4 items",
                   "floats are not allowed", "duplicate key", "invalid JSON",
                   "hero.xp_table[", "hero.skills[", "hero.max_secondary", "hero.skill_levels",
                   "hero.primary_high_from_level", ".id:", ".start_primary[", ".primary_low[",
                   ".primary_high[", ".secondary.", ".secondary:", "hero.classes[1]")
        msgs = [c["message"] for c in doc()["pack_invalid"]]
        for n in needles:
            self.assertTrue(any(n in m for m in msgs), n)

    def test_create_cases_reproduce(self):
        cats = set()
        for c in doc()["create"]:
            pol = H.HeroPolicy(**c["policy"])
            try:
                s = H.create_hero(c["hero"], c["class"], VH.CONTENT[c["pack"]], [tuple(p) for p in c["secondary"]], pol)
            except ValueError as e:
                self.assertEqual(c["error"], {"message": str(e), "category": VH._create_error_category(str(e))})
                cats.add(c["error"]["category"])
                continue
            self.assertEqual(c["hash"], H.state_hash(s), c["name"])
            self.assertEqual(c["canonical"], H.canonical(s).decode("ascii"))
        self.assertEqual(cats, {"unknown_class", "unknown_skill", "duplicate_skill", "bad_level", "too_many"})

    def test_policy_cases(self):
        errs = [c for c in doc()["policies"] if "message" in c]
        self.assertGreaterEqual(len(errs), 5)
        self.assertGreaterEqual(len(doc()["policies"]) - len(errs), 4)
        self.assertTrue(any(c["message"].startswith("bad offer_mode") for c in errs))
        self.assertTrue(any(c["message"].startswith("bad offer_fill") for c in errs))

    def test_streams_reproduce(self):
        for c in doc()["streams"]:
            r = H.hero_rng(c["seed"], c["hero"])
            self.assertEqual(r.state, c["state"])
            self.assertEqual([r.range(0, 1000) for _ in range(3)] + [r.range(0, CAP), r.range(0, 1 << 32)],
                             c["draws"])
            self.assertEqual(r.state, c["after"])

    def test_traces_replay_in_python(self):
        for t in doc()["traces"]:
            s = H.create_hero(t["hero"], t["class"], VH.CONTENT[t["pack"]],
                              [tuple(p) for p in t["secondary"]], H.HeroPolicy(**t["policy"]))
            rng = H.hero_rng(t["seed"], t["hero"])
            self.assertEqual((H.state_hash(s), rng.state), (t["initial_hash"], t["initial_rng"]), t["name"])
            for i, st in enumerate(t["steps"]):
                c = st["cmd"]
                cmd = H.GainXP(c["hero"], c["amount"]) if c["type"] == "GainXP" else H.ChooseSkill(c["hero"], c["index"])
                before = (H.state_hash(s), rng.state)
                if "error" in st:
                    with self.assertRaises(H.IllegalCommand) as cm:
                        H.apply(s, cmd, rng)
                    self.assertEqual(str(cm.exception), st["error"])
                    self.assertEqual((H.state_hash(s), rng.state), before)
                else:
                    s, ev = H.apply(s, cmd, rng)
                    self.assertEqual([VH._ev(e) for e in ev], st["events"], (t["name"], i))
                self.assertEqual((H.state_hash(s), rng.state), (st["hash"], st["rng"]), (t["name"], i))
            self.assertEqual(H.canonical(s).decode("ascii"), t["final_canonical"])

    def test_illegal_steps_leave_hash_and_stream_unchanged(self):
        n = 0
        for t in doc()["traces"]:
            prev = (t["initial_hash"], t["initial_rng"])
            for st in t["steps"]:
                if "error" in st:
                    n += 1
                    self.assertEqual((st["hash"], st["rng"]), prev)
                prev = (st["hash"], st["rng"])
        self.assertGreaterEqual(n, 100)

    # ---- coverage of the contract ----

    def test_policies_classes_seeds(self):
        ts = doc()["traces"]
        self.assertEqual({(t["policy"]["offer_mode"], t["policy"]["offer_fill"]) for t in ts},
                         {(m, f) for m in ("upgrade_and_new", "weighted_pair") for f in ("other_kind", "single")})
        self.assertEqual({t["class"] for t in ts if t["pack"] == "test"}, {"class.seer", "class.warden"})
        self.assertGreaterEqual(len({t["seed"] for t in ts if t["name"].startswith("random-test")}), 3)

    def test_past_the_end_of_the_table(self):
        final = [json.loads(t["final_canonical"])["hero"] for t in doc()["traces"] if t["pack"] == "test"]
        self.assertTrue(any(h["level"] == 12 and h["xp"] > 20600 for h in final))
        self.assertTrue(any(s["cmd"]["type"] == "GainXP" and "events" in s and len(s["events"]) == 1
                            and s["events"][0]["xp"] > 20600 for _, s in _steps()))

    def test_all_eight_slots_full(self):
        self.assertTrue(any(len(t["secondary"]) == 8 for t in doc()["traces"]))
        full = [json.loads(t["final_canonical"])["hero"] for t in doc()["traces"] if t["pack"] == "test"]
        self.assertTrue(any(len(h["secondary"]) == 8 for h in full))
        # a full maxed hero: levels pass with no SkillOffered at all
        quiet = [t for t in doc()["traces"] if t["name"].startswith("no-offers")]
        self.assertEqual(len(quiet), 2)
        for t in quiet:
            kinds = [e["type"] for s in t["steps"] if "events" in s for e in s["events"]]
            self.assertEqual(kinds.count("LevelGained"), 11)
            self.assertNotIn("SkillOffered", kinds)

    def test_zero_weight_skills_never_offered(self):
        zero = {"class.seer": "skill.ivy", "class.warden": "skill.jade"}
        offered = set()
        for t, s in _steps():
            if t["pack"] != "test":
                continue
            for e in s.get("events", ()):
                if e["type"] == "SkillOffered":
                    offered.update((t["class"], o["skill"]) for o in e["offers"])
        for cls, skill in zero.items():
            self.assertNotIn((cls, skill), offered)
        self.assertIn(("class.warden", "skill.anvil"), offered)
        # the tiny pack has a zero-weight skill for the mage too
        self.assertFalse(any(e["type"] == "SkillOffered" and any(o["skill"] == "skill.b" for o in e["offers"])
                             for t, s in _steps() if t["class"] == "class.mage" for e in s.get("events", ())))

    def test_every_legal_choose_index(self):
        idx = {}
        for t in doc()["traces"]:
            if t["name"].startswith("branch-"):
                idx.setdefault(t["name"].rsplit("-idx", 1)[0], set()).add(int(t["name"].rsplit("-idx", 1)[1]))
        self.assertTrue(idx)
        self.assertTrue(any(v == {0, 1} for v in idx.values()))
        self.assertTrue(any(v == {0} for v in idx.values()))     # a single offer (offer_fill=single)
        for t, s in _steps():
            if s["cmd"]["type"] == "ChooseSkill" and "events" in s:
                self.assertEqual(s["events"][0]["type"], "SkillLearned")

    def test_multi_level_gain_stops_at_each_level(self):
        t = next(t for t in doc()["traces"] if t["name"] == "stops-4600")
        lv = [e["level"] for s in t["steps"] for e in s.get("events", ()) if e["type"] == "SkillOffered"]
        self.assertEqual(lv, [2, 3, 4, 5])
        t = next(t for t in doc()["traces"] if t["name"].startswith("stops-warden-upgrade_and_new-other_kind-first"))
        lv = [e["level"] for s in t["steps"] for e in s.get("events", ()) if e["type"] == "SkillOffered"]
        self.assertEqual(lv, list(range(2, 13)))

    def test_draw_order_primary_then_offers(self):
        for _, s in _steps():
            kinds = [e["type"] for e in s.get("events", ())]
            for i, k in enumerate(kinds):
                if k == "LevelGained":
                    self.assertEqual(kinds[i + 1], "PrimaryGained")
                if k == "SkillOffered":
                    self.assertEqual(kinds[i - 1], "PrimaryGained")

    def test_xp_cap_boundary(self):
        errs = [s["error"] for _, s in _steps() if "error" in s and "XP would exceed" in s["error"]]
        self.assertGreaterEqual(len(errs), 6)
        self.assertTrue(all(e == "XP would exceed %d" % CAP for e in errs))
        reached = [s for _, s in _steps() if "events" in s and s["events"]
                   and s["events"][0]["type"] == "XPGained" and s["events"][0]["xp"] == CAP]
        self.assertGreaterEqual(len(reached), 3)
        for name in ("cap-exact-from-zero", "cap-then-more", "cap-minus-one", "cap-tiny-pack"):
            t = next(t for t in doc()["traces"] if t["name"] == name)
            amounts = [s["cmd"]["amount"] for s in t["steps"] if s["cmd"]["type"] == "GainXP"]
            self.assertTrue(CAP in amounts or CAP - 1 in amounts, name)
        t = next(t for t in doc()["traces"] if t["name"] == "cap-exact-from-zero")
        self.assertEqual(t["steps"][0]["cmd"]["amount"], CAP + 1)
        self.assertIn("error", t["steps"][0])
        self.assertIn("events", t["steps"][2])

    def test_weight_totals_at_the_cap(self):
        names = {c["name"] for c in doc()["pack_invalid"]}
        for n in ("primary_low-total-above-cap", "primary_high-total-above-cap",
                  "secondary-total-cap-plus-one", "secondary-total-above-cap"):
            self.assertIn(n, names)
        self.assertTrue(any(t["pack"] == "bigweights" for t in doc()["traces"]))
        big = [c for c in doc()["states"] if c["name"].startswith("total-at-cap")]
        self.assertEqual(len(big), 3)
        self.assertTrue(all("events" in c for c in big))

    def test_non_ascii_hero_ids(self):
        us = [t for t in doc()["traces"] if t["hero"] == VH.UNI_HERO]
        self.assertGreaterEqual(len(us), 8)
        for t in us:
            self.assertNotIn(VH.UNI_HERO, t["final_canonical"])        # escaped, pure ASCII
            self.assertIn("\\ud83d\\ude00", t["final_canonical"])
            t["final_canonical"].encode("ascii")

    def test_unicode_pack_sorts_by_code_point(self):
        c = VH.CONTENT["unicode"]
        self.assertEqual(c.rules.skills, tuple(sorted(VH.UNI_SKILLS)))
        self.assertEqual(c.rules.skills[-1], "skill.\U00010000")       # after U+FFEE: not UTF-16 order
        self.assertEqual([x.id for x in c.classes][-1], "class.\U0001F600")

    def test_hand_built_states(self):
        bad = [c for c in doc()["states"] if c["name"].startswith("bad-")]
        self.assertGreaterEqual(len(bad), 30)
        for c in bad:
            self.assertIn("weights", c["error"], c["name"])
            self.assertEqual(c["rng_after"], c["rng_before"], c["name"])
        for c in doc()["states"]:
            text = json.dumps(c["state"], sort_keys=True, separators=(",", ":")).encode("ascii")
            self.assertEqual(hashlib.sha256(text).hexdigest(), c["hash"], c["name"])
            if "error" in c:
                self.assertEqual(c["rng_after"], c["rng_before"], c["name"])
            else:
                self.assertIn("hash_after", c)
        unused = [c for c in doc()["states"] if c["name"].startswith("unused-")]
        self.assertEqual(len(unused), 6)
        self.assertTrue(all("events" in c for c in unused))

    def test_offer_sweep_reproduces(self):
        for c in doc()["offer_sweep"][::7]:
            s = H.create_hero("h1", c["class"], VH.CONTENT["test"], [tuple(p) for p in c["secondary"]],
                              H.HeroPolicy(**c["policy"]))
            s, _ = H.apply(s, H.GainXP("h1", 1000), H.hero_rng(c["seed"], "h1"))
            self.assertEqual([[o.skill, o.level] for o in s.hero.offer], c["offer"])
            self.assertEqual(H.state_hash(s), c["hash"])


if __name__ == "__main__":
    unittest.main()
