# Handoff (resume here)

Branch: `ccr-c70423ba-3alf1w`. Clean-room rule: no original assets/code; VCMI (GPL-2.0)
is used only as a source of functional facts, via the cross-check reports.
Run tests: `python3 -m unittest discover -s tools/h3re/tests` (all must pass before a commit).

## Done (committed + pushed), checkpoints 0-39
LOD, DEF (hardened), PCX, TXT, H3M (header, post-teams sections, terrain tiles, VCMI fixes),
PCG32 RNG, battle damage rules, battle core + greedy AI + `battle-sim` CLI, adventure core,
package exports, real-file tests gated on `H3_DATA_DIR`, CI, README, VCMI cross-check reports.

## In flight
Nothing. Checkpoints 0-39 are committed and pushed; 402 tests pass (2 skipped without H3_DATA_DIR).

## Next
1. Adventure state has no rules_hash (reads nothing from the pack); add it, with a reviewed re-pin, if adventure starts reading the pack.
2. A state saved under a different battle_policy.json keeps the policy stored in it; rules_hash covers rules.json only (see battle.md section 10).
3. Spells framework only after rules.md section 9 experiments (all formulas uncertain).
4. Optional: lazy-load pack constants so a bare `import h3re` does not need data/ present (it now opens rules.json and battle_policy.json).
5. Longer soak locally: `cd tools/h3re && python3 -m h3re.soak --games 200 --policy-matrix`.
6. Real-data work (needs the user): see below.

## Needs the user (cannot be verified without real data)
Legal HoMM3 install with `H3_DATA_DIR` set; real .h3m maps (RoE/AB/SoD); results of the rules.md section 9 experiments
(speed tie, wait order, bad-morale table, damage roll distribution).
