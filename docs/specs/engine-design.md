# Engine design: heroes-mobile

Status: draft v1. Owner: architecture checkpoint #3 (see `docs/checkpoints/GRAPH.md`).

## 0. Goals and clean-room constraints

- **What it is:** a data-driven, turn-based strategy engine that plays like
  Heroes of Might and Magic III and is built for phones and tablets first.
  At runtime it loads the game data the user legally owns: `H3bitmap.lod`,
  `H3sprite.lod`, `*.snd`/`*.vid`, and maps (`*.h3m`).
- **What gets committed:** no original assets, text tables, sounds, maps or
  code. The repository holds only our code, our specs and *synthetic*
  test fixtures that we build byte by byte in the tests.
- **Where the rules come from:** observable behaviour and publicly documented
  community knowledge. Formats and mechanics are written up in `docs/specs/`
  before anyone implements them. Every formula in `rules.md` is tagged
  **[documented]** or **[uncertain]**. Only **[documented]** formulas go into
  reference code without a verification ticket.
- **Determinism:** the same initial state, inputs and seed always give the same
  game. This gives us replays, network play and save/load, and it lets a
  golden-file test reproduce a bug.
- **Not a goal:** bit-exact match with the original's RNG stream or AI
  behaviour. We match the *rules* and the *distributions*, not the random
  sequences.

## 1. Layered architecture

```
+--------------------------------------------------------------+
|  app/            platform shell (Android/iOS/desktop), file  |
|                  picker for user's game dir, settings, saves |
+--------------------------------------------------------------+
|  ui/             touch input, gesture -> Command mapping,    |
|                  screens (adventure, town, hero, battle)     |
+------------------------------+-------------------------------+
|  render/                     |  audio/                       |
|  sprite atlas, palette anim, |  snd/wav decode, music, sfx   |
|  map/battle scene graph      |  event-driven                 |
+------------------------------+-------------------------------+
|  presenter/      read-only views of sim state + event stream |
|                  -> animations; never mutates state          |
+--------------------------------------------------------------+
|  sim/            PURE deterministic core                     |
|   sim.adventure  sim.town  sim.hero  sim.battle  sim.ai      |
|   sim.rules (formulas)  sim.rng  sim.commands  sim.events    |
+--------------------------------------------------------------+
|  content/        typed game database built from data/       |
|                  (creatures, spells, artifacts, heroes,      |
|                  buildings, terrain), plus mod overlays      |
+--------------------------------------------------------------+
|  data/           format readers: LOD, DEF, PCX, H3M, TXT     |
|                  (reference impl: tools/h3re)                |
+--------------------------------------------------------------+
```

Dependencies only point **downward**. The rules that hold the layers apart:

| Module     | May depend on            | Must NOT depend on                  |
|------------|--------------------------|-------------------------------------|
| `data`     | stdlib / byte I/O        | everything else                     |
| `content`  | `data`                   | `sim`, `render`, `ui`               |
| `sim`      | `content` (read-only IDs + stats) | `render`, `audio`, `ui`, clocks, threads, filesystem, floats in rule paths |
| `presenter`| `sim` (read), `content`  | mutating `sim` state                |
| `render`   | `presenter`, `content`, `data` (images) | `sim` internals     |
| `ui`       | `presenter`, `sim.commands` | direct state mutation            |

### 1.1 Data layer (`data/`)

The reference parsers live in Python in `tools/h3re`: `lod.py`, `defimg.py`
and `h3m.py`. Another workstream owns them. Production readers port those
specs to the engine language, and both implementations are tested against the
same synthetic fixtures.

- **LOD archive.** Header, then a file table (name, offset, size, compressed
  size). Entries are zlib-compressed when the compressed size is non-zero.
  The reader exposes `list()`, `open(name) -> bytes` and lazy, memory-mapped
  access. Names are matched case-insensitively.
- **DEF sprites.** Palette (256 RGB), groups, then frames. A frame has a
  size, a full width/height, a margin, and one of several RLE compressions.
  Special palette indices 0-7 (VCMI-confirmed, see def.md). `render` maps
  the special indices to alpha. The output is an indexed image plus palette, and `render`
  builds atlases from that.
- **PCX / bitmap** (in LOD): 8-bit palettized or 24-bit images.
- **TXT tables** (`CRTRAITS.TXT`, `SPTRAITS.TXT`, `HCTRAITS.TXT`, …):
  tab-separated localized tables. These are the **source of truth for numeric
  content** such as creature stats, costs, growth, spell power and class
  probabilities, so the engine never hard-codes them.
- **H3M maps.** gzip-compressed. Format version (RoE/AB/SoD), map header,
  player info, victory/loss conditions, terrain tiles (terrain, roads, rivers,
  flips), object templates, object instances with per-type payloads, and
  events. The parser yields a plain `MapDocument` that has no engine
  semantics.
- **Errors:** every reader validates sizes and offsets and raises a typed
  `FormatError`. Never crash on hostile input, because user files can be
  corrupt or modded.

### 1.2 Content layer (`content/`)

- Turns parsed tables into immutable typed records: `CreatureDef`,
  `SpellDef`, `HeroClassDef`, `BuildingDef`, `ArtifactDef` and `TerrainDef`.
  Each record has a stable string ID (`"creature.pikeman"`) plus a numeric
  index for compact state.
- Ability flags such as `shooter`, `flyer`, `double_wide`, `no_retaliation`,
  `unlimited_retaliation`, `hates:[...]`, `no_melee_penalty` and
  `double_attack` come from a **data-driven ability map**. One JSON file, our
  own and committed, maps creature IDs to abilities, because the original
  stores many of them in code rather than tables. This is the only place
  where "knowledge about the original" lives as data, and every entry cites
  the rule that justifies it.
- Mod overlays are JSON patches applied after loading the base content.

### 1.3 Simulation core (`sim/`)

- **State** is plain data: dicts/structs of ints and IDs. It has no object
  references into `render`. It serializes to a canonical byte form, which is
  used for saves, network sync and hashing.
- **Commands in, events out.** `apply(state, command, rng) -> (state', [Event])`.
  Commands are validated, and an invalid command is rejected without touching
  state. The presenter animates events (`Moved`, `DamageDealt`,
  `UnitDied`, `LuckRolled`, …).
- **Integer arithmetic only** in rule paths. Percentages are kept as integer
  per-mille or as exact rationals, and rounding happens at the points that
  `rules.md` documents. Floats would break cross-platform determinism.
- **Sub-modules:**
  - `sim.adventure`: map grid, movement points, pathfinding (A* with
    terrain costs and diagonals), object interaction, fog of war, day/week
    tick.
  - `sim.town`: building tree, one build per day, recruitment, weekly growth,
    mage guild.
  - `sim.hero`: experience/levels, primary/secondary skills, spell book,
    spell points, artifacts.
  - `sim.battle`: hex grid, turn queue, actions (move, attack, shoot, wait,
    defend), damage resolution, retaliation, morale/luck, obstacles,
    victory.
  - `sim.rules`: pure formula functions with no state. The Python reference
    is `tools/h3re/h3re/rules.py`.
  - `sim.ai`: deterministic AI that uses the same RNG facility, with its own
    named stream.

### 1.4 Deterministic seeded RNG (`sim.rng`)

- The algorithm is **PCG32** or **xoshiro128\*\***. It is fixed forever, and
  the version is stored in save files.
- **Named streams** come from the master seed:
  `stream = H(master_seed, domain, id)`. Example domains are
  `"battle:<battle_id>"`, `"map-gen"`, `"weekly"` and `"ai:<player>"`.
  Adding a new random call in one subsystem then cannot shift the outcomes of
  another.
- API: `next_u32()`, `range(lo, hi)` for the half-open interval `[lo, hi)`
  using rejection sampling (no modulo bias), `randint(lo, hi)` for the
  inclusive interval `[lo, hi]`, and `chance(num, den)`. See `rng.md`.
- **Draw order is part of the spec.** For each attack, `rules.md` fixes the
  order in which luck, damage rolls and so on are drawn, which keeps replays
  stable.
- **Golden tests:** a fixed seed, a scripted command list, and an expected
  state hash.

### 1.5 Presenter, rendering and audio

- The presenter turns the event stream into a timeline of animation clips.
  Rendering is fully interruptible: in "skip animations" mode the presenter
  drains events instantly. `sim` never waits on animation.
- Sprite rendering keeps palette-indexed textures and uses a shader for
  palette lookup, player-color substitution and special indices. This gives
  cheap palette cycling for water and lava and avoids per-player textures.
- Rendering runs at a fixed logical resolution of 800×600 tiles and is then
  scaled. `ui` uses DPI-aware chrome, so the scene can scale while the
  controls stay finger-sized.

### 1.6 Touch-UI considerations

- **Hit targets:** at least 44–48 dp. Battle hexes on a phone are smaller
  than a finger, so use **tap-to-preview, tap-again-to-confirm**. The first
  tap shows the path, the attack direction and the predicted damage range;
  the second tap commits.
- **Melee attack direction:** this replaces the PC's cursor-sector
  selection. Tapping an enemy shows up to 6 adjacent-hex "petals" (12 for
  two-hex units) to choose where to attack from. Drag-from-unit-to-target
  also works, and the hex where the drag is released is the direction.
- **Hover replacement:** long-press shows info (creature card, object
  tooltip). Nothing in the game may require hover.
- **Adventure map:** pinch zoom, two-finger pan and one-finger drag pan with
  inertia. Tapping a tile shows the path and its turn-cost markers; tapping
  the destination again moves the hero.
- **Damage preview:** `sim.rules` provides `damage_range()`, which takes no
  RNG and gives the min/max kills. It is shown before confirming. This only
  works because the rules are pure functions.
- **Layout:** safe-area insets, portrait-first for the town and hero screens,
  and landscape for the map and battle. Never put critical controls in
  corners that a hand covers. The End Turn button needs a confirm when heroes
  still have movement left.
- **Session robustness:** the app can be killed at any time, so it
  autosaves on every command, and saves stay cheap because the state is
  plain data plus a command log.

## 2. Testing strategy

- `data`: synthetic fixtures built in the tests (tiny LOD with 2 entries, DEF
  with a 2×2 frame for each compression type, minimal H3M). The real game
  files are only used by an optional, local-only test job gated by
  `H3_DATA_DIR`. CI never sees them.
- `sim.rules`: table-driven unit tests per formula, covering the cap edges
  (e.g. +60 and +28 point differences).
- `sim.*`: scenario tests (scripted battles) with golden state hashes, plus
  property tests such as "total HP never increases from damage", "a stack
  count is never negative" and "the turn queue contains each living unit
  exactly once per round".
- **Verification against the original:** every **[uncertain]** item has a
  checklist entry in `rules.md` §9. The user resolves it by an *observational
  experiment* in their own copy of the game (e.g. set up a battle in the map
  editor, record the outcomes over N trials). Once confirmed, the item is
  promoted to **[documented]**, and the experiment is recorded as a test
  case with its observed values.

## 3. Phased roadmap

Every phase ends with a milestone that a test can check.

Note: the phase numbers below are roadmap phases. They are distinct from the
checkpoint numbers in the checkpoint log in `docs/checkpoints/GRAPH.md`, so
"Phase 1" (LOD reader) is not "checkpoint 1".

| Phase | Scope | Testable milestone |
|------:|-------|--------------------|
| 0 | Repo scaffold, clean-room rules, CI running `unittest` | CI green on empty suite |
| 1 | `data`: LOD reader | Lists and extracts entries from a synthetic LOD; on a user's real install (local only), counts match `list()` and every entry decompresses |
| 2 | `data`: DEF + PCX decode, H3M parse | Synthetic DEF frames decode pixel-exact; synthetic H3M round-trips header, terrain and object counts; local job parses every bundled map without `FormatError` |
| 3 | Specs: `rules.md`, this doc; `rules.py` reference | Unit tests for every [documented] battle formula pass |
| 4 (skipped) | `content`: typed DB from TXT tables + ability map | Loads creatures/spells/heroes from synthetic TXT; local job: 100% of creatures in `CRTRAITS.TXT` resolve to a `CreatureDef` with abilities |
| 5 (done) | `sim.rng` + `sim.battle` (no spells) | Golden replay: seeded 2-stack-vs-2-stack battle reaches the expected state hash; property tests pass; damage matches `rules.py` |
| 6 | Battle render + touch UI (separate app target) | A battle is playable on a device; the "skip animations" path gives the same end hash as headless |
| 7 | `sim.adventure` movement + resources + day/week tick | Pathfinding cost tests per terrain; a hero's movement points match the table in rules §2; 7-day tick fires weekly growth |
| 8 | `sim.town` + `sim.hero` (levels, skills, spell points) | Building-tree prerequisite tests; growth math tests; level-up uses class probabilities from content |
| 9 | Spells (battle + adventure), artifacts | Per-spell effect tests; spell damage formulas promoted from [uncertain] only after verification |
| 10 | H3M → playable map; victory/loss conditions; save/load | Load a synthetic map, play scripted turns, save, load, and continue with an identical hash |
| 11 | AI (adventure + battle) | AI vs AI full games finish without invalid commands across 100 seeds |
| 12 | Polish: audio, video, accessibility, mods | Device performance budget: 60 fps on the battle screen on a mid-range phone |

Phase 4 (TXT content DB) was skipped so far: `battle.Creature` is built by
hand (in tests and callers), not loaded from a content database.

## 4. Open architecture questions

- Engine language: **decided** in ADR-0004. The target is an Android app with a Kotlin
  engine; the Python implementation stays as the reference oracle and conformance suite.
  `sim` must still compile headless for tests.
- Shipping our own replacement placeholder art (CC0) so the engine runs
  without game data, for development and CI screenshots.
- Multiplayer: lockstep over command logs works directly because of the
  determinism. Hidden information (fog of war) means a full-state hash
  exchange leaks nothing only if it is the hash and nothing more.
