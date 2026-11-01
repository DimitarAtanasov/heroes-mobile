"""Battle state conformance vectors (battle-port slice 2), from the Python reference.

``generate()`` returns ``{vector file name: JSON-serialisable content}``; the
orchestrator wires it into ``vectors.generate()`` (which owns serialisation).
Python is authoritative (ADR-0004, docs/specs/conformance.md "Battle state").

Each playout is played by the Python engine from a soak scenario
(``soak.build_scenario``, randomness only from ``Pcg32`` streams) with a
deterministic driver: the greedy AI, except that a ``derive_stream`` draw
sometimes substitutes a legal Wait or Defend so every command type occurs.

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
from .rng import derive_stream

VECTOR_FORMAT = 1
FILE = "battle_states.json"
MAX_STEPS = 120

COMMANDS = (B.Begin, B.Move, B.Attack, B.Shoot, B.Wait, B.Defend)
EVENTS = (B.BattleStarted, B.RoundStarted, B.TurnStarted, B.MoraleFrozen, B.MoraleBoost,
          B.Moved, B.Waited, B.Defended, B.LuckRolled, B.DamageDealt, B.UnitDied,
          B.BattleEnded)
DATACLASSES = (B.BattleState, B.BattlePolicy, B.Stack, B.Creature, B.Hero)

# (policy name, seeds): seeds chosen for coverage (one-hex only, shooters and
# flyers, two-hex units, both) under the default and all non-default policies.
PLAYOUTS = (("default", (0, 1, 4, 6)), ("alt-order", (0, 1, 6)),
            ("vcmi-like", (0, 1, 6)), ("strict", (0, 1, 6)))


def _jsonable(x):
    return json.loads(json.dumps(x))


def _event_dict(ev):
    d = soak.encode_command(ev)
    return _jsonable(d)


def _text(state):
    return B.canonical(state).decode("ascii")


def _driver_step(state, ai, drv):
    if state.winner is not None:
        return None
    pick = drv.range(0, 5)
    if pick < 2:
        legal = B.legal_commands(state)
        want = B.Wait if pick == 0 else B.Defend
        for c in legal:
            if isinstance(c, want):
                return c
    return ai.choose(state)


def _play(state, rng, seed):
    ai = battle_ai.GreedyAI(seed)
    drv = derive_stream(seed, "vectors_battle:driver")
    steps = []
    cmd = B.Begin()
    while cmd is not None and len(steps) < MAX_STEPS:
        state, events = B.apply(state, cmd, rng)
        steps.append({
            "command": _jsonable(soak.encode_command(cmd)),
            "canonical": _text(state),
            "sha256": B.state_hash(state),
            "events": [_event_dict(e) for e in events],
        })
        cmd = _driver_step(state, ai, drv)
    return steps


def _case(name, seed, policy_name, policy_kwargs, state, rng):
    initial = {"canonical": _text(state), "sha256": B.state_hash(state)}
    return {
        "name": name,
        "scenario": {"seed": seed, "policy": policy_name,
                     "policy_kwargs": _jsonable(policy_kwargs), "battle_id": state.battle_id,
                     "rng": "battle_rng(seed, battle_id)"},
        "initial": initial,
        "steps": _play(state, rng, seed),
    }


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
    cases = []
    st = V.golden_setup()
    rng = B.battle_rng(12345, "golden")
    cases.append(_case("golden", 12345, "default", {}, st, rng))
    kwargs = {n: b for n, b, _ in soak.POLICY_MATRIX}
    pols = {n: b for n, b, _ in soak.policy_matrix()}
    for pname, seeds in PLAYOUTS:
        for seed in seeds:
            state, rng = soak.build_scenario("battle", seed, pols[pname])
            cases.append(_case("%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng))
    cmds, evs = _encoding_cases()
    return {FILE: {
        "format": VECTOR_FORMAT,
        "packs": {"battle_policy": _jsonable(dict(pol)),
                  "bad_morale_numerators": list(R.BAD_MORALE_NUMERATORS),
                  "rules_hash": R.RULES_HASH},
        "schema": _schema(),
        "command_cases": cmds,
        "event_cases": evs,
        "cases": cases,
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
