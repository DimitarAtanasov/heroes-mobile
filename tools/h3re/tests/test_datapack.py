import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import battle as B  # noqa: E402
from h3re import battle_ai as AI  # noqa: E402
from h3re import datapack as D  # noqa: E402
from h3re import rules as R  # noqa: E402


def raw():
    with open(os.path.join(D.DEFAULT_DIR, "rules.json")) as f:
        r = json.load(f)
    with open(os.path.join(D.DEFAULT_DIR, "creatures.json")) as f:
        c = json.load(f)
    return r, c


class LoadTest(unittest.TestCase):
    def test_valid_load(self):
        pack = D.load_dir()
        self.assertEqual(pack.creature_names, tuple(sorted(pack.creature_names)))
        self.assertEqual(len(pack.creatures()), 4)
        g = pack.creature("Test Glider")
        self.assertIsInstance(g, B.Creature)
        self.assertTrue(g.flyer)
        self.assertEqual(g.hates, ("Test Brute",))
        self.assertTrue(pack.creature("Test Slinger").shooter)
        with self.assertRaises(KeyError):
            pack.creature("nope")
        with self.assertRaises(TypeError):
            pack.rules["half"] = 1

    def test_json_equals_code(self):
        # Independent literal copy: editing data/rules.json (or rules.py
        # derivation) without updating this copy fails the test.
        F = Fraction
        lit = {
            "ad_bonus_per_point": F(1, 20), "ad_bonus_cap": F(3),
            "da_penalty_per_point": F(1, 40), "da_penalty_cap": F(7, 10),
            "offense": (F(0), F(1, 10), F(2, 10), F(3, 10)),
            "archery": (F(0), F(1, 10), F(1, 4), F(1, 2)),
            "armorer": (F(0), F(1, 20), F(1, 10), F(3, 20)),
            "hate_bonus": F(1, 2), "luck_bonus": F(1), "half": F(1, 2),
            "morale_die": 24, "bad_morale_numerators": (1, 2, 3),
            "vcmi_bad_morale_numerators": (2, 4, 6),
        }
        r = D.load_dir().rules
        for k, v in lit.items():
            self.assertEqual(r[k], v, k)
            self.assertEqual(getattr(R, k.upper()), v, k)
            self.assertIs(type(getattr(R, k.upper())), type(v), k)
        self.assertEqual(r["ad_bonus_per_point"], R.AD_BONUS_PER_POINT)
        self.assertEqual(r["ad_bonus_cap"], R.AD_BONUS_CAP)
        self.assertEqual(r["da_penalty_per_point"], R.DA_PENALTY_PER_POINT)
        self.assertEqual(r["da_penalty_cap"], R.DA_PENALTY_CAP)
        self.assertEqual(r["offense"], R.OFFENSE)
        self.assertEqual(r["archery"], R.ARCHERY)
        self.assertEqual(r["armorer"], R.ARMORER)
        self.assertEqual(r["hate_bonus"], R.HATE_BONUS)
        self.assertEqual(r["luck_bonus"], R.LUCK_BONUS)
        self.assertEqual(r["half"], R.HALF)
        self.assertEqual(r["morale_die"], R.MORALE_DIE)
        self.assertEqual(r["bad_morale_numerators"], R.BAD_MORALE_NUMERATORS)
        self.assertEqual(r["vcmi_bad_morale_numerators"], R.VCMI_BAD_MORALE_NUMERATORS)
        for lvl in range(-3, 4):
            self.assertEqual(R.luck_chance(lvl), Fraction(max(0, lvl), r["morale_die"]))
            self.assertEqual(R.good_morale_chance(lvl), Fraction(max(0, lvl), r["morale_die"]))
            m = -lvl
            exp = Fraction(r["bad_morale_numerators"][m - 1], r["morale_die"]) if m > 0 else 0
            self.assertEqual(R.bad_morale_chance(lvl), exp)

    def test_hash_stable(self):
        a, b = D.load_dir(), D.load_dir()
        self.assertEqual(a.content_hash, b.content_hash)
        self.assertEqual(a.content_hash,
                         hashlib.sha256(a.canonical_json.encode()).hexdigest())
        r, c = raw()
        # key order / creature order do not matter; content does
        c2 = copy.deepcopy(c)
        c2["creatures"].reverse()
        r2 = dict(reversed(list(r.items())))
        self.assertEqual(D.parse(r2, c2).content_hash, a.content_hash)
        self.assertEqual(D.parse(r2, c2).creature_names, a.creature_names)
        c3 = copy.deepcopy(c)
        c3["creatures"][0]["hp"] += 1
        self.assertNotEqual(D.parse(r, c3).content_hash, a.content_hash)

    def test_resolve_dir_and_loaded_dir(self):
        self.assertTrue(os.path.isabs(D.DEFAULT_DIR))
        self.assertEqual(D.LOADED_DIR, D.DEFAULT_DIR)
        self.assertEqual(R.RULES_DIR, D.LOADED_DIR)
        self.assertEqual(R.RULES_HASH, D.load_rules_pack_dir().content_hash)
        rel = os.path.relpath(D.DEFAULT_DIR)
        self.assertEqual(D.resolve_dir(rel), D.DEFAULT_DIR)
        with tempfile.TemporaryDirectory() as d:
            for bad in (os.path.join(d, "nope"), __file__):
                with self.assertRaisesRegex(D.DataPackError, "not a directory"):
                    D.resolve_dir(bad)
                with self.assertRaisesRegex(D.DataPackError, "not a directory"):
                    D.load_dir(bad)
                with self.assertRaisesRegex(D.DataPackError, "not a directory"):
                    D.load_rules_dir(bad)

    def test_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(D.DataPackError, "cannot read"):
                D.load_dir(d)
            r, c = raw()
            with open(os.path.join(d, "rules.json"), "w") as f:
                json.dump(r, f)
            with open(os.path.join(d, "creatures.json"), "w") as f:
                f.write("{not json")
            with self.assertRaisesRegex(D.DataPackError, "invalid JSON"):
                D.load_dir(d)
            with open(os.path.join(d, "creatures.json"), "w") as f:
                f.write('{"schema_version": 1, "creatures": [{"name": "x", "hp": 1.5}]}')
            with self.assertRaisesRegex(D.DataPackError, "floats"):
                D.load_dir(d)
            with open(os.path.join(d, "creatures.json"), "w") as f:
                f.write('{"schema_version": 1, "schema_version": 1, "creatures": []}')
            with self.assertRaisesRegex(D.DataPackError, "duplicate key"):
                D.load_dir(d)


class ValidationTest(unittest.TestCase):
    def bad(self, pattern, rmut=None, cmut=None):
        r, c = raw()
        if rmut:
            rmut(r)
        if cmut:
            cmut(c["creatures"], c)
        with self.assertRaisesRegex(D.DataPackError, pattern):
            D.parse(r, c)

    def test_rules_failures(self):
        self.bad("unknown key", lambda r: r.update(extra=1))
        self.bad("missing key", lambda r: r.pop("half"))
        self.bad("expected integer", lambda r: r.update(morale_die=24.0))
        self.bad("expected integer", lambda r: r.update(morale_die=True))
        self.bad("expected integer", lambda r: r.update(half=[1, "2"]))
        self.bad("out of range", lambda r: r.update(half=[1, 0]))
        self.bad("expected 2 items", lambda r: r.update(half=[1]))
        self.bad("expected array", lambda r: r.update(half=1))
        self.bad("out of range", lambda r: r.update(bad_morale_numerators=[1, 2, 25]))
        self.bad("non-decreasing", lambda r: r.update(bad_morale_numerators=[3, 2, 1]))
        self.bad("expected 3 items", lambda r: r.update(bad_morale_numerators=[1, 2]))
        self.bad("level 0", lambda r: r.update(offense=[[1, 10]] + r["offense"][1:]))
        self.bad("non-decreasing", lambda r: r.update(archery=[[0, 1], [1, 2], [1, 4], [1, 2]]))
        self.bad("unsupported", lambda r: r.update(schema_version=2))

    def test_creature_failures(self):
        self.bad("unknown key", cmut=lambda l, c: l[0].update(bogus=1))
        self.bad("missing key", cmut=lambda l, c: l[0].pop("hp"))
        self.bad("expected integer", cmut=lambda l, c: l[0].update(hp=1.0))
        self.bad("expected integer", cmut=lambda l, c: l[0].update(hp="3"))
        self.bad("out of range", cmut=lambda l, c: l[0].update(hp=0))
        self.bad("out of range", cmut=lambda l, c: l[0].update(attack=-1))
        self.bad("dmg_min > dmg_max", cmut=lambda l, c: l[0].update(dmg_min=9, dmg_max=3))
        self.bad("expected boolean", cmut=lambda l, c: l[0].update(flyer=1))
        self.bad("non-empty string", cmut=lambda l, c: l[0].update(name=""))
        self.bad("duplicate", cmut=lambda l, c: l[1].update(name=l[0]["name"]))
        self.bad("unknown creature", cmut=lambda l, c: l[0].update(hates=["Ghost"]))
        self.bad("unique strings", cmut=lambda l, c: l[0].update(hates=[1]))
        self.bad("must not be empty", cmut=lambda l, c: l.clear())
        self.bad("expected object", cmut=lambda l, c: l.__setitem__(0, 5))
        self.bad("unsupported", cmut=lambda l, c: c.update(schema_version=0))

    def test_weak_unit_dmg_min_zero(self):
        # Owner decision 2026-11-02: dmg_min 0 is a valid weak unit; dmg_max stays >= 1.
        r, c = raw()
        c["creatures"][0].update(dmg_min=0, dmg_max=1)
        cr = D.parse(r, c).creature(c["creatures"][0]["name"])
        self.assertEqual((cr.dmg_min, cr.dmg_max), (0, 1))
        self.bad(r"dmg_min: -1 out of range 0\.\.10000",
                 cmut=lambda l, c: l[0].update(dmg_min=-1))
        self.bad(r"dmg_max: 0 out of range 1\.\.10000",
                 cmut=lambda l, c: l[0].update(dmg_min=0, dmg_max=0))

    def test_error_type(self):
        self.assertTrue(issubclass(D.DataPackError, ValueError))

    def test_max_int_is_the_jvm_int_max(self):
        # ADR-0004: the Kotlin engine uses Int, so a pack integer is at most 2**31-1.
        self.assertEqual(D.MAX_INT, 2147483647)
        r, c = raw()
        r["half"] = [D.MAX_INT, D.MAX_INT]
        D.parse(r, c)                                  # the cap itself is accepted
        for v in (D.MAX_INT + 1, 1 << 32):
            with self.subTest(v=v):
                self.bad("out of range", lambda r: r.update(half=[v, 1]))
                self.bad("out of range", lambda r: r.update(half=[1, v]))
        p = raw_policy()
        p["defend_bonus_num"] = D.MAX_INT + 1
        with self.assertRaisesRegex(D.DataPackError, "out of range"):
            D.parse_policy(p)
        p["defend_bonus_num"] = D.MAX_INT
        D.parse_policy(p)


def raw_policy():
    with open(os.path.join(D.DEFAULT_DIR, "battle_policy.json")) as f:
        return json.load(f)


# Independent literal copy of the shipped data/battle_policy.json (rule choices
# that BattlePolicy() defaults to). Editing the file or the loader without
# updating this copy fails the test.
POLICY_LITERAL = {
    "row_offset": "even", "edge_columns_walkable": False,
    "placement_rows": ((5,), (2, 8), (2, 5, 8), (0, 4, 6, 10), (0, 2, 5, 8, 10),
                       (0, 2, 4, 6, 8, 10), (0, 2, 4, 5, 6, 8, 10)),
    "speed_tie": "attacker_first", "wait_order": "reverse_speed",
    "defend_bonus_num": 1, "defend_bonus_den": 5, "defend_bonus_min": 1,
    "defend_bonus_rounding": "floor",
    "good_morale_after_wait": False, "good_morale_after_defend": False,
    "repeat_good_morale": False,
    "bad_morale_on_wait_activation": False, "good_morale_on_wait_activation": True,
    "bad_luck": False, "range_penalty_beyond": 10, "range_origin": "head",
}


class PolicyPackTest(unittest.TestCase):
    def test_json_equals_literal_and_battle_defaults(self):
        pack = D.load_policy_pack_dir()
        self.assertEqual(dict(pack.values), dict(POLICY_LITERAL, schema_version=1))
        p = B.BattlePolicy()
        for k in POLICY_LITERAL:
            self.assertEqual(getattr(p, k), POLICY_LITERAL[k], k)
            self.assertIs(type(getattr(p, k)), type(POLICY_LITERAL[k]), k)
        self.assertEqual(p.bad_morale_table, (1, 2, 3))
        self.assertEqual(B.DEFAULT_POLICY, p)

    def test_choices_match_battle_validation(self):
        for k, allowed in D.POLICY_CHOICES.items():
            for v in allowed:
                B.BattlePolicy(**{k: v})
            with self.assertRaises(ValueError):
                B.BattlePolicy(**{k: "bogus"})

    def test_max_row_is_the_grid_height(self):
        d = raw_policy()
        d["placement_rows"][0] = [B.HEIGHT - 1]
        D.parse_policy(d)
        d["placement_rows"][0] = [B.HEIGHT]
        with self.assertRaisesRegex(D.DataPackError, "out of range"):
            D.parse_policy(d)

    def test_hash_stable_and_order_independent(self):
        a = D.load_policy_pack_dir()
        d = raw_policy()
        rev = dict(reversed(list(d.items())))
        self.assertEqual(D.parse_policy(rev).content_hash, a.content_hash)
        self.assertEqual(a.content_hash,
                         hashlib.sha256(a.canonical_json.encode()).hexdigest())
        d["range_penalty_beyond"] += 1
        self.assertNotEqual(D.parse_policy(d).content_hash, a.content_hash)
        with self.assertRaises(TypeError):
            a.values["row_offset"] = "odd"

    def test_failures(self):
        def bad(pattern, mut):
            d = raw_policy()
            mut(d)
            with self.assertRaisesRegex(D.DataPackError, pattern):
                D.parse_policy(d)
        bad("unknown key", lambda d: d.update(extra=1))
        bad("missing key", lambda d: d.pop("bad_luck"))
        bad("expected boolean", lambda d: d.update(bad_luck=0))
        bad("expected boolean", lambda d: d.update(repeat_good_morale="no"))
        bad("expected integer", lambda d: d.update(range_penalty_beyond=10.0))
        bad("expected integer", lambda d: d.update(range_penalty_beyond=True))
        bad("out of range", lambda d: d.update(defend_bonus_den=0))
        bad("out of range", lambda d: d.update(defend_bonus_num=-1))
        bad("expected one of", lambda d: d.update(row_offset="left"))
        bad("expected one of", lambda d: d.update(speed_tie=3))
        bad("expected 7 items", lambda d: d.update(placement_rows=d["placement_rows"][:6]))
        bad("expected 3 items", lambda d: d["placement_rows"].__setitem__(2, [2, 5]))
        bad("distinct", lambda d: d["placement_rows"].__setitem__(1, [2, 2]))
        bad("out of range", lambda d: d["placement_rows"].__setitem__(0, [-1]))
        bad("expected array", lambda d: d.update(placement_rows=5))
        bad("unsupported", lambda d: d.update(schema_version=2))
        with self.assertRaisesRegex(D.DataPackError, "expected object"):
            D.parse_policy([])

    def test_file_errors(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(D.DataPackError, "cannot read"):
                D.load_policy_pack_dir(d)
            path = os.path.join(d, "battle_policy.json")
            with open(path, "w") as f:
                f.write('{"schema_version": 1, "schema_version": 1}')
            with self.assertRaisesRegex(D.DataPackError, "duplicate key"):
                D.load_policy_pack_dir(d)
            with open(path, "w") as f:
                f.write('{"range_penalty_beyond": 1.5}')
            with self.assertRaisesRegex(D.DataPackError, "floats"):
                D.load_policy_pack_dir(d)


def army(pack):
    names = pack.creature_names
    return lambda: [B.StackSetup(pack.creature(n), 12 + 3 * i, morale=i % 2, luck=1)
                    for i, n in enumerate(names)]


def play(pack, seed):
    mk = army(pack)
    state = B.create_battle("dp%d" % seed, mk(), mk(), obstacles=((8, 4), (8, 5), (8, 6)))
    rng = B.battle_rng(seed, "dp%d" % seed)
    state, _ = B.apply(state, B.Begin(), rng)
    n = 0
    while state.winner is None and n < 1000:
        state, _ = B.apply(state, AI.choose(state), rng)
        n += 1
    return state, n


class BattleFromPackTest(unittest.TestCase):
    def test_runs_to_completion_deterministically(self):
        pack = D.load_dir()
        for seed in range(5):
            s1, n1 = play(pack, seed)
            s2, n2 = play(D.load_dir(), seed)
            self.assertIsNotNone(s1.winner, "seed %d unfinished" % seed)
            self.assertEqual(n1, n2)
            self.assertEqual(B.state_hash(s1), B.state_hash(s2))


if __name__ == "__main__":
    unittest.main()
