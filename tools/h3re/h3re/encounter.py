"""Adventure-map encounters: a hero attacks a neighbouring enemy hero or a
neutral guard, the fight is a ``battle.py`` battle, survivors flow back.

Spec: docs/specs/encounter.md (and adventure.md section 8). Clean-room:
written from those specs only.

* The entry point is ``adventure.apply(state, adventure.Attack(hero, target),
  rng)``. It calls ``validate`` (every check, before any draw) and then
  ``resolve``. An illegal Attack raises ``adventure.IllegalCommand`` with the
  state and the stream untouched.
* ``rng`` for an Attack is the battle's named stream ``battle:<battle_id>``
  derived from the game's master seed (``encounter_rng``; ``stream_for``
  picks the right stream for any adventure command). Only the battle draws
  from it; the auto-combat chooser (``auto_command``) draws nothing.
* No floats; the battle does all arithmetic (``rules.py``).
* Every unverified rule is a field of ``EncounterPolicy``, which is stored in
  the game state (``GameState.encounter``) and so in its hash.
"""

from dataclasses import dataclass, replace

from . import adventure as A
from . import battle as B
from . import rules

__all__ = [
    "LOSER_FATES", "SLOT_MAPPINGS", "EncounterPolicy", "DEFAULT_POLICY",
    "EncounterSetup", "BattleFought", "ArmyChanged", "HeroDefeated",
    "GuardDefeated", "battle_id", "encounter_rng", "stream_for", "check_game",
    "validate", "build_battle", "auto_command", "fight", "resolve",
]

LOSER_FATES = ("removed", "winner_takes_tile")
SLOT_MAPPINGS = ("by_count", "by_slot")


@dataclass(frozen=True)
class EncounterPolicy:
    """Switchable encounter rules; see docs/specs/encounter.md section 5."""

    # [uncertain] What becomes of the loser's tile. The loser (no army left)
    # always leaves the map. "removed": the winner stays where it stood.
    # "winner_takes_tile": an attacking winner moves onto the freed tile
    # (no point cost).
    loser_fate: str = "removed"
    # [uncertain] Army slot -> battle stack placement. Slot i is always stack
    # slot i and its survivors return to slot i. "by_count": the battle
    # policy's placement table for the army size. "by_slot": slot i stands
    # on row placement_rows[6][i] (the 7-stack row of its own index).
    slot_mapping: str = "by_count"
    # [engine] Safety cap: a battle still running when this round starts
    # ends with no winner (both sides keep their survivors).
    round_limit: int = 100

    def __post_init__(self):
        if self.loser_fate not in LOSER_FATES:
            raise ValueError("bad loser_fate")
        if self.slot_mapping not in SLOT_MAPPINGS:
            raise ValueError("bad slot_mapping")
        if type(self.round_limit) is not int or self.round_limit < 1:
            raise ValueError("round_limit must be an int >= 1")


DEFAULT_POLICY = EncounterPolicy()


@dataclass(frozen=True)
class EncounterSetup:
    """What a game needs to fight battles. Stored in ``GameState.encounter``.

    ``creatures``: ``battle.Creature`` per army creature id (``name`` is the
    id; its ``speed`` must equal the ``ArmySlot.speed``). Sorted by name on
    construction, so equal setups have one canonical form.
    ``rules_hash``: the rules pack the game was set up under (ADR-0001); an
    Attack under a different local pack is refused before any draw.
    """

    creatures: tuple
    policy: EncounterPolicy = DEFAULT_POLICY
    battle_policy: B.BattlePolicy = B.DEFAULT_POLICY
    rules_hash: str = rules.RULES_HASH

    def __post_init__(self):
        if not all(isinstance(c, B.Creature) for c in self.creatures):
            raise ValueError("creatures must be battle.Creature values")
        cs = tuple(sorted(self.creatures, key=lambda c: c.name))
        if len(set(c.name for c in cs)) != len(cs):
            raise ValueError("duplicate creature name")
        if not isinstance(self.policy, EncounterPolicy):
            raise ValueError("policy must be an EncounterPolicy")
        if not isinstance(self.battle_policy, B.BattlePolicy):
            raise ValueError("battle_policy must be a battle.BattlePolicy")
        object.__setattr__(self, "creatures", cs)


# Events ----------------------------------------------------------------

@dataclass(frozen=True)
class BattleFought:
    battle_id: str
    attacker: int             # hero id
    target: object            # hero id (int) or guard id (str)
    winner: object            # battle.ATTACKER, battle.DEFENDER, None (round limit)
    rounds: int               # round the battle ended in (round_limit if none won)
    log: tuple                # battle commands applied, Begin first
    battle_events: tuple      # every battle event, in order (for the presenter)
    battle_hash: str          # battle.state_hash of the final battle state


@dataclass(frozen=True)
class ArmyChanged:
    unit: object              # hero id (int) or guard id (str)
    army: tuple               # survivors, ArmySlot


@dataclass(frozen=True)
class HeroDefeated:
    hero: int


@dataclass(frozen=True)
class GuardDefeated:
    guard: str


# Streams ---------------------------------------------------------------

def battle_id(state):
    """Id of the next battle in this game: ``<game_id>:<n>``, n = 1, 2, ..."""
    return "%s:%d" % (state.game_id, state.battles + 1)


def encounter_rng(master_seed, state):
    """The next battle's named stream ``battle:<battle_id(state)>``."""
    return B.battle_rng(master_seed, battle_id(state))


def stream_for(master_seed, state, cmd):
    """The stream ``adventure.apply(state, cmd, rng)`` expects: the battle
    stream for an Attack, the ``adventure:<game_id>`` stream otherwise."""
    if isinstance(cmd, A.Attack):
        return encounter_rng(master_seed, state)
    return A.adventure_rng(master_seed, state.game_id)


# Setup checks ----------------------------------------------------------

def _creature(setup, slot):
    """The battle creature for an army slot, or None (unknown or speed differs)."""
    for c in setup.creatures:
        if c.name == slot.creature:
            return c if c.speed == slot.speed else None
    return None


def check_game(state):
    """ValueError unless every army on the map has content in the setup."""
    setup = state.encounter
    if not isinstance(setup, EncounterSetup):
        raise ValueError("encounter must be an EncounterSetup")
    units = [("hero %d" % h.id, h.army) for h in state.heroes]
    units += [("guard %r" % (g.id,), g.army) for g in state.guards]
    for what, army in units:
        for slot in army:
            if _creature(setup, slot) is None:
                raise ValueError("%s: no creature %r with speed %d in the setup"
                                 % (what, slot.creature, slot.speed))


# Validation (no draws) -------------------------------------------------

def _guard(state, gid):
    for i, g in enumerate(state.guards):
        if g.id == gid:
            return i, g
    return None, None


def _stack_setups(setup, army, side):
    out = []
    for i, slot in enumerate(army):
        cr = _creature(setup, slot)
        if cr is None:
            raise A.IllegalCommand("no content for creature %r" % (slot.creature,))
        pos = None
        if setup.policy.slot_mapping == "by_slot":
            wide = 1 if cr.double_wide else 0
            col = 1 + wide if side == B.ATTACKER else B.WIDTH - 2 - wide
            pos = (col, setup.battle_policy.placement_rows[6][i])
        out.append(B.StackSetup(cr, slot.count, pos=pos))
    return out


def validate(state, cmd):
    """Check an ``adventure.Attack`` and build its battle. Returns the
    initial ``BattleState``; raises ``adventure.IllegalCommand`` otherwise.
    Draws nothing (``adventure._validate`` has checked the game started)."""
    setup = state.encounter
    if setup is None:
        raise A.IllegalCommand("battles are not enabled in this game")
    if setup.rules_hash != rules.RULES_HASH:
        raise A.IllegalCommand("game rules_hash %s differs from the local rules pack %s"
                               % (setup.rules_hash, rules.RULES_HASH))
    hid = cmd.hero
    if type(hid) is not int or not 0 <= hid < len(state.heroes):
        raise A.IllegalCommand("no such hero")
    hero = state.heroes[hid]
    if hero.owner != state.current:
        raise A.IllegalCommand("hero does not belong to the current player")
    if hero.pos is None:
        raise A.IllegalCommand("hero is not on the map")
    t = cmd.target
    if type(t) is int:
        if not 0 <= t < len(state.heroes) or t == hid:
            raise A.IllegalCommand("no such target hero")
        foe = state.heroes[t]
        if foe.pos is None:
            raise A.IllegalCommand("target hero is not on the map")
        if foe.owner == hero.owner:
            raise A.IllegalCommand("cannot attack an own hero")
        pos, army, foe_hero = foe.pos, foe.army, B.Hero()
    elif type(t) is str:
        _, guard = _guard(state, t)
        if guard is None:
            raise A.IllegalCommand("no such guard")
        pos, army, foe_hero = guard.pos, guard.army, None
    else:
        raise A.IllegalCommand("target must be a hero id or a guard id")
    if A.step_cost(state.grid, hero.pos, pos, hero.pathfinding, state.policy) is None:
        raise A.IllegalCommand("target is not next to the hero")
    try:
        return B.create_battle(
            battle_id(state),
            _stack_setups(setup, hero.army, B.ATTACKER),
            _stack_setups(setup, army, B.DEFENDER),
            heroes=(B.Hero(), foe_hero), policy=setup.battle_policy)
    except A.IllegalCommand:
        raise
    except ValueError as e:
        raise A.IllegalCommand("battle cannot be set up: %s" % (e,)) from e


def build_battle(state, cmd):
    """The battle an Attack would fight (no draws, no state change)."""
    return validate(state, cmd)


# The fight -------------------------------------------------------------

def auto_command(bs):
    """Deterministic auto-combat choice (no RNG): the attack or shot with the
    highest expected damage (``battle.strike_preview``), first in
    ``legal_commands`` order on ties; else the move that brings the head
    closest to an enemy cell, if it is closer than now (ties: smallest hex);
    else Defend."""
    legal = B.legal_commands(bs)
    if not bs.started:
        return legal[0]
    st = bs.stacks[bs.active]
    best = None
    seen = {}
    for c in legal:
        if isinstance(c, (B.Attack, B.Shoot)):
            key = (c.target, isinstance(c, B.Shoot))
            if key not in seen:
                seen[key] = B.strike_preview(bs, st.id, c.target, key[1]).expected
            if best is None or seen[key] > best[0]:
                best = (seen[key], c)
    if best is not None:
        return best[1]
    off = bs.policy.row_offset
    foes = [x for e in bs.stacks if e.alive and e.side != st.side for x in B.cells(e)]

    def gap(head):
        return min(B.hex_distance(head, x, off) for x in foes)

    moves = [c for c in legal if isinstance(c, B.Move)]
    if moves:
        m = min(moves, key=lambda c: (gap(c.dest), c.dest))
        if gap(m.dest) < gap(st.pos):
            return m
    return B.Defend(st.id)


def fight(bs, rng, round_limit):
    """Run a battle to its end with ``auto_command`` on ``rng``. Stops with
    no winner when round ``round_limit + 1`` starts. Returns
    (final state, commands, events)."""
    log, events = [], []
    while bs.winner is None and not (bs.started and bs.round > round_limit):
        cmd = auto_command(bs)
        bs, ev = B.apply(bs, cmd, rng)
        log.append(cmd)
        events.extend(ev)
    return bs, tuple(log), tuple(events)


def _survivors(army, bs, side):
    """Army slot i <- battle stack slot i of ``side``; dead slots drop out."""
    stacks = [s for s in bs.stacks if s.side == side]
    return tuple(replace(slot, count=s.count) for slot, s in zip(army, stacks) if s.count > 0)


def _hero_after(h, army, events):
    if not army:
        events.append(HeroDefeated(h.id))
        return replace(h, pos=None, army=(), mp=0, mp_max=0)
    if army != h.army:
        events.append(ArmyChanged(h.id, army))
        return replace(h, army=army)
    return h


def resolve(state, cmd, rng, bs):
    """Fight the battle ``bs`` (from ``validate``) on ``rng`` and apply the
    outcome. Returns (new_state, events)."""
    pol = state.encounter.policy
    end, log, bevents = fight(bs, rng, pol.round_limit)
    events = [BattleFought(bs.battle_id, cmd.hero, cmd.target, end.winner,
                           min(end.round, pol.round_limit), log, bevents,
                           B.state_hash(end))]
    heroes, guards = list(state.heroes), list(state.guards)
    att = heroes[cmd.hero]
    heroes[att.id] = _hero_after(att, _survivors(att.army, end, B.ATTACKER), events)
    if type(cmd.target) is int:
        foe = heroes[cmd.target]
        target_pos = foe.pos
        heroes[foe.id] = _hero_after(foe, _survivors(foe.army, end, B.DEFENDER), events)
    else:
        i, g = _guard(state, cmd.target)
        target_pos = g.pos
        army = _survivors(g.army, end, B.DEFENDER)
        if not army:
            del guards[i]
            events.append(GuardDefeated(g.id))
        elif army != g.army:
            guards[i] = replace(g, army=army)
            events.append(ArmyChanged(g.id, army))
    if end.winner == B.ATTACKER and pol.loser_fate == "winner_takes_tile":
        h = heroes[att.id]
        heroes[att.id] = replace(h, pos=target_pos)
        events.append(A.HeroMoved(h.id, (h.pos, target_pos), 0, h.mp))
    state = replace(state, heroes=tuple(heroes), guards=tuple(guards),
                    battles=state.battles + 1)
    return state, tuple(events)
