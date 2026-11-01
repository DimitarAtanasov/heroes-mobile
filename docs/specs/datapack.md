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
