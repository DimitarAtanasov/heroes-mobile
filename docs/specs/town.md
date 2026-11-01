# Town simulation core (`sim.town`): buildings, build rules and weekly growth

Status: draft v1, roadmap phase 8 (partial). Reference implementation:
`tools/h3re/h3re/town.py`. Tests: `tools/h3re/tests/test_town.py`. Test pack:
`data/towns_test.json` (synthetic factions, buildings and creatures with
made-up names; not game data).

Scope: a faction's building tree (prerequisites, costs, upgrades), the
one-build-per-day rule, resource cost checks against a player treasury, daily
town income as a query, and weekly creature growth computed into the
adventure `GrowthPool` shape. Out of scope: recruitment, the Mage Guild,
town capture, sieges, external (map) dwellings, week-of-creature and plague
effects, the Grail, and the link to `adventure.py`'s calendar and treasury
(see section 5). Source rules: `rules.md` §1, §3 and §4. Tags as in
`rules.md`: **[documented]**, **[uncertain]**, **[engine]**.

## 1. Interface

Same pattern as `battle.md` §1 and `adventure.md` §1. [engine]

- `load_town_pack(path)` / `parse_town_pack(obj)` validate a pack and return
  `TownContent(factions)`; `content_hash(content)` is the SHA-256 of its
  canonical JSON. The loader reuses `datapack.py` helpers: floats and
  duplicate keys are rejected, unknown keys are rejected, all numbers are
  integers or `[num, den]` pairs. It opens a file only when called;
  importing `h3re.town` opens nothing.
- `create_game(game_id, content, players, towns, policy=DEFAULT_POLICY)`.
  `players` is one `adventure.Resources` treasury per player (non-negative).
  `towns` is `TownSetup(id, faction, owner, built=())`; `built` must be
  prerequisite-closed, and a player may not start with two buildings of the
  same `player_unique` tag. The state starts on day 1.
- `apply(state, cmd, rng) -> (state', events)`. Commands:
  `Build(player, town, building)` and `NewDay()`.
- `rng`: nothing here is random. `apply` accepts the stream `town:<game_id>`
  (`town_rng(master_seed, game_id)`) only to keep the interface stable and
  never draws from it. The tests pass an object that fails if touched.
- Events: `BuildingBuilt(town, building, player, cost, treasury)` (treasury
  after paying) and `TownDayStarted(day)`.
- Queries: `missing_requirements`, `active_buildings`, `town_income`,
  `player_income`, `dwellings`, `growth_pools(state, town, current=())`,
  `weekly_growth(base, bonus, horde, policy)`, `find_building`.
- State is immutable: frozen dataclasses of tuples, ints, strings and bools;
  `canonical(state)` / `state_hash(state)` follow ADR-0001 exactly. The
  policy **and the content** are part of the state, so a different pack or
  policy gives a different hash at step 0. The module reads no `rules.json`
  value, so it carries no `rules_hash`.

## 2. Content model (pack schema v1)

`{"schema_version": 1, "factions": [{"id", "buildings": [...]}]}`. A building:

| Key | Meaning |
|---|---|
| `id`, `cost`, `requires` | required. `cost` is an object of the 7 resources (missing = 0). `requires` lists building ids of the same faction. |
| `upgrades` | the building this one replaces. It must also be in `requires`. A building is upgraded by at most one other (chains, no branches). |
| `income` | daily resources while the building is active |
| `fort` | counts as a fort for the dwelling rule |
| `growth_bonus` | `[num, den]`, castle bonus as a fraction of base growth |
| `dwelling` | `{level, creature, base_growth}` |
| `horde` | `{level, bonus}`: a fixed `+bonus` to that dwelling level |
| `player_unique` | tag; a player may own only one building with it |

Loader checks: unknown references, requirement cycles, every dwelling
transitively requires a `fort` building ("Creature dwellings need a Fort",
`rules.md` §4 [documented]), a dwelling upgrades only a dwelling of the same
level and only a dwelling upgrades a dwelling, exactly one base dwelling per
level, a horde's level has a dwelling. Factions and buildings are stored
sorted by id and `requires` is sorted, so file order does not reach the
state or the hash (tested).

**Active buildings** = built buildings that no built building upgrades. Income,
dwellings, castle bonus and hordes use active buildings only. Because an
upgrader requires its target and chains do not branch, at most one dwelling
per level is active. [engine]

## 3. Building

`Build(player, town, building)` is legal when, checked in this order (the
first failure is the error): the player exists; the town exists; the player
owns it; the building exists in the town's faction; it is not built; the town
has not built today; every `requires` entry is built; no other town of that
player holds a building with the same `player_unique` tag; the treasury
covers the cost in every resource. Then the cost is paid and the building is
added (the `built` tuple stays sorted).

- Buildings have costs and prerequisites, which are data. [engine, `rules.md` §4]
- At most one building per town per day. [documented, `rules.md` §1] The
  limit is per town, not per player (tested). `NewDay()` clears it.
- "A player may own only one Capitol" [documented, `rules.md` §3] is the
  generic `player_unique` tag (`"capital"` in the test pack).
- Fort → Citadel → Castle is data: an upgrade chain of `fort` buildings with
  `growth_bonus` 1/2 and 1/1 in the test pack.

## 4. Weekly growth

Per active dwelling level L (`rules.md` §4 [documented]):

```
bonus  = max growth_bonus over active buildings (0 if none)   # not cumulative
growth = base_growth + round(base_growth * bonus) + Σ horde_bonus(level L)
```

- `round` is `_round_castle_bonus`, the single rounding step, with mode
  `policy.citadel_rounding` (exact Fraction product, no floats).
- Castle bonuses do not stack: the largest active one applies. The data's
  upgrade chain already deactivates the Citadel when the Castle is built;
  the max makes the rule hold for any data. [documented: "not cumulative"]
- Hordes add a fixed number after the castle bonus and are not scaled by it.
  [documented formula shape]
- `growth_pools(state, town, current=())` returns one
  `adventure.GrowthPool(id, available, growth)` per active dwelling level,
  ascending by level, with `id = "<town>:dwelling<L>"`. `available` is taken
  from the pool with the same id in `current` (0 if none); the town core does
  not own creature counts. A horde with no dwelling of its level adds no pool.
- An integration test feeds the pools to `adventure.create_game` and checks
  that day 8 grows them by exactly these numbers.

## 5. Economy and integration

- `town_income(state, town)` sums `income` of active buildings, so Town Hall
  replaces Village Hall. `player_income(state, player)` sums the player's
  towns. These are meant for `adventure.Player.extra_income`. [engine]
- The town core does not pay income into its treasury (that would double
  count with the adventure core). Syncing the two treasuries and calendars is
  the job of a future game layer. [engine]
- Hall income values (500/1000/2000/4000) are [documented] but are content;
  the test pack uses them only as synthetic numbers.

## 6. Policy fields (`TownPolicy`)

| Field | Default | Alternatives | Question |
|---|---|---|---|
| `citadel_rounding` | `"floor"` | `"ceil"`, `"nearest"` (halves up) | Rounding of `base * castle_bonus` for an odd base (`rules.md` §9.10) |

Default source: VCMI cross-check (`vcmi-crosscheck-rules.md` §2, "Citadel
rounding (§9.10)", **clear**: base ÷ 2 rounded down). Under `rules.md` §0 a
clear note on an [uncertain] item may be the default; §9.10 still decides.
Example, base 13 with a Citadel: floor 19, ceil 20, nearest 20.

## 7. Golden hash

`tests/test_town.py` `GoldenTest.PINNED =
0360ce8861ca3b4a12f8210f0d8111b57c328becb8c433d41c59d6a6d257aae7`
(first pin; not a re-pin). Derivation:

1. Content: `data/towns_test.json` (content hash prefix `629836f9f419a851`,
   pinned separately so a pack edit is reported as such).
2. `create_game("golden", content, players, towns, DEFAULT_POLICY)` with
   players `Resources(gold=30000, wood=60, ore=60, mercury=4, gems=2)` and
   `Resources(gold=25000, wood=20, ore=50, mercury=2, sulfur=5)`; towns
   `north` (fernwood, player 0, `hall.1`), `south` (saltmarsh, player 1,
   `hall.1`), `east` (fernwood, player 1, `hall.1`, `keep.1`).
3. Seven days; each day the listed builds in order, then `NewDay()`:
   1. north keep.1, south wall.1, east den.1
   2. north den.1, south pool.1, east nest.2
   3. north market, south hall.2, east hive
   4. north keep.2, south reef.2, east market
   5. north hive, south wall.2
   6. north nest.2, east den.1u
   7. north hall.2
4. `state_hash` of the resulting day-8 state. The test also asserts both
   treasuries and the pools (north 23/10, south 13/9, east 17/7).

Changing the policy (`citadel_rounding="ceil"`) or one content number moves
the hash (tested). The hash is the same under `PYTHONHASHSEED` 0, 1, 12345
and random (checked when pinning). A later change to this hash follows the
ADR-0001 re-pin rule with its reason recorded here.

## 8. Unverified assumptions (no switch)

- The order of validation checks (only the error message depends on it).
- One build per town per day, not per player.
- Hordes are not scaled by the castle bonus (formula in `rules.md` §4).
- An upgraded dwelling uses its own `base_growth` and shares the level's pool.
- Prerequisite graphs are our own data [engine]; the test pack's graph is
  invented.
- Not modelled: external dwellings (VCMI clear: +1 per owned map dwelling in
  each town), week of creature / month of plague, Grail, neutral-town half
  growth, recruitment.
