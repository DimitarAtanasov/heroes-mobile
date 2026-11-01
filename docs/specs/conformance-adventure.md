# Conformance: adventure core (Kotlin port)

Scope: `android/sim/src/main/kotlin/h3/sim/Adventure.kt` versus `tools/h3re/h3re/adventure.py`
(docs/specs/adventure.md). Python is authoritative (ADR-0004); the vectors are the contract
(ADR-0007). Generator: `tools/h3re/h3re/vectors_adventure.py` (`generate()`), file
`android/sim/src/test/resources/vectors/adventure.json`. Never edited by hand.

## What is ported

- Typed immutable state (`AdventureState`, `AdventurePolicy`, grid, players, heroes, pools,
  guards) and its canonical form, byte-identical to `adventure.canonical`: `guards` and `battles`
  are left out at their defaults (ADR-0005), so the pinned 14-day golden hash holds.
  A state carrying `encounter` is refused: encounters and `Attack` are not ported yet.
- Commands `Begin`, `Move`, `EndTurn`; events `DayStarted`, `WeekStarted`, `PoolGrew`,
  `TurnStarted`, `IncomeReceived`, `MovementReset`, `HeroMoved`, `TurnEnded`.
- `apply(state, cmd, rng)`: validation in Python's order with Python's messages; Dijkstra with the
  `(spent, steps, path)` label tie-break; last-step, diagonal-exception and zero-remainder rules;
  roads, Pathfinding (flat and percent), diagonals (exact `floor(c * sqrt 2)` through integer
  square root, or a ratio with the named rounding); the day and week tick, income and growth.
- Policy validation (`__post_init__`, same order and messages). Integer only, `Math.*Exact`.
- The content-free tables (terrain costs, roads, speed to movement points, Logistics, mine
  output) are not in Kotlin code: `AdventureRules` takes them from the vector's `constants`
  block, which the generator copies from `adventure.py` (in Python they are migration debt).

## Command fields are strict integers

Python's `_validate` rejects a `bool` (and anything not `int`) for `hero`, `player` and the dest
coordinates. Kotlin `AdventureCodec.parseCommand` keeps an ill-typed field as `null` with its
Python `repr`, and `Adventure` rejects it at the same point with the same message, for example
`no such hero`, `not player True's turn`, `not a tile: (0, True)`. An integer beyond the Int range
is an unknown hero or player or an off-map tile, as in Python. The test-vector JSON reader refuses
floats, so the float case is a Kotlin unit test (a `Double` field is rejected like a `bool`).
An unknown command type or a missing field is an `IllegalArgumentException` (Python raises
`AttributeError`/`TypeError` there, not `IllegalCommand`); no vector covers those.

## Vector contents

- `cases`: 6 golden 14-day scripted runs (the `tests/test_adventure.py` driver; the default one
  ends on the pinned hash `179c5700...`) under default, alt-order, vcmi-like, strict,
  no-corner-cut and pf-percent-floor; 22 soak scenarios (`soak.build_adventure` and its driver,
  50 commands each) under the four `soak.POLICY_MATRIX` policies and twelve extra policies
  (road rate from dest, one-tile roads, custom road costs, ratio diagonals floor and nearest,
  no corner cut, `allow_if_fresh`, `allow_if_any`, percent Pathfinding floor and ceil, custom flat
  Pathfinding with a raised floor, income on day 1 with destination pricing).
- Per step: command, stage (`B` Move, `C` Begin/EndTurn), canonical text, SHA-256, events, and
  before a Move the SHA-256 and size of the moving hero's whole reachable map
  (`[[x, y], cost, path]` sorted by tile).
- `illegal_cases`: rejected commands on states at several points of every case, with the message.
- The `adventure:<game_id>` stream is never drawn from; its final state is recorded per case.

## Kotlin test (`AdventureTest`)

Stage A codec round trip and hash of every recorded state; B and C replay each step from the
previous recorded state and compare canonical text, hash, events, reachable-map digest and the
stream; D checks message, untouched state and untouched stream; plus a whole-case replay from the
initial state, the golden pin, strict-integer commands, policy/state refusals and guards.
