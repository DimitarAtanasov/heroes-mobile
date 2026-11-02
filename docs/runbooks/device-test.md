# Runbook: smoke-test the debug app on a real Android phone

Purpose: find out whether the app installs, starts and plays a whole battle on a real phone, and send
back a result we can act on. **Nothing in this runbook has been run on a device by the project yet.**
The app has only been built by CI and exercised by JVM tests; every expectation below comes from
reading the code (`android/app/src/main/kotlin/h3/app/`) and `docs/specs/app-shell.md`, not from
watching it run. If the phone disagrees with this page, the phone is probably right: write down what
you saw. Estimated time: 30 minutes without game files, plus 15 for the optional sprite part.

You need an Android phone (Android 8.0 / API 26 or newer), a GitHub login that can open the
repository's Actions page, and a USB cable plus a computer with `adb` for the optional steps. Plain
install by tapping the file needs no computer. "adb" is Google's command-line tool that talks to a
phone over USB (part of "platform-tools").

## 1. Get the debug APK from CI

An APK is the Android install file. A "debug" build is the test build: it is not signed for the Play
Store and it allows the extra commands in section 7.

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

**Home.** Title "Heroes" and the version line "Prototype 0.1 (placeholder art)". Four buttons:

* **New skirmish**: goes to Setup. (Greyed out, with a red "Could not load the data packs" line, only if the built-in rules files failed to load. That would be a bug: report it.)
* **Continue**: greyed out unless a usable autosave exists. Tapping it resumes the most recent battle at the exact position you left.
* **Load game**: opens the Saves list.
* **About**: licence text, "no game assets are bundled", a source link text.

**Setup.** Heading "New skirmish". Three presets, tapped like radio buttons: Easy (outnumber them),
Normal (even match), Hard (outgunned, the enemy has a two-hex Brute). One is selected on entry.
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

* The board is a hex grid. Each unit is a filled circle in its side colour with a letter (P, S, G, B) and the stack size under it. Two-hex units (Brute) are two circles joined by a thick line. Rocks are obstacles. If the game files are not installed this letter-token look is the normal and correct look.
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
| 1 | Open the app for the first time | Home with four buttons; Continue greyed out; version line shows "Prototype 0.1 (placeholder art)" | Time to open; any flash or blank screen | |
| 2 | Tap About, then Back | Licence text readable and scrolls; Back returns Home | Text cut off at the edges? | |
| 3 | Tap Load game | "No saves yet."; Save now greyed out with "There is no running game to save."; Back returns Home | | |
| 4 | New skirmish, clear the seed field | "Enter a seed." and Start battle greyed out | | |
| 5 | Type `12a`, then `99999999999999999999` | The digits-only message, then the too-large message; Start still greyed out | Does the on-screen keyboard offer a number pad? | |
| 6 | Seed `1`, preset Normal, Start battle | Battle screen opens; board shows 3 blue and 3 purple stacks plus 4 rocks; status says whose turn | Does the whole board fit on screen with no scrolling? | |
| 7 | Tap a green hex once | Preview card appears with "Move here"; yellow outline; nothing else changes | | |
| 8 | Tap the same hex again | Your stack moves; computer replies; status returns to "your turn"; log has new lines at the top | Any delay over about 2 seconds | |
| 9 | Tap a red enemy unit once | Card shows damage and kills numbers; Cancel closes it without playing | Numbers sane (min <= expected <= max)? | |
| 10 | Tap Defend, then on a later turn Wait | Each ends your turn; the log says so | Is Wait ever greyed out when it should work, or the reverse? | |
| 11 | Tap Save, then Save now, then Back | "Game saved."; a "Manual save 1" row appears; Back returns to the same battle position | | |
| 12 | Play on until "Battle over", tap Result | Result screen with Victory or Defeat, stack tallies and a hash | Write down the hash, preset and seed | |
| 13 | Play again, Normal, seed `1`, make the same first move | Same opening position as step 6 | Compare the roster and the first computer move with the first run | |
| 14 | Easy and Hard presets, each one move | Easy: you have about twice their numbers. Hard: a two-hex purple Brute | | |
| 15 | Play a battle to the end, then Home, then Load game | Autosave row present with its command count | | |

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
| R12 | **Two-hex unit.** Play the Hard preset until the purple Brute can be tapped | Tapping either circle of the Brute selects the whole unit | | |
| R13 | **Quit and re-enter.** Quit mid-battle, New skirmish, play a few moves, Quit, then Continue | Continue resumes the most recent battle, not an older one | | |

## 6. Sprites: what to expect

**With no game files (the normal case).** The board shows the letter tokens described above. This is
correct. The About screen says so too: "No game assets are bundled." Do nothing for this part.

**With your own game files (optional, debug builds only).** On start the app looks for your files in
its private storage, under `gamedata` (in `no_backup/gamedata/`, or `files/gamedata/`). It looks for
`H3sprite.lod` (and optionally `H3ab_spr.lod`) either in a `Data` folder there or directly in it,
ignoring letter case. If it finds one it tries to draw real sprites for the creatures it has a
placeholder mapping for, and it quietly keeps tokens for anything it cannot load. The app has no
import screen yet, so you copy the files by hand.

Your game files stay yours: they never go into the repo, an issue or a screenshot (laws 1 and 9 in
`CLAUDE.md`). Do these steps only with a copy you own.

1. Put the `Data` folder (containing `H3sprite.lod`, `H3ab_spr.lod` if you have it) next to you on the computer.
2. Push it to a place any app can read: `adb push Data /data/local/tmp/Data`
3. Copy it into the app's private folder. The `run-as` command lets adb act as the app, and only works on debug builds:

   ```
   adb shell run-as h3.app mkdir -p no_backup/gamedata
   adb shell run-as h3.app cp -r /data/local/tmp/Data no_backup/gamedata/Data
   adb shell run-as h3.app ls -l no_backup/gamedata/Data
   ```

   The last line must list your `.lod` files with their sizes. If `cp` says "Permission denied" for
   `/data/local/tmp` on your phone, tell us the phone and Android version; that is exactly the kind of
   thing this runbook is for.
4. Clean up the shared copy: `adb shell rm -r /data/local/tmp/Data`
5. Force-stop and reopen the app (`adb shell am force-stop h3.app`). Sprites are read once, at app start, on a background thread, so give it a few seconds after the first open before you start a battle.

**Status: unverified.** The `run-as` copy, the folder location and the loader have never been tried
on a real device. The creature-to-picture table is a placeholder with three guessed file names
(`docs/runbooks/real-data-check.md` lists the related findings), so a missing sprite may be the guess
being wrong, not a bug in the app.

What to look for:

| # | Check | Expected | Pass / Fail |
|---|---|---|---|
| S1 | Start Normal. Look at the Test Pikeman (P), Test Slinger (S) and Test Glider (G) units | They show a picture of a creature instead of a circle with a letter | |
| S2 | Start Hard. Look at the Test Brute (B) | **Still a token.** The Brute has no mapping, so a letter is correct. If the Brute shows a picture, note it | |
| S3 | Soft edges and shadows | Edges blend smoothly into the board. Shadows are a light, see-through grey. **Not** a hard dark outline, a black halo or visibly too-dark patches | |
| S4 | Counts and colours | Stack counts are still readable; you can still tell blue units from purple ones | |
| S5 | Everything else | Moving, previewing, saving and rotating still behave exactly as in sections 4 and 5 with sprites on | |

S3 is the "premultiplied pixel" check. Pictures on a phone store each pixel's colour already scaled by
its transparency. If that scaling were applied twice, every half-transparent pixel (the soft edge, the
shadow) would come out too dark. Looking for dark fringes and heavy shadows is how we catch it. The
code is written to avoid it, but only a real screen can confirm it.

If no sprites appear, that alone is a useful result. Send the phone model, Android version, and the
output of `adb shell run-as h3.app ls -lR no_backup/gamedata` (file names and sizes only, no contents).

To go back to tokens: `adb shell run-as h3.app rm -r no_backup/gamedata`, then force-stop and reopen.

## 7. Where the app keeps things (debug build)

| What | Where (inside the app's private storage) |
|---|---|
| Saves, including `.bak` backups | `files/saves/` |
| Your game files for sprites | `no_backup/gamedata/` |

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
* The checklist tables from sections 4 to 6 with Pass or Fail and your notes. A photo of a handwritten list is fine.
* For any Fail: the numbered steps you did, what you expected, what happened.
* For a crash: the `adb logcat` text from section 8.
* Screenshots of the placeholder (letter-token) screens are fine. **If sprites were on, send no screenshot or photo that shows the game's art.** Describe what you saw in words ("soft edge on the Pikeman looked dark, about like a black outline"). Never send `.lod` files, extracted files or the contents of `no_backup/gamedata`.
* Whether saves, Continue and the corrupt-save message behaved as in R5 to R9. These are the checks nothing else can do for us.

## 10. What this does NOT test

* **Balance.** Whether the presets are fun or fair, whether damage numbers feel right, whether the AI plays well. The stacks and creatures are synthetic placeholders; the numbers are not tuned.
* **Real maps and the adventure map.** Only the battle screen exists. No map is loaded.
* **Performance on low-end devices.** This is a quick feel on one phone, not a measurement of frame rate, memory or battery. Note "felt slow" if it did, but a proper test needs a profiler and a slow reference phone.
* **Real creatures and full art.** At most three placeholder pictures are checked, from a guessed mapping.
* **Sound, animations, zoom and pan, settings.** None are built yet.
* **Release builds.** This is the debug build only; the `run-as` steps do not work on a release build, and release signing is not covered.
* **The game rules themselves.** Rules are checked against the Python oracle by tests, not by hand here. Section 4 step 13 (same seed, same game) is a sanity check only.

## 11. What we do with each result

A crash or a Fail in R1 to R9 is fixed before anything else in the app. A Fail in R10 or R11 becomes
a layout fix. A sprite problem (S1 to S5) is handled like the findings in `real-data-check.md`: the
mapping table or the pixel handling is corrected in Kotlin with its test. Any fix goes through the
usual rules: a failing test first, the full suite, CI green, and no game data in the repo.
