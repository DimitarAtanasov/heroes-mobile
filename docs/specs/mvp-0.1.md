# MVP 0.1: a playable skirmish APK

Status: proposed (2026-11-01). Scope decision for the owner. Source of truth for the milestones it
cites is `docs/specs/android-app.md` section 9. Assumes ADR-0004 (Kotlin engine, Python oracle) and ADR-0010 (GPL).

## Goal (one sentence, with its test)
A person installs a debug APK on an Android phone, starts a skirmish between two placeholder armies,
and plays a complete hex battle against the greedy AI by tapping (tap to preview damage, tap again to
confirm), and the battle ends with a winner screen.

Success test (verifiable, in order):
1. `./gradlew :sim:test` and the conformance vectors pass in CI (engine proven equal to Python).
2. CI builds `:app:assembleDebug` and uploads `app-debug.apk` as a build artifact.
3. On a device: install, start a skirmish, play to the end, kill the app mid-battle and relaunch to
   resume the same position (autosave), and the final state hash equals what the Python oracle gives
   for the same command log (`python3 -m h3re replay verify`).

## What 0.1 is, and is not
| In 0.1 | Not in 0.1 (and why) |
|---|---|
| Skirmish setup from the placeholder roster | Real creatures and sprites (needs the player's install, A6/A8/A9, Q2) |
| Hex board drawn with simple tokens, obstacles, two-hex units | The player's own game data import (0.2) |
| Tap to preview, tap to confirm, wait, defend | Adventure map, towns, heroes' growth (engine exists in Python; not ported) |
| Greedy AI opponent | Spells (every formula is uncertain; needs the rules experiments) |
| Autosave and resume; replay file | Sound, music, animation polish, accessibility pass (A10) |
| About screen with the GPL notice and the "not affiliated" statement | Store release (signing, store terms vs GPL, trademark review) |

Honest value statement: 0.1 is a playable prototype that proves the whole pipeline on a real phone.
It is not yet the game; the game needs the owner's own data and the sprite work in 0.2.

## What exists today (checkpoints up to 59, plus agents in flight)
| Milestone (android-app.md) | State |
|---|---|
| A0 build skeleton | CI jobs exist (`kotlin-sim`, `android-app`, non-blocking); `:data` and `:presenter` modules and the Kotlin lint are not committed yet |
| A1 legal commands, strike preview, AI | legal commands and previews done and pinned; Kotlin AI in flight |
| A2/A3 presenter v1 port and view v2 | in flight |
| A4 BattleSession, animation timeline, skip equivalence | not started |
| A5 packs, scenario and replay ports | Kotlin data-pack loader done; scenario and replay ports not started |
| A6 data readers | LOD, PCX, DEF, TXT and creature loader done in Kotlin; H3M not ported (not needed for 0.1) |
| A7 app shell, screens, board, hit-testing, reducer | not started; `:app` is a 13-line stub |
| A8 data import, A9 real sprites, A10 performance | not in 0.1 |
| A11 release readiness | only "About and licences" are needed for 0.1 |

## Remaining work for 0.1, in order
1. Finish what is in flight and commit it verified: Kotlin AI, presenter v2 and its port, the Kotlin
   lint, the audit fixes (overflow caps, policy and state strictness).
2. `:presenter` module and `BattleSession` (single worker thread, command queue, immutable snapshots),
   with the skip-animations equivalence test across the battle vectors. Verifiable here.
3. Scenario and replay ports (Kotlin writes a replay that `python3 -m h3re replay verify` accepts).
   Verifiable here.
4. App shell: routes (home, skirmish setup, battle, result, about), Compose Canvas board, hit-testing
   for one- and two-hex units, the tap reducer. Logic is testable on the JVM; building and running it
   needs CI or a device.
5. CI: make `android-app` build the debug APK and upload it as an artifact; remove `continue-on-error`
   once green. Then a manual smoke test on a device (the owner, or an emulator step in CI later).
6. Resume (autosave as a replay file with atomic rename), About screen with licences.

Rough size: this is several rounds of the kind just completed (a round is a batch of parallel agents plus
my verification), mostly in steps 2 to 5. That is an estimate, not a measurement; the first real build
of `:app` may surface unknowns.

## Decisions needed from the owner
1. App name and package id. Do not use the game's trademark in the name. (Proposal: a neutral name.)
2. Is a sideload debug APK from CI enough for 0.1? (Yes means no signing or store work yet.)
3. The three open questions in `android-app.md` section 14 (distribution channel, sprite mapping source,
   supported editions) can wait until 0.2.
4. Allow the `nextwork.ai` host in the session's network settings if its project should inform this plan.

## Risks specific to 0.1
- `:app` has never been built; Compose and Gradle version issues are likely on first CI build.
- Nothing has run on real game data, but 0.1 does not need any.
- Touch ergonomics are only provable on a device.
