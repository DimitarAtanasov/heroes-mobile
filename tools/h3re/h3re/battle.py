"""Reference simulation core for field battles (no spells, no siege, no AI).

Spec: docs/specs/battle.md (built on rules.md section 6 and engine-design.md
section 1.3). Clean-room: written from those specs only.

Design:

* State is immutable (frozen dataclasses, tuples, ints, strings, bools).
* ``apply(state, cmd, rng) -> (state', events)`` is the only way to advance a
  battle. An illegal command raises ``IllegalCommand`` *before* any RNG draw,
  so neither the state nor the stream is touched.
* No floats. Damage is computed by ``rules.py`` (exact fractions, one floor),
  through ``rules.resolve_damage``: the same function serves execution
  (ACTUAL_SEED) and preview (``strike_preview``).
* Randomness comes only from the ``rng`` argument, which should be the
  ``rng.py`` stream ``battle:<battle_id>`` (see ``battle_rng``).
* Every rule that rules.md tags [uncertain] is a field of ``BattlePolicy``;
  the policy is stored in the state (and therefore in the state hash).
* docs/specs/vcmi-crosscheck-rules.md records VCMI evidence for several
  policies. VCMI is evidence, not proof: only "clear" items changed a default
  (``row_offset``, ``range_origin``, the wait-activation morale split); the
  rest are extra options pending rules.md section 9 experiments.
"""

import hashlib
import json
from collections import deque
from dataclasses import asdict, dataclass, replace

from . import datapack as _datapack
from . import rules
from .rng import derive_stream

__all__ = [
    "WIDTH", "HEIGHT", "ATTACKER", "DEFENDER",
    "BattlePolicy", "DEFAULT_POLICY", "Creature", "Hero", "StackSetup",
    "Stack", "BattleState", "IllegalCommand",
    "Begin", "Move", "Attack", "Shoot", "Wait", "Defend",
    "BattleStarted", "RoundStarted", "TurnStarted", "MoraleFrozen",
    "MoraleBoost", "Moved", "Waited", "Defended", "LuckRolled",
    "DamageDealt", "UnitDied", "BattleEnded",
    "in_grid", "neighbours", "hex_distance", "to_axial", "from_axial",
    "battle_rng", "create_battle", "apply", "cells", "reachable",
    "turn_order", "round_order", "legal_commands", "canonical", "state_hash",
    "defend_bonus", "effective_morale", "DEFAULT_ROW_OFFSET",
    "strike_context", "strike_preview", "PackMismatch", "POLICY_HASH",
    "check_state",
]

WIDTH = 17
HEIGHT = 11
ATTACKER = 0
DEFENDER = 1

# BattlePolicy defaults are rule choices, so they live in data/battle_policy.json
# (validated by datapack.py), not here. POLICY_HASH is the content hash of that
# file. It is not a state field: the policy itself is already in the state hash.
_POLICY_PACK = _datapack.load_policy_pack_dir()
POLICY_HASH = _POLICY_PACK.content_hash
_P = _POLICY_PACK.values
# Default row parity for the geometry helpers; equals BattlePolicy().row_offset.
DEFAULT_ROW_OFFSET = _P["row_offset"]


# --------------------------------------------------------------------------
# Policy: every [uncertain] rule of rules.md section 6 that is in scope.
# --------------------------------------------------------------------------

_SPEED_TIES = _datapack.POLICY_CHOICES["speed_tie"]
# ADR-0008: the Kotlin engine holds state and policy integers as 32-bit Int.
_MAX_INT = _datapack.MAX_INT
_MIN_INT = -_MAX_INT - 1


def _bounded(v, name, lo, hi):
    """Integer ``v`` in [lo, hi] (bools are not integers here), else ValueError."""
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError("%s out of range" % name)
    return v
_WAIT_ORDERS = _datapack.POLICY_CHOICES["wait_order"]


@dataclass(frozen=True)
class BattlePolicy:
    """Switchable rules. Defaults are the documented / commonly cited choice.

    All fields are [uncertain] in rules.md; see docs/specs/battle.md.
    """

    # 6.1 geometry: which rows are shifted half a hex to the right.
    # "even" since the VCMI cross-check (#1, clear); "odd" was the old default.
    row_offset: str = _P["row_offset"]   # "odd" | "even"
    # 6.1 geometry: may ordinary stacks use the war-machine edge columns?
    edge_columns_walkable: bool = _P["edge_columns_walkable"]
    # 6.1 initial placement: rows per army size (index = n_stacks - 1).
    placement_rows: tuple = _P["placement_rows"]
    # 6.3 speed ties: "attacker_first" (side, then slot) | "alternate"
    # (interleave, attacker first in every tie group) | "alternate_last_mover"
    # (the side that did not act last goes first; carries across rounds;
    # VCMI behaviour, pending rules.md 9.4).
    speed_tie: str = _P["speed_tie"]
    # 6.3 order within the wait phase: "reverse_speed" | "speed" | "fifo" |
    # "slow_first_alternate" (ascending speed, ties by the last-mover rule,
    # lower slot first; VCMI behaviour, pending rules.md 9.4).
    wait_order: str = _P["wait_order"]
    # 6.3 defend bonus: num/den of Defense, at least ``min``, rounding mode.
    defend_bonus_num: int = _P["defend_bonus_num"]
    defend_bonus_den: int = _P["defend_bonus_den"]
    defend_bonus_min: int = _P["defend_bonus_min"]
    defend_bonus_rounding: str = _P["defend_bonus_rounding"]   # "floor" | "ceil"
    # 6.5 good morale after Wait / Defend, repeated triggers.
    good_morale_after_wait: bool = _P["good_morale_after_wait"]
    good_morale_after_defend: bool = _P["good_morale_after_defend"]
    repeat_good_morale: bool = _P["repeat_good_morale"]
    # 6.5 morale rolls at a stack's wait-phase activation (VCMI cross-check
    # #4): no bad-morale roll, the good-morale roll still happens.
    # These two replace the deprecated ``morale_roll_on_wait_activation``
    # (old True == both True, old False == both False).
    bad_morale_on_wait_activation: bool = _P["bad_morale_on_wait_activation"]
    good_morale_on_wait_activation: bool = _P["good_morale_on_wait_activation"]
    # 6.5 bad-morale chance numerators over 24 for morale -1, -2, -3.
    # (1, 2, 3) is the community-documented value; VCMI uses (2, 4, 6).
    # Pending rules.md 9.13. Both tables are in data/rules.json; the default
    # is the documented one, so it is not repeated in battle_policy.json.
    bad_morale_table: tuple = rules.BAD_MORALE_NUMERATORS
    # 6.5 bad luck (|L|/24 chance to halve damage, after the final floor).
    bad_luck: bool = _P["bad_luck"]
    # 6.6 R_range: penalty when distance > this many hexes.
    range_penalty_beyond: int = _P["range_penalty_beyond"]
    # 6.6 R_range distance origin: "head" (shooter head hex to any target
    # cell; VCMI cross-check #12, clear) | "any_cell" (minimum over all
    # shooter cells; the old default). Only matters for two-hex shooters.
    range_origin: str = _P["range_origin"]

    def __post_init__(self):
        if self.row_offset not in _datapack.POLICY_CHOICES["row_offset"]:
            raise ValueError("row_offset must be 'odd' or 'even'")
        if self.speed_tie not in _SPEED_TIES:
            raise ValueError("bad speed_tie")
        if self.wait_order not in _WAIT_ORDERS:
            raise ValueError("bad wait_order")
        if self.range_origin not in _datapack.POLICY_CHOICES["range_origin"]:
            raise ValueError("bad range_origin")
        table = tuple(self.bad_morale_table)
        object.__setattr__(self, "bad_morale_table", table)
        rules.check_bad_morale_table(table)
        if self.defend_bonus_rounding not in _datapack.POLICY_CHOICES["defend_bonus_rounding"]:
            raise ValueError("bad defend_bonus_rounding")
        if self.defend_bonus_den <= 0 or self.defend_bonus_num < 0:
            raise ValueError("bad defend bonus fraction")
        if len(self.placement_rows) != 7 or any(
                len(rows) != i + 1 for i, rows in enumerate(self.placement_rows)):
            raise ValueError("placement_rows needs 7 rows tuples of size 1..7")
        if self.range_penalty_beyond < 0:
            raise ValueError("bad range_penalty_beyond")
        # ADR-0008: every policy integer is a 32-bit Int on the Kotlin side.
        for name in ("defend_bonus_num", "defend_bonus_den", "defend_bonus_min",
                     "range_penalty_beyond"):
            _bounded(getattr(self, name), name, 0, _MAX_INT)
        for rows in self.placement_rows:
            for v in rows:
                _bounded(v, "placement_rows", _MIN_INT, _MAX_INT)


DEFAULT_POLICY = BattlePolicy()


# --------------------------------------------------------------------------
# Hex geometry: 17 x 11 offset grid, hexes are (col, row) tuples.
# --------------------------------------------------------------------------

_AXIAL_DIRS = ((1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (-1, 1))


def in_grid(h):
    c, r = h
    return 0 <= c < WIDTH and 0 <= r < HEIGHT


def to_axial(h, row_offset=DEFAULT_ROW_OFFSET):
    c, r = h
    if row_offset == "odd":
        return c - (r - (r & 1)) // 2, r
    return c - (r + (r & 1)) // 2, r


def from_axial(q, r, row_offset=DEFAULT_ROW_OFFSET):
    if row_offset == "odd":
        return q + (r - (r & 1)) // 2, r
    return q + (r + (r & 1)) // 2, r


def neighbours(h, row_offset=DEFAULT_ROW_OFFSET):
    """Sorted tuple of in-grid neighbours of hex ``h`` (at most 6)."""
    q, r = to_axial(h, row_offset)
    out = []
    for dq, dr in _AXIAL_DIRS:
        n = from_axial(q + dq, r + dr, row_offset)
        if in_grid(n):
            out.append(n)
    return tuple(sorted(out))


def hex_distance(a, b, row_offset=DEFAULT_ROW_OFFSET):
    aq, ar = to_axial(a, row_offset)
    bq, br = to_axial(b, row_offset)
    dq, dr = aq - bq, ar - br
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


# --------------------------------------------------------------------------
# Content-shaped inputs (numbers come from data, not from this module).
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Creature:
    name: str
    attack: int
    defense: int
    dmg_min: int
    dmg_max: int
    hp: int
    speed: int
    shots: int = 0
    flyer: bool = False
    double_wide: bool = False
    no_enemy_retaliation: bool = False
    unlimited_retaliation: bool = False
    no_melee_penalty: bool = False
    no_range_penalty: bool = False
    strikes_twice: bool = False
    shoots_twice: bool = False
    no_morale: bool = False
    hates: tuple = ()

    @property
    def shooter(self):
        return self.shots > 0


@dataclass(frozen=True)
class Hero:
    attack: int = 0
    defense: int = 0
    offense: int = 0
    archery: int = 0
    armorer: int = 0


@dataclass(frozen=True)
class StackSetup:
    creature: Creature
    count: int
    morale: int = 0
    luck: int = 0
    pos: tuple = None  # head hex; None = policy placement table


@dataclass(frozen=True)
class Stack:
    id: int
    side: int
    slot: int
    creature: Creature
    count: int
    top_hp: int
    pos: tuple
    shots: int
    retaliations: int
    defending: bool
    morale: int
    luck: int

    @property
    def alive(self):
        return self.count > 0


@dataclass(frozen=True)
class BattleState:
    battle_id: str
    policy: BattlePolicy
    heroes: tuple
    obstacles: tuple
    stacks: tuple
    round: int = 0
    started: bool = False
    active: int = None
    done: tuple = ()
    waited: tuple = ()
    bonus_turn: bool = False
    morale_pending: bool = False
    winner: int = None
    # Content hash of the rules pack the state was built under (ADR-0001). Part
    # of the canonical form, so peers with different packs differ at step 0.
    rules_hash: str = rules.RULES_HASH
    # Side of the most recently activated stack (None before the first
    # activation). Carries across rounds; used by the last-mover tie rules.
    last_side: int = None


class IllegalCommand(ValueError):
    """Command rejected; state and RNG are untouched."""


class PackMismatch(IllegalCommand):
    """The state was built under a different rules pack than the local one."""


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Begin:
    pass


@dataclass(frozen=True)
class Move:
    stack: int
    dest: tuple


@dataclass(frozen=True)
class Attack:
    stack: int
    target: int
    from_hex: tuple = None  # None = attack from current position


@dataclass(frozen=True)
class Shoot:
    stack: int
    target: int


@dataclass(frozen=True)
class Wait:
    stack: int


@dataclass(frozen=True)
class Defend:
    stack: int


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BattleStarted:
    battle_id: str


@dataclass(frozen=True)
class RoundStarted:
    round: int


@dataclass(frozen=True)
class TurnStarted:
    stack: int
    phase: str
    bonus: bool


@dataclass(frozen=True)
class MoraleFrozen:
    stack: int


@dataclass(frozen=True)
class MoraleBoost:
    stack: int


@dataclass(frozen=True)
class Moved:
    stack: int
    path: tuple


@dataclass(frozen=True)
class Waited:
    stack: int


@dataclass(frozen=True)
class Defended:
    stack: int


@dataclass(frozen=True)
class LuckRolled:
    stack: int
    good: bool


@dataclass(frozen=True)
class DamageDealt:
    attacker: int
    target: int
    damage: int
    killed: int
    ranged: bool
    retaliation: bool


@dataclass(frozen=True)
class UnitDied:
    stack: int


@dataclass(frozen=True)
class BattleEnded:
    winner: int


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

def battle_rng(master_seed, battle_id):
    """The battle's named stream: ``battle:<battle_id>``."""
    return derive_stream(master_seed, "battle:%s" % (battle_id,))


def _tail(head, side, double_wide):
    if not double_wide:
        return None
    c, r = head
    return (c - 1, r) if side == ATTACKER else (c + 1, r)


def _cells_at(head, side, double_wide):
    t = _tail(head, side, double_wide)
    return (head,) if t is None else (head, t)


def cells(stack):
    return _cells_at(stack.pos, stack.side, stack.creature.double_wide)


def _playable(h, policy):
    if not in_grid(h):
        return False
    if policy.edge_columns_walkable:
        return True
    return 1 <= h[0] <= WIDTH - 2


def create_battle(battle_id, attackers, defenders, *, obstacles=(),
                  heroes=(None, None), policy=DEFAULT_POLICY):
    """Build the initial (not yet started) state. Apply ``Begin()`` next."""
    if not 1 <= len(attackers) <= 7 or not 1 <= len(defenders) <= 7:
        raise ValueError("each side needs 1..7 stacks")
    if len(heroes) != 2:
        raise ValueError("heroes must be a pair")
    obs = tuple(sorted(set(tuple(o) for o in obstacles)))
    for o in obs:
        if not in_grid(o):
            raise ValueError("obstacle off grid: %r" % (o,))
    stacks = []
    occupied = set(obs)
    for side, army in ((ATTACKER, attackers), (DEFENDER, defenders)):
        rows = policy.placement_rows[len(army) - 1]
        for slot, s in enumerate(army):
            cr = s.creature
            if s.count <= 0 or cr.hp <= 0 or cr.speed < 0:
                raise ValueError("invalid stack setup")
            if not 1 <= cr.dmg_min <= cr.dmg_max:
                raise ValueError("invalid damage range")
            if s.pos is not None:
                head = tuple(s.pos)
            else:
                lo, hi = 1, WIDTH - 2
                if side == ATTACKER:
                    head = (lo + (1 if cr.double_wide else 0), rows[slot])
                else:
                    head = (hi - (1 if cr.double_wide else 0), rows[slot])
            cs = _cells_at(head, side, cr.double_wide)
            for c in cs:
                if not _playable(c, policy) or c in occupied:
                    raise ValueError("stack %d cannot be placed at %r" % (len(stacks), head))
            occupied.update(cs)
            stacks.append(Stack(
                id=len(stacks), side=side, slot=slot, creature=cr,
                count=s.count, top_hp=cr.hp, pos=head, shots=cr.shots,
                retaliations=1, defending=False, morale=s.morale, luck=s.luck))
    state = BattleState(battle_id=str(battle_id), policy=policy,
                        heroes=tuple(heroes), obstacles=obs, stacks=tuple(stacks))
    check_state(state)
    return state


_CREATURE_INTS = (("attack", _MIN_INT), ("defense", _MIN_INT), ("dmg_min", 1),
                  ("dmg_max", 1), ("hp", 1), ("speed", 0), ("shots", 0))
_HERO_INTS = ("attack", "defense", "offense", "archery", "armorer")


def _opt_side(v, name):
    if v is not None and (type(v) is not int or v not in (ATTACKER, DEFENDER)):
        raise ValueError("%s must be 0, 1 or None" % name)


def check_state(state):
    """Invariants of a battle state (battle.md "State invariants and integer caps").

    Every integer fits a 32-bit Int (ADR-0008), and the derived products the
    damage pipeline builds stay within it: count x dmg_max, count x hp, the
    attack sum and the defense sum (with the defend bonus) of every stack.
    ``create_battle`` calls it on every state it returns; the Kotlin parser
    (BattleCodec.parseState) applies the same checks with the same messages.
    Raises ValueError; returns None.
    """
    if len(state.heroes) != 2:
        raise ValueError("heroes must be a pair")
    for h in state.heroes:
        if h is not None:
            for name in _HERO_INTS:
                _bounded(getattr(h, name), "hero " + name, _MIN_INT, _MAX_INT)
    for o in state.obstacles:
        if not in_grid(o):
            raise ValueError("obstacle off grid")
    per_side = [0, 0]
    for i, s in enumerate(state.stacks):
        if s.id != i:
            raise ValueError("stack id differs from its index")
        if type(s.side) is not int or s.side not in (ATTACKER, DEFENDER):
            raise ValueError("stack side must be 0 or 1")
        per_side[s.side] += 1
        _bounded(s.slot, "stack slot", 0, 6)
        cr = s.creature
        for name, lo in _CREATURE_INTS:
            _bounded(getattr(cr, name), "creature " + name, lo, _MAX_INT)
        if cr.dmg_min > cr.dmg_max:
            raise ValueError("invalid damage range")
        _bounded(s.count, "stack count", 0, _MAX_INT)
        if s.count == 0:
            if s.top_hp != 0:
                raise ValueError("empty stack must have top_hp 0")
        else:
            _bounded(s.top_hp, "stack top_hp", 1, cr.hp)
        for name in ("shots", "retaliations"):
            _bounded(getattr(s, name), "stack " + name, 0, _MAX_INT)
        for name in ("morale", "luck"):
            _bounded(getattr(s, name), "stack " + name, _MIN_INT, _MAX_INT)
        if any(not in_grid(c) for c in cells(s)):
            raise ValueError("stack position off grid")
        if s.count * cr.dmg_max > _MAX_INT:
            raise ValueError("count x dmg_max exceeds 2**31-1")
        if s.count * cr.hp > _MAX_INT:
            raise ValueError("count x hp exceeds 2**31-1")
        hero = state.heroes[s.side]
        _bounded(cr.attack + (hero.attack if hero else 0), "attack sum", _MIN_INT, _MAX_INT)
        d = cr.defense + (hero.defense if hero else 0)
        _bounded(d, "defense sum", _MIN_INT, _MAX_INT)
        _bounded(d + defend_bonus(state, s), "defense sum", _MIN_INT, _MAX_INT)
    if not all(1 <= n <= 7 for n in per_side):
        raise ValueError("each side needs 1..7 stacks")
    n = len(state.stacks)
    _bounded(state.round, "round", 0, _MAX_INT)
    if state.active is not None:
        _bounded(state.active, "active", 0, n - 1)
    for name in ("done", "waited"):
        for v in getattr(state, name):
            _bounded(v, name, 0, n - 1)
    _opt_side(state.winner, "winner")
    _opt_side(state.last_side, "last_side")


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------

def _living(state):
    return [s for s in state.stacks if s.alive]


def _occupancy(state, exclude=None):
    occ = set()
    for s in state.stacks:
        if s.alive and s.id != exclude:
            occ.update(cells(s))
    return occ


def _fits(state, stack, head, occ):
    for c in _cells_at(head, stack.side, stack.creature.double_wide):
        if not _playable(c, state.policy) or c in occ or c in state.obstacles:
            return False
    return True


def _reach(state, stack):
    """head -> path (tuple of heads, start excluded) for all reachable heads."""
    occ = _occupancy(state, exclude=stack.id)
    off = state.policy.row_offset
    speed = stack.creature.speed
    result = {}
    if stack.creature.flyer:
        for r in range(HEIGHT):
            for c in range(WIDTH):
                h = (c, r)
                if h != stack.pos and hex_distance(stack.pos, h, off) <= speed \
                        and _fits(state, stack, h, occ):
                    result[h] = (h,)
        return result
    parent = {stack.pos: None}
    dist = {stack.pos: 0}
    q = deque([stack.pos])
    while q:
        cur = q.popleft()
        if dist[cur] >= speed:
            continue
        for n in neighbours(cur, off):
            if n in dist or not _fits(state, stack, n, occ):
                continue
            dist[n] = dist[cur] + 1
            parent[n] = cur
            q.append(n)
    for h in dist:
        if h == stack.pos:
            continue
        path = []
        x = h
        while x != stack.pos:
            path.append(x)
            x = parent[x]
        result[h] = tuple(reversed(path))
    return result


def reachable(state, stack_id):
    """Sorted tuple of head hexes the stack can move to this turn."""
    return tuple(sorted(_reach(state, state.stacks[stack_id])))


def _adjacent_cells(a_cells, b_cells, off):
    bs = set(b_cells)
    return any(n in bs for c in a_cells for n in neighbours(c, off))


def _enemy_adjacent(state, stack):
    off = state.policy.row_offset
    mine = cells(stack)
    return any(s.alive and s.side != stack.side and _adjacent_cells(mine, cells(s), off)
               for s in state.stacks)


def _speed_sorted(state, stacks):
    if state.policy.speed_tie == "attacker_first":
        return sorted(stacks, key=lambda s: (-s.creature.speed, s.side, s.slot))
    # alternate: within a speed, interleave sides starting with the attacker.
    rank = {}
    for spd in set(s.creature.speed for s in stacks):
        for side in (ATTACKER, DEFENDER):
            group = sorted((s for s in stacks if s.creature.speed == spd and s.side == side),
                           key=lambda s: s.slot)
            for i, s in enumerate(group):
                rank[s.id] = i
    return sorted(stacks, key=lambda s: (-s.creature.speed, rank[s.id], s.side))


def _last_mover_sorted(stacks, last_side, descending):
    """Order by speed (descending or ascending); within a speed group, the
    side that did not act last goes next (attacker if nobody has acted),
    lower slot first within a side. Returns (order, last side)."""
    out = []
    speeds = sorted(set(s.creature.speed for s in stacks), reverse=descending)
    for spd in speeds:
        queues = {side: deque(sorted((s for s in stacks
                                      if s.creature.speed == spd and s.side == side),
                                     key=lambda s: s.slot))
                  for side in (ATTACKER, DEFENDER)}
        while queues[ATTACKER] or queues[DEFENDER]:
            side = ATTACKER if last_side is None else 1 - last_side
            if not queues[side]:
                side = 1 - side
            out.append(queues[side].popleft())
            last_side = side
    return out, last_side


def turn_order(state):
    """Ids still to act this round, in order (the active stack first)."""
    living = _living(state)
    done = set(state.done)
    waited = set(state.waited)
    act = state.active
    if act is not None and not state.stacks[act].alive:
        act = None
    main = [s for s in living if s.id not in done and s.id not in waited]
    wait = [s for s in living if s.id in waited and s.id not in done]
    pol = state.policy
    # The last-mover rules predict the queue after the active stack, so they
    # leave it out (state.last_side is already its side). The older modes
    # sort it in and then move it to the front, as they always have.
    last = state.last_side
    if pol.speed_tie == "alternate_last_mover":
        main_sorted, last = _last_mover_sorted(
            [s for s in main if s.id != act], last, True)
    else:
        main_sorted = [s for s in _speed_sorted(state, main) if s.id != act]
        if main_sorted:
            last = main_sorted[-1].side
    main_ids = [s.id for s in main_sorted]
    if pol.wait_order == "fifo":
        alive_wait = set(s.id for s in wait)
        wait_ids = [i for i in state.waited if i in alive_wait]
    elif pol.wait_order == "slow_first_alternate":
        wait_ids = [s.id for s in _last_mover_sorted(
            [s for s in wait if s.id != act], last, False)[0]]
    else:
        wait_ids = [s.id for s in _speed_sorted(state, wait)]
        if pol.wait_order == "reverse_speed":
            wait_ids.reverse()
    order = [i for i in main_ids + wait_ids if i != act]
    if act is not None:
        # The active stack leads; during a morale bonus turn it is already
        # in ``done`` but still acts first.
        order.insert(0, act)
    return tuple(order)


def round_order(state):
    """All living stacks for the current round: finished ones (in the order
    they finished) followed by the pending queue. Each exactly once."""
    alive = set(s.id for s in _living(state))
    finished = [i for i in state.done if i in alive]
    pending = [i for i in turn_order(state) if i not in set(finished)]
    return tuple(finished + pending)


def effective_morale(stack):
    if stack.creature.no_morale:
        return 0
    return max(-3, min(3, stack.morale))


def defend_bonus(state, stack):
    p = state.policy
    hero = state.heroes[stack.side]
    base = stack.creature.defense + (hero.defense if hero else 0)
    num = base * p.defend_bonus_num
    if p.defend_bonus_rounding == "floor":
        b = num // p.defend_bonus_den
    else:
        b = -(-num // p.defend_bonus_den)
    return max(p.defend_bonus_min, b)


# --------------------------------------------------------------------------
# Canonical form and hashing
# --------------------------------------------------------------------------

_OMIT_WHEN_DEFAULT = ()
_DEFAULT_POLICY_DICT = asdict(DEFAULT_POLICY)


def canonical(state):
    """Canonical byte form of the state (used for hashing, saves, sync)."""
    data = asdict(state)
    # Policy fields added after the golden hash was last pinned are listed in
    # _OMIT_WHEN_DEFAULT and left out while they hold their default, so older
    # states keep their hash. The list is empty right after a re-pin: every
    # current field (default or not) is part of the canonical form.
    for name in _OMIT_WHEN_DEFAULT:
        if data["policy"].get(name) == _DEFAULT_POLICY_DICT[name]:
            data["policy"].pop(name)
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def state_hash(state):
    return hashlib.sha256(canonical(state)).hexdigest()


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def _set(state, stack):
    stacks = list(state.stacks)
    stacks[stack.id] = stack
    return replace(state, stacks=tuple(stacks))


def _chance(rng, frac):
    return rng.chance(frac.numerator, frac.denominator)


def strike_context(state, att, dfn, ranged):
    """``rules.DamageCtx`` for one strike of stack ``att`` on stack ``dfn``.

    The single place battle state becomes damage inputs: execution
    (``_strike``) and every preview (``strike_preview``, the AI) use it.
    """
    pol = state.policy
    ha = state.heroes[att.side]
    hd = state.heroes[dfn.side]
    A = att.creature.attack + (ha.attack if ha else 0)
    D = dfn.creature.defense + (hd.defense if hd else 0)
    if dfn.defending:
        D += defend_bonus(state, dfn)
    range_pen = False
    if ranged and not att.creature.no_range_penalty:
        off = pol.row_offset
        origin = (att.pos,) if pol.range_origin == "head" else cells(att)
        dist = min(hex_distance(x, y, off) for x in origin for y in cells(dfn))
        range_pen = dist > pol.range_penalty_beyond
    melee_pen = (not ranged) and att.creature.shooter and not att.creature.no_melee_penalty
    return rules.DamageCtx(
        att.count, att.creature.dmg_min, att.creature.dmg_max, A, D,
        ranged=ranged,
        offense=ha.offense if ha else 0,
        archery=ha.archery if ha else 0,
        armorer=hd.armorer if hd else 0,
        hates=dfn.creature.name in att.creature.hates,
        range_penalty=range_pen, melee_penalty=melee_pen,
        luck=att.luck, bad_luck=pol.bad_luck)


def strike_preview(state, att_id, def_id, ranged):
    """``rules.DamagePreview`` (floor, expected, ceiling) of one strike.

    Same pipeline as execution; consumes no RNG. The damage ``apply`` deals
    for that strike always lies in [floor, ceiling].
    """
    return rules.preview_damage(
        strike_context(state, state.stacks[att_id], state.stacks[def_id], ranged))


def _strike(state, att_id, def_id, ranged, retaliation, rng, events):
    """One strike (luck roll, damage rolls, apply). Returns new state."""
    a = state.stacks[att_id]
    d = state.stacks[def_id]
    res = rules.resolve_damage(strike_context(state, a, d, ranged),
                               rules.RollPolicy.ACTUAL_SEED, rng)
    if res.lucky:
        events.append(LuckRolled(a.id, True))
    if res.unlucky:
        events.append(LuckRolled(a.id, False))
    dmg = res.damage
    count, top, killed = rules.apply_damage(d.count, d.top_hp, d.creature.hp, dmg)
    state = _set(state, replace(d, count=count, top_hp=top,
                                defending=d.defending if count else False))
    events.append(DamageDealt(a.id, d.id, dmg, killed, ranged, retaliation))
    if count == 0:
        events.append(UnitDied(d.id))
    return state


def _melee(state, att_id, def_id, rng, events):
    state = _strike(state, att_id, def_id, False, False, rng, events)
    d = state.stacks[def_id]
    a = state.stacks[att_id]
    if d.alive and not a.creature.no_enemy_retaliation:
        if d.creature.unlimited_retaliation or d.retaliations > 0:
            if not d.creature.unlimited_retaliation:
                state = _set(state, replace(d, retaliations=d.retaliations - 1))
            state = _strike(state, def_id, att_id, False, True, rng, events)
    a = state.stacks[att_id]
    d = state.stacks[def_id]
    if a.creature.strikes_twice and a.alive and d.alive:
        state = _strike(state, att_id, def_id, False, False, rng, events)
    return state


def _check_end(state, events):
    sides = set(s.side for s in _living(state))
    if len(sides) == 2:
        return state, False
    # Both sides empty is unreachable: only the active stack's target dies in
    # one action and retaliation cannot kill the whole of both armies at once
    # (a dead attacker's side keeps the target's side alive, and vice versa).
    # The DEFENDER fallback is defensive only.
    winner = sides.pop() if sides else DEFENDER
    events.append(BattleEnded(winner))
    return replace(state, winner=winner, active=None, bonus_turn=False,
                   morale_pending=False), True


def _activate_next(state, rng, events):
    """Pick the next stack to act, starting new rounds and rolling morale."""
    while True:
        order = [i for i in turn_order(replace(state, active=None))]
        if not order:
            stacks = tuple(replace(s, retaliations=1) if s.alive else s
                           for s in state.stacks)
            state = replace(state, round=state.round + 1, done=(), waited=(),
                            stacks=stacks)
            events.append(RoundStarted(state.round))
            continue
        sid = order[0]
        st = state.stacks[sid]
        if st.defending:
            st = replace(st, defending=False)
            state = _set(state, st)
        phase = "wait" if sid in state.waited else "main"
        state = replace(state, active=sid, bonus_turn=False, morale_pending=False,
                        last_side=st.side)
        events.append(TurnStarted(sid, phase, False))
        m = effective_morale(st)
        pol = state.policy
        if phase == "wait":
            if m < 0 and not pol.bad_morale_on_wait_activation:
                m = 0
            if m > 0 and not pol.good_morale_on_wait_activation:
                m = 0
        if m < 0 and _chance(rng, rules.bad_morale_chance(m, pol.bad_morale_table)):
            events.append(MoraleFrozen(sid))
            state = replace(state, done=state.done + (sid,), active=None)
            continue
        if m > 0:
            state = replace(state, morale_pending=_chance(rng, rules.good_morale_chance(m)))
        return state


def _finish_turn(state, kind, rng, events):
    state, over = _check_end(state, events)
    if over:
        return state
    sid = state.active
    st = state.stacks[sid]
    pol = state.policy
    if kind == "wait":
        allowed = pol.good_morale_after_wait
    elif kind == "defend":
        allowed = pol.good_morale_after_defend
    else:
        allowed = True
    if kind == "wait":
        state = replace(state, waited=state.waited + (sid,))
    elif sid not in state.done:
        state = replace(state, done=state.done + (sid,))
    if state.morale_pending and allowed and st.alive:
        if kind == "wait":
            # The wait is consumed by the bonus action: the stack is done after it.
            state = replace(state, done=state.done + (sid,))
        events.append(MoraleBoost(sid))
        state = replace(state, bonus_turn=True, morale_pending=False)
        phase = "wait" if sid in state.waited else "main"
        events.append(TurnStarted(sid, phase, True))
        m = effective_morale(st)
        if pol.repeat_good_morale and m > 0:
            state = replace(state, morale_pending=_chance(rng, rules.good_morale_chance(m)))
        return state
    state = replace(state, active=None, bonus_turn=False, morale_pending=False)
    return _activate_next(state, rng, events)


def _as_hex(v):
    """A command hex as a ``(col, row)`` tuple of ints, else IllegalCommand.
    Rejects non-pairs (no TypeError) and floats/bools (they would compare
    equal to a reachable hex and then reach the state)."""
    if isinstance(v, (tuple, list)) and len(v) == 2 and all(type(c) is int for c in v):
        return tuple(v)
    raise IllegalCommand("not a hex: %r" % (v,))


def _validate(state, cmd):
    """Raise IllegalCommand, or return precomputed data for the command."""
    if state.rules_hash != rules.RULES_HASH:
        raise PackMismatch("state rules_hash %s differs from the local rules pack %s"
                           % (state.rules_hash, rules.RULES_HASH))
    if isinstance(cmd, Begin):
        if state.started:
            raise IllegalCommand("battle already started")
        return None
    if not state.started:
        raise IllegalCommand("battle not started")
    if state.winner is not None:
        raise IllegalCommand("battle is over")
    sid = getattr(cmd, "stack", None)
    if sid != state.active:
        raise IllegalCommand("stack %r is not the active stack" % (sid,))
    st = state.stacks[sid]
    off = state.policy.row_offset
    if isinstance(cmd, Wait):
        if sid in state.waited or state.bonus_turn:
            raise IllegalCommand("cannot wait now")
        return None
    if isinstance(cmd, Defend):
        return None
    if isinstance(cmd, Move):
        dest = _as_hex(cmd.dest)
        reach = _reach(state, st)
        if dest not in reach:
            raise IllegalCommand("destination not reachable")
        return reach[dest]
    if isinstance(cmd, (Attack, Shoot)):
        if not (isinstance(cmd.target, int) and 0 <= cmd.target < len(state.stacks)):
            raise IllegalCommand("no such target")
        tgt = state.stacks[cmd.target]
        if not tgt.alive or tgt.side == st.side:
            raise IllegalCommand("invalid target")
        if isinstance(cmd, Shoot):
            if not st.creature.shooter or st.shots <= 0:
                raise IllegalCommand("cannot shoot")
            if _enemy_adjacent(state, st):
                raise IllegalCommand("enemy adjacent: must melee")
            return None
        head = st.pos if cmd.from_hex is None else _as_hex(cmd.from_hex)
        if head == st.pos:
            path = ()
        else:
            reach = _reach(state, st)
            if head not in reach:
                raise IllegalCommand("attack hex not reachable")
            path = reach[head]
        mine = _cells_at(head, st.side, st.creature.double_wide)
        if not _adjacent_cells(mine, cells(tgt), off):
            raise IllegalCommand("target not adjacent to attack hex")
        return head, path
    raise IllegalCommand("unknown command %r" % (cmd,))


def apply(state, cmd, rng):
    """Apply one command. Returns (new_state, events). Pure in ``state``;
    draws from ``rng`` (the ``battle:<id>`` stream) in the documented order."""
    data = _validate(state, cmd)
    events = []
    if isinstance(cmd, Begin):
        state = replace(state, started=True, round=1)
        events.append(BattleStarted(state.battle_id))
        events.append(RoundStarted(1))
        state = _activate_next(state, rng, events)
        return state, tuple(events)
    st = state.stacks[cmd.stack]
    if isinstance(cmd, Wait):
        events.append(Waited(st.id))
        kind = "wait"
    elif isinstance(cmd, Defend):
        state = _set(state, replace(st, defending=True))
        events.append(Defended(st.id))
        kind = "defend"
    elif isinstance(cmd, Move):
        state = _set(state, replace(st, pos=tuple(cmd.dest)))
        events.append(Moved(st.id, (st.pos,) + data))
        kind = "move"
    elif isinstance(cmd, Shoot):
        shots = 2 if st.creature.shoots_twice else 1
        for i in range(shots):
            cur = state.stacks[st.id]
            if cur.shots <= 0 or not state.stacks[cmd.target].alive:
                break
            state = _set(state, replace(cur, shots=cur.shots - 1))
            state = _strike(state, st.id, cmd.target, True, False, rng, events)
        kind = "shoot"
    else:  # Attack
        head, path = data
        if path:
            state = _set(state, replace(st, pos=head))
            events.append(Moved(st.id, (st.pos,) + path))
        state = _melee(state, st.id, cmd.target, rng, events)
        kind = "attack"
    state = _finish_turn(state, kind, rng, events)
    return state, tuple(events)


def legal_commands(state):
    """Every legal command in the current state (deterministic order)."""
    if not state.started:
        return (Begin(),)
    if state.winner is not None or state.active is None:
        return ()
    st = state.stacks[state.active]
    out = []
    if st.id not in state.waited and not state.bonus_turn:
        out.append(Wait(st.id))
    out.append(Defend(st.id))
    reach = _reach(state, st)
    for h in sorted(reach):
        out.append(Move(st.id, h))
    off = state.policy.row_offset
    heads = [st.pos] + sorted(reach)
    can_shoot = st.creature.shooter and st.shots > 0 and not _enemy_adjacent(state, st)
    for tgt in state.stacks:
        if not tgt.alive or tgt.side == st.side:
            continue
        if can_shoot:
            out.append(Shoot(st.id, tgt.id))
        for h in heads:
            mine = _cells_at(h, st.side, st.creature.double_wide)
            if _adjacent_cells(mine, cells(tgt), off):
                out.append(Attack(st.id, tgt.id, None if h == st.pos else h))
    return tuple(out)
