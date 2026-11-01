"""Adventure-core conformance vectors (Kotlin port of ``adventure.py``), from the Python reference.

``generate()`` returns ``{"adventure.json": ...}``; the orchestrator wires it into
``vectors.generate()`` (which owns serialisation). Python is authoritative (ADR-0004,
ADR-0007, docs/specs/conformance-adventure.md). Synthetic data only.

Contents:
  constants      the content-free tables of ``adventure.py`` (terrain costs, roads, speed to
                 movement points, Logistics, mine output), handed to the Kotlin engine
  cases          playouts: the golden 14-day scripted run (``tests/test_adventure.py``) under
                 several policies, and soak scenarios (``soak.build_adventure``, the soak
                 adventure driver) under the soak policy matrix and extra policies. Each step
                 has the command, the canonical state text and SHA-256 after it, the events,
                 the stage letter and, before a Move, a digest of the moving hero's reachable map
  illegal_cases  rejected commands: the state (case, step), the command, the exception class
                 and message; state and RNG must stay untouched

The adventure core draws nothing from its stream; every step also records that the
``adventure:<game_id>`` stream is still at its derived state.

Usage:  python3 -m h3re.vectors_adventure [--out DIR]
"""

import argparse
import dataclasses
import hashlib
import json
import os
import sys

from . import adventure as A
from . import soak
from . import vectors as V

VECTOR_FORMAT = 1
FILE = "adventure.json"
SOAK_MAX_STEPS = 50

COMMANDS = (A.Begin, A.Move, A.EndTurn)
EVENTS = (A.DayStarted, A.WeekStarted, A.PoolGrew, A.TurnStarted, A.IncomeReceived,
          A.MovementReset, A.HeroMoved, A.TurnEnded)

# Extra policies (beyond soak.POLICY_MATRIX) for branches the matrix leaves out.
EXTRA_POLICIES = (
    ("road-dest", dict(road_rate_from="dest")),
    ("road-one-source", dict(road_needs_both=False, road_rate_from="source")),
    ("road-custom", dict(road_cost=(("dirt", 90), ("gravel", 80), ("cobblestone", 60)),
                         road_rate_from="max")),
    ("diag-ratio-floor", dict(diagonal_mode="ratio", diagonal_num=3, diagonal_den=2,
                              diagonal_rounding="floor")),
    ("diag-ratio-nearest", dict(diagonal_mode="ratio", diagonal_num=1414, diagonal_den=1000,
                                diagonal_rounding="nearest", diagonal_exception=False)),
    ("no-corner-cut", dict(diagonal_corner_cut=False)),
    ("last-fresh", dict(last_step="allow_if_fresh", zero_remainder=False)),
    ("last-any", dict(last_step="allow_if_any")),
    ("pf-percent-floor", dict(pathfinding_mode="percent", pathfinding_pct=(0, 30, 55, 80))),
    ("pf-percent-ceil", dict(pathfinding_mode="percent", pathfinding_rounding="ceil")),
    ("pf-flat-custom", dict(pathfinding_flat=(0, 10, 40, 90), move_cost_floor=110)),
    ("income-day1", dict(income_on_first_day=True, cost_from="dest")),
)


def _policies():
    out = [(n, a) for n, _, a in soak.POLICY_MATRIX]
    return out + list(EXTRA_POLICIES)


# (policy name, soak seeds)
SOAK_GAMES = (
    ("default", (0, 1, 2, 3)), ("alt-order", (0, 1)), ("vcmi-like", (0, 2)),
    ("strict", (1, 2)), ("road-dest", (0,)), ("road-one-source", (1,)), ("road-custom", (2,)),
    ("diag-ratio-floor", (0,)), ("diag-ratio-nearest", (1,)), ("no-corner-cut", (3,)),
    ("last-fresh", (0,)), ("last-any", (1,)), ("pf-percent-floor", (2,)),
    ("pf-percent-ceil", (3,)), ("pf-flat-custom", (0,)), ("income-day1", (1,)),
)
GOLDEN_POLICIES = ("default", "alt-order", "vcmi-like", "strict", "no-corner-cut",
                   "pf-percent-floor")

# The golden 14-day run of tests/test_adventure.py (GoldenTest), restated here so the package
# does not import the tests; tests/test_vectors_adventure.py checks it reproduces the pin.
_TERR = {"d": "dirt", "g": "grass", "l": "lava", "u": "subterranean",
         "r": "rough", "s": "sand", "n": "snow", "w": "swamp",
         "~": "water", "#": "rock"}
_ROAD = {".": "none", "1": "dirt", "2": "gravel", "3": "cobblestone"}
GOLDEN_TERRAIN = (
    "gggrrsssnnww~~gg", "gdddrrsssnnw~ggg", "ggud#rrssnnww~gg", "llud#rrsssnnwwgg",
    "lluu#rrsssnnwwwg", "gggggggggggggggg", "wwwwssssrrrrdddd", "gggggggggggggggg",
)
GOLDEN_ROADS = (
    "1111............", "...1............", "...1............", "...222222222....",
    "...........2....", "...........33333", "................", "................",
)
GOLDEN_BLOCKED = ((9, 7), (10, 6))
WAYPOINTS = {0: ((15, 7), (2, 3), (14, 1), (0, 0)),
             1: ((15, 0), (8, 6), (1, 2), (0, 7)),
             2: ((0, 4), (11, 0), (6, 7), (15, 5))}
GOLDEN_DAYS = 14


def golden_setup(policy=A.DEFAULT_POLICY):
    tiles = []
    for y, row in enumerate(GOLDEN_TERRAIN):
        for x, code in enumerate(row):
            tiles.append(A.Tile(_TERR[code], _ROAD[GOLDEN_ROADS[y][x]], (x, y) in GOLDEN_BLOCKED))
    g = A.Grid(len(GOLDEN_TERRAIN[0]), len(GOLDEN_TERRAIN), tuple(tiles))

    def army(*speeds):
        return tuple(A.ArmySlot("c%d" % i, s, 10) for i, s in enumerate(speeds))
    players = (
        A.Player(A.Resources(gold=7500, wood=10, ore=10), ("gold_mine", "sawmill"),
                 A.Resources(gold=500)),
        A.Player(A.Resources(gold=5000), ("ore_pit", "crystal_cavern")),
    )
    heroes = (
        A.HeroSetup(0, (0, 0), army(4, 6), logistics=1),
        A.HeroSetup(0, (0, 7), army(7), pathfinding=2),
        A.HeroSetup(1, (15, 5), army(5, 11), logistics=3, pathfinding=1),
    )
    pools = (A.GrowthPool("a", 10, 10), A.GrowthPool("b", 0, 2))
    return A.create_game("golden", g, players, heroes, pools, policy)


def golden_commands(state):
    """The golden scripted driver: (commands, final state), Begin first."""
    cmds = [A.Begin()]
    state, _ = A.apply(state, A.Begin())
    while state.day <= GOLDEN_DAYS:
        for h in state.heroes:
            if h.owner != state.current:
                continue
            target = WAYPOINTS[h.id][state.day % 4]
            if h.pos == target:
                continue
            plan = A.find_path(state, h.id, target)
            if plan is None:
                continue
            reach = A.reachable(state, h.id)
            dest = None
            for t in plan[1][1:]:
                if t in reach:
                    dest = t
            if dest is not None:
                cmd = A.Move(h.id, dest)
                state, _ = A.apply(state, cmd)
                cmds.append(cmd)
        cmd = A.EndTurn(state.current)
        state, _ = A.apply(state, cmd)
        cmds.append(cmd)
    return cmds, state


def _jsonable(v):
    if dataclasses.is_dataclass(v):
        return {f.name: _jsonable(getattr(v, f.name)) for f in dataclasses.fields(v)}
    if isinstance(v, (tuple, list)):
        return [_jsonable(x) for x in v]
    return v


def encode_event(e):
    return dict({"type": type(e).__name__}, **_jsonable(e))


def _text(state):
    return A.canonical(state).decode("ascii")


def _sha(state):
    return A.state_hash(state)


def reach_digest(state, hero_id):
    """SHA-256 of the canonical JSON of the hero's reachable map: [[x, y], cost, path] sorted."""
    items = [[list(t), c, [list(p) for p in path]]
             for t, (c, path) in sorted(A.reachable(state, hero_id).items())]
    return hashlib.sha256(json.dumps(items, sort_keys=True, separators=(",", ":"))
                          .encode("ascii")).hexdigest(), len(items)


def _stage(cmd):
    return "B" if isinstance(cmd, A.Move) else "C"


def _play(name, policy_name, state, rng, cmds, seed, kind):
    initial = state
    steps = []
    for cmd in cmds:
        step = {"command": soak.encode_command(cmd), "stage": _stage(cmd)}
        if isinstance(cmd, A.Move):
            step["reach_sha256"], step["reach_size"] = reach_digest(state, cmd.hero)
        state, events = A.apply(state, cmd, rng)
        step["canonical"] = _text(state)
        step["sha256"] = _sha(state)
        step["events"] = [encode_event(e) for e in events]
        steps.append(step)
    return {
        "name": name, "kind": kind, "policy": policy_name,
        "scenario": {"master_seed": seed, "game_id": initial.game_id,
                     "stream_domain": "adventure:%s" % initial.game_id},
        "initial": {"canonical": _text(initial), "sha256": _sha(initial)},
        "final_rng_state": [rng.state, rng.inc],
        "steps": steps,
    }


def _states(case):
    return [case["initial"]["canonical"]] + [s["canonical"] for s in case["steps"]]


def _illegal_commands(state):
    """Commands to try on ``state`` (a mix of every reject branch reachable without encounters)."""
    out = [{"type": "Begin"}]
    if not state.day:
        out += [{"type": "EndTurn", "player": 0}, {"type": "Move", "hero": 0, "dest": [0, 0]}]
        return out
    cur = state.current
    other = (cur + 1) % len(state.players)
    out += [{"type": "EndTurn", "player": other}, {"type": "EndTurn", "player": True},
            {"type": "EndTurn", "player": "0"}, {"type": "EndTurn", "player": -1},
            {"type": "Move", "hero": len(state.heroes), "dest": [0, 0]},
            {"type": "Move", "hero": -1, "dest": [0, 0]},
            {"type": "Move", "hero": True, "dest": [0, 0]},
            {"type": "Move", "hero": 2 ** 40, "dest": [0, 0]}]
    foreign = [h for h in state.heroes if h.owner != cur]
    if foreign:
        out.append({"type": "Move", "hero": foreign[0].id, "dest": list(foreign[0].pos)})
    mine = [h for h in state.heroes if h.owner == cur]
    if mine:
        h = mine[0]
        x, y = h.pos
        out += [{"type": "Move", "hero": h.id, "dest": [x]},
                {"type": "Move", "hero": h.id, "dest": [x, y, 0]},
                {"type": "Move", "hero": h.id, "dest": [x, True]},
                {"type": "Move", "hero": h.id, "dest": "ab"},
                {"type": "Move", "hero": h.id, "dest": [x, y]},
                {"type": "Move", "hero": h.id, "dest": [-1, 0]},
                {"type": "Move", "hero": h.id, "dest": [2 ** 40, 0]},
                {"type": "Move", "hero": h.id, "dest": [state.grid.width - 1, state.grid.height - 1]}]
        reach = A.reachable(state, h.id)
        far = [t for t in sorted((x2, y2) for y2 in range(state.grid.height)
                                 for x2 in range(state.grid.width))
               if t not in reach and t != h.pos]
        if far:
            out.append({"type": "Move", "hero": h.id, "dest": list(far[len(far) // 2])})
    return out


def _decode(d):
    kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in d.items() if k != "type"}
    return getattr(A, d["type"])(**kw)


def illegal_cases(cases):
    out = []
    for case in cases:
        texts = _states(case)
        picks = sorted({0, 1, len(texts) // 2, len(texts) - 1})
        for k in picks:
            # Rebuild the Python state by replaying the case's commands up to step k.
            state = _initial_state(case)
            for s in case["steps"][:k]:
                state, _ = A.apply(state, _decode(s["command"]))
            assert _text(state) == texts[k]
            for cmd in _illegal_commands(state):
                try:
                    A.apply(state, _decode(cmd))
                except A.IllegalCommand as e:
                    out.append({"case": case["name"], "after_step": k - 1, "command": cmd,
                                "error": "IllegalCommand", "message": str(e)})
                    continue
                # A command that turned out legal is not an illegal case; leave it out.
    return out


_INITIAL = {}


def _initial_state(case):
    return _INITIAL[case["name"]]


def generate():
    pols = dict(_policies())
    cases = []
    for pname in GOLDEN_POLICIES:
        state = golden_setup(A.AdventurePolicy(**pols[pname]))
        cmds, _ = golden_commands(state)
        rng = A.adventure_rng(0, state.game_id)
        name = "golden" if pname == "default" else "golden-" + pname
        _INITIAL[name] = state
        cases.append(_play(name, pname, state, rng, cmds, 0, "golden"))
    for pname, seeds in SOAK_GAMES:
        policy = A.AdventurePolicy(**pols[pname])
        for seed in seeds:
            cmds, _ = soak.generate_log("adventure", seed, SOAK_MAX_STEPS, policy)
            state, rng = soak.build_adventure(seed, policy)
            name = "soak-%s-%d" % (pname, seed)
            _INITIAL[name] = state
            cases.append(_play(name, pname, state, rng, cmds, seed, "soak"))
    constants = {
        "terrain_cost": dict(sorted(A.TERRAIN_COST.items())),
        "impassable": list(A.IMPASSABLE),
        "roads": list(A.ROADS),
        "speed_mp": list(A._SPEED_MP),
        "logistics_pct": list(A.LOGISTICS_PCT),
        "resource_names": list(A.RESOURCE_NAMES),
        "mine_output": {k: _jsonable(v) for k, v in sorted(A.MINE_OUTPUT.items())},
    }
    doc = {
        "format": VECTOR_FORMAT,
        "description": "adventure.py playouts: canonical state, sha256 and events per step "
                       "(docs/specs/conformance-adventure.md)",
        "constants": constants,
        "policies": {n: _jsonable(A.AdventurePolicy(**kw)) for n, kw in _policies()},
        "cases": cases,
        "illegal_cases": illegal_cases(cases),
    }
    return {FILE: doc}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=V.DEFAULT_OUT if hasattr(V, "DEFAULT_OUT") else ".")
    args = ap.parse_args(argv)
    for name, obj in generate().items():
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(V._dump(obj))
    return 0


if __name__ == "__main__":
    sys.exit(main())
