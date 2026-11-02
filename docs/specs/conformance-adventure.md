# Conformance: adventure core (Kotlin port)

Scope: `android/sim/src/main/kotlin/h3/sim/Adventure.kt` versus `tools/h3re/h3re/adventure.py`
(docs/specs/adventure.md). Python is authoritative (ADR-0004); the vectors are the contract
(ADR-0007). Generator: `tools/h3re/h3re/vectors_adventure.py` (`generate()`), file
`android/sim/src/test/resources/vectors/adventure.json`. Never edited by hand.

## What is ported

- Typed immutable state (`AdventureState`, `AdventurePolicy`, grid, players, heroes, pools,
  guards) and its canonical form, byte-identical to `adventure.canonical`: `guards` and `battles`
  are left out at their defaults (ADR-0005), so the pinned 14-day golden hash holds.
  A state carrying `encounter`, and the `Attack` command, are handled through `AdventureEncounterHooks` (see `conformance-encounter.md`); without hooks, a state with `encounter` is refused.
- Commands `Begin`, `Move`, `EndTurn`, `Attack` (needs hooks); events `DayStarted`, `WeekStarted`, `PoolGrew`,
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

- `cases`: 7 golden 14-day scripted runs (the `tests/test_adventure.py` driver; the default one
  ends on the pinned hash `179c5700...`) under default, alt-order, vcmi-like, strict,
  no-corner-cut and pf-percent-floor, plus `golden-guards-nonbmp` (default policy, six guards whose
  ids are `Z`, U+00E9, U+FB01, U+FFFF, U+10000 and U+1F600: code-point order differs from UTF-16
  order, and the canonical state carries them as `\ud83d\ude00`-style escapes); 22 soak scenarios (`soak.build_adventure` and its driver,
  50 commands each) under the four `soak.POLICY_MATRIX` policies and twelve extra policies
  (road rate from dest, one-tile roads, custom road costs, ratio diagonals floor and nearest,
  no corner cut, `allow_if_fresh`, `allow_if_any`, percent Pathfinding floor and ceil, custom flat
  Pathfinding with a raised floor, income on day 1 with destination pricing).
- Per step: command, stage (`B` Move, `C` Begin/EndTurn), canonical text, SHA-256, events, and
  before a Move the SHA-256 and size of the moving hero's whole reachable map
  (`[[x, y], cost, path]` sorted by tile).
- `illegal_cases`: rejected commands on states at several points of every case, with the message.
  Three cases (`golden`, `golden-strict`, `soak-default-0`) also carry repr probes: an `EndTurn`
  with a wrong `player` and a `Move` with a malformed `dest` for each value of
  `vectors_adventure.REPR_PROBES`, so the message embeds Python's `repr` (see below).
- `policy_cases`: 35 policies (JSON) with the `ValueError` message Python raises or `null` when it
  is accepted: values at the 10^4 bound, over it, huge (10^8, 2^31, 2^70), bool, null and string
  fields, and pairs of faults that pin the check order.
- The `adventure:<game_id>` stream is never drawn from; its final state is recorded per case.

## Python `repr` in messages

`not player %r's turn` and `not a tile: %r` embed `repr` of the decoded JSON value (a top-level
list is a tuple). `AdventureCodec.pyRepr` ports it: `None`/`True`/`False`, integers, lists,
dicts (`{'k': v}` in the map's order; the vector file stores object keys sorted, and the probes
are built with sorted keys so Python's insertion order is the same), and str with Python's rules:
quote choice (`'`, or `"` when the text has a `'` and no `"`), escapes `\\ \' \t \n \r`, `\xNN`
for C0 controls, DEL and the non-printable code points up to U+00FF, `\uNNNN` and `\UNNNNNNNN`
above, and a lone surrogate as `\ud800`. Printable is `str.isprintable` (categories Cc, Cf, Cs,
Co, Cn, Zl, Zp, Zs other than the ASCII space are not). Compared over all code points above U+007F
with Python 3.13 (Unicode 15.1) on JDK 21 (Unicode 15.0): equal after adding the three 15.1
ranges the JDK lacks (U+2FFC..U+2FFF, U+31EF, U+2EBF0..U+2EE5D). Not ported: `repr` of a float
(the vector reader refuses floats; a Kotlin `Double` prints with `toString`).

## Policy bounds and guard order

Policy integers must be plain ints within the bounds of adventure.md section 6 (amendment);
`policy_cases` pins verdict, message and check order. Guards are sorted by id in code-point
order (`Canonical.codePointOrder`, as Python `sort` and `json.dumps(sort_keys=True)`), not by
UTF-16 code unit; `golden-guards-nonbmp` pins it. Unbudgeted path costs are `Long` in Kotlin.

## Kotlin test (`AdventureTest`)

Stage A codec round trip and hash of every recorded state; B and C replay each step from the
previous recorded state and compare canonical text, hash, events, reachable-map digest and the
stream; D checks message, untouched state and untouched stream; plus a whole-case replay from the
initial state, the golden pin, strict-integer commands, policy/state refusals, guards, every
`policy_cases` entry, non-integer policy fields (`Double`, `Boolean`), the 24-step 2.4 x 10^9
`findPath` cost, and `pyRepr` unit cases.
