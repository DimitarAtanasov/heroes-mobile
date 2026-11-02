"""Reference implementation of the [documented] battle damage rules.

Spec: docs/specs/rules.md sections 6.5-6.6. Clean-room: implemented from the
written spec only. Items the spec marks [uncertain] are deliberately absent
(spells, specialties, bad luck, defend bonus, ...), or are parameters whose
default is the documented value (the bad-morale table, rules.md 9.13).
Wall + range penalty stacking is multiplicative (VCMI cross-check #11, see
docs/specs/vcmi-crosscheck-rules.md; still listed in rules.md 9.3).

All arithmetic is exact (fractions.Fraction) with a single floor at the end,
so results are deterministic across platforms.

Forge law "ONE damage function serves preview and execution": battle
execution and every preview (UI, AI) call ``resolve_damage(ctx, policy)``.
The preview floor / expected / ceiling are the PESSIMAL / EXPECTED / OPTIMAL
policies of that same pipeline, so the executed (ACTUAL_SEED) damage always
lies in [floor, ceiling] (property-tested in tests/test_rules.py).
"""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from math import floor

from . import datapack as _datapack

__all__ = [
    "AD_BONUS_PER_POINT", "AD_BONUS_CAP", "DA_PENALTY_PER_POINT", "DA_PENALTY_CAP",
    "OFFENSE", "ARCHERY", "ARMORER", "HATE_BONUS", "LUCK_BONUS", "HALF",
    "attack_defense_factor", "base_damage", "damage_from_base", "damage_range",
    "RollPolicy", "DamageCtx", "DamageResult", "DamagePreview",
    "resolve_damage", "preview_damage",
    "apply_damage", "luck_chance", "good_morale_chance", "bad_morale_chance",
    "BAD_MORALE_NUMERATORS", "VCMI_BAD_MORALE_NUMERATORS", "MORALE_DIE",
    "check_bad_morale_table", "RULES_HASH", "RULES_DIR",
]

# Tuning constants come from data/rules.json (Forge law: balance numbers live
# in data/*.json). The file is read and validated in datapack.py (not a sim
# module); here we only bind the already-loaded ints and Fractions.
# Attack > Defense: +5% per point, capped at +300% (difference 60).
# Defense > Attack: -2.5% per point, capped at -70% (difference 28).
# Skill tables: level (0 = none, 1 basic, 2 advanced, 3 expert) -> fraction.
# MORALE_DIE is the morale/luck die size; BAD_MORALE_NUMERATORS are the
# bad-morale chance numerators for morale -1, -2, -3. (1, 2, 3) is the
# community-documented table; VCMI configures (2, 4, 6). Which one the
# original uses is open (rules.md 9.13).
_PACK_OBJ = _datapack.load_rules_pack_dir()
_PACK = _PACK_OBJ.rules
# Content hash of the loaded rules pack and the directory it came from. Battle
# state carries RULES_HASH, so peers with different packs diverge at step 0.
RULES_HASH = _PACK_OBJ.content_hash
RULES_DIR = _datapack.LOADED_DIR
AD_BONUS_PER_POINT = _PACK["ad_bonus_per_point"]
AD_BONUS_CAP = _PACK["ad_bonus_cap"]
DA_PENALTY_PER_POINT = _PACK["da_penalty_per_point"]
DA_PENALTY_CAP = _PACK["da_penalty_cap"]
OFFENSE = _PACK["offense"]
ARCHERY = _PACK["archery"]
ARMORER = _PACK["armorer"]
MORALE_DIE = _PACK["morale_die"]
BAD_MORALE_NUMERATORS = _PACK["bad_morale_numerators"]
VCMI_BAD_MORALE_NUMERATORS = _PACK["vcmi_bad_morale_numerators"]
HATE_BONUS = _PACK["hate_bonus"]
LUCK_BONUS = _PACK["luck_bonus"]
HALF = _PACK["half"]


def _skill(table, level):
    if not 0 <= level <= 3:
        raise ValueError("skill level must be 0..3, got %r" % (level,))
    return table[level]


def attack_defense_factor(attack, defense):
    """Return (increase, reduction) from the attack/defense difference.

    Exactly one of the two is non-zero (or both zero when equal).
    """
    diff = attack - defense
    if diff > 0:
        return min(AD_BONUS_PER_POINT * diff, AD_BONUS_CAP), Fraction(0)
    if diff < 0:
        return Fraction(0), min(DA_PENALTY_PER_POINT * (-diff), DA_PENALTY_CAP)
    return Fraction(0), Fraction(0)


def base_damage(count, dmg_min, dmg_max, rng):
    """Roll base damage for a stack.

    ``rng`` must provide ``randint(a, b)`` (inclusive), e.g. random.Random.
    N <= 10: sum of N rolls. N > 10: floor(sum of 10 rolls * N / 10).
    """
    if count <= 0:
        return 0
    if not 0 <= dmg_min <= dmg_max or dmg_max < 1:
        raise ValueError("need 0 <= dmg_min <= dmg_max and dmg_max >= 1")
    rolls = min(count, 10)
    total = sum(rng.randint(dmg_min, dmg_max) for _ in range(rolls))
    if count <= 10:
        return total
    return (total * count) // 10


def _check_flags(ranged, melee_penalty, range_penalty, wall_penalty):
    if ranged and melee_penalty:
        raise ValueError("melee_penalty applies only to melee attacks")
    if not ranged and (range_penalty or wall_penalty):
        raise ValueError("range/wall penalty applies only to ranged attacks")


def _scaled(base, attack, defense, ranged, offense, archery, armorer,
            luck_inc, hates, range_penalty, melee_penalty, wall_penalty):
    """Exact (unfloored) damage for a Fraction ``base``; ``luck_inc`` in [0, 1]."""
    inc_ad, red_da = attack_defense_factor(attack, defense)
    inc = inc_ad + (_skill(ARCHERY, archery) if ranged else _skill(OFFENSE, offense))
    inc += luck_inc
    if hates:
        inc += HATE_BONUS

    dmg = Fraction(base) * (1 + inc)
    dmg *= 1 - red_da
    dmg *= 1 - _skill(ARMORER, armorer)
    if range_penalty:
        dmg *= 1 - HALF
    if wall_penalty:
        dmg *= 1 - HALF
    if melee_penalty:
        dmg *= 1 - HALF
    return dmg


def damage_from_base(base, attack, defense, *, ranged=False, offense=0,
                     archery=0, armorer=0, lucky=False, hates=False,
                     range_penalty=False, melee_penalty=False,
                     wall_penalty=False):
    """Apply the documented modifiers to a rolled base damage.

    ``ranged`` selects Archery vs Offense. ``range_penalty`` / ``wall_penalty``
    apply only to ranged attacks; ``melee_penalty`` (shooter in melee) only to
    melee. Range and wall penalties are separate factors and multiply
    (a long shot over a wall deals 1/4), per the VCMI cross-check.
    """
    if base <= 0:
        return 0
    _check_flags(ranged, melee_penalty, range_penalty, wall_penalty)
    return max(1, floor(_scaled(
        base, attack, defense, ranged, offense, archery, armorer,
        LUCK_BONUS if lucky else Fraction(0), hates, range_penalty,
        melee_penalty, wall_penalty)))


# --------------------------------------------------------------------------
# ONE damage function serves preview and execution
# --------------------------------------------------------------------------

class RollPolicy(Enum):
    """How ``resolve_damage`` settles every random choice of a strike.

    ACTUAL_SEED draws from the RNG (execution). PESSIMAL / OPTIMAL take the
    worst / best outcome of every draw (preview floor / ceiling). EXPECTED
    uses the exact mean of every draw (preview expectation). All policies
    run the same pipeline, so floor <= actual <= ceiling by construction.
    """
    ACTUAL_SEED = "actual_seed"
    PESSIMAL = "pessimal"
    EXPECTED = "expected"
    OPTIMAL = "optimal"


@dataclass(frozen=True)
class DamageCtx:
    """Everything one strike's damage depends on (all integers / flags)."""
    count: int
    dmg_min: int
    dmg_max: int
    attack: int
    defense: int
    ranged: bool = False
    offense: int = 0
    archery: int = 0
    armorer: int = 0
    hates: bool = False
    range_penalty: bool = False
    melee_penalty: bool = False
    wall_penalty: bool = False
    luck: int = 0          # attacker luck; > 0 may double (rules.md 6.5)
    bad_luck: bool = False  # policy switch: luck < 0 may halve


@dataclass(frozen=True)
class DamageResult:
    damage: int
    lucky: bool = False
    unlucky: bool = False


@dataclass(frozen=True)
class DamagePreview:
    floor: int
    expected: int
    ceiling: int


def _settle(chance, policy, rng, good):
    """Resolve a luck-type event. ``good`` says whether it raises damage."""
    if policy is RollPolicy.ACTUAL_SEED:
        return rng.chance(chance.numerator, chance.denominator)
    if policy is RollPolicy.OPTIMAL:
        return chance > 0 if good else chance >= 1
    return chance >= 1 if good else chance > 0  # PESSIMAL


def resolve_damage(ctx, policy, rng=None):
    """Final damage of one strike under ``policy``. Returns DamageResult.

    ACTUAL_SEED needs ``rng`` (``chance(num, den)`` and ``randint(a, b)``);
    draw order is luck roll (only when luck can fire), then the damage rolls.
    The other policies never touch ``rng``. EXPECTED reports lucky/unlucky
    as False (its damage is the exact mean over both branches, floored once).
    """
    if policy is RollPolicy.ACTUAL_SEED and rng is None:
        raise ValueError("ACTUAL_SEED needs an rng")
    if not isinstance(policy, RollPolicy):
        raise ValueError("unknown roll policy %r" % (policy,))
    _check_flags(ctx.ranged, ctx.melee_penalty, ctx.range_penalty, ctx.wall_penalty)
    if ctx.count > 0 and (not 0 <= ctx.dmg_min <= ctx.dmg_max or ctx.dmg_max < 1):
        raise ValueError("need 0 <= dmg_min <= dmg_max and dmg_max >= 1")

    good = luck_chance(ctx.luck) if ctx.luck > 0 else Fraction(0)
    bad = luck_chance(-ctx.luck) if ctx.luck < 0 and ctx.bad_luck else Fraction(0)
    lucky = unlucky = False
    if policy is RollPolicy.EXPECTED:
        luck_inc = LUCK_BONUS * good
    else:
        if ctx.luck > 0:
            lucky = _settle(good, policy, rng, True)
        elif ctx.luck < 0 and ctx.bad_luck:
            unlucky = _settle(bad, policy, rng, False)
        luck_inc = LUCK_BONUS if lucky else Fraction(0)

    if ctx.count <= 0:
        return DamageResult(0, lucky, unlucky)
    if policy is RollPolicy.ACTUAL_SEED:
        base = base_damage(ctx.count, ctx.dmg_min, ctx.dmg_max, rng)
    elif policy is RollPolicy.PESSIMAL:
        base = ctx.count * ctx.dmg_min
    elif policy is RollPolicy.OPTIMAL:
        base = ctx.count * ctx.dmg_max
    else:
        base = Fraction(ctx.count * (ctx.dmg_min + ctx.dmg_max), 2)

    dmg = _scaled(base, ctx.attack, ctx.defense, ctx.ranged, ctx.offense,
                  ctx.archery, ctx.armorer, luck_inc, ctx.hates,
                  ctx.range_penalty, ctx.melee_penalty, ctx.wall_penalty)
    if policy is RollPolicy.EXPECTED:
        # Bad luck halves after the floor; floor(x / 2) == floor(x) // 2.
        dmg *= 1 - bad * HALF
        return DamageResult(max(1, floor(dmg)))
    dmg = max(1, floor(dmg))
    if unlucky:
        dmg = max(1, dmg // 2)
    return DamageResult(dmg, lucky, unlucky)


def preview_damage(ctx):
    """DamagePreview(floor, expected, ceiling): the same pipeline as execution
    under PESSIMAL / EXPECTED / OPTIMAL. No RNG is consumed."""
    return DamagePreview(resolve_damage(ctx, RollPolicy.PESSIMAL).damage,
                         resolve_damage(ctx, RollPolicy.EXPECTED).damage,
                         resolve_damage(ctx, RollPolicy.OPTIMAL).damage)


def damage_range(count, dmg_min, dmg_max, attack, defense, **mods):
    """(min, max) final damage without RNG, e.g. for a touch-UI preview.

    Thin wrapper over ``preview_damage``: the floor and ceiling of the same
    pipeline execution uses. ``mods`` are ``DamageCtx`` fields (luck and
    bad_luck included, so luck widens the range instead of escaping it).
    """
    if count <= 0:
        return 0, 0
    p = preview_damage(DamageCtx(count, dmg_min, dmg_max, attack, defense, **mods))
    return p.floor, p.ceiling


def apply_damage(count, top_hp, max_hp, damage):
    """Apply damage to a stack. Returns (new_count, new_top_hp, killed).

    An empty stack (count == 0) is valid and has no top creature, so its
    top_hp must be 0. Damage to it kills nothing and returns (0, 0, 0).
    """
    if max_hp <= 0 or count < 0:
        raise ValueError("invalid stack state")
    if damage < 0:
        raise ValueError("damage must be non-negative")
    if count == 0:
        if top_hp != 0:
            raise ValueError("empty stack must have top_hp 0")
        return 0, 0, 0
    if not 0 < top_hp <= max_hp:
        raise ValueError("invalid stack state")
    total = (count - 1) * max_hp + top_hp
    remaining = max(0, total - damage)
    if remaining == 0:
        return 0, 0, count
    new_count = -(-remaining // max_hp)  # ceil
    new_top = remaining - (new_count - 1) * max_hp
    return new_count, new_top, count - new_count


def _clamp3(v):
    return max(-3, min(3, v))


def luck_chance(luck):
    """Chance of good luck (double damage) per attack: L/MORALE_DIE for L in 1..3.

    Luck shares the pack's one die with morale (rules.md 6.5)."""
    return Fraction(max(0, _clamp3(luck)), MORALE_DIE)


def good_morale_chance(morale):
    """Chance of an extra action: M/MORALE_DIE for M in 1..3."""
    return Fraction(max(0, _clamp3(morale)), MORALE_DIE)


def check_bad_morale_table(table):
    """Validate a bad-morale table: 3 ints in 0..MORALE_DIE, non-decreasing."""
    table = tuple(table)
    if len(table) != 3 or any(type(n) is not int or not 0 <= n <= MORALE_DIE
                              for n in table):
        raise ValueError("bad_morale_table needs 3 integers in 0..%d" % MORALE_DIE)
    if list(table) != sorted(table):
        raise ValueError("bad_morale_table must be non-decreasing")
    return table


def bad_morale_chance(morale, table=BAD_MORALE_NUMERATORS):
    """Chance of freezing (losing the turn) for M in -3..-1.

    ``table[i]`` is the numerator over MORALE_DIE for morale -(i+1). The default
    (1, 2, 3) gives |M|/MORALE_DIE; VCMI_BAD_MORALE_NUMERATORS is the alternative.
    """
    m = -_clamp3(morale)
    if m <= 0:
        return Fraction(0)
    return Fraction(check_bad_morale_table(table)[m - 1], MORALE_DIE)
