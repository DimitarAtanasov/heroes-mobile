package h3.sim.encounter

import h3.sim.AdvArmySlot
import h3.sim.AdventureCommand
import h3.sim.AdventureEvent
import h3.sim.AdventureState
import h3.sim.Adventure
import h3.sim.AdventureCodec
import h3.sim.BattleCommand
import h3.sim.BattleCreature
import h3.sim.BattleEvent
import h3.sim.IllegalCommand
import h3.sim.Pcg32
import h3.sim.asDrawSource
import h3.sim.DrawSource
import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/** Hand-written checks of the encounter module (the vectors are in [EncounterConformanceTest]). */
class EncounterTest {
    private val engine = EncVectors.engine
    private val codec = EncVectors.codec
    private val adv = EncVectors.adventure
    private val seed = BigInteger.valueOf(2026)

    private fun golden(): AdventureState =
        EncVectors.parse(EncVectors.cases.first { it["name"] == "golden" }["initial"].let { (it as Map<*, *>)["canonical"] as String })

    private fun started(): AdventureState = adv.apply(golden(), AdventureCommand.Begin, null).state

    private fun step(s: AdventureState, c: AdventureCommand): Pair<AdventureState, List<AdventureEvent>> {
        val r = adv.apply(s, c, engine.streamFor(seed, s, c))
        return Pair(r.state, r.events)
    }

    private fun draw(name: String): AdventureState {
        val case = EncVectors.cases.first { it["name"] == name }
        return EncVectors.parse((case["initial"] as Map<*, *>)["canonical"] as String)
    }

    private fun refused(s: AdventureState, c: AdventureCommand, msg: String) {
        val g = engine.streamFor(seed, s, c)
        val fresh = EncVectors.pos(engine.streamFor(seed, s, c))
        val canon = codec.canonicalText(s)
        val e = assertFailsWith<IllegalCommand>("$c") { adv.apply(s, c, g) }
        assertEquals(msg, e.message, "$c")
        assertEquals(fresh, EncVectors.pos(g), "$c")
        assertEquals(canon, codec.canonicalText(s), "$c")
    }

    @Test
    fun illFormedFieldsAreRefusedBeforeAnyDraw() {
        val s = started()
        val bad = "target must be a hero id or a guard id"
        refused(s, AdventureCommand.Attack(0, null), bad)
        refused(s, AdventureCommand.Attack(0, true), bad)
        refused(s, AdventureCommand.Attack(0, 2.0), bad)
        refused(s, AdventureCommand.Attack(0, 2L), bad)
        refused(s, AdventureCommand.Attack(0, listOf("wolves")), bad)
        refused(s, AdventureCommand.Attack(null, "wolves"), "no such hero")
        refused(s, AdventureCommand.Attack(-1, "wolves"), "no such hero")
        refused(s, AdventureCommand.Attack(4, "wolves"), "no such hero")
        refused(s, AdventureCommand.Attack(0, -1), "no such target hero")
        refused(s, AdventureCommand.Attack(0, 0), "no such target hero")
        refused(s, AdventureCommand.Attack(0, 4), "no such target hero")
        refused(s, AdventureCommand.Attack(0, 1), "cannot attack an own hero")
        refused(s, AdventureCommand.Attack(0, 2), "target is not next to the hero")
        refused(s, AdventureCommand.Attack(2, "wolves"), "hero does not belong to the current player")
        refused(s, AdventureCommand.Attack(0, "camp"), "target is not next to the hero")
        refused(s, AdventureCommand.Attack(0, "zzz"), "no such guard")
        refused(golden(), AdventureCommand.Attack(0, "wolves"), "game not started")
    }

    @Test
    fun theCommandParserReadsAttack() {
        fun parse(hero: Any?, target: Any?) = AdventureCodec.parseCommand(mapOf("type" to "Attack", "hero" to hero, "target" to target))
        assertEquals(AdventureCommand.Attack(0, "g"), parse(BigInteger.ZERO, "g"))
        assertEquals(AdventureCommand.Attack(3, 2), parse(BigInteger.valueOf(3), BigInteger.TWO))
        assertEquals(AdventureCommand.Attack(null, null), parse(true, false))
        assertEquals(AdventureCommand.Attack(null, null), parse("0", listOf(BigInteger.ONE)))
        assertEquals(AdventureCommand.Attack(null, -1), parse(BigInteger.TWO.pow(40), BigInteger.TWO.pow(40)))
        assertEquals(AdventureCommand.Attack(null, null), parse(java.lang.Double.valueOf("0"), java.lang.Double.valueOf("1")))
        assertFailsWith<IllegalArgumentException> { AdventureCodec.parseCommand(mapOf("type" to "Attack", "hero" to BigInteger.ZERO)) }
        val c = AdventureCommand.Attack(1, "x")
        assertEquals(c, AdventureCodec.parseCommand(AdventureCodec.commandToMap(c)))
    }

    @Test
    fun withoutTheHooksTheAdventureCoreStillRefusesCleanly() {
        val plainRules = EncVectors.rules
        val noHooks = Adventure(plainRules)
        val s = started()
        // an encounter setup needs the hooks to be parsed at all
        val text = codec.canonicalText(s)
        val e = assertFailsWith<IllegalArgumentException> { AdventureCodec(plainRules).parseState(h3.sim.MiniJson.parse(text)) }
        assertEquals("state: encounters are not ported (encounter.md)", e.message)
        // a state with a setup, but an engine-less core: a configuration error, not an IllegalCommand
        assertFailsWith<IllegalStateException> { noHooks.apply(s, AdventureCommand.Attack(0, "wolves"), null) }
        // a state without a setup is refused as in Python
        val plain = s.copy(encounter = null)
        val r = assertFailsWith<IllegalCommand> { noHooks.apply(plain, AdventureCommand.Attack(0, "wolves"), null) }
        assertEquals("battles are not enabled in this game", r.message)
        val r2 = assertFailsWith<IllegalCommand> { adv.apply(plain, AdventureCommand.Attack(0, "wolves"), null) }
        assertEquals("battles are not enabled in this game", r2.message)
        assertEquals(codec.stateHash(plain.copy(encounter = s.encounter)), codec.stateHash(s))
        assertNotEquals(codec.stateHash(plain), codec.stateHash(s))
    }

    @Test
    fun aLegalAttackNeedsTheBattleStreamButTheValidationComesFirst() {
        val s = started()
        assertFailsWith<IllegalCommand> { adv.apply(s, AdventureCommand.Attack(0, "nope"), null) }
        val e = assertFailsWith<IllegalArgumentException> { adv.apply(s, AdventureCommand.Attack(0, "wolves"), null) }
        assertTrue(e !is IllegalCommand)
    }

    @Test
    fun theBattleCounterIsCheckedBeforeAnyDraw() {
        val s = started().copy(battles = Int.MAX_VALUE)
        assertEquals("enc:2147483648", engine.battleId(s))
        val c = AdventureCommand.Attack(0, "wolves")
        val g = engine.streamFor(seed, s, c)
        val fresh = EncVectors.pos(engine.streamFor(seed, s, c))
        assertFailsWith<ArithmeticException> { adv.apply(s, c, g) }
        assertEquals(fresh, EncVectors.pos(g))
    }

    @Test
    fun theBattleStreamAndTheLogReplay() {
        var s = started()
        val c = AdventureCommand.Attack(0, "wolves")
        val bs0 = engine.buildBattle(s, c)
        assertEquals("enc:1", bs0.battleId)
        val g = engine.streamFor(seed, s, c)
        val r = adv.apply(s, c, g)
        val f = r.events[0] as BattleFought
        s = r.state
        // replaying the recorded log on a fresh battle stream reproduces the hash and the stream position
        var bs = bs0
        val g2 = engine.battleRng(seed, bs0.battleId)
        for (bc in f.log) bs = engine.battle.apply(bs, bc, g2.asDrawSource()).state
        assertEquals(f.battleHash, engine.battleHash(bs))
        assertEquals(f.winner, bs.winner)
        assertEquals(EncVectors.pos(g), EncVectors.pos(g2))
        assertTrue(f.log.first() is BattleCommand.Begin)
        assertTrue(f.battleEvents.first() is BattleEvent.BattleStarted)
        assertEquals(1, s.battles)
        assertEquals("enc:2", engine.battleId(s))
    }

    @Test
    fun theRoundLimitEndsAStalledBattleWithNoWinner() {
        val s = adv.apply(draw("draw-r3"), AdventureCommand.Begin, null).state
        val c = AdventureCommand.Attack(0, 1)
        val bs = engine.buildBattle(s, c)
        val counting = object : DrawSource {
            var calls = 0
            val inner = engine.battleRng(seed, bs.battleId).asDrawSource()
            override fun randint(lo: Long, hi: Long): Long { calls++; return inner.randint(lo, hi) }
            override fun chance(num: Long, den: Long): Boolean { calls++; return inner.chance(num, den) }
        }
        val fought = engine.fight(bs, counting, 3L)
        assertEquals(null, fought.state.winner)
        assertEquals(4, fought.state.round)
        val r = adv.apply(s, c, engine.streamFor(seed, s, c))
        val f = r.events[0] as BattleFought
        assertEquals(1, r.events.size)
        assertEquals(null, f.winner)
        assertEquals(3L, f.rounds)
        assertEquals(s.heroes, r.state.heroes)
        assertEquals(1, r.state.battles)
        assertEquals("draw:2", engine.battleId(r.state))
        // a larger limit only lets the battle run longer
        val longer = engine.fight(bs, engine.battleRng(seed, bs.battleId).asDrawSource(), 7L)
        assertEquals(8, longer.state.round)
    }

    @Test
    fun survivorsKeepTheirSlotOrderAndDeadSlotsDrop() {
        val s = started()
        val bs = engine.buildBattle(s, AdventureCommand.Attack(0, "wolves"))
        val army = s.heroes[0].army
        assertEquals(army, engine.survivors(army, bs, 0))
        val dead = bs.copy(stacks = bs.stacks.map { if (it.side == 0 && it.slot == 0) it.copy(count = 0, topHp = 0) else if (it.side == 0) it.copy(count = 7) else it })
        assertEquals(listOf(AdvArmySlot("archer", 4, 7)), engine.survivors(army, dead, 0))
    }

    @Test
    fun setupAndPolicyChecks() {
        val bp = engine.battleCodec.pack.defaultPolicy()
        fun cr(n: String) = BattleCreature(n, 1, 1, 1, 2, 5, 3)
        val a = EncounterSetup.of(listOf(cr("b"), cr("a"), cr("￿"), cr("😀")), EncounterPolicy("removed", "by_count", 100), bp, "h")
        assertEquals(listOf("a", "b", "￿", "😀"), a.creatures.map { it.name })   // code point order, not UTF-16
        assertEquals(a, EncounterSetup.of(a.creatures.reversed(), a.policy, bp, "h"))
        assertEquals("duplicate creature name", assertFailsWith<IllegalArgumentException> { EncounterSetup.of(listOf(cr("a"), cr("a")), a.policy, bp, "h") }.message)
        assertEquals("bad loser_fate", assertFailsWith<IllegalArgumentException> { EncounterPolicy("x", "by_count", 1) }.message)
        assertEquals("bad slot_mapping", assertFailsWith<IllegalArgumentException> { EncounterPolicy("removed", "x", 1) }.message)
        assertEquals("round_limit must be an int >= 1", assertFailsWith<IllegalArgumentException> { EncounterPolicy("removed", "by_count", 0) }.message)
        assertEquals(Long.MAX_VALUE, EncounterPolicy("removed", "by_count", Long.MAX_VALUE).roundLimit)
    }

    @Test
    fun aRemovedHeroLeavesTheMapAndCannotBeAttacked() {
        val c = EncVectors.cases.first { it["name"] == "golden" }
        var s = started()
        val script = (c["steps"] as List<*>).drop(1).take(4).map { EncVectors.cmd((it as Map<*, *>)["command"]) }
        for (cmd in script) s = step(s, cmd).first
        val h = s.heroes[1]
        assertEquals(null, h.pos)
        assertEquals(emptyList<AdvArmySlot>(), h.army)
        assertEquals(0, h.mp)
        assertEquals(0, h.mpMax)
        assertTrue(adv.reachable(s, 1).isEmpty())
        assertEquals(null, adv.findPath(s, 1, Pair(0, 0)))
        refused(s.copy(current = 0), AdventureCommand.Attack(1, 2), "hero is not on the map")
        val p1 = s.copy(current = 1)
        refused(p1, AdventureCommand.Attack(2, 1), "target hero is not on the map")
    }

    @Test
    fun winnerTakesTheTileMovesTheAttackerWithoutCost() {
        val wtt = EncVectors.cases.first { it["name"] == "golden-wtt-script" }
        var s = EncVectors.parse((wtt["initial"] as Map<*, *>)["canonical"] as String)
        s = step(s, AdventureCommand.Begin).first
        val (s2, ev) = step(s, AdventureCommand.Attack(0, "wolves"))
        assertEquals(Pair(2, 1), s2.heroes[0].pos)
        assertEquals(AdventureEvent.HeroMoved(0, listOf(Pair(1, 1), Pair(2, 1)), 0, s.heroes[0].mp), ev.last())
        assertEquals(s.heroes[0].mp, s2.heroes[0].mp)
        assertTrue(s2.guards.none { it.id == "wolves" })
    }

    @Test
    fun eventsDescribeTheChangeAndDoNotMutateState() {
        val s = started()
        val c = AdventureCommand.Attack(0, "wolves")
        val (s2, ev) = step(s, c)
        val f = ev[0] as BattleFought
        val m = f.toMap()
        assertEquals(setOf("type", "battle_id", "attacker", "target", "winner", "rounds", "log", "battle_events", "battle_hash"), m.keys)
        assertEquals("wolves", m["target"])
        assertTrue(ev.drop(1).all { it is ArmyChanged || it is HeroDefeated || it is GuardDefeated })
        assertEquals(mapOf("type" to "GuardDefeated", "guard" to "wolves"), GuardDefeated("wolves").toMap())
        assertEquals(mapOf("type" to "HeroDefeated", "hero" to 3), HeroDefeated(3).toMap())
        assertEquals(codec.stateHash(s), codec.stateHash(started()))   // the input state is unchanged
        assertNotEquals(codec.stateHash(s), codec.stateHash(s2))
    }

    @Test
    fun seedsBeyondLongAreAccepted() {
        val s = started()
        val big = BigInteger.TWO.pow(70).add(BigInteger.valueOf(3))
        val a = engine.battleRng(big, "enc:1")
        val b = engine.battleRng(big, "enc:1")
        assertEquals(a.nextU32(), b.nextU32())
        assertEquals(EncVectors.pos(engine.streamFor(5L, s, AdventureCommand.Attack(0, "wolves"))), EncVectors.pos(engine.battleRng(5L, "enc:1")))
        assertEquals(EncVectors.pos(engine.encounterRng(BigInteger.valueOf(5), s)), EncVectors.pos(engine.battleRng(BigInteger.valueOf(5), "enc:1")))
        assertNotEquals(EncVectors.pos(engine.battleRng(BigInteger.valueOf(5), "enc:1")), EncVectors.pos(engine.battleRng(BigInteger.valueOf(6), "enc:1")))
        assertEquals(Pcg32::class, engine.battleRng(1L, "x")::class)
    }
}
