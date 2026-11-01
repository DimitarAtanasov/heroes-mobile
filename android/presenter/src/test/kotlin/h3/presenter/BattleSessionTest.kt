package h3.presenter

import h3.sim.BattleCommand
import h3.sim.BattleState
import h3.sim.RngStreams
import h3.sim.asDrawSource
import java.util.concurrent.Executor
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

class BattleSessionTest {
    private companion object { const val CAP = 90 } // the conformance games stop here

    private val direct = Executor { it.run() }
    private val battle = Fixture.battle
    private val codec = Fixture.codec

    /** The reference: a plain apply loop with the same stream and the same stateful AI. */
    private fun plain(g: Game): Pair<BattleState, Int> {
        val rng = RngStreams.derive(g.masterSeed, "battle:" + g.initial.battleId)
        val greedy = Fixture.ai.GreedyAi(g.aiSeed)
        var st = g.initial
        var n = 0
        while ((st.winner == null || !st.started) && n < CAP) {
            val side = st.active?.let { st.stacks[it].side }
            val cmd = if (!st.started) BattleCommand.Begin else greedy.choose(st, side)
            st = battle.apply(st, cmd, rng.asDrawSource()).state
            n++
        }
        return st to n
    }

    private fun session(g: Game, human: Set<Int> = emptySet(), ex: Executor = direct, sink: AutosaveSink? = null, cap: Int = Int.MAX_VALUE) =
        BattleSession(battle, codec, Fixture.ai.GreedyAi(g.aiSeed), g.initial, g.masterSeed, human, ex, sink, cap)

    @Test
    fun aiVsAiThroughSessionEqualsPlainApplyLoopAndRecordedHashForEveryGame() {
        var finished = 0
        var recorded = 0
        for (g in Fixture.games) {
            val (ref, steps) = plain(g)
            val s = session(g, cap = CAP)
            s.start()
            assertTrue(s.isOver() || s.log().size == CAP, g.name)
            assertEquals(codec.stateHash(ref), s.finalHash(), "${g.name} vs plain loop")
            assertEquals(steps, s.log().size, "${g.name} steps")
            // Perturbed games record commands that are not the AI's choice, so only the others
            // can be compared with the recorded Python result.
            if (!g.perturbed) {
                assertEquals(g.finalHash, s.finalHash(), "${g.name} vs recorded Python hash")
                assertEquals(g.finalSteps, s.log().size, g.name)
                assertEquals(g.winner, s.latest().state.winner, g.name)
                recorded++
            }
            finished++
        }
        assertTrue(finished >= 60, "games=$finished")
        assertTrue(recorded >= 40, "recorded=$recorded")
    }

    @Test
    fun skipAnimationsEquivalence_listenerPresenceAndSnapshotReadsDoNotChangeTheResult() {
        val g = Fixture.games.first()
        val quiet = session(g).also { it.start() }
        val busy = session(g)
        busy.addListener { it.view(); it.state.stacks.size }
        busy.start()
        assertEquals(quiet.finalHash(), busy.finalHash())
        assertEquals(quiet.log(), busy.log())
    }

    @Test
    fun staleAndDuplicateSubmissionsAreRejectedWithoutEffect() {
        val g = Fixture.games.first()
        val s = session(g, human = setOf(0, 1))
        var r: SubmitResult? = null
        s.submit(0, BattleCommand.Begin, Origin.Human) { r = it }
        assertIs<SubmitResult.NotYourTurn>(r) // nobody is active before Begin
        s.start()
        assertEquals(1, s.log().size)
        val hash = s.finalHash()
        s.submit(0, BattleCommand.Begin, Origin.Replay) { r = it }
        assertEquals(SubmitResult.Stale(0, 1), r)
        val active = s.latest().state.active!!
        val cmd = BattleCommand.Defend(active)
        s.submit(1, cmd) { r = it }
        val acc = r
        assertIs<SubmitResult.Accepted>(acc)
        assertEquals(2, s.log().size)
        s.submit(1, cmd) { r = it } // duplicate of the accepted one
        assertEquals(SubmitResult.Stale(1, 2), r)
        assertEquals(2, s.log().size)
        assertNotEquals(hash, s.finalHash())
        assertEquals(acc.snapshot.stateHash, s.finalHash())
    }

    @Test
    fun illegalAndWrongTurnHumanCommandsAreRejectedWithoutDrawingFromTheStream() {
        val g = Fixture.games.first()
        val ref = session(g, human = setOf(0, 1)).also { it.start() }
        val s = session(g, human = setOf(0, 1)).also { it.start() }
        var r: SubmitResult? = null
        val other = s.latest().state.stacks.first { it.id != s.latest().state.active }.id
        s.submit(1, BattleCommand.Defend(other)) { r = it }
        assertIs<SubmitResult.Illegal>(r)
        assertEquals(1, s.log().size)
        // A legal command afterwards gives the same result as in a session that never saw the error.
        val a = ref.latest().state.active!!
        ref.submit(1, BattleCommand.Defend(a))
        s.submit(1, BattleCommand.Defend(a))
        assertEquals(ref.finalHash(), s.finalHash())
    }

    @Test
    fun humanSidePausesTheAiAndAiRepliesFollowEachHumanCommand() {
        val g = Fixture.games.first()
        val s = session(g, human = setOf(0))
        s.start()
        var guard = 0
        while (!s.isOver() && guard++ < 2000) {
            val st = s.latest().state
            val a = st.active!!
            assertEquals(0, st.stacks[a].side, "session must stop on a human turn")
            var r: SubmitResult? = null
            s.submit(s.log().size, BattleCommand.Defend(a)) { r = it }
            assertIs<SubmitResult.Accepted>(r)
            // an AI command can be rejected as human origin
            if (!s.isOver()) {
                val st2 = s.latest().state
                assertEquals(0, st2.stacks[st2.active!!].side)
            }
        }
        assertTrue(s.log().any { it.origin == Origin.Ai })
        assertTrue(s.log().any { it.origin == Origin.Human })
        // After the end, further submissions are rejected as Over.
        var r: SubmitResult? = null
        s.submit(s.log().size, BattleCommand.Begin) { r = it }
        assertEquals(SubmitResult.Over, r)
    }

    @Test
    fun snapshotsAreImmutableAndStable() {
        val g = Fixture.games.first()
        val s = session(g)
        val seen = ArrayList<Snapshot>()
        s.addListener { seen.add(it) }
        s.start()
        val copies = seen.map { it.stateHash to it.events.toList() }
        assertEquals(s.log().size, seen.size)
        assertEquals((1..seen.size).toList(), seen.map { it.seq })
        for ((snap, c) in seen.zip(copies)) {
            assertEquals(c.first, codec.stateHash(snap.state), "state of snapshot ${snap.seq} changed")
            assertEquals(c.second, snap.events)
            @Suppress("UNCHECKED_CAST")
            assertFailsWith<UnsupportedOperationException> { (snap.events as MutableList<Any>).add(Unit) }
        }
        assertEquals(seen.last().stateHash, s.finalHash())
        assertEquals(seen[0].view(), seen[0].view())
    }

    @Test
    fun listenersAreCalledInRegistrationOrderForEverySnapshotAndAfterAutosave() {
        val g = Fixture.games[3]
        val trace = ArrayList<String>()
        val sink = AutosaveSink { e, snap -> trace.add("save${e.seq}:${snap.seq}") }
        val s = session(g, sink = sink)
        s.addListener { trace.add("A${it.seq}") }
        s.addListener { throw IllegalStateException("listener failure must not stop the session") }
        s.addListener { trace.add("B${it.seq}") }
        s.start()
        assertTrue(s.listenerFailures > 0)
        assertEquals(g.finalHash, s.finalHash())
        val n = s.log().size
        assertEquals(n * 3, trace.size)
        for (i in 0 until n) {
            assertEquals(listOf("save$i:${i + 1}", "A${i + 1}", "B${i + 1}"), trace.subList(i * 3, i * 3 + 3))
        }
    }

    @Test
    fun threadedWorkerGivesTheSameResultAsTheDirectExecutor() {
        val g = Fixture.games[5]
        val w = BattleSession.newWorker()
        try {
            val threads = HashSet<String>()
            val s = session(g, ex = w)
            s.addListener { threads.add(Thread.currentThread().name) }
            s.start()
            assertTrue(s.awaitIdle(60_000))
            assertEquals(g.finalHash, s.finalHash())
            assertEquals(setOf("h3-sim"), threads)
        } finally {
            w.shutdownNow()
        }
    }

    @Test
    fun streamIsTheNamedBattleStream() {
        // The stream is derived from the master seed: another seed changes the outcome of some game.
        val differs = Fixture.games.filter { !it.perturbed }.take(12).any { g ->
            val s = BattleSession(
                battle, codec, Fixture.ai.GreedyAi(g.aiSeed), g.initial, g.masterSeed.add(java.math.BigInteger.ONE),
                emptySet(), direct, null, CAP,
            )
            s.start()
            s.finalHash() != g.finalHash
        }
        assertTrue(differs)
    }
}
