# Rules specification

Status: draft v1. Scope: the rules of a HoMM3-like game (SoD-era ruleset)
that the heroes-mobile engine will implement.

## 0. Provenance and tagging

This spec was written clean-room. It draws only on mechanics that a player can
observe in the game and on long-standing public community documentation
(manual-level and wiki-level knowledge). It was not produced by disassembling
anything. Every formula and rule carries one of these tags:

- **[documented]** — widely and consistently documented, and also observable.
  These can go into the reference implementation
  (`tools/h3re/h3re/rules.py`) and the engine.
- **[uncertain]** — the documentation conflicts or is vague, or the detail
  (rounding, ordering, tie-breaking, edge cases) needs checking against the
  original by an observational experiment. The engine must implement these
  behind a named, configurable rule switch until §9 resolves them.
- **[engine]** — our own choice where the original's behaviour is
  unobservable or irrelevant, for example RNG draw order or the obstacle
  placement algorithm.

**VCMI cross-check annotations.** `docs/specs/vcmi-crosscheck-rules.md`
compares this spec with the VCMI engine. Where it applies, a rule carries an
extra note such as **VCMI #3: clear**, giving the cross-check row number and
its confidence (**clear**, **ambiguous**, **VCMI-differs**; defined in that
file). VCMI is a reimplementation: its behaviour is evidence of what the
original does, not proof, and it does not change a rule's tag by itself.
Code follows two rules:

- A "clear" note on an [uncertain] item may be adopted as the engine's
  policy default, recorded in that module's spec.
- If the note contradicts a [documented] value, or is "ambiguous", the
  documented value stays the default. The VCMI value becomes a switchable
  policy option, and a §9 item is added to settle it by experiment.

All numeric *content* comes from the user's data files and is **not** part
of this spec. That includes creature attack/defense/damage/HP/speed/shots,
growth, costs, spell power tables and class probabilities. The spec defines
only how those numbers combine.

---

## 1. Calendar and turn structure

| Rule | Tag |
|------|-----|
| A game day is one round in which each player in turn order takes a full turn on the adventure map. | [documented] |
| 7 days make a week and 4 weeks make a month. Weekly events (creature growth, "week of X" announcements) fire at the start of day 1 of each week except the very first. | [documented] |
| Hero movement points reset to full at the start of the owner's turn each day. Unused points do not carry over. | [documented] |
| Each town may construct at most one building per day. | [documented] |
| Random "week of <creature>" / "month of plague" effects: probabilities and magnitudes. | [uncertain] |

## 2. Adventure map: movement

### 2.1 Movement points (land)

A hero's base daily land movement depends on the **lowest speed among the
creatures in the hero's army** [documented, SoD values]:

| Slowest speed | ≤3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | ≥11 |
|---|---|---|---|---|---|---|---|---|---|
| Movement points | 1500 | 1560 | 1630 | 1700 | 1760 | 1830 | 1900 | 1960 | 2000 |

- Logistics secondary skill: +10% / +20% / +30% (basic/advanced/expert).
  [documented]
- How the percentage bonuses round, and in what order artifact and stable
  bonuses (e.g. "+N movement" items, Stables, Boots of Speed) are applied.
  [uncertain]
- Whether speed bonuses from artifacts change the "slowest speed" lookup.
  [uncertain]
- Sea movement uses a separate base (boats) and the Navigation skill.
  [uncertain: exact base values]

### 2.2 Terrain cost

Cost of one orthogonal step, with no Pathfinding. The terrain values are
[documented] (**VCMI, §2 row "Terrain base costs": clear**, it agrees):

| Terrain | Cost |
|---|---|
| Road (see the road rows) | 75 / 65 / 50 |
| Dirt, Grass, Lava, Subterranean | 100 |
| Rough | 125 |
| Sand, Snow | 150 |
| Swamp | 175 |

Road costs by type [uncertain; previously "any road = 50", documented for
dirt roads only] (**VCMI #3: clear**, from its road config; §9.14):

| Road | Cost |
|---|---|
| Dirt road | 75 |
| Gravel road | 65 |
| Cobblestone road | 50 |

VCMI's dirt road costs 75. That contradicts the earlier [documented] line
"any road = 50 (dirt road)". Under the §0 rule, a movement module takes the
road costs as a policy table with two options: `(75, 65, 50)` from VCMI
(clear) and a flat 50 from the earlier documentation. The module's owner
picks the default and records it, and §9.14 settles the question.

- **Which tile pays.** [uncertain; previously "cost to enter a tile"]
  (**VCMI #2: clear**; §9.14). A step is priced by its **source** tile (the
  tile being left), not the destination. The road rate applies only if
  **both** the source and the destination tile have a road. The rate is
  then that of the source tile's road. Otherwise the source tile's terrain
  cost applies. The step-cost function must take `(src, dst)`. This
  contradicts the earlier [documented] "cost to enter a tile", so a movement
  module makes it a policy: `step_cost_tile = "source" | "destination"`,
  and a road rule of "needs both tiles" or "destination only". The module's
  owner picks the default (VCMI evidence: clear) and §9.14 settles it.
- **Diagonal steps** cost `floor(cost × √2)`, the orthogonal cost of the
  same step multiplied by √2 and rounded down [uncertain → **VCMI (row
  "Adventure diagonal cost"): clear**; §9.7]: 100 → 141, 125 → 176,
  150 → 212, 175 → 247; roads 75 → 106, 65 → 91, 50 → 70. No floats: compute
  it as `isqrt(2 × cost²)`, which is `floor(cost·√2)` exactly for integers.
  VCMI also allows a diagonal step that costs more than the points left if
  those points cover the orthogonal cost of the step; the step then uses up
  all the points (row "Diagonal exception", clear).
- **Pathfinding** [uncertain; replaces "25/50/75 % of the penalty portion"]
  (**VCMI #8: clear**; §9.8): a **flat** 25 / 50 / 75 movement points
  (basic/advanced/expert) come off the step cost, but never below the base
  cost of 100: `max(100, cost − discount)` for costs above 100. Swamp 175
  → 150 / 125 / 100; Sand and Snow 150 → 125 / 100 / 100; Rough 125 → 100
  at every level. Costs of 100 or less (roads, plain terrain) are unchanged.
  Movement-module fields: `pathfinding_discount = (0, 25, 50, 75)`,
  `move_cost_floor = 100`.
- Native terrain: an army made only of the hero's native-terrain creatures
  (or the hero's own terrain) ignores that terrain's penalty. [uncertain:
  exact rule for mixed armies]
- Last-step rule: whether a hero with too few remaining points to pay a step
  may still take it, and at what cost. [uncertain — must verify; affects
  pathfinding]
- Visiting/attacking an object or picking up a resource ends the movement
  into that tile, but entering costs the normal tile cost. [uncertain:
  exact cost]

## 3. Resource economy

- There are seven resources: Gold, Wood, Ore, Mercury, Sulfur, Crystal and
  Gems. [documented]
- Daily mine output at the start of the owner's day [documented]:

  | Mine | Output/day |
  |---|---|
  | Sawmill (Wood) | 2 |
  | Ore Pit (Ore) | 2 |
  | Alchemist's Lab (Mercury) | 1 |
  | Sulfur Dune / Crystal Cavern / Gem Pond | 1 |
  | Gold Mine | 1000 |

- Town gold income per day by hall level: Village Hall 500, Town Hall 1000,
  City Hall 2000, Capitol 4000. A player may own only one Capitol.
  [documented]
- The Resource Silo and the Estates secondary skill add daily income.
  [documented existence; amounts are content data, and the values are
  [uncertain] if the data does not supply them]
- Marketplace exchange rate as a function of the number of marketplaces
  owned. [uncertain]
- Player starting resources by difficulty level. [uncertain — content table
  from scenario/difficulty]

## 4. Towns

- Buildings have costs and prerequisites, which are data. The prerequisite
  graph is shipped as our own JSON keyed to building IDs, because it is not
  reliably present in the text tables. [engine]
- Creature dwellings need a Fort. The Fort → Citadel → Castle chain adds
  walls/towers for sieges. [documented]
- **Weekly growth** of each dwelling level, applied on day 1 of each new
  week, and added to the creatures still unrecruited [documented]:

  ```
  growth = base_growth                      # from creature data
         + base_growth * castle_bonus       # Citadel: +50%, Castle: +100% (not cumulative)
         + horde_bonus                      # e.g. growth buildings: fixed +N, from data
  ```

  - Rounding of the Citadel's +50% for odd base growth. [uncertain]
  - Contributions from creature-generator dwellings owned on the adventure
    map, and whether each counts once per town of that faction. [uncertain]
  - Week-of-creature bonus (+N to one creature type) and month-of-plague
    halving. [uncertain]
- Mage Guild level L offers a fixed number of spells per level, taken from
  the faction's allowed pool. [documented existence; per-level counts are
  data]. The selection algorithm is [engine], with a seeded RNG.
- Recruitment: pay the per-unit cost and move creatures into the town
  garrison or the visiting hero's army (7 slots, merged by type).
  [documented]

## 5. Heroes

### 5.1 Primary skills

There are four primary skills: Attack, Defense, Spell Power and Knowledge.
[documented]

- Hero Attack is added to the Attack of each stack in battle. Hero Defense is
  added likewise to each stack's Defense. [documented]
- On level-up, one primary skill increases by 1. Which skill is chosen at
  random using the hero class's probability table (from `HCTRAITS`, with
  separate tables for levels 2–9 and 10+). [documented mechanism;
  probabilities are data]

### 5.2 Experience levels

Total experience required [documented for levels 1–12]:

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| XP | 0 | 1000 | 2000 | 3200 | 4600 | 6200 | 8000 | 10000 | 12200 | 14700 | 17500 | 20600 |

- Levels 13+ follow a geometric increase in step size (about +20% per level).
  [uncertain: exact rounding and the level cap behaviour]
- Battle XP awarded = total HP of the enemy creatures killed, with a
  separate award for defeating an enemy hero. [uncertain: exact rule]

### 5.3 Secondary skills

- A hero has at most 8 secondary skills, each at Basic, Advanced or Expert.
  [documented]
- On level-up the player chooses between two offers. These are an upgrade
  to an existing skill and/or a new skill, weighted by class probabilities.
  [documented mechanism]. The guaranteed-Wisdom / guaranteed-magic-school
  intervals and the exact offer-generation algorithm are [uncertain].
- Battle-relevant secondary skill values [documented, SoD]:

  | Skill | Basic | Advanced | Expert | Applies to |
  |---|---|---|---|---|
  | Offense | +10% | +20% | +30% | melee damage of hero's stacks |
  | Archery | +10% | +25% | +50% | ranged damage of hero's stacks |
  | Armorer | −5% | −10% | −15% | damage received by hero's stacks |
  | Luck | +1 | +2 | +3 | luck |
  | Leadership | +1 | +2 | +3 | morale |
  | Logistics | +10% | +20% | +30% | land movement |
  | Intelligence | +25% | +50% | +100% | max spell points |
  | Mysticism | 2 | 3 | 4 | spell points regenerated/day (replaces the base 1; §5.4) |

- Hero specialties that scale these with level (e.g. +5% of skill effect per
  level). [uncertain]

### 5.4 Spell points

- Maximum spell points = 10 × Knowledge × (1 + Intelligence bonus).
  [documented]. Rounding of the Intelligence product is [uncertain].
- Regeneration per day is capped at the maximum. The base rate is 1 point
  per day. [documented] How Mysticism combines with it is [uncertain;
  previously documented as "1 + Mysticism bonus" (3/4/5)] (**VCMI #9:
  clear in VCMI**; §9.15). In VCMI, Mysticism **replaces** the base point,
  so the total is 2 / 3 / 4 per day (basic/advanced/expert), plus specialty
  or artifact sources: `regen = mysticism_regen[level]` with
  `mysticism_regen = (1, 2, 3, 4)` (totals, not deltas). Because this
  contradicts a documented value, a hero/economy module keeps the rule
  switchable: a policy `mysticism_mode = "replace" | "add"`. The default
  is for that module's owner to set; the VCMI evidence is clear.
- A hero who starts the day in a town with a Mage Guild is fully restored.
  [documented]
- Spell cost is per spell and school level (data), reduced by expertise in
  the spell's school and by some artifacts. [uncertain: exact reductions]
- Spell effect formulas (`base + power × SpellPower` per mastery level, with
  values from the `SPTRAITS` data) are [uncertain] as a generic shape. Each
  spell must be verified individually before implementation.

## 6. Battle system

### 6.1 Battlefield

- The battlefield is a hex grid of 11 rows, with 15 playable columns plus
  one edge column on each side (17 in total) used for war machines.
  [uncertain: exact geometry and which edge hexes are usable; the engine
  stores this in a geometry table]
- Rows are offset (odd/even). Each hex has up to 6 neighbours. [documented]
  Which parity is shifted is a convention. `battle.py` defaults to even rows
  shifted right (**VCMI #1: clear**; see `battle.md` §2 and §10).
- Two-hex ("double-wide") creatures occupy their head hex plus one hex
  behind it, facing their side. [documented]
- Initial placement: the attacker's stacks start in the leftmost playable
  column and the defender's in the rightmost, at fixed rows per slot index.
  [uncertain: row table for 1–7 stacks and for "tactics" deployment]

### 6.2 Obstacles

- Field battles place random terrain-specific obstacles at the start. The
  obstacles block walking movement and standing. [documented]
- Flying creatures ignore obstacles while moving, but cannot end on an
  obstacle. [documented]
- In field battles, obstacles do **not** block or penalize ranged attacks.
  [documented]
- Siege walls: ranged attacks across the castle walls deal half damage,
  unless the shooter ignores this penalty (ability flag). [documented].
  Whether the wall penalty stacks with the distance penalty is [uncertain]
  (**VCMI #11: clear in VCMI**: two separate factors that multiply, so a
  long shot over the wall deals 25 %; §9.3). `rules.py` implements the
  multiplicative form. It no longer raises on the combination.
- The obstacle placement algorithm and the obstacle shapes are [engine]
  (seeded RNG; shapes from our own JSON keyed to obstacle IDs).

### 6.3 Turn order (initiative)

- Each round, every stack acts once, in **descending Speed** order.
  [documented]
- Speed ties: the commonly cited order is that the attacking side goes first
  on a tie and same-side ties are broken by slot. Whether sides alternate
  instead is [uncertain] (**VCMI #5: clear in VCMI, ambiguous against the
  original**: among tied stacks, the side that did not act most recently
  goes first; this carries across rounds; §9.4). `battle.py` offers this as
  `speed_tie="alternate_last_mover"`. The default stays attacker-first.
- **Wait** puts the stack in a second phase of the round. Waited stacks act
  after all non-waited stacks. The order within the wait phase (reverse
  speed?) is [uncertain] (**VCMI #6: clear in VCMI**: slowest first, ties
  by the same last-mover rule, lower slot first; §9.4). `battle.py` offers
  this as `wait_order="slow_first_alternate"`. The default stays
  reverse-speed.
- **Defend** ends the stack's turn and gives a Defense bonus until its next
  turn. The bonus is commonly cited as +20% of Defense (minimum +1).
  [uncertain: rounding]
- Speed changes during a round (Slow/Haste) reorder the remaining stacks.
  [uncertain: exact rule]

### 6.4 Movement in battle

- A stack moves up to `speed` hexes along a walkable path (BFS/Dijkstra over
  hexes, cost 1 per hex). [documented]
- Flyers move up to `speed` hexes in straight hex distance, ignoring
  intervening stacks and obstacles. [documented]
- Movement and attack happen in one action: move to a hex adjacent to the
  target, then strike. [documented]
- Moat/quicksand/firewall effects. [uncertain]

### 6.5 Morale and luck

- Morale and luck values are clamped to −3..+3. [documented]
- **Good morale:** at the start of a turn with morale M > 0, there is a
  M/24 chance (M=1 → 1/24, 2 → 2/24, 3 → 3/24) of an extra action
  immediately after this one. [documented]
- **Bad morale:** with morale M < 0, there is a chance that the stack
  "freezes" and loses its turn. The commonly documented value is |M|/24
  (1/24, 2/24, 3/24). [uncertain: the sources conflict] (**VCMI #7:
  ambiguous**: VCMI uses 2/24, 4/24, 6/24 for M = −1/−2/−3; §9.13).
  `rules.bad_morale_chance(morale, table)` takes the numerator table,
  default `BAD_MORALE_NUMERATORS = (1, 2, 3)`. The VCMI value is
  `VCMI_BAD_MORALE_NUMERATORS = (2, 4, 6)`. `battle.py` exposes it as
  policy `bad_morale_table`.
- Undead and stacks with the "no morale" ability are always neutral.
  [documented]
- Whether good morale can fire after a Wait or Defend action, and whether it
  can fire repeatedly. [uncertain] (VCMI agrees with the `battle.py`
  defaults: no roll after Wait or Defend, at most one bonus per round.)
- Morale at a waited stack's wait-phase activation. [uncertain]
  (**VCMI #4: clear in VCMI, original unverified**: no bad-morale roll, but
  good morale can still fire after the wait-phase action; §9.12).
  `battle.py` policies are `bad_morale_on_wait_activation=False` and
  `good_morale_on_wait_activation=True`.
- **Good luck:** each attack with luck L > 0 has an L/24 chance to
  **double** the damage. In the damage formula this is the `I_luck = +1.0`
  term. [documented]
- **Bad luck:** with L < 0, an |L|/24 chance to halve the damage.
  [uncertain: availability by version and where it sits in the formula]
- Army morale modifiers (mixed factions −1 per extra faction, undead −1,
  etc.). [uncertain: exact table]

### 6.6 Damage formula

Notation: `A` = the attacker's effective Attack (creature Attack + hero
Attack + modifiers), `D` = the defender's effective Defense (creature Defense
+ hero Defense + defend bonus + modifiers), `N` = the attacker stack count,
and `[min, max]` = the creature damage range.

**Step 1 — base damage** [documented]:

```
if N <= 10: base = sum of N independent uniform rolls in [min, max]
else:       base = floor( (sum of 10 independent uniform rolls in [min, max]) * N / 10 )
```

The RNG draw order (luck roll first, then damage rolls) is [engine].

**Step 2 — modifiers** [documented structure]. Increases are additive with
each other, and reductions are applied as factors:

```
damage = base * (1 + I_ad + I_skill + I_luck + I_special)
              * (1 - R_da)
              * (1 - R_armorer)
              * (1 - R_range)
              * (1 - R_melee)
              * (1 - R_wall)
```

| Term | Value | Tag |
|---|---|---|
| `I_ad` (A > D) | `0.05 * (A - D)`, capped at **3.0** (reached at a difference of 60) | [documented] |
| `R_da` (D > A) | `0.025 * (D - A)`, capped at **0.70** (reached at a difference of 28) | [documented] |
| `I_skill` | Offense (melee) 0.10/0.20/0.30, or Archery (ranged) 0.10/0.25/0.50 | [documented] |
| `I_luck` | 1.0 when good luck triggers, else 0 | [documented] |
| `I_special` | e.g. "hates" target: +0.5 | [documented for hate]; other specials (elemental opposition, Death Blow, Ballista crits) [uncertain] |
| `R_armorer` | defender hero Armorer 0.05/0.10/0.15 | [documented] |
| `R_range` | 0.5 when the target is beyond the shooter's full-damage range (commonly "more than 10 hexes") and the shooter lacks "no range penalty" | [documented factor]; exact distance threshold/inclusivity [uncertain] (VCMI: penalty when > 10). Distance origin: the shooter's head hex to the nearest target hex (**VCMI #12: clear**; `battle.py` policy `range_origin="head"`) |
| `R_melee` | 0.5 when a shooter attacks in melee and lacks "no melee penalty" | [documented] |
| `R_wall` | 0.5 when shooting across siege walls, unless exempt | [documented factor]; stacking with `R_range` [uncertain], implemented as multiplicative (**VCMI #11: clear in VCMI**; §9.3) |
| Shield / Air Shield / Stone Skin / Bless / Curse / Frenzy … | spell-dependent | [uncertain] — per-spell verification |
| Hero specialty bonuses | level-scaled | [uncertain] |

**Step 3 — rounding** [documented]: the final damage is rounded down to an
integer. The minimum is 1 when the attack lands. Whether the original rounds
at any intermediate step is [uncertain]. The reference implementation uses
exact rational arithmetic and floors once, at the end.

**Step 4 — applying damage to a stack** [documented]: a stack is `count`
creatures, with the top creature at `top_hp` out of `max_hp`.

```
total = (count - 1) * max_hp + top_hp
remaining = max(0, total - damage)
count'  = ceil(remaining / max_hp)
top_hp' = remaining - (count' - 1) * max_hp   (if count' > 0)
killed  = count - count'
```

Resurrection and healing restore HP to the top creature first and cannot
exceed the original stack size. [documented]. The cap details for
resurrection spells are [uncertain].

### 6.7 Retaliation and attack sequencing

- A melee attack that the defender survives triggers **one retaliation per
  round**. The retaliation is a normal melee attack by the defender, with
  roles swapped, and uses its count after taking damage. [documented]
- Ranged attacks are never retaliated. [documented]
- Stacks with "unlimited retaliations" retaliate on every melee attack.
  "No enemy retaliation" attackers suppress the retaliation. Paralysed,
  blinded or petrified defenders do not retaliate. [documented]
- "Strikes twice" melee: strike → (retaliation if available) → second
  strike, if the attacker is still alive. "Shoots twice": two shots, with
  no retaliation. [documented]
- The retaliation counter resets at the start of each round. [documented]
- Shooters with an enemy stack adjacent cannot shoot. They must melee, at
  the `R_melee` penalty unless exempt. Shooters with no ammo left must
  melee. [documented]
- Multi-hex attacks (breath, cleave, all-around attacks): which hexes are
  hit and whether each target retaliates. [uncertain — per ability]

### 6.8 Battle end and experience

- A side loses when it has no living stacks, or when its hero retreats or
  surrenders. [documented]
- The surrender cost formula, and the experience and necromancy awards.
  [uncertain]

---

## 7. Determinism requirements [engine]

- Every random event uses `sim.rng` named streams. For a melee exchange the
  draw order is: attacker luck roll → attacker damage rolls → (if
  retaliating) defender luck roll → defender damage rolls → morale roll
  at the start of the next turn.
- Rule paths use only integer/rational math (see `rules.py`, which uses
  `fractions.Fraction`).

## 8. Reference implementation

`tools/h3re/h3re/rules.py` implements **only** the [documented] items of
§6.5–§6.6:

- `attack_defense_factor`, `base_damage` (with an injectable RNG),
  `damage_from_base`, `damage_range`, `apply_damage`, `luck_chance` and
  `good_morale_chance` and `bad_morale_chance`, plus the skill constant tables.

Items marked [uncertain] stay out of it until §9 verifies them. There are
two exceptions, both backed by VCMI and both still open in §9:

- `R_wall` × `R_range` multiply (§9.3).
- The bad-morale table is a parameter (`BAD_MORALE_NUMERATORS`, default
  documented (1, 2, 3); `VCMI_BAD_MORALE_NUMERATORS` (2, 4, 6); §9.13).

All arithmetic stays exact: integers and `fractions.Fraction`, no floats.

## 9. Verification checklist (to promote [uncertain] → [documented])

Each item is resolved by a controlled experiment in the user's own copy of
the game, for example a custom map from the editor with fixed armies and
many repeated trials. The observed values are recorded as test fixtures.

Each item lists the VCMI evidence (`vcmi-crosscheck-rules.md`) and the
current engine default. An experiment still decides the matter.

1. Intermediate rounding in the damage formula: compare the observed
   min/max damage for stacks whose rational product is non-integer. (VCMI
   #10, ambiguous: it builds a floored final range in floating point and
   averages up to 10 draws inside it. `rules.py` is unchanged.)
2. Range penalty distance threshold (10 vs 11 hexes), and the distance
   origin for two-hex shooters. (VCMI: > 10, measured from the head hex,
   #12 clear. `battle.py` default `range_penalty_beyond=10`,
   `range_origin="head"`; option `"any_cell"`.)
3. Wall and range penalty stacking. (VCMI #11, clear in VCMI:
   multiplicative, 25 %. `rules.py` implements this. Experiment: a long
   shot across a standing wall should deal a quarter.)
4. Speed tie order and wait-phase order. (VCMI #5/#6: last-mover
   alternation carrying across rounds; wait phase slowest first, lower slot
   first. Pending experiment: `battle.py` options
   `speed_tie="alternate_last_mover"` and
   `wait_order="slow_first_alternate"`; defaults still `"attacker_first"`
   and `"reverse_speed"`. Test: two equal-speed stacks per side plus one
   faster attacker. The last-mover rule predicts the defender takes the
   first tie slot.)
5. Defend bonus value and rounding. (VCMI agrees: 20 %, floor, minimum 1.)
6. Bad-luck availability and its position in the formula. (VCMI: absent in
   SoD.)
7. Diagonal movement cost and the last-step rule on the adventure map.
   (VCMI: `floor(cost·√2)`, 100 → 141; diagonal exception; zero the
   remainder when it is below the next step's cost; clear. §2.2.)
8. Pathfinding reductions and the native-terrain rule for mixed armies.
   (VCMI #8: flat 25/50/75, floor 100; native only if every stack is
   native; clear. §2.2.)
9. Experience table beyond level 12.
10. Citadel +50% rounding for odd growth.
11. Each spell's effect formula and cost reductions.
12. Morale after Wait/Defend, repeated good-morale triggers, and morale at
    a waited stack's wait-phase activation. (VCMI agrees with "no roll after
    Wait/Defend, no repeat". VCMI #4 for the wait-phase activation: no bad
    roll, good roll kept. `battle.py` now defaults to that,
    `bad_morale_on_wait_activation=False`,
    `good_morale_on_wait_activation=True`. Before 2026-11-01 both rolls
    happened. Experiment: a stack with morale −3 that waits should never
    freeze in the wait phase over many trials.)
13. **Bad-morale chance per morale point** (new). Documented: |M|/24. VCMI
    #7 (ambiguous): 2/24, 4/24, 6/24. The default stays
    `bad_morale_table = (1, 2, 3)`. Experiment: count freezes of a morale
    −1 and a morale −3 stack over a few hundred activations. At −3 the two
    tables predict 12.5 % and 25 %.
14. **Adventure step pricing and road costs** (new). Documented: the
    destination tile pays, any road 50. VCMI #2/#3 (clear): the source tile
    pays, the road rate needs a road on both tiles, roads cost 75/65/50
    (dirt/gravel/cobblestone). Experiment: walk a hero one step off and one
    step onto a dirt road and onto swamp, and compare the points left.
15. **Mysticism regeneration** (new). Documented: 1 + 2/3/4. VCMI #9
    (clear in VCMI): Mysticism replaces the base, 2/3/4 in total.
    Experiment: a hero with Basic Mysticism and no other sources, away
    from towns, regains 2 or 3 points per day.
