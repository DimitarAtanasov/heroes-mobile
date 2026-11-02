# Graph Report - proj  (2026-11-02)

## Corpus Check
- 277 files · ~303,445 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 3, .properties 2, .xml 1)

## Summary
- 5656 nodes · 14475 edges · 335 communities (177 shown, 158 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 929 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- __init__.py
- .write
- StackRosterTest
- vectors_town.py
- assertequals
- parse_txt
- soak.py
- vectors.py
- vectors_encounter.py
- battle.py
- H3mTest.kt
- BattleSession
- adventure.py
- town.py
- BattleState
- Def
- golden_game
- vectors_hero.py
- AdventureState
- HexCell
- hero.py
- Datapack
- datapack.py
- vectors_ai.py
- SetupForm
- BattleCodec
- ResumeError
- HeroTest
- dataclasses
- h3m.py
- replay.py
- Screens.kt
- BattleStateTest
- with
- battle_cli.py
- run_cli
- SegKind
- vectors_pack.py
- BoardFitTest
- Hero.kt
- TownTest
- parse_h3m_bytes
- Encounter.kt
- defimg.py
- BattleScreen.kt
- MainActivity.kt
- encounter.py
- vectors_h3m.py
- MenuModelTest
- Replay
- SaveSlotsTest
- .encode
- Rules
- TownConformanceTest
- Battle simulation core (`sim.battle`)
- test_h3m.py
- Pcg32
- BattleCommand
- SaveSlots
- .boardStacks
- Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)
- build_lod
- Rational
- Present
- struct
- Pcg32
- grid
- VectorsHeroTest
- TownCore
- vectors_adventure.py
- hero
- HeroConformanceTest
- H3mObjectTests
- BoardView.kt
- BattleLogTest
- ResultSummaryTest
- Rules: battle damage (`rules.json`)
- re
- vectors_replay.py
- game
- DataPack
- VectorsTownTest
- _Visitor
- ReplayAutosaveTest
- .parseState
- HeroCore
- bisect_tool.py
- parse_pcx
- resolve_damage
- rules
- BoardGeometry
- EncounterTest
- argparse
- PolicyPackTest
- Rules specification
- parse_def
- BattleLog
- TapReducerTest
- LodArchive
- _Pretty
- kotlin_banned_api_lint.py
- Scenario
- AdventureTest
- TestBattleVectors
- golden_setup
- _run_isolated
- GameController
- SaveFolderWriter
- damage_from_base
- _Reader
- EncounterSetup
- .parseCreatures
- TownState
- .parse
- PresentTest
- ReplayTest
- Town.kt
- RulesTest.kt
- H3mUnsupportedObject
- vectors_txt.py
- ScriptRng
- TapState
- AdventureCodec
- __main__.py
- LintTest
- LodTest.kt
- Replay file format
- apply_damage
- .test_every_mutation_changes_the_hash
- module_doc
- VectorsEncounterTest
- EncounterEngine
- P
- base_damage
- BattleAiTest
- _oracle
- present.py
- verify
- vectors_lodpcx.py
- NoRng
- LodArchive
- MEMORY.md
- TestVectors
- golden_setup
- BattleEvent
- Txt.kt
- TownText
- LegalTest
- Data pack (`h3re.datapack`)
- parsePcx
- README.md
- Conformance: hero core (`h3.sim.hero`)
- Determinism gate
- ss
- ContentErrorCategory
- .parse
- Test
- StrictIntFieldsTest
- KotlinLintTests
- LoopCheck
- GoldenTest
- H3mVectorTests
- Resources
- BattleAiTest
- PcxTest
- Loop: one agent round (advise, fan out, verify, checkpoint)
- LOD archive format
- HoMM3 PCX bitmap variant (clean-room notes)
- _bld
- RealLodTests
- assert_module_deterministic
- LodPcxVectorTests
- doc
- Datapack.kt
- Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic)
- Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)
- Battle scenario file (JSON)
- .extract_all
- Hero simulation core (`sim.hero`): experience, levels and skill gain
- started
- cr
- IntegerCapTest
- raw
- TestAdventureVectors
- Scripted
- Handoff (resume here)
- Android app design (`android/`)
- HoMM3 .H3M map header (clean-room notes)
- heroes-mobile
- attack_defense_factor
- RecordingRng
- four
- GoldenTest
- AllowlistTests
- GrowthTest
- .repr
- .parse
- ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)
- candidate_actions
- MVP 0.1: a playable skirmish APK
- _Reader
- raw
- ReadTests
- PackVectorsTest
- Txt
- DrawSource
- Second brain (project memory)
- ADR-0004: Android app with a Kotlin engine; Python is the reference oracle
- 4. Rendering
- Town simulation core (`sim.town`): buildings, build rules and weekly growth
- VCMI cross-check: file-format specs
- GeometryTest
- IllegalCommandNoRngTest
- LastMoverOrderTest
- ContentTest
- 3. Data import
- Conformance: adventure core (Kotlin port)
- army
- TickTest
- PolicyAndHeroTest
- MalformedHexTest
- PackMismatchTest
- OfferPolicyTest
- CorruptPayloadTests
- MemoryCheck
- StoredContentHashTest
- TestContractEdgeVectors
- Loop graph builder
- ADR-0010: The project is licensed GPL-2.0-or-later
- 6. Screens and navigation
- ModuleEntryPointTests
- SkillCheck
- 7. Threading, saves, replay and crash safety
- index.sh
- PolicyDefaultsFromPackTest
- Cli
- TestAll
- .shot
- RealSourcesTests
- RepoWiring
- RepoFiles
- ADR-0003-vcmi-as-fact-source-clean-room.md
- ADR-0006-state-content-stands-in-for-a-pack-hash.md
- ADR-0007-replay-and-vectors-are-the-cross-language-contract.md

## God Nodes (most connected - your core abstractions)
1. `BattleState` - 119 edges
2. `HexCell` - 85 edges
3. `derive_stream()` - 69 edges
4. `BattleSession` - 62 edges
5. `Battle` - 58 edges
6. `BattleCommand` - 57 edges
7. `BattleCodec` - 52 edges
8. `Datapack` - 52 edges
9. `Pcg32` - 51 edges
10. `TownCore` - 45 edges

## Surprising Connections (you probably didn't know these)
- `Decision` --references--> `BattleSession`  [INFERRED]
  docs/adr/ADR-0011-android-app-architecture.md → android/presenter/src/main/kotlin/h3/presenter/BattleSession.kt
- `Remaining work for 0.1, in order` --references--> `BattleSession`  [INFERRED]
  docs/specs/mvp-0.1.md → android/presenter/src/main/kotlin/h3/presenter/BattleSession.kt
- `Amendments (2026-11-01)` --references--> `Rational`  [INFERRED]
  docs/adr/ADR-0004-android-kotlin-core-python-oracle.md → android/sim/src/main/kotlin/h3/sim/Rational.kt
- `Out of scope (Kotlin's types cannot express them)` --references--> `TownTest`  [INFERRED]
  docs/specs/conformance-town.md → android/sim/src/test/kotlin/h3/sim/town/TownTest.kt
- `Default changes and the golden hash` --references--> `GameState`  [INFERRED]
  docs/specs/adventure.md → tools/h3re/h3re/adventure.py

## Import Cycles
- 2-file cycle: `tools/h3re/h3re/adventure.py -> tools/h3re/h3re/encounter.py -> tools/h3re/h3re/adventure.py`
- 2-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/__init__.py`
- 2-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`
- 3-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/__init__.py`
- 3-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`

## Communities (335 total, 158 thin omitted)

### Community 0 - "__init__.py"
Cohesion: 0.06
Nodes (12): _inflate(), LodError, LodFormatError, PcxImage, RollPolicy, TxtTable, FloatSub, army() (+4 more)

### Community 1 - ".write"
Cohesion: 0.06
Nodes (18): AiChooserTest, choose(), _board_at(), _cell_glyphs(), ChooserTest, CliTestCase, golden_scenario(), GoldenScenarioTest (+10 more)

### Community 2 - "StackRosterTest"
Cohesion: 0.05
Nodes (30): add(), addAll(), Atlas, AtlasFrame, BudgetCheck, BuildResult, Exceeded, Failed (+22 more)

### Community 3 - "vectors_town.py"
Cohesion: 0.06
Nodes (61): _b(), _base(), _bigvalues(), _bld(), _canon(), classify_pack(), _cmd(), _create_cases() (+53 more)

### Community 4 - "assertequals"
Cohesion: 0.09
Nodes (12): Holding, plain(), session(), Fixture, Game, asDrawSource(), big(), list() (+4 more)

### Community 5 - "parse_txt"
Cohesion: 0.05
Nodes (30): Abilities, API, Column order (data: `data/txt_maps/crtraits.json`, unverified), Content loader (`h3re.content`), engine roadmap Phase 4 (creatures), Errors, Reading, Tests, API (+22 more)

### Community 6 - "soak.py"
Cohesion: 0.05
Nodes (26): _AdventureDriver, build_adventure(), build_battle(), build_scenario(), check_seed(), Divergence, _driver(), _events_digest() (+18 more)

### Community 7 - "vectors.py"
Cohesion: 0.06
Nodes (49): Test cost, derive_stream(), _enc(), RngStreams, _attack_defense_vectors(), _base_damage_vectors(), _canon_corpus(), _canon_vectors() (+41 more)

### Community 8 - "vectors_encounter.py"
Cohesion: 0.07
Nodes (50): Vector file `hero.json`, all_games(), army(), auto_cases(), _battery(), _bpol(), build_setup(), _case() (+42 more)

### Community 9 - "battle.py"
Cohesion: 0.07
Nodes (54): Next, in order, 2. Grid, Hex: battle grid geometry and movement (`hex.json`), _activate_next(), _adjacent_cells(), apply(), Attack, BattleEnded (+46 more)

### Community 10 - "H3mTest.kt"
Cohesion: 0.09
Nodes (30): H3m, H3mDisposedHero, H3mError, H3mHeader, H3mHotaError, H3mLoss, H3mPlayer, H3mPredefinedHero (+22 more)

### Community 11 - "BattleSession"
Cohesion: 0.07
Nodes (32): Accepted, AutosaveSink, BattleSession, Faulted, Illegal, LogEntry, NotYourTurn, Origin (+24 more)

### Community 12 - "adventure.py"
Cohesion: 0.05
Nodes (39): ADR-0002: Integer-only simulation (int and Fraction, one explicit rounding step), ADR-0005: The omit-at-default canonical mechanism applies to every state module, not only battle, adventure_rng(), apply(), Attack, base_movement(), Begin, calendar() (+31 more)

### Community 13 - "town.py"
Cohesion: 0.06
Nodes (40): Vector file `town.json`, 1. Interface, 4. Weekly growth, GrowthPool, Resources, _active(), active_buildings(), apply() (+32 more)

### Community 14 - "BattleState"
Cohesion: 0.09
Nodes (18): ApplyResult, Battle, Damaged, IllegalCommand, Kind, ATTACK, DEFEND, MOVE (+10 more)

### Community 15 - "Def"
Cohesion: 0.09
Nodes (22): Def, DefBlock, DefException, DefFile, DefFrame, Out, Reader, DefTest (+14 more)

### Community 16 - "golden_game"
Cohesion: 0.09
Nodes (16): army(), BuildBattleTest, flat_grid(), fought(), golden_game(), GoldenTest, IllegalTest, OutcomeTest (+8 more)

### Community 17 - "vectors_hero.py"
Cohesion: 0.08
Nodes (40): _base(), _bigweights(), _canon(), classify_pack(), _cmd(), _create_cases(), add(), _create_error_category() (+32 more)

### Community 18 - "AdventureState"
Cohesion: 0.09
Nodes (18): Adventure, AdventureEncounterHooks, AdventurePolicy, AdventureRules, AdventureState, AdvGrid, AdvGrowthPool, AdvGuard (+10 more)

### Community 19 - "HexCell"
Cohesion: 0.11
Nodes (13): footprints(), UnitFootprint, UnitHit, Hex, HexCell, HexEntry, cell(), cells() (+5 more)

### Community 20 - "hero.py"
Cohesion: 0.07
Nodes (32): _advance(), apply(), _canon_bytes(), canonical(), _check_class(), _check_total(), ChooseSkill, content_hash() (+24 more)

### Community 21 - "Datapack"
Cohesion: 0.10
Nodes (12): CreaturesDoc, Datapack, PolicyDoc, pyRepr(), RulesDoc, DatapackTest, API (Kotlin), Conformance: data-pack loader (`vectors/datapack.json`) (+4 more)

### Community 22 - "datapack.py"
Cohesion: 0.11
Nodes (33): Pack directory and rules hash (determinism audit), _check_creatures(), _check_policy(), _check_rules(), DataPackError, _frac(), _int(), _list() (+25 more)

### Community 23 - "vectors_ai.py"
Cohesion: 0.07
Nodes (25): Conformance: greedy battle AI (`battle_ai.json`), File layout, Kotlin contract, What is pinned, choose(), _decide(), pick(), _enemy_dist() (+17 more)

### Community 24 - "SetupForm"
Cohesion: 0.10
Nodes (15): presetErrorText(), seedErrorText(), setupFormMessage(), PresetError, NoPresets, OutOfRange, SeedError, Empty (+7 more)

### Community 25 - "BattleCodec"
Cohesion: 0.09
Nodes (14): AppEngine, Preset, BattleCodec, BattleCreature, BattlePolicy, BattlePolicyPack, policyDefendBonus(), Shared (+6 more)

### Community 26 - "ResumeError"
Cohesion: 0.07
Nodes (23): ByteSink, Failed, Ok, ReplayAutosave, ReplayResume, Resumed, ResumeError, Diverged (+15 more)

### Community 27 - "HeroTest"
Cohesion: 0.16
Nodes (4): ChooseSkill, GainXP, HeroTest, Script

### Community 28 - "dataclasses"
Cohesion: 0.11
Nodes (28): encode_command(), _ability_creature(), build_ability_scenario(), build_tie_scenario(), cap_setup(), _case(), _driver(), _driver_step() (+20 more)

### Community 29 - "h3m.py"
Cohesion: 0.11
Nodes (32): _army(), _art(), _bits(), _body_abandoned_mine(), _body_artifact(), _body_event(), _body_garrison(), _body_generic() (+24 more)

### Community 30 - "replay.py"
Cohesion: 0.10
Nodes (22): _canon(), _check_plain(), Diverged, _is_int(), load(), Malformed, MismatchedCreatures, MismatchedPolicy (+14 more)

### Community 31 - "Screens.kt"
Cohesion: 0.12
Nodes (6): AboutScreen(), HomeScreen(), SetupScreen(), ResultScreen(), SideTallyCard(), Page()

### Community 32 - "BattleStateTest"
Cohesion: 0.11
Nodes (4): BattleStateTest, MiniJson, Amendment (2026-11-01): caps on derived products, CheckStateTest

### Community 33 - "with"
Cohesion: 0.07
Nodes (39): runs-on, steps, timeout-minutes, runs-on, steps, H3_DATA_DIR, jobs, android-app (+31 more)

### Community 34 - "battle_cli.py"
Cohesion: 0.13
Nodes (26): _ai(), pick(), _check_keys(), _check_pretty_options(), CliError, _creature(), _dataclass_kwargs(), _first_legal() (+18 more)

### Community 35 - "run_cli"
Cohesion: 0.11
Nodes (11): def_bytes(), DefCommandTests, h3m_bytes(), H3mCommandTests, lod_bytes(), LodCommandTests, png_size(), run_cli() (+3 more)

### Community 36 - "SegKind"
Cohesion: 0.09
Nodes (25): AnimationPrefs, AnimSpeed, FAST, NORMAL, SKIP, SLOW, Frames, SegKind (+17 more)

### Community 37 - "vectors_pack.py"
Cohesion: 0.11
Nodes (27): with_(), base(), classify(), _collect_invalid(), data_dir(), _delete(), _derived_valid(), dumps() (+19 more)

### Community 39 - "Hero.kt"
Cohesion: 0.12
Nodes (21): Category, asHeroDraw(), Hero, HeroApplyResult, HeroCategory, HeroCommand, HeroDraw, HeroEvent (+13 more)

### Community 41 - "parse_h3m_bytes"
Cohesion: 0.13
Nodes (9): H3mHeader, parse_h3m(), parse_h3m_bytes(), _read_tiles(), Tile, build(), extra(), H3mTests (+1 more)

### Community 42 - "Encounter.kt"
Cohesion: 0.08
Nodes (16): AdvArmySlot, AdventureEvent, AdventureStep, DayStarted, HeroMoved, MovementReset, PoolGrew, TurnEnded (+8 more)

### Community 43 - "defimg.py"
Cohesion: 0.11
Nodes (20): Contract, Blocks, Frame, Header, HoMM3 .DEF sprite container (clean-room notes), Implementation status / caveats, Mismatches, ranked by severity, _decode_frame() (+12 more)

### Community 44 - "BattleScreen.kt"
Cohesion: 0.14
Nodes (16): BattleBody(), BattleScreen(), candidateLabel(), LogPanel(), PreviewPanel(), RosterPanel(), RosterSide(), BoardSprites (+8 more)

### Community 45 - "MainActivity.kt"
Cohesion: 0.06
Nodes (17): MainActivity, Screen, About, Battle, Home, Result, Saves, Setup (+9 more)

### Community 46 - "encounter.py"
Cohesion: 0.08
Nodes (19): 1. Document, ArmyChanged, auto_command(), battle_id(), BattleFought, build_battle(), _creature(), encounter_rng() (+11 more)

### Community 47 - "vectors_h3m.py"
Cohesion: 0.16
Nodes (26): build(), _Cases, _cond(), _cut_cases(), default_players(), dump_header(), _error_cases(), _expect() (+18 more)

### Community 48 - "MenuModelTest"
Cohesion: 0.12
Nodes (9): menuEdgeAllowed(), MenuModel, MenuRoute, About, Battle, Home, Result, Setup (+1 more)

### Community 49 - "Replay"
Cohesion: 0.16
Nodes (17): Diverged, Loaded, Malformed, MismatchedCreatures, MismatchedPolicy, MismatchedRulesPack, Replay, ReplayError (+9 more)

### Community 50 - "SaveSlotsTest"
Cohesion: 0.16
Nodes (5): Listing, MemFolder, Played, SaveSlotsTest, Scn

### Community 51 - ".encode"
Cohesion: 0.12
Nodes (4): Canonical, ConformanceTest, PresentTest, ADR-0009: The Kotlin engine uses a small exact Rational type with one named rounding step, not an integer rewrite

### Community 52 - "Rules"
Cohesion: 0.11
Nodes (13): DrawSource, AttackDefenseFactor, DamageCtx, DamagePreview, DamageResult, DrawSource, RollPolicy, ACTUAL_SEED (+5 more)

### Community 53 - "TownConformanceTest"
Cohesion: 0.16
Nodes (12): TownSetup, assertError(), canonText(), commandOf(), eventMap(), i32(), kindOf(), lng() (+4 more)

### Community 54 - "Battle simulation core (`sim.battle`)"
Cohesion: 0.07
Nodes (23): ADR-0001: Canonical JSON form and SHA-256 state hash for battle and adventure state, 10. Change notes, 1. Interface, 2026-11-01: golden hash re-pinned (one reviewed change), 2026-11-01: malformed hex raises IllegalCommand (no re-pin), 2026-11-01: state invariants and integer caps (no re-pin), 3. Movement [documented], 4. Turn queue (+15 more)

### Community 55 - "test_h3m.py"
Cohesion: 0.21
Nodes (21): box(), e_army(), e_box(), e_event_common(), e_hero(), e_monster(), e_msg_guards(), e_opt8() (+13 more)

### Community 56 - "Pcg32"
Cohesion: 0.10
Nodes (4): Pcg32, RngStreams, Edge, RngEdgeTest

### Community 57 - "BattleCommand"
Cohesion: 0.16
Nodes (10): drive(), Attack, BattleCommand, Begin, Defend, Move, Shoot, Wait (+2 more)

### Community 58 - "SaveSlots"
Cohesion: 0.14
Nodes (18): readSaveFolder(), SaveRowCard(), SaveScreen(), Load, NotListed, ParsedName, Ready, Refused (+10 more)

### Community 59 - ".boardStacks"
Cohesion: 0.21
Nodes (8): ArtPoint, ArtRect, BoardArt, BoardStack, CountPlate, SpriteDraw, StackArt, BoardArtTest

### Community 60 - "Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)"
Cohesion: 0.07
Nodes (24): 1. Interface, 2. Grid and step costs, 3. Movement points, 4. Pathfinding, 5. Calendar, income and growth, 6. Policy fields (`AdventurePolicy`), 7. Tests, 8. Encounters (battles on the map) (+16 more)

### Community 61 - "build_lod"
Cohesion: 0.17
Nodes (5): build_lod(), ExtractTests, MalformedInputTests, member(), open_bytes()

### Community 62 - "Rational"
Cohesion: 0.13
Nodes (3): Rational, RulesPack, longs()

### Community 63 - "Present"
Cohesion: 0.13
Nodes (11): legalCommands(), Present, What exists, 9. Milestones and acceptance criteria, Conformance: presenter view v2 (`h3.sim.Present`), States, What is pinned, 2. Shape (+3 more)

### Community 64 - "struct"
Cohesion: 0.19
Nodes (21): _bad_cases(), single(), build_def(), case(), encode_body(), _format_cases(), one(), frame_blob() (+13 more)

### Community 65 - "Pcg32"
Cohesion: 0.13
Nodes (3): Pcg32, _TracedPcg32, TestPcg32

### Community 66 - "grid"
Cohesion: 0.12
Nodes (5): game(), grid(), PolicyTest, StepCostTest, costs()

### Community 67 - "VectorsHeroTest"
Cohesion: 0.13
Nodes (4): doc(), _floats(), _steps(), VectorsHeroTest

### Community 68 - "TownCore"
Cohesion: 0.15
Nodes (5): Building, Faction, TownContent, TownCore, TownKeyError

### Community 69 - "vectors_adventure.py"
Cohesion: 0.12
Nodes (21): Vector contents, _decode(), encode_event(), generate(), golden_commands(), golden_setup(), illegal_cases(), _illegal_commands() (+13 more)

### Community 70 - "hero"
Cohesion: 0.13
Nodes (8): gain(), hero(), IllegalTest, LevelUpTest, NoRng, resolve(), with_class(), XpTest

### Community 71 - "HeroConformanceTest"
Cohesion: 0.18
Nodes (11): canonText(), commandOf(), CountingDraw, eventMap(), HeroConformanceTest, HeroVectors, i32(), lng() (+3 more)

### Community 72 - "H3mObjectTests"
Cohesion: 0.18
Nodes (5): e_objects(), e_template(), H3mObjectTests, map_with(), tmpl()

### Community 73 - "BoardView.kt"
Cohesion: 0.10
Nodes (8): artPoint(), drawBoard(), drawOutline(), drawPlate(), drawSprite(), drawToken(), hexPath(), toRect()

### Community 75 - "ResultSummaryTest"
Cohesion: 0.17
Nodes (7): ResultOutcome, Defeat, Unfinished, Victory, ResultSummary, SideTally, ResultSummaryTest

### Community 76 - "Rules: battle damage (`rules.json`)"
Cohesion: 0.11
Nodes (16): 5.1 Preview and confirm (pure reducer in `:presenter`), 5.3 Accessibility, 5.4 Layout, 5. Touch interaction, 2026-11-01: golden hash re-pinned a second time (rules pack in the hash), 5. Morale and luck, Rules: battle damage (`rules.json`), 8. Reference implementation (+8 more)

### Community 77 - "re"
Cohesion: 0.13
Nodes (17): golden_scenario(), ReplayCliTest, _back_edges(), visit(), eval_graph(), eval_run(), _load_run(), main() (+9 more)

### Community 78 - "vectors_replay.py"
Cohesion: 0.14
Nodes (21): run_chooser(), _creature_dict(), _explicit_pos_scenario(), generate(), _golden(), _hero_dict(), _jsonable(), main() (+13 more)

### Community 79 - "game"
Cohesion: 0.14
Nodes (6): build(), build_days(), BuildTest, game(), IncomeTest, NoRng

### Community 80 - "DataPack"
Cohesion: 0.09
Nodes (18): API, 0. Goals and clean-room constraints, 1.1 Data layer (`data/`), 1.2 Content layer (`content/`), 1.3 Simulation core (`sim/`), 1.4 Deterministic seeded RNG (`sim.rng`), 1.5 Presenter, rendering and audio, 1.6 Touch-UI considerations (+10 more)

### Community 81 - "VectorsTownTest"
Cohesion: 0.13
Nodes (7): _cmd(), doc(), _err(), _floats(), NoRng, _steps(), VectorsTownTest

### Community 82 - "_Visitor"
Cohesion: 0.15
Nodes (4): _is_dict_view(), _is_set_expr(), Violation, _Visitor

### Community 83 - "ReplayAutosaveTest"
Cohesion: 0.25
Nodes (4): Case, MemSink, ReplayAutosaveTest, Run

### Community 85 - "HeroCore"
Cohesion: 0.19
Nodes (4): HeroClass, HeroContent, HeroCore, HeroRules

### Community 86 - "bisect_tool.py"
Cohesion: 0.13
Nodes (16): bisect(), diff_states(), dump_log(), flatten(), format_policy(), format_report(), load_log(), load_log_ex() (+8 more)

### Community 87 - "parse_pcx"
Cohesion: 0.16
Nodes (6): parse_pcx(), PcxError, bgr_2x2(), indexed_2x2(), PcxErrorTests, PcxParseTests

### Community 88 - "resolve_damage"
Cohesion: 0.16
Nodes (9): _check_flags(), DamageCtx, DamagePreview, DamageResult, preview_damage(), resolve_damage(), _settle(), random_ctx() (+1 more)

### Community 89 - "rules"
Cohesion: 0.18
Nodes (3): GraphCriteria, rules(), RunCriteria

### Community 90 - "BoardGeometry"
Cohesion: 0.20
Nodes (3): BoardGeometry, Pt, BoardGeometryTest

### Community 91 - "EncounterTest"
Cohesion: 0.19
Nodes (3): EncounterTest, DrawSource, Vector file `encounter.json`

### Community 92 - "argparse"
Cohesion: 0.14
Nodes (13): _canon(), _entries(), generate(), main(), _playouts(), _sha(), _taps(), apply_allowlist() (+5 more)

### Community 93 - "PolicyPackTest"
Cohesion: 0.11
Nodes (7): ADR-0008: Kotlin pack values are 32-bit Int capped at 2**31-1; hashes and XP accumulation use Long, LoadTest, PolicyPackTest, bad(), raw(), raw_policy(), ValidationTest

### Community 94 - "Rules specification"
Cohesion: 0.08
Nodes (23): 0. Provenance and tagging, 1. Calendar and turn structure, 2.1 Movement points (land), 2.2 Terrain cost, 2. Adventure map: movement, 3. Resource economy, 4. Towns, 5.1 Primary skills (+15 more)

### Community 95 - "parse_def"
Cohesion: 0.21
Nodes (7): Block, DefFile, parse_def(), build_def(), build_shared(), DefTests, frame_bytes()

### Community 96 - "BattleLog"
Cohesion: 0.12
Nodes (17): BattleLog, BattleLogGroup, BattleLogKind, DEFEND, DIED, END, HIT, LUCK_BAD (+9 more)

### Community 98 - "LodArchive"
Cohesion: 0.16
Nodes (7): inflateMember(), LodArchive, LodEntry, LodError, LodFormatError, LodKeyError, Error categories

### Community 99 - "_Pretty"
Cohesion: 0.12
Nodes (12): Files, _board_lines(), _fields(), _hp(), _legend_lines(), _mark(), _pos_text(), _Pretty (+4 more)

### Community 100 - "kotlin_banned_api_lint.py"
Cohesion: 0.13
Nodes (11): apply_allowlist(), default_paths(), _entry_matches(), lint_paths(), lint_source(), load_allowlist(), main(), _scan() (+3 more)

### Community 101 - "Scenario"
Cohesion: 0.23
Nodes (4): BattleEngine, Scenario, ScenarioError, Setup

### Community 103 - "TestBattleVectors"
Cohesion: 0.13
Nodes (5): decode_command(), state_from_json(), stream_at(), _t(), TestBattleVectors

### Community 104 - "golden_setup"
Cohesion: 0.14
Nodes (8): golden_setup(), GoldenTest, play(), PreviewLawTest, PropertyTest, scripted_choice(), total_hp(), golden_states()

### Community 105 - "_run_isolated"
Cohesion: 0.14
Nodes (6): _probe(), _repo_data_dir(), _run_isolated(), TestBattleExports, TestImportSideEffects, TestRulesPackIdentity

### Community 107 - "SaveFolderWriter"
Cohesion: 0.13
Nodes (10): SaveFolderWriter, FileState, Invalid, Missing, Valid, WriteStep, CopyMainToBackup, RenameTempToMain (+2 more)

### Community 108 - "damage_from_base"
Cohesion: 0.15
Nodes (8): 6.6 Damage formula, 1. Mismatches (ranked by gameplay impact), Notes on VCMI-only behaviour we should **not** copy, defend_bonus(), damage_from_base(), damage_range(), DamageFromBaseTest, DamageRangeTest

### Community 109 - "_Reader"
Cohesion: 0.17
Nodes (9): H3mError, PlayerInfo, _read_extra(), _read_loss(), _read_mask(), _read_player(), _read_predefined(), _read_victory() (+1 more)

### Community 110 - "EncounterSetup"
Cohesion: 0.12
Nodes (9): AdvEncounter, EncounterPolicy, EncounterSetup, Conformance: encounters and adventure stage E (`h3.sim.encounter`), Dependency direction, Kotlin API, Mutation check (producer's run, in a private copy; the lead re-verifies), Stage E in `Adventure.kt` (what changed there) (+1 more)

### Community 111 - ".parseCreatures"
Cohesion: 0.22
Nodes (9): Content, ContentResult, Creature, CreatureMapping, CreatureValidator, DefaultCreatureValidator, MapColumn, UnknownAbility (+1 more)

### Community 112 - "TownState"
Cohesion: 0.29
Nodes (4): GrowthPool, Town, TownPolicy, TownState

### Community 113 - ".parse"
Cohesion: 0.29
Nodes (4): enc(), EncounterConformanceTest, EncVectors, s()

### Community 114 - "PresentTest"
Cohesion: 0.15
Nodes (5): all_states(), FailRng, PresentTest, synthetic_states(), walk()

### Community 116 - "Town.kt"
Cohesion: 0.18
Nodes (15): BuildingBuilt, Dwelling, IllegalCommand, NewDay, RawResources, RawSetup, TownApplyResult, TownCategory (+7 more)

### Community 117 - "RulesTest.kt"
Cohesion: 0.28
Nodes (6): ctxOf(), isError(), loadPack(), long(), rat(), RulesTest

### Community 118 - "H3mUnsupportedObject"
Cohesion: 0.13
Nodes (12): End of data, Global events, Object instances, Objects, object instances and events (`objects=True`), Template table, Unverified assumptions (objects section), H3mUnsupportedObject, MapObject (+4 more)

### Community 119 - "vectors_txt.py"
Cohesion: 0.20
Nodes (14): _base(), _content_case(), _content_cases(), _content_error(), _creature_row(), generate(), _header(), _Lcg (+6 more)

### Community 120 - "ScriptRng"
Cohesion: 0.23
Nodes (4): begin(), CombatTest, MoraleTest, ScriptRng

### Community 121 - "TapState"
Cohesion: 0.20
Nodes (12): Cancel, Candidate, Confirmed, Idle, LongPress, Previewing, PreviewNumbers, Select (+4 more)

### Community 122 - "AdventureCodec"
Cohesion: 0.19
Nodes (6): AdventureCodec, AdventureCommand, Attack, Begin, EndTurn, Move

### Community 123 - "__main__.py"
Cohesion: 0.22
Nodes (12): build_parser(), cmd_battle_sim(), cmd_def_to_png(), cmd_h3m_info(), cmd_lod_extract(), cmd_lod_list(), cmd_replay(), _condition() (+4 more)

### Community 125 - "LodTest.kt"
Cohesion: 0.31
Nodes (6): categoryOf(), hexOf(), le32(), LodTest, oneMember(), unhex()

### Community 126 - "Replay file format"
Cohesion: 0.12
Nodes (15): `canonical_json.json`, File format, `rng.json`, `state_hash.json`, 1. Interface, 1. Encoding, 2. Header (all keys required, unknown keys rejected), 3. Body (+7 more)

### Community 127 - "apply_damage"
Cohesion: 0.15
Nodes (7): 2. Confirmed (VCMI agrees with our default or our documented value), 3. Items VCMI does not settle, VCMI cross-check of `rules.md` / `battle.md` uncertain items, _last_mover_sorted(), turn_order(), apply_damage(), ApplyDamageTest

### Community 128 - ".test_every_mutation_changes_the_hash"
Cohesion: 0.17
Nodes (5): StoredContentHashTest, high(), low(), sec(), start()

### Community 129 - "module_doc"
Cohesion: 0.15
Nodes (3): DefVectorTests, VectorsTxtTest, module_doc()

### Community 131 - "EncounterEngine"
Cohesion: 0.25
Nodes (3): BattleHero, EncounterEngine, Setup

### Community 132 - "P"
Cohesion: 0.32
Nodes (5): JsonFraction, P, Rejected, ScenarioJson, Syntax

### Community 133 - "base_damage"
Cohesion: 0.17
Nodes (7): Algorithm, API, Deterministic RNG (`sim.rng`), Named streams, base_damage(), BaseDamageTest, FixedRng

### Community 134 - "BattleAiTest"
Cohesion: 0.20
Nodes (3): BattleAiTest, play(), scenario()

### Community 135 - "_oracle"
Cohesion: 0.17
Nodes (5): _decode_name(), _key(), LodEntry, add(), _oracle()

### Community 136 - "present.py"
Cohesion: 0.23
Nodes (11): _actions(), slot(), target_slot(), command_to_dict(), _grid(), _hx(), _preview(), _queue() (+3 more)

### Community 137 - "verify"
Cohesion: 0.23
Nodes (4): info(), verify(), ReplayTest, reseal()

### Community 138 - "vectors_lodpcx.py"
Cohesion: 0.20
Nodes (9): _entry_pos(), generate(), _lod(), _lod_cases(), _member(), _patch_u32(), _pcx_cases(), add() (+1 more)

### Community 142 - "TestVectors"
Cohesion: 0.13
Nodes (5): Conformance: LOD archive and PCX bitmap readers, Open items, Results, Vectors, TestVectors

### Community 143 - "golden_setup"
Cohesion: 0.22
Nodes (5): golden_setup(), GoldenTest, play_days(), PropertyTest, scripted_turn()

### Community 144 - "BattleEvent"
Cohesion: 0.27
Nodes (13): BattleEnded, BattleEvent, BattleStarted, DamageDealt, Defended, LuckRolled, MoraleBoost, MoraleFrozen (+5 more)

### Community 145 - "Txt.kt"
Cohesion: 0.18
Nodes (7): TxtError, TxtErrorCategory, DECODE, HEADER_ROWS, TOO_LARGE, TOO_MANY_LINES, UNKNOWN_ENCODING

### Community 146 - "TownText"
Cohesion: 0.20
Nodes (5): TownText, Conformance: town core (`h3.sim.town`), Known differences (documented, not silent), Mutation check (producer's run, in a private copy; the lead re-verifies), Out of scope (Kotlin's types cannot express them)

### Community 148 - "Data pack (`h3re.datapack`)"
Cohesion: 0.14
Nodes (10): Battle policy pack, Data pack (`h3re.datapack`), Determinism and hash, Drift guard, Files, Integer range, Runtime loading (checkpoint 34), Validation (+2 more)

### Community 149 - "parsePcx"
Cohesion: 0.26
Nodes (9): parsePcx(), PcxError, PcxImage, PcxMode, BGR24, INDEXED, u32le(), Port fidelity (+1 more)

### Community 150 - "README.md"
Cohesion: 0.15
Nodes (7): Commands, heroes-mobile: project constitution, Laws, Roles and delegation, Working principles, Checkpoint log, Reverse-engineering loop graph

### Community 151 - "Conformance: hero core (`h3.sim.hero`)"
Cohesion: 0.19
Nodes (8): Conformance: hero core (`h3.sim.hero`), Known differences (documented, not silent), Mutation check (producer's run, in a private copy; the lead re-verifies), Out of scope (Kotlin's types cannot express them), _check_draw_inputs(), IllegalCommand, level_for_xp(), _validate()

### Community 152 - "Determinism gate"
Cohesion: 0.15
Nodes (9): 1. Soak (`tools/h3re/h3re/soak.py`), 2. Bisector (`tools/h3re/h3re/bisect_tool.py`), 3. Banned-API lint (`tools/lint/banned_api_lint.py`), CI, Determinism gate, Kotlin banned-API lint (`tools/lint/kotlin_banned_api_lint.py`), AdventurePolicy, _int_in() (+1 more)

### Community 153 - "ss"
Cohesion: 0.22
Nodes (3): SetupTest, ss(), WaitActivationMoraleTest

### Community 154 - "ContentErrorCategory"
Cohesion: 0.17
Nodes (11): ContentError, ContentErrorCategory, DUPLICATE, EMPTY_CELL, HEADER, MAPPING, MISSING_CELL, NO_ROWS (+3 more)

### Community 155 - ".parse"
Cohesion: 0.29
Nodes (3): TxtTable, hexBytes(), TxtTest

### Community 162 - "Resources"
Cohesion: 0.35
Nodes (4): Resources, resMap(), resOf(), typedPlayers()

### Community 164 - "PcxTest"
Cohesion: 0.33
Nodes (4): hexOf(), le32(), PcxTest, unhex()

### Community 165 - "Loop: one agent round (advise, fan out, verify, checkpoint)"
Cohesion: 0.18
Nodes (10): Actions, Budget, Evidence, Goal and input, Loop: one agent round (advise, fan out, verify, checkpoint), Notes learned the hard way, Observation, State (+2 more)

### Community 166 - "LOD archive format"
Cohesion: 0.18
Nodes (10): Directory entry (32-byte stride), Errors, Extraction safety, File layout, Header (92 bytes), LOD archive format, Name rules, Open items (+2 more)

### Community 167 - "HoMM3 PCX bitmap variant (clean-room notes)"
Cohesion: 0.18
Nodes (6): Errors, Header (12 bytes), HoMM3 PCX bitmap variant (clean-room notes), Mode selection, Open items, Output model

### Community 168 - "_bld"
Cohesion: 0.31
Nodes (10): 2. Content model (pack schema v1), 5. Economy and integration, _bld(), cost(), f(), income(), f(), other_faction() (+2 more)

### Community 169 - "RealLodTests"
Cohesion: 0.24
Nodes (4): _files(), RealLodTests, RealMapTests, _rel()

### Community 172 - "doc"
Cohesion: 0.31
Nodes (3): doc(), _floats(), VectorsReplayTest

### Community 173 - "Datapack.kt"
Cohesion: 0.49
Nodes (8): bad(), DatapackError, floatErr(), lit(), num(), parse(), value(), ws()

### Community 174 - "Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic)"
Cohesion: 0.20
Nodes (9): Actions, Budget, Evidence, Goal and input, Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic), Observation, State, Stop and escalation (+1 more)

### Community 175 - "Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)"
Cohesion: 0.20
Nodes (9): Actions, Budget, Evidence, Goal and input, Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors), Observation, State, Stop and escalation (+1 more)

### Community 176 - "Battle scenario file (JSON)"
Cohesion: 0.20
Nodes (9): 2. Creatures, 3. Stacks, 4. Heroes, 5. Policy, 6. Choosers, 7. Golden scenario, 8. Pretty output (`--pretty`), Battle scenario file (JSON) (+1 more)

### Community 178 - "Hero simulation core (`sim.hero`): experience, levels and skill gain"
Cohesion: 0.20
Nodes (9): 1. Interface, 2. Content model (pack schema v1), 3. Experience and levels, 4. Level-up, 5. Secondary skills, 6. Policy fields (`HeroPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch) (+1 more)

### Community 179 - "started"
Cohesion: 0.24
Nodes (3): MalformedDestTest, RoadCostCanonicalTest, started()

### Community 185 - "Handoff (resume here)"
Cohesion: 0.22
Nodes (9): Checkpoint 75 notes, Checkpoint 77, Checkpoint 81 (2026-11-02), CI facts (seen on GitHub, run for checkpoint 63), Handoff (resume here), In flight when this was saved (results are NOT in the repo until verified and committed), Loop tooling (done, commit 4dcc384), Needs the owner (+1 more)

### Community 186 - "Android app design (`android/`)"
Cohesion: 0.22
Nodes (8): 0. Problem statement, 10. Determinism and purity impact, 11. Risks, 12. Assumptions (proposed defaults; the owner may overturn any), 13. Out of scope, 14. Open questions for the owner, 8. Build and CI, Android app design (`android/`)

### Community 187 - "HoMM3 .H3M map header (clean-room notes)"
Cohesion: 0.22
Nodes (8): After teams (parsed; then terrain tiles), Conditions and teams, Header, HoMM3 .H3M map header (clean-room notes), Not implemented, Players (8 slots), Verification status, levels()

### Community 188 - "heroes-mobile"
Cohesion: 0.22
Nodes (9): Development loop, Features, heroes-mobile, License, Project laws, Quick start, Repository layout, Status (+1 more)

### Community 189 - "attack_defense_factor"
Cohesion: 0.28
Nodes (4): attack_defense_factor(), _scaled(), _skill(), AttackDefenseTest

### Community 197 - "ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)"
Cohesion: 0.25
Nodes (7): ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build), Alternatives considered, Consequences, Context, Decision, Verification, Why

### Community 198 - "candidate_actions"
Cohesion: 0.29
Nodes (5): 1. Spec grounding and gaps, 5.2 Hit-testing (`:app`, `h3.app.board.BoardGeometry`), candidate_actions(), candidate_commands(), _enemy_at()

### Community 199 - "MVP 0.1: a playable skirmish APK"
Cohesion: 0.25
Nodes (7): Decisions needed from the owner, Goal (one sentence, with its test), MVP 0.1: a playable skirmish APK, Remaining work for 0.1, in order, Risks specific to 0.1, What 0.1 is, and is not, What exists today (checkpoints up to 59, plus agents in flight)

### Community 204 - "Txt"
Cohesion: 0.33
Nodes (3): Txt, Conformance: TXT reader and creature content loader (Kotlin port), Vectors

### Community 206 - "Second brain (project memory)"
Cohesion: 0.29
Nodes (6): Note format, Operations, Principles, Relationship to other records, Second brain (project memory), What never goes in

### Community 207 - "ADR-0004: Android app with a Kotlin engine; Python is the reference oracle"
Cohesion: 0.29
Nodes (7): ADR-0004: Android app with a Kotlin engine; Python is the reference oracle, Amendments (2026-11-01), Consequences, Context, Decision, Risks, Why

### Community 208 - "4. Rendering"
Cohesion: 0.29
Nodes (7): 4.1 Spaces and transform, 4.2 Layers (drawn in this order each frame), 4.3 Sprites and atlas, 4.4 Animation timeline (UI only; closes G2), 4.5 Frame budget (60 fps), 4.6 Placeholder renderer, 4. Rendering

### Community 209 - "Town simulation core (`sim.town`): buildings, build rules and weekly growth"
Cohesion: 0.29
Nodes (6): 3. Building, 6. Policy fields (`TownPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch), Growth pools digest (second pin), Town simulation core (`sim.town`): buildings, build rules and weekly growth

### Community 210 - "VCMI cross-check: file-format specs"
Cohesion: 0.29
Nodes (6): DEF (`docs/specs/def.md`, `tools/h3re/h3re/defimg.py`), H3M (`docs/specs/h3m.md`, `tools/h3re/h3re/h3m.py`), LOD (`docs/specs/lod.md`, `tools/h3re/h3re/lod.py`), PCX (`docs/specs/pcx.md`, `tools/h3re/h3re/pcx.py`), TXT (`docs/specs/txt.md`, `tools/h3re/h3re/txt.py`), VCMI cross-check: file-format specs

### Community 215 - "3. Data import"
Cohesion: 0.33
Nodes (6): 3.1 Principles, 3.2 Flow, 3.3 Editions, 3.4 Files, 3.5 Validation (first run and every import), 3. Data import

### Community 216 - "Conformance: adventure core (Kotlin port)"
Cohesion: 0.33
Nodes (5): Command fields are strict integers, Conformance: adventure core (Kotlin port), Kotlin test (`AdventureTest`), Policy bounds and guard order, Python `repr` in messages

### Community 227 - "Loop graph builder"
Cohesion: 0.40
Nodes (4): Contract template, Loop graph builder, Principles (Karpathy-style, applied), Procedure

### Community 228 - "ADR-0010: The project is licensed GPL-2.0-or-later"
Cohesion: 0.40
Nodes (4): ADR-0010: The project is licensed GPL-2.0-or-later, Consequences, Context, Decision

### Community 229 - "6. Screens and navigation"
Cohesion: 0.40
Nodes (5): 6.1 MVP routes, 6.2 Skirmish setup, 6.3 Behaviour without data, 6.4 Phase after the MVP (outline only), 6. Screens and navigation

### Community 233 - "7. Threading, saves, replay and crash safety"
Cohesion: 0.50
Nodes (4): 7.1 Threads, 7.2 Saves (autosave on every command, as `engine-design.md` 1.6 requires), 7.3 Crash safety, 7. Threading, saves, replay and crash safety

### Community 234 - "index.sh"
Cohesion: 0.50
Nodes (3): GRAPHIFY_BACKEND, GRAPHIFY_QUERY_LOG_DISABLE, index.sh script

## Knowledge Gaps
- **104 isolated node(s):** `Home`, `Setup`, `Battle`, `Result`, `About` (+99 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1368 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **158 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `derive_stream()` connect `vectors.py` to `__init__.py`, `VectorsEncounterTest`, `vectors_town.py`, `soak.py`, `vectors_encounter.py`, `battle.py`, `adventure.py`, `town.py`, `golden_setup`, `golden_game`, `vectors_hero.py`, `hero.py`, `README.md`, `vectors_ai.py`, `BattleCodec`, `dataclasses`, `GoldenTest`, `Battle scenario file (JSON)`, `Present`, `GoldenTest`, `Pcg32`, `ADR-0004: Android app with a Kotlin engine; Python is the reference oracle`, `TestBattleVectors`, `golden_setup`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `HexCell` (e.g. with `.enemyDist()` and `.checkState()`) actually correct?**
  _`HexCell` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Home`, `Setup`, `Battle` to the rest of the system?**
  _104 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0629004076878276 - nodes in this community are weakly interconnected._
- **Why does `Battle state (`battle_states.json`)` connect `BattleCodec` to `BattleStateTest`, `EncounterEngine`, `BattleAiTest`, `vectors.py`, `vectors_encounter.py`, `BattleState`, `BattleEvent`, `.encode`, `BattleCommand`, `dataclasses`, `Replay file format`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `derive_stream()` (e.g. with `sim-engineer.md` and `Laws`) actually correct?**
  _`derive_stream()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `.write` be split into smaller, more focused modules?**
  _Cohesion score 0.057711950970377936 - nodes in this community are weakly interconnected._