"""Battle scenario and replay-file conformance vectors (milestone A5), from the Python reference.

``generate()`` returns ``{"replay.json": ...}``; the orchestrator wires it into
``vectors.generate()`` (which owns serialisation). Python is authoritative (ADR-0004,
docs/specs/conformance-replay.md). Synthetic data only: the golden scenario of
docs/specs/battle-scenario.md and generated soak scenarios.

Contents:
  packs            the three data-pack file texts and their hashes
  scenarios        valid scenarios: scenario text, initial state canonical text and hash, the
                   seed, the command log and the exact replay file Python records
  scenario_errors  scenarios ``parse_scenario`` refuses: the text and the CliError message
  replay_errors    damaged replay files and the error class Python raises; ``replay_hex`` is
                   given when the bytes are not ASCII
  truncation       a small replay: every proper prefix must raise Truncated

Usage:  python3 -m h3re.vectors_replay [--out DIR]
"""

import argparse
import json
import os
import re
import sys

from . import battle as B
from . import battle_cli
from . import datapack
from . import replay
from . import rules as R
from . import soak
from . import vectors as V
from . import vectors_battle as VB

VECTOR_FORMAT = 1
FILE = "replay.json"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCENARIO_DOC = os.path.join(REPO, "docs", "specs", "battle-scenario.md")

# (policy name, soak seeds, chooser)
SOAK_GAMES = (
    ("default", (0, 1, 2), "scripted"),
    ("alt-order", (1, 2), "first-legal"),
    ("vcmi-like", (0, 3), "scripted"),
    ("strict", (1, 2), "first-legal"),
    ("mix-fifo", (0, 1), "scripted"),
    ("mix-speed", (2,), "first-legal"),
    ("mix-alt", (1,), "scripted"),
)
MAX_SOAK_COMMANDS = 400


def _golden():
    with open(SCENARIO_DOC, encoding="utf-8") as f:
        text = f.read()
    return json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))


def _policies():
    pol = {name: kw for name, kw, _ in soak.POLICY_MATRIX}
    pol.update(dict(VB.EXTRA_POLICIES))
    return pol


def _jsonable(x):
    return json.loads(json.dumps(x))


def _creature_dict(c):
    d = {"attack": c.attack, "defense": c.defense, "dmg_min": c.dmg_min, "dmg_max": c.dmg_max,
         "hp": c.hp, "speed": c.speed}
    for k in ("shots", "flyer", "double_wide", "no_enemy_retaliation", "unlimited_retaliation",
              "no_melee_penalty", "no_range_penalty", "strikes_twice", "shoots_twice", "no_morale"):
        v = getattr(c, k)
        if v:
            d[k] = v
    if c.hates:
        d["hates"] = list(c.hates)
    return d


def soak_scenario(seed, policy_name):
    """The scenario JSON of ``soak.build_battle(seed, policy)``; asserts it rebuilds the same state."""
    kw = _policies()[policy_name]
    policy = B.BattlePolicy(**kw)
    state, _ = soak.build_battle(seed, policy)
    creatures, stacks = {}, {0: [], 1: []}
    for s in state.stacks:
        creatures[s.creature.name] = _creature_dict(s.creature)
        stacks[s.side].append({"creature": s.creature.name, "count": s.count,
                               "morale": s.morale, "luck": s.luck})
    scn = {
        "battle_id": state.battle_id,
        "creatures": creatures,
        "attackers": stacks[0], "defenders": stacks[1],
        "obstacles": [list(o) for o in state.obstacles],
        "heroes": [None if h is None else _jsonable(h.__dict__) if hasattr(h, "__dict__")
                   else _hero_dict(h) for h in state.heroes],
        "policy": _jsonable(kw),
    }
    _, rebuilt = battle_cli.parse_scenario(scn)
    assert rebuilt == state, (seed, policy_name)
    return scn


def _hero_dict(h):
    return {"attack": h.attack, "defense": h.defense, "offense": h.offense,
            "archery": h.archery, "armorer": h.armorer}


def _text(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _record_case(name, scn, seed, chooser):
    cmds = replay.run_chooser(scn, seed, chooser)
    data = replay.record(scn, cmds, seed)
    header = replay.verify(data)
    _, state = battle_cli.parse_scenario(scn)
    return {
        "name": name,
        "scenario": _text(scn),
        "seed": seed,
        "chooser": chooser,
        "initial_canonical": B.canonical(state).decode("ascii"),
        "initial_hash": B.state_hash(state),
        "commands": [soak.encode_command(c) for c in cmds],
        "replay": data.decode("ascii"),
        "header": header,
    }


def _explicit_pos_scenario():
    """Hand-made: explicit pos, a double-wide, hates, one hero, obstacles, edge columns off."""
    return {
        "battle_id": "pos-demo",
        "creatures": {
            "knight": {"attack": 10, "defense": 9, "dmg_min": 2, "dmg_max": 3, "hp": 35, "speed": 6,
                       "hates": ["imp"]},
            "imp": {"attack": 2, "defense": 3, "dmg_min": 1, "dmg_max": 2, "hp": 4, "speed": 7,
                    "flyer": True},
            "dragon": {"attack": 19, "defense": 19, "dmg_min": 40, "dmg_max": 50, "hp": 200,
                       "speed": 11, "double_wide": True, "flyer": True},
            "archer": {"attack": 6, "defense": 3, "dmg_min": 2, "dmg_max": 3, "hp": 10, "speed": 4,
                       "shots": 12},
        },
        "attackers": [{"creature": "knight", "count": 12, "pos": [2, 3], "morale": 1},
                      {"creature": "archer", "count": 20, "luck": -1}],
        "defenders": [{"creature": "dragon", "count": 2, "pos": [14, 5]},
                      {"creature": "imp", "count": 30, "pos": [12, 8], "morale": -1, "luck": 2}],
        "obstacles": [[7, 4], [7, 5], [9, 2], [7, 4]],
        "heroes": [{"attack": 3, "defense": 1, "archery": 1}, None],
        "policy": {"row_offset": "odd", "wait_order": "fifo"},
    }


def _scenarios():
    out = []
    out.append(_record_case("golden", _golden(), 12345, "scripted"))
    out.append(_record_case("golden-ai", _golden(), 7, "ai"))
    out.append(_record_case("explicit-pos", _explicit_pos_scenario(), 99, "ai"))
    for pname, seeds, chooser in SOAK_GAMES:
        for seed in seeds:
            scn = soak_scenario(seed, pname)
            try:
                cmds = replay.run_chooser(scn, seed, chooser)
            except replay.Malformed:  # a battle too long for the chooser cap: skip it
                continue
            if len(cmds) > MAX_SOAK_COMMANDS:
                continue
            out.append(_record_case("soak-%s-%d" % (pname, seed), scn, seed, chooser))
    return out


# ------------------------------------------------------------------ scenario errors

def _mut(base, fn):
    scn = json.loads(json.dumps(base))
    fn(scn)
    return scn


def _scenario_error_cases():
    g = _golden()
    pike = next(iter(g["creatures"]))
    cases = []

    def add(name, scn_or_text, exact=True):
        text = scn_or_text if isinstance(scn_or_text, str) else _text(scn_or_text)
        try:
            battle_cli.parse_scenario(json.loads(text))
        except battle_cli.CliError as exc:
            cases.append({"name": name, "scenario": text, "error": " ".join(str(exc).split()),
                          "exact": exact})
            return
        raise AssertionError("scenario %s did not fail" % name)

    add("not-object", "[]")
    add("unknown-top-key", _mut(g, lambda s: s.update(extra=1)))
    for k in ("battle_id", "creatures", "attackers", "defenders"):
        add("missing-" + k, _mut(g, lambda s, k=k: s.pop(k)))
    add("empty-battle-id", _mut(g, lambda s: s.update(battle_id="")))
    add("battle-id-int", _mut(g, lambda s: s.update(battle_id=5)))
    add("creatures-list", _mut(g, lambda s: s.update(creatures=[])))
    add("empty-creature-name", _mut(g, lambda s: s["creatures"].update({"": {}})))
    add("creature-not-object", _mut(g, lambda s: s["creatures"].update(x=5)))
    add("creature-unknown-key", _mut(g, lambda s: s["creatures"][pike].update(bogus=1)))
    add("creature-missing-hp", _mut(g, lambda s: s["creatures"][pike].pop("hp")))
    add("creature-hp-string", _mut(g, lambda s: s["creatures"][pike].update(hp="9")))
    add("creature-hp-bool", _mut(g, lambda s: s["creatures"][pike].update(hp=True)))
    add("creature-flag-int", _mut(g, lambda s: s["creatures"][pike].update(flyer=1)))
    add("creature-hates-str", _mut(g, lambda s: s["creatures"][pike].update(hates="x")))
    add("creature-hates-nested", _mut(g, lambda s: s["creatures"][pike].update(hates=[["a"]])))
    add("creature-hates-int", _mut(g, lambda s: s["creatures"][pike].update(hates=[3])))
    add("creature-float", re.sub(r'"speed":(\d+)', r'"speed":\1.5', _text(g), count=1))
    add("creature-dmg-range", _mut(g, lambda s: s["creatures"][pike].update(dmg_min=9, dmg_max=2)))
    add("creature-hp-zero", _mut(g, lambda s: s["creatures"][pike].update(hp=0)))
    add("creature-speed-negative", _mut(g, lambda s: s["creatures"][pike].update(speed=-1)))
    add("creature-hp-huge", _mut(g, lambda s: s["creatures"][pike].update(hp=2 ** 40)), exact=False)
    add("attackers-empty", _mut(g, lambda s: s.update(attackers=[])))
    add("attackers-eight", _mut(g, lambda s: s.update(attackers=[{"creature": pike, "count": 1}] * 8)))
    add("attackers-dict", _mut(g, lambda s: s.update(attackers={})))
    add("stack-not-object", _mut(g, lambda s: s["attackers"].__setitem__(0, 3)))
    add("stack-unknown-key", _mut(g, lambda s: s["attackers"][0].update(x=1)))
    add("stack-missing-count", _mut(g, lambda s: s["attackers"][0].pop("count")))
    add("stack-unknown-creature", _mut(g, lambda s: s["attackers"][0].update(creature="nope")))
    add("stack-creature-int", _mut(g, lambda s: s["attackers"][0].update(creature=4)))
    add("stack-count-float", re.sub(r'"count":(\d+)', r'"count":\1.5', _text(g), count=1))
    add("stack-count-string", _mut(g, lambda s: s["attackers"][0].update(count="3")))
    add("stack-count-zero", _mut(g, lambda s: s["attackers"][0].update(count=0)))
    add("stack-count-huge", _mut(g, lambda s: s["attackers"][0].update(count=2 ** 40)), exact=False)
    add("stack-morale-bool", _mut(g, lambda s: s["attackers"][0].update(morale=True)))
    add("stack-luck-null", _mut(g, lambda s: s["attackers"][0].update(luck=None)))
    add("stack-pos-short", _mut(g, lambda s: s["attackers"][0].update(pos=[1])))
    add("stack-pos-string", _mut(g, lambda s: s["attackers"][0].update(pos=[1, "a"])))
    add("stack-pos-off-grid", _mut(g, lambda s: s["attackers"][0].update(pos=[40, 2])))
    add("stack-pos-edge-column", _mut(g, lambda s: s["attackers"][0].update(pos=[0, 2])))
    add("stack-pos-overlap", _mut(g, lambda s: [s["attackers"][0].update(pos=[3, 3]),
                                                 s["attackers"][1].update(pos=[3, 3])]))
    add("stack-on-obstacle", _mut(g, lambda s: [s.update(obstacles=[[3, 3]]),
                                                 s["attackers"][0].update(pos=[3, 3])]))
    add("obstacles-dict", _mut(g, lambda s: s.update(obstacles={})))
    add("obstacle-not-pair", _mut(g, lambda s: s.update(obstacles=[[1, 2, 3]])))
    add("obstacle-off-grid", _mut(g, lambda s: s.update(obstacles=[[17, 2]])))
    add("heroes-one", _mut(g, lambda s: s.update(heroes=[None])))
    add("heroes-dict", _mut(g, lambda s: s.update(heroes={})))
    add("hero-unknown-key", _mut(g, lambda s: s.update(heroes=[{"luck": 1}, None])))
    add("hero-attack-string", _mut(g, lambda s: s.update(heroes=[{"attack": "1"}, None])))
    add("policy-list", _mut(g, lambda s: s.update(policy=[])))
    add("policy-unknown-key", _mut(g, lambda s: s.update(policy={"nope": 1})))
    add("policy-row-offset-bad", _mut(g, lambda s: s.update(policy={"row_offset": "left"})))
    add("policy-row-offset-int", _mut(g, lambda s: s.update(policy={"row_offset": 1})))
    add("policy-bool-int", _mut(g, lambda s: s.update(policy={"bad_luck": 1})))
    add("policy-num-str", _mut(g, lambda s: s.update(policy={"defend_bonus_num": "1"})))
    add("policy-den-zero", _mut(g, lambda s: s.update(policy={"defend_bonus_den": 0})))
    add("policy-rounding-bad", _mut(g, lambda s: s.update(policy={"defend_bonus_rounding": "up"})))
    add("policy-speed-tie-bad", _mut(g, lambda s: s.update(policy={"speed_tie": "x"})))
    add("policy-wait-order-bad", _mut(g, lambda s: s.update(policy={"wait_order": "x"})))
    add("policy-range-origin-bad", _mut(g, lambda s: s.update(policy={"range_origin": "x"})))
    add("policy-morale-table-short", _mut(g, lambda s: s.update(policy={"bad_morale_table": [1, 2]})))
    add("policy-morale-table-decreasing", _mut(g, lambda s: s.update(policy={"bad_morale_table": [3, 2, 1]})))
    add("policy-rows-not-list", _mut(g, lambda s: s.update(policy={"placement_rows": 5})))
    add("policy-rows-wrong-shape", _mut(g, lambda s: s.update(policy={"placement_rows": [[1]]})))
    add("policy-range-penalty-negative", _mut(g, lambda s: s.update(policy={"range_penalty_beyond": -1})))
    add("policy-rows-off-grid", _mut(g, lambda s: s.update(
        policy={"placement_rows": [[11] * n for n in range(1, 8)]})))
    add("double-wide-at-edge", _mut(g, lambda s: [
        s["creatures"][pike].update(double_wide=True),
        s["attackers"][0].update(pos=[1, 2])]))
    return cases


# ------------------------------------------------------------------ replay errors

def _reseal(data, header=None, body=None, **changes):
    doc = json.loads(data)
    h = dict(doc["header"] if header is None else header)
    h.update(changes)
    return replay._seal(h, doc["body"] if body is None else body)


def _replay_error_cases(base):
    data = base["replay"].encode("ascii")
    doc = json.loads(data)
    cases = []

    def add(name, blob, expect, packs="shipped"):
        if isinstance(blob, str):
            blob = blob.encode("ascii")
        try:
            replay.verify(blob)
        except replay.ReplayError as exc:
            got = type(exc).__name__
        else:
            got = None
        assert got == expect, (name, got, expect)
        case = {"name": name, "error": expect}
        try:
            case["replay"] = blob.decode("ascii")
        except UnicodeDecodeError:
            case["replay_hex"] = blob.hex()
        cases.append(case)

    def edited(fn):
        d = json.loads(data)
        fn(d)
        return replay._canon(d)

    add("empty", b"", "Truncated")
    add("garbage", b"hello", "Malformed")
    add("array", b"[]", "Malformed")
    add("null", b"null", "Malformed")
    add("empty-object", b"{}", "Malformed")
    add("float", b'{"a":1.5}', "Malformed")
    add("nan", b'{"a":NaN}', "Malformed")
    add("whitespace-start-cut", b' {"a":', "Malformed")
    add("bad-utf8", b"\xff\xfe", "Malformed")
    add("trailing-x", data + b"x", "Malformed")
    add("trailing-newline", data + b"\n", "Malformed")
    add("pretty-printed", json.dumps(doc, indent=1, sort_keys=True).encode("ascii"), "Malformed")
    add("spaced-separators", json.dumps(doc, sort_keys=True).encode("ascii"), "Malformed")
    add("version-0", _reseal(data, format_version=0), "UnsupportedVersion")
    add("version-2", _reseal(data, format_version=2), "UnsupportedVersion")
    add("version-2-unsealed", edited(lambda d: d["header"].update(format_version=2)), "UnsupportedVersion")
    add("version-string", edited(lambda d: d["header"].update(format_version="1")), "Malformed")
    add("version-missing", edited(lambda d: d["header"].pop("format_version")), "Malformed")
    add("tamper-seed", edited(lambda d: d["header"].update(seed=d["header"]["seed"] + 1)), "Tampered")
    add("tamper-command", edited(lambda d: d["body"]["commands"][3].update(stack=99)), "Tampered")
    add("tamper-checksum", edited(lambda d: d.update(checksum="0" * 64)), "Tampered")
    add("tamper-scenario", edited(lambda d: d["body"]["scenario"].update(battle_id="other")), "Tampered")
    add("tamper-final-hash", edited(lambda d: d["header"].update(final_hash="0" * 64)), "Tampered")
    add("checksum-dropped", edited(lambda d: d.pop("checksum")), "Malformed")
    add("top-level-extra", edited(lambda d: d.update(extra=1)), "Malformed")
    add("kind-adventure", _reseal(data, kind="adventure"), "UnsupportedKind")
    add("kind-other", _reseal(data, kind="duel"), "UnsupportedKind")
    add("kind-int", _reseal(data, kind=5), "UnsupportedKind")
    add("rules-pack-mismatch", _reseal(data, rules_hash="0" * 64), "MismatchedRulesPack")
    add("policy-mismatch", _reseal(data, policy_hash="0" * 64), "MismatchedPolicy")
    add("creatures-mismatch", _reseal(data, creatures_hash="0" * 64), "MismatchedCreatures")
    add("rules-hash-int", _reseal(data, rules_hash=5), "Malformed")
    add("final-hash-wrong", _reseal(data, final_hash="0" * 64), "Diverged")
    add("seed-changed", _reseal(data, seed=base["seed"] + 1), "Diverged")
    add("seed-float-text", data.replace(b'"seed":%d' % base["seed"], b'"seed":1.5'), "Malformed")
    add("seed-string", _reseal(data, seed="1"), "Malformed")
    add("seed-bool", _reseal(data, seed=True), "Malformed")
    add("header-extra-key", _reseal(data, extra=1), "Malformed")
    h2 = dict(doc["header"])
    h2.pop("scenario_hash")
    add("header-missing-key", _reseal(data, header=h2), "Malformed")
    add("count-mismatch", _reseal(data, command_count=doc["header"]["command_count"] + 1), "Malformed")
    add("count-string", _reseal(data, command_count="x"), "Malformed")
    add("scenario-hash-mismatch", _reseal(data, scenario_hash="0" * 64), "Malformed")
    add("battle-id-mismatch", _reseal(data, battle_id="other"), "Malformed")
    b2 = json.loads(json.dumps(doc["body"]))
    b2["commands"] = b2["commands"][:5] + [{"type": "Move", "stack": 0, "dest": [0, 0]}]
    add("illegal-command", _reseal(data, body=b2, command_count=6), "Diverged")
    b3 = json.loads(json.dumps(doc["body"]))
    b3["commands"][2] = {"type": "Fly", "stack": 0}
    add("unknown-command-type", _reseal(data, body=b3), "Malformed")
    b4 = json.loads(json.dumps(doc["body"]))
    b4["commands"][1] = {"type": "Wait", "stack": 0, "extra": 1}
    add("command-extra-key", _reseal(data, body=b4), "Malformed")
    b5 = json.loads(json.dumps(doc["body"]))
    b5["commands"][1] = {"type": "Wait"}
    add("command-missing-key", _reseal(data, body=b5), "Malformed")
    b6 = json.loads(json.dumps(doc["body"]))
    b6["commands"] = ["Begin"]
    add("command-not-object", _reseal(data, body=b6, command_count=1), "Malformed")
    b7 = {"commands": doc["body"]["commands"]}
    add("body-missing-scenario", _reseal(data, body=b7), "Malformed")
    b8 = json.loads(json.dumps(doc["body"]))
    b8["scenario"]["attackers"] = []
    add("scenario-invalid", _reseal(data, body=b8, scenario_hash=replay._sha(replay._canon(b8["scenario"]))),
        "Malformed")
    return cases


def _truncation_case():
    scn = {
        "battle_id": "tiny",
        "creatures": {"s": {"attack": 9, "defense": 6, "dmg_min": 4, "dmg_max": 6, "hp": 20, "speed": 5}},
        "attackers": [{"creature": "s", "count": 3}], "defenders": [{"creature": "s", "count": 2}],
    }
    cmds = replay.run_chooser(scn, 5, "scripted")
    data = replay.record(scn, cmds, 5)
    for cut in range(len(data)):
        try:
            replay.verify(data[:cut])
        except replay.Truncated:
            continue
        raise AssertionError("cut %d is not Truncated" % cut)
    return {"scenario": _text(scn), "seed": 5, "replay": data.decode("ascii"), "length": len(data)}


def generate():
    packs = {}
    for key, name in (("rules", "rules.json"), ("battle_policy", "battle_policy.json"),
                      ("creatures", "creatures.json")):
        with open(os.path.join(datapack.DEFAULT_DIR, name), encoding="utf-8") as f:
            packs[key] = f.read()
    packs.update(rules_hash=R.RULES_HASH, policy_hash=B.POLICY_HASH,
                 creatures_hash=datapack.load_dir().content_hash)
    scenarios = _scenarios()
    return {FILE: {
        "format": VECTOR_FORMAT,
        "packs": packs,
        "scenarios": scenarios,
        "scenario_errors": _scenario_error_cases(),
        "replay_errors": _replay_error_cases(scenarios[0]),
        "truncation": _truncation_case(),
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
