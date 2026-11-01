"""Reference implementation of the [documented] battle damage rules.

Spec: docs/specs/rules.md sections 6.5-6.6. Clean-room: implemented from the
written spec only. Items the spec marks [uncertain] are deliberately absent
(spells, specialties, bad luck, defend bonus, ...), or are parameters whose
default is the documented value (the bad-morale table, rules.md 9.13).
Wall + range penalty stacking is multiplicative (VCMI cross-check #11, see
docs/specs/vcmi-crosscheck-rules.md; still listed in rules.md 9.3).

All arithmetic is exact (fractions.Fraction) with a single floor at the end,
so results are deterministic across platforms.
"""

from fractions import Fraction
from math import floor

__all__ = [
    "AD_BONUS_PER_POINT", "AD_BONUS_CAP", "DA_PENALTY_PER_POINT", "DA_PENALTY_CAP",
    "OFFENSE", "ARCHERY", "ARMORER", "HATE_BONUS", "LUCK_BONUS", "HALF",
    "attack_defense_factor", "base_damage", "damage_from_base", "damage_range",
    "apply_damage", "luck_chance", "good_morale_chance", "bad_morale_chance",
    "BAD_MORALE_NUMERATORS", "VCMI_BAD_MORALE_NUMERATORS", "MORALE_DIE",
    "check_bad_morale_table",
]

# Attack > Defense: +5% per point, capped at +300% (difference 60).
AD_BONUS_PER_POINT = Fraction(1, 20)
AD_BONUS_CAP = Fraction(3)
# Defense > Attack: -2.5% per point, capped at -70% (difference 28).
DA_PENALTY_PER_POINT = Fraction(1, 40)
DA_PENALTY_CAP = Fraction(7, 10)

# Secondary skill level (0 = none, 1 basic, 2 advanced, 3 expert) -> fraction.
OFFENSE = (Fraction(0), Fraction(1, 10), Fraction(2, 10), Fraction(3, 10))
ARCHERY = (Fraction(0), Fraction(1, 10), Fraction(1, 4), Fraction(1, 2))
ARMORER = (Fraction(0), Fraction(1, 20), Fraction(1, 10), Fraction(3, 20))

# Morale/luck die size, and the bad-morale chance numerators for morale
# -1, -2, -3. (1, 2, 3) is the community-documented table; VCMI configures
# (2, 4, 6). Which one the original uses is open (rules.md 9.13).
MORALE_DIE = 24
BAD_MORALE_NUMERATORS = (1, 2, 3)
VCMI_BAD_MORALE_NUMERATORS = (2, 4, 6)

HATE_BONUS = Fraction(1, 2)
LUCK_BONUS = Fraction(1)
HALF = Fraction(1, 2)


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
    if not 1 <= dmg_min <= dmg_max:
        raise ValueError("need 1 <= dmg_min <= dmg_max")
    rolls = min(count, 10)
    total = sum(rng.randint(dmg_min, dmg_max) for _ in range(rolls))
    if count <= 10:
        return total
    return (total * count) // 10


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
    if ranged and melee_penalty:
        raise ValueError("melee_penalty applies only to melee attacks")
    if not ranged and (range_penalty or wall_penalty):
        raise ValueError("range/wall penalty applies only to ranged attacks")

    inc_ad, red_da = attack_defense_factor(attack, defense)
    inc = inc_ad + (_skill(ARCHERY, archery) if ranged else _skill(OFFENSE, offense))
    if lucky:
        inc += LUCK_BONUS
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
    return max(1, floor(dmg))


def damage_range(count, dmg_min, dmg_max, attack, defense, **mods):
    """(min, max) final damage without RNG, e.g. for a touch-UI preview."""
    if count <= 0:
        return 0, 0
    lo = damage_from_base(count * dmg_min, attack, defense, **mods)
    hi = damage_from_base(count * dmg_max, attack, defense, **mods)
    return lo, hi


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
    """Chance of good luck (double damage) per attack: L/24 for L in 1..3."""
    return Fraction(max(0, _clamp3(luck)), 24)


def good_morale_chance(morale):
    """Chance of an extra action: M/24 for M in 1..3."""
    return Fraction(max(0, _clamp3(morale)), 24)


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

    ``table[i]`` is the numerator over 24 for morale -(i+1). The default
    (1, 2, 3) gives |M|/24; VCMI_BAD_MORALE_NUMERATORS is the alternative.
    """
    m = -_clamp3(morale)
    if m <= 0:
        return Fraction(0)
    return Fraction(check_bad_morale_table(table)[m - 1], MORALE_DIE)
