# Adventure-map simulation core (`sim.adventure`): movement and economy

Status: draft v1, roadmap phase 7 (partial). Reference implementation:
`tools/h3re/h3re/adventure.py`. Tests: `tools/h3re/tests/test_adventure.py`.

Scope: a tile grid with terrain and road movement costs, hero movement
points, pathfinding, and the day/week tick with daily income and a weekly
growth hook. Out of scope: towns, map objects (mines exist only as a list of
owned mine kinds), fog of war, boats and sea movement, native terrain,
artifacts, spells, AI and random weekly effects. Battles on the map (an
`Attack` on a guard or an enemy hero) are in section 8 and `encounter.md`,
not here. The source rules are `rules.md` §1–§3. Tags are the same as in that file: **[documented]**,
**[uncertain]** and **[engine]**.

## 1. Interface

Same pattern as `battle.md` §1. [engine]

- `create_game(game_id, grid, players, heroes, pools=(), policy=DEFAULT_POLICY)`
  builds the initial state, which has not started yet. Inputs:
  `Grid(width, height, tiles)` with row-major `Tile(terrain, road="none", blocked=False)`,
  `Player(resources, mines, extra_income)`,
  `HeroSetup(owner, pos, army, logistics=0, pathfinding=0)` with
  `ArmySlot(creature, speed, count)` (1–7 slots; the speed comes from content
  data), and `GrowthPool(id, available, growth)`.
- `apply(state, cmd, rng) -> (state', events)`. Commands: `Begin()` (once,
  first), `Move(hero, dest)` and `EndTurn(player)`.
- Validation: an illegal command raises `IllegalCommand` and leaves the state
  unchanged. Only the current player may act. `Move` requires `dest` to be in
  `reachable(state, hero)`. The hero moves along exactly that path.
- `rng`: nothing in scope is random. `apply` accepts the stream
  `adventure:<game_id>` (`adventure_rng(master_seed, game_id)`) only to keep
  the interface stable, and it never draws from it. The tests pass an object
  that fails if it is touched.
- State is immutable: frozen dataclasses with tuples, ints, strings and
  bools. There are no floats. `canonical(state)` is sorted-key compact JSON
  and `state_hash(state)` is its SHA-256. The policy is part of the state.
- Queries: `step_cost(grid, a, b, pathfinding, policy)`,
  `find_path(state, hero, dest)` (cheapest path with no daily limit, for UI
  planning), `reachable(state, hero)` (tile → `(cost, path)` within today's
  points), `base_movement(army)`, `max_movement(hero)`, `daily_income(player)`
  and `calendar(day)`.
- Events: `DayStarted(day, week, day_of_week, month)`,
  `WeekStarted(week, month, new_month)`, `PoolGrew(pool, added, available)`,
  `TurnStarted(player, day)`, `IncomeReceived(player, income)`,
  `MovementReset(hero, mp)`, `HeroMoved(hero, path, cost, mp_left)` and
  `TurnEnded(player)`.

## 2. Grid and step costs

- Tiles are `(x, y)` and every tile has 8 neighbours. [engine]
- Terrain cost of an orthogonal step: dirt/grass/lava/subterranean 100,
  rough 125, sand/snow 150, swamp 175. [documented] `water` and `rock`, and
  any tile with `blocked=True`, cannot be entered or left on land.
  [engine: stand-in for map decorations and the sea]
- Road step (VCMI cross-check, `vcmi-crosscheck-rules.md`, clear): a road
  applies only if both tiles have one (`road_needs_both=True`), and the rate is
  the SOURCE tile's road (`road_rate_from="source"`). `road_cost` defaults to
  dirt 75, gravel 65, cobblestone 50. With `road_needs_both=False` a road on
  either tile applies (the rate comes from the tile that has one, or per
  `road_rate_from` when both do; `"dest"` and `"max"` are options).
- Without a road, the tile LEFT sets the terrain price (`cost_from="source"`;
  `"dest"` keeps the old wording of rules.md §2.2).
- Pathfinding level L (`pathfinding_mode="flat"`): subtract
  `pathfinding_flat[L]` = 0/25/50/75 points from the terrain cost, never below
  `move_cost_floor` = 100 (swamp 175 -> 150/125/100, sand 150 -> 125/100/100,
  rough 125 -> 100). It never affects roads. `pathfinding_mode="percent"`
  keeps the old rule: cut `pathfinding_pct[L]` percent of the part above 100,
  rounded by `pathfinding_rounding`.
- Diagonal step (`diagonal_mode="sqrt2"`): floor(cost x sqrt 2), computed
  exactly with `isqrt(2*cost^2)` (no floats): 100 -> 141, 125 -> 176,
  150 -> 212, 175 -> 247; roads 75 -> 106, 65 -> 91, 50 -> 70. Applied after
  the road and Pathfinding rules. `diagonal_mode="ratio"` keeps the old
  `diagonal_num / diagonal_den` with `diagonal_rounding` (141/100 gives 246
  for 175, one less than sqrt2).
- Corner cutting: with `diagonal_corner_cut=False`, a diagonal step needs
  both orthogonal side tiles to be passable. [uncertain]
- Tiles occupied by other heroes (of any owner) and by guards cannot be entered
  or crossed. [engine: meeting an own hero is out of scope; attacks on other
  heroes and on guards are in section 8 and `encounter.md`]

## 3. Movement points

- Base daily points from the slowest stack, using the table in rules.md
  §2.1 (≤3 → 1500 … ≥11 → 2000). [documented]
- Logistics adds 10/20/30% of the base. [documented] Every table value is a
  multiple of 10, so the result is always an integer and the [uncertain]
  rounding question cannot come up. It returns once artifact or stable
  bonuses are added.
- Points are set to full at the start of the owner's turn each day and do
  not carry over. [documented] The army as it stands at that moment sets the
  value. A change of army during the day does not recompute it. [uncertain]
- Before `Begin`, heroes have 0 points. After `Begin`, the first player's
  heroes start full, and every other player's heroes fill up when that
  player's turn starts.
- Last step. A step needs points left >= its cost (`last_step="forbid"`,
  the default), with two VCMI-documented rules (both clear in the report):
  - `diagonal_exception=True`: a diagonal step that costs more than the points
    left is still allowed if the points left cover the orthogonal cost of the
    same step. It uses up all remaining points.
  - `zero_remainder=True`: after a paid step, if 0 < points left < the cost of
    repeating that step, all remaining points are used up (the step is charged
    `left`). This is applied inside `reachable`, so a tile reached this way
    costs the whole remaining budget and ends the day. `find_path` (no budget)
    never applies it.
  - Old options: `last_step="allow_if_any"` (any points left: take the step,
    costs exactly what is left) and `"allow_if_fresh"` (only as the hero's
    first step of the day).
- Points never go negative (property-tested).

## 4. Pathfinding

- Dijkstra over tiles from the hero's position. Every step costs more than
  0. [engine]
- Each tile's label is `(cost, steps, tile sequence)`, and the lexicographically
  smallest label wins. That means cheapest first, then fewest steps, then the
  path whose tile sequence (as `(x, y)` tuples) compares smallest. A tile's
  path always extends the winning path of its predecessor, so the result does
  not depend on neighbour iteration order. [engine]
- `reachable` runs the search with today's points as the budget and the
  last-step rule. `find_path` runs it with no budget. For tiles that cost
  less than the points left, the two give identical results (tested).
- Multi-day route splitting and turn markers belong to the UI layer. It
  walks the `find_path` route and moves to the furthest tile on it that is
  in `reachable`. [engine]

## 5. Calendar, income and growth

- `day` is absolute and starts at 1. `calendar(day)` gives
  `week = (day-1)//7 + 1`, `day_of_week = (day-1)%7 + 1` and
  `month = (day-1)//28 + 1`. [documented: 7-day weeks, 4-week months]
- `EndTurn(player)` passes the turn to the next player in index order. After
  the last player, a new day starts. [documented]
- At the start of a day that is day 1 of a week other than the first:
  `WeekStarted`, and then each `GrowthPool` gets `available += growth`, in
  tuple order (unrecruited creatures accumulate). [documented] This happens
  once per day, before the first player's turn. [engine]
- `growth` is computed by its owner (the future town module, with Citadel or
  Castle bonuses and their [uncertain] rounding, or map dwellings), so this
  core only applies the number. The week-of-creature and plague effects are
  out of scope.
- At the start of each player's turn: `TurnStarted`, then daily income
  `extra_income + Σ MINE_OUTPUT[mine]`, with the mine table from rules.md §3
  [documented], then `MovementReset` for that player's heroes.
  `extra_income` is the hook for town halls, the Silo and Estates, because
  the amounts come from content.
- Income on day 1 (`income_on_first_day`, default `False`). [uncertain]
- Resources are 7 integers: gold, wood, ore, mercury, sulfur, crystal and
  gems. Nothing in scope spends them.

## 6. Policy fields (`AdventurePolicy`)

Fields in the first rows now default to the VCMI cross-check values
(`docs/specs/vcmi-crosscheck-rules.md`, items rated clear). VCMI is evidence,
not proof: `rules.md` §9 items 7 and 8 still decide, and each old behaviour is
kept as an option. Mysticism is out of scope. Items marked * were never in §9.

| Field | Default | Alternatives | Question |
|---|---|---|---|
| `road_cost` | dirt 75, gravel 65, cobblestone 50 | any costs 1..10000 | Road rates (VCMI) |
| `road_needs_both` | `True` | `False` | Road needed on both tiles (VCMI) |
| `road_rate_from` | `"source"` | `"dest"`, `"max"` | Which road sets the rate (VCMI: source) |
| `cost_from` | `"source"` | `"dest"` | Tile that prices a step (VCMI: source) |
| `diagonal_moves` | `True` | `False` | (engine switch, for comparison) |
| `diagonal_mode` | `"sqrt2"` | `"ratio"` | floor(cost x sqrt2) vs a fixed ratio |
| `diagonal_num/den` | 141/100 | e.g. 142/100; each 1..10000 | Ratio mode only |
| `diagonal_rounding` | `"floor"` | `"ceil"`, `"nearest"` | Ratio mode only |
| `diagonal_corner_cut` | `True` | `False` | Can a diagonal pass between two blocked tiles?* |
| `last_step` | `"forbid"` | `"allow_if_any"`, `"allow_if_fresh"` | Points needed for a step |
| `diagonal_exception` | `True` | `False` | Diagonal allowed if orthogonal cost is covered |
| `zero_remainder` | `True` | `False` | Leftover < repeat cost is used up |
| `pathfinding_mode` | `"flat"` | `"percent"` | Flat 25/50/75 points vs percent of penalty |
| `pathfinding_flat` | (0, 25, 50, 75) | each 0..10000 | Flat reductions |
| `move_cost_floor` | 100 | 1..10000 | Floor for Pathfinding |
| `pathfinding_pct` | (0, 25, 50, 75) | any 0..100 | Percent mode only |
| `pathfinding_rounding` | `"floor"` | `"ceil"`, `"nearest"` | Percent mode only |
| `income_on_first_day` | `False` | `True` | Is income paid on day 1?* |

### Integer bounds and types (amendment, ADR-0008 style)

Context: the Kotlin port (ADR-0004) holds step costs and movement points in a 32-bit `Int`
(ADR-0008). Python accepted any `int` for the policy integers, so a legal policy such as
`diagonal_num=10**8` or `move_cost_floor=2_000_000_000` made Python return a cost the Kotlin
engine could only refuse with an overflow. Python also accepted a `bool` (`diagonal_num=True`
hashed as `true` and priced as 1) and a `float` (which reached the integer-only sim).

Decision: `AdventurePolicy.__post_init__` requires `type(x) is int` (not a `bool`, not a
`float`) for `diagonal_num`, `diagonal_den`, `move_cost_floor`, every `pathfinding_flat` and
`pathfinding_pct` entry and every `road_cost` cost, and bounds them: `1..POLICY_INT_MAX` for
`diagonal_num`, `diagonal_den`, `move_cost_floor` and road costs, `0..POLICY_INT_MAX` for
`pathfinding_flat`, `0..100` for `pathfinding_pct`, with `POLICY_INT_MAX = 10_000`. A value
outside the bound or of the wrong type raises `ValueError`; nothing is clamped. Messages:
`diagonal_num and diagonal_den need ints in 1..10000` (was `bad diagonal fraction`),
`move_cost_floor needs an int in 1..10000` (was `bad move_cost_floor`),
`pathfinding_flat needs 4 ints in 0..10000`, `pathfinding_pct needs 4 values in 0..100` and
`road_cost needs a cost in 1..10000 for each road type`. The check order is unchanged.

With the bound, an orthogonal step costs at most 10^4 (terrain is at most 175), a ratio
diagonal at most 10^4 x 10^4 = 10^8, and a budgeted search never spends more than the hero's
`Int` points, so `Adventure.apply` cannot overflow. An unbudgeted `find_path` can sum past
`Int` (24 diagonal steps of 10^8 is 2.4 x 10^9), so Kotlin keeps path costs in `Long`.

Kotlin `AdventurePolicy.validate` mirrors the checks in the same order; an integer beyond `Int`
in the source JSON is clamped for the check only (every bound is far inside `Int`, so the
verdict and message are Python's) and a non-integer is refused with the same message.
Conformance: `policy_cases` in `adventure.json` (docs/specs/conformance-adventure.md).
No pinned hash moved: the default and every vector policy are far below the bound
(adventure golden `179c5700...` unchanged). Boolean policy fields still accept any truthy
value in Python; that is not covered by this amendment.

### Default changes and the golden hash

One reviewed change moved these defaults: `cost_from` dest -> source;
`road_needs_both` False -> True (plus `road_rate_from="source"`); road costs
50/50/50 -> 75/65/50; Pathfinding percent -> flat points with a floor of 100;
diagonals 141/100 -> exact floor(cost x sqrt2); `last_step` `"allow_if_any"` ->
`"forbid"` plus `diagonal_exception` and `zero_remainder`. The 14-day golden
hash was re-pinned once, from `e859fff5...` to `179c5700...`, because the
scripted heroes now pay different costs and so take different tiles each day.
The policy is also part of the hashed state. Most old values are reachable as
policy options, and the property tests cover them. One is not: the original
rule "a road discount applies only if the destination tile has a road, and then
the destination's rate is used" (with `road_needs_both=False`, a step off a
road onto a roadless tile got no discount). Today `road_needs_both=False` also
discounts a step that has a road only on the source tile, and
`road_rate_from="dest"` does not change that. Decision (law 10, audit
2026-11-01): correct the spec, do not add an option. The original rule was a
draft guess, not a documented behaviour, and a new policy field would move the
adventure hash for no gain. The `road_needs_both=True` old behaviour (rate
`max` of both tiles) is reachable with `road_rate_from="max"`.

`road_cost` is stored as a tuple of `(road, cost)` pairs sorted by road name;
`AdventurePolicy` sorts it on construction and rejects a duplicate road, so one
policy has one canonical form and one hash (this does not move the default
hash, which was already sorted). `GameState` does not carry the rules-pack hash:
`adventure.py` reads no `rules.json` value (see `battle.md` §10).

Other unverified assumptions that have no switch (the VCMI order of road,
Pathfinding and diagonal is as above): Pathfinding is applied before the
diagonal factor; points are computed from the army at the start
of the day; heroes block tiles; `water`/`rock` cannot be passed on land.

## 7. Tests

- Step cost for each terrain and road, impassable tiles, the road detour,
  Pathfinding, and the deterministic tie-break.
- A test for every policy field showing the outcome changes as described
  above.
- The movement-point table, the slowest stack, Logistics, and the daily
  reset without carry-over.
- Daily income by player turn, week rollover with pool growth across 4 weeks
  including the month flag, and the event order on day 8.
- Golden: a scripted 14-day run (2 players, 3 heroes, daily waypoints)
  reaches a pinned state hash. A policy change alters the run.
- Properties over random playouts under 3 policies: points are never
  negative and never above the maximum; a move subtracts exactly its cost;
  heroes stay on distinct, passable tiles; illegal commands leave the state
  unchanged; identical inputs give identical state and events.

## 8. Encounters (battles on the map)

Battles between a hero and an enemy hero or a neutral guard are specified in
`docs/specs/encounter.md`. This section lists what they change here. The
scope line and the §2 note point here: attacking is possible, meeting an
own hero still is not.

- Command `Attack(hero, target)` (target: hero id `int` or guard id `str`).
  `apply` hands it to `encounter.validate` / `encounter.resolve`. For this
  command only, `rng` is the battle stream `battle:<game_id>:<n>`
  (`encounter.stream_for`); every other command still never draws.
- `Guard(id, pos, army)`: a neutral army on a passable tile. Guards block
  their tile like heroes (they cannot be entered or crossed). [engine]
- `GameState` gains `guards=()`, `encounter=None` and `battles=0`.
  `create_game(..., guards=(), encounter=None)` validates guards (string id,
  unique, 1..7 valid slots, passable tile not shared with a hero or guard)
  and, if `encounter` is set, that every army has content in it.
- Canonical form: those three fields are left out while at their default
  (`_OMIT_WHEN_DEFAULT`, ADR-0005, which extends ADR-0001). The 14-day golden
  `179c5700...` is unchanged.
- A hero removed after a lost battle keeps its id with `pos=None` and
  `army=()`. It gets no `MovementReset`, cannot `Move` or `Attack`, does
  not block its old tile, and `reachable`/`find_path` return `{}`/`None`.
- Malformed `Move.dest` (fix): `dest` must be a tuple or list of two `int`s
  (not `bool`); anything else raises `IllegalCommand` before any work.
  Before, a non-iterable raised `TypeError`, and a float or bool pair was
  accepted because it compares equal to the integer tile (the state was
  still built from the path, so no float reached it). `battle.py` had the
  same bug in `Move.dest` and `Attack.from_hex`, where `(2.0, 5)` *was*
  stored as the stack position; it is fixed the same way. Neither golden
  hash moved: legal commands always use int pairs.
- Strict integer command fields (fix): every integer field of `Move`,
  `EndTurn` and `Attack` (`Move.hero`, the elements of `Move.dest`,
  `EndTurn.player`, `Attack.hero`, `Attack.target` when it is a hero id) must
  satisfy `type(v) is int`. `bool`, `float`, `str`, `None` and `int`
  subclasses (numpy-style integers) raise `IllegalCommand` before any state
  or RNG change. Before, `Move.hero` used `isinstance(.., int)` so `True` and
  `False` reached heroes 1 and 0, and `EndTurn.player` was only compared with
  `==`, so `0.0` and `False` passed as player 0. Neither golden hash moved
  (adventure `179c5700...`, encounter `512b53ca...`): legal commands always
  use plain ints.
