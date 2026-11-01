# Handoff (resume here)

Branch: `ccr-c70423ba-3alf1w`. Clean-room rule: no original assets/code; VCMI (GPL-2.0)
is used only as a source of functional facts, via the cross-check reports.
Run tests: `python3 -m unittest discover -s tools/h3re/tests` (all must pass before a commit).

## Done (committed + pushed), checkpoints 0-35
LOD, DEF (hardened), PCX, TXT, H3M (header, post-teams sections, terrain tiles, VCMI fixes),
PCG32 RNG, battle damage rules, battle core + greedy AI + `battle-sim` CLI, adventure core,
package exports, real-file tests gated on `H3_DATA_DIR`, CI, README, VCMI cross-check reports.

## In flight
Nothing. Checkpoints 0-35 are committed and pushed; 356 tests pass (2 skipped without H3_DATA_DIR).

## Next
1. Migrate battle.py policy defaults and creature stats into data/ (rules.py already reads data/rules.json). Golden hash must stay unchanged.
2. Mysticism and remaining rules.md section 9 items need real-game experiments.
3. Longer determinism soak locally: `cd tools/h3re && python3 -m h3re.soak --games 200`.
4. Spells framework (all formulas are [uncertain]; needs rules.md section 9.11 experiments first).
5. Optional: lazy-load rules constants so a bare `import h3re` does not need data/ present.

## Needs the user (cannot be verified without real data)
Legal HoMM3 install with `H3_DATA_DIR` set; real .h3m maps (RoE/AB/SoD); results of the rules.md section 9 experiments
(speed tie, wait order, bad-morale table, damage roll distribution).
