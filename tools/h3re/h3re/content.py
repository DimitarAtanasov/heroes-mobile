"""Content loader: CRTRAITS-style TXT table -> datapack creature records.

Spec: docs/specs/content.md. Not a simulation module. The column layout and the
ability-text -> flag table are data (data/txt_maps/crtraits.json), not code.
Records are validated by datapack's creature validator.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import datapack
from .txt import TxtError, parse_txt

__all__ = ["ContentError", "ContentResult", "load_mapping", "load_creatures",
           "parse_creatures", "DEFAULT_MAPPING"]

DEFAULT_MAPPING = Path(__file__).resolve().parents[3] / "data" / "txt_maps" / "crtraits.json"


class ContentError(ValueError):
    """A table or mapping that cannot be turned into content."""


@dataclass(frozen=True)
class ContentResult:
    creatures: tuple      # validated creature dicts, in file order (data-row index; see creature_rows)
    extras: dict          # name -> dict of columns with no datapack slot (cost, growth, ...)
    unknown: tuple        # (row, creature name, ability text) for unmapped ability texts
    # name -> zero-based data-row index among creature records (header skipped, blank and
    # empty-name rows not counted), file order. Side map for sprite lookup; not hashed.
    creature_rows: dict = field(default_factory=dict)
    # names of accepted creatures with dmg 0/0 (case C): no fixed damage (the attack comes from
    # an ability). Side set, not hashed; battle creation still refuses them (dmg_max >= 1).
    no_fixed_damage: frozenset = frozenset()


def load_mapping(path=None) -> dict:
    p = Path(path) if path else DEFAULT_MAPPING
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ContentError("mapping %s: %s" % (p.name, e)) from None
    if not isinstance(m, dict) or m.get("schema_version") != 1:
        raise ContentError("mapping: unsupported schema_version")
    for k in ("header_rows", "columns", "ability_flags"):
        if k not in m:
            raise ContentError("mapping: missing key %s" % k)
    flags = set(datapack._CR_FLAGS)
    for text, flag in m["ability_flags"].items():
        if flag is not None and flag not in flags:
            raise ContentError("mapping.ability_flags[%r]: unknown flag %r" % (text, flag))
    return m


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _layout(m, plural2, roe):
    out = []
    for c in m["columns"]:
        w = c.get("when")
        if w == "plural2" and not plural2:
            continue
        if w == "not_roe" and roe:
            continue
        out.append(c)
    return out


def _int(cell, where):
    s = cell.strip()
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        raise ContentError("%s: not an integer: %r" % (where, s[:40])) from None


def parse_creatures(data: bytes, mapping=None, *, roe=False, encoding="cp1252") -> ContentResult:
    m = mapping if mapping is not None else load_mapping()
    try:
        t = parse_txt(data, m["header_rows"], encoding=encoding)
    except TxtError as e:
        raise ContentError("table: %s" % e) from None
    if len(t.header) < m["header_rows"]:
        raise ContentError("table: fewer than %d header rows" % m["header_rows"])
    h = [c.strip().lower() for c in t.header[-1]]
    if h[:2] != ["singular", "plural"]:
        raise ContentError("header row %d: expected Singular, Plural" % len(t.header))
    plural2 = len(h) > 2 and h[2] == "plural2"
    cols = _layout(m, plural2, roe)
    sep = m.get("ability_separator", ",")
    table = {_norm(k): v for k, v in m["ability_flags"].items()}

    records, extras, unknown, rowno = [], {}, [], {}
    creature_rows, no_fixed_damage = {}, set()
    for i, row in enumerate(t.rows):
        r = i + 1 + m["header_rows"]
        if not any(c.strip() for c in row):
            continue
        if not row[0].strip():
            continue  # source skips rows whose first entry is empty
        rec, ex, abil = {}, {}, ""
        for j, c in enumerate(cols):
            where = "row %d, column %r (index %d)" % (r, c["name"], j)
            if j >= len(row):
                if c.get("required"):
                    raise ContentError("%s: missing cell" % where)
                continue
            cell = row[j]
            if c["kind"] == "str":
                v = cell.strip()
                if c.get("required") and not v:
                    raise ContentError("%s: empty" % where)
            else:
                if c.get("required") and not cell.strip():
                    raise ContentError("%s: empty" % where)
                v = _int(cell, where)
            tg = c["target"]
            if tg is None:
                continue
            if tg == "abilities":
                abil = v
            elif tg.startswith("extra:"):
                ex[tg[6:]] = v
            else:
                rec[tg] = v
        if not rec.get("shots"):
            rec.pop("shots", None)
        name = rec["name"]
        for a in abil.split(sep):
            key = _norm(a)
            if not key:
                continue
            if key not in table:
                unknown.append((r, name, a.strip()))
            elif table[key] is not None:
                rec[table[key]] = True
        try:
            datapack._check_creatures({"schema_version": 1, "creatures": [rec]}, dmg_max_floor=0,
                                      hp_floor=0)
        except datapack.DataPackError as e:
            raise ContentError("row %d: %s" % (r, e)) from None
        if name in extras:
            raise ContentError("row %d, column 'singular': duplicate name %r (first at row %d)"
                               % (r, name, rowno[name]))
        extras[name] = ex
        rowno[name] = r
        creature_rows[name] = len(records)
        if rec["dmg_max"] == 0:
            no_fixed_damage.add(name)
        records.append(rec)
    if not records:
        raise ContentError("table: no creature rows")
    validated = datapack._check_creatures({"schema_version": 1, "creatures": records},
                                          dmg_max_floor=0, hp_floor=0)
    # _check_creatures returns name-sorted (datapack canonical order); restore file order so the
    # name sort never leaks past the datapack (roster order = data-row index).
    by_name = {c["name"]: c for c in validated}
    creatures = [by_name[r["name"]] for r in records]
    return ContentResult(tuple(creatures), extras, tuple(unknown), creature_rows,
                         frozenset(no_fixed_damage))


def load_creatures(path, mapping=None, *, roe=False, encoding="cp1252") -> ContentResult:
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise ContentError("table %s: %s" % (Path(path).name, e.strerror)) from None
    return parse_creatures(data, mapping, roe=roe, encoding=encoding)
