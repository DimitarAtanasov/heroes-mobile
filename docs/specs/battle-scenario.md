# Battle scenario file (JSON)

Status: draft v1. Read by `python3 -m h3re battle-sim` (see
`tools/h3re/h3re/battle_cli.py`). The simulation core is `docs/specs/battle.md`.

```
python3 -m h3re battle-sim SCENARIO.json --seed N [--chooser first-legal|interactive|ai|scripted]
```

`--seed` is the master seed. The battle draws from the named stream
`battle:<battle_id>` (see `battle.battle_rng`). The output is the event log,
one command per block, then the winner, the round count and the state hash:

```
> Begin()
  BattleStarted(battle_id='golden')
  RoundStarted(round=1)
  TurnStarted(stack=0, phase='main', bonus=False)
> Wait(stack=0)
  Waited(stack=0)
...
winner: defender
rounds: 4
state hash: cd969e37b84f2c1dde88ad5cf2b3d8e0f11f211ace9ccfe2226405a6c06da95d
```

Exit status: 0 on success. 1 for a malformed scenario, an unreadable file,
an illegal command, a chooser failure, or a battle that is not finished after
2000 commands. Each error is one line on stderr, prefixed `h3re: error:`.
Usage errors (unknown `--chooser`, missing `--seed`) exit 2.

## 1. Document

A JSON object. Unknown keys are errors at every level, so typos are caught.

| key         | type                 | required | meaning                                          |
|-------------|----------------------|----------|--------------------------------------------------|
| `battle_id` | string, non-empty    | yes      | names the RNG stream `battle:<battle_id>`        |
| `creatures` | object               | yes      | creature table, keyed by name (see 2)            |
| `attackers` | list of 1 to 7 stacks | yes     | attacker side, slot order (see 3)                |
| `defenders` | list of 1 to 7 stacks | yes     | defender side, slot order (see 3)                |
| `obstacles` | list of `[col, row]` | no       | blocked hexes, default `[]`                      |
| `heroes`    | list of 2            | no       | `[attacker, defender]`, each `null` or a hero (see 4); default `[null, null]` |
| `policy`    | object               | no       | overrides of `BattlePolicy` fields (see 5); default `{}` |

Grid coordinates are `[col, row]` with `0 <= col < 17` and `0 <= row < 11`.

## 2. Creatures

The object key is the creature name. Stacks refer to creatures by that name,
and `hates` refers to names too.

| key                   | type         | required | default |
|-----------------------|--------------|----------|---------|
| `attack`              | integer      | yes      |         |
| `defense`             | integer      | yes      |         |
| `dmg_min`             | integer      | yes      |         |
| `dmg_max`             | integer      | yes      |         |
| `hp`                  | integer      | yes      |         |
| `speed`               | integer      | yes      |         |
| `shots`               | integer      | no       | 0       |
| `hates`               | list of names | no      | `[]`    |
| `flyer`               | boolean      | no       | false   |
| `double_wide`         | boolean      | no       | false   |
| `no_enemy_retaliation` | boolean     | no       | false   |
| `unlimited_retaliation` | boolean   | no       | false   |
| `no_melee_penalty`    | boolean      | no       | false   |
| `no_range_penalty`    | boolean      | no       | false   |
| `strikes_twice`       | boolean      | no       | false   |
| `shoots_twice`        | boolean      | no       | false   |
| `no_morale`           | boolean      | no       | false   |

All numbers come from the scenario. Nothing is taken from game data here.

## 3. Stacks

Each entry of `attackers` and `defenders` is an object:

| key        | type                          | required | default |
|------------|-------------------------------|----------|---------|
| `creature` | name from `creatures`         | yes      |         |
| `count`    | integer, at least 1           | yes      |         |
| `morale`   | integer (clamped to -3..3 by the rules) | no | 0    |
| `luck`     | integer                       | no       | 0       |
| `pos`      | `[col, row]` head hex, or `null` | no    | `null` (the policy placement table) |

A double-wide creature occupies `pos` and the hex next to it (left for the
attacker, right for the defender).

## 4. Heroes

Each hero is an object with the integer keys `attack`, `defense`, `offense`,
`archery` and `armorer`, all defaulting to 0. `null` means no hero. The two
values are kept distinct: `null` and `{}` are different states, and the state
hash reflects that.

## 5. Policy

`policy` overrides fields of `BattlePolicy` in `battle.py`. Any field that is
left out keeps its default. The fields are `row_offset`, `edge_columns_walkable`,
`placement_rows`, `speed_tie`, `wait_order`, `defend_bonus_num`,
`defend_bonus_den`, `defend_bonus_min`, `defend_bonus_rounding`,
`good_morale_after_wait`, `good_morale_after_defend`, `repeat_good_morale`,
`bad_luck` and `range_penalty_beyond`. Their values are validated by
`BattlePolicy`. `placement_rows` is a list of 7 lists, the list of size `i+1`
at index `i`.

## 6. Choosers

| name           | behaviour                                                                                   |
|----------------|---------------------------------------------------------------------------------------------|
| `first-legal`  | the first entry of `legal_commands(state)`. Default.                                        |
| `interactive`  | prints the numbered legal commands to stderr and reads an index from stdin. `q` aborts.    |
| `ai`           | calls `h3re.battle_ai.choose(state, side=None)`. The module is imported only when this chooser is selected. If it cannot be imported, the run fails with a one-line error. |
| `scripted`     | the deterministic player of the golden test: shoot, else attack, else advance to the nearest enemy, else defend. |

## 7. Golden scenario

This document reproduces the golden test in `tools/h3re/tests/test_battle.py`
(`golden_setup`). With `--chooser scripted --seed 12345` it prints the state
hash pinned there:

```json
{
  "battle_id": "golden",
  "creatures": {
    "pikeman": {"attack": 4, "defense": 5, "dmg_min": 1, "dmg_max": 3, "hp": 10, "speed": 4},
    "archer": {"attack": 6, "defense": 3, "dmg_min": 2, "dmg_max": 3, "hp": 10, "speed": 4, "shots": 12},
    "wolf": {"attack": 7, "defense": 5, "dmg_min": 2, "dmg_max": 5, "hp": 15, "speed": 8, "strikes_twice": true},
    "gnoll": {"attack": 6, "defense": 7, "dmg_min": 2, "dmg_max": 4, "hp": 13, "speed": 6, "double_wide": true, "hates": ["pikeman"]}
  },
  "attackers": [
    {"creature": "pikeman", "count": 30, "morale": 1, "luck": 1},
    {"creature": "archer", "count": 20, "morale": 2}
  ],
  "defenders": [
    {"creature": "wolf", "count": 15, "morale": -1, "luck": 2},
    {"creature": "gnoll", "count": 25, "morale": 1}
  ],
  "obstacles": [[7, 3], [8, 5], [9, 7], [6, 8]],
  "heroes": [
    {"attack": 2, "defense": 1, "offense": 1, "archery": 2},
    {"defense": 2, "armorer": 1}
  ],
  "policy": {}
}
```

Pinned state hash for this scenario with seed 12345 and the scripted chooser:
`cd969e37b84f2c1dde88ad5cf2b3d8e0f11f211ace9ccfe2226405a6c06da95d`.
