# Hero simulation core (`sim.hero`): experience, levels and skill gain

Status: draft v1, roadmap phase 8 (partial). Reference implementation:
`tools/h3re/h3re/hero.py`. Tests: `tools/h3re/tests/test_hero.py`. Test pack:
`data/hero_test.json` (the experience table from `rules.md` §5.2 plus
synthetic classes and secondary skills with made-up names; not game data).

Scope: the experience table, level-up, the primary-skill draw from class
weights, and the secondary-skill offer and choice. Out of scope: spell points
and Mysticism (`rules.md` §5.4; `mysticism_mode` belongs here once they
land), battle XP awards, specialties, artifacts, spells, skill effects, and
guaranteed-skill intervals. Source rules: `rules.md` §5. Tags as in
`rules.md`.

## 1. Interface

Same pattern as `battle.md` §1. [engine]

- `load_hero_pack(path)` / `parse_hero_pack(obj)` return
  `HeroContent(rules, classes)`; `content_hash(content)` as in `town.md`.
  Loader helpers come from `datapack.py` (floats, duplicate and unknown keys
  rejected). Importing `h3re.hero` opens nothing.
- `create_hero(hero_id, class_id, content, secondary=(), policy=DEFAULT_POLICY)`:
  level 1, 0 XP, the class's starting primary skills, and the given starting
  `(skill, level)` pairs (known, distinct, level 1..`skill_levels`, at most
  `max_secondary`).
- `apply(state, cmd, rng) -> (state', events)`. Commands:
  `GainXP(hero, amount)` (positive int) and `ChooseSkill(hero, index)`.
- **RNG**: one state holds one hero. `rng` is that hero's stream
  `hero:<hero_id>` (`hero_rng(master_seed, hero_id)`), so a stream is never
  shared between heroes or with another feature. Illegal commands raise
  `IllegalCommand` before any draw and leave the state unchanged (tested
  with an RNG that fails if touched).
- Events: `XPGained(hero, amount, xp)`, `LevelGained(hero, level)`,
  `PrimaryGained(hero, skill, value)`, `SkillOffered(hero, level, offers)`,
  `SkillLearned(hero, skill, level)`.
- State: `HeroState(policy, rules, class_def, hero)`; frozen dataclasses of
  tuples, ints, strings and bools; `canonical` / `state_hash` per ADR-0001.
  The policy, the pack's rules and the hero's class are in the state, so they
  are in the hash. No `rules.json` value is read, so no `rules_hash`.

## 2. Content model (pack schema v1)

| Key | Meaning |
|---|---|
| `xp_table` | total XP for levels 1, 2, ...; starts at 0, strictly increasing |
| `max_secondary` | secondary skill slots (8, `rules.md` §5.3 [documented]) |
| `skill_levels` | Basic..Expert (3 [documented]) |
| `primary_high_from_level` | first level that uses the high table (10: "levels 2–9 and 10+" [documented]) |
| `skills` | secondary skill ids (stored sorted) |
| `classes[]` | `id`, `start_primary` (4), `primary_low` (4 weights), `primary_high` (4 weights), `secondary` (object: a weight for every skill, 0 allowed) |

Primary weights are in the order attack, defense, power, knowledge
(`PRIMARY`) and must have a positive total. Weights are relative, not
percentages. Classes are stored sorted by id.

## 3. Experience and levels

- `level_for_xp(xp, table)` = number of table entries ≤ xp. The test pack
  holds the [documented] table for levels 1–12: 0, 1000, 2000, 3200, 4600,
  6200, 8000, 10000, 12200, 14700, 17500, 20600.
- **Gap: levels 13+ are not implemented.** `rules.md` §5.2 tags them
  [uncertain] and §9.9 is open, so nothing beyond level 12 was invented. A
  hero above 20600 XP keeps accruing XP and stays at level 12 (tested). VCMI
  evidence (`vcmi-crosscheck-rules.md` §2, "XP beyond level 12", clear:
  24 320, 28 784, 34 140, then +1/5 per step, floored) is recorded there and
  is not used. Extending the data table is all a later change needs.
- XP gain is a command amount; how much a battle awards is out of scope.

## 4. Level-up

For each level the XP allows, one at a time [engine]:

1. `level += 1`.
2. Primary skill: one weighted draw from `primary_low` if the new level is
   below `primary_high_from_level`, else `primary_high`; that skill +1.
   [documented mechanism; weights are data]
3. Secondary offers (section 5). If there is at least one offer, the hero
   stores it in `offer` and stops; `ChooseSkill` applies the choice and
   continues with the next level. With nothing to offer, the next level
   follows at once.

`GainXP` is illegal while an offer is pending [engine]: a multi-level gain
resolves level by level, so each level's offers see the previous choice
(tested: 4600 XP from level 1 stops at levels 2, 3, 4, 5).

**Draw order** within one level [engine]: primary draw, then offer draws
(the upgrade before the new skill). Weighted draw: one
`rng.range(0, total)`, walked over the weights in their fixed order; a draw
is made even when only one candidate exists. Changing this order changes
replays (`rng.md`).

## 5. Secondary skills

- Candidates, in skill-id order: **upgrades** are held skills below Expert,
  offered at level + 1; **new** skills are unheld skills, only while a slot
  is free, offered at Basic. A skill whose class weight is 0 is never a
  candidate (tested), even for an upgrade.
- At most 8 skills, each Basic/Advanced/Expert [documented]; the cap, level
  range and distinctness are property-tested.
- Choosing: a new skill is appended (skills stay in the order learned); an
  upgrade raises the held skill in place.
- The offer algorithm is [uncertain] (`rules.md` §5.3), so it is the policy
  below. Guaranteed Wisdom / magic-school intervals are not modelled.

## 6. Policy fields (`HeroPolicy`)

| Field | Default | Alternatives | Question |
|---|---|---|---|
| `offer_mode` | `"upgrade_and_new"` | `"weighted_pair"` | How the two offers are built: one upgrade then one new skill, each by class weight; or two distinct weighted draws from upgrades and new skills together |
| `offer_fill` | `"other_kind"` | `"single"` | `upgrade_and_new` only: when one kind has no candidate, offer two of the other kind or just one |

Defaults are [engine] choices that follow the `rules.md` §5.3 wording ("an
upgrade to an existing skill and/or a new skill"). No VCMI cross-check row
covers the offer algorithm; the defaults are unverified.

## 7. Golden hash

`tests/test_hero.py` `GoldenTest.PINNED =
f18f5ebb1e249b9b4f35d707add6b89a01b19310554a723d3b048a19583022f9`
(first pin; not a re-pin). Derivation:

1. Content: `data/hero_test.json` (content hash prefix `2720746c773ed8ad`,
   pinned separately).
2. `create_hero("h1", "class.warden", content, (("skill.anvil", 1),), DEFAULT_POLICY)`;
   stream `hero_rng(2026, "h1")` (domain `hero:h1`).
3. `GainXP` of 1500, 5000, 999, 16000 and 3000 in turn (26 499 XP in total,
   level 12). After each, every pending offer is answered with
   `ChooseSkill(index = hero.level % len(offer))`.
4. `state_hash` of the final state. The test also asserts primary skills
   7/5/4/1, the six secondary skills and their levels, and 49 events.

The hash is the same under `PYTHONHASHSEED` 0, 1, 12345 and random (checked
when pinning). A different seed changes the trace and `offer_mode` changes
the hash (tested). A later change follows the ADR-0001 re-pin rule with its
reason recorded here.

## 8. Unverified assumptions (no switch)

- Level-ups resolve one at a time; XP cannot be added while an offer waits.
- A zero-weight skill is never offered, not even as an upgrade of a skill the
  hero already has.
- The primary draw happens before the offers; offers are drawn upgrade first.
- No caps on primary skills.
- XP beyond the last table entry gives no level (gap, section 3).
