# ADR-0013: Reconcile the Android app specs with the shipped code (five drift items)

Status: proposed (2026-11-02). The owner decides each item in the checklist at the end. Each item
that is accepted gets its own ADR (one decision per ADR); this file is the review record for all five.

## Context

Law 10 (`CLAUDE.md`) says that when code and spec disagree the disagreement is flagged and decided
in an ADR, and that neither side is edited silently. This ADR records five drifts found on
2026-11-02 by reading `docs/specs/android-app.md`, `docs/specs/app-shell.md`,
`docs/specs/presenter-geometry-timeline.md`, `docs/adr/ADR-0008`, `ADR-0011` and `ADR-0012`
against `android/` and `tools/h3re/`. Every line citation below was checked in the working tree.
The build floor is `minSdk = 26` and `targetSdk = 35` (`android/app/build.gradle.kts:23-24`).

**Item 1. Board geometry lives in `:presenter` and uses `Double`.** `android-app.md` section 2
(line 78) says `:presenter` has no floats, and section 2 rule 3 (line 89) and section 5.2 (line 349)
place `BoardGeometry` in `:app` as `h3.app.board.BoardGeometry`. The shipped class is
`h3.presenter.BoardGeometry` at `android/presenter/src/main/kotlin/h3/presenter/BoardGeometry.kt`.
It declares `Pt(val x: Double, val y: Double)` (line 17), Double view and zoom fields (lines 40-46),
and `hitTest(x: Double, y: Double)` and `hitTestUnit` on Doubles (lines 94, 120, 138). The class
comment (lines 25-27) says the Double math is deliberate. `presenter-geometry-timeline.md` section 1
(line 6) and its note 6 (line 51) say the class is in `:presenter` "as asked", and line 20 sets a
"Float rule: pixel math is `Double`". So two specs disagree with each other. `ADR-0011` D2 (lines
22-24, proposed) says floats exist only in `:app`, and `android-app.md` line 79 agrees. The code
follows the newer geometry spec and conflicts with ADR-0011 D2. No Python lint covers Kotlin
`:presenter`, so nothing mechanical catches it.

**Item 2. Navigation is held in state, not Compose Navigation.** `android-app.md` section 6 says
"Single activity, Compose Navigation." (line 395) and lists `navigation-compose` among the
dependencies (line 507). `MainActivity.kt` says "state-based navigation (no navigation library)"
(line 31), declares `enum class Screen { Home, Setup, Battle, Result, About, Saves, Import }` (line
28), and holds it in `mutableStateOf(Screen.Home)` (line 85). No `navigation` artifact appears in any
`*.kts` or `*.toml` under `android/`. The `NavigationTest` named in `android-app.md` line 631 does not
exist (`find android -name "NavigationTest*"` returns nothing).

**Item 3. Backup is not disabled.** `android-app.md` section 3.1 (lines 104-106) says the manifest
sets `android:allowBackup="false"` and data-extraction rules that exclude the app data. The manifest
(`android/app/src/main/AndroidManifest.xml`) has an `<application>` element with a label and theme
and no `allowBackup`, no `fullBackupContent` and no `dataExtractionRules`. There is no
`android/app/src/main/res/xml/`. Android's default is backup-enabled. The exposure is narrower than
the spec implies. Game data is copied to `noBackupFilesDir/gamedata` (`MainActivity.kt:51`, `:58`;
`GameDataStore.kt:25`), which Android never backs up. Saves are written to `File(filesDir, "saves")`
(`MainActivity.kt:55`, `SaveFiles.kt:34`), which is in the default backup set. So the saves are the
exposed data. Save files hold game state and the tests derive no game content from them, but
`ADR-0011` D3 says the app's data is "never backed up" (line 27 onward), and that sentence is broader
than the code.

**Item 4. `app-shell.md` describes a menu that differs from the shipped screens.** The spec's route
list (section "Menu and setup logic", line 81) is Home, Setup, Battle, Result, About. The code also
has `Saves` and `Import` (`MainActivity.kt:28`). Specific differences:
- Home. `app-shell.md` line 23 says Home has "New skirmish ... and About". The code (`MenuScreens.kt:19-25`)
  has New skirmish, Continue, Load game, Game data and About. The spec's own lines 83 and 87 list the
  extra buttons, so the spec contradicts itself.
- Back. Line 81 says "Back from any non-Home screen lands on Home". `MainActivity.kt:256` sends Save
  Back to `Screen.Battle` when a game is open. Result Home and Battle Quit (`MainActivity.kt:230`,
  `:235`) and Import Back to Home (`:200`) are legal edges missing from the spec's edge list.
- Continue. The code enables Continue when an autosave is `Ready` and no engine error exists
  (`MainActivity.kt:173-174`, `MenuScreens.kt:56`). The spec says "enabled iff a usable autosave
  exists" (line 84). These match. The brief's wording "whenever an autosave exists" is looser than the
  code and is not what the code does.
- Preset default. `SetupForm.kt:35` sets `presetIndex: Int = 0`. This matches the spec's default of
  index 0 (line 81).
- Screen file names. Line 13 says `Screens.kt` holds all Home, Setup, Battle, Result and About
  composables. The code has `MenuScreens.kt`, `BattleScreen.kt`, `ResultScreen.kt`, `SaveScreen.kt`,
  `ImportScreen.kt` and `Screens.kt`.
- The menu rules (Back, Continue, preset default) were chosen by the spec author and "await owner
  sign-off" (line 81). None is confirmed yet.

**Item 5. ADR-0008 amendments and ADR-0012 are not confirmed.** ADR-0008 has an amendment dated
2026-11-01 (lines 23-38) that caps derived products at `2**31-1` and says "Policy integers are
bounded to 0..2**31-1". The code matches the caps: `battle.py:158-159` bounds `defend_bonus_num`,
`defend_bonus_den`, `defend_bonus_min` and `range_penalty_beyond` to `0.._MAX_INT`, and
`battle.check_state` (line 508) enforces the caps that the ADR lists. Two points do not match:
- `battle.py:162` bounds each `placement_rows` entry to `_MIN_INT.._MAX_INT`, so negative values
  pass. The ADR says "0..2**31-1" for policy integers. Either the ADR or the code is wrong.
- The "policy integer bounds <= 10000" the owner asked about is not in ADR-0008. It is adventure
  policy: `adventure.py:96` defines `POLICY_INT_MAX = 10_000`, used at `adventure.py:165-166` for
  `pathfinding_flat`. The rule is recorded only in `docs/specs/adventure.md` section 6 (around line
  207) and in `docs/checkpoints/HANDOFF.md:68`, where it is marked "OWNER must confirm". The
  battle policy has no 10000 bound.
- Strict-int and plain-bool. `battle.py:76` says bools are not integers, and `battle.py:958` uses
  `type(c) is int`. The plain-bool rule for adventure flags is in `adventure.md` (second amendment)
  and `HANDOFF.md:77`. Neither is in ADR-0008. The owner has not confirmed them.
- `battle.check_state` refuses more input than before, and the owner has not confirmed that
  (`HANDOFF.md:50`).
- `ADR-0012` is still `Status: proposed` (line 3). `HANDOFF.md:65` and `:93` list its acceptance
  as an open owner decision.

## Decision

The owner chooses, per item, one of the options below. The recommendations are the adr-scribe's and
the spec-agent's; the owner's choice replaces them. Nothing in the specs, the manifest or the code is
changed by this ADR.

**Item 1 (geometry placement).**
- Option A (recommended): move `BoardGeometry` and its `Pt` to `:app` (`h3.app.board`), as
  `android-app.md` sections 2 and 5.2 say. `:presenter` keeps only `Int` cell types and the
  command-building reducer. Update `presenter-geometry-timeline.md` section 1 to match. Reason: it
  keeps the no-float rule of `ADR-0011` D2 for every module that feeds `:sim`, so the determinism
  auditor does not have to carve out an exception.
- Option B: keep `BoardGeometry` in `:presenter`. Amend `ADR-0011` D2 and `android-app.md` section 2
  line 78 to allow `Double` in one named geometry class, under the rule already in
  `presenter-geometry-timeline.md` line 20 (no pixel value reaches a command, state or hash). The
  determinism auditor must then check that rule on every `:presenter` change.

**Item 2 (navigation).**
- Option A (recommended): amend `android-app.md` section 6 to say state-held navigation (`enum class
  Screen` in `MainActivity`), remove `navigation-compose` from section 8's dependency list (line
  507), and remove the `NavigationTest` reference (line 631) or rename it to the test that really
  covers routes. Add the note that process death returns to Home; a game is recovered only through
  Continue, which reads the autosave.
- Option B: adopt Compose Navigation. This adds a dependency and a route migration. It is not needed
  for the current five screens.

**Item 3 (backup).**
- Option A (recommended): set `android:allowBackup="false"` on `<application>` in
  `AndroidManifest.xml`. This is honoured on every API level from 26 up, and no XML file is needed.
  It also disables Android 12+ device-to-device transfer and cloud backup. Saves stay on the device,
  which fits "never backed up" in `ADR-0011` D3.
- Option B: keep backup on and exclude the saves. This needs both files, because the two Android
  backup mechanisms read different attributes:
  - `android:fullBackupContent` (an XML file of `<exclude>` rules) governs Android 6 to 11 (API 23 to
    30). With `minSdk = 26`, it governs API 26 to 30.
  - `android:dataExtractionRules` (XML with `<cloud-backup>` and `<device-transfer>` sections) governs
    Android 12 and up (API 31+). The attribute is ignored below API 31.
  - Both files must exclude `saves/` under `filesDir`. The `gamedata` tree needs no rule because it
    lives in `noBackupFilesDir`.
- The spec's wording in section 3.1 must change under either option. Under option A, it says backup
  is off. Under option B, it says which paths are excluded and why.

**Item 4 (menu rules).**
- Option A (recommended): codify the shipped behaviour. Back from Save returns to the open game when
  one exists and to Home otherwise, and the spec's edge list gains Battle to Home (Quit), Result to
  Home, Save to Battle or Home, Import to Home and About to Home. Continue is enabled when an autosave
  is `Ready`. Default preset index stays 0. Update the screen list in `app-shell.md` line 13 and the
  Home description on line 23 so that they match the code and lines 83 and 87.
- Option B: keep "Back always lands on Home" and change `MainActivity.kt:256` to `Screen.Home`. This
  makes the save list drop the player out of a game in progress, so the player has to press Continue
  again.

**Item 5 (ADR-0008 amendments and ADR-0012).**
- ADR-0008 and battle code: option A (recommended) keeps the code and corrects the ADR text to say
  that `placement_rows` entries accept the full `Int` range (`_MIN_INT.._MAX_INT`). Option B
  tightens `battle.py:162` to `0.._MAX_INT` and re-checks the golden hash. Under option B, a change in
  the golden hash is a re-pin under law 6, not a silent edit.
- Adventure 10000 bound and plain-bool flags: record them in a new ADR, or cite them from ADR-0008,
  with the adventure spec as the owning reference. Do not leave them only in `HANDOFF.md`.
- ADR-0012 stays `proposed` until the owner accepts it. Its acceptance does not depend on items 1
  to 4.

## Consequences

- **Owner.** Confirms each item in the checklist. Until then the specs and code keep disagreeing, and
  the disagreement is recorded here rather than resolved in silence.
- **adr-scribe.** After a decision, writes one ADR per accepted item (one decision per ADR), updates the
  owning spec's cross-references, and records any golden re-pin under law 6 with the old and new
  values, the field or rule changed, and the reviewer. Does not edit specs without a decision.
- **spec-agent.** Rewrites `android-app.md` sections 2, 3.1, 6, 8 and the affected lines of
  `app-shell.md` and `presenter-geometry-timeline.md` only after the owner decides, and states the
  acceptance criteria for each rewritten rule.
- **sim-engineer.** Under item 5 option B for the battle placement rule, makes the code change with a
  test and a golden check. Under item 1 option A, moves `BoardGeometry` and its test to `:app` in one
  change. No `:sim` change is needed for any item.
- **determinism-auditor.** Under item 1 option B, must check every `:presenter` change for pixel
  values reaching a command, state or hash. Under item 3, confirms that saves are not reachable through
  backup when option A is chosen.
- **Android build.** Item 3 option A needs no new dependency. Option B adds two XML resources and
  must be checked on an API 26 device or emulator and an API 31+ device, because each attribute is
  read on different levels.

## Verification

- `python3 tools/skills/validate.py` passes with this file present.
- `grep -n "allowBackup" android/app/src/main/AndroidManifest.xml` shows `allowBackup="false"` after
  item 3 option A is applied (the owner decides whether it is applied).
- `grep -rn "Compose Navigation\|navigation-compose" docs/specs/android-app.md android` returns no
  matches for the spec or build files after item 2 option A.
- `grep -rn "Double" android/presenter/src/main/kotlin` returns no matches after item 1 option A, or
  matches only inside the one class named by item 1 option B.
- `python3 -m unittest discover -s tools/h3re/tests` still passes after any Python change under item 5,
  and `python3 -m h3re.vectors --check` still exits 0 with the golden hashes unchanged, unless a
  re-pin is recorded under law 6.
- Reviewer check: each accepted item has its own ADR with a status and a verification line, and the
  checklist below is ticked by the owner.

## Owner decisions

- [ ] Item 1: option A (move `BoardGeometry` to `:app`) or option B (allow `Double` in `:presenter`).
- [ ] Item 2: option A (state-held navigation, amend spec) or option B (adopt Compose Navigation).
- [ ] Item 3: option A (`allowBackup="false"`) or option B (keep backup, exclude `saves/` with both
      `fullBackupContent` for API 26 to 30 and `dataExtractionRules` for API 31+).
- [ ] Item 4: option A (codify the shipped menu rules) or option B (Back always lands on Home).
- [ ] Item 4: confirm Continue is enabled only when the autosave is `Ready`.
- [ ] Item 5: ADR-0008 placement-row bound: correct the ADR text (A) or tighten the code (B).
- [ ] Item 5: confirm the adventure policy bound of 10000 and the plain-bool flags, and record them in
      an ADR.
- [ ] Item 5: confirm the `battle.check_state` input refusals.
- [ ] Item 5: accept or amend ADR-0012.
