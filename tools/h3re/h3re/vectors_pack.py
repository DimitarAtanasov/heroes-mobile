"""Data-pack loader conformance vectors (the Kotlin `Datapack` port), from the Python reference.

``generate()`` returns ``{vector file name: JSON-serialisable content}``; the
orchestrator wires it into ``vectors.generate()`` (which owns serialisation).
Python (``datapack.py``) is authoritative (ADR-0004, docs/specs/conformance-datapack.md).

Contents of ``datapack.json``:

* ``shipped``: the three shipped packs (``data/rules.json``, ``battle_policy.json``,
  ``creatures.json``) as text, with their content hashes and parsed values.
* ``valid``: valid variants (reordered keys, other formatting, creature order, boundary
  values, non-ASCII names). Each has ``hash`` and ``parsed``; ``same_hash_as`` names a case
  whose hash it must equal (key order and formatting never change a hash).
* ``invalid``: generated invalid packs, each with the Python error ``message`` and its
  ``category``. Kotlin must raise the same category and message (``invalid_json`` is
  compared by category only: the parser texts differ).

Usage:  python3 -m h3re.vectors_pack [--out DIR]
"""

import argparse
import copy
import json
import os
import re
import sys
from fractions import Fraction

from . import datapack as D
from . import vectors as V

VECTOR_FORMAT = 1
FILE = "datapack.json"
BIG = 2 ** 31
KINDS = ("rules", "policy", "creatures")
FILENAMES = {"rules": "rules.json", "policy": "battle_policy.json", "creatures": "creatures.json"}
CHECKS = {"rules": D._check_rules, "policy": D._check_policy, "creatures": D._check_creatures}


class Raw:
    """A literal JSON fragment to splice into the dumped text (floats, NaN, ...)."""

    def __init__(self, text):
        self.text = text


def dumps(obj, **kw):
    raws = []

    def walk(v):
        if isinstance(v, Raw):
            raws.append(v.text)
            return "@@RAW%d@@" % (len(raws) - 1)
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v
    text = json.dumps(walk(obj), **kw)
    for i, r in enumerate(raws):
        text = text.replace('"@@RAW%d@@"' % i, r)
    return text


def data_dir():
    return D._REPO_DIR


def read_base(kind):
    with open(os.path.join(data_dir(), FILENAMES[kind]), encoding="utf-8") as f:
        return f.read()


def run(kind, text):
    """Parse ``text`` as the Python loader does. Returns (message, None) or (None, checked)."""
    try:
        return None, CHECKS[kind](D._loads(text, FILENAMES[kind]))
    except D.DataPackError as e:
        return str(e), None


def classify(msg):
    if "invalid JSON" in msg:
        return "invalid_json"
    if "duplicate key" in msg:
        return "duplicate_key"
    if "floats are not allowed" in msg:
        return "float"
    if "unknown key(s)" in msg:
        return "unknown_key"
    if "missing key(s)" in msg:
        return "missing_key"
    if "expected one of" in msg:
        return "enum"
    if re.search(r"expected \d+ items", msg):
        return "length"
    if "unsupported" in msg:
        return "schema_version"
    if "out of range" in msg:
        return "range"
    if "level 0 must be" in msg or "non-decreasing" in msg:
        return "table"
    if "must be distinct" in msg:
        return "distinct"
    if "dmg_min > dmg_max" in msg:
        return "dmg_order"
    if ": duplicate '" in msg or ': duplicate "' in msg:
        return "duplicate_name"
    if "unknown creature" in msg:
        return "unknown_creature"
    if "must not be empty" in msg:
        return "empty"
    if "expected " in msg:
        return "type"
    raise AssertionError("unclassified message: %s" % msg)


# --------------------------------------------------------------------------
# Mutation walker
# --------------------------------------------------------------------------

def _get(obj, path):
    for p in path:
        obj = obj[p]
    return obj


def _set(obj, path, value):
    obj = copy.deepcopy(obj)
    if not path:
        return value
    _get(obj, path[:-1])[path[-1]] = value
    return obj


def _delete(obj, path):
    obj = copy.deepcopy(obj)
    parent = _get(obj, path[:-1])
    del parent[path[-1]]
    return obj


def _fmt(path):
    return "".join("[%d]" % p if isinstance(p, int) else ".%s" % p for p in path) or "<root>"


def _walk(obj, path=()):
    yield path, obj
    if isinstance(obj, dict):
        for k in obj:
            yield from _walk(obj[k], path + (k,))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            yield from _walk(x, path + (i,))


def mutations(obj):
    """Yield (description, mutated object) for a broad set of single-point corruptions."""
    for path, v in _walk(obj):
        here = _fmt(path)
        if isinstance(v, dict):
            m = copy.deepcopy(v)
            m["zzz_unknown"] = 1
            yield "%s add unknown key" % here, _set(obj, path, m)
            for k in v:
                yield "%s delete %s" % (here, k), _delete(obj, path + (k,))
            for name, alt in (("array", []), ("string", "x"), ("null", None)):
                if path:
                    yield "%s as %s" % (here, name), _set(obj, path, alt)
        elif isinstance(v, list):
            yield "%s pop" % here, _set(obj, path, v[:-1])
            yield "%s append" % here, _set(obj, path, v + [v[-1] if v else 0])
            yield "%s empty" % here, _set(obj, path, [])
            for name, alt in (("object", {}), ("string", "x"), ("null", None)):
                yield "%s as %s" % (here, name), _set(obj, path, alt)
        elif isinstance(v, bool):
            for name, alt in (("int", 1), ("string", "x"), ("null", None), ("float", Raw("1.0"))):
                yield "%s bool as %s" % (here, name), _set(obj, path, alt)
        elif isinstance(v, int):
            for name, alt in (("bool", True), ("string", "1"), ("null", None), ("float", Raw("1.0")),
                              ("exp", Raw("1e2")), ("2^31", BIG), ("negative", -1),
                              ("huge", 10 ** 30)):
                yield "%s int as %s" % (here, name), _set(obj, path, alt)
        elif isinstance(v, str):
            for name, alt in (("int", 5), ("null", None), ("bogus", "bogus"), ("empty", ""),
                              ("blank", "  "), ("bool", False)):
                yield "%s string as %s" % (here, name), _set(obj, path, alt)


def _collect_invalid(kind, base, cases, seen):
    for desc, mutated in mutations(base):
        text = dumps(mutated, sort_keys=True)
        msg, _ = run(kind, text)
        if msg is None or msg in seen:
            continue
        seen.add(msg)
        cases.append({"id": "%s: %s" % (kind, desc), "kind": kind, "text": text,
                      "category": classify(msg), "message": msg})


def _extra_invalid(kind, base, cases, seen):
    """Hand-written cases: a few classes the mutation walker cannot reach, plus raw-text ones."""
    pretty = dumps(base, sort_keys=True)
    raw = {
        "empty text": "",
        "only whitespace": "  \n",
        "truncated": pretty[:len(pretty) // 2],
        "trailing garbage": pretty + " x",
        "trailing comma": pretty[:-1] + ",}",
        "single quotes": "{'schema_version': 1}",
        "top-level array": "[]",
        "top-level int": "1",
        "top-level null": "null",
        "duplicate key": pretty[:-1] + ',"schema_version":1}',
        "NaN": pretty.replace('"schema_version": 1', '"schema_version": NaN').replace(
            '"schema_version":1', '"schema_version":NaN'),
        "Infinity": pretty.replace('"schema_version":1', '"schema_version":Infinity'),
        "-Infinity": pretty.replace('"schema_version":1', '"schema_version":-Infinity'),
        "float 1.0": pretty.replace('"schema_version":1', '"schema_version":1.0'),
        "float 1E+0": pretty.replace('"schema_version":1', '"schema_version":1E+0'),
        "float -0.5": pretty.replace('"schema_version":1', '"schema_version":-0.5'),
        "leading zero": pretty.replace('"schema_version":1', '"schema_version":01'),
        "bad escape": pretty.replace('"schema_version"', '"schema\\x_version"'),
    }
    for name, text in raw.items():
        msg, _ = run(kind, text)
        if msg is None or msg in seen:
            continue
        seen.add(msg)
        cases.append({"id": "%s: raw %s" % (kind, name), "kind": kind, "text": text,
                      "category": classify(msg), "message": msg})
    for name, mutated in _special(kind, base):
        text = dumps(mutated, sort_keys=True)
        msg, _ = run(kind, text)
        assert msg is not None, (kind, name)
        if msg in seen:
            continue
        seen.add(msg)
        cases.append({"id": "%s: %s" % (kind, name), "kind": kind, "text": text,
                      "category": classify(msg), "message": msg})


def _special(kind, base):
    out = []
    if kind == "rules":
        def s(path, value):
            return _set(base, path, value)
        out += [
            ("schema_version 2", s(["schema_version"], 2)),
            ("schema_version 0", s(["schema_version"], 0)),
            ("morale_die 0", s(["morale_die"], 0)),
            ("morale_die 1001", s(["morale_die"], 1001)),
            ("morale_die below numerator", s(["morale_die"], 5)),
            ("offense level 0 not [0,1]", s(["offense", 0], [0, 2])),
            ("offense level 0 [1,1]", s(["offense", 0], [1, 1])),
            ("archery decreasing", s(["archery", 2], [1, 20])),
            ("armorer decreasing late", s(["armorer", 3], [1, 20])),
            ("bad morale decreasing", s(["bad_morale_numerators"], [3, 2, 1])),
            ("vcmi bad morale above die", s(["vcmi_bad_morale_numerators"], [2, 4, 25])),
            ("zero denominator", s(["half"], [1, 0])),
            ("negative numerator", s(["half"], [-1, 2])),
            ("denominator 2^31", s(["half"], [1, BIG])),
            ("numerator 2^31", s(["luck_bonus"], [BIG, 1])),
            ("fraction of 3", s(["half"], [1, 2, 3])),
            ("fraction bool part", s(["half"], [True, 2])),
        ]
    elif kind == "policy":
        def s(path, value):
            return _set(base, path, value)
        out += [
            ("schema_version 2", s(["schema_version"], 2)),
            ("defend_bonus_den 0", s(["defend_bonus_den"], 0)),
            ("defend_bonus_num 2^31", s(["defend_bonus_num"], BIG)),
            ("range_penalty_beyond 1001", s(["range_penalty_beyond"], 1001)),
            ("placement duplicate cells", s(["placement_rows", 1], [2, 2])),
            ("placement row index 11", s(["placement_rows", 0], [11])),
            ("placement negative row", s(["placement_rows", 2], [2, -1, 8])),
            ("placement wrong row length", s(["placement_rows", 3], [0, 4, 6])),
            ("placement 8 rows", s(["placement_rows"], base["placement_rows"] + [[0]])),
            ("placement bool cell", s(["placement_rows", 0], [True])),
            ("enum case", s(["row_offset"], "Odd")),
            ("enum list", s(["speed_tie"], ["attacker_first"])),
        ]
    else:
        cs = base["creatures"]

        def c(i, **kw):
            m = copy.deepcopy(base)
            m["creatures"][i].update(kw)
            return m

        out += [
            ("schema_version 2", _set(base, ["schema_version"], 2)),
            ("no creatures", _set(base, ["creatures"], [])),
            ("creatures as object", _set(base, ["creatures"], {})),
            ("dmg_min above dmg_max", c(0, dmg_min=5, dmg_max=4)),
            ("dmg_min 0 dmg_max 0", c(0, dmg_min=0, dmg_max=0)),
            ("dmg_max 10001", c(0, dmg_max=10001)),
            ("hp 0", c(0, hp=0)),
            ("hp 100001", c(0, hp=100001)),
            ("attack 256", c(0, attack=256)),
            ("speed 101", c(1, speed=101)),
            ("shots 1001", c(1, shots=1001)),
            ("shots float", c(1, shots=Raw("2.5"))),
            ("flag as int", c(0, flyer=1)),
            ("flag as string", c(0, strikes_twice="true")),
            ("duplicate name", c(1, name=cs[0]["name"])),
            ("name blank", c(0, name="   ")),
            ("name number", c(0, name=7)),
            ("hates unknown", c(0, hates=["Nobody"])),
            ("hates self-unknown mixed", c(2, hates=["Test Brute", "Nobody"])),
            ("hates duplicate", c(2, hates=["Test Brute", "Test Brute"])),
            ("hates non-string", c(2, hates=["Test Brute", 3])),
            ("hates not a list", c(2, hates="Test Brute")),
            ("unknown field", c(0, armor=3)),
            ("creature as array", _set(base, ["creatures", 0], [])),
        ]
    return out


# --------------------------------------------------------------------------
# Valid variants
# --------------------------------------------------------------------------

def _reverse_keys(v):
    if isinstance(v, dict):
        return {k: _reverse_keys(v[k]) for k in reversed(list(v))}
    if isinstance(v, list):
        return [_reverse_keys(x) for x in v]
    return v


def _jsonable(v):
    if isinstance(v, Fraction):
        return [v.numerator, v.denominator]
    if isinstance(v, dict) or hasattr(v, "keys"):
        return {k: _jsonable(v[k]) for k in v}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def parsed_and_hash(kind, text, rules_checked):
    """Python's parsed values and content hash for a valid pack text."""
    checked = CHECKS[kind](D._loads(text, FILENAMES[kind]))
    if kind == "rules":
        pack = D.DataPack(checked, [])
        return _jsonable(pack.rules), pack.content_hash
    if kind == "policy":
        pack = D.PolicyPack(checked)
        return _jsonable(pack.values), pack.content_hash
    pack = D.DataPack(rules_checked, checked)
    import dataclasses
    crs = [dict(dataclasses.asdict(c), hates=list(c.hates)) for c in pack.creatures()]
    return crs, pack.content_hash


def _valid_variants(kind, base):
    """(name, text, same_as_shipped_flag) for valid texts."""
    shipped = dumps(base, indent=2)
    out = [
        ("shipped file text", read_base(kind), True),
        ("compact sorted", dumps(base, sort_keys=True, separators=(",", ":")), True),
        ("indent 2", shipped, True),
        ("indent 4 with newline", dumps(base, indent=4) + "\n", True),
        ("reversed keys", dumps(_reverse_keys(base)), True),
        ("reversed keys, tabs", dumps(_reverse_keys(base), indent="\t"), True),
        ("ascii-escaped", dumps(base, ensure_ascii=True), True),
        ("surrounding whitespace", "\n\t " + dumps(base) + " \r\n", True),
    ]
    if kind == "creatures":
        rev = copy.deepcopy(base)
        rev["creatures"] = list(reversed(rev["creatures"]))
        out.append(("creature order reversed", dumps(rev), True))
        rev2 = copy.deepcopy(base)
        rev2["creatures"] = [rev2["creatures"][i] for i in (2, 0, 3, 1)]
        out.append(("creature order shuffled, keys reversed", dumps(_reverse_keys(rev2)), True))
    return out


def _derived_valid(kind, base):
    """Valid packs that differ from the shipped ones: (id, text, group). Group members share a hash."""
    out = []
    if kind == "rules":
        m = copy.deepcopy(base)
        m["da_penalty_per_point"] = [2, 80]          # unreduced: parsed 1/40, hash differs
        out.append(("unreduced fraction", dumps(m), "unreduced"))
        out.append(("unreduced fraction, keys reversed", dumps(_reverse_keys(m)), "unreduced"))
        m = copy.deepcopy(base)
        m["ad_bonus_cap"] = [2 ** 31 - 1, 1]
        m["luck_bonus"] = [0, 2 ** 31 - 1]
        m["morale_die"] = 1000
        m["bad_morale_numerators"] = [0, 0, 1000]
        m["vcmi_bad_morale_numerators"] = [1000, 1000, 1000]
        out.append(("boundary values", dumps(m), "boundary"))
        out.append(("boundary values, sorted compact", dumps(m, sort_keys=True, separators=(",", ":")),
                    "boundary"))
        m = copy.deepcopy(base)
        m["offense"] = [[0, 1], [0, 5], [0, 7], [0, 9]]
        m["armorer"] = [[0, 1], [1, 3], [2, 6], [1, 2]]  # equal values via cross-multiplication
        out.append(("equal non-decreasing steps", dumps(m), "equalsteps"))
    elif kind == "policy":
        m = copy.deepcopy(base)
        m["defend_bonus_num"] = m["defend_bonus_den"] = m["defend_bonus_min"] = 2 ** 31 - 1
        m["range_penalty_beyond"] = 1000
        m["row_offset"] = "odd"
        m["speed_tie"] = "alternate_last_mover"
        m["wait_order"] = "slow_first_alternate"
        m["defend_bonus_rounding"] = "ceil"
        m["range_origin"] = "any_cell"
        for k in ("edge_columns_walkable", "good_morale_after_wait", "good_morale_after_defend",
                  "repeat_good_morale", "bad_morale_on_wait_activation", "bad_luck"):
            m[k] = True
        m["good_morale_on_wait_activation"] = False
        m["placement_rows"] = [[10], [9, 10], [0, 1, 2], [10, 9, 8, 7], [0, 1, 2, 3, 4],
                               [5, 4, 3, 2, 1, 0], [10, 0, 5, 3, 7, 1, 9]]
        out.append(("all fields changed", dumps(m), "policy-changed"))
        out.append(("all fields changed, keys reversed", dumps(_reverse_keys(m), indent=1),
                    "policy-changed"))
    else:
        m = copy.deepcopy(base)
        m["creatures"][0].update(hates=["Test Slinger", "Test Brute", "Test Glider"], shots=0,
                                 flyer=False, no_morale=True)
        out.append(("multiple hates unsorted", dumps(m), "hates"))
        m2 = copy.deepcopy(m)
        m2["creatures"][0]["hates"] = ["Test Glider", "Test Brute", "Test Slinger"]
        out.append(("multiple hates reversed", dumps(m2), "hates"))
        m = copy.deepcopy(base)
        m["creatures"] = [
            {"name": "\U0001F600 Test", "attack": 0, "defense": 0, "dmg_min": 0, "dmg_max": 1,
             "hp": 1, "speed": 0},
            {"name": "Ａ Test", "attack": 255, "defense": 255, "dmg_min": 10000, "dmg_max": 10000,
             "hp": 100000, "speed": 100, "shots": 1000, "flyer": True, "double_wide": True,
             "no_enemy_retaliation": True, "unlimited_retaliation": True, "no_melee_penalty": True,
             "no_range_penalty": True, "strikes_twice": True, "shoots_twice": True,
             "no_morale": True, "hates": ["\U0001F600 Test", "Tab\there", "q\"uote\\"]},
            {"name": "Tab\there", "attack": 1, "defense": 2, "dmg_min": 3, "dmg_max": 3, "hp": 4,
             "speed": 5},
            {"name": "q\"uote\\", "attack": 1, "defense": 2, "dmg_min": 3, "dmg_max": 4, "hp": 4,
             "speed": 5, "hates": []},
            {"name": "éclair", "attack": 1, "defense": 2, "dmg_min": 3, "dmg_max": 4, "hp": 4,
             "speed": 5, "shots": 0},
        ]
        out.append(("non-ascii names and boundary stats", dumps(m), "unicode"))
        out.append(("non-ascii names, raw utf-8", json.dumps(m, ensure_ascii=False), "unicode"))
        m3 = copy.deepcopy(m)
        m3["creatures"].reverse()
        out.append(("non-ascii names, reversed order", dumps(_reverse_keys(m3)), "unicode"))
        m = copy.deepcopy(base)
        m["creatures"] = m["creatures"][:1]
        out.append(("single creature", dumps(m), "single"))
    return out


def generate():
    bases = {k: json.loads(read_base(k)) for k in KINDS}
    rules_checked = D._check_rules(D._loads(read_base("rules"), "rules.json"))
    shipped = {}
    for k in KINDS:
        parsed, h = parsed_and_hash(k, read_base(k), rules_checked)
        shipped[k] = {"text": read_base(k), "hash": h, "parsed": parsed}
    full = D.DataPack(rules_checked, D._check_creatures(bases["creatures"]))
    shipped["pack_hash"] = full.content_hash
    shipped["canonical_policy"] = D.parse_policy(bases["policy"]).canonical_json

    valid, group_first = [], {}
    for k in KINDS:
        for name, text, _ in _valid_variants(k, bases[k]):
            parsed, h = parsed_and_hash(k, text, rules_checked)
            assert h == shipped[k]["hash"], (k, name)
            valid.append({"id": "%s: %s" % (k, name), "kind": k, "text": text, "hash": h,
                          "parsed": parsed, "same_hash_as": "shipped"})
        for name, text, group in _derived_valid(k, bases[k]):
            parsed, h = parsed_and_hash(k, text, rules_checked)
            gid = "%s: %s" % (k, group)
            first = group_first.setdefault(gid, h)
            assert first == h, (k, name)
            valid.append({"id": "%s: %s" % (k, name), "kind": k, "text": text, "hash": h,
                          "parsed": parsed, "group": gid})
        # derived variants must differ from the shipped pack
    for v in valid:
        if "group" in v:
            assert v["hash"] != shipped[v["kind"]]["hash"], v["id"]

    invalid, seen = [], {k: set() for k in KINDS}
    for k in KINDS:
        _collect_invalid(k, bases[k], invalid, seen[k])
        _extra_invalid(k, bases[k], invalid, seen[k])
    for c in invalid:
        assert run(c["kind"], c["text"])[0] == c["message"]
    return {FILE: {"format": VECTOR_FORMAT, "max_int": D.MAX_INT, "shipped": shipped,
                   "valid": valid, "invalid": invalid}}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m h3re.vectors_pack")
    ap.add_argument("--out", default=V.DEFAULT_OUT)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for name, obj in generate().items():
        with open(os.path.join(a.out, name), "wb") as f:
            f.write(V._dump(obj))
        print("wrote %s" % os.path.join(a.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
