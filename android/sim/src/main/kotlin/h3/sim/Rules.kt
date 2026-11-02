package h3.sim

/**
 * Battle damage formulas, ported from `tools/h3re/h3re/rules.py` (rules.md 6.5-6.6, ADR-0004).
 *
 * Exact arithmetic only: every value is a [Rational] or a Long, with one floor at the end of each
 * damage pipeline (rules.md 6.6 step 3). No Double, Float or kotlin.math on reals. Each function
 * below keeps the Python function's name and operation order.
 *
 * Balance constants are not in this file (ADR-0004: balance numbers live in the data packs). The caller
 * supplies a [RulesPack] read from `data/rules.json`; the conformance vectors carry the same values.
 */

/** Balance constants of `data/rules.json`, as loaded (fractions exact, tables indexed by skill level). */
class RulesPack(
    val adBonusPerPoint: Rational,
    val adBonusCap: Rational,
    val daPenaltyPerPoint: Rational,
    val daPenaltyCap: Rational,
    val offense: List<Rational>,
    val archery: List<Rational>,
    val armorer: List<Rational>,
    val hateBonus: Rational,
    val luckBonus: Rational,
    val half: Rational,
    val moraleDie: Long,
    val badMoraleNumerators: List<Long>,
    val vcmiBadMoraleNumerators: List<Long>,
) {
    init {
        require(offense.size == 4 && archery.size == 4 && armorer.size == 4) { "skill tables need 4 levels" }
        require(moraleDie > 0L) { "morale_die must be positive" }
    }
}

/**
 * Random draws used by the damage formulas: the same two operations as `Pcg32` in Rng.kt.
 * [Pcg32.asDrawSource] adapts the real generator; tests supply scripted sources.
 */
interface DrawSource {
    /** Inclusive [lo, hi], as `Pcg32.randint`. */
    fun randint(lo: Long, hi: Long): Long

    /** True with probability num/den, as `Pcg32.chance`. */
    fun chance(num: Long, den: Long): Boolean
}

fun Pcg32.asDrawSource(): DrawSource = object : DrawSource {
    override fun randint(lo: Long, hi: Long): Long = this@asDrawSource.randint(lo, hi)
    override fun chance(num: Long, den: Long): Boolean = this@asDrawSource.chance(num, den)
}

/** Roll policies of `resolve_damage` (rules.md 6.6 step 5). */
enum class RollPolicy { ACTUAL_SEED, PESSIMAL, EXPECTED, OPTIMAL }

/** Everything one strike's damage depends on. Mirrors `rules.DamageCtx`. */
data class DamageCtx(
    val count: Long,
    val dmgMin: Long,
    val dmgMax: Long,
    val attack: Long,
    val defense: Long,
    val ranged: Boolean = false,
    val offense: Int = 0,
    val archery: Int = 0,
    val armorer: Int = 0,
    val hates: Boolean = false,
    val rangePenalty: Boolean = false,
    val meleePenalty: Boolean = false,
    val wallPenalty: Boolean = false,
    val luck: Long = 0L,
    val badLuck: Boolean = false,
)

data class DamageResult(val damage: Long, val lucky: Boolean = false, val unlucky: Boolean = false)

data class DamagePreview(val floor: Long, val expected: Long, val ceiling: Long)

/** `attack_defense_factor` result: (increase, reduction). Exactly one is non-zero, or both are zero. */
data class AttackDefenseFactor(val increase: Rational, val reduction: Rational)

class Rules(val pack: RulesPack) {

    fun attackDefenseFactor(attack: Long, defense: Long): AttackDefenseFactor {
        val diff = Math.subtractExact(attack, defense)
        if (diff > 0L) {
            return AttackDefenseFactor(minOf(pack.adBonusPerPoint * Rational.of(diff), pack.adBonusCap), Rational.ZERO)
        }
        if (diff < 0L) {
            return AttackDefenseFactor(Rational.ZERO, minOf(pack.daPenaltyPerPoint * Rational.of(Math.negateExact(diff)), pack.daPenaltyCap))
        }
        return AttackDefenseFactor(Rational.ZERO, Rational.ZERO)
    }

    /**
     * Base damage of a stack (rules.md 6.6 step 1). Draws `min(count, 10)` randints, in order.
     * A non-positive count returns 0 without drawing or checking the range.
     */
    fun baseDamage(count: Long, dmgMin: Long, dmgMax: Long, rng: DrawSource): Long {
        if (count <= 0L) return 0L
        require(0L <= dmgMin && dmgMin <= dmgMax && dmgMax >= 1L) { "need 0 <= dmg_min <= dmg_max and dmg_max >= 1" }
        val rolls = minOf(count, 10L).toInt()
        var total = 0L
        repeat(rolls) { total = Math.addExact(total, rng.randint(dmgMin, dmgMax)) }
        if (count <= 10L) return total
        // Python: (total * count) // 10
        return Math.floorDiv(Math.multiplyExact(total, count), 10L)
    }

    /** Final damage from a rolled base (rules.md 6.6 steps 2-3). Minimum 1 when base > 0. */
    fun damageFromBase(
        base: Long,
        attack: Long,
        defense: Long,
        ranged: Boolean = false,
        offense: Int = 0,
        archery: Int = 0,
        armorer: Int = 0,
        lucky: Boolean = false,
        hates: Boolean = false,
        rangePenalty: Boolean = false,
        meleePenalty: Boolean = false,
        wallPenalty: Boolean = false,
    ): Long {
        if (base <= 0L) return 0L
        checkFlags(ranged, meleePenalty, rangePenalty, wallPenalty)
        val luckInc = if (lucky) pack.luckBonus else Rational.ZERO
        val dmg = scaled(
            Rational.of(base), attack, defense, ranged, offense, archery, armorer,
            luckInc, hates, rangePenalty, meleePenalty, wallPenalty,
        )
        return maxOf(1L, dmg.floor())
    }

    /**
     * Resolve one strike under [policy] (rules.md 6.6 step 5). ACTUAL_SEED draws from [rng]
     * (luck roll first, then damage rolls); the other policies never touch it.
     */
    fun resolveDamage(ctx: DamageCtx, policy: RollPolicy, rng: DrawSource? = null): DamageResult {
        require(policy != RollPolicy.ACTUAL_SEED || rng != null) { "ACTUAL_SEED needs an rng" }
        checkFlags(ctx.ranged, ctx.meleePenalty, ctx.rangePenalty, ctx.wallPenalty)
        require(ctx.count <= 0L || (0L <= ctx.dmgMin && ctx.dmgMin <= ctx.dmgMax && ctx.dmgMax >= 1L)) {
            "need 0 <= dmg_min <= dmg_max and dmg_max >= 1"
        }

        val good = if (ctx.luck > 0L) luckChance(ctx.luck) else Rational.ZERO
        val bad = if (ctx.luck < 0L && ctx.badLuck) luckChance(-ctx.luck) else Rational.ZERO
        var lucky = false
        var unlucky = false
        val luckInc: Rational
        if (policy == RollPolicy.EXPECTED) {
            luckInc = pack.luckBonus * good
        } else {
            if (ctx.luck > 0L) {
                lucky = settle(good, policy, rng, good = true)
            } else if (ctx.luck < 0L && ctx.badLuck) {
                unlucky = settle(bad, policy, rng, good = false)
            }
            luckInc = if (lucky) pack.luckBonus else Rational.ZERO
        }

        if (ctx.count <= 0L) return DamageResult(0L, lucky, unlucky)

        val base: Rational = when (policy) {
            RollPolicy.ACTUAL_SEED -> Rational.of(baseDamage(ctx.count, ctx.dmgMin, ctx.dmgMax, checkNotNull(rng)))
            RollPolicy.PESSIMAL -> Rational.of(Math.multiplyExact(ctx.count, ctx.dmgMin))
            RollPolicy.OPTIMAL -> Rational.of(Math.multiplyExact(ctx.count, ctx.dmgMax))
            RollPolicy.EXPECTED -> Rational.of(Math.multiplyExact(ctx.count, Math.addExact(ctx.dmgMin, ctx.dmgMax)), 2L)
        }

        var dmg = scaled(
            base, ctx.attack, ctx.defense, ctx.ranged, ctx.offense, ctx.archery, ctx.armorer,
            luckInc, ctx.hates, ctx.rangePenalty, ctx.meleePenalty, ctx.wallPenalty,
        )
        if (policy == RollPolicy.EXPECTED) {
            // Bad luck is the factor 1 - P(bad) / 2, applied before the single floor.
            dmg = dmg * (Rational.ONE - bad * pack.half)
            return DamageResult(maxOf(1L, dmg.floor()))
        }
        var out = maxOf(1L, dmg.floor())
        if (unlucky) out = maxOf(1L, Math.floorDiv(out, 2L))
        return DamageResult(out, lucky, unlucky)
    }

    /** floor / expected / ceiling: the PESSIMAL, EXPECTED and OPTIMAL policies. Consumes no RNG. */
    fun previewDamage(ctx: DamageCtx): DamagePreview = DamagePreview(
        resolveDamage(ctx, RollPolicy.PESSIMAL).damage,
        resolveDamage(ctx, RollPolicy.EXPECTED).damage,
        resolveDamage(ctx, RollPolicy.OPTIMAL).damage,
    )

    /** Chance of good luck (double damage): L / die for L in 1..3 (rules.md 6.5). */
    fun luckChance(luck: Long): Rational = Rational.of(maxOf(0L, clamp3(luck)), pack.moraleDie)

    /** Chance of an extra action: M / die for M in 1..3. */
    fun goodMoraleChance(morale: Long): Rational = Rational.of(maxOf(0L, clamp3(morale)), pack.moraleDie)

    /** Chance of losing the turn for M in -3..-1. `table[i]` is the numerator for morale -(i+1). */
    fun badMoraleChance(morale: Long, table: List<Long> = pack.badMoraleNumerators): Rational {
        val m = -clamp3(morale)
        if (m <= 0L) return Rational.ZERO
        checkBadMoraleTable(table)
        return Rational.of(table[(m - 1L).toInt()], pack.moraleDie)
    }

    private fun checkBadMoraleTable(table: List<Long>) {
        require(table.size == 3 && table.all { it in 0L..pack.moraleDie }) {
            "bad_morale_table needs 3 integers in 0..${pack.moraleDie}"
        }
        require(table.zipWithNext().all { (a, b) -> a <= b }) { "bad_morale_table must be non-decreasing" }
    }

    private fun skill(table: List<Rational>, level: Int): Rational {
        require(level in 0..3) { "skill level must be 0..3, got $level" }
        return table[level]
    }

    /** Exact (unfloored) damage for [base]. [luckInc] is in [0, 1]. Python `_scaled`. */
    private fun scaled(
        base: Rational,
        attack: Long,
        defense: Long,
        ranged: Boolean,
        offense: Int,
        archery: Int,
        armorer: Int,
        luckInc: Rational,
        hates: Boolean,
        rangePenalty: Boolean,
        meleePenalty: Boolean,
        wallPenalty: Boolean,
    ): Rational {
        val f = attackDefenseFactor(attack, defense)
        var inc = f.increase + (if (ranged) skill(pack.archery, archery) else skill(pack.offense, offense))
        inc = inc + luckInc
        if (hates) inc = inc + pack.hateBonus

        var dmg = base * (Rational.ONE + inc)
        dmg = dmg * (Rational.ONE - f.reduction)
        dmg = dmg * (Rational.ONE - skill(pack.armorer, armorer))
        if (rangePenalty) dmg = dmg * (Rational.ONE - pack.half)
        if (wallPenalty) dmg = dmg * (Rational.ONE - pack.half)
        if (meleePenalty) dmg = dmg * (Rational.ONE - pack.half)
        return dmg
    }

    /** Python `_settle`: a luck-type event. [good] says whether it raises damage. */
    private fun settle(chance: Rational, policy: RollPolicy, rng: DrawSource?, good: Boolean): Boolean = when (policy) {
        RollPolicy.ACTUAL_SEED -> checkNotNull(rng).chance(chance.numerator, chance.denominator)
        RollPolicy.OPTIMAL -> if (good) chance > Rational.ZERO else chance >= Rational.ONE
        else -> if (good) chance >= Rational.ONE else chance > Rational.ZERO
    }

    private fun checkFlags(ranged: Boolean, meleePenalty: Boolean, rangePenalty: Boolean, wallPenalty: Boolean) {
        require(!(ranged && meleePenalty)) { "melee_penalty applies only to melee attacks" }
        require(!(!ranged && (rangePenalty || wallPenalty))) { "range/wall penalty applies only to ranged attacks" }
    }

    private fun clamp3(v: Long): Long = maxOf(-3L, minOf(3L, v))
}
