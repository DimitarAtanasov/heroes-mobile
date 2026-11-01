# ADR-0005: The omit-at-default canonical mechanism applies to every state module, not only battle

Status: accepted

Context: ADR-0001 introduced `_OMIT_WHEN_DEFAULT` as a battle-only rule. `adventure.py` now uses the same list for `GameState.guards`, `encounter` and `battles` (`tools/h3re/h3re/adventure.py` ~L618-628), so the 14-day adventure pin `179c5700...` survived the encounter fields (`docs/specs/adventure.md` section 8, `docs/specs/encounter.md` section 6). `town.py` and `hero.py` have no omit list; their `canonical` is `asdict` of the whole state, so their first pins hold every field.

Decision:
- Any state module may list fields added after a golden pin in its own `_OMIT_WHEN_DEFAULT`. A listed field is left out of the canonical JSON only while it equals its dataclass default. The rest of ADR-0001 (sorted keys, compact separators, UTF-8, SHA-256) is unchanged.
- A module that has no such field needs no list (`town.py` and `hero.py` today).
- First pins recorded on 2026-11-01. These are first pins, not re-pins, so they do not enter the ADR-0001 re-pin history:
  - town `0360ce88...` (`tools/h3re/tests/test_town.py` `GoldenTest.PINNED`, `docs/specs/town.md` section 7);
  - hero `f18f5ebb...` (`tools/h3re/tests/test_hero.py` `GoldenTest.PINNED`, `docs/specs/hero.md` section 7);
  - encounter `512b53ca...` (`tools/h3re/tests/test_encounter.py` `GoldenTest.PINNED`, `docs/specs/encounter.md` section 7). This is an `adventure.state_hash` of the final state, not a separate state form.
- Lists that are non-empty today: `adventure._OMIT_WHEN_DEFAULT = ("guards", "encounter", "battles")`. `battle._OMIT_WHEN_DEFAULT` is empty (`tools/h3re/h3re/battle.py` ~L663) and only covers policy fields.

Consequences:
- `sim-engineer`: when a field is added after a pin, add it to the owning module's list, prove the default-state hash equals the old pin in a test, and document it in the owning spec. The list is emptied at the next reviewed re-pin (ADR-0001).
- `spec-agent`: flags any new post-pin field and states its default.
- `determinism-auditor`: checks that a list entry is removed from the canonical form only when it is at its default, and that the default is a fixed value (no clock, no pack read).
- `adr-scribe`: the spec section names the list entries; this ADR does not repeat them as a moving record.

Verification:
- `test_golden_hash` in `tools/h3re/tests/test_adventure.py` (`179c5700...`), `test_battle.py` (`fbe9015b...`), `test_encounter.py` (`512b53ca...`), `test_town.py` (`0360ce88...`) and `test_hero.py` (`f18f5ebb...`).
- `grep -n "_OMIT_WHEN_DEFAULT" tools/h3re/h3re/*.py` shows only `adventure.py` and `battle.py`, and any new module that adds one must appear in its owning spec.
- Full suite: `cd tools/h3re && python3 -m unittest discover -s tests`.
