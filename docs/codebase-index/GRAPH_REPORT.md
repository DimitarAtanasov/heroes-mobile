# Graph Report - proj  (2026-11-02)

## Corpus Check
- 252 files · ~285,350 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 3, .properties 2, .xml 1)

## Summary
- 5293 nodes · 13305 edges · 324 communities (186 shown, 138 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 904 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- battle.py
- __init__.py
- vectors_town.py
- vectors_encounter.py
- replay.py
- Rational
- loadVector
- H3mTest.kt
- town.py
- soak.py
- test_encounter.py
- derive_stream
- vectors_hero.py
- Battle
- BattleTest
- test_cli.py
- hero.py
- h3m.py
- BattleState
- HexCell
- datapack.py
- .write
- Test
- vectors_battle.py
- Screens.kt
- with
- battle_cli.py
- HeroTest
- Scenario
- SegKind
- AdventureState
- vectors_pack.py
- TownTest
- defimg.py
- adventure.py
- parse_h3m_bytes
- Handoff (resume here)
- Encounter.kt
- BattleStateTest
- encounter.py
- vectors_h3m.py
- kotlin_banned_api_lint.py
- MenuModelTest
- Hero.kt
- TownConformanceTest.kt
- test_h3m.py
- SetupFormTest
- Def
- HeroConformanceTest.kt
- ScriptRng
- Data pack (`h3re.datapack`)
- struct
- BoardGeometry
- SpriteAtlasTest.kt
- AdventureEvent
- Pcg32
- grid
- VectorsHeroTest
- BattleSession
- test_battle_cli.py
- BattleCodec
- .encode
- Replay
- TownState
- test_battle.py
- re
- H3mObjectTests
- .load
- Datapack
- TownCore
- vectors_adventure.py
- build_lod
- game
- VectorsTownTest
- ReplayAutosaveTest
- HeroCore
- content.py
- .parseState
- BattleCommand
- generate
- bisect_tool.py
- parse_pcx
- resolve_damage
- _rules_vectors
- rules
- _Visitor
- BoardView.kt
- LodArchive
- Rules specification
- parse_def
- vectors_replay.py
- cr
- SpriteAtlas.kt
- PolicyPackTest
- _Pretty
- BattleAiTest
- PrettyTest
- AdventureTest
- _run_isolated
- GameController
- LodArchive
- damage_from_base
- test_adventure.py
- Pcg32
- .parse
- EncounterTest
- _Reader
- parse_txt
- PresentTest
- Snapshot
- AdventureCodec
- Rules: battle damage (`rules.json`)
- TestBattleVectors
- vectors_txt.py
- MainActivity.kt
- Txt.kt
- ReplayTest
- Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)
- LintTest
- VectorsEncounterTest
- Town.kt
- Kotlin API
- vectors_lodpcx.py
- .test_every_mutation_changes_the_hash
- Conformance: adventure core (Kotlin port)
- LodTest
- DefTest.kt
- H3mUnsupportedObject
- base_damage
- _oracle
- present.py
- NoRng
- _search
- hero
- module_doc
- App shell (milestone A7, MVP 0.1)
- BattleEvent
- .parseCreatures
- TownText
- txt.py
- MalformedScenarioTest
- AdvGrid
- candidate_actions
- DatapackTest
- banned_api_lint.py
- Adventure-map simulation core (`sim.adventure`): movement and economy
- Android app design (`android/`)
- Conformance: hero core (`h3.sim.hero`)
- Determinism gate
- apply_damage
- test_hero.py
- test_real_files.py
- .parse
- MEMORY.md
- HoMM3 PCX bitmap variant (clean-room notes)
- LoopCheck
- GoldenTest
- H3mVectorTests
- Datapack.kt
- parsePcx
- BattleAiTest
- PcxTest
- Loop: one agent round (advise, fan out, verify, checkpoint)
- TestVectors
- Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)
- LOD archive format
- _bld
- vectors_present.py
- NoRng
- assert_module_deterministic
- LodPcxVectorTests
- GreedyAi
- RngStreams
- ContentErrorCategory
- Conformance: LOD archive and PCX bitmap readers
- .createGameChecked
- Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)
- IllegalCommand
- Hero simulation core (`sim.hero`): experience, levels and skill gain
- DataPack
- started
- IntegerCapTest
- ReadTests
- raw
- TestAdventureVectors
- .fromTree
- HoMM3 .H3M map header (clean-room notes)
- attack_defense_factor
- StrictIntFieldsTest
- RecordingRng
- GoldenTest
- AllowlistTests
- GrowthTest
- Content
- .repr
- ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)
- GameState
- MVP 0.1: a playable skirmish APK
- Sprite atlas builder
- _Reader
- CheckStateTest
- WaitActivationMoraleTest
- BisectPolicyTest
- doc
- PackVectorsTest
- Second brain (project memory)
- 4. Rendering
- 9. Milestones and acceptance criteria
- Town simulation core (`sim.town`): buildings, build rules and weekly growth
- VCMI cross-check: file-format specs
- GeometryTest
- IllegalCommandNoRngTest
- AutosaveSink
- 3. Data import
- TXT tables (tab-separated)
- army
- TickTest
- PolicyAndHeroTest
- PackMismatchTest
- OfferPolicyTest
- CorruptPayloadTests
- MemoryCheck
- StoredContentHashTest
- TestContractEdgeVectors
- Origin
- Loop graph builder
- ADR-0010: The project is licensed GPL-2.0-or-later
- 6. Screens and navigation
- Conformance: data-pack loader (`vectors/datapack.json`)
- Grid
- SkillCheck
- .checkBudget
- DrawSource
- File format
- Conformance: scenario and replay (milestone A5)
- index.sh
- Cli
- TestAll
- RealSourcesTests
- RepoWiring
- RepoFiles
- ADR-0003-vcmi-as-fact-source-clean-room.md
- ADR-0006-state-content-stands-in-for-a-pack-hash.md
- ADR-0007-replay-and-vectors-are-the-cross-language-contract.md

## God Nodes (most connected - your core abstractions)
1. `BattleState` - 94 edges
2. `HexCell` - 79 edges
3. `derive_stream()` - 69 edges
4. `BattleCommand` - 55 edges
5. `Battle` - 54 edges
6. `BattleSession` - 53 edges
7. `Pcg32` - 51 edges
8. `BattleCodec` - 50 edges
9. `Datapack` - 45 edges
10. `TownCore` - 45 edges

## Surprising Connections (you probably didn't know these)
- `Decision` --references--> `BattleSession`  [INFERRED]
  docs/adr/ADR-0011-android-app-architecture.md → android/presenter/src/main/kotlin/h3/presenter/BattleSession.kt
- `Remaining work for 0.1, in order` --references--> `BattleSession`  [INFERRED]
  docs/specs/mvp-0.1.md → android/presenter/src/main/kotlin/h3/presenter/BattleSession.kt
- `Out of scope (Kotlin's types cannot express them)` --references--> `TownTest`  [INFERRED]
  docs/specs/conformance-town.md → android/sim/src/test/kotlin/h3/sim/town/TownTest.kt
- `Default changes and the golden hash` --references--> `GameState`  [INFERRED]
  docs/specs/adventure.md → tools/h3re/h3re/adventure.py
- `5. Policy fields (`EncounterPolicy`)` --references--> `create_battle()`  [INFERRED]
  docs/specs/encounter.md → tools/h3re/h3re/battle.py

## Import Cycles
- 2-file cycle: `tools/h3re/h3re/adventure.py -> tools/h3re/h3re/encounter.py -> tools/h3re/h3re/adventure.py`
- 2-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/__init__.py`
- 2-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`
- 3-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/__init__.py`
- 3-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`

## Communities (324 total, 138 thin omitted)

### Community 0 - "battle.py"
Cohesion: 0.04
Nodes (77): Next, in order, 1. Interface, 2. Grid, 3. Movement [documented], 4. Turn queue, 6. Damage and attacks, 7. Battle end, 8. Uncertain policy summary (+69 more)

### Community 1 - "__init__.py"
Cohesion: 0.07
Nodes (16): _inflate(), LodError, LodFormatError, RollPolicy, _canon_corpus(), _canon_vectors(), check(), main() (+8 more)

### Community 2 - "vectors_town.py"
Cohesion: 0.06
Nodes (61): _b(), _base(), _bigvalues(), _bld(), _canon(), classify_pack(), _cmd(), _create_cases() (+53 more)

### Community 3 - "vectors_encounter.py"
Cohesion: 0.07
Nodes (50): Vector file `hero.json`, all_games(), army(), auto_cases(), _battery(), _bpol(), build_setup(), _case() (+42 more)

### Community 4 - "replay.py"
Cohesion: 0.06
Nodes (31): _canon(), _check_plain(), Diverged, info(), _is_int(), load(), Malformed, MismatchedCreatures (+23 more)

### Community 5 - "Rational"
Cohesion: 0.06
Nodes (20): Rational, DrawSource, AttackDefenseFactor, DamagePreview, DamageResult, DrawSource, RollPolicy, ACTUAL_SEED (+12 more)

### Community 6 - "loadVector"
Cohesion: 0.08
Nodes (8): Holding, asDrawSource(), big(), list(), loadVector(), object@L90, obj(), u64()

### Community 7 - "H3mTest.kt"
Cohesion: 0.09
Nodes (30): H3m, H3mDisposedHero, H3mError, H3mHeader, H3mHotaError, H3mLoss, H3mPlayer, H3mPredefinedHero (+22 more)

### Community 8 - "town.py"
Cohesion: 0.06
Nodes (43): Vector file `town.json`, 1. Interface, 4. Weekly growth, GrowthPool, Resources, _active(), active_buildings(), apply() (+35 more)

### Community 9 - "soak.py"
Cohesion: 0.06
Nodes (24): build_adventure(), build_battle(), build_scenario(), check_seed(), Divergence, _driver(), _events_digest(), _first_diff() (+16 more)

### Community 10 - "test_encounter.py"
Cohesion: 0.09
Nodes (16): army(), BuildBattleTest, flat_grid(), fought(), golden_game(), GoldenTest, IllegalTest, OutcomeTest (+8 more)

### Community 11 - "derive_stream"
Cohesion: 0.06
Nodes (29): Conformance: greedy battle AI (`battle_ai.json`), File layout, Kotlin contract, What is pinned, choose(), _decide(), pick(), _enemy_dist() (+21 more)

### Community 12 - "vectors_hero.py"
Cohesion: 0.08
Nodes (39): _base(), _bigweights(), _canon(), classify_pack(), _cmd(), _create_cases(), add(), _create_error_category() (+31 more)

### Community 13 - "Battle"
Cohesion: 0.09
Nodes (17): ApplyResult, Battle, Damaged, IllegalCommand, Kind, ATTACK, DEFEND, MOVE (+9 more)

### Community 14 - "BattleTest"
Cohesion: 0.11
Nodes (5): TapReducerTest, BattleTest, DrawSource, DrawSource, Outcome

### Community 15 - "test_cli.py"
Cohesion: 0.10
Nodes (12): def_bytes(), DefCommandTests, h3m_bytes(), H3mCommandTests, lod_bytes(), LodCommandTests, ModuleEntryPointTests, png_size() (+4 more)

### Community 16 - "hero.py"
Cohesion: 0.07
Nodes (32): _advance(), apply(), _canon_bytes(), canonical(), _check_class(), _check_total(), ChooseSkill, content_hash() (+24 more)

### Community 17 - "h3m.py"
Cohesion: 0.10
Nodes (35): _army(), _art(), _bits(), _body_abandoned_mine(), _body_artifact(), _body_event(), _body_garrison(), _body_generic() (+27 more)

### Community 18 - "BattleState"
Cohesion: 0.10
Nodes (17): Cancel, Candidate, Confirmed, Previewing, PreviewNumbers, Select, Tap, TapEvent (+9 more)

### Community 19 - "HexCell"
Cohesion: 0.12
Nodes (10): Hex, HexCell, legalCommands(), cell(), cells(), HexTest, 2. Module layout and dependency rules, 1. BoardGeometry (`h3.presenter.BoardGeometry`) (+2 more)

### Community 20 - "datapack.py"
Cohesion: 0.11
Nodes (31): Hashes, Pack directory and rules hash (determinism audit), _check_creatures(), _check_policy(), _check_rules(), DataPackError, _frac(), _int() (+23 more)

### Community 21 - ".write"
Cohesion: 0.13
Nodes (7): AiChooserTest, ChooserTest, CliTestCase, golden_scenario(), GoldenScenarioTest, MainIntegrationTest, tiny_scenario()

### Community 22 - "Test"
Cohesion: 0.12
Nodes (11): DamageCtx, ctxOf(), isError(), loadPack(), long(), longs(), rat(), RationalTest (+3 more)

### Community 23 - "vectors_battle.py"
Cohesion: 0.10
Nodes (29): encode_command(), _ability_creature(), build_ability_scenario(), build_tie_scenario(), cap_setup(), _case(), _driver(), _driver_step() (+21 more)

### Community 24 - "Screens.kt"
Cohesion: 0.08
Nodes (12): GameUi, AboutScreen(), BattleBody(), BattleScreen(), candidateLabel(), HomeScreen(), Page(), PreviewPanel() (+4 more)

### Community 25 - "with"
Cohesion: 0.07
Nodes (39): runs-on, steps, timeout-minutes, runs-on, steps, H3_DATA_DIR, jobs, android-app (+31 more)

### Community 26 - "battle_cli.py"
Cohesion: 0.12
Nodes (27): _ai(), pick(), _check_keys(), _check_pretty_options(), CliError, _creature(), _dataclass_kwargs(), _first_legal() (+19 more)

### Community 27 - "HeroTest"
Cohesion: 0.17
Nodes (4): ChooseSkill, GainXP, HeroTest, Script

### Community 28 - "Scenario"
Cohesion: 0.13
Nodes (7): Preset, BattleCreature, BattleEngine, Scenario, ScenarioError, Setup, ScenarioTest

### Community 29 - "SegKind"
Cohesion: 0.09
Nodes (25): AnimationPrefs, AnimSpeed, FAST, NORMAL, SKIP, SLOW, Frames, SegKind (+17 more)

### Community 30 - "AdventureState"
Cohesion: 0.11
Nodes (14): AdvEncounter, Adventure, AdventureEncounterHooks, AdventureState, AdventureStep, AdvGrowthPool, AdvGuard, AdvHero (+6 more)

### Community 31 - "vectors_pack.py"
Cohesion: 0.11
Nodes (27): with_(), base(), classify(), _collect_invalid(), data_dir(), _delete(), _derived_valid(), dumps() (+19 more)

### Community 33 - "defimg.py"
Cohesion: 0.10
Nodes (19): Blocks, Frame, Header, HoMM3 .DEF sprite container (clean-room notes), Implementation status / caveats, Mismatches, ranked by severity, _decode_frame(), _decode_runs() (+11 more)

### Community 34 - "adventure.py"
Cohesion: 0.08
Nodes (26): adventure_rng(), apply(), Attack, base_movement(), Begin, calendar(), _check_army(), create_game() (+18 more)

### Community 35 - "parse_h3m_bytes"
Cohesion: 0.13
Nodes (9): H3mHeader, parse_h3m(), parse_h3m_bytes(), _read_tiles(), Tile, build(), extra(), H3mTests (+1 more)

### Community 36 - "Handoff (resume here)"
Cohesion: 0.06
Nodes (30): Commands, heroes-mobile: project constitution, Laws, Roles and delegation, Working principles, Checkpoint log, Reverse-engineering loop graph, Checkpoint 75 notes (+22 more)

### Community 37 - "Encounter.kt"
Cohesion: 0.10
Nodes (9): AdventureRules, BattleHero, BattleFought, EncounterEngine, EncounterPolicy, EncounterSetup, Fought, GuardDefeated (+1 more)

### Community 38 - "BattleStateTest"
Cohesion: 0.14
Nodes (3): BattleStateTest, MiniJson, Amendment (2026-11-01): caps on derived products

### Community 39 - "encounter.py"
Cohesion: 0.08
Nodes (20): 1. Document, 2. Header (all keys required, unknown keys rejected), ArmyChanged, battle_id(), BattleFought, build_battle(), check_game(), _creature() (+12 more)

### Community 40 - "vectors_h3m.py"
Cohesion: 0.16
Nodes (26): build(), _Cases, _cond(), _cut_cases(), default_players(), dump_header(), _error_cases(), _expect() (+18 more)

### Community 41 - "kotlin_banned_api_lint.py"
Cohesion: 0.08
Nodes (13): KotlinLintTests, rules(), apply_allowlist(), default_paths(), _entry_matches(), lint_paths(), lint_source(), load_allowlist() (+5 more)

### Community 42 - "MenuModelTest"
Cohesion: 0.12
Nodes (9): menuEdgeAllowed(), MenuModel, MenuRoute, About, Battle, Home, Result, Setup (+1 more)

### Community 43 - "Hero.kt"
Cohesion: 0.14
Nodes (19): asHeroDraw(), Hero, HeroApplyResult, HeroCategory, HeroCommand, HeroDraw, HeroEvent, HeroPolicy (+11 more)

### Community 44 - "TownConformanceTest.kt"
Cohesion: 0.16
Nodes (11): assertError(), canonText(), commandOf(), eventMap(), i32(), kindOf(), lng(), resMap() (+3 more)

### Community 45 - "test_h3m.py"
Cohesion: 0.20
Nodes (21): box(), e_army(), e_box(), e_event_common(), e_hero(), e_monster(), e_msg_guards(), e_opt8() (+13 more)

### Community 46 - "SetupFormTest"
Cohesion: 0.12
Nodes (11): PresetError, NoPresets, OutOfRange, SeedError, Empty, NotDigits, TooLarge, SetupForm (+3 more)

### Community 47 - "Def"
Cohesion: 0.16
Nodes (11): Def, DefBlock, DefException, DefFile, DefFrame, Out, Reader, Ambiguities / notes (+3 more)

### Community 48 - "HeroConformanceTest.kt"
Cohesion: 0.17
Nodes (12): canonText(), commandOf(), CountingDraw, eventMap(), HeroConformanceTest, HeroVectors, i32(), lng() (+4 more)

### Community 49 - "ScriptRng"
Cohesion: 0.14
Nodes (7): begin(), four(), LastMoverOrderTest, MalformedHexTest, MoraleTest, QueueTest, ScriptRng

### Community 50 - "Data pack (`h3re.datapack`)"
Cohesion: 0.07
Nodes (24): API, Battle policy pack, Data pack (`h3re.datapack`), Determinism and hash, Drift guard, Files, Integer range, Runtime loading (checkpoint 34) (+16 more)

### Community 51 - "struct"
Cohesion: 0.18
Nodes (21): _bad_cases(), single(), build_def(), case(), encode_body(), _format_cases(), one(), frame_blob() (+13 more)

### Community 52 - "BoardGeometry"
Cohesion: 0.16
Nodes (6): BoardGeometry, footprints(), Pt, UnitFootprint, UnitHit, BoardGeometryTest

### Community 53 - "SpriteAtlasTest.kt"
Cohesion: 0.18
Nodes (11): Atlas, FrameMeta, Rect, assertSameAtlas(), checkInvariants(), hex(), ok(), randomFrames() (+3 more)

### Community 54 - "AdventureEvent"
Cohesion: 0.07
Nodes (16): AdvArmySlot, AdventureEvent, DayStarted, HeroMoved, MovementReset, PoolGrew, TurnEnded, TurnStarted (+8 more)

### Community 55 - "Pcg32"
Cohesion: 0.13
Nodes (3): Pcg32, _TracedPcg32, TestPcg32

### Community 56 - "grid"
Cohesion: 0.12
Nodes (5): game(), grid(), PolicyTest, StepCostTest, costs()

### Community 57 - "VectorsHeroTest"
Cohesion: 0.13
Nodes (4): doc(), _floats(), _steps(), VectorsHeroTest

### Community 58 - "BattleSession"
Cohesion: 0.13
Nodes (10): BattleSession, LogEntry, Submission, drive(), 1. Scope, 3. `BattleSession` (android-app.md 7.1, ADR-0012), 4. Tests (`android/presenter/src/test/kotlin/h3/presenter/`), 5. Not yet here (+2 more)

### Community 59 - "test_battle_cli.py"
Cohesion: 0.11
Nodes (15): build_parser(), cmd_battle_sim(), cmd_def_to_png(), cmd_h3m_info(), cmd_lod_extract(), cmd_lod_list(), cmd_replay(), _condition() (+7 more)

### Community 60 - "BattleCodec"
Cohesion: 0.15
Nodes (11): AppEngine, plain(), Fixture, Game, BattleAi, BattleCodec, BattlePolicy, BattlePolicyPack (+3 more)

### Community 61 - ".encode"
Cohesion: 0.14
Nodes (4): Canonical, ConformanceTest, PresentTest, ADR-0009: The Kotlin engine uses a small exact Rational type with one named rounding step, not an integer rewrite

### Community 62 - "Replay"
Cohesion: 0.21
Nodes (13): Diverged, Loaded, Malformed, MismatchedCreatures, MismatchedPolicy, MismatchedRulesPack, Replay, ReplayError (+5 more)

### Community 63 - "TownState"
Cohesion: 0.19
Nodes (8): Building, GrowthPool, IllegalCommand, Resources, Town, TownState, resOf(), typedPlayers()

### Community 64 - "test_battle.py"
Cohesion: 0.12
Nodes (9): golden_setup(), GoldenTest, play(), PolicyDefaultsFromPackTest, PreviewLawTest, PropertyTest, scripted_choice(), total_hp() (+1 more)

### Community 65 - "re"
Cohesion: 0.13
Nodes (17): golden_scenario(), ReplayCliTest, _back_edges(), visit(), eval_graph(), eval_run(), _load_run(), main() (+9 more)

### Community 66 - "H3mObjectTests"
Cohesion: 0.18
Nodes (5): e_objects(), e_template(), H3mObjectTests, map_with(), tmpl()

### Community 67 - ".load"
Cohesion: 0.11
Nodes (18): ByteSink, Failed, Ok, ReplayAutosave, ReplayResume, Resumed, ResumeError, Diverged (+10 more)

### Community 68 - "Datapack"
Cohesion: 0.19
Nodes (6): CreaturesDoc, Datapack, PolicyDoc, RulesDoc, ReplayVectors, API (Kotlin)

### Community 69 - "TownCore"
Cohesion: 0.15
Nodes (4): Faction, TownContent, TownCore, TownKeyError

### Community 70 - "vectors_adventure.py"
Cohesion: 0.13
Nodes (19): _decode(), encode_event(), generate(), golden_commands(), golden_setup(), illegal_cases(), _illegal_commands(), _initial_state() (+11 more)

### Community 71 - "build_lod"
Cohesion: 0.20
Nodes (5): build_lod(), ExtractTests, MalformedInputTests, member(), open_bytes()

### Community 72 - "game"
Cohesion: 0.14
Nodes (6): build(), build_days(), BuildTest, game(), IncomeTest, NoRng

### Community 73 - "VectorsTownTest"
Cohesion: 0.14
Nodes (7): _cmd(), doc(), _err(), _floats(), NoRng, _steps(), VectorsTownTest

### Community 74 - "ReplayAutosaveTest"
Cohesion: 0.22
Nodes (4): Case, MemSink, ReplayAutosaveTest, Run

### Community 75 - "HeroCore"
Cohesion: 0.17
Nodes (4): HeroClass, HeroContent, HeroCore, HeroRules

### Community 76 - "content.py"
Cohesion: 0.20
Nodes (11): ContentError, ContentResult, _int(), _layout(), load_creatures(), load_mapping(), _norm(), parse_creatures() (+3 more)

### Community 78 - "BattleCommand"
Cohesion: 0.16
Nodes (9): Attack, BattleCommand, Begin, Defend, Move, Shoot, Wait, LegalTest (+1 more)

### Community 79 - "generate"
Cohesion: 0.11
Nodes (18): Test cost, _core_outputs(), _cr(), _dump(), generate(), generate_fresh(), golden_setup(), _grid_cells() (+10 more)

### Community 80 - "bisect_tool.py"
Cohesion: 0.13
Nodes (16): bisect(), diff_states(), dump_log(), flatten(), format_policy(), format_report(), load_log(), load_log_ex() (+8 more)

### Community 81 - "parse_pcx"
Cohesion: 0.16
Nodes (6): parse_pcx(), PcxError, bgr_2x2(), indexed_2x2(), PcxErrorTests, PcxParseTests

### Community 82 - "resolve_damage"
Cohesion: 0.16
Nodes (9): _check_flags(), DamageCtx, DamagePreview, DamageResult, preview_damage(), resolve_damage(), _settle(), random_ctx() (+1 more)

### Community 83 - "_rules_vectors"
Cohesion: 0.11
Nodes (20): _attack_defense_vectors(), _base_damage_vectors(), _chance_vectors(), _clamp_attack(), _ctx_json(), _damage_from_base_kwargs(), _damage_from_base_vectors(), _pack_json() (+12 more)

### Community 84 - "rules"
Cohesion: 0.18
Nodes (3): GraphCriteria, rules(), RunCriteria

### Community 85 - "_Visitor"
Cohesion: 0.16
Nodes (3): _is_set_expr(), Violation, _Visitor

### Community 86 - "BoardView.kt"
Cohesion: 0.11
Nodes (5): BoardView(), drawBoard(), drawToken(), glyph(), hexPath()

### Community 88 - "Rules specification"
Cohesion: 0.08
Nodes (23): 0. Provenance and tagging, 1. Calendar and turn structure, 2.1 Movement points (land), 2.2 Terrain cost, 2. Adventure map: movement, 3. Resource economy, 4. Towns, 5.1 Primary skills (+15 more)

### Community 89 - "parse_def"
Cohesion: 0.22
Nodes (7): Block, DefFile, parse_def(), build_def(), build_shared(), DefTests, frame_bytes()

### Community 90 - "vectors_replay.py"
Cohesion: 0.16
Nodes (19): run_chooser(), _creature_dict(), _explicit_pos_scenario(), generate(), _golden(), _hero_dict(), _jsonable(), main() (+11 more)

### Community 91 - "cr"
Cohesion: 0.19
Nodes (5): CombatTest, cr(), MovementTest, SetupTest, ss()

### Community 92 - "SpriteAtlas.kt"
Cohesion: 0.12
Nodes (14): add(), addAll(), AtlasFrame, BuildResult, Failed, MaskPage, Ok, Page (+6 more)

### Community 93 - "PolicyPackTest"
Cohesion: 0.11
Nodes (7): ADR-0008: Kotlin pack values are 32-bit Int capped at 2**31-1; hashes and XP accumulation use Long, LoadTest, PolicyPackTest, bad(), raw(), raw_policy(), ValidationTest

### Community 94 - "_Pretty"
Cohesion: 0.12
Nodes (12): Files, _board_lines(), _fields(), _hp(), _legend_lines(), _mark(), _pos_text(), _Pretty (+4 more)

### Community 95 - "BattleAiTest"
Cohesion: 0.12
Nodes (9): 1. Encoding, 3. Body, 4. Verification order and errors, 5. API and CLI, 6. Notes, Replay file format, BattleAiTest, play() (+1 more)

### Community 96 - "PrettyTest"
Cohesion: 0.21
Nodes (3): _board_at(), _grid_rows(), PrettyTest

### Community 98 - "_run_isolated"
Cohesion: 0.14
Nodes (6): _probe(), _repo_data_dir(), _run_isolated(), TestBattleExports, TestImportSideEffects, TestRulesPackIdentity

### Community 99 - "GameController"
Cohesion: 0.18
Nodes (3): GameController, Battle interaction, Verified here (JVM, `gradle --offline :sim:test :presenter:test`)

### Community 100 - "LodArchive"
Cohesion: 0.17
Nodes (5): inflateMember(), LodArchive, LodEntry, LodError, LodFormatError

### Community 101 - "damage_from_base"
Cohesion: 0.15
Nodes (8): 6.6 Damage formula, 1. Mismatches (ranked by gameplay impact), Notes on VCMI-only behaviour we should **not** copy, defend_bonus(), damage_from_base(), damage_range(), DamageFromBaseTest, DamageRangeTest

### Community 102 - "test_adventure.py"
Cohesion: 0.16
Nodes (7): FloatSub, golden_setup(), GoldenTest, IntSub, play_days(), PropertyTest, scripted_turn()

### Community 103 - "Pcg32"
Cohesion: 0.16
Nodes (3): Pcg32, Edge, RngEdgeTest

### Community 104 - ".parse"
Cohesion: 0.29
Nodes (4): enc(), EncounterConformanceTest, EncVectors, s()

### Community 106 - "_Reader"
Cohesion: 0.18
Nodes (9): H3mError, PlayerInfo, _read_extra(), _read_loss(), _read_mask(), _read_player(), _read_predefined(), _read_victory() (+1 more)

### Community 107 - "parse_txt"
Cohesion: 0.18
Nodes (3): parse_txt(), build(), TxtTests

### Community 108 - "PresentTest"
Cohesion: 0.15
Nodes (5): all_states(), FailRng, PresentTest, synthetic_states(), walk()

### Community 109 - "Snapshot"
Cohesion: 0.22
Nodes (10): Accepted, Faulted, Illegal, NotYourTurn, Over, ShutDown, Snapshot, Stale (+2 more)

### Community 110 - "AdventureCodec"
Cohesion: 0.18
Nodes (6): AdventureCodec, AdventureCommand, Attack, Begin, EndTurn, Move

### Community 111 - "Rules: battle damage (`rules.json`)"
Cohesion: 0.18
Nodes (11): 5. Morale and luck, Conformance vectors (Python -> Kotlin), Generating and checking, Python/Kotlin differences resolved, Rules: battle damage (`rules.json`), 8. Reference implementation, bad_morale_chance(), _clamp3() (+3 more)

### Community 112 - "TestBattleVectors"
Cohesion: 0.15
Nodes (3): decode_command(), stream_at(), TestBattleVectors

### Community 113 - "vectors_txt.py"
Cohesion: 0.20
Nodes (14): _base(), _content_case(), _content_cases(), _content_error(), _creature_row(), generate(), _header(), _Lcg (+6 more)

### Community 115 - "Txt.kt"
Cohesion: 0.14
Nodes (8): Txt, TxtError, TxtErrorCategory, DECODE, HEADER_ROWS, TOO_LARGE, TOO_MANY_LINES, UNKNOWN_ENCODING

### Community 117 - "Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)"
Cohesion: 0.11
Nodes (13): ADR-0001: Canonical JSON form and SHA-256 state hash for battle and adventure state, ADR-0005: The omit-at-default canonical mechanism applies to every state module, not only battle, 3. The battle, 4. Outcome, 5. Policy fields (`EncounterPolicy`), 7. Golden encounter hash, 8. Tests, 9. Open items (+5 more)

### Community 120 - "Town.kt"
Cohesion: 0.19
Nodes (13): Category, BuildingBuilt, Dwelling, NewDay, RawResources, RawSetup, TownApplyResult, TownCategory (+5 more)

### Community 121 - "Kotlin API"
Cohesion: 0.29
Nodes (6): JsonFraction, P, Rejected, ScenarioJson, Syntax, Kotlin API

### Community 122 - "vectors_lodpcx.py"
Cohesion: 0.18
Nodes (10): Vectors, _entry_pos(), generate(), _lod(), _lod_cases(), _member(), _patch_u32(), _pcx_cases() (+2 more)

### Community 123 - ".test_every_mutation_changes_the_hash"
Cohesion: 0.17
Nodes (5): StoredContentHashTest, high(), low(), sec(), start()

### Community 124 - "Conformance: adventure core (Kotlin port)"
Cohesion: 0.14
Nodes (13): 6. Policy fields (`AdventurePolicy`), Default changes and the golden hash, Integer bounds and types (amendment, ADR-0008 style), Command fields are strict integers, Conformance: adventure core (Kotlin port), Kotlin test (`AdventureTest`), Policy bounds and guard order, Python `repr` in messages (+5 more)

### Community 125 - "LodTest"
Cohesion: 0.29
Nodes (6): categoryOf(), hexOf(), le32(), LodTest, oneMember(), unhex()

### Community 126 - "DefTest.kt"
Cohesion: 0.29
Nodes (5): DefTest, hex(), hexStr(), long(), sha()

### Community 127 - "H3mUnsupportedObject"
Cohesion: 0.14
Nodes (11): End of data, Global events, Object instances, Objects, object instances and events (`objects=True`), Template table, Unverified assumptions (objects section), Features, H3mUnsupportedObject (+3 more)

### Community 128 - "base_damage"
Cohesion: 0.17
Nodes (7): Algorithm, API, Deterministic RNG (`sim.rng`), Named streams, base_damage(), BaseDamageTest, FixedRng

### Community 129 - "_oracle"
Cohesion: 0.17
Nodes (5): _decode_name(), _key(), LodEntry, add(), _oracle()

### Community 130 - "present.py"
Cohesion: 0.23
Nodes (11): _actions(), slot(), target_slot(), command_to_dict(), _grid(), _hx(), _preview(), _queue() (+3 more)

### Community 132 - "_search"
Cohesion: 0.14
Nodes (8): ADR-0002: Integer-only simulation (int and Fraction, one explicit rounding step), _diagonal(), _div(), _orth_cost(), _paid(), _search(), step_cost(), _step_parts()

### Community 133 - "hero"
Cohesion: 0.25
Nodes (4): gain(), hero(), LevelUpTest, XpTest

### Community 134 - "module_doc"
Cohesion: 0.17
Nodes (3): DefVectorTests, VectorsTxtTest, module_doc()

### Community 135 - "App shell (milestone A7, MVP 0.1)"
Cohesion: 0.14
Nodes (13): Screen, About, Battle, Home, Result, Setup, App shell (milestone A7, MVP 0.1), Data packs (+5 more)

### Community 136 - "BattleEvent"
Cohesion: 0.27
Nodes (13): BattleEnded, BattleEvent, BattleStarted, DamageDealt, Defended, LuckRolled, MoraleBoost, MoraleFrozen (+5 more)

### Community 137 - ".parseCreatures"
Cohesion: 0.26
Nodes (7): ContentError, ContentResult, Creature, CreatureValidator, DefaultCreatureValidator, UnknownAbility, Kotlin notes and known divergences

### Community 138 - "TownText"
Cohesion: 0.20
Nodes (5): TownText, Conformance: town core (`h3.sim.town`), Known differences (documented, not silent), Mutation check (producer's run, in a private copy; the lead re-verifies), Out of scope (Kotlin's types cannot express them)

### Community 139 - "txt.py"
Cohesion: 0.20
Nodes (4): read_txt(), _scan(), TxtError, TxtTable

### Community 140 - "MalformedScenarioTest"
Cohesion: 0.24
Nodes (4): MalformedScenarioTest, delete(), set_(), mutate()

### Community 141 - "AdvGrid"
Cohesion: 0.35
Nodes (3): AdventurePolicy, AdvGrid, AdvTile

### Community 142 - "candidate_actions"
Cohesion: 0.18
Nodes (9): 1. Spec grounding and gaps, 5.1 Preview and confirm (pure reducer in `:presenter`), 5.2 Hit-testing (`:app`, `h3.app.board.BoardGeometry`), 5.3 Accessibility, 5.4 Layout, 5. Touch interaction, candidate_actions(), candidate_commands() (+1 more)

### Community 144 - "banned_api_lint.py"
Cohesion: 0.23
Nodes (7): apply_allowlist(), _entry_matches(), _is_dict_view(), lint_paths(), lint_source(), load_allowlist(), main()

### Community 145 - "Adventure-map simulation core (`sim.adventure`): movement and economy"
Cohesion: 0.18
Nodes (10): 1. Interface, 2. Grid and step costs, 3. Movement points, 4. Pathfinding, 5. Calendar, income and growth, 7. Tests, 8. Encounters (battles on the map), Adventure-map simulation core (`sim.adventure`): movement and economy (+2 more)

### Community 146 - "Android app design (`android/`)"
Cohesion: 0.15
Nodes (12): 0. Problem statement, 10. Determinism and purity impact, 11. Risks, 12. Assumptions (proposed defaults; the owner may overturn any), 13. Out of scope, 14. Open questions for the owner, 7.1 Threads, 7.2 Saves (autosave on every command, as `engine-design.md` 1.6 requires) (+4 more)

### Community 147 - "Conformance: hero core (`h3.sim.hero`)"
Cohesion: 0.19
Nodes (8): Conformance: hero core (`h3.sim.hero`), Known differences (documented, not silent), Mutation check (producer's run, in a private copy; the lead re-verifies), Out of scope (Kotlin's types cannot express them), _check_draw_inputs(), IllegalCommand, level_for_xp(), _validate()

### Community 148 - "Determinism gate"
Cohesion: 0.15
Nodes (9): 1. Soak (`tools/h3re/h3re/soak.py`), 2. Bisector (`tools/h3re/h3re/bisect_tool.py`), 3. Banned-API lint (`tools/lint/banned_api_lint.py`), CI, Determinism gate, Kotlin banned-API lint (`tools/lint/kotlin_banned_api_lint.py`), AdventurePolicy, _int_in() (+1 more)

### Community 149 - "apply_damage"
Cohesion: 0.22
Nodes (5): 2. Confirmed (VCMI agrees with our default or our documented value), 3. Items VCMI does not settle, VCMI cross-check of `rules.md` / `battle.md` uncertain items, apply_damage(), ApplyDamageTest

### Community 150 - "test_hero.py"
Cohesion: 0.24
Nodes (4): PackTest, raw(), resolve(), with_class()

### Community 151 - "test_real_files.py"
Cohesion: 0.23
Nodes (4): _files(), RealLodTests, RealMapTests, _rel()

### Community 152 - ".parse"
Cohesion: 0.29
Nodes (3): TxtTable, hexBytes(), TxtTest

### Community 154 - "HoMM3 PCX bitmap variant (clean-room notes)"
Cohesion: 0.18
Nodes (7): Errors, Header (12 bytes), HoMM3 PCX bitmap variant (clean-room notes), Mode selection, Open items, Output model, PcxImage

### Community 158 - "Datapack.kt"
Cohesion: 0.42
Nodes (9): bad(), DatapackError, floatErr(), lit(), num(), parse(), pyRepr(), value() (+1 more)

### Community 159 - "parsePcx"
Cohesion: 0.31
Nodes (7): parsePcx(), PcxError, PcxImage, PcxMode, BGR24, INDEXED, u32le()

### Community 161 - "PcxTest"
Cohesion: 0.33
Nodes (4): hexOf(), le32(), PcxTest, unhex()

### Community 162 - "Loop: one agent round (advise, fan out, verify, checkpoint)"
Cohesion: 0.18
Nodes (10): Actions, Budget, Evidence, Goal and input, Loop: one agent round (advise, fan out, verify, checkpoint), Notes learned the hard way, Observation, State (+2 more)

### Community 164 - "Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)"
Cohesion: 0.18
Nodes (8): Abilities, API, Column order (data: `data/txt_maps/crtraits.json`, unverified), Content loader (`h3re.content`), engine roadmap Phase 4 (creatures), Errors, Reading, Tests, RealCrtraitsTest

### Community 165 - "LOD archive format"
Cohesion: 0.18
Nodes (10): Directory entry (32-byte stride), Errors, Extraction safety, File layout, Header (92 bytes), LOD archive format, Name rules, Open items (+2 more)

### Community 166 - "_bld"
Cohesion: 0.31
Nodes (10): 2. Content model (pack schema v1), 5. Economy and integration, _bld(), cost(), f(), income(), f(), other_faction() (+2 more)

### Community 167 - "vectors_present.py"
Cohesion: 0.31
Nodes (7): _canon(), _entries(), generate(), main(), _playouts(), _sha(), _taps()

### Community 171 - "GreedyAi"
Cohesion: 0.24
Nodes (7): LongPress, GreedyAi, ADR-0012: The session AI is a pure function of the state, Behaviour change, Consequences, Context, Decision

### Community 173 - "ContentErrorCategory"
Cohesion: 0.20
Nodes (10): ContentErrorCategory, DUPLICATE, EMPTY_CELL, HEADER, MAPPING, MISSING_CELL, NO_ROWS, NOT_INTEGER (+2 more)

### Community 174 - "Conformance: LOD archive and PCX bitmap readers"
Cohesion: 0.24
Nodes (8): LodKeyError, Conformance: LOD archive and PCX bitmap readers, Discrepancies flagged (CLAUDE.md law 10), Error categories, Port fidelity, Results, Scope, _check_member_name()

### Community 175 - ".createGameChecked"
Cohesion: 0.27
Nodes (5): TownPolicy, TownSetup, TownValueError, policyOf(), typedTowns()

### Community 176 - "Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)"
Cohesion: 0.20
Nodes (9): Actions, Budget, Evidence, Goal and input, Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors), Observation, State, Stop and escalation (+1 more)

### Community 177 - "IllegalCommand"
Cohesion: 0.22
Nodes (6): 2026-11-01: malformed hex raises IllegalCommand (no re-pin), 2. Validation, _as_tile(), IllegalCommand, reachable(), _validate()

### Community 178 - "Hero simulation core (`sim.hero`): experience, levels and skill gain"
Cohesion: 0.20
Nodes (9): 1. Interface, 2. Content model (pack schema v1), 3. Experience and levels, 4. Level-up, 5. Secondary skills, 6. Policy fields (`HeroPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch) (+1 more)

### Community 179 - "DataPack"
Cohesion: 0.22
Nodes (4): _build(), DataPack, _is_frac(), _is_frac_table()

### Community 180 - "started"
Cohesion: 0.24
Nodes (3): MalformedDestTest, RoadCostCanonicalTest, started()

### Community 185 - ".fromTree"
Cohesion: 0.39
Nodes (3): CreatureMapping, MapColumn, ContentTest

### Community 186 - "HoMM3 .H3M map header (clean-room notes)"
Cohesion: 0.22
Nodes (8): After teams (parsed; then terrain tiles), Conditions and teams, Header, HoMM3 .H3M map header (clean-room notes), Not implemented, Players (8 slots), Verification status, levels()

### Community 187 - "attack_defense_factor"
Cohesion: 0.28
Nodes (4): attack_defense_factor(), _scaled(), _skill(), AttackDefenseTest

### Community 193 - "Content"
Cohesion: 0.36
Nodes (3): Content, Conformance: TXT reader and creature content loader (Kotlin port), Vectors

### Community 195 - "ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)"
Cohesion: 0.25
Nodes (7): ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build), Alternatives considered, Consequences, Context, Decision, Verification, Why

### Community 196 - "GameState"
Cohesion: 0.25
Nodes (8): 10. Change notes, 2026-11-01: golden hash re-pinned a second time (rules pack in the hash), 2026-11-01: golden hash re-pinned (one reviewed change), 2026-11-01: state invariants and integer caps (no re-pin), Later: policy defaults moved to data, `apply` checks the pack (no re-pin), 1. Interface, GameState, HeroMoved

### Community 197 - "MVP 0.1: a playable skirmish APK"
Cohesion: 0.25
Nodes (7): Decisions needed from the owner, Goal (one sentence, with its test), MVP 0.1: a playable skirmish APK, Remaining work for 0.1, in order, Risks specific to 0.1, What 0.1 is, and is not, What exists today (checkpoints up to 59, plus agents in flight)

### Community 198 - "Sprite atlas builder"
Cohesion: 0.25
Nodes (7): Input and output, Mask pages, Memory (4.5), Open points, Packing, Pixel conversion, Sprite atlas builder

### Community 203 - "doc"
Cohesion: 0.39
Nodes (3): doc(), _floats(), VectorsAiTest

### Community 205 - "Second brain (project memory)"
Cohesion: 0.29
Nodes (6): Note format, Operations, Principles, Relationship to other records, Second brain (project memory), What never goes in

### Community 206 - "4. Rendering"
Cohesion: 0.29
Nodes (7): 4.1 Spaces and transform, 4.2 Layers (drawn in this order each frame), 4.3 Sprites and atlas, 4.4 Animation timeline (UI only; closes G2), 4.5 Frame budget (60 fps), 4.6 Placeholder renderer, 4. Rendering

### Community 207 - "9. Milestones and acceptance criteria"
Cohesion: 0.29
Nodes (5): 9. Milestones and acceptance criteria, Conformance: presenter view v2 (`h3.sim.Present`), States, What is pinned, view_json()

### Community 208 - "Town simulation core (`sim.town`): buildings, build rules and weekly growth"
Cohesion: 0.29
Nodes (6): 3. Building, 6. Policy fields (`TownPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch), Growth pools digest (second pin), Town simulation core (`sim.town`): buildings, build rules and weekly growth

### Community 209 - "VCMI cross-check: file-format specs"
Cohesion: 0.29
Nodes (6): DEF (`docs/specs/def.md`, `tools/h3re/h3re/defimg.py`), H3M (`docs/specs/h3m.md`, `tools/h3re/h3re/h3m.py`), LOD (`docs/specs/lod.md`, `tools/h3re/h3re/lod.py`), PCX (`docs/specs/pcx.md`, `tools/h3re/h3re/pcx.py`), TXT (`docs/specs/txt.md`, `tools/h3re/h3re/txt.py`), VCMI cross-check: file-format specs

### Community 212 - "AutosaveSink"
Cohesion: 0.40
Nodes (5): AutosaveSink, session(), 1. Autosave, 3. Acceptance, Replay autosave and resume

### Community 213 - "3. Data import"
Cohesion: 0.33
Nodes (6): 3.1 Principles, 3.2 Flow, 3.3 Editions, 3.4 Files, 3.5 Validation (first run and every import), 3. Data import

### Community 214 - "TXT tables (tab-separated)"
Cohesion: 0.33
Nodes (5): API, Format, Limits, Options (backward compatibility), TXT tables (tab-separated)

### Community 224 - "Origin"
Cohesion: 0.40
Nodes (5): Origin, Ai, Human, Replay, Session

### Community 225 - "Loop graph builder"
Cohesion: 0.40
Nodes (4): Contract template, Loop graph builder, Principles (Karpathy-style, applied), Procedure

### Community 226 - "ADR-0010: The project is licensed GPL-2.0-or-later"
Cohesion: 0.40
Nodes (4): ADR-0010: The project is licensed GPL-2.0-or-later, Consequences, Context, Decision

### Community 227 - "6. Screens and navigation"
Cohesion: 0.40
Nodes (5): 6.1 MVP routes, 6.2 Skirmish setup, 6.3 Behaviour without data, 6.4 Phase after the MVP (outline only), 6. Screens and navigation

### Community 228 - "Conformance: data-pack loader (`vectors/datapack.json`)"
Cohesion: 0.40
Nodes (4): Conformance: data-pack loader (`vectors/datapack.json`), Error classes, File layout, Known limits

### Community 232 - ".checkBudget"
Cohesion: 0.83
Nodes (3): BudgetCheck, Exceeded, Within

### Community 234 - "File format"
Cohesion: 0.50
Nodes (4): `canonical_json.json`, File format, `rng.json`, `state_hash.json`

### Community 235 - "Conformance: scenario and replay (milestone A5)"
Cohesion: 0.50
Nodes (3): Conformance: scenario and replay (milestone A5), Known differences (documented, not silent), Vector file `replay.json`

### Community 236 - "index.sh"
Cohesion: 0.50
Nodes (3): GRAPHIFY_BACKEND, GRAPHIFY_QUERY_LOG_DISABLE, index.sh script

## Knowledge Gaps
- **78 isolated node(s):** `Home`, `Setup`, `Battle`, `Result`, `About` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1330 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **138 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `derive_stream()` connect `derive_stream` to `battle.py`, `__init__.py`, `vectors_town.py`, `vectors_encounter.py`, `Rational`, `town.py`, `soak.py`, `test_encounter.py`, `vectors_hero.py`, `hero.py`, `test_hero.py`, `vectors_battle.py`, `GoldenTest`, `adventure.py`, `Handoff (resume here)`, `Pcg32`, `BattleSession`, `BattleCodec`, `GoldenTest`, `test_battle.py`, `9. Milestones and acceptance criteria`, `generate`, `_rules_vectors`, `test_adventure.py`, `TestBattleVectors`, `VectorsEncounterTest`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `HexCell` (e.g. with `.enemyDist()` and `.checkState()`) actually correct?**
  _`HexCell` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Home`, `Setup`, `Battle` to the rest of the system?**
  _78 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `battle.py` be split into smaller, more focused modules?**
  _Cohesion score 0.03901098901098901 - nodes in this community are weakly interconnected._
- **Why does `Battle state (`battle_states.json`)` connect `BattleCodec` to `battle.py`, `vectors_encounter.py`, `Encounter.kt`, `BattleStateTest`, `BattleEvent`, `derive_stream`, `Battle`, `BattleCommand`, `Rules: battle damage (`rules.json`)`, `vectors_battle.py`, `Scenario`, `.encode`, `BattleAiTest`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `derive_stream()` (e.g. with `sim-engineer.md` and `Laws`) actually correct?**
  _`derive_stream()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0746922024623803 - nodes in this community are weakly interconnected._