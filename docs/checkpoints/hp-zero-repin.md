# CRTRAITS hp floor 0: content.json re-pin

Owner decision 2026-11-02: the CRTRAITS loader accepts creature `hp` 0 (floor 0, was 1). Only the
CRTRAITS path changes (`content.py` passes `hp_floor=0`; Kotlin `DefaultCreatureValidator` hp
0..100000). `creatures.json` and the pack path (`datapack._check_creatures` default) keep floor 1.
Battle code is unchanged: `create_battle` still refuses hp 0 (`cr.hp <= 0`).

## Vector change (`android/sim/src/test/resources/vectors/content.json`)

Regenerated with the repo generator (`python3 -m h3re.vectors`, case table in
`tools/h3re/h3re/vectors_txt.py`); no JSON was edited by hand. One case changed (index 30), same
input bytes (a row with hp cell "0"):

| | name | result |
|---|---|---|
| old | `err_hp_zero` | error: category `schema`, row 3, column null |
| new | `err_hp_zero_ok` | accepted: creature Glimmerwisp, hp 0 (other fields as the base row), no error |

The new name follows the `dmg_min_zero_ok` style. No other content.json case changed.

## Other vector files

The same generator run also differed in `h3m.json` and `lod.json` (zlib-compressed bytes and the
derived packed sizes/offsets in `lod.json`) on this machine. That is zlib-version drift, unrelated
to this change, and those files are not part of this commit. The other 17 files were
line-ending-only differences.

Specs: `docs/specs/content.md` and ADR-0008 carry the one-line hp floor 0 amendment.
