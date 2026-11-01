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
  stacks, then pending ones) and `legal_commands`.

## 2. Grid

- The grid is 17 columns × 11 rows, with hexes addressed as `(col, row)`.
  Rows are offset. [documented] Which parity is shifted is
  **[uncertain]**: policy `row_offset`, default `"odd"`, meaning odd rows are
  shifted half a hex to the right.
- Neighbours and distance go through axial coordinates. Distance is the
  standard hex metric. [engine]
- Columns 0 and 16 are the war-machine edge columns. Whether ordinary stacks
  may use them is **[uncertain]**: policy `edge_columns_walkable`, default
  `False`.
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
  `"attacker_first"` orders by side and then by slot. The alternative,
  `"alternate"`, interleaves the sides starting with the attacker.
- **Wait** moves the stack into the wait phase, which runs after all
  stacks that did not wait. A stack cannot wait twice in one round, and it
  cannot wait during a morale bonus action. [engine] The order within the
  wait phase is **[uncertain]**: policy `wait_order`. The default
  `"reverse_speed"` is the exact reverse of the main-phase order. The
  alternatives are `"speed"` and `"fifo"` (the order in which stacks waited).
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
and `rules.luck_chance`, which clamp to −3..+3. Stacks with `no_morale` count
as morale 0. [documented] The morale value itself is an input: army morale
modifiers are **[uncertain]** and the caller computes them.

- At each regular activation, including a wait-phase activation, the engine
  makes one morale roll if M ≠ 0. [engine] With M < 0, a successful roll
  freezes the stack: its turn is lost. With M > 0, a successful roll grants a
  bonus action once the current action has finished.
- Whether good morale fires after **Wait** or after **Defend** is
  **[uncertain]**: policies `good_morale_after_wait` and
  `good_morale_after_defend`, both default `False`. When a bonus is granted
  after a Wait, it replaces the wait-phase turn.
- Whether good morale can fire repeatedly is **[uncertain]**: policy
  `repeat_good_morale`, default `False`, so a bonus action makes no roll.
- Good luck: each strike by a stack with L > 0 rolls `luck_chance(L)`. On
  success, `lucky=True` is passed to `damage_from_base`. [documented]
- Bad luck is **[uncertain]**: policy `bad_luck`, default `False`, matching
  `rules.py`, which leaves it out. When it is enabled, a stack with L < 0
  rolls `luck_chance(-L)`, and on success the final damage is halved by
  floor division with a minimum of 1. Where this sits in the formula is part
  of the uncertainty.

## 6. Damage and attacks

- Damage is `rules.base_damage` followed by `rules.damage_from_base`, and the
  result is applied with `rules.apply_damage`. A is the creature's Attack
  plus the hero's Attack. D is the creature's Defense plus the hero's Defense
  plus any defend bonus. Offense and Archery come from the attacker's hero,
  Armorer from the defender's hero, and `hates` from the creature's
  hated-name list. [documented]
- Intermediate rounding is **[uncertain]** (rules.md §9.1). It is handled
  inside `rules.py`, which floors once at the end, and is not switchable
  from this module.
- `R_range` applies when the minimum cell-to-cell distance is greater than
  the threshold, unless the shooter has `no_range_penalty`. The threshold is
  **[uncertain]**: policy `range_penalty_beyond`, default 10.
- `R_melee` applies when a shooter makes a melee attack or retaliates,
  unless it has `no_melee_penalty`. [documented]
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
- Multi-hex attacks, siege wall penalties and their stacking with `R_range`
  (**[uncertain]**) are out of scope here.

## 7. Battle end

A side loses as soon as it has no living stacks. `BattleEnded(winner)` is
emitted, the state keeps `winner` and stops accepting commands.
[documented] Retreat, surrender and experience are out of scope.

## 8. Uncertain policy summary

| Policy field | Default | rules.md |
|---|---|---|
| `row_offset` | `"odd"` | §6.1 [uncertain] |
| `edge_columns_walkable` | `False` | §6.1 [uncertain] |
| `placement_rows` | table in §2 | §6.1 [uncertain] |
| `speed_tie` | `"attacker_first"` | §6.3 [uncertain], §9.4 |
| `wait_order` | `"reverse_speed"` | §6.3 [uncertain], §9.4 |
| `defend_bonus_num/den/min/rounding` | 1/5, 1, floor | §6.3 [uncertain], §9.5 |
| `good_morale_after_wait` | `False` | §6.5 [uncertain], §9.12 |
| `good_morale_after_defend` | `False` | §6.5 [uncertain], §9.12 |
| `repeat_good_morale` | `False` | §6.5 [uncertain], §9.12 |
| `bad_luck` | `False` | §6.5 [uncertain], §9.6 |
| `range_penalty_beyond` | 10 | §6.6 [uncertain], §9.2 |

## 9. Tests

- Neighbour and distance tables for both parities. Distance is
  cross-checked against BFS on an empty grid.
- Movement around obstacles: walls, detours, flyers versus walkers, two-hex
  fit, and the edge-column policy.
- Queue order: speed, both tie policies, all three wait orders, defend
  bonus and expiry, and round rollover.
- Morale, luck, retaliation once per round, shooting and penalties, and
  battle end.
- Golden hash: a seeded 2v2 battle (`battle_rng(12345, "golden")`, scripted
  chooser) replays to a pinned SHA-256.
- Property tests: random legal playouts under default and non-default
  policies. They check that counts are never negative, HP never increases,
  `round_order` holds each living stack exactly once, cells never overlap or
  sit on obstacles, and illegal commands consume no RNG.
