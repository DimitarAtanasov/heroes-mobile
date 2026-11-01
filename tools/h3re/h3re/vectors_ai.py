"""Greedy battle AI conformance vectors (battle-AI port), from the Python reference.

``generate()`` returns ``{"battle_ai.json": ...}``; the orchestrator wires it into
``vectors.generate()`` (which owns serialisation). Python is authoritative
(ADR-0004, docs/specs/conformance-ai.md).

Each game is played to its end (or ``MAX_STEPS``) by the stateful ``GreedyAI(ai_seed)`` on
both sides; "perturbed" games substitute, every few steps, a random legal command (drawn from
``derive_stream``, never Python's ``random``) so the AI sees states greedy play never reaches.
At every decision point the record holds the pre-state hash, the active side, the per-side
consecutive-Defend count before the call, the stateless ``choose`` result, the stateful
``GreedyAI.choose`` result and the command actually applied; the canonical text of the state
is kept for every ``CANONICAL_EVERY``-th step (and the first steps). The battle stream is
asserted unchanged by both AI calls. ``final`` pins the end state hash and stream position.

Usage:  python3 -m h3re.vectors_ai [--out DIR]
"""

import argparse
import json
import os
import sys

from . import battle as B
from . import battle_ai
from . import rules as R
from . import soak
from . import vectors as V
from . import vectors_battle as VB
from .rng import derive_stream

VECTOR_FORMAT = 1
FILE = "battle_ai.json"
MAX_STEPS = 600
CANONICAL_EVERY = 7
PERTURB_EVERY = 4  # perturbed games: one step in 4 applies a random legal command

# (kind, policy name, seeds, perturbed)
GAMES = (
    ("soak", "default", (0, 1, 2, 3, 4, 5, 6, 7), False),
    ("soak", "alt-order", (0, 1, 2, 6), False),
    ("soak", "vcmi-like", (0, 1, 2, 6), False),
    ("soak", "strict", (0, 1, 2, 6), False),
    ("soak", "mix-fifo", (0, 1), False),
    ("soak", "mix-speed", (0, 1), False),
    ("soak", "mix-alt", (0, 1), False),
    ("flat", "default", (0, 3), False),
    ("flat", "vcmi-like", (1,), False),
    ("ability", "default", (1, 4, 5, 6), False),
    ("ability", "alt-order", (1, 2), False),
    ("ability", "vcmi-like", (1, 9), False),
    ("ability", "strict", (3,), False),
    ("ability", "mix-fifo", (1, 7), False),
    ("ability", "mix-speed", (4,), False),
    ("ability", "mix-alt", (9,), False),
    ("tie", "default", (1,), False),
    ("tie", "alt-order", (1,), False),
    ("tie", "vcmi-like", (1, 2), False),
    ("tie", "mix-fifo", (2,), False),
    ("tie", "mix-alt", (1,), False),
    ("soak", "default", (0, 1, 4, 6), True),
    ("soak", "strict", (1,), True),
    ("ability", "default", (1, 4), True),
    ("ability", "vcmi-like", (1,), True),
    ("tie", "mix-fifo", (2,), True),
    # Walled-off armies: no attack, no closer move, so the Defend cap, Wait and the
    # closest-Move fallback run (and the stateless round-8 cap).
    ("wall", "default", (0, 1, 2), False),
    ("wall", "alt-order", (1,), False),
    ("wall", "strict", (2,), False),
    ("wall", "vcmi-like", (0,), False),
    ("wall", "mix-fifo", (1,), True),
)
WALL_MAX_STEPS = 90


def _jsonable(x):
    return json.loads(json.dumps(x))


def _enc(cmd):
    return _jsonable(soak.encode_command(cmd))


def _policies():
    kwargs = {n: b for n, b, _ in soak.POLICY_MATRIX}
    pols = {n: b for n, b, _ in soak.policy_matrix()}
    for n, kw in VB.EXTRA_POLICIES:
        kwargs[n] = kw
        pols[n] = B.BattlePolicy(**kw)
    return kwargs, pols


def _wall_scenario(seed, policy):
    """Ground armies (no shooters, flyers or two-hex units except a few big ones) split by a
    full-height wall of obstacles: nobody can strike anybody."""
    rng = derive_stream(seed, "vectors_ai:wall")

    def army(tag):
        out = []
        for i in range(rng.range(2, 5)):
            lo = rng.range(1, 6)
            c = B.Creature("w%d" % (tag * 10 + i), rng.range(1, 15), rng.range(1, 15), lo,
                           lo + rng.range(0, 6), rng.range(3, 60), rng.range(2, 9),
                           double_wide=rng.chance(1, 4))
            out.append(B.StackSetup(c, rng.range(1, 40), morale=rng.range(-2, 3),
                                    luck=rng.range(-2, 3)))
        return out

    obstacles = [(8, r) for r in range(B.HEIGHT)]
    state = B.create_battle("wall-%d" % seed, army(1), army(2), obstacles=obstacles,
                            policy=policy)
    return state, B.battle_rng(seed, state.battle_id)


def _build(kind, seed, policy):
    if kind == "wall":
        return _wall_scenario(seed, policy)
    if kind == "ability":
        return VB.build_ability_scenario(seed, policy)
    if kind == "tie":
        return VB.build_tie_scenario(seed, policy)
    state, rng = soak.build_scenario("battle", seed, policy)
    return (VB._flat(state) if kind == "flat" else state), rng


def _game(kind, pname, seed, perturbed, kwargs, pols):
    state, brng = _build(kind, seed, pols[pname])
    ai_seed = seed
    ai = battle_ai.GreedyAI(ai_seed)
    drv = derive_stream(seed, "vectors_ai:driver")
    name = "%s-%s-%d%s" % (kind, pname, seed, "-perturbed" if perturbed else "")
    initial = {"canonical": VB._text(state), "sha256": B.state_hash(state)}
    steps, tied = [], 0
    n = 0
    limit = WALL_MAX_STEPS if kind == "wall" else MAX_STEPS
    while state.winner is None and n < limit:
        side = None if state.active is None else state.stacks[state.active].side
        defends_before = ai._defends[side if side is not None else 0]
        before = (brng.state, brng.inc)
        stateless = battle_ai.choose(state)
        stateful = ai.choose(state)
        assert (brng.state, brng.inc) == before, "AI drew from the battle stream"
        applied = stateful
        if perturbed and state.started and drv.range(0, PERTURB_EVERY) == 0:
            legal = B.legal_commands(state)
            applied = legal[drv.range(0, len(legal))]
        rec = {"side": side, "defends_before": defends_before,
               "sha256": B.state_hash(state),
               "stateless": _enc(stateless), "stateful": _enc(stateful),
               "applied": _enc(applied)}
        if n < 3 or n % CANONICAL_EVERY == 0:
            rec["canonical"] = VB._text(state)
        steps.append(rec)
        state, _ = B.apply(state, applied, brng)
        n += 1
    return {
        "name": name,
        "scenario": {"kind": kind, "seed": seed, "policy": pname,
                     "policy_kwargs": _jsonable(kwargs[pname]), "battle_id": state.battle_id,
                     "master_seed": seed, "stream_domain": "battle:%s" % state.battle_id,
                     "stream_id": "", "ai_seed": ai_seed, "perturbed": perturbed},
        "initial": initial,
        "steps": steps,
        "final": {"sha256": B.state_hash(state), "winner": state.winner, "steps": n,
                  "round": state.round,
                  "rng_state": brng.state, "rng_inc": brng.inc},
    }


def generate():
    kwargs, pols = _policies()
    games = []
    for kind, pname, seeds, perturbed in GAMES:
        for seed in seeds:
            games.append(_game(kind, pname, seed, perturbed, kwargs, pols))
    return {FILE: {
        "format": VECTOR_FORMAT,
        "max_defends": battle_ai.MAX_DEFENDS,
        "stateless_defend_round": battle_ai._STATELESS_DEFEND_ROUND,
        "packs": {"battle_policy": _jsonable(dict(B._POLICY_PACK.values)),
                  "bad_morale_numerators": list(R.BAD_MORALE_NUMERATORS),
                  "rules_hash": R.RULES_HASH,
                  "rules": V._pack_json()},
        "games": games,
    }}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m h3re.vectors_ai")
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
