# Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)

Turns a CRTRAITS-style TXT table into creature records that pass the datapack
creature schema (`datapack._check_creatures`; see `datapack.md`). Everything
below about the real file layout is **unverified against real files**: it is
taken as functional fact from VCMI `lib/CCreatureHandler.cpp`
(`loadLegacyData`) and `lib/texts/CLegacyConfigParser.cpp` (facts only, no code
or paraphrase of it; ADR-0003). Confirm with the gated test on a local install.

## Reading
`txt.parse_txt(data, header_rows=2, encoding=cp1252)` (CR LF records, quoting
on). Header row 2 must start `Singular`, `Plural`; a third cell `Plural2`
marks a variant with one extra name column (VCMI header check,
`CCreatureHandler.cpp`). Rows with all-empty cells, or an empty first cell, are
skipped (VCMI `isNextEntryEmpty`, `CLegacyConfigParser.cpp`). Non-numeric-empty
numeric cells read as 0 (VCMI `readNumber`); here an empty cell in a *required*
column is an error instead.

## Column order (data: `data/txt_maps/crtraits.json`, unverified)
singular, [plural2 if that header variant], plural, cost wood, mercury, ore,
sulfur, crystal, gems, gold (resource order from VCMI
`lib/constants/StringConstants.h`), fight value, AI value, growth, horde
growth, hit points, speed, attack, defense, damage min, damage max, shots,
[spell points, absent for RoE data: `roe=True`], adventure-map amount min,
max, ability text (long description), abilities (short list).
Datapack fields filled: name (singular), hp, speed, attack, defense, dmg_min,
dmg_max, shots (omitted when 0) and the boolean flags.
Creature field ranges (the datapack bounds): `dmg_min` 0..10000 (floor 0: real
CRTRAITS rows have minimum damage 0; owner decision, 2026-11-02), `dmg_max`
1..10000, `dmg_max >= dmg_min`. The CRTRAITS loader alone lowers the `dmg_max`
floor to 0 (owner decision, 2026-11-02; `creatures.json` keeps 1), so with
`dmg_max >= dmg_min` the only new row it admits is dmg 0/0.
The CRTRAITS loader also lowers the `hp` floor to 0 (owner decision, 2026-11-02;
`creatures.json` keeps 1); battle creation still refuses hp 0.
Owner's meaning of the damage cells (2026-11-02):
- A: `dmg_min` 0, `dmg_max` > 0: a weak unit dealing 0..`dmg_max`. Loads.
- B: `dmg_min` >= 1, `dmg_max` 0: no upper limit. Still refused (`dmg_min >
  dmg_max`); its representation is an open owner question (ADR-0008 holds
  pack values in 32 bits; no cap is invented and 0 is not stored as a real
  maximum).
- C: `dmg_min` 0, `dmg_max` 0: no fixed damage (the attack comes from an
  ability). Loads; the name is listed in `result.no_fixed_damage`.
Battle creation needs `0 <= dmg_min <= dmg_max` and `dmg_max >= 1` (battle.md), so
creatures in C (and hp 0) are refused there; A is accepted. Whether
the battle roster offers them is an owner question. Everything else
(plural, costs, values, growth, spell points, map amounts) lands in
`result.extras[name]`; the schema has no slot for it yet.

## Abilities
VCMI ignores the two trailing text columns (it takes abilities from its own
JSON). Here the last column is split on `ability_separator` (`,`), each item
normalised (lowercase, whitespace collapsed) and looked up in
`ability_flags`: a flag name sets that flag, `null` means known with no flag
(e.g. shooter, derived from `shots`). Anything else is appended to
`result.unknown` as `(row, creature name, text)`; it is never dropped silently
and never fatal. The ability texts in the shipped table are placeholders
(unverified); flag targets are checked against `datapack._CR_FLAGS`.

## Errors
`ContentError` (a `ValueError`): bad mapping, undecodable table, bad header,
missing/empty required cell, non-integer cell, schema violation (the datapack
message is wrapped), duplicate name. Messages name `row N` (1-based file line,
header included) and, where applicable, `column 'name' (index i)`.
`hates` is not derivable from the table.

## API
`load_mapping(path=None)`, `parse_creatures(bytes, mapping=None, roe=False,
encoding="cp1252") -> ContentResult(creatures, extras, unknown, creature_rows,
no_fixed_damage)`, `load_creatures(path, ...)`. Creatures are sorted by name
(datapack order). `no_fixed_damage` (Kotlin `noFixedDamage`) is a frozenset of
the names of accepted creatures with dmg 0/0 (case C). Like `creature_rows` it
is a side structure: not in the creature record, `toMap`, `content_hash` or any
battle state, so no hash moves. Those creatures stay in `creatures` and keep
their data-row index; later creatures' indices are unchanged.

## Tests
`tests/test_content.py`: synthetic fixtures only. `RealCrtraitsTest` is gated
on `H3_DATA_DIR`, finds `CRTRAITS.TXT` under it, requires every row to resolve
and asserts invariants only (no content printed).
