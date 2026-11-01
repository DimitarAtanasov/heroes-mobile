# ADR-0009: The Kotlin engine uses a small exact Rational type with one named rounding step, not an integer rewrite

Status: accepted

Context: ADR-0004 (Consequences, "Exact rationals") offered two routes and preferred rewriting the Python `Fraction` formulas as integer arithmetic. Python still uses `fractions.Fraction` in `tools/h3re/h3re/rules.py` (`docs/specs/rules.md` sections 6.5-6.6), in `town.py` (`_frac`) and in the adventure step costs (`docs/specs/adventure.md` section 2, `floor(cost x sqrt 2)` via `isqrt`). At the time of writing, a `Rational.kt` is in progress and uncommitted under `android/sim/src/main/kotlin/h3/sim/`; the committed `sim` module has only `Canonical.kt` and `Rng.kt`.

Decision:
- The Kotlin sim module gets a small `Rational` type: numerator and denominator as `Long`, normalised (gcd-reduced, positive denominator), with exact add, subtract, multiply, divide and comparison.
- Every derived integer is produced by exactly one named rounding function (floor, ceiling or nearest, as the spec names it). No other conversion from `Rational` to an integer exists.
- Arithmetic is overflow-checked and throws; it never wraps. The in-progress file uses `Math.*Exact`, and a zero denominator throws. This detail was not in the amendment request; it is recorded here and needs the user's confirmation.
- The integer-rewrite option in ADR-0004 is withdrawn, because it would change the formula shape on one side only and the vectors (ADR-0007) would have to carry that difference.

Consequences:
- `sim-engineer` (Kotlin): implements `Rational` and the rounding functions in the `sim` module, tested against the Python values in the vectors.
- `spec-agent`: a formula in a spec that uses a fraction names its rounding step, so the Kotlin side has one function to call.
- `determinism-auditor`: the `Rational` path must contain no `Double` or `Float`; the rounding helper is reviewed first (ADR-0002).
- Python is unchanged by this ADR.

Verification:
- Kotlin unit tests for normalisation, sign handling, and an overflow that throws (to be added with the type).
- `ConformanceTest` passes every vector that holds a fraction-derived value (`cd` to `android/` and run the `:sim` test task).
- `grep -rn "Double\|Float" android/sim/src/main/kotlin` returns nothing in the sim code.
