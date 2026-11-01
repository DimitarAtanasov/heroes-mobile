import os
import random
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from h3re import rules  # noqa: E402
from h3re.rng import Pcg32  # noqa: E402


class FixedRng:
    """randint stub returning a scripted sequence."""

    def __init__(self, values):
        self.values = list(values)

    def randint(self, a, b):
        v = self.values.pop(0)
        assert a <= v <= b
        return v


class AttackDefenseTest(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(rules.attack_defense_factor(10, 10), (0, 0))

    def test_bonus_and_cap(self):
        self.assertEqual(rules.attack_defense_factor(11, 10), (Fraction(1, 20), 0))
        self.assertEqual(rules.attack_defense_factor(60, 0), (Fraction(3), 0))
        self.assertEqual(rules.attack_defense_factor(59, 0)[0], Fraction(59, 20))
        self.assertEqual(rules.attack_defense_factor(100, 0), (Fraction(3), 0))

    def test_penalty_and_cap(self):
        self.assertEqual(rules.attack_defense_factor(0, 1), (0, Fraction(1, 40)))
        self.assertEqual(rules.attack_defense_factor(0, 27)[1], Fraction(27, 40))
        self.assertEqual(rules.attack_defense_factor(0, 28)[1], Fraction(7, 10))
        self.assertEqual(rules.attack_defense_factor(0, 50)[1], Fraction(7, 10))


class BaseDamageTest(unittest.TestCase):
    def test_small_stack_sums_each(self):
        self.assertEqual(rules.base_damage(3, 1, 3, FixedRng([1, 2, 3])), 6)

    def test_large_stack_scales_ten_rolls(self):
        rng = FixedRng([2] * 10)
        self.assertEqual(rules.base_damage(25, 1, 3, rng), 50)  # 20*25/10
        rng = FixedRng([1, 2, 1, 2, 1, 2, 1, 2, 1, 2])  # sum 15
        self.assertEqual(rules.base_damage(13, 1, 2, rng), 19)  # floor(195/10)

    def test_bounds_with_real_rng(self):
        rng = random.Random(1234)
        for n in (1, 7, 10, 11, 57, 500):
            for _ in range(50):
                b = rules.base_damage(n, 2, 5, rng)
                self.assertTrue(2 * n <= b <= 5 * n, (n, b))

    def test_empty_and_invalid(self):
        self.assertEqual(rules.base_damage(0, 1, 2, FixedRng([])), 0)
        with self.assertRaises(ValueError):
            rules.base_damage(1, 3, 2, FixedRng([]))


class DamageFromBaseTest(unittest.TestCase):
    def test_neutral(self):
        self.assertEqual(rules.damage_from_base(100, 5, 5), 100)

    def test_attack_advantage(self):
        self.assertEqual(rules.damage_from_base(100, 15, 5), 150)
        self.assertEqual(rules.damage_from_base(100, 99, 0), 400)

    def test_defense_advantage(self):
        self.assertEqual(rules.damage_from_base(100, 5, 15), 75)
        self.assertEqual(rules.damage_from_base(100, 0, 99), 30)

    def test_offense_vs_archery(self):
        self.assertEqual(rules.damage_from_base(100, 0, 0, offense=3), 130)
        self.assertEqual(rules.damage_from_base(100, 0, 0, ranged=True, archery=3), 150)
        # Offense ignored for ranged, archery ignored for melee.
        self.assertEqual(rules.damage_from_base(100, 0, 0, ranged=True, offense=3), 100)
        self.assertEqual(rules.damage_from_base(100, 0, 0, archery=3), 100)

    def test_increases_are_additive(self):
        # +50% (A-D=10) + 30% offense + 100% luck + 50% hate = x3.3
        self.assertEqual(
            rules.damage_from_base(100, 10, 0, offense=3, lucky=True, hates=True), 330)

    def test_reductions_multiply(self):
        # -25% (D-A=10), armorer expert -15%, shooter melee -50%
        # 100 * 0.75 * 0.85 * 0.5 = 31.875 -> 31
        self.assertEqual(
            rules.damage_from_base(100, 0, 10, armorer=3, melee_penalty=True), 31)

    def test_range_and_wall_penalty(self):
        self.assertEqual(rules.damage_from_base(100, 0, 0, ranged=True, range_penalty=True), 50)
        self.assertEqual(rules.damage_from_base(100, 0, 0, ranged=True, wall_penalty=True), 50)
        # Range and wall penalties are separate factors: they multiply.
        self.assertEqual(rules.damage_from_base(100, 0, 0, ranged=True, range_penalty=True,
                                                wall_penalty=True), 25)
        # 77 * 1.5 (archery expert) * 0.5 * 0.5 = 28.875 -> 28 (one floor).
        self.assertEqual(rules.damage_from_base(77, 0, 0, ranged=True, archery=3,
                                                range_penalty=True, wall_penalty=True), 28)
        # 3 * 0.25 = 0.75 -> minimum 1.
        self.assertEqual(rules.damage_from_base(3, 0, 0, ranged=True, range_penalty=True,
                                                wall_penalty=True), 1)
        self.assertEqual(rules.damage_range(10, 2, 4, 0, 0, ranged=True, range_penalty=True,
                                            wall_penalty=True), (5, 10))

    def test_flag_validation(self):
        with self.assertRaises(ValueError):
            rules.damage_from_base(10, 0, 0, ranged=True, melee_penalty=True)
        with self.assertRaises(ValueError):
            rules.damage_from_base(10, 0, 0, range_penalty=True)
        with self.assertRaises(ValueError):
            rules.damage_from_base(10, 0, 0, offense=4)

    def test_floor_and_minimum_one(self):
        self.assertEqual(rules.damage_from_base(3, 0, 1), 2)  # 2.925
        self.assertEqual(rules.damage_from_base(1, 0, 50, armorer=3), 1)
        self.assertEqual(rules.damage_from_base(0, 10, 0), 0)


class DamageRangeTest(unittest.TestCase):
    def test_range(self):
        self.assertEqual(rules.damage_range(10, 1, 3, 5, 5), (10, 30))
        self.assertEqual(rules.damage_range(20, 2, 4, 15, 5), (60, 120))
        self.assertEqual(rules.damage_range(0, 2, 4, 0, 0), (0, 0))

    def test_rolls_within_range(self):
        rng = random.Random(7)
        lo, hi = rules.damage_range(37, 2, 7, 12, 9, offense=2)
        for _ in range(200):
            b = rules.base_damage(37, 2, 7, rng)
            d = rules.damage_from_base(b, 12, 9, offense=2)
            self.assertTrue(lo <= d <= hi)


def random_ctx(r):
    """A random legal DamageCtx (integers / flags only)."""
    ranged = r.randrange(10) < 5
    lo = r.randint(1, 20)
    return rules.DamageCtx(
        count=r.choice((0, 1, r.randint(1, 10), r.randint(11, 999))),
        dmg_min=lo, dmg_max=lo + r.randint(0, 30),
        attack=r.randint(0, 80), defense=r.randint(0, 80), ranged=ranged,
        offense=r.randint(0, 3), archery=r.randint(0, 3), armorer=r.randint(0, 3),
        hates=r.randrange(10) < 3,
        range_penalty=ranged and r.randrange(10) < 4,
        wall_penalty=ranged and r.randrange(10) < 3,
        melee_penalty=(not ranged) and r.randrange(10) < 3,
        luck=r.randint(-4, 4), bad_luck=r.randrange(10) < 5)


class ResolveDamageLawTest(unittest.TestCase):
    """Forge law: ONE damage function serves preview and execution."""

    N = 2000

    def test_actual_within_preview(self):
        r = random.Random(20261101)
        for i in range(self.N):
            ctx = random_ctx(r)
            p = rules.preview_damage(ctx)
            self.assertLessEqual(p.floor, p.expected, ctx)
            self.assertLessEqual(p.expected, p.ceiling, ctx)
            rng = Pcg32(i)
            for _ in range(5):
                d = rules.resolve_damage(ctx, rules.RollPolicy.ACTUAL_SEED, rng).damage
                self.assertTrue(p.floor <= d <= p.ceiling, (ctx, p, d))

    def test_monotonic_in_attack(self):
        r = random.Random(99)
        for i in range(self.N // 4):
            ctx = random_ctx(r)
            prev = None
            for a in range(0, 90, 3):
                c = rules.DamageCtx(**{**ctx.__dict__, "attack": a})
                p = rules.preview_damage(c)
                act = rules.resolve_damage(c, rules.RollPolicy.ACTUAL_SEED, Pcg32(i)).damage
                cur = (p.floor, p.expected, p.ceiling, act)
                if prev is not None:
                    for x, y in zip(prev, cur):
                        self.assertLessEqual(x, y, (ctx, a))
                prev = cur

    def test_monotonic_in_offense_and_archery(self):
        r = random.Random(5)
        for i in range(self.N // 4):
            ctx = random_ctx(r)
            field = "archery" if ctx.ranged else "offense"
            vals = [rules.resolve_damage(rules.DamageCtx(**{**ctx.__dict__, field: lv}),
                                         rules.RollPolicy.ACTUAL_SEED, Pcg32(i)).damage
                    for lv in range(4)]
            self.assertEqual(vals, sorted(vals), ctx)

    def test_deterministic(self):
        r = random.Random(3)
        for i in range(self.N // 4):
            ctx = random_ctx(r)
            a, b = Pcg32(i, 1), Pcg32(i, 1)
            for _ in range(3):
                self.assertEqual(rules.resolve_damage(ctx, rules.RollPolicy.ACTUAL_SEED, a),
                                 rules.resolve_damage(ctx, rules.RollPolicy.ACTUAL_SEED, b))
            self.assertEqual(a.next_u32(), b.next_u32())
            self.assertEqual(rules.preview_damage(ctx), rules.preview_damage(ctx))

    def test_preview_consumes_no_rng(self):
        class Boom:
            def __getattr__(self, name):
                raise AssertionError("preview touched the rng")
        ctx = rules.DamageCtx(30, 1, 3, 6, 4, luck=2)
        for pol in (rules.RollPolicy.PESSIMAL, rules.RollPolicy.EXPECTED,
                    rules.RollPolicy.OPTIMAL):
            rules.resolve_damage(ctx, pol, Boom())

    def test_execution_matches_legacy_two_step(self):
        # ACTUAL_SEED == old base_damage + damage_from_base with the same draws.
        r = random.Random(11)
        for i in range(self.N // 2):
            ctx = random_ctx(r)
            a, b = Pcg32(i), Pcg32(i)
            res = rules.resolve_damage(ctx, rules.RollPolicy.ACTUAL_SEED, a)
            lucky = unlucky = False
            if ctx.luck > 0:
                f = rules.luck_chance(ctx.luck)
                lucky = b.chance(f.numerator, f.denominator)
            elif ctx.luck < 0 and ctx.bad_luck:
                f = rules.luck_chance(-ctx.luck)
                unlucky = b.chance(f.numerator, f.denominator)
            base = rules.base_damage(ctx.count, ctx.dmg_min, ctx.dmg_max, b)
            mods = {k: v for k, v in ctx.__dict__.items()
                    if k not in ("count", "dmg_min", "dmg_max", "attack", "defense",
                                 "luck", "bad_luck")}
            d = rules.damage_from_base(base, ctx.attack, ctx.defense, lucky=lucky, **mods)
            if unlucky and ctx.count > 0:  # legacy halved an empty stack's 0 up to 1
                d = max(1, d // 2)
            self.assertEqual(res, rules.DamageResult(d, lucky, unlucky), ctx)
            self.assertEqual(a.next_u32(), b.next_u32())

    def test_known_values(self):
        ctx = rules.DamageCtx(10, 1, 3, 5, 5)
        self.assertEqual(rules.preview_damage(ctx), rules.DamagePreview(10, 20, 30))
        # Luck widens the ceiling (double) and lifts the expectation by L/24.
        ctx = rules.DamageCtx(24, 1, 1, 0, 0, luck=3)
        self.assertEqual(rules.preview_damage(ctx), rules.DamagePreview(24, 27, 48))
        # Bad luck lowers the floor (halved after the floor).
        ctx = rules.DamageCtx(24, 1, 1, 0, 0, luck=-3, bad_luck=True)
        self.assertEqual(rules.preview_damage(ctx), rules.DamagePreview(12, 22, 24))
        self.assertEqual(rules.damage_range(24, 1, 1, 0, 0, luck=3), (24, 48))

    def test_actual_seed_needs_rng(self):
        with self.assertRaises(ValueError):
            rules.resolve_damage(rules.DamageCtx(1, 1, 1, 0, 0), rules.RollPolicy.ACTUAL_SEED)
        with self.assertRaises(ValueError):
            rules.resolve_damage(rules.DamageCtx(1, 1, 1, 0, 0, ranged=True,
                                                 melee_penalty=True),
                                 rules.RollPolicy.PESSIMAL)

    def test_no_floats(self):
        r = random.Random(8)
        for _ in range(200):
            p = rules.preview_damage(random_ctx(r))
            for v in (p.floor, p.expected, p.ceiling):
                self.assertIs(type(v), int)


class ApplyDamageTest(unittest.TestCase):
    def test_partial(self):
        self.assertEqual(rules.apply_damage(10, 10, 10, 25), (8, 5, 2))

    def test_top_creature_wounded(self):
        self.assertEqual(rules.apply_damage(5, 3, 10, 3), (4, 10, 1))
        self.assertEqual(rules.apply_damage(5, 3, 10, 2), (5, 1, 0))

    def test_overkill(self):
        self.assertEqual(rules.apply_damage(3, 7, 10, 1000), (0, 0, 3))
        self.assertEqual(rules.apply_damage(3, 7, 10, 27), (0, 0, 3))

    def test_empty_stack_is_valid(self):
        self.assertEqual(rules.apply_damage(0, 0, 10, 0), (0, 0, 0))
        self.assertEqual(rules.apply_damage(0, 0, 10, 500), (0, 0, 0))
        with self.assertRaises(ValueError):
            rules.apply_damage(0, 3, 10, 5)
        with self.assertRaises(ValueError):
            rules.apply_damage(0, 0, 10, -1)

    def test_zero_and_invalid(self):
        self.assertEqual(rules.apply_damage(4, 6, 6, 0), (4, 6, 0))
        with self.assertRaises(ValueError):
            rules.apply_damage(1, 11, 10, 1)
        with self.assertRaises(ValueError):
            rules.apply_damage(1, 5, 10, -1)

    def test_hp_conserved(self):
        rng = random.Random(99)
        for _ in range(300):
            mx = rng.randint(1, 50)
            c, top = rng.randint(1, 30), rng.randint(1, mx)
            d = rng.randint(0, 2000)
            nc, nt, k = rules.apply_damage(c, top, mx, d)
            before = (c - 1) * mx + top
            after = (nc - 1) * mx + nt if nc else 0
            self.assertEqual(after, max(0, before - d))
            self.assertEqual(k, c - nc)


class LuckMoraleTest(unittest.TestCase):
    def test_luck(self):
        self.assertEqual([rules.luck_chance(x) for x in (-2, 0, 1, 2, 3, 5)],
                         [0, 0, Fraction(1, 24), Fraction(2, 24), Fraction(3, 24),
                          Fraction(3, 24)])

    def test_morale(self):
        self.assertEqual(rules.good_morale_chance(2), Fraction(1, 12))
        self.assertEqual(rules.good_morale_chance(-1), 0)
        self.assertEqual(rules.bad_morale_chance(-3), Fraction(1, 8))
        self.assertEqual(rules.bad_morale_chance(-9), Fraction(1, 8))
        self.assertEqual(rules.bad_morale_chance(1), 0)

    def test_bad_morale_table_parameter(self):
        self.assertEqual(rules.BAD_MORALE_NUMERATORS, (1, 2, 3))
        self.assertEqual([rules.bad_morale_chance(m) for m in (-1, -2, -3, -7)],
                         [Fraction(1, 24), Fraction(2, 24), Fraction(3, 24), Fraction(3, 24)])
        vcmi = rules.VCMI_BAD_MORALE_NUMERATORS
        self.assertEqual(vcmi, (2, 4, 6))
        self.assertEqual([rules.bad_morale_chance(m, vcmi) for m in (-1, -2, -3, 0, 2)],
                         [Fraction(2, 24), Fraction(4, 24), Fraction(6, 24), 0, 0])
        for bad in ((1, 2), (1, 2, 25), (2, 1, 3), (0, 1, "2")):
            with self.assertRaises(ValueError, msg=bad):
                rules.bad_morale_chance(-1, bad)


if __name__ == "__main__":
    unittest.main()
