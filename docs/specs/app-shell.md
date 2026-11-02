# App shell (milestone A7, MVP 0.1)

Status: draft v1 (2026-11-01). Implements the shell of `docs/specs/mvp-0.1.md` on top of
`android-app.md` sections 4, 5 and 9. Placeholder art only; no game assets (ADR-0010).

## Files (`android/app`)
| File | Role | Android imports |
|---|---|---|
| `Engine.kt` | `AppEngine`: `Battle`, `BattleCodec`, `BattleAi` from the three data packs (same wiring as the engine's scenario loader, public API only) | none |
| `Presets.kt` | 3 built-in skirmishes; writes the scenario JSON, its creature table coming from the bundled roster | none |
| `GameController.kt` | wraps `BattleSession` + `TapReducer`; produces immutable `GameUi` | none |
| `BoardView.kt` | Canvas board, tokens, tap to hex | yes (Compose, `android.graphics.Paint`) |
| `Screens.kt` | Home, Setup, Battle, Result, About composables | yes |
| `MainActivity.kt` | one activity, state-based navigation, asset loading, thread hop | yes |

The first three files are pure JVM so they can be compiled and run under `:presenter` tests.

## Screens and state flow
`Screen` = Home, Setup, Battle, Result, About, held in `remember` in `MainActivity.App()`.
No navigation library. The manifest sets `configChanges`, so rotation does not recreate the
activity and the running game survives.

- Home: New skirmish (disabled with an error line if the data packs failed to load), About.
- Setup: pick one of 3 presets (difficulty is only the preset) and a decimal seed (digits only,
  default 1). Start parses the scenario (`Scenario.parse`), builds a `GameController`, calls
  `start()` (queues `Begin`).
- Battle: status line, board, preview panel, Wait / Defend / Quit (Result once over), last 3 events.
- Result: winner (side 0 = you, the attacker), rounds, command count, final state hash.
- About: GPL-2.0-or-later notice, "not affiliated with the rights holders of Heroes of Might and
  Magic", "no game assets are bundled", source link text.

## Battle interaction
- The human plays the attacker (`Hex.ATTACKER`); the greedy AI plays the defender. The session runs
  the AI on its worker thread (`BattleSession.newWorker()`), `maxAiCommands` = 5000.
- Tap: `BoardGeometry.hitTestUnit` (either cell of a two-hex unit gives its head), else
  `hitTest`; the `HexCell` goes to `GameController.onTap` -> `TapReducer.reduce(TapEvent.Tap)`.
  First tap on a candidate hex = `Previewing` (damage floor/expected/ceiling and kills shown;
  several candidates are selectable); second tap on the same hex = `Confirmed` -> `session.submit(
  snapshot.seq, command, Origin.Human)`. `seq` is the snapshot's `seq`, which equals the log
  size, so a stale tap is answered with `Stale` and shown as a message. A Confirm button does the
  same as the second tap. Wait / Defend submit `BattleCommand.Wait/Defend(activeStack)`; the
  buttons are enabled only when `Battle.legalCommands` contains them.
- Highlights come from `legalCommands` (move heads green, attackable/shootable stacks red), the
  previewed hex has a yellow outline, the active stack a white one.
- Every accepted command (human or AI) resets the tap state to Idle.
- Tokens: filled circle in the side colour, first letter of the creature name (a leading
  "Test " is skipped, since every roster name starts with it), stack count below. Two-hex units
  are two circles joined by a thick line.

## Threading
`BattleSession` listeners run on the worker. `GameController` builds an immutable `GameUi` under a
lock and calls `onChange` outside it, possibly from the worker or the tap thread. `MainActivity`
posts it to the main `Handler`; a per-game `generation` counter drops posts from a closed game.
Only the main thread writes Compose state.

## Data packs
`app/build.gradle.kts` registers `copyH3Data`, which copies only `data/rules.json`,
`data/battle_policy.json`, `data/creatures.json` to `build/generated/h3assets`, added as an
assets source dir. Loaded with `assets.open` and `Datapack.load`. No tuning number lives in the app:
preset creature stats come from `creatures.json`; only stack counts, obstacles and colours are in code.
Colours, sizes and pixel math are UI floats; nothing float-valued reaches the engine (only `Int`
cells and presenter commands do).

## Dependencies
Added to `app/build.gradle.kts`: `project(":presenter")`, and BOM-managed (2024.10.01, no explicit
version) `compose.foundation`, `compose.ui`, `compose.runtime`. No experimental APIs.

## Verified here (JVM, `gradle --offline :sim:test :presenter:test`)
`Engine.kt`, `Presets.kt`, `GameController.kt` compiled and exercised by a throwaway test
(copied into `:presenter`'s test dir in a private copy, not committed): all 3 presets are
parsed, played by a driver using only `onTap` x2 / `onDefend`, and end with a winner and a
64-char hash; the tap path reaches `Previewing` after the first tap.

## Only CI can verify (`android-app` job)
`BoardView.kt`, `Screens.kt`, `MainActivity.kt`, the manifest, the Copy task and asset wiring
have never been compiled. First CI log: see the report of the milestone for the list of assumed
APIs. Not done: autosave/resume (A7 follow-up), replay export, animation, zoom/pan, long-press
card, accessibility.

## Menu and setup logic (h3.presenter.ui, slice A)
Pure logic in `:presenter`. Routes Home, Setup, Battle, Result, About. Legal edges: Home to Setup/About; Home to Battle only while an autosave exists (Continue); Setup to Battle; Battle to Result; Result to Setup. Back from any non-Home screen lands on Home; entering Battle drops Setup from the stack. Setup seed: ASCII digits only, 0..2^63-1, one error code per field; preset index default 0, preset count supplied by the app. These rules were chosen by the producer and await owner sign-off.

## App screens (Compose, loop app-screens)
Home shows New skirmish, Continue (enabled iff a usable autosave exists, MenuModel.continueEnabled), Load game (opens the save list) and About. Setup shows the preset list and a seed field; errors come from SetupForm via MenuText.setupFormMessage; Start is enabled only while SetupForm.isValid. The battle screen shows the board (sprites from the player's own data via the atlas when loaded, otherwise token plus letter), a roster with turn order, a round-grouped log, Wait, Defend, Save and Quit. Saves: autosave after every accepted command, manual saves, and a list from which the player picks an exact save; no import or export. All file I/O runs on the SaveFolderWriter thread. Sprites: SpriteLoader looks for the player's own game files under gamedata (noBackupFilesDir or filesDir) and builds an atlas via SpriteLoadPlan; the creature-to-DEF table is a placeholder (open decision G3); without data the token fallback is used.

## Game data (sideload only, for now)
Home has a Game data button. The Import screen shows whether the player's own game files under `noBackupFilesDir/gamedata` are Found, Missing or Changed (manifest.json, sizes only), validates a sideloaded set on Check again (GameDataCheck) and writes the manifest atomically. The copier (`GameDataStore.importFrom`) exists and is tested but has no UI source: there is no folder picker or drop folder until the owner says yes. Sprites load from `noBackupFilesDir/gamedata` only (not `filesDir`, which can go to cloud backup); a newly validated set is used at once: Check again reloads the board sprites (`SpriteReload.needed`), with no restart.
