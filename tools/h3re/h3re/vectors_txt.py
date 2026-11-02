"""Conformance vectors for the TXT reader and the creature content loader.

Everything here is SYNTHETIC (invented creatures, invented numbers). Python
(h3re.txt, h3re.content) is the oracle; the Kotlin port (h3.sim.Txt, h3.sim.Content)
must reproduce every expectation. ``generate()`` returns {filename: object}; the
caller serialises. Wired into vectors.py by the integrator (see
docs/specs/conformance-txt.md); this module does not edit vectors.py.
"""

from __future__ import annotations

import json

from . import content as C
from . import txt as T

_CATEGORIES = (
    ("header_rows must", "header_rows"),
    ("input is ", "too_large"),
    ("input exceeds cap", "too_many_lines"),
    ("input has ", "too_many_lines"),
    ("unknown encoding", "unknown_encoding"),
    ("not valid ", "decode"),
)


def txt_category(msg):
    for prefix, cat in _CATEGORIES:
        if msg.startswith(prefix):
            return cat
    raise AssertionError("unclassified TxtError: " + msg)


def _rows(t):
    return [list(r) for r in t]


def _txt_case(name, data, header_rows=0, **kw):
    case = {"name": name, "data_hex": data.hex(), "header_rows": header_rows}
    case.update(kw)
    call = {k: v for k, v in kw.items()
            if k in ("encoding", "lenient_newlines", "quoting", "max_bytes", "max_lines")}
    try:
        t = T.parse_txt(data, header_rows, **call)
        case["expect"] = {"header": _rows(t.header), "rows": _rows(t.rows)}
    except T.TxtError as e:
        case["error"] = txt_category(str(e))
    return case


class _Lcg:
    def __init__(self, seed):
        self.s = seed

    def next(self, n):
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
        return (self.s >> 33) % n


def _txt_cases():
    b = lambda s: s.encode("latin-1")  # noqa: E731
    cs = []
    add = lambda *a, **k: cs.append(_txt_case(*a, **k))  # noqa: E731
    add("simple", b("a\tb\r\nc\td\r\n"))
    add("no_trailing_terminator", b("a\tb\r\nc\td"))
    add("single_terminator_no_extra_record", b("a\r\n"))
    add("blank_line_is_one_empty_field", b("a\r\n\r\nb\r\n"))
    add("only_crlf", b("\r\n"))
    add("bare_lf_is_data", b("a\nb\tc\r\nd\r\n"))
    add("bare_cr_is_data", b("a\rb\tc\r\n"))
    add("trailing_tab", b("a\tb\t"))
    add("trailing_tab_then_crlf", b("a\tb\t\r\n"))
    add("leading_tab", b("\ta\r\n"))
    add("double_tab", b("a\t\tb\r\n"))
    add("ragged", b("a\r\nb\tc\td\r\ne\tf\r\n"))
    add("empty_input", b(""))
    add("only_bom", b"\xef\xbb\xbf")
    add("bom_then_data", b"\xef\xbb\xbfa\tb\r\n")
    add("bom_with_cp1250", b"\xef\xbb\xbfa\r\n", encoding="cp1250")
    add("bom_not_at_start_is_data_error", b("a\r\n") + b"\xef\xbb\xbf", encoding="utf-8")
    add("header_rows_1", b("h1\th2\r\na\tb\r\n"), 1)
    add("header_rows_2", b("h1\r\nh2\r\na\r\nb\r\n"), 2)
    add("header_rows_exceed_records", b("h1\r\nh2\r\n"), 5)
    add("header_rows_exact", b("h1\r\n"), 1)
    add("header_rows_negative", b("a\r\n"), -1)
    add("quoted_tab", b('"a\tb"\tc\r\n'))
    add("quoted_crlf", b('"a\r\nb"\tc\r\nd\r\n'))
    add("quoted_lf", b('"a\nb"\tc\r\n'))
    add("doubled_quote", b('"say ""hi"""\tx\r\n'))
    add("empty_quoted", b('""\tx\r\n'))
    add("quoted_only_quote", b('""""\tx\r\n'))
    add("text_after_closing_quote", b('"ab"cd\tx\r\n'))
    add("quote_mid_field_is_data", b('ab"cd\tx\r\n'))
    add("unterminated_quote_ends_at_tab", b('"abc\tx\r\n'))
    add("unterminated_quote_ends_at_crlf", b('"abc\r\nx\r\n'))
    add("unterminated_quote_at_eof", b('x\t"abc'))
    add("lone_quote_at_eof", b('"'))
    add("quoted_field_at_eof", b('a\t"b c"'))
    add("quoted_then_trailing_tab", b('"a"\t'))
    add("quoted_doubled_at_end_of_data", b('"a""'))
    add("quoting_off", b('"a\tb"\r\n'), quoting=False)
    add("quoting_off_doubled", b('"say ""hi"""\tx\r\n'), quoting=False)
    add("lenient_bare_lf", b("a\nb\r\nc\n"), lenient_newlines=True)
    add("lenient_lf_in_quotes_kept", b('"a\nb"\nc\r\n'), lenient_newlines=True)
    add("lenient_bare_cr_still_data", b("a\rb\n"), lenient_newlines=True)
    add("strict_same_input", b("a\nb\r\nc\n"))
    add("cp1252_eacute_euro", b"Br\xfbl\xe9 \x80\r\n", encoding="cp1252")
    add("cp1252_undefined_0x81", b"a\x81\r\n", encoding="cp1252")
    add("cp1250_lstroke", b"Z\xb3oty\r\n", encoding="cp1250")
    add("cp1251_cyrillic", b"\xd0\xe0\xe4\xee\tx\r\n", encoding="cp1251")
    add("gbk_two_byte", "龙\t鹰\r\n".encode("gbk"), encoding="gbk")
    add("utf8_multibyte", "Wyrmé 龙\t\U0001F600\r\n".encode("utf-8"), encoding="utf-8")
    add("utf8_invalid", b"a\xff\r\n", encoding="utf-8")
    add("utf8_overlong", b"\xc0\xaf\r\n", encoding="utf-8")
    add("utf8_alias", b"\xc3\xa9\r\n", encoding="utf8")
    add("unknown_encoding", b("a\r\n"), encoding="klingon")
    add("default_encoding_high_bytes", b"\xe9\xe8\r\n")
    add("max_bytes_exact", b("ab\r\n"), max_bytes=4)
    add("max_bytes_exceeded", b("ab\r\n"), max_bytes=3)
    add("max_lines_exact", b("a\r\nb\r\n"), max_lines=2)
    add("max_lines_exceeded", b("a\r\nb\r\nc\r\n"), max_lines=2)
    add("max_lines_no_terminator", b("a\r\nb\r\nc"), max_lines=2)
    add("max_lines_zero_empty", b(""), max_lines=0)
    add("many_lines_default", b("x\r\n") * 50)
    # Deterministic pseudo-random fuzz over a small ASCII alphabet.
    alpha = ["a", "b", " ", "\t", "\r\n", "\n", "\r", '"', '""', "\t", "\r\n"]
    rng = _Lcg(0xC0FFEE)
    for n in range(240):
        s = "".join(alpha[rng.next(len(alpha))] for _ in range(rng.next(14)))
        hr = rng.next(3)
        flags = rng.next(4)
        kw = {}
        if flags & 1:
            kw["lenient_newlines"] = True
        if flags & 2:
            kw["quoting"] = False
        add("fuzz_%03d" % n, b(s), hr, **kw)
    return cs


# ---------------------------------------------------------------------------
# content

def _content_error(e):
    """(category, row, column) from a Python ContentError message."""
    import re
    msg = str(e)
    m = re.match(r"row (\d+), column '([^']*)'(?: \(index (\d+)\))?: (.*)", msg)
    if m:
        row, col, rest = int(m.group(1)), m.group(2), m.group(4)
        if rest == "missing cell":
            cat = "missing_cell"
        elif rest == "empty":
            cat = "empty_cell"
        elif rest.startswith("not an integer"):
            cat = "not_integer"
        elif rest.startswith("duplicate name"):
            cat = "duplicate"
        else:
            raise AssertionError(msg)
        return cat, row, col
    m = re.match(r"row (\d+): ", msg)
    if m:
        return "schema", int(m.group(1)), None
    if msg.startswith("table: no creature rows"):
        return "no_rows", None, None
    if msg.startswith("table: fewer than"):
        return "header", None, None
    if msg.startswith("header row"):
        return "header", None, None
    if msg.startswith("table: "):
        return "table", None, None
    raise AssertionError(msg)


def _line(cells):
    return "\t".join(cells)


def _creature_row(c, plural2=False, roe=False):
    cells = [c["singular"]]
    if plural2:
        cells.append(c.get("plural2", c["singular"] + "z"))
    cells.append(c.get("plural", c["singular"] + "s"))
    cells += [str(c.get("cost_" + r, 0)) for r in
              ("wood", "mercury", "ore", "sulfur", "crystal", "gems", "gold")]
    cells += [str(c.get(k, 0)) for k in ("fight_value", "ai_value", "growth", "horde")]
    cells += [str(c[k]) for k in ("hp", "speed", "attack", "defense", "dmg_min", "dmg_max")]
    cells.append(str(c.get("shots", 0)))
    if not roe:
        cells.append(str(c.get("spell_points", 0)))
    cells += [str(c.get("adv_min", 0)), str(c.get("adv_max", 0))]
    cells += [c.get("text", "description"), c.get("abilities", "")]
    return _line(cells)


def _header(plural2=False, roe=False):
    h = ["Singular", "Plural"] + (["Plural2"] if plural2 else [])
    h += ["Wood", "Mercury", "Ore", "Sulfur", "Crystal", "Gems", "Gold", "Fight", "AI",
          "Grow", "Horde", "HP", "Speed", "Attack", "Defense", "DmgMin", "DmgMax", "Shots"]
    h += ([] if roe else ["Spells"]) + ["AdvMin", "AdvMax", "Text", "Abilities"]
    return "Creature traits\r\n" + _line(h) + "\r\n"


def _base(name, **kw):
    d = {"singular": name, "hp": 40, "speed": 5, "attack": 7, "defense": 6,
         "dmg_min": 2, "dmg_max": 5}
    d.update(kw)
    return d


def _table(creatures, plural2=False, roe=False, eol="\r\n"):
    return (_header(plural2, roe) + "".join(_creature_row(c, plural2, roe) + eol
                                            for c in creatures)).encode("cp1252")


def _content_case(name, data, mapping, roe=False, encoding="cp1252"):
    case = {"name": name, "data_hex": data.hex(), "roe": roe, "encoding": encoding}
    try:
        r = C.parse_creatures(data, mapping, roe=roe, encoding=encoding)
        case["expect"] = {
            "creatures": [dict(c) for c in r.creatures],
            "extras": {k: dict(v) for k, v in r.extras.items()},
            "unknown": [[row, nm, tx] for row, nm, tx in r.unknown],
        }
    except C.ContentError as e:
        cat, row, col = _content_error(e)
        case["error"] = {"category": cat, "row": row, "column": col}
    return case


def _content_cases(mapping):
    cs = []
    add = lambda *a, **k: cs.append(_content_case(*a, mapping=mapping, **k))  # noqa: E731
    a = _base("Glimmerwisp", abilities="Flying", cost_gold=120, cost_gems=2, growth=7,
              fight_value=300, ai_value=410, adv_min=3, adv_max=9, spell_points=4)
    b = _base("Stonehorn", hp=130, speed=4, attack=12, defense=11, dmg_min=6, dmg_max=9,
              abilities="Double Wide, no enemy retaliation , Strikes Twice")
    c = _base("Quillfox", shots=12, abilities="Shooter, Shoots Twice, no melee penalty")
    d = _base("Mossback", abilities="Spits Acid, flying, Teleports", hp=60)
    add("two_creatures_file_order", _table([b, a]))
    add("all_flags", _table([_base("Omniform", abilities="flyer, double wide, no retaliation, "
        "unlimited retaliation, no melee penalty, no range penalty, double attack, "
        "shoots twice, no morale")]))
    add("shooter_known_no_flag", _table([c]))
    add("unknown_abilities_reported", _table([d, a]))
    add("ability_normalisation", _table([_base("Dunebloom", abilities="  FLYING ,  double\t wide ,, ")]))
    add("empty_abilities", _table([_base("Plainling")]))
    add("shots_zero_omitted", _table([_base("Archerling", shots=0)]))
    add("plural2_variant", _table([a, b], plural2=True))
    add("roe_variant", _table([a, b], roe=True), roe=True)
    add("roe_header_without_flag_misaligns", _table([a], roe=True))
    add("skip_blank_rows", (_header() + _creature_row(a) + "\r\n\t\t\r\n"
                            + _creature_row(_base("")) + "\r\n" + _creature_row(b) + "\r\n").encode("cp1252"))
    add("last_row_no_terminator", _table([a, b], eol="\r\n").rstrip(b"\r\n"))
    add("lf_only_is_one_record_error", _table([a], eol="\n").replace(b"\r\n", b"\n"))
    add("quoted_name_with_comma_and_quote",
        (_header() + _creature_row(_base('"Ash ""Drake"", Elder"', abilities='"flying, no morale"'))
         + "\r\n").encode("cp1252"))
    add("cp1252_accented_name", _table([_base("Brûlé Drake", plural="Brûlés")]))
    add("cp1251_names", (_header() + _creature_row(_base("Ёж", plural="Ёжи"))
                         + "\r\n").encode("cp1251"), encoding="cp1251")
    add("utf8_names", (_header() + _creature_row(_base("龙", plural="龙")) + "\r\n")
        .encode("utf-8"), encoding="utf-8")
    add("utf8_bom", b"\xef\xbb\xbf" + _table([a]), encoding="cp1252")
    add("explicit_plus_sign_and_underscore", _table([_base("Signling", hp="+1_0", speed="+5")]))
    # errors
    add("err_decode_utf8", b"\xff\xfe" + _table([a]), encoding="utf-8")
    add("err_empty", b"")
    add("err_header_only", _header().encode("cp1252"))
    add("err_one_header_row", b"Singular\tPlural\r\n")
    add("err_bad_header", b"x\r\nName\tPlural\r\n" + _creature_row(a).encode("cp1252") + b"\r\n")
    add("err_all_rows_skipped", (_header() + "\r\n\t\r\n").encode("cp1252"))
    add("err_missing_required_cell", (_header() + "Shorty\tShortys\t1\t2\r\n").encode("cp1252"))
    row = _creature_row(a).split("\t")
    for label, idx, val in (("hp_empty", 13, ""), ("speed_not_int", 14, "fast"),
                            ("attack_float", 15, "7.5"), ("hp_hex", 13, "0x10"),
                            ("hp_zero_ok", 13, "0"), ("speed_too_high", 14, "101"),
                            ("attack_negative", 15, "-1"), ("defense_too_high", 16, "256"),
                            ("dmg_min_zero_ok", 17, "0"), ("shots_too_many", 19, "1001"),
                            ("cost_not_int", 8, "lots"), ("cost_negative_ok", 8, "-3"),
                            ("growth_underscore_edge", 11, "1__0")):
        r2 = list(row)
        r2[idx] = val
        add("err_" + label, (_header() + _line(r2) + "\r\n").encode("cp1252"))
    r3 = list(row)
    r3[17], r3[18] = "9", "3"
    add("err_dmg_min_gt_max", (_header() + _line(r3) + "\r\n").encode("cp1252"))
    r4 = list(row)
    r4[0] = "Glimmerwisp"
    add("err_second_row_bad", (_header() + _creature_row(b) + "\r\n"
                                + _line(r4[:14] + ["abc"] + r4[15:]) + "\r\n").encode("cp1252"))
    add("err_duplicate_name", _table([a, b, a]))
    add("err_name_blank_after_strip_skipped_not_error", (_header() + _creature_row(_base("  ")) + "\r\n"
                                                         + _creature_row(a) + "\r\n").encode("cp1252"))
    add("err_whitespace_only_numeric_required", (_header() + _line(row[:13] + [" "] + row[14:]) + "\r\n")
        .encode("cp1252"))
    add("err_first_error_wins", (_header() + _line(row[:13] + ["zz"] + row[14:15] + ["qq"] + row[16:])
                                 + "\r\n").encode("cp1252"))
    add("err_plural2_header_row_short", (_header(True) + _creature_row(a) + "\r\n").encode("cp1252"),
        roe=False)
    return cs


def generate():
    mapping = C.load_mapping()
    return {
        "txt.json": {"format": 1, "cases": _txt_cases()},
        "content.json": {"format": 1, "mapping": mapping, "cases": _content_cases(mapping)},
    }


if __name__ == "__main__":  # debugging aid
    print(json.dumps({k: len(v["cases"]) for k, v in generate().items()}))
