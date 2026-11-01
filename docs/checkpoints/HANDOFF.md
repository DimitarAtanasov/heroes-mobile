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
