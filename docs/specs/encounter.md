# Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)

Status: draft v1. Reference implementation: `tools/h3re/h3re/encounter.py`
(hooks in `adventure.py`, see `adventure.md` §8). Tests:
`tools/h3re/tests/test_encounter.py`. Tags as in `rules.md`:
**[documented]**, **[uncertain]**, **[engine]**.

Scope: a hero attacks a neighbouring enemy hero or a neutral guard; the fight
is an ordinary `battle.py` field battle between the two armies; survivors
return to the armies; a hero with no army left leaves the map. Out of scope:
hero primary skills in battle (no `sim.hero` yet), morale/luck modifiers from
the army, experience, artifacts, retreat/surrender, towns and sieges, guard
zones of control, neutral growth, interactive (player-driven) battles.

## 1. Interface

- Command `adventure.Attack(hero, target)`: `target` is an enemy hero id
  (`int`) or a guard id (`str`). It goes through `adventure.apply(state,
  cmd, rng)` like every other command. [engine]
- State (`adventure.GameState`, all optional, see §6):
  `guards` (tuple of `Guard(id, pos, army)`, sorted by id),
  `encounter` (`EncounterSetup` or `None`; `None` = battles disabled) and
  `battles` (number of encounters fought).
  `create_game(..., guards=(), encounter=None)`.
- `EncounterSetup(creatures, policy=EncounterPolicy(), battle_policy=battle.DEFAULT_POLICY, rules_hash=rules.RULES_HASH)`.
  `creatures` holds one `battle.Creature` per army creature id (`name` is the
  id, `speed` must equal `ArmySlot.speed`); it is sorted by name and must
  have unique names. `create_game` raises `ValueError` if any hero or guard
  army has no matching creature.
- Queries: `battle_id(state)`, `encounter_rng(master_seed, state)`,
  `stream_for(master_seed, state, cmd)`, `build_battle(state, cmd)` (the
  battle an Attack would fight; pure), `auto_command(battle_state)`,
  `fight(battle_state, rng, round_limit)`.
- Events, in order: `BattleFought(battle_id, attacker, target, winner, rounds, log, battle_events, battle_hash)`,
  then for the attacker and then the defender either
  `HeroDefeated(hero)` / `GuardDefeated(guard)` (no army left) or
  `ArmyChanged(unit, army)` (army changed), then `adventure.HeroMoved` if
  the winner takes the tile (§5). `winner` is `battle.ATTACKER`,
  `battle.DEFENDER` or `None` (round limit). `log` is the battle command
  sequence (`Begin` first); `battle_events` are all battle events in order,
  for the presenter; `battle_hash` is `battle.state_hash` of the final
  battle state.

## 2. Validation

All checks run before any draw. A failure raises `adventure.IllegalCommand`;
state and stream are untouched (tested with a stream that fails on use).
[engine]

- The game has started; `state.encounter` is not `None`.
- `encounter.rules_hash == rules.RULES_HASH` (the local rules pack;
  ADR-0001). Otherwise the battle would use other damage numbers than the
  ones the game committed to.
- `hero` is an `int` (not `bool`) naming a hero of the current player that is
  on the map.
- `target` is an `int` (not `bool`) naming another player's hero on the map,
  or a `str` naming a guard. Anything else is illegal.
- The target's tile is one legal step from the hero's tile:
  `adventure.step_cost(grid, hero.pos, target.pos, hero.pathfinding, policy)`
  is not `None` (8 neighbours; `diagonal_moves` and `diagonal_corner_cut`
  apply; occupancy is ignored).
- Every army slot of both sides has a creature in the setup with the same
  speed, and `battle.create_battle` accepts the stacks.

## 3. The battle

- Battle id `"<game_id>:<n>"` with `n = state.battles + 1`, so every
  encounter of a game has its own id. [engine]
- Stream: the battle draws only from `rng`, which must be the named stream
  `battle:<battle_id>` from the game's master seed:
  `encounter_rng(master_seed, state) = battle.battle_rng(master_seed, battle_id(state))`
  `= derive_stream(master_seed, "battle:<game_id>:<n>")`. `stream_for`
  returns that stream for an Attack and `adventure_rng(master_seed, game_id)`
  for every other command, so a replay driver needs only the master seed.
  The adventure stream is never drawn from. As in `battle.md` §1, `apply`
  cannot check which stream it was given; that is the caller's contract.
  [engine]
- Sides: the attacking hero is `battle.ATTACKER`, the target is
  `battle.DEFENDER`. Army slot i becomes battle stack slot i
  (`StackSetup(creature, count, morale=0, luck=0)`); placement follows
  `slot_mapping` (§5). Battle heroes: `battle.Hero()` (all zero) for a hero
  side, `None` for a guard. [engine: heroes have no primary skills until
  `sim.hero`; army morale/luck is not modelled]
- No obstacles; the battle policy is `setup.battle_policy`.
- Auto-combat [engine]: the battle is resolved inside the Attack by
  `auto_command`, which uses no randomness: the Attack or Shoot with the
  highest expected damage (`battle.strike_preview(...).expected`, the
  pipeline execution uses), first in `battle.legal_commands` order on a tie;
  otherwise the Move whose head ends closest to an enemy cell, if closer than
  now (ties: smallest hex); otherwise Defend. Player-driven battles are a
  later change (an Attack that carries its battle command log).
- Round limit [engine]: if round `round_limit + 1` starts with no winner,
  the battle stops. `winner = None`, `rounds = round_limit`, both sides keep
  their survivors, nobody is removed. This is a safety cap against stalls
  (e.g. two speed-0 armies), not a rule of the original game.

## 4. Outcome

- Survivors [engine]: army slot i gets the `count` of battle stack slot i of
  its side (a wounded top creature counts as alive). Slots whose stack died
  are dropped; the others keep their order. The `ArmySlot` fields other
  than `count` are unchanged.
- A hero with no army left is removed from the map: `pos=None`, `army=()`,
  `mp=0`, `mp_max=0`. Its index (hero id) stays, so the other ids do not
  shift. A removed hero does not act (no `MovementReset`, `Move` and
  `Attack` are illegal, `reachable` is `{}`, `find_path` is `None`), cannot
  be attacked and frees its tile. [uncertain: the policy field `loser_fate`;
  the tavern and the loser's belongings are out of scope]
- A guard with no army left is removed from `guards`. A guard that wins
  keeps its survivors (no regeneration). [uncertain]
- Movement points of the attacker are unchanged by the battle, and attacking
  costs none. [uncertain, no switch yet]
- `battles` is incremented once per Attack (win, loss or round limit).

## 5. Policy fields (`EncounterPolicy`)

The policy lives in `GameState.encounter.policy`, so it is part of the hash.

| Field | Default | Alternatives | Question |
|---|---|---|---|
| `loser_fate` | `"removed"` | `"winner_takes_tile"` | The loser (no army) always leaves the map. Does an attacking winner then step onto the freed tile (no point cost)? A defending winner stays put either way. [uncertain] |
| `slot_mapping` | `"by_count"` | `"by_slot"` | Where army slot i stands in battle. `by_count`: the battle policy's `placement_rows` entry for the army size (as `create_battle`). `by_slot`: row `placement_rows[6][i]`, the 7-stack row of the slot's own index (attacker column 1, defender 15; two-hex heads at 2 / 14). Survivors always return to slot i. [uncertain] |
| `round_limit` | 100 | any int >= 1 | Safety cap, §3. [engine] |

The defaults are in code, like `AdventurePolicy`. Moving them to
`data/*.json` needs a `datapack.py` loader (outside this change).

## 6. Canonical form and hashes

- `guards`, `encounter` and `battles` were added to `GameState` after the
  adventure golden hash was pinned. `adventure.canonical` leaves each of them
  out while it holds its default (`()`, `None`, `0`):
  `adventure._OMIT_WHEN_DEFAULT`, the mechanism ADR-0001 describes for
  battle. A game without encounters has exactly the old canonical form, so
  the 14-day golden `179c5700...` did not move (tested). A game with
  encounters carries the setup (creatures, both policies, `rules_hash`),
  the guards and the counter.
- The battle golden `fbe9015b...` did not move: `battle.py` only changed in
  command validation (`adventure.md` §8).

## 7. Golden encounter hash

`GoldenTest.PINNED` in `tests/test_encounter.py`:
`512b53ca56c4c5611e718b4b23129984ab5a3c0f6e0de4a7feb48c620568bd60`.

Derivation: `golden_game()` in the test: game id `"enc"`, an 8x4 all-grass
grid, two players with no resources, creatures pike/archer/wolf/gnoll/statue
as in `CREATURES`, default `EncounterPolicy` and `BattlePolicy`, the shipped
rules pack; heroes 0 `(1,1)` pike 30 + archer 20 and 1 `(4,2)` wolf 6
(player 0), 2 `(6,1)` gnoll 12 + pike 10 and 3 `(7,3)` pike 25 + archer 6
(player 1); guards `wolves` `(2,1)` wolf 8 and `camp` `(6,3)` gnoll 20.
Master seed 2026; each command's stream is `stream_for(2026, state, cmd)`.
Commands: `Begin`; `Attack(0,"wolves")` (hero wins), `Move(1,(5,1))`,
`Attack(1,2)` (attacker removed), `EndTurn(0)`; `Attack(3,"camp")` (guard
wins, keeps 12), `Move(2,(2,1))`, `Attack(2,0)` (attacker removed),
`EndTurn(1)`; `Move(0,(3,1))` (across a freed tile), `EndTurn(0)`,
`EndTurn(1)`. The pin is `adventure.state_hash` of the final state (day 3,
4 battles). It depends on the rules pack and the battle policy defaults
through the stored setup. A change of this hash is a re-pin (ADR-0001).

## 8. Tests

Golden hash and replay determinism; both older goldens unchanged; stream
names and battle ids; each battle's `log` replayed on
`battle:<battle_id>` reproduces `battle_hash` and `winner`; non-Attack
commands never touch the stream; stacks mirror the armies (sides, slots,
counts, heroes, placement for both `slot_mapping` values); survivors per
slot, dead slots dropped; removed-hero behaviour; guard win; guards block
movement; both `loser_fate` values; policy in the hash; round-limit draw;
every illegal Attack leaves state and stream untouched (pack mismatch,
content mismatch, non-adjacent, own hero, bad types, diagonal rules);
setup validation; omitted fields at default; random playouts under three
policies (distinct tiles, removed iff army empty, counts > 0, identical
reruns).

## 9. Open items

- `tools/lint/banned_api_lint.py` does not list `encounter.py` among its
  default targets (it passes the lint when given explicitly). Add it to
  `SIM_MODULES`.
- ADR-0001 calls `_OMIT_WHEN_DEFAULT` battle-only; `adventure.py` now uses
  it too. The ADR needs that amendment (adr-scribe).
- Interactive battles, hero primary skills, army morale/luck, attack point
  cost and guard zones of control.
