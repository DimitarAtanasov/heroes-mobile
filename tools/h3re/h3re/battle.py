"""Reference simulation core for field battles (no spells, no siege, no AI).

Spec: docs/specs/battle.md (built on rules.md section 6 and engine-design.md
section 1.3). Clean-room: written from those specs only.

Design:

* State is immutable (frozen dataclasses, tuples, ints, strings, bools).
* ``apply(state, cmd, rng) -> (state', events)`` is the only way to advance a
  battle. An illegal command raises ``IllegalCommand`` *before* any RNG draw,
  so neither the state nor the stream is touched.
* No floats. Damage is computed by ``rules.py`` (exact fractions, one floor).
* Randomness comes only from the ``rng`` argument, which should be the
  ``rng.py`` stream ``battle:<battle_id>`` (see ``battle_rng``).
* Every rule that rules.md tags [uncertain] is a field of ``BattlePolicy``;
  the policy is stored in the state (and therefore in the state hash).
"""

import hashlib
import json
from collections import deque
from dataclasses import asdict, dataclass, replace

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
    "defend_bonus", "effective_morale",
]

WIDTH = 17
HEIGHT = 11
ATTACKER = 0
DEFENDER = 1


# --------------------------------------------------------------------------
# Policy: every [uncertain] rule of rules.md section 6 that is in scope.
# --------------------------------------------------------------------------

_DEFAULT_PLACEMENT = (
    (5,),
    (2, 8),
    (2, 5, 8),
    (0, 4, 6, 10),
    (0, 2, 5, 8, 10),
    (0, 2, 4, 6, 8, 10),
    (0, 2, 4, 5, 6, 8, 10),
)


@dataclass(frozen=True)
class BattlePolicy:
    """Switchable rules. Defaults are the documented / commonly cited choice.

    All fields are [uncertain] in rules.md; see docs/specs/battle.md.
    """

    # 6.1 geometry: which rows are shifted half a hex to the right.
    row_offset: str = "odd"            # "odd" | "even"
    # 6.1 geometry: may ordinary stacks use the war-machine edge columns?
    edge_columns_walkable: bool = False
    # 6.1 initial placement: rows per army size (index = n_stacks - 1).
    placement_rows: tuple = _DEFAULT_PLACEMENT
    # 6.3 speed ties: "attacker_first" (side, then slot) | "alternate".
    speed_tie: str = "attacker_first"
    # 6.3 order within the wait phase: "reverse_speed" | "speed" | "fifo".
    wait_order: str = "reverse_speed"
    # 6.3 defend bonus: num/den of Defense, at least ``min``, rounding mode.
    defend_bonus_num: int = 1
    defend_bonus_den: int = 5
    defend_bonus_min: int = 1
    defend_bonus_rounding: str = "floor"   # "floor" | "ceil"
    # 6.5 good morale after Wait / Defend, repeated triggers.
    good_morale_after_wait: bool = False
    good_morale_after_defend: bool = False
    repeat_good_morale: bool = False
    # 6.5 bad luck (|L|/24 chance to halve damage, after the final floor).
    bad_luck: bool = False
    # 6.6 R_range: penalty when distance > this many hexes.
    range_penalty_beyond: int = 10

    def __post_init__(self):
        if self.row_offset not in ("odd", "even"):
            raise ValueError("row_offset must be 'odd' or 'even'")
        if self.speed_tie not in ("attacker_first", "alternate"):
            raise ValueError("bad speed_tie")
        if self.wait_order not in ("reverse_speed", "speed", "fifo"):
            raise ValueError("bad wait_order")
        if self.defend_bonus_rounding not in ("floor", "ceil"):
            raise ValueError("bad defend_bonus_rounding")
        if self.defend_bonus_den <= 0 or self.defend_bonus_num < 0:
            raise ValueError("bad defend bonus fraction")
        if len(self.placement_rows) != 7 or any(
                len(rows) != i + 1 for i, rows in enumerate(self.placement_rows)):
            raise ValueError("placement_rows needs 7 rows tuples of size 1..7")
        if self.range_penalty_beyond < 0:
            raise ValueError("bad range_penalty_beyond")


DEFAULT_POLICY = BattlePolicy()


# --------------------------------------------------------------------------
# Hex geometry: 17 x 11 offset grid, hexes are (col, row) tuples.
# --------------------------------------------------------------------------

_AXIAL_DIRS = ((1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (-1, 1))


def in_grid(h):
    c, r = h
    return 0 <= c < WIDTH and 0 <= r < HEIGHT


def to_axial(h, row_offset="odd"):
    c, r = h
    if row_offset == "odd":
        return c - (r - (r & 1)) // 2, r
    return c - (r + (r & 1)) // 2, r


def from_axial(q, r, row_offset="odd"):
    if row_offset == "odd":
        return q + (r - (r & 1)) // 2, r
    return q + (r + (r & 1)) // 2, r


def neighbours(h, row_offset="odd"):
    """Sorted tuple of in-grid neighbours of hex ``h`` (at most 6)."""
    q, r = to_axial(h, row_offset)
    out = []
    for dq, dr in _AXIAL_DIRS:
        n = from_axial(q + dq, r + dr, row_offset)
        if in_grid(n):
            out.append(n)
    return tuple(sorted(out))


def hex_distance(a, b, row_offset="odd"):
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


class IllegalCommand(ValueError):
    """Command rejected; state and RNG are untouched."""


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
    return BattleState(battle_id=str(battle_id), policy=policy,
                       heroes=tuple(heroes), obstacles=obs, stacks=tuple(stacks))


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


def turn_order(state):
    """Ids still to act this round, in order (the active stack first)."""
    living = _living(state)
    done = set(state.done)
    waited = set(state.waited)
    main = [s for s in living if s.id not in done and s.id not in waited]
    wait = [s for s in living if s.id in waited and s.id not in done]
    main_ids = [s.id for s in _speed_sorted(state, main)]
    pol = state.policy.wait_order
    if pol == "fifo":
        alive_wait = set(s.id for s in wait)
        wait_ids = [i for i in state.waited if i in alive_wait]
    else:
        wait_ids = [s.id for s in _speed_sorted(state, wait)]
        if pol == "reverse_speed":
            wait_ids.reverse()
    order = main_ids + wait_ids
    act = state.active
    if act is not None and state.stacks[act].alive:
        # The active stack leads; during a morale bonus turn it is already
        # in ``done`` but still acts first.
        if act in order:
            order.remove(act)
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

def canonical(state):
    """Canonical byte form of the state (used for hashing, saves, sync)."""
    return json.dumps(asdict(state), sort_keys=True, separators=(",", ":")).encode("utf-8")


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


def _strike(state, att_id, def_id, ranged, retaliation, rng, events):
    """One strike (luck roll, damage rolls, apply). Returns new state."""
    a = state.stacks[att_id]
    d = state.stacks[def_id]
    pol = state.policy
    ha = state.heroes[a.side]
    hd = state.heroes[d.side]
    A = a.creature.attack + (ha.attack if ha else 0)
    D = d.creature.defense + (hd.defense if hd else 0)
    if d.defending:
        D += defend_bonus(state, d)
    lucky = unlucky = False
    if a.luck > 0:
        lucky = _chance(rng, rules.luck_chance(a.luck))
        if lucky:
            events.append(LuckRolled(a.id, True))
    elif a.luck < 0 and pol.bad_luck:
        unlucky = _chance(rng, rules.luck_chance(-a.luck))
        if unlucky:
            events.append(LuckRolled(a.id, False))
    base = rules.base_damage(a.count, a.creature.dmg_min, a.creature.dmg_max, rng)
    range_pen = False
    if ranged and not a.creature.no_range_penalty:
        off = pol.row_offset
        dist = min(hex_distance(x, y, off) for x in cells(a) for y in cells(d))
        range_pen = dist > pol.range_penalty_beyond
    melee_pen = (not ranged) and a.creature.shooter and not a.creature.no_melee_penalty
    dmg = rules.damage_from_base(
        base, A, D, ranged=ranged,
        offense=ha.offense if ha else 0,
        archery=ha.archery if ha else 0,
        armorer=hd.armorer if hd else 0,
        lucky=lucky, hates=d.creature.name in a.creature.hates,
        range_penalty=range_pen, melee_penalty=melee_pen)
    if unlucky:
        dmg = max(1, dmg // 2)
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
        state = replace(state, active=sid, bonus_turn=False, morale_pending=False)
        events.append(TurnStarted(sid, phase, False))
        m = effective_morale(st)
        if m < 0 and _chance(rng, rules.bad_morale_chance(m)):
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


def _validate(state, cmd):
    """Raise IllegalCommand, or return precomputed data for the command."""
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
        reach = _reach(state, st)
        dest = tuple(cmd.dest)
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
        if cmd.from_hex is None or tuple(cmd.from_hex) == st.pos:
            head, path = st.pos, ()
        else:
            reach = _reach(state, st)
            head = tuple(cmd.from_hex)
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
