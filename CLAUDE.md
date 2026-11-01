# heroes-mobile: project constitution

Clean-room, data-driven reimplementation tooling inspired by Heroes of Might and Magic 3.
Python 3.13 package `tools/h3re/` (readers, rules, battle, adventure, encounter, town and hero
cores, replay files, battle presenter, content loader, tests). The Android app and its Kotlin
engine live in `android/` (`sim` module), per ADR-0004; Python is the reference oracle.
Specs live in `docs/specs/`, decisions in `docs/adr/`, progress in `docs/checkpoints/`.

## Laws

1. **Clean-room.** Specs come from public documentation and observed mechanics. VCMI
   (GPL) is a source of facts only: no code, comments or paraphrase of its code (ADR-0003).
   Original game files, assets and binaries never enter the repo. Tests use synthetic
   fixtures; real-file tests are gated on `H3_DATA_DIR`.
2. **Determinism.** Simulation modules (`rules.py`, `rng.py`, `battle.py`, `adventure.py`,
   `encounter.py`, `town.py`, `hero.py`; the list the lint checks is `SIM_MODULES` in
   `tools/lint/banned_api_lint.py`) must not use floats, clocks, environment reads, threads, I/O, or iteration over unordered
   collections where order reaches state or events. Randomness comes only from the passed
   stream (`rng.derive_stream`, one named stream per feature). Set membership is fine.
3. **Integer-only simulation** (ADR-0002). `int` and `fractions.Fraction` only, with one
   named rounding step per derived quantity. No `/` on sim values, no float literals.
4. **Balance numbers live in `data/*.json`.** Code holds formulas, not tuning values. At import,
   `rules.py` constants are loaded from `data/rules.json` and the `battle.py` policy defaults from
   `data/battle_policy.json`, both via `h3re/datapack.py` (override the directory with
   `H3_DATA_PACK_DIR`). Importing `h3re` opens exactly these two files; a test pins that
   (`tests/test_package.py`). Other tuning constants still in code (adventure constants, for
   example) are migration debt (HANDOFF), not precedent.
5. **Every sim change needs a test** in `tools/h3re/tests/`, in the same change.
6. **Golden re-pin rule.** Golden hashes are pinned in the tests. A re-pin is a reviewed
   change, and its reason is recorded in the owning spec (`docs/specs/battle.md` or
   `adventure.md`). A hash change without a re-pin is a bug to find, not a pin to update
   (ADR-0001).
7. **Tests before commit.** The full suite must pass:
   `python3 -m unittest discover -s tools/h3re/tests`
8. **Commit only finished, verified pieces.** No WIP commits to the main line.
9. **No real game data in the repo.** Maps, LOD archives, DEF/PCX assets and extracted
   text tables stay on the user's machine.
10. **Specs are the source of truth.** When code and spec disagree, flag it, decide, and
    record the decision in an ADR. Never silently edit code to match stale docs, or docs to
    match a bug.

## Roles and delegation

The main session orchestrates: it triages, routes and verifies. Role definitions live in
`.claude/agents/*.md`; the models and effort levels are set only there, so this file and
other docs refer to roles, never models.

| Role | Purpose |
|---|---|
| `explore` | Read-only recon: file and symbol lookup, log and test triage. Any lookup reading more than two files goes here. |
| `spec-agent` | Turns a requirement into a spec section, acceptance criteria and determinism impact. Runs before non-trivial sim work. |
| `sim-engineer` | Implements changes in the simulation modules, with tests. |
| `test-verifier` | Checks acceptance criteria against command output. Trusts nothing without output. |
| `determinism-auditor` | Reviews sim diffs for determinism hazards. Runs before merging sim changes and on any hash divergence. |
| `adr-scribe` | Writes ADRs, keeps spec cross-references current, records re-pins. |

## Commands

- Tests: `python3 -m unittest discover -s tools/h3re/tests`
- CLI: `cd tools/h3re && python3 -m h3re <lod-list|lod-extract|def-to-png|h3m-info|battle-sim|replay>`
- Conformance vectors (the Kotlin contract, ADR-0007): `cd tools/h3re && python3 -m h3re.vectors`
  writes to `android/sim/src/test/resources/vectors`; `--check` exits non-zero if the committed
  files differ from a fresh generation. Vectors are never edited by hand.
