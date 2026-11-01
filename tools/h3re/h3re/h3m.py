"""Clean-room parser for HoMM3 .H3M map headers (stdlib only).

Parses: format version, size, name, description, difficulty, player slots,
victory/loss conditions and teams.  Everything after is not parsed.
See docs/specs/h3m.md.  Malformed data raises H3mError.
"""
from __future__ import annotations

import gzip
import struct
import zlib
from dataclasses import dataclass, field

__all__ = ["H3mError", "H3mHeader", "PlayerInfo", "parse_h3m", "parse_h3m_bytes",
           "ROE", "AB", "SOD", "WOG"]

ROE, AB, SOD, WOG = 0x0E, 0x15, 0x1C, 0x33
VERSION_NAMES = {ROE: "RoE", AB: "AB", SOD: "SoD", WOG: "WoG"}
MAX_DECOMPRESSED = 64 * 1024 * 1024
MAX_STRING = 1 << 20
NO_CONDITION = 0xFF


class H3mError(ValueError):
    """Raised when an .H3M file is malformed or unsupported."""


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _take(self, n: int, what: str) -> int:
        if n < 0 or self.pos + n > len(self.data):
            raise H3mError(f"truncated data reading {what}: need {n} bytes at "
                           f"offset {self.pos}, size {len(self.data)}")
        p = self.pos
        self.pos += n
        return p

    def u8(self, what="u8") -> int:
        return self.data[self._take(1, what)]

    def u16(self, what="u16") -> int:
        return struct.unpack_from("<H", self.data, self._take(2, what))[0]

    def u32(self, what="u32") -> int:
        return struct.unpack_from("<I", self.data, self._take(4, what))[0]

    def skip(self, n: int, what="padding") -> None:
        self._take(n, what)

    def string(self, what="string") -> str:
        n = self.u32(what + " length")
        if n > MAX_STRING:
            raise H3mError(f"{what}: implausible length {n}")
        p = self._take(n, what)
        return self.data[p:p + n].decode("cp1252", errors="replace")

    def pos3(self, what="position"):
        p = self._take(3, what)
        return tuple(self.data[p:p + 3])


@dataclass
class PlayerInfo:
    index: int
    can_human: bool = False
    can_computer: bool = False
    ai_behavior: int = 0
    allowed_factions: int | None = None  # bitmask
    faction_random: bool = False
    has_main_town: bool = False
    generate_hero_at_main_town: bool = False
    main_town_pos: tuple | None = None
    has_random_hero: bool = False
    main_hero_id: int | None = None
    main_hero_portrait: int | None = None
    main_hero_name: str | None = None
    heroes: list = field(default_factory=list)  # (id, name)

    @property
    def active(self) -> bool:
        return self.can_human or self.can_computer


@dataclass
class H3mHeader:
    format: int
    version: str
    has_hero: bool
    size: int
    two_levels: bool
    name: str
    description: str
    difficulty: int
    max_hero_level: int | None
    players: list
    victory: dict | None
    loss: dict | None
    teams: list  # team index per player (empty when no teams)


def _read_victory(r: _Reader, ver: int):
    t = r.u8("victory type")
    if t == NO_CONDITION:
        return None
    v = {"type": t, "allow_normal_victory": bool(r.u8()), "applies_to_ai": bool(r.u8())}
    wide = ver != ROE
    if t == 0:
        v["artifact"] = r.u16() if wide else r.u8()
    elif t == 1:
        v["creature"] = r.u16() if wide else r.u8()
        v["count"] = r.u32()
    elif t == 2:
        v["resource"] = r.u8()
        v["amount"] = r.u32()
    elif t == 3:
        v["pos"] = r.pos3()
        v["hall_level"] = r.u8()
        v["castle_level"] = r.u8()
    elif t in (4, 5, 6, 7):
        v["pos"] = r.pos3()
    elif t in (8, 9):
        pass
    elif t == 10:
        v["artifact"] = r.u8()
    else:
        raise H3mError(f"unknown victory condition type {t}")
    return v


def _read_loss(r: _Reader):
    t = r.u8("loss type")
    if t == NO_CONDITION:
        return None
    l = {"type": t}
    if t in (0, 1):
        l["pos"] = r.pos3()
    elif t == 2:
        l["days"] = r.u16()
    else:
        raise H3mError(f"unknown loss condition type {t}")
    return l


def _read_player(r: _Reader, ver: int, idx: int) -> PlayerInfo:
    p = PlayerInfo(idx)
    p.can_human = bool(r.u8("can_human"))
    p.can_computer = bool(r.u8("can_computer"))
    if not p.active:
        r.skip({ROE: 6, AB: 12}.get(ver, 13), "inactive player data")
        return p
    p.ai_behavior = r.u8("ai behavior")
    if ver >= SOD:
        r.u8("customized towns flag")
    p.allowed_factions = r.u8() if ver == ROE else r.u16()
    p.faction_random = bool(r.u8("random faction"))
    p.has_main_town = bool(r.u8("has main town"))
    if p.has_main_town:
        if ver != ROE:
            p.generate_hero_at_main_town = bool(r.u8())
            r.u8("generate hero")
        p.main_town_pos = r.pos3()
    p.has_random_hero = bool(r.u8("random hero"))
    hid = r.u8("main hero id")
    if hid != 0xFF:
        p.main_hero_id = hid
        p.main_hero_portrait = r.u8("portrait")
        p.main_hero_name = r.string("main hero name")
    if ver != ROE:
        r.u8("hero placeholder")
        n = r.u32("hero count")
        if n > 256:
            raise H3mError(f"implausible hero count {n}")
        for _ in range(n):
            p.heroes.append((r.u8("hero id"), r.string("hero name")))
    return p


def parse_h3m_bytes(raw: bytes) -> H3mHeader:
    """Parse an .H3M given its *decompressed* contents."""
    r = _Reader(raw)
    fmt = r.u32("format")
    if fmt not in VERSION_NAMES:
        raise H3mError(f"unsupported map format 0x{fmt:X}")
    has_hero = bool(r.u8("has hero"))
    size = r.u32("map size")
    if not 1 <= size <= 1024:
        raise H3mError(f"implausible map size {size}")
    two = bool(r.u8("two levels"))
    name = r.string("map name")
    desc = r.string("map description")
    diff = r.u8("difficulty")
    if diff > 4:
        raise H3mError(f"invalid difficulty {diff}")
    mhl = r.u8("max hero level") if fmt != ROE else None
    players = [_read_player(r, fmt, i) for i in range(8)]
    victory = _read_victory(r, fmt)
    loss = _read_loss(r)
    teams = []
    nt = r.u8("team count")
    if nt:
        teams = [r.u8("team") for _ in range(8)]
    return H3mHeader(fmt, VERSION_NAMES[fmt], has_hero, size, two, name, desc,
                     diff, mhl, players, victory, loss, teams)


def parse_h3m(data: bytes) -> H3mHeader:
    """Parse an .H3M file (gzip-wrapped; uncompressed data is also accepted)."""
    data = bytes(data)
    if data[:2] == b"\x1f\x8b":
        try:
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            raw = d.decompress(data, MAX_DECOMPRESSED)
            if d.unconsumed_tail:
                raise H3mError("decompressed map exceeds size limit")
        except (zlib.error, EOFError, gzip.BadGzipFile) as e:
            raise H3mError(f"bad gzip stream: {e}") from e
    else:
        raw = data
    return parse_h3m_bytes(raw)
