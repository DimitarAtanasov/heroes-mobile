"""Determinism soak: seeded AI-vs-AI battles and adventure scripts.

Concepts ported from Forge's fuzz_soak (ideas only). For each seed a game is
played live with a deterministic driver, recording a command log and the
state hash after every step. The game is then checked three ways:

1. a second live run gives the identical step-by-step hash trace;
2. replaying the recorded log from scratch twice gives the same trace;
3. snapshot-and-resume: the state and RNG state are serialised mid-game
   (pickle), restored, and the remaining commands produce the same trace.

CLI: ``python3 -m h3re.soak --games N``. Spec: docs/specs/determinism-gate.md.
"""

import argparse
import hashlib
import pickle
import sys
from dataclasses import fields

from . import adventure as A
from . import battle as B
from . import battle_ai
from .rng import Pcg32, derive_stream

__all__ = [
    "KINDS", "Divergence", "build_scenario", "generate_log", "replay_steps",
    "trace", "encode_command", "decode_command", "check_seed", "run_seed", "soak",
    "soak_digest", "trace_digest", "POLICY_MATRIX", "policy_matrix", "main",
]

KINDS = ("battle", "adventure")
_MODULES = {"battle": B, "adventure": A}


class Divergence(AssertionError):
    pass


# --------------------------------------------------------------------------
# Policy matrix: non-default (BattlePolicy, AdventurePolicy) combinations.
# Each entry is (name, battle kwargs, adventure kwargs); the empty kwargs of
# "default" give the default policy. Values are the documented alternatives.
# --------------------------------------------------------------------------

POLICY_MATRIX = (
    ("default", {}, {}),
    ("alt-order",
     dict(row_offset="odd", speed_tie="alternate", wait_order="speed",
          good_morale_after_wait=True, repeat_good_morale=True),
     dict(road_needs_both=False, road_rate_from="max", cost_from="dest",
          last_step="allow_if_any")),
    ("vcmi-like",
     dict(speed_tie="alternate_last_mover", wait_order="slow_first_alternate",
          bad_morale_table=(2, 4, 6), bad_luck=True, range_origin="any_cell",
          bad_morale_on_wait_activation=True),
     dict(diagonal_mode="ratio", diagonal_rounding="ceil", pathfinding_mode="percent",
          pathfinding_rounding="nearest", last_step="allow_if_fresh",
          income_on_first_day=True)),
    ("strict",
     dict(edge_columns_walkable=True, defend_bonus_num=1, defend_bonus_den=4,
          defend_bonus_min=2, defend_bonus_rounding="ceil", range_penalty_beyond=6,
          good_morale_after_defend=True),
     dict(diagonal_moves=False, diagonal_corner_cut=False, diagonal_exception=False,
          zero_remainder=False, last_step="forbid")),
)


def policy_matrix():
    """Instantiate POLICY_MATRIX: list of (name, BattlePolicy, AdventurePolicy)."""
    return [(n, B.BattlePolicy(**b), A.AdventurePolicy(**a))
            for n, b, a in POLICY_MATRIX]


# --------------------------------------------------------------------------
# Command (de)serialisation: {"type": "Move", "stack": 1, "dest": [3, 4]}
# --------------------------------------------------------------------------

def encode_command(cmd):
    d = {"type": type(cmd).__name__}
    for f in fields(cmd):
        v = getattr(cmd, f.name)
        d[f.name] = list(v) if isinstance(v, tuple) else v
    return d


def decode_command(kind, d):
    cls = getattr(_MODULES[kind], d["type"])
    kw = {k: (tuple(v) if isinstance(v, list) else v)
          for k, v in d.items() if k != "type"}
    return cls(**kw)


# --------------------------------------------------------------------------
# Scenario builders (pure functions of the seed)
# --------------------------------------------------------------------------

def _scn_rng(kind, seed):
    return derive_stream(seed, "soak:scenario:" + kind)


def _random_creature(rng, i):
    lo = rng.range(1, 6)
    return B.Creature(
        "c%d" % i, rng.range(1, 15), rng.range(1, 15), lo, lo + rng.range(0, 6),
        rng.range(3, 60), rng.range(2, 12),
        shots=rng.range(4, 16) if rng.chance(1, 3) else 0,
        flyer=rng.chance(1, 4), double_wide=rng.chance(1, 4),
        strikes_twice=rng.chance(1, 8), no_enemy_retaliation=rng.chance(1, 10))


def _random_army(rng, n, tag):
    return [B.StackSetup(_random_creature(rng, tag * 10 + i), rng.range(1, 40),
                         morale=rng.range(-2, 3), luck=rng.range(-2, 3))
            for i in range(n)]


def build_battle(seed, policy=None):
    rng = _scn_rng("battle", seed)
    n_a, n_d = rng.range(1, 6), rng.range(1, 6)
    obstacles = sorted({(rng.range(5, 10), rng.range(0, B.HEIGHT))
                        for _ in range(rng.range(0, 6))})
    heroes = tuple(B.Hero(rng.range(0, 6), rng.range(0, 6), rng.range(0, 4),
                          rng.range(0, 4), rng.range(0, 4)) for _ in range(2))
    state = B.create_battle("soak-b%d" % seed, _random_army(rng, n_a, 1),
                            _random_army(rng, n_d, 2), obstacles=obstacles,
                            heroes=heroes, policy=policy or B.DEFAULT_POLICY)
    return state, B.battle_rng(seed, state.battle_id)


def build_adventure(seed, policy=None):
    rng = _scn_rng("adventure", seed)
    w, h = rng.range(6, 13), rng.range(6, 13)
    terrains = sorted(A.TERRAIN_COST)
    tiles = []
    for _ in range(w * h):
        if rng.chance(1, 12):
            tiles.append(A.Tile("water" if rng.chance(1, 2) else "rock"))
        else:
            tiles.append(A.Tile(terrains[rng.range(0, len(terrains))],
                                A.ROADS[rng.range(0, len(A.ROADS))]))
    # Clear distinct start tiles for four heroes.
    starts = []
    for i in range(4):
        pos = (i * 2 % w, i // 2)
        starts.append(pos)
        tiles[pos[1] * w + pos[0]] = A.Tile("grass")
    grid = A.Grid(w, h, tuple(tiles))
    players = tuple(A.Player(A.Resources(gold=rng.range(0, 5000)),
                             mines=("gold_mine",) if rng.chance(1, 2) else ("sawmill", "ore_pit"))
                    for _ in range(2))
    heroes = tuple(A.HeroSetup(
        i % 2, starts[i],
        tuple(A.ArmySlot("c%d" % j, rng.range(3, 14), rng.range(1, 30))
              for j in range(rng.range(1, 5))),
        logistics=rng.range(0, 4), pathfinding=rng.range(0, 4)) for i in range(4))
    pools = (A.GrowthPool("d0", 5, 3), A.GrowthPool("d1", 0, 7))
    state = A.create_game("soak-a%d" % seed, grid, players, heroes, pools,
                          policy=policy or A.DEFAULT_POLICY)
    return state, A.adventure_rng(seed, state.game_id)


def build_scenario(kind, seed, policy=None):
    """Initial (state, rng) for ``kind`` ('battle' | 'adventure'). ``policy`` is
    the kind's policy object (None: the default)."""
    return {"battle": build_battle, "adventure": build_adventure}[kind](seed, policy)


# --------------------------------------------------------------------------
# Drivers: choose the next command from the current state (deterministic)
# --------------------------------------------------------------------------

class _BattleDriver:
    def __init__(self, seed):
        self.ai = battle_ai.GreedyAI(seed)

    def next(self, state):
        return None if state.winner is not None else self.ai.choose(state)


class _AdventureDriver:
    def __init__(self, seed):
        self.rng = derive_stream(seed, "soak:adventure-driver")

    def next(self, state):
        if not state.day:
            return A.Begin()
        mine = [h for h in state.heroes if h.owner == state.current]
        moves = []
        for hero in mine:
            for dest in sorted(A.reachable(state, hero.id)):
                moves.append(A.Move(hero.id, dest))
        if moves and not self.rng.chance(1, 4):
            return moves[self.rng.range(0, len(moves))]
        return A.EndTurn(state.current)


def _driver(kind, seed):
    return {"battle": _BattleDriver, "adventure": _AdventureDriver}[kind](seed)


def _first_command(kind):
    return _MODULES[kind].Begin()


# --------------------------------------------------------------------------
# Running / replaying
# --------------------------------------------------------------------------

def _events_digest(events):
    return repr(events)


def _hash(kind, state):
    return _MODULES[kind].state_hash(state)


def generate_log(kind, seed, max_steps=400, policy=None):
    """Play live; return (commands, trace). Trace entry i is
    (state hash, events repr) after command i."""
    state, rng = build_scenario(kind, seed, policy)
    drv = _driver(kind, seed)
    mod = _MODULES[kind]
    cmds, tr = [], []
    cmd = mod.Begin()
    while cmd is not None and len(cmds) < max_steps:
        state, events = mod.apply(state, cmd, rng)
        cmds.append(cmd)
        tr.append((_hash(kind, state), _events_digest(events)))
        cmd = drv.next(state)
    return cmds, tr


def replay_steps(kind, seed, commands, perturb=None, policy=None):
    """Replay ``commands`` from the seed's initial state. Yields
    (index, command, state_or_None, events_or_None, error_or_None) per step;
    stops after an illegal command. ``perturb`` is (name, k) with name in
    'rng' (draw one extra u32 before step k), 'drop' (skip step k), 'dup'
    (apply step k twice)."""
    mod = _MODULES[kind]
    state, rng = build_scenario(kind, seed, policy)
    out_i = 0
    for k, cmd in enumerate(commands):
        reps = 1
        if perturb and perturb[1] == k:
            if perturb[0] == "drop":
                continue
            if perturb[0] == "dup":
                reps = 2
            if perturb[0] == "rng":
                rng.next_u32()
        for _ in range(reps):
            try:
                state, events = mod.apply(state, cmd, rng)
            except mod.IllegalCommand as e:
                yield out_i, cmd, None, None, "IllegalCommand: %s" % (e,)
                return
            yield out_i, cmd, state, events, None
            out_i += 1


def trace(kind, seed, commands, perturb=None, policy=None):
    return [(_hash(kind, s), _events_digest(e)) if err is None else ("ERR", err)
            for _, _, s, e, err in replay_steps(kind, seed, commands, perturb, policy)]


def trace_digest(tr):
    """SHA-256 hex over the per-step (state hash, events) trace. Each step is
    length-prefixed so the encoding is unambiguous."""
    h = hashlib.sha256()
    for step in tr:
        for part in step:
            b = str(part).encode("utf-8")
            h.update(len(b).to_bytes(4, "little"))
            h.update(b)
    return h.hexdigest()


def _first_diff(a, b):
    for i in range(max(len(a), len(b))):
        if i >= len(a) or i >= len(b) or a[i] != b[i]:
            return i
    return None


def _snapshot_resume(kind, seed, commands, expect, policy=None):
    """Serialise (state, rng) mid-game, restore, finish; compare to ``expect``."""
    mod = _MODULES[kind]
    cut = len(commands) // 2
    state, rng = build_scenario(kind, seed, policy)
    for cmd in commands[:cut]:
        state, _ = mod.apply(state, cmd, rng)
    blob = pickle.dumps((state, rng.state, rng.inc))
    state2, rs, ri = pickle.loads(blob)
    if mod.canonical(state2) != mod.canonical(state):
        raise Divergence("%s seed %d: snapshot round-trip changed canonical form"
                         % (kind, seed))
    rng2 = Pcg32(0)
    rng2.state, rng2.inc = rs, ri
    got = []
    for cmd in commands[cut:]:
        state2, ev = mod.apply(state2, cmd, rng2)
        got.append((_hash(kind, state2), _events_digest(ev)))
    d = _first_diff(got, expect[cut:])
    if d is not None:
        raise Divergence("%s seed %d: snapshot-resume diverges at step %d"
                         % (kind, seed, cut + d))


def run_seed(kind, seed, max_steps=400, policy=None):
    """Run all determinism checks for one seed; raise Divergence on failure.
    Returns (steps played, trace digest of the live run)."""
    cmds, tr1 = generate_log(kind, seed, max_steps, policy)
    _, tr2 = generate_log(kind, seed, max_steps, policy)
    d = _first_diff(tr1, tr2)
    if d is not None:
        raise Divergence("%s seed %d: second live run diverges at step %d"
                         % (kind, seed, d))
    for n in (1, 2):
        d = _first_diff(tr1, trace(kind, seed, cmds, None, policy))
        if d is not None:
            raise Divergence("%s seed %d: replay %d diverges at step %d"
                             % (kind, seed, n, d))
    _snapshot_resume(kind, seed, cmds, tr1, policy)
    return len(cmds), trace_digest(tr1)


def check_seed(kind, seed, max_steps=400, policy=None):
    """As ``run_seed`` but returns only the number of steps played."""
    return run_seed(kind, seed, max_steps, policy)[0]


def soak_digest(lines):
    """Combine per-run ``(label, digest)`` pairs into one hex digest."""
    h = hashlib.sha256()
    for label, dg in lines:
        h.update(("%s=%s\n" % (label, dg)).encode("ascii"))
    return h.hexdigest()


def soak(games, seed_base=0, max_steps=400, kinds=KINDS, out=None,
         matrix=False, digests=None):
    """Run ``games`` seeds of each kind (under every policy combo when
    ``matrix``). Returns a list of failure strings. If ``digests`` is a
    list, ``(label, trace digest)`` is appended for every passing run."""
    combos = policy_matrix() if matrix else [("default", None, None)]
    failures = []
    for name, bpol, apol in combos:
        for kind in kinds:
            pol = bpol if kind == "battle" else apol
            for seed in range(seed_base, seed_base + games):
                tag = "%s/%s" % (name, kind) if matrix else kind
                try:
                    n, dg = run_seed(kind, seed, max_steps, pol)
                    if digests is not None:
                        digests.append(("%s:%d" % (tag, seed), dg))
                    if out:
                        out.write("ok   %-16s seed %-6d %d steps\n" % (tag, seed, n))
                except Divergence as e:
                    failures.append("[%s] %s" % (name, e))
                    if out:
                        out.write("FAIL [%s] %s\n" % (name, e))
    return failures


def main(argv=None):
    ap = argparse.ArgumentParser(prog="h3re.soak", description=__doc__.split("\n")[0])
    ap.add_argument("--games", type=int, default=20, help="seeds per kind")
    ap.add_argument("--seed-base", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--kind", choices=KINDS, action="append")
    ap.add_argument("--policy-matrix", action="store_true",
                    help="also run non-default BattlePolicy/AdventurePolicy combos")
    ap.add_argument("--digest-out", metavar="FILE",
                    help="write the overall trace digest to FILE")
    ap.add_argument("--expect-digest-file", metavar="FILE",
                    help="fail (exit 1) unless the digest equals the one in FILE")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    digests = []
    fails = soak(args.games, args.seed_base, args.max_steps,
                 tuple(args.kind or KINDS), None if args.quiet else sys.stdout,
                 args.policy_matrix, digests)
    digest = soak_digest(digests)
    print("%d failure(s)" % len(fails))
    print("DIGEST %s" % digest)
    status = 1 if fails else 0
    if fails:
        print("bisect with: python3 -m h3re.bisect_tool --kind K --seed S ...")
    if args.digest_out:
        with open(args.digest_out, "w", encoding="ascii") as f:
            f.write(digest + "\n")
    if args.expect_digest_file:
        with open(args.expect_digest_file, "r", encoding="ascii") as f:
            want = f.read().strip()
        if want != digest:
            print("DIGEST MISMATCH: expected %s, got %s" % (want, digest))
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
