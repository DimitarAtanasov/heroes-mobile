# Graph Report - proj  (2026-11-02)

## Corpus Check
- 305 files · ~342,481 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 3, .properties 2, .xml 1)

## Summary
- 6308 nodes · 16341 edges · 350 communities (190 shown, 160 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 1004 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- GameDataCheckTest
- assertequals
- AdventureState
- .write
- LodArchive
- vectors_town.py
- vectors.py
- json
- soak.py
- vectors_encounter.py
- BattleSession
- LodArchive
- SaveSlots
- H3mTest.kt
- parse_pcx
- town.py
- Datapack
- hero.py
- test_encounter.py
- battle.py
- parse_txt
- BattleLogTest
- Handoff (resume here)
- ReplayAutosaveTest
- Scenario
- datapack.py
- BattleCodec
- HexCell
- Android app design (`android/`)
- MainActivity.kt
- BattleState
- Battle
- BattleCommand
- Adventure
- test_cli.py
- resolve_damage
- BoardView.kt
- h3m.py
- replay.py
- with
- vectors_battle.py
- .load
- HeroTest
- SegKind
- battle_cli.py
- SpriteLoadPlan.kt
- BoardFitTest
- TownTest
- Test
- adventure.py
- parse_h3m_bytes
- BattleStateTest
- TownConformanceTest.kt
- vectors_h3m.py
- ImportPlanTest
- MenuModelTest
- test_h3m.py
- ScriptRng
- Def
- HeroConformanceTest.kt
- encounter.py
- vectors_hero.py
- .boardStacks
- Rational
- AdventureTest
- Rules
- parse_creatures
- real_report.py
- vectors_adventure.py
- grid
- BoardGeometry
- DefError
- defimg.py
- struct
- Pcg32
- test_battle.py
- cr
- VectorsHeroTest
- DataPack
- Hero.kt
- vectors_pack.py
- SpriteAtlasTest.kt
- lod.py
- H3mObjectTests
- .report
- .encode
- HeroCore
- TownCore
- parse_def
- battle_ai.py
- VectorsTownTest
- argparse
- vectors_replay.py
- Atlas
- SetupForm
- .parseState
- turn_order
- Rules specification
- bisect_tool.py
- rules
- _Visitor
- Test
- ImportPlan
- BattleTest
- EncounterConformanceTest.kt
- EncounterTest
- PolicyPackTest
- re
- kotlin_banned_api_lint.py
- ResumeError
- GameDataLayoutTest
- ImportPlanTest.kt
- _activate_next
- TestBattleVectors
- _run_isolated
- PresentTest
- game
- StackRosterRow
- GameController
- _Pretty
- _Reader
- idle_def
- GameDataStore
- .parseCreatures
- .validate
- apply_damage
- GameDataStore.kt
- SetupFormTest
- TapReducerTest
- StackRosterTest
- TownState
- H3mUnsupportedObject
- base_damage
- vectors_txt.py
- TapState
- Town simulation core (`sim.town`): buildings, build rules and weekly growth
- LintTest
- App shell (milestone A7, MVP 0.1)
- AtlasFrame
- ResultSummaryTest
- Town.kt
- ReplayTest
- __main__.py
- Adventure-map simulation core (`sim.adventure`): movement and economy
- verify
- _valid_cases
- .test_every_mutation_changes_the_hash
- module_doc
- VectorsEncounterTest
- ManifestError
- Resources
- TownText
- Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)
- MEMORY.md
- BattleAiTest
- present.py
- NoRng
- SpriteLoader.kt
- ManifestFile
- Pcg32
- _search
- render
- golden_setup
- hero
- lod
- ImportTextTest
- BattleEvent
- Txt.kt
- .parse
- LegalTest
- test_real_report.py
- TestAdventureVectors
- Runbook: smoke-test the debug app on a real Android phone
- Integer bounds and types (amendment, ADR-0008 style)
- Battle roster from the player's CRTRAITS.TXT
- damage_from_base
- test_hero.py
- GoldenTest
- ManifestReader
- SpriteImportNameCrossCheckTest
- ContentErrorCategory
- .parse
- StrictIntFieldsTest
- _states
- KotlinLintTests
- LoopCheck
- H3mVectorTests
- IoStage
- BattleAiTest
- Loop: one agent round (advise, fan out, verify, checkpoint)
- Conformance vectors (Python -> Kotlin)
- Replay file format
- LOD archive format
- vectors_present.py
- NoRng
- doc
- ResultSummary
- Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic)
- Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)
- IllegalCommand
- Hero simulation core (`sim.hero`): experience, levels and skill gain
- started
- IntegerCapTest
- assert_module_deterministic
- HoMM3 .H3M map header (clean-room notes)
- HoMM3 PCX bitmap variant (clean-room notes)
- Sprite atlas builder
- attack_defense_factor
- GoldenTest
- AllowlistTests
- Cli
- raw
- GrowthTest
- .pack
- ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)
- MVP 0.1: a playable skirmish APK
- parse_scenario
- PackTest
- PackVectorsTest
- Txt
- DrawSource
- ContentTest
- Second brain (project memory)
- ADR-0004: Android app with a Kotlin engine; Python is the reference oracle
- ADR-0014: Creature sprite table ported from VCMI, keyed by CRTRAITS row
- Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)
- army
- TickTest
- GeometryTest
- IllegalCommandNoRngTest
- test_town.py
- WaitActivationMoraleTest
- OfferPolicyTest
- MemoryCheck
- TestContractEdgeVectors
- WriteStep
- Loop graph builder
- ADR-0010: The project is licensed GPL-2.0-or-later
- index.sh
- Grid
- _bounded
- MalformedHexTest
- PackMismatchTest
- ModuleEntryPointTests
- SkillCheck
- DrawSource
- Cli
- TestAll
- TownPolicy
- .shot
- RealSourcesTests
- RepoWiring
- RepoFiles
- ADR-0003-vcmi-as-fact-source-clean-room.md
- ADR-0006-state-content-stands-in-for-a-pack-hash.md
- ADR-0007-replay-and-vectors-are-the-cross-language-contract.md

## God Nodes (most connected - your core abstractions)
1. `BattleState` - 118 edges
2. `HexCell` - 84 edges
3. `derive_stream()` - 69 edges
4. `BattleSession` - 62 edges
5. `Battle` - 58 edges
6. `BattleCommand` - 57 edges
7. `ImportPlanTest` - 53 edges
8. `Pcg32` - 53 edges
9. `BattleCodec` - 52 edges
10. `Datapack` - 52 edges

## Surprising Connections (you probably didn't know these)
- `Decision` --references--> `BattleSession`  [INFERRED]
  docs/adr/ADR-0011-android-app-architecture.md → android/presenter/src/main/kotlin/h3/presenter/BattleSession.kt
- `Remaining work for 0.1, in order` --references--> `BattleSession`  [INFERRED]
  docs/specs/mvp-0.1.md → android/presenter/src/main/kotlin/h3/presenter/BattleSession.kt
- `Re-pin and verification` --references--> `def()`  [INFERRED]
  docs/adr/ADR-0014-vcmi-creature-sprite-table.md → android/presenter/src/test/kotlin/h3/presenter/ui/SpriteLoadPlanTest.kt
- `Amendments (2026-11-01)` --references--> `Rational`  [INFERRED]
  docs/adr/ADR-0004-android-kotlin-core-python-oracle.md → android/sim/src/main/kotlin/h3/sim/Rational.kt
- `Out of scope (Kotlin's types cannot express them)` --references--> `TownTest`  [INFERRED]
  docs/specs/conformance-town.md → android/sim/src/test/kotlin/h3/sim/town/TownTest.kt

## Import Cycles
- 2-file cycle: `tools/h3re/h3re/adventure.py -> tools/h3re/h3re/encounter.py -> tools/h3re/h3re/adventure.py`
- 2-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/__init__.py`
- 2-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`
- 3-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/__init__.py`
- 3-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`

## Communities (350 total, 160 thin omitted)

### Community 0 - "GameDataCheckTest"
Cohesion: 0.07
Nodes (36): Candidate, CheckedFile, CorruptArchive, GameDataCheck, GameDataIssue, GameDataResult, GameFile, Invalid (+28 more)

### Community 1 - "assertequals"
Cohesion: 0.06
Nodes (15): Holding, plain(), session(), Fixture, Game, glLe32(), glLod(), XcScenario (+7 more)

### Community 2 - "AdventureState"
Cohesion: 0.05
Nodes (33): AdvArmySlot, AdvEncounter, AdventureCodec, AdventureCommand, AdventureEncounterHooks, AdventureEvent, AdventureState, AdventureStep (+25 more)

### Community 3 - ".write"
Cohesion: 0.06
Nodes (17): AiChooserTest, _board_at(), _cell_glyphs(), ChooserTest, CliTestCase, golden_scenario(), GoldenScenarioTest, _grid_rows() (+9 more)

### Community 4 - "LodArchive"
Cohesion: 0.05
Nodes (10): LodArchive, build_lod(), CorruptPayloadTests, ExtractTests, MalformedInputTests, member(), open_bytes(), OpenAndListTests (+2 more)

### Community 5 - "vectors_town.py"
Cohesion: 0.06
Nodes (61): _b(), _base(), _bigvalues(), _bld(), _canon(), classify_pack(), _cmd(), _create_cases() (+53 more)

### Community 6 - "vectors.py"
Cohesion: 0.05
Nodes (52): Conformance: greedy battle AI (`battle_ai.json`), File layout, Kotlin contract, What is pinned, Test cost, derive_stream(), _enc(), RngStreams (+44 more)

### Community 7 - "json"
Cohesion: 0.09
Nodes (8): RollPolicy, FloatSub, army(), BattleFromPackTest, play(), golden_scenario(), ReplayCliTest, _dump()

### Community 8 - "soak.py"
Cohesion: 0.05
Nodes (26): _AdventureDriver, build_adventure(), build_battle(), build_scenario(), check_seed(), Divergence, _driver(), _events_digest() (+18 more)

### Community 9 - "vectors_encounter.py"
Cohesion: 0.07
Nodes (51): Vector file `encounter.json`, Vector file `hero.json`, all_games(), army(), auto_cases(), _battery(), _bpol(), build_setup() (+43 more)

### Community 10 - "BattleSession"
Cohesion: 0.07
Nodes (35): Accepted, AutosaveSink, BattleSession, Faulted, Illegal, LogEntry, NotYourTurn, Origin (+27 more)

### Community 11 - "LodArchive"
Cohesion: 0.06
Nodes (28): inflateMember(), LodArchive, LodEntry, LodError, LodFormatError, LodKeyError, parsePcx(), PcxError (+20 more)

### Community 12 - "SaveSlots"
Cohesion: 0.08
Nodes (23): readSaveFolder(), SaveRowCard(), SaveScreen(), FileState, Invalid, Missing, Valid, ParsedName (+15 more)

### Community 13 - "H3mTest.kt"
Cohesion: 0.09
Nodes (30): H3m, H3mDisposedHero, H3mError, H3mHeader, H3mHotaError, H3mLoss, H3mPlayer, H3mPredefinedHero (+22 more)

### Community 14 - "parse_pcx"
Cohesion: 0.06
Nodes (20): Open items, Vectors, parse_pcx(), PcxError, PcxImage, _entry_pos(), generate(), _lod() (+12 more)

### Community 15 - "town.py"
Cohesion: 0.07
Nodes (39): Vector file `town.json`, 1. Interface, 4. Weekly growth, GrowthPool, Resources, _active(), active_buildings(), apply() (+31 more)

### Community 16 - "Datapack"
Cohesion: 0.09
Nodes (20): bad(), CreaturesDoc, Datapack, DatapackError, floatErr(), lit(), num(), parse() (+12 more)

### Community 17 - "hero.py"
Cohesion: 0.06
Nodes (37): Mutation check (producer's run, in a private copy; the lead re-verifies), _advance(), apply(), _canon_bytes(), canonical(), _check_class(), _check_draw_inputs(), _check_total() (+29 more)

### Community 18 - "test_encounter.py"
Cohesion: 0.09
Nodes (16): army(), BuildBattleTest, flat_grid(), fought(), golden_game(), GoldenTest, IllegalTest, OutcomeTest (+8 more)

### Community 19 - "battle.py"
Cohesion: 0.08
Nodes (38): 1. Interface, 2. Grid, Hex: battle grid geometry and movement (`hex.json`), 3. The battle, _adjacent_cells(), _as_hex(), Attack, BattleState (+30 more)

### Community 20 - "parse_txt"
Cohesion: 0.06
Nodes (17): 2. Run the real-file tests (optional, local only), API, Format, Limits, Options (backward compatibility), TXT tables (tab-separated), parse_txt(), read_txt() (+9 more)

### Community 21 - "BattleLogTest"
Cohesion: 0.08
Nodes (18): BattleLog, BattleLogGroup, BattleLogKind, DEFEND, DIED, END, HIT, LUCK_BAD (+10 more)

### Community 22 - "Handoff (resume here)"
Cohesion: 0.04
Nodes (41): Commands, heroes-mobile: project constitution, Laws, Roles and delegation, Working principles, Checkpoint log, Reverse-engineering loop graph, Checkpoint 0.2 status (2026-11-02) (+33 more)

### Community 23 - "ReplayAutosaveTest"
Cohesion: 0.12
Nodes (11): ByteSink, Failed, Ok, ReplayAutosave, ReplayResume, Resumed, ResumeResult, Case (+3 more)

### Community 24 - "Scenario"
Cohesion: 0.11
Nodes (10): BattleEngine, JsonFraction, P, Rejected, Scenario, ScenarioError, ScenarioJson, Setup (+2 more)

### Community 25 - "datapack.py"
Cohesion: 0.10
Nodes (34): Hashes, Pack directory and rules hash (determinism audit), _check_creatures(), _check_policy(), _check_rules(), DataPackError, _frac(), _int() (+26 more)

### Community 26 - "BattleCodec"
Cohesion: 0.09
Nodes (13): AppEngine, Preset, BattleCodec, BattleCreature, BattleHero, BattlePolicy, BattlePolicyPack, policyDefendBonus() (+5 more)

### Community 27 - "HexCell"
Cohesion: 0.12
Nodes (10): Hex, HexCell, legalCommands(), cell(), cells(), HexTest, 2. Module layout and dependency rules, 1. BoardGeometry (`h3.presenter.BoardGeometry`) (+2 more)

### Community 28 - "Android app design (`android/`)"
Cohesion: 0.05
Nodes (39): 0. Problem statement, 10. Determinism and purity impact, 11. Risks, 12. Assumptions (proposed defaults; the owner may overturn any), 13. Out of scope, 14. Open questions for the owner, 1. Spec grounding and gaps, 3.1 Principles (+31 more)

### Community 29 - "MainActivity.kt"
Cohesion: 0.07
Nodes (14): ImportScreen(), MainActivity, AboutScreen(), HomeScreen(), SetupScreen(), ResultScreen(), SideTallyCard(), Page() (+6 more)

### Community 30 - "BattleState"
Cohesion: 0.11
Nodes (12): AttackMovedScenario, BattleAi, BattleStack, BattleState, HexEntry, Present, 9. Milestones and acceptance criteria, Conformance: presenter view v2 (`h3.sim.Present`) (+4 more)

### Community 31 - "Battle"
Cohesion: 0.11
Nodes (13): ApplyResult, Battle, Damaged, Kind, ATTACK, DEFEND, MOVE, SHOOT (+5 more)

### Community 32 - "BattleCommand"
Cohesion: 0.12
Nodes (24): drive(), Attack, BattleCommand, Begin, Defend, Move, Shoot, Wait (+16 more)

### Community 33 - "Adventure"
Cohesion: 0.09
Nodes (19): Adventure, AdventurePolicy, AdvGrid, AdvTile, DayStarted, Label, Parts, PoolGrew (+11 more)

### Community 34 - "test_cli.py"
Cohesion: 0.11
Nodes (11): def_bytes(), DefCommandTests, h3m_bytes(), H3mCommandTests, lod_bytes(), LodCommandTests, png_size(), run_cli() (+3 more)

### Community 35 - "resolve_damage"
Cohesion: 0.10
Nodes (18): 2026-11-01: golden hash re-pinned a second time (rules pack in the hash), 5. Morale and luck, Rules: battle damage (`rules.json`), 8. Reference implementation, bad_morale_chance(), _clamp3(), damage_range(), DamageCtx (+10 more)

### Community 36 - "BoardView.kt"
Cohesion: 0.09
Nodes (19): BattleBody(), BattleScreen(), candidateLabel(), LogPanel(), PreviewPanel(), RosterPanel(), artPoint(), BoardSprites (+11 more)

### Community 37 - "h3m.py"
Cohesion: 0.11
Nodes (32): _army(), _art(), _bits(), _body_abandoned_mine(), _body_artifact(), _body_event(), _body_garrison(), _body_generic() (+24 more)

### Community 38 - "replay.py"
Cohesion: 0.10
Nodes (22): _canon(), _check_plain(), Diverged, _is_int(), load(), Malformed, MismatchedCreatures, MismatchedPolicy (+14 more)

### Community 39 - "with"
Cohesion: 0.07
Nodes (39): runs-on, steps, timeout-minutes, runs-on, steps, H3_DATA_DIR, jobs, android-app (+31 more)

### Community 40 - "vectors_battle.py"
Cohesion: 0.10
Nodes (28): encode_command(), _ability_creature(), build_ability_scenario(), build_tie_scenario(), cap_setup(), _case(), _driver(), _driver_step() (+20 more)

### Community 41 - ".load"
Cohesion: 0.19
Nodes (12): LodSource, def(), F, idleOnlyDef(), le32(), lod(), lodWith(), pageAt() (+4 more)

### Community 42 - "HeroTest"
Cohesion: 0.17
Nodes (4): ChooseSkill, GainXP, HeroTest, Script

### Community 43 - "SegKind"
Cohesion: 0.09
Nodes (25): AnimationPrefs, AnimSpeed, FAST, NORMAL, SKIP, SLOW, Frames, SegKind (+17 more)

### Community 44 - "battle_cli.py"
Cohesion: 0.12
Nodes (26): _ai(), pick(), _check_keys(), _check_pretty_options(), CliError, _creature(), _dataclass_kwargs(), _first_legal() (+18 more)

### Community 45 - "SpriteLoadPlan.kt"
Cohesion: 0.07
Nodes (23): BuildResult, Failed, Ok, Reason, DUPLICATE_KEY, FRAME_TOO_LARGE, OVER_BUDGET, SpriteScale (+15 more)

### Community 48 - "Test"
Cohesion: 0.15
Nodes (9): ctxOf(), isError(), loadPack(), long(), longs(), rat(), RationalTest, RulesTest (+1 more)

### Community 49 - "adventure.py"
Cohesion: 0.08
Nodes (26): adventure_rng(), apply(), Attack, base_movement(), Begin, calendar(), _check_army(), create_game() (+18 more)

### Community 50 - "parse_h3m_bytes"
Cohesion: 0.13
Nodes (9): H3mHeader, parse_h3m(), parse_h3m_bytes(), _read_tiles(), Tile, build(), extra(), H3mTests (+1 more)

### Community 52 - "BattleStateTest"
Cohesion: 0.14
Nodes (3): BattleStateTest, MiniJson, Amendment (2026-11-01): caps on derived products

### Community 53 - "TownConformanceTest.kt"
Cohesion: 0.16
Nodes (11): assertError(), canonText(), commandOf(), eventMap(), i32(), kindOf(), lng(), policyOf() (+3 more)

### Community 54 - "vectors_h3m.py"
Cohesion: 0.16
Nodes (26): build(), _Cases, _cond(), _cut_cases(), default_players(), dump_header(), _error_cases(), _expect() (+18 more)

### Community 55 - "ImportPlanTest"
Cohesion: 0.12
Nodes (15): CopyToPart, DeleteOld, MoveLiveToOld, Progress, PromoteStaging, RenamePart, Step, SyncFile (+7 more)

### Community 56 - "MenuModelTest"
Cohesion: 0.12
Nodes (9): menuEdgeAllowed(), MenuModel, MenuRoute, About, Battle, Home, Result, Setup (+1 more)

### Community 57 - "test_h3m.py"
Cohesion: 0.21
Nodes (21): box(), e_army(), e_box(), e_event_common(), e_hero(), e_monster(), e_msg_guards(), e_opt8() (+13 more)

### Community 58 - "ScriptRng"
Cohesion: 0.13
Nodes (7): begin(), four(), LastMoverOrderTest, MoraleTest, QueueTest, RecordingRng, ScriptRng

### Community 59 - "Def"
Cohesion: 0.16
Nodes (11): Def, DefBlock, DefException, DefFile, DefFrame, Out, Reader, Ambiguities / notes (+3 more)

### Community 60 - "HeroConformanceTest.kt"
Cohesion: 0.17
Nodes (12): canonText(), commandOf(), CountingDraw, eventMap(), HeroConformanceTest, HeroVectors, i32(), lng() (+4 more)

### Community 61 - "encounter.py"
Cohesion: 0.09
Nodes (17): ArmyChanged, auto_command(), BattleFought, build_battle(), check_game(), _creature(), EncounterPolicy, EncounterSetup (+9 more)

### Community 62 - "vectors_hero.py"
Cohesion: 0.13
Nodes (24): _canon(), _cmd(), _create_cases(), add(), _create_error_category(), _ev(), generate(), _golden() (+16 more)

### Community 63 - ".boardStacks"
Cohesion: 0.21
Nodes (8): ArtPoint, ArtRect, BoardArt, BoardStack, CountPlate, SpriteDraw, StackArt, BoardArtTest

### Community 64 - "Rational"
Cohesion: 0.11
Nodes (3): Rational, RulesPack, ADR-0009: The Kotlin engine uses a small exact Rational type with one named rounding step, not an integer rewrite

### Community 65 - "AdventureTest"
Cohesion: 0.16
Nodes (4): Attack, EndTurn, Move, AdventureTest

### Community 66 - "Rules"
Cohesion: 0.12
Nodes (12): DrawSource, AttackDefenseFactor, DamageCtx, DamagePreview, DamageResult, DrawSource, RollPolicy, ACTUAL_SEED (+4 more)

### Community 67 - "parse_creatures"
Cohesion: 0.16
Nodes (13): Tests, ContentError, ContentResult, _int(), _layout(), load_creatures(), load_mapping(), _norm() (+5 more)

### Community 68 - "real_report.py"
Cohesion: 0.13
Nodes (18): _archive_report(), build_report(), cmd(), _count_errors(), _decode(), _def_report(), _etype(), _find_sprite_lods() (+10 more)

### Community 69 - "vectors_adventure.py"
Cohesion: 0.12
Nodes (22): _decode(), edge_day_cases(), encode_event(), _enum_cases(), generate(), golden_commands(), golden_setup(), illegal_cases() (+14 more)

### Community 70 - "grid"
Cohesion: 0.11
Nodes (5): game(), grid(), PolicyTest, StepCostTest, costs()

### Community 71 - "BoardGeometry"
Cohesion: 0.15
Nodes (7): BoardGeometry, footprints(), Pt, UnitFootprint, UnitHit, BoardGeometryTest, Battle interaction

### Community 72 - "DefError"
Cohesion: 0.09
Nodes (18): 1. Point the tools at your game folder, 3. Make the report, 4. What to send back, 5. What we do with each result, Privacy checklist before sending, Runbook: check the project against your own Heroes 3 files, What the report contains, and nothing else, DEF (`docs/specs/def.md`, `tools/h3re/h3re/defimg.py`) (+10 more)

### Community 73 - "defimg.py"
Cohesion: 0.14
Nodes (16): Blocks, Frame, Header, HoMM3 .DEF sprite container (clean-room notes), Implementation status / caveats, EmptyImageError, Frame, frame_is_empty() (+8 more)

### Community 74 - "struct"
Cohesion: 0.19
Nodes (21): _bad_cases(), single(), build_def(), case(), encode_body(), _format_cases(), one(), frame_blob() (+13 more)

### Community 75 - "Pcg32"
Cohesion: 0.13
Nodes (3): Pcg32, _TracedPcg32, TestPcg32

### Community 76 - "test_battle.py"
Cohesion: 0.10
Nodes (10): BadMoraleTableTest, CheckStateTest, golden_setup(), GoldenTest, play(), PolicyDefaultsFromPackTest, PreviewLawTest, PropertyTest (+2 more)

### Community 77 - "cr"
Cohesion: 0.15
Nodes (6): CombatTest, cr(), MovementTest, SetupTest, ss(), synthetic_states()

### Community 78 - "VectorsHeroTest"
Cohesion: 0.13
Nodes (4): doc(), _floats(), _steps(), VectorsHeroTest

### Community 79 - "DataPack"
Cohesion: 0.08
Nodes (17): API, Battle policy pack, Data pack (`h3re.datapack`), Determinism and hash, Drift guard, Files, Integer range, Runtime loading (checkpoint 34) (+9 more)

### Community 80 - "Hero.kt"
Cohesion: 0.16
Nodes (18): asHeroDraw(), Hero, HeroApplyResult, HeroCategory, HeroCommand, HeroDraw, HeroEvent, HeroPolicy (+10 more)

### Community 81 - "vectors_pack.py"
Cohesion: 0.14
Nodes (20): classify(), _collect_invalid(), data_dir(), _delete(), _derived_valid(), dumps(), walk(), _extra_invalid() (+12 more)

### Community 82 - "SpriteAtlasTest.kt"
Cohesion: 0.19
Nodes (10): assertSameAtlas(), checkInvariants(), hex(), ok(), randomFrames(), shuffled(), solid(), SpriteAtlasTest (+2 more)

### Community 83 - "lod.py"
Cohesion: 0.11
Nodes (10): Discrepancies flagged (CLAUDE.md law 10), _check_member_name(), _decode_name(), _inflate(), _key(), LodEntry, LodError, LodFormatError (+2 more)

### Community 84 - "H3mObjectTests"
Cohesion: 0.18
Nodes (5): e_objects(), e_template(), H3mObjectTests, map_with(), tmpl()

### Community 85 - ".report"
Cohesion: 0.17
Nodes (5): EmptyAndMissing, Hostile, MapParsing, valid_map(), write()

### Community 86 - ".encode"
Cohesion: 0.15
Nodes (3): Canonical, ConformanceTest, PresentTest

### Community 87 - "HeroCore"
Cohesion: 0.16
Nodes (3): HeroClass, HeroContent, HeroCore

### Community 88 - "TownCore"
Cohesion: 0.17
Nodes (4): Building, Faction, TownContent, TownCore

### Community 89 - "parse_def"
Cohesion: 0.17
Nodes (10): 2026-11-02: first contact (H3ab_spr.lod, H3ab_ahd.snd, H3ab_ahd.vid, two hd_*.p32 files), Findings on real game files (structure only, no content), Still needed to proceed with 0.2, Block, DefFile, parse_def(), build_def(), build_shared() (+2 more)

### Community 90 - "battle_ai.py"
Cohesion: 0.10
Nodes (13): choose(), _decide(), pick(), _enemy_dist(), GreedyAI, _pick(), _preview(), _score_attack() (+5 more)

### Community 91 - "VectorsTownTest"
Cohesion: 0.14
Nodes (7): _cmd(), doc(), _err(), _floats(), NoRng, _steps(), VectorsTownTest

### Community 92 - "argparse"
Cohesion: 0.13
Nodes (15): _build(), _enc(), _game(), generate(), _jsonable(), main(), _policies(), _wall_scenario() (+7 more)

### Community 93 - "vectors_replay.py"
Cohesion: 0.14
Nodes (21): run_chooser(), _creature_dict(), _explicit_pos_scenario(), generate(), _golden(), _hero_dict(), _jsonable(), main() (+13 more)

### Community 94 - "Atlas"
Cohesion: 0.14
Nodes (11): add(), addAll(), Atlas, BudgetCheck, Exceeded, FrameMeta, Page, Rect (+3 more)

### Community 95 - "SetupForm"
Cohesion: 0.16
Nodes (13): presetErrorText(), seedErrorText(), setupFormMessage(), PresetError, NoPresets, OutOfRange, SeedError, Empty (+5 more)

### Community 97 - "turn_order"
Cohesion: 0.09
Nodes (19): 9. Tests, 1. Contract, 2. Shape, 3. Tap semantics, Battle presenter (`h3re.present`), 1. Mismatches (ranked by gameplay impact), 2. Confirmed (VCMI agrees with our default or our documented value), 3. Items VCMI does not settle (+11 more)

### Community 98 - "Rules specification"
Cohesion: 0.08
Nodes (24): 0. Provenance and tagging, 1. Calendar and turn structure, 2.1 Movement points (land), 2.2 Terrain cost, 2. Adventure map: movement, 3. Resource economy, 4. Towns, 5.1 Primary skills (+16 more)

### Community 99 - "bisect_tool.py"
Cohesion: 0.13
Nodes (16): bisect(), diff_states(), dump_log(), flatten(), format_policy(), format_report(), load_log(), load_log_ex() (+8 more)

### Community 100 - "rules"
Cohesion: 0.18
Nodes (3): GraphCriteria, rules(), RunCriteria

### Community 101 - "_Visitor"
Cohesion: 0.16
Nodes (3): _is_set_expr(), Violation, _Visitor

### Community 102 - "Test"
Cohesion: 0.23
Nodes (8): AmbiguousSource, Chosen, InvalidName, MissingSource, SelectedFile, Selection, SourceEntry, UnknownSize

### Community 103 - "ImportPlan"
Cohesion: 0.13
Nodes (6): ImportPlan, NotEnoughSpace, Ok, SpaceCheck, ImportText, SourceProblem

### Community 105 - "EncounterConformanceTest.kt"
Cohesion: 0.26
Nodes (5): AdventureRules, enc(), EncounterConformanceTest, EncVectors, s()

### Community 107 - "PolicyPackTest"
Cohesion: 0.11
Nodes (7): ADR-0008: Kotlin pack values are 32-bit Int capped at 2**31-1; hashes and XP accumulation use Long, LoadTest, PolicyPackTest, bad(), raw(), raw_policy(), ValidationTest

### Community 108 - "re"
Cohesion: 0.17
Nodes (15): _back_edges(), visit(), eval_graph(), eval_run(), _load_run(), main(), parse_loop(), check_loop() (+7 more)

### Community 109 - "kotlin_banned_api_lint.py"
Cohesion: 0.13
Nodes (11): apply_allowlist(), default_paths(), _entry_matches(), lint_paths(), lint_source(), load_allowlist(), main(), _scan() (+3 more)

### Community 110 - "ResumeError"
Cohesion: 0.12
Nodes (20): ResumeError, Diverged, Malformed, MismatchedCreatures, MismatchedPolicy, MismatchedRulesPack, Tampered, Truncated (+12 more)

### Community 111 - "GameDataLayoutTest"
Cohesion: 0.19
Nodes (5): GameDataLayout, GameDataLayoutTest, glCheckAccepts(), GlFixture, glLayoutFindsAll()

### Community 112 - "ImportPlanTest.kt"
Cohesion: 0.09
Nodes (9): DataStatus, Changed, Found, Missing, RecoverAction, DeleteLive, DeleteOld, DeleteStaging (+1 more)

### Community 113 - "_activate_next"
Cohesion: 0.13
Nodes (19): _activate_next(), apply(), BattleStarted, _chance(), DamageDealt, Defended, effective_morale(), _finish_turn() (+11 more)

### Community 114 - "TestBattleVectors"
Cohesion: 0.13
Nodes (5): decode_command(), state_from_json(), stream_at(), _t(), TestBattleVectors

### Community 115 - "_run_isolated"
Cohesion: 0.14
Nodes (6): _probe(), _repo_data_dir(), _run_isolated(), TestBattleExports, TestImportSideEffects, TestRulesPackIdentity

### Community 116 - "PresentTest"
Cohesion: 0.15
Nodes (5): all_states(), FailRng, golden_states(), PresentTest, walk()

### Community 117 - "game"
Cohesion: 0.17
Nodes (4): build(), BuildTest, game(), NoRng

### Community 118 - "StackRosterRow"
Cohesion: 0.19
Nodes (6): RosterSide(), BattlePanels, RosterEntry, TurnChip, StackRosterRow, BattlePanelsTest

### Community 120 - "_Pretty"
Cohesion: 0.14
Nodes (10): _board_lines(), _fields(), _hp(), _legend_lines(), _mark(), _pos_text(), _Pretty, _shifted() (+2 more)

### Community 121 - "_Reader"
Cohesion: 0.17
Nodes (9): H3mError, PlayerInfo, _read_extra(), _read_loss(), _read_mask(), _read_player(), _read_predefined(), _read_victory() (+1 more)

### Community 122 - "idle_def"
Cohesion: 0.23
Nodes (4): ArchiveParsing, Base, Determinism, idle_def()

### Community 124 - ".parseCreatures"
Cohesion: 0.22
Nodes (9): Content, ContentResult, Creature, CreatureMapping, CreatureValidator, DefaultCreatureValidator, MapColumn, UnknownAbility (+1 more)

### Community 125 - ".validate"
Cohesion: 0.14
Nodes (7): HeroValueError, IllegalCommand, PyText, Conformance: hero core (`h3.sim.hero`), Known differences (documented, not silent), Kotlin API, Out of scope (Kotlin's types cannot express them)

### Community 126 - "apply_damage"
Cohesion: 0.13
Nodes (12): 10. Change notes, 2026-11-01: golden hash re-pinned (one reviewed change), 2026-11-01: state invariants and integer caps (no re-pin), 3. Movement [documented], 4. Turn queue, 6. Damage and attacks, 7. Battle end, 8. Uncertain policy summary (+4 more)

### Community 131 - "TownState"
Cohesion: 0.29
Nodes (5): GrowthPool, IllegalCommand, Town, TownPolicy, TownState

### Community 132 - "H3mUnsupportedObject"
Cohesion: 0.13
Nodes (12): End of data, Global events, Object instances, Objects, object instances and events (`objects=True`), Template table, Unverified assumptions (objects section), H3mUnsupportedObject, MapObject (+4 more)

### Community 133 - "base_damage"
Cohesion: 0.13
Nodes (8): Algorithm, API, Deterministic RNG (`sim.rng`), Named streams, base_damage(), BaseDamageTest, DamageRangeTest, FixedRng

### Community 134 - "vectors_txt.py"
Cohesion: 0.20
Nodes (14): _base(), _content_case(), _content_cases(), _content_error(), _creature_row(), generate(), _header(), _Lcg (+6 more)

### Community 135 - "TapState"
Cohesion: 0.20
Nodes (12): Cancel, Candidate, Confirmed, Idle, LongPress, Previewing, PreviewNumbers, Select (+4 more)

### Community 136 - "Town simulation core (`sim.town`): buildings, build rules and weekly growth"
Cohesion: 0.16
Nodes (16): 2. Content model (pack schema v1), 3. Building, 5. Economy and integration, 6. Policy fields (`TownPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch), Growth pools digest (second pin), Town simulation core (`sim.town`): buildings, build rules and weekly growth (+8 more)

### Community 138 - "App shell (milestone A7, MVP 0.1)"
Cohesion: 0.12
Nodes (16): Screen, About, Battle, Home, Import, Result, Saves, Setup (+8 more)

### Community 139 - "AtlasFrame"
Cohesion: 0.29
Nodes (4): AtlasFrame, frame(), px(), SpriteScaleTest

### Community 141 - "Town.kt"
Cohesion: 0.19
Nodes (14): Category, BuildingBuilt, Dwelling, NewDay, RawResources, RawSetup, TownApplyResult, TownCategory (+6 more)

### Community 143 - "__main__.py"
Cohesion: 0.23
Nodes (11): build_parser(), cmd_battle_sim(), cmd_h3m_info(), cmd_lod_extract(), cmd_lod_list(), cmd_replay(), _condition(), _describe_error() (+3 more)

### Community 144 - "Adventure-map simulation core (`sim.adventure`): movement and economy"
Cohesion: 0.14
Nodes (14): 1. Interface, 2. Grid and step costs, 3. Movement points, 4. Pathfinding, 5. Calendar, income and growth, 6. Policy fields (`AdventurePolicy`), 7. Tests, 8. Encounters (battles on the map) (+6 more)

### Community 145 - "verify"
Cohesion: 0.21
Nodes (4): info(), verify(), ReplayTest, reseal()

### Community 146 - "_valid_cases"
Cohesion: 0.17
Nodes (15): _base(), _bigweights(), classify_pack(), _invalid_cases(), add(), mut(), _load(), _nobody() (+7 more)

### Community 147 - ".test_every_mutation_changes_the_hash"
Cohesion: 0.17
Nodes (5): StoredContentHashTest, high(), low(), sec(), start()

### Community 148 - "module_doc"
Cohesion: 0.15
Nodes (3): DefVectorTests, VectorsTxtTest, module_doc()

### Community 150 - "ManifestError"
Cohesion: 0.12
Nodes (15): ManifestError, BadName, BadNumber, BadString, DuplicateKey, DuplicateName, MissingKey, NoFiles (+7 more)

### Community 151 - "Resources"
Cohesion: 0.23
Nodes (6): Resources, TownSetup, TownValueError, resOf(), typedPlayers(), typedTowns()

### Community 152 - "TownText"
Cohesion: 0.17
Nodes (6): TownKeyError, TownText, Conformance: town core (`h3.sim.town`), Known differences (documented, not silent), Mutation check (producer's run, in a private copy; the lead re-verifies), Out of scope (Kotlin's types cannot express them)

### Community 153 - "Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)"
Cohesion: 0.13
Nodes (12): ADR-0001: Canonical JSON form and SHA-256 state hash for battle and adventure state, ADR-0005: The omit-at-default canonical mechanism applies to every state module, not only battle, 4. Outcome, 5. Policy fields (`EncounterPolicy`), 6. Canonical form and hashes, 7. Golden encounter hash, 8. Tests, 9. Open items (+4 more)

### Community 155 - "BattleAiTest"
Cohesion: 0.20
Nodes (3): BattleAiTest, play(), scenario()

### Community 156 - "present.py"
Cohesion: 0.23
Nodes (11): _actions(), slot(), target_slot(), command_to_dict(), _grid(), _hx(), _preview(), _queue() (+3 more)

### Community 158 - "SpriteLoader.kt"
Cohesion: 0.21
Nodes (3): Loaded, SpriteLoader, PagePixels

### Community 159 - "ManifestFile"
Cohesion: 0.24
Nodes (5): Failed, Manifest, ManifestFile, ManifestParse, Parsed

### Community 160 - "Pcg32"
Cohesion: 0.23
Nodes (3): Pcg32, Edge, RngEdgeTest

### Community 161 - "_search"
Cohesion: 0.14
Nodes (8): ADR-0002: Integer-only simulation (int and Fraction, one explicit rounding step), _diagonal(), _div(), _orth_cost(), _paid(), _search(), step_cost(), _step_parts()

### Community 162 - "render"
Cohesion: 0.15
Nodes (13): 0. Goals and clean-room constraints, 1.1 Data layer (`data/`), 1.2 Content layer (`content/`), 1.3 Simulation core (`sim/`), 1.4 Deterministic seeded RNG (`sim.rng`), 1.5 Presenter, rendering and audio, 1.6 Touch-UI considerations, 1. Layered architecture (+5 more)

### Community 163 - "golden_setup"
Cohesion: 0.22
Nodes (5): golden_setup(), GoldenTest, play_days(), PropertyTest, scripted_turn()

### Community 164 - "hero"
Cohesion: 0.25
Nodes (4): gain(), hero(), LevelUpTest, XpTest

### Community 165 - "lod"
Cohesion: 0.23
Nodes (5): def_blocks(), empty_idle_def(), lod(), no_group2_def(), SpriteCheck

### Community 167 - "BattleEvent"
Cohesion: 0.27
Nodes (13): BattleEnded, BattleEvent, BattleStarted, DamageDealt, Defended, LuckRolled, MoraleBoost, MoraleFrozen (+5 more)

### Community 168 - "Txt.kt"
Cohesion: 0.18
Nodes (7): TxtError, TxtErrorCategory, DECODE, HEADER_ROWS, TOO_LARGE, TOO_MANY_LINES, UNKNOWN_ENCODING

### Community 169 - ".parse"
Cohesion: 0.31
Nodes (5): DefTest, hex(), hexStr(), long(), sha()

### Community 171 - "test_real_report.py"
Cohesion: 0.23
Nodes (4): all_keys(), all_strings(), NoPayload, txt_bytes()

### Community 173 - "Runbook: smoke-test the debug app on a real Android phone"
Cohesion: 0.15
Nodes (12): 10. What this does NOT test, 11. What we do with each result, 1. Get the debug APK from CI, 2. Install it, 3. What each screen should do, 4. Main checklist, 5. Risk checks (the ones most likely to find real bugs), 6. Sprites: what to expect (+4 more)

### Community 174 - "Integer bounds and types (amendment, ADR-0008 style)"
Cohesion: 0.15
Nodes (9): Integer bounds and types (amendment, ADR-0008 style), 1. Soak (`tools/h3re/h3re/soak.py`), 2. Bisector (`tools/h3re/h3re/bisect_tool.py`), 3. Banned-API lint (`tools/lint/banned_api_lint.py`), CI, Determinism gate, Kotlin banned-API lint (`tools/lint/kotlin_banned_api_lint.py`), AdventurePolicy (+1 more)

### Community 175 - "Battle roster from the player's CRTRAITS.TXT"
Cohesion: 0.15
Nodes (10): 1. Document, 1. Status, 3. Proposed design, 4. Hash impact, 5. Test plan, 6. Risks and open questions, 7. Slices, Battle roster from the player's CRTRAITS.TXT (+2 more)

### Community 176 - "damage_from_base"
Cohesion: 0.26
Nodes (3): _check_flags(), damage_from_base(), DamageFromBaseTest

### Community 177 - "test_hero.py"
Cohesion: 0.24
Nodes (4): PackTest, raw(), resolve(), with_class()

### Community 178 - "GoldenTest"
Cohesion: 0.21
Nodes (3): golden_run(), GoldenTest, growth_digest()

### Community 180 - "SpriteImportNameCrossCheckTest"
Cohesion: 0.35
Nodes (3): SpriteImportNameCrossCheckTest, xcImport(), xcImportPick()

### Community 181 - "ContentErrorCategory"
Cohesion: 0.17
Nodes (11): ContentError, ContentErrorCategory, DUPLICATE, EMPTY_CELL, HEADER, MAPPING, MISSING_CELL, NO_ROWS (+3 more)

### Community 182 - ".parse"
Cohesion: 0.29
Nodes (3): TxtTable, hexBytes(), TxtTest

### Community 184 - "_states"
Cohesion: 0.20
Nodes (8): with_(), _states(), base(), Raw, _set(), _special(), c(), s()

### Community 188 - "IoStage"
Cohesion: 0.18
Nodes (7): IoFailed, IoStage, Copy, Manifest, Recover, Scan, Swap

### Community 190 - "Loop: one agent round (advise, fan out, verify, checkpoint)"
Cohesion: 0.18
Nodes (10): Actions, Budget, Evidence, Goal and input, Loop: one agent round (advise, fan out, verify, checkpoint), Notes learned the hard way, Observation, State (+2 more)

### Community 191 - "Conformance vectors (Python -> Kotlin)"
Cohesion: 0.18
Nodes (9): `canonical_json.json`, Conformance vectors (Python -> Kotlin), Contract edges: caps, policy and state rejects (`battle_states.json`), File format, Generating and checking, Python/Kotlin differences resolved, `rng.json`, `state_hash.json` (+1 more)

### Community 192 - "Replay file format"
Cohesion: 0.18
Nodes (10): 1. Interface, 1. Encoding, 2. Header (all keys required, unknown keys rejected), 3. Body, 4. Verification order and errors, 5. API and CLI, 6. Notes, Replay file format (+2 more)

### Community 193 - "LOD archive format"
Cohesion: 0.18
Nodes (10): Directory entry (32-byte stride), Errors, Extraction safety, File layout, Header (92 bytes), LOD archive format, Name rules, Open items (+2 more)

### Community 194 - "vectors_present.py"
Cohesion: 0.31
Nodes (7): _canon(), _entries(), generate(), main(), _playouts(), _sha(), _taps()

### Community 196 - "doc"
Cohesion: 0.31
Nodes (3): doc(), _floats(), VectorsReplayTest

### Community 197 - "ResultSummary"
Cohesion: 0.31
Nodes (6): ResultOutcome, Defeat, Unfinished, Victory, ResultSummary, SideTally

### Community 198 - "Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic)"
Cohesion: 0.20
Nodes (9): Actions, Budget, Evidence, Goal and input, Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic), Observation, State, Stop and escalation (+1 more)

### Community 199 - "Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)"
Cohesion: 0.20
Nodes (9): Actions, Budget, Evidence, Goal and input, Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors), Observation, State, Stop and escalation (+1 more)

### Community 200 - "IllegalCommand"
Cohesion: 0.22
Nodes (6): 2026-11-01: malformed hex raises IllegalCommand (no re-pin), 2. Validation, _as_tile(), IllegalCommand, reachable(), _validate()

### Community 201 - "Hero simulation core (`sim.hero`): experience, levels and skill gain"
Cohesion: 0.20
Nodes (9): 1. Interface, 2. Content model (pack schema v1), 3. Experience and levels, 4. Level-up, 5. Secondary skills, 6. Policy fields (`HeroPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch) (+1 more)

### Community 202 - "started"
Cohesion: 0.24
Nodes (3): MalformedDestTest, RoadCostCanonicalTest, started()

### Community 205 - "HoMM3 .H3M map header (clean-room notes)"
Cohesion: 0.22
Nodes (8): After teams (parsed; then terrain tiles), Conditions and teams, Header, HoMM3 .H3M map header (clean-room notes), Not implemented, Players (8 slots), Verification status, levels()

### Community 206 - "HoMM3 PCX bitmap variant (clean-room notes)"
Cohesion: 0.22
Nodes (6): Errors, Header (12 bytes), HoMM3 PCX bitmap variant (clean-room notes), Mode selection, Open items, Output model

### Community 207 - "Sprite atlas builder"
Cohesion: 0.22
Nodes (8): Input and output, Mask pages, Memory (4.5), Open points, Packing, Pixel conversion, Sprite atlas builder, Upscaling (0.2)

### Community 208 - "attack_defense_factor"
Cohesion: 0.28
Nodes (4): attack_defense_factor(), _scaled(), _skill(), AttackDefenseTest

### Community 215 - "ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)"
Cohesion: 0.25
Nodes (7): ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build), Alternatives considered, Consequences, Context, Decision, Verification, Why

### Community 216 - "MVP 0.1: a playable skirmish APK"
Cohesion: 0.25
Nodes (7): Decisions needed from the owner, Goal (one sentence, with its test), MVP 0.1: a playable skirmish APK, Remaining work for 0.1, in order, Risks specific to 0.1, What 0.1 is, and is not, What exists today (checkpoints up to 59, plus agents in flight)

### Community 220 - "Txt"
Cohesion: 0.33
Nodes (3): Txt, Conformance: TXT reader and creature content loader (Kotlin port), Vectors

### Community 223 - "Second brain (project memory)"
Cohesion: 0.29
Nodes (6): Note format, Operations, Principles, Relationship to other records, Second brain (project memory), What never goes in

### Community 224 - "ADR-0004: Android app with a Kotlin engine; Python is the reference oracle"
Cohesion: 0.29
Nodes (7): ADR-0004: Android app with a Kotlin engine; Python is the reference oracle, Amendments (2026-11-01), Consequences, Context, Decision, Risks, Why

### Community 225 - "ADR-0014: Creature sprite table ported from VCMI, keyed by CRTRAITS row"
Cohesion: 0.29
Nodes (6): ADR-0014: Creature sprite table ported from VCMI, keyed by CRTRAITS row, Alternatives considered, Consequences, Context, Decision, Re-pin and verification

### Community 226 - "Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)"
Cohesion: 0.29
Nodes (6): Abilities, API, Column order (data: `data/txt_maps/crtraits.json`, unverified), Content loader (`h3re.content`), engine roadmap Phase 4 (creatures), Errors, Reading

### Community 236 - "WriteStep"
Cohesion: 0.40
Nodes (5): WriteStep, CopyMainToBackup, RenameTempToMain, SyncTemp, WriteTemp

### Community 237 - "Loop graph builder"
Cohesion: 0.40
Nodes (4): Contract template, Loop graph builder, Principles (Karpathy-style, applied), Procedure

### Community 238 - "ADR-0010: The project is licensed GPL-2.0-or-later"
Cohesion: 0.40
Nodes (4): ADR-0010: The project is licensed GPL-2.0-or-later, Consequences, Context, Decision

### Community 239 - "index.sh"
Cohesion: 0.40
Nodes (3): GRAPHIFY_BACKEND, GRAPHIFY_QUERY_LOG_DISABLE, index.sh script

## Knowledge Gaps
- **134 isolated node(s):** `Home`, `Setup`, `Battle`, `Result`, `About` (+129 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1513 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **160 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `derive_stream()` connect `vectors.py` to `vectors_town.py`, `json`, `soak.py`, `vectors_encounter.py`, `town.py`, `hero.py`, `test_encounter.py`, `battle.py`, `VectorsEncounterTest`, `Handoff (resume here)`, `BattleCodec`, `BattleState`, `golden_setup`, `vectors_battle.py`, `adventure.py`, `test_hero.py`, `GoldenTest`, `vectors_hero.py`, `Pcg32`, `test_battle.py`, `GoldenTest`, `battle_ai.py`, `argparse`, `ADR-0004: Android app with a Kotlin engine; Python is the reference oracle`, `test_town.py`, `TestBattleVectors`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `HexCell` (e.g. with `.enemyDist()` and `.checkState()`) actually correct?**
  _`HexCell` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Home`, `Setup`, `Battle` to the rest of the system?**
  _134 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `GameDataCheckTest` be split into smaller, more focused modules?**
  _Cohesion score 0.06605749095754807 - nodes in this community are weakly interconnected._
- **Why does `Battle state (`battle_states.json`)` connect `BattleCodec` to `BattleCommand`, `vectors.py`, `BattleEvent`, `vectors_battle.py`, `vectors_encounter.py`, `battle.py`, `BattleStateTest`, `.encode`, `BattleAiTest`, `BattleState`, `Conformance vectors (Python -> Kotlin)`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `derive_stream()` (e.g. with `sim-engineer.md` and `Laws`) actually correct?**
  _`derive_stream()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `assertequals` be split into smaller, more focused modules?**
  _Cohesion score 0.06292134831460675 - nodes in this community are weakly interconnected._