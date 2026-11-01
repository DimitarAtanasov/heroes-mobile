"""Reference simulation core for the adventure map: movement and economy.

Spec: docs/specs/adventure.md (built on rules.md sections 1-3 and
engine-design.md section 1.3). Clean-room: written from those specs only.
Out of scope: towns, map objects, fog of war, boats, spells, artifacts, AI.

Design (same as battle.py):

* State is immutable (frozen dataclasses, tuples, ints, strings, bools).
* ``apply(state, cmd, rng) -> (state', events)`` is the only way to advance
  the game. An illegal command raises ``IllegalCommand`` before anything
  happens. Nothing here is random yet; ``rng`` (stream ``adventure:<id>``)
  is accepted for interface stability and is never drawn from.
* No floats. Percentages are integer and every rounding goes through
  ``_div`` with the mode the policy names.
* Every rule that rules.md tags [uncertain] and that is in scope is a field
  of ``AdventurePolicy``; the policy is stored in the state (and hash).
"""

import hashlib
import heapq
import json
from dataclasses import asdict, dataclass, replace

from .rng import derive_stream

__all__ = [
    "TERRAIN_COST", "IMPASSABLE", "ROADS", "MINE_OUTPUT", "LOGISTICS_PCT",
    "AdventurePolicy", "DEFAULT_POLICY", "Resources", "Tile", "Grid",
    "ArmySlot", "HeroSetup", "Hero", "Player", "GrowthPool", "GameState",
    "IllegalCommand", "Begin", "Move", "EndTurn",
    "DayStarted", "WeekStarted", "PoolGrew", "TurnStarted", "IncomeReceived",
    "MovementReset", "HeroMoved", "TurnEnded",
    "adventure_rng", "base_movement", "max_movement", "step_cost",
    "find_path", "reachable", "daily_income", "calendar",
    "create_game", "apply", "canonical", "state_hash",
]

# --------------------------------------------------------------------------
# Content-free constants from rules.md (all [documented]).
# --------------------------------------------------------------------------

TERRAIN_COST = {          # rules.md 2.2, orthogonal step, no Pathfinding
    "dirt": 100, "grass": 100, "lava": 100, "subterranean": 100,
    "rough": 125, "sand": 150, "snow": 150, "swamp": 175,
}
IMPASSABLE = ("water", "rock")   # for land movement [engine]
ROADS = ("none", "dirt", "gravel", "cobblestone")

# rules.md 2.1: slowest speed -> base land movement points
_SPEED_MP = (1500, 1500, 1500, 1500, 1560, 1630, 1700, 1760, 1830, 1900, 1960, 2000)
LOGISTICS_PCT = (0, 10, 20, 30)      # none/basic/advanced/expert

RESOURCE_NAMES = ("gold", "wood", "ore", "mercury", "sulfur", "crystal", "gems")


@dataclass(frozen=True)
class Resources:
    gold: int = 0
    wood: int = 0
    ore: int = 0
    mercury: int = 0
    sulfur: int = 0
    crystal: int = 0
    gems: int = 0

    def __add__(self, other):
        return Resources(*(getattr(self, n) + getattr(other, n) for n in RESOURCE_NAMES))

    def __bool__(self):
        return any(getattr(self, n) for n in RESOURCE_NAMES)


MINE_OUTPUT = {           # rules.md 3, per day
    "sawmill": Resources(wood=2),
    "ore_pit": Resources(ore=2),
    "alchemists_lab": Resources(mercury=1),
    "sulfur_dune": Resources(sulfur=1),
    "crystal_cavern": Resources(crystal=1),
    "gem_pond": Resources(gems=1),
    "gold_mine": Resources(gold=1000),
}


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

_ROUNDING = ("floor", "ceil", "nearest")


@dataclass(frozen=True)
class AdventurePolicy:
    """Switchable rules. Every field is [uncertain] in rules.md (or [engine]);
    see docs/specs/adventure.md section 6 for the list and the defaults."""

    # 2.2 road cost per road type (rules.md: dirt 50; others may be cheaper).
    road_cost: tuple = (("cobblestone", 50), ("dirt", 50), ("gravel", 50))
    # Does the road discount need a road on both tiles of the step?
    road_needs_both: bool = False
    # Whose terrain prices a step: the tile entered or the tile left.
    cost_from: str = "dest"             # "dest" | "source"
    # 2.2 diagonals: allowed?, cost = orth * num / den rounded.
    diagonal_moves: bool = True
    diagonal_num: int = 141
    diagonal_den: int = 100
    diagonal_rounding: str = "floor"
    # May a diagonal step squeeze between two impassable orthogonal tiles?
    diagonal_corner_cut: bool = True
    # 2.2 last step with too few points: "forbid" | "allow_if_any"
    # (any points left: take it, points drop to 0) | "allow_if_fresh"
    # (only as the hero's first step of the day).
    last_step: str = "allow_if_any"
    # 2.2 Pathfinding: % cut of the part of terrain cost above 100.
    pathfinding_pct: tuple = (0, 25, 50, 75)
    pathfinding_rounding: str = "floor"
    # 3 Do players receive daily income at the start of day 1?
    income_on_first_day: bool = False

    def __post_init__(self):
        if self.cost_from not in ("dest", "source"):
            raise ValueError("bad cost_from")
        if self.last_step not in ("forbid", "allow_if_any", "allow_if_fresh"):
            raise ValueError("bad last_step")
        for r in (self.diagonal_rounding, self.pathfinding_rounding):
            if r not in _ROUNDING:
                raise ValueError("bad rounding mode %r" % (r,))
        if self.diagonal_den <= 0 or self.diagonal_num <= 0:
            raise ValueError("bad diagonal fraction")
        if len(self.pathfinding_pct) != 4 or not all(
                0 <= p <= 100 for p in self.pathfinding_pct):
            raise ValueError("pathfinding_pct needs 4 values in 0..100")
        roads = dict(self.road_cost)
        if sorted(roads) != sorted(ROADS[1:]) or any(c <= 0 for c in roads.values()):
            raise ValueError("road_cost needs a positive cost for each road type")


DEFAULT_POLICY = AdventurePolicy()


def _div(n, d, mode):
    if mode == "floor":
        return n // d
    if mode == "ceil":
        return -(-n // d)
    return (2 * n + d) // (2 * d)   # nearest, halves up


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Tile:
    terrain: str
    road: str = "none"
    blocked: bool = False     # impassable map decoration [engine]


@dataclass(frozen=True)
class Grid:
    width: int
    height: int
    tiles: tuple              # row-major, len == width * height

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0 or len(self.tiles) != self.width * self.height:
            raise ValueError("grid size mismatch")
        for t in self.tiles:
            if t.terrain not in TERRAIN_COST and t.terrain not in IMPASSABLE:
                raise ValueError("unknown terrain %r" % (t.terrain,))
            if t.road not in ROADS:
                raise ValueError("unknown road %r" % (t.road,))

    def tile(self, pos):
        x, y = pos
        return self.tiles[y * self.width + x]

    def inside(self, pos):
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def passable(self, pos):
        if not self.inside(pos):
            return False
        t = self.tile(pos)
        return not t.blocked and t.terrain not in IMPASSABLE


@dataclass(frozen=True)
class ArmySlot:
    creature: str             # content id
    speed: int                # from content data
    count: int


@dataclass(frozen=True)
class HeroSetup:
    owner: int
    pos: tuple
    army: tuple               # 1..7 ArmySlot
    logistics: int = 0        # 0..3
    pathfinding: int = 0      # 0..3


@dataclass(frozen=True)
class Hero:
    id: int
    owner: int
    pos: tuple
    army: tuple
    logistics: int
    pathfinding: int
    mp: int                   # movement points left today
    mp_max: int               # points granted at the start of today
    moved_today: bool


@dataclass(frozen=True)
class Player:
    resources: Resources = Resources()
    mines: tuple = ()                       # MINE_OUTPUT keys
    extra_income: Resources = Resources()   # hook: towns, silos, Estates...


@dataclass(frozen=True)
class GrowthPool:
    """Weekly growth hook: a dwelling (town or map) as plain numbers. The
    owner module computes ``growth``; this core only applies it weekly."""
    id: str
    available: int
    growth: int


@dataclass(frozen=True)
class GameState:
    game_id: str
    policy: AdventurePolicy
    grid: Grid
    players: tuple
    heroes: tuple
    pools: tuple
    day: int = 0              # 0 = not started
    current: int = 0          # index of the player whose turn it is


class IllegalCommand(ValueError):
    """Command rejected; state untouched."""


# Commands --------------------------------------------------------------

@dataclass(frozen=True)
class Begin:
    pass


@dataclass(frozen=True)
class Move:
    hero: int
    dest: tuple


@dataclass(frozen=True)
class EndTurn:
    player: int


# Events ----------------------------------------------------------------

@dataclass(frozen=True)
class DayStarted:
    day: int
    week: int
    day_of_week: int
    month: int


@dataclass(frozen=True)
class WeekStarted:
    week: int
    month: int
    new_month: bool


@dataclass(frozen=True)
class PoolGrew:
    pool: str
    added: int
    available: int


@dataclass(frozen=True)
class TurnStarted:
    player: int
    day: int


@dataclass(frozen=True)
class IncomeReceived:
    player: int
    income: Resources


@dataclass(frozen=True)
class MovementReset:
    hero: int
    mp: int


@dataclass(frozen=True)
class HeroMoved:
    hero: int
    path: tuple               # start tile first
    cost: int
    mp_left: int


@dataclass(frozen=True)
class TurnEnded:
    player: int


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

def adventure_rng(master_seed, game_id):
    """The game's named stream: ``adventure:<game_id>`` (unused for now)."""
    return derive_stream(master_seed, "adventure:%s" % (game_id,))


def calendar(day):
    """(week, day_of_week, month) for absolute day >= 1. [documented]"""
    return (day - 1) // 7 + 1, (day - 1) % 7 + 1, (day - 1) // 28 + 1


def base_movement(army):
    """rules.md 2.1: base land points from the slowest stack. [documented]"""
    if not army:
        raise ValueError("hero needs an army")
    slowest = min(s.speed for s in army)
    return _SPEED_MP[max(0, min(slowest, len(_SPEED_MP) - 1))]


def max_movement(hero, policy=DEFAULT_POLICY):
    """Daily land points: base + Logistics. Every table value is a multiple
    of 10 and every Logistics step a multiple of 10%, so the product is
    always an integer and the [uncertain] rounding cannot arise here."""
    base = base_movement(hero.army)
    return base + base * LOGISTICS_PCT[hero.logistics] // 100


def step_cost(grid, a, b, pathfinding=0, policy=DEFAULT_POLICY):
    """Movement cost of one step a -> b (8-neighbours), ignoring the
    remaining-points rule. Returns None when the step is not allowed."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if (dx, dy) == (0, 0) or max(abs(dx), abs(dy)) != 1:
        return None
    if not grid.passable(a) or not grid.passable(b):
        return None
    diagonal = dx != 0 and dy != 0
    if diagonal:
        if not policy.diagonal_moves:
            return None
        if not policy.diagonal_corner_cut and not (
                grid.passable((a[0] + dx, a[1])) and grid.passable((a[0], a[1] + dy))):
            return None
    ta, tb = grid.tile(a), grid.tile(b)
    roads = dict(policy.road_cost)
    if tb.road != "none" and (ta.road != "none" or not policy.road_needs_both):
        if policy.road_needs_both:
            cost = max(roads[ta.road], roads[tb.road])
        else:
            cost = roads[tb.road]
    else:
        terrain = tb.terrain if policy.cost_from == "dest" else ta.terrain
        cost = TERRAIN_COST[terrain]
        if cost > 100 and pathfinding:
            pen = cost - 100
            cut = _div(pen * policy.pathfinding_pct[pathfinding], 100,
                       policy.pathfinding_rounding)
            cost = 100 + pen - cut
    if diagonal:
        cost = _div(cost * policy.diagonal_num, policy.diagonal_den, policy.diagonal_rounding)
    return cost


_DIRS = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def _search(state, hero, budget):
    """Dijkstra from the hero's tile. Labels are (spent, steps, path) and the
    smallest label wins (deterministic tie-break). ``budget`` None = no
    movement-point limit (planning). Returns tile -> (spent, path)."""
    grid, pol = state.grid, state.policy
    occupied = set(h.pos for h in state.heroes if h.id != hero.id)
    start = hero.pos
    best = {start: (0, 0, (start,))}
    heap = [(0, 0, (start,))]
    done = set()
    while heap:
        spent, steps, path = heapq.heappop(heap)
        cur = path[-1]
        if cur in done:
            continue
        done.add(cur)
        if budget is not None and spent >= budget:
            continue
        for dx, dy in _DIRS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in occupied or nxt in done:
                continue
            c = step_cost(grid, cur, nxt, hero.pathfinding, pol)
            if c is None:
                continue
            if budget is not None and spent + c > budget:
                left = budget - spent
                fresh = spent == 0 and not hero.moved_today
                if pol.last_step == "allow_if_any" or (
                        pol.last_step == "allow_if_fresh" and fresh):
                    c = left           # the step uses up every point left
                else:
                    continue
            label = (spent + c, steps + 1, path + (nxt,))
            if nxt not in best or label < best[nxt]:
                best[nxt] = label
                heapq.heappush(heap, label)
    return {t: (lab[0], lab[2]) for t, lab in best.items() if t != start}


def find_path(state, hero_id, dest):
    """Cheapest path ignoring today's points (UI planning): (cost, path) with
    the start tile first, or None. Ends of day are not modelled."""
    hero = state.heroes[hero_id]
    return _search(state, hero, None).get(tuple(dest))


def reachable(state, hero_id):
    """tile -> (cost, path) for every tile the hero can reach today."""
    hero = state.heroes[hero_id]
    return _search(state, hero, hero.mp)


def daily_income(player):
    total = player.extra_income
    for m in player.mines:
        total = total + MINE_OUTPUT[m]
    return total


# --------------------------------------------------------------------------
# Setup, canonical form, hash
# --------------------------------------------------------------------------

def create_game(game_id, grid, players, heroes, pools=(), policy=DEFAULT_POLICY):
    """Build the initial (not yet started) state. Apply ``Begin()`` next."""
    if not players:
        raise ValueError("need at least one player")
    for p in players:
        for m in p.mines:
            if m not in MINE_OUTPUT:
                raise ValueError("unknown mine %r" % (m,))
    ids = [p.id for p in pools]
    if len(ids) != len(set(ids)) or any(p.available < 0 or p.growth < 0 for p in pools):
        raise ValueError("bad growth pools")
    built = []
    seen = set()
    for i, h in enumerate(heroes):
        pos = tuple(h.pos)
        if not 0 <= h.owner < len(players):
            raise ValueError("hero %d: no such owner" % i)
        if not 1 <= len(h.army) <= 7 or any(s.count <= 0 or s.speed < 0 for s in h.army):
            raise ValueError("hero %d: invalid army" % i)
        if not (0 <= h.logistics <= 3 and 0 <= h.pathfinding <= 3):
            raise ValueError("hero %d: skill level out of range" % i)
        if not grid.passable(pos) or pos in seen:
            raise ValueError("hero %d cannot stand at %r" % (i, pos))
        seen.add(pos)
        built.append(Hero(id=i, owner=h.owner, pos=pos, army=tuple(h.army),
                          logistics=h.logistics, pathfinding=h.pathfinding,
                          mp=0, mp_max=0, moved_today=False))
    return GameState(game_id=str(game_id), policy=policy, grid=grid,
                     players=tuple(players), heroes=tuple(built), pools=tuple(pools))


def canonical(state):
    """Canonical byte form of the state (used for hashing, saves, sync)."""
    return json.dumps(asdict(state), sort_keys=True, separators=(",", ":")).encode("utf-8")


def state_hash(state):
    return hashlib.sha256(canonical(state)).hexdigest()


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def _start_day(state, events):
    week, dow, month = calendar(state.day)
    events.append(DayStarted(state.day, week, dow, month))
    if dow == 1 and week > 1:     # rules.md 1: not on the very first week
        events.append(WeekStarted(week, month, (week - 1) % 4 == 0))
        pools = []
        for p in state.pools:
            p = replace(p, available=p.available + p.growth)
            events.append(PoolGrew(p.id, p.growth, p.available))
            pools.append(p)
        state = replace(state, pools=tuple(pools))
    return state


def _start_turn(state, events):
    pid = state.current
    events.append(TurnStarted(pid, state.day))
    if state.day > 1 or state.policy.income_on_first_day:
        player = state.players[pid]
        inc = daily_income(player)
        players = list(state.players)
        players[pid] = replace(player, resources=player.resources + inc)
        state = replace(state, players=tuple(players))
        events.append(IncomeReceived(pid, inc))
    heroes = list(state.heroes)
    for h in state.heroes:
        if h.owner == pid:
            mp = max_movement(h, state.policy)
            heroes[h.id] = replace(h, mp=mp, mp_max=mp, moved_today=False)
            events.append(MovementReset(h.id, mp))
    return replace(state, heroes=tuple(heroes))


def _validate(state, cmd):
    if isinstance(cmd, Begin):
        if state.day:
            raise IllegalCommand("game already started")
        return None
    if not state.day:
        raise IllegalCommand("game not started")
    if isinstance(cmd, EndTurn):
        if cmd.player != state.current:
            raise IllegalCommand("not player %r's turn" % (cmd.player,))
        return None
    if isinstance(cmd, Move):
        if not (isinstance(cmd.hero, int) and 0 <= cmd.hero < len(state.heroes)):
            raise IllegalCommand("no such hero")
        if state.heroes[cmd.hero].owner != state.current:
            raise IllegalCommand("hero does not belong to the current player")
        reach = reachable(state, cmd.hero)
        dest = tuple(cmd.dest)
        if dest not in reach:
            raise IllegalCommand("destination not reachable today")
        return reach[dest]
    raise IllegalCommand("unknown command %r" % (cmd,))


def apply(state, cmd, rng=None):
    """Apply one command. Returns (new_state, events). Pure; ``rng`` (the
    ``adventure:<id>`` stream) is reserved and not drawn from."""
    data = _validate(state, cmd)
    events = []
    if isinstance(cmd, Begin):
        state = _start_day(replace(state, day=1, current=0), events)
        state = _start_turn(state, events)
    elif isinstance(cmd, Move):
        cost, path = data
        h = state.heroes[cmd.hero]
        h = replace(h, pos=path[-1], mp=h.mp - cost, moved_today=True)
        heroes = list(state.heroes)
        heroes[h.id] = h
        state = replace(state, heroes=tuple(heroes))
        events.append(HeroMoved(h.id, path, cost, h.mp))
    else:  # EndTurn
        events.append(TurnEnded(state.current))
        nxt = state.current + 1
        if nxt == len(state.players):
            state = _start_day(replace(state, day=state.day + 1, current=0), events)
        else:
            state = replace(state, current=nxt)
        state = _start_turn(state, events)
    return state, tuple(events)
