"""Read-only battle presenter: ``view(state)`` -> JSON-serialisable dict.

A view-model for the touch UI (engine-design.md 1.5/1.6, presenter.md). It
reads a ``BattleState`` through the public battle API only; it never draws from
an RNG, never mutates the state and uses ints, bools, strings, lists and dicts
(no floats). Not a simulation module: it feeds the UI, not the state.
"""

import json

from . import battle as B

VIEW_VERSION = 1

__all__ = ["VIEW_VERSION", "view", "view_json", "command_to_dict",
           "candidate_commands", "candidate_actions"]


def _hx(h):
    return [h[0], h[1]]


def command_to_dict(cmd):
    """Stable dict form of a battle command (the UI sends one back)."""
    if isinstance(cmd, B.Begin):
        return {"type": "begin"}
    if isinstance(cmd, B.Wait):
        return {"type": "wait", "stack": cmd.stack}
    if isinstance(cmd, B.Defend):
        return {"type": "defend", "stack": cmd.stack}
    if isinstance(cmd, B.Move):
        return {"type": "move", "stack": cmd.stack, "dest": _hx(cmd.dest)}
    if isinstance(cmd, B.Shoot):
        return {"type": "shoot", "stack": cmd.stack, "target": cmd.target}
    if isinstance(cmd, B.Attack):
        return {"type": "attack", "stack": cmd.stack, "target": cmd.target,
                "from_hex": None if cmd.from_hex is None else _hx(cmd.from_hex)}
    raise ValueError("unknown command %r" % (cmd,))


def _total_hp(s):
    return (s.count - 1) * s.creature.hp + s.top_hp if s.count > 0 else 0


def _stack_view(state, s):
    c = s.creature
    return {
        "id": s.id, "side": s.side, "slot": s.slot,
        "creature": c.name, "count": s.count, "alive": s.alive,
        "top_hp": s.top_hp, "unit_hp": c.hp, "hp": _total_hp(s),
        "speed": c.speed, "shots": s.shots, "shooter": c.shooter,
        "double_wide": c.double_wide, "flyer": c.flyer,
        "defending": s.defending, "morale": s.morale, "luck": s.luck,
        "active": s.id == state.active,
        "pos": _hx(s.pos),
        "cells": [_hx(x) for x in B.cells(s)],
    }


def _grid(state):
    occ = {}
    for s in state.stacks:
        if s.alive:
            for i, cell in enumerate(B.cells(s)):
                occ[cell] = (s.id, "head" if i == 0 else "tail")
    obstacles = set(state.obstacles)
    walk_edges = state.policy.edge_columns_walkable
    rows = []
    for r in range(B.HEIGHT):
        row = []
        for c in range(B.WIDTH):
            sid, part = occ.get((c, r), (None, None))
            row.append({
                "c": c, "r": r,
                "playable": bool(walk_edges or 1 <= c <= B.WIDTH - 2),
                "obstacle": (c, r) in obstacles,
                "stack": sid, "part": part,
            })
        rows.append(row)
    return rows


def _queue(state):
    done = set(state.done)
    waited = set(state.waited)
    out = []
    for i in B.round_order(state):
        if i == state.active:
            status = "active"
        elif i in done:
            status = "done"
        elif i in waited:
            status = "waited"
        else:
            status = "pending"
        out.append({"stack": i, "status": status})
    return out


def _preview(state, att, tgt, ranged):
    p = B.strike_preview(state, att, tgt, ranged)
    return {"floor": p.floor, "expected": p.expected, "ceiling": p.ceiling}


def _actions(state):
    cmds = B.legal_commands(state)
    global_cmds = []
    by_hex = {}

    def slot(h):
        return by_hex.setdefault(h, {"hex": _hx(h), "move": None, "target": None})

    def target_slot(tid):
        e = slot(state.stacks[tid].pos)
        if e["target"] is None:
            e["target"] = {"stack": tid, "shoot": None, "attacks": []}
        return e["target"]

    for cmd in cmds:
        d = command_to_dict(cmd)
        if isinstance(cmd, (B.Begin, B.Wait, B.Defend)):
            global_cmds.append({"command": d})
        elif isinstance(cmd, B.Move):
            slot(cmd.dest)["move"] = {"command": d}
        elif isinstance(cmd, B.Shoot):
            target_slot(cmd.target)["shoot"] = {
                "command": d, "preview": _preview(state, cmd.stack, cmd.target, True)}
        else:
            st = state.stacks[cmd.stack]
            frm = st.pos if cmd.from_hex is None else tuple(cmd.from_hex)
            target_slot(cmd.target)["attacks"].append({
                "from_hex": _hx(frm), "command": d,
                "preview": _preview(state, cmd.stack, cmd.target, False)})
    return {"global": global_cmds,
            "by_hex": [by_hex[h] for h in sorted(by_hex)]}


def view(state):
    """Versioned, read-only view-model of ``state`` (see presenter.md)."""
    if state.winner is not None:
        phase = "over"
    elif not state.started:
        phase = "not_started"
    else:
        phase = "active"
    return {
        "view_version": VIEW_VERSION,
        "battle_id": state.battle_id,
        "phase": phase,
        "round": state.round,
        "winner": state.winner,
        "active": state.active if phase == "active" else None,
        "bonus_turn": state.bonus_turn,
        "morale_pending": state.morale_pending,
        "grid": {"width": B.WIDTH, "height": B.HEIGHT, "rows": _grid(state)},
        "stacks": [_stack_view(state, s) for s in state.stacks],
        "queue": _queue(state),
        "actions": _actions(state),
    }


def view_json(state):
    """Canonical JSON text of ``view(state)``: sorted keys, no spaces."""
    return json.dumps(view(state), sort_keys=True, separators=(",", ":"))


def _enemy_at(state, h):
    """Id of the living stack of the side not on turn that covers ``h``."""
    if state.active is None:
        return None
    me = state.stacks[state.active].side
    for s in state.stacks:
        if s.alive and s.side != me and h in B.cells(s):
            return s.id
    return None


def candidate_commands(state, hex_):
    """Battle commands a tap on ``hex_`` can mean, in ``legal_commands`` order.

    A tap on any cell of a living enemy stack (relative to the active stack) gives its Shoot and Attack
    commands (one Attack per from-hex "petal"); a tap on an empty reachable
    hex gives its Move; anything else gives an empty list. The UI previews on
    the first tap (see ``candidate_actions``) and commits on the second.
    """
    h = (hex_[0], hex_[1])
    cmds = B.legal_commands(state)
    tgt = _enemy_at(state, h)
    out = []
    for cmd in cmds:
        if isinstance(cmd, B.Move):
            if cmd.dest == h:
                out.append(cmd)
        elif isinstance(cmd, (B.Attack, B.Shoot)):
            if tgt is not None and cmd.target == tgt:
                out.append(cmd)
    return out


def candidate_actions(state, hex_):
    """The ``actions.by_hex`` entry for a tapped hex (any cell of a stack), or None."""
    h = (hex_[0], hex_[1])
    tgt = _enemy_at(state, h)
    key = h if tgt is None else state.stacks[tgt].pos
    for e in _actions(state)["by_hex"]:
        if tuple(e["hex"]) == key:
            return e
    return None
