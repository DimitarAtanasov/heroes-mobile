import gzip
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from h3re.h3m import H3mError, parse_h3m, parse_h3m_bytes, ROE, AB, SOD


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


def build(ver, victory=b"\xff", loss=b"\xff", teams=b"\x00", inactive_from=2):
    b = struct.pack("<I", ver) + b"\x01" + struct.pack("<I", 36) + b"\x00"
    b += s("Test Map") + s("A description") + b"\x02"
    if ver != ROE:
        b += b"\x00"
    for i in range(8):
        b += player(ver, active=i < inactive_from, hero=(i == 0))
    return b + victory + loss + teams


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

    def test_uncompressed_accepted(self):
        self.assertEqual(parse_h3m(build(AB)).name, "Test Map")


if __name__ == "__main__":
    unittest.main()
