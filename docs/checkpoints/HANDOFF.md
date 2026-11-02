# Handoff (resume here)

Branch `ccr-c70423ba-3alf1w`. PR #1 (merge b081922) and PR #2 (merge fa70b8a, checkpoints 53-64, skills, memory, loop tooling, APK CI)
are merged into `main`. Work since (Graphify index and later) continues on this branch, based on `main`. Open a
new PR for it; do not merge without the owner. License GPL-2.0-or-later (ADR-0010). Python is the oracle; Kotlin must
reproduce its hashes (ADR-0004, ADR-0007). Read `docs/memory/MEMORY.md` first, then this file.

Verify the state:
- Python: `python3 -m unittest discover -s tools/h3re/tests` (699 tests at checkpoint 64; slow, see below)
- `python3 tools/lint/banned_api_lint.py` and `python3 tools/lint/kotlin_banned_api_lint.py` (0 violations)
- `cd tools/h3re && python3 -m h3re.vectors --check`
- `cd android && gradle :sim:test` (111 Kotlin tests; Maven Central may answer HTTP 429: wait, retry, `--offline`)
- `python3 tools/skills/validate.py` (loops + strict criteria, run traces, skills, memory); `python3 tools/skills/loop_eval.py graph|run ...` is the deterministic judge
- Always verify from `git archive HEAD` plus only the owner's files (memory note clean-copy-verification).

## What exists
- Python reference engine: readers (LOD, DEF, PCX, TXT, H3M with objects), rules, battle, adventure, encounter,
  town, hero, replay files, presenter v2, content loader, determinism gate (soak, bisector, two lints), data packs.
- Kotlin `android/sim` (plain JVM): canonical JSON/SHA-256, PCG32, Rational, damage rules, hex, typed state +
  codec, `Battle.apply`, `legalCommands`, strike preview, greedy AI, presenter, datapack/LOD/PCX/DEF/TXT/content
  loaders. Every piece is proven equal to Python by generated vectors (about 20 MB in `android/sim/src/test/resources/vectors`).
- `android/app` is a 13-line stub. It builds only with `-PwithApp=true` and cannot be built in the dev container
  (dl.google.com is blocked); the CI job `android-app` builds it (non-blocking until green).

## CI facts (seen on GitHub, run for checkpoint 63)
- kotlin-sim: green. determinism (both lints + soak under two hash seeds): green.
- unittest: green but about 30 minutes. A test-speed task was started (memoise vector generation; keep every check).
- android-app: GREEN since 1a34df1 (two build-config fixes, see memory `android-gradle-setup`). The job is now
  blocking and uploads the debug APK as artifact `heroes-mobile-debug-apk` (run 41336051621: 8.4 MB). It is
  still the 13-line stub app. GitHub artifacts need a login to download.

## Loop tooling (done, commit 4dcc384)
`tools/skills/loop_eval.py` judges loops (S1-S4) and recorded runs (R1-R8); agents `loop-advisor` (opus),
`loop-producer` (opus), `loop-runner` (haiku) in `.claude/agents/`. The three agents have NOT yet been run on a
live task; only the evaluator is tested (41 tests, rule mutations killed). Try them on the next real round.

## In flight when this was saved (results are NOT in the repo until verified and committed)
Python suite speed-up, Kotlin scenario + replay port, board geometry + animation timeline (in :presenter), a read-only
audit of :presenter, and a `loop-graph` plugin being prepared for the owner's `sdlc-sandbix` repo (private copy in
/tmp/w_sdlc; nothing pushed there). Re-run `ListAgents`; if they are gone, redo the tasks from this list.

## Next, in order
1. (done) `:app:assembleDebug` is green in CI and the APK is uploaded. Next is real app code (see 3).
2. Cut the Python suite time: NOT started in the repo (the agent was stopped at the usage line and had produced no changes). The suite takes about 30 minutes on a runner because several tests regenerate the vector sets (present vectors alone ~130 s, plus `vectors --check`). Memoise generation per process and keep every check; the CI `kotlin-sim` job already runs `vectors --check`. Target under about 8 minutes.
3. 0.1 plan is `docs/specs/mvp-0.1.md`: `:presenter`/`BattleSession`, scenario and replay ports (a Kotlin replay must
   pass `python3 -m h3re replay verify`), app shell (screens, Compose board, hit-testing, tap reducer), autosave/resume,
   About screen. Then a device smoke test by the owner.
4. Rule decision for the owner: `bad_morale_table=(24,24,24)` makes every stack freeze forever so `Begin` never
   returns, in both engines (audit finding 3). Options: reject entries equal to `morale_die`, or cap consecutive freezes.
5. Python now refuses more input (`battle.check_state`, policy integer limits): the owner should confirm (ADR-0008 amendment).
6. Later: real sprites and the player's data import (needs Q2), adventure/town/hero/replay Kotlin ports, spells after
   the rules.md section 9 experiments, adventure constants into data (reviewed re-pin).

## Needs the owner
- App name and package id (not the game's trademark), whether a sideload debug APK is enough for 0.1.
- The three questions in `docs/specs/android-app.md` section 14 (channel, sprite mapping source, editions).
- Allow `nextwork.ai` in the session network settings if its project should inform the plan.
- Real game data (`H3_DATA_DIR`), real maps, and the rules.md section 9 experiments; nothing has run on real files.

## Wrap-up (checkpoint 72, usage 100%)
- Committed + pushed: 71 (Kotlin H3M reader), 72 (Kotlin adventure core). Python 742 tests OK; Kotlin sim 140 / presenter 76 OK.
- Branch `app-shell-ci` holds the uncompiled Compose app shell; CI run 86 pending. Read its log, fix errors, then merge into the working branch.
- Hero Kotlin port: producer agent a61be954a4a70e04c may still be running; verify in a clean copy (verify_clean, mutations M1-M5/V1, audit), wire `vectors_hero`, commit.
- Next: determinism audit of Adventure.kt/H3m.kt; adventure stage E (encounter/Attack); port encounter and town.
- Owner decisions open: bad-morale (24,24,24) rule, ADR-0008 amendment, ADR-0012 acceptance, sdlc-sandbix license, nextwork.ai network allow.

## Checkpoint 75 notes
- Adventure parity fixes (audit): policy ints bounded to 10000 and strict-int in Python (refuses more input than before: OWNER must confirm, ADR-0008 amendment in docs/specs/adventure.md s6); guard sort by code point; pyRepr ported. Adventure golden 179c5700 unchanged.
- Open parity gaps: Python accepts non-bool values in boolean policy fields (Kotlin refuses); EndTurn at Int.MAX day throws in Kotlin; float repr not ported; h3m error text compared by class only.
- Verified chain so far: 71 H3M, 72 adventure, 73 hero, 74 gzip cap, 75 adventure parity. App shell merged (CI green, APK built).

## Checkpoint 77
- 76: encounter + adventure stage E (Attack via AdventureEncounterHooks). 77: town core. All sim modules (battle, adventure, encounter, town, hero, h3m) now have Kotlin ports with conformance vectors; goldens unchanged.
- Remaining: dedupe create_battle (Scenario.kt private copy in Encounter.kt); real-data tests (H3_DATA_DIR); app UI beyond shell; owner decisions listed earlier.

## Checkpoint 82 (parity gaps closed)
- Python AdventurePolicy flags must be plain bools (refuses more input; owner to confirm with the ADR-0008 amendment); Kotlin adventure day is a Long (EndTurn at Int.MAX no longer throws; at 2^63-1 Kotlin throws where Python continues, documented); create_battle dedupe done. Goldens unchanged.
- Still open: Kotlin policyFrom gives "cost_from: expected string" for a non-string cost_from where Python says "bad cost_from" (not in policy_cases).

## Checkpoint 81 (2026-11-02)
- PR #3 merged (checkpoints 65-80). PR #4 (`feature/app-screens`) open: Compose screens wired; android-app builds the APK; no device test yet.
- In flight (agents, not committed): sprite loader (SpriteLoadPlan + SpriteLoader.kt; lead wires MainActivity sprites) and parity cleanup (bool policy fields, EndTurn max day, create_battle dedupe).
- Next: verify both in clean copies, commit on separate branches or PR #4 as appropriate; device smoke test by the owner; creature-to-DEF mapping decision (G3); real game data (`H3_DATA_DIR`).
- Owner decisions still open: bad-morale (24,24,24); ADR-0008/0012 acceptance and the new policy bounds; app-shell navigation defaults; broken-main-save overwrite rule; sdlc-sandbix license; nextwork.ai allow.

## Wrap-up (2026-11-02, usage 91%)
- On `main`: everything through PR #5 (screens, parity fixes, Kotlin ports). Open: PR #6 `feature/sprite-loader` (sprite loader; CI on the merged head not read yet).
- Branch `feature/game-data-import` (from main): loop contract `docs/loops/game-data-import.md` (passes evaluator). Owner decision: game data by sideload only, no picker.
- Owner order of work: (1) real game data, (2) import flow, (3) device test.
- (1) Real data: tool `python3 -m h3re real-report <data_dir>` (sanitized report) + runbook `docs/runbooks/real-data-check.md` were being built by an agent in /tmp/w_real; if not on a branch, rebuild: it is NOT committed. The owner must run it on their machine and send back report.json.
- (2) Import flow slices V (GameDataCheck), P (ImportPlan), U (GameDataStore + ImportScreen) were in flight in /tmp/w_sliceV, /tmp/w_sliceP (private copies, ephemeral). Anything not committed is lost: restart from the contract. Lead wiring still to do: Home Import button, drop `File(filesDir, "gamedata")` root in MainActivity.kt:54 (backup leak), cross-check test that SpriteLoader and ImportPlan name matching agree.
- (3) Device test: run the CI debug APK `heroes-mobile-debug-apk`; no screen has run on a device. Checklist still to write.
- Open owner decisions: bad-morale (24,24,24); ADR-0008/0012 acceptance incl. policy bounds and plain-bool flags; app-shell navigation defaults; broken-main-save overwrite rule; creature-to-DEF mapping (G3); sdlc-sandbix license; nextwork.ai allow; hd/edition support (G5).

## Checkpoint 83 (wrap-up, 91%+)
- Landed and verified: `real-report` tool + runbook (docs/runbooks/real-data-check.md; full Python suite 870 OK; a reversed-member-order mutation survived - minor test gap), GameDataCheck (V) and ImportPlan (P) in :presenter ui (presenter suite green, lead mutations caught).
- Not built yet: slice U (GameDataStore + ImportScreen), lead wiring (Home Import button, drop `File(filesDir, "gamedata")` in MainActivity.kt:54, cross-check SpriteLoader vs ImportPlan name matching), device-test checklist. ImportPlan mutants M22-M26 never ran.
- Owner next: run `python3 -m h3re real-report <your Data dir> --out report.json` on your machine and send report.json (see the runbook).

## Checkpoint 84 (import UI wired)
- Slice U (GameDataStore, ImportScreen, ImportText) landed and wired: Home Game data button, Screen.Import, SpriteLoader root only noBackupFilesDir/gamedata. Device runbook: docs/runbooks/device-test.md. Branch `feature/game-data-wiring`; :app verified by CI only.
- Law 10 mismatch for the owner: android-app.md says allowBackup="false" but the manifest has no such attribute, so files/saves (filesDir) can go to cloud backup. Decide: change the manifest or the spec.
- Still open: cross-check test that SpriteLoader and ImportPlan agree on name matching; sprites need an app restart after a new import; 3 surviving mutants in GameDataStore (non-atomic manifest write, no fsync, ignored recover failure: need a real crash to test); no Cancel in the import.
