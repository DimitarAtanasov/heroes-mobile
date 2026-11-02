package h3.presenter.ui

import h3.presenter.Fixture
import h3.sim.BattleCommand
import h3.sim.BattleCreature
import h3.sim.BattleEvent
import h3.sim.BattleStack
import h3.sim.BattleState
import h3.sim.RngStreams
import h3.sim.asDrawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

class BattleLogTest {
    private fun creature(name: String) = BattleCreature(name, 5, 5, 1, 3, 10, 5)

    private fun stack(id: Int, side: Int, name: String, count: Int = 5) =
        BattleStack(id, side, id, creature(name), count, 10, Pair(1 + id, 2), 0, 1, false, 0, 0)

    /** Stack 0 = attacker Test Pikeman, 1 = defender Test Imp, 2 = defender Griffin (no prefix). */
    private val st: BattleState = Fixture.games[0].initial.copy(
        stacks = listOf(stack(0, 0, "Test Pikeman"), stack(1, 1, "Test Imp"), stack(2, 1, "Griffin")),
        round = 1, started = true, active = 0, done = emptyList(), waited = emptyList(), winner = null,
    )

    private fun one(e: BattleEvent, round: Int = 3) = BattleLog.describe(st, e, round)

    @Test
    fun hit_namesBothCreaturesAndSides() {
        val l = one(BattleEvent.DamageDealt(0, 1, 12, 2, ranged = false, retaliation = false))!!
        assertEquals("Attacker Pikeman hits Defender Imp for 12, 2 killed", l.text)
        assertEquals(0, l.side)
        assertEquals(3, l.round)
    }

    @Test
    fun hit_variants() {
        assertEquals(
            "Defender Griffin shoots Attacker Pikeman for 7, 0 killed",
            one(BattleEvent.DamageDealt(2, 0, 7, 0, ranged = true, retaliation = false))!!.text,
        )
        val r = one(BattleEvent.DamageDealt(1, 0, 4, 1, ranged = false, retaliation = true))!!
        assertEquals("Defender Imp retaliates against Attacker Pikeman for 4, 1 killed", r.text)
        assertEquals(1, r.side)
    }

    @Test
    fun hit_damageAboveIntRangeIsPrintedInFull() {
        val big = 5_000_000_000L
        assertTrue(one(BattleEvent.DamageDealt(0, 1, big, 1, false, false))!!.text.contains("for 5000000000,"))
    }

    @Test
    fun otherEvents() {
        assertEquals("Attacker Pikeman waits", one(BattleEvent.Waited(0))!!.text)
        assertEquals("Defender Imp defends", one(BattleEvent.Defended(1))!!.text)
        assertEquals("Defender Imp is wiped out", one(BattleEvent.UnitDied(1))!!.text)
        assertEquals("Attacker Pikeman moves to (5,7)", one(BattleEvent.Moved(0, listOf(Pair(2, 7), Pair(5, 7))))!!.text)
        assertEquals("Attacker Pikeman moves", one(BattleEvent.Moved(0, emptyList()))!!.text)
        assertEquals("Defender Imp loses its turn (bad morale)", one(BattleEvent.MoraleFrozen(1))!!.text)
        assertEquals("Attacker Pikeman gains an extra turn (good morale)", one(BattleEvent.MoraleBoost(0))!!.text)
        assertEquals("Attacker Pikeman has good luck", one(BattleEvent.LuckRolled(0, true))!!.text)
        assertEquals("Attacker Pikeman has bad luck", one(BattleEvent.LuckRolled(0, false))!!.text)
        assertEquals("Battle begins", one(BattleEvent.BattleStarted("b"))!!.text)
        assertNull(one(BattleEvent.BattleStarted("b"))!!.side)
        assertEquals("Battle over: Defender wins", one(BattleEvent.BattleEnded(1))!!.text)
        assertEquals(1, one(BattleEvent.BattleEnded(1))!!.side)
    }

    @Test
    fun noiseEventsAreNotLogged() {
        assertNull(one(BattleEvent.RoundStarted(2)))
        assertNull(one(BattleEvent.TurnStarted(0, "main", false)))
    }

    @Test
    fun unknownStackIdFallsBackToPlainLabel() {
        assertEquals("Stack 9 waits", one(BattleEvent.Waited(9))!!.text)
        assertNull(one(BattleEvent.Waited(9))!!.side)
    }

    @Test
    fun onlyLeadingTestPrefixIsStripped() {
        val s2 = st.copy(stacks = listOf(stack(0, 0, "Testy Gnoll"), stack(1, 1, "Test")))
        assertEquals("Attacker Testy Gnoll waits", BattleLog.describe(s2, BattleEvent.Waited(0), 1)!!.text)
        assertEquals("Defender Test waits", BattleLog.describe(s2, BattleEvent.Waited(1), 1)!!.text)
    }

    @Test
    fun roundStartedMovesTheRoundCounterForLaterLines() {
        val log = BattleLog.empty().add(
            st,
            listOf(
                BattleEvent.BattleStarted("b"), BattleEvent.RoundStarted(1), BattleEvent.Waited(0),
                BattleEvent.RoundStarted(2), BattleEvent.Defended(1),
            ),
        )
        assertEquals(listOf(0, 1, 2), log.lines.map { it.round })
        assertEquals(2, log.round)
    }

    @Test
    fun roundCarriesAcrossAddCalls() {
        var log = BattleLog.empty().add(st, listOf(BattleEvent.RoundStarted(4)))
        log = log.add(st, listOf(BattleEvent.Waited(0)))
        assertEquals(listOf(4), log.lines.map { it.round })
    }

    @Test
    fun groupsAreConsecutiveRoundsInOrder() {
        val log = BattleLog.empty().add(
            st,
            listOf(
                BattleEvent.BattleStarted("b"), BattleEvent.RoundStarted(1), BattleEvent.Waited(0), BattleEvent.Defended(1),
                BattleEvent.RoundStarted(2), BattleEvent.Waited(1),
            ),
        )
        val g = log.groups()
        assertEquals(listOf(0, 1, 2), g.map { it.round })
        assertEquals(listOf(1, 2, 1), g.map { it.lines.size })
        assertEquals(log.lines, g.flatMap { it.lines })
        assertTrue(BattleLog.empty().groups().isEmpty())
    }

    @Test
    fun capKeepsTheNewestLines() {
        var log = BattleLog.empty(3)
        for (i in 0 until 5) log = log.add(st, listOf(BattleEvent.Moved(0, listOf(Pair(i, 0)))))
        assertEquals(3, log.lines.size)
        assertEquals(listOf("(2,0)", "(3,0)", "(4,0)"), log.lines.map { it.text.substringAfter("to ") })
    }

    @Test
    fun capOfExactlyNLinesDropsNothing() {
        var log = BattleLog.empty(4)
        for (i in 0 until 4) log = log.add(st, listOf(BattleEvent.Moved(0, listOf(Pair(i, 0)))))
        assertEquals(4, log.lines.size)
        assertEquals("(0,0)", log.lines.first().text.substringAfter("to "))
    }

    @Test
    fun oneBatchLargerThanCapIsTrimmedToo() {
        val evs = (0 until 10).map { BattleEvent.Moved(0, listOf(Pair(it, 0))) }
        val log = BattleLog.empty(2).add(st, evs)
        assertEquals(listOf("(8,0)", "(9,0)"), log.lines.map { it.text.substringAfter("to ") })
    }

    @Test
    fun capTrimKeepsRoundOfSurvivingLinesAndCurrentRound() {
        val log = BattleLog.empty(1).add(st, listOf(BattleEvent.RoundStarted(7), BattleEvent.Waited(0), BattleEvent.RoundStarted(8)))
        assertEquals(1, log.lines.size)
        assertEquals(7, log.lines[0].round)
        assertEquals(8, log.round)
    }

    @Test
    fun defaultCapIsApplied() {
        var log = BattleLog.empty()
        for (i in 0 until BattleLog.DEFAULT_CAP + 5) log = log.add(st, listOf(BattleEvent.Waited(0)))
        assertEquals(BattleLog.DEFAULT_CAP, log.lines.size)
    }

    @Test
    fun badCapIsRefused() {
        assertFailsWith<IllegalArgumentException> { BattleLog.empty(0) }
        assertFailsWith<IllegalArgumentException> { BattleLog.empty(-1) }
    }

    @Test
    fun addIsPureAndDoesNotChangeTheReceiver() {
        val a = BattleLog.empty()
        val b = a.add(st, listOf(BattleEvent.Waited(0)))
        assertTrue(a.lines.isEmpty())
        assertEquals(1, b.lines.size)
        assertEquals(b, a.add(st, listOf(BattleEvent.Waited(0))))
    }

    @Test
    fun goldenPlayoutsLogEveryHitWithMatchingSidesAndNondecreasingRounds() {
        for (g in Fixture.games) {
            val rng = RngStreams.derive(g.masterSeed, "battle:" + g.initial.battleId)
            val greedy = Fixture.ai.GreedyAi(g.aiSeed)
            var s = g.initial
            var log = BattleLog.empty(100_000)
            var n = 0
            var hits = 0
            while ((s.winner == null || !s.started) && n < 120) {
                val side = s.active?.let { s.stacks[it].side }
                val cmd: BattleCommand = if (!s.started) BattleCommand.Begin else greedy.choose(s, side)
                val r = Fixture.battle.apply(s, cmd, rng.asDrawSource())
                hits += r.events.count { it is BattleEvent.DamageDealt }
                log = log.add(r.state, r.events)
                s = r.state
                n++
            }
            assertEquals(hits, log.lines.count { it.text.contains(" for ") && it.text.contains(" killed") }, g.name)
            assertEquals(log.lines.map { it.round }.sorted(), log.lines.map { it.round }, g.name)
            assertTrue(log.lines.none { it.text.startsWith("Stack ") || it.text.contains("Test ") }, g.name)
        }
    }

    @Test
    fun partsExposeKindIdsAndSpriteKeysForARenderer() {
        val hit = one(BattleEvent.DamageDealt(0, 2, 12, 2, ranged = false, retaliation = false))!!
        assertEquals(BattleLogKind.HIT, hit.kind)
        assertEquals(0, hit.actorId)
        assertEquals(2, hit.targetId)
        assertEquals("creature/test_pikeman/002/0000", hit.actorKey)
        assertEquals("creature/griffin/002/0000", hit.targetKey)
        assertEquals(12L, hit.damage)
        assertEquals(2, hit.killed)
        assertEquals(BattleLogKind.SHOOT, one(BattleEvent.DamageDealt(0, 2, 1, 0, true, false))!!.kind)
        assertEquals(BattleLogKind.RETALIATE, one(BattleEvent.DamageDealt(2, 0, 1, 0, false, true))!!.kind)
        val w = one(BattleEvent.Waited(1))!!
        assertEquals(BattleLogKind.WAIT, w.kind)
        assertEquals(1, w.actorId)
        assertNull(w.targetId)
        assertNull(w.targetKey)
        assertEquals("creature/test_imp/002/0000", w.actorKey)
    }

    @Test
    fun everyLoggedEventHasItsOwnKind() {
        val evs = listOf(
            BattleEvent.BattleStarted("b") to BattleLogKind.START, BattleEvent.MoraleFrozen(0) to BattleLogKind.MORALE_LOST,
            BattleEvent.MoraleBoost(0) to BattleLogKind.MORALE_GAIN, BattleEvent.Moved(0, emptyList()) to BattleLogKind.MOVE,
            BattleEvent.Waited(0) to BattleLogKind.WAIT, BattleEvent.Defended(0) to BattleLogKind.DEFEND,
            BattleEvent.LuckRolled(0, true) to BattleLogKind.LUCK_GOOD, BattleEvent.LuckRolled(0, false) to BattleLogKind.LUCK_BAD,
            BattleEvent.UnitDied(0) to BattleLogKind.DIED, BattleEvent.BattleEnded(0) to BattleLogKind.END,
        )
        for ((e, k) in evs) assertEquals(k, one(e)!!.kind, e.toString())
    }

    @Test
    fun unknownStackHasNoSpriteKeyButStillAText() {
        val l = one(BattleEvent.DamageDealt(9, 0, 1, 0, false, false))!!
        assertNull(l.actorKey)
        assertEquals("creature/test_pikeman/002/0000", l.targetKey)
        assertTrue(l.text.startsWith("Stack 9 hits "))
    }
}

