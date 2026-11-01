"""Hero core conformance vectors (the Kotlin `h3.sim.hero` port), from the Python reference.

``generate()`` returns ``{"hero.json": ...}``; the orchestrator wires it into ``vectors.generate()``
(which owns serialisation). Python (``hero.py``) is authoritative (ADR-0004,
docs/specs/conformance-hero.md). Every random choice here (the command plans) comes from
``derive_stream``, never Python's ``random``.

Contents of ``hero.json`` (all numbers are integers):

* ``packs``: valid hero packs by name (``test`` is ``data/hero_test.json`` verbatim).
* ``pack_valid`` / ``pack_invalid``: pack texts with content hash, or Python error message and category.
* ``level_for_xp``, ``policies``, ``create``, ``streams``: the small pure functions and ``create_hero``.
* ``traces``: command scripts replayed from ``create_hero``: per step the command, the events (or the
  ``IllegalCommand`` message), the state hash and the stream position afterwards.
* ``offer_sweep``: the offers of one level-up over many seeds, classes, policies and starting skills.
* ``states``: hand-built states (bad weights, odd heroes, odd rules) with one command each.
* ``golden``: the scripted run pinned in ``test_hero.py``.

Usage:  python3 -m h3re.vectors_hero [--out DIR]
"""

import argparse
import copy
import json
import os
import re
import sys
from dataclasses import asdict, replace

from . import datapack as D
from . import hero as H
from . import vectors as V
from .rng import derive_stream

VECTOR_FORMAT = 1
FILE = "hero.json"
CAP = 2 ** 31 - 1
WHAT = "hero.json"          # the `what` prefix of loader errors (Python: the file's base name)

POLICIES = tuple(H.HeroPolicy(m, f) for m in ("upgrade_and_new", "weighted_pair")
                 for f in ("other_kind", "single"))


# --------------------------------------------------------------------------
# Packs
# --------------------------------------------------------------------------

def _test_text():
    with open(os.path.join(D._REPO_DIR, "hero_test.json"), encoding="utf-8") as f:
        return f.read()


def _base():
    return json.loads(_test_text())


def _tiny():
    return {
        "schema_version": 1, "xp_table": [0, 10, 25, 45, 70], "max_secondary": 2,
        "skill_levels": 2, "primary_high_from_level": 3,
        "skills": ["skill.c", "skill.a", "skill.b"],
        "classes": [
            {"id": "class.mage", "start_primary": [1, 0, 3, 3], "primary_low": [1, 1, 5, 5],
             "primary_high": [0, 0, 1, 1],
             "secondary": {"skill.a": 3, "skill.b": 0, "skill.c": 1}},
            {"id": "class.knight", "start_primary": [4, 3, 0, 0], "primary_low": [5, 3, 1, 1],
             "primary_high": [3, 3, 0, 1],
             "secondary": {"skill.a": 1, "skill.b": 2, "skill.c": 5}},
        ],
    }


UNI_SKILLS = ["skill.\U00010000", "skill.￮", "skill.é", "skill.z"]
UNI_HERO = "héro-中-\U0001F600"


def _unicode():
    return {
        "schema_version": 1, "xp_table": [0, 5, 12, 30, 60], "max_secondary": 3,
        "skill_levels": 3, "primary_high_from_level": 4, "skills": UNI_SKILLS,
        "classes": [
            {"id": "class.é", "start_primary": [1, 2, 3, 4], "primary_low": [3, 1, 4, 1],
             "primary_high": [1, 5, 9, 2],
             "secondary": {"skill.\U00010000": 2, "skill.￮": 7, "skill.é": 1, "skill.z": 0}},
            {"id": "class.\U0001F600", "start_primary": [0, 0, 0, 0], "primary_low": [2, 7, 1, 8],
             "primary_high": [2, 8, 1, 8],
             "secondary": {"skill.\U00010000": 5, "skill.￮": 5, "skill.é": 5, "skill.z": 5}},
            {"id": "class.￮", "start_primary": [5, 5, 5, 5], "primary_low": [1, 1, 1, 1],
             "primary_high": [1, 0, 0, 0],
             "secondary": {"skill.\U00010000": 1, "skill.￮": 0, "skill.é": 3, "skill.z": 3}},
        ],
    }


def _bigweights():
    d = _base()
    for c in d["classes"]:
        if c["id"] == "class.warden":
            c["primary_low"], c["primary_high"] = [CAP - 1, 1, 0, 0], [CAP, 0, 0, 0]
            c["secondary"] = {k: 0 for k in c["secondary"]}
            c["secondary"]["skill.anvil"], c["secondary"]["skill.brook"] = CAP - 5, 5
        else:
            c["primary_low"], c["primary_high"] = [CAP - 2, 1, 1, 0], [0, 0, 0, CAP]
            c["secondary"] = {k: 0 for k in c["secondary"]}
            c["secondary"]["skill.fable"] = CAP
    return d


def _nobody():
    return {
        "schema_version": 1, "xp_table": [0, 100, 300], "max_secondary": 3, "skill_levels": 3,
        "primary_high_from_level": 3, "skills": [],
        "classes": [{"id": "class.plain", "start_primary": [1, 1, 1, 1], "primary_low": [1, 2, 3, 4],
                     "primary_high": [4, 3, 2, 1], "secondary": {}}],
    }


def _packs():
    return {
        "test": _test_text(),
        "tiny": json.dumps(_tiny()),
        "unicode": json.dumps(_unicode(), ensure_ascii=False),
        "bigweights": json.dumps(_bigweights(), indent=1),
        "nobody": json.dumps(_nobody(), separators=(",", ":")),
    }


def _load(text):
    return H.parse_hero_pack(D._loads(text, WHAT))


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
    if "weights must have a positive total" in msg or "weight total" in msg:
        return "total"
    if "must not be empty" in msg:
        return "empty"
    if "must start at 0" in msg or "strictly increasing" in msg:
        return "table"
    if "duplicate skill" in msg or "duplicate class" in msg:
        return "duplicate_name"
    if "expected " in msg:
        return "type"
    raise AssertionError("unclassified message: %s" % msg)


# --------------------------------------------------------------------------
# Valid and invalid packs
# --------------------------------------------------------------------------

def _valid_cases():
    base = _base()
    cases = []

    def add(name, text, same_hash_as=None):
        err, content = _run_pack(text)
        assert err is None, (name, err)
        case = {"name": name, "text": text, "hash": H.content_hash(content),
                "classes": [c.id for c in content.classes], "skills": list(content.rules.skills),
                "xp_table": list(content.rules.xp_table)}
        if same_hash_as:
            case["same_hash_as"] = same_hash_as
            assert case["hash"] == next(c["hash"] for c in cases if c["name"] == same_hash_as)
        cases.append(case)

    add("test-file", _test_text())
    add("test-compact", json.dumps(base, separators=(",", ":")), "test-file")
    rev = copy.deepcopy(base)
    rev["classes"].reverse()
    rev["skills"].reverse()
    for c in rev["classes"]:
        c["secondary"] = dict(reversed(list(c["secondary"].items())))
    add("test-reordered", json.dumps(dict(reversed(list(rev.items()))), indent=2), "test-file")
    add("test-ascii-escapes", json.dumps(base, ensure_ascii=True), "test-file")

    d = _nobody()
    add("no-skills", json.dumps(d))
    d = _base()
    d["xp_table"] = [0]
    add("single-xp-entry", json.dumps(d))

    d = _base()
    d.update(max_secondary=0, skill_levels=1, primary_high_from_level=2, xp_table=[0, 1])
    for c in d["classes"]:
        c["start_primary"] = [0, 0, 0, 0]
        c["primary_low"], c["primary_high"] = [0, 0, 0, 1], [1, 0, 0, 0]
    add("bounds-low", json.dumps(d))

    d = _base()
    d.update(max_secondary=1000, skill_levels=100, primary_high_from_level=CAP, xp_table=[0, CAP])
    for c in d["classes"]:
        c["start_primary"] = [1000, 1000, 1000, 1000]
    add("bounds-high", json.dumps(d))

    d = _base()
    d["classes"][0]["primary_low"], d["classes"][0]["primary_high"] = [CAP - 1, 1, 0, 0], [CAP, 0, 0, 0]
    sec = d["classes"][0]["secondary"]
    for k in sec:
        sec[k] = 0
    sec["skill.anvil"], sec["skill.brook"] = CAP - 5, 5
    add("totals-at-cap", json.dumps(d))

    d = _base()
    d["classes"][1]["primary_low"] = [0, 0, 0, CAP]
    d["classes"][1]["secondary"] = {k: (CAP if k == "skill.jade" else 0) for k in d["classes"][1]["secondary"]}
    add("single-weight-at-cap", json.dumps(d))

    add("bigweights", PACK_TEXT["bigweights"])
    add("tiny", PACK_TEXT["tiny"])
    add("unicode-raw", PACK_TEXT["unicode"])
    add("unicode-escaped", json.dumps(_unicode(), ensure_ascii=True), "unicode-raw")

    d = _base()
    d["skills"].append("​")
    for c in d["classes"]:
        c["secondary"]["​"] = 1
    d["classes"].append(copy.deepcopy(d["classes"][0]))
    d["classes"][2]["id"] = "​"
    add("zero-width-ids", json.dumps(d))

    d = _base()
    ids = ["class.m", "class.b", "class.é", "class.a", "class.Z"]
    d["classes"] = []
    for i, cid in enumerate(ids):
        c = copy.deepcopy(base["classes"][i % 2])
        c["id"] = cid
        d["classes"].append(c)
    add("many-classes-unsorted", json.dumps(d))
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

    def cls(d, i=0):
        return d["classes"][i]

    # --- text level
    for name, text in (("empty-text", ""), ("only-space", "   "), ("brace-open", "{"),
                       ("missing-value", '{"a":}'), ("trailing-comma", "[1,]"),
                       ("single-quotes", "{'a': 1}"), ("garbage-after", "{} x"),
                       ("bad-literal", "nul"), ("leading-zero", '{"schema_version": 01}')):
        add(name, text)
    for name, text in (("top-null", "null"), ("top-list", "[]"), ("top-string", '"x"'), ("top-int", "5"),
                       ("top-bool", "true")):
        add(name, text)
    t = _test_text()
    for name, a, b in (
            ("float-max-secondary", '"max_secondary": 8', '"max_secondary": 8.0'),
            ("float-exponent", '"skill_levels": 3', '"skill_levels": 3e0'),
            ("float-negative-exponent", '"skill_levels": 3', '"skill_levels": 3E-1'),
            ("float-in-weights", '"primary_low": [10, 15, 40, 35]', '"primary_low": [10, 15.5, 40, 35]'),
            ("float-in-xp-table", '[0, 1000, 2000', '[0, 1000.0, 2000'),
            ("nan", '"max_secondary": 8', '"max_secondary": NaN'),
            ("infinity", '"max_secondary": 8', '"max_secondary": Infinity'),
            ("minus-infinity", '"max_secondary": 8', '"max_secondary": -Infinity'),
            ("duplicate-top-key", '"max_secondary": 8,', '"max_secondary": 8, "max_secondary": 9,'),
            ("duplicate-class-key", '"id": "class.seer",', '"id": "class.seer", "id": "class.seer",'),
            ("duplicate-secondary-key", '"skill.jade": 7}', '"skill.jade": 7, "skill.jade": 1}')):
        assert a in t, name
        add(name, t.replace(a, b, 1))

    # --- top level
    mut("unknown-key", lambda d: d.update(extra=1))
    mut("unknown-keys-sorted", lambda d: d.update(zz=1, aa=2))
    for k in ("schema_version", "xp_table", "max_secondary", "skill_levels",
              "primary_high_from_level", "skills", "classes"):
        mut("missing-" + k, lambda d, k=k: d.pop(k))
    mut("missing-two-keys", lambda d: (d.pop("skills"), d.pop("classes")))
    mut("unknown-before-missing", lambda d: (d.pop("skills"), d.update(zz=1)))
    for name, v in (("two", 2), ("zero", 0), ("negative", -1), ("above-max", CAP + 1), ("bool", True),
                    ("string", "1"), ("null", None), ("list", [1]), ("huge", 10 ** 30)):
        mut("schema-version-" + name, lambda d, v=v: d.update(schema_version=v))

    # --- xp_table
    for name, v in (("object", {}), ("int", 5), ("string", "x"), ("null", None)):
        mut("xp-table-" + name, lambda d, v=v: d.update(xp_table=v))
    mut("xp-table-empty", lambda d: d.update(xp_table=[]))
    for name, v in (("string", "x"), ("bool", True), ("null", None), ("list", [1]), ("object", {})):
        mut("xp-entry-" + name, lambda d, v=v: d["xp_table"].__setitem__(2, v))
    mut("xp-entry-negative", lambda d: d["xp_table"].__setitem__(2, -1))
    mut("xp-entry-above-max", lambda d: d["xp_table"].__setitem__(2, CAP + 1))
    mut("xp-entry-huge", lambda d: d["xp_table"].__setitem__(2, 10 ** 40))
    mut("xp-first-not-zero", lambda d: d["xp_table"].__setitem__(0, 5))
    mut("xp-single-not-zero", lambda d: d.update(xp_table=[7]))
    mut("xp-type-before-start", lambda d: d.update(xp_table=[5, "x"]))
    mut("xp-equal", lambda d: d["xp_table"].__setitem__(3, 2000))
    mut("xp-decreasing", lambda d: d["xp_table"].__setitem__(3, 1500))
    mut("xp-last-decreasing", lambda d: d["xp_table"].__setitem__(-1, 100))

    # --- skills
    for name, v in (("object", {}), ("string", "skill.a"), ("null", None), ("int", 3)):
        mut("skills-" + name, lambda d, v=v: d.update(skills=v))
    for name, v in (("int", 3), ("null", None), ("empty", ""), ("spaces", "   "), ("tab-newline", "\t\n"),
                    ("nbsp", " "), ("nel", "\u0085"), ("ideographic-space", "　"),
                    ("unit-separator", "\u001f"), ("line-separator", " "), ("list", ["a"]),
                    ("bool", False)):
        mut("skill-entry-" + name, lambda d, v=v: d["skills"].__setitem__(3, v))
    mut("skills-duplicate", lambda d: d["skills"].append("skill.anvil"))
    mut("skills-duplicate-adjacent", lambda d: d.update(skills=["skill.a", "skill.a"]))
    mut("skills-entry-before-duplicate", lambda d: d["skills"].extend(["skill.anvil", 5]))

    # --- scalars
    for k, vals in (("max_secondary", (-1, 1001, "8", True, None, CAP + 1, [8])),
                    ("skill_levels", (0, 101, -3, "3", False, None)),
                    ("primary_high_from_level", (1, 0, -1, CAP + 1, "10", True, None))):
        for j, v in enumerate(vals):
            mut("%s-%d-%s" % (k, j, re.sub(r"\W+", "-", repr(v)).strip("-")), lambda d, k=k, v=v: d.update({k: v}))
    mut("scalar-order-max-before-levels", lambda d: d.update(max_secondary=-1, skill_levels=0))
    mut("scalar-order-levels-before-high", lambda d: d.update(skill_levels=0, primary_high_from_level=1))
    mut("order-xp-before-skills", lambda d: (d.update(xp_table=[]), d.update(skills="x")))
    mut("order-skills-before-scalars", lambda d: (d["skills"].append("skill.anvil"), d.update(max_secondary=-1)))
    mut("order-scalars-before-classes", lambda d: (d.update(max_secondary=-1), d.update(classes=[])))

    # --- classes
    for name, v in (("object", {}), ("null", None), ("string", "x")):
        mut("classes-" + name, lambda d, v=v: d.update(classes=v))
    mut("classes-empty", lambda d: d.update(classes=[]))
    for name, v in (("int", 5), ("null", None), ("list", []), ("string", "x")):
        mut("class-" + name, lambda d, v=v: d["classes"].__setitem__(1, v))
    mut("class-unknown-key", lambda d: cls(d).update(extra=0))
    mut("class-unknown-keys-sorted", lambda d: cls(d).update(zz=0, aa=0))
    for k in ("id", "start_primary", "primary_low", "primary_high", "secondary"):
        mut("class-missing-" + k, lambda d, k=k: cls(d).pop(k))
    for name, v in (("int", 5), ("null", None), ("empty", ""), ("spaces", " \t "), ("nbsp", " "),
                    ("list", ["x"]), ("bool", True)):
        mut("class-id-" + name, lambda d, v=v: cls(d).update(id=v))
    mut("class-duplicate", lambda d: cls(d, 1).update(id="class.seer"))
    mut("class-duplicate-quote", lambda d: (cls(d).update(id="it's"), cls(d, 1).update(id="it's")))
    mut("class-duplicate-both-quotes", lambda d: (cls(d).update(id="a'b\"c"), cls(d, 1).update(id="a'b\"c")))
    mut("class-duplicate-unicode", lambda d: (cls(d).update(id="é中\U0001F600"),
                                              cls(d, 1).update(id="é中\U0001F600")))
    mut("class-duplicate-control", lambda d: (cls(d).update(id="a\x01b​­"),
                                              cls(d, 1).update(id="a\x01b​­")))
    mut("class-duplicate-backslash-tab", lambda d: (cls(d).update(id="a\\b\tc\nd"),
                                                    cls(d, 1).update(id="a\\b\tc\nd")))
    mut("class-duplicate-after-bad-high", lambda d: (cls(d, 1).update(id="class.seer"),
                                                     cls(d, 1).update(primary_high=[0, 0, 0, 0])))
    mut("second-class-invalid", lambda d: cls(d, 1).update(start_primary=[1, 1, 1]))

    for key in ("start_primary", "primary_low", "primary_high"):
        for name, v in (("object", {}), ("null", None), ("string", "abcd")):
            mut("%s-%s" % (key, name), lambda d, key=key, v=v: cls(d).update({key: v}))
        for n in (0, 3, 5):
            mut("%s-len-%d" % (key, n), lambda d, key=key, n=n: cls(d).update({key: [1] * n}))
        for name, v in (("negative", -1), ("string", "x"), ("bool", True), ("null", None), ("list", [1]),
                        ("huge", 10 ** 30)):
            mut("%s-entry-%s" % (key, name), lambda d, key=key, v=v: cls(d)[key].__setitem__(2, v))
    mut("start-primary-1001", lambda d: cls(d)["start_primary"].__setitem__(0, 1001))
    mut("start-primary-1000-ok-then-bad", lambda d: cls(d).update(start_primary=[1000, 1000, 1000, 1001]))
    for key in ("primary_low", "primary_high"):
        mut(key + "-above-max-entry", lambda d, key=key: cls(d)[key].__setitem__(1, CAP + 1))
        mut(key + "-zero-total", lambda d, key=key: cls(d).update({key: [0, 0, 0, 0]}))
        mut(key + "-total-above-cap", lambda d, key=key: cls(d).update({key: [CAP, 1, 0, 0]}))
        mut(key + "-two-halves-above-cap", lambda d, key=key: cls(d).update({key: [CAP // 2 + 1, CAP // 2 + 1, 0, 0]}))
        mut(key + "-all-max", lambda d, key=key: cls(d).update({key: [CAP, CAP, CAP, CAP]}))
    mut("primary-low-total-checked-before-high", lambda d: cls(d).update(primary_low=[0, 0, 0, 0], primary_high=[1, 2]))

    for name, v in (("list", []), ("null", None), ("string", "x"), ("int", 3)):
        mut("secondary-" + name, lambda d, v=v: cls(d).update(secondary=v))
    mut("secondary-empty-object", lambda d: cls(d).update(secondary={}))
    mut("secondary-missing-one", lambda d: cls(d)["secondary"].pop("skill.anvil"))
    mut("secondary-missing-two", lambda d: (cls(d)["secondary"].pop("skill.anvil"), cls(d)["secondary"].pop("skill.jade")))
    mut("secondary-unknown", lambda d: cls(d)["secondary"].update({"skill.zz": 1}))
    mut("secondary-unknown-two-sorted", lambda d: cls(d)["secondary"].update({"skill.zz": 1, "skill.aa": 2}))
    mut("secondary-unknown-and-missing", lambda d: (cls(d)["secondary"].pop("skill.anvil"),
                                                    cls(d)["secondary"].update({"skill.zz": 1})))
    for name, v in (("negative", -1), ("above-max", CAP + 1), ("string", "x"), ("bool", True), ("null", None),
                    ("list", [1]), ("huge", 10 ** 30)):
        mut("secondary-weight-" + name, lambda d, v=v: cls(d)["secondary"].__setitem__("skill.cinder", v))
    mut("secondary-total-above-cap", lambda d: cls(d)["secondary"].update(
        {"skill.anvil": CAP // 2 + 1, "skill.brook": CAP // 2 + 1}))
    mut("secondary-total-cap-plus-one", lambda d: cls(d)["secondary"].update(
        {k: 0 for k in cls(d)["secondary"]}) or cls(d)["secondary"].update({"skill.anvil": CAP, "skill.brook": 1}))
    mut("secondary-weight-first-bad-in-skill-order", lambda d: cls(d)["secondary"].update(
        {"skill.jade": -1, "skill.anvil": CAP + 1}))

    # --- precedence inside a class and across classes
    mut("order-id-before-start", lambda d: cls(d).update(id="", start_primary=[]))
    mut("order-start-before-secondary", lambda d: cls(d).update(start_primary=[], secondary=[]))
    mut("order-secondary-before-low", lambda d: cls(d).update(secondary=[], primary_low=[]))
    mut("order-secondary-total-before-low", lambda d: (cls(d)["secondary"].update(
        {"skill.anvil": CAP, "skill.brook": CAP}), cls(d).update(primary_low=[])))
    mut("order-low-before-high", lambda d: cls(d).update(primary_low=[0, 0, 0, 0], primary_high=[]))
    mut("order-first-class-before-second", lambda d: (cls(d).update(primary_high=[]), cls(d, 1).update(id="")))
    return cases


# --------------------------------------------------------------------------
# JSON helpers
# --------------------------------------------------------------------------

def _pol(p):
    return {"offer_mode": p.offer_mode, "offer_fill": p.offer_fill}


def _sec(pairs):
    return [[s, l] for s, l in pairs]


def _ev(e):
    d = asdict(e)
    d["type"] = type(e).__name__
    return d


def _cmd(c):
    d = asdict(c)
    d["type"] = type(c).__name__
    return d


def _canon(s):
    return H.canonical(s).decode("ascii")


# --------------------------------------------------------------------------
# Small functions
# --------------------------------------------------------------------------

def _level_cases():
    t = list(CONTENT["test"].rules.xp_table)
    cases = []
    for xp in (0, 1, 999, 1000, 1001, 3199, 3200, 14700, 20599, 20600, 20601, 10 ** 6, CAP):
        cases.append({"table": t, "xp": xp, "level": H.level_for_xp(xp, t)})
    for table, xps in (([0], (0, 1, CAP)), ([0, 1], (0, 1, 2)), ([0, 5, 10], (4, 5, 9, 10, 11)),
                       ([], (0, 5)),                    # hand-built tables: the count of entries <= xp
                       ([0, 50, 20, 100], (0, 19, 20, 49, 50, 99, 100)),
                       ([5, 5, 5], (4, 5, 6))):
        for xp in xps:
            cases.append({"table": table, "xp": xp, "level": H.level_for_xp(xp, table)})
    return cases


def _policy_cases():
    out = []
    for mode, fill in (("upgrade_and_new", "other_kind"), ("upgrade_and_new", "single"),
                       ("weighted_pair", "other_kind"), ("weighted_pair", "single"),
                       ("x", "other_kind"), ("upgrade_and_new", "y"), ("", ""), ("Weighted_Pair", "single"),
                       ("it's", "single"), ("weighted_pair", "a'b\"c")):
        c = {"offer_mode": mode, "offer_fill": fill}
        try:
            H.HeroPolicy(mode, fill)
        except ValueError as e:
            c["message"] = str(e)
        out.append(c)
    return out


def _create_error_category(msg):
    for prefix, cat in (("unknown hero class", "unknown_class"), ("unknown skill", "unknown_skill"),
                        ("duplicate skill", "duplicate_skill"), ("bad skill level", "bad_level"),
                        ("at most", "too_many")):
        if msg.startswith(prefix):
            return cat
    raise AssertionError(msg)


def _create_cases():
    cases = []

    def add(name, pack, hero_id, cls, secondary=(), policy=H.DEFAULT_POLICY):
        c = {"name": name, "pack": pack, "hero": hero_id, "class": cls, "secondary": _sec(secondary),
             "policy": _pol(policy)}
        try:
            s = H.create_hero(hero_id, cls, CONTENT[pack], secondary, policy)
        except ValueError as e:
            c["error"] = {"message": str(e), "category": _create_error_category(str(e))}
        else:
            c["hash"] = H.state_hash(s)
            c["canonical"] = _canon(s)
        cases.append(c)

    sk = CONTENT["test"].rules.skills
    for cls in ("class.seer", "class.warden"):
        add("plain-" + cls, "test", "h1", cls)
    add("empty-hero-id", "test", "", "class.seer")
    add("space-hero-id", "test", " ", "class.warden")
    add("unicode-hero-id", "test", UNI_HERO, "class.warden")
    add("start-skills", "test", "h1", "class.warden", (("skill.hollow", 2), ("skill.anvil", 3), ("skill.ivy", 1)))
    add("eight-skills", "test", "h1", "class.seer", tuple((s, 1 + i % 3) for i, s in enumerate(sk[:8])))
    add("zero-weight-start", "test", "h1", "class.warden", (("skill.jade", 3),))
    for pol in POLICIES:
        add("policy-%s-%s" % (pol.offer_mode, pol.offer_fill), "test", "h1", "class.seer", (("skill.anvil", 1),), pol)
    add("tiny-full", "tiny", "t", "class.mage", (("skill.b", 2), ("skill.a", 1)))
    add("tiny-unicode", "unicode", UNI_HERO, "class.\U0001F600", (("skill.\U00010000", 1), ("skill.é", 3)))
    add("nobody", "nobody", "n", "class.plain")
    add("bigweights", "bigweights", "b", "class.warden")

    add("err-unknown-class", "test", "h1", "class.none")
    add("err-class-case", "test", "h1", "CLASS.SEER")
    add("err-class-empty", "test", "h1", "")
    add("err-class-quote", "test", "h1", "it's")
    add("err-class-both-quotes", "test", "h1", "a'b\"c")
    add("err-class-control", "test", "h1", "a\x01​­\x7fé\U0001F600")
    add("err-class-backslash", "test", "h1", "a\\b\tc\nd\re")
    add("err-unknown-skill", "test", "h1", "class.seer", (("skill.zz", 1),))
    add("err-unknown-skill-quote", "test", "h1", "class.seer", (("it's", 1),))
    add("err-duplicate-skill", "test", "h1", "class.seer", (("skill.anvil", 1), ("skill.anvil", 2)))
    add("err-duplicate-after-other", "test", "h1", "class.seer", (("skill.anvil", 1), ("skill.brook", 1), ("skill.anvil", 1)))
    for lv in (0, -1, 4, 100, 2 ** 40):
        add("err-level-%d" % lv, "test", "h1", "class.seer", (("skill.anvil", lv),))
    add("err-too-many", "test", "h1", "class.seer", tuple((s, 1) for s in sk[:9]))
    add("err-too-many-tiny", "tiny", "t", "class.knight", (("skill.a", 1), ("skill.b", 1), ("skill.c", 1)))
    add("err-unknown-before-duplicate", "test", "h1", "class.seer",
        (("skill.anvil", 1), ("skill.zz", 1), ("skill.anvil", 1)))
    add("err-duplicate-before-level", "test", "h1", "class.seer",
        (("skill.anvil", 1), ("skill.anvil", 9)))
    add("err-level-before-unknown-later", "test", "h1", "class.seer",
        (("skill.anvil", 7), ("skill.zz", 1)))
    add("err-bad-entry-before-count", "test", "h1", "class.seer",
        tuple((s, 1) for s in sk[:9]) + (("skill.zz", 1),))
    add("err-unicode-class", "unicode", "u", "class.\U0001F601")
    add("err-nobody-skill", "nobody", "n", "class.plain", (("skill.anvil", 1),))
    return cases


def _stream_cases():
    out = []
    for seed, hid in ((0, "h1"), (1, "h1"), (2026, "h1"), (2026, "h2"), (-1, "h1"), (2 ** 64 + 5, "x"),
                      (-(2 ** 70), "x"), (7, ""), (7, UNI_HERO), (12345, "a:b"), (3, "hero:h1")):
        r = H.hero_rng(seed, hid)
        start = r.state
        out.append({"seed": seed, "hero": hid, "state": start,
                    "draws": [r.range(0, 1000) for _ in range(3)] + [r.range(0, CAP), r.range(0, 1 << 32)],
                    "after": r.state})
    return out


# --------------------------------------------------------------------------
# Traces
# --------------------------------------------------------------------------

def _scenarios(pack):
    """Starting (skill, level) lists for a pack: none, one, mixed, full, full and maxed, ..."""
    sk = CONTENT[pack].rules.skills
    r = CONTENT[pack].rules
    if pack == "test":
        return [(), (("skill.anvil", 1),), (("skill.hollow", 2), ("skill.brook", 1), ("skill.cinder", 3)),
                tuple((s, 1 + i % 3) for i, s in enumerate(sk[:8])), tuple((s, 3) for s in sk[:8]),
                tuple((s, 1) for s in sk[:7]), (("skill.ivy", 1), ("skill.jade", 2)),
                (("skill.drift", 3),)]
    if pack == "tiny":
        return [(), (("skill.a", 1),), (("skill.a", 2), ("skill.c", 1)), (("skill.a", 2), ("skill.b", 2)),
                (("skill.b", 1),), (("skill.c", 2),)]
    if pack == "unicode":
        return [(), (("skill.\U00010000", 1),), (("skill.é", 2), ("skill.z", 1)),
                tuple((s, 1) for s in sk[:3])]
    if pack == "bigweights":
        return [(), (("skill.anvil", 1),), (("skill.brook", 3), ("skill.fable", 1))]
    return [()] if not r.skills else [(), ((sk[0], 1),)]


def _illegal(d, s):
    h = s.hero
    k = d.range(0, 7)
    if k == 0:
        return H.GainXP(h.id + "x", 10) if d.range(0, 2) else H.ChooseSkill(h.id + "x", 0)
    if k == 1:
        return H.GainXP(h.id, 0)
    if k == 2:
        return H.GainXP(h.id, -7)
    if k == 3:
        return H.ChooseSkill(h.id, -1)
    if k == 4:
        return H.ChooseSkill(h.id, len(h.offer))
    if k == 5:
        return H.ChooseSkill(h.id, 1 << 40)
    return H.GainXP(h.id, 5 if h.offer else 1 << 31)


def _random_plan(seed, tag, amounts):
    d = derive_stream(seed, "vectors:hero:plan", tag)

    def plan(s, i):
        h = s.hero
        if d.range(0, 100) < 12:
            return _illegal(d, s)
        if h.offer:
            return H.ChooseSkill(h.id, d.range(0, len(h.offer)))
        return H.GainXP(h.id, amounts[d.range(0, len(amounts))])
    return plan


def _script_plan(script, finish_pick=None):
    """Fixed commands, then (if ``finish_pick``) answer offers with ``finish_pick(state)``."""
    it = iter(script)

    def plan(s, i):
        c = next(it, None)
        if c is None and finish_pick is not None and s.hero.offer:
            return H.ChooseSkill(s.hero.id, finish_pick(s))
        return c
    return plan


def _play(name, pack, hero_id, cls, secondary, policy, seed, plan, max_steps):
    s = H.create_hero(hero_id, cls, CONTENT[pack], secondary, policy)
    rng = H.hero_rng(seed, hero_id)
    rec = {"name": name, "pack": pack, "hero": hero_id, "class": cls, "secondary": _sec(secondary),
           "policy": _pol(policy), "seed": seed, "initial_hash": H.state_hash(s),
           "initial_rng": rng.state, "steps": []}
    for i in range(max_steps):
        cmd = plan(s, i)
        if cmd is None:
            break
        before_c, before_r = H.canonical(s), rng.state
        step = {"cmd": _cmd(cmd)}
        try:
            s, ev = H.apply(s, cmd, rng)
        except H.IllegalCommand as e:
            assert H.canonical(s) == before_c and rng.state == before_r
            step["error"] = str(e)
        else:
            step["events"] = [_ev(e) for e in ev]
        step["hash"] = H.state_hash(s)
        step["rng"] = rng.state
        rec["steps"].append(step)
    rec["final_canonical"] = _canon(s)
    return rec


TEST_AMOUNTS = (1, 300, 999, 1000, 1000, 1200, 2000, 3000, 5000, 8000, 20600, 40000, 250000)
TINY_AMOUNTS = (1, 5, 10, 10, 15, 25, 40, 100)
UNI_AMOUNTS = (1, 5, 7, 12, 18, 30, 80)


def _traces():
    traces = []

    # random plans: every policy, both classes, three seeds, rotating starting skills
    sc = _scenarios("test")
    for si, seed in enumerate((1, 2026, 77)):
        for ci, cls in enumerate(("class.seer", "class.warden")):
            for pi, pol in enumerate(POLICIES):
                k = (pi + 3 * ci + 5 * si) % len(sc)
                name = "random-test-%s-%s-%s-seed%d" % (cls[6:], pol.offer_mode, pol.offer_fill, seed)
                traces.append(_play(name, "test", "h1", cls, sc[k], pol, seed,
                                    _random_plan(seed, name, TEST_AMOUNTS), 34))
    sc = _scenarios("tiny")
    for si, seed in enumerate((3, 9)):
        for ci, cls in enumerate(("class.mage", "class.knight")):
            for pi, pol in enumerate(POLICIES):
                k = (pi + 2 * ci + 3 * si) % len(sc)
                name = "random-tiny-%s-%s-%s-seed%d" % (cls[6:], pol.offer_mode, pol.offer_fill, seed)
                traces.append(_play(name, "tiny", "t", cls, sc[k], pol, seed,
                                    _random_plan(seed, name, TINY_AMOUNTS), 30))
    sc = _scenarios("unicode")
    for si, seed in enumerate((4, 5)):
        for pi, pol in enumerate(POLICIES):
            for ci, cls in enumerate(("class.é", "class.\U0001F600", "class.￮")):
                k = (pi + ci + si) % len(sc)
                name = "random-unicode-%d-%s-%s-seed%d" % (ci, pol.offer_mode, pol.offer_fill, seed)
                traces.append(_play(name, "unicode", UNI_HERO, cls, sc[k], pol, seed,
                                    _random_plan(seed, name, UNI_AMOUNTS), 24))
    sc = _scenarios("bigweights")
    for ci, cls in enumerate(("class.seer", "class.warden")):
        for pi, pol in enumerate(POLICIES):
            name = "random-big-%s-%s-%s" % (cls[6:], pol.offer_mode, pol.offer_fill)
            traces.append(_play(name, "bigweights", "b", cls, sc[(pi + ci) % len(sc)], pol, 11,
                                _random_plan(11, name, TEST_AMOUNTS), 24))
    for pi, pol in enumerate(POLICIES[:2]):
        name = "random-nobody-%d" % pi
        traces.append(_play(name, "nobody", "n", "class.plain", (), pol, 6,
                            _random_plan(6, name, (1, 50, 100, 150, 200, 400)), 20))

    # one big gain, every level stops for an offer; answered with the first, then the last offer
    for pi, pol in enumerate(POLICIES):
        for pick_name, pick in (("first", lambda s: 0), ("last", lambda s: len(s.hero.offer) - 1)):
            for cls in ("class.warden", "class.seer"):
                traces.append(_play("stops-%s-%s-%s-%s" % (cls[6:], pol.offer_mode, pol.offer_fill, pick_name),
                                    "test", "h1", cls, (), pol, 8 + pi,
                                    _script_plan([H.GainXP("h1", 20600)], pick), 20))
    # four levels from level 1: stops at levels 2, 3, 4 and 5
    traces.append(_play("stops-4600", "test", "h1", "class.warden", (), H.DEFAULT_POLICY, 9,
                        _script_plan([H.GainXP("h1", 4600)], lambda s: 0), 12))
    # nothing to offer: all slots full and maxed -> levels pass without stops
    maxed = tuple((s, 3) for s in CONTENT["test"].rules.skills[:8])
    for pol in (POLICIES[0], POLICIES[2]):
        traces.append(_play("no-offers-%s" % pol.offer_mode, "test", "h1", "class.seer", maxed, pol, 3,
                            _script_plan([H.GainXP("h1", 25000), H.GainXP("h1", 100)]), 4))

    # XP cap
    fin = lambda s: 0   # noqa: E731
    traces.append(_play("cap-exact-from-zero", "test", "h1", "class.warden", (), H.DEFAULT_POLICY, 21,
                        _script_plan([H.GainXP("h1", CAP + 1), H.GainXP("h1", 1 << 40), H.GainXP("h1", CAP),
                                      ], fin), 40))
    s2 = [H.GainXP("h1", CAP + 1), H.GainXP("h1", CAP)]
    traces.append(_play("cap-then-more", "test", "h1", "class.seer", (), POLICIES[1], 22,
                        _script_plan_after(s2, [H.GainXP("h1", 1), H.GainXP("h1", CAP)], fin), 60))
    traces.append(_play("cap-minus-one", "test", "h1", "class.warden", (), POLICIES[3], 23,
                        _script_plan_after([H.GainXP("h1", CAP - 1)],
                                           [H.GainXP("h1", 2), H.GainXP("h1", 1), H.GainXP("h1", 1)], fin), 60))
    traces.append(_play("cap-tiny-pack", "tiny", "t", "class.knight", (), H.DEFAULT_POLICY, 24,
                        _script_plan_after([H.GainXP("t", CAP)], [H.GainXP("t", 1)], fin), 30))

    # every legal ChooseSkill index at a pending offer, then play on
    for scn, secs in (("none", ()), ("one", (("skill.anvil", 1),)), ("full", tuple(
            (s, 1 + i % 2) for i, s in enumerate(CONTENT["test"].rules.skills[:8]))),
                      ("three", (("skill.hollow", 2), ("skill.brook", 1), ("skill.cinder", 3)))):
        for pol in POLICIES:
            probe = H.create_hero("h1", "class.warden", CONTENT["test"], secs, pol)
            s, _ = H.apply(probe, H.GainXP("h1", 1000), H.hero_rng(5, "h1"))
            for idx in range(len(s.hero.offer)):
                script = [H.GainXP("h1", 1000), H.ChooseSkill("h1", idx), H.GainXP("h1", 2200)]
                traces.append(_play("branch-%s-%s-%s-idx%d" % (scn, pol.offer_mode, pol.offer_fill, idx),
                                    "test", "h1", "class.warden", secs, pol, 5,
                                    _script_plan(script, lambda s, idx=idx: idx % len(s.hero.offer)), 14))
    return traces


def _script_plan_after(first, then, fin):
    """``first`` commands, then offers answered with ``fin`` until none is pending, then ``then``."""
    q = list(first) + [None] + list(then)

    def plan(s, i):
        while q:
            if q[0] is None:
                if s.hero.offer:
                    return H.ChooseSkill(s.hero.id, fin(s))
                q.pop(0)
                continue
            return q.pop(0)
        return H.ChooseSkill(s.hero.id, fin(s)) if s.hero.offer else None
    return plan


def _sweep():
    out = []
    sc = _scenarios("test")
    for cls in ("class.seer", "class.warden"):
        for k in (0, 1, 2, 3, 5, 6):
            for pol in POLICIES:
                for seed in range(8):
                    s = H.create_hero("h1", cls, CONTENT["test"], sc[k], pol)
                    s, _ = H.apply(s, H.GainXP("h1", 1000), H.hero_rng(seed, "h1"))
                    out.append({"class": cls, "secondary": _sec(sc[k]), "policy": _pol(pol), "seed": seed,
                                "offer": _sec((o.skill, o.level) for o in s.hero.offer),
                                "primary": [s.hero.attack, s.hero.defense, s.hero.power, s.hero.knowledge],
                                "hash": H.state_hash(s)})
    return out


# --------------------------------------------------------------------------
# Hand-built states
# --------------------------------------------------------------------------

def _states():
    out = []
    test = CONTENT["test"]

    def hand(name, s, cmd, seed=5):
        rng = H.hero_rng(seed, s.hero.id)
        rec = {"name": name, "state": json.loads(H.canonical(s)), "hash": H.state_hash(s), "seed": seed,
               "rng_before": rng.state, "cmd": _cmd(cmd)}
        before = H.canonical(s)
        try:
            s2, ev = H.apply(s, cmd, rng)
        except H.IllegalCommand as e:
            assert H.canonical(s) == before and rng.state == rec["rng_before"], name
            rec["error"] = str(e)
        else:
            rec["events"] = [_ev(e) for e in ev]
            rec["hash_after"] = H.state_hash(s2)
        rec["rng_after"] = rng.state
        out.append(rec)

    def base(cls="class.warden", sec=(), pol=H.DEFAULT_POLICY, content=test, hid="h1"):
        return H.create_hero(hid, cls, content, sec, pol)

    def with_class(s, **ch):
        return replace(s, class_def=replace(s.class_def, **ch))

    def with_hero(s, **ch):
        return replace(s, hero=replace(s.hero, **ch))

    sec = H.find_class(test, "class.warden").secondary_weights
    gain = H.GainXP("h1", 1000)
    for name, ch in (
            ("low-over-cap", {"primary_low": (CAP, CAP, 0, 0)}),
            ("low-zero", {"primary_low": (0, 0, 0, 0)}),
            ("low-negative", {"primary_low": (1, -1, 1, 1)}),
            ("low-three", {"primary_low": (1, 1, 1)}),
            ("low-five", {"primary_low": (1, 1, 1, 1, 1)}),
            ("low-empty", {"primary_low": ()}),
            ("high-three", {"primary_high": (1, 1, 1)}),
            ("high-zero", {"primary_high": (0, 0, 0, 0)}),
            ("high-over-cap", {"primary_high": (CAP, 1, 0, 0)}),
            ("high-negative-big", {"primary_high": (5, 5, -(2 ** 40), 5)}),
            ("high-huge-pair", {"primary_high": (2 ** 62, 2 ** 62, 0, 0)}),
            ("sec-over-cap", {"secondary_weights": tuple((k, CAP if i < 2 else w) for i, (k, w) in enumerate(sec))}),
            ("sec-short", {"secondary_weights": sec[:-1]}),
            ("sec-empty", {"secondary_weights": ()}),
            ("sec-swapped", {"secondary_weights": (sec[1], sec[0]) + sec[2:]}),
            ("sec-renamed", {"secondary_weights": (("skill.zz", sec[0][1]),) + sec[1:]}),
            ("sec-negative", {"secondary_weights": ((sec[0][0], -1),) + sec[1:]}),
            ("sec-extra", {"secondary_weights": sec + (("skill.zz", 1),)})):
        s = with_class(base(), **ch)
        hand("bad-" + name, s, gain)
        hand("bad-%s-on-choose" % name, with_class(
            H.apply(base(), H.GainXP("h1", 4600), H.hero_rng(5, "h1"))[0], **ch), H.ChooseSkill("h1", 0))
    # the same bad tables do not matter when the command draws nothing
    for name, ch in (("low-zero", {"primary_low": (0, 0, 0, 0)}),
                     ("high-three", {"primary_high": (1, 1, 1)}),
                     ("sec-short", {"secondary_weights": sec[:-1]})):
        hand("unused-%s-gain" % name, with_class(base(), **ch), H.GainXP("h1", 999))
        pend = H.apply(base(), H.GainXP("h1", 1000), H.hero_rng(5, "h1"))[0]
        hand("unused-%s-choose" % name, with_class(pend, **ch), H.ChooseSkill("h1", 1))
    # exact-cap totals are legal
    hand("total-at-cap-low", with_class(base(), primary_low=(CAP - 1, 1, 0, 0)), gain)
    hand("total-at-cap-high", with_class(base(), primary_high=(0, 0, CAP, 0)), H.GainXP("h1", 20600))
    hand("total-at-cap-secondary", with_class(base(), secondary_weights=tuple(
        (k, CAP - 5 if i == 0 else (5 if i == 1 else 0)) for i, (k, w) in enumerate(sec))), gain)
    hand("single-primary-weight", with_class(base(), primary_low=(0, 0, 3, 0)), H.GainXP("h1", 4600))

    # hand-built heroes
    hand("hero-xp-ahead-of-level", with_hero(base(), xp=5000), H.GainXP("h1", 1))
    hand("hero-xp-ahead-choose", with_hero(base(), xp=9000, level=2,
                                           offer=(H.SkillOffer("skill.brook", 1),)), H.ChooseSkill("h1", 0))
    hand("hero-level-ahead-of-xp", with_hero(base(), level=5, xp=100), H.GainXP("h1", 1))
    hand("hero-unknown-held-skill", with_hero(base(), secondary=(
        H.SecondarySkill("skill.zz", 2), H.SecondarySkill("skill.anvil", 1))), gain)
    hand("hero-held-above-max", with_hero(base(), secondary=(
        H.SecondarySkill("skill.anvil", 4), H.SecondarySkill("skill.brook", 3))), gain)
    hand("hero-held-level-zero", with_hero(base(), secondary=(H.SecondarySkill("skill.anvil", 0),)), gain)
    hand("hero-duplicate-held", with_hero(base(), secondary=(
        H.SecondarySkill("skill.anvil", 1), H.SecondarySkill("skill.anvil", 2))), gain)
    dup_pending = with_hero(base(), level=2, xp=1000, secondary=(
        H.SecondarySkill("skill.anvil", 1), H.SecondarySkill("skill.brook", 1), H.SecondarySkill("skill.anvil", 1)),
        offer=(H.SkillOffer("skill.anvil", 3), H.SkillOffer("skill.cinder", 1)))
    hand("hero-choose-upgrade-duplicates", dup_pending, H.ChooseSkill("h1", 0))
    hand("hero-choose-new", dup_pending, H.ChooseSkill("h1", 1))
    hand("hero-offer-unheld-upgrade", with_hero(base(), level=2, xp=1000,
                                                offer=(H.SkillOffer("skill.gale", 2),)), H.ChooseSkill("h1", 0))
    hand("hero-offer-held-as-new", with_hero(base(sec=(("skill.gale", 2),)), level=2, xp=1000,
                                             offer=(H.SkillOffer("skill.gale", 1),)), H.ChooseSkill("h1", 0))
    hand("hero-offer-over-slots", with_hero(base(), level=2, xp=1000, secondary=tuple(
        H.SecondarySkill(s, 1) for s in test.rules.skills[:8]), offer=(H.SkillOffer("skill.ivy", 1),)),
        H.ChooseSkill("h1", 0))
    hand("hero-nine-held", with_hero(base(), secondary=tuple(
        H.SecondarySkill(s, 1) for s in test.rules.skills[:9])), gain)
    hand("hero-xp-at-cap-gain", with_hero(base(), xp=CAP, level=12), H.GainXP("h1", 1))
    hand("hero-xp-one-below-cap", with_hero(base(), xp=CAP - 1, level=12), H.GainXP("h1", 1))
    hand("hero-xp-above-cap", with_hero(base(), xp=CAP + 5, level=12), H.GainXP("h1", 1))
    hand("hero-wrong-id-in-command", base(), H.ChooseSkill("h2", 0))
    hand("hero-wrong-id-unicode", base(hid=UNI_HERO), H.GainXP(UNI_HERO + "é", 5))
    hand("hero-id-quote", base(hid="it's"), H.GainXP("it", 5))
    hand("hero-no-class-weight-for-held", with_hero(base("class.warden", (("skill.jade", 1),)),
                                                    level=1), gain)
    hand("hero-attack-large", with_hero(base(), attack=2 ** 30), gain)

    # hand-built rules
    r = test.rules
    for name, ch in (("empty-xp-table", {"xp_table": ()}),
                     ("unsorted-xp-table", {"xp_table": (0, 50, 20, 100)}),
                     ("one-skill-level", {"skill_levels": 1}),
                     ("zero-slots", {"max_secondary": 0}),
                     ("high-from-1", {"primary_high_from_level": 1}),
                     ("high-from-2", {"primary_high_from_level": 2}),
                     ("high-from-13", {"primary_high_from_level": 13}),
                     ("four-levels", {"skill_levels": 4})):
        s = replace(base(sec=(("skill.anvil", 1),)), rules=replace(r, **ch))
        hand("rules-" + name, s, H.GainXP("h1", 1200))
        hand("rules-%s-big" % name, s, H.GainXP("h1", 30000))
    rev = tuple(reversed(r.skills))
    wrev = tuple(reversed(sec))
    s = replace(base(sec=(("skill.anvil", 1),)), rules=replace(r, skills=rev),
                class_def=replace(H.find_class(test, "class.warden"), secondary_weights=wrev))
    hand("rules-skills-reversed", s, gain)
    hand("rules-skills-reversed-weights-not", replace(s, class_def=replace(
        s.class_def, secondary_weights=sec)), gain)
    for pol in POLICIES:
        hand("rules-skills-reversed-%s-%s" % (pol.offer_mode, pol.offer_fill),
             replace(s, policy=pol), H.GainXP("h1", 3000))
    return out


# --------------------------------------------------------------------------
# Golden
# --------------------------------------------------------------------------

def _golden():
    """docs/specs/hero.md section 7; mirrors ``golden_run`` in tests/test_hero.py."""
    s = H.create_hero("h1", "class.warden", CONTENT["test"], (("skill.anvil", 1),), H.DEFAULT_POLICY)
    rng = H.hero_rng(2026, "h1")
    n = 0
    for amount in (1500, 5000, 999, 16000, 3000):
        s, ev = H.apply(s, H.GainXP("h1", amount), rng)
        n += len(ev)
        while s.hero.offer:
            s, ev = H.apply(s, H.ChooseSkill("h1", s.hero.level % len(s.hero.offer)), rng)
            n += len(ev)
    h = s.hero
    return {"pack": "test", "hero": "h1", "class": "class.warden", "secondary": [["skill.anvil", 1]],
            "policy": _pol(H.DEFAULT_POLICY), "seed": 2026, "amounts": [1500, 5000, 999, 16000, 3000], "events": n, "level": h.level,
            "xp": h.xp, "primary": [h.attack, h.defense, h.power, h.knowledge],
            "secondary_final": _sec((x.skill, x.level) for x in h.secondary),
            "hash": H.state_hash(s), "content_hash": H.content_hash(CONTENT["test"])}


def generate():
    return {FILE: {
        "format": VECTOR_FORMAT,
        "packs": dict(PACK_TEXT),
        "pack_valid": _valid_cases(),
        "pack_invalid": _invalid_cases(),
        "level_for_xp": _level_cases(),
        "policies": _policy_cases(),
        "create": _create_cases(),
        "streams": _stream_cases(),
        "traces": _traces(),
        "offer_sweep": _sweep(),
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
