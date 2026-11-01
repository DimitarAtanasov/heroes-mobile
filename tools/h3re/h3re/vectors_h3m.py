"""H3M map-header conformance vectors (synthetic maps only, no game data).

``generate()`` returns ``{vector file name: JSON-serialisable content}``; the
orchestrator wires it into ``vectors.generate()`` (which owns serialisation).
Python is authoritative (ADR-0004, ADR-0007): every expectation is produced by
running ``h3re.h3m.parse_h3m`` on the case bytes, so the Kotlin port
(``h3.sim.H3m``) must reproduce it exactly.

``h3m.json``: ``{"format", "cases": [...]}``. A case is
``{"name", "hex" | ("of", "cut"), "expect"}``. ``of`` names an earlier case
whose bytes are cut to the first ``cut`` bytes (saves space for the
every-cut-point cases). The bytes are passed to ``parse_h3m`` (gzip or plain).
``expect`` is ``{"ok": false, "error": "H3mError"}`` (``"hota": true`` when the
message names HotA) or ``{"ok": true, "header": DUMP}``.

DUMP is the canonical dump of the parsed header (``dump_header``): bytes as
lower-case hex, tuples as lists, ``predefined_heroes`` keyed by decimal string,
and the tile array as ``{"count", "sha256"}`` plus ``"raw"`` (hex) when the map
has at most ``RAW_TILES_MAX`` tiles.  Objects are not part of this port.
"""

import gzip
import hashlib
import struct
import zlib

from . import h3m as H
from .h3m import AB, CHR, ROE, SOD, WOG, H3mError, parse_h3m

VECTOR_FILE = "h3m.json"
VECTOR_FORMAT = 1
RAW_TILES_MAX = 16


# --------------------------------------------------------------------------
# canonical dump
# --------------------------------------------------------------------------

def _hex(b):
    return None if b is None else bytes(b).hex()


def _pos(p):
    return None if p is None else list(p)


def _cond(d):
    if d is None:
        return None
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in d.items()}


def _predef(d):
    out = {}
    for k, v in d.items():
        if k == "spells_mask":
            out[k] = _hex(v)
        elif k == "secondary_skills":
            out[k] = [list(x) for x in v]
        elif k == "primary_skills":
            out[k] = list(v)
        else:
            out[k] = v
    return out


def dump_header(h):
    n_tiles = len(h.tiles_raw) // H.TILE_BYTES
    tiles = {"count": n_tiles, "sha256": hashlib.sha256(h.tiles_raw).hexdigest()}
    if n_tiles <= RAW_TILES_MAX:
        tiles["raw"] = h.tiles_raw.hex()
    return {
        "format": h.format, "version": h.version, "has_hero": h.has_hero,
        "size": h.size, "two_levels": h.two_levels, "levels": h.levels,
        "name": h.name, "description": h.description,
        "difficulty": h.difficulty, "max_hero_level": h.max_hero_level,
        "players": [{
            "index": p.index, "can_human": p.can_human,
            "can_computer": p.can_computer, "ai_behavior": p.ai_behavior,
            "allowed_factions": p.allowed_factions,
            "faction_random": p.faction_random,
            "has_main_town": p.has_main_town,
            "generate_hero_at_main_town": p.generate_hero_at_main_town,
            "main_town_pos": _pos(p.main_town_pos),
            "has_random_hero": p.has_random_hero,
            "main_hero_id": p.main_hero_id,
            "main_hero_portrait": p.main_hero_portrait,
            "main_hero_name": p.main_hero_name,
            "heroes": [list(x) for x in p.heroes],
        } for p in h.players],
        "victory": _cond(h.victory), "loss": _cond(h.loss),
        "teams": list(h.teams),
        "allowed_heroes_mask": _hex(h.allowed_heroes_mask),
        "allowed_heroes": list(h.allowed_heroes),
        "placeholder_heroes": list(h.placeholder_heroes),
        "disposed_heroes": [dict(d) for d in h.disposed_heroes],
        "allowed_artifacts_mask": _hex(h.allowed_artifacts_mask),
        "banned_artifacts": h.banned_artifacts,
        "allowed_spells_mask": _hex(h.allowed_spells_mask),
        "banned_spells": h.banned_spells,
        "allowed_skills_mask": _hex(h.allowed_skills_mask),
        "banned_skills": h.banned_skills,
        "rumors": [list(r) for r in h.rumors],
        "predefined_heroes": {str(k): _predef(v)
                              for k, v in h.predefined_heroes.items()},
        "tiles": tiles,
    }


# --------------------------------------------------------------------------
# synthetic builders
# --------------------------------------------------------------------------

def s(t):
    """Length-prefixed string; ``t`` is text (cp1252) or raw bytes."""
    b = t if isinstance(t, bytes) else t.encode("cp1252")
    return struct.pack("<I", len(b)) + b


def u16(v):
    return struct.pack("<H", v)


def u32(v):
    return struct.pack("<I", v)


def player(ver, active=True, town=True, hero=True, *, human=1, comp=1, ai=0,
           factions=None, rnd=0, gen_hero=1, town_pos=(3, 4, 0), hid=5,
           portrait=7, hname="Orrin", heroes=((9, "Bob"),), rand_hero=0):
    if not active:
        return b"\0\0" + bytes({ROE: 6, AB: 12}.get(ver, 13))
    b = bytes([human, comp, ai])
    if ver >= SOD:
        b += b"\x00"
    if factions is None:
        factions = 0xFF if ver == ROE else 0x01FF
    b += bytes([factions]) if ver == ROE else u16(factions)
    b += bytes([rnd])
    if town:
        b += b"\x01"
        if ver != ROE:
            b += bytes([gen_hero, 0])
        b += bytes(town_pos)
    else:
        b += b"\x00"
    b += bytes([rand_hero])
    if hero:
        b += bytes([hid, portrait]) + s(hname)
    else:
        b += b"\xff"
    if ver != ROE:
        b += b"\x00" + u32(len(heroes))
        for i, n in heroes:
            b += bytes([i]) + s(n)
    return b


def default_players(ver, active=2):
    return [player(ver, i < active, hero=(i == 0)) for i in range(8)]


def predef(exp=None, skills=None, arts=None, backpack=(), bio=None,
           gender=0xFF, spells=None, prim=None):
    b = b"\x01"
    b += b"\x01" + u32(exp) if exp is not None else b"\x00"
    if skills is not None:
        b += b"\x01" + u32(len(skills)) + b"".join(bytes(x) for x in skills)
    else:
        b += b"\x00"
    if arts is not None:
        b += b"\x01" + b"".join(u16(a) for a in arts)
        b += u16(len(backpack)) + b"".join(u16(a) for a in backpack)
    else:
        b += b"\x00"
    b += b"\x01" + s(bio) if bio is not None else b"\x00"
    b += bytes([gender])
    b += b"\x01" + bytes(spells) if spells is not None else b"\x00"
    b += b"\x01" + bytes(prim) if prim is not None else b"\x00"
    return b


def extra(ver, *, heroes_mask=None, placeholders=(5, 6),
          disposed=((10, 11, "Dis", 3),), art_mask=None, spell_mask=None,
          skill_mask=None, rumors=(("Tavern", "Dragons!"),), predefined=None):
    if heroes_mask is None:
        heroes_mask = bytes([0xFF] * 16) if ver == ROE else bytes([0xFF] * 19 + [0x0F])
    b = heroes_mask
    if ver != ROE:
        b += u32(len(placeholders)) + bytes(placeholders)
    if ver >= SOD:
        b += bytes([len(disposed)])
        for i, p, n, pl in disposed:
            b += bytes([i, p]) + s(n) + bytes([pl])
    b += bytes(31)
    if ver != ROE:
        if art_mask is None:
            art_mask = bytes([0x01] + [0] * (16 if ver == AB else 17))
        b += art_mask
    if ver >= SOD:
        b += spell_mask if spell_mask is not None else bytes([0x02] + [0] * 8)
        b += skill_mask if skill_mask is not None else bytes([0, 0x80, 0, 0])
    b += u32(len(rumors))
    for n, t in rumors:
        b += s(n) + s(t)
    if ver >= SOD:
        pre = predefined or {}
        for i in range(156):
            b += pre.get(i, b"\x00")
    return b


def tiles_for(size, levels, salt=0):
    out = bytearray()
    for z in range(levels):
        for y in range(size):
            for x in range(size):
                out += bytes([(x + salt) % 256, (y * 3 + salt) % 256, z,
                              (x ^ y) % 4, 2, 3, (x + y) % 8])
    return bytes(out)


def build(ver, victory=b"\xff", loss=b"\xff", teams=b"\x00", *, players=None,
          tail=None, size=36, two=False, tiles=None, name="Test Map",
          desc="A description", diff=2, mhl=0, has_hero=1, size_field=None):
    b = (u32(ver) + bytes([has_hero]) + u32(size if size_field is None else size_field)
         + (b"\x01" if two else b"\x00"))
    b += s(name) + s(desc) + bytes([diff])
    if ver != ROE:
        b += bytes([mhl])
    for p in (players if players is not None else default_players(ver)):
        b += p
    if tiles is None:
        tiles = tiles_for(size, 2 if two else 1)
    return b + victory + loss + teams + (extra(ver) if tail is None else tail) + tiles


def victory(t, ver, *, normal=1, ai=0):
    b = bytes([t, normal, ai])
    wide = ver != ROE
    if t == 0:
        b += u16(0x2A) if wide else b"\x2a"
    elif t == 1:
        b += (u16(77) if wide else b"\x4d") + u32(1234)
    elif t == 2:
        b += b"\x03" + u32(5000)
    elif t == 3:
        b += bytes([5, 6, 1, 2, 3])
    elif t in (4, 5, 6, 7):
        b += bytes([8, 9, 0])
    elif t == 10:
        b += b"\x2a" + bytes([5, 6, 1])
    return b


def loss(t):
    if t in (0, 1):
        return bytes([t, 10, 11, 0])
    return bytes([2]) + u16(30)


def gz(data, *, level=9):
    return gzip.compress(data, compresslevel=level, mtime=0)


def gz_member(data, *, flags=0, fname=b"", extra_f=b"", comment=b"", cm=8,
              hcrc=None, crc=None, isize=None, xfl=0, os_=3):
    """Hand-built gzip member (to vary header fields and the trailer)."""
    hdr = bytes([0x1F, 0x8B, cm, flags]) + u32(0) + bytes([xfl, os_])
    if flags & 4:
        hdr += u16(len(extra_f)) + extra_f
    if flags & 8:
        hdr += fname + b"\0"
    if flags & 16:
        hdr += comment + b"\0"
    if flags & 2:
        hdr += u16((zlib.crc32(hdr) & 0xFFFF) if hcrc is None else hcrc)
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    body = c.compress(data) + c.flush()
    return (hdr + body + u32(zlib.crc32(data) if crc is None else crc)
            + u32(len(data) & 0xFFFFFFFF if isize is None else isize))


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

def _expect(data):
    try:
        h = parse_h3m(data)
    except H3mError as e:
        d = {"ok": False, "error": "H3mError"}
        if "HotA" in str(e):
            d["hota"] = True
        return d
    return {"ok": True, "header": dump_header(h)}


class _Cases:
    def __init__(self):
        self.cases = []
        self.blobs = {}
        self.names = set()

    def add(self, name, data):
        assert name not in self.names, name
        self.names.add(name)
        self.blobs[name] = data
        self.cases.append({"name": name, "hex": data.hex(), "expect": _expect(data)})

    def cut(self, name, of, cut):
        data = self.blobs[of][:cut]
        assert name not in self.names, name
        self.names.add(name)
        self.cases.append({"name": name, "of": of, "cut": cut, "expect": _expect(data)})


VERSIONS = ((ROE, "roe"), (AB, "ab"), (SOD, "sod"), (CHR, "chr"), (WOG, "wog"))
FULL_PREDEF = {
    3: predef(1000, [(3, 2), (5, 1)], [7] + [0xFFFF] * 18, [9, 10], "Bio", 1,
              [1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4]),
    4: predef(exp=0),
    5: predef(skills=[]),
    6: predef(arts=[0xFFFF] * 19),
    7: predef(bio="", gender=0),
    8: predef(spells=[0xFF] * 9),
    9: predef(prim=[0, 0, 0, 0]),
    155: b"\x01" + b"\x00" * 4 + b"\xff" + b"\x00" * 2,
}


def _fixtures(c):
    for ver, tag in VERSIONS:
        c.add(f"{tag}_default_36", build(ver))
        c.add(f"{tag}_default_36_two_levels", gz(build(ver, two=True)))
        c.add(f"{tag}_default_72", gz(build(ver, size=72, tiles=tiles_for(72, 1, 5))))
        c.add(f"{tag}_default_72_two_levels",
              gz(build(ver, size=72, two=True, tiles=tiles_for(72, 2, 9))))
        c.add(f"{tag}_tiny_2x2", build(ver, size=2))
        c.add(f"{tag}_tiny_3x3_two_levels", build(ver, size=3, two=True))
        c.add(f"{tag}_no_hero_no_town_players", build(ver, size=1, players=[
            player(ver, True, town=False, hero=False, human=1, comp=0),
            player(ver, True, town=True, hero=True, human=0, comp=1, ai=2,
                   factions=0x0A, rnd=1, gen_hero=0, town_pos=(255, 0, 1),
                   hid=0xFE, portrait=0xFF, hname="", heroes=()),
            *[player(ver, False) for _ in range(6)]]))
        c.add(f"{tag}_all_players_active", build(ver, size=1, players=[
            player(ver, True, hero=bool(i % 2), ai=i % 3, hid=i, heroes=((i, "H%d" % i), (200, "x")))
            for i in range(8)]))
        c.add(f"{tag}_difficulty_0_4", build(ver, size=1, diff=0, mhl=255))
        c.add(f"{tag}_difficulty_4", build(ver, size=1, diff=4, has_hero=0))
        c.add(f"{tag}_bad_difficulty_5", build(ver, size=1, diff=5))
        c.add(f"{tag}_cp1252_strings", build(
            ver, size=1, name=b"Caf\xe9 \x80 \x81 \x8d \x8f \x90 \x9d \x9f \xff\xa0\x01\x22\\/",
            desc=b"\x0a\x0d\x09 \x7f \x92\x93\x94 caf\xe9"))
        c.add(f"{tag}_empty_strings", build(ver, size=1, name="", desc=""))
        # victory / loss / teams
        for t in range(0, 11):
            if t == 10 and False:
                continue
            c.add(f"{tag}_victory_{t}", build(ver, size=1, victory=victory(t, ver, normal=t % 2, ai=1 - t % 2),
                                              loss=loss(t % 3), teams=b"\x00"))
        c.add(f"{tag}_victory_10_position", build(
            ver, size=1, victory=victory(10, ver), loss=loss(2),
            teams=b"\x02" + bytes([0, 0, 1, 1, 0, 0, 0, 0])))
        c.add(f"{tag}_victory_unknown_11", build(ver, size=1, victory=bytes([11, 0, 0])))
        c.add(f"{tag}_victory_unknown_9x", build(ver, size=1, victory=b"\x63\x00\x00"))
        c.add(f"{tag}_victory_truncated_type3", build(ver, size=1, victory=bytes([3, 0, 0, 1]), tail=b"", tiles=b""))
        c.add(f"{tag}_loss_unknown_3", build(ver, size=1, loss=bytes([3, 0, 0, 0])))
        c.add(f"{tag}_loss_0_1_2", build(ver, size=1, loss=loss(1)))
        c.add(f"{tag}_teams_8", build(ver, size=1, teams=b"\x04" + bytes(range(8))))
        c.add(f"{tag}_teams_flag_ff", build(ver, size=1, teams=b"\xff" + bytes([7] * 8)))
        c.add(f"{tag}_teams_truncated", build(ver, size=1, teams=b"\x02\x00\x01", tail=b"", tiles=b""))
        # extra sections
        c.add(f"{tag}_rumors_none", build(ver, size=1, tail=extra(ver, rumors=())))
        c.add(f"{tag}_rumors_many", build(ver, size=1, tail=extra(
            ver, rumors=tuple(("N%d" % i, "T" * i) for i in range(12)))))
        c.add(f"{tag}_rumors_cp1252", build(ver, size=1, tail=extra(
            ver, rumors=((b"\xe9\x80\x81", b"\x99\x9f"),))))
        c.add(f"{tag}_heroes_mask_all_clear", build(ver, size=1, tail=extra(
            ver, heroes_mask=bytes(16 if ver == ROE else 20))))
        c.add(f"{tag}_heroes_mask_patterns", build(ver, size=1, tail=extra(
            ver, heroes_mask=bytes((i * 37 + 5) % 256 for i in range(16 if ver == ROE else 20)))))
        c.add(f"{tag}_heroes_mask_high_bits_beyond_count", build(ver, size=1, tail=extra(
            ver, heroes_mask=bytes([0xFF] * (16 if ver == ROE else 20)))))
        if ver != ROE:
            c.add(f"{tag}_placeholders_many", build(ver, size=1, tail=extra(
                ver, placeholders=tuple(range(0, 256, 3)))))
            c.add(f"{tag}_placeholders_none", build(ver, size=1, tail=extra(ver, placeholders=())))
            n = 17 if ver == AB else 18
            c.add(f"{tag}_artifacts_mask_patterns", build(ver, size=1, tail=extra(
                ver, art_mask=bytes((i * 91 + 3) % 256 for i in range(n)))))
            c.add(f"{tag}_artifacts_mask_last_byte_full", build(ver, size=1, tail=extra(
                ver, art_mask=bytes([0] * (n - 1) + [0xFF]))))
            c.add(f"{tag}_artifacts_mask_all_set", build(ver, size=1, tail=extra(
                ver, art_mask=bytes([0xFF] * n))))
        if ver >= SOD:
            c.add(f"{tag}_disposed_none", build(ver, size=1, tail=extra(ver, disposed=())))
            c.add(f"{tag}_disposed_many", build(ver, size=1, tail=extra(
                ver, disposed=tuple((i, 255 - i, "D%d" % i, i) for i in range(20)))))
            c.add(f"{tag}_spells_mask_all", build(ver, size=1, tail=extra(
                ver, spell_mask=bytes([0xFF] * 9))))
            c.add(f"{tag}_spells_mask_none", build(ver, size=1, tail=extra(
                ver, spell_mask=bytes(9))))
            c.add(f"{tag}_skills_mask_all", build(ver, size=1, tail=extra(
                ver, skill_mask=bytes([0xFF] * 4))))
            c.add(f"{tag}_skills_mask_patterns", build(ver, size=1, tail=extra(
                ver, skill_mask=bytes([0xA5, 0x5A, 0xF0, 0x0F]))))
            c.add(f"{tag}_predefined_all_fields", build(ver, size=1, tail=extra(ver, predefined=FULL_PREDEF)))
            c.add(f"{tag}_predefined_every_slot", build(ver, size=1, tail=extra(
                ver, predefined={i: predef(exp=i, gender=i % 2) for i in range(156)})))
            c.add(f"{tag}_predefined_gender_2", build(ver, size=1, tail=extra(
                ver, predefined={0: predef(gender=0xFE)})))
            c.add(f"{tag}_predefined_skill_count_28", build(ver, size=1, tail=extra(
                ver, predefined={0: predef(skills=[(i, i % 4) for i in range(28)])})))
            c.add(f"{tag}_predefined_skill_count_29", build(ver, size=1, tail=extra(
                ver, predefined={0: predef(skills=[(i % 28, 1) for i in range(29)])})))
            c.add(f"{tag}_predefined_backpack_many", build(ver, size=1, tail=extra(
                ver, predefined={0: predef(arts=[0xFFFF] * 19, backpack=list(range(300)))})))
            c.add(f"{tag}_predefined_flags_nonzero", build(ver, size=1, tail=extra(
                ver, predefined={2: b"\x02\x07" + u32(5) + b"\x00\x00\x00\xff\x00\x00"})))
        c.add(f"{tag}_trailing_bytes_ignored", build(ver, size=2) + b"objects...")


def _error_cases(c):
    good = build(SOD)
    c.add("empty_input", b"")
    c.add("one_byte", b"\x1c")
    c.add("bad_version_0x99", u32(0x99) + good[4:])
    c.add("bad_version_0", u32(0) + good[4:])
    c.add("bad_version_0x1e", u32(0x1E) + good[4:])
    c.add("bad_version_0x34", u32(0x34) + good[4:])
    c.add("hota_0x20", u32(0x20) + bytes(64))
    c.add("hota_0x20_full_sod_layout", u32(0x20) + good[4:])
    for size, ok in ((0, False), (1, True), (2, True), (1024, True), (1025, False),
                     (0xFFFFFFFF, False), (0x10000, False)):
        if size in (1024,):
            data = gz(build(SOD, size=1024, tiles=bytes(1024 * 1024 * 7)))
        elif ok:
            data = build(SOD, size=size)
        else:
            data = build(SOD, size=1, size_field=size)
        c.add(f"size_bound_{size}", data)
    c.add("size_1024_two_levels_no_tiles", build(SOD, size=1, size_field=1024, two=True, tiles=b""))
    c.add("size_1024_two_levels_missing_second_level",
          gz(build(SOD, size=1, size_field=1024, two=True, tiles=bytes(1024 * 1024 * 7))))
    c.add("size_36_header_two_levels_one_level_tiles", build(SOD, size=36, two=True, tiles=tiles_for(36, 1)))
    c.add("tiles_one_byte_short", build(SOD, size=3)[:-1])
    c.add("tiles_missing", build(SOD, size=3, tiles=b""))
    # count bombs and implausible lengths
    big = build(SOD, size=1)
    pos_name = 10
    c.add("string_len_0x7fffffff", big[:pos_name] + u32(0x7FFFFFFF) + big[pos_name + 4:])
    c.add("string_len_u32_max", big[:pos_name] + u32(0xFFFFFFFF) + big[pos_name + 4:])
    c.add("string_len_max_plus_1", big[:pos_name] + u32((1 << 20) + 1) + big[pos_name + 4:])
    c.add("string_len_max_but_no_data", big[:pos_name] + u32(1 << 20) + big[pos_name + 4:])
    c.add("string_len_exceeds_remaining", big[:pos_name] + u32(len(big)) + big[pos_name + 4:])
    for ver, tag in ((AB, "ab"), (SOD, "sod")):
        base = build(ver, size=1, tail=b"", tiles=b"")
        hm = bytes([0xFF] * 20)
        c.add(f"{tag}_placeholder_count_bomb", base + hm + u32(1 << 30))
        c.add(f"{tag}_placeholder_count_257", base + hm + u32(257) + bytes(300))
        c.add(f"{tag}_placeholder_count_256_truncated", base + hm + u32(256) + bytes(100))
        c.add(f"{tag}_placeholder_count_u32_max", base + hm + u32(0xFFFFFFFF))
    for ver, tag in ((ROE, "roe"), (AB, "ab"), (SOD, "sod")):
        e = extra(ver, rumors=())
        head = build(ver, size=1, tail=b"", tiles=b"")
        cut = len(e) - 4 - (156 if ver >= SOD else 0)
        pre, post = e[:cut], e[cut + 4:]
        c.add(f"{tag}_rumor_count_bomb", head + pre + u32(1 << 30) + post)
        c.add(f"{tag}_rumor_count_4097", head + pre + u32(4097) + bytes(5000) + post)
        c.add(f"{tag}_rumor_count_4096_truncated", head + pre + u32(4096) + bytes(100))
        c.add(f"{tag}_rumor_count_u32_max", head + pre + u32(0xFFFFFFFF) + post)
        c.add(f"{tag}_rumor_string_bomb", head + pre + u32(1) + u32(0xFFFFFFFF) + post)
        c.add(f"{tag}_rumor_second_string_missing", head + pre + u32(1) + s("a"))
    for ver, tag in ((AB, "ab"), (SOD, "sod")):
        pl = [player(ver, True, heroes=())] + [player(ver, False)] * 7
        p0 = player(ver, True, heroes=())
        # player 0 heroes count is the last u32 of the player block
        bomb = p0[:-4] + u32(257) + bytes(2000)
        c.add(f"{tag}_player_hero_count_257", build(ver, size=1, players=[bomb] + pl[1:]))
        c.add(f"{tag}_player_hero_count_bomb", build(ver, size=1, players=[p0[:-4] + u32(1 << 30)] + pl[1:]))
        c.add(f"{tag}_player_hero_count_u32_max", build(ver, size=1, players=[p0[:-4] + u32(0xFFFFFFFF)] + pl[1:]))
        c.add(f"{tag}_player_hero_count_256_truncated", build(ver, size=1, players=[p0[:-4] + u32(256) + bytes(50)] + pl[1:]))
    c.add("sod_disposed_count_255_truncated",
          build(SOD, size=1, tail=bytes([0xFF] * 20) + u32(0) + b"\xff" + bytes(10), tiles=b""))
    c.add("sod_predefined_backpack_65535_truncated", build(SOD, size=1, tail=extra(
        SOD, predefined={0: b"\x01\x00\x00\x01" + u16(0xFFFF) * 19 + u16(0xFFFF) + bytes(20)})))
    c.add("sod_predefined_skill_count_bomb", build(SOD, size=1, tail=extra(
        SOD, predefined={0: b"\x01\x00\x01" + u32(0xFFFFFFFF)})))
    c.add("sod_predefined_bio_string_bomb", build(SOD, size=1, tail=extra(
        SOD, predefined={0: b"\x01\x00\x00\x00\x01" + u32(0xFFFFFFF0)})))
    # truncation at the start of every optional section (explicit cut points)
    for ver, tag in ((ROE, "roe"), (AB, "ab"), (SOD, "sod")):
        for cut_name, cut_data in (
                ("before_extra", build(ver, size=1, tail=b"", tiles=b"")),
                ("before_tiles", build(ver, size=1, tiles=b"")),
        ):
            c.add(f"{tag}_ends_{cut_name}", cut_data)


def _small(ver):
    """Tiny but complete map used for the every-cut-point cases."""
    pre = {1: predef(exp=7, skills=[(1, 2)], arts=[0xFFFF] * 19, backpack=[3], bio="b",
                     gender=1, spells=[1] * 9, prim=[1, 2, 3, 4])}
    return build(ver, victory=victory(10, ver), loss=loss(2),
                 teams=b"\x02" + bytes([0, 0, 1, 1, 0, 0, 0, 0]), size=2, two=True,
                 players=[player(ver, i < 2, hero=(i == 0)) for i in range(8)],
                 tail=extra(ver, predefined=pre))


def _cut_cases(c):
    for ver, tag in ((ROE, "roe"), (AB, "ab"), (SOD, "sod")):
        base = f"cut_{tag}_base"
        data = _small(ver)
        c.add(base, data)
        for n in range(len(data)):
            c.cut(f"cut_{tag}_at_{n}", base, n)


def _gzip_cases(c):
    m = build(SOD, size=2)
    c.add("gz_valid", gz(m))
    c.add("gz_valid_level_1", gz(m, level=1))
    c.add("gz_valid_level_0_stored", gz(m, level=0))
    c.add("gz_member_fname", gz_member(m, flags=8, fname=b"map.h3m"))
    c.add("gz_member_extra", gz_member(m, flags=4, extra_f=b"\x01\x02\x03\x04\x05"))
    c.add("gz_member_extra_empty", gz_member(m, flags=4))
    c.add("gz_member_comment", gz_member(m, flags=16, comment=b"hello"))
    c.add("gz_member_all_header_fields_with_hcrc", gz_member(
        m, flags=2 | 4 | 8 | 16, fname=b"a", extra_f=b"xy", comment=b"c"))
    c.add("gz_member_ftext_flag", gz_member(m, flags=1))
    c.add("gz_member_bad_hcrc", gz_member(m, flags=2, hcrc=0x1234))
    c.add("gz_member_reserved_flag_0x20", gz_member(m, flags=0x20))
    c.add("gz_member_reserved_flag_0x80", gz_member(m, flags=0x80))
    c.add("gz_member_cm_7", gz_member(m, cm=7))
    c.add("gz_member_bad_crc", gz_member(m, crc=0xDEADBEEF))
    c.add("gz_member_bad_isize", gz_member(m, isize=len(m) + 1))
    c.add("gz_member_isize_zero", gz_member(m, isize=0))
    c.add("gz_magic_only", b"\x1f\x8b")
    c.add("gz_magic_and_garbage", b"\x1f\x8b\x08garbage")
    c.add("gz_header_only", gz(m)[:10])
    c.add("gz_empty_payload", gz(b""))
    c.add("gz_wrapping_hota", gz(u32(0x20) + bytes(64)))
    c.add("gz_wrapping_empty_map", gz(b"\x1c"))
    g = gz(m)
    c.add("gz_base", g)
    for n in range(2, len(g)):
        c.cut(f"gz_cut_at_{n}", "gz_base", n)
    c.add("gz_trailing_one_byte", g + b"\0")
    c.add("gz_trailing_junk", g + b"junk")
    c.add("gz_trailing_magic_only", g + b"\x1f\x8b")
    c.add("gz_multi_member", g + gz(b"more"))
    c.add("gz_multi_member_same_map", g + g)
    c.add("gz_multi_member_empty_second", g + gz(b""))
    c.add("gz_split_across_members", gz(m[:50]) + gz(m[50:]))
    # decompression cap: 64 MiB of zeros (and one byte under) compress to ~64 KB
    c.add("gz_bomb_64mib", gz(bytes(H.MAX_DECOMPRESSED)))
    c.add("gz_bomb_64mib_plus_1", gz(bytes(H.MAX_DECOMPRESSED + 1)))
    big = u32(SOD) + bytes(H.MAX_DECOMPRESSED - 4 - 8)
    c.add("gz_bomb_just_under_cap", gz(big))
    c.add("plain_starting_like_gzip_magic", b"\x1f\x8b" + bytes(60))


def generate():
    c = _Cases()
    _fixtures(c)
    _error_cases(c)
    _cut_cases(c)
    _gzip_cases(c)
    return {VECTOR_FILE: {"format": VECTOR_FORMAT, "cases": c.cases}}
