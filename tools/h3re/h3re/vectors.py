"""Cross-language conformance vectors, generated from the Python reference.

Python is authoritative (ADR-0004, docs/specs/conformance.md). This module
only *exports*; the Kotlin port (android/sim) must reproduce every value.
Output is deterministic: no timestamps, canonical JSON, sorted keys.

Usage:  python3 -m h3re.vectors [--out DIR] [--check]
"""

import argparse
import hashlib
import json
import os
import sys

from . import battle as B
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

def generate():
    """Return {filename: bytes}. Pure function of the Python implementation."""
    return {
        "rng.json": _dump(_rng_vectors()),
        "canonical_json.json": _dump(_canon_vectors()),
        "state_hash.json": _dump(_state_vectors()),
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
