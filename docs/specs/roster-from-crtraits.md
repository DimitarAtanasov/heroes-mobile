# Battle roster from the player's CRTRAITS.TXT

## 1. Status

Approved for slice 4 (owner, 2026-11-03). Direction approved by the owner (two decisions,
section 3); Q1, Q2, Q5, Q7 and Q8 are answered (section 6). Slices 1 to 3 are done. Slice 4 wires
the app (section 7). No slice changes a golden hash. Section 2 records the state before slice 1.

## 2. Current state

- The roster source is `data/creatures.json`: four fixture creatures "Test Pikeman", "Test
  Slinger", "Test Glider", "Test Brute". `MainActivity.kt:65` reads it from assets and passes it to
  `AppEngine.fromTexts` (`Engine.kt:29`); `Engine.kt:26` exposes `packs.creatures.creatures` as
  `roster`, used for the UI names (`MainActivity.kt:57`) and for preset scenarios (`:223`).
- `BattleCreature` (`android/sim/src/main/kotlin/h3/sim/BattleState.kt:22`) has no row or index
  field. The creature is identified by `name` everywhere in state and in `hates`.
- `Content.parseCreatures` (`android/sim/src/main/kotlin/h3/sim/Content.kt:188`) parses a
  CRTRAITS-style table with the mapping `data/txt_maps/crtraits.json` (spec `content.md`). The
  1-based file row `r` (`:218`) is used only for error text (`ContentError`, `:228-:289`) and the
  `rowNo` duplicate check (`:231`). The result is `records.sortedBy { it.name }` (`:323`), so the
  file order is lost.
- `tools/h3re/h3re/content.py` mirrors it: `parse_creatures` (`:79`), row `r` at `:97`, result
  sorted by name via `datapack._check_creatures` (`:150`, docstring `:30`). `content.md:51` states
  the by-name order.
- Datapack: `DataPack` (`tools/h3re/h3re/datapack.py:232`) and the Kotlin `Datapack.kt:48` sort
  creatures by name; `content_hash` is SHA-256 of the canonical JSON and is independent of
  creature order (`datapack.md:58-60`). Only `rules.json` is covered by `BattleState.rules_hash`
  (`battle.py:296`, `battle.md` section 10, `battle.py:965` PackMismatch).
- Golden pins: adventure `179c5700` (`AdventureTest.kt:133`, `test_adventure.py`), encounter
  `512b53ca` (`EncounterConformanceTest.kt:269`), battle `fbe9015b` (`BattleTest.kt:159`,
  `ReplayTest.kt:67`), hero `f18f5ebb` (`HeroConformanceTest.kt:290`), town `0360ce88`
  (`TownTest.kt:72`, `TownConformanceTest.kt:372`). Their Python twins are named in ADR-0005.
  The battle golden builds its creatures inline (`test_battle.py:432` `golden_setup`: pikeman,
  archer, wolf, gnoll); none of the five reads `data/creatures.json`.

## 3. Proposed design

Owner decisions (not re-opened): (1) the battle roster comes from the player's own CRTRAITS.TXT,
replacing the four "Test ..." creatures as the battle roster source; (2) the sprite table key is
the data-row index.

**Data-row index.** Definition: the 0-based position of a creature among the creature records,
counted in file order after the header rows; blank rows and rows with an empty first cell (skipped
by the source, `Content.kt:219-220`) do not count. This differs from the file row `r`, which stays
the error-message number. Both loaders add an `index` to each accepted record, identically:
`Creature.index` in Kotlin, a key in the content record in Python. `index` is loader output, not a
datapack field: it is not in `creatures.json`, not in `content_hash`, not in battle state, so the
canonical state form and every state hash are untouched.

**Order.** Rule: the roster is ordered by ascending data-row index (file order). It is a total
order, free of locale and of name comparison, and equal to the sprite key. The by-name sort is kept
only inside `DataPack`/`content_hash` canonicalization, where order must not matter. The loader
returns records in file order and the datapack sorts its own copy; the roster builder takes the
loader order. `ContentResult.creatures` order changes from by-name to file order in both languages
(update `content.md:51`).

**Roster build.** The app builds the roster from the loaded `ContentResult` of the user's file:
`BattleCreature` from each record, in index order, with the index kept beside it (a roster entry
type holding `(index, BattleCreature)`; `BattleCreature` itself is not widened, to keep
`creatureToMap` and the canonical form unchanged). The battle identity stays the `singular`
column; names are unique (the loader already refuses duplicates, `Content.kt:231`).

**Test fixture.** `data/creatures.json` stays in the repo as a test fixture only (datapack
conformance, preset tests). The app no longer reads it as the battle roster. Without a CRTRAITS
imported there is no roster: Home shows only the import prompt, not the fixture (Q2, owner
decision 2026-11-03; ADR-0011 D3 amended). `data/creatures.json` is still bundled as a fixture
pack, because replay headers record and check its pack hash (Q8, below).

**Presets name rows (Q7, owner decision 2026-11-03).** A built-in preset (`Presets.kt`) refers to
its creatures by data-row index (zero-based, the same index as the sprite key), never by name. The
default presets use rows 0, 2 and 4, the placeholder creatures of the VCMI-derived sprite table
(ADR-0014); the owner confirms this default. The scenario JSON is built from the roster entries of
those rows, so the battle names are the player's own `singular` cells.

**Preset row not in the roster.** A preset whose row is absent from the roster (past the end of the
file, or a no-fixed-damage creature left out under Q5) is not started: it is shown disabled with
the reason "Needs creature row N, not in your game's creatures" (`PresetCheck`, `MenuText`), and
nothing is substituted. A preset whose row has hp 0 is also disabled with a reason, because battle
creation refuses hp 0 (Q5). No fallback to "Test ..." names.

**Replays keep the fixture pack hash (Q8, owner decision 2026-11-03).** The app still loads the
three bundled packs, `creatures.json` included, and the replay header's `creatures_hash` stays the
hash of that fixture pack (`replay.md` section 2). The player's roster does not enter any pack
hash: each scenario carries its own creature table, so a replay needs no game data. Saves written
before slice 4 therefore still verify and load.

**Invalid row.** Pick: refuse the whole import (Q1, confirmed by the owner 2026-11-03). Reasons: (a) the data-row index is positional, so
skipping a bad row would silently shift every later sprite key and the player would see wrong
sprites with no error; (b) law 10: the loader spec already makes a row error fatal with row,
column and category (`content.md`), and a partial roster would be a second, unspecified
behaviour; (c) `hates` and presets name creatures, so a dropped row breaks references silently.
The error shown is the existing `ContentError` text (row, column, category), never file contents.
Confirmed by the owner (Q1).

**Zero damage (owner decision, 2026-11-02).** Keep every row the loader accepts. The
data-row index counts every accepted record, including zero-damage ones, so later creatures keep
their sprite index. Owner's meaning of the two damage cells:
- A: `dmg_min` 0, `dmg_max` > 0: a weak unit dealing 0..`dmg_max`. Loads normally.
- B: `dmg_min` >= 1, `dmg_max` 0: no upper limit. The loader still refuses it (`dmg_min >
  dmg_max`); how to represent an unbounded maximum within ADR-0008's 32-bit pack values is an
  open owner question (Q4). No numeric cap is invented and 0 is not stored as a real maximum.
- C: `dmg_min` 0, `dmg_max` 0: no fixed damage; the attack comes from an ability. Loads, and the
  name is listed in the side set `ContentResult.no_fixed_damage` / `noFixedDamage` (not in the
  record, `toMap`, `content_hash` or battle state). It is not "non-combat".
Battle creation requires `0 <= dmg_min <= dmg_max` with `dmg_max >= 1` (battle.md section 10): it accepts A
and refuses C with "invalid damage range" (Python `battle.py:473` `create_battle`, `:498` `_CREATURE_INTS` via
`check_state`, `rules.py:96` `base_damage`, `:227` `resolve_damage`; Kotlin `Scenario.kt:280`,
`BattleState.kt:457`, `Rules.kt:101`, `Rules.kt:142`). Q5 answered (owner, 2026-11-02, slice 3):
the battle roster leaves C out (`Content.battleRoster`, `roster.battle_roster`) and offers A. A
creature with hp 0 is offered too; battle creation refuses it, so a preset that uses one is
disabled with a reason (slice 4).

## 4. Hash impact

Goldens that change: none. Reason: the five pins (adventure `179c5700`, encounter `512b53ca`,
battle `fbe9015b`, hero `f18f5ebb`, town `0360ce88`) are computed from state built inline in the
tests (battle `golden_setup`, `test_battle.py:432`) or from their own fixtures, not from
`data/creatures.json` or the content loader. `index` is not part of any canonical form, and
`BattleState.rules_hash` covers `rules.json` only. Hence no pin moves and nothing is re-pinned.

Hashes that do differ and are not goldens: the `content_hash` of a pack built from a player's file
differs from the fixture pack's by design; it is per-install and unpinned.

A golden re-pin is a reviewed change under law 6, recorded in the owning spec. This spec does not
re-pin anything. If an implementation slice moves any of the five, that is a bug to find, not a pin
to update (ADR-0001).

## 5. Test plan

- Parity vectors: extend `tools/h3re/h3re/vectors.py` with a content vector (input TXT bytes,
  expected per-record `index`, name, order, and error category and row for bad inputs); generate
  with `python3 -m h3re.vectors`, check with `--check`; the Kotlin conformance test consumes the
  same files. Cases: blank rows, empty first cell, trailing blank row, duplicate name, non-integer
  cell, header only.
- Synthetic fixture: a small hand-written CRTRAITS-style TXT (about 6 invented creatures) built in
  the test code or as a text file under the test resources. No real file; a real-file test is gated
  on `H3_DATA_DIR` (law 1) and only checks "loads, indices are 0..n-1 with no gaps".
- Roster tests: order equals file order, not name order (fixture rows deliberately out of
  alphabetical order); index equals the sprite key; a bad row refuses the import and names the row.
- Golden check: `python3 -m unittest discover -s tools/h3re/tests`, the Kotlin sim tests and
  `python3 -m h3re.vectors --check`; the five pins unchanged. Lints:
  `python3 tools/lint/banned_api_lint.py`, `python3 tools/lint/kotlin_banned_api_lint.py`.
- Device step: install the debug build, import the player's own CRTRAITS.TXT from device storage,
  start a battle, confirm the roster list is in file order and the sprites match; import a
  deliberately broken copy and confirm the whole import is refused with the row number.

## 6. Risks and open questions

Risks: the column order in `content.md` is marked unverified, so a real file may be refused until
the mapping is checked on the device. Sprite lookup by index assumes the sprite table and the
player's CRTRAITS come from the same install; a different file gives wrong sprites silently.
Mitigation: the sprite loader logs a mismatch between table rows and record count.

Open questions for the owner:

- Q1. Answered (owner, 2026-11-03): a bad row refuses the whole import (the loader already does).
- Q2. Answered (owner, 2026-11-03): with no CRTRAITS imported, the app shows only the import
  prompt; the test roster is no longer the battle roster (ADR-0011 D3 amended).
- Q3. If two rows share a name in the real file: keep refusing (today's rule), or disambiguate by
  index? Needs a look at the real file, which only the owner has.
- Q4. Case B (`dmg_min` >= 1, `dmg_max` 0 = no upper limit): how to represent it (ADR-0008 holds
  pack values in 32 bits), and what battle does with it.
- Q5. Answered (owner, 2026-11-02): C (0/0) is left out of the roster; A (`dmg_min` 0,
  `dmg_max` > 0) is offered and battle accepts it; hp 0 is offered, battle refuses it, and a preset
  using it is disabled with a reason.
- Q7. Answered (owner, 2026-11-03): presets name creatures by data-row index, not by name. Default
  rows 0, 2 and 4; the owner confirms this default on the PR.
- Q8. Answered (owner, 2026-11-03): replays keep the fixture pack hash (`creatures_hash`
  unchanged), so existing saves still load.

## 7. Slices

1. Python `content.py`: file-order output plus `index`; update `content.md:51`; tests. Verify: Python
   suite green, goldens unchanged.
2. Kotlin `Content.kt` mirror; vectors generated and checked. Verify: `--check` clean, Kotlin
   conformance green.
3. Roster entry type and builder (pure), with synthetic-fixture tests for order and invalid-row
   refusal. Verify: those tests green.
4. App wiring: import step, roster from the loaded file (`GameRoster` in `:presenter`, read from
   `H3bitmap.lod` on the data-store thread), presets by row and disabled when a row is missing
   (`PresetCheck`), Home shows only the import prompt without a roster; `creatures.json` no longer
   loaded as the roster but kept for the replay pack hashes. Verify: `:presenter` unit tests, lints;
   `:app` compiles in CI.
5. Sprite table keyed by index (update `sprite-atlas.md`). Verify: atlas tests.
6. Device run per section 5. Verify: owner confirms on the device.
