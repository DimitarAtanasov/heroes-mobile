# ADR-0014: Creature sprite table ported from VCMI, keyed by CRTRAITS row

Status: accepted (owner decision, 2026-11-02). Amends ADR-0003 for one fact table only; resolves
open question Q2 in `docs/specs/android-app.md` section 14.

## Context

Q2 asks where the creature-to-sprite mapping comes from (battle DEF, missile DEF, obstacles and
backgrounds). `CRTRAITS.TXT` and `CRANIM.TXT` carry no DEF file names: they hold stats and
animation timing only (verified). The mapping therefore cannot be read from the player's install
text tables. ADR-0003 forbids VCMI data tables by default, and ADR-0010 permits porting VCMI
material with provenance. Names are localised, so the key must be the `CRTRAITS.TXT` row, not a
name. The owner chose option (b): port the mapping from VCMI's creature configuration.

## Decision

The mapping is a data table `data/sprite_map.json`, `schema_version` 2, keyed by `CRTRAITS.TXT`
row index. Each entry is `{row, def, source}`. The table holds facts only: a row number and a
DEF archive member name. Each entry's `source` cites the VCMI file path and the VCMI commit the
fact was read from. No VCMI code is ported and no VCMI file is copied into the repo.

This amends ADR-0003 for this one fact table only. Its "no data tables from VCMI" default stays
in force for every other table, and numeric game values still come from the player's own data at
runtime.

## Consequences

- The table is data under the project's licence (ADR-0010) and ships with the repo. It contains
  names of files, not any game asset, so law 9 holds.
- At runtime the app resolves a creature to its row from the owner's `CRTRAITS.TXT`, then looks
  up the DEF name in the table.
- The key changes from name to row. Schema v2 supersedes the name-keyed format in
  `docs/specs/sprite-atlas.md`, section "Creature sprite table (0.2)"; that section must be
  updated when the table is written.
- Entries must be reviewed against the cited commit. Adding an entry without a `source` is
  rejected.

## Alternatives considered

- (a) The owner writes the table by hand with ADR-0003 citations. Rejected: slow and error-prone
  for the full creature list, with no benefit over a cited port of facts.
- (c) Derive the mapping from the player's install. Not possible: the text tables carry no DEF
  names.

## Re-pin and verification

At load, every `def` in the table is checked against the decoded DEF archives of the install. A
missing member is reported (row, name, source), never guessed or replaced by a fallback name. If
the table is re-generated from a newer VCMI commit, each changed entry's `source` is updated and
the change is reviewed as a data change.
