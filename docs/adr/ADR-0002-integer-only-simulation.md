# ADR-0002: Integer-only simulation (int and Fraction, one explicit rounding step)

Status: accepted

Context: The simulation must give identical results on every machine and Python build, and
the state hash (ADR-0001) must match across them. Floating-point results can differ by platform
and expression order, and they cannot be reviewed for exactness by reading. `rules.py` already
uses exact fractions with one floor (`docs/specs/rules.md` sections 6.5-6.6), and
`adventure.py` keeps percentages as integers with a named rounding mode (`_div`, ~L167).

Decision:
- Modules `rules.py`, `rng.py`, `battle.py`, `adventure.py` and any new sim module use only `int` and `fractions.Fraction` for values that reach state, events or hashes.
- No float literals, no `float()`, no true division `/` on sim values. Use `//`, `Fraction`, or a named rounding helper.
- Each derived quantity has one explicit rounding step. Its mode (floor, ceiling, nearest) comes from the policy or from the spec. Use `math.isqrt` for square roots.
- Floats are allowed outside the simulation, for example in presentation or image tools such as `defimg.py`, as long as their output never feeds sim state.

Consequences:
- Rounding bugs become visible in one place: the rounding helper. Reviewers check that helper first.
- Any float that sneaks into the sim is a determinism hazard, and `determinism-auditor` treats it as a blocker.
- `data/*.json` tuning values are integers or explicit rationals (for example `[num, den]`), never decimals.

Verification:
- Review by `determinism-auditor` on every sim diff (CLAUDE.md law 2).
- Exact-value tests in `tools/h3re/tests/test_rules.py` and the damage and movement tests.
- Pending: an automated banned-API lint (float, `/`, time, unordered iteration, I/O), tracked in `docs/checkpoints/HANDOFF.md` item 3. Until it is committed and wired into the suite, this ADR is enforced by review and tests only.
