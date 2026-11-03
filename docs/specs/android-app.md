# Android app design (`android/`)

Status: draft v1 (2026-11-01), written by `spec-agent`. The architecture decisions are recorded in
ADR-0011. This spec implements roadmap phase 6 of `engine-design.md` section 3 ("a battle is
playable on a device; the skip-animations path gives the same end hash as headless"), together
with sections 1.5 (presenter, rendering) and 1.6 (touch UI) of that file. It also implements the
Android parts of ADR-0004 (Kotlin engine, Python oracle, user data through the Storage Access
Framework), ADR-0007 (vectors are the contract), ADR-0008 (pack integers are `Int`) and ADR-0010
(GPL-2.0-or-later; VCMI client design may be studied and ported with provenance).

## 0. Problem statement

A player who owns HoMM3 should be able to point the app at their own install and play a hex battle
on a phone. The battle must be comfortable with a thumb and must run at 60 fps. The Kotlin engine
must give exactly the state hashes the Python oracle gives, whether animations play or are skipped.
This spec fixes the module boundaries, the data import, the rendering and input model, the screens,
the threading and save model, the build, and a milestone list. Each milestone is checkable by a
named test or command, and the milestones that can be verified without a device are marked.

## 1. Spec grounding and gaps

| Topic | Source this spec implements or touches |
|---|---|
| Layering and dependency direction | `engine-design.md` section 1 (layer table); ADR-0004 "Project layout" |
| Presenter, skip animations, rendering | `engine-design.md` 1.5; `presenter.md` sections 1-3 |
| Touch UI | `engine-design.md` 1.6 (tap-to-preview, petals, long-press, layout, autosave) |
| View-model contract | `presenter.md` (view v1, `candidate_commands`, `candidate_actions`) |
| Battle API, events, legality | `battle.md` section 1 (commands, events, `IllegalCommand` before any draw), sections 2, 3, 6, 7 |
| Scenario document | `battle-scenario.md` sections 1-5 |
| Saves and replays | `replay.md` (format v1, verification order, `.h3r`) |
| Cross-language contract | `conformance.md`; ADR-0007; ADR-0008; ADR-0009 |
| Packs and hashes | `datapack.md` ("Determinism and hash", "Battle policy pack", "Pack directory and rules hash"); ADR-0001; ADR-0006 |
| Readers | `lod.md`, `def.md` (special indices 0-7), `pcx.md`, `txt.md`, `h3m.md` (HotA 0x20 refused), `content.md` |
| Licence, data and provenance | CLAUDE.md laws 1 and 9; ADR-0003; ADR-0010 |

Spec gaps. These are not covered by any existing spec. This document does not invent rules for
them. Each one gets an owner and a milestone below.

- **G1, view v1 lacks fields the board needs.** `presenter.md` view v1 does not expose the row
  parity (`BattlePolicy.row_offset`), so a board cannot place hexes correctly under the `"odd"`
  policy. It also lacks the path to each reachable hex (needed for the path preview of
  `engine-design.md` 1.6), the creature attack, defense and damage range (needed for the info
  card), and the kill range of a preview (`rules.md` `damage_range`). The fix is a view v2
  (`VIEW_VERSION` 2), made in Python first (`present.py`, `presenter.md`, `test_present.py`) and then
  ported. See milestone A3.
- **G2, no spec for the event-to-animation timeline.** `engine-design.md` 1.5 only says one
  exists. Section 4.4 below specifies it as a UI-only construct.
- **G3, no creature-to-sprite mapping.** Nothing maps a creature to its battle DEF, missile DEF,
  obstacle sprites or battlefield background. The game keeps these names outside its text tables.
  The animation-timing table `CRANIM.TXT` has no format spec. This is open question Q2. It blocks
  real sprites (A9), not the MVP.
- **G4, Kotlin ports with no Kotlin-side spec section.** The datapack loader and hashes, the
  scenario loader, replay, content and the five readers have Python specs but no `conformance.md`
  sections yet. Each port adds its section (pattern of `conformance.md`) in the same change.
- **G5, edition-detection facts are unverified.** The HD Edition `.pak` files, the names of the
  expansion and HotA archives, and the marker members are in no spec. Section 3.3 cites VCMI
  evidence. The facts must be confirmed on a real install before the validator refuses anything
  on their basis.
- **G6, obstacle shapes and the battlefield are unspecified.** `battle.md` section 2 takes
  obstacles as a hex set and leaves placement to callers. The skirmish screen therefore generates
  obstacle hexes itself (section 6.2), and the MVP draws obstacles procedurally.
- **G7, no Kotlin determinism lint.** `tools/lint/banned_api_lint.py` covers Python only.
- **G8, palette shader versus minSdk 26.** `engine-design.md` 1.5 plans a palette-lookup shader.
  Compose runtime shaders need API 33, and the app's minSdk is 26. ADR-0011 D5 decides this for
  Android, and `engine-design.md` 1.5 needs a cross-reference (`adr-scribe`).
- **G9, no audio format spec.** Nothing specifies `.snd` archives or music. Audio is out of the
  MVP.

## 2. Module layout and dependency rules

Four Gradle modules under `android/`. Package roots: `h3.sim`, `h3.data`, `h3.presenter`,
`h3.app`.

| Module | Kind | Contents | May depend on | Must not depend on or use |
|---|---|---|---|---|
| `:sim` | Kotlin/JVM library (exists) | Canonical JSON and SHA-256, PCG32 and streams, `Rational`, `Rules`, `Hex`, `BattleState` and codec, `Battle.apply`, `legalCommands`, `strikePreview`; to add: strict JSON text parser (`h3.sim.json`, exact integers), pack loader and content hashes (`h3.sim.pack`), scenario loader (`h3.sim.scenario`), replay record/verify/load (`h3.sim.replay`), greedy AI (`h3.sim.ai`) | Kotlin stdlib, `java.math`, `java.security.MessageDigest` | any other module, Android, coroutines; floats, clocks, threads, file or network I/O, `java.util.Random`, iteration over hash-ordered collections that reaches state or events (CLAUDE.md laws 2-3) |
| `:data` | Kotlin/JVM library (new) | Ports of `lod.py`, `defimg.py` (decode and `to_rgba`), `pcx.py`, `txt.py`, `h3m.py`, `content.py`; typed `FormatError` hierarchy; a `ByteSource` interface (random access by offset and length) with in-memory and `FileChannel` implementations | Kotlin stdlib, `java.util.zip` (zlib, gzip), `java.nio.channels.FileChannel` | `:sim`, `:presenter`, Android, SAF types; floats in decoders |
| `:presenter` | Kotlin/JVM library (new) | Port of `present.py` (`view`, `viewJson`, `candidateCommands`, `candidateActions`); the tap/preview reducer (section 5.1); the animation timeline builder (section 4.4); `BattleSession` (command log, sequence numbers, snapshots; single-threaded, no clock) | `:sim`, Kotlin stdlib | `:data`, Android, coroutines; floats, clocks, threads, I/O (the same bans as `:sim`) |
| `:app` | Android application (stub exists) | Activity, Compose screens, navigation, board geometry and hit-testing (floats allowed), Canvas renderer, sprite atlas and disk cache, SAF import and validation, sim worker thread, autosave I/O, settings | `:sim`, `:data`, `:presenter`, AndroidX, Compose, kotlinx-coroutines | nothing may depend on `:app` |

Rules:

1. Dependencies point downward only, as in `engine-design.md` section 1. `:data` and `:sim` do not
   know each other. `:app` turns `:data` content records into a scenario document
   (`battle-scenario.md` section 2 shape), and the `:sim` scenario loader validates it.
2. `:sim`, `:data` and `:presenter` are plain JVM modules. They build and test without the Android
   Gradle plugin and without Google Maven, so they are always included in `settings.gradle.kts`.
   Only `:app` stays behind `-PwithApp=true`.
3. No floating point crosses from `:app` into `:presenter` or `:sim`. Hit-testing ends in an
   integer `(col, row)` or nothing. Commands are built only from entries of the view (that is,
   from `legalCommands`), never from screen coordinates.
4. Balance numbers enter Kotlin only through packs parsed from the repo's `data/*.json` (CLAUDE.md
   law 4). The `:app` build copies `data/rules.json`, `data/battle_policy.json`,
   `data/creatures.json` and the content mapping `data/txt_maps/crtraits.json` into the APK assets
   with a Gradle copy task, so the repo holds no second copy.
5. `:presenter` and `:sim` are covered by the Kotlin banned-API check of milestone A0 (G7).

## 3. Data import

### 3.1 Principles

- The app ships no game data. The player picks their own install. Copies, decoded sprites and
  caches stay in app-private storage on that device (CLAUDE.md laws 1 and 9; ADR-0004).
- Nothing derived from game data leaves the device on its own. App-private game data and caches
  are excluded from Android backup: they live under `noBackupFilesDir`, and the manifest sets
  `android:allowBackup="false"` plus data-extraction rules that exclude them. The app makes no
  network calls and sends no telemetry. Bug reports contain build ID, state hash and command
  count, and never file contents or images.
- The battle roster comes only from the player's own `CRTRAITS.TXT` (ADR-0011 D3, amended
  2026-11-03, owner decision Q2 of `roster-from-crtraits.md`). Without it, Home shows only the
  import prompt where "New skirmish" would be; there is no placeholder battle roster.
  `data/creatures.json` is still bundled, only as a fixture pack for the replay pack hashes
  (`creatures_hash`, unchanged so existing saves load). Saves carry their own creatures and still
  load without game data. Creatures without sprites are drawn as procedural tokens (section 4.6).
  No art is shipped.

### 3.2 Flow

1. **Explain.** The import screen says what is needed ("the folder that contains `Data`, from
   Heroes III Shadow of Death or Complete"), that files stay on the device, and roughly how much
   space the copy takes. A "Back" action returns to Home, which keeps showing the import prompt
   (3.1).
2. **Pick.** `ActivityResultContracts.OpenDocumentTree` (`ACTION_OPEN_DOCUMENT_TREE`). The user
   may pick the install root or the `Data` folder itself. Both are detected. On API 30+ the system
   picker refuses the storage root and the `Download` root, so the text tells the user to keep the
   game in a subfolder.
3. **Scan.** Through `DocumentsContract` children queries, names matched case-insensitively (as
   `lod.md` name rules). The scan finds `Data/`, and optionally `Maps/` and `MP3/`.
4. **Classify** the edition (3.3). An unsupported edition stops here with its message.
5. **Pre-flight.** The bytes needed are compared with `StorageManager.getAllocatableBytes`.
   `NotEnoughSpace` names both numbers.
6. **Copy** the required files (3.4) into `noBackupFilesDir/gamedata/`. Each file is streamed to a
   temp name with its SHA-256 computed on the fly, then renamed. The copy shows progress, can be
   cancelled (temp files are removed) and resumes per file.
7. **Validate** the copies (3.5).
8. **Record** `gamedata/manifest.json`: file names, sizes, SHA-256, detected edition, validator
   version, and an import time for display only.
9. **Release** the tree URI. The app does not keep a persistable permission, so it holds the
   least access. Re-import repeats the flow.

Why copy instead of reading through SAF each time: LOD and DEF access is random by offset
(`lod.md`), and many document providers (cloud, some USB) give only non-seekable streams. A
private copy is seekable, can be memory-mapped through `FileChannel`, and stays valid if the
source is removed. The cost is storage; the real sizes are measured in milestone A8.

### 3.3 Editions

Evidence, stated in our own words: VCMI `launcher/firstLaunch/firstlaunch_moc.cpp` (data-folder
validation) treats an LOD archive in `Data` whose name starts with `H3ab` as the mark of
Shadow-of-Death-compatible data, treats `.pak` files as the HD Edition (which it does not support),
and probes the members `GENRLTXT.TXT` (base game) and `TENTCOLR.TXT` (Shadow of Death). VCMI commit
`c53e0e85d4d280107661d65b42d88ea6ab6eb6ee`. Per ADR-0003 this is evidence, not proof (G5).

| Detected | Rule | Behaviour |
|---|---|---|
| Shadow of Death, Complete, GOG, non-HD Steam | base LODs plus `H3ab_*.lod` | supported |
| Restoration of Erathia or Armageddon's Blade only | base LODs, no `H3ab_*.lod` | MVP: refused with "not supported yet" (Q3). `content.md` already supports the RoE table variant, so support can follow later. |
| HD Edition | `.pak` files, no LODs | refused: "HD Edition files cannot be read. Pick a Complete or Shadow of Death install." |
| Horn of the Abyss on top of Complete | SoD set plus extra HotA archives (names to be confirmed, G5) | accepted. Only base and `H3ab` archives are copied. Notice: "Horn of the Abyss content is ignored. HotA maps cannot be opened." (`h3m.md`: format 0x20 is refused) |
| Demo, Chronicles, unknown | none of the above | refused with "unknown or unsupported version" |
| Localised install | header or encoding check of `CRTRAITS.TXT` fails | warning, plus an encoding choice in settings, marked experimental (`txt.md`; `vcmi-crosscheck-formats.md` #9). The `content.md` header check expects English header words, which is a risk (section 11). |

### 3.4 Files

| Path (case-insensitive) | Needed for | MVP |
|---|---|---|
| `Data/H3bitmap.lod` | `CRTRAITS.TXT` (`content.md`), `CRANIM.TXT` (G3), battlefield backgrounds and hex-cell overlays (PCX), UI bitmaps | required |
| `Data/H3sprite.lod` | creature battle DEFs, obstacle and projectile DEFs | required |
| `Data/H3ab_bmp.lod`, `Data/H3ab_spr.lod` | expansion creatures and bitmaps | required (SoD is the MVP edition) |
| `Maps/*.h3m` | adventure phase (section 6.4) | optional, offered after the MVP |
| sound archives (`*.snd`), `MP3/` | audio (G9) | not imported in the MVP |
| video (`*.vid`) | none | never imported |

The expansion file names are to be confirmed on a real install (G5). The background and overlay
member names VCMI uses (battlefield `CMBK*` images listed in `config/battlefields.json`, and the
cell outline and shade `CCELLGRD`/`CCELLSHD` in `client/battle/BattleFieldController.cpp`) are
evidence only.

### 3.5 Validation (first run and every import)

Each check runs with `:data` readers on the copies. Any reader exception becomes a typed import
error. Nothing crashes on hostile input (`engine-design.md` 1.1 "Errors").

| Check | Failure |
|---|---|
| V1 required files present | `MissingRequired(file)` |
| V2 each LOD parses: magic, directory bounds, entry bounds (`lod.md`) | `NotAnArchive(file)`, `CorruptArchive(file, detail)` |
| V3 required members present: `CRTRAITS.TXT`; once G3 is resolved also `CRANIM.TXT`, the mapped DEFs and one background | `MissingMember(archive, member)` |
| V4 decode: `CRTRAITS.TXT` through the content port (every row resolves; unknown ability texts are counted, not fatal, as in `content.md`); the header and first frame of each mapped DEF; one PCX | `CorruptMember(archive, member, detail)` |
| V5 deep check (optional, in settings): decompress every member | as V2/V4 |

Other errors: `NoGameFolder`, `HdEditionUnsupported`, `UnsupportedEdition(kind)`,
`UnreadableSource` (provider error), `NotEnoughSpace(needed, free)`, `Cancelled`. Each has one
user-facing sentence and a details string the user can copy. The details hold names and offsets,
never contents. The outcome is OK, OK with warnings (shown once, then kept in settings), or failed
(nothing is kept).

On every start, the app compares manifest sizes with the files (a cheap check). If game data has
disappeared or changed, the app has no battle roster (Home shows the import prompt, 3.1) and
shows a "Game data missing: re-import" banner. Battles and saves keep working, because a battle's state never depends on art
and a scenario carries its creature stats (`battle-scenario.md` section 2).

## 4. Rendering

### 4.1 Spaces and transform

- **Hex space:** `(col, row)` integers from the view.
- **Board space:** the 800x600 logical battle window of `engine-design.md` 1.5. Geometry facts
  (VCMI `client/battle/BattleFieldController.cpp`, `hexPositionLocal`): cells are 44 px apart
  horizontally and rows 42 px apart, a shifted row is offset 22 px to the right, and the first
  cell's box starts at (14, 86). The shifted parity comes from the view's row offset (G1). It is
  never hard-coded, and the default `"even"` matches VCMI (`battle.md` section 2).
- **Screen space:** one affine transform, `screen = board * scale + offset`. Its scale is
  "fit to the available rect" times the user's zoom (1x to 3x), and its offset comes from the pan.
  Float math happens only here, in `:app`.

### 4.2 Layers (drawn in this order each frame)

1. Background: a battlefield image (once G3 is resolved), else a flat terrain colour.
2. Hex grid: outline overlay (optional in settings) and playable or edge-column tint.
3. Highlights: reachable hexes (from `actions.by_hex` move entries), the preview path, the
   preview footprint, and the attack petals.
4. Obstacles.
5. Stacks, sorted by (row, col, stack id) so lower rows overlap upper ones. A two-hex stack sorts
   by its head. The attacker's sprites face right and the defender's face left; the left-facing
   sprite is a horizontal flip at draw time, not a second texture (the engine never turns stacks,
   `battle.md` section 2).
6. Count plates, the active-stack outline, and the defending marker.
7. Transient effects: luck, morale, damage numbers, projectiles.
8. Chrome (queue, action bar, panels) is ordinary Compose UI, not Canvas.

### 4.3 Sprites and atlas

- **Decode.** `:data` DEF decoder gives indexed frames. The `to_rgba` port applies `def.md`:
  indices 0, 1 and 4 always, 2 and 3 only near their reference colour, 6 and 7 as shadow. Index 5
  (selection) is left transparent in the colour image and goes into a separate ALPHA_8 mask. The
  renderer tints that mask to draw the active-stack outline.
- **Groups.** The DEF group meanings follow VCMI `client/battle/BattleConstants.h`
  (`ECreatureAnimType`), stated as facts: 0 moving, 1 mouse-over, 2 idle, 3 hit, 4 defend,
  5 death, 6 ranged death (optional), 7 and 8 turn, 11-13 melee attack up/front/down, 14-16 shoot
  up/front/down, 17-19 special, 20 and 21 move start/end. A missing optional group falls back:
  6 to 5, 20 and 21 to nothing.
- **Atlas.** The cropped frames of one creature are packed into pages of at most 2048x2048 by a
  deterministic shelf packer, sorted by (height descending, group, frame index). Each page becomes
  one `ImageBitmap`. Drawing uses `drawImage` with source and destination rects. Filtering is
  nearest at integer scales and bilinear otherwise (a setting).
- **Disk cache.** `noBackupFilesDir/sprite-cache/<sha256 of DEF bytes>-<decoder version>`, holding
  zlib-compressed RGBA pages, the masks and a JSON frame index. A missing or corrupt entry is
  rebuilt. Removing game data clears the cache. The cache is never exported.
- **Placement.** Sprite anchoring relative to a hex follows the VCMI study item
  `client/battle/BattleStacksController.cpp` (`getStackPositionAtHex`). It is ported with a
  provenance header (ADR-0010) or restated as facts in a cross-check entry, at milestone A9.
- **Memory budget.** Decoded sprite bitmaps are capped at 96 MB in an LRU by bytes. The working set
  of the current battle is pinned: at most 14 creature types, one background, obstacles and
  effects. `onTrimMemory` evicts everything outside the pinned set. The estimate is 2-8 MB of ARGB
  per creature, to be measured in A9. Total app PSS on the battle screen should stay at or below
  300 MB. A cold first load of a battle takes at most 3 s and a warm one at most 1 s on the
  reference device (assumption A1).
- **APK size.** At most 15 MB: code plus our JSON packs, with no art.

### 4.4 Animation timeline (UI only; closes G2)

- **Input:** the previous view, the events of one `apply` (`battle.md` section 1 list), and a
  timing table. **Output:** a list of clips `(startMs, durationMs, kind, stack, group, from, to)`
  with integer milliseconds. `:presenter` builds it as a pure function, with no clock.
- **Event mapping:**

  | Event | Clip |
  |---|---|
  | `Moved(stack, path)` | walk along the path, per hex (`MOVE_START`/`MOVE_END` groups if present); a flyer's path is `[dest]` (`battle.md` section 3), so it is one straight segment |
  | `DamageDealt` (melee) | attack group (up, front or down from the relative row of the target cell), then hit (3) or defend (4, if defending), then the count change |
  | `DamageDealt` (ranged) | shoot group, projectile (procedural until G3 is resolved), hit |
  | `UnitDied` | death group, then the last death frame held |
  | `LuckRolled`, `MoraleBoost`, `MoraleFrozen` | overlay effect |
  | `TurnStarted`, `RoundStarted` | outline pulse, round banner (short) |
  | `BattleEnded` | hand-off to the results screen |

- **Timing defaults.** Facts from VCMI `client/battle/CreatureAnimation.cpp`
  (`getCreatureAnimationSpeed`, `getAnimationSpeedFactor`): the base rate is 10 frames per second at
  the slowest setting, and a speed factor scales it. Per-creature walk, attack and idle times come
  from `CRANIM.TXT` (`lib/CCreatureHandler.cpp`, its loader). Our settings map to frame times of
  100, 67 and 33 ms (about 6, 4 and 2 frames at 60 Hz), plus "skip". These are UI tuning, not
  balance numbers. They live in one reviewed `UiTiming` table in `:app`, are overridden by the
  player's `CRANIM.TXT` values once G3 is resolved, and never enter a state or a hash.
- **Display model.** The board draws `display(prevView, clips, t)`: positions, counts, alive flags,
  group and frame for each stack. Invariant: `display(prevView, clips, end) == display(nextView)`
  on every displayed field. Skipping jumps `t` to `end`. A tap during a timeline fast-forwards it.
- **Independence.** The sim never waits for animation (`engine-design.md` 1.5). The timeline reads
  events and views only. No value computed from time, frames or the timeline reaches a command
  (section 2 rule 3). Animation therefore cannot change the state sequence.

### 4.5 Frame budget (60 fps)

- 16.7 ms per frame. UI-thread work for the battle draw should stay at or below 8 ms at the 95th
  percentile on the reference device.
- No allocation inside draw lambdas. The frame clock (`withFrameNanos`) is read only in the draw
  phase (`drawWithCache` or `drawBehind` reading a `State<Long>`), so animation never recomposes.
  The view model is rebuilt only when a new snapshot arrives.
- Views, previews and AI decisions are computed on the sim worker, never on the UI thread
  (section 7). Target: building a view takes at most 10 ms and an AI decision at most 50 ms on the
  reference device.
- At most 200 draw calls per frame (atlas pages make most sprites one call each).

### 4.6 Placeholder renderer

Used without game data and for CI screenshots. Each stack is a side-coloured hexagon token. The
two sides also differ by pattern, not only by colour. A token shows the creature's initials and
count, and a two-hex unit is a capsule over both cells. Obstacles are hatched hexes. It has the
same layers, timeline and hit-testing as the sprite renderer.

## 5. Touch interaction

### 5.1 Preview and confirm (pure reducer in `:presenter`)

The input is an integer hex, or a petal, or a global action. The reducer reads only the current
view (`candidate_actions`) and keeps a small UI state:
`Idle | Preview(entry, choice) | PetalPick(target) | Animating | NotMyTurn | Over`.

| In state | Input | Result |
|---|---|---|
| Idle | tap a hex with no `by_hex` entry | stays Idle, light feedback |
| Idle | tap a hex with only `move` | Preview(move): destination footprint, plus path once view v2 lands (G1) |
| Idle | tap any cell of an enemy with `shoot` | Preview(shoot): damage preview `floor`-`ceiling` and `expected` (and kills in v2); petals also shown as alternatives |
| Idle | tap an enemy with exactly one attack | Preview(that attack) |
| Idle | tap an enemy with several attacks | PetalPick: one petal per `attacks[].from_hex`, each labelled with its preview; the own-position petal (attack without moving), if present, is pre-highlighted |
| PetalPick | tap a petal | Preview(attack from that hex), with the attacker's footprint shown at `from_hex` |
| Preview | tap the same hex, or the same petal, again | submit the previewed command (section 7), subject to the confirm guard |
| Preview or PetalPick | tap another actionable hex | new preview for that hex |
| any preview | tap a non-actionable hex, back gesture, or Cancel | Idle |
| Animating | tap | fast-forward the timeline; no command |
| NotMyTurn or Over | tap | no command |

- The command sent is always the exact `command` dict of the previewed view entry. The reducer
  never builds a command from parts.
- **Confirm guard.** The second tap counts only if the preview has been on screen for at least
  150 ms (configurable, can be turned off). This keeps an accidental double-tap from committing.
  It changes only which input the player sends, not how a state evolves.
- **Double-tap.** Not bound to anything (it would collide with confirm).
- **Global actions.** Wait and Defend are buttons that use the same two-step rule (tap shows
  "Wait?", tap again sends). `Begin` is sent by the session when the battle screen opens.
- **Drag.** A drag that starts on the active stack's cells shows a ghost along the path. Releasing
  it gives the same Preview as tapping the release hex: a reachable hex gives a move preview, a
  petal hex next to an enemy gives that attack, and an enemy cell gives the petal nearest the
  release point (the "release hex is the direction" rule of `engine-design.md` 1.6; VCMI's
  swipe-to-attack setting, `client/battle/BattleFieldController.cpp`, is the precedent). A drag
  never commits by itself; the "commit on release" setting is off by default.
- **Long-press** (system long-press timeout). On a stack it opens the creature card in a bottom
  sheet: count, HP, top HP, speed, shots, morale, luck and flags from view v1, plus attack,
  defense and damage in v2. On a hex it shows hex info, and on a queue entry it highlights that
  stack. A long-press never changes the preview state, and nothing in the app needs hover.
- **Pan and zoom.** Pinch zooms from 1x to 3x of fit, around the focal point. Two fingers always
  pan. One finger pans only when zoomed in and only when the drag did not start on the active
  stack. A gesture that moves beyond the touch slop is never a tap. Pan and zoom keep the preview.

### 5.2 Hit-testing (`:app`, `h3.app.board.BoardGeometry`)

1. Apply the inverse of the screen transform to get board coordinates.
2. Take the candidate hexes in the two nearest rows, and pick the one whose centre is nearest. The
   point must lie within the hex polygon; otherwise the result is null. Ties break by (row, col),
   so the result is deterministic.
3. The priority of targets is: petal buttons (drawn at 48 dp or more, outside the board scale),
   then stack sprite bounds, then hexes. Sprite bounds take a tap only in hexes that have no
   action of their own, so a tall sprite never hides an empty reachable hex behind it.
4. A two-hex unit is hit on either cell. The grid cell gives the stack id
   (`grid.rows[r][c].stack`), and `candidate_actions` maps any cell to the head entry
   (`presenter.md` section 3).

### 5.3 Accessibility

- **Actions list.** A panel that works without the board lists the legal commands grouped by kind
  and target ("Wait", "Defend", "Move to column 5, row 3", "Attack Archers x20 from column 6,
  row 4: 12 to 18 damage"). It uses the same preview-then-confirm rule. A battle can be finished
  with TalkBack through this list alone (assumption A3).
- **Semantics and announcements.** The board exposes semantics nodes for stacks and actionable
  hexes, with labels and custom actions. Event results are announced through a polite live region.
- **Targets and colour.** Every chrome target is at least 48 dp. Text contrast is at least 4.5:1.
  Sides differ by pattern as well as colour. A high-contrast board option exists.
- **Text and motion.** Chrome text follows the font scale up to 200%. Count plates have a minimum
  size. When the system animator scale is 0, the app starts in skip mode.
- **Haptics.** Optional tick on preview and confirm.

### 5.4 Layout

- **Landscape** (battle default): the board fits the height. The turn queue is a strip along the
  top. The action rail (Wait, Defend, Actions list, Speed, Menu) is on the handed side (a
  left/right setting), in the lower half within thumb reach. The info and preview panel is on the
  other side.
- **Portrait** (supported): the board fits the width (pinch to zoom). The queue strip and preview
  panel sit below it, and the action bar is at the bottom. One-handed rule: every action that can
  commit is reachable in the lower 40% of the screen. Menu and settings go at the top because they
  are not critical (`engine-design.md` 1.6: no critical controls in corners a hand covers).
- **Insets.** `WindowInsets.safeDrawing` and display cutouts are respected. No tap target is placed
  in system gesture zones.
- **Rotation and window size.** Rotation keeps the session (ViewModel) and the preview state
  (saveable). Window size classes (compact, medium, expanded) cover tablets and foldables.
- **Other screens.** Town and hero screens (after the MVP) are portrait-first, as in
  `engine-design.md` 1.6.

## 6. Screens and navigation

Single activity, Compose Navigation.

### 6.1 MVP routes

| Route | Content |
|---|---|
| `home` | Continue (an unfinished autosave), New skirmish, Replays, Settings, About. If no `CRTRAITS.TXT` is imported, an "Import game data" prompt replaces New skirmish (3.1) |
| `import` | Section 3 flow, with a progress view and an error view (sentence, details, Retry or Pick another folder) |
| `skirmish` | Setup (6.2) |
| `battle/{session}` | Board, queue, action rail, preview panel, creature sheet, actions list, pause menu (Speed; Leave, which saves and exits. There is no Concede, because `battle.md` has no retreat or surrender) |
| `results/{session}` | Winner, survivors and casualties per side, rounds, a short final state hash (full on long-press), Watch replay, Export replay (SAF `ACTION_CREATE_DOCUMENT`), Rematch (same seed), New |
| `replays` | Import `.h3r` (SAF open), verify (`replay.md` section 4; errors are named), play with play, pause, step and speed controls |
| `settings` | Game data (re-import, deep check, remove, space used), animation speed (100/67/33 ms per frame, skip), confirm guard, handedness, orientation (auto, landscape, portrait), hex grid, damage preview, high contrast, haptics, text encoding (experimental), filtering |
| `about` | Licence (GPL-2.0-or-later text), source URL and build commit, third-party licences, the not-affiliated notice from `README.md` |

### 6.2 Skirmish setup

- **Roster source:** only "Your game's creatures": `CRTRAITS.TXT` from the imported
  `H3bitmap.lod`, through the content port, in file row order, without the no-fixed-damage
  creatures (`Content.battleRoster`; `roster-from-crtraits.md`). Each entry keeps its data-row
  index (the sprite key). The bundled `data/creatures.json` is not offered (ADR-0011 D3, amended
  2026-11-03). With no roster the Setup screen is not reachable; Home shows the import prompt.
  A roster note says: "Stats from your files. Abilities unverified." (`content.md`: the ability
  table is a placeholder and `hates` cannot be derived.)
- **Presets:** the built-in presets name creatures by data-row index, never by name (owner
  decision Q7). Default rows 0, 2 and 4 (to be confirmed by the owner). A preset whose row is not
  in the roster, or whose creature has 0 hit points (battle creation refuses hp 0), is shown
  disabled with its reason ("Needs creature row N, not in your game's creatures") and cannot
  start; nothing is substituted.
- **Each side:** 1-7 stacks with creature and count, plus morale and luck (`battle-scenario.md`
  section 3). Optional hero stats (section 4). Control: Human, AI, or both Human (hot seat).
- **Rules preset:** a policy preset from `battle-scenario.md` section 5. The default is the pack
  defaults.
- **Seed:** random from `java.security.SecureRandom` in `:app` (63-bit, non-negative), or entered.
  The seed is the only nondeterministic input, and it is recorded in the replay header.
- **Obstacles:** none, or "random". Random obstacles are drawn from
  `derive_stream(seed, "skirmish", battle_id)` at setup and written into the scenario's
  `obstacles` list. Replay then needs only the scenario, so this setup stream is UI-level, is not
  in the battle state, and has no Python mirror (G6).
- **Output:** a scenario document (`battle-scenario.md`) checked by the `:sim` scenario loader
  before the battle opens. Errors are shown per field.

### 6.3 Behaviour without data

Without an imported `CRTRAITS.TXT` there is no new battle: Home shows the import prompt (3.1).
Continue, Load game and About still work, because a save carries its own creature table; it plays
with placeholder art.

### 6.4 Phase after the MVP (outline only)

- B1: adventure map viewer for the player's own `.h3m` files (header, terrain and objects through
  the `h3m.md` port).
- B2: adventure play on the Kotlin port of `adventure.md` and `encounter.md`. A map battle reuses
  the battle screen.
- B3: town and hero screens (`town.md`, `hero.md`), portrait-first.
- B4: adventure saves. `replay.md` reserves kind `"adventure"`, and the format must be specified
  there first.

## 7. Threading, saves, replay and crash safety

### 7.1 Threads

- **Sim worker.** One thread, `h3-sim`, used as a coroutine dispatcher. It holds the only mutable
  references: the current `BattleState`, the `Pcg32` battle stream (`battle_rng(seed, battle_id)`)
  and the command log. No UI code calls `Battle.apply`, and no worker code touches Compose state.
- **Command queue.** A FIFO `Channel<Submission>` with
  `Submission(expectedSeq, command, origin = Human | Ai | Replay)`. The worker handles one
  submission at a time:
  1. If `expectedSeq != log.size`, it rejects the submission as `Stale`. The UI previewed an older
     snapshot. The state and stream are untouched.
  2. It calls `apply`. `IllegalCommand` is rejected without a state change or draw (`battle.md`
     section 1).
  3. On success it appends to the log, computes `stateHash`, builds the view (and v2 extras), and
     publishes a `Snapshot`.
- **Snapshots.** `Snapshot(seq, state, stateHash, view, events)` is immutable: read-only lists that
  are never mutated after construction (`SnapshotImmutabilityTest`). It is published on a
  `StateFlow` (the latest) and on a bounded `SharedFlow` of steps (for the animation queue). If more
  than 8 steps are waiting, their timelines are compressed.
- **AI.** When the active stack belongs to an AI side, the worker computes the AI command from the
  state (a pure function) and submits it to itself. AI commands go into the log like human ones,
  so a replay never re-runs the AI, and an AI change cannot break old saves.
- **Input gating.** The board accepts a confirm only when the newest snapshot is on screen and the
  active stack belongs to a human side.
- **Determinism argument.** The state sequence is the fold of `apply` over the log from the
  scenario and seed. The UI decides only which commands go into the log. Timing decides when, not
  what. So skip mode, any animation speed, rotation or process death all give the same hashes for
  the same log.

### 7.2 Saves (autosave on every command, as `engine-design.md` 1.6 requires)

- **Format.** A save is a replay file, format v1 (`replay.md`, kind `"battle"`), produced by the
  Kotlin `record` port byte for byte. There is no second save format.
- **Location.** `filesDir/saves/<battle_id>.h3r`, with the previous generation kept as `.h3r.bak`.
- **Writes.** A single I/O writer coroutine, separate from the sim worker, writes the newest log
  after each snapshot. Writes coalesce: the newest wins. Each write goes to a temp file, then
  fsync, then an atomic rename. If the process is killed, at most the last command is lost, and a
  file is either the old one or the new one.
- **Resume.** Resume is `load` (`replay.md` section 4): it checks the checksum and packs, replays
  every command and checks `final_hash`. On `Diverged` or `Mismatched*` (for example after an app
  update changed a pack) the file is kept and the reason is shown. It is never deleted
  automatically.
- **Process death.** The ViewModel's `SavedStateHandle` holds only the session id. The state is
  rebuilt from the autosave.
- **Shared replays.** Exported replays contain the scenario, so a battle with real creatures
  carries stats and names read from the player's files. The export dialog says so (section 11).

### 7.3 Crash safety

- An uncaught-exception handler writes a crash note to `filesDir/crash/` (stack trace, build
  commit, state hash, command count, no game data). The next start offers "copy report".
- Reader failures are contained per asset. A DEF that fails to decode falls back to its
  placeholder token with a notice, and never crashes the battle.
- Low memory is handled by evicting the sprite LRU (section 4.3).

## 8. Build and CI

- **Repositories.** The dev container cannot reach `dl.google.com`, so the Android Gradle plugin and
  AndroidX resolve only on GitHub Actions. The `withApp` gate in `settings.gradle.kts` stays.
  AGP is applied only in `app/build.gradle.kts`, never in the root `plugins {}` block, so JVM-only
  builds never need Google Maven.
- **Version catalog.** `android/gradle/libs.versions.toml` pins: Kotlin (2.0.21 today), AGP (8.7.3
  today), Compose BOM, activity-compose, lifecycle-viewmodel-compose, navigation-compose,
  kotlinx-coroutines, documentfile, and the test libraries (kotlin-test and JUnit 5 for JVM;
  Robolectric and Compose UI test for `:app`). Catalog entries resolve only when used.
- **SDK levels.** `minSdk` 26 (Android 8.0: native bitmap heap, `FileChannel` on SAF file
  descriptors). `compileSdk` and `targetSdk` 35 now; raise `targetSdk` to the store's required
  level before any store release. JDK 17 target for `:app`; `:sim` keeps toolchain 21.
- **Signing.** Debug builds use the AGP default debug keystore, which is generated per machine and
  never committed. Release signing reads `H3_RELEASE_KEYSTORE`, `H3_RELEASE_STORE_PASSWORD`,
  `H3_RELEASE_KEY_ALIAS` and `H3_RELEASE_KEY_PASSWORD` from the environment. When any of them is
  missing, the release APK is unsigned. `.gitignore` adds `*.jks`, `*.keystore`,
  `keystore.properties` and `local.properties`. A later release workflow uses GitHub encrypted
  secrets in a protected environment and never runs on `pull_request`.
- **Release build.** R8 minify on. An in-app About screen shows the GPL text, the source URL and the
  build commit (a build-config field). A dependency licence list ships with the app. Apache-2.0
  libraries are fine under "or later" (ADR-0010).
- **CI jobs** (`.github/workflows/test.yml` is owned by whoever edits CI; this is the plan):
  - `kotlin-sim` (exists): extend to `./gradlew --no-daemon :sim:test :data:test :presenter:test`,
    plus the Kotlin banned-API check and the cross-language replay check of A5.
  - `android-app` (exists, `continue-on-error: true`, assembleDebug only): extend to
    `./gradlew --no-daemon -PwithApp=true :app:assembleDebug :app:testDebugUnitTest :app:lintDebug`.
    Upload `app-debug.apk` and the reports. Remove `continue-on-error` once the job is green on the
    main line.
  - `android-instrumented` (later; `workflow_dispatch` and nightly): an emulator on a KVM runner
    (API 26 and one current level) running `:app:connectedDebugAndroidTest`. It covers the SAF
    import of a synthetic install tree pushed with adb (synthetic files only) and a battle smoke
    test. Frame-time benchmarks are not taken on emulators.
  - Real game data never reaches CI (law 9). Gated JVM tests in `:data` run when `H3_DATA_DIR` is
    set, locally or on the self-hosted `real-files` runner.

## 9. Milestones and acceptance criteria

Column "No device" means the milestone can be verified without a phone or emulator. "Here" means
in this dev container (JVM modules plus Python). "CI" means GitHub Actions only.

| ID | Scope | No device |
|---|---|---|
| A0 | Build skeleton: catalog, `:data` and `:presenter` modules, Kotlin banned-API check, CI extensions | here + CI |
| A1 | Kotlin `legalCommands` and `strikePreview` pinned, greedy AI (HANDOFF "Next" 1; in progress elsewhere) | here |
| A2 | Presenter v1 port | here |
| A3 | View v2 (Python first, then Kotlin) | here |
| A4 | `BattleSession`, timeline, skip equivalence | here |
| A5 | Packs, scenario and replay ports; Kotlin-to-Python replay check | here |
| A6 | `:data` readers and content port | here (gated real-file part local only) |
| A7 | App shell with placeholder units: screens, board, hit-testing, reducer | CI (Robolectric) + manual device smoke |
| A8 | Data import and validation | logic: CI; SAF: device or instrumented |
| A9 | Real sprites: atlas, cache, timing from `CRANIM.TXT` (needs Q2) | logic: here; visuals: device |
| A10 | Performance and accessibility pass | device only |
| A11 | Release readiness (signing, About, licences; Q1) | CI + owner |

Acceptance criteria (Given / When / Then; each names its check):

- **A0-1.** Given a clean checkout, when `cd android && ./gradlew :sim:test :data:test :presenter:test`
  runs without `-PwithApp`, then it passes and no repository other than Maven Central and the
  Gradle plugin portal is contacted (the `google()` gate in `settings.gradle.kts` is unchanged).
- **A0-2.** Given the `:presenter` and `:data` modules, when
  `./gradlew -q :presenter:dependencies --configuration runtimeClasspath` and the same for `:data`
  run, then `:presenter` lists only `project :sim` and the Kotlin stdlib, and `:data` lists no
  project.
- **A0-3.** Given the Kotlin banned-API check (G7; a script under `tools/lint/`, for example
  `kotlin_banned_api_lint.py`, scanning `android/sim` and `android/presenter` sources for
  `Float`/`Double`, float literals, `System.currentTimeMillis`/`nanoTime`, `java.util.Random`,
  `Thread`, `java.io`/`java.nio.file` and `HashMap`/`HashSet` iteration), when it runs, then it
  exits 0. A seeded violation in a test fixture makes it exit 1
  (`tools/h3re/tests/test_kotlin_lint.py`).
- **A0-4.** Given CI, when the `android-app` job runs the extended command of section 8, then it is
  green and `app-debug.apk` is uploaded.
- **A2-1.** Given a new Python vector file `presenter.json` (from `python3 -m h3re.vectors`, Python
  first per ADR-0007), holding the SHA-256 of `view_json` for every step of every
  `battle_states.json` case and the full text for a bounded sample of at most 20 steps, when
  `./gradlew :presenter:test --tests h3.presenter.ViewConformanceTest` runs, then Kotlin `viewJson`
  matches byte for byte. `python3 -m h3re.vectors --check` exits 0.
- **A2-2.** Given the same sampled steps and all 187 hexes, when `CandidateActionsTest` runs, then
  `candidateCommands` and `candidateActions` equal the Python lists recorded in `presenter.json`.
- **A2-3.** Given any recorded state, when `view` is called twice, then the results are equal and
  `stateHash` is unchanged (`ViewPurityTest`, mirroring `test_present.py`).
- **A3-1.** Given `presenter.md` updated to v2 (row offset, move paths, creature attack, defense and
  damage, preview kill range) with `VIEW_VERSION` 2, when
  `python3 -m unittest discover -s tools/h3re/tests` runs, then it passes, and
  `git diff -- android/sim/src/test/resources/vectors/battle_states.json` is empty (a view change
  moves no state hash, so there is no re-pin), and `presenter.json` is regenerated. A2-1 and A2-2
  then pass on v2.
- **A4-1.** Given the golden scenario (seed 12345, scripted chooser), when it is driven through
  `BattleSession` (`BattleSessionTest`), then the final hash equals the `final_hash` of the
  Python-recorded golden replay in the A5 vectors (`fbe9015b...`, `replay.md` section 6).
- **A4-2.** Given every `battle_states.json` case's command list, when `SkipEquivalenceTest` drives
  it (a) with timelines skipped, (b) played under a fake clock at every speed, (c) with frame-time
  jitter from a `Pcg32` stream, and (d) with taps injected during animations, then every per-step
  hash equals the recorded `sha256` in all modes.
- **A4-3.** Given a session at seq n, when a submission with `expectedSeq != n` arrives, then it is
  rejected as `Stale` and `stateHash` and the stream state are unchanged (`StaleCommandTest`).
- **A4-4.** Given every recorded step, when `TimelineEndStateTest` evaluates the display model at
  the end of the timeline, then it equals the display of the next view on every displayed field.
- **A4-5.** Given two AI sides, when the same scenario and seed run with animations skipped and at
  1x, then the command logs are identical (`AiTimingIndependenceTest`).
- **A5-1.** Given `data/rules.json`, `data/battle_policy.json` and `data/creatures.json`, when
  `PackHashTest` runs, then the Kotlin content hashes equal `packs.rules_hash` in
  `battle_states.json`, and the policy and creatures hashes equal the header values in a new
  `replay.json` vector.
- **A5-2.** Given the Python-recorded replays in `replay.json` (the golden one plus soak cases,
  and the error cases of `replay.md` section 4), when `ReplayConformanceTest` runs, then Kotlin
  `verify` accepts every valid file. Kotlin `record` of the same inputs is byte-identical. Every
  proper prefix raises `Truncated`, a flipped body byte raises `Tampered`, and each Python error
  class maps to one Kotlin error.
- **A5-3.** Given a replay written by a Kotlin JVM test to `android/sim/build/`, when CI runs
  `cd tools/h3re && python3 -m h3re replay verify <file>`, then the exit code is 0 (the
  cross-language direction Kotlin to Python).
- **A6-1.** Given a new Python vector file `formats.json` built from the synthetic fixtures of the
  Python reader tests (LOD, DEF in all formats including the legacy format-1 case, PCX in both
  modes, TXT, H3M header), when `./gradlew :data:test` runs, then the decoded outputs (indices,
  `to_rgba` bytes, tables, header fields) match, and every Python error case raises the matching
  `FormatError` subclass.
- **A6-2.** Given each fixture, when `HostileInputTest` applies 10 000 `Pcg32`-seeded byte
  mutations, then only `FormatError` subclasses are thrown (no other exception, no out-of-memory;
  the DEF pixel cap of `def.md` applies).
- **A6-3.** Given `H3_DATA_DIR` set locally, when `RealDataTest` runs, then every LOD lists, every
  required member decodes, and `CRTRAITS.TXT` resolves every row. The test prints counts only. It
  is skipped without the variable.
- **A7-1.** Given scales 0.5 to 4 and both row parities, when `BoardGeometryTest` (`:app` unit test)
  maps every hex centre to the screen and back, then it returns the same hex. Points on a shared
  edge resolve by the (row, col) tie rule, and points outside the grid give null.
- **A7-2.** Given the table of section 5.1, when `TapReducerTest` (`:presenter`) runs every row on
  recorded views, then the resulting state and any submitted command match the table. A
  submitted command is always an element of `legalCommands`.
- **A7-3.** Given CI, when `:app:testDebugUnitTest` runs Robolectric Compose tests
  (`NavigationTest`, `SkirmishSetupTest`, `ChromeTargetSizeTest` asserting at least 48 dp), then
  they pass. On a device: a placeholder battle can be played to the results screen (manual smoke
  test, recorded in the checkpoint).
- **A8-1.** Given synthetic install trees (synthetic LODs with the real file names and synthetic
  members), when `ImportValidatorTest` runs, then: SoD-like gives OK; a missing `H3sprite.lod` gives
  `MissingRequired`; `.pak` only gives `HdEditionUnsupported`; extra HotA-named archives give OK
  with the HotA notice and are not copied; a corrupt directory gives `CorruptArchive`; a missing
  `CRTRAITS.TXT` gives `MissingMember`; and a cancel during copy leaves no files.
- **A8-2.** On a device or emulator (`android-instrumented`, later): picking a synthetic tree
  through the system picker imports it and survives an app restart (`ImportFlowTest`).
- **A9-1.** Given `formats.json` DEF fixtures, when `AtlasBuilderTest` runs, then the packed layout
  is identical across runs, every frame's RGBA equals the Python `to_rgba`, and the index-5 mask
  marks exactly the index-5 pixels.
- **A9-2.** Given a corrupt or stale cache entry, when `SpriteCacheTest` loads it, then the entry is
  rebuilt from the DEF and the result equals a fresh decode.
- **A9-3.** Given `H3_DATA_DIR` locally, when `SpriteBudgetReport` runs, then it prints the decoded
  bytes per creature and confirms that a 14-creature working set fits 96 MB.
- **A10-1.** On the reference device (A1), `BattleFrameBenchmark` (Macrobenchmark, scripted replay
  at 1x for 60 s) gives a 95th-percentile frame time of at most 16.7 ms, at most 1% janky frames,
  and battle-screen PSS of at most 300 MB (`dumpsys meminfo`).
- **A10-2.** On a device with TalkBack, a battle can be finished through the Actions list only
  (manual script recorded in the checkpoint), and Accessibility Scanner reports no critical issue.

## 10. Determinism and purity impact

- **No change** to sim state, RNG streams, canonical form or any golden hash. No new state field.
  If a milestone moves a pinned hash, that is a bug (CLAUDE.md law 6, ADR-0001). The view v2
  change (A3) changes presenter output, which is versioned and not hashed, so it needs no re-pin.
- **RNG.** The battle uses the existing `battle:<battle_id>` stream only. The setup-only
  `skirmish` stream (6.2) produces scenario content and is never part of a state. The master seed
  comes from `SecureRandom` in `:app`, outside the sim, and is recorded in the replay header.
- **Floats** exist only in `:app` (geometry, rendering, gestures). None reaches a command
  (section 2 rule 3). `:presenter` follows the sim bans (A0-3).
- **Canonical form.** The Kotlin replay writer and the pack hashes must be byte-identical to Python
  (A5). Snapshots, the display model, timelines and UI state are not canonical and are never
  hashed.
- **Ordering.** Draw order, atlas packing and hit-test ties are fixed sorts. These are UI matters,
  but they make the tests reproducible.

## 11. Risks

- **Store policy versus GPL.** GPL-2.0 forbids further restrictions, and store terms have
  conflicted with that before (ADR-0010). VCMI is itself distributed through Google Play, which is
  a precedent and not legal advice. Trademarks: the app name and listing must not use the game's
  marks or art. Store screenshots use the placeholder renderer only.
- **Sprite licensing.** Decoded sprites and caches are a format conversion of the player's own
  copy. They are kept private, excluded from backup, never exported, and never bundled. OS
  screenshots are the player's own act. Exported replays and crash notes carry no images. Replays
  do carry creature stats and names from the player's files (7.2); the export dialog says so, and
  such files never enter the repo (law 9).
- **Wrong rules with real creatures.** The ability table is a placeholder and `hates` cannot be
  derived (`content.md`, HANDOFF), so real-roster battles may differ from the game. The note in
  the picker is the mitigation until the ability map is verified.
- **Localised installs.** The `CRTRAITS.TXT` header check and the cp1252 default may fail
  (`txt.md`, `vcmi-crosscheck-formats.md` #9).
- **Performance.** Pre-expanded ARGB costs about four times the memory of indexed textures (D5 of
  ADR-0011). A cold decode of a large DEF set may exceed 3 s on low-end phones; the disk cache
  mitigates this after the first battle.
- **SAF quirks.** Root pickers are refused on API 30+, and cloud providers are slow. Copying (3.2)
  avoids most of this.
- **Drift.** The presenter becomes a third contract (after sim and replay). Vectors (A2, A3) keep
  Python authoritative.
- **Feedback loop.** `:app` builds only on CI, so UI iterations are slow. Keep logic in the JVM
  modules where it can be tested here.
- **Accessibility.** A spatial hex game is hard to make fully accessible. The Actions list is the
  baseline, not a complete answer.
- **Audio** has no format spec (G9), and adding it later touches the timeline (sound cues per
  clip).

## 12. Assumptions (proposed defaults; the owner may overturn any)

- A1: reference device for budgets: a 2022-2023 mid-range phone with 4 GB RAM (Galaxy A54 or
  Pixel 6a class), Android 13 or later.
- A2: no audio in the MVP.
- A3: TalkBack playability through the Actions list is part of the MVP.
- A4: `allowBackup="false"` for the MVP. Saves are not backed up either.
- A5: import copies files rather than linking to the picked folder.
- A6: no shipped art of any kind; placeholders are procedural.
- A7: English-only UI strings in the MVP. Creature names come from the player's files.
- A8: battle supports portrait as well as landscape.
- A9: a drag never commits on release by default.
- A10: no network access and no telemetry.

## 13. Out of scope

Spells, sieges, war machines, retreat and surrender (not in `battle.md`), audio and video,
multiplayer, cloud saves, mods, iOS, HotA content, store publication, and the adventure, town and
hero screens beyond the outline in 6.4.

## 14. Open questions for the owner

- **Q1, distribution channel.** Google Play, F-Droid or GitHub releases only? This decides the
  `targetSdk` cadence, the signing setup, the app name and trademark review, and whether the store
  terms must be checked against the GPL (ADR-0010) before the first release.
- **Q2, source of the creature-to-sprite mapping (G3).** The mapping covers the battle DEF, missile
  DEF, obstacles and backgrounds, keyed by `CRTRAITS.TXT` row, not by name (names are localised).
  There are three options: (a) a table of file-name facts the owner writes, each entry with an
  ADR-0003 citation; (b) a port of VCMI's creature config under ADR-0010 with provenance, which
  conflicts with ADR-0003's "no data tables from VCMI" unless that ADR is amended; (c) deriving it
  from the player's install. This blocks A9, not the MVP.
- **Q3, editions for the MVP.** The proposal is: Shadow-of-Death-compatible data only; RoE and AB
  refused for now; HotA installs accepted with base content only and a notice; HD Edition refused;
  localised installs experimental. Is that acceptable, and is HotA content wanted later?
