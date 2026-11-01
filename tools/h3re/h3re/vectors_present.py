"""Presenter (view v2) conformance vectors, from the Python reference.

``generate()`` returns ``{"present.json": content}``; the orchestrator wires it into
``vectors.generate()``. Python is authoritative (ADR-0004, docs/specs/conformance-present.md).

The states are the recorded states of the ``battle_states.json`` playouts: the same cases, in the
same order, produced by the same ``vectors_battle`` helpers (Pcg32 streams and
``derive_stream`` drivers only, no ``random`` module). A ``present.json`` entry refers to a
state by ``(case name, index)`` where index 0 is the initial state and index i+1 the state after
step i; the entry's ``state_sha256`` is that state's hash, so the Kotlin test can check it loaded
the right one. Every state has the SHA-256 of ``view_json``; every ``TEXT_EVERY``-th state (and
the first and last of each case) also carries the full text (the files would be too large with
all of them). Every ``TAP_EVERY``-th state carries the tap candidates: for each hex with a
non-empty ``candidate_commands`` the command dicts and the SHA-256 of the canonical
``candidate_actions`` entry; every other hex must give an empty list and ``None``.

Usage:  python3 -m h3re.vectors_present [--out DIR]
"""

import argparse
import hashlib
import json
import os
import sys

from . import battle as B
from . import present as P
from . import soak
from . import vectors as V
from . import vectors_battle as VB

VECTOR_FORMAT = 1
FILE = "present.json"
TEXT_EVERY = 9
TAP_EVERY = 4


def _sha(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _taps(state):
    out = []
    for r in range(B.HEIGHT):
        for c in range(B.WIDTH):
            cmds = P.candidate_commands(state, (c, r))
            if not cmds:
                # test_present pins: candidate_actions is None exactly when there are no
                # candidate commands (Kotlin checks every hex), so skip the costly call here.
                continue
            ent = P.candidate_actions(state, (c, r))
            out.append({"hex": [c, r],
                        "commands": [P.command_to_dict(x) for x in cmds],
                        "action_sha256": None if ent is None else _sha(_canon(ent))})
    return out


def _entries(case_name, states):
    out = []
    last = len(states) - 1
    for i, st in enumerate(states):
        h0 = B.state_hash(st)
        text = P.view_json(st)
        assert B.state_hash(st) == h0
        e = {"index": i, "state_sha256": h0, "view_sha256": _sha(text)}
        if i == 0 or i == last or i % TEXT_EVERY == 0:
            e["view_json"] = text
        if i % TAP_EVERY == 0 or i == last:
            e["taps"] = _taps(st)
        out.append(e)
    return out




def _playouts():
    """(case name, states) in the order of ``vectors_battle.generate``."""
    cases = []

    def add(case_states):
        case, states = case_states
        cases.append((case["name"], states))

    add(VB._case("golden", 12345, "default", {}, V.golden_setup(),
                 B.battle_rng(12345, "golden"), VB._driver(12345)))
    kwargs = {n: b for n, b, _ in soak.POLICY_MATRIX}
    pols = {n: b for n, b, _ in soak.policy_matrix()}
    for n, kw in VB.EXTRA_POLICIES:
        kwargs[n] = kw
        pols[n] = B.BattlePolicy(**kw)
    for pname, seeds in VB.PLAYOUTS:
        for seed in seeds:
            state, rng = soak.build_scenario("battle", seed, pols[pname])
            add(VB._case("%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng,
                         VB._driver(seed)))
    for pname, seeds in VB.FLAT_PLAYOUTS:
        for seed in seeds:
            state, rng = soak.build_scenario("battle", seed, pols[pname])
            add(VB._case("flat-%s-%d" % (pname, seed), seed, pname, kwargs[pname],
                         VB._flat(state), rng, VB._driver(seed)))
    for pname, seeds in VB.ABILITY_PLAYOUTS:
        for seed in seeds:
            state, rng = VB.build_ability_scenario(seed, pols[pname])
            add(VB._case("ability-%s-%d" % (pname, seed), seed, pname, kwargs[pname], state,
                         rng, VB._driver(seed, any_legal=True), max_steps=VB.ABILITY_MAX_STEPS))
    for pname, seeds in VB.TIE_PLAYOUTS:
        for seed in seeds:
            state, rng = VB.build_tie_scenario(seed, pols[pname])
            add(VB._case("tie-%s-%d" % (pname, seed), seed, pname, kwargs[pname], state, rng,
                         VB._driver(seed, any_legal=True), max_steps=VB.TIE_MAX_STEPS))
    return cases


def generate():
    cases = [{"name": name, "states": _entries(name, states)}
             for name, states in _playouts()]
    return {FILE: {"format": VECTOR_FORMAT, "view_version": P.VIEW_VERSION,
                   "text_every": TEXT_EVERY, "tap_every": TAP_EVERY, "cases": cases}}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m h3re.vectors_present")
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
