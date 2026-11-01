# Conformance vectors (Python -> Kotlin)

Python (`tools/h3re`) is authoritative (ADR-0004). The Kotlin engine (`android/sim`,
package `h3.sim`) is correct only when it reproduces every vector below byte for byte.
A rule or format change lands in Python first, then the vectors are regenerated in the same
change, then Kotlin follows. Vectors never contain timestamps and are never hand-edited.

## Generating and checking

- Generate: `cd tools/h3re && python3 -m h3re.vectors [--out DIR]`
  (default `android/sim/src/test/resources/vectors/`).
- Check without writing: `python3 -m h3re.vectors --check` (exit 1 if stale).
- `tools/h3re/tests/test_vectors.py` asserts the generator is deterministic and that the
  committed files equal a fresh generation, so Python drift fails the Python suite until the
  vectors are regenerated and reviewed.
- Kotlin: `cd android && gradle :sim:test` (the `:app` module is only included with
  `-PwithApp=true`, because the Android Gradle plugin needs the Google Maven repository).

## File format

Each file is `json.dumps(obj, sort_keys=True, separators=(",", ":"))` plus one LF, pure
ASCII (non-ASCII escaped), top-level `"format": 1`. Integers may exceed 2^53 and 2^64; readers
must parse them exactly (the Kotlin test reader uses `BigInteger`). Booleans are JSON booleans.

### `rng.json`
- `published`: `{seed, seq, u32[6]}`, the published PCG32 check vector (seed 42, seq 54).
- `pcg32_u32`: cases `{seed, seq, state, inc, u32[1000]}`; `state`/`inc` are the generator
  after seeding, before the first draw.
- `pcg32_ops`: cases `{seed, seq, ops, out}`. `ops` entries are `["u32"]`,
  `["range", lo, hi]` (half-open), `["randint", lo, hi]` (inclusive), `["chance", num, den]`;
  `out` holds the results in order (ints, or booleans for `chance`). 1000 ops per case, including
  spans of 1 and 2^32, negative bounds, and `chance` with num <= 0 and num >= den (no draw).
- `derived`: cases `{master, domain, id, state, inc, ops, out}` for `derive_stream(master,
  domain, id)`: negative and > 64-bit master seeds (byte length `max(8, (bit_length(|x|)+8)//8)`,
  little-endian two's complement), empty domain/id, non-ASCII and astral text, NUL, long
  strings, and field-boundary cases (`"a","bc"` vs `"ab","c"`).

### `canonical_json.json`
Cases `{name, value, hex, sha256}`: `hex` is the canonical encoding of `value` (ADR-0001), and
`sha256` its digest. Rules the Kotlin encoder must match:
- keys sorted by Unicode **code point** (not UTF-16 unit: U+1F600 sorts after U+FFFF);
- compact separators, no whitespace;
- `ensure_ascii=True`: everything outside 0x20..0x7E is escaped, including DEL (`\u007f`);
  escapes are `\" \\ \n \r \t \b \f`, other controls and non-ASCII as lowercase `\uXXXX`
  (astral characters as UTF-16 surrogate pairs);
- ints (arbitrary size), strings, lists, string-keyed maps, booleans, null. No floats; other
  types are rejected.

### `state_hash.json`
Cases `{name, canonical, sha256}` built through the public battle API (golden scenario of
`tests/test_battle.py`, state before and after `Begin` with `battle_rng(12345, "golden")`).
`canonical` is the `battle.canonical` text. Kotlin currently parses it and checks that
re-encoding is identical and the SHA-256 matches; once `h3.sim` has a battle state, tests will
build the state natively, compare, and add per-step hashes from replays (follow-up).
`golden_setup()` in `vectors.py` mirrors the test's by hand; these vectors move with the
battle rules (including re-pins per ADR-0001) and must be regenerated with them.

## Python/Kotlin differences resolved
- Unsigned 64-bit arithmetic uses `ULong`; outputs and bounds are `Long` (u32 fits).
- Python `str` ordering is by code point; Kotlin `String` by UTF-16 unit. The encoder sorts by
  code point explicitly.
- Java `BigInteger.bitLength()` differs from Python for negatives; the seed byte length uses
  `abs().bitLength()`, matching Python's `bit_length()`.
- Lone surrogates cannot be UTF-8 encoded in Python and are excluded from vectors.

## Rules: battle damage (`rules.json`)

Source: `tools/h3re/h3re/rules.py` (rules.md 6.5-6.6), exported by `vectors.py` `_rules_vectors()`.
Kotlin: `Rules.kt` (formulas, with `RulesPack` supplied by the caller from `data/rules.json`),
`Rational.kt` (exact type, ADR-0009), `RulesTest.kt` (vectors plus `RationalTest`).

Encoding:
- Exact values are `[numerator, denominator]` pairs, reduced, denominator > 0 (Python
  `Fraction.numerator` and `.denominator`). Plain integers are plain JSON integers.
- `pack`: the constants as `rules.py` loaded them from `data/rules.json`. Kotlin takes them
  as a `RulesPack`; it has no balance numbers of its own (ADR-0004).
- `ctx` is `dataclasses.asdict(DamageCtx)`: `count, dmg_min, dmg_max, attack, defense, ranged,
  offense, archery, armorer, hates, range_penalty, melee_penalty, wall_penalty, luck, bad_luck`.
  Flag and parameter names in other sections use the same Python keyword names.

Sections (`format` 1):
- `attack_defense`: `{attack, defense, inc, red}`, every difference -255..255 at base 0, and -100..100 at base 100.
- `base_damage`: `{count, dmg_min, dmg_max, rolls, out}`. `rolls` are the scripted `randint`
  results in call order (`min(count, 10)` of them, none for `count <= 0`). `error: true` marks
  a `ValueError` case; the Kotlin test fails if the rolls are not all consumed.
- `damage_from_base`: `{base, attack, defense, ranged, offense, archery, armorer, lucky, hates,
  range_penalty, wall_penalty, melee_penalty, out | error}`.
- `resolve`: `{ctx, policy, damage, lucky, unlucky | error}` with `policy` one of `PESSIMAL`,
  `EXPECTED`, `OPTIMAL` (the Kotlin `RollPolicy` names).
- `resolve_seeded`: `{ctx, seed, seq, damage, lucky, unlucky, state_after | error}`. The strike
  is `ACTUAL_SEED` with `Pcg32(seed, seq)`. `state_after` is the generator state (u64) after the
  strike: it pins the number and order of draws, not just the damage.
- `preview`: `{ctx, floor, expected, ceiling}`.
- `luck_chance` `{luck, out}`, `good_morale_chance` `{morale, out}`, `bad_morale_chance`
  `{morale, table, out | error}` (both default tables, the VCMI table, custom tables, invalid tables).
- `penalties`: `{base, ranged, range_penalty, wall_penalty, melee_penalty, out}`, the range,
  wall and melee factors (each 1/2) applied on their own and together, through `damage_from_base`.

Rules the Kotlin side must match (these are where a port silently drifts):
- Rationals are always reduced. `resolve_damage` passes the reduced pair to `rng.chance`, so
  luck 2 (`2/24`) draws from `chance(1, 12)`, not `chance(2, 24)`.
- One floor per pipeline (`Rational.floor()`, Python `math.floor`). Integer `//` on ints
  (`Math.floorDiv`) is separate and used only where Python uses it (`(total * count) // 10`, `dmg // 2`).
- `base_damage` and `resolve_damage` return for `count <= 0` before the range check. `resolve_damage`
  draws the luck roll before that return, so a zero-count strike still advances the generator.
- `damage_from_base` returns 0 for `base <= 0` before the flag checks.
- `EXPECTED` folds bad luck in as `1 - P(bad) * half` before the single floor. It reports
  `lucky` and `unlucky` as false.
- Python `ValueError` maps to Kotlin `IllegalArgumentException` (`require`). Kotlin arithmetic
  overflow throws `ArithmeticException`; it never wraps, so an out-of-range case fails loudly.

Not in this set: `apply_damage` (rules.md 6.6 step 4) and `damage_range` (a thin wrapper over
`preview_damage`) are not ported yet.

Regenerate and check with the commands at the top of this file. Python is authoritative: a
change to any of these values is a `rules.py` change first (spec, re-pin per ADR-0001 if a
pinned hash moves), then a regeneration.

## Hex: battle grid geometry and movement (`hex.json`)

Source: `tools/h3re/h3re/battle.py` (battle.md sections 2-3: `in_grid`, `to_axial`, `from_axial`,
`neighbours`, `hex_distance`, `_cells_at`/`_tail`, `_playable`, `_fits`, `_reach`, `reachable`,
`_adjacent_cells`), exported by `vectors.py` `_hex_vectors()`. Kotlin: `Hex.kt` (`object Hex`,
`HexCell`), `HexTest.kt`. Hexes are `[col, row]` pairs; cell index is `row * 17 + col`. Booleans
that Python used as dict keys appear as `"True"`/`"False"`. The generator is seeded through
`derive_stream(0x5EED, "vectors:hex", ...)` (Pcg32), never Python's `random`.

Sections (`format` 1):
- `width`, `height`: 17, 11.
- `neighbours`: `{row_offset, hex, out}` for every cell, both `"even"` and `"odd"`; `out` is the
  sorted in-grid neighbour list (column, then row).
- `axial`: `{row_offset, hex, q, r}`; `from_axial`: `{row_offset, q, r, out}` over r in -3..13 and
  q in -12..19 (includes negative rows, where floor division matters); `in_grid`: `{hex, out}`
  including out-of-grid points.
- `distance`: `{even: [...], odd: [...]}`, each the flat row-major matrix of `hex_distance` over all
  187 x 187 ordered pairs (`out[a_index * 187 + b_index]`).
- `cells`: `{side, head, double_wide, cells, fits_empty}`: footprint (head then tail; tail is
  `col-1` for side 0, `col+1` for side 1) and, per `edge_columns_walkable`, whether every cell is
  playable on an empty board (heads at -1 and 17 included).
- `adjacent`: `{row_offset, a, b, out}` for `_adjacent_cells` over one- and two-cell lists.
- `reach`: scenarios `{row_offset, edge_columns_walkable, side, double_wide, flyer, speed, pos,
  obstacles, others, reachable, paths}`. `others` are `{side, head, double_wide, alive}`; occupancy
  is the union of the cells of the living ones (dead stacks never block). `reachable` is the sorted
  head list; `paths[i]` is the path to `reachable[i]` (start excluded, destination last). Speeds
  include 0 and values beyond the grid; the mover's own start cell is never validated.

Rules the Kotlin side must match:
- Row parity: any `row_offset` other than `"odd"` behaves as `"even"` (Python's `if == "odd"`).
- Axial conversion uses floor division on `r +/- (r & 1)`; Kotlin uses `Math.floorDiv`.
- Walking is breadth-first with neighbours visited in sorted order; the first discovery of a cell
  fixes its parent, so path tie-breaking falls out of that order and must not be changed.
  The search stops expanding at distance `speed`.
- Flyers: path is just `[dest]`; any in-range head (distance <= speed, not the start) whose cells
  all fit; obstacles and units in between are ignored.
- A head fits only if every footprint cell is in the grid, in columns 1..15 (unless the edge flag),
  not an obstacle and not occupied.

Not portable bit-for-bit: Python's dict order of `_reach` results is exposed in Kotlin as a
`LinkedHashMap` in the same order, but only the sorted `reachable` list is in the vectors.

## Battle state (`battle_states.json`)

Source: `tools/h3re/h3re/vectors_battle.py` `generate()` (`python3 -m h3re.vectors_battle [--out DIR]`
writes the file; the `vectors.py` generator may call `generate()` too). Kotlin: `BattleState.kt`
(typed model, `BattleCodec`, `BattlePolicyPack`), `BattleStateTest.kt`. No apply logic yet: this
slice pins the state model and its canonical encoding only.

Content (`format` 1):
- `packs`: `battle_policy` (the parsed `data/battle_policy.json`), `bad_morale_numerators` (the rules
  pack default of the policy's `bad_morale_table`, which is not in the policy file) and `rules_hash`.
  Kotlin builds its policy defaults from these; `BattlePolicy` has no hard-coded balance numbers.
- `schema`: dataclass field names (declaration order) of `BattleState`, `BattlePolicy`, `Stack`,
  `Creature`, `Hero` and every command and event class. The Kotlin test checks that the typed
  classes have exactly these properties (snake_case to camelCase) and that their maps carry
  exactly these keys.
- `command_cases`, `event_cases`: static encodings of every command (both `Attack` forms) and event.
  Commands and events are `soak.encode_command` dicts: `{"type": ClassName, <fields>}`, tuples as lists,
  `None` as null.
- `cases` (14): the golden scenario (seed 12345) plus soak scenarios `soak.build_scenario("battle", seed, policy)`
  under `default` (seeds 0, 1, 4, 6) and the non-default `alt-order`, `vcmi-like`, `strict` policies
  (seeds 0, 1, 6): one- and two-hex units, shooters, flyers, obstacles, heroes. Each case:
  `scenario` (seed, policy name and kwargs, battle id), `initial` `{canonical, sha256}` (before `Begin`)
  and `steps` (up to 120, 586 in all) of `{command, canonical, sha256, events}` after each command.
  The driver is the greedy AI, except that a `derive_stream` draw substitutes a legal `Wait` or
  `Defend` 40% of the time, so all six commands and all twelve events occur. Randomness is `Pcg32` only.

Rules the Kotlin side matches:
- `canonical` is the exact text of `battle.canonical`. Kotlin parses it into the typed model, re-encodes
  with `Canonical.encode` and requires byte-identical text and the same SHA-256. Parsing is strict:
  missing or unknown keys, and wrong JSON types, are errors (no silent defaults).
- Omit-at-default (ADR-0005): `BattleCodec(pack, omitWhenDefault)` mirrors `_OMIT_WHEN_DEFAULT` (policy
  field names; empty today). A listed field is left out while equal to the pack default and is restored
  from the default on parse. The vectors cannot exercise it while the Python list is empty, so
  `BattleStateTest.omitWhenDefaultMechanism` covers it synthetically. When Python lists a field, the
  Kotlin codec must be constructed with the same list.
- Tuples and lists are both JSON arrays; `None` is null (`active`, `winner`, `last_side`, `Attack.from_hex`,
  and `None` hero entries).
- Integers are 32-bit `Int` (ADR-0008) and parsing fails on values outside the range. `rules_hash` is a
  required field in Kotlin (the Python default is the local rules pack's content hash).
- Kotlin class names: `BattleCreature`, `BattleHero`, `BattleStack` (to stay clear of future adventure
  types), commands and events nested in `BattleCommand` / `BattleEvent`. Positions are `Pair<Int, Int>`
  (col, row); hex geometry lives elsewhere.
