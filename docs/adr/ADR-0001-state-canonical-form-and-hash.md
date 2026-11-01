# ADR-0001: Canonical JSON form and SHA-256 state hash for battle and adventure state

Status: accepted

Context: Replays, saves and sync need one byte form per game state, so equal states hash
equal on every machine. `battle.py` and `adventure.py` both implement `canonical(state)` and
`state_hash(state)` (`tools/h3re/h3re/battle.py` ~L659-673, `tools/h3re/h3re/adventure.py`
~L553-559). Python's `repr`, pickle and dict ordering are not stable contracts, and floats
are excluded by ADR-0002, so the canonical form must be explicit.

Decision:
- `canonical(state)` = `json.dumps(dataclasses.asdict(state), sort_keys=True, separators=(",", ":")).encode("utf-8")`.
- `state_hash(state)` = `sha256(canonical(state)).hexdigest()`.
- The policy (`BattlePolicy`, `AdventurePolicy`) is part of the state, so it is part of the hash.
- The rules pack in force is part of the state: `BattleState.rules_hash` is the `datapack`
  content hash of the loaded `rules.json` (`rules.RULES_HASH`) and is always in the canonical
  form, so peers with different packs diverge at step 0. A sim module that starts reading pack
  values must carry the hash too (`adventure.py` reads none today and does not).
- `apply` refuses a battle state whose `rules_hash` differs from the local pack
  (`battle.PackMismatch`, an `IllegalCommand`), before any RNG draw.
- `BattlePolicy` defaults come from `data/battle_policy.json`. The policy values are in
  the state, so that file needs no hash field of its own (`battle.POLICY_HASH` is for logs
  and tests); moving the defaults out of code was not a re-pin.
- Battle only: fields added after a pin may be listed in `_OMIT_WHEN_DEFAULT` and are left out
  of the canonical form while they hold their default. This keeps older hashes valid. The list
  is empty right after a re-pin.
- Re-pin rule: a golden hash changes only through a reviewed re-pin. The re-pin:
  1. is its own reviewed change, not mixed with unrelated edits;
  2. records the reason in the owning spec (`docs/specs/battle.md` or `docs/specs/adventure.md`): the rule or field that changed, why the new hash is expected, and the old and new values;
  3. updates every pin together: `PINNED` in `tests/test_battle.py` and `tests/test_adventure.py`, and `GOLDEN_PINNED` in `tests/test_battle_cli.py`, which mirrors the battle value;
  4. empties `_OMIT_WHEN_DEFAULT` if it was used.
- A golden hash that moves without a re-pin is a regression to find and fix, not a value to update.

Re-pin history:
- 2026-11-01 (1): battle `cd969e37...` -> `2191ae97...` (row parity, policy fields, `last_side`).
- 2026-11-01 (2): battle `2191ae97...` -> `fbe9015b...` (`rules_hash` added; play unchanged).
  Reasons are in `docs/specs/battle.md` section 10. Adventure pin `179c5700...` did not move.

Consequences:
- Every state field must be canonical-serialisable: ints, strings, bools, tuples, nested dataclasses. A set or a non-string dict key makes `json.dumps` fail, which is the intended fail-closed behaviour.
- Adding a field changes every hash unless it is omitted while at default. `sim-engineer` must handle this, `spec-agent` must flag it, and `determinism-auditor` must check it.
- `adr-scribe` writes the re-pin record. The spec, not the test file, is where the reason lives.

Verification:
- `test_golden_hash` in `tools/h3re/tests/test_battle.py` and `tools/h3re/tests/test_adventure.py`.
- `GOLDEN_PINNED` check in `tools/h3re/tests/test_battle_cli.py`.
- Same-input, same-hash tests (`test_battle.py`, `test_adventure.py`) and policy-change-changes-hash tests.
- Full suite: `python3 -m unittest discover -s tools/h3re/tests`.
