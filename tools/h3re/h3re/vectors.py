"""Cross-language conformance vectors, generated from the Python reference.

Python is authoritative (ADR-0004, docs/specs/conformance.md). This module
only *exports*; the Kotlin port (android/sim) must reproduce every value.
Output is deterministic: no timestamps, canonical JSON, sorted keys.

Usage:  python3 -m h3re.vectors [--out DIR] [--check]
"""

import argparse
import dataclasses
import hashlib
import json
import os
import sys
from fractions import Fraction

from . import battle as B
from . import rules as R
from .rng import Pcg32, derive_stream

VECTOR_FORMAT = 1
DEFAULT_OUT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "android", "sim", "src", "test",
    "resources", "vectors"))

_M64 = (1 << 64) - 1


def _dump(obj):
    """Vector file bytes: sorted keys, compact, ASCII (ensure_ascii), LF-terminated."""
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


# --------------------------------------------------------------------------
# rng
# --------------------------------------------------------------------------

def _ops(n, tag):
    """A deterministic mixed op script, chosen by a fixed driver stream."""
    drv = derive_stream(0x5EED, "vectors:ops", tag)
    ranges = [(0, 1), (0, 2), (0, 6), (1, 7), (-5, 5), (0, 1000), (3, 3 + (1 << 31) + 1),
              (0, (1 << 32) - 1), (0, 1 << 32), (-(1 << 40), -(1 << 40) + 977),
              (10, 10 + 3_000_000_000)]
    chances = [(0, 5), (-3, 5), (5, 5), (9, 5), (1, 2), (1, 3), (2, 7), (999, 1000), (1, 1 << 30)]
    out = []
    for _ in range(n):
        k = drv.range(0, 4)
        if k == 0:
            out.append(["u32"])
        elif k == 1:
            lo, hi = ranges[drv.range(0, len(ranges))]
            out.append(["range", lo, hi])
        elif k == 2:
            lo, hi = ranges[drv.range(0, len(ranges))]
            out.append(["randint", lo, hi - 1])
        else:
            num, den = chances[drv.range(0, len(chances))]
            out.append(["chance", num, den])
    return out


def _run(g, ops):
    res = []
    for op in ops:
        if op[0] == "u32":
            res.append(g.next_u32())
        elif op[0] == "range":
            res.append(g.range(op[1], op[2]))
        elif op[0] == "randint":
            res.append(g.randint(op[1], op[2]))
        else:
            res.append(g.chance(op[1], op[2]))
    return res


def _rng_vectors():
    pcg = []
    for seed, seq in [(42, 54), (0, 0), (1, 0), (0, 1), (12345, 7), (_M64, _M64 >> 1),
                      (0xDEADBEEFCAFEBABE, 0x0123456789ABCDEF), (1 << 63, 1 << 62)]:
        g = Pcg32(seed, seq)
        pcg.append({"seed": seed, "seq": seq, "state": g.state, "inc": g.inc,
                    "u32": [g.next_u32() for _ in range(1000)]})
    pcg_ops = []
    for i, (seed, seq) in enumerate([(42, 54), (7, 0), (_M64, 3), (99, _M64 >> 1)]):
        ops = _ops(1000, "pcg%d" % i)
        pcg_ops.append({"seed": seed, "seq": seq, "ops": ops, "out": _run(Pcg32(seed, seq), ops)})

    derived = []
    long_s = "x" * 300
    cases = [
        (12345, "battle:7", "a"), (12345, "battle:7", ""), (12345, "", ""), (0, "", ""),
        (12345, "", "id-only"), (1, "map-gen", ""), (1, "weekly", "2"), (1, "ai:1", ""),
        (-1, "battle:golden", ""), (-(1 << 63), "d", "i"), (-(1 << 63) - 1, "d", "i"),
        ((1 << 63) - 1, "d", "i"), (1 << 63, "d", "i"), (1 << 64, "d", "i"),
        (1 << 70, "d", "i"), (-(1 << 70), "d", "i"), (255, "é", "ü"), (256, "日本語", "ID"),
        (7, "emoji:\U0001F600", "\U0001F680x"), (7, "nul:\x00", "\x00"), (7, long_s, long_s),
        (7, "a", "bc"), (7, "ab", "c"),
    ]
    for master, dom, ident in cases:
        g = derive_stream(master, dom, ident)
        entry = {"master": master, "domain": dom, "id": ident, "state": g.state, "inc": g.inc}
        ops = _ops(1000, "d:%s|%s|%s" % (master, dom, ident))
        # The ops were drawn from a separate stream; results come from a fresh stream.
        entry["ops"] = ops
        entry["out"] = _run(g, ops)
        derived.append(entry)
    return {"format": VECTOR_FORMAT, "pcg32_u32": pcg, "pcg32_ops": pcg_ops, "derived": derived,
            "published": {"seed": 42, "seq": 54,
                          "u32": [0xA15C02B7, 0x7B47F409, 0xBA1D3330, 0x83D2F293,
                                  0xBFA4784B, 0xCBED606E]}}


# --------------------------------------------------------------------------
# canonical json
# --------------------------------------------------------------------------

def _canon_corpus():
    big = (1 << 53) + 1
    return [
        ("null", None), ("true", True), ("false", False), ("zero", 0), ("neg_one", -1),
        ("int_2_53_plus_1", big), ("int_neg_2_53_minus_1", -big),
        ("int_i64_max", (1 << 63) - 1), ("int_i64_min", -(1 << 63)),
        ("int_u64_max", (1 << 64) - 1), ("int_beyond_u64", 1 << 100), ("int_neg_beyond", -(1 << 100)),
        ("empty_string", ""), ("empty_list", []), ("empty_map", {}),
        ("nested_empty", {"a": [], "b": {}, "c": [[], {}]}),
        ("ascii_escapes", "quote\" back\\ nl\n cr\r tab\t bs\b ff\f"),
        ("control_chars", "".join(chr(i) for i in range(32))),
        ("del_char", "a\x7fb"),
        ("slash", "a/b"),
        ("latin1", "café ÿ"),
        ("bmp", "日本語    � ￿"),
        ("astral", "\U0001F600 \U00010000 \U0010FFFF"),
        ("unicode_key", {"é": 1, "e": 2, "z": 3}),
        ("key_order_basic", {"b": 1, "a": 2, "B": 3, "A": 4, "": 5, "aa": 6, "a ": 7}),
        ("key_order_digits", {"10": 1, "9": 2, "1": 3, "2": 4}),
        # code point order differs from UTF-16 code unit order for astral vs U+E000..U+FFFF
        ("key_order_astral", {"\U0001F600": 1, "￿": 2, "": 3, "\U00010000": 4, "Ā": 5}),
        ("key_escapes", {"a\"b": 1, "a\nb": 2, "é": 3}),
        ("list_order_kept", [3, 1, 2, [9, 8], {"z": 1, "a": 2}]),
        ("nested", {"stacks": [{"id": 0, "pos": [1, 2], "creature": {"name": "pike", "flags": [True, False, None]}},
                               {"id": 1, "pos": [-1, 2 ** 64], "creature": {"name": "é", "flags": []}}],
                    "winner": None, "round": 3, "z": {"b": {"d": 1, "c": 2}, "a": []}}),
        ("deep", [[[[[[[[[[1]]]]]]]]]]),
        ("tuple_like_list", [1, [2, 3], []]),
    ]


def _canon_vectors():
    out = []
    for name, value in _canon_corpus():
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        out.append({"name": name, "value": value, "hex": data.hex(),
                    "sha256": hashlib.sha256(data).hexdigest()})
    return {"format": VECTOR_FORMAT, "cases": out}


# --------------------------------------------------------------------------
# state hash (battle golden scenario, built through the public battle API)
# --------------------------------------------------------------------------

def _cr(name, attack, defense, dmg, hp, speed, **kw):
    return B.Creature(name, attack, defense, dmg[0], dmg[1], hp, speed, **kw)


def golden_setup():
    """Mirror of tests/test_battle.py golden_setup() (kept in step by hand;
    a divergence only changes these vectors, never the Python pin)."""
    pike = _cr("pikeman", 4, 5, (1, 3), 10, 4)
    archer = _cr("archer", 6, 3, (2, 3), 10, 4, shots=12)
    wolf = _cr("wolf", 7, 5, (2, 5), 15, 8, strikes_twice=True)
    gnoll = _cr("gnoll", 6, 7, (2, 4), 13, 6, double_wide=True, hates=("pikeman",))
    return B.create_battle(
        "golden",
        [B.StackSetup(pike, 30, morale=1, luck=1), B.StackSetup(archer, 20, morale=2)],
        [B.StackSetup(wolf, 15, morale=-1, luck=2), B.StackSetup(gnoll, 25, morale=1)],
        obstacles=[(7, 3), (8, 5), (9, 7), (6, 8)],
        heroes=(B.Hero(attack=2, defense=1, offense=1, archery=2), B.Hero(defense=2, armorer=1)),
    )


def _state_vectors():
    cases = []
    st = golden_setup()
    cases.append(("golden_initial", st))
    rng = B.battle_rng(12345, "golden")
    st2, _ = B.apply(st, B.Begin(), rng)
    cases.append(("golden_after_begin", st2))
    out = []
    for name, s in cases:
        data = B.canonical(s)
        out.append({"name": name, "canonical": data.decode("ascii"),
                    "sha256": B.state_hash(s)})
    return {"format": VECTOR_FORMAT, "cases": out}


# --------------------------------------------------------------------------
# rules: battle damage (rules.md 6.5-6.6), from the public API of rules.py.
# Exact values are [numerator, denominator] pairs, reduced, denominator > 0.
# --------------------------------------------------------------------------

_DIFFS = (-61, -60, -59, -29, -28, -27, -1, 0, 1, 2, 27, 28, 29, 59, 60, 61)
_STACK_COUNTS = (1, 2, 9, 10, 11, 12, 1000)
_DET_POLICIES = (R.RollPolicy.PESSIMAL, R.RollPolicy.EXPECTED, R.RollPolicy.OPTIMAL)


def _pair(x):
    f = Fraction(x)
    return [f.numerator, f.denominator]


def _u64(g):
    return (g.next_u32() << 32) | g.next_u32()


def _ctx_json(c):
    return dataclasses.asdict(c)


def _clamp_attack(a):
    return max(0, min(255, a))


class _Scripted:
    """Roll source that replays a fixed list of randint results in order.

    Each result must lie in the requested bounds, and the script must be used up
    exactly, so a case also pins how many dice base_damage draws."""

    def __init__(self, rolls):
        self._rolls = list(rolls)
        self._i = 0

    def randint(self, lo, hi):
        if self._i >= len(self._rolls):
            raise AssertionError("script exhausted")
        v = self._rolls[self._i]
        self._i += 1
        if not lo <= v <= hi:
            raise AssertionError("scripted roll %d outside [%d, %d]" % (v, lo, hi))
        return v

    def chance(self, num, den):
        raise AssertionError("base_damage must not draw a chance")

    def finished(self):
        return self._i == len(self._rolls)


def _rand_ctx(drv):
    count = (_STACK_COUNTS[drv.range(0, len(_STACK_COUNTS))] if drv.range(0, 3) == 0
             else drv.range(1, 61))
    lo = 1 if drv.range(0, 4) == 0 else drv.range(1, 41)
    hi = lo + drv.range(0, 26)
    defense = drv.range(0, 256)
    diff = (_DIFFS[drv.range(0, len(_DIFFS))] if drv.range(0, 2) == 0
            else drv.range(-100, 101))
    ranged = drv.range(0, 2) == 0
    return R.DamageCtx(
        count=count, dmg_min=lo, dmg_max=hi,
        attack=_clamp_attack(defense + diff), defense=defense,
        ranged=ranged,
        offense=drv.range(0, 4), archery=drv.range(0, 4), armorer=drv.range(0, 4),
        hates=drv.range(0, 4) == 0,
        range_penalty=ranged and drv.range(0, 2) == 0,
        wall_penalty=ranged and drv.range(0, 2) == 0,
        melee_penalty=(not ranged) and drv.range(0, 2) == 0,
        luck=drv.range(-4, 5), bad_luck=drv.range(0, 2) == 0)


def _rules_edge_contexts():
    C = R.DamageCtx
    out = [
        C(count=1, dmg_min=1, dmg_max=1, attack=0, defense=0),
        C(count=1, dmg_min=1, dmg_max=1, attack=0, defense=255),   # 0.3 floors to 0: minimum 1
        C(count=1, dmg_min=1, dmg_max=1, attack=255, defense=0),   # attack bonus at its cap
        C(count=1, dmg_min=1, dmg_max=1, attack=0, defense=255, melee_penalty=True),
        C(count=1, dmg_min=3, dmg_max=3, attack=0, defense=0, ranged=True,
          range_penalty=True, wall_penalty=True),                  # 3 / 4 floors to 0: minimum 1
        C(count=1000, dmg_min=1, dmg_max=1, attack=0, defense=255),
        C(count=1000, dmg_min=10000, dmg_max=10000, attack=255, defense=0, ranged=True,
          archery=3, armorer=3, range_penalty=True, wall_penalty=True, hates=True,
          luck=3, bad_luck=True),
        C(count=1000, dmg_min=1, dmg_max=10000, attack=255, defense=0, luck=5),
        C(count=65537, dmg_min=2, dmg_max=3, attack=10, defense=20, offense=2),
    ]
    for n in (1, 10, 11, 1000):
        for diff in (-29, -28, -27, 59, 60, 61):
            out.append(C(count=n, dmg_min=5, dmg_max=9, attack=max(0, 100 + diff),
                         defense=100))
        for diff in (59, 60, 61):
            out.append(C(count=n, dmg_min=5, dmg_max=9, attack=diff, defense=0, archery=3,
                         ranged=True, range_penalty=True))
    for n in (1, 11):
        for luck in (-5, -3, -1, 0, 1, 3, 5):
            for bad in (False, True):
                out.append(C(count=n, dmg_min=2, dmg_max=7, attack=10, defense=10,
                             luck=luck, bad_luck=bad))
    return out


def _rules_contexts():
    drv = derive_stream(0x5EED, "vectors:rules", "ctx")
    return _rules_edge_contexts() + [_rand_ctx(drv) for _ in range(180)]


def _pack_json():
    return {
        "ad_bonus_cap": _pair(R.AD_BONUS_CAP),
        "ad_bonus_per_point": _pair(R.AD_BONUS_PER_POINT),
        "archery": [_pair(x) for x in R.ARCHERY],
        "armorer": [_pair(x) for x in R.ARMORER],
        "bad_morale_numerators": list(R.BAD_MORALE_NUMERATORS),
        "da_penalty_cap": _pair(R.DA_PENALTY_CAP),
        "da_penalty_per_point": _pair(R.DA_PENALTY_PER_POINT),
        "half": _pair(R.HALF),
        "hate_bonus": _pair(R.HATE_BONUS),
        "luck_bonus": _pair(R.LUCK_BONUS),
        "morale_die": R.MORALE_DIE,
        "offense": [_pair(x) for x in R.OFFENSE],
        "vcmi_bad_morale_numerators": list(R.VCMI_BAD_MORALE_NUMERATORS),
    }


def _attack_defense_vectors():
    out = []
    for base, span in ((0, 255), (100, 100)):
        for diff in range(-span, span + 1):
            a = base + max(diff, 0)
            d = base + max(-diff, 0)
            inc, red = R.attack_defense_factor(a, d)
            out.append({"attack": a, "defense": d, "inc": _pair(inc), "red": _pair(red)})
    return out


def _base_damage_vectors():
    drv = derive_stream(0x5EED, "vectors:rules", "base")
    out = []
    for _ in range(150):
        count = (_STACK_COUNTS[drv.range(0, len(_STACK_COUNTS))] if drv.range(0, 3) == 0
                 else drv.range(1, 61))
        lo = drv.range(1, 41)
        hi = lo + drv.range(0, 26)
        n = min(count, 10) if count > 0 else 0
        rolls = [drv.range(lo, hi + 1) for _ in range(n)]
        script = _Scripted(rolls)
        val = R.base_damage(count, lo, hi, script)
        if not script.finished():
            raise AssertionError("base_damage left scripted rolls unused")
        out.append({"count": count, "dmg_min": lo, "dmg_max": hi, "rolls": rolls, "out": val})
    # Explicit edges: stacks of 1, 10, 11, 1000; all-min and all-max rolls; minimum damage 1.
    explicit = [
        (1, 1, 1, [1]),
        (1, 4, 4, [4]),
        (10, 1, 6, [6] * 10),
        (10, 1, 6, [1] * 10),
        (11, 1, 6, [1] * 10),
        (11, 1, 6, [6] * 10),
        (1000, 1, 1, [1] * 10),
        (1000, 3, 9, [9] * 10),
        (1000, 3, 9, [3] * 10),
        (2 ** 20, 1, 1, [1] * 10),
        (0, 1, 3, []),
        (0, 0, 0, []),
        (-4, 1, 3, []),
    ]
    for count, lo, hi, rolls in explicit:
        script = _Scripted(rolls)
        val = R.base_damage(count, lo, hi, script)
        if not script.finished():
            raise AssertionError("base_damage left scripted rolls unused")
        out.append({"count": count, "dmg_min": lo, "dmg_max": hi, "rolls": rolls, "out": val})
    for count, lo, hi in ((5, 0, 3), (5, 4, 3), (1, -1, 1)):
        if not _raises_value_error(lambda: R.base_damage(count, lo, hi, _Scripted([]))):
            raise AssertionError("expected ValueError for base_damage(%d, %d, %d)" % (count, lo, hi))
        out.append({"count": count, "dmg_min": lo, "dmg_max": hi, "rolls": [], "error": True})
    return out


def _raises_value_error(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def _damage_from_base_kwargs(drv):
    ranged = drv.range(0, 2) == 0
    return {
        "ranged": ranged,
        "offense": drv.range(0, 4), "archery": drv.range(0, 4), "armorer": drv.range(0, 4),
        "lucky": drv.range(0, 2) == 0, "hates": drv.range(0, 4) == 0,
        "range_penalty": ranged and drv.range(0, 2) == 0,
        "wall_penalty": ranged and drv.range(0, 2) == 0,
        "melee_penalty": (not ranged) and drv.range(0, 2) == 0,
    }


def _damage_from_base_vectors():
    drv = derive_stream(0x5EED, "vectors:rules", "dfb")
    out = []
    for _ in range(200):
        kw = _damage_from_base_kwargs(drv)
        base = drv.range(-2, 3000)
        defense = drv.range(0, 256)
        diff = (_DIFFS[drv.range(0, len(_DIFFS))] if drv.range(0, 2) == 0
                else drv.range(-100, 101))
        attack = _clamp_attack(defense + diff)
        out.append(dict(kw, base=base, attack=attack, defense=defense,
                        out=R.damage_from_base(base, attack, defense, **kw)))
    # Flag combinations that must be refused, and the cases where a check is skipped.
    bad = [
        (dict(base=10, attack=0, defense=0, ranged=True, melee_penalty=True), True),
        (dict(base=10, attack=0, defense=0, range_penalty=True), True),
        (dict(base=10, attack=0, defense=0, wall_penalty=True), True),
        (dict(base=10, attack=0, defense=0, offense=4), True),
        (dict(base=10, attack=0, defense=0, ranged=True, archery=-1), True),
        (dict(base=10, attack=0, defense=0, armorer=4), True),
        # base <= 0 returns before the flag checks, and ranged ignores the offense level.
        (dict(base=0, attack=0, defense=0, ranged=True, melee_penalty=True), False),
        (dict(base=0, attack=0, defense=0, offense=4), False),
        (dict(base=10, attack=0, defense=0, ranged=True, offense=4), False),
    ]
    for params, expect_error in bad:
        entry = dict(params)
        for k, v in (("ranged", False), ("offense", 0), ("archery", 0), ("armorer", 0),
                     ("lucky", False), ("hates", False), ("range_penalty", False),
                     ("wall_penalty", False), ("melee_penalty", False)):
            entry.setdefault(k, v)
        call = {k: v for k, v in entry.items() if k not in ("base", "attack", "defense")}
        fn = lambda: R.damage_from_base(entry["base"], entry["attack"], entry["defense"], **call)
        if expect_error:
            if not _raises_value_error(fn):
                raise AssertionError("expected ValueError for %r" % (entry,))
            out.append(dict(entry, error=True))
        else:
            out.append(dict(entry, out=fn()))
    return out


def _resolve_vectors(contexts):
    out = []
    for c in contexts:
        for pol in _DET_POLICIES:
            r = R.resolve_damage(c, pol)
            out.append({"ctx": _ctx_json(c), "policy": pol.name, "damage": r.damage,
                        "lucky": r.lucky, "unlucky": r.unlucky})
    # Errors raised by the same checks on the deterministic policies.
    err_ctx = [
        R.DamageCtx(count=3, dmg_min=0, dmg_max=2, attack=0, defense=0),
        R.DamageCtx(count=5, dmg_min=4, dmg_max=3, attack=0, defense=0),
        R.DamageCtx(count=2, dmg_min=1, dmg_max=2, attack=0, defense=0, offense=4),
        R.DamageCtx(count=2, dmg_min=1, dmg_max=2, attack=0, defense=0, ranged=True,
                    melee_penalty=True),
        R.DamageCtx(count=2, dmg_min=1, dmg_max=2, attack=0, defense=0, wall_penalty=True),
    ]
    for c in err_ctx:
        for pol in _DET_POLICIES:
            if not _raises_value_error(lambda: R.resolve_damage(c, pol)):
                raise AssertionError("expected ValueError for %r" % (c,))
            out.append({"ctx": _ctx_json(c), "policy": pol.name, "error": True})
    # A zero-count stack returns before the skill and damage checks, after the luck draws.
    zero = R.DamageCtx(count=0, dmg_min=0, dmg_max=0, attack=0, defense=0, armorer=4)
    for pol in _DET_POLICIES:
        r = R.resolve_damage(zero, pol)
        out.append({"ctx": _ctx_json(zero), "policy": pol.name, "damage": r.damage,
                    "lucky": r.lucky, "unlucky": r.unlucky})
    return out


def _resolve_seeded_vectors(contexts):
    drv = derive_stream(0x5EED, "vectors:rules", "seed")
    out = []
    for c in contexts:
        seed = _u64(drv)
        seq = _u64(drv)
        g = Pcg32(seed, seq)
        r = R.resolve_damage(c, R.RollPolicy.ACTUAL_SEED, g)
        out.append({"ctx": _ctx_json(c), "seed": seed, "seq": seq, "damage": r.damage,
                    "lucky": r.lucky, "unlucky": r.unlucky, "state_after": g.state})
    # Seeded error: the stack has no damage range, so base_damage refuses after the luck draws.
    bad = R.DamageCtx(count=3, dmg_min=0, dmg_max=2, attack=0, defense=0, luck=2)
    if not _raises_value_error(lambda: R.resolve_damage(bad, R.RollPolicy.ACTUAL_SEED,
                                                       Pcg32(1, 0))):
        raise AssertionError("expected ValueError for seeded resolve")
    out.append({"ctx": _ctx_json(bad), "seed": 1, "seq": 0, "error": True})
    return out


def _preview_vectors(contexts):
    out = []
    for c in contexts:
        p = R.preview_damage(c)
        out.append({"ctx": _ctx_json(c), "floor": p.floor, "expected": p.expected,
                    "ceiling": p.ceiling})
    return out


def _chance_vectors():
    luck = [{"luck": v, "out": _pair(R.luck_chance(v))} for v in range(-5, 6)]
    good = [{"morale": v, "out": _pair(R.good_morale_chance(v))} for v in range(-5, 6)]
    bad = []
    for table in (list(R.BAD_MORALE_NUMERATORS), list(R.VCMI_BAD_MORALE_NUMERATORS),
                  [0, 0, 0], [1, 2, 24], [24, 24, 24], [0, 12, 24]):
        for m in range(-4, 5):
            bad.append({"morale": m, "table": table,
                        "out": _pair(R.bad_morale_chance(m, table))})
    # Invalid tables are refused only when a morale penalty actually reads them.
    for table in ([3, 2, 1], [1, 2], [1, 2, 25], [-1, 0, 0], [1, 2, 3, 4]):
        if not _raises_value_error(lambda: R.bad_morale_chance(-1, table)):
            raise AssertionError("expected ValueError for table %r" % (table,))
        bad.append({"morale": -1, "table": table, "error": True})
    bad.append({"morale": 0, "table": [3, 2, 1], "out": _pair(R.bad_morale_chance(0, [3, 2, 1]))})
    return luck, good, bad


def _penalty_vectors():
    out = []
    combos = ((False, False, False, False), (False, False, False, True),
              (True, False, False, False), (True, True, False, False),
              (True, False, True, False), (True, True, True, False))
    for ranged, range_p, wall_p, melee_p in combos:
        for base in (1, 2, 3, 7, 1000, 1048576, 2 ** 31 - 1):
            out.append({"base": base, "ranged": ranged, "range_penalty": range_p,
                        "wall_penalty": wall_p, "melee_penalty": melee_p,
                        "out": R.damage_from_base(base, 0, 0, ranged=ranged,
                                                  range_penalty=range_p, wall_penalty=wall_p,
                                                  melee_penalty=melee_p)})
    return out


def _rules_vectors():
    contexts = _rules_contexts()
    luck, good, bad = _chance_vectors()
    return {
        "format": VECTOR_FORMAT,
        "pack": _pack_json(),
        "attack_defense": _attack_defense_vectors(),
        "base_damage": _base_damage_vectors(),
        "damage_from_base": _damage_from_base_vectors(),
        "resolve": _resolve_vectors(contexts),
        "resolve_seeded": _resolve_seeded_vectors(contexts),
        "preview": _preview_vectors(contexts),
        "luck_chance": luck,
        "good_morale_chance": good,
        "bad_morale_chance": bad,
        "penalties": _penalty_vectors(),
    }


# --------------------------------------------------------------------------

def generate():
    """Return {filename: bytes}. Pure function of the Python implementation."""
    return {
        "rng.json": _dump(_rng_vectors()),
        "canonical_json.json": _dump(_canon_vectors()),
        "state_hash.json": _dump(_state_vectors()),
        "rules.json": _dump(_rules_vectors()),
    }


def write(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, data in generate().items():
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(data)


def check(out_dir):
    """Names of files that differ from a fresh generation."""
    bad = []
    for name, data in generate().items():
        p = os.path.join(out_dir, name)
        if not os.path.exists(p) or open(p, "rb").read() != data:
            bad.append(name)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m h3re.vectors")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true", help="fail if files differ from a fresh generation")
    a = ap.parse_args(argv)
    if a.check:
        bad = check(a.out)
        if bad:
            print("stale vector files: " + ", ".join(bad), file=sys.stderr)
            return 1
        print("vectors up to date")
        return 0
    write(a.out)
    print("wrote %d files to %s" % (len(generate()), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
