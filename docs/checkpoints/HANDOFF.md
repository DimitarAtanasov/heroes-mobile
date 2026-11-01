# Handoff (resume here)

Branch: `ccr-c70423ba-3alf1w`. Clean-room rule: no original assets/code; VCMI (GPL-2.0)
is used only as a source of functional facts, via the cross-check reports.
Run tests: `python3 -m unittest discover -s tools/h3re/tests` (all must pass before a commit).

## Done (committed + pushed), checkpoints 0-29
LOD, DEF (hardened), PCX, TXT, H3M (header, post-teams sections, terrain tiles, VCMI fixes),
PCG32 RNG, battle damage rules, battle core + greedy AI + `battle-sim` CLI, adventure core,
package exports, real-file tests gated on `H3_DATA_DIR`, CI, README, VCMI cross-check reports.

## In flight
Nothing. Checkpoints 0-29 are committed and pushed; 299 tests pass (2 skipped without H3_DATA_DIR).

## Next (user-approved order: VCMI fixes first, then the Forge-inspired work)
1. Data pack: creatures and rule constants in JSON (Forge law: no hardcoded balance numbers), loaded and schema-checked.
2. Single damage pipeline for preview and execution with roll policies; property test actual in [floor, ceiling].
3. Determinism gate: Python fuzz soak + divergence bisector for battle.py, banned-API lint (float, time, unordered iteration, I/O).
4. ADR for the canonical-state and hash format.
5. `CLAUDE.md` with project laws + `.claude/agents` role files (models pinned in frontmatter, effort per role).
6. Prettier output: battle-sim board + event log, README loop graph.
7. Reconcile engine-design.md palette note (0-7 per VCMI), tidy GRAPH.md rows 18-24.

## Needs the user (cannot be verified without real data)
Legal HoMM3 install with `H3_DATA_DIR` set; real .h3m maps (RoE/AB/SoD); results of the rules.md section 9 experiments
(speed tie, wait order, bad-morale table, damage roll distribution).
