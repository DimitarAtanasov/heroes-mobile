# Graph Report - proj  (2026-11-01)

## Corpus Check
- 183 files · ~191,710 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 3, .properties 2, .xml 1)

## Summary
- 3582 nodes · 8367 edges · 211 communities (126 shown, 85 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 622 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- .write
- replay.py
- LodArchive
- h3m.py
- battle_cli.py
- vectors.py
- town.py
- __init__.py
- .decodeFrame
- test_encounter.py
- datapack.py
- Battle
- hero.py
- BattleState
- HexCell
- defimg.py
- raw
- with
- Data pack (`h3re.datapack`)
- run_cli
- test_town.py
- Datapack
- vectors_battle.py
- vectors_pack.py
- soak.py
- encounter.py
- adventure.py
- parse_txt
- parse_h3m_bytes
- test_h3m.py
- Battle scenario file (JSON)
- H3mObjectTests
- struct
- build_lod
- BattleTest
- content.py
- Pcg32
- cr
- BattleStateTest
- Rational
- grid
- BattleCodec
- parse_pcx
- ScriptRng
- BattleCommand
- bisect_tool.py
- rules
- _Visitor
- derive_stream
- PolicyPackTest
- Rules specification
- vectors_ai.py
- parse_def
- loadVector
- re
- test_battle.py
- kotlin_banned_api_lint.py
- argparse
- LodArchive
- LodFormatError
- resolve_damage
- _run_isolated
- __main__.py
- Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)
- create_battle
- test_adventure.py
- SoakTest
- .resolveDamage
- TestBattleVectors
- RulesTest.kt
- rules.py
- vectors_txt.py
- PresentTest
- Adventure-map simulation core (`sim.adventure`): movement and economy
- _validate
- damage_from_base
- present.py
- LintTest
- .parseCreatures
- vectors_lodpcx.py
- _activate_next
- hero
- .test_every_mutation_changes_the_hash
- base_damage
- BattleAiTest
- NoRng
- BisectPolicyTest
- Pcg32
- LegalTest
- battle.py
- _search
- Rules: battle damage (`rules.json`)
- Hero simulation core (`sim.hero`): experience, levels and skill gain
- .parseEvent
- AdventurePolicy
- Objects, object instances and events (`objects=True`)
- write_png
- candidate_actions
- Txt.kt
- .parse
- BattleAiTest
- Android app design (`android/`)
- LodPcxVectorTests
- Datapack.kt
- Rules
- MiniJson.kt
- Test
- Battle simulation core (`sim.battle`)
- KotlinLintTests
- LoopCheck
- test_vectors_ai.py
- Loop: one agent round (advise, fan out, verify, checkpoint)
- MEMORY.md
- HoMM3 .H3M map header (clean-room notes)
- LOD archive format
- NoRng
- RealLodTests
- ContentErrorCategory
- PresentTest
- IllegalCommand
- _strike
- started
- IntegerCapTest
- Scripted
- round_order
- turn_order
- apply_damage
- StrictIntFieldsTest
- RecordingRng
- GoldenTest
- raw
- AllowlistTests
- MVP 0.1: a playable skirmish APK
- ReadTests
- PackVectorsTest
- MainActivity.kt
- Txt
- ContentTest.kt
- Second brain (project memory)
- ADR-0004: Android app with a Kotlin engine; Python is the reference oracle
- 4. Rendering
- Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)
- VCMI cross-check: file-format specs
- GreedyAI
- GeometryTest
- IllegalCommandNoRngTest
- DefVectorTests
- .derive
- Handoff (resume here)
- 3. Data import
- Conformance: data-pack loader (`vectors/datapack.json`)
- TXT tables (tab-separated)
- check_state
- army
- TickTest
- WaitActivationMoraleTest
- OfferPolicyTest
- CorruptPayloadTests
- MemoryCheck
- TestContractEdgeVectors
- VectorsTxtTest
- Content
- Loop graph builder
- ADR-0010: The project is licensed GPL-2.0-or-later
- 6. Screens and navigation
- Conformance: greedy battle AI (`battle_ai.json`)
- Grid
- CheckStateTest
- MalformedHexTest
- PackMismatchTest
- ModuleEntryPointTests
- SkillCheck
- VectorsPresentTest
- check_seed
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
1. `derive_stream()` - 57 edges
2. `BattleState` - 52 edges
3. `parse_h3m_bytes()` - 45 edges
4. `Rational` - 42 edges
5. `Battle` - 39 edges
6. `ScriptRng` - 38 edges
7. `Pcg32` - 37 edges
8. `HexCell` - 35 edges
9. `grid()` - 35 edges
10. `BattleCodec` - 34 edges

## Surprising Connections (you probably didn't know these)
- `Amendments (2026-11-01)` --references--> `Rational`  [INFERRED]
  docs/adr/ADR-0004-android-kotlin-core-python-oracle.md → android/sim/src/main/kotlin/h3/sim/Rational.kt
- `Next, in order` --references--> `check_state()`  [INFERRED]
  docs/checkpoints/HANDOFF.md → tools/h3re/h3re/battle.py
- `Error classes` --references--> `DataPackError`  [INFERRED]
  docs/specs/conformance-datapack.md → tools/h3re/h3re/datapack.py
- `Validation` --references--> `DataPackError`  [INFERRED]
  docs/specs/datapack.md → tools/h3re/h3re/datapack.py
- `Hashes` --references--> `load_rules_pack()`  [INFERRED]
  docs/specs/conformance-datapack.md → tools/h3re/h3re/datapack.py

## Import Cycles
- 2-file cycle: `tools/h3re/h3re/adventure.py -> tools/h3re/h3re/encounter.py -> tools/h3re/h3re/adventure.py`
- 2-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/__init__.py`
- 2-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`
- 3-file cycle: `tools/h3re/h3re/__init__.py -> tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/__init__.py`
- 3-file cycle: `tools/h3re/h3re/battle.py -> tools/h3re/h3re/rules.py -> tools/h3re/h3re/datapack.py -> tools/h3re/h3re/battle.py`

## Communities (211 total, 85 thin omitted)

### Community 0 - ".write"
Cohesion: 0.06
Nodes (18): c(), AiChooserTest, _board_at(), _cell_glyphs(), ChooserTest, CliTestCase, golden_scenario(), GoldenScenarioTest (+10 more)

### Community 1 - "replay.py"
Cohesion: 0.05
Nodes (44): ADR-0011: Android app architecture (modules, data import, rendering, threading, saves, build), Alternatives considered, Consequences, Context, Decision, Verification, Why, 7.2 Saves (autosave on every command, as `engine-design.md` 1.6 requires) (+36 more)

### Community 2 - "LodArchive"
Cohesion: 0.06
Nodes (28): inflateMember(), LodArchive, LodEntry, LodError, LodFormatError, LodKeyError, parsePcx(), PcxError (+20 more)

### Community 3 - "h3m.py"
Cohesion: 0.07
Nodes (45): _army(), _art(), _bits(), _body_abandoned_mine(), _body_artifact(), _body_event(), _body_garrison(), _body_generic() (+37 more)

### Community 4 - "battle_cli.py"
Cohesion: 0.07
Nodes (38): _ai(), pick(), _board_lines(), _check_keys(), _check_pretty_options(), CliError, _creature(), _dataclass_kwargs() (+30 more)

### Community 5 - "vectors.py"
Cohesion: 0.06
Nodes (43): Open items, _attack_defense_vectors(), _base_damage_vectors(), _canon_corpus(), _canon_vectors(), _chance_vectors(), check(), _clamp_attack() (+35 more)

### Community 6 - "town.py"
Cohesion: 0.06
Nodes (42): 1. Interface, 3. Building, 4. Weekly growth, 6. Policy fields (`TownPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch), Growth pools digest (second pin), Town simulation core (`sim.town`): buildings, build rules and weekly growth (+34 more)

### Community 7 - "__init__.py"
Cohesion: 0.10
Nodes (5): LodError, PcxImage, army(), BattleFromPackTest, play()

### Community 8 - ".decodeFrame"
Cohesion: 0.08
Nodes (23): Def, DefBlock, DefException, DefFile, DefFrame, Out, Reader, DefTest (+15 more)

### Community 9 - "test_encounter.py"
Cohesion: 0.09
Nodes (16): army(), BuildBattleTest, flat_grid(), fought(), golden_game(), GoldenTest, IllegalTest, OutcomeTest (+8 more)

### Community 10 - "datapack.py"
Cohesion: 0.10
Nodes (35): Pack directory and rules hash (determinism audit), Runtime loading (checkpoint 34), _check_creatures(), _check_policy(), _check_rules(), DataPackError, _frac(), _int() (+27 more)

### Community 11 - "Battle"
Cohesion: 0.10
Nodes (14): ApplyResult, Battle, Damaged, IllegalCommand, Kind, ATTACK, DEFEND, MOVE (+6 more)

### Community 12 - "hero.py"
Cohesion: 0.08
Nodes (28): _advance(), apply(), _canon_bytes(), canonical(), _check_draw_inputs(), content_hash(), create_hero(), _draw() (+20 more)

### Community 13 - "BattleState"
Cohesion: 0.12
Nodes (11): BattleAi, GreedyAi, BattleStack, BattleState, Present, Shared, Conformance: presenter view v2 (`h3.sim.Present`), States (+3 more)

### Community 14 - "HexCell"
Cohesion: 0.13
Nodes (7): Hex, HexCell, legalCommands(), HexEntry, cell(), cells(), HexTest

### Community 15 - "defimg.py"
Cohesion: 0.08
Nodes (21): Blocks, Frame, Header, HoMM3 .DEF sprite container (clean-room notes), Implementation status / caveats, Mismatches, ranked by severity, Block, _decode_frame() (+13 more)

### Community 16 - "raw"
Cohesion: 0.08
Nodes (16): 2. Content model (pack schema v1), 5. Economy and integration, _bld(), golden_run(), GoldenTest, growth_digest(), PackTest, raw() (+8 more)

### Community 17 - "with"
Cohesion: 0.07
Nodes (39): runs-on, steps, timeout-minutes, runs-on, steps, H3_DATA_DIR, jobs, android-app (+31 more)

### Community 18 - "Data pack (`h3re.datapack`)"
Cohesion: 0.06
Nodes (27): API, Battle policy pack, Data pack (`h3re.datapack`), Determinism and hash, Drift guard, Files, Integer range, Validation (+19 more)

### Community 19 - "run_cli"
Cohesion: 0.11
Nodes (11): def_bytes(), DefCommandTests, h3m_bytes(), H3mCommandTests, lod_bytes(), LodCommandTests, png_size(), run_cli() (+3 more)

### Community 20 - "test_town.py"
Cohesion: 0.10
Nodes (7): build(), build_days(), BuildTest, game(), GrowthTest, IncomeTest, NoRng

### Community 21 - "Datapack"
Cohesion: 0.14
Nodes (6): CreaturesDoc, Datapack, PolicyDoc, RulesDoc, DatapackTest, API (Kotlin)

### Community 22 - "vectors_battle.py"
Cohesion: 0.12
Nodes (25): encode_command(), _ability_creature(), build_ability_scenario(), build_tie_scenario(), cap_setup(), _case(), _driver(), _driver_step() (+17 more)

### Community 23 - "vectors_pack.py"
Cohesion: 0.12
Nodes (24): classify(), _collect_invalid(), data_dir(), _delete(), _derived_valid(), dumps(), walk(), _extra_invalid() (+16 more)

### Community 24 - "soak.py"
Cohesion: 0.11
Nodes (18): _AdventureDriver, build_adventure(), build_battle(), build_scenario(), Divergence, _driver(), _events_digest(), _first_diff() (+10 more)

### Community 25 - "encounter.py"
Cohesion: 0.09
Nodes (20): 3. The battle, Hero, ArmyChanged, auto_command(), battle_id(), BattleFought, build_battle(), check_game() (+12 more)

### Community 26 - "adventure.py"
Cohesion: 0.08
Nodes (23): adventure_rng(), apply(), Attack, base_movement(), Begin, calendar(), _check_army(), create_game() (+15 more)

### Community 27 - "parse_txt"
Cohesion: 0.11
Nodes (7): parse_txt(), read_txt(), _scan(), TxtError, TxtTable, build(), TxtTests

### Community 28 - "parse_h3m_bytes"
Cohesion: 0.14
Nodes (7): parse_h3m(), parse_h3m_bytes(), Tile, build(), extra(), H3mTests, tiles_for()

### Community 29 - "test_h3m.py"
Cohesion: 0.21
Nodes (21): box(), e_army(), e_box(), e_event_common(), e_hero(), e_monster(), e_msg_guards(), e_opt8() (+13 more)

### Community 30 - "Battle scenario file (JSON)"
Cohesion: 0.06
Nodes (25): Commands, heroes-mobile: project constitution, Laws, Roles and delegation, Working principles, Checkpoint log, Reverse-engineering loop graph, 1. Document (+17 more)

### Community 31 - "H3mObjectTests"
Cohesion: 0.16
Nodes (6): ObjectTemplate, e_objects(), e_template(), H3mObjectTests, map_with(), tmpl()

### Community 32 - "struct"
Cohesion: 0.18
Nodes (21): _bad_cases(), single(), build_def(), case(), encode_body(), _format_cases(), one(), frame_blob() (+13 more)

### Community 33 - "build_lod"
Cohesion: 0.17
Nodes (5): build_lod(), ExtractTests, MalformedInputTests, member(), open_bytes()

### Community 34 - "BattleTest"
Cohesion: 0.16
Nodes (4): BattleTest, DrawSource, DrawSource, Outcome

### Community 35 - "content.py"
Cohesion: 0.17
Nodes (13): Tests, ContentError, ContentResult, _int(), _layout(), load_creatures(), load_mapping(), _norm() (+5 more)

### Community 36 - "Pcg32"
Cohesion: 0.13
Nodes (3): Pcg32, _TracedPcg32, TestPcg32

### Community 37 - "cr"
Cohesion: 0.15
Nodes (6): CombatTest, cr(), MovementTest, SetupTest, ss(), synthetic_states()

### Community 39 - "Rational"
Cohesion: 0.13
Nodes (3): Rational, RulesPack, longs()

### Community 40 - "grid"
Cohesion: 0.14
Nodes (5): game(), grid(), PolicyTest, StepCostTest, costs()

### Community 41 - "BattleCodec"
Cohesion: 0.14
Nodes (11): BattleCodec, BattleCreature, BattleHero, BattlePolicy, BattlePolicyPack, policyDefendBonus(), Battle state (`battle_states.json`), Conformance vectors (Python -> Kotlin) (+3 more)

### Community 42 - "parse_pcx"
Cohesion: 0.15
Nodes (7): parse_pcx(), PcxError, _pcx_expect(), bgr_2x2(), indexed_2x2(), PcxErrorTests, PcxParseTests

### Community 43 - "ScriptRng"
Cohesion: 0.18
Nodes (6): begin(), four(), LastMoverOrderTest, MoraleTest, QueueTest, ScriptRng

### Community 44 - "BattleCommand"
Cohesion: 0.21
Nodes (8): Attack, BattleCommand, BattleJson, Begin, Defend, Move, Shoot, Wait

### Community 45 - "bisect_tool.py"
Cohesion: 0.13
Nodes (16): bisect(), diff_states(), dump_log(), flatten(), format_policy(), format_report(), load_log(), load_log_ex() (+8 more)

### Community 46 - "rules"
Cohesion: 0.18
Nodes (3): GraphCriteria, rules(), RunCriteria

### Community 47 - "_Visitor"
Cohesion: 0.16
Nodes (3): _is_set_expr(), Violation, _Visitor

### Community 48 - "derive_stream"
Cohesion: 0.11
Nodes (9): hero_rng(), derive_stream(), _enc(), RngStreams, _canon_bytes(), canonical(), content_hash(), state_hash() (+1 more)

### Community 49 - "PolicyPackTest"
Cohesion: 0.11
Nodes (7): ADR-0008: Kotlin pack values are 32-bit Int capped at 2**31-1; hashes and XP accumulation use Long, LoadTest, PolicyPackTest, bad(), raw(), raw_policy(), ValidationTest

### Community 50 - "Rules specification"
Cohesion: 0.08
Nodes (23): 0. Provenance and tagging, 1. Calendar and turn structure, 2.1 Movement points (land), 2.2 Terrain cost, 2. Adventure map: movement, 3. Resource economy, 4. Towns, 5.1 Primary skills (+15 more)

### Community 51 - "vectors_ai.py"
Cohesion: 0.14
Nodes (16): choose(), _decide(), pick(), _enemy_dist(), _pick(), _preview(), _score_attack(), _stack_hp() (+8 more)

### Community 52 - "parse_def"
Cohesion: 0.24
Nodes (6): parse_def(), to_rgb(), build_def(), build_shared(), DefTests, frame_bytes()

### Community 53 - "loadVector"
Cohesion: 0.19
Nodes (5): Canonical, ConformanceTest, loadVector(), object@L90, ADR-0009: The Kotlin engine uses a small exact Rational type with one named rounding step, not an integer rewrite

### Community 54 - "re"
Cohesion: 0.17
Nodes (15): _back_edges(), visit(), eval_graph(), eval_run(), _load_run(), main(), parse_loop(), check_loop() (+7 more)

### Community 55 - "test_battle.py"
Cohesion: 0.17
Nodes (8): golden_setup(), GoldenTest, play(), PreviewLawTest, PropertyTest, scripted_choice(), total_hp(), golden_states()

### Community 56 - "kotlin_banned_api_lint.py"
Cohesion: 0.13
Nodes (11): apply_allowlist(), default_paths(), _entry_matches(), lint_paths(), lint_source(), load_allowlist(), main(), _scan() (+3 more)

### Community 57 - "argparse"
Cohesion: 0.15
Nodes (13): _canon(), _entries(), generate(), main(), _sha(), _taps(), apply_allowlist(), _entry_matches() (+5 more)

### Community 59 - "LodFormatError"
Cohesion: 0.13
Nodes (8): Discrepancies flagged (CLAUDE.md law 10), _check_member_name(), _decode_name(), _inflate(), _key(), LodEntry, LodFormatError, _oracle()

### Community 60 - "resolve_damage"
Cohesion: 0.19
Nodes (7): DamageCtx, DamagePreview, DamageResult, preview_damage(), resolve_damage(), random_ctx(), ResolveDamageLawTest

### Community 61 - "_run_isolated"
Cohesion: 0.14
Nodes (6): _probe(), _repo_data_dir(), _run_isolated(), TestBattleExports, TestImportSideEffects, TestRulesPackIdentity

### Community 62 - "__main__.py"
Cohesion: 0.17
Nodes (13): build_parser(), cmd_battle_sim(), cmd_h3m_info(), cmd_lod_extract(), cmd_lod_list(), cmd_replay(), _condition(), _describe_error() (+5 more)

### Community 63 - "Encounters: adventure-map battles (`sim.adventure` + `sim.battle`)"
Cohesion: 0.11
Nodes (14): ADR-0005: The omit-at-default canonical mechanism applies to every state module, not only battle, 1. Interface, 5. Policy fields (`EncounterPolicy`), 6. Canonical form and hashes, 7. Golden encounter hash, 8. Tests, 9. Open items, Encounters: adventure-map battles (`sim.adventure` + `sim.battle`) (+6 more)

### Community 64 - "create_battle"
Cohesion: 0.16
Nodes (16): 2. Grid, Hex: battle grid geometry and movement (`hex.json`), BattleState, _cells_at(), create_battle(), _fits(), from_axial(), hex_distance() (+8 more)

### Community 65 - "test_adventure.py"
Cohesion: 0.16
Nodes (7): FloatSub, golden_setup(), GoldenTest, IntSub, play_days(), PropertyTest, scripted_turn()

### Community 66 - "SoakTest"
Cohesion: 0.13
Nodes (6): main(), policy_matrix(), soak(), soak_digest(), _playouts(), SoakTest

### Community 67 - ".resolveDamage"
Cohesion: 0.16
Nodes (11): asDrawSource(), DrawSource, DamageCtx, DamagePreview, DamageResult, DrawSource, RollPolicy, ACTUAL_SEED (+3 more)

### Community 68 - "TestBattleVectors"
Cohesion: 0.14
Nodes (3): decode_command(), stream_at(), TestBattleVectors

### Community 69 - "RulesTest.kt"
Cohesion: 0.28
Nodes (6): ctxOf(), isError(), loadPack(), long(), rat(), RulesTest

### Community 70 - "rules.py"
Cohesion: 0.13
Nodes (8): attack_defense_factor(), check_bad_morale_table(), _check_flags(), RollPolicy, _scaled(), _settle(), _skill(), AttackDefenseTest

### Community 71 - "vectors_txt.py"
Cohesion: 0.20
Nodes (14): _base(), _content_case(), _content_cases(), _content_error(), _creature_row(), generate(), _header(), _Lcg (+6 more)

### Community 72 - "PresentTest"
Cohesion: 0.16
Nodes (4): all_states(), FailRng, PresentTest, walk()

### Community 73 - "Adventure-map simulation core (`sim.adventure`): movement and economy"
Cohesion: 0.14
Nodes (15): 1. Interface, 2. Grid and step costs, 3. Movement points, 4. Pathfinding, 5. Calendar, income and growth, 7. Tests, 8. Encounters (battles on the map), Adventure-map simulation core (`sim.adventure`): movement and economy (+7 more)

### Community 74 - "_validate"
Cohesion: 0.15
Nodes (12): 1. Interface, _adjacent_cells(), _as_hex(), cells(), _enemy_adjacent(), IllegalCommand, _occupancy(), PackMismatch (+4 more)

### Community 75 - "damage_from_base"
Cohesion: 0.18
Nodes (5): 6.6 Damage formula, damage_from_base(), damage_range(), DamageFromBaseTest, DamageRangeTest

### Community 76 - "present.py"
Cohesion: 0.20
Nodes (12): _actions(), slot(), target_slot(), command_to_dict(), _grid(), _hx(), _preview(), _queue() (+4 more)

### Community 78 - ".parseCreatures"
Cohesion: 0.23
Nodes (9): ContentError, ContentResult, Creature, CreatureMapping, CreatureValidator, DefaultCreatureValidator, MapColumn, UnknownAbility (+1 more)

### Community 79 - "vectors_lodpcx.py"
Cohesion: 0.18
Nodes (10): Vectors, _entry_pos(), generate(), _lod(), _lod_cases(), add(), _member(), _patch_u32() (+2 more)

### Community 80 - "_activate_next"
Cohesion: 0.17
Nodes (15): _activate_next(), apply(), BattleStarted, _chance(), Defended, effective_morale(), _finish_turn(), _melee() (+7 more)

### Community 81 - "hero"
Cohesion: 0.21
Nodes (5): gain(), hero(), LevelUpTest, resolve(), XpTest

### Community 82 - ".test_every_mutation_changes_the_hash"
Cohesion: 0.17
Nodes (5): StoredContentHashTest, high(), low(), sec(), start()

### Community 84 - "base_damage"
Cohesion: 0.17
Nodes (7): Algorithm, API, Deterministic RNG (`sim.rng`), Named streams, base_damage(), BaseDamageTest, FixedRng

### Community 85 - "BattleAiTest"
Cohesion: 0.20
Nodes (3): BattleAiTest, play(), scenario()

### Community 88 - "Pcg32"
Cohesion: 0.23
Nodes (3): Pcg32, Edge, RngEdgeTest

### Community 90 - "battle.py"
Cohesion: 0.21
Nodes (11): Attack, BattleEnded, Begin, _check_end(), Defend, legal_commands(), _living(), Move (+3 more)

### Community 91 - "_search"
Cohesion: 0.14
Nodes (8): ADR-0002: Integer-only simulation (int and Fraction, one explicit rounding step), _diagonal(), _div(), _orth_cost(), _paid(), _search(), step_cost(), _step_parts()

### Community 92 - "Rules: battle damage (`rules.json`)"
Cohesion: 0.25
Nodes (8): 5. Morale and luck, Rules: battle damage (`rules.json`), 8. Reference implementation, bad_morale_chance(), _clamp3(), good_morale_chance(), luck_chance(), LuckMoraleTest

### Community 93 - "Hero simulation core (`sim.hero`): experience, levels and skill gain"
Cohesion: 0.14
Nodes (12): 1. Interface, 2. Content model (pack schema v1), 3. Experience and levels, 4. Level-up, 5. Secondary skills, 6. Policy fields (`HeroPolicy`), 7. Golden hash, 8. Unverified assumptions (no switch) (+4 more)

### Community 94 - ".parseEvent"
Cohesion: 0.27
Nodes (13): BattleEnded, BattleEvent, BattleStarted, DamageDealt, Defended, LuckRolled, MoraleBoost, MoraleFrozen (+5 more)

### Community 95 - "AdventurePolicy"
Cohesion: 0.16
Nodes (10): ADR-0001: Canonical JSON form and SHA-256 state hash for battle and adventure state, 6. Policy fields (`AdventurePolicy`), Default changes and the golden hash, 1. Soak (`tools/h3re/h3re/soak.py`), 2. Bisector (`tools/h3re/h3re/bisect_tool.py`), 3. Banned-API lint (`tools/lint/banned_api_lint.py`), CI, Determinism gate (+2 more)

### Community 96 - "Objects, object instances and events (`objects=True`)"
Cohesion: 0.16
Nodes (9): End of data, Global events, Object instances, Objects, object instances and events (`objects=True`), Template table, Unverified assumptions (objects section), H3mUnsupportedObject, MapObject (+1 more)

### Community 97 - "write_png"
Cohesion: 0.15
Nodes (7): Errors, Header (12 bytes), HoMM3 PCX bitmap variant (clean-room notes), Mode selection, Open items, Output model, write_png()

### Community 98 - "candidate_actions"
Cohesion: 0.18
Nodes (9): 1. Spec grounding and gaps, 5.1 Preview and confirm (pure reducer in `:presenter`), 5.2 Hit-testing (`:app`, `h3.app.board.BoardGeometry`), 5.3 Accessibility, 5.4 Layout, 5. Touch interaction, candidate_actions(), candidate_commands() (+1 more)

### Community 99 - "Txt.kt"
Cohesion: 0.17
Nodes (7): TxtError, TxtErrorCategory, DECODE, HEADER_ROWS, TOO_LARGE, TOO_MANY_LINES, UNKNOWN_ENCODING

### Community 100 - ".parse"
Cohesion: 0.28
Nodes (3): TxtTable, hexBytes(), TxtTest

### Community 102 - "Android app design (`android/`)"
Cohesion: 0.15
Nodes (12): 0. Problem statement, 10. Determinism and purity impact, 11. Risks, 12. Assumptions (proposed defaults; the owner may overturn any), 13. Out of scope, 14. Open questions for the owner, 2. Module layout and dependency rules, 7.1 Threads (+4 more)

### Community 104 - "Datapack.kt"
Cohesion: 0.36
Nodes (10): bad(), Category, DatapackError, floatErr(), lit(), num(), parse(), pyRepr() (+2 more)

### Community 106 - "MiniJson.kt"
Cohesion: 0.26
Nodes (3): MiniJson, obj(), u64()

### Community 108 - "Battle simulation core (`sim.battle`)"
Cohesion: 0.17
Nodes (11): 10. Change notes, 2026-11-01: golden hash re-pinned a second time (rules pack in the hash), 2026-11-01: golden hash re-pinned (one reviewed change), 2026-11-01: state invariants and integer caps (no re-pin), 3. Movement [documented], 4. Turn queue, 6. Damage and attacks, 7. Battle end (+3 more)

### Community 111 - "test_vectors_ai.py"
Cohesion: 0.27
Nodes (5): doc(), _floats(), VectorsAiTest, state_from_json(), _t()

### Community 112 - "Loop: one agent round (advise, fan out, verify, checkpoint)"
Cohesion: 0.18
Nodes (10): Actions, Budget, Evidence, Goal and input, Loop: one agent round (advise, fan out, verify, checkpoint), Notes learned the hard way, Observation, State (+2 more)

### Community 114 - "HoMM3 .H3M map header (clean-room notes)"
Cohesion: 0.18
Nodes (8): After teams (parsed; then terrain tiles), Conditions and teams, Header, HoMM3 .H3M map header (clean-room notes), Not implemented, Players (8 slots), Verification status, levels()

### Community 115 - "LOD archive format"
Cohesion: 0.18
Nodes (10): Directory entry (32-byte stride), Errors, Extraction safety, File layout, Header (92 bytes), LOD archive format, Name rules, Open items (+2 more)

### Community 117 - "RealLodTests"
Cohesion: 0.24
Nodes (4): _files(), RealLodTests, RealMapTests, _rel()

### Community 118 - "ContentErrorCategory"
Cohesion: 0.20
Nodes (10): ContentErrorCategory, DUPLICATE, EMPTY_CELL, HEADER, MAPPING, MISSING_CELL, NO_ROWS, NOT_INTEGER (+2 more)

### Community 120 - "IllegalCommand"
Cohesion: 0.22
Nodes (6): 2026-11-01: malformed hex raises IllegalCommand (no re-pin), 2. Validation, _as_tile(), IllegalCommand, reachable(), _validate()

### Community 121 - "_strike"
Cohesion: 0.22
Nodes (8): 1. Mismatches (ranked by gameplay impact), Notes on VCMI-only behaviour we should **not** copy, DamageDealt, defend_bonus(), LuckRolled, _strike(), strike_context(), UnitDied

### Community 122 - "started"
Cohesion: 0.24
Nodes (3): MalformedDestTest, RoadCostCanonicalTest, started()

### Community 125 - "round_order"
Cohesion: 0.25
Nodes (6): 9. Tests, 1. Contract, 3. Tap semantics, Battle presenter (`h3re.present`), round_order(), strike_preview()

### Community 126 - "turn_order"
Cohesion: 0.22
Nodes (6): 2. Confirmed (VCMI agrees with our default or our documented value), 3. Items VCMI does not settle, VCMI cross-check of `rules.md` / `battle.md` uncertain items, _last_mover_sorted(), _speed_sorted(), turn_order()

### Community 131 - "raw"
Cohesion: 0.36
Nodes (3): PackTest, raw(), with_class()

### Community 133 - "MVP 0.1: a playable skirmish APK"
Cohesion: 0.25
Nodes (7): Decisions needed from the owner, Goal (one sentence, with its test), MVP 0.1: a playable skirmish APK, Remaining work for 0.1, in order, Risks specific to 0.1, What 0.1 is, and is not, What exists today (checkpoints up to 59, plus agents in flight)

### Community 137 - "Txt"
Cohesion: 0.33
Nodes (3): Txt, Conformance: TXT reader and creature content loader (Kotlin port), Vectors

### Community 139 - "Second brain (project memory)"
Cohesion: 0.29
Nodes (6): Note format, Operations, Principles, Relationship to other records, Second brain (project memory), What never goes in

### Community 140 - "ADR-0004: Android app with a Kotlin engine; Python is the reference oracle"
Cohesion: 0.29
Nodes (7): ADR-0004: Android app with a Kotlin engine; Python is the reference oracle, Amendments (2026-11-01), Consequences, Context, Decision, Risks, Why

### Community 141 - "4. Rendering"
Cohesion: 0.29
Nodes (7): 4.1 Spaces and transform, 4.2 Layers (drawn in this order each frame), 4.3 Sprites and atlas, 4.4 Animation timeline (UI only; closes G2), 4.5 Frame budget (60 fps), 4.6 Placeholder renderer, 4. Rendering

### Community 142 - "Content loader (`h3re.content`), engine roadmap Phase 4 (creatures)"
Cohesion: 0.29
Nodes (6): Abilities, API, Column order (data: `data/txt_maps/crtraits.json`, unverified), Content loader (`h3re.content`), engine roadmap Phase 4 (creatures), Errors, Reading

### Community 143 - "VCMI cross-check: file-format specs"
Cohesion: 0.29
Nodes (6): DEF (`docs/specs/def.md`, `tools/h3re/h3re/defimg.py`), H3M (`docs/specs/h3m.md`, `tools/h3re/h3re/h3m.py`), LOD (`docs/specs/lod.md`, `tools/h3re/h3re/lod.py`), PCX (`docs/specs/pcx.md`, `tools/h3re/h3re/pcx.py`), TXT (`docs/specs/txt.md`, `tools/h3re/h3re/txt.py`), VCMI cross-check: file-format specs

### Community 149 - "Handoff (resume here)"
Cohesion: 0.33
Nodes (6): CI facts (seen on GitHub, run for checkpoint 63), Handoff (resume here), Loop tooling (done, commit 4dcc384), Needs the owner, Next, in order, What exists

### Community 150 - "3. Data import"
Cohesion: 0.33
Nodes (6): 3.1 Principles, 3.2 Flow, 3.3 Editions, 3.4 Files, 3.5 Validation (first run and every import), 3. Data import

### Community 151 - "Conformance: data-pack loader (`vectors/datapack.json`)"
Cohesion: 0.33
Nodes (5): Conformance: data-pack loader (`vectors/datapack.json`), Error classes, File layout, Hashes, Known limits

### Community 152 - "TXT tables (tab-separated)"
Cohesion: 0.33
Nodes (5): API, Format, Limits, Options (backward compatibility), TXT tables (tab-separated)

### Community 153 - "check_state"
Cohesion: 0.33
Nodes (3): _bounded(), check_state(), _opt_side()

### Community 163 - "Loop graph builder"
Cohesion: 0.40
Nodes (4): Contract template, Loop graph builder, Principles (Karpathy-style, applied), Procedure

### Community 164 - "ADR-0010: The project is licensed GPL-2.0-or-later"
Cohesion: 0.40
Nodes (4): ADR-0010: The project is licensed GPL-2.0-or-later, Consequences, Context, Decision

### Community 165 - "6. Screens and navigation"
Cohesion: 0.40
Nodes (5): 6.1 MVP routes, 6.2 Skirmish setup, 6.3 Behaviour without data, 6.4 Phase after the MVP (outline only), 6. Screens and navigation

### Community 166 - "Conformance: greedy battle AI (`battle_ai.json`)"
Cohesion: 0.40
Nodes (4): Conformance: greedy battle AI (`battle_ai.json`), File layout, Kotlin contract, What is pinned

## Knowledge Gaps
- **26 isolated node(s):** `WAIT`, `DEFEND`, `MOVE`, `SHOOT`, `ATTACK` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 980 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **85 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `derive_stream()` connect `derive_stream` to `GoldenTest`, `vectors.py`, `town.py`, `__init__.py`, `test_encounter.py`, `ADR-0004: Android app with a Kotlin engine; Python is the reference oracle`, `BattleState`, `hero.py`, `GreedyAI`, `raw`, `test_town.py`, `vectors_battle.py`, `soak.py`, `adventure.py`, `Battle scenario file (JSON)`, `Pcg32`, `Conformance: greedy battle AI (`battle_ai.json`)`, `BattleCodec`, `vectors_ai.py`, `test_battle.py`, `test_adventure.py`, `TestBattleVectors`, `battle.py`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `derive_stream()` (e.g. with `sim-engineer.md` and `Laws`) actually correct?**
  _`derive_stream()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `WAIT`, `DEFEND`, `MOVE` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `.write` be split into smaller, more focused modules?**
  _Cohesion score 0.057711950970377936 - nodes in this community are weakly interconnected._
- **Why does `Battle state (`battle_states.json`)` connect `BattleCodec` to `create_battle`, `BattleStateTest`, `.decodeFrame`, `BattleCommand`, `BattleState`, `derive_stream`, `loadVector`, `vectors_battle.py`, `BattleAiTest`, `.parseEvent`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Should `replay.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05126582278481013 - nodes in this community are weakly interconnected._
- **Why does `generate()` connect `vectors.py` to `Conformance: greedy battle AI (`battle_ai.json`)`, `.decodeFrame`, `Txt`, `BattleState`, `vectors_lodpcx.py`, `Conformance: data-pack loader (`vectors/datapack.json`)`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._