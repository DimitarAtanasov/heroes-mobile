"""Encounter conformance vectors (Kotlin `h3.sim.encounter` and adventure stage E), from the Python reference.

``generate()`` returns ``{"encounter.json": ...}``; the orchestrator wires it into ``vectors.generate()``
(which owns serialisation). Python (``encounter.py``, ``adventure.py``) is authoritative (ADR-0004,
docs/specs/conformance-encounter.md). Synthetic creatures only. Every random choice (the command plans)
comes from ``derive_stream``, never Python's ``random``.

Contents of ``encounter.json`` (all numbers are integers):

* ``packs``: the shipped rules / battle policy / creatures files (text) and their hashes. The Kotlin engine
  is built from them; the games' ``rules_hash`` is the rules pack hash.
* ``constants``: the content-free adventure tables (as in ``adventure.json``).
* ``cases``: playouts. Per step the command, then either ``error`` (the ``IllegalCommand`` text) or the
  canonical state, SHA-256 and events (an Attack's ``BattleFought`` carries the battle command log, every
  battle event and the final battle hash), the SHA-256 of the battle ``build_battle`` makes for an
  Attack, and the stream (``battle`` or ``adventure``) position after the step.
* ``variants``: hand-built states (rules mismatch, bad content, bad battle setups, removed heroes, ...) with
  a battery of Attack commands each: the error text, or the hash of the legal result.
* ``check_game``, ``setups``: ``check_game`` on hand-built states; ``EncounterSetup`` / ``EncounterPolicy``
  construction from JSON, error text or canonical form.
* ``auto_cases``: battle states with the command ``auto_command`` picks.
* ``streams``: battle ids and the first draws of the two named streams.
* ``golden``: the scripted run pinned in ``tests/test_encounter.py`` (``512b53ca...``).

Usage:  python3 -m h3re.vectors_encounter [--out DIR]
"""

import argparse
import dataclasses
import json
import os
import sys

from . import adventure as A
from . import battle as B
from . import datapack
from . import encounter as E
from . import rules
from . import vectors as V
from .rng import derive_stream

VECTOR_FORMAT = 1
FILE = "encounter.json"
SEED = 2026
GOLDEN_PIN = "512b53ca56c4c5611e718b4b23129984ab5a3c0f6e0de4a7feb48c620568bd60"
INT_MAX = 2 ** 31 - 1

# --------------------------------------------------------------------------
# Creatures and games
# --------------------------------------------------------------------------

CREATURES = (
    B.Creature("pike", 4, 5, 1, 3, 10, 4),
    B.Creature("archer", 6, 3, 2, 3, 10, 4, shots=12),
    B.Creature("wolf", 7, 5, 2, 5, 15, 8, strikes_twice=True),
    B.Creature("gnoll", 6, 7, 2, 4, 13, 6, double_wide=True, hates=("pike",)),
    B.Creature("statue", 1, 1, 1, 1, 50, 0),     # speed 0: can never close in
)

ZOO = CREATURES + (
    B.Creature("drake", 9, 8, 3, 6, 30, 9, flyer=True, double_wide=True, no_morale=True),
    B.Creature("ballista", 10, 5, 4, 8, 20, 3, shots=8, shoots_twice=True, no_range_penalty=True),
    B.Creature("golem", 6, 9, 3, 5, 40, 3, unlimited_retaliation=True, no_melee_penalty=True),
    B.Creature("wisp", 3, 3, 1, 2, 9, 7, no_enemy_retaliation=True, flyer=True),
    B.Creature("hydra", 8, 8, 2, 7, 45, 5, double_wide=True, shots=6),
    B.Creature("ghoul", 5, 4, 1, 4, 12, 6, hates=("wolf", "pike")),
)

# Names that sort differently by code point and by UTF-16 code unit (U+10000 is D800 DC00).
UNI_NAMES = ("Z", "é", "ﬁ", "￿", "\U00010000", "\U0001f600")
UNI = tuple(B.Creature(n, 3 + i, 2 + i % 3, 1, 2 + i, 8 + 2 * i, 3 + i)
            for i, n in enumerate(UNI_NAMES))


def army(table, *parts):
    speed = {c.name: c.speed for c in table}
    return tuple(A.ArmySlot(n, speed[n], k) for n, k in parts)


def grid(w, h, special=None):
    special = special or {}
    return A.Grid(w, h, tuple(A.Tile(special.get((x, y), "grass")) for y in range(h) for x in range(w)))


def setup_of(creatures, policy=E.DEFAULT_POLICY, battle_policy=B.DEFAULT_POLICY, **kw):
    return E.EncounterSetup(creatures, policy=policy, battle_policy=battle_policy, **kw)


def golden_game(policy=E.DEFAULT_POLICY, battle_policy=B.DEFAULT_POLICY, reverse_inputs=False):
    """The game of ``tests/test_encounter.py`` (docs/specs/encounter.md section 7)."""
    a = lambda *p: army(CREATURES, *p)   # noqa: E731
    heroes = (
        A.HeroSetup(0, (1, 1), a(("pike", 30), ("archer", 20))),
        A.HeroSetup(0, (4, 2), a(("wolf", 6))),
        A.HeroSetup(1, (6, 1), a(("gnoll", 12), ("pike", 10))),
        A.HeroSetup(1, (7, 3), a(("pike", 25), ("archer", 6))),
    )
    guards = (A.Guard("wolves", (2, 1), a(("wolf", 8))), A.Guard("camp", (6, 3), a(("gnoll", 20))))
    creatures = CREATURES
    if reverse_inputs:
        guards, creatures = guards[::-1], creatures[::-1]
    return A.create_game("enc", grid(8, 4), (A.Player(), A.Player()), heroes, guards=guards,
                         encounter=setup_of(creatures, policy, battle_policy))


GOLDEN_SCRIPT = (
    A.Begin(),
    A.Attack(0, "wolves"), A.Move(1, (5, 1)), A.Attack(1, 2), A.EndTurn(0),
    A.Attack(3, "camp"), A.Move(2, (2, 1)), A.Attack(2, 0), A.EndTurn(1),
    A.Move(0, (3, 1)), A.EndTurn(0), A.EndTurn(1),
)


def zoo_game(policy=E.DEFAULT_POLICY, battle_policy=B.DEFAULT_POLICY, game_id="zoo"):
    """Three players, 7-, 5-, 3- and 1-slot armies, flyers, shooters, two-hex units, water and rock."""
    a = lambda *p: army(ZOO, *p)   # noqa: E731
    heroes = (
        A.HeroSetup(0, (2, 2), a(("pike", 40), ("archer", 30), ("wolf", 12), ("gnoll", 14),
                                 ("drake", 6), ("ballista", 10), ("golem", 4))),
        A.HeroSetup(0, (2, 4), a(("wisp", 20), ("pike", 12)), logistics=1),
        A.HeroSetup(1, (3, 2), a(("gnoll", 20), ("archer", 25), ("statue", 2), ("wolf", 10),
                                 ("wisp", 15))),
        A.HeroSetup(1, (8, 1), a(("drake", 5), ("golem", 6), ("ballista", 12)), pathfinding=2),
        A.HeroSetup(2, (3, 4), a(("hydra", 8))),
        A.HeroSetup(2, (6, 5), a(("ghoul", 30), ("pike", 9), ("wolf", 7))),
    )
    guards = (
        A.Guard("camp", (4, 4), a(("golem", 5), ("wisp", 9))),
        A.Guard("g-é", (1, 2), a(("wolf", 15))),
        A.Guard("hill", (7, 2), a(("hydra", 4), ("ghoul", 11), ("archer", 8), ("statue", 1))),
    )
    return A.create_game(game_id, grid(10, 6, {(5, 2): "water", (5, 3): "water", (7, 4): "rock"}),
                         (A.Player(), A.Player(), A.Player()), heroes, guards=guards,
                         encounter=setup_of(ZOO, policy, battle_policy))


def draw_game(policy):
    """Two speed-0 armies: the battle can only end by the round limit."""
    a = lambda *p: army(CREATURES, *p)   # noqa: E731
    return A.create_game("draw", grid(8, 4), (A.Player(), A.Player()),
                         (A.HeroSetup(0, (1, 1), a(("statue", 3))),
                          A.HeroSetup(1, (2, 1), a(("statue", 4))),
                          A.HeroSetup(1, (5, 2), a(("pike", 4), ("statue", 2)))),
                         guards=(A.Guard("rock", (1, 2), a(("statue", 1))),),
                         encounter=setup_of(CREATURES, policy))


def unicode_game(policy=E.DEFAULT_POLICY):
    """Creature names and guard ids whose code-point order differs from their UTF-16 order."""
    a = lambda *p: army(UNI, *p)   # noqa: E731
    ids = UNI_NAMES
    tiles = ((1, 2), (3, 2), (5, 2), (1, 4), (3, 4), (5, 4))
    guards = tuple(A.Guard(gid, pos, a((UNI_NAMES[(i + 1) % 6], 4 + i), (UNI_NAMES[(i + 2) % 6], 3)))
                   for i, (gid, pos) in enumerate(zip(ids, tiles)))
    heroes = (A.HeroSetup(0, (2, 2), a((UNI_NAMES[0], 12), (UNI_NAMES[4], 6))),
              A.HeroSetup(0, (2, 4), a((UNI_NAMES[5], 9))),
              A.HeroSetup(1, (4, 2), a((UNI_NAMES[2], 11), (UNI_NAMES[3], 5), (UNI_NAMES[1], 4))),
              A.HeroSetup(1, (4, 4), a((UNI_NAMES[1], 14))))
    return A.create_game("gé\U0001f600", grid(7, 6), (A.Player(), A.Player()), heroes,
                         guards=guards, encounter=setup_of(tuple(reversed(UNI)), policy))


def plain_game():
    """No encounter setup: Attack is refused."""
    a = lambda *p: army(CREATURES, *p)   # noqa: E731
    return A.create_game("plain", grid(6, 4), (A.Player(), A.Player()),
                         (A.HeroSetup(0, (1, 1), a(("pike", 5))), A.HeroSetup(1, (2, 1), a(("pike", 5)))),
                         guards=(A.Guard("g", (1, 2), a(("pike", 2))),))


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------

def jsonable(v):
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: jsonable(getattr(v, f.name)) for f in dataclasses.fields(v)}
    if isinstance(v, (tuple, list)):
        return [jsonable(x) for x in v]
    return v


def encode(e):
    """``{"type": ClassName, <fields>}``; nested dataclasses of a battle log or event list carry a type too."""
    d = {"type": type(e).__name__}
    for f in dataclasses.fields(e):
        v = getattr(e, f.name)
        if f.name in ("log", "battle_events"):
            v = [encode(x) for x in v]
        else:
            v = jsonable(v)
        d[f.name] = v
    return d


def decode(d):
    t = d["type"]
    if t == "Begin":
        return A.Begin()
    if t == "Move":
        return A.Move(d["hero"], tuple(d["dest"]) if isinstance(d["dest"], list) else d["dest"])
    if t == "EndTurn":
        return A.EndTurn(d["player"])
    return A.Attack(d["hero"], d["target"])


def text(state):
    return A.canonical(state).decode("ascii")


def rng_pos(g):
    return [g.state, g.inc]


# --------------------------------------------------------------------------
# Playouts
# --------------------------------------------------------------------------

BAD_ATTACKS = (
    {"type": "Attack", "hero": True, "target": "wolves"},
    {"type": "Attack", "hero": None, "target": 1},
    {"type": "Attack", "hero": -1, "target": 1},
    {"type": "Attack", "hero": 2 ** 40, "target": 1},
    {"type": "Attack", "hero": "0", "target": 1},
    {"type": "Attack", "hero": [0], "target": 1},
    {"type": "Attack", "hero": 0, "target": True},
    {"type": "Attack", "hero": 0, "target": None},
    {"type": "Attack", "hero": 0, "target": -1},
    {"type": "Attack", "hero": 0, "target": 2 ** 40},
    {"type": "Attack", "hero": 0, "target": [1]},
    {"type": "Attack", "hero": 0, "target": {"a": 1}},
    {"type": "Attack", "hero": 0, "target": ""},
    {"type": "Attack", "hero": 0, "target": "no such guard"},
)


def _legal_attacks(state, mine, targets):
    out = []
    for h in mine:
        for t in targets:
            try:
                E.validate(state, A.Attack(h.id, t))
            except A.IllegalCommand:
                continue
            out.append(A.Attack(h.id, t))
    return out


def choose(state, plan):
    """The next command of a playout, from the plan stream. Mostly legal attacks and moves, some
    arbitrary (often illegal) ones."""
    on_map = [h for h in state.heroes if h.pos is not None]
    mine = [h for h in on_map if h.owner == state.current]
    targets = [h.id for h in state.heroes] + [g.id for g in state.guards]
    r = plan.range(0, 100)
    if r < 50 and state.encounter is not None:
        legal = _legal_attacks(state, mine, targets)
        if legal:
            return legal[plan.range(0, len(legal))]
    if r < 75 and mine:
        h = mine[plan.range(0, len(mine))]
        reach = sorted(A.reachable(state, h.id))
        if reach:
            return A.Move(h.id, reach[plan.range(0, len(reach))])
    if r < 87 and state.heroes:
        any_hero = state.heroes[plan.range(0, len(state.heroes))]
        t = targets[plan.range(0, len(targets))] if targets else 0
        return A.Attack(any_hero.id, t)
    if r < 94:
        return decode(BAD_ATTACKS[plan.range(0, len(BAD_ATTACKS))])
    return A.EndTurn(state.current)


def _step(state, cmd, seed):
    """(record, new state) for one command on the stream ``stream_for`` gives."""
    rng = E.stream_for(seed, state, cmd)
    rec = {"command": V_command(cmd), "stream": "battle" if isinstance(cmd, A.Attack) else "adventure"}
    before = A.canonical(state)
    try:
        if isinstance(cmd, A.Attack) and state.day and state.encounter is not None:
            try:
                rec["battle_sha256"] = B.state_hash(E.build_battle(state, cmd))
            except A.IllegalCommand:
                pass
        new, events = A.apply(state, cmd, rng)
    except A.IllegalCommand as e:
        assert A.canonical(state) == before
        rec.pop("battle_sha256", None)
        rec["error"] = str(e)
        rec["rng_after"] = rng_pos(rng)
        return rec, state
    rec["canonical"] = text(new)
    rec["sha256"] = A.state_hash(new)
    rec["events"] = [encode(e) for e in events]
    rec["rng_after"] = rng_pos(rng)
    return rec, new


def V_command(cmd):
    d = {"type": type(cmd).__name__}
    for f in dataclasses.fields(cmd):
        v = getattr(cmd, f.name)
        d[f.name] = list(v) if isinstance(v, tuple) else v
    return d


def _case(name, kind, state, seed, cmds):
    initial = state
    steps = []
    for cmd in cmds:
        rec, state = _step(state, cmd, seed)
        steps.append(rec)
    return {"name": name, "kind": kind, "seed": seed, "game_id": initial.game_id,
            "initial": {"canonical": text(initial), "sha256": A.state_hash(initial)},
            "steps": steps}


def _playout(name, state, seed, n):
    plan = derive_stream(seed, "encounter-vec:%s" % name)
    steps = []
    initial = state
    rec, state = _step(state, A.Attack(0, 1), seed)          # before Begin
    steps.append(rec)
    rec, state = _step(state, A.Begin(), seed)
    steps.append(rec)
    for _ in range(n):
        rec, state = _step(state, choose(state, plan), seed)
        steps.append(rec)
    return {"name": name, "kind": "playout", "seed": seed, "game_id": initial.game_id,
            "initial": {"canonical": text(initial), "sha256": A.state_hash(initial)},
            "steps": steps}


def _policy_json(**over):
    d = jsonable(B.DEFAULT_POLICY)
    d.update(over)
    return d


def _bpol(**over):
    kw = dict(over)
    if "placement_rows" in kw:
        kw["placement_rows"] = tuple(tuple(r) for r in kw["placement_rows"])
    return B.BattlePolicy(**kw)


ALT_BATTLE = _bpol(speed_tie="alternate_last_mover", wait_order="slow_first_alternate", row_offset="odd",
                   edge_columns_walkable=True, range_origin="any_cell", defend_bonus_rounding="ceil",
                   defend_bonus_num=1, defend_bonus_den=3, defend_bonus_min=2)
TIE_BATTLE = _bpol(speed_tie="alternate", wait_order="fifo", range_penalty_beyond=3, bad_luck=True)

POLICY_WTT = E.EncounterPolicy(loser_fate="winner_takes_tile")
POLICY_SLOT = E.EncounterPolicy(slot_mapping="by_slot")
POLICY_BOTH = E.EncounterPolicy(loser_fate="winner_takes_tile", slot_mapping="by_slot")
POLICY_R4 = E.EncounterPolicy(round_limit=4)
POLICY_R1 = E.EncounterPolicy(round_limit=1, loser_fate="winner_takes_tile")

# (name, game builder, seed, plan steps)
PLAYOUTS = (
    ("golden-p0", lambda: golden_game(), SEED, 45),
    ("golden-p1", lambda: golden_game(), SEED + 1, 45),
    ("golden-wtt", lambda: golden_game(POLICY_WTT), SEED + 2, 45),
    ("golden-slot", lambda: golden_game(POLICY_SLOT), SEED + 3, 45),
    ("golden-both-alt", lambda: golden_game(POLICY_BOTH, ALT_BATTLE), SEED + 4, 45),
    ("golden-r4-tie", lambda: golden_game(POLICY_R4, TIE_BATTLE), SEED + 5, 45),
    ("zoo-p0", lambda: zoo_game(), SEED, 50),
    ("zoo-p1", lambda: zoo_game(), 7, 50),
    ("zoo-slot", lambda: zoo_game(POLICY_SLOT), 11, 50),
    ("zoo-wtt-alt", lambda: zoo_game(POLICY_WTT, ALT_BATTLE), 13, 50),
    ("zoo-both-tie", lambda: zoo_game(POLICY_BOTH, TIE_BATTLE), -5, 50),
    ("zoo-bigseed", lambda: zoo_game(), 2 ** 70 + 3, 40),
    ("draw-r3", lambda: draw_game(E.EncounterPolicy(round_limit=3)), SEED, 30),
    ("draw-r100", lambda: draw_game(E.DEFAULT_POLICY), SEED + 1, 20),
    ("unicode", lambda: unicode_game(), SEED, 45),
    ("unicode-slot-wtt", lambda: unicode_game(POLICY_BOTH), 99, 45),
    ("plain", lambda: plain_game(), SEED, 10),
)


# (name, game builder, seed): the scripted golden run under several policies
GOLDEN_RUNS = (
    ("golden", lambda: golden_game(), SEED),
    ("golden-wtt-script", lambda: golden_game(POLICY_WTT), SEED),
    ("golden-slot-script", lambda: golden_game(POLICY_SLOT), SEED),
    ("golden-r4-script", lambda: golden_game(POLICY_R4), SEED),
    ("golden-alt-script", lambda: golden_game(E.DEFAULT_POLICY, ALT_BATTLE), SEED),
    ("golden-seed-2027", lambda: golden_game(), SEED + 1),
    ("golden-reversed", lambda: golden_game(reverse_inputs=True), SEED),
)


def slow_game(slots, pair, policy):
    """Two adjacent heroes with slow, two-hex and blocking stacks: late in the fight a stack has moves
    but none brings it closer (the auto-combat then defends)."""
    names = (pair[0], pair[1], pair[0], pair[1], pair[0], pair[1], pair[0])[:slots]
    att = tuple((n, 3 + i) for i, n in enumerate(names))
    dfn = tuple((n, 3) for n in (pair[1], pair[0], pair[1])[:max(1, slots % 4)])
    return A.create_game("x", grid(8, 4), (A.Player(), A.Player()),
                         (A.HeroSetup(0, (1, 1), army(ZOO, *att)), A.HeroSetup(1, (2, 1), army(ZOO, *dfn))),
                         encounter=setup_of(ZOO, policy))


# (name, game builder, seed): one Attack between two slow armies
SLOW_RUNS = (
    ("slow-golem-gnoll", lambda: slow_game(3, ("golem", "gnoll"), E.DEFAULT_POLICY), 1),
    ("slow-pike-golem-slot", lambda: slow_game(4, ("pike", "golem"), POLICY_SLOT), 1),
    ("slow-gnoll-gnoll-slot", lambda: slow_game(4, ("gnoll", "gnoll"), POLICY_SLOT), 1),
    ("slow-golem-golem-slot", lambda: slow_game(4, ("golem", "golem"), POLICY_SLOT), 1),
)


def slow_cases():
    return [_case(name, "slow", mk(), seed, [A.Begin(), A.Attack(0, 1)]) for name, mk, seed in SLOW_RUNS]


def golden_cases():
    script = list(GOLDEN_SCRIPT)
    out = [_case(name, "golden", mk(), seed, script) for name, mk, seed in GOLDEN_RUNS]
    # the input order of guards and creatures never changes the state
    assert out[-1]["initial"] == out[0]["initial"] and out[-1]["steps"] == out[0]["steps"]
    return out


def all_games():
    """case name -> (initial state, seed) for every case of ``cases``."""
    out = {name: (mk(), seed) for name, mk, seed in GOLDEN_RUNS}
    out.update({name: (mk(), seed) for name, mk, seed in SLOW_RUNS})
    out.update({name: (mk(), seed) for name, mk, seed, _ in PLAYOUTS})
    return out


def decode_battle(d):
    kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in d.items() if k != "type"}
    return getattr(B, d["type"])(**kw)


def playout_cases():
    return [_playout(n, mk(), seed, steps) for n, mk, seed, steps in PLAYOUTS]


# --------------------------------------------------------------------------
# Variants: hand-built states with a battery of Attack commands
# --------------------------------------------------------------------------

def _battery(state):
    """Every (hero, target) pair of real ids, then ill-typed or unknown ids against a few targets."""
    heroes = [h.id for h in state.heroes]
    targets = heroes + [g.id for g in state.guards]
    odd_targets = [len(state.heroes), -1, "nope", "", True, None, 2 ** 40, [0]]
    odd_heroes = [len(state.heroes), -1, True, None, 2 ** 40]
    out = []
    for h in heroes:
        for t in targets + odd_targets:
            out.append({"type": "Attack", "hero": h, "target": t})
    for h in odd_heroes:
        for t in targets[:2] + odd_targets[:3]:
            out.append({"type": "Attack", "hero": h, "target": t})
    return out


def _variant(name, state, seed=SEED, battery=None):
    attempts = []
    for d in (battery if battery is not None else _battery(state)):
        cmd = decode(d)
        rng = E.stream_for(seed, state, cmd)
        before = A.canonical(state)
        try:
            new, _ = A.apply(state, cmd, rng)
        except A.IllegalCommand as e:
            assert A.canonical(state) == before
            attempts.append({"command": d, "error": str(e), "rng_after": rng_pos(rng)})
        else:
            attempts.append({"command": d, "ok": A.state_hash(new), "rng_after": rng_pos(rng)})
    return {"name": name, "seed": seed, "canonical": text(state), "sha256": A.state_hash(state),
            "attempts": attempts}


def _started(state):
    return A.apply(state, A.Begin(), E.stream_for(SEED, state, A.Begin()))[0]


def _replace_setup(state, **kw):
    return dataclasses.replace(state, encounter=dataclasses.replace(state.encounter, **kw))


def _hero(state, i, **kw):
    hs = list(state.heroes)
    hs[i] = dataclasses.replace(hs[i], **kw)
    return dataclasses.replace(state, heroes=tuple(hs))


def _guard(state, i, **kw):
    gs = list(state.guards)
    gs[i] = dataclasses.replace(gs[i], **kw)
    return dataclasses.replace(state, guards=tuple(gs))


def _creature_swap(state, name, **kw):
    cs = tuple(dataclasses.replace(c, **kw) if c.name == name else c for c in state.encounter.creatures)
    return _replace_setup(state, creatures=cs)


def _one_pair(*pairs):
    return [{"type": "Attack", "hero": h, "target": t} for h, t in pairs]


def variants():
    g = _started(golden_game())
    out = [_variant("golden-started", g), _variant("golden-before-begin", golden_game())]
    out.append(_variant("no-encounter", _started(plain_game())))
    out.append(_variant("rules-hash-mismatch", _replace_setup(g, rules_hash="0" * 64)))
    # content: the speed differs / the creature is missing, on the attacker's or the defender's side
    ws = _guard(g, 1, army=(A.ArmySlot("wolf", 7, 8),))
    out.append(_variant("content-speed-defender", ws))
    out.append(_variant("content-missing-attacker",
                        _hero(g, 0, army=(A.ArmySlot("pike", 4, 3), A.ArmySlot("ghost", 4, 1)))))
    out.append(_variant("content-missing-defender",
                        _guard(g, 1, army=(A.ArmySlot("ghöst'\"", 4, 1),))))
    out.append(_variant("content-both-missing",
                        _hero(_guard(g, 1, army=(A.ArmySlot("ghost2", 4, 1),)), 0,
                              army=(A.ArmySlot("ghost", 4, 1),))))
    # battle set-up failures (ValueError from create_battle / check_state, wrapped)
    rows_off = tuple(tuple(99 for _ in range(i + 1)) for i in range(7))
    out.append(_variant("bad-placement-offgrid", _replace_setup(g, battle_policy=_bpol(placement_rows=rows_off))))
    rows_same = tuple(tuple(5 for _ in range(i + 1)) for i in range(7))
    out.append(_variant("bad-placement-collision", _replace_setup(g, battle_policy=_bpol(placement_rows=rows_same))))
    rows7 = tuple(tuple(r) for r in B.DEFAULT_POLICY.placement_rows[:6]) + ((5,) * 7,)
    z = _started(zoo_game(POLICY_SLOT))
    out.append(_variant("bad-by-slot-collision", _replace_setup(z, battle_policy=_bpol(placement_rows=rows7))))
    out.append(_variant("creature-bad-damage", _creature_swap(g, "pike", dmg_min=5, dmg_max=2)))
    out.append(_variant("creature-zero-damage", _creature_swap(g, "archer", dmg_min=0)))
    out.append(_variant("creature-zero-hp", _creature_swap(g, "wolf", hp=0)))
    out.append(_variant("creature-big-hp", _creature_swap(g, "pike", hp=INT_MAX)))
    out.append(_variant("creature-speed-mismatch-negative", _creature_swap(g, "statue", speed=-1)))
    out.append(_variant("count-times-damage-overflow",
                        _hero(g, 0, army=(A.ArmySlot("pike", 4, INT_MAX), A.ArmySlot("archer", 4, 20)))))
    out.append(_variant("count-times-hp-overflow",
                        _hero(_creature_swap(g, "pike", dmg_max=1, dmg_min=1), 0,
                              army=(A.ArmySlot("pike", 4, INT_MAX), A.ArmySlot("archer", 4, 20)))))
    out.append(_variant("defense-sum-overflow", _creature_swap(g, "wolf", defense=INT_MAX)))
    out.append(_variant("attack-at-bounds", _creature_swap(g, "wolf", attack=INT_MAX, defense=-INT_MAX - 1)))
    out.append(_variant("defend-bonus-min-huge",
                        _replace_setup(g, battle_policy=_bpol(defend_bonus_min=INT_MAX))))
    # removed heroes and a lost guard from real play
    s = _started(golden_game())
    for cmd in GOLDEN_SCRIPT[1:5]:
        s = A.apply(s, cmd, E.stream_for(SEED, s, cmd))[0]
    out.append(_variant("after-hero-removed", s))
    out.append(_variant("after-hero-removed-p1", dataclasses.replace(s, current=1)))
    # another current player and a hero that is far away / on the map edge
    out.append(_variant("current-1", dataclasses.replace(g, current=1)))
    z0 = _started(zoo_game())
    out.append(_variant("zoo-started", z0))
    out.append(_variant("zoo-current-2", dataclasses.replace(z0, current=2)))
    diag = A.create_game("d", grid(5, 4), (A.Player(), A.Player()),
                         (A.HeroSetup(0, (1, 1), army(CREATURES, ("pike", 3))),
                          A.HeroSetup(1, (2, 2), army(CREATURES, ("pike", 3))),
                          A.HeroSetup(1, (0, 0), army(CREATURES, ("pike", 3)))),
                         policy=A.AdventurePolicy(diagonal_moves=False),
                         encounter=setup_of(CREATURES))
    out.append(_variant("no-diagonals", _started(diag)))
    corner = A.create_game("c", grid(5, 4, {(2, 1): "rock", (1, 2): "rock"}), (A.Player(), A.Player()),
                           (A.HeroSetup(0, (1, 1), army(CREATURES, ("pike", 3))),
                            A.HeroSetup(1, (2, 2), army(CREATURES, ("pike", 3)))),
                           policy=A.AdventurePolicy(diagonal_corner_cut=False),
                           encounter=setup_of(CREATURES))
    out.append(_variant("no-corner-cut", _started(corner)))
    out.append(_variant("corner-cut-allowed", _started(dataclasses.replace(
        corner, policy=A.AdventurePolicy(diagonal_corner_cut=True)))))
    return out


# --------------------------------------------------------------------------
# check_game and EncounterSetup construction
# --------------------------------------------------------------------------

def check_game_cases():
    g = golden_game()
    out = []

    def add(name, state):
        try:
            E.check_game(state)
            err = None
        except ValueError as e:
            err = str(e)
        out.append({"name": name, "canonical": text(state), "error": err})

    add("valid", g)
    add("hero-unknown", _hero(g, 2, army=(A.ArmySlot("gnoll", 6, 1), A.ArmySlot("ghost", 4, 1))))
    add("hero-speed", _hero(g, 1, army=(A.ArmySlot("wolf", 9, 2),)))
    add("guard-unknown", _guard(g, 0, army=(A.ArmySlot("ghost", 4, 1),)))
    add("guard-speed", _guard(g, 1, army=(A.ArmySlot("wolf", 7, 2),)))
    add("hero-before-guard", _guard(_hero(g, 3, army=(A.ArmySlot("zzz", 1, 1),)), 0,
                                    army=(A.ArmySlot("yyy", 1, 1),)))
    add("first-slot-first", _hero(g, 0, army=(A.ArmySlot("b", 1, 1), A.ArmySlot("a", 1, 1))))
    add("name-escapes", _hero(g, 0, army=(A.ArmySlot("a'b\"c\n\x00é\U0001f600\ud800", 1, 1),)))
    add("name-single-quote", _hero(g, 0, army=(A.ArmySlot("it's", 1, 1),)))
    add("name-empty", _hero(g, 0, army=(A.ArmySlot("", 1, 1),)))
    add("speed-zero", _hero(g, 0, army=(A.ArmySlot("statue", 1, 1),)))
    removed = dataclasses.replace(g.heroes[1], pos=None, army=(), mp=0, mp_max=0)
    add("removed-hero-ok", dataclasses.replace(g, heroes=(g.heroes[0], removed) + g.heroes[2:]))
    add("guard-id-repr", _guard(g, 0, id="o'k", army=(A.ArmySlot("ghost", 4, 1),)))
    add("guard-id-unicode", _guard(g, 0, id="café\U0001f600", army=(A.ArmySlot("ghost", 4, 1),)))
    add("guard-id-both-quotes", _guard(g, 0, id="a'\"b", army=(A.ArmySlot("ghost", 4, 1),)))
    add("unicode-game", unicode_game())
    return out


def _creature_json(c):
    return jsonable(c)


def build_setup(d):
    """Python ``EncounterSetup`` from its JSON form (the order Kotlin parses in: policy, battle policy, creatures)."""
    pol = E.EncounterPolicy(**d["policy"])
    bp = d["battle_policy"]
    bp = B.BattlePolicy(**dict(bp, placement_rows=tuple(tuple(r) for r in bp["placement_rows"]),
                               bad_morale_table=tuple(bp["bad_morale_table"])))
    cs = tuple(B.Creature(**dict(c, hates=tuple(c["hates"]))) for c in d["creatures"])
    return E.EncounterSetup(cs, policy=pol, battle_policy=bp, rules_hash=d["rules_hash"])


def _setup_json(creatures=CREATURES, policy=None, battle_policy=None, rules_hash=None):
    return {"creatures": [_creature_json(c) for c in creatures],
            "policy": jsonable(policy or E.DEFAULT_POLICY),
            "battle_policy": battle_policy if battle_policy is not None else _policy_json(),
            "rules_hash": rules.RULES_HASH if rules_hash is None else rules_hash}


def setup_cases():
    base = _setup_json()
    out = []

    def add(name, d):
        try:
            s = build_setup(d)
        except ValueError as e:
            out.append({"name": name, "setup": d, "error": str(e), "canonical": None})
            return
        out.append({"name": name, "setup": d, "error": None,
                    "canonical": json.dumps(jsonable(s), sort_keys=True, separators=(",", ":"))})

    def with_(**over):
        d = json.loads(json.dumps(base))
        d.update(over)
        return d

    pol = lambda **o: dict(jsonable(E.DEFAULT_POLICY), **o)   # noqa: E731
    add("default", base)
    add("creatures-reversed", with_(creatures=list(reversed(base["creatures"]))))
    add("creatures-unicode-unsorted", _setup_json(UNI))
    add("creatures-unicode-sorted-desc", _setup_json(tuple(reversed(UNI))))
    add("creatures-empty", with_(creatures=[]))
    add("creatures-one", _setup_json(CREATURES[:1]))
    add("creatures-zoo", _setup_json(ZOO))
    add("rules-hash-other", with_(rules_hash="ab" * 32))
    add("rules-hash-empty", with_(rules_hash=""))
    dup = list(base["creatures"]) + [base["creatures"][0]]
    add("duplicate-creature", with_(creatures=dup))
    add("duplicate-creature-differs", with_(creatures=dup[:-1] + [dict(base["creatures"][0], hp=99)]))
    for k, v in (("loser_fate", "x"), ("loser_fate", ""), ("loser_fate", None), ("loser_fate", True),
                 ("slot_mapping", "x"), ("slot_mapping", 3), ("round_limit", 0), ("round_limit", -4),
                 ("round_limit", True), ("round_limit", False), ("round_limit", None),
                 ("round_limit", "100"), ("round_limit", [1])):
        add("policy-%s-%r" % (k, v), with_(policy=pol(**{k: v})))
    for v in (1, 2, 100, INT_MAX, 2 ** 31, 2 ** 62):
        add("policy-round_limit-%d" % v, with_(policy=pol(round_limit=v)))
    add("policy-winner_takes_tile-by_slot", with_(policy=pol(loser_fate="winner_takes_tile",
                                                              slot_mapping="by_slot")))
    # order: policy before battle policy before the duplicate check
    add("order-policy-before-battle-policy", with_(policy=pol(round_limit=0),
                                                   battle_policy=_policy_json(row_offset="x")))
    add("order-policy-before-duplicate", with_(policy=pol(loser_fate="x"), creatures=dup))
    add("order-battle-policy-before-duplicate", with_(battle_policy=_policy_json(speed_tie="x"), creatures=dup))
    for name, over in (("row_offset", {"row_offset": "up"}), ("speed_tie", {"speed_tie": "x"}),
                       ("wait_order", {"wait_order": "x"}), ("range_origin", {"range_origin": "x"}),
                       ("defend_bonus_rounding", {"defend_bonus_rounding": "round"}),
                       ("defend_den_0", {"defend_bonus_den": 0}),
                       ("defend_num_neg", {"defend_bonus_num": -1}),
                       ("range_penalty_neg", {"range_penalty_beyond": -1}),
                       ("morale_table_short", {"bad_morale_table": [1, 2]}),
                       ("morale_table_decreasing", {"bad_morale_table": [3, 2, 1]}),
                       ("morale_table_negative", {"bad_morale_table": [-1, 2, 3]}),
                       ("rows_short", {"placement_rows": [[5]] * 6}),
                       ("rows_wrong_size", {"placement_rows": [[5], [2, 8], [2, 5, 8], [0, 4, 6, 10],
                                                               [0, 2, 5, 8, 10], [0, 2, 4, 6, 8, 10],
                                                               [0, 2, 4, 6, 8, 10]]}),
                       ("rows_negative_ok", {"placement_rows": [[-1], [2, 8], [2, 5, 8], [0, 4, 6, 10],
                                                                [0, 2, 5, 8, 10], [0, 2, 4, 6, 8, 10],
                                                                [0, 2, 4, 5, 6, 8, 10]]}),
                       ("defend_min_huge_ok", {"defend_bonus_min": INT_MAX}),
                       ("odd_rows_and_edges", {"row_offset": "odd", "edge_columns_walkable": True}),
                       ("alt_everything", {"speed_tie": "alternate_last_mover",
                                           "wait_order": "slow_first_alternate", "range_origin": "any_cell",
                                           "defend_bonus_rounding": "ceil", "bad_luck": True,
                                           "good_morale_after_wait": True})):
        add("battle-policy-" + name, with_(battle_policy=_policy_json(**over)))
    return out


# --------------------------------------------------------------------------
# Battle states and auto_command
# --------------------------------------------------------------------------

def _no_progress(bs):
    """True when the active stack can move, cannot attack or shoot, and no move brings its head closer."""
    legal = B.legal_commands(bs)
    moves = [c for c in legal if isinstance(c, B.Move)]
    if not moves or any(isinstance(c, (B.Attack, B.Shoot)) for c in legal):
        return False
    st = bs.stacks[bs.active]
    foes = [x for e in bs.stacks if e.alive and e.side != st.side for x in B.cells(e)]
    off = bs.policy.row_offset

    def gap(h):
        return min(B.hex_distance(h, x, off) for x in foes)
    return min(gap(c.dest) for c in moves) >= gap(st.pos)


def auto_cases(cases):
    """Sample battle states from the fights of every case, with the command ``auto_command`` picks (every
    kind of command is represented several times; every state where no move helps is kept)."""
    out = []
    seen = set()
    kinds = {}
    stalls = 0
    games = all_games()
    for case in cases:
        state, seed = games[case["name"]]
        for d in [s["command"] for s in case["steps"]]:
            cmd = decode(d)
            if isinstance(cmd, A.Attack):
                try:
                    bs = E.build_battle(state, cmd)
                except A.IllegalCommand:
                    bs = None
                if bs is not None:
                    rng = B.battle_rng(seed, bs.battle_id)
                    limit = state.encounter.policy.round_limit
                    k = 0
                    while bs.winner is None and not (bs.started and bs.round > limit):
                        c = E.auto_command(bs)
                        kind = type(c).__name__
                        key = B.state_hash(bs)
                        stall = bs.started and _no_progress(bs)
                        if key not in seen and (k < 2 or k % 11 == 0 or kinds.get(kind, 0) < 10 or stall):
                            seen.add(key)
                            kinds[kind] = kinds.get(kind, 0) + 1
                            stalls += stall
                            out.append({"battle": B.canonical(bs).decode("ascii"),
                                        "command": V_command(c), "sha256": key, "stall": bool(stall)})
                        bs, _ = B.apply(bs, c, rng)
                        k += 1
            try:
                state = A.apply(state, cmd, E.stream_for(seed, state, cmd))[0]
            except A.IllegalCommand:
                pass
    assert stalls >= 5
    return out


# --------------------------------------------------------------------------
# Streams
# --------------------------------------------------------------------------

def stream_cases():
    out = []
    for gid, battles, seed in (("enc", 0, 2026), ("enc", 3, 2026), ("", 0, 0), ("a:b", 12, -1),
                               ("gé\U0001f600", 7, 2 ** 64 + 5), ("x", 99, -2 ** 70),
                               ("long" * 40, 1000, 31337)):
        state = dataclasses.replace(golden_game(), game_id=gid, battles=battles)
        bid = E.battle_id(state)
        b = E.encounter_rng(seed, state)
        a = E.stream_for(seed, state, A.EndTurn(0))
        s = E.stream_for(seed, state, A.Attack(0, "wolves"))
        assert rng_pos(s) == rng_pos(derive_stream(seed, "battle:%s" % bid))
        out.append({"canonical": text(state), "seed": seed, "battle_id": bid,
                    "battle_draws": [b.next_u32() for _ in range(4)],
                    "adventure_draws": [a.next_u32() for _ in range(4)]})
    return out


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

def packs():
    out = {}
    for key, name in (("rules", "rules.json"), ("battle_policy", "battle_policy.json"),
                      ("creatures", "creatures.json")):
        with open(os.path.join(datapack.DEFAULT_DIR, name), encoding="utf-8") as f:
            out[key] = f.read()
    out.update(rules_hash=rules.RULES_HASH, policy_hash=B.POLICY_HASH,
               creatures_hash=datapack.load_dir().content_hash)
    return out


def constants():
    return {
        "terrain_cost": dict(sorted(A.TERRAIN_COST.items())),
        "impassable": list(A.IMPASSABLE),
        "roads": list(A.ROADS),
        "speed_mp": list(A._SPEED_MP),
        "logistics_pct": list(A.LOGISTICS_PCT),
        "resource_names": list(A.RESOURCE_NAMES),
        "mine_output": {k: jsonable(v) for k, v in sorted(A.MINE_OUTPUT.items())},
    }


def golden_block(case):
    last = case["steps"][-1]
    final = json.loads(last["canonical"])
    fought = [e for s in case["steps"] if "events" in s for e in s["events"] if e["type"] == "BattleFought"]
    return {"hash": last["sha256"], "day": final["day"], "battles": final["battles"],
            "winners": [e["winner"] for e in fought], "rounds": [e["rounds"] for e in fought],
            "battle_hashes": [e["battle_hash"] for e in fought], "pin": GOLDEN_PIN}


def generate():
    golden = golden_cases()
    cases = golden + slow_cases() + playout_cases()
    return {FILE: {
        "format": VECTOR_FORMAT,
        "description": "encounter.py and adventure Attack: playouts, variants, set-up checks "
                       "(docs/specs/conformance-encounter.md)",
        "packs": packs(),
        "constants": constants(),
        "cases": cases,
        "variants": variants(),
        "check_game": check_game_cases(),
        "setups": setup_cases(),
        "auto_cases": auto_cases(cases),
        "streams": stream_cases(),
        "golden": golden_block(golden[0]),
    }}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=V.DEFAULT_OUT)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    for name, doc in generate().items():
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(V._dump(doc))
        print("wrote", os.path.join(args.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
