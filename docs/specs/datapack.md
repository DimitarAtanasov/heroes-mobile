# Data pack (`h3re.datapack`)

Forge law: **all balance numbers live in `data/*.json`, never hardcoded.**
Reference implementation: `tools/h3re/h3re/datapack.py` (stdlib only).

## Files

- `data/rules.json`: rule constants mirroring `rules.py`. Fractions are
  `[numerator, denominator]` integer pairs; skill tables are 4 such pairs
  (levels 0..3); bad-morale tables are 3 integers (numerators over
  `morale_die`). Keys: `ad_bonus_per_point`, `ad_bonus_cap`,
  `da_penalty_per_point`, `da_penalty_cap`, `offense`, `archery`, `armorer`,
  `hate_bonus`, `luck_bonus`, `half`, `morale_die`, `bad_morale_numerators`,
  `vcmi_bad_morale_numerators`, `schema_version`.
- `data/creatures.json`: `{"schema_version": 1, "creatures": [...]}`. The
  shipped roster is a small synthetic placeholder set ("Test ..."), not game
  data. Required per creature: `name`, `attack`, `defense`, `dmg_min`,
  `dmg_max`, `hp`, `speed`. Optional: `shots`, boolean flags matching
  `battle.Creature` (`flyer`, `double_wide`, ...), `hates` (list of roster
  names).

- `data/battle_policy.json`: the `BattlePolicy` defaults (rule choices).
  Keys: `schema_version`, `row_offset`, `edge_columns_walkable`,
  `placement_rows` (7 arrays of size 1..7, distinct row indices 0..10),
  `speed_tie`, `wait_order`, `defend_bonus_num`, `defend_bonus_den` (>= 1),
  `defend_bonus_min`, `defend_bonus_rounding`, `good_morale_after_wait`,
  `good_morale_after_defend`, `repeat_good_morale`,
  `bad_morale_on_wait_activation`, `good_morale_on_wait_activation`,
  `bad_luck`, `range_penalty_beyond`, `range_origin`. Integers, booleans and
  enumerated strings only (`datapack.POLICY_CHOICES` lists the allowed
  strings; `battle.BattlePolicy` validates against the same tuples). Unknown
  or missing keys, floats, wrong types and out-of-range values raise
  `DataPackError` (`battle_policy.<key>: ...`). `bad_morale_table` is not in
  this file: its default is `rules.BAD_MORALE_NUMERATORS`, already in
  `rules.json`, and is not repeated.

## Validation

Any problem raises `DataPackError` (a `ValueError`) naming the path, e.g.
`creatures[2].hp: 0 out of range 1..100000`. Rejected: unknown or missing
keys, wrong types (bool is not an integer), floats anywhere in the JSON
(including `1.0`), duplicate JSON keys, out-of-range values, `dmg_min >
dmg_max`, duplicate names, `hates` naming unknown creatures, non-monotonic
skill/morale tables, unsupported `schema_version`.

## Determinism and hash

Creatures are sorted by name; `hates` is sorted. `content_hash` is the
SHA-256 (hex) of the canonical JSON (`sort_keys`, compact separators, ASCII)
of the validated pack, so file formatting and key/creature order do not
affect it; any value change does.

## API

`load_dir(dir=data/)`, `load(rules_path, creatures_path)`,
`parse(rules_obj, creatures_obj)` return a `DataPack` with `.rules`
(read-only mapping; fractions as `Fraction`), `.creatures()`,
`.creature(name)` (`battle.Creature`), `.creature_names`, `.content_hash`,
`.canonical_json`.

## Drift guard

`tests/test_datapack.py` asserts the JSON values equal the current `rules.py`
constants. `rules.py` is not yet wired to read the JSON; that is a follow-up
once its refactor lands.

## Runtime loading (checkpoint 34)
`rules.py` binds its tuning constants from `data/rules.json` at import, through
`datapack.load_rules_dir()`. The directory is `$H3_DATA_PACK_DIR` if set, otherwise `<repo>/data`.
A missing or invalid pack raises `DataPackError` at import. The simulation modules do no file I/O
themselves; the read happens in `datapack.py`. `test_package.py` pins that importing `h3re` opens
only `rules.json`. `test_datapack.py::test_json_equals_code` compares both the loaded pack and the
`rules.py` constants with an independent literal copy inside the test, so drift in either fails.

## Battle policy pack
`datapack.load_policy_pack_dir()` (same `H3_DATA_PACK_DIR` rules as `rules.json`)
returns a `PolicyPack`: `.values` (read-only mapping, `placement_rows` as nested
tuples), `.canonical_json` and `.content_hash` (SHA-256 of the canonical JSON,
`sort_keys`, so formatting and key order do not matter). `battle.py` reads it
at import and exposes `battle.POLICY_HASH`. Importing `h3re` opens exactly two
files, `rules.json` then `battle_policy.json` (pinned by `test_package.py`).
`POLICY_HASH` is **not** a `BattleState` field: the policy values themselves are
already in the state (and so in its hash), so a different pack shows up as a
different hash at step 0 without adding a field. `tests/test_datapack.py::
PolicyPackTest` compares the loaded values and `BattlePolicy()` against an
independent literal copy. Moving the defaults out of code did not change the
golden hash (`fbe9015b...`).

## Pack directory and rules hash (determinism audit)
- `H3_DATA_PACK_DIR` is made absolute once, at `datapack` import (`DEFAULT_DIR`, also exported as
  `LOADED_DIR`), so a later `chdir` cannot change which pack is read. A relative value resolves
  against the working directory at import time.
- `resolve_dir(dir)` makes a path absolute and raises `DataPackError` if it is not an existing
  directory; `load_dir`, `load_rules_dir` and `load_rules_pack_dir` use it, so an unusable
  `H3_DATA_PACK_DIR` fails with one clear message at `rules` import.
- `rules.RULES_DIR` and `rules.RULES_HASH` expose the directory and the content hash
  (`DataPack.content_hash` of the validated `rules.json`, no creatures) that `rules.py` loaded.
  `BattleState.rules_hash` carries `RULES_HASH` into the state hash (`battle.md` §10, ADR-0001).
