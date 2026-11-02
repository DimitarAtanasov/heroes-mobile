"""Town core conformance vectors (the Kotlin `h3.sim.town` port), from the Python reference.

``generate()`` returns ``{"town.json": ...}``; the orchestrator wires it into ``vectors.generate()``
(which owns serialisation). Python (``town.py``) is authoritative (ADR-0004,
docs/specs/conformance-town.md). Every random choice here (the command plans) comes from
``derive_stream``, never Python's ``random``.

Contents of ``town.json`` (all numbers are integers):

* ``packs``: valid town packs by name (``test`` is ``data/towns_test.json`` verbatim).
* ``pack_valid`` / ``pack_invalid``: pack texts with content hash, or Python error message and category.
* ``policies``, ``weekly_growth``, ``streams``: the small pure functions.
* ``create``: ``create_game`` calls with arbitrarily typed arguments (descriptors, see below), the state hash and
  canonical text, or the error ``{kind, message}``.
* ``traces``: command scripts replayed from ``create_game``: per step the command, the events (or the error), the
  state hash, the stream position and (after a legal step) the query results.
* ``queries``: query calls on built states, including errors.
* ``states``: hand-built states (content the loader would refuse, odd towns and treasuries) with one command and
  queries each.
* ``golden``: the scripted run pinned in ``test_town.py`` (state hash and growth digest).

Descriptors (``create`` and ``traces`` inputs): ``players`` is a list of ``{"res": [seven values]}`` (a
``Resources`` whose fields may have any JSON type) or ``{"raw": v}`` (any other value), or ``{"raw": v}`` as a whole;
``towns`` is a list of ``{"setup": {id, faction, owner, built}}`` or ``{"raw": v}``, or ``{"raw": v}`` as a whole.

Usage:  python3 -m h3re.vectors_town [--out DIR]
"""

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, replace

from . import adventure as A
from . import datapack as D
from . import town as T
from . import vectors as V
from .rng import derive_stream

VECTOR_FORMAT = 1
FILE = "town.json"
CAP = 2 ** 31 - 1
WHAT = "towns.json"          # the `what` prefix of loader errors raised while reading (Python: the file's base name)
NAMES = A.RESOURCE_NAMES
MODES = ("floor", "ceil", "nearest")
POLICIES = tuple(T.TownPolicy(m) for m in MODES)


# --------------------------------------------------------------------------
# Packs
# --------------------------------------------------------------------------

def _test_text():
    with open(os.path.join(D._REPO_DIR, "towns_test.json"), encoding="utf-8") as f:
        return f.read()


def _base():
    return json.loads(_test_text())


def _b(bid, cost=None, requires=(), **kw):
    d = {"id": bid, "cost": dict(cost or {}), "requires": list(requires)}
    d.update(kw)
    return d


def _tiny():
    return {"schema_version": 1, "factions": [
        {"id": "f.b", "buildings": [_b("only")]},
        {"id": "f.a", "buildings": [
            _b("hall", {"gold": 100}, income={"gold": 10}),
            _b("hall2", {"gold": 200, "wood": 1}, ["hall"], upgrades="hall", income={"gold": 25, "wood": 1}),
            _b("fort", {"gold": 50, "ore": 2}, fort=True),
            _b("cit", {"gold": 70}, ["fort"], upgrades="fort", fort=True, growth_bonus=[1, 2]),
            _b("cas", {"gold": 90}, ["cit"], upgrades="cit", fort=True, growth_bonus=[3, 4]),
            _b("bless", {"gold": 5}, growth_bonus=[2, 3]),
            _b("bless2", {"gold": 6}, growth_bonus=[2, 4]),
            _b("d1", {"gold": 10}, ["fort"], dwelling={"level": 1, "creature": "c.one", "base_growth": 5}),
            _b("d1u", {"gold": 12}, ["d1"], upgrades="d1", dwelling={"level": 1, "creature": "c.one+", "base_growth": 6}),
            _b("d2", {"gold": 14}, ["cit"], dwelling={"level": 2, "creature": "c.two", "base_growth": 3}),
            _b("d3", {"gold": 16}, ["fort"], dwelling={"level": 3, "creature": "c.three", "base_growth": 0}),
            _b("h1a", {"gold": 8}, ["d1"], horde={"level": 1, "bonus": 2}),
            _b("h1b", {"gold": 9}, ["d1"], horde={"level": 1, "bonus": 3}),
            _b("h2", {"gold": 11}, ["d2"], horde={"level": 2, "bonus": 1}),
            _b("h3", {"gold": 13}, ["d3"], horde={"level": 3, "bonus": 4}),
        ]},
    ]}


UNI_F = ["fac.\U00010000", "fac.\uffee", "fac.\xe9"]


def _unicode():
    def fac(fid, tag):
        return {"id": fid, "buildings": [
            _b("hall.\xe9", {"gold": 10}, income={"gold": 3}),
            _b("hall.\U00010000", {"gold": 20}, ["hall.\xe9"], upgrades="hall.\xe9", income={"gold": 4}, player_unique=tag),
            _b("hall.\uffee", {"gold": 30}),
            _b("keep.\u4e2d", {"gold": 40, "ore": 1}, fort=True, growth_bonus=[1, 3]),
            _b("keep.\U0001F600", {"gold": 41}, ["keep.\u4e2d"], upgrades="keep.\u4e2d", fort=True, growth_bonus=[1, 2]),
            _b("d.\xe9", {"gold": 50}, ["keep.\u4e2d"], dwelling={"level": 1, "creature": "cr.\U00010000", "base_growth": 7}),
            _b("d.\uffee", {"gold": 51}, ["keep.\u4e2d"], dwelling={"level": 2, "creature": "cr.\uffee", "base_growth": 9}),
            _b("h.\U00010000", {"gold": 52}, ["d.\xe9"], horde={"level": 1, "bonus": 1}),
        ]}
    return {"schema_version": 1, "factions": [fac(UNI_F[0], "cap.\U00010000"), fac(UNI_F[1], "cap.\uffee"),
                                              fac(UNI_F[2], "cap.\xe9")]}


def _bigvalues():
    res = {n: CAP for n in NAMES}
    return {"schema_version": 1, "factions": [{"id": "f.big", "buildings": [
        _b("hall", res, income=res),
        _b("fort", res, fort=True, growth_bonus=[CAP, CAP - 1]),
        _b("fort2", {"gold": CAP}, ["fort"], upgrades="fort", fort=True, growth_bonus=[CAP - 1, CAP]),
        _b("d1", {"gold": CAP}, ["fort"], dwelling={"level": 1, "creature": "c", "base_growth": CAP}),
        _b("d1000", {"gold": CAP}, ["fort"], dwelling={"level": 1000, "creature": "c1000", "base_growth": CAP}),
        _b("hordebig", {"gold": CAP}, ["d1"], horde={"level": 1, "bonus": CAP}),
        _b("hordebig2", {"gold": CAP}, ["d1"], horde={"level": 1, "bonus": CAP}),
    ]}]}


def _twin():
    return {"schema_version": 1, "factions": [
        {"id": "f.one", "buildings": [
            _b("cap.a", {"gold": 100}, player_unique="capital"),
            _b("cap.b", {"gold": 100}, player_unique="capital"),
            _b("other", {"gold": 100}, player_unique="other"),
            _b("plain", {"gold": 1}),
        ]},
        {"id": "f.two", "buildings": [_b("cap.c", {"gold": 100}, player_unique="capital"), _b("plain", {"gold": 1})]},
    ]}


def _minimal():
    return {"schema_version": 1, "factions": [{"id": "f", "buildings": [_b("b")]}]}


def _seven():
    """One building per resource, each costing exactly 3 of it."""
    return {"schema_version": 1, "factions": [{"id": "f", "buildings": [_b("r." + n, {n: 3}) for n in NAMES]}]}


def _packs():
    return {
        "test": _test_text(),
        "tiny": json.dumps(_tiny()),
        "unicode": json.dumps(_unicode(), ensure_ascii=False),
        "bigvalues": json.dumps(_bigvalues(), indent=1),
        "twin": json.dumps(_twin(), separators=(",", ":")),
        "minimal": json.dumps(_minimal()),
        "seven": json.dumps(_seven()),
    }


def _load(text):
    return T.parse_town_pack(D._loads(text, WHAT))


PACK_TEXT = _packs()
CONTENT = {name: _load(text) for name, text in PACK_TEXT.items()}


def _run_pack(text):
    """(None, content) or (message, None), as the Python loader behaves on file text."""
    try:
        return None, _load(text)
    except D.DataPackError as e:
        return str(e), None


def classify_pack(msg):
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
    if re.search(r"expected \d+ items", msg):
        return "length"
    if "unsupported" in msg:
        return "schema_version"
    if "out of range" in msg:
        return "range"
    if "expected " in msg:
        return "type"
    if "must not be empty" in msg:
        return "empty"
    if "duplicate" in msg:
        return "duplicate_name"
    if "unknown building" in msg:
        return "unknown_building"
    if "must also be required" in msg or "upgraded by more than one" in msg:
        return "upgrade"
    if "requirement cycle" in msg:
        return "cycle"
    if "player_unique" in msg:
        return "player_unique"
    if "horde level" in msg:
        return "horde"
    if "dwelling" in msg:
        return "dwelling"
    raise AssertionError("unclassified message: %s" % msg)


def _dump_text(d, **kw):
    return json.dumps(d, **kw)


def _fb(d, fi, bid):
    """The building ``bid`` of faction index ``fi`` in a decoded pack."""
    return next(b for b in d["factions"][fi]["buildings"] if b["id"] == bid)


# --------------------------------------------------------------------------
# Valid and invalid packs
# --------------------------------------------------------------------------

def _valid_cases():
    base = _base()
    cases = []

    def add(name, text, same_hash_as=None):
        err, content = _run_pack(text)
        assert err is None, "%s rejected: %s" % (name, err)
        c = {"name": name, "text": text, "hash": T.content_hash(content),
             "factions": [{"id": f.id, "buildings": [b.id for b in f.buildings]} for f in content.factions]}
        if same_hash_as:
            c["same_hash_as"] = same_hash_as
        cases.append(c)

    add("test-file", _test_text())
    add("test-compact", json.dumps(base, separators=(",", ":")), "test-file")
    add("test-indent-sorted-keys", json.dumps(base, indent=4, sort_keys=True), "test-file")
    add("test-ascii-escapes-off", json.dumps(base, ensure_ascii=False), "test-file")
    add("test-tabs-and-newlines", json.dumps(base).replace(", ", ",\n\t").replace(": ", " :\r\n"), "test-file")

    d = _base()
    d["factions"].reverse()
    add("faction-order-reversed", json.dumps(d), "test-file")
    d = _base()
    for f in d["factions"]:
        f["buildings"].reverse()
    add("building-order-reversed", json.dumps(d), "test-file")
    d = _base()
    for f in d["factions"]:
        for b in f["buildings"]:
            b["requires"].reverse()
            b = dict(reversed(list(b.items())))
    add("requires-order-reversed", json.dumps(d), "test-file")
    d = _base()
    d["factions"] = [dict(reversed(list(f.items()))) for f in d["factions"]]
    d = dict(reversed(list(d.items())))
    add("key-order-reversed", json.dumps(d), "test-file")
    d = _base()
    for f in d["factions"]:
        for b in f["buildings"]:
            for n in NAMES:
                b["cost"].setdefault(n, 0)
            b.setdefault("income", {n: 0 for n in NAMES}) if "income" not in b else None
            b.setdefault("fort", False)
            b.setdefault("growth_bonus", [0, 1])
    add("explicit-defaults", json.dumps(d), "test-file")
    d = _base()
    _fb(d, 0, "market")["cost"] = {"wood": 5, "gold": 500}
    add("cost-key-order", json.dumps(d), "test-file")
    add("unicode-escapes-in-ids", _test_text().replace('"faction.fernwood"', '"faction.fern\\u0077ood"'), "test-file")
    d = _base()
    _fb(d, 0, "keep.2")["growth_bonus"] = [2, 4]
    add("growth-bonus-unreduced", json.dumps(d))
    d = _base()
    _fb(d, 0, "keep.2")["growth_bonus"] = [1, 2]
    add("growth-bonus-reduced", json.dumps(d), "test-file")
    d = _base()
    _fb(d, 0, "keep.2")["growth_bonus"] = [0, 1]
    add("growth-bonus-zero", json.dumps(d))

    for name in PACK_TEXT:
        if name != "test":
            add("pack-" + name, PACK_TEXT[name])
    add("unicode-compact", json.dumps(_unicode(), ensure_ascii=True, separators=(",", ":")), "pack-unicode")
    d = _unicode()
    d["factions"].reverse()
    add("unicode-faction-order", json.dumps(d), "pack-unicode")

    # boundaries
    d = _minimal()
    _fb(d, 0, "b")["cost"] = {n: CAP for n in NAMES}
    _fb(d, 0, "b")["income"] = {n: CAP for n in NAMES}
    add("resources-at-cap", json.dumps(d))
    d = _minimal()
    _fb(d, 0, "b")["growth_bonus"] = [CAP, CAP]
    add("growth-bonus-at-cap", json.dumps(d))
    d = _minimal()
    d["schema_version"] = 1
    add("minimal", json.dumps(d), "pack-minimal")
    d = {"schema_version": 1, "factions": [{"id": " f\xa0", "buildings": [_b(" b ")]}]}
    add("ids-with-edge-spaces", json.dumps(d))
    d = {"schema_version": 1, "factions": [{"id": "f", "buildings": [_b("\u200b"), _b("\x7f")]}]}
    add("ids-non-printable", json.dumps(d))
    # a long requirement chain (closure and cycle check walk it)
    chain = [_b("n0", fort=True)] + [_b("n%d" % i, {"gold": i}, ["n%d" % (i - 1)]) for i in range(1, 60)]
    add("chain-60", json.dumps({"schema_version": 1, "factions": [{"id": "f", "buildings": chain}]}))
    chain.append(_b("dw", {"gold": 1}, ["n59"], dwelling={"level": 1, "creature": "c", "base_growth": 1}))
    add("dwelling-behind-long-chain", json.dumps({"schema_version": 1, "factions": [{"id": "f", "buildings": chain}]}))
    # dwelling gets its fort only transitively; upgrade of a dwelling keeps the level
    d = {"schema_version": 1, "factions": [{"id": "f", "buildings": [
        _b("fort", fort=True), _b("mid", requires=["fort"]), _b("dw", requires=["mid"],
                                                                dwelling={"level": 7, "creature": "c", "base_growth": 1}),
        _b("dw2", requires=["dw"], upgrades="dw", dwelling={"level": 7, "creature": "c2", "base_growth": 2}),
        _b("dw3", requires=["dw2"], upgrades="dw2", dwelling={"level": 7, "creature": "c3", "base_growth": 3}),
        _b("hd", requires=["dw"], horde={"level": 7, "bonus": 0}),
        _b("fort2", requires=["fort"], fort=True, upgrades="fort"),
    ]}]}
    add("transitive-fort-and-chain", json.dumps(d))
    # the same tag on two buildings neither of which requires the other is fine
    add("unique-tag-twice-unrelated", PACK_TEXT["twin"])
    # unknown top-level order: factions before schema_version
    d = _base()
    add("schema-version-last", json.dumps({"factions": d["factions"], "schema_version": 1}), "test-file")
    return cases


def _invalid_cases():
    cases = []

    def add(name, text):
        err, _ = _run_pack(text)
        assert err is not None, "%s was accepted" % name
        cases.append({"name": name, "text": text, "message": err, "category": classify_pack(err)})

    def mut(name, fn):
        d = _base()
        fn(d)
        add(name, json.dumps(d))

    def fb(d, bid, fi=0):
        return _fb(d, fi, bid)

    # --- text level
    for name, text in (("empty-text", ""), ("only-space", "   "), ("brace-open", "{"),
                       ("missing-value", '{"a":}'), ("trailing-comma", "[1,]"),
                       ("single-quotes", "{'a': 1}"), ("garbage-after", "{} x"),
                       ("bad-literal", "nul"), ("leading-zero", '{"schema_version": 01}'),
                       ("unterminated-string", '{"schema_version')):
        add(name, text)
    for name, text in (("top-null", "null"), ("top-list", "[]"), ("top-string", '"x"'), ("top-int", "5"),
                       ("top-bool", "true")):
        add(name, text)
    t = _test_text()
    for name, a, b in (
            ("float-base-growth", '"base_growth": 13', '"base_growth": 13.0'),
            ("float-income", '"income": {"gold": 500}', '"income": {"gold": 500.5}'),
            ("float-exponent", '"bonus": 4', '"bonus": 4e0'),
            ("float-negative-exponent", '"level": 2', '"level": 2E-1'),
            ("float-in-growth-bonus", '"growth_bonus": [1, 2]', '"growth_bonus": [1, 2.0]'),
            ("float-schema-version", '"schema_version": 1', '"schema_version": 1.0'),
            ("nan", '"bonus": 4', '"bonus": NaN'),
            ("infinity", '"bonus": 4', '"bonus": Infinity'),
            ("minus-infinity", '"bonus": 4', '"bonus": -Infinity'),
            ("duplicate-top-key", '"schema_version": 1,', '"schema_version": 1, "schema_version": 1,'),
            ("duplicate-building-key", '{"id": "market", ', '{"id": "market", "id": "market", '),
            ("duplicate-cost-key", '"cost": {"gold": 500, "wood": 5}', '"cost": {"gold": 500, "gold": 1, "wood": 5}'),
            ("duplicate-dwelling-key", '"base_growth": 13}', '"base_growth": 13, "base_growth": 14}')):
        assert a in t, name
        add(name, t.replace(a, b, 1))

    # --- top level
    mut("unknown-top-key", lambda d: d.update(colour=1))
    mut("two-unknown-top-keys", lambda d: d.update(zeta=1, alpha=2))
    mut("missing-factions", lambda d: d.pop("factions"))
    mut("missing-schema", lambda d: d.pop("schema_version"))
    mut("missing-both", lambda d: (d.pop("factions"), d.pop("schema_version")))
    for name, v in (("two", 2), ("zero", 0), ("negative", -1), ("string", "1"), ("bool", True), ("null", None),
                    ("list", [1]), ("cap-plus-one", CAP + 1), ("huge", 2 ** 70)):
        mut("schema-" + name, lambda d, v=v: d.update(schema_version=v))
    for name, v in (("object", {}), ("string", "x"), ("null", None), ("int", 3)):
        mut("factions-" + name, lambda d, v=v: d.update(factions=v))
    mut("factions-empty", lambda d: d.update(factions=[]))
    mut("faction-duplicate", lambda d: d["factions"].append(copy.deepcopy(d["factions"][0])))
    for name, v in (("null", None), ("string", "f"), ("list", []), ("int", 1)):
        mut("faction-" + name, lambda d, v=v: d["factions"].__setitem__(1, v))
    mut("faction-unknown-key", lambda d: d["factions"][0].update(name="x"))
    mut("faction-missing-id", lambda d: d["factions"][0].pop("id"))
    mut("faction-missing-buildings", lambda d: d["factions"][0].pop("buildings"))
    mut("faction-missing-both", lambda d: d["factions"].__setitem__(0, {}))
    for name, v in (("int", 5), ("null", None), ("empty", ""), ("spaces", "  "), ("tab-nl", "\t\n"),
                    ("nbsp", "\xa0"), ("ls", "\u2028"), ("list", ["f"]), ("bool", False)):
        mut("faction-id-" + name, lambda d, v=v: d["factions"][0].update(id=v))
    for name, v in (("object", {}), ("string", "b"), ("null", None)):
        mut("faction-buildings-" + name, lambda d, v=v: d["factions"][0].update(buildings=v))
    mut("faction-buildings-empty", lambda d: d["factions"][1].update(buildings=[]))
    mut("duplicate-building", lambda d: d["factions"][1]["buildings"].append(copy.deepcopy(d["factions"][1]["buildings"][2])))

    # --- building keys and types
    for name, v in (("null", None), ("string", "x"), ("list", []), ("int", 1)):
        mut("building-" + name, lambda d, v=v: d["factions"][0]["buildings"].__setitem__(3, v))
    mut("building-unknown-key", lambda d: fb(d, "market").update(colour=1))
    mut("building-unknown-keys-sorted", lambda d: fb(d, "market").update(zz=1, aa=2, mm=3))
    for key in ("id", "cost", "requires"):
        mut("building-missing-" + key, lambda d, key=key: fb(d, "market").pop(key))
    mut("building-missing-two", lambda d: (fb(d, "market").pop("cost"), fb(d, "market").pop("id")))
    for name, v in (("int", 5), ("null", None), ("empty", ""), ("spaces", " \t"), ("list", ["a"]), ("true", True)):
        mut("building-id-" + name, lambda d, v=v: fb(d, "market").update(id=v))
    for name, v in (("list", []), ("null", None), ("string", "gold"), ("int", 0)):
        mut("cost-" + name, lambda d, v=v: fb(d, "market").update(cost=v))
    mut("cost-unknown-resource", lambda d: fb(d, "market")["cost"].update(silver=1))
    mut("cost-two-unknown-resources", lambda d: fb(d, "market")["cost"].update(zinc=1, aluminium=2))
    for n in NAMES:
        mut("cost-%s-negative" % n, lambda d, n=n: fb(d, "market")["cost"].update({n: -1}))
        mut("cost-%s-above-cap" % n, lambda d, n=n: fb(d, "market")["cost"].update({n: CAP + 1}))
    for name, v in (("bool", True), ("string", "5"), ("null", None), ("list", [5]), ("object", {}), ("huge", 2 ** 80)):
        mut("cost-gold-" + name, lambda d, v=v: fb(d, "market")["cost"].update(gold=v))
    mut("cost-last-field-first-error", lambda d: fb(d, "market")["cost"].update(wood=-5, gems=-1))
    for name, v in (("object", {}), ("null", None), ("string", "x"), ("int", 3)):
        mut("requires-" + name, lambda d, v=v: fb(d, "market").update(requires=v))
    mut("requires-int-item", lambda d: fb(d, "market").update(requires=["hall.1", 5]))
    mut("requires-blank-item", lambda d: fb(d, "market").update(requires=["hall.1", " "]))
    mut("requires-null-item", lambda d: fb(d, "market").update(requires=[None]))
    mut("requires-duplicate", lambda d: fb(d, "market").update(requires=["hall.1", "hall.1"]))
    for name, v in (("int", 1), ("null", None), ("empty", ""), ("blank", "  "), ("list", ["hall.1"])):
        mut("upgrades-" + name, lambda d, v=v: fb(d, "hall.2").update(upgrades=v))
    for name, v in (("list", []), ("null", None), ("string", "x"), ("int", 1)):
        mut("income-" + name, lambda d, v=v: fb(d, "hall.1").update(income=v))
    mut("income-unknown-resource", lambda d: fb(d, "hall.1")["income"].update(silver=1))
    mut("income-negative", lambda d: fb(d, "hall.1")["income"].update(gold=-1))
    mut("income-above-cap", lambda d: fb(d, "hall.1")["income"].update(ore=CAP + 1))
    for name, v in (("string", "yes"), ("int-one", 1), ("int-zero", 0), ("null", None), ("list", [])):
        mut("fort-" + name, lambda d, v=v: fb(d, "keep.1").update(fort=v))
    for name, v in (("object", {}), ("null", None), ("int", 1), ("string", "1/2")):
        mut("growth-bonus-" + name, lambda d, v=v: fb(d, "keep.2").update(growth_bonus=v))
    for name, v in (([], "empty"), ([1], "one"), ([1, 2, 3], "three")):
        mut("growth-bonus-length-" + v, lambda d, name=name: fb(d, "keep.2").update(growth_bonus=name))
    for name, v in (("numerator-negative", [-1, 2]), ("denominator-zero", [1, 0]), ("denominator-negative", [1, -2]),
                    ("numerator-above-cap", [CAP + 1, 2]), ("denominator-above-cap", [1, CAP + 1]),
                    ("numerator-bool", [True, 2]), ("denominator-bool", [1, True]), ("numerator-string", ["1", 2]),
                    ("denominator-null", [1, None]), ("numerator-list", [[1], 2])):
        mut("growth-bonus-" + name, lambda d, v=v: fb(d, "keep.2").update(growth_bonus=v))
    for name, v in (("list", []), ("null", None), ("string", "x"), ("int", 1)):
        mut("dwelling-" + name, lambda d, v=v: fb(d, "den.1").update(dwelling=v))
    for key in ("level", "creature", "base_growth"):
        mut("dwelling-missing-" + key, lambda d, key=key: fb(d, "den.1")["dwelling"].pop(key))
    mut("dwelling-unknown-key", lambda d: fb(d, "den.1")["dwelling"].update(speed=1))
    mut("dwelling-missing-and-unknown", lambda d: (fb(d, "den.1")["dwelling"].pop("level"), fb(d, "den.1")["dwelling"].update(x=1)))
    for name, v in (("zero", 0), ("above-limit", 1001), ("negative", -3), ("string", "1"), ("bool", True), ("null", None)):
        mut("dwelling-level-" + name, lambda d, v=v: fb(d, "den.1")["dwelling"].update(level=v))
    for name, v in (("empty", ""), ("blank", "   "), ("int", 3), ("null", None)):
        mut("dwelling-creature-" + name, lambda d, v=v: fb(d, "den.1")["dwelling"].update(creature=v))
    for name, v in (("negative", -1), ("above-cap", CAP + 1), ("string", "5"), ("bool", False), ("null", None)):
        mut("dwelling-base-growth-" + name, lambda d, v=v: fb(d, "den.1")["dwelling"].update(base_growth=v))
    for name, v in (("list", []), ("null", None), ("string", "x"), ("int", 1)):
        mut("horde-" + name, lambda d, v=v: fb(d, "hive").update(horde=v))
    for key in ("level", "bonus"):
        mut("horde-missing-" + key, lambda d, key=key: fb(d, "hive")["horde"].pop(key))
    mut("horde-unknown-key", lambda d: fb(d, "hive")["horde"].update(extra=1))
    for name, v in (("zero", 0), ("above-limit", 1001), ("string", "1"), ("bool", True)):
        mut("horde-level-" + name, lambda d, v=v: fb(d, "hive")["horde"].update(level=v))
    for name, v in (("negative", -1), ("above-cap", CAP + 1), ("string", "4"), ("null", None)):
        mut("horde-bonus-" + name, lambda d, v=v: fb(d, "hive")["horde"].update(bonus=v))
    for name, v in (("empty", ""), ("blank", " "), ("int", 1), ("null", None), ("list", ["capital"])):
        mut("player-unique-" + name, lambda d, v=v: fb(d, "hall.4").update(player_unique=v))

    # --- semantic checks
    mut("requires-unknown", lambda d: fb(d, "market")["requires"].append("nope"))
    mut("requires-unknown-quote", lambda d: fb(d, "market")["requires"].append("it's"))
    mut("requires-unknown-double-quote-and-quote", lambda d: fb(d, "market")["requires"].append("a'b\"c"))
    mut("requires-unknown-unicode", lambda d: fb(d, "market")["requires"].append("n\xf6pe\u200b\U0001F600"))
    mut("requires-unknown-tab", lambda d: fb(d, "market")["requires"].append("a\tb\nc\\d"))
    mut("requires-unknown-control", lambda d: fb(d, "market")["requires"].append("a\x01b\x7f"))
    mut("requires-unknown-private-use", lambda d: fb(d, "market")["requires"].append("a\ue000b\U0010ffff"))
    mut("requires-unknown-latin1-control", lambda d: fb(d, "market")["requires"].append("a\u0085b\xad"))
    mut("upgrades-unknown", lambda d: fb(d, "hall.2").update(upgrades="nope"))
    mut("upgrades-self", lambda d: fb(d, "hall.2").update(upgrades="hall.2"))
    mut("upgrades-not-required", lambda d: fb(d, "den.1u").update(requires=["den.1"], upgrades="market"))
    mut("upgrades-without-requiring", lambda d: fb(d, "hall.2").update(requires=["market"]))
    mut("upgraded-twice", lambda d: d["factions"][0]["buildings"].append(
        _b("hall.2b", {"gold": 1}, ["hall.1"], upgrades="hall.1")))
    mut("upgraded-twice-reports-later-id", lambda d: d["factions"][0]["buildings"].insert(
        0, _b("aaa", {"gold": 1}, ["hall.1"], upgrades="hall.1")))
    mut("unknown-requires-before-upgrade-error", lambda d: fb(d, "hall.2").update(requires=["market", "zzz"]))
    mut("cycle-self", lambda d: fb(d, "hall.1")["requires"].append("hall.1"))
    mut("cycle-two", lambda d: fb(d, "hall.1")["requires"].append("hall.2"))
    mut("cycle-three", lambda d: fb(d, "hall.1")["requires"].append("hall.3"))
    mut("cycle-with-dependents", lambda d: (fb(d, "market")["requires"].append("hive"), fb(d, "hive")["requires"].append("market")))
    mut("cycle-through-upgrades", lambda d: fb(d, "keep.1")["requires"].append("keep.3"))
    mut("unique-on-required-direct", lambda d: fb(d, "hall.3").update(player_unique="capital"))
    mut("unique-on-required-transitive", lambda d: fb(d, "hall.2").update(player_unique="capital"))
    mut("unique-on-required-other-tag", lambda d: (fb(d, "market").update(player_unique="shop"),
                                                    fb(d, "hall.2").update(player_unique="shop")))
    mut("dwelling-needs-fort", lambda d: fb(d, "den.1").update(requires=[]))
    mut("dwelling-needs-fort-transitive", lambda d: fb(d, "grove.3").update(requires=["market"]))
    mut("dwelling-fort-only-after-fort-removed", lambda d: fb(d, "keep.1").update(fort=False))
    mut("dwelling-upgrades-other-level", lambda d: fb(d, "nest.2")["dwelling"].update(level=1))
    mut("dwelling-upgrades-non-dwelling", lambda d: fb(d, "den.1u").update(requires=["den.1", "market"], upgrades="market"))
    mut("dwelling-two-bases-one-level", lambda d: fb(d, "nest.2")["dwelling"].update(level=3))
    mut("dwelling-two-bases-reports-later-id", lambda d: (fb(d, "den.1u").pop("upgrades"),
                                                           fb(d, "den.1u").update(requires=["den.1", "market"])))
    mut("non-dwelling-upgrades-dwelling", lambda d: d["factions"][0]["buildings"].append(
        _b("odd", {"gold": 1}, ["nest.2"], upgrades="nest.2")))
    mut("horde-without-dwelling", lambda d: fb(d, "hive")["horde"].update(level=7))
    mut("horde-level-of-upgrade-only", lambda d: fb(d, "hive")["horde"].update(level=1000))
    mut("second-faction-bad-after-first-ok", lambda d: fb(d, "wall.2", 1).update(upgrades="wall.3"))
    mut("first-faction-semantic-before-second-syntax", lambda d: (fb(d, "market").update(requires=["nope"]),
                                                                   fb(d, "wall.1", 1).update(cost=5)))
    mut("first-building-syntax-before-second-building-range", lambda d: (fb(d, "hall.1").update(cost=[]),
                                                                          fb(d, "hall.2")["cost"].update(gold=-1)))
    mut("syntax-before-semantic-in-faction", lambda d: (fb(d, "market").update(requires=["nope"]),
                                                         fb(d, "hive")["horde"].update(level=0)))

    # ids are reported in code point order, not UTF-16 order
    def uni(fn):
        d = {"schema_version": 1, "factions": [{"id": "f", "buildings": [
            _b("a.\U00010000", requires=["zz1"]), _b("a.\uffee", requires=["zz2"]), _b("a.\xe9", requires=["zz3"])]}]}
        fn(d)
        return d

    add("unknown-ref-first-in-code-point-order", json.dumps(uni(lambda d: None)))
    add("cycle-ids-in-code-point-order", json.dumps({"schema_version": 1, "factions": [{"id": "f", "buildings": [
        _b("c.\U00010000", requires=["c.\uffee"]), _b("c.\uffee", requires=["c.\U00010000"]), _b("c.\xe9", requires=["c.\U00010000"])]}]}))
    add("unknown-keys-sorted-by-code-point", json.dumps({"schema_version": 1, "factions": [], "\U00010000": 1, "\uffee": 2}))
    add("upgraded-twice-code-point-order", json.dumps({"schema_version": 1, "factions": [{"id": "f", "buildings": [
        _b("r"), _b("u.\U00010000", requires=["r"], upgrades="r"), _b("u.\uffee", requires=["r"], upgrades="r")]}]}))
    add("duplicate-faction-unicode", json.dumps({"schema_version": 1, "factions": [
        {"id": "f\xe9\u200b", "buildings": [_b("b")]}, {"id": "f\xe9\u200b", "buildings": [_b("b")]}]}))
    add("duplicate-building-unicode", json.dumps({"schema_version": 1, "factions": [
        {"id": "fa\xe7", "buildings": [_b("b'\xe9"), _b("b'\xe9")]}]}))
    return cases


# --------------------------------------------------------------------------
# Serialisation helpers
# --------------------------------------------------------------------------

def _res(r):
    return [getattr(r, n) for n in NAMES]


def _ev(e):
    d = asdict(e)
    d["type"] = type(e).__name__
    return d


def _cmd(c):
    d = asdict(c)
    d["type"] = type(c).__name__
    return d


def _canon(s):
    return T.canonical(s).decode("ascii")


def _err(e):
    return {"kind": type(e).__name__, "message": str(e)}


def _pol(p):
    return {"citadel_rounding": p.citadel_rounding}


# --------------------------------------------------------------------------
# Small functions
# --------------------------------------------------------------------------

def _policy_cases():
    cases = []
    for v in ("floor", "ceil", "nearest"):
        cases.append({"citadel_rounding": v})
    for v in ("round", "", "FLOOR", "Floor", " floor", "floor ", "nearest ", "up", "it's", 'say "x"', "it's \"q\"",
              "caf\xe9", "\u200b", "tab\t", "\U0001F600", "back\\slash", "nl\n"):
        try:
            T.TownPolicy(v)
        except ValueError as e:
            cases.append({"citadel_rounding": v, "message": str(e)})
        else:
            raise AssertionError(v)
    return cases


def _weekly_cases():
    cases = []

    def add(base, bonus, horde, mode):
        c = {"base": base, "bonus": list(bonus), "horde": horde, "mode": mode}
        try:
            c["result"] = T.weekly_growth(base, bonus, horde, T.TownPolicy(mode))
        except Exception as e:      # ZeroDivisionError for a zero denominator
            c["error"] = _err(e)
        cases.append(c)

    bonuses = ((0, 1), (1, 2), (1, 1), (1, 3), (2, 3), (3, 2), (3, 4), (5, 4), (2, 4), (7, 3), (1, 7), (13, 5),
               (0, 5), (4, 4), (10, 3), (9, 2))
    for mode in MODES:
        for bonus in bonuses:
            for base in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 25, 49, 50, 99, 100, 1001):
                add(base, bonus, (base * 7) % 5, mode)
    for mode in MODES:
        for base, bonus, horde in (
                (CAP, (CAP, CAP - 1), CAP), (CAP, (CAP - 1, CAP), CAP), (CAP, (CAP, 1), CAP), (CAP, (1, CAP), 0),
                (CAP, (CAP, CAP), 0), (CAP - 1, (CAP, CAP - 2), 0), (1, (CAP, 1), 0), (CAP, (0, 1), CAP),
                (1 << 30, (CAP, CAP - 1), 1), (46341, (CAP, 2), 0), (3037000499, (1, 3037000499), 0),
                (10 ** 9, (3, 2), 10 ** 9), (2 ** 40, (1, 3), 5), (2 ** 40 + 1, (1, 2), 0), (2 ** 40 + 1, (2, 3), 1)):
            add(base, bonus, horde, mode)
        # negative operands (Python floor division semantics; unreachable from loaded content)
        for base, bonus in ((-7, (1, 2)), (7, (-1, 2)), (7, (1, -2)), (-7, (-1, 2)), (-1, (1, 2)), (-13, (1, 3)),
                            (13, (-1, 3)), (-13, (3, -2)), (5, (-5, 10)), (0, (-3, 1))):
            add(base, bonus, 1, mode)
        # a zero denominator
        add(5, (1, 0), 0, mode)
        add(0, (-3, 0), 2, mode)
    return cases


def _stream_cases():
    cases = []
    for seed in (0, 1, 2026, -1, 2 ** 63, 2 ** 64 + 5, -2 ** 70, 12345678901234567890, 0x5EED):
        for gid in ("golden", "", "g:1", "h\xe9ro-\u4e2d-\U0001F600", "x" * 100, "t"):
            r = T.town_rng(seed, gid)
            state = r.state
            draws = [r.range(0, 1000) for _ in range(3)] + [r.range(0, CAP), r.range(0, 1 << 32)]
            cases.append({"seed": seed, "game_id": gid, "state": state, "draws": draws, "after": r.state})
    return cases


# --------------------------------------------------------------------------
# Descriptors, create_game
# --------------------------------------------------------------------------

def _mk_players(d):
    if isinstance(d, dict):
        return d["raw"]
    return [A.Resources(*x["res"]) if "res" in x else x["raw"] for x in d]


def _mk_towns(d):
    if isinstance(d, dict):
        return d["raw"]
    return [T.TownSetup(**x["setup"]) if "setup" in x else x["raw"] for x in d]


def _res_d(*vals, **kw):
    v = dict(zip(NAMES, vals))
    v.update(kw)
    return {"res": [v.get(n, 0) for n in NAMES]}


def _setup(id, faction, owner, built=()):
    return {"setup": {"id": id, "faction": faction, "owner": owner, "built": list(built)}}


RICH = _res_d(100000, 200, 200, 20, 20, 20, 20)
FERN = "faction.fernwood"
SALT = "faction.saltmarsh"


def _create_cases():
    cases = []

    def add(name, pack, players, towns, game_id="g", policy=T.DEFAULT_POLICY):
        c = {"name": name, "pack": pack, "game_id": game_id, "players": players, "towns": towns, "policy": _pol(policy)}
        try:
            s = T.create_game(game_id, CONTENT[pack], _mk_players(players), _mk_towns(towns), policy)
        except ValueError as e:
            c["error"] = _err(e)
        else:
            c["hash"] = T.state_hash(s)
            c["canonical"] = _canon(s)
        cases.append(c)

    one = [_setup("t1", FERN, 0, ("hall.1",))]
    # --- successes
    add("basic", "test", [RICH], one)
    add("no-towns", "test", [RICH], [])
    add("empty-built", "test", [RICH], [_setup("t1", FERN, 0)])
    add("built-sorted-whatever-the-order-a", "test", [RICH], [_setup("t1", FERN, 0, ("market", "hall.1"))])
    add("built-sorted-whatever-the-order-b", "test", [RICH], [_setup("t1", FERN, 0, ("hall.1", "market"))])
    add("closed-chain", "test", [RICH], [_setup("t1", FERN, 0, ("hall.1", "keep.1", "keep.2", "keep.3", "den.1", "hive"))])
    add("all-fernwood", "test", [RICH], [_setup("t1", FERN, 0, [b.id for b in CONTENT["test"].factions[0].buildings
                                                                 if b.id != "hall.4"])])
    add("two-players-three-towns", "test", [RICH, _res_d(5, 4, 3, 2, 1, 0, 9)],
        [_setup("a", FERN, 0, ("hall.1",)), _setup("b", SALT, 1), _setup("c", FERN, 1, ("hall.1", "keep.1"))])
    add("treasury-at-cap", "test", [_res_d(*([CAP] * 7))], one)
    add("treasury-zero", "test", [_res_d()], one)
    add("capital-different-players", "test", [RICH, RICH],
        [_setup("a", FERN, 0, ("hall.1", "hall.2", "market", "keep.1", "keep.2", "keep.3", "hall.3", "hall.4")),
         _setup("b", FERN, 1, ("hall.1", "hall.2", "market", "keep.1", "keep.2", "keep.3", "hall.3", "hall.4"))])
    add("unique-tags-differ-and-plain-repeats", "twin", [RICH], [_setup("a", "f.one", 0, ("cap.a", "other")),
                                                                _setup("b", "f.one", 0, ("plain",))])
    add("unique-same-other-tag-twice", "twin", [RICH], [_setup("a", "f.one", 0, ("cap.a", "other")),
                                                       _setup("b", "f.one", 0, ("other",))])
    add("game-id-int", "test", [RICH], one, game_id=5)
    add("game-id-none", "test", [RICH], one, game_id=None)
    add("game-id-bool", "test", [RICH], one, game_id=True)
    add("game-id-list", "test", [RICH], one, game_id=[1, "a"])
    add("game-id-dict", "test", [RICH], one, game_id={"a": None})
    add("game-id-unicode", "test", [RICH], one, game_id="g\xe9-\u4e2d-\U0001F600")
    add("game-id-empty", "test", [RICH], one, game_id="")
    add("game-id-control", "test", [RICH], one, game_id="a\x01\n\"'\\")
    add("policy-ceil", "test", [RICH], one, policy=T.TownPolicy("ceil"))
    add("policy-nearest", "test", [RICH], one, policy=T.TownPolicy("nearest"))
    add("unicode-pack", "unicode", [RICH], [_setup("t\xe9", UNI_F[0], 0, ("hall.\xe9", "hall.\U00010000", "keep.\u4e2d")),
                                            _setup("t\U0001F600", UNI_F[1], 0, ("hall.\uffee",)),
                                            _setup("t\u200b", UNI_F[2], 0, ())])
    add("town-ids-non-printable", "test", [RICH], [_setup("\u200b", FERN, 0), _setup("\x7f", FERN, 0), _setup("a\tb", FERN, 0),
                                                   _setup("\U000e0001\ue000", FERN, 0)])
    add("town-id-edge-spaces", "test", [RICH], [_setup(" a ", FERN, 0), _setup("\u200b ", FERN, 0)])
    add("big-pack", "bigvalues", [_res_d(*([CAP] * 7))], [_setup("t", "f.big", 0, ("hall", "fort", "fort2", "d1"))])
    add("many-towns-same-faction", "tiny", [RICH], [_setup("t%d" % i, "f.a", 0, ("hall",)) for i in range(12)])

    # --- players
    for name, v in (("none", None), ("string", "abc"), ("int", 5), ("object", {}), ("true", True)):
        add("players-raw-" + name, "test", {"raw": v}, one)
    add("players-empty", "test", [], one)
    add("players-empty-and-bad-towns", "test", [], {"raw": None})
    for name, v in (("int", 5), ("none", None), ("string", "x"), ("list-of-seven", [1, 2, 3, 4, 5, 6, 7]),
                    ("dict", {"gold": 1}), ("true", True)):
        add("player-raw-" + name, "test", [{"raw": v}], one)
    add("player-second-bad", "test", [RICH, {"raw": None}], one)
    add("player-first-bad-second-bad-too", "test", [{"raw": 5}, {"raw": None}], one)
    for i, n in enumerate(NAMES):
        for tag, v in (("true", True), ("false", False), ("string", "1"), ("none", None), ("negative", -1),
                       ("cap-plus-one", CAP + 1), ("huge", 2 ** 70), ("list", [1]), ("dict", {}), ("negative-huge", -2 ** 70)):
            vals = [1] * 7
            vals[i] = v
            add("resource-%s-%s" % (n, tag), "test", [{"res": vals}], one)
        vals = [0] * 7
        vals[i] = CAP
        add("resource-%s-cap-ok" % n, "test", [{"res": vals}], one)
    add("resource-two-bad-first-reported-by-player", "test", [_res_d(-1), _res_d(True)], one)

    # --- towns container
    for name, v in (("none", None), ("string", "t1"), ("int", 5), ("object", {}), ("true", True)):
        add("towns-raw-" + name, "test", [RICH], {"raw": v})
    # --- town element
    for name, v in (("none", None), ("int", 5), ("string", "x"), ("true", True), ("dict", {"id": "t"}), ("empty-list", []),
                    ("unicode-string", "\xe9'\"")):
        add("town-raw-" + name, "test", [RICH], [{"raw": v}])
    add("town-raw-after-valid-town", "test", [RICH], [_setup("a", FERN, 0), {"raw": None}])
    # --- id
    for name, v in (("int", 1), ("none", None), ("true", True), ("list", ["t"]), ("dict", {}), ("empty", ""),
                    ("spaces", "   "), ("tab-nl", "\t\n\r"), ("nbsp", "\xa0"), ("ideographic-space", "\u3000"),
                    ("line-sep", "\u2028"), ("fs-gs-rs-us", "\x1c\x1d\x1e\x1f"), ("nel", "\u0085"), ("ogham-space", "\u1680")):
        add("town-id-" + name, "test", [RICH], [_setup(v, FERN, 0)])
    add("town-id-bad-and-faction-bad", "test", [RICH], [_setup(1, 5, True, "x")])
    # --- faction
    for name, v in (("int", 5), ("none", None), ("true", True), ("list", [FERN])):
        add("town-faction-" + name, "test", [RICH], [_setup("t", v, 0)])
    add("town-faction-bad-and-owner-bad", "test", [RICH], [_setup("t", 5, True)])
    # --- owner
    for name, v in (("true", True), ("false", False), ("string", "0"), ("none", None), ("list", [0]), ("dict", {})):
        add("town-owner-" + name, "test", [RICH], [_setup("t", FERN, v)])
    add("town-owner-bad-and-built-bad", "test", [RICH], [_setup("t", FERN, "0", "x")])
    # --- built
    for name, v in (("string", "hall.1"), ("none", None), ("int", 5), ("dict", {"hall.1": 1}), ("true", True)):
        add("town-built-" + name, "test", [RICH], [_setup("t", FERN, 0, ())] + [{"setup": {"id": "u", "faction": FERN, "owner": 0, "built": v}}])
    add("town-built-int-item", "test", [RICH], [{"setup": {"id": "t", "faction": FERN, "owner": 0, "built": ["hall.1", 5]}}])
    add("town-built-none-item", "test", [RICH], [{"setup": {"id": "t", "faction": FERN, "owner": 0, "built": [None]}}])
    add("town-built-list-item", "test", [RICH], [{"setup": {"id": "t", "faction": FERN, "owner": 0, "built": [["hall.1"]]}}])
    add("town-built-bad-and-duplicate-id", "test", [RICH], [_setup("t", FERN, 0), {"setup": {"id": "t", "faction": FERN, "owner": 0, "built": "x"}}])
    # --- value checks, in order
    add("duplicate-town-id", "test", [RICH], [_setup("t", FERN, 0), _setup("t", SALT, 0)])
    add("duplicate-town-id-quote", "test", [RICH], [_setup("it's", FERN, 0), _setup("it's", FERN, 0)])
    add("duplicate-before-faction-check", "test", [RICH], [_setup("t", FERN, 0), _setup("t", "faction.none", 0)])
    add("unknown-faction", "test", [RICH], [_setup("t", "faction.none", 0)])
    add("unknown-faction-empty", "test", [RICH], [_setup("t", "", 0)])
    add("unknown-faction-repr", "test", [RICH], [_setup("t'", "fa\"c'\u200b\U0001F600\x01", 0)])
    add("unknown-faction-case", "test", [RICH], [_setup("t", "Faction.Fernwood", 0)])
    add("unknown-faction-before-owner", "test", [RICH], [_setup("t", "faction.none", 9)])
    for name, v in (("negative", -1), ("equal-to-count", 1), ("past", 2), ("huge", 2 ** 70), ("negative-huge", -2 ** 70),
                    ("beyond-int", 2 ** 40)):
        add("owner-" + name, "test", [RICH], [_setup("t", FERN, v)])
    add("owner-before-building-check", "test", [RICH], [_setup("t", FERN, 5, ("zzz",))])
    add("owner-second-player-ok", "test", [RICH, RICH], [_setup("t", FERN, 1)])
    add("unknown-building", "test", [RICH], [_setup("t", FERN, 0, ("zzz",))])
    add("unknown-building-other-faction", "test", [RICH], [_setup("t", FERN, 0, ("wall.1",))])
    add("duplicate-building", "test", [RICH], [_setup("t", FERN, 0, ("hall.1", "hall.1"))])
    add("duplicate-and-unknown", "test", [RICH], [_setup("t", FERN, 0, ("hall.1", "hall.1", "zzz"))])
    add("missing-requirement", "test", [RICH], [_setup("t", FERN, 0, ("market",))])
    add("missing-requirement-lists-all", "test", [RICH], [_setup("t", FERN, 0, ("hall.2",))])
    add("missing-requirement-lists-all-even-if-some-built", "test", [RICH], [_setup("t", FERN, 0, ("hall.1", "hall.2"))])
    add("missing-requirement-first-in-id-order", "test", [RICH], [_setup("t", FERN, 0, ("den.1u", "hall.1"))])
    add("missing-requirement-unicode", "unicode", [RICH], [_setup("t", UNI_F[0], 0, ("hall.\U00010000", "keep.\U0001F600"))])
    add("later-town-fails-first-town-ok", "test", [RICH], [_setup("a", FERN, 0), _setup("b", FERN, 0, ("market",))])
    add("first-town-fails-second-town-bad-type", "test", [RICH], [_setup("a", FERN, 0, ("market",)), {"raw": None}])
    add("first-town-bad-type-second-fails", "test", [RICH], [{"raw": 5}, _setup("b", FERN, 0, ("market",))])
    add("unique-two-in-two-towns", "test", [RICH], [
        _setup("a", FERN, 0, ("hall.1", "hall.2", "market", "keep.1", "keep.2", "keep.3", "hall.3", "hall.4")),
        _setup("b", SALT, 0, ("hall.1", "hall.2", "wall.1", "wall.2", "wall.3", "hall.3", "hall.4"))])
    add("unique-two-in-one-town", "twin", [RICH], [_setup("a", "f.one", 0, ("cap.a", "cap.b"))])
    add("unique-across-factions", "twin", [RICH], [_setup("a", "f.one", 0, ("cap.a",)), _setup("b", "f.two", 0, ("cap.c",))])
    add("unique-three", "twin", [RICH], [_setup("a", "f.one", 0, ("cap.a", "cap.b")), _setup("b", "f.two", 0, ("cap.c",))])
    add("unique-tag-quote-in-message", "unicode", [RICH], [
        _setup("a", UNI_F[0], 0, ("hall.\xe9", "hall.\U00010000")), _setup("b", UNI_F[0], 0, ("hall.\xe9", "hall.\U00010000"))])
    add("unique-checked-after-all-towns", "twin", [RICH], [_setup("a", "f.one", 0, ("cap.a",)), _setup("b", "f.one", 0, ("cap.a",)),
                                                           _setup("c", "f.one", 0, ("zzz",))])
    return cases


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------

def _qres(fn, r):
    if fn in ("active_buildings", "missing_requirements"):
        return list(r)
    if fn in ("town_income", "player_income"):
        return _res(r)
    if fn == "dwellings":
        return [list(x) for x in r]
    if fn == "growth_pools":
        return [[p.id, p.available, p.growth] for p in r]
    raise AssertionError(fn)


def _q(s, fn, *args):
    """One query record: ``{"fn", "args", "result" | "error"}``; a growth_pools ``current`` is [[id, available, growth]]."""
    rec = {"fn": fn, "args": list(args)}
    call = list(args)
    if fn == "growth_pools":
        call = [args[0], tuple(A.GrowthPool(*p) for p in args[1])]
    try:
        r = getattr(T, fn)(s, *call)
    except Exception as e:
        rec["error"] = _err(e)
    else:
        rec["result"] = _qres(fn, r)
    return rec


def _current(town, i):
    """Carried-over pools for growth_pools: a junk id, a duplicate id (the last one wins) and one per level."""
    return [["other:dwelling1", 77, 0], ["%s:dwelling1" % town, 1, 0], ["%s:dwelling1" % town, 10 * i + 1, 0],
            ["%s:dwelling2" % town, 10 * i + 2, 0], ["%s:dwelling3" % town, 10 * i + 3, 0]]


def _snapshot(s, i, full=False):
    out = []
    for t in s.towns:
        out.append(_q(s, "active_buildings", t.id))
        out.append(_q(s, "town_income", t.id))
        out.append(_q(s, "dwellings", t.id))
        out.append(_q(s, "growth_pools", t.id, _current(t.id, i)))
        if full:
            out.append(_q(s, "growth_pools", t.id, []))
            for f in s.content.factions:
                if f.id == t.faction:
                    for b in f.buildings:
                        out.append(_q(s, "missing_requirements", t.id, b.id))
    for p in range(len(s.players)):
        out.append(_q(s, "player_income", p))
    return out


# --------------------------------------------------------------------------
# Traces
# --------------------------------------------------------------------------

class _Fail:
    """The town core is not random: any draw is a bug."""

    def __getattr__(self, name):
        raise AssertionError("rng used: %s" % name)


def _step(s, cmd, rng, i):
    """Apply ``cmd`` to ``s``; (new state, step record). Checks the stream is never touched."""
    rec = {"cmd": _cmd(cmd)}
    before = (T.state_hash(s), rng.state)
    try:
        s2, ev = T.apply(s, cmd, rng)
    except (T.IllegalCommand, KeyError) as e:
        rec["error"] = _err(e)
        s2 = s
        assert (T.state_hash(s), rng.state) == before
    else:
        rec["events"] = [_ev(e) for e in ev]
        rec["queries"] = _snapshot(s2, i)
    assert rng.state == before[1], "the town core drew from its stream"
    rec["hash"] = T.state_hash(s2)
    rec["rng"] = rng.state
    return s2, rec


def _trace(name, pack, game_id, players, towns, policy, seed, plan, max_steps):
    """Play ``plan(state, i) -> command | None`` from ``create_game`` and record everything."""
    s = T.create_game(game_id, CONTENT[pack], _mk_players(players), _mk_towns(towns), policy)
    rng = T.town_rng(seed, game_id)
    t = {"name": name, "pack": pack, "game_id": game_id, "players": players, "towns": towns, "policy": _pol(policy),
         "seed": seed, "initial_hash": T.state_hash(s), "initial_rng": rng.state,
         "initial_queries": _snapshot(s, 0, full=True), "steps": []}
    for i in range(max_steps):
        cmd = plan(s, i)
        if cmd is None:
            break
        s, rec = _step(s, cmd, rng, i + 1)
        t["steps"].append(rec)
    t["final_canonical"] = _canon(s)
    t["final_queries"] = _snapshot(s, len(t["steps"]) + 1, full=True)
    return t


def _random_plan(tag):
    drv = derive_stream(0x70A5, "vectors:town:plan", tag)
    junk_towns = ("nope", "", "T1", "\xe9", "it's")

    def plan(s, i):
        op = drv.range(0, 100)
        if op < 12:
            return T.NewDay()
        if op >= 92:
            k = drv.range(0, 6)
            town = s.towns[drv.range(0, len(s.towns))] if s.towns else None
            bld = "market"
            if k == 0:
                return T.Build(drv.range(0, len(s.players)), junk_towns[drv.range(0, len(junk_towns))], bld)
            if k == 1:
                return T.Build(-1, town.id, bld)
            if k == 2:
                return T.Build(len(s.players) + drv.range(0, 3), town.id, bld)
            if k == 3:
                return T.Build(2 ** 40, town.id, bld)
            if k == 4:
                return T.Build(town.owner, town.id, "")
            return T.Build(town.owner, town.id, "no.such.building")
        town = s.towns[drv.range(0, len(s.towns))]
        if town.built_today and drv.range(0, 100) < 85:
            return T.NewDay()
        fac = T._faction(s.content, town.faction)
        cands = [b.id for b in fac.buildings if b.id not in town.built and all(r in town.built for r in b.requires)]
        if op < 75 and cands:
            bid = cands[drv.range(0, len(cands))]
        else:
            bid = fac.buildings[drv.range(0, len(fac.buildings))].id
        roll = drv.range(0, 100)
        player = town.owner if roll < 88 else drv.range(0, len(s.players))
        return T.Build(player, town.id, bid)

    return plan


def _script_plan(cmds):
    def plan(s, i):
        return cmds[i] if i < len(cmds) else None
    return plan


def _full_build_script(content, towns):
    """Build every building of every town in dependency order, one build per town per day."""
    cmds = []
    todo = {t["setup"]["id"]: [b.id for b in T._faction(content, t["setup"]["faction"]).buildings
                               if b.id not in t["setup"]["built"]] for t in towns}
    built = {t["setup"]["id"]: set(t["setup"]["built"]) for t in towns}
    owner = {t["setup"]["id"]: t["setup"]["owner"] for t in towns}
    fac = {t["setup"]["id"]: T._faction(content, t["setup"]["faction"]) for t in towns}
    for _ in range(60):
        progressed = False
        for tid, left in todo.items():
            for bid in left:
                b = next(x for x in fac[tid].buildings if x.id == bid)
                if all(r in built[tid] for r in b.requires):
                    cmds.append(T.Build(owner[tid], tid, bid))
                    built[tid].add(bid)
                    left.remove(bid)
                    progressed = True
                    break
        cmds.append(T.NewDay())
        if not progressed:
            break
    return cmds


def _traces():
    out = []
    pr = {
        "rich": [RICH, RICH],
        "mid": [_res_d(20000, 40, 40, 3, 3, 3, 3), _res_d(15000, 30, 30, 2, 2, 2, 2)],
        "poor": [_res_d(3000, 10, 10, 1, 1, 1, 1), _res_d(2600, 8, 8, 0, 0, 0, 0)],
    }
    test_towns = {
        "three": [_setup("north", FERN, 0, ("hall.1",)), _setup("south", SALT, 1, ("hall.1",)),
                  _setup("east", FERN, 1, ("hall.1", "keep.1"))],
        "same-player": [_setup("a", FERN, 0), _setup("b", SALT, 0), _setup("c", FERN, 0, ("hall.1",))],
        "one": [_setup("solo", SALT, 0)],
    }
    n = 0
    for tname, towns in test_towns.items():
        for pname, players in pr.items():
            for pi, pol in enumerate(POLICIES):
                n += 1
                tag = "random-test-%s-%s-%s" % (tname, pname, pol.citadel_rounding)
                out.append(_trace(tag, "test", "g%d" % n, players, towns, pol, 100 + n, _random_plan(tag), 45))
    tiny_towns = [_setup("p", "f.a", 0, ("hall",)), _setup("q", "f.b", 1), _setup("r", "f.a", 1, ("fort",))]
    for pi, pol in enumerate(POLICIES):
        for seed in (1, 2):
            tag = "random-tiny-%s-%d" % (pol.citadel_rounding, seed)
            out.append(_trace(tag, "tiny", "tiny", pr["rich"], tiny_towns, pol, seed, _random_plan(tag), 60))
    uni_towns = [_setup("t\xe9", UNI_F[0], 0), _setup("t\U0001F600", UNI_F[1], 1), _setup("t\uffee", UNI_F[2], 0)]
    for pi, pol in enumerate(POLICIES):
        tag = "random-unicode-" + pol.citadel_rounding
        out.append(_trace(tag, "unicode", "g\xe9-\U0001F600", pr["rich"], uni_towns, pol, 7 + pi, _random_plan(tag), 60))
    twin_towns = [_setup("a", "f.one", 0), _setup("b", "f.one", 0), _setup("c", "f.two", 1), _setup("d", "f.two", 0)]
    for seed in (3, 4):
        tag = "random-twin-%d" % seed
        out.append(_trace(tag, "twin", "twin", pr["rich"], twin_towns, T.DEFAULT_POLICY, seed, _random_plan(tag), 40))
    big_towns = [_setup("big", "f.big", 0), _setup("big2", "f.big", 0)]
    big_players = [_res_d(*([CAP] * 7))]
    for pol in POLICIES:
        tag = "random-big-" + pol.citadel_rounding
        out.append(_trace(tag, "bigvalues", "big", big_players, big_towns, pol, 11, _random_plan(tag), 40))

    # --- scripted
    for pack, towns, players in (
            ("test", test_towns["three"], pr["rich"]),
            ("tiny", tiny_towns, pr["rich"]),
            ("unicode", uni_towns, pr["rich"]),
            ("twin", twin_towns, pr["rich"]),
            ("bigvalues", big_towns, big_players)):
        for pol in (T.DEFAULT_POLICY, T.TownPolicy("nearest")):
            cmds = _full_build_script(CONTENT[pack], towns)
            out.append(_trace("full-build-%s-%s" % (pack, pol.citadel_rounding), pack, "full", players, towns, pol, 5,
                              _script_plan(cmds), len(cmds)))
    # exact money: a build costing everything is legal, one short is not
    for short in (0, 1):
        pl = [_res_d(500 - short, 5, 0, 0, 0, 0, 0)]
        out.append(_trace("exact-money-short-%d" % short, "test", "g", pl, [_setup("t", FERN, 0, ("hall.1",))],
                          T.DEFAULT_POLICY, 1, _script_plan([T.Build(0, "t", "market")]), 1))
    for i, n in enumerate(NAMES):
        for have_n in (2, 3):
            have = [3] * 7
            have[i] = have_n
            out.append(_trace("short-%s-%d" % (n, have_n), "seven", "g", [{"res": have}], [_setup("t", "f", 0)],
                              T.DEFAULT_POLICY, 1, _script_plan([T.Build(0, "t", "r." + n)]), 1))
    # one build per town per day, not per player
    two = [_setup("a", FERN, 0), _setup("b", FERN, 0)]
    cmds = [T.Build(0, "a", "hall.1"), T.Build(0, "b", "hall.1"), T.Build(0, "a", "keep.1"), T.Build(0, "b", "keep.1"),
            T.NewDay(), T.Build(0, "a", "keep.1"), T.Build(0, "a", "market"), T.NewDay(), T.Build(0, "a", "market"),
            T.NewDay(), T.NewDay(), T.Build(0, "b", "market")]
    out.append(_trace("one-build-per-town-per-day", "test", "g", [RICH], two, T.DEFAULT_POLICY, 1, _script_plan(cmds), len(cmds)))
    # capital: one per player over all towns, also inside one town
    cap_chain = ["hall.1", "market", "hall.2", "keep.1", "keep.2", "keep.3", "hall.3", "hall.4"]
    cmds = []
    for b in cap_chain:
        cmds += [T.Build(0, "a", b), T.NewDay()]
    cmds += [T.Build(0, "b", "hall.1"), T.NewDay(), T.Build(0, "b", "market"), T.NewDay(), T.Build(0, "b", "hall.2"), T.NewDay(),
             T.Build(0, "b", "keep.1"), T.NewDay(), T.Build(0, "b", "keep.2"), T.NewDay(), T.Build(0, "b", "keep.3"), T.NewDay(),
             T.Build(0, "b", "hall.3"), T.NewDay(), T.Build(0, "b", "hall.4"), T.Build(1, "c", "hall.1")]
    out.append(_trace("capital-once-per-player", "test", "g", [RICH, RICH],
                      [_setup("a", FERN, 0), _setup("b", FERN, 0), _setup("c", FERN, 1, ())], T.DEFAULT_POLICY, 1,
                      _script_plan(cmds), len(cmds)))
    cmds = [T.Build(0, "a", "cap.a"), T.NewDay(), T.Build(0, "a", "cap.b"), T.Build(0, "a", "other"), T.NewDay(),
            T.Build(0, "b", "cap.c"), T.Build(0, "b", "plain"), T.Build(1, "c", "cap.c"), T.Build(0, "d", "cap.c")]
    out.append(_trace("capital-same-town-and-across-factions", "twin", "g", [RICH, RICH],
                      [_setup("a", "f.one", 0), _setup("b", "f.two", 0), _setup("c", "f.two", 1), _setup("d", "f.two", 0)],
                      T.DEFAULT_POLICY, 1, _script_plan(cmds), len(cmds)))
    # many days
    cmds = [T.NewDay() for _ in range(40)] + [T.Build(0, "t", "b")]
    out.append(_trace("forty-days", "minimal", "g", [_res_d(1)], [_setup("t", "f", 0)], T.DEFAULT_POLICY, 1,
                      _script_plan(cmds), len(cmds)))
    # growth with carried pools: the castle bonus is the largest active one, hordes add after it
    cmds = []
    for b in ("fort", "d1", "d3", "cit", "d2", "h1a", "bless", "h1b", "d1u", "cas", "h2", "h3", "bless2", "hall", "hall2"):
        cmds += [T.Build(0, "p", b), T.NewDay()]
    for pol in POLICIES:
        out.append(_trace("growth-mix-tiny-" + pol.citadel_rounding, "tiny", "g", [RICH], [_setup("p", "f.a", 0)], pol, 1,
                          _script_plan(cmds), len(cmds)))
    return out


# --------------------------------------------------------------------------
# Standalone query cases and hand-built states
# --------------------------------------------------------------------------

def _game(pack, players, towns, policy=T.DEFAULT_POLICY, game_id="g"):
    return T.create_game(game_id, CONTENT[pack], _mk_players(players), _mk_towns(towns), policy)


def _query_cases():
    s = _game("test", [RICH, RICH], [_setup("north", FERN, 0, ("hall.1", "keep.1", "den.1")), _setup("south", SALT, 1, ("hall.1",))])
    cases = []
    for fn, args in (
            ("active_buildings", ["nope"]), ("active_buildings", [""]), ("active_buildings", ["it's"]), ("active_buildings", ["a\"'\u200b"]),
            ("town_income", ["nope"]), ("dwellings", ["nope"]), ("growth_pools", ["nope", []]),
            ("missing_requirements", ["nope", "market"]), ("missing_requirements", ["north", "nope"]),
            ("missing_requirements", ["north", ""]), ("missing_requirements", ["north", "wall.1"]),
            ("missing_requirements", ["north", "it's"]), ("missing_requirements", ["north", "market"]),
            ("missing_requirements", ["north", "hall.4"]), ("missing_requirements", ["north", "hall.1"]),
            ("missing_requirements", ["south", "hall.3"]), ("player_income", [0]), ("player_income", [1]),
            ("player_income", [2]), ("player_income", [-1]), ("player_income", [2 ** 40]),
            ("growth_pools", ["north", []]), ("growth_pools", ["north", [["north:dwelling1", 9, 1]]]),
            ("growth_pools", ["north", [["north:dwelling1", 9, 1], ["north:dwelling1", 4, 1]]]),
            ("growth_pools", ["north", [["north:dwelling1", CAP, 0], ["north:dwelling2", 0, 0]]]),
            ("growth_pools", ["north", [["north:dwelling1", -5, 0]]]),
            ("growth_pools", ["north", [["north:dwelling1", 2 ** 40, 0]]]),
            ("growth_pools", ["south", [["north:dwelling1", 9, 1]]])):
        cases.append({"name": "%s-%s" % (fn, len(cases)), "pack": "test", "state": json.loads(_canon(s)), "hash": T.state_hash(s),
                      "query": _q(s, fn, *args)})
    return cases


def _mk_state(content, players, towns, day=1, policy=T.DEFAULT_POLICY, game_id="hand"):
    return T.TownState(game_id, policy, content, tuple(players), tuple(towns), day)


def _bld(id, requires=(), **kw):
    return T.Building(id=id, cost=kw.pop("cost", A.Resources()), requires=tuple(requires), **kw)


def _states():
    cases = []
    test = CONTENT["test"]
    R = A.Resources

    def add(name, s, cmd=None, queries=(), seed=5):
        c = {"name": name, "state": json.loads(_canon(s)), "hash": T.state_hash(s), "seed": seed}
        rng = T.town_rng(seed, s.game_id)
        c["rng_before"] = rng.state
        if cmd is not None:
            c["cmd"] = _cmd(cmd)
            try:
                s2, ev = T.apply(s, cmd, rng)
            except (T.IllegalCommand, KeyError) as e:
                c["error"] = _err(e)
                s2 = s
            else:
                c["events"] = [_ev(e) for e in ev]
                c["hash_after"] = T.state_hash(s2)
                c["canonical_after"] = _canon(s2)
        else:
            s2 = s
        c["rng_after"] = rng.state
        assert c["rng_after"] == c["rng_before"]
        c["queries"] = [_q(s, fn, *a) for fn, a in queries]
        if cmd is not None and "events" in c:
            c["queries_after"] = [_q(s2, fn, *a) for fn, a in queries]
        cases.append(c)

    def town(id, faction=FERN, owner=0, built=(), today=False):
        return T.Town(id, faction, owner, tuple(built), today)

    allq = [("active_buildings", ["t"]), ("town_income", ["t"]), ("dwellings", ["t"]), ("growth_pools", ["t", []]),
            ("missing_requirements", ["t", "market"]), ("player_income", [0]), ("player_income", [1])]
    rich = R(gold=100000, wood=200, ore=200, mercury=20, sulfur=20, crystal=20, gems=20)

    # unknown faction in a town
    chain = ("hall.1", "market", "hall.2", "keep.1", "keep.2", "keep.3", "hall.3")
    s = _mk_state(test, [rich], [town("t", "faction.none", 0, ("hall.1",)), town("u", FERN, 0, chain)])
    add("unknown-faction-build-there", s, T.Build(0, "t", "hall.1"), allq)
    add("unknown-faction-build-elsewhere-plain", s, T.Build(0, "u", "den.1"), allq + [("active_buildings", ["u"])])
    add("unknown-faction-build-elsewhere-unique-escapes-as-key-error", s, T.Build(0, "u", "hall.4"), [])
    add("unknown-faction-newday", s, T.NewDay(), allq)
    add("unknown-faction-player-income", s, None, [("player_income", [0]), ("town_income", ["u"])])
    s = _mk_state(test, [rich], [town("t", "faction.none", 0), town("u", FERN, 0, ("hall.1", "market", "hall.2"))])
    add("unknown-faction-with-tagless-build", s, T.Build(0, "u", "keep.1"), [("active_buildings", ["u"])])
    s = _mk_state(test, [rich], [town("t", "faction.none\xe9'", 0)])
    add("unknown-faction-repr-in-key-error", s, None, [("active_buildings", ["t"]), ("missing_requirements", ["t", "x"])])

    # content-side oddities
    empty_fac = T.TownContent((T.Faction("empty", ()), T.Faction("zz", (_bld("b"),)), T.Faction("aa", (_bld("b"),))))
    s = _mk_state(empty_fac, [R(gold=5)], [town("t", "empty", 0), town("u", "zz", 0), town("v", "aa", 0)])
    add("empty-faction-build", s, T.Build(0, "t", "b"), [("active_buildings", ["t"]), ("dwellings", ["t"]), ("growth_pools", ["t", []])])
    add("unsorted-factions-lookup", s, T.Build(0, "u", "b"), [("active_buildings", ["u"]), ("active_buildings", ["v"])])

    # state-side oddities
    base_towns = [town("t", FERN, 0, ("hall.1", "keep.1"))]
    add("built-today-flag", _mk_state(test, [rich], [town("t", FERN, 0, ("hall.1",), True)]), T.Build(0, "t", "market"), allq)
    add("built-today-cleared-by-newday", _mk_state(test, [rich], [town("t", FERN, 0, ("hall.1",), True), town("u", FERN, 0, (), True)]),
        T.NewDay(), [("active_buildings", ["t"])])
    add("unsorted-built-is-sorted-on-build", _mk_state(test, [rich], [town("t", FERN, 0, ("keep.1", "hall.1"))]), T.Build(0, "t", "market"), allq)
    add("unsorted-built-unicode", _mk_state(CONTENT["unicode"], [rich], [town("t", UNI_F[0], 0, ("hall.\xe9",))]),
        T.Build(0, "t", "hall.\U00010000"), [("active_buildings", ["t"])])
    add("unicode-sorts-by-code-point-on-build", _mk_state(CONTENT["unicode"], [rich], [town("t", UNI_F[0], 0, ("hall.\U00010000", "hall.\xe9", "hall.\uffee"))]),
        T.Build(0, "t", "keep.\u4e2d"), [("active_buildings", ["t"])])
    add("built-unknown-id-ignored", _mk_state(test, [rich], [town("t", FERN, 0, ("hall.1", "zzz", "wall.1"))]), T.Build(0, "t", "market"),
        allq)
    add("built-duplicates", _mk_state(test, [rich], [town("t", FERN, 0, ("hall.1", "hall.1", "keep.1"))]), T.Build(0, "t", "market"), allq)
    add("duplicate-town-ids-both-get-the-building", _mk_state(test, [rich, rich], [town("t", FERN, 0, ("hall.1",)), town("t", FERN, 1, ("hall.1",))]),
        T.Build(0, "t", "market"), [("active_buildings", ["t"]), ("player_income", [0]), ("player_income", [1])])
    add("duplicate-town-ids-second-owner-cannot-build", _mk_state(test, [rich, rich], [town("t", FERN, 0, ("hall.1",)), town("t", FERN, 1, ("hall.1",))]),
        T.Build(1, "t", "market"), [("player_income", [0]), ("player_income", [1])])
    add("no-players", _mk_state(test, [], [town("t", FERN, 0)]), T.Build(0, "t", "hall.1"), [("player_income", [0])])
    add("owner-out-of-range", _mk_state(test, [rich], [town("t", FERN, 5, ("hall.1",))]), T.Build(5, "t", "market"),
        [("player_income", [5]), ("player_income", [0])])
    add("owner-negative", _mk_state(test, [rich], [town("t", FERN, -1, ("hall.1",))]), T.Build(-1, "t", "market"), [("player_income", [-1])])
    add("other-owner", _mk_state(test, [rich, rich], base_towns), T.Build(1, "t", "market"), allq)
    add("big-day-newday", _mk_state(test, [rich], base_towns, day=2 ** 40), T.NewDay(), [])
    add("day-zero-newday", _mk_state(test, [rich], base_towns, day=0), T.NewDay(), [])
    add("negative-day-newday", _mk_state(test, [rich], base_towns, day=-5), T.NewDay(), [])
    add("treasury-negative-cannot-afford", _mk_state(test, [R(gold=-1)], [town("t", FERN, 0, ("hall.1",))]), T.Build(0, "t", "market"), [])
    add("treasury-negative-free-building", _mk_state(test, [R(gold=-1)], [town("t", FERN, 0)]), T.Build(0, "t", "hall.1"), [])
    add("treasury-above-int-cap", _mk_state(test, [R(gold=2 ** 40, wood=2 ** 40)], [town("t", FERN, 0, ("hall.1",))]),
        T.Build(0, "t", "market"), [])
    add("treasury-exactly-cost", _mk_state(test, [R(gold=500, wood=5)], [town("t", FERN, 0, ("hall.1",))]), T.Build(0, "t", "market"), [])

    # content with active-building oddities
    dup_level = T.TownContent((T.Faction("f", (
        _bld("fort", fort=True), _bld("a", ["fort"], dwelling_level=1, creature="cr.\U00010000", base_growth=4),
        _bld("b", ["fort"], dwelling_level=1, creature="cr.\uffee", base_growth=9),
        _bld("c", ["fort"], dwelling_level=1, creature="cr.\uffee", base_growth=2),
        _bld("h", ["a"], horde_level=1, horde_bonus=3),
    )),))
    s = _mk_state(dup_level, [R(gold=0)], [town("t", "f", 0, ("fort", "a", "b", "c", "h"))])
    add("two-active-dwellings-one-level", s, None, [("dwellings", ["t"]), ("growth_pools", ["t", [["t:dwelling1", 6, 0]]]), ("active_buildings", ["t"])])
    mixed_levels = T.TownContent((T.Faction("f", (
        _bld("z", dwelling_level=3, creature="z", base_growth=1), _bld("y", dwelling_level=2, creature="y", base_growth=1),
        _bld("x", dwelling_level=1, creature="x", base_growth=1),
        _bld("hz", horde_level=3, horde_bonus=2), _bld("h9", horde_level=9, horde_bonus=5),
        _bld("neg", horde_level=2, horde_bonus=-1))),))
    s = _mk_state(mixed_levels, [R()], [town("t", "f", 0, ("z", "y", "x", "hz", "h9", "neg"))])
    add("pools-ascending-by-level-not-content-order", s, None, [("dwellings", ["t"]), ("growth_pools", ["t", []]), ("active_buildings", ["t"])])
    bonuses = T.TownContent((T.Faction("f", (
        _bld("d", dwelling_level=1, creature="c", base_growth=13),
        _bld("p", growth_bonus=(1, 2)), _bld("q", growth_bonus=(2, 4)), _bld("r", growth_bonus=(1, 3)),
        _bld("neg", growth_bonus=(-1, 2)), _bld("negden", growth_bonus=(1, -2)), _bld("big", growth_bonus=(CAP, 2)),
        _bld("zero", growth_bonus=(0, 5)))),))
    for pol in POLICIES:
        for name, built in (("tie", ("d", "p", "q")), ("max-of-three", ("d", "p", "q", "r")), ("negative-ignored", ("d", "neg", "negden")),
                            ("zero", ("d", "zero")), ("large", ("d", "p", "big")), ("none", ("d",)), ("third-only", ("d", "r"))):
            s = _mk_state(bonuses, [R()], [town("t", "f", 0, built)], policy=pol)
            add("growth-bonus-%s-%s" % (name, pol.citadel_rounding), s, None, [("growth_pools", ["t", []])])
    zero_den = T.TownContent((T.Faction("f", (_bld("d", dwelling_level=1, creature="c", base_growth=13), _bld("z", growth_bonus=(1, 0)),
                                              _bld("zz", growth_bonus=(0, 0)))),))
    add("zero-denominator-active", _mk_state(zero_den, [R()], [town("t", "f", 0, ("d", "z"))]), None,
        [("growth_pools", ["t", []]), ("dwellings", ["t"]), ("town_income", ["t"])])
    add("zero-denominator-other-compare", _mk_state(zero_den, [R()], [town("t", "f", 0, ("d", "zz"))]), None, [("growth_pools", ["t", []])])
    add("zero-denominator-inactive", _mk_state(zero_den, [R()], [town("t", "f", 0, ("d",))]), None, [("growth_pools", ["t", []])])
    income = T.TownContent((T.Faction("f", (
        _bld("h1", income=R(gold=5, wood=-2)), _bld("h2", requires=("h1",), upgrades="h1", income=R(gold=7)),
        _bld("h3", requires=("h2",), upgrades="h2", income=R(gold=9, gems=1)), _bld("x", income=R(ore=2 ** 40)),
        _bld("y", income=R(ore=2 ** 40)), _bld("neg", cost=R(gold=-10)))),))
    add("income-chain-top-only", _mk_state(income, [R()], [town("t", "f", 0, ("h1", "h2", "h3", "x", "y"))]), None,
        [("town_income", ["t"]), ("player_income", [0]), ("active_buildings", ["t"])])
    add("income-chain-two-built", _mk_state(income, [R()], [town("t", "f", 0, ("h1", "h2", "x"))]), None, [("town_income", ["t"])])
    add("income-two-towns-one-player", _mk_state(income, [R(), R()], [town("t", "f", 0, ("h1", "x")), town("u", "f", 1, ("h2",)), town("v", "f", 0, ("y",))]),
        None, [("player_income", [0]), ("player_income", [1]), ("player_income", [2])])
    add("income-duplicate-town-ids", _mk_state(income, [R()], [town("t", "f", 0, ("h1",)), town("t", "f", 0, ("x",))]), None,
        [("player_income", [0]), ("town_income", ["t"])])
    add("negative-cost-adds-money", _mk_state(income, [R(gold=5)], [town("t", "f", 0)]), T.Build(0, "t", "neg"), [])
    add("upgrade-built-without-target", _mk_state(income, [R()], [town("t", "f", 0, ("h2",))]), None, [("active_buildings", ["t"]), ("town_income", ["t"])])
    add("upgrade-target-missing-in-content-order", _mk_state(income, [R()], [town("t", "f", 0, ("h3", "h1"))]), None,
        [("active_buildings", ["t"]), ("town_income", ["t"])])

    # unique tags on hand-built states
    uniq = T.TownContent((T.Faction("f", (_bld("c1", player_unique="cap"), _bld("c2", player_unique="cap"), _bld("o", player_unique="o"),
                                         _bld("n"))),))
    add("unique-held-in-other-town", _mk_state(uniq, [R(), R()], [town("a", "f", 0, ("c1",)), town("b", "f", 0)]), T.Build(0, "b", "c2"), [])
    add("unique-held-by-other-player-is-fine", _mk_state(uniq, [R(), R()], [town("a", "f", 1, ("c1",)), town("b", "f", 0)]), T.Build(0, "b", "c2"), [])
    add("unique-held-in-same-town", _mk_state(uniq, [R()], [town("a", "f", 0, ("c1",))]), T.Build(0, "a", "c2"), [])
    add("unique-different-tag", _mk_state(uniq, [R()], [town("a", "f", 0, ("c1",))]), T.Build(0, "a", "o"), [])
    add("unique-untagged-building-ignores-tags", _mk_state(uniq, [R()], [town("a", "f", 0, ("c1", "c2"))]), T.Build(0, "a", "n"), [])
    add("unique-count-skips-duplicates-of-owner", _mk_state(uniq, [R(), R()], [town("a", "f", 0, ("c1", "c1")), town("b", "f", 1)]), T.Build(1, "b", "c2"), [])

    # illegal commands in the documented check order, one failure at a time
    s = _game("test", [RICH, _res_d(10)], [_setup("t", FERN, 0, ("hall.1",)), _setup("u", FERN, 1, ("hall.1",))])
    for name, cmd in (("player-negative", T.Build(-1, "t", "market")), ("player-past", T.Build(2, "t", "market")),
                      ("player-huge", T.Build(2 ** 40, "t", "market")), ("town-unknown", T.Build(0, "x", "market")),
                      ("town-unknown-quote", T.Build(0, "it's \"x\"", "market")), ("not-owner", T.Build(1, "t", "market")),
                      ("building-unknown", T.Build(0, "t", "zzz")), ("building-empty", T.Build(0, "t", "")),
                      ("building-other-faction", T.Build(0, "t", "wall.1")), ("already-built", T.Build(0, "t", "hall.1")),
                      ("missing-one", T.Build(0, "t", "hall.2")), ("missing-several", T.Build(0, "t", "hall.3")),
                      ("cannot-afford", T.Build(1, "u", "market")), ("fine", T.Build(0, "t", "market"))):
        add("order-" + name, s, cmd, [])
    return cases


# --------------------------------------------------------------------------
# Golden
# --------------------------------------------------------------------------

GOLDEN_TOWNS = [_setup("north", FERN, 0, ("hall.1",)), _setup("south", SALT, 1, ("hall.1",)),
                _setup("east", FERN, 1, ("hall.1", "keep.1"))]
GOLDEN_PLAYERS = [_res_d(30000, 60, 60, 4, 0, 0, 2), _res_d(25000, 20, 50, 2, 5)]
GOLDEN_SCRIPT = (
    ((0, "north", "keep.1"), (1, "south", "wall.1"), (1, "east", "den.1")),
    ((0, "north", "den.1"), (1, "south", "pool.1"), (1, "east", "nest.2")),
    ((0, "north", "market"), (1, "south", "hall.2"), (1, "east", "hive")),
    ((0, "north", "keep.2"), (1, "south", "reef.2"), (1, "east", "market")),
    ((0, "north", "hive"), (1, "south", "wall.2")),
    ((0, "north", "nest.2"), (1, "east", "den.1u")),
    ((0, "north", "hall.2"),),
)


def _golden_run(policy):
    s = T.create_game("golden", CONTENT["test"], _mk_players(GOLDEN_PLAYERS), _mk_towns(GOLDEN_TOWNS), policy)
    n = 0
    for day in GOLDEN_SCRIPT:
        for p, t, b in day:
            s, ev = T.apply(s, T.Build(p, t, b), _Fail())
            n += len(ev)
        s, ev = T.apply(s, T.NewDay(), _Fail())
        n += len(ev)
    pools = [p for t in s.towns for p in T.growth_pools(s, t.id)]
    return s, n, pools


def _golden():
    s, n, pools = _golden_run(T.DEFAULT_POLICY)
    digest = []
    for mode in MODES:
        _, _, ps = _golden_run(T.TownPolicy(mode))
        digest.append([mode, [[p.id, p.available, p.growth] for p in ps]])
    return {"pack": "test", "game_id": "golden", "players": GOLDEN_PLAYERS, "towns": GOLDEN_TOWNS,
            "script": [[list(c) for c in day] for day in GOLDEN_SCRIPT], "policy": _pol(T.DEFAULT_POLICY),
            "events": n, "day": s.day, "hash": T.state_hash(s), "content_hash": T.content_hash(CONTENT["test"]),
            "pools": [[p.id, p.available, p.growth] for p in pools], "growth_modes": digest,
            "growth_digest": hashlib.sha256(json.dumps(digest, separators=(",", ":")).encode("utf-8")).hexdigest(),
            "treasuries": [_res(p) for p in s.players]}


def generate():
    return {FILE: {
        "format": VECTOR_FORMAT,
        "packs": dict(PACK_TEXT),
        "pack_valid": _valid_cases(),
        "pack_invalid": _invalid_cases(),
        "policies": _policy_cases(),
        "weekly_growth": _weekly_cases(),
        "streams": _stream_cases(),
        "create": _create_cases(),
        "traces": _traces(),
        "queries": _query_cases(),
        "states": _states(),
        "golden": _golden(),
    }}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=V.DEFAULT_OUT)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    for name, doc in generate().items():
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(V._dump(doc))
        print("wrote", os.path.join(args.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
