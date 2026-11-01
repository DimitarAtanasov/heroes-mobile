"""Save/replay file format for battles (spec: docs/specs/replay.md).

A replay file is canonical JSON (sorted keys, no whitespace, ASCII, integers and
strings only, no timestamps) holding a header, a body (scenario + command log)
and a SHA-256 checksum over header and body. ``record`` builds the bytes,
``verify`` replays the battle and checks every pinned hash, ``info`` parses the
header after the integrity checks. Stdlib only. Not a simulation module.
"""

from __future__ import annotations

import hashlib
import json

from . import battle as B
from . import battle_cli, datapack, rules, soak

__all__ = [
    "FORMAT_VERSION", "KIND_BATTLE", "KINDS", "ReplayError", "Malformed",
    "Truncated", "Tampered", "UnsupportedVersion", "UnsupportedKind",
    "MismatchedRulesPack", "MismatchedPolicy", "MismatchedCreatures",
    "Diverged", "record", "verify", "load", "info", "run_chooser",
]

FORMAT_VERSION = 1
KIND_BATTLE = "battle"
# "adventure" is reserved for later saves; files of an unlisted kind are refused.
KINDS = (KIND_BATTLE,)
RESERVED_KINDS = ("adventure",)

_HEADER_KEYS = ("battle_id", "command_count", "creatures_hash", "final_hash",
                "format_version", "kind", "policy_hash", "rules_hash", "scenario_hash",
                "seed")
_DOC_KEYS = ("body", "checksum", "header")
_BODY_KEYS = ("commands", "scenario")


class ReplayError(ValueError):
    """Base class of every replay failure (a ValueError so the CLI reports it)."""


class Malformed(ReplayError):
    """Not a replay file, or a structurally invalid one."""


class Truncated(ReplayError):
    """The data ends before the document does."""


class Tampered(ReplayError):
    """The checksum does not match the header and body."""


class UnsupportedVersion(ReplayError):
    """format_version is not one this code reads."""


class UnsupportedKind(ReplayError):
    """The save kind is reserved or unknown."""


class MismatchedRulesPack(ReplayError):
    """The file was made under a different rules pack."""


class MismatchedPolicy(ReplayError):
    """The file was made under a different battle policy pack."""


class MismatchedCreatures(ReplayError):
    """The file was made under a different creatures pack."""


class Diverged(ReplayError):
    """Replaying the commands fails or ends in a different final state."""


# ------------------------------------------------------------------ helpers

def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _reject_float(text):
    raise Malformed("floats are not allowed")


def _no_const(text):
    raise Malformed("non-finite number")


def _check_plain(obj, path="scenario"):
    """Only dict (str keys), list, str, int, bool and None may appear."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise Malformed(f"{path}: keys must be strings")
            _check_plain(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_plain(v, f"{path}[{i}]")
    elif not (obj is None or isinstance(obj, (str, int, bool))):
        raise Malformed(f"{path}: unsupported value type {type(obj).__name__}")


def _pack_hashes():
    return {"rules_hash": rules.RULES_HASH, "policy_hash": B.POLICY_HASH,
            "creatures_hash": datapack.load_dir().content_hash}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _seal(header, body):
    doc = {"header": header, "body": body}
    doc["checksum"] = _sha(_canon({"header": header, "body": body}))
    return _canon(doc)


def _play(scenario, seed, commands):
    """Apply ``commands`` to the scenario's initial state; return the final state."""
    try:
        battle_id, state = battle_cli.parse_scenario(scenario)
    except battle_cli.CliError as exc:
        raise Malformed(f"bad scenario: {' '.join(str(exc).split())}") from None
    rng = B.battle_rng(seed, battle_id)
    for i, cmd in enumerate(commands):
        try:
            state, _ = B.apply(state, cmd, rng)
        except B.IllegalCommand as exc:
            raise Diverged(f"illegal command at step {i}: {exc}") from None
    return battle_id, state


# ------------------------------------------------------------------- record

def run_chooser(scenario, seed, chooser="first-legal", *, stdin=None, stderr=None):
    """Play ``scenario`` with a named chooser; return the command list (starts
    with Begin). Stops when the battle ends or after ``battle_cli.MAX_COMMANDS``."""
    import sys
    stdin = sys.stdin if stdin is None else stdin
    stderr = sys.stderr if stderr is None else stderr
    try:
        battle_id, state = battle_cli.parse_scenario(scenario)
        pick = battle_cli._make_chooser(chooser, stdin, stderr)
        rng = B.battle_rng(seed, battle_id)
        cmds = [B.Begin()]
        state, _ = B.apply(state, cmds[0], rng)
        while state.winner is None:
            if len(cmds) > battle_cli.MAX_COMMANDS:
                raise Malformed(f"battle not finished after {battle_cli.MAX_COMMANDS} commands")
            cmd = pick(state)
            if not isinstance(cmd, battle_cli._COMMAND_TYPES):
                raise Malformed(f"chooser returned {cmd!r}, not a battle command")
            try:
                state, _ = B.apply(state, cmd, rng)
            except B.IllegalCommand as exc:
                raise Malformed(f"illegal command {cmd!r}: {exc}") from None
            cmds.append(cmd)
    except battle_cli.CliError as exc:
        raise Malformed(' '.join(str(exc).split())) from None
    return cmds


def record(scenario, commands, seed, kind=KIND_BATTLE):
    """Replay ``commands`` on ``scenario`` (a decoded scenario dict) and return
    the canonical file bytes. Same inputs give the same bytes."""
    if kind in RESERVED_KINDS or kind not in KINDS:
        raise UnsupportedKind(f"kind {kind!r} is not supported")
    if not _is_int(seed):
        raise Malformed("seed must be an integer")
    _check_plain(scenario)
    scen = json.loads(_canon(scenario).decode("ascii"))  # detach, canonical key order
    commands = list(commands)
    battle_id, final = _play(scen, seed, commands)
    header = {
        "format_version": FORMAT_VERSION, "kind": kind, "seed": seed,
        "battle_id": battle_id, "scenario_hash": _sha(_canon(scen)),
        "command_count": len(commands), "final_hash": B.state_hash(final),
    }
    header.update(_pack_hashes())
    body = {"scenario": scen, "commands": [soak.encode_command(c) for c in commands]}
    return _seal(header, body)


# --------------------------------------------------------------------- load

def _parse(data):
    """Structure and integrity checks; return (header, body)."""
    if not isinstance(data, (bytes, bytearray)):
        raise Malformed("replay data must be bytes")
    try:
        text = bytes(data).decode("utf-8")
    except UnicodeDecodeError as exc:
        if exc.end >= len(data):
            raise Truncated("data ends inside a character") from None
        raise Malformed("not UTF-8 text") from None
    if not text:
        raise Truncated("file is empty")
    try:
        doc = json.loads(text, parse_float=_reject_float, parse_constant=_no_const)
    except json.JSONDecodeError as exc:
        # A cut file is a proper prefix of an object, so it fails inside the
        # document; "Extra data" or a non-object start is garbage instead.
        if text.startswith("{") and exc.msg != "Extra data":
            raise Truncated(f"data ends early (at byte {len(data)})") from None
        raise Malformed(f"not a replay file: {exc.msg}") from None
    except RecursionError:
        raise Malformed("nesting too deep") from None
    if not isinstance(doc, dict) or tuple(sorted(doc)) != _DOC_KEYS:
        raise Malformed("not a replay file: bad top-level keys")
    header, body, checksum = doc["header"], doc["body"], doc["checksum"]
    if not isinstance(header, dict) or not isinstance(body, dict) \
            or not isinstance(checksum, str):
        raise Malformed("not a replay file: bad top-level types")
    version = header.get("format_version")
    if not _is_int(version):
        raise Malformed("header.format_version missing or not an integer")
    if version != FORMAT_VERSION:
        raise UnsupportedVersion(f"format_version {version} is not supported "
                                 f"(this code reads {FORMAT_VERSION})")
    if _sha(_canon({"header": header, "body": body})) != checksum:
        raise Tampered("checksum does not match header and body")
    if text.encode("utf-8") != _canon(doc):
        raise Malformed("file is not in canonical form")
    if tuple(sorted(header)) != _HEADER_KEYS:
        raise Malformed("header has missing or unknown keys")
    if tuple(sorted(body)) != _BODY_KEYS:
        raise Malformed("body has missing or unknown keys")
    kind = header["kind"]
    if kind in RESERVED_KINDS or kind not in KINDS:
        raise UnsupportedKind(f"kind {kind!r} is not supported")
    for k in ("seed", "command_count"):
        if not _is_int(header[k]):
            raise Malformed(f"header.{k} must be an integer")
    for k in ("battle_id", "scenario_hash", "final_hash", "rules_hash",
              "policy_hash", "creatures_hash"):
        if not isinstance(header[k], str):
            raise Malformed(f"header.{k} must be a string")
    if not isinstance(body["commands"], list) or not all(
            isinstance(c, dict) for c in body["commands"]):
        raise Malformed("body.commands must be a list of objects")
    if len(body["commands"]) != header["command_count"]:
        raise Malformed("header.command_count does not match the body")
    if not isinstance(body["scenario"], dict) \
            or _sha(_canon(body["scenario"])) != header["scenario_hash"]:
        raise Malformed("body.scenario does not match header.scenario_hash")
    return header, body


def info(data):
    """Header dict of a structurally valid, untampered file (no replay)."""
    header, _ = _parse(data)
    return dict(header)


def load(data):
    """Verify ``data`` and return ``(header, scenario, commands, final_state)``."""
    header, body = _parse(data)
    cur = _pack_hashes()
    if header["rules_hash"] != cur["rules_hash"]:
        raise MismatchedRulesPack("rules pack hash differs from this build")
    if header["policy_hash"] != cur["policy_hash"]:
        raise MismatchedPolicy("battle policy pack hash differs from this build")
    if header["creatures_hash"] != cur["creatures_hash"]:
        raise MismatchedCreatures("creatures pack hash differs from this build")
    try:
        commands = [soak.decode_command("battle", c) for c in body["commands"]]
    except (KeyError, TypeError, AttributeError, ValueError):
        raise Malformed("body.commands holds an undecodable command") from None
    if not all(isinstance(c, battle_cli._COMMAND_TYPES) for c in commands):
        raise Malformed("body.commands holds a non-battle command")
    battle_id, final = _play(body["scenario"], header["seed"], commands)
    if battle_id != header["battle_id"]:
        raise Malformed("header.battle_id does not match the scenario")
    if B.state_hash(final) != header["final_hash"]:
        raise Diverged("final state hash differs from the recorded one")
    return dict(header), body["scenario"], commands, final


def verify(data):
    """Replay and check; return the header on success, raise ReplayError."""
    return load(data)[0]
