# Adventure-map simulation core (`sim.adventure`): movement and economy

Status: draft v1, roadmap phase 7 (partial). Reference implementation:
`tools/h3re/h3re/adventure.py`. Tests: `tools/h3re/tests/test_adventure.py`.

Scope: a tile grid with terrain and road movement costs, hero movement
points, pathfinding, and the day/week tick with daily income and a weekly
growth hook. Out of scope: towns, map objects (mines exist only as a list of
owned mine kinds), fog of war, boats and sea movement, native terrain,
artifacts, spells, battles, AI and random weekly effects. The source rules
are `rules.md` §1–§3. Tags are the same as in that file: **[documented]**,
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
- A road step costs `policy.road_cost[road]`. [uncertain] The road applies
  when the tile entered has a road, or, with `road_needs_both`, only when
  both tiles do. In that case the step costs the dearer of the two road
  costs. [uncertain]
- Without a road, the terrain that sets the price is the tile entered
  (`cost_from="dest"`, per the wording of rules.md §2.2) or the tile left
  (`"source"`). [uncertain]
- Pathfinding level L reduces the part of the terrain cost above 100 by
  `pathfinding_pct[L]` percent, rounded by `pathfinding_rounding`. It never
  affects roads or 100-cost terrain. [uncertain]
- Diagonal step = the orthogonal cost (after the road and Pathfinding rules)
  × `diagonal_num / diagonal_den`, rounded by `diagonal_rounding`.
  [uncertain] The order "Pathfinding first, then the diagonal factor" is
  [uncertain] and has no switch.
- Corner cutting: with `diagonal_corner_cut=False`, a diagonal step needs
  both orthogonal side tiles to be passable. [uncertain]
- Tiles occupied by other heroes (of any owner) cannot be entered or crossed.
  [engine: hero meetings and battles are out of scope]

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
- Last step (`last_step`) [uncertain], when the next step costs more than
  the points left:
  - `"forbid"`: the step cannot be taken.
  - `"allow_if_any"` (default): with any points left, the step is taken and
    costs exactly what is left, so the hero ends on 0.
  - `"allow_if_fresh"`: only allowed as the hero's first step of the day,
    which spends all of the points. Otherwise the same as `"forbid"`.
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

Each field below is an unverified assumption. They are resolved by
`rules.md` §9 items 7 and 8, plus the new items marked *.

| Field | Default | Alternatives | Question |
|---|---|---|---|
| `road_cost` | dirt/gravel/cobblestone all 50 | any positive costs | Are gravel/cobblestone roads cheaper? |
| `road_needs_both` | `False` | `True` (dearer road wins) | Does a road need to be on both tiles?* |
| `cost_from` | `"dest"` | `"source"` | Is a step priced by the tile entered or the tile left?* |
| `diagonal_moves` | `True` | `False` | (engine switch, for comparison) |
| `diagonal_num/den` | 141/100 | e.g. 142/100, 1414/1000 | Diagonal multiplier |
| `diagonal_rounding` | `"floor"` | `"ceil"`, `"nearest"` | Diagonal rounding |
| `diagonal_corner_cut` | `True` | `False` | Can a diagonal pass between two blocked tiles?* |
| `last_step` | `"allow_if_any"` | `"forbid"`, `"allow_if_fresh"` | Last-step rule |
| `pathfinding_pct` | (0, 25, 50, 75) | any 0..100 | Pathfinding reductions |
| `pathfinding_rounding` | `"floor"` | `"ceil"`, `"nearest"` | Pathfinding rounding* |
| `income_on_first_day` | `False` | `True` | Is income paid on day 1?* |

Other unverified assumptions that have no switch: Pathfinding is applied
before the diagonal factor; points are computed from the army at the start
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
