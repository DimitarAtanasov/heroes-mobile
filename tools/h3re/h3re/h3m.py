"""Clean-room parser for HoMM3 .H3M map headers (stdlib only).

Parses: format version, size, name, description, difficulty, player slots,
victory/loss conditions, teams, then (per version) allowed heroes,
placeholder heroes, disposed heroes, allowed artifacts/spells/skills, rumors
and predefined hero data, then terrain tiles.  With ``objects=True`` it also
parses the object-template table, the object instances (bodies for a
supported subset of classes) and the global events.  See docs/specs/h3m.md.
Malformed data raises H3mError; an object class whose body is not supported
raises H3mUnsupportedObject (a subclass) carrying the object index and offset.
"""
from __future__ import annotations

import gzip
import struct
import zlib
from dataclasses import dataclass, field
from typing import NamedTuple

__all__ = ["H3mError", "H3mUnsupportedObject", "H3mHeader", "Tile", "PlayerInfo",
           "ObjectTemplate", "MapObject", "parse_h3m", "parse_h3m_bytes",
           "ROE", "AB", "SOD", "CHR", "WOG", "HOTA"]

ROE, AB, SOD, CHR, WOG, HOTA = 0x0E, 0x15, 0x1C, 0x1D, 0x33, 0x20
# CHR (Chronicles) and WoG share the SoD layout; all comparisons use `>= SOD`
# or `!= ROE`, and HOTA (0x20) is deliberately absent from this table.
VERSION_NAMES = {ROE: "RoE", AB: "AB", SOD: "SoD", CHR: "Chronicles", WOG: "WoG"}
MAX_DECOMPRESSED = 64 * 1024 * 1024
MAX_STRING = 1 << 20
NO_CONDITION = 0xFF


TILE_BYTES = 7


class Tile(NamedTuple):
    terrain: int
    view: int
    river_type: int
    river_dir: int
    road_type: int
    road_dir: int
    flags: int


class H3mError(ValueError):
    """Raised when an .H3M file is malformed or unsupported."""


class H3mUnsupportedObject(H3mError):
    """An object instance whose class body this parser does not implement.

    Raised instead of skipping or guessing a length; ``index`` is the object
    instance index, ``offset`` the byte offset of its record, ``body_offset``
    where its body would start, ``class_id``/``subid`` from its template."""

    def __init__(self, index: int, offset: int, body_offset: int,
                 class_id: int, subid: int):
        super().__init__(
            f"object {index} at offset {offset} (body at {body_offset}): "
            f"unsupported object class {class_id} subid {subid}")
        self.index = index
        self.offset = offset
        self.body_offset = body_offset
        self.class_id = class_id
        self.subid = subid


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

    def i8(self, what="i8") -> int:
        return struct.unpack_from("<b", self.data, self._take(1, what))[0]

    def i32(self, what="i32") -> int:
        return struct.unpack_from("<i", self.data, self._take(4, what))[0]

    def flag(self, what="flag") -> bool:
        # Presence flags are decided by the low bit (VCMI behaviour; see spec).
        return bool(self.u8(what) & 1)

    def raw(self, n: int, what: str) -> bytes:
        p = self._take(n, what)
        return bytes(self.data[p:p + n])

    def count(self, what: str, cap: int, min_each: int, width: int = 4) -> int:
        """Read a count and bound it by `cap` and by the bytes that remain."""
        n = self.u32(what) if width == 4 else (self.u16(what) if width == 2
                                              else self.u8(what))
        if n > cap:
            raise H3mError(f"implausible {what} {n} at offset {self.pos - width}")
        if n * min_each > len(self.data) - self.pos:
            raise H3mError(f"truncated data: {what} {n} needs at least "
                           f"{n * min_each} bytes at offset {self.pos}, "
                           f"{len(self.data) - self.pos} remain")
        return n


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
    allowed_heroes_mask: bytes = b""  # raw bitmask (16 bytes RoE, 20 AB+)
    allowed_heroes: list = field(default_factory=list)  # hero ids, bit set = allowed
    placeholder_heroes: list = field(default_factory=list)  # AB+ hero ids
    disposed_heroes: list = field(default_factory=list)  # SoD: dicts
    allowed_artifacts_mask: bytes | None = None  # AB+ raw (17 AB, 18 SoD)
    banned_artifacts: list | None = None  # AB+: ids whose bit is set
    allowed_spells_mask: bytes | None = None  # SoD raw, 9 bytes
    banned_spells: list | None = None
    allowed_skills_mask: bytes | None = None  # SoD raw, 4 bytes
    banned_skills: list | None = None
    rumors: list = field(default_factory=list)  # (name, text)
    predefined_heroes: dict = field(default_factory=dict)  # SoD: hero id -> dict
    levels: int = 1  # 1 + underground level
    tiles_raw: bytes = b""  # levels * size * size * 7 bytes, level-major, row-major
    # Filled only by parse_h3m*(..., objects=True); see docs/specs/h3m.md.
    objects_parsed: bool = False
    templates: list = field(default_factory=list)  # ObjectTemplate
    objects: list = field(default_factory=list)  # MapObject
    events: list = field(default_factory=list)  # global timed events (dicts)
    trailing_bytes: int = 0  # bytes after the events block (not interpreted)

    def tile(self, x: int, y: int, level: int = 0) -> Tile:
        """Tile at (x, y) on `level`; IndexError when out of bounds."""
        if not (0 <= x < self.size and 0 <= y < self.size
                and 0 <= level < self.levels):
            raise IndexError(f"tile ({x}, {y}, {level}) out of bounds")
        o = ((level * self.size + y) * self.size + x) * TILE_BYTES
        return Tile(*self.tiles_raw[o:o + TILE_BYTES])

    @property
    def tiles(self):
        """Lazy iterator of Tile over all tiles (level, then row, then column)."""
        raw = self.tiles_raw
        return (Tile(*raw[o:o + TILE_BYTES])
                for o in range(0, len(raw), TILE_BYTES))


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
        v["pos"] = r.pos3()
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


MAX_RUMORS = 4096
HERO_COUNT = {ROE: 128}  # AB and later: 156
HERO_BYTES = {ROE: 16}
ARTIFACT_BYTES = {AB: 17}  # SoD and later: 18
ARTIFACT_COUNT = {AB: 129}  # SoD and later: 144 (mask is 18 bytes, all bits meaningful)
SPELL_BYTES, SPELL_COUNT = 9, 70
SKILL_BYTES, SKILL_COUNT = 4, 28
PREDEFINED_HEROES = 156
ARTIFACT_SLOTS = 19  # 16 worn + catapult + spellbook + misc5
NO_ARTIFACT = 0xFFFF


def _bits(raw: bytes, limit: int, value: bool) -> list:
    return [i for i in range(min(limit, len(raw) * 8))
            if bool(raw[i >> 3] >> (i & 7) & 1) == value]


def _read_mask(r: _Reader, n: int, what: str) -> bytes:
    p = r._take(n, what)
    return bytes(r.data[p:p + n])


def _read_extra(r: _Reader, h: H3mHeader, ver: int) -> None:
    sodplus = ver >= SOD
    hb = HERO_BYTES.get(ver, 20)
    h.allowed_heroes_mask = _read_mask(r, hb, "allowed heroes")
    h.allowed_heroes = _bits(h.allowed_heroes_mask, HERO_COUNT.get(ver, 156), True)
    if ver != ROE:
        n = r.u32("placeholder hero count")
        if n > 256:
            raise H3mError(f"implausible placeholder hero count {n}")
        h.placeholder_heroes = [r.u8("placeholder hero id") for _ in range(n)]
    if sodplus:
        n = r.u8("disposed hero count")
        for _ in range(n):
            h.disposed_heroes.append({
                "id": r.u8("disposed hero id"),
                "portrait": r.u8("disposed hero portrait"),
                "name": r.string("disposed hero name"),
                "players": r.u8("disposed hero players"),
            })
    r.skip(31, "reserved block")
    if ver != ROE:
        m = _read_mask(r, ARTIFACT_BYTES.get(ver, 18), "allowed artifacts")
        h.allowed_artifacts_mask = m
        h.banned_artifacts = _bits(m, ARTIFACT_COUNT.get(ver, 144), True)
    if sodplus:
        m = _read_mask(r, SPELL_BYTES, "allowed spells")
        h.allowed_spells_mask = m
        h.banned_spells = _bits(m, SPELL_COUNT, True)
        m = _read_mask(r, SKILL_BYTES, "allowed skills")
        h.allowed_skills_mask = m
        h.banned_skills = _bits(m, SKILL_COUNT, True)
    n = r.u32("rumor count")
    if n > MAX_RUMORS:
        raise H3mError(f"implausible rumor count {n}")
    for _ in range(n):
        h.rumors.append((r.string("rumor name"), r.string("rumor text")))
    if sodplus:
        for hid in range(PREDEFINED_HEROES):
            d = _read_predefined(r)
            if d is not None:
                h.predefined_heroes[hid] = d


def _read_predefined(r: _Reader):
    if not r.u8("predefined hero flag"):
        return None
    d: dict = {}
    if r.u8("has experience"):
        d["experience"] = r.u32("experience")
    if r.u8("has secondary skills"):
        n = r.u32("secondary skill count")
        if n > 28:
            raise H3mError(f"implausible secondary skill count {n}")
        d["secondary_skills"] = [(r.u8("skill"), r.u8("skill level")) for _ in range(n)]
    if r.u8("has artifacts"):
        slots = [r.u16("artifact") for _ in range(ARTIFACT_SLOTS)]
        d["artifacts"] = [None if a == NO_ARTIFACT else a for a in slots]
        n = r.u16("backpack count")
        d["backpack"] = [r.u16("backpack artifact") for _ in range(n)]
    if r.u8("has biography"):
        d["biography"] = r.string("biography")
    g = r.u8("gender")
    if g != 0xFF:
        d["gender"] = g
    if r.u8("has spells"):
        d["spells_mask"] = _read_mask(r, SPELL_BYTES, "hero spells")
    if r.u8("has primary skills"):
        d["primary_skills"] = tuple(r.u8("primary skill") for _ in range(4))
    return d


def _read_tiles(r: _Reader, h: H3mHeader) -> None:
    h.levels = 2 if h.two_levels else 1
    # size <= 1024 bounds this at 14 MiB; _take checks the data really is
    # there before anything is copied, so a lying header cannot over-allocate.
    n = h.size * h.size * h.levels * TILE_BYTES
    p = r._take(n, "terrain tiles")
    h.tiles_raw = bytes(r.data[p:p + n])


# ---------------------------------------------------------------- objects
MAX_TEMPLATES = 1 << 16
MAX_OBJECTS = 1 << 18
MAX_EVENTS = 1 << 13
MAX_TOWN_EVENTS = 1 << 10
MAX_SKILLS = 28
TEMPLATE_MIN = 4 + 6 + 6 + 2 + 2 + 4 + 4 + 1 + 1 + 16  # empty def name
OBJECT_HEAD = 3 + 4 + 5  # position, template index, 5 reserved bytes
RESOURCES = 7  # i32 each, every version
PRIMARY = 4
ARMY_SLOTS = 7
BUILDING_BYTES = 6
RESOURCE_MASK_BYTES = 4
NONE8, NONE16 = 0xFF, 0xFFFF


class ObjectTemplate(NamedTuple):
    """One entry of the object-template ("def") table; masks kept raw."""
    def_name: str
    passable: bytes  # 6 bytes, one per row; clear bit = blocked tile
    active: bytes  # 6 bytes, one per row; set bit = visitable tile
    terrain_mask_first: int  # u16 not used by VCMI (see spec)
    allowed_terrains: int  # u16 bitmask, bit i = terrain id i
    class_id: int  # u32
    subid: int  # u32
    type: int  # u8 object group (2 creature, 3 hero, 4 artifact, 5 resource)
    draw_order: int  # u8 draw-priority flag
    reserved: bytes  # 16 trailing bytes, kept raw


@dataclass
class MapObject:
    index: int
    offset: int  # byte offset of this object's record in the decompressed data
    x: int
    y: int
    level: int
    template_index: int
    class_id: int
    subid: int
    kind: str  # body family, e.g. "town", "hero", "generic"
    body: dict = field(default_factory=dict)


def _wide(ver: int) -> bool:
    return ver != ROE


def _art(r: _Reader, ver: int, what="artifact"):
    a = r.u16(what) if _wide(ver) else r.u8(what)
    return None if a == (NONE16 if _wide(ver) else NONE8) else a


def _creature(r: _Reader, ver: int, what="creature"):
    c = r.u16(what) if _wide(ver) else r.u8(what)
    return None if c == (NONE16 if _wide(ver) else NONE8) else c


def _opt8(v: int):
    return None if v == NONE8 else v


def _army(r: _Reader, ver: int) -> list:
    return [(_creature(r, ver, "army creature"), r.u16("army count"))
            for _ in range(ARMY_SLOTS)]


def _resources(r: _Reader) -> tuple:
    return tuple(r.i32("resource amount") for _ in range(RESOURCES))


def _msg_guards(r: _Reader, ver: int) -> dict:
    d = {"message": None, "guards": None}
    if r.flag("has message"):
        d["message"] = r.string("message")
        if r.flag("has guards"):
            d["guards"] = _army(r, ver)
        r.skip(4, "message reserved")
    return d


def _box(r: _Reader, ver: int) -> dict:
    """Shared body of events and Pandora's boxes."""
    d = _msg_guards(r, ver)
    d["experience"] = r.u32("box experience")
    d["mana"] = r.i32("box mana")
    d["morale"] = r.i8("box morale")
    d["luck"] = r.i8("box luck")
    d["resources"] = _resources(r)
    d["primary_skills"] = tuple(r.u8("box primary") for _ in range(PRIMARY))
    n = r.u8("box skill count")
    d["secondary_skills"] = [(r.u8("box skill"), r.u8("box skill level"))
                             for _ in range(n)]
    n = r.u8("box artifact count")
    d["artifacts"] = [_art(r, ver, "box artifact") for _ in range(n)]
    n = r.u8("box spell count")
    d["spells"] = [r.u8("box spell") for _ in range(n)]
    n = r.u8("box creature count")
    d["creatures"] = [(_creature(r, ver, "box creature"), r.u16("box creature count"))
                      for _ in range(n)]
    r.skip(8, "box reserved")
    return d


def _body_event(r, ver, t):
    d = _box(r, ver)
    d["players_mask"] = r.u8("event players")
    d["computer_activate"] = r.flag("event computer activate")
    d["remove_after_visit"] = r.flag("event remove after visit")
    r.skip(4, "event reserved")
    return d


def _body_pandora(r, ver, t):
    return _box(r, ver)


def _hero_artifacts(r: _Reader, ver: int):
    if not r.flag("hero has artifacts"):
        return None
    slots = [_art(r, ver, "hero artifact")
             for _ in range(ARTIFACT_SLOTS if ver >= SOD else ARTIFACT_SLOTS - 1)]
    n = r.count("hero backpack count", NONE16, 2 if _wide(ver) else 1, width=2)
    return {"slots": slots,
            "backpack": [_art(r, ver, "hero backpack artifact") for _ in range(n)]}


def _body_hero(r, ver, t):
    d = {"identifier": r.u32("hero identifier") if ver >= AB else None}
    d["owner"] = _opt8(r.u8("hero owner"))
    d["hero_type"] = _opt8(r.u8("hero type"))
    d["name"] = r.string("hero name") if r.flag("hero has name") else None
    if ver >= SOD:
        d["experience"] = r.u32("hero experience") if r.flag("hero has exp") else None
    else:
        d["experience"] = r.u32("hero experience")  # 0 = not set (RoE/AB)
    d["portrait"] = r.u8("hero portrait") if r.flag("hero has portrait") else None
    d["secondary_skills"] = None
    if r.flag("hero has skills"):
        n = r.count("hero skill count", MAX_SKILLS, 2)
        d["secondary_skills"] = [(r.u8("hero skill"), r.u8("hero skill level"))
                                 for _ in range(n)]
    d["army"] = _army(r, ver) if r.flag("hero has army") else None
    d["formation"] = r.u8("hero formation")
    d["artifacts"] = _hero_artifacts(r, ver)
    d["patrol_radius"] = _opt8(r.u8("hero patrol"))
    d["biography"] = d["gender"] = None
    if ver >= AB:
        d["biography"] = r.string("hero biography") if r.flag("hero has bio") else None
        d["gender"] = _opt8(r.u8("hero gender"))
    d["spells_mask"] = d["spell"] = None
    if ver >= SOD:
        if r.flag("hero has spells"):
            d["spells_mask"] = r.raw(SPELL_BYTES, "hero spells")
    elif ver >= AB:
        d["spell"] = r.u8("hero spell")  # 0xFF none, 0xFE preset (raw)
    d["primary_skills"] = None
    if ver >= SOD and r.flag("hero has primary"):
        d["primary_skills"] = tuple(r.u8("hero primary") for _ in range(PRIMARY))
    r.skip(16, "hero reserved")
    return d


def _body_monster(r, ver, t):
    d = {"identifier": r.u32("monster identifier") if ver >= AB else None}
    d["count"] = r.u16("monster count")
    d["character"] = r.u8("monster character")
    d["message"] = d["resources"] = d["artifact"] = None
    if r.flag("monster has message"):
        d["message"] = r.string("monster message")
        d["resources"] = _resources(r)
        d["artifact"] = _art(r, ver, "monster artifact")
    d["never_flees"] = r.flag("monster never flees")
    d["not_growing"] = r.flag("monster not growing")
    r.skip(2, "monster reserved")
    return d


def _body_artifact(r, ver, t):
    return _msg_guards(r, ver)


def _body_scroll(r, ver, t):
    d = _msg_guards(r, ver)
    d["spell"] = r.u32("scroll spell")
    return d


def _body_resource(r, ver, t):
    d = _msg_guards(r, ver)
    d["amount"] = r.u32("resource amount")  # raw; not scaled
    r.skip(4, "resource reserved")
    return d


def _body_owned(r, ver, t):
    return {"owner": r.u32("owner")}  # 0xFF = neutral (raw)


def _body_abandoned_mine(r, ver, t):
    m = r.raw(RESOURCE_MASK_BYTES, "abandoned mine resources")
    return {"resources_mask": m, "resources": _bits(m, RESOURCES, True)}


def _body_random_dwelling(r, ver, t):
    d = {"owner": r.u32("dwelling owner"), "faction_identifier": None,
         "factions_mask": None, "min_level": None, "max_level": None}
    if t.class_id in (216, 217):
        d["faction_identifier"] = r.u32("dwelling faction town")
        if d["faction_identifier"] == 0:
            d["factions_mask"] = (r.u8("dwelling factions") if ver == ROE
                                  else r.u16("dwelling factions"))
    if t.class_id in (216, 218):
        d["min_level"] = r.u8("dwelling min level")
        d["max_level"] = r.u8("dwelling max level")
    return d


def _event_common(r: _Reader, ver: int) -> dict:
    d = {"name": r.string("event name"), "message": r.string("event message"),
         "resources": _resources(r), "players_mask": r.u8("event players")}
    d["human_affected"] = r.flag("event human") if ver >= SOD else True
    d["computer_affected"] = r.flag("event computer")
    d["first_day"] = r.u16("event first day")
    d["repeat_days"] = r.u16("event repeat")
    r.skip(16, "event reserved")
    return d


EVENT_MIN = {ROE: 58, AB: 58}  # SoD+: 59 (human-affected byte)


def _body_town(r, ver, t):
    d = {"identifier": r.u32("town identifier") if ver >= AB else None}
    d["owner"] = _opt8(r.u8("town owner"))
    d["name"] = r.string("town name") if r.flag("town has name") else None
    d["army"] = _army(r, ver) if r.flag("town has army") else None
    d["formation"] = r.u8("town formation")
    d["built_mask"] = d["forbidden_mask"] = d["has_fort"] = None
    if r.flag("town custom buildings"):
        d["built_mask"] = r.raw(BUILDING_BYTES, "town built")
        d["forbidden_mask"] = r.raw(BUILDING_BYTES, "town forbidden")
    else:
        d["has_fort"] = r.flag("town has fort")
    d["obligatory_spells_mask"] = (r.raw(SPELL_BYTES, "town obligatory spells")
                                   if ver >= AB else None)
    d["banned_spells_mask"] = r.raw(SPELL_BYTES, "town possible spells")
    n = r.count("town event count", MAX_TOWN_EVENTS,
                EVENT_MIN.get(ver, 59) + BUILDING_BYTES + 2 * ARMY_SLOTS + 4)
    evs = []
    for _ in range(n):
        e = _event_common(r, ver)
        e["buildings_mask"] = r.raw(BUILDING_BYTES, "town event buildings")
        e["creatures"] = tuple(r.u16("town event creatures") for _ in range(ARMY_SLOTS))
        r.skip(4, "town event reserved")
        evs.append(e)
    d["events"] = evs
    d["alignment"] = r.u8("town alignment") if ver >= SOD else None
    r.skip(3, "town reserved")
    return d


def _body_generic(r, ver, t):
    return {}


_HERO = (34, 62, 70)
_MONSTER = (54, 71, 72, 73, 74, 75, 162, 163, 164)
_ARTIFACT = (5, 65, 66, 67, 68, 69)
_DWELLING = (17, 18, 19, 20)
# Classes with a body in RoE/AB/SoD that this parser does not implement:
# garrison 33/219, grail 36, lighthouse 42, bottle 59, scholar 81, seer hut 83,
# shipyard 87, shrines 88-90, sign 91, witch hut 113, hero placeholder 214,
# quest guard 215.  Everything else in _GENERIC has no body before HotA.
_GENERIC = frozenset(
    set(range(2, 40)) | set(range(41, 139)) | {143} | set(range(147, 162))
    | set(range(212, 232))
) - frozenset((5, 6, 17, 18, 19, 20, 26, 33, 34, 36, 42, 53, 54, 59, 62)
              + tuple(range(65, 80)) + (81, 83, 87, 88, 89, 90, 91, 93, 98, 113)
              + tuple(range(214, 221)))


def _classify(t: ObjectTemplate):
    """(kind, reader) for a template, or None when unsupported/unknown."""
    c, sub = t.class_id, t.subid
    if c == 26:
        return "event", _body_event
    if c == 6:
        return "pandora", _body_pandora
    if c in _HERO:
        return "hero", _body_hero
    if c in _MONSTER:
        return "monster", _body_monster
    if c in _ARTIFACT:
        return "artifact", _body_artifact
    if c == 93:
        return "spell_scroll", _body_scroll
    if c in (76, 79):
        return "resource", _body_resource
    if c in (77, 98):
        return "town", _body_town
    if c == 53:
        return ("mine", _body_owned) if sub < 7 else ("abandoned_mine", _body_abandoned_mine)
    if c == 220:
        return "abandoned_mine", _body_abandoned_mine
    if c in _DWELLING:
        return "dwelling", _body_owned
    if c in (216, 217, 218):
        return "random_dwelling", _body_random_dwelling
    if c == 212 and sub >= 1000:  # HotA quest gate / grave share this class
        return None
    if c in _GENERIC:
        return "generic", _body_generic
    return None


def _read_template(r: _Reader) -> ObjectTemplate:
    return ObjectTemplate(
        r.string("template def name"), r.raw(6, "template passable mask"),
        r.raw(6, "template active mask"), r.u16("template terrain mask"),
        r.u16("template allowed terrains"), r.u32("template class"),
        r.u32("template subid"), r.u8("template type"),
        r.u8("template draw order"), r.raw(16, "template reserved"))


def _read_objects(r: _Reader, h: H3mHeader, ver: int) -> None:
    n = r.count("object template count", MAX_TEMPLATES, TEMPLATE_MIN)
    h.templates = [_read_template(r) for _ in range(n)]
    n = r.count("object count", MAX_OBJECTS, OBJECT_HEAD)
    objs = []
    for i in range(n):
        off = r.pos
        x, y, z = r.pos3("object position")
        ti = r.u32("object template index")
        if ti >= len(h.templates):
            raise H3mError(f"object {i} at offset {off}: template index {ti} "
                           f"out of range ({len(h.templates)} templates)")
        r.skip(5, "object reserved")
        t = h.templates[ti]
        kr = _classify(t)
        if kr is None:
            raise H3mUnsupportedObject(i, off, r.pos, t.class_id, t.subid)
        try:
            body = kr[1](r, ver, t)
        except H3mUnsupportedObject:
            raise
        except H3mError as e:
            raise H3mError(f"object {i} at offset {off} (class {t.class_id}): {e}") from e
        objs.append(MapObject(i, off, x, y, z, ti, t.class_id, t.subid, kr[0], body))
    h.objects = objs
    n = r.count("global event count", MAX_EVENTS, EVENT_MIN.get(ver, 59))
    h.events = [_event_common(r, ver) for _ in range(n)]
    h.trailing_bytes = len(r.data) - r.pos
    h.objects_parsed = True


def parse_h3m_bytes(raw: bytes, *, objects: bool = False) -> H3mHeader:
    """Parse an .H3M given its *decompressed* contents.

    By default parsing stops after the terrain tiles (later bytes are ignored).
    With ``objects=True`` the templates, object instances and global events
    are parsed too and exposed on the result (``objects_parsed`` is True).
    """
    r = _Reader(raw)
    fmt = r.u32("format")
    if fmt == HOTA:
        raise H3mError("unsupported map format 0x20 (HotA): it uses an "
                       "extended header this parser does not implement")
    if fmt not in VERSION_NAMES:
        raise H3mError(f"unsupported map format 0x{fmt:X}")
    has_hero = bool(r.u8("has hero"))
    size = r.u32("map size")
    # Deliberately permissive sanity bound (see docs/specs/h3m.md).
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
    h = H3mHeader(fmt, VERSION_NAMES[fmt], has_hero, size, two, name, desc,
                  diff, mhl, players, victory, loss, teams)
    _read_extra(r, h, fmt)
    _read_tiles(r, h)
    if objects:
        _read_objects(r, h, fmt)
    return h


def parse_h3m(data: bytes, *, objects: bool = False) -> H3mHeader:
    """Parse an .H3M file (gzip-wrapped; uncompressed data is also accepted).

    ``objects`` is passed to parse_h3m_bytes."""
    data = bytes(data)
    if data[:2] == b"\x1f\x8b":
        try:
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            raw = d.decompress(data, MAX_DECOMPRESSED)
            if d.unconsumed_tail:
                raise H3mError("decompressed map exceeds size limit")
            if not d.eof:
                raise H3mError("truncated gzip stream")
            if d.unused_data:
                # Real maps are a single gzip member; trailing bytes or
                # additional members are rejected rather than ignored.
                raise H3mError(
                    f"{len(d.unused_data)} bytes of trailing data after "
                    "gzip stream (multi-member gzip not supported)")
        except (zlib.error, EOFError, gzip.BadGzipFile) as e:
            raise H3mError(f"bad gzip stream: {e}") from e
    else:
        raw = data
    return parse_h3m_bytes(raw, objects=objects)
