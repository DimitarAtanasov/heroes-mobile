package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * Owner decision 2026-11-02: a creature with dmg_min 0 and dmg_max >= 1 is a valid weak unit.
 * Synthetic data only. Mirrors `WeakUnitDamageTest` in tools/h3re/tests/test_battle.py, with the
 * same seed (0x5EED, sequence 7).
 */
class WeakUnitDamageTest {
    private val packs = ReplayVectors.packs
    private val engine = BattleEngine(packs)
    private fun gen() = Pcg32(0x5EEDUL, 7UL)

    private fun scenario(lo: Int, hi: Int): String =
        """{"battle_id":"w","creatures":{
            "weak":{"attack":5,"defense":5,"dmg_min":$lo,"dmg_max":$hi,"hp":10,"speed":5},
            "tough":{"attack":5,"defense":5,"dmg_min":1,"dmg_max":1,"hp":1000,"speed":4}},
            "attackers":[{"creature":"weak","count":1,"pos":[7,5]}],
            "defenders":[{"creature":"tough","count":5,"pos":[8,5]}]}"""

    @Test
    fun baseRollSpansZeroToMax() {
        val g = gen().asDrawSource()
        val rules = engine.battle.rules
        val rolls = List(200) { rules.baseDamage(1, 0, 3, g) }
        assertEquals(listOf(3L, 1L, 3L, 2L, 0L, 2L, 0L, 3L, 1L, 1L, 2L, 2L), rolls.take(12))
        assertTrue(rolls.all { it in 0L..3L })
        assertEquals(setOf(0L, 1L, 2L, 3L), rolls.toSet())
    }

    @Test
    fun finalDamageKeepsTheMinimumOfOne() {
        val g = gen().asDrawSource()
        val rules = engine.battle.rules
        val ctx = DamageCtx(1, 0, 3, 0, 0)
        val out = List(200) { rules.resolveDamage(ctx, RollPolicy.ACTUAL_SEED, g).damage }
        assertEquals(listOf(3L, 1L, 3L, 2L, 1L, 2L, 1L, 3L, 1L, 1L, 2L, 2L), out.take(12))
        assertTrue(out.all { it in 1L..3L })
    }

    @Test
    fun battleWithAWeakUnitResolves() {
        var st = Scenario.parse(scenario(0, 3), packs)
        assertEquals(0, st.stacks[0].creature.dmgMin)
        val g = gen().asDrawSource()
        st = engine.battle.apply(st, BattleCommand.Begin, g).state
        val hits = ArrayList<Long>()
        repeat(20) {
            if (st.winner != null) return@repeat
            val att = checkNotNull(st.active)
            val tgt = st.stacks.first { it.side != st.stacks[att].side && it.count > 0 }.id
            val r = engine.battle.apply(st, BattleCommand.Attack(att, tgt), g)
            st = r.state
            for (e in r.events) if (e is BattleEvent.DamageDealt && e.attacker == 0) hits.add(e.damage)
        }
        assertTrue(hits.isNotEmpty())
        assertTrue(hits.all { it in 1L..3L }, "$hits")
    }

    @Test
    fun badRangesAreStillRefused() {
        val rules = engine.battle.rules
        for ((lo, hi) in listOf(-1 to 3, 4 to 3, 0 to 0, 0 to -1)) {
            assertFailsWith<IllegalArgumentException>("scenario $lo..$hi") { Scenario.parse(scenario(lo, hi), packs) }
            assertFailsWith<IllegalArgumentException>("base $lo..$hi") {
                rules.baseDamage(5, lo.toLong(), hi.toLong(), gen().asDrawSource())
            }
            assertFailsWith<IllegalArgumentException>("resolve $lo..$hi") {
                rules.resolveDamage(DamageCtx(5, lo.toLong(), hi.toLong(), 0, 0), RollPolicy.PESSIMAL)
            }
        }
        val good = Scenario.parse(scenario(0, 3), packs)
        for (v in listOf(-1, 4)) {
            val stacks = good.stacks.mapIndexed { i, s -> if (i == 0) s.copy(creature = s.creature.copy(dmgMin = v)) else s }
            assertFailsWith<IllegalArgumentException>("check_state dmg_min=$v") { BattleCodec.checkState(good.copy(stacks = stacks)) }
        }
        BattleCodec.checkState(good)
    }
}
