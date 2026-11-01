import gzip
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from h3re.h3m import H3mError, Tile, parse_h3m, parse_h3m_bytes, ROE, AB, SOD


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


if __name__ == "__main__":
    unittest.main()
