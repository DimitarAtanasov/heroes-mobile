"""Text simulator for field battles (``python3 -m h3re battle-sim``).

Loads a JSON scenario (schema: docs/specs/battle-scenario.md), plays one
battle with ``h3re.battle`` and prints the event log and the final state hash.

Choosers decide every command after ``Begin``:

* ``first-legal``  the first entry of ``legal_commands(state)``.
* ``interactive``  asks on stdin; the prompts go to stderr.
* ``ai``           ``h3re.battle_ai.choose(state, side=None)``, imported
                   lazily, only when this chooser is selected.
* ``scripted``     the deterministic player of the golden test in
                   tests/test_battle.py (shoot > attack > advance > defend).

Errors (bad scenario, unreadable file, illegal command, unfinished battle)
are reported as one line on stderr with exit status 1. No traceback.

``--pretty`` (``pretty=True`` in ``run``) replaces the plain event log with a
readable report: a text hex board with a legend at the start and the end (and
every N commands with ``--board-every N``), an event log with aligned columns
and round headers, and a table of surviving stacks. The last three lines
(winner, rounds, state hash) are the same with and without it. Stacks are
drawn as one letter each: attacker stacks A-G, defender stacks H-N, in slot
order. ``#`` is an obstacle and ``.`` an empty hex. ANSI colour is used only
with ``color=True`` and a TTY on stdout.

Stdlib only. Output is ASCII.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import sys
import typing
from pathlib import Path
from typing import Callable, TextIO

from . import battle as B

__all__ = ["CHOOSERS", "CliError", "parse_scenario", "run"]

CHOOSERS = ("first-legal", "interactive", "ai", "scripted")

# A battle that is still running after this many commands is reported as an
# error. The golden scenario finishes well below this.
MAX_COMMANDS = 2000

EXIT_OK = 0
EXIT_FAILURE = 1

_COMMAND_TYPES = (B.Begin, B.Move, B.Attack, B.Shoot, B.Wait, B.Defend)
_TOP_KEYS = ("battle_id", "creatures", "attackers", "defenders",
             "obstacles", "heroes", "policy")
_STACK_KEYS = ("creature", "count", "morale", "luck", "pos")
_SIDE_NAMES = {B.ATTACKER: "attacker", B.DEFENDER: "defender"}


class CliError(Exception):
    """A problem the user can fix. Reported as one line, exit status 1."""


# ------------------------------------------------------------ scenario parsing

def _object(value, path):
    if not isinstance(value, dict):
        raise CliError(f"{path} must be an object")
    return value


def _check_keys(obj, path, allowed):
    unknown = sorted(str(k) for k in obj if k not in allowed)
    if unknown:
        raise CliError(f"{path}: unknown key {unknown[0]!r}")


def _int(value, path):
    if isinstance(value, bool) or not isinstance(value, int):
        raise CliError(f"{path} must be an integer")
    return value


def _pair(value, path):
    if not isinstance(value, list) or len(value) != 2:
        raise CliError(f"{path} must be a [col, row] pair")
    return (_int(value[0], path + "[0]"), _int(value[1], path + "[1]"))


def _freeze(value, path):
    """JSON lists become tuples (recursively); leaves must be scalars."""
    if isinstance(value, list):
        return tuple(_freeze(v, f"{path}[{i}]") for i, v in enumerate(value))
    if isinstance(value, (bool, int, str)):
        return value
    raise CliError(f"{path} contains an unsupported value")


def _typed(value, typ, path):
    if typ is bool:
        if not isinstance(value, bool):
            raise CliError(f"{path} must be true or false")
        return value
    if typ is int:
        return _int(value, path)
    if typ is str:
        if not isinstance(value, str):
            raise CliError(f"{path} must be a string")
        return value
    if typ is tuple:
        if not isinstance(value, list):
            raise CliError(f"{path} must be a list")
        return _freeze(value, path)
    raise CliError(f"{path}: unsupported field type")


def _dataclass_kwargs(obj, cls, path, skip=()):
    """Validate a JSON object against the fields of a battle dataclass.

    Field types come from the dataclass annotations, so the schema follows
    battle.py. Unknown keys and missing required keys are errors.
    """
    hints = typing.get_type_hints(cls)
    fields = [f for f in dataclasses.fields(cls) if f.name not in skip]
    names = {f.name for f in fields}
    _check_keys(obj, path, names)
    required = [f.name for f in fields
                if f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING]
    for name in required:
        if name not in obj:
            raise CliError(f"{path}: missing key {name!r}")
    return {name: _typed(value, hints[name], f"{path}.{name}")
            for name, value in obj.items()}


def _creature(name, obj, path):
    kwargs = _dataclass_kwargs(_object(obj, path), B.Creature, path, skip=("name",))
    for h in kwargs.get("hates", ()):
        if not isinstance(h, str):
            raise CliError(f"{path}.hates must contain creature names")
    return B.Creature(name=name, **kwargs)


def _stack(obj, creatures, path):
    obj = _object(obj, path)
    _check_keys(obj, path, _STACK_KEYS)
    if "creature" not in obj or "count" not in obj:
        raise CliError(f"{path}: needs 'creature' and 'count'")
    name = obj["creature"]
    if not isinstance(name, str) or name not in creatures:
        raise CliError(f"{path}.creature: unknown creature {name!r}")
    pos = None
    if obj.get("pos") is not None:
        pos = _pair(obj["pos"], f"{path}.pos")
    return B.StackSetup(
        creatures[name],
        _int(obj["count"], f"{path}.count"),
        morale=_int(obj.get("morale", 0), f"{path}.morale"),
        luck=_int(obj.get("luck", 0), f"{path}.luck"),
        pos=pos,
    )


def _side(value, creatures, path):
    if not isinstance(value, list) or not 1 <= len(value) <= 7:
        raise CliError(f"{path} must be a list of 1 to 7 stacks")
    return tuple(_stack(v, creatures, f"{path}[{i}]") for i, v in enumerate(value))


def parse_scenario(data):
    """Build ``(battle_id, initial BattleState)`` from decoded scenario JSON.

    Raises CliError for anything malformed. The result is the same state as
    ``battle.create_battle`` gives for the same arguments.
    """
    top = _object(data, "scenario")
    _check_keys(top, "scenario", _TOP_KEYS)
    for key in ("battle_id", "creatures", "attackers", "defenders"):
        if key not in top:
            raise CliError(f"scenario: missing key {key!r}")

    battle_id = top["battle_id"]
    if not isinstance(battle_id, str) or not battle_id:
        raise CliError("scenario.battle_id must be a non-empty string")

    creatures = {}
    for name, obj in _object(top["creatures"], "scenario.creatures").items():
        if not name:
            raise CliError("scenario.creatures: creature names must be non-empty")
        creatures[name] = _creature(name, obj, f"scenario.creatures[{name!r}]")
    attackers = _side(top["attackers"], creatures, "scenario.attackers")
    defenders = _side(top["defenders"], creatures, "scenario.defenders")

    raw_obstacles = top.get("obstacles", [])
    if not isinstance(raw_obstacles, list):
        raise CliError("scenario.obstacles must be a list")
    obstacles = [_pair(o, f"scenario.obstacles[{i}]") for i, o in enumerate(raw_obstacles)]

    raw_heroes = top.get("heroes", [None, None])
    if not isinstance(raw_heroes, list) or len(raw_heroes) != 2:
        raise CliError("scenario.heroes must be a list of two entries (null or hero object)")
    heroes = tuple(
        None if h is None else
        B.Hero(**_dataclass_kwargs(h, B.Hero, f"scenario.heroes[{i}]"))
        for i, h in enumerate(raw_heroes))

    policy_kwargs = _dataclass_kwargs(
        _object(top.get("policy", {}), "scenario.policy"), B.BattlePolicy, "scenario.policy")
    try:
        policy = B.BattlePolicy(**policy_kwargs)
    except ValueError as exc:
        raise CliError(f"scenario.policy: {exc}") from None

    try:
        state = B.create_battle(battle_id, attackers, defenders, obstacles=obstacles,
                                heroes=heroes, policy=policy)
    except ValueError as exc:
        raise CliError(f"scenario: {exc}") from None
    return battle_id, state


def _load_json(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise CliError(f"scenario {path} is not UTF-8 text") from None
    except OSError as exc:
        raise CliError(f"cannot read scenario {path}: {exc.strerror or exc}") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CliError(f"{path} is not valid JSON: {exc.msg} (line {exc.lineno})") from None


# -------------------------------------------------------------------- choosers

def scripted_choice(state):
    """Deterministic player; mirrors ``scripted_choice`` in tests/test_battle.py.

    Shoot if possible, else attack, else advance towards the nearest enemy,
    else defend.
    """
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


def _first_legal(state):
    cmds = B.legal_commands(state)
    if not cmds:
        raise CliError("no legal command in this state")
    return cmds[0]


def _interactive(stdin: TextIO, stderr: TextIO) -> Callable:
    def pick(state):
        cmds = B.legal_commands(state)
        if not cmds:
            raise CliError("no legal command in this state")
        stderr.write(f"round {state.round}, active stack {state.active}; legal commands:\n")
        for i, cmd in enumerate(cmds):
            stderr.write(f"  [{i}] {cmd!r}\n")
        while True:
            stderr.write(f"choose 0-{len(cmds) - 1} (q to quit): ")
            stderr.flush()
            line = stdin.readline()
            stderr.write("\n")  # end the prompt line, whatever the answer
            if line == "":
                raise CliError("input ended before the battle finished")
            text = line.strip()
            if text.lower() in ("q", "quit"):
                raise CliError("aborted by user")
            if text.isdigit() and int(text) < len(cmds):
                return cmds[int(text)]
            stderr.write("not a valid choice\n")
    return pick


def _ai():
    try:
        module = importlib.import_module("h3re.battle_ai")
    except Exception as exc:  # missing or broken module: report, do not crash
        raise CliError(f"chooser 'ai' needs h3re.battle_ai, which cannot be "
                       f"imported ({type(exc).__name__}: {exc})") from None
    choose = getattr(module, "choose", None)
    if not callable(choose):
        raise CliError("h3re.battle_ai has no callable choose(state, side=None)")

    def pick(state):
        try:
            return choose(state, side=None)
        except Exception as exc:
            raise CliError(f"ai chooser failed: {type(exc).__name__}: {exc}") from None
    return pick


def _make_chooser(name, stdin, stderr):
    if name == "first-legal":
        return _first_legal
    if name == "scripted":
        return scripted_choice
    if name == "interactive":
        return _interactive(stdin, stderr)
    if name == "ai":
        return _ai()
    raise CliError(f"unknown chooser {name!r}")


# ------------------------------------------------------------------ simulation

def _log(out: TextIO, cmd, events):
    out.write(f"> {cmd!r}\n")
    for ev in events:
        out.write(f"  {ev!r}\n")


# --------------------------------------------------------------- pretty output

_MARKS = {B.ATTACKER: "ABCDEFG", B.DEFENDER: "HIJKLMN"}
_SIDE_TEXT = {B.ATTACKER: "attacker", B.DEFENDER: "defender"}
_ANSI = {B.ATTACKER: "\x1b[34m", B.DEFENDER: "\x1b[31m"}
_ANSI_RESET = "\x1b[0m"
_CELL = 4    # board columns per hex
_LABEL = 4   # row label "NN  " in front of each board row
_RULE = 64   # width of round headers


def _txt(value) -> str:
    """Text as ASCII: non-ASCII characters are escaped."""
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def _mark(stack) -> str:
    return _MARKS[stack.side][stack.slot]


def _hp(stack) -> int:
    """Total HP of a stack: full units plus the wounded top unit."""
    if not stack.alive:
        return 0
    return (stack.count - 1) * stack.creature.hp + stack.top_hp


def _pos_text(stack) -> str:
    if not stack.alive:
        return "-"
    col, row = stack.pos
    return f"[{col},{row}]"


def _fields(obj) -> str:
    return " ".join(f"{f.name}={ascii(getattr(obj, f.name))}"
                    for f in dataclasses.fields(obj))


def _shifted(row: int, row_offset: str) -> bool:
    """True when the row is drawn half a hex to the right (battle.py geometry:
    ``"even"`` shifts even rows right, ``"odd"`` shifts odd rows right)."""
    return (row % 2 == 0) == (row_offset == "even")


def _table(headers, rows, numeric):
    """Aligned plain-text table lines; ``numeric`` marks right-aligned columns."""
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]

    def fmt(cells):
        parts = [c.rjust(w) if numeric[i] else c.ljust(w)
                 for i, (c, w) in enumerate(zip(cells, widths))]
        return ("  " + "  ".join(parts)).rstrip()

    return [fmt(headers)] + [fmt(r) for r in rows]


def _board_lines(state, color: bool):
    """The hex board as text lines: column digits, then one line per row."""
    off = state.policy.row_offset
    paint = {}
    for s in state.stacks:
        if not s.alive:
            continue
        text = _mark(s)
        if color:
            text = f"{_ANSI[s.side]}{text}{_ANSI_RESET}"
        for hex_ in B.cells(s):
            paint[hex_] = text
    obstacles = set(state.obstacles)
    width = _LABEL + _CELL * B.WIDTH + 2

    tens = [" "] * width
    units = [" "] * width
    for c in range(B.WIDTH):
        x = _LABEL + _CELL * c + 2
        units[x] = str(c % 10)
        if c >= 10:
            tens[x] = str(c // 10)
    lines = ["".join(tens).rstrip(), "".join(units).rstrip()]

    for r in range(B.HEIGHT):
        arr = [" "] * width
        arr[:_LABEL] = list(f"{r:>2}  ")
        shift = _CELL // 2 if _shifted(r, off) else 0
        for c in range(B.WIDTH):
            hex_ = (c, r)
            if hex_ in paint:
                tok = paint[hex_]
            elif hex_ in obstacles:
                tok = "#"
            else:
                tok = "."
            arr[_LABEL + shift + _CELL * c + 2] = tok
        lines.append("".join(arr).rstrip())
    return lines


def _legend_lines(state):
    rows = []
    for s in state.stacks:
        rows.append([_mark(s), _SIDE_TEXT[s.side], _txt(s.creature.name),
                     str(s.count), str(_hp(s)), _pos_text(s),
                     "alive" if s.alive else "dead"])
    return _table(["mark", "side", "creature", "count", "HP", "pos", "state"], rows,
                  (False, False, False, True, True, False, False))


class _Pretty:
    """Renders ``--pretty``: boards, the event log and the survivor table."""

    def __init__(self, out: TextIO, board_every: int, color: bool):
        self.out = out
        self.board_every = board_every
        self.color = color

    def header(self, battle_id, seed, chooser):
        self.out.write(f"== battle {_txt(battle_id)} | seed {seed} | chooser {chooser} ==\n\n")

    def board(self, state, label):
        self.out.write(f"-- board, {label}, round {state.round} --\n")
        for line in _board_lines(state, self.color):
            self.out.write(line + "\n")
        self.out.write("\n")
        self.out.write("legend: A-G attacker, H-N defender, # obstacle, . empty\n")
        for line in _legend_lines(state):
            self.out.write(line + "\n")
        self.out.write("\n")

    def command(self, step, cmd, events, state):
        self.out.write(f"{step:>4}  {type(cmd).__name__:<8} {_fields(cmd)}".rstrip() + "\n")
        for ev in events:
            if isinstance(ev, B.RoundStarted):
                self.out.write(f"== round {ev.round} ".ljust(_RULE, "=") + "\n")
            self.out.write(f"      {type(ev).__name__:<16} {_fields(ev)}".rstrip() + "\n")
        if self.board_every and step % self.board_every == 0:
            self.board(state, f"after step {step}")

    def end(self, state):
        self.board(state, "end")
        self.out.write("== summary ==\n")
        rows = [[_mark(s), _SIDE_TEXT[s.side], _txt(s.creature.name), str(s.count),
                 str(_hp(s)), _pos_text(s)]
                for s in state.stacks if s.alive]
        if rows:
            for line in _table(["mark", "side", "creature", "count", "HP", "pos"], rows,
                               (False, False, False, True, True, False)):
                self.out.write(line + "\n")
        else:
            self.out.write("  no surviving stacks\n")
        self.out.write("\n")


def _record(out: TextIO, pretty, step, cmd, events, state):
    if pretty is None:
        _log(out, cmd, events)
    else:
        pretty.command(step, cmd, events, state)


def _play(state, rng, pick, out: TextIO, pretty=None):
    """Play to the end. Returns ``(state, finished)``; ``finished`` is False
    when the command cap is hit first (e.g. first-legal never attacks).

    ``pretty`` (a ``_Pretty``) renders the steps instead of the plain log.
    Commands, RNG draws and the returned state do not depend on it.
    """
    if pretty is not None:
        pretty.board(state, "start")
    state, events = B.apply(state, B.Begin(), rng)
    _record(out, pretty, 1, B.Begin(), events, state)
    commands = 0
    while state.winner is None:
        if commands >= MAX_COMMANDS:
            return state, False
        cmd = pick(state)
        if not isinstance(cmd, _COMMAND_TYPES):
            raise CliError(f"chooser returned {cmd!r}, which is not a battle command")
        try:
            state, events = B.apply(state, cmd, rng)
        except B.IllegalCommand as exc:
            raise CliError(f"illegal command {cmd!r}: {exc}") from None
        commands += 1
        _record(out, pretty, commands + 1, cmd, events, state)
    return state, True


def _check_pretty_options(pretty, board_every):
    if isinstance(board_every, bool) or not isinstance(board_every, int) or board_every < 0:
        raise CliError("board_every must be an integer of 0 or more")
    if board_every and not pretty:
        raise CliError("--board-every needs --pretty")


def _is_tty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def run(scenario, seed, chooser="first-legal", *, stdin=None, stdout=None, stderr=None,
        pretty=False, board_every=0, color=False):
    """Simulate the battle described by the JSON file ``scenario``.

    Prints the event log, then the winner, round count and state hash, to
    ``stdout``. Returns the exit status: 0 when the battle finished, 1 for
    any reported error (including a battle still running at the command cap,
    whose summary is still printed).

    ``pretty`` prints the readable report described in the module docstring.
    ``board_every`` (needs ``pretty``) adds a board after every N-th step.
    ``color`` adds ANSI colour to the board only when ``stdout`` is a TTY.
    """
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        _check_pretty_options(pretty, board_every)
        battle_id, state = parse_scenario(_load_json(scenario))
        pick = _make_chooser(chooser, stdin, stderr)
        view = None
        if pretty:
            view = _Pretty(stdout, board_every, bool(color) and _is_tty(stdout))
            view.header(battle_id, seed, chooser)
        final, finished = _play(state, B.battle_rng(seed, battle_id), pick, stdout, view)
        if view is not None:
            view.end(final)
    except CliError as exc:
        stderr.write(f"h3re: error: {' '.join(str(exc).split())}\n")
        return EXIT_FAILURE
    winner = _SIDE_NAMES[final.winner] if finished else "none (not finished)"
    stdout.write(f"winner: {winner}\n")
    stdout.write(f"rounds: {final.round}\n")
    stdout.write(f"state hash: {B.state_hash(final)}\n")
    if not finished:
        stderr.write(f"h3re: error: battle not finished after {MAX_COMMANDS} commands "
                     f"(round {final.round})\n")
        return EXIT_FAILURE
    return EXIT_OK
