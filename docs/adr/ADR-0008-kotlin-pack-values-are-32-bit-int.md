# ADR-0008: Kotlin pack values are 32-bit Int capped at 2**31-1; hashes and XP accumulation use Long

Status: accepted

Context: `tools/h3re/h3re/datapack.py` bounds every pack integer through `MAX_INT`. The working tree now sets `MAX_INT = (1 << 31) - 1` with a comment citing ADR-0004 (uncommitted at the time of writing; the datapack owner makes that change). Before that the value was `1 << 31`, one above the largest Kotlin `Int`, so Python would have accepted a value the Kotlin engine cannot hold. `docs/specs/datapack.md` and `tools/h3re/tests/test_datapack.py` (`test_max_int_is_the_jvm_int_max`) pin the bound.

Decision:
- In the Kotlin engine, a pack integer (any integer read from `data/*.json`) is a 32-bit `Int` with the accepted range 0 to 2**31-1 inclusive. Python's `datapack.MAX_INT` is the same value, so both sides refuse the same packs.
- Intermediate sums in state hashing (byte counts and totals of canonical JSON) and experience accumulation use `Long` (64-bit). A value that the state stores as a pack integer stays within `Int`; a value that is only a running sum does not.
- Amendment (owner decision, 2026-11-02): the creature `dmg_min` floor is 0, not 1, because real CRTRAITS rows have minimum damage 0. The upper bound 10000 and `dmg_min <= dmg_max` are unchanged, in both Python (`datapack._check_creatures`) and Kotlin (`Datapack.CR_INTS`, `DefaultCreatureValidator`).
- Amendment (owner decision, 2026-11-02): for CRTRAITS loading only, the creature `dmg_max` floor is 0 (`content.py` passes `dmg_max_floor=0` to `datapack._check_creatures`; Kotlin `DefaultCreatureValidator`); `creatures.json` (`Datapack.CR_INTS`) keeps 1, and `dmg_min <= dmg_max` and the upper bound 10000 are unchanged.
- A value outside the range fails the pack load on both sides. Nothing is clamped.
- The change of `MAX_INT` from `1 << 31` to `(1 << 31) - 1` is a validation-bound change only. It moves no pinned hash, because no pinned pack holds the value 2**31.

Consequences:
- `sim-engineer` (Kotlin): pack values are read as `Int`; any arithmetic that can exceed `Int` widens to `Long` before the operation.
- Python owner (datapack): the change to `MAX_INT` is committed with the test that pins it. That test, `test_max_int_is_the_jvm_int_max`, already expects `2147483647`.
- `determinism-auditor`: checks that an overflow of a pack value is refused, not wrapped.

Verification:
- `test_datapack.py::test_max_int_is_the_jvm_int_max` (2147483647 accepted, 2147483648 refused) and the boundary tests in the same file.
- `python3 -c "import h3re.datapack as d; print(d.MAX_INT)"` prints `2147483647` from `tools/h3re`.
- Kotlin unit test: a pack value at `Int.MAX_VALUE` loads and one above it fails (to be added with the Kotlin pack loader).

## Amendment (2026-11-01): caps on derived products

Context: the Kotlin-port audit found that the per-value bound is not enough. A stack of 2**31-1
creatures with a large attack makes Python report a strike of 8589934588 damage, which the Kotlin
engine refused at `toIntExact`, and `count x dmg_max` with both factors near 2**31 overflowed the
Long arithmetic of the damage pipeline.

Decision:
- A battle state also caps the products the damage pipeline builds: `count x dmg_max` <= 2**31-1 and
  `count x hp` <= 2**31-1 for every stack, and the attack sum (creature plus hero) and the defense
  sum (creature plus hero, with and without the defend bonus) lie in the Int range. Python
  `battle.check_state` enforces this (called by `create_battle`); Kotlin `BattleCodec.parseState`
  enforces the same checks with the same messages. Policy integers are bounded to 0..2**31-1.
- Values the caps do not bound are `Long` in Kotlin: `DamageDealt.damage` (a strike can exceed
  2**31-1) and the defend bonus. Killed creatures, counts and HP stay `Int`.
- A value above a cap is refused, never clamped or wrapped.

Consequences: no pinned hash moved (golden `fbe9015b...`, every earlier vector step unchanged).
`battle_states.json` carries the `cap` case, `policy_reject_cases` and `state_reject_cases`.

Verification: `tests/test_battle.py` `IntegerCapTest` and `CheckStateTest`;
`tests/test_vectors_battle.py` `TestContractEdgeVectors`; Kotlin `BattleStateTest`
(`policyRejectCasesMatchPython`, `stateRejectCasesMatchPython`, `theCapStateIsAcceptedAndOneAboveIsNot`),
`BattleTest.capCaseDealsMoreThanIntDamageAsALong` and `RationalTest.damagePipelineStaysInLongAtTheCaps`.
