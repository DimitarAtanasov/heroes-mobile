# ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)

Status: proposed (2026-11-01). The owner accepts or amends it. Extends the "Project layout" of
ADR-0004. Amends `engine-design.md` 1.5 for Android (D5). Detailed in `docs/specs/android-app.md`.

## Context

ADR-0004 chose a native Android app with a Kotlin engine (`:sim`, done through `Battle.apply`)
and the Python code as the oracle. ADR-0007 made replay files and vectors the cross-language
contract. ADR-0010 made the project GPL-2.0-or-later and allowed VCMI's client design to be ported
with provenance. Still undecided: where the view-model and readers live, how user data enters the
device, how rendering and animation stay separate from the state, how threads hand off state, what
a save is, and how `:app` builds when the dev container cannot reach Google Maven.

## Decision

- **D1, four modules.** `:sim` (exists), `:data` (readers and content port), `:presenter`
  (port of `present.py`, the tap reducer, the animation timeline builder and `BattleSession`) and
  `:app` (Android, Compose). Dependencies point downward only: `:presenter` depends on `:sim`;
  `:data` depends on neither; only `:app` depends on all three. `:sim`, `:data` and `:presenter` are
  plain JVM modules, always built. Only `:app` is behind `-PwithApp=true`.
- **D2, purity boundary.** `:sim` and `:presenter` keep the simulation bans (no floats, clocks,
  threads, I/O, or hash-ordered iteration that reaches output). Floats exist only in `:app`
  (geometry, rendering, gestures). A command sent to the sim is always an element of the current
  view's command list, never something built from screen coordinates. `:data` readers take bytes
  through a `ByteSource`, not Android types.
- **D3, user data by copy.** The player picks their install with the Storage Access Framework. The
  needed files are copied into app-private no-backup storage, then validated with the `:data`
  readers. The tree permission is released after the copy. Game data, decoded sprites and caches
  are never bundled, never backed up, never exported, and never sent over the network. The battle
  roster comes only from the player's own `CRTRAITS.TXT` (amended 2026-11-03, see "Amendments"):
  without it the app shows only the import prompt where a new battle would start. Creatures without
  sprites are drawn as procedural tokens. No art of any kind is shipped.
- **D4, packs come from the repo's `data/`.** The `:app` build copies `data/*.json` into the APK
  assets at build time. Kotlin computes the pack content hashes itself, and those hashes must equal
  Python's. No balance number lives in app code. UI timing values live in one reviewed table and
  never enter a state.
- **D5, rendering.** Compose Canvas over a fixed 800x600 logical board space with one affine
  transform. DEF frames are pre-expanded to ARGB with the `def.md` alpha rules, plus an ALPHA_8 mask
  for the selection index, and packed into deterministic atlas pages. The disk cache is keyed by the
  SHA-256 of the source DEF and the decoder version. This replaces the palette-lookup shader of
  `engine-design.md` 1.5 on Android, because runtime shaders need API 33 and minSdk is 26. Shader
  palettes may return as an API 33+ optimisation that changes no output.
- **D6, animation outside the state.** A pure timeline (integer milliseconds) is built from the
  previous view and the events of one step. The board draws a display model derived from the view
  and the timeline. Skipping jumps to the end, and the display at the end equals the next view. The
  sim never waits for animation, and nothing derived from time reaches a command.
- **D7, threading.** A single sim worker thread owns the state, the battle stream and the command
  log. Input is a FIFO queue of `(expectedSeq, command, origin)`, and a submission against a stale
  sequence is rejected without effect. Immutable snapshots (seq, state, hash, view, events) go to
  the UI through flows. AI commands are computed on the worker and logged like human ones.
- **D8, saves are replays.** An autosave is a `replay.md` format-v1 file, written by the Kotlin
  port byte-identically to Python's `record`. It is written after every command by a separate I/O
  writer (coalescing, temp file, fsync, atomic rename, one `.bak`). Resume is `load` with full
  verification. A file that fails verification is kept and its reason shown, never deleted
  automatically.
- **D9, build.** AGP is applied only in `app/build.gradle.kts`. A version catalog pins versions.
  `minSdk` 26; `compileSdk` and `targetSdk` 35 until a store requires more. `:app` is built and
  unit-tested only on GitHub Actions (Google Maven reachable): assembleDebug, testDebugUnitTest and
  lintDebug, non-blocking until first green. Instrumented tests come later on an emulator job.
  Release signing reads environment variables only; no keystore or secret is in the repo.

## Why

- D1 and D2 keep every piece of logic that can be checked against Python on the JVM, where this
  container and CI can test it. Only drawing and platform glue need a device.
- D3: random access into LOD archives needs a seekable file, and many document providers give only
  streams. Copying also keeps the app working if the source folder goes away. Keeping derived data
  private follows CLAUDE.md laws 1 and 9.
- D5: minSdk 26 rules out runtime shaders. Pre-expanded atlases are simple and fast to draw, and
  they cost memory, which a budget controls (`android-app.md` 4.3).
- D6 to D8 make "the skip-animations path gives the same end hash as headless" (roadmap phase 6)
  follow from the structure: the state is a fold of `apply` over a log, and only the log is saved.
- D8 reuses a format that already has a verifier, error classes and a golden check, instead of
  adding a second save format.

## Alternatives considered

- Reading through SAF on every access (rejected: non-seekable providers, permission churn).
- One `:app` module with packages (rejected: the view-model and session could then use Android or
  floats, and could not be tested in the container).
- A palette shader through OpenGL ES instead of Compose (rejected for the MVP: a second rendering
  stack; may be revisited for the adventure map's palette cycling).
- A separate save format with a state snapshot (rejected: a second canonical format to keep in step;
  replay from the log is cheap for battles).

## Consequences

- `sim-engineer`: ports the presenter, session, packs, scenario, replay and readers, each with a
  Python-generated vector set (`presenter.json`, `replay.json`, `formats.json`) and a
  `conformance.md` section in the same change (ADR-0007).
- Python owner: view v2 (row offset, move paths, creature card stats, kill range) lands in
  `present.py` and `presenter.md` first, as `VIEW_VERSION` 2. It moves no state hash.
- `determinism-auditor`: reviews `:presenter` like a sim module. It confirms that no float or clock
  value reaches a command, and that the Kotlin banned-API check covers `android/sim` and
  `android/presenter`.
- `test-verifier`: quotes the output of the JVM tasks, `python3 -m h3re.vectors --check`, the
  Kotlin-to-Python replay check and the CI `android-app` job. Device-only criteria are marked as
  such in `android-app.md` section 9 and are not claimed without device output.
- `adr-scribe`: adds a cross-reference from ADR-0004 "Project layout" and from `engine-design.md`
  1.5 (palette shader) to this ADR.

## Amendments

- **D3, 2026-11-03 (owner decision, Q2 of `roster-from-crtraits.md`).** The synthetic
  `data/creatures.json` roster is no longer a battle roster and there is no placeholder battle
  mode. When no `CRTRAITS.TXT` has been imported (no valid `H3bitmap.lod` holding it in the app's
  game-data folder), Home shows only the import prompt in place of "New skirmish". A file that the
  content loader refuses gives no roster either; the refusal names row, column and category, never
  file contents. `data/creatures.json` stays bundled as a fixture pack: it still feeds the pack
  hashes recorded in and checked against replay headers (`creatures_hash`), so saves made before
  and after this change load (Q8). Saves carry their own creature table and load without game
  data. Detailed in `android-app.md` 3.1 and 6.2 and in `roster-from-crtraits.md`.

## Verification

- `cd android && ./gradlew :sim:test :data:test :presenter:test` passes without `-PwithApp`.
- `./gradlew -q :presenter:dependencies --configuration runtimeClasspath` lists only `:sim` and the
  Kotlin stdlib; `:data` lists no project dependency.
- `grep -n "com.android" android/build.gradle.kts` returns nothing (AGP only in `app/`).
- `SkipEquivalenceTest` and `ReplayConformanceTest` pass (`android-app.md` A4-2, A5-2), and a
  Kotlin-written replay passes `python3 -m h3re replay verify` (A5-3).
- The CI `android-app` job runs assembleDebug, testDebugUnitTest and lintDebug with `-PwithApp=true`.
- `git ls-files | grep -Ei '\.(jks|keystore|lod|def|pcx|h3m|snd|vid)$'` returns nothing.
