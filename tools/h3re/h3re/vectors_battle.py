"""Battle state and apply conformance vectors (battle-port slices 2 and 3), from the Python reference.

``generate()`` returns ``{vector file name: JSON-serialisable content}``; the
orchestrator wires it into ``vectors.generate()`` (which owns serialisation).
Python is authoritative (ADR-0004, docs/specs/conformance.md "Battle state" and
"Battle apply").

Each playout is played by the Python engine from a scenario whose randomness
comes only from ``Pcg32`` streams, with a deterministic driver: the greedy AI,
except that a ``derive_stream`` draw sometimes substitutes a legal Wait or
Defend (and, in the ability playouts, sometimes any legal command) so every
command type occurs. The golden-scripted case replays the pinned golden battle
of ``tests/test_battle.py`` (scripted chooser).

Every step records the battle stream's position: ``rng_u32_before`` (raw
``next_u32`` outputs consumed before the command, counted from the freshly
derived ``battle:<battle_id>`` stream), ``rng_u32`` (consumed by the command),
``rng_state_after`` (generator state after it) and ``rng_calls`` (``randint``
calls for damage, ``chance`` calls for luck and for morale). ``illegal_cases``
are rejected commands with the exception class and message.

Usage:  python3 -m h3re.vectors_battle [--out DIR]
"""

import argparse
import dataclasses
import json
import os
import sys

from . import battle as B
from . import battle_ai
from . import rules as R
from . import soak
from . import vectors as V
from .rng import Pcg32, derive_stream

VECTOR_FORMAT = 1
FILE = "battle_states.json"
MAX_STEPS = 120
ABILITY_MAX_STEPS = 40
BAD_RULES_HASH = "0" * 64

COMMANDS = (B.Begin, B.Move, B.Attack, B.Shoot, B.Wait, B.Defend)
EVENTS = (B.BattleStarted, B.RoundStarted, B.TurnStarted, B.MoraleFrozen, B.MoraleBoost,
          B.Moved, B.Waited, B.Defended, B.LuckRolled, B.DamageDealt, B.UnitDied,
          B.BattleEnded)
DATACLASSES = (B.BattleState, B.BattlePolicy, B.Stack, B.Creature, B.Hero)

# (policy name, seeds): seeds chosen for coverage (one-hex only, shooters and
# flyers, two-hex units, both) under the default and all non-default policies.
PLAYOUTS = (("default", (0, 1, 4, 6)), ("alt-order", (0, 1, 6)),
            ("vcmi-like", (0, 1, 6)), ("strict", (0, 1, 6)))
# Flat playouts: the soak scenarios with every stack's morale and luck set to 0,
# so most attacks and shots involve no morale or luck roll (stage B coverage).
FLAT_PLAYOUTS = (("default", (0,)), ("alt-order", (1,)), ("vcmi-like", (0,)),
                 ("strict", (1,)))
# Ability playouts: synthetic armies with every creature flag (hates,
# shoots_twice, unlimited_retaliation, no_melee/range_penalty, no_morale, ...),
# morale and luck in -3..3, counts above 10, under every policy.
ABILITY_PLAYOUTS = (("default", (1, 4)), ("alt-order", (1,)), ("vcmi-like", (1, 9)),
                    ("strict", (3,)), ("mix-fifo", (1, 7)), ("mix-speed", (4,)),
                    ("mix-alt", (9,)))
# Tie playouts: ability armies with every speed set to 5 or 6, so speed ties
# across sides occur from the first activation (last-mover and alternate rules).
TIE_PLAYOUTS = (("default", (1,)), ("alt-order", (1,)), ("vcmi-like", (1, 2)),
                ("mix-fifo", (2,)), ("mix-alt", (1,)))
TIE_MAX_STEPS = 30
# Wait-heavy tie playouts: the driver waits whenever it may (3 times in 5), so
# whole tie groups enter the wait phase (fifo versus speed order, reversed
# "alternate" ranking).
WAIT_PLAYOUTS = (("mix-fifo", (1, 2, 3)), ("mix-alt-rev", (1, 2, 3)))
# Extra policy combinations (beyond soak.POLICY_MATRIX) for branches the matrix
# leaves out: wait_order "fifo", "alternate_last_mover" with a speed-sorted wait
# phase, "alternate" with "slow_first_alternate", good morale after Wait.
EXTRA_POLICIES = (
    ("mix-fifo", dict(speed_tie="alternate_last_mover", wait_order="fifo",
                      good_morale_after_wait=True, good_morale_after_defend=True,
                      repeat_good_morale=True, bad_luck=True,
                      bad_morale_on_wait_activation=True, good_morale_on_wait_activation=False,
                      defend_bonus_num=1, defend_bonus_den=3, defend_bonus_rounding="ceil")),
    ("mix-speed", dict(speed_tie="alternate_last_mover", wait_order="reverse_speed",
                       row_offset="odd", range_origin="any_cell", range_penalty_beyond=4,
                       edge_columns_walkable=True, good_morale_after_wait=True)),
    ("mix-alt", dict(speed_tie="alternate", wait_order="slow_first_alternate",
                     bad_morale_table=(0, 4, 24), repeat_good_morale=True, bad_luck=True)),
    ("mix-alt-rev", dict(speed_tie="alternate", wait_order="reverse_speed")),
)


class _TracedPcg32(Pcg32):
    """The same generator, counting raw outputs and tagging calls (luck / morale /
    damage) by caller. Output is identical to the wrapped Pcg32."""

    __slots__ = ("u32", "calls")

    @classmethod
    def wrap(cls, g):
        t = cls.__new__(cls)
        t.state, t.inc, t.u32 = g.state, g.inc, 0
        t.calls = {"damage": 0, "luck": 0, "morale": 0}
        return t

    def next_u32(self):
        self.u32 += 1
        return Pcg32.next_u32(self)

    def chance(self, num, den):
        caller = sys._getframe(1).f_code.co_name
        self.calls[{"_settle": "luck", "_chance": "morale"}[caller]] += 1
        return Pcg32.chance(self, num, den)

    def randint(self, lo, hi):
        # Only rules.base_damage calls randint (from a generator expression).
        self.calls["damage"] += 1
        return Pcg32.randint(self, lo, hi)

    def snapshot(self):
        return self.u32, dict(self.calls)


def _jsonable(x):
    return json.loads(json.dumps(x))


def _event_dict(ev):
    d = soak.encode_command(ev)
    return _jsonable(d)


def _text(state):
    return B.canonical(state).decode("ascii")


def _stage(cmd, calls, events):
    """A: Begin/Move/Wait/Defend without morale or luck; B: Attack/Shoot without
    morale or luck; C: any step that rolls (or applies) morale or luck."""
    names = {type(e).__name__ for e in events}
    if calls["luck"] or calls["morale"] or names & {"MoraleFrozen", "MoraleBoost", "LuckRolled"}:
        return "C"
    return "B" if isinstance(cmd, (B.Attack, B.Shoot)) else "A"


def _legal_block(state):
    """Slice 4: the full ordered ``legal_commands(state)`` (encoded) and, for every
    Attack / Shoot candidate, its strike_preview triple and DamageCtx fields.
    Previews are deduplicated per (attacker, target, ranged) in first-seen order
    (melee previews are the same for every attack hex)."""
    legal = B.legal_commands(state)
    previews, seen = [], set()
    for c in legal:
        if not isinstance(c, (B.Attack, B.Shoot)):
            continue
        ranged = isinstance(c, B.Shoot)
        key = (c.stack, c.target, ranged)
        if key in seen:
            continue
        seen.add(key)
        ctx = B.strike_context(state, state.stacks[c.stack], state.stacks[c.target], ranged)
        p = B.strike_preview(state, c.stack, c.target, ranged)
        previews.append({"attacker": c.stack, "target": c.target, "ranged": ranged,
                         "floor": p.floor, "expected": p.expected, "ceiling": p.ceiling,
                         "ctx": _jsonable(dataclasses.asdict(ctx))})
    return {"legal": [_jsonable(soak.encode_command(c)) for c in legal],
            "previews": previews}


def _driver_step(state, ai, drv, any_legal=False, wait_first=False):
    if state.winner is not None:
        return None
    pick = drv.range(0, 5)
    if wait_first and pick < 3:
        for c in B.legal_commands(state):
            if isinstance(c, B.Wait):
                return c
    if pick < 2:
        legal = B.legal_commands(state)
        want = B.Wait if pick == 0 else B.Defend
        for c in legal:
            if isinstance(c, want):
                return c
    if any_legal and pick == 2:
        legal = B.legal_commands(state)
        return legal[drv.range(0, len(legal))]
    return ai.choose(state)


def scripted_choice(state):
    """Mirror of tests/test_battle.py scripted_choice (shoot > attack > advance > defend)."""
    cmds = B.legal_commands(state)
    for kind in (B.Shoot, B.Attack):
        hits = [c for c in cmds if isinstance(c, kind)]
        if hits:
            return hits[0]
    me = state.stacks[state.active]
    enemies = [s for s in state.stacks if s.alive and s.side != me.side]
    moves = [c for c in cmds if isinstance(c, B.Move)]
    if moves:
        return min(moves, key=lambda c: (min(B.hex_distance(c.dest, e.pos) for e in enemies),
                                         c.dest))
    return B.Defend(me.id)


def _play(state, rng, chooser, max_steps):
    """Steps of {command, canonical, sha256, events, rng_*, stage}, and the
    states (initial first) for the illegal-command cases."""
    rng = _TracedPcg32.wrap(rng)
    steps, states = [], [state]
    cmd = B.Begin()
    while cmd is not None and len(steps) < max_steps:
        u0, c0 = rng.snapshot()
        state, events = B.apply(state, cmd, rng)
        u1, c1 = rng.snapshot()
        calls = {k: c1[k] - c0[k] for k in c1}
        steps.append({
            "command": _jsonable(soak.encode_command(cmd)),
            "canonical": _text(state),
            "sha256": B.state_hash(state),
            "events": [_event_dict(e) for e in events],
            "rng_u32_before": u0,
            "rng_u32": u1 - u0,
            "rng_state_after": rng.state,
            "rng_calls": calls,
            "stage": _stage(cmd, calls, events),
            **_legal_block(state),
        })
        states.append(state)
        cmd = None if state.winner is not None else chooser(state)
    return steps, states


def _case(name, seed, policy_name, policy_kwargs, state, rng, chooser, max_steps=MAX_STEPS):
    initial = {"canonical": _text(state), "sha256": B.state_hash(state), **_legal_block(state)}
    steps, states = _play(state, rng, chooser, max_steps)
    return {
        "name": name,
        "scenario": {"seed": seed, "policy": policy_name,
                     "policy_kwargs": _jsonable(policy_kwargs), "battle_id": state.battle_id,
                     "rng": "battle_rng(seed, battle_id)",
                     "master_seed": seed, "stream_domain": "battle:%s" % state.battle_id,
                     "stream_id": ""},
        "initial": initial,
        "steps": steps,
    }, states


def _driver(seed, any_legal=False, wait_first=False):
    ai = battle_ai.GreedyAI(seed)
    drv = derive_stream(seed, "vectors_battle:driver")
    return lambda state: _driver_step(state, ai, drv, any_legal, wait_first)


# --------------------------------------------------------------------------
# Ability scenarios
# --------------------------------------------------------------------------

def _ability_creature(rng, i, names):
    lo = rng.range(1, 6)
    shooter = rng.chance(1, 2)
    return B.Creature(
        "a%d" % i, rng.range(1, 20), rng.range(1, 20), lo, lo + rng.range(0, 6),
        rng.range(3, 60), rng.range(2, 12),
        shots=rng.range(1, 8) if shooter else 0,
        flyer=rng.chance(1, 4), double_wide=rng.chance(1, 3),
        no_enemy_retaliation=rng.chance(1, 5), unlimited_retaliation=rng.chance(1, 5),
        no_melee_penalty=rng.chance(1, 3), no_range_penalty=rng.chance(1, 4),
        strikes_twice=rng.chance(1, 4), shoots_twice=rng.chance(1, 3),
        no_morale=rng.chance(1, 5),
        hates=tuple(n for n in names if rng.chance(1, 3)))


def _flat(state):
    """The same initial state with morale and luck 0 on every stack."""
    return dataclasses.replace(state, stacks=tuple(
        dataclasses.replace(s, morale=0, luck=0) for s in state.stacks))


def build_tie_scenario(seed, policy):
    """An ability scenario whose speeds are all 5 or 6 (speed ties on both sides)."""
    state, rng = build_ability_scenario(seed, policy)
    pick = derive_stream(seed, "vectors_battle:tie")
    stacks = tuple(dataclasses.replace(s, creature=dataclasses.replace(
        s.creature, speed=5 + pick.range(0, 2))) for s in state.stacks)
    return dataclasses.replace(state, stacks=stacks), rng


def build_ability_scenario(seed, policy):
    rng = derive_stream(seed, "vectors_battle:ability")
    n_a, n_d = rng.range(2, 6), rng.range(2, 6)
    names = ["a%d" % i for i in range(10, 10 + n_a)] + ["a%d" % i for i in range(20, 20 + n_d)]
    armies = []
    for tag, n in ((1, n_a), (2, n_d)):
        armies.append([B.StackSetup(_ability_creature(rng, tag * 10 + i, names),
                                    rng.range(1, 60), morale=rng.range(-3, 4),
                                    luck=rng.range(-3, 4))
                       for i in range(n)])
    obstacles = sorted({(rng.range(5, 12), rng.range(0, B.HEIGHT))
                        for _ in range(rng.range(0, 6))})
    heroes = tuple(B.Hero(rng.range(0, 8), rng.range(0, 8), rng.range(0, 4),
                          rng.range(0, 4), rng.range(0, 4)) if rng.chance(3, 4) else None
                   for _ in range(2))
    state = B.create_battle("ability-%d" % seed, armies[0], armies[1], obstacles=obstacles,
                            heroes=heroes, policy=policy)
    return state, B.battle_rng(seed, state.battle_id)


# --------------------------------------------------------------------------
# Illegal commands
# --------------------------------------------------------------------------

def _illegal_candidates(state):
    n = len(state.stacks)
    if not state.started:
        return [B.Wait(0), B.Defend(0), B.Move(0, (8, 5)), B.Attack(0, n - 1),
                B.Attack(0, n - 1, (8, 5)), B.Shoot(0, n - 1)]
    out = [B.Begin()]
    if state.winner is not None:
        return out + [B.Wait(0), B.Defend(n - 1), B.Move(0, (8, 5)), B.Shoot(0, n - 1),
                      B.Attack(n - 1, 0)]
    act = state.active
    st = state.stacks[act]
    others = [s.id for s in state.stacks if s.id != act]
    out += [B.Wait(others[0]), B.Defend(others[-1]), B.Move(others[0], st.pos),
            B.Attack(others[0], act)]
    reach = set(B.reachable(state, act))
    out += [B.Move(act, st.pos), B.Move(act, (-1, st.pos[1])), B.Move(act, (17, 0)),
            B.Move(act, (0, 0)), B.Move(act, (16, 10))]
    for o in state.obstacles[:2]:
        out.append(B.Move(act, o))
    for s in state.stacks:
        if s.alive and s.id != act:
            out.append(B.Move(act, s.pos))
            break
    far = [(c, r) for r in range(B.HEIGHT) for c in range(B.WIDTH)
           if (c, r) not in reach and (c, r) != st.pos]
    if far:
        out.append(B.Move(act, far[len(far) // 2]))
    out += [B.Attack(act, -1), B.Attack(act, n), B.Shoot(act, -1), B.Shoot(act, n),
            B.Attack(act, act), B.Shoot(act, act)]
    for s in state.stacks:
        if s.id == act:
            continue
        if s.side == st.side or not s.alive:
            out += [B.Attack(act, s.id), B.Shoot(act, s.id)]
            continue
        out += [B.Attack(act, s.id), B.Shoot(act, s.id)]
        if far:
            out.append(B.Attack(act, s.id, far[0]))
        off = state.policy.row_offset
        for h in sorted(reach):
            mine = B._cells_at(h, st.side, st.creature.double_wide)
            if not B._adjacent_cells(mine, B.cells(s), off):
                out.append(B.Attack(act, s.id, h))
                break
    out.append(B.Wait(act))
    return out


def _illegal_cases(name, steps, states):
    """Rejected commands at selected states of one playout. ``after_step`` is the
    index of the step whose resulting state is used (-1: the initial state)."""
    out = []
    picks = [0, len(states) - 1]
    picks += [i for i in range(len(states)) if i % 12 == 6]
    special = [i for i, s in enumerate(states)
               if s.winner is None and s.active is not None
               and (s.bonus_turn or s.active in s.waited)]
    picks += special[:3]
    for i in sorted(set(picks)):
        state = states[i]
        u = 0 if i == 0 else steps[i - 1]["rng_u32_before"] + steps[i - 1]["rng_u32"]
        seen, per_message = set(), {}
        for cmd in _illegal_candidates(state):
            enc = json.dumps(soak.encode_command(cmd), sort_keys=True)
            if enc in seen:
                continue
            seen.add(enc)
            try:
                B._validate(state, cmd)
            except B.IllegalCommand as e:
                # At most two commands per rejection reason and state.
                reason = str(e).split(" ")[0] if str(e).startswith("stack ") else str(e)
                per_message[reason] = per_message.get(reason, 0) + 1
                if per_message[reason] > 2:
                    continue
                out.append({"case": name, "after_step": i - 1, "rng_u32_before": u,
                            "rules_hash": None, "command": _jsonable(soak.encode_command(cmd)),
                            "error": type(e).__name__, "message": str(e)})
        # The pack check comes first, even for a command that is otherwise legal.
        bad = dataclasses.replace(state, rules_hash=BAD_RULES_HASH)
        cmd = B.Begin() if not state.started else (
            B.Defend(state.active) if state.active is not None else B.Wait(0))
        try:
            B._validate(bad, cmd)
            raise AssertionError("PackMismatch expected")
        except B.PackMismatch as e:
            out.append({"case": name, "after_step": i - 1, "rng_u32_before": u,
                        "rules_hash": BAD_RULES_HASH, "command": _jsonable(soak.encode_command(cmd)),
                        "error": type(e).__name__, "message": str(e)})
    return out


def _schema():
    out = {}
    for cls in DATACLASSES + COMMANDS + EVENTS:
        out[cls.__name__] = [f.name for f in dataclasses.fields(cls)]
    return out


def _encoding_cases():
    """Static encodings of every command (both Attack forms) and event type."""
    cmds = [B.Begin(), B.Move(3, (5, 7)), B.Attack(1, 4), B.Attack(1, 4, (6, 2)),
            B.Shoot(2, 5), B.Wait(0), B.Defend(6)]
    evs = [B.BattleStarted("x"), B.RoundStarted(2), B.TurnStarted(1, "wait", True),
           B.MoraleFrozen(1), B.MoraleBoost(2), B.Moved(3, ((1, 1), (2, 1), (2, 2))),
           B.Moved(3, ()), B.Waited(0), B.Defended(4), B.LuckRolled(5, True),
           B.LuckRolled(5, False), B.DamageDealt(1, 2, 33, 4, True, False),
           B.DamageDealt(2, 1, 0, 0, False, True), B.UnitDied(6), B.BattleEnded(1)]
    return ([_jsonable(soak.encode_command(c)) for c in cmds],
            [_event_dict(e) for e in evs])


def generate():
    pol = B._POLICY_PACK.values
    cases, illegal = [], []

    def add(case_states):
        case, states = case_states
        cases.append(case)
        illegal.extend(_illegal_cases(case["name"], case["steps"], states))

    add(_case("golden", 12345, "default", {}, V.golden_setup(),
              B.battle_rng(12345, "golden"), _driver(12345)))
    kwargs = {n: b for n, b, _ in soak.POLICY_MATRIX}
    pols = {n: b for n, b, _ in soak.policy_matrix()}
    for n, kw in EXTRA_POLICIES:
        kwargs[n] = kw
        pols[n] = B.BattlePolicy(**kw)
    for pname, seeds in PLAYOUTS:
        for seed in seeds:
            state, rng = soak.build_scenario("battle", seed, pols[pname])
            add(_case("%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng,
                      _driver(seed)))
    # The pinned golden battle (tests/test_battle.py GoldenTest): its last step
    # hashes to GoldenTest.PINNED.
    add(_case("golden-scripted", 12345, "default", {}, V.golden_setup(),
              B.battle_rng(12345, "golden"), scripted_choice, max_steps=401))
    for pname, seeds in FLAT_PLAYOUTS:
        for seed in seeds:
            state, rng = soak.build_scenario("battle", seed, pols[pname])
            state = _flat(state)
            add(_case("flat-%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng,
                      _driver(seed)))
    for pname, seeds in ABILITY_PLAYOUTS:
        for seed in seeds:
            state, rng = build_ability_scenario(seed, pols[pname])
            add(_case("ability-%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng,
                      _driver(seed, any_legal=True), max_steps=ABILITY_MAX_STEPS))
    for pname, seeds in TIE_PLAYOUTS:
        for seed in seeds:
            state, rng = build_tie_scenario(seed, pols[pname])
            add(_case("tie-%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng,
                      _driver(seed, any_legal=True), max_steps=TIE_MAX_STEPS))
    for pname, seeds in WAIT_PLAYOUTS:
        for seed in seeds:
            state, rng = build_tie_scenario(seed, pols[pname])
            add(_case("wait-%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng,
                      _driver(seed, wait_first=True), max_steps=TIE_MAX_STEPS))
    cmds, evs = _encoding_cases()
    return {FILE: {
        "format": VECTOR_FORMAT,
        "packs": {"battle_policy": _jsonable(dict(pol)),
                  "bad_morale_numerators": list(R.BAD_MORALE_NUMERATORS),
                  "rules_hash": R.RULES_HASH,
                  "rules": V._pack_json()},
        "schema": _schema(),
        "command_cases": cmds,
        "event_cases": evs,
        "cases": cases,
        "illegal_cases": illegal,
    }}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m h3re.vectors_battle")
    ap.add_argument("--out", default=V.DEFAULT_OUT)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for name, obj in generate().items():
        with open(os.path.join(a.out, name), "wb") as f:
            f.write(V._dump(obj))
        print("wrote %s" % os.path.join(a.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
