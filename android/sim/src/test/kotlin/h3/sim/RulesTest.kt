package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

private val RULES_DOC by lazy { loadVector("rules.json") }

private fun Any?.rat(): Rational {
    val l = list()
    return Rational.of(l[0].big().toLong(), l[1].big().toLong())
}

private fun Map<String, Any?>.long(k: String): Long = this[k].big().toLong()
private fun Map<String, Any?>.int(k: String): Int = this[k].big().toInt()
private fun Map<String, Any?>.bool(k: String): Boolean = this[k] as Boolean
private fun Map<String, Any?>.isError(): Boolean = this["error"] == true
private fun Any?.longs(): List<Long> = list().map { it.big().toLong() }

/** The pack exactly as `rules.json` carries it (exported from rules.py as loaded). */
private fun loadPack(): RulesPack {
    val p = RULES_DOC["pack"].obj()
    fun table(k: String): List<Rational> = p[k].list().map { it.rat() }
    return RulesPack(
        adBonusPerPoint = p["ad_bonus_per_point"].rat(),
        adBonusCap = p["ad_bonus_cap"].rat(),
        daPenaltyPerPoint = p["da_penalty_per_point"].rat(),
        daPenaltyCap = p["da_penalty_cap"].rat(),
        offense = table("offense"),
        archery = table("archery"),
        armorer = table("armorer"),
        hateBonus = p["hate_bonus"].rat(),
        luckBonus = p["luck_bonus"].rat(),
        half = p["half"].rat(),
        moraleDie = p["morale_die"].big().toLong(),
        badMoraleNumerators = p["bad_morale_numerators"].longs(),
        vcmiBadMoraleNumerators = p["vcmi_bad_morale_numerators"].longs(),
    )
}

private fun ctxOf(m: Map<String, Any?>) = DamageCtx(
    count = m.long("count"),
    dmgMin = m.long("dmg_min"),
    dmgMax = m.long("dmg_max"),
    attack = m.long("attack"),
    defense = m.long("defense"),
    ranged = m.bool("ranged"),
    offense = m.int("offense"),
    archery = m.int("archery"),
    armorer = m.int("armorer"),
    hates = m.bool("hates"),
    rangePenalty = m.bool("range_penalty"),
    meleePenalty = m.bool("melee_penalty"),
    wallPenalty = m.bool("wall_penalty"),
    luck = m.long("luck"),
    badLuck = m.bool("bad_luck"),
)

/** Replays scripted randint results; checks each against its bounds and that all are used. */
private class Scripted(private val rolls: List<Long>) : DrawSource {
    private var i = 0

    override fun randint(lo: Long, hi: Long): Long {
        check(i < rolls.size) { "script exhausted" }
        val v = rolls[i++]
        check(v in lo..hi) { "scripted roll $v outside $lo..$hi" }
        return v
    }

    override fun chance(num: Long, den: Long): Boolean = error("base_damage must not draw a chance")

    fun assertFinished() = assertEquals(rolls.size, i, "unused scripted rolls")
}

class RulesTest {
    private val rules = Rules(loadPack())

    private fun section(name: String): List<Any?> = RULES_DOC[name].list()

    @Test
    fun vectorSectionsAreNonEmptyAndLargeEnough() {
        val names = listOf(
            "attack_defense", "base_damage", "damage_from_base", "resolve", "resolve_seeded",
            "preview", "luck_chance", "good_morale_chance", "bad_morale_chance", "penalties",
        )
        val total = names.sumOf { section(it).size }
        assertTrue(total >= 300, "only $total rules vectors")
        for (n in names) assertTrue(section(n).isNotEmpty(), n)
    }

    @Test
    fun attackDefenseFactorMatchesPython() {
        for (c in section("attack_defense")) {
            val o = c.obj()
            val f = rules.attackDefenseFactor(o.long("attack"), o.long("defense"))
            val label = "attack ${o["attack"]} defense ${o["defense"]}"
            assertEquals(o["inc"].rat(), f.increase, label)
            assertEquals(o["red"].rat(), f.reduction, label)
        }
    }

    @Test
    fun baseDamageWithScriptedRollsMatchesPython() {
        for (c in section("base_damage")) {
            val o = c.obj()
            val count = o.long("count")
            val lo = o.long("dmg_min")
            val hi = o.long("dmg_max")
            val rolls = o["rolls"].longs()
            val label = "count $count range $lo..$hi"
            if (o.isError()) {
                assertFailsWith<IllegalArgumentException>(label) { rules.baseDamage(count, lo, hi, Scripted(rolls)) }
            } else {
                val src = Scripted(rolls)
                assertEquals(o["out"].big().toLong(), rules.baseDamage(count, lo, hi, src), label)
                src.assertFinished()
            }
        }
    }

    @Test
    fun damageFromBaseMatchesPython() {
        for (c in section("damage_from_base")) {
            val o = c.obj()
            val call = {
                rules.damageFromBase(
                    base = o.long("base"),
                    attack = o.long("attack"),
                    defense = o.long("defense"),
                    ranged = o.bool("ranged"),
                    offense = o.int("offense"),
                    archery = o.int("archery"),
                    armorer = o.int("armorer"),
                    lucky = o.bool("lucky"),
                    hates = o.bool("hates"),
                    rangePenalty = o.bool("range_penalty"),
                    meleePenalty = o.bool("melee_penalty"),
                    wallPenalty = o.bool("wall_penalty"),
                )
            }
            val label = o.toString()
            if (o.isError()) assertFailsWith<IllegalArgumentException>(label) { call() }
            else assertEquals(o["out"].big().toLong(), call(), label)
        }
    }

    @Test
    fun deterministicPoliciesMatchPython() {
        for (c in section("resolve")) {
            val o = c.obj()
            val ctx = ctxOf(o["ctx"].obj())
            val policy = RollPolicy.valueOf(o["policy"] as String)
            val label = "${o["policy"]} ${o["ctx"]}"
            if (o.isError()) {
                assertFailsWith<IllegalArgumentException>(label) { rules.resolveDamage(ctx, policy) }
                continue
            }
            val r = rules.resolveDamage(ctx, policy)
            assertEquals(o.long("damage"), r.damage, label)
            assertEquals(o.bool("lucky"), r.lucky, label)
            assertEquals(o.bool("unlucky"), r.unlucky, label)
        }
    }

    @Test
    fun actualSeedDrawsMatchPythonDrawForDraw() {
        for (c in section("resolve_seeded")) {
            val o = c.obj()
            val ctx = ctxOf(o["ctx"].obj())
            val g = Pcg32(o["seed"].u64(), o["seq"].u64())
            val label = "seed ${o["seed"]} seq ${o["seq"]} ${o["ctx"]}"
            if (o.isError()) {
                assertFailsWith<IllegalArgumentException>(label) {
                    rules.resolveDamage(ctx, RollPolicy.ACTUAL_SEED, g.asDrawSource())
                }
                continue
            }
            val r = rules.resolveDamage(ctx, RollPolicy.ACTUAL_SEED, g.asDrawSource())
            assertEquals(o.long("damage"), r.damage, label)
            assertEquals(o.bool("lucky"), r.lucky, label)
            assertEquals(o.bool("unlucky"), r.unlucky, label)
            assertEquals(o["state_after"].u64(), g.state, "$label: generator state after strike")
        }
    }

    @Test
    fun previewFloorExpectedCeilingMatchPython() {
        for (c in section("preview")) {
            val o = c.obj()
            val p = rules.previewDamage(ctxOf(o["ctx"].obj()))
            val label = o["ctx"].toString()
            assertEquals(o.long("floor"), p.floor, label)
            assertEquals(o.long("expected"), p.expected, label)
            assertEquals(o.long("ceiling"), p.ceiling, label)
        }
    }

    @Test
    fun luckAndMoraleChancesMatchPython() {
        for (c in section("luck_chance")) {
            val o = c.obj()
            assertEquals(o["out"].rat(), rules.luckChance(o.long("luck")), "luck ${o["luck"]}")
        }
        for (c in section("good_morale_chance")) {
            val o = c.obj()
            assertEquals(o["out"].rat(), rules.goodMoraleChance(o.long("morale")), "morale ${o["morale"]}")
        }
        for (c in section("bad_morale_chance")) {
            val o = c.obj()
            val label = "morale ${o["morale"]} table ${o["table"]}"
            val table = o["table"].longs()
            if (o.isError()) {
                assertFailsWith<IllegalArgumentException>(label) { rules.badMoraleChance(o.long("morale"), table) }
            } else {
                assertEquals(o["out"].rat(), rules.badMoraleChance(o.long("morale"), table), label)
            }
        }
    }

    @Test
    fun rangeWallAndMeleePenaltyMultiplicationsMatchPython() {
        for (c in section("penalties")) {
            val o = c.obj()
            val got = rules.damageFromBase(
                base = o.long("base"),
                attack = 0,
                defense = 0,
                ranged = o.bool("ranged"),
                rangePenalty = o.bool("range_penalty"),
                wallPenalty = o.bool("wall_penalty"),
                meleePenalty = o.bool("melee_penalty"),
            )
            assertEquals(o.long("out"), got, o.toString())
        }
    }

    @Test
    fun wallAndRangeStackMultiplicatively() {
        // A long shot over a wall deals one quarter (rules.md 6.6, VCMI #11).
        assertEquals(250L, rules.damageFromBase(1000, 0, 0, ranged = true, rangePenalty = true, wallPenalty = true))
    }

    @Test
    fun rejectsFlagCombinationsAndBadRanges() {
        assertFailsWith<IllegalArgumentException> {
            rules.damageFromBase(10, 0, 0, ranged = true, meleePenalty = true)
        }
        assertFailsWith<IllegalArgumentException> { rules.damageFromBase(10, 0, 0, rangePenalty = true) }
        assertFailsWith<IllegalArgumentException> { rules.baseDamage(5, 0, 3, Scripted(emptyList())) }
        assertFailsWith<IllegalArgumentException> { rules.baseDamage(5, 4, 3, Scripted(emptyList())) }
        assertFailsWith<IllegalArgumentException> {
            rules.resolveDamage(DamageCtx(1, 1, 1, 0, 0, archery = 4, ranged = true), RollPolicy.PESSIMAL)
        }
        assertFailsWith<IllegalArgumentException> {
            rules.resolveDamage(DamageCtx(1, 1, 1, 0, 0), RollPolicy.ACTUAL_SEED, null)
        }
    }
}

class RationalTest {
    private fun r(n: Long, d: Long = 1L) = Rational.of(n, d)

    @Test
    fun normalizesByGcdAndSign() {
        assertEquals("1/2", r(2, 4).toString())
        assertEquals("-1/2", r(1, -2).toString())
        assertEquals("-1/2", r(-2, 4).toString())
        assertEquals("0/1", r(0, -7).toString())
        assertEquals(Rational.ZERO, r(0, 7))
        assertEquals(Rational.ONE, r(-9, -9))
    }

    @Test
    fun arithmeticIsExact() {
        assertEquals(r(5, 6), r(1, 2) + r(1, 3))
        assertEquals(r(1, 6), r(1, 2) - r(1, 3))
        assertEquals(r(1, 6), r(1, 2) * r(1, 3))
        assertEquals(r(3, 2), r(1, 2) / r(1, 3))
        assertEquals(r(-1, 4), r(-1, 2) * r(1, 2))
        assertEquals(r(1, 40), r(1, 20) * r(1, 2))
        assertEquals(Rational.ZERO, r(3, 4) - r(3, 4))
        assertEquals(r(7, 4), r(3, 4).add(r(1, 1)))
        assertEquals(r(1, 4), r(3, 4).sub(r(1, 2)))
        assertEquals(r(3, 8), r(3, 4).mul(r(1, 2)))
    }

    @Test
    fun divisionByZeroThrows() {
        assertFailsWith<ArithmeticException> { r(1, 2) / Rational.ZERO }
        assertFailsWith<ArithmeticException> { r(1, 0) }
    }

    @Test
    fun compareOrdersByValue() {
        assertTrue(r(1, 3) < r(1, 2))
        assertTrue(r(-1, 2) < r(-1, 3))
        assertEquals(0, r(2, 4).compareTo(r(1, 2)))
        assertEquals(r(1, 2), r(2, 4))
    }

    @Test
    fun floorRoundsTowardNegativeInfinity() {
        assertEquals(0L, r(1, 3).floor())
        assertEquals(-1L, r(-1, 3).floor())
        assertEquals(-1L, r(-1, 2).floor())
        assertEquals(3L, r(7, 2).floor())
        assertEquals(-4L, r(-7, 2).floor())
        assertEquals(5L, r(5, 1).floor())
    }

    @Test
    fun crossReductionKeepsLargeProductsExact() {
        assertEquals(Rational.ONE, r(1L shl 40, 3) * r(3, 1L shl 40))
    }

    @Test
    fun overflowThrowsInsteadOfWrapping() {
        assertFailsWith<ArithmeticException> { r(Long.MAX_VALUE) * r(2) }
        assertFailsWith<ArithmeticException> { r(Long.MAX_VALUE) + r(1) }
        assertFailsWith<ArithmeticException> { r(1, Long.MAX_VALUE) + r(1, Long.MAX_VALUE - 1) }
    }
}
