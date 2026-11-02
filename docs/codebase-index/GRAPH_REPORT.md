# Graph Report - proj  (2026-11-02)

## Corpus Check
- 310 files · ~349,068 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 3, .properties 2, .xml 1)

## Summary
- 6411 nodes · 16629 edges · 353 communities (197 shown, 156 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 1028 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- derive_stream
- struct
- GameDataCheckTest
- .report
- json
- BattleState
- .write
- defimg.py
- HexCell
- vectors_town.py
- assertequals
- LodArchive
- H3mTest.kt
- battle.py
- BattleSession
- hero.py
- vectors.py
- Test
- build_lod
- test_encounter.py
- vectors_hero.py
- BattleLogTest
- LodArchive
- ImportPlanTest
- parse_pcx
- town.py
- generate_log
- MainActivity.kt
- AdventureState
- Vector file `town.json`
- HeroTest
- module_doc
- Pcg32
- resolve_damage
- replay.py
- BoardView.kt
- GameController
- BattleCodec
- h3m.py
- .load
- adventure.py
- parse_txt
- with
- SegKind
- SpriteLoadPlan.kt
- BoardFitTest
- Encounter.kt
- TownTest
- vectors_encounter.py
- test_h3m.py
- SaveSlots
- SaveSlotsTest
- BattleStateTest
- TownConformanceTest.kt
- vectors_pack.py
- parse_creatures
- ScriptRng
- kotlin_banned_api_lint.py
- MenuModelTest
- Hero.kt
- apply_damage
- battle_cli.py
- Pcg32
- Def
- HeroConformanceTest.kt
- present.py
- Test
- encounter.py
- grid
- .boardStacks
- Rational
- Rules
- Android app design (`android/`)
- vectors_adventure.py
- parse_h3m_bytes
- BattleTest
- TestBattleVectors
- VectorsHeroTest
- .encode
- H3mObjectTests
- ResumeError
- ReplayAutosaveTest
- AdventureEvent
- Replay
- _Reader
- Datapack
- TownCore
- bisect_tool.py
- game
- VectorsTownTest
- Atlas
- BattleCommand
- GameDataLayoutTest
- Scenario
- Town.kt
- base_damage
- SetupForm
- BattleEvent
- AdventureTest
- dataclasses
- Rules specification
- re
- real_report.py
- vectors_replay.py
- cr
- rules
- _Visitor
- PresentTest
- ImportPlan
- .parseCreatures
- HeroCore
- test_adventure.py
- test_battle.py
- _Pretty
- _run_isolated
- StackRosterRow
- .plan
- __main__.py
- create_battle
- .parse
- RealLodTests
- SetupFormTest
- TapReducerTest
- StackRosterTest
- AdventureCodec
- EncounterTest
- vectors_txt.py
- GameDataStore
- ReplayAutosave
- Txt.kt
- ReplayTest
- Creature
- LintTest
- AtlasFrame
- ResultSummaryTest
- Kotlin API
- _search
- verify
- hero
- .test_every_mutation_changes_the_hash
- VectorsEncounterTest
- ManifestError
- TownState
- Battle scenario file (JSON)
- Handoff (resume here)
- MEMORY.md
- 10. Change notes
- BattleAiTest
- damage_from_base
- NoRng
- BattleCreature
- SpriteLoader.kt
- Adventure-map simulation core (`sim.adventure`): movement and economy
- DataPack
- Data pack (`h3re.datapack`)
- ImportPlanTest.kt
- ImportTextTest
- Conformance: adventure core (Kotlin port)
- ContentTest
- TownText
- .parse
- LegalTest
- Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)
- TestVectors
- H3mUnsupportedObject
- TestAdventureVectors
- ResultSummary
- ManifestFile
- DatapackTest
- Runbook: smoke-test the debug app on a real Android phone
- Replay file format
- jsonable
- raw
- ManifestReader
- SpriteImportNameCrossCheckTest
- .parse
- StrictIntFieldsTest
- started
- LoopCheck
- GoldenTest
- H3mVectorTests
- IoStage
- DatapackError
- 2. Module layout and dependency rules
- BattleAiTest
- Loop: one agent round (advise, fan out, verify, checkpoint)
- Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)
- LOD archive format
- _bld
- vectors_present.py
- NoRng
- doc
- ContentErrorCategory
- Resources
- _step_parts
- Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic)
- Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)
- Hero simulation core (`sim.hero`): experience, levels and skill gain
- IntegerCapTest
- raw
- GreedyAi
- HoMM3 .H3M map header (clean-room notes)
- Sprite atlas builder
- heroes-mobile
- attack_defense_factor
- RecordingRng
- PolicyPackTest
- GoldenTest
- raw
- AllowlistTests
- GrowthTest
- .pack
- .repr
- .parse
- Scripted
- ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)
- MVP 0.1: a playable skirmish APK
- _play
- DefaultCreatureValidator
- RngStreams
- Second brain (project memory)
- ADR-0004: Android app with a Kotlin engine; Python is the reference oracle
- ADR-0014: Creature sprite table ported from VCMI, keyed by CRTRAITS row
- Battle roster from the player's CRTRAITS.TXT
- Town simulation core (`sim.town`): buildings, build rules and weekly growth
- GeometryTest
- IllegalCommandNoRngTest
- heroes-mobile: project constitution
- HoMM3 PCX bitmap variant (clean-room notes)
- _canon_bytes
- TickTest
- PolicyAndHeroTest
- MalformedHexTest
- PackMismatchTest
- OfferPolicyTest
- MemoryCheck
- StoredContentHashTest
- WriteStep
- Loop graph builder
- ADR-0010: The project is licensed GPL-2.0-or-later
- Conformance: data-pack loader (`vectors/datapack.json`)
- index.sh
- Grid
- CheckStateTest
- ModuleEntryPointTests
- SkillCheck
- DrawSource
- Conformance: scenario and replay (milestone A5)
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
7. `Pcg32` - 54 edges
8. `ImportPlanTest` - 53 edges
9. `Datapack` - 53 edges
10. `BattleCodec` - 52 edges

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

## Communities (353 total, 156 thin omitted)

### Community 0 - "derive_stream"
Cohesion: 0.04
Nodes (66): Conformance: greedy battle AI (`battle_ai.json`), File layout, Kotlin contract, What is pinned, choose(), _decide(), pick(), _enemy_dist() (+58 more)

### Community 1 - "struct"
Cohesion: 0.05
Nodes (58): _bad_cases(), single(), build_def(), case(), encode_body(), _format_cases(), one(), frame_blob() (+50 more)

### Community 2 - "GameDataCheckTest"
Cohesion: 0.07
Nodes (34): Candidate, CheckedFile, CorruptArchive, GameDataCheck, GameDataIssue, GameDataResult, GameFile, Invalid (+26 more)

### Community 3 - ".report"
Cohesion: 0.07
Nodes (28): 1.1 Data layer (`data/`), 1.3 Simulation core (`sim/`), 1.4 Deterministic seeded RNG (`sim.rng`), 1.5 Presenter, rendering and audio, 1.6 Touch-UI considerations, 1. Layered architecture, build_report(), _findings() (+20 more)

### Community 4 - "json"
Cohesion: 0.06
Nodes (15): RollPolicy, reach_digest(), army(), BattleFromPackTest, play(), golden_scenario(), growth_digest(), _dump() (+7 more)

### Community 5 - "BattleState"
Cohesion: 0.06
Nodes (27): AttackMovedScenario, ApplyResult, Battle, Damaged, IllegalCommand, Kind, ATTACK, DEFEND (+19 more)

### Community 6 - ".write"
Cohesion: 0.06
Nodes (17): AiChooserTest, _board_at(), _cell_glyphs(), ChooserTest, CliTestCase, golden_scenario(), GoldenScenarioTest, _grid_rows() (+9 more)

### Community 7 - "defimg.py"
Cohesion: 0.06
Nodes (37): 2026-11-02: first contact (H3ab_spr.lod, H3ab_ahd.snd, H3ab_ahd.vid, two hd_*.p32 files), Findings on real game files (structure only, no content), Still needed to proceed with 0.2, Blocks, Frame, Header, HoMM3 .DEF sprite container (clean-room notes), Implementation status / caveats (+29 more)

### Community 8 - "HexCell"
Cohesion: 0.07
Nodes (15): BoardGeometry, footprints(), Pt, UnitFootprint, UnitHit, BoardGeometryTest, Hex, HexCell (+7 more)

### Community 9 - "vectors_town.py"
Cohesion: 0.06
Nodes (61): _b(), _base(), _bigvalues(), _bld(), _canon(), classify_pack(), _cmd(), _create_cases() (+53 more)

### Community 10 - "assertequals"
Cohesion: 0.08
Nodes (14): Holding, plain(), session(), Fixture, Game, XcScenario, BattlePolicyPack, asDrawSource() (+6 more)

### Community 11 - "LodArchive"
Cohesion: 0.06
Nodes (28): inflateMember(), LodArchive, LodEntry, LodError, LodFormatError, LodKeyError, parsePcx(), PcxError (+20 more)

### Community 12 - "H3mTest.kt"
Cohesion: 0.09
Nodes (30): H3m, H3mDisposedHero, H3mError, H3mHeader, H3mHotaError, H3mLoss, H3mPlayer, H3mPredefinedHero (+22 more)

### Community 13 - "battle.py"
Cohesion: 0.06
Nodes (47): 1. Interface, 3. The battle, _activate_next(), _adjacent_cells(), apply(), _as_hex(), Attack, BattleEnded (+39 more)

### Community 14 - "BattleSession"
Cohesion: 0.07
Nodes (30): Accepted, AutosaveSink, BattleSession, Faulted, Illegal, LogEntry, NotYourTurn, Origin (+22 more)

### Community 15 - "hero.py"
Cohesion: 0.05
Nodes (40): Conformance: hero core (`h3.sim.hero`), Known differences (documented, not silent), Mutation check (producer's run, in a private copy; the lead re-verifies), Out of scope (Kotlin's types cannot express them), _advance(), apply(), _canon_bytes(), canonical() (+32 more)

### Community 16 - "vectors.py"
Cohesion: 0.07
Nodes (45): Test cost, _attack_defense_vectors(), _base_damage_vectors(), _canon_corpus(), _canon_vectors(), _chance_vectors(), check(), _clamp_attack() (+37 more)

### Community 17 - "Test"
Cohesion: 0.09
Nodes (19): BadDefName, BadRow, BadSchemaVersion, BadShape, DefHasPath, DuplicateRow, Failed, InvalidJson (+11 more)

### Community 18 - "build_lod"
Cohesion: 0.08
Nodes (8): build_lod(), CorruptPayloadTests, ExtractTests, MalformedInputTests, member(), open_bytes(), OpenAndListTests, ReadTests

### Community 19 - "test_encounter.py"
Cohesion: 0.09
Nodes (16): army(), BuildBattleTest, flat_grid(), fought(), golden_game(), GoldenTest, IllegalTest, OutcomeTest (+8 more)

### Community 20 - "vectors_hero.py"
Cohesion: 0.08
Nodes (40): _base(), _bigweights(), _canon(), classify_pack(), _cmd(), _create_cases(), add(), _create_error_category() (+32 more)

### Community 21 - "BattleLogTest"
Cohesion: 0.08
Nodes (18): BattleLog, BattleLogGroup, BattleLogKind, DEFEND, DIED, END, HIT, LUCK_BAD (+10 more)

### Community 22 - "LodArchive"
Cohesion: 0.07
Nodes (12): Discrepancies flagged (CLAUDE.md law 10), _check_member_name(), _decode_name(), _inflate(), _key(), LodArchive, LodEntry, LodError (+4 more)

### Community 23 - "ImportPlanTest"
Cohesion: 0.12
Nodes (10): AmbiguousSource, Chosen, InvalidName, MissingSource, Progress, SelectedFile, Selection, SourceEntry (+2 more)

### Community 24 - "parse_pcx"
Cohesion: 0.08
Nodes (17): Vectors, parse_pcx(), PcxError, PcxImage, _entry_pos(), generate(), _lod(), _lod_cases() (+9 more)

### Community 25 - "town.py"
Cohesion: 0.11
Nodes (32): _check_creatures(), _check_policy(), _check_rules(), DataPackError, _frac(), _int(), _list(), load() (+24 more)

### Community 26 - "generate_log"
Cohesion: 0.06
Nodes (12): check_seed(), _driver(), generate_log(), main(), policy_matrix(), run_seed(), soak(), soak_digest() (+4 more)

### Community 27 - "MainActivity.kt"
Cohesion: 0.05
Nodes (21): ImportScreen(), Screen, About, Battle, Home, Import, Result, Saves (+13 more)

### Community 28 - "AdventureState"
Cohesion: 0.11
Nodes (16): AdvEncounter, Adventure, AdventureEncounterHooks, AdventurePolicy, AdventureRules, AdventureState, AdvGrid, AdvGrowthPool (+8 more)

### Community 29 - "Vector file `town.json`"
Cohesion: 0.07
Nodes (30): Vector file `town.json`, 1. Interface, 4. Weekly growth, GrowthPool, Resources, _active(), active_buildings(), apply() (+22 more)

### Community 30 - "HeroTest"
Cohesion: 0.15
Nodes (4): ChooseSkill, GainXP, HeroTest, Script

### Community 31 - "module_doc"
Cohesion: 0.06
Nodes (7): TestContractEdgeVectors, DefVectorTests, PackVectorsTest, VectorsPresentTest, VectorsTxtTest, assert_module_deterministic(), module_doc()

### Community 32 - "Pcg32"
Cohesion: 0.12
Nodes (11): assertSameAtlas(), checkInvariants(), hex(), ok(), randomFrames(), shuffled(), solid(), SpriteAtlasTest (+3 more)

### Community 33 - "resolve_damage"
Cohesion: 0.10
Nodes (17): 5. Morale and luck, Rules: battle damage (`rules.json`), 8. Reference implementation, bad_morale_chance(), _clamp3(), damage_range(), DamageCtx, DamagePreview (+9 more)

### Community 34 - "replay.py"
Cohesion: 0.10
Nodes (23): _canon(), _check_plain(), Diverged, _is_int(), load(), Malformed, MismatchedCreatures, MismatchedPolicy (+15 more)

### Community 35 - "BoardView.kt"
Cohesion: 0.09
Nodes (19): BattleBody(), BattleScreen(), candidateLabel(), LogPanel(), PreviewPanel(), RosterPanel(), artPoint(), BoardSprites (+11 more)

### Community 36 - "GameController"
Cohesion: 0.08
Nodes (13): AppEngine, GameController, MainActivity, App screens (Compose, loop app-screens), App shell (milestone A7, MVP 0.1), Battle interaction, Data packs, Dependencies (+5 more)

### Community 37 - "BattleCodec"
Cohesion: 0.14
Nodes (6): BattleCodec, BattleJson, BattlePolicy, policyDefendBonus(), Contract edges: caps, policy and state rejects (`battle_states.json`), Out of scope / known differences (documented, not silent)

### Community 38 - "h3m.py"
Cohesion: 0.11
Nodes (32): _army(), _art(), _bits(), _body_abandoned_mine(), _body_artifact(), _body_event(), _body_garrison(), _body_generic() (+24 more)

### Community 39 - ".load"
Cohesion: 0.18
Nodes (13): LodSource, def(), F, idleOnlyDef(), le32(), lod(), lodWith(), pageAt() (+5 more)

### Community 40 - "adventure.py"
Cohesion: 0.07
Nodes (29): 1. Interface, adventure_rng(), apply(), Attack, base_movement(), Begin, calendar(), _check_army() (+21 more)

### Community 41 - "parse_txt"
Cohesion: 0.09
Nodes (12): API, Format, Limits, Options (backward compatibility), TXT tables (tab-separated), parse_txt(), read_txt(), _scan() (+4 more)

### Community 42 - "with"
Cohesion: 0.07
Nodes (39): runs-on, steps, timeout-minutes, runs-on, steps, H3_DATA_DIR, jobs, android-app (+31 more)

### Community 43 - "SegKind"
Cohesion: 0.09
Nodes (25): AnimationPrefs, AnimSpeed, FAST, NORMAL, SKIP, SLOW, Frames, SegKind (+17 more)

### Community 44 - "SpriteLoadPlan.kt"
Cohesion: 0.07
Nodes (23): BuildResult, Failed, Ok, Reason, DUPLICATE_KEY, FRAME_TOO_LARGE, OVER_BUDGET, SpriteScale (+15 more)

### Community 46 - "Encounter.kt"
Cohesion: 0.10
Nodes (10): AdvArmySlot, AdvGuard, ArmyChanged, BattleFought, EncounterEngine, Fought, GuardDefeated, HeroDefeated (+2 more)

### Community 49 - "vectors_encounter.py"
Cohesion: 0.11
Nodes (25): Vector file `encounter.json`, Vector file `hero.json`, all_games(), auto_cases(), _battery(), _case(), choose(), constants() (+17 more)

### Community 50 - "test_h3m.py"
Cohesion: 0.20
Nodes (23): box(), e_army(), e_box(), e_event_common(), e_hero(), e_monster(), e_msg_guards(), e_opt8() (+15 more)

### Community 51 - "SaveSlots"
Cohesion: 0.12
Nodes (22): readSaveFolder(), SaveRowCard(), SaveScreen(), FileState, Invalid, Missing, Valid, Load (+14 more)

### Community 52 - "SaveSlotsTest"
Cohesion: 0.15
Nodes (5): Listing, MemFolder, Played, SaveSlotsTest, Scn

### Community 53 - "BattleStateTest"
Cohesion: 0.14
Nodes (3): BattleStateTest, MiniJson, Amendment (2026-11-01): caps on derived products

### Community 54 - "TownConformanceTest.kt"
Cohesion: 0.16
Nodes (12): assertError(), canonText(), commandOf(), eventMap(), i32(), kindOf(), lng(), policyOf() (+4 more)

### Community 55 - "vectors_pack.py"
Cohesion: 0.12
Nodes (24): classify(), _collect_invalid(), data_dir(), _delete(), _derived_valid(), dumps(), walk(), _extra_invalid() (+16 more)

### Community 56 - "parse_creatures"
Cohesion: 0.17
Nodes (12): ContentError, ContentResult, _int(), _layout(), load_creatures(), load_mapping(), _norm(), parse_creatures() (+4 more)

### Community 57 - "ScriptRng"
Cohesion: 0.14
Nodes (7): begin(), CombatTest, four(), LastMoverOrderTest, MoraleTest, QueueTest, ScriptRng

### Community 58 - "kotlin_banned_api_lint.py"
Cohesion: 0.08
Nodes (13): KotlinLintTests, rules(), apply_allowlist(), default_paths(), _entry_matches(), lint_paths(), lint_source(), load_allowlist() (+5 more)

### Community 59 - "MenuModelTest"
Cohesion: 0.12
Nodes (9): menuEdgeAllowed(), MenuModel, MenuRoute, About, Battle, Home, Result, Setup (+1 more)

### Community 60 - "Hero.kt"
Cohesion: 0.14
Nodes (21): Category, asHeroDraw(), Hero, HeroApplyResult, HeroCategory, HeroCommand, HeroDraw, HeroEvent (+13 more)

### Community 61 - "apply_damage"
Cohesion: 0.08
Nodes (21): 3. Movement [documented], 4. Turn queue, 6. Damage and attacks, 7. Battle end, 8. Uncertain policy summary, 9. Tests, Battle simulation core (`sim.battle`), 1. Contract (+13 more)

### Community 62 - "battle_cli.py"
Cohesion: 0.15
Nodes (22): _ai(), pick(), _check_keys(), _check_pretty_options(), CliError, _creature(), _dataclass_kwargs(), _first_legal() (+14 more)

### Community 63 - "Pcg32"
Cohesion: 0.11
Nodes (4): Pcg32, _TracedPcg32, WeakUnitDamageTest, TestPcg32

### Community 64 - "Def"
Cohesion: 0.16
Nodes (11): Def, DefBlock, DefException, DefFile, DefFrame, Out, Reader, Ambiguities / notes (+3 more)

### Community 65 - "HeroConformanceTest.kt"
Cohesion: 0.17
Nodes (12): canonText(), commandOf(), CountingDraw, eventMap(), HeroConformanceTest, HeroVectors, i32(), lng() (+4 more)

### Community 66 - "present.py"
Cohesion: 0.10
Nodes (22): 1. Spec grounding and gaps, 5.1 Preview and confirm (pure reducer in `:presenter`), 5.2 Hit-testing (`:app`, `h3.app.board.BoardGeometry`), 5.3 Accessibility, 5.4 Layout, 5. Touch interaction, What is pinned, _actions() (+14 more)

### Community 67 - "Test"
Cohesion: 0.18
Nodes (8): ctxOf(), isError(), loadPack(), long(), longs(), rat(), RationalTest, RulesTest

### Community 68 - "encounter.py"
Cohesion: 0.09
Nodes (17): ArmyChanged, auto_command(), BattleFought, build_battle(), check_game(), _creature(), EncounterPolicy, EncounterSetup (+9 more)

### Community 69 - "grid"
Cohesion: 0.11
Nodes (5): game(), grid(), PolicyTest, StepCostTest, costs()

### Community 70 - ".boardStacks"
Cohesion: 0.21
Nodes (8): ArtPoint, ArtRect, BoardArt, BoardStack, CountPlate, SpriteDraw, StackArt, BoardArtTest

### Community 71 - "Rational"
Cohesion: 0.11
Nodes (3): Rational, RulesPack, ADR-0009: The Kotlin engine uses a small exact Rational type with one named rounding step, not an integer rewrite

### Community 72 - "Rules"
Cohesion: 0.11
Nodes (11): DrawSource, AttackDefenseFactor, DamagePreview, DamageResult, DrawSource, RollPolicy, ACTUAL_SEED, EXPECTED (+3 more)

### Community 73 - "Android app design (`android/`)"
Cohesion: 0.06
Nodes (30): 0. Problem statement, 10. Determinism and purity impact, 11. Risks, 12. Assumptions (proposed defaults; the owner may overturn any), 13. Out of scope, 14. Open questions for the owner, 3.1 Principles, 3.2 Flow (+22 more)

### Community 74 - "vectors_adventure.py"
Cohesion: 0.12
Nodes (23): Vector contents, build_adventure(), _decode(), edge_day_cases(), encode_event(), _enum_cases(), generate(), golden_commands() (+15 more)

### Community 75 - "parse_h3m_bytes"
Cohesion: 0.16
Nodes (6): parse_h3m(), parse_h3m_bytes(), build(), extra(), H3mTests, tiles_for()

### Community 76 - "BattleTest"
Cohesion: 0.17
Nodes (4): BattleTest, DrawSource, DrawSource, Outcome

### Community 77 - "TestBattleVectors"
Cohesion: 0.10
Nodes (8): decode_command(), doc(), _floats(), VectorsAiTest, state_from_json(), stream_at(), _t(), TestBattleVectors

### Community 78 - "VectorsHeroTest"
Cohesion: 0.13
Nodes (4): doc(), _floats(), _steps(), VectorsHeroTest

### Community 79 - ".encode"
Cohesion: 0.14
Nodes (3): Canonical, ConformanceTest, PresentTest

### Community 80 - "H3mObjectTests"
Cohesion: 0.15
Nodes (5): ObjectTemplate, Tile, e_objects(), H3mObjectTests, map_with()

### Community 81 - "ResumeError"
Cohesion: 0.11
Nodes (21): Failed, Ok, ReplayResume, Resumed, ResumeError, Diverged, Malformed, MismatchedCreatures (+13 more)

### Community 82 - "ReplayAutosaveTest"
Cohesion: 0.22
Nodes (4): Case, MemSink, ReplayAutosaveTest, Run

### Community 83 - "AdventureEvent"
Cohesion: 0.10
Nodes (13): AdventureEvent, AdventureStep, DayStarted, HeroMoved, IncomeReceived, MovementReset, PoolGrew, TurnEnded (+5 more)

### Community 84 - "Replay"
Cohesion: 0.21
Nodes (13): Diverged, Loaded, Malformed, MismatchedCreatures, MismatchedPolicy, MismatchedRulesPack, Replay, ReplayError (+5 more)

### Community 85 - "_Reader"
Cohesion: 0.12
Nodes (13): H3mError, H3mHeader, PlayerInfo, _read_extra(), _read_loss(), _read_mask(), _read_objects(), _read_player() (+5 more)

### Community 86 - "Datapack"
Cohesion: 0.19
Nodes (6): CreaturesDoc, Datapack, PolicyDoc, RulesDoc, ReplayVectors, API (Kotlin)

### Community 87 - "TownCore"
Cohesion: 0.16
Nodes (5): Building, Faction, TownContent, TownCore, TownKeyError

### Community 88 - "bisect_tool.py"
Cohesion: 0.12
Nodes (17): bisect(), diff_states(), dump_log(), flatten(), format_policy(), format_report(), load_log(), load_log_ex() (+9 more)

### Community 89 - "game"
Cohesion: 0.14
Nodes (6): build(), build_days(), BuildTest, game(), IncomeTest, NoRng

### Community 90 - "VectorsTownTest"
Cohesion: 0.14
Nodes (7): _cmd(), doc(), _err(), _floats(), NoRng, _steps(), VectorsTownTest

### Community 91 - "Atlas"
Cohesion: 0.14
Nodes (11): add(), addAll(), Atlas, BudgetCheck, Exceeded, FrameMeta, Page, Rect (+3 more)

### Community 92 - "BattleCommand"
Cohesion: 0.14
Nodes (19): Cancel, Candidate, Confirmed, Idle, Previewing, PreviewNumbers, Select, Tap (+11 more)

### Community 93 - "GameDataLayoutTest"
Cohesion: 0.17
Nodes (7): GameDataLayout, GameDataLayoutTest, glCheckAccepts(), GlFixture, glLayoutFindsAll(), glLe32(), glLod()

### Community 94 - "Scenario"
Cohesion: 0.19
Nodes (5): BattleHero, BattleEngine, Scenario, ScenarioError, Setup

### Community 95 - "Town.kt"
Cohesion: 0.14
Nodes (17): BuildingBuilt, Dwelling, IllegalCommand, NewDay, RawResources, RawSetup, TownApplyResult, TownCategory (+9 more)

### Community 96 - "base_damage"
Cohesion: 0.10
Nodes (16): Changed cases, content.json, Data pack and content floor (second commit), datapack.json, encounter.json, Generator changes (`tools/h3re/h3re/vectors.py`), rules.json, Unchanged (+8 more)

### Community 97 - "SetupForm"
Cohesion: 0.16
Nodes (13): presetErrorText(), seedErrorText(), setupFormMessage(), PresetError, NoPresets, OutOfRange, SeedError, Empty (+5 more)

### Community 98 - "BattleEvent"
Cohesion: 0.12
Nodes (22): BattleEnded, BattleEvent, BattleStarted, DamageDealt, Defended, LuckRolled, MoraleBoost, MoraleFrozen (+14 more)

### Community 100 - "dataclasses"
Cohesion: 0.16
Nodes (18): army(), _bpol(), check_game_cases(), add(), _creature_swap(), draw_game(), golden_game(), grid() (+10 more)

### Community 101 - "Rules specification"
Cohesion: 0.08
Nodes (24): 0. Provenance and tagging, 1. Calendar and turn structure, 2.1 Movement points (land), 2.2 Terrain cost, 2. Adventure map: movement, 3. Resource economy, 4. Towns, 5.1 Primary skills (+16 more)

### Community 102 - "re"
Cohesion: 0.15
Nodes (16): _h3re_version(), _back_edges(), visit(), eval_graph(), eval_run(), _load_run(), main(), parse_loop() (+8 more)

### Community 103 - "real_report.py"
Cohesion: 0.16
Nodes (15): _archive_report(), cmd(), _count_errors(), _decode(), _def_report(), _etype(), _find_sprite_lods(), _h3m_error() (+7 more)

### Community 104 - "vectors_replay.py"
Cohesion: 0.15
Nodes (19): run_chooser(), _creature_dict(), _explicit_pos_scenario(), generate(), _golden(), _hero_dict(), _jsonable(), main() (+11 more)

### Community 105 - "cr"
Cohesion: 0.17
Nodes (5): cr(), MovementTest, SetupTest, ss(), WaitActivationMoraleTest

### Community 106 - "rules"
Cohesion: 0.18
Nodes (3): GraphCriteria, rules(), RunCriteria

### Community 107 - "_Visitor"
Cohesion: 0.16
Nodes (3): _is_set_expr(), Violation, _Visitor

### Community 108 - "PresentTest"
Cohesion: 0.13
Nodes (6): all_states(), FailRng, golden_states(), PresentTest, synthetic_states(), walk()

### Community 109 - "ImportPlan"
Cohesion: 0.13
Nodes (10): DataStatus, Changed, Found, Missing, ImportPlan, NotEnoughSpace, Ok, SpaceCheck (+2 more)

### Community 110 - ".parseCreatures"
Cohesion: 0.17
Nodes (11): Content, ContentError, ContentResult, Creature, CreatureMapping, CreatureValidator, MapColumn, UnknownAbility (+3 more)

### Community 111 - "HeroCore"
Cohesion: 0.19
Nodes (3): HeroClass, HeroContent, HeroCore

### Community 112 - "test_adventure.py"
Cohesion: 0.15
Nodes (8): army(), FloatSub, golden_setup(), GoldenTest, MovementPointsTest, play_days(), PropertyTest, scripted_turn()

### Community 113 - "test_battle.py"
Cohesion: 0.15
Nodes (8): golden_setup(), GoldenTest, play(), PolicyDefaultsFromPackTest, PreviewLawTest, PropertyTest, scripted_choice(), total_hp()

### Community 114 - "_Pretty"
Cohesion: 0.13
Nodes (12): Files, _board_lines(), _fields(), _hp(), _legend_lines(), _mark(), _pos_text(), _Pretty (+4 more)

### Community 115 - "_run_isolated"
Cohesion: 0.14
Nodes (6): _probe(), _repo_data_dir(), _run_isolated(), TestBattleExports, TestImportSideEffects, TestRulesPackIdentity

### Community 116 - "StackRosterRow"
Cohesion: 0.19
Nodes (6): RosterSide(), BattlePanels, RosterEntry, TurnChip, StackRosterRow, BattlePanelsTest

### Community 117 - ".plan"
Cohesion: 0.18
Nodes (13): CopyToPart, DeleteOld, MoveLiveToOld, PromoteStaging, RenamePart, Step, SyncFile, WriteManifest (+5 more)

### Community 118 - "__main__.py"
Cohesion: 0.18
Nodes (13): build_parser(), cmd_battle_sim(), cmd_def_to_png(), cmd_h3m_info(), cmd_lod_extract(), cmd_lod_list(), cmd_replay(), _condition() (+5 more)

### Community 119 - "create_battle"
Cohesion: 0.16
Nodes (17): 2. Grid, Hex: battle grid geometry and movement (`hex.json`), 3. Proposed design, BattleState, _cells_at(), check_state(), create_battle(), _fits() (+9 more)

### Community 120 - ".parse"
Cohesion: 0.29
Nodes (4): enc(), EncounterConformanceTest, EncVectors, s()

### Community 121 - "RealLodTests"
Cohesion: 0.12
Nodes (12): 1. Point the tools at your game folder, 2. Run the real-file tests (optional, local only), 3. Make the report, 4. What to send back, 5. What we do with each result, Privacy checklist before sending, Runbook: check the project against your own Heroes 3 files, What the report contains, and nothing else (+4 more)

### Community 125 - "AdventureCodec"
Cohesion: 0.18
Nodes (7): AdventureCodec, AdventureCommand, Attack, Begin, EndTurn, Move, Command fields are strict integers

### Community 127 - "vectors_txt.py"
Cohesion: 0.20
Nodes (14): _base(), _content_case(), _content_cases(), _content_error(), _creature_row(), generate(), _header(), _Lcg (+6 more)

### Community 129 - "ReplayAutosave"
Cohesion: 0.18
Nodes (3): SaveFolderWriter, ByteSink, ReplayAutosave

### Community 130 - "Txt.kt"
Cohesion: 0.14
Nodes (8): Txt, TxtError, TxtErrorCategory, DECODE, HEADER_ROWS, TOO_LARGE, TOO_MANY_LINES, UNKNOWN_ENCODING

### Community 132 - "Creature"
Cohesion: 0.11
Nodes (12): API, Files, 0. Goals and clean-room constraints, 1.2 Content layer (`content/`), 2. Testing strategy, 3. Phased roadmap, 4. Open architecture questions, Engine design: heroes-mobile (+4 more)

### Community 134 - "AtlasFrame"
Cohesion: 0.29
Nodes (4): AtlasFrame, frame(), px(), SpriteScaleTest

### Community 136 - "Kotlin API"
Cohesion: 0.29
Nodes (6): JsonFraction, P, Rejected, ScenarioJson, Syntax, Kotlin API

### Community 137 - "_search"
Cohesion: 0.12
Nodes (10): 1. Soak (`tools/h3re/h3re/soak.py`), 2. Bisector (`tools/h3re/h3re/bisect_tool.py`), 3. Banned-API lint (`tools/lint/banned_api_lint.py`), CI, Determinism gate, Kotlin banned-API lint (`tools/lint/kotlin_banned_api_lint.py`), AdventurePolicy, _int_in() (+2 more)

### Community 138 - "verify"
Cohesion: 0.21
Nodes (5): info(), verify(), add(), ReplayTest, reseal()

### Community 139 - "hero"
Cohesion: 0.21
Nodes (5): gain(), hero(), LevelUpTest, resolve(), XpTest

### Community 140 - ".test_every_mutation_changes_the_hash"
Cohesion: 0.17
Nodes (5): StoredContentHashTest, high(), low(), sec(), start()

### Community 142 - "ManifestError"
Cohesion: 0.12
Nodes (15): ManifestError, BadName, BadNumber, BadString, DuplicateKey, DuplicateName, MissingKey, NoFiles (+7 more)

### Community 143 - "TownState"
Cohesion: 0.37
Nodes (3): GrowthPool, Town, TownState

### Community 144 - "Battle scenario file (JSON)"
Cohesion: 0.12
Nodes (11): Checkpoint log, Reverse-engineering loop graph, 1. Document, 2. Creatures, 3. Stacks, 4. Heroes, 5. Policy, 6. Choosers (+3 more)

### Community 145 - "Handoff (resume here)"
Cohesion: 0.12
Nodes (16): Checkpoint 0.2 status (2026-11-02), Checkpoint 2026-11-02b (status), Checkpoint 75 notes, Checkpoint 77, Checkpoint 81 (2026-11-02), Checkpoint 82 (parity gaps closed), Checkpoint 83 (wrap-up, 91%+), Checkpoint 84 (import UI wired) (+8 more)

### Community 147 - "10. Change notes"
Cohesion: 0.13
Nodes (12): 10. Change notes, 2026-11-01: golden hash re-pinned a second time (rules pack in the hash), 2026-11-01: golden hash re-pinned (one reviewed change), 2026-11-01: malformed hex raises IllegalCommand (no re-pin), 2026-11-01: state invariants and integer caps (no re-pin), 2026-11-02: weak-unit vectors re-pinned (owner review pending), Later: policy defaults moved to data, `apply` checks the pack (no re-pin), 2. Validation (+4 more)

### Community 148 - "BattleAiTest"
Cohesion: 0.20
Nodes (3): BattleAiTest, play(), scenario()

### Community 149 - "damage_from_base"
Cohesion: 0.19
Nodes (4): _check_flags(), damage_from_base(), DamageFromBaseTest, DamageRangeTest

### Community 152 - "BattleCreature"
Cohesion: 0.23
Nodes (4): Preset, BattleCreature, EncounterPolicy, EncounterSetup

### Community 153 - "SpriteLoader.kt"
Cohesion: 0.21
Nodes (3): Loaded, SpriteLoader, PagePixels

### Community 154 - "Adventure-map simulation core (`sim.adventure`): movement and economy"
Cohesion: 0.15
Nodes (12): 1. Interface, 2. Grid and step costs, 3. Movement points, 4. Pathfinding, 5. Calendar, income and growth, 7. Tests, 8. Encounters (battles on the map), Adventure-map simulation core (`sim.adventure`): movement and economy (+4 more)

### Community 155 - "DataPack"
Cohesion: 0.13
Nodes (7): Hashes, 2. Current state, DataPack, _is_frac(), _is_frac_table(), load_rules(), load_rules_pack()

### Community 156 - "Data pack (`h3re.datapack`)"
Cohesion: 0.15
Nodes (11): Battle policy pack, Data pack (`h3re.datapack`), Determinism and hash, Drift guard, Integer range, Pack directory and rules hash (determinism audit), Runtime loading (checkpoint 34), Validation (+3 more)

### Community 157 - "ImportPlanTest.kt"
Cohesion: 0.14
Nodes (5): RecoverAction, DeleteLive, DeleteOld, DeleteStaging, RestoreOld

### Community 159 - "Conformance: adventure core (Kotlin port)"
Cohesion: 0.18
Nodes (12): 6. Policy fields (`AdventurePolicy`), Default changes and the golden hash, Integer bounds and types (amendment, ADR-0008 style), The day counter, Conformance: adventure core (Kotlin port), Kotlin test (`AdventureTest`), Policy bounds and guard order, Policy flags (+4 more)

### Community 161 - "TownText"
Cohesion: 0.20
Nodes (5): TownText, Conformance: town core (`h3.sim.town`), Known differences (documented, not silent), Mutation check (producer's run, in a private copy; the lead re-verifies), Out of scope (Kotlin's types cannot express them)

### Community 162 - ".parse"
Cohesion: 0.31
Nodes (5): DefTest, hex(), hexStr(), long(), sha()

### Community 164 - "Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)"
Cohesion: 0.15
Nodes (10): ADR-0001: Canonical JSON form and SHA-256 state hash for battle and adventure state, ADR-0005: The omit-at-default canonical mechanism applies to every state module, not only battle, 5. Policy fields (`EncounterPolicy`), 6. Canonical form and hashes, 7. Golden encounter hash, 8. Tests, 9. Open items, Encounters: adventure-map battles (`sim.adventure` + `sim.battle`) (+2 more)

### Community 165 - "TestVectors"
Cohesion: 0.14
Nodes (3): Open items, TestVectors, fresh_all()

### Community 166 - "H3mUnsupportedObject"
Cohesion: 0.16
Nodes (9): End of data, Global events, Object instances, Objects, object instances and events (`objects=True`), Template table, Unverified assumptions (objects section), H3mUnsupportedObject, MapObject (+1 more)

### Community 168 - "ResultSummary"
Cohesion: 0.24
Nodes (8): ResultScreen(), SideTallyCard(), ResultOutcome, Defeat, Unfinished, Victory, ResultSummary, SideTally

### Community 169 - "ManifestFile"
Cohesion: 0.27
Nodes (5): Failed, Manifest, ManifestFile, ManifestParse, Parsed

### Community 171 - "Runbook: smoke-test the debug app on a real Android phone"
Cohesion: 0.15
Nodes (12): 10. What this does NOT test, 11. What we do with each result, 1. Get the debug APK from CI, 2. Install it, 3. What each screen should do, 4. Main checklist, 5. Risk checks (the ones most likely to find real bugs), 6. Sprites: what to expect (+4 more)

### Community 172 - "Replay file format"
Cohesion: 0.15
Nodes (10): 1. Encoding, 2. Header (all keys required, unknown keys rejected), 3. Body, 4. Verification order and errors, 5. API and CLI, 6. Notes, Replay file format, state_hash() (+2 more)

### Community 173 - "jsonable"
Cohesion: 0.22
Nodes (11): build_setup(), _creature_json(), encode(), jsonable(), _policy_json(), setup_cases(), add(), with_() (+3 more)

### Community 174 - "raw"
Cohesion: 0.24
Nodes (3): LoadTest, raw(), ValidationTest

### Community 176 - "SpriteImportNameCrossCheckTest"
Cohesion: 0.35
Nodes (3): SpriteImportNameCrossCheckTest, xcImport(), xcImportPick()

### Community 177 - ".parse"
Cohesion: 0.29
Nodes (3): TxtTable, hexBytes(), TxtTest

### Community 179 - "started"
Cohesion: 0.20
Nodes (3): MalformedDestTest, RoadCostCanonicalTest, started()

### Community 183 - "IoStage"
Cohesion: 0.18
Nodes (7): IoFailed, IoStage, Copy, Manifest, Recover, Scan, Swap

### Community 184 - "DatapackError"
Cohesion: 0.42
Nodes (9): bad(), DatapackError, floatErr(), lit(), num(), parse(), pyRepr(), value() (+1 more)

### Community 185 - "2. Module layout and dependency rules"
Cohesion: 0.36
Nodes (3): DamageCtx, WeakUnitDamageTest, 2. Module layout and dependency rules

### Community 187 - "Loop: one agent round (advise, fan out, verify, checkpoint)"
Cohesion: 0.18
Nodes (10): Actions, Budget, Evidence, Goal and input, Loop: one agent round (advise, fan out, verify, checkpoint), Notes learned the hard way, Observation, State (+2 more)

### Community 188 - "Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)"
Cohesion: 0.18
Nodes (8): Abilities, API, Column order (data: `data/txt_maps/crtraits.json`, unverified), Content loader (`h3re.content`), engine roadmap Phase 4 (creatures), Errors, Reading, Tests, RealCrtraitsTest

### Community 189 - "LOD archive format"
Cohesion: 0.18
Nodes (10): Directory entry (32-byte stride), Errors, Extraction safety, File layout, Header (92 bytes), LOD archive format, Name rules, Open items (+2 more)

### Community 190 - "_bld"
Cohesion: 0.31
Nodes (10): 2. Content model (pack schema v1), 5. Economy and integration, _bld(), cost(), f(), income(), f(), other_faction() (+2 more)

### Community 191 - "vectors_present.py"
Cohesion: 0.31
Nodes (7): _canon(), _entries(), generate(), main(), _playouts(), _sha(), _taps()

### Community 193 - "doc"
Cohesion: 0.31
Nodes (3): doc(), _floats(), VectorsReplayTest

### Community 194 - "ContentErrorCategory"
Cohesion: 0.20
Nodes (10): ContentErrorCategory, DUPLICATE, EMPTY_CELL, HEADER, MAPPING, MISSING_CELL, NO_ROWS, NOT_INTEGER (+2 more)

### Community 195 - "Resources"
Cohesion: 0.42
Nodes (3): Resources, resOf(), typedPlayers()

### Community 196 - "_step_parts"
Cohesion: 0.22
Nodes (6): ADR-0002: Integer-only simulation (int and Fraction, one explicit rounding step), _diagonal(), _div(), _orth_cost(), step_cost(), _step_parts()

### Community 197 - "Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic)"
Cohesion: 0.20
Nodes (9): Actions, Budget, Evidence, Goal and input, Loop: app screens (Compose screens for `:app` on the merged `:presenter` ui logic), Observation, State, Stop and escalation (+1 more)

### Community 198 - "Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors)"
Cohesion: 0.20
Nodes (9): Actions, Budget, Evidence, Goal and input, Loop: hero port (Python hero core to Kotlin `h3.sim.hero`, with conformance vectors), Observation, State, Stop and escalation (+1 more)

### Community 199 - "Hero simulation core (`sim.hero`): experience, levels and skill gain"
Cohesion: 0.20
Nodes (9): 1. Interface, 2. Content model (pack schema v1), 3. Experience and levels, 4. Level-up, 5. Secondary skills, 6. Policy fields (`HeroPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch) (+1 more)

### Community 202 - "GreedyAi"
Cohesion: 0.25
Nodes (5): GreedyAi, ADR-0012: The session AI is a pure function of the state, Behaviour change, Consequences, Context

### Community 203 - "HoMM3 .H3M map header (clean-room notes)"
Cohesion: 0.22
Nodes (8): After teams (parsed; then terrain tiles), Conditions and teams, Header, HoMM3 .H3M map header (clean-room notes), Not implemented, Players (8 slots), Verification status, levels()

### Community 204 - "Sprite atlas builder"
Cohesion: 0.22
Nodes (8): Input and output, Mask pages, Memory (4.5), Open points, Packing, Pixel conversion, Sprite atlas builder, Upscaling (0.2)

### Community 205 - "heroes-mobile"
Cohesion: 0.22
Nodes (9): Development loop, Features, heroes-mobile, License, Project laws, Quick start, Repository layout, Status (+1 more)

### Community 206 - "attack_defense_factor"
Cohesion: 0.28
Nodes (4): attack_defense_factor(), _scaled(), _skill(), AttackDefenseTest

### Community 208 - "PolicyPackTest"
Cohesion: 0.28
Nodes (3): PolicyPackTest, bad(), raw_policy()

### Community 210 - "raw"
Cohesion: 0.36
Nodes (3): PackTest, raw(), with_class()

### Community 217 - "ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build)"
Cohesion: 0.25
Nodes (7): ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build), Alternatives considered, Consequences, Context, Decision, Verification, Why

### Community 218 - "MVP 0.1: a playable skirmish APK"
Cohesion: 0.25
Nodes (7): Decisions needed from the owner, Goal (one sentence, with its test), MVP 0.1: a playable skirmish APK, Remaining work for 0.1, in order, Risks specific to 0.1, What 0.1 is, and is not, What exists today (checkpoints up to 59, plus agents in flight)

### Community 219 - "_play"
Cohesion: 0.36
Nodes (5): _interactive(), pick(), _log(), _play(), _record()

### Community 220 - "DefaultCreatureValidator"
Cohesion: 0.29
Nodes (5): DefaultCreatureValidator, ADR-0008: Kotlin pack values are 32-bit Int capped at 2**31-1; hashes and XP accumulation use Long, CRTRAITS hp floor 0: content.json re-pin, Other vector files, Vector change (`android/sim/src/test/resources/vectors/content.json`)

### Community 222 - "Second brain (project memory)"
Cohesion: 0.29
Nodes (6): Note format, Operations, Principles, Relationship to other records, Second brain (project memory), What never goes in

### Community 223 - "ADR-0004: Android app with a Kotlin engine; Python is the reference oracle"
Cohesion: 0.29
Nodes (7): ADR-0004: Android app with a Kotlin engine; Python is the reference oracle, Amendments (2026-11-01), Consequences, Context, Decision, Risks, Why

### Community 224 - "ADR-0014: Creature sprite table ported from VCMI, keyed by CRTRAITS row"
Cohesion: 0.29
Nodes (6): ADR-0014: Creature sprite table ported from VCMI, keyed by CRTRAITS row, Alternatives considered, Consequences, Context, Decision, Re-pin and verification

### Community 225 - "Battle roster from the player's CRTRAITS.TXT"
Cohesion: 0.29
Nodes (6): 1. Status, 4. Hash impact, 5. Test plan, 6. Risks and open questions, 7. Slices, Battle roster from the player's CRTRAITS.TXT

### Community 226 - "Town simulation core (`sim.town`): buildings, build rules and weekly growth"
Cohesion: 0.29
Nodes (6): 3. Building, 6. Policy fields (`TownPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch), Growth pools digest (second pin), Town simulation core (`sim.town`): buildings, build rules and weekly growth

### Community 229 - "heroes-mobile: project constitution"
Cohesion: 0.33
Nodes (5): Commands, heroes-mobile: project constitution, Laws, Roles and delegation, Working principles

### Community 230 - "HoMM3 PCX bitmap variant (clean-room notes)"
Cohesion: 0.33
Nodes (5): Errors, Header (12 bytes), HoMM3 PCX bitmap variant (clean-room notes), Mode selection, Open items

### Community 231 - "_canon_bytes"
Cohesion: 0.33
Nodes (4): _canon_bytes(), canonical(), content_hash(), state_hash()

### Community 239 - "WriteStep"
Cohesion: 0.40
Nodes (5): WriteStep, CopyMainToBackup, RenameTempToMain, SyncTemp, WriteTemp

### Community 240 - "Loop graph builder"
Cohesion: 0.40
Nodes (4): Contract template, Loop graph builder, Principles (Karpathy-style, applied), Procedure

### Community 241 - "ADR-0010: The project is licensed GPL-2.0-or-later"
Cohesion: 0.40
Nodes (4): ADR-0010: The project is licensed GPL-2.0-or-later, Consequences, Context, Decision

### Community 242 - "Conformance: data-pack loader (`vectors/datapack.json`)"
Cohesion: 0.40
Nodes (4): Conformance: data-pack loader (`vectors/datapack.json`), Error classes, File layout, Known limits

### Community 243 - "index.sh"
Cohesion: 0.40
Nodes (3): GRAPHIFY_BACKEND, GRAPHIFY_QUERY_LOG_DISABLE, index.sh script

### Community 250 - "Conformance: scenario and replay (milestone A5)"
Cohesion: 0.50
Nodes (3): Conformance: scenario and replay (milestone A5), Known differences (documented, not silent), Vector file `replay.json`

## Knowledge Gaps
- **134 isolated node(s):** `Home`, `Setup`, `Battle`, `Result`, `About` (+129 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1532 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **156 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `derive_stream()` connect `derive_stream` to `json`, `BattleState`, `vectors_town.py`, `battle.py`, `BattleSession`, `hero.py`, `vectors.py`, `VectorsEncounterTest`, `test_encounter.py`, `vectors_hero.py`, `town.py`, `Vector file `town.json``, `adventure.py`, `vectors_encounter.py`, `GoldenTest`, `Pcg32`, `TestBattleVectors`, `GoldenTest`, `ADR-0004: Android app with a Kotlin engine; Python is the reference oracle`, `BattleEvent`, `heroes-mobile: project constitution`, `test_adventure.py`, `test_battle.py`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `HexCell` (e.g. with `.enemyDist()` and `.checkState()`) actually correct?**
  _`HexCell` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Home`, `Setup`, `Battle` to the rest of the system?**
  _134 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `derive_stream` be split into smaller, more focused modules?**
  _Cohesion score 0.03521703521703522 - nodes in this community are weakly interconnected._
- **Why does `Battle state (`battle_states.json`)` connect `BattleEvent` to `derive_stream`, `BattleCodec`, `BattleState`, `assertequals`, `.encode`, `vectors_encounter.py`, `BattleStateTest`, `create_battle`, `BattleCreature`, `BattleCommand`, `Scenario`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `derive_stream()` (e.g. with `sim-engineer.md` and `Laws`) actually correct?**
  _`derive_stream()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `struct` be split into smaller, more focused modules?**
  _Cohesion score 0.050183150183150185 - nodes in this community are weakly interconnected._