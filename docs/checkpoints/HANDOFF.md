# Handoff (resume here)

Branch: `ccr-c70423ba-3alf1w`. Clean-room rule: no original assets or code; VCMI (GPL-2.0)
is a source of functional facts only, via the cross-check reports (ADR-0003).
Run tests: `cd tools/h3re && python3 -m unittest discover -s tests` (all must pass before a commit).

## State
- Checkpoints 0-46 are committed and pushed. Head: `d26e517` (checkpoint 46). No unpushed commits.
- Tests: 557 run, OK, 4 skipped (real-file tests need `H3_DATA_DIR`). Count taken from the working
  tree on 2026-11-01, which includes uncommitted work (below).
- Uncommitted work by other roles is in the tree and is not checkpoint 46: `datapack.py`
  (`MAX_INT` to 2**31-1), `town.py`, `hero.py`, `vectors.py`, their tests, spec edits to
  `datapack.md`, `hero.md`, `town.md`, and new Kotlin files `Rational.kt`, `Rules.kt`,
  `RulesTest.kt` and `vectors/rules.json`. Review, commit or revert each before checkpoint 47.

## Decisions in force
ADR-0001 (canonical form, hash, re-pins), ADR-0002 (integer-only), ADR-0003 (clean-room),
ADR-0004 (Kotlin engine, Python oracle), ADR-0005 (omit-at-default for every state module),
ADR-0006 (stored content stands in for a pack hash), ADR-0007 (replay files and vectors are
the cross-language contract), ADR-0008 (Kotlin pack values are `Int`, capped at 2**31-1),
ADR-0009 (Kotlin `Rational` with one named rounding step).

## Next, in order
1. **Kotlin port: rules, then battle, then canonical state.** Each step must pass the vectors:
   `cd tools/h3re && python3 -m h3re.vectors --check` and the Kotlin `:sim` tests (ADR-0007).
   The pack loader needs ADR-0008 first; formulas that use fractions need ADR-0009.
2. **Implement the unsupported H3M object bodies** (sign, seer hut, garrison, shrine and the
   others listed as unsupported). Each class gets a note in `docs/specs/h3m.md` and a synthetic
   test. Until a class is implemented it keeps failing loudly with its index and offset.
3. **Adventure constants into `data/*.json`** (the migration debt in `CLAUDE.md` law 4). If the
   values do not change, the adventure hash does not move. If a value changes, the change is a
   reviewed re-pin (ADR-0001) recorded in `docs/specs/adventure.md`. If adventure starts reading
   a `rules.json` value, it also gets a `rules_hash` (ADR-0006).
4. **Spells**, only after the `rules.md` section 9 experiments. Every spell formula is [uncertain].
5. **Small pending items** (each needs a test in the same change):
   - Commit the `MAX_INT` change with `test_max_int_is_the_jvm_int_max` (ADR-0008).
   - A test that a changed stored content value changes `state_hash` for town and hero (ADR-0006).
   - A test that `adventure.py` `Move.dest` refuses a float or bool pair (`battle.md` section 10, 2026-11-01).
   - Optional: lazy-load the pack constants so a bare `import h3re` opens no files. Today it opens
     `rules.json` and `battle_policy.json` (pinned by `tests/test_package.py`).
   - Longer soak locally: `cd tools/h3re && python3 -m h3re.soak --games 200 --policy-matrix`.

## Needs the user
- A legal HoMM3 install, with `H3_DATA_DIR` set, to run the real-file tests. They have never run.
- Real `.h3m` maps (RoE, AB, SoD) to check the H3M layouts, which are still unverified.
- Results of the `rules.md` section 9 experiments: speed tie, wait order, bad-morale table, damage roll distribution.
- Confirm the Kotlin `Rational` overflow behaviour in ADR-0009 (it throws; it does not wrap). That detail was proposed, not requested.
- Whether the agent column for checkpoints 40-46 in `GRAPH.md` should be filled in. Git history does not record which role did each one.
