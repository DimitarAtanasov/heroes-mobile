# ADR-0006: Content and policy stored in a state stand in for a separate pack hash

Status: accepted

Context: ADR-0001 requires a `rules_hash` field on a state that reads a `rules.json` value (`BattleState.rules_hash`, `EncounterSetup.rules_hash`). `docs/specs/town.md` section 1 and `docs/specs/hero.md` section 1 say their pack content, policy and class are stored in the state, so they carry no `rules_hash`. `town.py` and `hero.py` `content_hash` exist for logs and tests only.

Decision:
- A state module whose only pack input is data stored in the state (its content, its policy, its class) needs no separate pack-hash field. The stored content is in the canonical form, so a different pack produces a different state hash and peers diverge at step 0.
- Such a module must store the whole content it reads (values, not a name or a reference to a file) and must read no `rules.json` value.
- A module that reads any `rules.json` value, directly or through `battle`, carries `rules_hash` as ADR-0001 says and refuses a mismatch before any RNG draw. `encounter` is in this group: it carries `EncounterSetup.rules_hash` and checks it in `encounter.py` (~L201).
- A content hash (`content_hash`) is never a substitute for the stored content in a state and is not compared at load time.

Consequences:
- `spec-agent`: a new module states in its spec whether it reads `rules.json`. The town and hero "no `rules_hash`" statements hold only while that stays false; if either starts reading a rules value, it gets a `rules_hash` as a reviewed re-pin (ADR-0001).
- `sim-engineer`: a module in the first group must not keep a file path or a loaded object outside the state.
- `determinism-auditor`: checks that the module's imports do not reach `rules.json` (the `rules` module, or `datapack` loaders for that file) without the `rules_hash` field.

Verification:
- Required: a test that changing one stored content value changes `state_hash` for town and hero. If it is absent, it is a gap for `sim-engineer`, not an exemption.
- `grep -n "import" tools/h3re/h3re/town.py tools/h3re/h3re/hero.py` shows no import of `rules`.
- `test_golden_hash` in `test_town.py` and `test_hero.py` (pins in ADR-0005).
