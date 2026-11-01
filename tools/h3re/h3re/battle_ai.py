"""Greedy battle AI for playtesting (not part of the simulation rules).

``choose(state, side=None) -> Command`` returns one command from
``battle.legal_commands(state)``. It never draws from the battle RNG stream:
damage is previewed without randomness (``rules.resolve_damage`` with
``RollPolicy.EXPECTED``, the same function execution runs) and
ties are broken with a separate stream ``derive_stream(seed, "ai:<side>")``.

Policy: attack/shoot with the best expected net damage (damage dealt, capped
by what the target has left, minus expected retaliation); otherwise move
toward the nearest enemy; otherwise Defend, but never more than
``MAX_DEFENDS`` times in a row (then Wait, or the closest Move, to avoid
stalls).
"""

from . import battle as B
from . import rules
from .rng import derive_stream

__all__ = ["choose", "GreedyAI", "MAX_DEFENDS"]

MAX_DEFENDS = 2
_STATELESS_DEFEND_ROUND = 8  # module-level choose(): no memory, so cap by round


def _stack_hp(s):
    return (s.count - 1) * s.creature.hp + s.top_hp if s.count > 0 else 0


def _preview(state, att, dfn, ranged):
    """No-RNG expected final damage of one strike of ``att`` on ``dfn``.

    The shared pipeline (``battle.strike_context`` + ``rules.resolve_damage``
    under EXPECTED) that execution also runs; no local copy of the rules.
    """
    return rules.resolve_damage(B.strike_context(state, att, dfn, ranged),
                                rules.RollPolicy.EXPECTED).damage


def _score_attack(state, att, cmd):
    tgt = state.stacks[cmd.target]
    ranged = isinstance(cmd, B.Shoot)
    shots = 2 if ranged and att.creature.shoots_twice else 1
    if not ranged and att.creature.strikes_twice:
        shots = 2
    dealt = min(_preview(state, att, tgt, ranged) * shots, _stack_hp(tgt))
    value = dealt
    if not ranged and dealt < _stack_hp(tgt) and not att.creature.no_enemy_retaliation \
            and (tgt.creature.unlimited_retaliation or tgt.retaliations > 0):
        count, top, _ = rules.apply_damage(tgt.count, tgt.top_hp, tgt.creature.hp, dealt)
        if count > 0:
            r = B.replace(tgt, count=count, top_hp=top)
            value -= min(_preview(state, r, att, False), _stack_hp(att))
    elif dealt >= _stack_hp(tgt):
        value += 1  # a kill removes the target's future damage
    return value


def _enemy_dist(state, st, head):
    off = state.policy.row_offset
    mine = B._cells_at(head, st.side, st.creature.double_wide)
    return min(B.hex_distance(a, b, off)
               for e in state.stacks if e.alive and e.side != st.side
               for a in mine for b in B.cells(e))


def _pick(cands, rng):
    return cands[0] if len(cands) == 1 else cands[rng.range(0, len(cands))]


def _decide(state, side, defends, rng_factory, stateless):
    legal = B.legal_commands(state)
    if not legal:
        raise ValueError("no legal commands (battle over)")
    if not state.started:
        return legal[0]
    st = state.stacks[state.active]
    if side is not None and st.side != side:
        raise ValueError("active stack belongs to side %r, not %r" % (st.side, side))
    rng = None

    def pick(c):
        nonlocal rng
        if len(c) > 1 and rng is None:
            rng = rng_factory(st.side)
        return _pick(c, rng)

    attacks = [(c, _score_attack(state, st, c)) for c in legal
               if isinstance(c, (B.Attack, B.Shoot))]
    if attacks:
        best = max(s for _, s in attacks)
        return pick([c for c, s in attacks if s == best])

    cur = _enemy_dist(state, st, st.pos)
    moves = [(c, _enemy_dist(state, st, c.dest)) for c in legal if isinstance(c, B.Move)]
    if moves:
        d = min(x for _, x in moves)
        if d < cur:
            return pick([c for c, x in moves if x == d])
    stalled = (state.round > _STATELESS_DEFEND_ROUND) if stateless else (defends >= MAX_DEFENDS)
    if not stalled:
        return B.Defend(st.id)
    waits = [c for c in legal if isinstance(c, B.Wait)]
    if waits:
        return waits[0]
    if moves:
        d = min(x for _, x in moves)
        return pick([c for c, x in moves if x == d])
    return B.Defend(st.id)


class GreedyAI:
    """Stateful greedy chooser: tracks consecutive Defends per side."""

    def __init__(self, side_seed):
        self.seed = side_seed
        self._streams = {}
        self._defends = {0: 0, 1: 0}

    def _stream(self, side):
        if side not in self._streams:
            self._streams[side] = derive_stream(self.seed, "ai:%d" % side)
        return self._streams[side]

    def choose(self, state, side=None):
        cmd = _decide(state, side, self._defends.get(
            state.stacks[state.active].side if state.active is not None else 0, 0),
            self._stream, False)
        if state.started and state.active is not None:
            s = state.stacks[state.active].side
            self._defends[s] = self._defends[s] + 1 if isinstance(cmd, B.Defend) else 0
        return cmd


def choose(state, side=None):
    """Stateless greedy choice (tie-break stream seeded from the state hash)."""
    seed = int(B.state_hash(state)[:16], 16)
    return _decide(state, side, 0, lambda s: derive_stream(seed, "ai:%d" % s), True)
