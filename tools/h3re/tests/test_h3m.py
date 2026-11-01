import gzip
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from h3re.h3m import H3mError, Tile, parse_h3m, parse_h3m_bytes, ROE, AB, SOD, CHR
from h3re.h3m import H3mUnsupportedObject, MapObject, ObjectTemplate, WOG


def s(t):
    b = t.encode("cp1252")
    return struct.pack("<I", len(b)) + b


def player(ver, active=True, town=True, hero=True):
    if not active:
        return b"\0\0" + bytes({ROE: 6, AB: 12}.get(ver, 13))
    b = b"\x01\x01" + b"\x00"  # human, computer, behavior
    if ver >= SOD:
        b += b"\x00"
    b += b"\xff" if ver == ROE else b"\xff\x01"
    b += b"\x00"  # random faction
    if town:
        b += b"\x01"
        if ver != ROE:
            b += b"\x01\x00"
        b += bytes([3, 4, 0])
    else:
        b += b"\x00"
    if hero:
        b += b"\x00\x05\x07" + s("Orrin")
    else:
        b += b"\x00\xff"
    if ver != ROE:
        b += b"\x00" + struct.pack("<I", 1) + b"\x09" + s("Bob")
    return b


def extra(ver, rumors=(("Tavern", "Dragons!"),), disposed=True, predefined=None):
    """Synthetic post-teams sections for the given version."""
    b = bytes([0xFF] * 16) if ver == ROE else bytes([0xFF] * 19 + [0x0F])
    if ver != ROE:
        b += struct.pack("<I", 2) + b"\x05\x06"
    if ver >= SOD:
        b += b"\x01\x0a\x0b" + s("Dis") + b"\x03"
    b += bytes(31)
    if ver != ROE:
        b += bytes([0x01] + [0] * (16 if ver == AB else 17))
    if ver >= SOD:
        b += bytes([0x02] + [0] * 8) + bytes([0, 0x80, 0, 0])
    b += struct.pack("<I", len(rumors))
    for n, t in rumors:
        b += s(n) + s(t)
    if ver >= SOD:
        pre = predefined or {}
        for i in range(156):
            b += pre.get(i, b"\x00")
    return b


def tiles_for(size, levels):
    out = b""
    for z in range(levels):
        for y in range(size):
            for x in range(size):
                out += bytes([x % 256, y % 256, z, 1, 2, 3, 4])
    return out


def build(ver, victory=b"\xff", loss=b"\xff", teams=b"\x00", inactive_from=2,
          tail=None, size=36, two=False, tiles=None):
    b = (struct.pack("<I", ver) + b"\x01" + struct.pack("<I", size)
         + (b"\x01" if two else b"\x00"))
    b += s("Test Map") + s("A description") + b"\x02"
    if ver != ROE:
        b += b"\x00"
    for i in range(8):
        b += player(ver, active=i < inactive_from, hero=(i == 0))
    if tiles is None:
        tiles = tiles_for(size, 2 if two else 1)
    return (b + victory + loss + teams + (extra(ver) if tail is None else tail)
            + tiles)


class H3mTests(unittest.TestCase):
    def check_ver(self, ver, name):
        h = parse_h3m(gzip.compress(build(ver)))
        self.assertEqual(h.version, name)
        self.assertEqual(h.size, 36)
        self.assertEqual(h.name, "Test Map")
        self.assertEqual(h.description, "A description")
        self.assertEqual(h.difficulty, 2)
        self.assertEqual(h.max_hero_level, None if ver == ROE else 0)
        self.assertEqual(len(h.players), 8)
        self.assertTrue(h.players[0].active)
        self.assertFalse(h.players[5].active)
        self.assertEqual(h.players[0].main_town_pos, (3, 4, 0))
        self.assertEqual(h.players[0].main_hero_name, "Orrin")
        self.assertIsNone(h.players[1].main_hero_id)
        if ver != ROE:
            self.assertEqual(h.players[0].heroes, [(9, "Bob")])
            self.assertEqual(h.players[0].allowed_factions, 0x01FF)
        else:
            self.assertEqual(h.players[0].allowed_factions, 0xFF)
        self.assertIsNone(h.victory)
        self.assertIsNone(h.loss)
        self.assertEqual(h.teams, [])

    def test_extra_sections(self):
        for ver in (ROE, AB, SOD):
            h = parse_h3m_bytes(build(ver))
            self.assertEqual(h.rumors, [("Tavern", "Dragons!")])
            self.assertEqual(len(h.allowed_heroes_mask), 16 if ver == ROE else 20)
            self.assertIn(0, h.allowed_heroes)
            if ver == ROE:
                self.assertEqual(len(h.allowed_heroes), 128)
                self.assertEqual(h.placeholder_heroes, [])
                self.assertIsNone(h.banned_artifacts)
            else:
                self.assertEqual(len(h.allowed_heroes), 156)
                self.assertEqual(h.placeholder_heroes, [5, 6])
                self.assertEqual(h.banned_artifacts, [0])
            if ver >= SOD:
                self.assertEqual(h.disposed_heroes, [
                    {"id": 10, "portrait": 11, "name": "Dis", "players": 3}])
                self.assertEqual(h.banned_spells, [1])
                self.assertEqual(h.banned_skills, [15])
                self.assertEqual(h.predefined_heroes, {})
            else:
                self.assertEqual(h.disposed_heroes, [])
                self.assertIsNone(h.banned_spells)

    def test_predefined_heroes(self):
        full = (b"\x01" + b"\x01" + struct.pack("<I", 1000)
                + b"\x01" + struct.pack("<I", 2) + b"\x03\x02\x05\x01"
                + b"\x01" + struct.pack("<H", 7) * 1 + struct.pack("<H", 0xFFFF) * 18
                + struct.pack("<H", 1) + struct.pack("<H", 9)
                + b"\x01" + s("Bio") + b"\x01"
                + b"\x01" + bytes([1] + [0] * 8)
                + b"\x01" + bytes([1, 2, 3, 4]))
        raw = build(SOD, tail=extra(SOD, predefined={3: full, 155: b"\x01" + b"\x00" * 4 + b"\xff" + b"\x00" * 2}))
        h = parse_h3m_bytes(raw)
        d = h.predefined_heroes[3]
        self.assertEqual(d["experience"], 1000)
        self.assertEqual(d["secondary_skills"], [(3, 2), (5, 1)])
        self.assertEqual(d["artifacts"][0], 7)
        self.assertIsNone(d["artifacts"][1])
        self.assertEqual(d["backpack"], [9])
        self.assertEqual(d["biography"], "Bio")
        self.assertEqual(d["gender"], 1)
        self.assertEqual(d["spells_mask"][0], 1)
        self.assertEqual(d["primary_skills"], (1, 2, 3, 4))
        self.assertEqual(h.predefined_heroes[155], {})

    def test_extra_errors(self):
        for ver in (ROE, AB, SOD):
            good = build(ver)
            start = len(build(ver, tail=b"", tiles=b""))
            for cut in range(start, len(good), 7):
                with self.assertRaises(H3mError, msg=f"{ver} {cut}"):
                    parse_h3m_bytes(good[:cut])
            with self.assertRaises(H3mError):
                parse_h3m_bytes(good[:-1])
        base = build(AB, tail=b"")
        with self.assertRaises(H3mError):  # huge placeholder count
            parse_h3m_bytes(base + bytes(20) + struct.pack("<I", 1 << 30))
        with self.assertRaises(H3mError):  # huge rumor count
            parse_h3m_bytes(build(ROE, tail=bytes(16 + 31) + struct.pack("<I", 1 << 30)))
        with self.assertRaises(H3mError):  # bad skill count
            pre = b"\x01\x00\x01" + struct.pack("<I", 99)
            parse_h3m_bytes(build(SOD, tail=extra(SOD, predefined={0: pre})))

    def test_roe(self):
        self.check_ver(ROE, "RoE")

    def test_ab(self):
        self.check_ver(AB, "AB")

    def test_sod(self):
        self.check_ver(SOD, "SoD")

    def test_conditions_and_teams(self):
        vic = b"\x02\x01\x00" + b"\x03" + struct.pack("<I", 5000)
        loss = b"\x02" + struct.pack("<H", 30)
        teams = b"\x02" + bytes([0, 0, 1, 1, 0, 0, 0, 0])
        h = parse_h3m_bytes(build(SOD, vic, loss, teams))
        self.assertEqual(h.victory["type"], 2)
        self.assertEqual(h.victory["amount"], 5000)
        self.assertTrue(h.victory["allow_normal_victory"])
        self.assertEqual(h.loss, {"type": 2, "days": 30})
        self.assertEqual(h.teams[2], 1)
        h = parse_h3m_bytes(build(ROE, b"\x00\x00\x01\x07", b"\x00\x0a\x0b\x00"))
        self.assertEqual(h.victory["artifact"], 7)
        self.assertEqual(h.loss["pos"], (10, 11, 0))

    def test_victory_transport_artifact_has_position(self):
        vic = b"\x0a\x01\x00" + b"\x2a" + bytes([5, 6, 1])
        loss = b"\x02" + struct.pack("<H", 30)
        teams = b"\x02" + bytes([0, 0, 1, 1, 0, 0, 0, 0])
        for ver in (ROE, AB, SOD):
            h = parse_h3m_bytes(build(ver, vic, loss, teams))
            self.assertEqual(h.victory["artifact"], 0x2A)
            self.assertEqual(h.victory["pos"], (5, 6, 1))
            self.assertEqual(h.loss, {"type": 2, "days": 30})
            self.assertEqual(h.teams[2], 1)
            self.assertEqual(h.rumors, [("Tavern", "Dragons!")])
            self.assertEqual(h.size, 36)

    def test_sod_artifact_ids_141_to_143_banned(self):
        tail = extra(SOD)
        old = bytes([0x01] + [0] * 17)
        new = bytes([0x01] + [0] * 16 + [0xE0])
        self.assertIn(old, tail)
        h = parse_h3m_bytes(build(SOD, tail=tail.replace(old, new)))
        self.assertEqual(h.banned_artifacts, [0, 141, 142, 143])
        self.assertEqual(len(h.allowed_artifacts_mask), 18)

    def test_chronicles_uses_sod_layout(self):
        h = parse_h3m_bytes(build(CHR))
        self.assertEqual(h.version, "Chronicles")
        self.assertEqual(h.banned_spells, [1])
        self.assertEqual(len(h.allowed_artifacts_mask), 18)

    def test_hota_explicitly_unsupported(self):
        raw = struct.pack("<I", 0x20) + bytes(64)
        with self.assertRaises(H3mError) as cm:
            parse_h3m_bytes(raw)
        self.assertIn("HotA", str(cm.exception))
        self.assertIn("unsupported map format", str(cm.exception))

    def test_errors(self):
        good = build(SOD)
        with self.assertRaises(H3mError):
            parse_h3m_bytes(b"")
        with self.assertRaises(H3mError):
            parse_h3m_bytes(struct.pack("<I", 0x99) + good[4:])
        for cut in (5, 20, 40, 100, len(good) - 1):
            with self.assertRaises(H3mError, msg=str(cut)):
                parse_h3m_bytes(good[:cut])
        with self.assertRaises(H3mError):
            parse_h3m(b"\x1f\x8b\x08garbage")
        with self.assertRaises(H3mError):
            parse_h3m(gzip.compress(good)[:-10])
        # huge string length
        bad = good[:10] + struct.pack("<I", 0x7FFFFFFF) + good[14:]
        with self.assertRaises(H3mError):
            parse_h3m_bytes(bad)
        with self.assertRaises(H3mError):
            parse_h3m_bytes(build(SOD, victory=b"\x63\x00\x00"))
        bad = bytearray(good)
        bad[5:9] = struct.pack("<I", 0)
        with self.assertRaises(H3mError):
            parse_h3m_bytes(bytes(bad))

    def test_gzip_truncated_rejected(self):
        gz = gzip.compress(build(SOD))
        for cut in (len(gz) - 1, len(gz) - 8, len(gz) // 2):
            with self.assertRaises(H3mError, msg=str(cut)):
                parse_h3m(gz[:cut])

    def test_gzip_trailing_and_multimember_rejected(self):
        gz = gzip.compress(build(SOD))
        with self.assertRaises(H3mError):
            parse_h3m(gz + b"junk")
        with self.assertRaises(H3mError):
            parse_h3m(gz + gzip.compress(b"more"))
        self.assertEqual(parse_h3m(gz).name, "Test Map")

    def test_map_size_bounds(self):
        good = build(SOD, tiles=b"")
        for size, ok in ((0, False), (1, True), (1024, True), (1025, False)):
            raw = good[:5] + struct.pack("<I", size) + good[9:] + tiles_for(1, 1) * (size * size if ok else 0)
            if ok:
                self.assertEqual(parse_h3m_bytes(raw).size, size)
            else:
                with self.assertRaises(H3mError):
                    parse_h3m_bytes(raw)

    def test_tiles_one_level(self):
        for ver in (ROE, AB, SOD):
            h = parse_h3m_bytes(build(ver, size=3))
            self.assertEqual(h.levels, 1)
            self.assertEqual(len(h.tiles_raw), 3 * 3 * 7)
            self.assertEqual(h.tile(2, 1), Tile(2, 1, 0, 1, 2, 3, 4))
            self.assertEqual(len(list(h.tiles)), 9)
            with self.assertRaises(IndexError):
                h.tile(0, 0, 1)
            with self.assertRaises(IndexError):
                h.tile(3, 0)

    def test_tiles_two_levels(self):
        h = parse_h3m_bytes(build(SOD, size=4, two=True))
        self.assertEqual(h.levels, 2)
        self.assertEqual(len(h.tiles_raw), 4 * 4 * 2 * 7)
        self.assertEqual(h.tile(3, 2, 1), Tile(3, 2, 1, 1, 2, 3, 4))
        self.assertEqual(list(h.tiles)[16], h.tile(0, 0, 1))

    def test_tiles_truncated_and_trailing(self):
        good = build(SOD, size=3, two=True)
        for cut in (1, 7, 3 * 3 * 2 * 7 - 1, 3 * 3 * 7):
            with self.assertRaises(H3mError, msg=str(cut)):
                parse_h3m_bytes(good[:len(good) - cut])
        # one-level tiles but header says two levels
        with self.assertRaises(H3mError):
            parse_h3m_bytes(build(SOD, size=3, two=True, tiles=tiles_for(3, 1)))
        # bytes after the tiles (objects) are ignored, not parsed
        h = parse_h3m_bytes(good + b"objects...")
        self.assertEqual(len(h.tiles_raw), 3 * 3 * 2 * 7)

    def test_tiles_huge_size_no_data(self):
        with self.assertRaises(H3mError):
            parse_h3m_bytes(build(SOD, size=1024, two=True, tiles=b""))

    def test_uncompressed_accepted(self):
        self.assertEqual(parse_h3m(build(AB)).name, "Test Map")


# ------------------------------------------------------------ objects section
# Encoders below follow docs/specs/h3m.md ("Objects"); each takes the dict the
# parser is expected to return, so parse(encode(d)) == d is a round trip.

u8 = lambda v: struct.pack("<B", v)  # noqa: E731
u16 = lambda v: struct.pack("<H", v)  # noqa: E731
u32 = lambda v: struct.pack("<I", v)  # noqa: E731
i32 = lambda v: struct.pack("<i", v)  # noqa: E731
i8 = lambda v: struct.pack("<b", v)  # noqa: E731


def w_id(ver, v):
    """u8 id in RoE, u16 later; None encodes the 'none' sentinel."""
    if ver == ROE:
        return u8(0xFF if v is None else v)
    return u16(0xFFFF if v is None else v)


def e_opt8(v):
    return u8(0xFF if v is None else v)


def e_army(ver, army):
    return b"".join(w_id(ver, c) + u16(n) for c, n in army)


def e_res(res):
    return b"".join(i32(v) for v in res)


def e_msg_guards(ver, d):
    if d["message"] is None:
        return b"\0"
    b = b"\x01" + s(d["message"])
    b += b"\0" if d["guards"] is None else b"\x01" + e_army(ver, d["guards"])
    return b + bytes(4)


def e_box(ver, d):
    b = e_msg_guards(ver, d) + u32(d["experience"]) + i32(d["mana"])
    b += i8(d["morale"]) + i8(d["luck"]) + e_res(d["resources"])
    b += bytes(d["primary_skills"])
    b += u8(len(d["secondary_skills"])) + b"".join(bytes(p) for p in d["secondary_skills"])
    b += u8(len(d["artifacts"])) + b"".join(w_id(ver, a) for a in d["artifacts"])
    b += u8(len(d["spells"])) + bytes(d["spells"])
    b += u8(len(d["creatures"])) + b"".join(w_id(ver, c) + u16(n) for c, n in d["creatures"])
    return b + bytes(8)


def e_event_common(ver, d):
    b = s(d["name"]) + s(d["message"]) + e_res(d["resources"]) + u8(d["players_mask"])
    if ver >= SOD:
        b += u8(d["human_affected"])
    return b + u8(d["computer_affected"]) + u16(d["first_day"]) + u16(d["repeat_days"]) + bytes(16)


def e_hero(ver, d):
    b = u32(d["identifier"]) if ver >= AB else b""
    b += e_opt8(d["owner"]) + e_opt8(d["hero_type"])
    b += b"\0" if d["name"] is None else b"\x01" + s(d["name"])
    if ver >= SOD:
        b += b"\0" if d["experience"] is None else b"\x01" + u32(d["experience"])
    else:
        b += u32(d["experience"])
    b += b"\0" if d["portrait"] is None else b"\x01" + u8(d["portrait"])
    sk = d["secondary_skills"]
    b += b"\0" if sk is None else b"\x01" + u32(len(sk)) + b"".join(bytes(p) for p in sk)
    b += b"\0" if d["army"] is None else b"\x01" + e_army(ver, d["army"])
    b += u8(d["formation"])
    a = d["artifacts"]
    if a is None:
        b += b"\0"
    else:
        b += b"\x01" + b"".join(w_id(ver, x) for x in a["slots"])
        b += u16(len(a["backpack"])) + b"".join(w_id(ver, x) for x in a["backpack"])
    b += e_opt8(d["patrol_radius"])
    if ver >= AB:
        b += b"\0" if d["biography"] is None else b"\x01" + s(d["biography"])
        b += e_opt8(d["gender"])
    if ver >= SOD:
        b += b"\0" if d["spells_mask"] is None else b"\x01" + d["spells_mask"]
        b += b"\0" if d["primary_skills"] is None else b"\x01" + bytes(d["primary_skills"])
    elif ver >= AB:
        b += u8(d["spell"])
    return b + bytes(16)


def e_monster(ver, d):
    b = u32(d["identifier"]) if ver >= AB else b""
    b += u16(d["count"]) + u8(d["character"])
    if d["message"] is None:
        b += b"\0"
    else:
        b += b"\x01" + s(d["message"]) + e_res(d["resources"]) + w_id(ver, d["artifact"])
    return b + u8(d["never_flees"]) + u8(d["not_growing"]) + bytes(2)


def e_town(ver, d):
    b = u32(d["identifier"]) if ver >= AB else b""
    b += e_opt8(d["owner"])
    b += b"\0" if d["name"] is None else b"\x01" + s(d["name"])
    b += b"\0" if d["army"] is None else b"\x01" + e_army(ver, d["army"])
    b += u8(d["formation"])
    if d["built_mask"] is not None:
        b += b"\x01" + d["built_mask"] + d["forbidden_mask"]
    else:
        b += b"\0" + u8(d["has_fort"])
    if ver >= AB:
        b += d["obligatory_spells_mask"]
    b += d["banned_spells_mask"] + u32(len(d["events"]))
    for e in d["events"]:
        b += e_event_common(ver, e) + e["buildings_mask"]
        b += b"".join(u16(c) for c in e["creatures"]) + bytes(4)
    if ver >= SOD:
        b += u8(d["alignment"])
    return b + bytes(3)


def e_random_dwelling(ver, cls, d):
    b = u32(d["owner"])
    if cls in (216, 217):
        b += u32(d["faction_identifier"])
        if d["faction_identifier"] == 0:
            b += u8(d["factions_mask"]) if ver == ROE else u16(d["factions_mask"])
    if cls in (216, 218):
        b += u8(d["min_level"]) + u8(d["max_level"])
    return b


def e_template(t):
    return (s(t.def_name) + t.passable + t.active + u16(t.terrain_mask_first)
            + u16(t.allowed_terrains) + u32(t.class_id) + u32(t.subid)
            + u8(t.type) + u8(t.draw_order) + t.reserved)


def tmpl(name, cls, sub, typ=0, order=0):
    return ObjectTemplate(name, bytes([0xFF] * 5 + [0x7F]), bytes(5) + b"\x80",
                          0x01FF, 0x00FF, cls, sub, typ, order, bytes(16))


ARMY = [(1, 10), (None, 0), (3, 5), (None, 0), (None, 0), (None, 0), (7, 1)]
RES = (1, 2, 3, 4, 5, 6, -500)


def box(ver):
    return {"message": "Boo", "guards": ARMY, "experience": 1500, "mana": -5,
            "morale": -3, "luck": 2, "resources": RES, "primary_skills": (1, 0, 2, 0),
            "secondary_skills": [(4, 2)], "artifacts": [7, None], "spells": [3],
            "creatures": [(2, 20), (None, 1)]}


def gevent(ver, name):
    return {"name": name, "message": "msg", "resources": RES, "players_mask": 0x81,
            "human_affected": True, "computer_affected": False, "first_day": 3,
            "repeat_days": 7}


def object_fixture(ver):
    """(templates, [(template index, pos, kind, body, body bytes)], events)."""
    hero = {"identifier": 77 if ver >= AB else None, "owner": 1, "hero_type": 5,
            "name": "Tester", "experience": 1234, "portrait": 9,
            "secondary_skills": [(1, 3), (2, 1)], "army": ARMY, "formation": 1,
            "artifacts": {"slots": [3] + [None] * (18 if ver >= SOD else 17),
                          "backpack": [8, 9]},
            "patrol_radius": None,
            "biography": "Bio" if ver >= AB else None,
            "gender": 1 if ver >= AB else None,
            "spells_mask": bytes([1] + [0] * 8) if ver >= SOD else None,
            "spell": 0xFE if ver == AB else None,
            "primary_skills": (1, 2, 3, 4) if ver >= SOD else None}
    random_hero = dict(hero, owner=None, hero_type=None, name=None, portrait=None,
                       secondary_skills=None, army=None, artifacts=None,
                       patrol_radius=3, biography=None,
                       gender=None, spells_mask=None, primary_skills=None,
                       experience=None if ver >= SOD else 0)
    town_ev = dict(gevent(ver, "TE"), buildings_mask=bytes([1, 2, 3, 4, 5, 6]),
                   creatures=(1, 2, 3, 4, 5, 6, 7))
    if ver < SOD:
        town_ev["human_affected"] = True
    town = {"identifier": 99 if ver >= AB else None, "owner": 0, "name": "Burg",
            "army": ARMY, "formation": 0, "built_mask": bytes([0xFF, 0, 0, 0, 0, 1]),
            "forbidden_mask": bytes(6), "has_fort": None,
            "obligatory_spells_mask": bytes(9) if ver >= AB else None,
            "banned_spells_mask": bytes([0x10] + [0] * 8), "events": [town_ev],
            "alignment": 0xFF if ver >= SOD else None}
    town2 = dict(town, name=None, army=None, built_mask=None, forbidden_mask=None,
                 has_fort=True, events=[], identifier=100 if ver >= AB else None,
                 owner=None)
    monster = {"identifier": 5 if ver >= AB else None, "count": 25, "character": 2,
               "message": "Grr", "resources": RES, "artifact": 4,
               "never_flees": True, "not_growing": False}
    monster2 = dict(monster, message=None, resources=None, artifact=None)
    ev = box(ver)
    ev.update(players_mask=0x05, computer_activate=True, remove_after_visit=False)
    temps = [tmpl("AVCTOWN0", 98, 1), tmpl("AH00_", 34, 0, 3), tmpl("AVWMON", 54, 3, 2),
             tmpl("AVMMINE", 53, 2), tmpl("AVXAMINE", 53, 7), tmpl("AVTRES", 79, 6, 5),
             tmpl("AVA0001", 5, 7, 4), tmpl("AVGDWEL", 17, 4), tmpl("AVXRDW", 216, 0),
             tmpl("AVZEVNT", 26, 0), tmpl("AVTPINE", 137, 0, 0, 1), tmpl("AVAPAND", 6, 0),
             tmpl("AVSCROLL", 93, 0, 4), tmpl("AVRHERO", 70, 0, 3), tmpl("AVRTOWN", 77, 0),
             tmpl("AVRMON", 71, 0, 2), tmpl("AVXRDW2", 217, 2), tmpl("AVXRDW3", 218, 1),
             tmpl("UNUSED", 250, 0)]
    rd216 = {"owner": 255, "faction_identifier": 0, "factions_mask": 0x0F,
             "min_level": 1, "max_level": 4}
    rd217 = {"owner": 2, "faction_identifier": 1234, "factions_mask": None,
             "min_level": None, "max_level": None}
    rd218 = {"owner": 2, "faction_identifier": None, "factions_mask": None,
             "min_level": 0, "max_level": 6}
    art = {"message": None, "guards": None}
    art2 = {"message": "Take it", "guards": None}
    res = {"message": "Gold", "guards": ARMY, "amount": 500}
    scroll = {"message": None, "guards": None, "spell": 17}
    am = {"resources_mask": bytes([0x05, 0, 0, 0]), "resources": [0, 2]}
    objs = [
        (0, (1, 1, 0), "town", town, e_town(ver, town)),
        (1, (2, 0, 0), "hero", hero, e_hero(ver, hero)),
        (2, (0, 2, 0), "monster", monster, e_monster(ver, monster)),
        (2, (2, 2, 0), "monster", monster2, e_monster(ver, monster2)),
        (3, (1, 0, 0), "mine", {"owner": 255}, u32(255)),
        (4, (0, 1, 0), "abandoned_mine", am, am["resources_mask"]),
        (5, (2, 1, 0), "resource", res, e_msg_guards(ver, res) + u32(500) + bytes(4)),
        (6, (0, 0, 0), "artifact", art, e_msg_guards(ver, art)),
        (6, (1, 2, 0), "artifact", art2, e_msg_guards(ver, art2)),
        (7, (8, 8, 0), "dwelling", {"owner": 3}, u32(3)),
        (8, (1, 1, 0), "random_dwelling", rd216, e_random_dwelling(ver, 216, rd216)),
        (9, (0, 0, 0), "event", ev, e_box(ver, ev) + bytes([5, 1, 0]) + bytes(4)),
        (10, (2, 2, 0), "generic", {}, b""),
        (11, (1, 1, 0), "pandora", box(ver), e_box(ver, box(ver))),
        (12, (0, 1, 0), "spell_scroll", scroll, e_msg_guards(ver, scroll) + u32(17)),
        (13, (2, 0, 0), "hero", random_hero, e_hero(ver, random_hero)),
        (14, (1, 1, 0), "town", town2, e_town(ver, town2)),
        (15, (0, 2, 0), "monster", monster2, e_monster(ver, monster2)),
        (16, (1, 0, 0), "random_dwelling", rd217, e_random_dwelling(ver, 217, rd217)),
        (17, (1, 0, 0), "random_dwelling", rd218, e_random_dwelling(ver, 218, rd218)),
    ]
    events = [gevent(ver, "E1"), dict(gevent(ver, "E2"), players_mask=0, first_day=1)]
    if ver < SOD:
        for e in events:
            e["human_affected"] = True
    return temps, objs, events


def e_quest(ver, q):
    """AB-style quest encoder (None = no quest)."""
    if q is None:
        return u8(0)
    m = q["type"]
    b = u8(m)
    if m == 1:
        b += u32(q["level"])
    elif m == 2:
        b += bytes(q["primary_skills"])
    elif m in (3, 4):
        b += u32(q["target_identifier"])
    elif m == 5:
        b += u8(len(q["artifacts"])) + b"".join(w_id(ver, a) for a in q["artifacts"])
    elif m == 6:
        b += u8(len(q["creatures"])) + e_army(ver, q["creatures"])
    elif m == 7:
        b += b"".join(u32(v) for v in q["resources"])
    elif m == 8:
        b += e_opt8(q["hero"])
    elif m == 9:
        b += e_opt8(q["player"])
    return (b + i32(q["deadline"]) + s(q["first_visit"]) + s(q["next_visit"])
            + s(q["completed"]))


def e_reward(ver, d):
    k = d["type"]
    b = u8(k)
    return b + {
        0: lambda: b"",
        1: lambda: u32(d.get("experience", 0)),
        2: lambda: u32(d.get("mana", 0)),
        3: lambda: i8(d.get("morale", 0)),
        4: lambda: i8(d.get("luck", 0)),
        5: lambda: i8(d.get("resource", 0)) + u32(d.get("amount", 0)),
        6: lambda: u8(d.get("primary_skill", 0)) + u8(d.get("amount", 0)),
        7: lambda: u8(d.get("skill", 0)) + i8(d.get("level", 0)),
        8: lambda: w_id(ver, d.get("artifact")),
        9: lambda: u8(d.get("spell", 0)),
        10: lambda: w_id(ver, d.get("creature")) + u16(d.get("count", 0)),
    }[k]()


def e_seer(ver, d):
    q = d["quest"]
    if ver == ROE:
        b = w_id(ver, None if q is None else q["artifacts"][0])
    else:
        b = e_quest(ver, q)
    b += u8(0) if q is None else e_reward(ver, d["reward"])
    return b + bytes(2)


QUEST_SAMPLES = [
    {"type": 1, "level": 12},
    {"type": 2, "primary_skills": (1, 2, 3, 4)},
    {"type": 3, "target_identifier": 0xDEAD},
    {"type": 4, "target_identifier": 7},
    {"type": 5, "artifacts": [7, 9, None]},
    {"type": 6, "creatures": [(1, 10), (None, 3)]},
    {"type": 7, "resources": (1, 2, 3, 4, 5, 6, 0xFFFFFFFF)},
    {"type": 8, "hero": 33},
    {"type": 9, "player": None},
]
REWARD_SAMPLES = [
    {"type": 0}, {"type": 1, "experience": 5000}, {"type": 2, "mana": 30},
    {"type": 3, "morale": -2}, {"type": 4, "luck": 3},
    {"type": 5, "resource": 6, "amount": 2000},
    {"type": 6, "primary_skill": 2, "amount": 4}, {"type": 7, "skill": 14, "level": 3},
    {"type": 8, "artifact": 100}, {"type": 9, "spell": 53},
    {"type": 10, "creature": 13, "count": 6},
]


def full_quest(i, q):
    return dict(q, deadline=-1 if i % 2 else 120, first_visit=f"first {i}",
                next_visit="", completed=f"done {i}")


def new_object_fixture(ver):
    """Fixture for the bodies added after the first object cut (signs ... quest guards)."""
    temps = [tmpl("AVXSIGN", 91, 0), tmpl("AVXBOTL", 59, 0), tmpl("AVCGAR", 33, 0),
             tmpl("AVCGAR2", 219, 0), tmpl("AVZGRAIL", 36, 0), tmpl("AVXLITE", 42, 0),
             tmpl("AVXSCHL", 81, 0), tmpl("AVXSEER", 83, 0), tmpl("AVXSHYD", 87, 0),
             tmpl("AVXSHR1", 88, 0), tmpl("AVXSHR2", 89, 0), tmpl("AVXSHR3", 90, 0),
             tmpl("AVXWHUT", 113, 0), tmpl("AVXHPL", 214, 0), tmpl("AVXQGRD", 215, 0),
             tmpl("AVXBGRD", 9, 2), tmpl("AVXKEYM", 10, 2), tmpl("AVXBGAT", 212, 3),
             tmpl("AVXPYRA", 63, 0), tmpl("AVXUNIV", 104, 0)]
    sign = {"message": "Beware"}
    gar = {"owner": 255, "army": ARMY, "removable_units": False if ver >= AB else True}
    gar2 = dict(gar, owner=3, removable_units=True)
    objs = [
        (0, (0, 0, 0), "sign", sign, s("Beware") + bytes(4)),
        (1, (1, 0, 0), "sign", {"message": ""}, s("") + bytes(4)),
        (2, (2, 0, 0), "garrison", gar, u32(255) + e_army(ver, ARMY)
         + (u8(0) if ver >= AB else b"") + bytes(8)),
        (3, (0, 1, 0), "garrison", gar2, u32(3) + e_army(ver, ARMY)
         + (u8(1) if ver >= AB else b"") + bytes(8)),
        (4, (1, 1, 0), "grail", {"radius": 4}, i32(4)),
        (5, (2, 1, 0), "lighthouse", {"owner": 1}, u32(1)),
        (6, (0, 2, 0), "scholar", {"bonus_type": -1, "bonus_id": 0}, i8(-1) + u8(0) + bytes(6)),
        (6, (0, 2, 0), "scholar", {"bonus_type": 2, "bonus_id": 15}, i8(2) + u8(15) + bytes(6)),
        (8, (1, 2, 0), "shipyard", {"owner": 255}, u32(255)),
        (9, (2, 2, 0), "shrine", {"spell": 17}, u32(17)),
        (10, (2, 2, 0), "shrine", {"spell": None}, u32(0xFF)),
        (11, (2, 2, 0), "shrine", {"spell": 0}, u32(0)),
    ]
    if ver == ROE:
        objs.append((12, (0, 0, 0), "witch_hut", {"skills_mask": None, "skills": None}, b""))
    else:
        m = bytes([0x01, 0, 0x80, 0x08])
        objs.append((12, (0, 0, 0), "witch_hut",
                     {"skills_mask": m, "skills": [0, 23, 27]}, m))
    objs += [
        (13, (0, 0, 0), "hero_placeholder", {"owner": 2, "hero_type": 40, "power_rank": None},
         u8(2) + u8(40)),
        (13, (0, 0, 0), "hero_placeholder", {"owner": None, "hero_type": None, "power_rank": 3},
         u8(0xFF) + u8(0xFF) + u8(3)),
        (15, (0, 0, 0), "generic", {}, b""),
        (16, (0, 0, 0), "generic", {}, b""),
        (17, (0, 0, 0), "generic", {}, b""),
        (18, (0, 0, 0), "generic", {}, b""),
        (19, (0, 0, 0), "generic", {}, b""),
    ]
    # Seer huts: an empty one, then every quest type (AB+) / the artifact quest
    # (RoE), and every reward type.
    seers = [{"quest": None, "reward": None}]
    if ver == ROE:
        for rw in REWARD_SAMPLES:
            a = rw.get("artifact", 0) if rw["type"] == 8 else 3
            seers.append({"quest": {"type": 5, "artifacts": [a], "deadline": None,
                                    "first_visit": None, "next_visit": None,
                                    "completed": None}, "reward": rw})
    else:
        for i, rw in enumerate(REWARD_SAMPLES):
            q = full_quest(i, QUEST_SAMPLES[i % len(QUEST_SAMPLES)])
            seers.append({"quest": q, "reward": rw})
    for d in seers:
        objs.append((7, (1, 1, 0), "seer_hut", d, e_seer(ver, d)))
    # Quest guards: no quest, then every quest type (AB-style in every version).
    for q in [None] + [full_quest(i, q) for i, q in enumerate(QUEST_SAMPLES)]:
        objs.append((14, (2, 2, 0), "quest_guard", {"quest": q}, e_quest(ver, q)))
    return temps, objs, []


def e_objects(ver, temps, objs, events, trailer=b""):
    b = u32(len(temps)) + b"".join(e_template(t) for t in temps) + u32(len(objs))
    for ti, (x, y, z), _k, _d, body in objs:
        b += bytes([x, y, z]) + u32(ti) + bytes(5) + body
    b += u32(len(events)) + b"".join(e_event_common(ver, e) for e in events)
    return b + trailer


def map_with(ver, section, size=3):
    return build(ver, size=size) + section


class H3mObjectTests(unittest.TestCase):
    def roundtrip(self, ver):
        temps, objs, events = object_fixture(ver)
        h = parse_h3m_bytes(map_with(ver, e_objects(ver, temps, objs, events)),
                            objects=True)
        self.assertTrue(h.objects_parsed)
        self.assertEqual(h.templates, temps)
        self.assertEqual(len(h.objects), len(objs))
        for i, (o, (ti, pos, kind, body, _b)) in enumerate(zip(h.objects, objs)):
            with self.subTest(ver=ver, obj=i, kind=kind):
                self.assertIsInstance(o, MapObject)
                self.assertEqual(o.index, i)
                self.assertEqual((o.x, o.y, o.level), pos)
                self.assertEqual(o.template_index, ti)
                self.assertEqual((o.class_id, o.subid),
                                 (temps[ti].class_id, temps[ti].subid))
                self.assertEqual(o.kind, kind)
                self.assertEqual(o.body, body)
        self.assertEqual(h.events, events)
        self.assertEqual(h.trailing_bytes, 0)
        # header and tiles are unaffected by object parsing
        self.assertEqual(h.tile(2, 1), Tile(2, 1, 0, 1, 2, 3, 4))
        return h

    def test_roundtrip_roe(self):
        self.roundtrip(ROE)

    def test_roundtrip_ab(self):
        self.roundtrip(AB)

    def test_roundtrip_sod(self):
        self.roundtrip(SOD)

    def test_wog_and_chronicles_use_sod_bodies(self):
        temps, objs, events = object_fixture(SOD)
        sec = e_objects(SOD, temps, objs, events)
        for ver in (CHR, WOG):
            h = parse_h3m_bytes(map_with(ver, sec), objects=True)
            self.assertEqual([o.body for o in h.objects], [o[3] for o in objs])

    def test_object_offsets_point_at_records(self):
        temps, objs, events = object_fixture(SOD)
        raw = map_with(SOD, e_objects(SOD, temps, objs, events))
        h = parse_h3m_bytes(raw, objects=True)
        for o in h.objects:
            self.assertEqual(tuple(raw[o.offset:o.offset + 3]), (o.x, o.y, o.level))
            self.assertEqual(struct.unpack_from("<I", raw, o.offset + 3)[0],
                             o.template_index)

    def test_template_fields(self):
        t = ObjectTemplate("AVXTEST.def", bytes([1, 2, 3, 4, 5, 6]),
                           bytes([6, 5, 4, 3, 2, 1]), 0xABCD, 0x1234,
                           0xDEADBEEF, 0x01020304, 9, 1, bytes(range(16)))
        sec = u32(1) + e_template(t) + u32(0) + u32(0)
        self.assertEqual(len(e_template(t)), 4 + 11 + 42)
        h = parse_h3m_bytes(map_with(AB, sec), objects=True)
        self.assertEqual(h.templates, [t])
        self.assertEqual(h.objects, [])
        self.assertEqual(h.events, [])

    def test_default_ignores_objects(self):
        temps, objs, events = object_fixture(SOD)
        raw = map_with(SOD, e_objects(SOD, temps, objs, events))
        h = parse_h3m_bytes(raw)
        self.assertFalse(h.objects_parsed)
        self.assertEqual(h.objects, [])
        self.assertEqual(h.templates, [])
        h = parse_h3m(gzip.compress(raw), objects=True)
        self.assertEqual(len(h.objects), len(objs))

    def test_trailing_bytes_counted(self):
        temps, objs, events = object_fixture(SOD)
        sec = e_objects(SOD, temps, objs, events, trailer=bytes(124))
        h = parse_h3m_bytes(map_with(SOD, sec), objects=True)
        self.assertEqual(h.trailing_bytes, 124)

    def test_truncation_everywhere(self):
        for ver in (ROE, AB, SOD):
            temps, objs, events = object_fixture(ver)
            head = map_with(ver, b"")
            full = head + e_objects(ver, temps, objs, events)
            for cut in range(len(head), len(full)):
                with self.assertRaises(H3mError, msg=f"{ver} {cut}"):
                    parse_h3m_bytes(full[:cut], objects=True)

    def test_truncated_body_names_object(self):
        temps, objs, events = object_fixture(SOD)
        full = map_with(SOD, e_objects(SOD, temps, objs[:2], events))
        h = parse_h3m_bytes(full, objects=True)
        o = h.objects[1]  # hero
        with self.assertRaises(H3mError) as cm:
            parse_h3m_bytes(full[:o.offset + 20], objects=True)
        self.assertIn(f"object 1 at offset {o.offset} (class 34)", str(cm.exception))
        self.assertNotIsInstance(cm.exception, H3mUnsupportedObject)

    def unsupported(self, ver, cls, sub):
        temps = [tmpl("OK", 137, 0), tmpl("BAD", cls, sub)]
        objs = [(0, (0, 0, 0), "generic", {}, b""), (1, (1, 1, 0), "x", {}, b"\xAA" * 64)]
        head = map_with(ver, b"")
        raw = map_with(ver, e_objects(ver, temps, objs, []))
        with self.assertRaises(H3mUnsupportedObject) as cm:
            parse_h3m_bytes(raw, objects=True)
        e = cm.exception
        rec = len(head) + 4 + sum(len(e_template(t)) for t in temps) + 4 + 12
        self.assertEqual((e.index, e.offset, e.body_offset), (1, rec, rec + 12))
        self.assertEqual((e.class_id, e.subid), (cls, sub))
        self.assertIn(f"object 1 at offset {rec}", str(e))
        self.assertIsInstance(e, H3mError)

    def test_new_bodies_roundtrip(self):
        for ver in (ROE, AB, SOD, CHR, WOG):
            ev = SOD if ver >= SOD else ver
            temps, objs, events = new_object_fixture(ev)
            h = parse_h3m_bytes(map_with(ver, e_objects(ev, temps, objs, events)),
                                objects=True)
            self.assertEqual(len(h.objects), len(objs))
            for i, (o, (ti, pos, kind, body, _b)) in enumerate(zip(h.objects, objs)):
                with self.subTest(ver=ver, obj=i, kind=kind):
                    self.assertEqual((o.x, o.y, o.level), pos)
                    self.assertEqual(o.template_index, ti)
                    self.assertEqual(o.kind, kind)
                    self.assertEqual(o.body, body)
            self.assertEqual(h.trailing_bytes, 0)
            kinds = {o.kind for o in h.objects}
            self.assertLessEqual({"sign", "garrison", "grail", "lighthouse", "scholar",
                                  "seer_hut", "shipyard", "shrine", "witch_hut",
                                  "hero_placeholder", "quest_guard"}, kinds)

    def test_new_bodies_quest_and_reward_coverage(self):
        for ver in (ROE, AB, SOD):
            objs = new_object_fixture(ver)[1]
            rewards = {o[3]["reward"]["type"] for o in objs
                       if o[2] == "seer_hut" and o[3]["reward"]}
            self.assertEqual(rewards, set(range(11)), ver)
            quests = {o[3]["quest"]["type"] for o in objs
                      if o[2] == "quest_guard" and o[3]["quest"]}
            self.assertEqual(quests, set(range(1, 10)), ver)
            if ver >= AB:
                seer_q = {o[3]["quest"]["type"] for o in objs
                          if o[2] == "seer_hut" and o[3]["quest"]}
                self.assertEqual(seer_q, set(range(1, 10)), ver)

    def test_new_bodies_truncation_everywhere(self):
        for ver in (ROE, AB, SOD):
            temps, objs, events = new_object_fixture(ver)
            head = map_with(ver, b"")
            full = head + e_objects(ver, temps, objs, events)
            parse_h3m_bytes(full, objects=True)
            for cut in range(len(head), len(full)):
                with self.assertRaises(H3mError, msg=f"{ver} {cut}"):
                    parse_h3m_bytes(full[:cut], objects=True)

    def test_new_bodies_truncation_per_body(self):
        # Each new body alone, cut at every byte inside it: the error names the
        # object (not an unsupported-object error).
        for ver in (ROE, AB, SOD):
            temps, objs, _ = new_object_fixture(ver)
            for ti, pos, kind, body, b in objs:
                if not b:
                    continue
                sec = e_objects(ver, temps, [(ti, pos, kind, body, b)], [])
                raw = map_with(ver, sec)
                body_end = len(raw) - 4  # before the global event count
                for cut in range(body_end - len(b), body_end):
                    with self.assertRaises(H3mError, msg=f"{ver} {kind} {cut}") as cm:
                        parse_h3m_bytes(raw[:cut], objects=True)
                    self.assertNotIsInstance(cm.exception, H3mUnsupportedObject)
                    self.assertIn(f"(class {temps[ti].class_id})", str(cm.exception))

    def one(self, ver, cls, body, sub=0):
        sec = u32(1) + e_template(tmpl("X", cls, sub)) + u32(1) + bytes(3) + u32(0) \
            + bytes(5) + body
        return parse_h3m_bytes(map_with(ver, sec) + bytes(64), objects=True)

    def test_quest_count_bombs(self):
        bomb = "implausible|needs at least"
        for ver in (ROE, AB, SOD):
            for typ in (5, 6):
                for cls in (215, 83):
                    if cls == 83 and ver == ROE:
                        continue
                    body = u8(typ) + u8(0xFF)  # 255 items, none present
                    with self.assertRaisesRegex(H3mError, bomb, msg=f"{ver} {typ}"):
                        sec = u32(1) + e_template(tmpl("X", cls, 0)) + u32(1) \
                            + bytes(3) + u32(0) + bytes(5) + body + bytes(8)
                        parse_h3m_bytes(map_with(ver, sec), objects=True)

    def test_quest_and_reward_type_errors(self):
        for ver in (AB, SOD):
            for bad in (11, 0x80, 0xFF):
                with self.assertRaisesRegex(H3mError, "invalid quest type"):
                    self.one(ver, 215, u8(bad))
            with self.assertRaisesRegex(H3mError, "HotA-only"):
                self.one(ver, 215, u8(10) + bytes(16))
            q = full_quest(0, QUEST_SAMPLES[0])
            for bad in (11, 0xFF):
                with self.assertRaisesRegex(H3mError, "invalid seer hut reward type"):
                    self.one(ver, 83, e_quest(ver, q) + u8(bad))
        with self.assertRaisesRegex(H3mError, "invalid seer hut reward type"):
            self.one(ROE, 83, u8(3) + u8(11))
        e = None
        try:
            self.one(SOD, 215, u8(11))
        except H3mError as ex:
            e = ex
        self.assertIn("object 0 at offset", str(e))
        self.assertNotIsInstance(e, H3mUnsupportedObject)

    def test_border_objects_have_no_body(self):
        for ver in (ROE, AB, SOD):
            for cls, sub in ((9, 0), (10, 7), (212, 0), (212, 999)):
                h = self.one(ver, cls, b"", sub)
                self.assertEqual((h.objects[0].kind, h.objects[0].body), ("generic", {}))
                self.assertEqual(h.trailing_bytes, 60)  # 4 of the 64 are the event count

    def test_unknown_class_fails_with_offset(self):
        for ver in (ROE, AB, SOD):
            self.unsupported(ver, 250, 0)
            self.unsupported(ver, 0xFFFFFFFF, 3)
            self.unsupported(ver, 145, 0)  # HotA-only class id

    def test_hota_subids_still_unsupported(self):
        for ver in (ROE, AB, SOD):
            self.unsupported(ver, 212, 1000)  # HotA quest gate on the border-gate class
            self.unsupported(ver, 212, 1001)  # HotA grave
            self.unsupported(ver, 36, 1000)  # HotA battle location on the grail class

    def test_generic_classes_have_no_body(self):
        for cls in (2, 16, 24, 63, 101, 104, 109, 212, 221, 231):
            temps = [tmpl("G", cls, 0)]
            objs = [(0, (0, 0, 0), "generic", {}, b"")] * 3
            h = parse_h3m_bytes(map_with(SOD, e_objects(SOD, temps, objs, [])),
                                objects=True)
            self.assertEqual([o.kind for o in h.objects], ["generic"] * 3, cls)

    def test_bad_template_index(self):
        temps = [tmpl("G", 137, 0)]
        raw = map_with(SOD, e_objects(SOD, temps, [(1, (0, 0, 0), "", {}, b"")], []))
        with self.assertRaisesRegex(H3mError, "template index 1"):
            parse_h3m_bytes(raw, objects=True)

    def test_count_bombs(self):
        head = map_with(SOD, b"")
        big = u32(1 << 30)
        t = e_template(tmpl("G", 137, 0))
        cases = [
            big,  # templates
            u32(1000) + t,  # within cap, more than the data holds
            u32(1) + t + big,  # objects
            u32(1) + t + u32(5000) + bytes(30),
            u32(1) + t + u32(0) + big,  # global events
        ]
        bomb = "implausible|needs at least"
        for i, sec in enumerate(cases):
            with self.assertRaisesRegex(H3mError, bomb, msg=str(i)):
                parse_h3m_bytes(head + sec + bytes(64), objects=True)
        # nested counts: town events, hero skills, hero backpack
        town = dict(object_fixture(SOD)[1][0][3], events=[])
        tb = e_town(SOD, town)
        cut = tb.index(u32(0) + u8(0xFF) + bytes(3))
        bad_town = tb[:cut] + big + bytes(64)
        hero = object_fixture(SOD)[1][1][3]
        hb = e_hero(SOD, hero)
        skill = hb.replace(b"\x01" + u32(2) + bytes([1, 3, 2, 1]), b"\x01" + u32(99), 1)
        pack = hb.replace(u16(2) + u16(8) + u16(9), u16(0xFFFF), 1)
        self.assertNotEqual(skill, hb)
        self.assertNotEqual(pack, hb)
        for cls, body in ((98, bad_town), (34, skill), (34, pack)):
            raw = head + u32(1) + e_template(tmpl("X", cls, 0)) + u32(1) + bytes(3) \
                + u32(0) + bytes(5) + body
            with self.assertRaisesRegex(H3mError, bomb, msg=str(cls)):
                parse_h3m_bytes(raw, objects=True)


MAPS_DIR = os.environ.get("H3_DATA_DIR")


@unittest.skipUnless(MAPS_DIR, "H3_DATA_DIR not set; real-game-file tests are optional")
class RealMapObjectTests(unittest.TestCase):
    """Invariants only; messages carry indices, never map content."""

    MAX_FILES = 50
    MAX_BYTES = 16 * 1024 * 1024

    def test_objects_section(self):
        maps = []
        for d, _dirs, names in os.walk(MAPS_DIR):
            maps += [Path(d) / n for n in names if n.lower().endswith(".h3m")]
        maps = sorted(set(maps))[:self.MAX_FILES]
        if not maps:
            self.skipTest("no *.h3m files under H3_DATA_DIR")
        for k, path in enumerate(maps):
            with self.subTest(map_index=k):
                if path.stat().st_size > self.MAX_BYTES:
                    continue
                data = path.read_bytes()
                try:
                    h = parse_h3m(data, objects=True)
                except H3mUnsupportedObject as e:
                    # Allowed outcome: a body this parser does not implement.
                    self.assertGreaterEqual(e.index, 0)
                    self.assertGreater(e.body_offset, e.offset)
                    continue
                except H3mError as e:
                    if "unsupported map format" in str(e):
                        continue
                    self.fail(f"map {k}: object parse failed: H3mError")
                self.assertTrue(h.objects_parsed)
                self.assertGreaterEqual(h.trailing_bytes, 0)
                for i, o in enumerate(h.objects):
                    self.assertEqual(o.index, i)
                    self.assertLess(o.template_index, len(h.templates), f"map {k} obj {i}")
                    self.assertLess(o.x, h.size + 8, f"map {k} obj {i}")
                    self.assertLess(o.y, h.size + 8, f"map {k} obj {i}")
                    self.assertLess(o.level, h.levels, f"map {k} obj {i}")
                for t in h.templates:
                    self.assertEqual((len(t.passable), len(t.active)), (6, 6))


if __name__ == "__main__":
    unittest.main()
