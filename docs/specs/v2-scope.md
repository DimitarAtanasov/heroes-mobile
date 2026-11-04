# v2 scope (DRAFT, not approved)

Status: draft proposal (2026-11-04). Nothing here is decided. Owner approval is needed, and
the open questions in section 6 must be answered before any slice starts. v1 scope itself
(`docs/specs/v1-scope.md`) is only on a local branch of the owner and is not approved either; v2
assumes v1 as defined by the checklist in `docs/checkpoints/HANDOFF.md` (Checkpoint 3).

## 1. Goal

v1 is a single skirmish battle on a phone, using the player's own game data. v2 makes the game
loop playable: **load a map, move a hero on the adventure map, visit a town, meet a creature
stack, fight it with the v1 battle screen, and come back to the map**, with save and resume.

The Kotlin engine already has all the cores (battle, adventure, encounter, town, hero, h3m)
with conformance vectors. The app exposes only battle. v2 is mostly **app and presenter work
over finished sim code**, plus the data and rules decisions that real maps will force.

## 2. In scope

| ID | Item | Builds on |
|---|---|---|
| V2-1 | Map import: the player's own `.h3m` by sideload, validated with the existing H3M reader | import flow (`GameDataStore`), `H3m.kt` |
| V2-2 | Adventure presenter: view of the map, hero, objects, fog; tap reducer for move and visit | `Adventure.kt`, presenter pattern of `present` |
| V2-3 | Adventure screen in `:app` (Compose): terrain from player's `H3sprite.lod` / `H3bitmap.lod`, hero marker, path preview | sprite loader, board geometry |
| V2-4 | Encounter hand-off: a hero meeting a stack builds a battle (`AdventureEncounterHooks`), plays the v1 battle screen, returns the outcome to the map | `Encounter.kt`, `BattleSession` |
| V2-5 | Town screen: build, recruit, visit as a hero | `Town.kt` |
| V2-6 | Hero screen: army, stats, move army between slots | `Hero.kt` |
| V2-7 | Adventure save and resume (replay file kind `"adventure"`) and Kotlin-to-Python verification | `replay.md`, A5-3 style CI check |
| V2-8 | Turn loop against a simple AI player (end turn, day roll-over) | `Adventure.kt` `EndTurn` |

## 3. Out of scope for v2

- Spells and magic (blocked on the `rules.md` section 9 experiments; battle stays spell-free).
- Multiplayer, campaigns, scripted events beyond what the h3m reader already parses.
- Editing maps, bundling any map or art (law 9: the player's files only).
- HD or other editions (Q3) unless the owner decides otherwise.
- A signed store release; v2 stays a sideload build unless Q1 is answered differently.

## 4. Preconditions from v1 (must be true first)

1. Device test of the CI APK recorded (runbook `docs/runbooks/device-test.md`); no screen has run on a phone.
2. Real-data run (`H3_DATA_DIR`, `python3 -m h3re real-report`) returns a clean report, including at least one real map.
3. Owner decisions that touch sim behaviour: bad-morale `(24,24,24)` freeze, ADR-0008 / ADR-0012 acceptance and the new input bounds, unbounded max damage.
4. `allowBackup` mismatch resolved (ADR-0013): adventure saves are bigger and more private.

## 5. Determinism and law impact

- No new sim rule is proposed, so no golden should move. Any hash change is a bug to find (law 6).
- Adventure constants still live in code (migration debt, law 4). **Move them to `data/*.json` before v2 balance work**, as a reviewed re-pin recorded in `docs/specs/adventure.md`.
- Real maps will exercise code paths the synthetic fixtures never reached. Expect Python-first fixes with re-generated vectors (ADR-0007), not Kotlin-only patches.
- New presenter code follows the sim bans (Kotlin lint). Floats stay in `:app` only.
- Known open parity gaps to close first: Kotlin `policyFrom` error text for a non-string `cost_from`; Kotlin throws at day 2^63-1 where Python continues; float repr not ported; h3m error text compared by class only.

## 6. Open questions for the owner

1. Is "adventure loop playable" the right v2? Alternatives: (a) polish and release v1 only, (b) spells first, (c) editions and HD data.
2. Which maps count as v2 targets: any SoD `.h3m`, or one named small map as the acceptance fixture?
3. Is a simple AI player enough, or is a stronger one wanted in v2?
4. Where do real-map findings go: extend `docs/checkpoints/real-data-findings.md`, or a new report?
5. App name and package id (still undecided; blocks any release).

## 7. Proposed slice order

1. Close v1 preconditions (section 4) and the parity gaps (section 5).
2. V2-1 map import, then V2-2 adventure presenter (Python-first vectors if the view needs new fields; view change moves no state hash).
3. V2-3 adventure screen with token graphics only, then real art.
4. V2-4 encounter hand-off (the riskiest join between two screens and two sessions).
5. V2-6 hero screen, V2-5 town screen.
6. V2-7 save and resume, V2-8 turn loop and AI.
7. Device test round, real-map run, performance pass (the frame budget of A10 applies to the larger map).

Each slice follows the repo process: spec-agent, then sim-engineer / presenter work with tests,
then determinism-auditor and test-verifier on a clean copy, and one PR per slice.

## 8. Acceptance (sketch, to be refined per slice)

- **V2-A.** Given a synthetic small map and seed, when a scripted hero walk, an encounter, a won battle and an end turn run through the presenter, then the final state hash equals the Python oracle's.
- **V2-B.** Given the same run recorded as an adventure replay by Kotlin, when `python3 -m h3re replay verify` runs, then it exits 0.
- **V2-C.** Given a real `.h3m` on the owner's machine (gated on `H3_DATA_DIR`), when the import runs, then it is accepted or refused with a named category, and never crashes.
- **V2-D.** On a device, a map can be opened, a hero moved, a stack fought and the app killed and resumed (manual script recorded in a checkpoint).
