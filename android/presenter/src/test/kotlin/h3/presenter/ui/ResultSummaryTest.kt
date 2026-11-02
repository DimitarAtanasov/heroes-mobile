package h3.presenter.ui

import h3.presenter.BattleSession
import h3.presenter.Fixture
import h3.presenter.Game
import h3.sim.BattleState
import h3.sim.Hex
import java.util.concurrent.Executor
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The result screen's numbers (docs/specs/app-shell.md, Result): pure functions of two states. */
class ResultSummaryTest {
    private val direct = Executor { it.run() }
    private val hash64 = "0123456789abcdef".repeat(4)

    /** A real initial state with at least two stacks on each side, from the conformance games. */
    private val base: BattleState = Fixture.games.map { it.initial }.first { st ->
        st.stacks.count { it.side == 0 } >= 2 && st.stacks.count { it.side == 1 } >= 2
    }

    /** [base] with the stack counts replaced by [counts] (stack id to count); other stacks keep theirs. */
    private fun withCounts(counts: Map<Int, Int>, winner: Int? = null, round: Int = 3): BattleState =
        base.copy(stacks = base.stacks.map { s -> counts[s.id]?.let { s.copy(count = it) } ?: s }, winner = winner, round = round)

    private fun sideTotal(st: BattleState, side: Int): Long = st.stacks.filter { it.side == side }.sumOf { it.count.toLong() }

    private fun summarise(final: BattleState, commands: Int = 7, hash: String = hash64, human: Int = Hex.ATTACKER) =
        ResultSummary.of(base, final, commands, hash, human)

    private fun tally(r: ResultSummary, side: Int): SideTally = assertNotNull(r.tally(side), "side $side")

    /** Plays [g] to its end, AI against AI, in a fresh session. */
    private fun playOut(g: Game): BattleSession {
        val s = BattleSession(Fixture.battle, Fixture.codec, Fixture.ai, g.initial, g.masterSeed, emptySet(), direct, 5000)
        s.start()
        assertEquals(null, s.fault(), g.name)
        return s
    }

    @Test
    fun casualtiesAndSurvivorsAreCountedPerSideFromTheTwoStates() {
        val a = base.stacks.filter { it.side == 0 }
        val d = base.stacks.filter { it.side == 1 }
        // First attacker stack loses 1, first defender stack loses 2 and the second is wiped out.
        val final = withCounts(
            mapOf(a[0].id to a[0].count - 1, d[0].id to d[0].count - 2, d[1].id to 0),
        )
        val r = summarise(final)
        val ta = tally(r, 0)
        val td = tally(r, 1)
        assertEquals(1L, ta.casualties)
        assertEquals(sideTotal(base, 0) - 1, ta.survivors)
        assertEquals(sideTotal(base, 0), ta.startCreatures)
        assertEquals(a.size, ta.startStacks)
        assertEquals(a.size, ta.survivingStacks)
        assertEquals(2L + d[1].count, td.casualties)
        assertEquals(sideTotal(base, 1) - 2 - d[1].count, td.survivors)
        assertEquals(sideTotal(base, 1), td.startCreatures)
        assertEquals(d.size, td.startStacks)
        assertEquals(d.size - 1, td.survivingStacks)
    }

    @Test
    fun anUnchangedFinalStateHasNoCasualties() {
        val r = summarise(base)
        for (t in r.sides) {
            assertEquals(0L, t.casualties)
            assertEquals(t.startCreatures, t.survivors)
            assertEquals(t.startStacks, t.survivingStacks)
        }
    }

    @Test
    fun aStackMissingFromTheFinalStateIsFullyLost() {
        val gone = base.stacks.first { it.side == 1 }
        val r = summarise(base.copy(stacks = base.stacks.filter { it.id != gone.id }))
        assertEquals(gone.count.toLong(), tally(r, 1).casualties)
        assertEquals(base.stacks.count { it.side == 1 } - 1, tally(r, 1).survivingStacks)
        assertEquals(0L, tally(r, 0).casualties)
    }

    @Test
    fun aFinalCountAboveTheStartIsNotNegativeCasualtiesAndStacksOutsideTheStartAreIgnored() {
        val s0 = base.stacks.first { it.side == 0 }
        val grown = withCounts(mapOf(s0.id to s0.count + 50))
        val extra = s0.copy(id = 9999, count = 40)
        val r = summarise(grown.copy(stacks = grown.stacks + extra))
        assertEquals(0L, tally(r, 0).casualties)
        assertEquals(tally(r, 0).startCreatures, tally(r, 0).survivors)
        for (t in r.sides) assertEquals(t.startCreatures, t.survivors + t.casualties)
    }

    @Test
    fun sidesAreListedInAscendingOrderWhateverTheStackOrder() {
        val flipped = base.copy(stacks = base.stacks.reversed())
        val r = ResultSummary.of(flipped, base, 1, hash64)
        assertEquals(listOf(0, 1), r.sides.map { it.side })
        assertNull(r.tally(2))
        assertEquals(sideTotal(base, 0), tally(r, 0).startCreatures)
    }

    @Test
    fun winnerAndOutcomeFollowTheFinalState() {
        assertEquals(ResultOutcome.Victory, summarise(withCounts(emptyMap(), winner = 0)).outcome)
        assertEquals(0, summarise(withCounts(emptyMap(), winner = 0)).winner)
        assertEquals(ResultOutcome.Defeat, summarise(withCounts(emptyMap(), winner = 1)).outcome)
        assertEquals(1, summarise(withCounts(emptyMap(), winner = 1)).winner)
        val open = summarise(withCounts(emptyMap(), winner = null))
        assertEquals(ResultOutcome.Unfinished, open.outcome)
        assertNull(open.winner)
        // The viewpoint is a parameter: the same game seen from the defender.
        assertEquals(ResultOutcome.Defeat, summarise(withCounts(emptyMap(), winner = 0), human = Hex.DEFENDER).outcome)
        assertEquals(ResultOutcome.Victory, summarise(withCounts(emptyMap(), winner = 1), human = Hex.DEFENDER).outcome)
    }

    @Test
    fun roundsCommandsAndHashesAreCarried() {
        val r = summarise(withCounts(emptyMap(), round = 12), commands = 345)
        assertEquals(12, r.rounds)
        assertEquals(345, r.commands)
        assertEquals(hash64, r.fullHash)
        assertEquals("01234567", r.shortHash)
        assertEquals(8, ResultSummary.SHORT_HASH_LENGTH)
        // A hash shorter than the short form is shown whole, never padded or failing.
        assertEquals("abc", summarise(base, hash = "abc").shortHash)
        assertEquals("", summarise(base, hash = "").shortHash)
    }

    @Test
    fun badInputsAreRefused() {
        assertFailsWith<IllegalArgumentException> { summarise(base, commands = -1) }
        assertFailsWith<IllegalArgumentException> { summarise(base.copy(battleId = base.battleId + "-other")) }
    }

    @Test
    fun finishedGamesBalanceAndLeaveOneSideStanding() {
        var finished = 0
        for (g in Fixture.games) {
            val s = playOut(g)
            val snap = s.latest()
            val r = ResultSummary.of(g.initial, snap)
            assertEquals(snap.state.winner, r.winner, g.name)
            assertEquals(snap.seq, r.commands, g.name)
            assertEquals(snap.state.round, r.rounds, g.name)
            assertEquals(s.finalHash(), r.fullHash, g.name)
            assertEquals(r.fullHash.take(8), r.shortHash, g.name)
            for (t in r.sides) {
                assertEquals(t.startCreatures, t.survivors + t.casualties, "${g.name} side ${t.side}")
                assertEquals(sideTotal(g.initial, t.side), t.startCreatures, g.name)
                assertEquals(sideTotal(snap.state, t.side), t.survivors, g.name)
                assertEquals(snap.state.stacks.count { it.side == t.side && it.count > 0 }, t.survivingStacks, g.name)
            }
            val w = r.winner
            if (w != null) {
                finished++
                val loser = tally(r, 1 - w)
                assertEquals(0L, loser.survivors, g.name)
                assertEquals(loser.startCreatures, loser.casualties, g.name)
                assertTrue(tally(r, w).survivors > 0, g.name)
                assertEquals(if (w == 0) ResultOutcome.Victory else ResultOutcome.Defeat, r.outcome, g.name)
            }
        }
        assertTrue(finished >= 40, "finished=$finished")
    }

    @Test
    fun anUnstartedSessionSummarisesAsUnfinishedWithNoLosses() {
        val g = Fixture.games.first()
        val s = BattleSession(Fixture.battle, Fixture.codec, Fixture.ai, g.initial, g.masterSeed, emptySet(), direct, 5000)
        val r = ResultSummary.of(g.initial, s.latest())
        assertEquals(ResultOutcome.Unfinished, r.outcome)
        assertEquals(0, r.commands)
        for (t in r.sides) assertEquals(0L, t.casualties)
    }
}
