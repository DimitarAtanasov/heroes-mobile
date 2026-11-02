"""Data pack loader: balance numbers live in data/*.json, never in code.

Spec: docs/specs/datapack.md. Stdlib only. Strict validation (types, ranges,
unknown keys rejected), integer-only values (floats rejected), deterministic
ordering (creatures sorted by name) and a SHA-256 content hash of the
canonical JSON of the validated pack. ``battle_policy.json`` (the
``BattlePolicy`` defaults) is validated and hashed the same way. ``rules.py`` derives its constants from
this module at import (``load_rules_dir``), so this module must not import
``rules`` or ``battle`` at module load (``battle`` is imported lazily).
"""

import hashlib
import json
import os
from fractions import Fraction
from types import MappingProxyType


__all__ = ["DataPackError", "DataPack", "load", "load_dir", "parse", "DEFAULT_DIR", "ENV_DIR",
           "LOADED_DIR", "load_rules", "load_rules_dir", "load_rules_pack",
           "load_rules_pack_dir", "resolve_dir", "PolicyPack", "POLICY_CHOICES",
           "load_policy_pack", "load_policy_pack_dir", "parse_policy"]

ENV_DIR = "H3_DATA_PACK_DIR"
_REPO_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data"))
# H3_DATA_PACK_DIR (if set and non-empty) overrides the repo-relative data/ dir.
# It is made absolute once, here, so a later chdir cannot change which pack a
# lazy loader sees. LOADED_DIR is the directory ``rules.py`` read its constants
# from (the same value; a documented, importable name for logs and tests).
DEFAULT_DIR = os.path.abspath(os.environ.get(ENV_DIR) or _REPO_DIR)
LOADED_DIR = DEFAULT_DIR
SCHEMA_VERSION = 1
# Largest value a pack integer may take: the JVM Int.MAX (the Kotlin engine uses
# Int, ADR-0004). docs/specs/datapack.md.
MAX_INT = (1 << 31) - 1


class DataPackError(ValueError):
    """Invalid or unreadable data pack."""


def _int(v, path, lo, hi):
    if type(v) is not int:
        raise DataPackError("%s: expected integer, got %s" % (path, type(v).__name__))
    if not lo <= v <= hi:
        raise DataPackError("%s: %d out of range %d..%d" % (path, v, lo, hi))
    return v


def _obj(v, path, required, optional=()):
    if not isinstance(v, dict):
        raise DataPackError("%s: expected object" % path)
    unknown = sorted(set(v) - set(required) - set(optional))
    if unknown:
        raise DataPackError("%s: unknown key(s) %s" % (path, ", ".join(unknown)))
    missing = sorted(set(required) - set(v))
    if missing:
        raise DataPackError("%s: missing key(s) %s" % (path, ", ".join(missing)))
    return v


def _list(v, path, n=None):
    if not isinstance(v, list):
        raise DataPackError("%s: expected array" % path)
    if n is not None and len(v) != n:
        raise DataPackError("%s: expected %d items, got %d" % (path, n, len(v)))
    return v


def _frac(v, path):
    a = _list(v, path, 2)
    return (_int(a[0], path + "[0]", 0, MAX_INT), _int(a[1], path + "[1]", 1, MAX_INT))


_FRACS = ("ad_bonus_per_point", "ad_bonus_cap", "da_penalty_per_point",
          "da_penalty_cap", "hate_bonus", "luck_bonus", "half")
_FRAC_TABLES = ("offense", "archery", "armorer")
_INT_TABLES = ("bad_morale_numerators", "vcmi_bad_morale_numerators")


def _check_rules(d):
    _obj(d, "rules", _FRACS + _FRAC_TABLES + _INT_TABLES + ("morale_die", "schema_version"))
    if _int(d["schema_version"], "rules.schema_version", 0, MAX_INT) != SCHEMA_VERSION:
        raise DataPackError("rules.schema_version: unsupported")
    die = _int(d["morale_die"], "rules.morale_die", 1, 1000)
    out = {"schema_version": SCHEMA_VERSION, "morale_die": die}
    for k in _FRACS:
        out[k] = _frac(d[k], "rules." + k)
    for k in _FRAC_TABLES:
        rows = _list(d[k], "rules." + k, 4)
        tab = tuple(_frac(r, "rules.%s[%d]" % (k, i)) for i, r in enumerate(rows))
        if tab[0] != (0, 1):
            raise DataPackError("rules.%s[0]: level 0 must be [0, 1]" % k)
        vals = [Fraction(*t) for t in tab]
        if vals != sorted(vals):
            raise DataPackError("rules.%s: must be non-decreasing" % k)
        out[k] = tab
    for k in _INT_TABLES:
        rows = _list(d[k], "rules." + k, 3)
        tab = tuple(_int(r, "rules.%s[%d]" % (k, i), 0, die) for i, r in enumerate(rows))
        if list(tab) != sorted(tab):
            raise DataPackError("rules.%s: must be non-decreasing" % k)
        out[k] = tab
    return out


# --------------------------------------------------------------------------
# Battle policy defaults (data/battle_policy.json). Spec: docs/specs/datapack.md.
# --------------------------------------------------------------------------

# Allowed values of the string-valued policy fields (battle.py validates its own
# fields against these same tuples, so the two cannot drift).
POLICY_CHOICES = {
    "row_offset": ("odd", "even"),
    "speed_tie": ("attacker_first", "alternate", "alternate_last_mover"),
    "wait_order": ("reverse_speed", "speed", "fifo", "slow_first_alternate"),
    "defend_bonus_rounding": ("floor", "ceil"),
    "range_origin": ("head", "any_cell"),
}
_POLICY_BOOLS = ("edge_columns_walkable", "good_morale_after_wait", "good_morale_after_defend",
                 "repeat_good_morale", "bad_morale_on_wait_activation",
                 "good_morale_on_wait_activation", "bad_luck")
_POLICY_INTS = (("defend_bonus_num", 0, MAX_INT), ("defend_bonus_den", 1, MAX_INT),
                ("defend_bonus_min", 0, MAX_INT), ("range_penalty_beyond", 0, 1000))
_POLICY_ENUMS = ("row_offset", "speed_tie", "wait_order", "defend_bonus_rounding",
                 "range_origin")
_POLICY_KEYS = (_POLICY_BOOLS + tuple(k for k, _, _ in _POLICY_INTS) + _POLICY_ENUMS
                + ("placement_rows", "schema_version"))
# Largest row index of a placement table: the battle grid has 11 rows.
_MAX_ROW = 10


def _check_policy(d):
    _obj(d, "battle_policy", _POLICY_KEYS)
    if _int(d["schema_version"], "battle_policy.schema_version", 0, MAX_INT) != SCHEMA_VERSION:
        raise DataPackError("battle_policy.schema_version: unsupported")
    out = {"schema_version": SCHEMA_VERSION}
    for k in _POLICY_BOOLS:
        if type(d[k]) is not bool:
            raise DataPackError("battle_policy.%s: expected boolean" % k)
        out[k] = d[k]
    for k, lo, hi in _POLICY_INTS:
        out[k] = _int(d[k], "battle_policy." + k, lo, hi)
    for k in _POLICY_ENUMS:
        if type(d[k]) is not str or d[k] not in POLICY_CHOICES[k]:
            raise DataPackError("battle_policy.%s: expected one of %s"
                                % (k, ", ".join(POLICY_CHOICES[k])))
        out[k] = d[k]
    rows = _list(d["placement_rows"], "battle_policy.placement_rows", 7)
    table = []
    for i, r in enumerate(rows):
        p = "battle_policy.placement_rows[%d]" % i
        cells = tuple(_int(x, "%s[%d]" % (p, j), 0, _MAX_ROW)
                      for j, x in enumerate(_list(r, p, i + 1)))
        if len(set(cells)) != len(cells):
            raise DataPackError("%s: rows must be distinct" % p)
        table.append(cells)
    out["placement_rows"] = tuple(table)
    return out


class PolicyPack:
    """Validated ``BattlePolicy`` defaults. ``values`` is read-only; tuples are
    nested tuples (no lists). ``content_hash`` is the SHA-256 of the canonical
    JSON, so file formatting and key order do not affect it."""

    def __init__(self, values):
        canon = {"battle_policy": {
            k: ([list(r) for r in values[k]] if k == "placement_rows" else values[k])
            for k in _POLICY_KEYS}}
        self.canonical_json = json.dumps(canon, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=True)
        self.content_hash = hashlib.sha256(self.canonical_json.encode("ascii")).hexdigest()
        self.values = MappingProxyType(dict(values))


def parse_policy(obj):
    """Validate an already-decoded battle_policy.json object."""
    return PolicyPack(_check_policy(obj))


_CR_REQ = ("name", "attack", "defense", "dmg_min", "dmg_max", "hp", "speed")
_CR_FLAGS = ("flyer", "double_wide", "no_enemy_retaliation", "unlimited_retaliation",
             "no_melee_penalty", "no_range_penalty", "strikes_twice", "shoots_twice",
             "no_morale")
_CR_OPT = _CR_FLAGS + ("shots", "hates")


def _check_creatures(d, dmg_max_floor=1, hp_floor=1):
    # dmg_max_floor: 1 for creatures.json; the CRTRAITS loader (content.py) passes 0
    # (owner decision 2026-11-02, content.md). Battle creation still needs dmg >= 1.
    # hp_floor: 1 for creatures.json; the CRTRAITS loader passes 0 (owner decision
    # 2026-11-02, content.md). The battle hp rule is unchanged.
    _obj(d, "creatures", ("schema_version", "creatures"))
    if _int(d["schema_version"], "creatures.schema_version", 0, MAX_INT) != SCHEMA_VERSION:
        raise DataPackError("creatures.schema_version: unsupported")
    items = _list(d["creatures"], "creatures.creatures")
    if not items:
        raise DataPackError("creatures.creatures: must not be empty")
    out = {}
    for i, c in enumerate(items):
        p = "creatures[%d]" % i
        _obj(c, p, _CR_REQ, _CR_OPT)
        name = c["name"]
        if type(name) is not str or not name.strip():
            raise DataPackError("%s.name: expected non-empty string" % p)
        if name in out:
            raise DataPackError("%s.name: duplicate %r" % (p, name))
        r = {"name": name}
        for k, lo, hi in (("attack", 0, 255), ("defense", 0, 255), ("dmg_min", 0, 10000),
                          ("dmg_max", dmg_max_floor, 10000), ("hp", hp_floor, 100000),
                          ("speed", 0, 100), ("shots", 0, 1000)):
            if k in c or k in _CR_REQ:
                r[k] = _int(c[k], "%s.%s" % (p, k), lo, hi)
        if r["dmg_min"] > r["dmg_max"]:
            raise DataPackError("%s: dmg_min > dmg_max" % p)
        for k in _CR_FLAGS:
            if k in c:
                if type(c[k]) is not bool:
                    raise DataPackError("%s.%s: expected boolean" % (p, k))
                r[k] = c[k]
        if "hates" in c:
            h = _list(c["hates"], p + ".hates")
            if any(type(x) is not str for x in h) or len(set(h)) != len(h):
                raise DataPackError("%s.hates: expected unique strings" % p)
            r["hates"] = sorted(h)
        out[name] = r
    for name, r in out.items():
        for h in r.get("hates", ()):
            if h not in out:
                raise DataPackError("creatures.%s.hates: unknown creature %r" % (name, h))
    return [out[n] for n in sorted(out)]


class DataPack:
    """Validated, read-only pack. Use ``load`` / ``load_dir`` / ``parse``."""

    def __init__(self, rules, creatures):
        self._rules = rules
        self._creatures = creatures
        canon = {"creatures": creatures,
                 "rules": {k: (list(v) if isinstance(v, tuple) else v)
                           for k, v in rules.items()}}
        self.canonical_json = json.dumps(canon, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=True)
        self.content_hash = hashlib.sha256(self.canonical_json.encode("ascii")).hexdigest()
        self.rules = MappingProxyType({
            k: (Fraction(*v) if _is_frac(v) else
                tuple(Fraction(*t) for t in v) if _is_frac_table(v) else v)
            for k, v in rules.items()})

    @property
    def creature_names(self):
        return tuple(c["name"] for c in self._creatures)

    def creature(self, name):
        for c in self._creatures:
            if c["name"] == name:
                return _build(c)
        raise KeyError(name)

    def creatures(self):
        """All creatures as battle.Creature, sorted by name."""
        return tuple(_build(c) for c in self._creatures)


def _is_frac(v):
    return isinstance(v, tuple) and len(v) == 2 and all(type(x) is int for x in v)


def _is_frac_table(v):
    return isinstance(v, tuple) and v and all(isinstance(t, tuple) for t in v)


def _build(c):
    from . import battle  # lazy: battle -> rules -> datapack
    kw = {k: v for k, v in c.items() if k != "hates"}
    kw["hates"] = tuple(c.get("hates", ()))
    return battle.Creature(**kw)


def _reject_float(x):
    raise DataPackError("floats are not allowed (got %s)" % x)


def _loads(text, what):
    def no_dupes(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise DataPackError("%s: duplicate key %r" % (what, k))
            d[k] = v
        return d
    try:
        return json.loads(text, parse_float=_reject_float, parse_constant=_reject_float,
                          object_pairs_hook=no_dupes)
    except json.JSONDecodeError as e:
        raise DataPackError("%s: invalid JSON: %s" % (what, e)) from None
    except DataPackError as e:
        raise DataPackError("%s: %s" % (what, e)) from None


def parse(rules_obj, creatures_obj):
    """Validate already-decoded JSON objects and return a DataPack."""
    return DataPack(_check_rules(rules_obj), _check_creatures(creatures_obj))


def _read(paths):
    texts = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                texts.append(_loads(f.read(), os.path.basename(p)))
        except OSError as e:
            raise DataPackError("cannot read %s: %s" % (p, e.strerror)) from None
        except UnicodeDecodeError:
            raise DataPackError("%s: not valid UTF-8" % p) from None
    return texts


def load(rules_path, creatures_path):
    return parse(*_read((rules_path, creatures_path)))


def load_rules_pack(rules_path):
    """Validate only rules.json; return a DataPack with no creatures. Its
    ``content_hash`` is the rules-pack content hash that battle state carries."""
    return DataPack(_check_rules(_read((rules_path,))[0]), [])


def load_rules(rules_path):
    """Validate only rules.json; return the read-only constants mapping."""
    return load_rules_pack(rules_path).rules


def resolve_dir(directory=None):
    """Absolute path of a pack directory (default: DEFAULT_DIR); raises
    DataPackError if it is not an existing directory."""
    path = os.path.abspath(directory or DEFAULT_DIR)
    if not os.path.isdir(path):
        raise DataPackError("data pack directory %s is not a directory (check %s)"
                            % (path, ENV_DIR))
    return path


def load_rules_pack_dir(directory=None):
    return load_rules_pack(os.path.join(resolve_dir(directory), "rules.json"))


def load_rules_dir(directory=None):
    return load_rules_pack_dir(directory).rules


def load_dir(directory=None):
    d = resolve_dir(directory)
    return load(os.path.join(d, "rules.json"), os.path.join(d, "creatures.json"))


def load_policy_pack(path):
    """Validate only battle_policy.json; return a PolicyPack."""
    return parse_policy(_read((path,))[0])


def load_policy_pack_dir(directory=None):
    return load_policy_pack(os.path.join(resolve_dir(directory), "battle_policy.json"))
