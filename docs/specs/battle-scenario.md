# Battle scenario file (JSON)

Status: draft v1. Read by `python3 -m h3re battle-sim` (see
`tools/h3re/h3re/battle_cli.py`). The simulation core is `docs/specs/battle.md`.

```
python3 -m h3re battle-sim SCENARIO.json --seed N [--chooser first-legal|interactive|ai|scripted]
    [--pretty [--board-every N] [--color]]
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
state hash: 2191ae97fb22c8d15389d3e54c1a1eb6569a8d53630e0af647bd4ca97ca0d67d
```

Exit status: 0 on success. 1 for a malformed scenario, an unreadable file,
an illegal command, a chooser failure, `--board-every` without `--pretty`, or a
battle that is not finished after 2000 commands. Each error is one line on
stderr, prefixed `h3re: error:`. Usage errors (unknown `--chooser`, missing
`--seed`) exit 2.

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
`bad_morale_on_wait_activation`, `good_morale_on_wait_activation`,
`bad_morale_table`, `bad_luck`, `range_penalty_beyond` and `range_origin`.
Their values are validated by `BattlePolicy`. `placement_rows` is a list of 7
lists, the list of size `i+1` at index `i`. `bad_morale_table` is a list of 3
integers (numerators over 24 for morale −1, −2, −3).

The old field `morale_roll_on_wait_activation` was removed on 2026-11-01 and is
now rejected as an unknown key. Write `true` as
`"bad_morale_on_wait_activation": true, "good_morale_on_wait_activation": true`
and `false` as both `false`. See `battle.md` §5.

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
`2191ae97fb22c8d15389d3e54c1a1eb6569a8d53630e0af647bd4ca97ca0d67d`.
It was re-pinned on 2026-11-01 (previously `cd969e37…a95d`) when the default
row parity became `"even"`. The reason is recorded in `battle.md` §10.

## 8. Pretty output (`--pretty`)

`--pretty` replaces the plain event log with a report for people. Without it
the output is the plain log shown at the top of this document (the golden
hash tests depend on that). With it, the report has four parts. Everything is ASCII. Output is
deterministic for a given scenario, seed and chooser.

- **Board.** A text hex board of 17 columns and 11 rows, printed at the start
  (round 0), at the end, and after every N-th step with `--board-every N`
  (steps are numbered from 1, where `Begin` is step 1). Each row starts with
  its row number. Each hex is four columns wide. Row parity follows
  `policy.row_offset`: with the default `"even"`, even rows are drawn half a
  hex to the right. Markers:

  | glyph   | meaning                                                   |
  |---------|-----------------------------------------------------------|
  | `A`-`G` | attacker stack in slot 0-6                                |
  | `H`-`N` | defender stack in slot 0-6                                |
  | `#`     | obstacle                                                  |
  | `.`     | empty hex                                                 |

  A double-wide stack shows its letter on both hexes. Dead stacks are not
  drawn. Column digits are printed above the board (tens line, then units).

- **Legend.** Under each board, one row per stack of the state: mark, side,
  creature, count, HP, head position and `alive` or `dead`. HP is the total:
  `(count - 1) * creature.hp + top_hp`. A dead stack has `-` for position.

- **Event log.** One line per command (step number, command name, fields),
  followed by one line per event, indented, with the event name in a fixed
  16-column field. A `== round N ====` header is printed directly before the
  `RoundStarted` event that starts round N, so the header sits inside the step
  that began the round.

- **Summary.** A table of surviving stacks (mark, side, creature, count, HP,
  position), or `no surviving stacks`.

After the report, the last three lines are the same as in the plain output:
`winner:`, `rounds:` and `state hash:`. Their values do not depend on
`--pretty`, `--board-every` or `--color`.

`--color` adds ANSI colour to the board letters (attacker blue, defender red)
only when stdout is a terminal. With a pipe or a file it is ignored, so
redirected output is always plain ASCII.

Example (golden scenario, first board and the start of the log):

```text
-- board, start, round 0 --
                                              1   1   1   1   1   1   1
      0   1   2   3   4   5   6   7   8   9   0   1   2   3   4   5   6
 0      .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
 1    .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
 2      .   A   .   .   .   .   .   .   .   .   .   .   .   .   .   H   .
 3    .   .   .   .   .   .   .   #   .   .   .   .   .   .   .   .   .
 4      .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
 5    .   .   .   .   .   .   .   .   #   .   .   .   .   .   .   .   .
 6      .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
 7    .   .   .   .   .   .   .   .   .   #   .   .   .   .   .   .   .
 8      .   B   .   .   .   .   #   .   .   .   .   .   .   .   I   I   .
 9    .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
10      .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
...
legend: A-G attacker, H-N defender, # obstacle, . empty
  mark  side      creature  count   HP  pos     state
  A     attacker  pikeman      30  300  [1,2]   alive
  B     attacker  archer       20  200  [1,8]   alive
  H     defender  wolf         15  225  [15,2]  alive
  I     defender  gnoll        25  325  [14,8]  alive

   1  Begin
      BattleStarted    battle_id='golden'
== round 1 =====================================================
      RoundStarted     round=1
      TurnStarted      stack=2 phase='main' bonus=False
   2  Move     stack=2 dest=(7, 2)
```

The example is abbreviated and its rows are not all shown.
