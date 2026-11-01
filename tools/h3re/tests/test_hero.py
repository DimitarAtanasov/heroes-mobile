"""Tests for the hero core (tools/h3re/h3re/hero.py, docs/specs/hero.md)."""

import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import hero as H  # noqa: E402
from h3re.datapack import DataPackError  # noqa: E402
from h3re.rng import derive_stream  # noqa: E402

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                    "data", "hero_test.json"))


def raw():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


CONTENT = H.load_hero_pack(DATA)
SKILLS = CONTENT.rules.skills


class NoRng:
    """Commands that need no randomness must not touch the stream."""

    def __getattr__(self, name):
        raise AssertionError("rng used: %s" % name)


def hero(cls="class.warden", secondary=(), policy=H.DEFAULT_POLICY, content=CONTENT, hid="h1"):
    return H.create_hero(hid, cls, content, secondary, policy)


def resolve(s, rng, pick=lambda s: 0):
    """Answer every pending offer with ``pick(state)``; return state, events."""
    out = []
    while s.hero.offer:
        s, ev = H.apply(s, H.ChooseSkill(s.hero.id, pick(s)), rng)
        out.extend(ev)
    return s, out


def gain(s, amount, rng, pick=lambda s: 0):
    s, ev = H.apply(s, H.GainXP(s.hero.id, amount), rng)
    s, more = resolve(s, rng, pick)
    return s, list(ev) + more


def with_class(**changes):
    d = raw()
    c = next(c for c in d["classes"] if c["id"] == "class.warden")
    c.update(changes)
    return H.parse_hero_pack(d)


class PackTest(unittest.TestCase):
    def test_test_pack(self):
        r = CONTENT.rules
        # rules.md 5.2, documented for levels 1-12 only
        self.assertEqual(r.xp_table, (0, 1000, 2000, 3200, 4600, 6200, 8000, 10000,
                                      12200, 14700, 17500, 20600))
        self.assertEqual((r.max_secondary, r.skill_levels, r.primary_high_from_level),
                         (8, 3, 10))
        self.assertEqual([c.id for c in CONTENT.classes], ["class.seer", "class.warden"])
        w = H.find_class(CONTENT, "class.warden")
        self.assertEqual(w.start_primary, (2, 2, 1, 1))
        self.assertEqual(w.secondary_weights[0], ("skill.anvil", 8))
        self.assertEqual([s for s, _ in w.secondary_weights], list(SKILLS))

    def test_hash_ignores_formatting(self):
        d = raw()
        d["classes"].reverse()
        self.assertEqual(H.content_hash(H.parse_hero_pack(d)), H.content_hash(CONTENT))

    def _bad(self, mutate, needle):
        d = raw()
        mutate(d)
        with self.assertRaises(DataPackError) as cm:
            H.parse_hero_pack(d)
        self.assertIn(needle, str(cm.exception))

    def test_rejects_bad_content(self):
        self._bad(lambda d: d["xp_table"].__setitem__(3, 2000), "increasing")
        self._bad(lambda d: d["xp_table"].__setitem__(0, 5), "start at 0")
        self._bad(lambda d: d.update(xp_table=[]), "xp_table")
        self._bad(lambda d: d["classes"][0].update(primary_low=[0, 0, 0, 0]), "positive")
        self._bad(lambda d: d["classes"][0].update(start_primary=[1, 1, 1]), "expected 4")
        self._bad(lambda d: d["classes"][0]["secondary"].pop("skill.anvil"), "missing")
        self._bad(lambda d: d["classes"][0]["secondary"].update({"skill.zz": 1}), "unknown")
        self._bad(lambda d: d["classes"][0]["secondary"].update({"skill.anvil": -1}),
                  "out of range")
        self._bad(lambda d: d["skills"].append("skill.anvil"), "duplicate")
        self._bad(lambda d: d["classes"].append(copy.deepcopy(d["classes"][0])), "duplicate")
        self._bad(lambda d: d.update(primary_high_from_level=1), "out of range")
        self._bad(lambda d: d.update(schema_version=9), "schema_version")

    def test_floats_rejected_from_file(self):
        import tempfile
        text = json.dumps(raw()).replace('"max_secondary": 8', '"max_secondary": 8.0')
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "h.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            with self.assertRaises(DataPackError) as cm:
                H.load_hero_pack(p)
        self.assertIn("float", str(cm.exception))


class XpTest(unittest.TestCase):
    def test_level_for_xp(self):
        t = CONTENT.rules.xp_table
        cases = {0: 1, 999: 1, 1000: 2, 3199: 3, 3200: 4, 14700: 10, 20599: 11,
                 20600: 12, 10 ** 9: 12}
        for xp, lv in cases.items():
            self.assertEqual(H.level_for_xp(xp, t), lv, xp)

    def test_gain_without_level_draws_nothing(self):
        s, ev = H.apply(hero(), H.GainXP("h1", 999), NoRng())
        self.assertEqual(ev, (H.XPGained("h1", 999, 999),))
        self.assertEqual((s.hero.level, s.hero.xp), (1, 999))

    def test_beyond_the_table_holds_the_level(self):
        # Levels above 12 are not documented (rules.md 9.9): XP accrues, no level.
        rng = H.hero_rng(1, "h1")
        s, _ = gain(hero(), 20600, rng)
        self.assertEqual(s.hero.level, 12)
        s2, ev = H.apply(s, H.GainXP("h1", 50000), NoRng())
        self.assertEqual((s2.hero.level, s2.hero.xp), (12, 70600))
        self.assertEqual(ev, (H.XPGained("h1", 50000, 70600),))


class LevelUpTest(unittest.TestCase):
    def test_one_level(self):
        rng = H.hero_rng(5, "h1")
        s, ev = H.apply(hero(secondary=(("skill.anvil", 1),)), H.GainXP("h1", 1000), rng)
        self.assertEqual(s.hero.level, 2)
        self.assertEqual(sum((s.hero.attack, s.hero.defense, s.hero.power,
                              s.hero.knowledge)), 2 + 2 + 1 + 1 + 1)
        kinds = [type(e).__name__ for e in ev]
        self.assertEqual(kinds, ["XPGained", "LevelGained", "PrimaryGained", "SkillOffered"])
        offer = s.hero.offer
        # upgrade_and_new: an upgrade of the held skill, then a new skill
        self.assertEqual(offer[0], H.SkillOffer("skill.anvil", 2))
        self.assertEqual(offer[1].level, 1)
        self.assertNotEqual(offer[1].skill, "skill.anvil")
        self.assertEqual(ev[-1], H.SkillOffered("h1", 2, offer))

    def test_primary_tables_switch_at_level_10(self):
        c = with_class(primary_low=[1, 0, 0, 0], primary_high=[0, 0, 0, 1])
        s, _ = gain(hero(content=c), 20600, H.hero_rng(3, "h1"))
        h = s.hero
        self.assertEqual((h.level, h.attack, h.defense, h.power, h.knowledge),
                         (12, 2 + 8, 2, 1, 1 + 3))

    def test_primary_frequencies_follow_class_weights(self):
        counts = [0, 0, 0, 0]
        for i in range(300):
            s, ev = gain(hero(hid="h%d" % i), 12200, H.hero_rng(11, "h%d" % i))  # levels 2-9
            for e in ev:
                if isinstance(e, H.PrimaryGained):
                    counts[H.PRIMARY.index(e.skill)] += 1
        total = sum(counts)
        self.assertEqual(total, 300 * 8)
        for got, weight in zip(counts, (40, 30, 15, 15)):
            self.assertLess(abs(got * 100 - weight * total), 4 * total)  # within 4 points

    def test_choose_new_and_upgrade(self):
        rng = H.hero_rng(5, "h1")
        s, _ = H.apply(hero(secondary=(("skill.anvil", 1),)), H.GainXP("h1", 1000), rng)
        new = s.hero.offer[1].skill
        s1, ev = H.apply(s, H.ChooseSkill("h1", 1), rng)
        self.assertEqual(ev, (H.SkillLearned("h1", new, 1),))
        self.assertEqual(s1.hero.secondary, (H.SecondarySkill("skill.anvil", 1),
                                             H.SecondarySkill(new, 1)))
        self.assertEqual(s1.hero.offer, ())
        s2, _ = H.apply(s, H.ChooseSkill("h1", 0), rng)
        self.assertEqual(s2.hero.secondary, (H.SecondarySkill("skill.anvil", 2),))

    def test_several_levels_resolve_one_at_a_time(self):
        rng = H.hero_rng(9, "h1")
        s, ev = H.apply(hero(), H.GainXP("h1", 4600), rng)          # level 5 worth
        self.assertEqual(s.hero.level, 2)                             # waits on the offer
        levels = [s.hero.level]
        while s.hero.offer:
            s, ev = H.apply(s, H.ChooseSkill("h1", 0), rng)
            levels.append(s.hero.level)
        self.assertEqual(levels, [2, 3, 4, 5, 5])
        self.assertEqual(sum(x.level for x in s.hero.secondary), 4)   # one pick per level

    def test_zero_weight_skill_never_offered(self):
        seen = set()
        for i in range(40):
            s, ev = gain(hero(hid="z%d" % i), 20600, H.hero_rng(2, "z%d" % i),
                         pick=lambda s: len(s.hero.offer) - 1)
            for e in ev:
                if isinstance(e, H.SkillOffered):
                    seen.update(o.skill for o in e.offers)
        self.assertNotIn("skill.jade", seen)      # warden weight 0
        self.assertIn("skill.anvil", seen)

    def test_skill_cap_and_levels_hold(self):
        for i in range(20):
            s, _ = gain(hero(hid="c%d" % i), 20600, H.hero_rng(4, "c%d" % i),
                        pick=lambda s: s.hero.level % len(s.hero.offer))
            sec = s.hero.secondary
            self.assertLessEqual(len(sec), 8)
            self.assertEqual(len(set(x.skill for x in sec)), len(sec))
            self.assertTrue(all(1 <= x.level <= 3 for x in sec))
            self.assertEqual(sum(x.level for x in sec), 11)   # one pick per level 2-12


EIGHT = tuple((sk, 2) for sk in SKILLS[:8])


class OfferPolicyTest(unittest.TestCase):
    def offers(self, secondary, policy, seed=1):
        s, _ = H.apply(hero(secondary=secondary, policy=policy), H.GainXP("h1", 1000),
                       H.hero_rng(seed, "h1"))
        return s.hero.offer

    def test_full_slots_offer_upgrades_only(self):
        both = self.offers(EIGHT, H.DEFAULT_POLICY)
        self.assertEqual(len(both), 2)
        self.assertTrue(all(o.level == 3 for o in both))
        self.assertNotEqual(both[0].skill, both[1].skill)
        one = self.offers(EIGHT, H.HeroPolicy(offer_fill="single"))
        self.assertEqual(len(one), 1)
        self.assertEqual(one[0].level, 3)

    def test_no_skills_offer_new_only(self):
        both = self.offers((), H.DEFAULT_POLICY)
        self.assertEqual([o.level for o in both], [1, 1])
        self.assertNotEqual(both[0].skill, both[1].skill)
        self.assertEqual(len(self.offers((), H.HeroPolicy(offer_fill="single"))), 1)

    def test_nothing_to_offer(self):
        maxed = tuple((sk, 3) for sk in SKILLS[:8])
        s, ev = gain(hero(secondary=maxed), 4600, H.hero_rng(1, "h1"))
        self.assertEqual(s.hero.level, 5)
        self.assertFalse(any(isinstance(e, H.SkillOffered) for e in ev))

    def test_weighted_pair(self):
        pol = H.HeroPolicy(offer_mode="weighted_pair")
        seen_two_upgrades = seen_two_new = False
        for seed in range(60):
            o = self.offers((("skill.anvil", 1), ("skill.hollow", 1)), pol, seed)
            self.assertEqual(len(o), 2)
            self.assertNotEqual(o[0].skill, o[1].skill)
            seen_two_upgrades |= all(x.level == 2 for x in o)
            seen_two_new |= all(x.level == 1 for x in o)
        self.assertTrue(seen_two_upgrades and seen_two_new)
        # upgrade_and_new never offers two upgrades while a new skill is possible
        for seed in range(60):
            o = self.offers((("skill.anvil", 1), ("skill.hollow", 1)), H.DEFAULT_POLICY, seed)
            self.assertEqual([x.level for x in o], [2, 1])

    def test_policy_validation(self):
        for kw in ({"offer_mode": "x"}, {"offer_fill": "x"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                H.HeroPolicy(**kw)


class IllegalTest(unittest.TestCase):
    def test_illegal_commands_draw_nothing_and_change_nothing(self):
        rng = H.hero_rng(5, "h1")
        base = hero()
        pending, _ = H.apply(base, H.GainXP("h1", 1000), rng)
        for s, cmd, msg in ((base, H.ChooseSkill("h1", 0), "no pending"),
                            (pending, H.ChooseSkill("h1", 2), "no such offer"),
                            (pending, H.ChooseSkill("h1", True), "no such offer"),
                            (pending, H.GainXP("h1", 5), "pending"),
                            (base, H.GainXP("h2", 5), "not hero"),
                            (base, H.GainXP("h1", 0), "positive"),
                            (base, H.GainXP("h1", True), "positive"),
                            (base, object(), "unknown command")):
            with self.subTest(msg=msg):
                canon = H.canonical(s)
                with self.assertRaisesRegex(H.IllegalCommand, msg):
                    H.apply(s, cmd, NoRng())
                self.assertEqual(H.canonical(s), canon)

    def test_create_validates(self):
        for kw, msg in (({"cls": "class.none"}, "class"),
                        ({"secondary": (("skill.zz", 1),)}, "unknown skill"),
                        ({"secondary": (("skill.anvil", 1), ("skill.anvil", 2))}, "duplicate"),
                        ({"secondary": (("skill.anvil", 4),)}, "level"),
                        ({"secondary": tuple((sk, 1) for sk in SKILLS[:9])}, "at most 8")):
            with self.subTest(msg=msg), self.assertRaisesRegex(ValueError, msg):
                hero(**kw)


def golden_run(policy=H.DEFAULT_POLICY, seed=2026):
    """docs/specs/hero.md section 7: the scripted golden run."""
    s = H.create_hero("h1", "class.warden", CONTENT, (("skill.anvil", 1),), policy)
    rng = H.hero_rng(seed, "h1")
    trace = []
    for amount in (1500, 5000, 999, 16000, 3000):
        s, ev = gain(s, amount, rng, pick=lambda s: s.hero.level % len(s.hero.offer))
        trace.append(tuple(ev))
    return s, trace


class GoldenTest(unittest.TestCase):
    # First pin of the hero core (not a re-pin). Derivation: docs/specs/hero.md
    # section 7. Covers content (data/hero_test.json), policy and hero.
    PINNED = "f18f5ebb1e249b9b4f35d707add6b89a01b19310554a723d3b048a19583022f9"
    CONTENT_HASH = "2720746c773ed8ad"   # prefix of content_hash(data/hero_test.json)

    def test_golden_hash(self):
        s, trace = golden_run()
        h = s.hero
        self.assertEqual((h.level, h.xp), (12, 26499))
        self.assertEqual((h.attack, h.defense, h.power, h.knowledge), (7, 5, 4, 1))
        self.assertEqual(tuple((x.skill, x.level) for x in h.secondary), (
            ("skill.anvil", 3), ("skill.gale", 3), ("skill.brook", 2),
            ("skill.hollow", 1), ("skill.ember", 2), ("skill.ivy", 1)))
        self.assertEqual(sum(len(ev) for ev in trace), 49)
        self.assertEqual(H.state_hash(s), self.PINNED)

    def test_content_hash_prefix(self):
        # if this moves, the test pack changed: that moves PINNED too
        self.assertEqual(H.content_hash(CONTENT)[:16], self.CONTENT_HASH)

    def test_replay_is_deterministic(self):
        a, ta = golden_run()
        b, tb = golden_run()
        self.assertEqual(H.canonical(a), H.canonical(b))
        self.assertEqual(ta, tb)

    def test_seed_and_policy_change_the_run(self):
        a, ta = golden_run()
        b, tb = golden_run(seed=2027)
        self.assertNotEqual(ta, tb)
        c, _ = golden_run(H.HeroPolicy(offer_mode="weighted_pair"))
        self.assertNotEqual(H.state_hash(a), H.state_hash(c))

    def test_stream_name(self):
        a, b = H.hero_rng(7, "x"), derive_stream(7, "hero:x")
        self.assertEqual([a.next_u32() for _ in range(3)], [b.next_u32() for _ in range(3)])

    def test_state_is_immutable(self):
        s = hero()
        with self.assertRaises(Exception):
            s.hero.level = 3


if __name__ == "__main__":
    unittest.main()
