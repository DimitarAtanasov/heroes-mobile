# Runbook: smoke-test the debug app on a real Android phone

Purpose: find out whether the app installs, starts and plays a whole battle on a real phone, and send
back a result we can act on. **Nothing in this runbook has been run on a device by the project yet.**
The app has only been built by CI and exercised by JVM tests; every expectation below comes from
reading the code (`android/app/src/main/kotlin/h3/app/`) and `docs/specs/app-shell.md`, not from
watching it run. If the phone disagrees with this page, the phone is probably right: write down what
you saw. Estimated time: 20 minutes for the install and the no-game-files checks, plus 30 for the
import and the battle checks.

The app has no built-in creatures. Battles use the creature table from **your own** game files, which
you copy onto the phone yourself (section 6). Nothing from the game is committed to the repository or
bundled in the APK. So this runbook has two phases: first what the app does with no game files, then
what it does after you import them.

You need an Android phone (Android 8.0 / API 26 or newer), a GitHub login that can open the
repository's Actions page, and your own copy of the game's `Data` folder. You also need a USB cable
and a computer with `adb`, because the import is by `adb` for now. Plain install by tapping the file
needs no computer. "adb" is Google's command-line tool that talks to a phone over USB (part of
"platform-tools").

## 1. Get the debug APK from CI

An APK is the Android install file. A "debug" build is the test build: it is not signed for the Play
Store and it allows the extra commands in sections 6 to 8.

1. Open the repository on GitHub, then the **Actions** tab, then the workflow **test**.
2. Pick the newest run on `main` whose job **android-app** has a green tick. Do not use a run where that job is red or skipped.
3. Open the run page and scroll to **Artifacts** at the bottom.
4. Download **heroes-mobile-debug-apk**. It is a `.zip` and needs a GitHub login. Artifacts expire after 14 days; if it is gone, ask for a fresh CI run.
5. Unzip it. Inside is one `.apk` file (usually `app-debug.apk`). Write down the run number and the commit shown on the run page: you will send them back.

## 2. Install it

| Way | Steps |
|---|---|
| On the phone | Copy the `.apk` to the phone (USB, cloud drive, email to yourself). Open it from a file manager. Android asks to allow installs from this source ("unknown sources" / "Install unknown apps"): allow it for that one app only, go back and tap **Install**. If Play Protect warns about an unrecognised app, choose **Install anyway**; this is expected for a debug build. |
| With adb | Phone: Settings, About phone, tap **Build number** 7 times, then Settings, Developer options, turn on **USB debugging**. Plug in and accept the prompt on the phone. On the computer: `adb devices` (the phone must be listed as `device`), then `adb install -r app-debug.apk`. `-r` means replace an existing install and keep its data. |

Pass: an app called **Heroes** appears in the launcher and opens. Fail: "App not installed", "Parse
error" or a crash on opening; note the exact words and see section 8.

To start from a clean state at any point: `adb uninstall h3.app` (removes the app and all its saves).

## 3. What each screen should do

Colours: you play **blue**, the computer plays **purple**. You are the attacker and move first
unless the speed order says otherwise.

**Home.** Title "Heroes" and the version line "Prototype 0.1 (placeholder art)". What it shows
depends on whether the app has a creature table from your game files (the "roster"):

* **No roster (a fresh install).** A card in place of "New skirmish" reads "Import your game data to play. Battles use the creatures from your own game files; nothing is bundled." with an **Import game data** button. Below it: **Continue**, **Load game** and **About**. There is no "New skirmish" button and no separate "Game data" button in this state; the card's button opens the same Game data screen. If your files were found but refused, a red line under the card's text says why in words (for example that the archive is not readable or has no creature table); it names rows and columns at most, never file contents. The app reads the roster at start on a background thread, so the card may show for a moment even when files are imported.
* **With a roster.** **New skirmish**, **Continue**, **Load game**, **Game data** and **About**.
* In both states a red "Could not load the data packs" line appears, and New skirmish and Load game are greyed out, only if the built-in rules files failed to load. That would be a bug: report it.

Buttons:

* **New skirmish**: goes to Setup. Only reachable with a roster.
* **Continue**: greyed out unless a usable autosave exists. It does not need a roster: a save carries its own creature table (ADR-0011 D3 amendment, Q8 in `docs/specs/roster-from-crtraits.md`). Tapping it resumes the most recent battle at the exact position you left.
* **Load game**: opens the Saves list. Also works with no roster.
* **Import game data** / **Game data**: opens the Game data screen (below).
* **About**: licence text, "no game assets are bundled", a source link text. Works with no roster.

**Game data.** Heading "Game data". A status line, then (after you tap Check again) the result of the
check, then a grey hint with the adb commands, then **Check again** and **Back**. The status line is one of:

| Status line | Meaning |
|---|---|
| "Checking game data..." | The first check is still running |
| "Game data found." | A record of a successful check exists and the files still match it |
| "Game data missing. The game runs with placeholder art." | No such record (nothing imported, or the check never succeeded) |
| "Game data changed since it was checked. Check it again." | The record exists but a file's size no longer matches it |

**Check again** validates the files already in the app's `gamedata` folder (section 6). On success the
result line reads "Game data is in place." followed by a small details line listing each file name and
size; on failure the sentences are in red, one per problem (for example "<file> was not found.", "<file>
is not a Heroes III archive.", "<file> is damaged. Copy it again from your install."), plus a details
line of file names and sizes. After a successful check the app reads the creature table and, if that
works, Home gains New skirmish.

**Setup.** Heading "New skirmish". Three presets, tapped like radio buttons, each named by creature
row in the app's code and filled in with the creatures from your own game files:

* Easy, "outnumber them": two stacks each; you field twice their numbers; 2 rocks.
* Normal, "even match": three stacks each, equal strength; 4 rocks.
* Hard, "outgunned": three stacks each; the enemy has more of every stack; 4 rocks.

The presets use creature rows 0, 2 and 4 of your game's creature table (Easy uses 0 and 2). There is
no special two-hex enemy any more; whether a stack is two hexes wide depends on your game's data. One
preset is selected on entry. A preset the creature table cannot supply is **blocked**: its card shows a
red line "Needs creature row N, not in your game's creatures" (N is the row number), or "Needs creature
row N, which has 0 hit points in your game's creatures", and **Start battle** stays greyed out while it
is selected. You can still pick another preset. Whether a row is present depends on your files (the
app leaves some creatures out of the table), so note which presets, if any, are blocked on your phone.
A **Seed** field takes digits only; the same seed with the same preset must give the same battle.
Errors appear in red under the field and **Start battle** is greyed out while one is showing:

| Type | Message |
|---|---|
| (empty field) | "Enter a seed." |
| `12a`, `-5`, `1.5`, a space | "The seed may only contain the digits 0 to 9." |
| `9223372036854775808` (one more than the limit) | "The seed is too large (the largest is 9223372036854775807)." |
| `1`, `0`, `9223372036854775807` | no message; Start battle is enabled |

**Back** returns Home.

**Battle** (top to bottom): a status line ("Round N - your turn" or "Round N - computer's turn"), a
"Turn order" line, the board, two panels side by side (roster of both sides with the active stack
highlighted, and a log with the newest line first), a hint or preview card, then buttons.

* The board is a hex grid. Each unit is a filled circle in its side colour with a letter and the stack size under it. Two-hex units are two circles joined by a thick line. Rocks are obstacles. Real pictures replace the circles only for creatures that have one (section 6); with the app as it is today, expect the letter-token look for every creature, and treat that as normal.
* Green hexes: where the active stack can move. Red units: ones it can attack or shoot. White outline: the active stack. Yellow outline: the hex you are previewing.
* **Tap to preview, tap again to confirm.** The first tap on a green hex or red unit does nothing to the game; it opens a card with "Move here", "Attack from here" or "Shoot" and, for attacks, "Damage: min / expected / max" and "Kills: min / expected / max". When one target can be attacked from several hexes, the card lists each as a radio choice. A second tap on the same hex, or the **Confirm** button, plays the move. **Cancel** closes the card with no effect.
* **Wait** and **Defend** only work on your turn and are greyed out otherwise (and Wait is greyed out when the game says it is not allowed, for example after a stack has already waited).
* After your move the computer plays by itself and the status line returns to "your turn".
* **Save** opens the Saves list for this running game (see below). **Quit** leaves the battle and returns Home; the autosave stays. When the battle ends the status reads "Battle over" and Quit is replaced by **Result**.
* A red line under the status ("The position changed; tap again.") means a tap arrived after the board changed. It is harmless; tap again.
* "The computer stopped (stalemate guard)" or "Engine fault: ..." are not expected in normal play. Screenshot and report.

**Result.** "Victory", "Defeat" or "Battle not finished", then a card per side (stacks standing,
survivors out of starting creatures, casualties), rounds, commands played, and a short state hash.
Write the hash down. **Play again** goes to Setup; **Home** goes Home.

**Saves.** A list, autosave first, then "Manual save 1", "Manual save 2" and so on. Each row shows the
title, the battle name, "Commands: N, rounds: M" and a short hash. Tap a good row to load exactly that
save. A row that cannot be loaded shows a red message instead and cannot be tapped. **Save now**
writes the next free manual slot and shows "Game saved."; it is greyed out when opened from Home
(with the note "There is no running game to save."). **Back** returns to the battle if you came from
one, otherwise Home. The autosave is written automatically after every accepted move; you never have to press anything for it.

## 4. Main checklist

Run these in order on one fresh install. Mark Pass or Fail, and write in "What to note" anything that
surprised you, even on a Pass.

| # | Do this | Expected | What to note | Pass / Fail |
|---|---|---|---|---|
Rows 1 to 5 are on a fresh install with **no game files**. Row 6 onward needs your files imported
(section 6); do the import at row 5.

| # | Do this | Expected | What to note | Pass / Fail |
|---|---|---|---|---|
| 1 | Open the app for the first time, with no game files | Home shows the import card ("Import your game data to play. ...") with an **Import game data** button, then Continue (greyed out), Load game and About. **No** New skirmish button. Version line shows "Prototype 0.1 (placeholder art)" | Time to open; any flash or blank screen | |
| 2 | Tap About, then Back | Licence text readable and scrolls; Back returns Home | Text cut off at the edges? | |
| 3 | Tap Load game | "No saves yet."; Save now greyed out with "There is no running game to save."; Back returns Home | | |
| 4 | Tap Import game data | Game data screen: "Game data missing. The game runs with placeholder art."; the adb hint is shown; Check again and Back. Tap Check again with nothing copied: red sentence(s) saying a file "was not found."; status stays "missing". Back returns Home | Exact wording of the red lines | |
| 5 | Do section 6 (copy your `Data` folder), then Check again | Result "Game data is in place." with file names and sizes; status "Game data found."; Back to Home: **New skirmish** and **Game data** now appear in place of the import card (a moment may pass while the table is read) | Time from Check again to New skirmish appearing. If red lines show instead, copy them | |
| 6 | New skirmish, clear the seed field | "Enter a seed." and Start battle greyed out | | |
| 7 | Type `12a`, then `99999999999999999999` | The digits-only message, then the too-large message; Start still greyed out | Does the on-screen keyboard offer a number pad? | |
| 8 | Look at the three preset cards | Each shows a title and one line of text. If any shows a red "Needs creature row N, not in your game's creatures" (or the "0 hit points" version), selecting it greys out Start battle and the others still work | Which presets, if any, are blocked, and which row number | |
| 9 | Seed `1`, preset Normal, Start battle | Battle screen opens; board shows 3 blue and 3 purple stacks plus 4 rocks; status says whose turn | Does the whole board fit on screen with no scrolling? | |
| 10 | Tap a green hex once | Preview card appears with "Move here"; yellow outline; nothing else changes | | |
| 11 | Tap the same hex again | Your stack moves; computer replies; status returns to "your turn"; log has new lines at the top | Any delay over about 2 seconds | |
| 12 | Tap a red enemy unit once | Card shows damage and kills numbers; Cancel closes it without playing | Numbers sane (min <= expected <= max)? | |
| 13 | Tap Defend, then on a later turn Wait | Each ends your turn; the log says so | Is Wait ever greyed out when it should work, or the reverse? | |
| 14 | Tap Save, then Save now, then Back | "Game saved."; a "Manual save 1" row appears; Back returns to the same battle position | | |
| 15 | Play on until "Battle over", tap Result | Result screen with Victory or Defeat, stack tallies and a hash | Write down the hash, preset and seed | |
| 16 | Play again, Normal, seed `1`, make the same first move | Same opening position as step 9 | Compare the roster and the first computer move with the first run | |
| 17 | Easy and Hard presets, each one move | Easy: two stacks each, you have about twice their numbers, 2 rocks. Hard: three stacks each, the enemy has more of every stack, 4 rocks. No two-hex enemy is promised | Stack counts you see versus these | |
| 18 | Play a battle to the end, then Home, then Load game | Autosave row present with its command count | | |
| 19 | Game data screen with files imported: Home, Game data | Status "Game data found." Tap Check again: "Game data is in place." again, status still found | | |
| 20 | Make the status change: with a battle not running, replace one imported `.lod` with a file of a different size (for example `adb shell run-as h3.app sh -c 'echo x >> no_backup/gamedata/Data/<name>'`, using a real name from `ls`), then Home, Game data | Status "Game data changed since it was checked. Check it again." Check again then either goes back to found (the file still validates) or shows a red sentence about that file; note which. Restore by copying the real file again and Check again | Exact lines shown | |
| 21 | Old save still loads. Make a save in a battle (row 14), then `adb shell run-as h3.app rm -r no_backup/gamedata`, force-stop, reopen | Home is back to the import card (no New skirmish), but Continue is still enabled and Load game still lists and loads the save. A save made before an import loads the same way | Anything greyed out or refused | |

## 5. Risk checks (the ones most likely to find real bugs)

Do each with a battle already under way (play 3 or 4 moves first). Write the position down before you
start: the round number, the roster counts and the last log line.

| # | Do this | Expected | What to note | Pass / Fail |
|---|---|---|---|---|
| R1 | **Rotate mid-battle.** Turn on auto-rotate, then rotate to landscape and back, twice | The game survives: same round, same units, same log. The layout is redrawn to fit. No restart, no jump to Home. Playing a move afterwards still works | Is the board usable in landscape (it may be small, that is a layout note, not a failure)? Did a preview card disappear? | |
| R2 | **Rotate while the computer is moving** (tap Confirm and rotate at once) | Still no crash; the computer's move shows up once, not twice | | |
| R3 | **Background and resume.** Press Home during your turn, wait 1 minute, open the app from recents | Same position, buttons still respond | Any blank frame or restart | |
| R4 | **Background for a long time.** Leave the app 15 to 30 minutes, with other apps used in between | Either it is exactly as you left it, or it restarted at Home and Continue brings the battle back (see R5). Never a corrupted board | Which of the two happened | |
| R5 | **Kill mid-battle, then Continue.** Make a move, then swipe the app away from recents (or `adb shell am force-stop h3.app`). Reopen | Home shows **Continue** enabled (it can take a moment to turn on while the saves are read). Tap it: you are back at the same round, same units, same counts and same log | If Continue is greyed out or the position is one move older. Write down exactly which move was lost | |
| R6 | **Kill, then Load game.** Same as R5 but use Load game and tap the Autosave row | Same position as Continue | | |
| R7 | **Pick an exact save.** In one battle, Save now at move A, play 3 more moves, Save now again. Quit, Load game, tap "Manual save 1" | Position matches move A, not the later one. Commands count in the list matches | | |
| R8 | **Corrupt save keeps the file.** Debug build only; needs adb. In a terminal: `adb shell run-as h3.app ls files/saves` to see the names, then `adb shell run-as h3.app sh -c 'echo junk > files/saves/<name of a manual save>'` (use the real name from `ls`). Reopen the app, Load game | The damaged row shows a red message naming the problem in words (for example "This save is not a readable game file. The file was kept.") and cannot be tapped. The other saves still load. No crash. `ls files/saves` still lists the damaged file afterwards (it is never deleted) | The exact message text | |
| R9 | **Damaged autosave and Continue.** Repeat R8 on the autosave file, then reopen | Continue is greyed out (no usable autosave) and Load game shows the message; New skirmish still works | | |
| R10 | **Tap targets on a narrow phone.** Best on a phone 360 dp wide (most 6-inch phones; Settings, Developer options, Smallest width, shows the number; do not change it). Use your thumb, not a fingertip | Every button is easy to hit the first time: Wait, Defend, Save, Quit, Confirm, Cancel, the preset cards, the radio buttons in the preview card, the save rows. A single hex of the board is the smallest target | Which targets you missed, and how often (for example "missed Cancel 3 of 10"). A hex that needs two tries counts as a note | |
| R11 | **The board fits.** Check on the narrowest phone you have | The whole board is visible on the Battle screen with nothing cut off at the left, right or under the bottom buttons; the buttons are not pushed off screen; status bar and the system gesture bar do not overlap controls | Screenshot of the Battle screen in portrait. Also try the largest font size in Android settings (Display, Font size) and note whether buttons get cut off | |
| R12 | **Two-hex unit (only if your game's data has one).** If any stack on the board is drawn as two circles joined by a line, tap it | Tapping either circle selects the whole unit. If no stack is two hexes wide in any preset, write "none" and skip | Which preset and row, if you can tell | |
| R13 | **Quit and re-enter.** Quit mid-battle, New skirmish, play a few moves, Quit, then Continue | Continue resumes the most recent battle, not an older one | | |
| R14 | **Roster after a restart.** With files imported, force-stop and reopen, and watch Home for a few seconds | Home may briefly show the import card, then New skirmish appears on its own without re-importing. It must not stay on the import card | How long it took | |

## 6. Import your game data, and sprites

**The rule.** You copy your own game files to the phone. They never go into the repo, an issue, a
pull request or a screenshot (laws 1 and 9 in `CLAUDE.md`). Do these steps only with a copy you own.
The app bundles no game files; it ships only its own rules and a column mapping.

**What the app needs.** A `Data` folder from a Complete or Shadow of Death install holding four
archives: `H3bitmap.lod`, `H3sprite.lod`, `H3ab_bmp.lod` and `H3ab_spr.lod` (letter case does not
matter). The HD Edition (`.pak` files) is not readable and the app says so. `H3bitmap.lod` must contain
the creature table, which is what gives you a roster. The app looks in its private storage, in
`no_backup/gamedata`, with the files either directly in it or inside a `Data` folder there.

There is no file picker and no in-app copy button yet. The **Game data** screen only checks files
already in that folder (this is the sideload route, debug builds only). The steps, which the Game data
screen also prints as its hint:

1. On the computer, have your `Data` folder ready.
2. Push it to a place any app can read: `adb push Data /data/local/tmp/Data`
3. Copy it into the app's private folder. `run-as` lets adb act as the app and only works on debug builds:

   ```
   adb shell run-as h3.app mkdir -p no_backup/gamedata/Data
   adb shell run-as h3.app cp -r /data/local/tmp/Data/. no_backup/gamedata/Data/
   adb shell run-as h3.app ls -l no_backup/gamedata/Data
   ```

   The last line must list your `.lod` files with their sizes. If `cp` says "Permission denied" for
   `/data/local/tmp` on your phone, tell us the phone and Android version; that is exactly the kind of
   thing this runbook is for.
4. Clean up the shared copy: `adb shell rm -r /data/local/tmp/Data`
5. In the app: Home, **Import game data** (or **Game data**), **Check again**. Expect "Game data is in
   place." and the status "Game data found." Then Back; Home should offer New skirmish.

Check again writes a small `manifest.json` into `gamedata` once every file passes; "found", "missing"
and "changed" are decided against it (section 3). If it fails, the red sentences name the file and the
problem; copy them and the details line into your report (they hold file names and sizes only).

**Status: unverified.** The `run-as` copy, the folder location and the loaders have never been tried
on a real device.

**Sprites: what to expect.** After a successful check, and again at every app start, the app reads the
creature table and then, if `H3sprite.lod` or `H3ab_spr.lod` is in `gamedata`, tries to draw pictures
on a background thread, so give it a few seconds before you start a battle. It quietly keeps the letter
tokens for anything it cannot draw. Read this carefully, because the code and the design notes differ:

* The design (ADR-0014, `docs/specs/sprite-atlas.md`) is to pick pictures by creature **row** from the table `data/sprite_map.json`.
* The code on `main` does not do that yet. The board still looks pictures up **by creature name** in a small built-in table of three placeholder names, and `sprite_map.json` is not bundled into the app or read by it (`MainActivity.kt` says the table "is still name-keyed ... until slice 5"). Names from your own game files do not match those three, so **expect letter tokens for every creature**, even with all four archives imported.
* If you do see a real picture on the board, that is a surprise worth a report: say which preset and which stack.

Per `CLAUDE.md` law 10 this mismatch is flagged here and not papered over: the sprite checks below are
written for what the code does today and need updating when the row-keyed table is wired in.

| # | Check | Expected | Pass / Fail |
|---|---|---|---|
| S1 | Files imported (row 5 passed). Start Normal and look at the stacks | Every stack is still a coloured circle with a letter and a count. No crash, no long freeze while the sprite thread runs | |
| S2 | Same battle, after waiting a minute | Still tokens; counts readable; you can tell blue from purple | |
| S3 | Remove only the sprite archives (`adb shell run-as h3.app rm no_backup/gamedata/Data/<H3sprite.lod name>`, using the real names from `ls`; do the same for `H3ab_spr.lod`), force-stop, reopen | Game data now reads "missing" (a file the record lists is gone). The creature table comes from `H3bitmap.lod`, so Home should still offer New skirmish and battles still start with tokens. Restore the files afterwards | |
| S4 | Everything else | Moving, previewing, saving and rotating still behave exactly as in sections 4 and 5 | |
| S5 | If a real picture does appear | Soft edges blend into the board; shadows are a light, see-through grey; **not** a hard dark outline, black halo or too-dark patches | |

S5 is the "premultiplied pixel" check. Pictures on a phone store each pixel's colour already scaled by
its transparency. If that scaling were applied twice, every half-transparent pixel (the soft edge, the
shadow) would come out too dark. The code is written to avoid it, but only a real screen can confirm
it, and only if a picture shows up at all.

If you want sprite data for us, send the phone model, Android version, and the output of
`adb shell run-as h3.app ls -lR no_backup/gamedata` (file names and sizes only, no contents).

To go back to a fresh state: `adb shell run-as h3.app rm -r no_backup/gamedata`, then force-stop and
reopen. Home returns to the import card; saves are kept.

## 7. Where the app keeps things (debug build)

| What | Where (inside the app's private storage) |
|---|---|
| Saves, including `.bak` backups | `files/saves/` |
| Your game files (creature table and sprites), plus `manifest.json` written by Check again | `no_backup/gamedata/` |

Read them with `adb shell run-as h3.app ls -l files/saves`. Other apps cannot see this folder, and it
is removed when you uninstall.

## 8. If the app crashes

1. Reproduce it once if you can, and note the last thing you tapped.
2. Straight after the crash, with the phone still plugged in:

   ```
   adb logcat -d -s AndroidRuntime
   ```

   `-d` prints what is already recorded and exits. Save the output to a text file. If it is empty, also try `adb logcat -d | tail -200` (on Windows, copy the last screen of output by hand). The log can contain your phone's name and app names; read it before sending and delete anything you do not want to share.
3. If there is no computer at hand, a screenshot of the Android "App keeps stopping" dialog and the steps are still useful.

## 9. What to send back

* Phone make and model, and the Android version (Settings, About phone). The screen size in dp, if you know it.
* The CI run number and commit shown on the run page, and how you installed (tap or adb).
* The checklist tables from sections 4 to 6 (including the Game data status you saw at each step) with Pass or Fail and your notes. A photo of a handwritten list is fine.
* For any Fail: the numbered steps you did, what you expected, what happened.
* For a crash: the `adb logcat` text from section 8.
* Screenshots of the letter-token screens are fine, but **crop or avoid anything that shows your game's creature names, numbers or art**: the creature table comes from your files. Refer to creatures by row number and describe what you saw in words. Never send `.lod` files, extracted files or the contents of `no_backup/gamedata`; the file names and sizes from `ls -l` are fine.
* Whether saves, Continue and the corrupt-save message behaved as in R5 to R9. These are the checks nothing else can do for us.

## 10. What this does NOT test

* **Balance.** Whether the presets are fun or fair, whether damage numbers feel right, whether the AI plays well. The stacks come from fixed creature rows and your game's table; the counts are not tuned.
* **Real maps and the adventure map.** Only the battle screen exists. No map is loaded.
* **Performance on low-end devices.** This is a quick feel on one phone, not a measurement of frame rate, memory or battery. Note "felt slow" if it did, but a proper test needs a profiler and a slow reference phone.
* **Real creatures and full art.** Pictures by creature row (ADR-0014) are not wired into the app yet, so sprites are only checked for "stays on tokens, no crash".
* **Import polish.** There is no file picker, no in-app copy and no progress bar yet; only the adb route and Check again.
* **Sound, animations, zoom and pan, settings.** None are built yet.
* **Release builds.** This is the debug build only; the `run-as` steps do not work on a release build, and release signing is not covered.
* **The game rules themselves.** Rules are checked against the Python oracle by tests, not by hand here. Section 4 step 16 (same seed, same game) is a sanity check only.

## 11. What we do with each result

A crash or a Fail in R1 to R9 is fixed before anything else in the app. A Fail in R10 or R11 becomes
a layout fix. A problem in the import or Game data checks (rows 4, 5, 19 to 21) is a Kotlin fix with its test. A sprite problem (S1 to S5) is handled like the findings in `real-data-check.md`: the
mapping table or the pixel handling is corrected in Kotlin with its test. Any fix goes through the
usual rules: a failing test first, the full suite, CI green, and no game data in the repo.
