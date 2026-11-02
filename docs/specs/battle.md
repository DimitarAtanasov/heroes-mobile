# Battle simulation core (`sim.battle`)

Status: draft v1, roadmap phase 5. Reference implementation:
`tools/h3re/h3re/battle.py`. Tests: `tools/h3re/tests/test_battle.py`.

Scope: field battles only, between two sides of 1–7 stacks with optional
heroes. Out of scope: spells, sieges (walls, moat, towers), war machines, AI,
retreat/surrender, experience. The source rules are `rules.md` §6. Tags are
the same as in that file: **[documented]**, **[uncertain]** and **[engine]**.

## 1. Interface

- `create_battle(battle_id, attackers, defenders, obstacles=(), heroes=(None, None), policy=DEFAULT_POLICY)`
  builds the initial state, which has not started yet. Inputs are `StackSetup(creature, count, morale, luck, pos=None)`,
  `Creature(...)` (all numbers come from content data, along with the ability flags) and
  `Hero(attack, defense, offense, archery, armorer)`.
- `apply(state, cmd, rng) -> (state', events)`. This is the only way to
  advance a battle. The first command must be `Begin()`. After that come
  `Move(stack, dest)`, `Attack(stack, target, from_hex=None)`,
  `Shoot(stack, target)`, `Wait(stack)` and `Defend(stack)`. `stack` must be
  the active stack.
- An illegal command raises `IllegalCommand`. All validation runs before any
  RNG draw, so a rejected command touches neither the state nor the stream.
  [engine]
- A malformed hex is an illegal command: `Move.dest` and `Attack.from_hex` must
  be a tuple or list of exactly two `int`s. A float, a `bool`, a non-pair or a
  non-iterable raises `IllegalCommand` (`battle._as_hex`) before any state
  change or RNG draw. It never raises `TypeError` and never reaches the state.
  See section 10, 2026-11-01.
- `apply` refuses a state whose `rules_hash` differs from the local rules pack
  (`rules.RULES_HASH`) by raising `PackMismatch`, a subclass of
  `IllegalCommand`, as the first check of validation (every command, `Begin`
  included): no RNG draw and no state change. [engine]
- `rng` is the `rng.py` named stream `battle:<battle_id>`. Get it with
  `battle_rng(master_seed, battle_id)`, which is
  `derive_stream(master_seed, "battle:<id>")`. [engine]
- State is immutable: frozen dataclasses with tuples, ints, strings and
  bools. There are no floats. `canonical(state)` gives sorted-key compact
  JSON, and `state_hash(state)` is its SHA-256. The active `BattlePolicy` is
  part of the state, so it is also part of the hash. [engine]
- Events (for the presenter): `BattleStarted`, `RoundStarted`, `TurnStarted(stack, phase, bonus)`,
  `MoraleFrozen`, `MoraleBoost`, `Moved(stack, path)`, `Waited`, `Defended`,
  `LuckRolled(stack, good)`, `DamageDealt(attacker, target, damage, killed, ranged, retaliation)`,
  `UnitDied`, `BattleEnded(winner)`.
- Helper queries: `reachable`, `turn_order` (the pending queue, with the active
  stack first), `round_order` (every living stack exactly once: finished
  stacks, then pending ones), `legal_commands`, and the damage preview
  `strike_preview(state, att_id, def_id, ranged)` (section 6).

## 2. Grid

- The grid is 17 columns × 11 rows, with hexes addressed as `(col, row)`.
  Rows are offset. [documented] Which parity is shifted is
  **[uncertain]**: policy `row_offset`, default `"even"`, meaning even rows
  (0, 2, …, 10) are shifted half a hex to the right. A hex in an even row has
  its upper neighbours at `col` and `col+1`; a hex in an odd row has them at
  `col-1` and `col`. The default was `"odd"` until 2026-11-01. It changed
  because VCMI's grid, distance function and renderer all use even rows
  (cross-check #1, confidence clear: its distance matches our
  `hex_distance(..., "even")` on every pair of the grid, while 13 880 pairs
  differ for `"odd"`). The parity is a convention with no other gameplay effect, so this
  is not waiting on a §9 experiment. `"odd"` stays available. The geometry
  helpers (`neighbours`, `hex_distance`, `to_axial`, `from_axial`) default to
  `DEFAULT_ROW_OFFSET = "even"` as well.
- Neighbours and distance go through axial coordinates. Distance is the
  standard hex metric. [engine]
- Columns 0 and 16 are the hero/war-machine edge columns. Whether ordinary
  stacks may use them is **[uncertain]**: policy `edge_columns_walkable`,
  default `False` (VCMI agrees: it marks them as side columns).
- Two-hex stacks occupy their head plus the hex behind it: `col-1` for the
  attacker and `col+1` for the defender, so facing is fixed by side.
  [documented] Both cells must be playable and free. The engine never turns
  stacks around. [engine]
- Initial placement: the attacker uses column 1 (head at column 2 for a two-hex
  stack) and the defender uses column 15 (head at 14 for a two-hex stack),
  with rows taken from a table by army size. **[uncertain]**: policy
  `placement_rows`, default `(5) (2,8) (2,5,8) (0,4,6,10) (0,2,5,8,10)
  (0,2,4,6,8,10) (0,2,4,5,6,8,10)`. An explicit `pos` overrides the table.
- Obstacles come from the caller as a set of blocked hexes. The placement
  algorithm and the obstacle shapes are [engine] and live outside this module.

## 3. Movement [documented]

- Walkers search breadth-first from the head, at cost 1 per hex, up to
  `speed`. Each head position on the path must fit the whole stack: the
  cells must be playable, not obstacles, and not occupied by another living
  stack. Dead stacks do not block. [engine]
- Flyers can reach any head within `hex_distance <= speed`, ignoring
  obstacles and stacks on the way, but they cannot end on an obstacle or an
  occupied hex.
- `Move` ends the turn. `Attack` with `from_hex` moves first (`from_hex` must
  be reachable) and then strikes. The attacker's cells must be adjacent to a
  target cell.

## 4. Turn queue

- Each round, every living stack acts once, in descending speed order.
  [documented]
- Speed ties are **[uncertain]**: policy `speed_tie`. The default
  `"attacker_first"` orders by side and then by slot. The alternatives:
  - `"alternate"` interleaves the sides starting with the attacker in every
    tie group. Because the queue is rebuilt at each activation from the
    stacks still to act, the realised order can differ from the first
    prediction (after the first stack of a group acts, the remaining stacks
    are re-ranked).
  - `"alternate_last_mover"` (VCMI behaviour, cross-check #5): among tied
    stacks the side that did **not** act most recently goes first. "Acted
    most recently" is the side of the last activated stack of any speed
    (a frozen activation counts), and it carries over across rounds. The
    attacker goes first only at the very first activation of the battle.
    Within one side, the lower slot goes first. The state field
    `last_side` records that side (`None` before the first activation).
  VCMI is clear about its own behaviour but not proof of the original's, so
  the default stays `"attacker_first"` until the rules.md §9.4 experiment.
- **Wait** moves the stack into the wait phase, which runs after all
  stacks that did not wait. A stack cannot wait twice in one round, and it
  cannot wait during a morale bonus action. [engine] The order within the
  wait phase is **[uncertain]**: policy `wait_order`. The default
  `"reverse_speed"` is the exact reverse of the main-phase order (this also
  reverses the slot and side priority). The alternatives are `"speed"`,
  `"fifo"` (the order in which stacks waited) and `"slow_first_alternate"`
  (VCMI behaviour, cross-check #6): ascending speed, ties broken by the
  last-mover rule above whatever `speed_tie` says, lower slot first within a
  side. The default stays `"reverse_speed"` pending rules.md §9.4. VCMI's
  extra sub-phase for stacks that waited during a morale bonus turn is not
  modelled, because waiting in a bonus turn is forbidden here (cross-check
  #14, ambiguous; no change).
- **Defend** ends the turn. Until the stack's next activation it gets
  `max(min, round(Defense × num/den))`, where Defense is the creature's
  Defense plus the hero's Defense. The value and rounding are
  **[uncertain]**: policy `defend_bonus_num/den/min/rounding`, default
  1/5, minimum 1, floor.
- When the queue is empty, a new round starts and every retaliation
  counter resets to 1. [documented]
- Speed changes in the middle of a round (Slow/Haste) are **[uncertain]** and
  not applicable here, since there are no spells. Speeds are static.

## 5. Morale and luck

Chances come only from `rules.good_morale_chance`, `rules.bad_morale_chance`
(called with the policy's `bad_morale_table`) and `rules.luck_chance`, which clamp to −3..+3. Stacks with `no_morale` count
as morale 0. [documented] The morale value itself is an input: army morale
modifiers are **[uncertain]** and the caller computes them.

- At each regular main-phase activation the engine makes one morale roll if
  M ≠ 0. At a wait-phase activation the two signs are switched separately
  **[uncertain]** (rules.md §6.5, §9.12): policy
  `bad_morale_on_wait_activation`, default `False` (a stack that waited
  cannot freeze when its wait-phase turn starts), and
  `good_morale_on_wait_activation`, default `True` (it still rolls for a
  bonus action after its wait-phase action). This follows VCMI
  (cross-check #4, clear in VCMI, original unverified).
  - **Deprecated:** these replace `morale_roll_on_wait_activation`
    (removed 2026-11-01). Old `True` (the old default) = both new fields
    `True`; old `False` = both `False`. The new default differs from the old
    one in the bad-morale roll only.
- The bad-morale chance table is **[uncertain]** (rules.md §6.5, §9.13):
  policy `bad_morale_table`, numerators over 24 for morale −1/−2/−3,
  default `(1, 2, 3)` (`rules.BAD_MORALE_NUMERATORS`, the documented
  |M|/24). VCMI uses `(2, 4, 6)` (`rules.VCMI_BAD_MORALE_NUMERATORS`).
- A good-morale result drawn at the main activation
  of a stack that then waits is discarded when `good_morale_after_wait` is
  `False`; the draw still happens, so the RNG sequence does not depend on
  that choice. With M < 0, a successful roll
  freezes the stack: its turn is lost. With M > 0, a successful roll grants a
  bonus action once the current action has finished.
- Whether good morale fires after **Wait** or after **Defend** is
  **[uncertain]**: policies `good_morale_after_wait` and
  `good_morale_after_defend`, both default `False`. When a bonus is granted
  after a Wait, it replaces the wait-phase turn.
- Whether good morale can fire repeatedly is **[uncertain]**: policy
  `repeat_good_morale`, default `False`, so a bonus action makes no roll.
- Good luck: each strike by a stack with L > 0 rolls `luck_chance(L)`. On
  success the strike takes `I_luck = 1.0` (inside `rules.resolve_damage`).
  [documented]
- Bad luck is **[uncertain]**: policy `bad_luck`, default `False`, matching
  `rules.py`, which leaves it out. When it is enabled, a stack with L < 0
  rolls `luck_chance(-L)`, and on success the final damage is halved by
  floor division with a minimum of 1. Where this sits in the formula is part
  of the uncertainty.

## 6. Damage and attacks

- Damage is one call: `rules.resolve_damage(strike_context(...),
  RollPolicy.ACTUAL_SEED, rng)` (luck roll, damage rolls, modifiers; draw
  for draw the same as the former `base_damage` + `damage_from_base`
  two-step, so the golden hash did not change). The result is applied with
  `rules.apply_damage`. `strike_context(state, att, dfn, ranged)` is the only
  place battle state becomes damage inputs. `strike_preview(state, att_id,
  def_id, ranged)` runs the same pipeline under PESSIMAL / EXPECTED /
  OPTIMAL and returns `(floor, expected, ceiling)` without touching the RNG;
  the damage `apply` deals for that strike always lies in
  `[floor, ceiling]` (rules.md §6.6 step 5). The greedy AI
  (`battle_ai.py`) scores attacks with the EXPECTED value of this same
  function and keeps no copy of the rules. A is the creature's Attack
  plus the hero's Attack. D is the creature's Defense plus the hero's Defense
  plus any defend bonus. Offense and Archery come from the attacker's hero,
  Armorer from the defender's hero, and `hates` from the creature's
  hated-name list. [documented]
- Intermediate rounding is **[uncertain]** (rules.md §9.1). It is handled
  inside `rules.py`, which floors once at the end, and is not switchable
  from this module.
- `R_range` applies when the distance is greater than the threshold, unless
  the shooter has `no_range_penalty`. The threshold is **[uncertain]**:
  policy `range_penalty_beyond`, default 10 (VCMI agrees: penalty at 11+).
  The distance origin is policy `range_origin`: the default `"head"`
  measures from the shooter's head hex to the nearest target cell
  (cross-check #12, clear); `"any_cell"` takes the minimum over all shooter
  cells (the behaviour before 2026-11-01). The two differ only for two-hex
  shooters, so the golden battle is not affected.
- `R_melee` applies when a shooter makes a melee attack or retaliates,
  unless it has `no_melee_penalty`. [documented] The penalty depends on the
  creature being a shooter (`shots > 0` in its definition), not on ammo left:
  a shooter with 0 shots remaining still takes the melee penalty when it
  attacks or retaliates in melee (rules.md 6.7).
- A shooter with an enemy adjacent, or with no ammo left, cannot shoot.
  Shots are never retaliated. `shoots_twice` makes two shots, using one
  piece of ammo each. [documented; ammo per shot is engine]
- Melee: strike, then a retaliation if the defender survived and
  still has one left (or has `unlimited_retaliation`) and the attacker lacks
  `no_enemy_retaliation`. With `strikes_twice`, a second strike follows if
  both stacks are still alive. A retaliation is a normal melee strike that
  uses the retaliator's count after it has taken damage. [documented]
- Draw order per strike: luck roll, then damage rolls. For a melee exchange
  the order is: attacker luck → attacker damage → defender luck → defender
  damage → (second strike) → morale roll at the next activation. A chance
  that is 0 or 1 consumes no draw. [engine, rules.md §7]
- Multi-hex attacks and siege wall penalties are out of scope here.
  `rules.damage_from_base` already multiplies `R_wall` and `R_range` when
  both apply (a long shot over a wall deals 25 %; cross-check #11, rules.md
  §9.3), so a future siege module only has to set `wall_penalty`.

## 7. Battle end

A side loses as soon as it has no living stacks. `BattleEnded(winner)` is
emitted, the state keeps `winner` and stops accepting commands.
[documented] Retreat, surrender and experience are out of scope.

## 8. Uncertain policy summary

The defaults below are not in `battle.py`: they are read from
`data/battle_policy.json` (validated by `datapack.py`, `datapack.md`), except
`bad_morale_table`, whose default is `rules.BAD_MORALE_NUMERATORS` from
`data/rules.json`. A drift test compares the file and `BattlePolicy()` with a
literal copy. The state still carries the whole policy, so the hash is
unchanged by this move.

| Policy field | Default | rules.md |
|---|---|---|
| `row_offset` | `"even"` (was `"odd"`) | §6.1 [uncertain]; VCMI #1 clear |
| `edge_columns_walkable` | `False` | §6.1 [uncertain] |
| `placement_rows` | table in §2 | §6.1 [uncertain] |
| `speed_tie` | `"attacker_first"` (option `"alternate_last_mover"`) | §6.3 [uncertain], §9.4 |
| `wait_order` | `"reverse_speed"` (option `"slow_first_alternate"`) | §6.3 [uncertain], §9.4 |
| `defend_bonus_num/den/min/rounding` | 1/5, 1, floor | §6.3 [uncertain], §9.5 |
| `good_morale_after_wait` | `False` | §6.5 [uncertain], §9.12 |
| `good_morale_after_defend` | `False` | §6.5 [uncertain], §9.12 |
| `repeat_good_morale` | `False` | §6.5 [uncertain], §9.12 |
| `bad_morale_on_wait_activation` | `False` (old field: `True`) | §6.5 [uncertain], §9.12 |
| `good_morale_on_wait_activation` | `True` | §6.5 [uncertain], §9.12 |
| `bad_morale_table` | `(1, 2, 3)` (VCMI: `(2, 4, 6)`) | §6.5 [uncertain], §9.13 |
| `bad_luck` | `False` | §6.5 [uncertain], §9.6 |
| `range_penalty_beyond` | 10 | §6.6 [uncertain], §9.2 |
| `range_origin` | `"head"` (was all cells) | §6.6, §9.2; VCMI #12 clear |

Cross-check numbers (#1, #4, …) refer to the table in
`docs/specs/vcmi-crosscheck-rules.md` §1.

## 9. Tests

- Neighbour and distance tables for both parities. Distance is
  cross-checked against BFS on an empty grid.
- Movement around obstacles: walls, detours, flyers versus walkers, two-hex
  fit, and the edge-column policy.
- Queue order: speed, all three tie policies (including the last-mover
  alternation carrying across rounds), all four wait orders, defend bonus
  and expiry, and round rollover.
- Morale at wait-phase activation (both switches), the bad-morale table,
  and the range-penalty origin for a two-hex shooter.
- Morale, luck, retaliation once per round, shooting and penalties, and
  battle end.
- Preview law: across seeded golden battles (with and without `bad_luck`)
  and random-command playouts, the first strike of every Attack/Shoot lies
  in the `strike_preview` range computed just before it.
- Golden hash: a seeded 2v2 battle (`battle_rng(12345, "golden")`, scripted
  chooser) replays to a pinned SHA-256.
- Property tests: random legal playouts under default and non-default
  policies. They check that counts are never negative, HP never increases,
  `round_order` holds each living stack exactly once, cells never overlap or
  sit on obstacles, and illegal commands consume no RNG.

## 10. Change notes

### 2026-11-01: golden hash re-pinned (one reviewed change)

`GoldenTest.PINNED` (`tests/test_battle.py`), `GOLDEN_PINNED`
(`tests/test_battle_cli.py`) and `battle-scenario.md` §7 moved together from
`cd969e37b84f2c1dde88ad5cf2b3d8e0f11f211ace9ccfe2226405a6c06da95d` to
`2191ae97fb22c8d15389d3e54c1a1eb6569a8d53630e0af647bd4ca97ca0d67d`.

Reason: applying `docs/specs/vcmi-crosscheck-rules.md` to the battle side.

- `row_offset` default `"odd"` → `"even"` (cross-check #1, clear). This
  changes adjacency, paths and distances, so the golden battle plays
  differently. It is the main cause of the new hash.
- `morale_roll_on_wait_activation` (default `True`) replaced by
  `bad_morale_on_wait_activation=False` and
  `good_morale_on_wait_activation=True` (cross-check #4). Only the
  bad-morale roll at a wait-phase activation changes.
- Canonical form: every `BattlePolicy` field is now included, including the
  new ones at their default values (the "omit while default" list,
  `_OMIT_WHEN_DEFAULT`, is empty again after this re-pin), and the state
  gains `last_side`.
- Added options that do not change defaults: `speed_tie=
  "alternate_last_mover"`, `wait_order="slow_first_alternate"`,
  `bad_morale_table` (default unchanged), `range_origin` (new default
  `"head"`; it does not affect the golden battle, which has no two-hex
  shooter).

Anyone holding saved battle states or hashes from before this date must
re-derive them. A state built with `BattlePolicy(row_offset="odd",
bad_morale_on_wait_activation=True, range_origin="any_cell")` plays like the
old default, but its hash is still different because of the new canonical
fields.

### 2026-11-01: golden hash re-pinned a second time (rules pack in the hash)

`GoldenTest.PINNED` (`tests/test_battle.py`), `GOLDEN_PINNED`
(`tests/test_battle_cli.py`) and `battle-scenario.md` §7 moved together from
`2191ae97fb22c8d15389d3e54c1a1eb6569a8d53630e0af647bd4ca97ca0d67d` to
`fbe9015bde1b6e5c165c08fc1604f98ea7c3cdf09cc38528ec2fda496f040e2b`.

Reason (determinism-audit finding, HIGH): `rules.py` binds its tuning
constants from `data/rules.json` at import (`H3_DATA_PACK_DIR` can point
elsewhere), but the pack was not part of the hashed state. Two peers with
different packs played different battles from the same seed yet hashed equal
at step 0. `BattleState` now has a string field `rules_hash`, set from
`rules.RULES_HASH` (the `datapack` content hash of the loaded `rules.json`;
`898c9b9f…03c559e` for the shipped pack), and it is always in the canonical
form (`_OMIT_WHEN_DEFAULT` stays empty). Peers with different packs now
differ from the first `create_battle`.

This is a pure canonical-form change. The play is unchanged: removing
`rules_hash` from the canonical JSON of the golden final state reproduces
`2191ae97…` exactly. The hash covers `rules.json` only; `creatures.json` is
still passed in as `Creature` values and is already part of the state.
`apply` did not compare `rules_hash` with the local pack at this point; that
follow-up is done, see the next change note.

Adventure: `adventure.py` reads no pack value (its terrain, road and
Logistics numbers are its own constants and policy), so a pack difference
cannot change an adventure outcome and `GameState` does not carry
`rules_hash`. The adventure golden hash did not move. If adventure starts
reading the pack, add the field then, as a re-pin.

Also in this change (no hash effect): `luck_chance` and `good_morale_chance`
divide by `MORALE_DIE` instead of a literal 24. Luck shares the pack's one
die with morale; there is no separate luck die in `rules.json`.

### Later: policy defaults moved to data, `apply` checks the pack (no re-pin)

The golden hash did **not** move (`fbe9015b...` stays pinned).

- `BattlePolicy` defaults now come from `data/battle_policy.json` (see section 8
  and `datapack.md`) instead of literals in `battle.py`. The values are the same,
  and the policy was already in the canonical form, so no state field was added.
  `_OMIT_WHEN_DEFAULT` stays empty. `battle.POLICY_HASH` exposes the file's
  content hash for logs and tests; it is not part of the state.
- `apply` now raises `PackMismatch` (an `IllegalCommand`) when
  `state.rules_hash != rules.RULES_HASH`, before any RNG draw or state change.
  Only `rules.json` is covered by `rules_hash`; a state saved under another
  `battle_policy.json` keeps playing by the policy stored in it, which is what
  its hash already commits to.

### 2026-11-01: malformed hex raises IllegalCommand (no re-pin)

The golden hash did **not** move (`fbe9015b...`). Legal commands always use
int pairs, so no pinned scenario changes.

- Before: a float pair such as `(2.0, 5)` passed as `Attack.from_hex` was stored
  as the stack position; a non-pair could raise `TypeError`.
- Now: `Move.dest` and `Attack.from_hex` go through `_as_hex`, which accepts only
  a tuple or list of two values of exact type `int`. Anything else (float, bool,
  wrong length, non-iterable) raises `IllegalCommand` before any state change
  or RNG draw.
- `adventure.py` `Move.dest` has the same entry check (`_as_tile`, `adventure.md`
  section 8). No test found in `test_adventure.py` pins a float or bool `dest`:
  a gap for `sim-engineer`.
- Verification: `MalformedHexTest` in `tools/h3re/tests/test_battle.py` (rejects
  `(2.0, 5)`, `(True, 5)`, `[1]`, `(1, 2, 3)`, `5`, `"ab"` and `{1: 2}` with
  `IllegalCommand`, and checks that no draw happens).


### 2026-11-01: state invariants and integer caps (no re-pin)

Kotlin-port audit, findings 1, 2 and 4. `battle.check_state(state)` states the invariants of a
battle state; `create_battle` calls it on every state it returns, and the Kotlin parser
(`BattleCodec.parseState`) applies the same checks in the same order with the same messages.
Python had no state parser, and `create_battle` did not bound its inputs, so these checks are new on
the Python side (recorded here, per CLAUDE.md law 10). They only refuse input; `apply` is unchanged.

- Shape: two hero slots; 1..7 stacks per side; stack `id` equals its index; `side` is 0 or 1;
  `slot` in 0..6; every footprint cell and obstacle on the grid; `round` >= 0; `active`, `done` and
  `waited` ids index a stack; `winner` and `last_side` are 0, 1 or None.
- Stack values: `count` >= 0; `top_hp` is 0 for an empty stack and in 1..hp otherwise; `shots` and
  `retaliations` >= 0; creature `hp` >= 1, `speed` >= 0, `shots` >= 0, 0 <= `dmg_min` <= `dmg_max`, `dmg_max` >= 1.
  Owner decision 2026-11-02: `dmg_min` 0 is a valid weak unit (base roll 0..`dmg_max`; the final damage keeps
  its existing minimum of 1). Pinned vectors that encoded the old `1 <= dmg_min` floor need owner re-pin
  review (law 6); they are not regenerated in this change.
- Every integer fits a 32-bit Int (ADR-0008).
- Caps on the derived products (ADR-0008 amendment): `count x dmg_max` <= 2**31-1, `count x hp`
  <= 2**31-1, creature plus hero attack within Int, creature plus hero defense within Int with and
  without the defend bonus (the bonus is added whether or not the stack defends now, because it
  can defend later).
- `BattlePolicy` also bounds `defend_bonus_num`, `defend_bonus_den`, `defend_bonus_min` and
  `range_penalty_beyond` to 0..2**31-1 (the same bounds `datapack.py` applies to the pack) and each
  `placement_rows` entry to the Int range.
- Damage is not capped: one strike at the caps deals more than 2**31-1 (8589934588 in the `cap`
  vector case). `DamageDealt.damage` is a `Long` in Kotlin.

No pinned hash moved: the golden hash is still `fbe9015b...`, and all 41 earlier vector cases and
4007 earlier illegal cases are byte-identical after regeneration (`battle_states.json` gains the
`cap` case and the reject lists).
