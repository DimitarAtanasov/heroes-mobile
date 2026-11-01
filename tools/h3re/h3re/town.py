"""Reference simulation core for towns: buildings, build rules and weekly growth.

Spec: docs/specs/town.md (built on rules.md sections 1, 3 and 4, and
engine-design.md section 1.3). Clean-room: written from those specs only.

Design (same as battle.py / adventure.py):

* State is immutable (frozen dataclasses, tuples, ints, strings, bools). The
  town content (factions and buildings, loaded from a JSON pack such as
  ``data/towns_test.json``) is part of the state, so it is part of the hash.
* ``apply(state, cmd, rng) -> (state', events)`` is the only way to advance a
  town. An illegal command raises ``IllegalCommand`` before anything happens.
  Nothing here is random; ``rng`` (stream ``town:<game_id>``) is accepted for
  interface stability and is never drawn from.
* No floats. The castle growth bonus is an exact Fraction rounded once, in
  ``_round_castle_bonus``, with the mode ``TownPolicy.citadel_rounding`` names.
* Weekly growth is a query (``growth_pools``) that returns adventure
  ``GrowthPool`` values; the adventure core applies them each week.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from fractions import Fraction

from .adventure import RESOURCE_NAMES, GrowthPool, Resources
from .datapack import MAX_INT, SCHEMA_VERSION, DataPackError, _frac, _int, _list, _obj, _read
from .rng import derive_stream

__all__ = [
    "TownPolicy", "DEFAULT_POLICY", "Building", "Faction", "TownContent",
    "TownSetup", "Town", "TownState", "IllegalCommand", "Build", "NewDay",
    "BuildingBuilt", "TownDayStarted",
    "parse_town_pack", "load_town_pack", "content_hash", "find_building",
    "town_rng", "weekly_growth", "missing_requirements", "active_buildings",
    "town_income", "player_income", "dwellings", "growth_pools",
    "create_game", "apply", "canonical", "state_hash",
]

_ROUNDING = ("floor", "ceil", "nearest")


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TownPolicy:
    """Switchable rules for [uncertain] items (docs/specs/town.md section 6)."""

    # rules.md 4 / 9.10: rounding of base * castle bonus (Citadel +1/2 on an
    # odd base). VCMI cross-check (clear): rounded down.
    citadel_rounding: str = "floor"     # "floor" | "ceil" | "nearest" (halves up)

    def __post_init__(self):
        if self.citadel_rounding not in _ROUNDING:
            raise ValueError("bad citadel_rounding %r" % (self.citadel_rounding,))


DEFAULT_POLICY = TownPolicy()


# --------------------------------------------------------------------------
# Content (loaded from a town pack; stored in the state)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Building:
    id: str
    cost: Resources
    requires: tuple                 # sorted building ids of the same faction
    upgrades: str = ""              # building this one replaces ("" = none)
    income: Resources = Resources()  # daily income while active
    fort: bool = False              # counts as a fort for dwellings
    growth_bonus: tuple = (0, 1)    # castle bonus, fraction of base growth
    dwelling_level: int = 0         # 0 = not a dwelling
    creature: str = ""
    base_growth: int = 0
    horde_level: int = 0            # 0 = not a horde (growth) building
    horde_bonus: int = 0
    player_unique: str = ""         # tag: one such building per player


@dataclass(frozen=True)
class Faction:
    id: str
    buildings: tuple                # Building, sorted by id


@dataclass(frozen=True)
class TownContent:
    factions: tuple                 # Faction, sorted by id


def _resources(v, path):
    _obj(v, path, (), RESOURCE_NAMES)
    return Resources(*(_int(v.get(n, 0), "%s.%s" % (path, n), 0, MAX_INT)
                       for n in RESOURCE_NAMES))


def _str(v, path):
    if type(v) is not str or not v.strip():
        raise DataPackError("%s: expected non-empty string" % path)
    return v


_B_REQ = ("id", "cost", "requires")
_B_OPT = ("upgrades", "income", "fort", "growth_bonus", "dwelling", "horde", "player_unique")


def _check_building(b, path):
    _obj(b, path, _B_REQ, _B_OPT)
    kw = {"id": _str(b["id"], path + ".id"), "cost": _resources(b["cost"], path + ".cost")}
    reqs = [_str(r, "%s.requires[%d]" % (path, i))
            for i, r in enumerate(_list(b["requires"], path + ".requires"))]
    if len(set(reqs)) != len(reqs):
        raise DataPackError("%s.requires: duplicate entry" % path)
    kw["requires"] = tuple(sorted(reqs))
    if "upgrades" in b:
        kw["upgrades"] = _str(b["upgrades"], path + ".upgrades")
    if "income" in b:
        kw["income"] = _resources(b["income"], path + ".income")
    if "fort" in b:
        if type(b["fort"]) is not bool:
            raise DataPackError("%s.fort: expected boolean" % path)
        kw["fort"] = b["fort"]
    if "growth_bonus" in b:
        kw["growth_bonus"] = _frac(b["growth_bonus"], path + ".growth_bonus")
    if "dwelling" in b:
        d = _obj(b["dwelling"], path + ".dwelling", ("level", "creature", "base_growth"))
        kw["dwelling_level"] = _int(d["level"], path + ".dwelling.level", 1, 1000)
        kw["creature"] = _str(d["creature"], path + ".dwelling.creature")
        kw["base_growth"] = _int(d["base_growth"], path + ".dwelling.base_growth", 0, MAX_INT)
    if "horde" in b:
        h = _obj(b["horde"], path + ".horde", ("level", "bonus"))
        kw["horde_level"] = _int(h["level"], path + ".horde.level", 1, 1000)
        kw["horde_bonus"] = _int(h["bonus"], path + ".horde.bonus", 0, MAX_INT)
    if "player_unique" in b:
        kw["player_unique"] = _str(b["player_unique"], path + ".player_unique")
    return Building(**kw)


def _closure(bid, by_id):
    """All buildings ``bid`` needs, directly or transitively (graph is acyclic)."""
    out, todo = [], list(by_id[bid].requires)
    while todo:
        r = todo.pop()
        if r not in out:
            out.append(r)
            todo.extend(by_id[r].requires)
    return tuple(sorted(out))


def _check_faction(f, path):
    _obj(f, path, ("id", "buildings"))
    fid = _str(f["id"], path + ".id")
    blds = [_check_building(b, "%s.buildings[%d]" % (path, i))
            for i, b in enumerate(_list(f["buildings"], path + ".buildings"))]
    if not blds:
        raise DataPackError("%s.buildings: must not be empty" % path)
    by_id = {}
    for b in blds:
        if b.id in by_id:
            raise DataPackError("%s: duplicate building %r" % (fid, b.id))
        by_id[b.id] = b
    ids = sorted(by_id)
    upgraded_by = {}
    for bid in ids:
        b = by_id[bid]
        for r in b.requires + ((b.upgrades,) if b.upgrades else ()):
            if r not in by_id:
                raise DataPackError("%s.%s: unknown building %r" % (fid, bid, r))
        if b.upgrades:
            if b.upgrades == bid or b.upgrades not in b.requires:
                raise DataPackError("%s.%s: upgrades %r must also be required"
                                    % (fid, bid, b.upgrades))
            if b.upgrades in upgraded_by:
                raise DataPackError("%s.%s: %r is upgraded by more than one building"
                                    % (fid, bid, b.upgrades))
            upgraded_by[b.upgrades] = bid
    # Acyclic: place buildings whose requirements are all placed, in id order.
    placed = set()
    while len(placed) < len(ids):
        ready = [bid for bid in ids if bid not in placed
                 and all(r in placed for r in by_id[bid].requires)]
        if not ready:
            raise DataPackError("%s: requirement cycle among %s" % (
                fid, ", ".join(bid for bid in ids if bid not in placed)))
        placed.update(ready)
    roots = {}
    for bid in ids:
        b = by_id[bid]
        if b.dwelling_level:
            if not any(by_id[r].fort for r in _closure(bid, by_id)):
                raise DataPackError("%s.%s: a dwelling needs a fort" % (fid, bid))
            up = by_id[b.upgrades] if b.upgrades else None
            if up is not None and up.dwelling_level != b.dwelling_level:
                raise DataPackError("%s.%s: a dwelling upgrades only a dwelling of its level"
                                    % (fid, bid))
            if up is None:
                if b.dwelling_level in roots:
                    raise DataPackError("%s: dwelling level %d has more than one base dwelling"
                                        % (fid, b.dwelling_level))
                roots[b.dwelling_level] = bid
        elif b.upgrades and by_id[b.upgrades].dwelling_level:
            raise DataPackError("%s.%s: only a dwelling may upgrade a dwelling" % (fid, bid))
    for bid in ids:
        lv = by_id[bid].horde_level
        if lv and lv not in roots:
            raise DataPackError("%s.%s: horde level %d has no dwelling" % (fid, bid, lv))
    return Faction(fid, tuple(by_id[bid] for bid in ids))


def parse_town_pack(obj):
    """Validate an already-decoded town pack and return a TownContent."""
    _obj(obj, "towns", ("schema_version", "factions"))
    if _int(obj["schema_version"], "towns.schema_version", 0, MAX_INT) != SCHEMA_VERSION:
        raise DataPackError("towns.schema_version: unsupported")
    facs = [_check_faction(f, "towns.factions[%d]" % i)
            for i, f in enumerate(_list(obj["factions"], "towns.factions"))]
    if not facs:
        raise DataPackError("towns.factions: must not be empty")
    by_id = {}
    for f in facs:
        if f.id in by_id:
            raise DataPackError("towns: duplicate faction %r" % (f.id,))
        by_id[f.id] = f
    return TownContent(tuple(by_id[k] for k in sorted(by_id)))


def load_town_pack(path):
    """Read and validate a town pack file (floats and duplicate keys rejected)."""
    return parse_town_pack(_read((path,))[0])


def _canon_bytes(obj):
    return json.dumps(asdict(obj), sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_hash(content):
    """SHA-256 of the canonical JSON of validated content (for logs and tests;
    the content itself is in every state, so the state hash covers it)."""
    return hashlib.sha256(_canon_bytes(content)).hexdigest()


def _faction(content, fid):
    for f in content.factions:
        if f.id == fid:
            return f
    raise KeyError(fid)


def find_building(content, faction_id, building_id):
    for b in _faction(content, faction_id).buildings:
        if b.id == building_id:
            return b
    raise KeyError(building_id)


# --------------------------------------------------------------------------
# State, commands, events
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TownSetup:
    id: str
    faction: str
    owner: int
    built: tuple = ()


@dataclass(frozen=True)
class Town:
    id: str
    faction: str
    owner: int
    built: tuple                    # sorted building ids
    built_today: bool = False


@dataclass(frozen=True)
class TownState:
    game_id: str
    policy: TownPolicy
    content: TownContent
    players: tuple                  # Resources per player (treasury)
    towns: tuple
    day: int = 1


class IllegalCommand(ValueError):
    """Command rejected; state untouched."""


@dataclass(frozen=True)
class Build:
    player: int
    town: str
    building: str


@dataclass(frozen=True)
class NewDay:
    pass


@dataclass(frozen=True)
class BuildingBuilt:
    town: str
    building: str
    player: int
    cost: Resources
    treasury: Resources             # the player's resources after paying


@dataclass(frozen=True)
class TownDayStarted:
    day: int


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

def town_rng(master_seed, game_id):
    """The town core's named stream: ``town:<game_id>`` (never drawn from)."""
    return derive_stream(master_seed, "town:%s" % (game_id,))


def _round_castle_bonus(base, bonus, mode):
    """The one rounding step of weekly growth: base * bonus (an exact Fraction)."""
    n, d = base * bonus.numerator, bonus.denominator
    if mode == "floor":
        return n // d
    if mode == "ceil":
        return -(-n // d)
    return (2 * n + d) // (2 * d)       # nearest, halves up


def weekly_growth(base, bonus, horde, policy=DEFAULT_POLICY):
    """rules.md 4: base + base * castle_bonus + horde. ``bonus`` is (num, den)."""
    return base + _round_castle_bonus(base, Fraction(*bonus), policy.citadel_rounding) + horde


def _town(state, town_id):
    for t in state.towns:
        if t.id == town_id:
            return t
    raise IllegalCommand("no such town %r" % (town_id,))


def _buildings(state, town):
    return _faction(state.content, town.faction).buildings


def _active(state, town):
    """Built buildings that no built building upgrades, in id order."""
    blds = [b for b in _buildings(state, town) if b.id in town.built]
    gone = set(b.upgrades for b in blds if b.upgrades)
    return tuple(b for b in blds if b.id not in gone)


def missing_requirements(state, town_id, building_id):
    town = _town(state, town_id)
    b = find_building(state.content, town.faction, building_id)
    return tuple(r for r in b.requires if r not in town.built)


def active_buildings(state, town_id):
    return tuple(b.id for b in _active(state, _town(state, town_id)))


def town_income(state, town_id):
    """Daily income of the town's active buildings (an upgrade replaces the
    building it upgrades). Feed it to the adventure ``Player.extra_income``."""
    total = Resources()
    for b in _active(state, _town(state, town_id)):
        total = total + b.income
    return total


def player_income(state, player):
    total = Resources()
    for t in state.towns:
        if t.owner == player:
            total = total + town_income(state, t.id)
    return total


def dwellings(state, town_id):
    """(level, creature, base_growth) of each active dwelling, by level."""
    act = _active(state, _town(state, town_id))
    return tuple(sorted((b.dwelling_level, b.creature, b.base_growth)
                        for b in act if b.dwelling_level))


def growth_pools(state, town_id, current=()):
    """Weekly growth of each dwelling level as adventure ``GrowthPool`` values
    (id ``<town>:dwelling<level>``, ascending level). ``available`` is carried
    over from the pool with the same id in ``current`` (0 if none)."""
    town = _town(state, town_id)
    act = _active(state, town)
    bonus = (0, 1)
    for b in act:
        if Fraction(*b.growth_bonus) > Fraction(*bonus):
            bonus = b.growth_bonus      # castle bonuses do not stack [documented]
    have = {}
    for p in current:
        have[p.id] = p.available
    out = []
    for level, _creature, base in dwellings(state, town_id):
        horde = sum(b.horde_bonus for b in act if b.horde_level == level)
        pid = "%s:dwelling%d" % (town.id, level)
        out.append(GrowthPool(pid, have.get(pid, 0),
                              weekly_growth(base, bonus, horde, state.policy)))
    return tuple(out)


def _covers(have, cost):
    return all(getattr(have, n) >= getattr(cost, n) for n in RESOURCE_NAMES)


def _minus(have, cost):
    return Resources(*(getattr(have, n) - getattr(cost, n) for n in RESOURCE_NAMES))


def _unique_holder(state, player, tag, skip_town):
    """Id of another town of ``player`` that has a ``tag`` building, or None."""
    for t in state.towns:
        if t.owner == player and t.id != skip_town and any(
                b.player_unique == tag for b in _buildings(state, t) if b.id in t.built):
            return t.id
    return None


# --------------------------------------------------------------------------
# Setup, canonical form, hash
# --------------------------------------------------------------------------

def create_game(game_id, content, players, towns, policy=DEFAULT_POLICY):
    """Build the initial state (day 1). ``players``: a Resources treasury per
    player. ``towns``: TownSetup with a prerequisite-closed ``built`` list."""
    if not players or any(getattr(p, n) < 0 for p in players for n in RESOURCE_NAMES):
        raise ValueError("players need non-negative resources")
    built, seen = [], set()
    for s in towns:
        if s.id in seen:
            raise ValueError("duplicate town id %r" % (s.id,))
        seen.add(s.id)
        try:
            fac = _faction(content, s.faction)
        except KeyError:
            raise ValueError("town %r: unknown faction %r" % (s.id, s.faction)) from None
        if not 0 <= s.owner < len(players):
            raise ValueError("town %r: no such owner %r" % (s.id, s.owner))
        names = tuple(sorted(s.built))
        known = tuple(b.id for b in fac.buildings)
        if len(set(names)) != len(names) or any(n not in known for n in names):
            raise ValueError("town %r: unknown or duplicate building" % (s.id,))
        for b in fac.buildings:
            if b.id in names and any(r not in names for r in b.requires):
                raise ValueError("town %r: %r requires %s" % (s.id, b.id, ", ".join(b.requires)))
        built.append(Town(str(s.id), s.faction, s.owner, names))
    state = TownState(str(game_id), policy, content, tuple(players), tuple(built))
    for t in state.towns:
        for b in _buildings(state, t):
            if b.id in t.built and b.player_unique and _unique_holder(
                    state, t.owner, b.player_unique, t.id) is not None:
                raise ValueError("player %d has more than one %r building"
                                 % (t.owner, b.player_unique))
    return state


def canonical(state):
    """Canonical byte form of the state (ADR-0001)."""
    return _canon_bytes(state)


def state_hash(state):
    return hashlib.sha256(canonical(state)).hexdigest()


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def _validate_build(state, cmd):
    if not (type(cmd.player) is int and 0 <= cmd.player < len(state.players)):
        raise IllegalCommand("no such player %r" % (cmd.player,))
    town = _town(state, cmd.town)
    if town.owner != cmd.player:
        raise IllegalCommand("player %d does not own town %r" % (cmd.player, town.id))
    try:
        b = find_building(state.content, town.faction, cmd.building)
    except KeyError:
        raise IllegalCommand("no such building %r" % (cmd.building,)) from None
    if b.id in town.built:
        raise IllegalCommand("%r already built" % (b.id,))
    if town.built_today:
        raise IllegalCommand("town %r already built today" % (town.id,))
    missing = tuple(r for r in b.requires if r not in town.built)
    if missing:
        raise IllegalCommand("%r: missing %s" % (b.id, ", ".join(missing)))
    if b.player_unique and _unique_holder(state, cmd.player, b.player_unique, town.id):
        raise IllegalCommand("player %d already has a %r building"
                             % (cmd.player, b.player_unique))
    if not _covers(state.players[cmd.player], b.cost):
        raise IllegalCommand("player %d cannot afford %r" % (cmd.player, b.id))
    return town, b


def apply(state, cmd, rng=None):
    """Apply one command. Returns (new_state, events). Pure; ``rng`` (the
    ``town:<id>`` stream) is reserved and never drawn from."""
    if isinstance(cmd, NewDay):
        day = state.day + 1
        towns = tuple(replace(t, built_today=False) for t in state.towns)
        return replace(state, day=day, towns=towns), (TownDayStarted(day),)
    if not isinstance(cmd, Build):
        raise IllegalCommand("unknown command %r" % (cmd,))
    town, b = _validate_build(state, cmd)
    left = _minus(state.players[cmd.player], b.cost)
    players = list(state.players)
    players[cmd.player] = left
    towns = tuple(replace(t, built=tuple(sorted(t.built + (b.id,))), built_today=True)
                  if t.id == town.id else t for t in state.towns)
    state = replace(state, players=tuple(players), towns=towns)
    return state, (BuildingBuilt(town.id, b.id, cmd.player, b.cost, left),)
