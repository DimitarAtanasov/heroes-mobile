package h3.presenter

import h3.sim.BattleCommand
import h3.sim.BattleState
import h3.sim.RngStreams
import h3.sim.asDrawSource
import java.io.IOException
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executor
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class BattleSessionTest {
    private companion object { const val CAP = 90 } // AI commands per game, as in the conformance games

    private val direct = Executor { it.run() }
    private val battle = Fixture.battle
    private val codec = Fixture.codec
    private val ai = Fixture.ai

    /** Queues tasks and runs them only when told: submissions arrive long before they are handled. */
    private class Holding : Executor {
        val tasks = ArrayDeque<Runnable>()
        override fun execute(command: Runnable) { tasks.addLast(command) }
        fun runAll() { while (tasks.isNotEmpty()) tasks.removeFirst().run() }
    }

    /** The reference: a plain apply loop with the same stream and the stateless AI. */
    private fun plain(g: Game, label: String = "battle:" + g.initial.battleId): Pair<BattleState, Int> {
        val rng = RngStreams.derive(g.masterSeed, label)
        var st = g.initial
        var n = 0
        var aiN = 0
        if (!st.started) { st = battle.apply(st, BattleCommand.Begin, rng.asDrawSource()).state; n++ }
        while (st.winner == null && aiN < CAP) {
            st = battle.apply(st, ai.choose(st), rng.asDrawSource()).state
            n++; aiN++
        }
        return st to n
    }

    private fun session(g: Game, human: Set<Int> = emptySet(), ex: Executor = direct, sink: AutosaveSink? = null, cap: Int = CAP) =
        BattleSession(battle, codec, ai, g.initial, g.masterSeed, human, ex, cap, sink)

    /** A scripted human: on every human turn it submits the stateless AI's choice for the state. */
    private fun drive(s: BattleSession, limit: Int = 400): List<Pair<Int, BattleCommand>> {
        val out = ArrayList<Pair<Int, BattleCommand>>()
        var guard = 0
        while (!s.isOver() && !s.isStalled() && guard++ < limit) {
            val snap = s.latest()
            val cmd = ai.choose(snap.state)
            var r: SubmitResult? = null
            s.submit(snap.seq, cmd) { r = it }
            assertIs<SubmitResult.Accepted>(r, "human step at ${snap.seq}")
            out += snap.seq to cmd
        }
        return out
    }

    @Test
    fun aiVsAiThroughSessionEqualsPlainStatelessApplyLoopForEveryGame() {
        // The recorded games were played by the stateful GreedyAi; the session uses the stateless
        // chooser (ADR-0012), whose per-state parity with Python is BattleAiTest's job in :sim.
        var finished = 0
        for (g in Fixture.games) {
            val (ref, steps) = plain(g)
            val s = session(g)
            s.start()
            assertTrue(s.isOver() || s.isStalled(), g.name)
            assertEquals(codec.stateHash(ref), s.finalHash(), "${g.name} vs plain loop")
            assertEquals(steps, s.log().size, "${g.name} steps")
            if (s.isOver()) finished++
        }
        assertEquals(64, Fixture.games.size)
        assertTrue(finished > 0)
    }

    @Test
    fun holdingAndDirectExecutorsGiveTheSameGameForTheSameHumanSubmissions() {
        var compared = 0
        for (g in Fixture.games.take(16)) {
            val a = session(g, human = setOf(0)).also { it.start() }
            val subs = drive(a)
            val h = Holding()
            val b = session(g, human = setOf(0), ex = h)
            b.start()
            val replies = ArrayList<SubmitResult>()
            for ((seq, c) in subs) b.submit(seq, c) { replies += it }
            h.runAll()
            assertEquals(subs.size, replies.size, g.name)
            assertTrue(replies.all { it is SubmitResult.Accepted }, "${g.name}: $replies")
            assertEquals(a.log(), b.log(), g.name)
            assertEquals(a.finalHash(), b.finalHash(), g.name)
            if (subs.isNotEmpty()) compared++
        }
        assertTrue(compared >= 8, "compared=$compared")
    }

    @Test
    fun gameResumedFromItsLogEqualsTheUninterruptedGame() {
        var resumed = 0
        for (g in Fixture.games.take(16)) {
            val a = session(g, human = setOf(0)).also { it.start() }
            drive(a)
            val log = a.log()
            val k = log.size / 2
            val b = session(g, human = setOf(0))
            var r: SubmitResult? = null
            b.loadLog(log.take(k)) { r = it }
            assertIs<SubmitResult.Accepted>(r, g.name)
            b.start()
            drive(b)
            assertEquals(log, b.log(), g.name)
            assertEquals(a.finalHash(), b.finalHash(), g.name)
            resumed++
        }
        assertEquals(16, resumed)
    }

    @Test
    fun loadLogIsAtomicVerifiesEveryStepAndRunsOnlyOnAnEmptySession() {
        val g = Fixture.games.first()
        val a = session(g).also { it.start() }
        val log = a.log()
        assertTrue(log.size > 4)
        // A tampered step (an illegal command) is rejected and the session stays at its initial state.
        val bad = log.take(4) + LogEntry(4, BattleCommand.Defend(99), Origin.Ai)
        val b = session(g)
        val seen = ArrayList<Snapshot>()
        b.addListener { seen += it }
        var r: SubmitResult? = null
        b.loadLog(bad) { r = it }
        val ill = r
        assertIs<SubmitResult.Illegal>(ill)
        assertTrue(ill.reason.startsWith("step 4"), ill.reason)
        assertEquals(emptyList(), b.log())
        assertEquals(codec.stateHash(g.initial), b.finalHash())
        assertTrue(seen.isEmpty())
        // A wrong seq is rejected too.
        b.loadLog(listOf(log[1])) { r = it }
        assertIs<SubmitResult.Illegal>(r)
        // The whole log loads, with the AI disabled during the load, and gives the same game.
        b.loadLog(log) { r = it }
        assertIs<SubmitResult.Accepted>(r)
        assertEquals(log, b.log())
        assertEquals(a.finalHash(), b.finalHash())
        assertEquals(1, seen.size)
        // A second load on a non-empty session is stale.
        b.loadLog(log) { r = it }
        assertEquals(SubmitResult.Stale(0, log.size), r)
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
    fun humanCommandOnAnAiSideTurnIsNotYourTurn() {
        // No AI in the session: side 1 is driven by Ai-origin submissions, so its turn is observable.
        val g = Fixture.games.first { gm ->
            val st = battle.apply(gm.initial, BattleCommand.Begin, RngStreams.derive(gm.masterSeed, "battle:" + gm.initial.battleId).asDrawSource()).state
            st.stacks[st.active!!].side == 1
        }
        val s = BattleSession(battle, codec, null, g.initial, g.masterSeed, setOf(0), direct, CAP)
        s.start()
        val st = s.latest().state
        assertEquals(1, st.stacks[st.active!!].side, "precondition: side 1 is to move")
        var r: SubmitResult? = null
        s.submit(1, BattleCommand.Defend(st.active!!), Origin.Human) { r = it }
        assertEquals(SubmitResult.NotYourTurn(1), r)
        assertEquals(1, s.log().size)
        s.submit(1, ai.choose(st), Origin.Ai) { r = it }
        assertIs<SubmitResult.Accepted>(r)
    }

    @Test
    fun humanSidePausesTheAiAndAiRepliesFollowEachHumanCommand() {
        val g = Fixture.games.first()
        val s = session(g, human = setOf(0), cap = 10_000)
        s.start()
        var guard = 0
        while (!s.isOver() && guard++ < 2000) {
            val st = s.latest().state
            val a = st.active!!
            assertEquals(0, st.stacks[a].side, "session must stop on a human turn")
            var r: SubmitResult? = null
            s.submit(s.log().size, BattleCommand.Defend(a)) { r = it }
            assertIs<SubmitResult.Accepted>(r)
        }
        assertTrue(s.isOver())
        assertTrue(s.log().any { it.origin == Origin.Ai })
        assertTrue(s.log().any { it.origin == Origin.Human })
        // After the end, further submissions are rejected as Over.
        var r: SubmitResult? = null
        s.submit(s.log().size, BattleCommand.Begin) { r = it }
        assertEquals(SubmitResult.Over, r)
    }

    @Test
    fun stalemateCapCountsAiCommandsOnlyAndReportsStalled() {
        val g = Fixture.games.first()
        val cap = 3
        val s = session(g, human = setOf(0), cap = cap)
        s.start()
        var guard = 0
        while (!s.isOver() && !s.isStalled() && guard++ < 400) {
            val snap = s.latest()
            var r: SubmitResult? = null
            s.submit(snap.seq, ai.choose(snap.state)) { r = it }
            assertIs<SubmitResult.Accepted>(r)
        }
        assertTrue(s.isStalled(), "precondition: the game reaches the cap")
        assertEquals(cap, s.log().count { it.origin == Origin.Ai })
        assertTrue(s.log().count { it.origin == Origin.Human } > 0)
        var r: SubmitResult? = null
        s.submit(s.log().size, BattleCommand.Begin) { r = it }
        assertEquals(SubmitResult.Stalled, r)
        assertFailsWith<IllegalArgumentException> { session(g, cap = -1) }
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
        @Suppress("UNCHECKED_CAST")
        assertFailsWith<UnsupportedOperationException> { (s.log() as MutableList<LogEntry>).clear() }
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
        assertEquals(codec.stateHash(plain(g).first), s.finalHash())
        val n = s.log().size
        assertEquals(n * 3, trace.size)
        for (i in 0 until n) {
            assertEquals(listOf("save$i:${i + 1}", "A${i + 1}", "B${i + 1}"), trace.subList(i * 3, i * 3 + 3))
        }
    }

    @Test
    fun checkedListenerExceptionsAutosaveAndReplyFailuresNeverStopTheQueue() {
        val g = Fixture.games.first()
        val ref = session(g, human = setOf(0, 1)).also { it.start() }
        val s = session(g, human = setOf(0, 1), sink = { e, _ -> if (e.seq == 1) throw IOException("disk full") })
        val seqs = ArrayList<Int>()
        s.addListener { if (it.seq == 2) throw IOException("listener") }
        s.addListener { seqs += it.seq }
        s.start()
        var replies = 0
        val a1 = s.latest().state.active!!
        s.submit(1, BattleCommand.Defend(a1)) { replies++; throw IOException("reply") }
        ref.submit(1, BattleCommand.Defend(a1))
        val a2 = s.latest().state.active!!
        s.submit(2, BattleCommand.Defend(a2)) { replies++ }
        ref.submit(2, BattleCommand.Defend(a2))
        assertEquals(2, replies)
        assertEquals(listOf(1, 2, 3), seqs)
        assertEquals(1, s.autosaveFailures)
        assertEquals(2, s.listenerFailures) // one listener, one reply
        assertEquals(ref.finalHash(), s.finalHash())
    }

    @Test
    fun anAiFailurePublishesATerminalFaultedSnapshotAndEverySubmitIsAnswered() {
        // Corrupt state: side 0 is wiped out but no winner is set, so the AI finds no enemy.
        val base = Fixture.states.first { st ->
            st.started && st.winner == null && st.active != null && st.stacks[st.active!!].side == 1
        }
        val broken = base.copy(stacks = base.stacks.map { if (it.side == 0) it.copy(count = 0) else it })
        val s = BattleSession(battle, codec, ai, broken, java.math.BigInteger.ONE, setOf(0), direct, CAP)
        val seen = ArrayList<Snapshot>()
        s.addListener { seen += it }
        s.start()
        val f = assertNotNull(s.fault())
        assertEquals(1, seen.size)
        assertEquals(f, seen.single().fault)
        assertEquals(f, s.latest().fault)
        var r: SubmitResult? = null
        s.submit(0, BattleCommand.Defend(0)) { r = it }
        assertEquals(SubmitResult.Faulted(f), r)
        assertTrue(s.log().isEmpty())
    }

    @Test
    fun aListenerThatHandsOffToAnotherThreadCallingLogDoesNotDeadlock() {
        val g = Fixture.games.first()
        val w = BattleSession.newWorker()
        try {
            val s = session(g, ex = w)
            val blocked = AtomicInteger()
            val sizes = Collections.synchronizedList(ArrayList<Int>())
            s.addListener { snap ->
                if (blocked.get() > 0) return@addListener // one deadlock is enough evidence
                val done = CountDownLatch(1)
                Thread { sizes += s.log().size; done.countDown() }.start()
                if (!done.await(3, TimeUnit.SECONDS)) blocked.incrementAndGet() else assertTrue(sizes.last() >= snap.seq)
            }
            s.start()
            assertTrue(s.awaitIdle(120_000))
            assertTrue(s.log().isNotEmpty())
            assertEquals(0, blocked.get())
            assertTrue(s.awaitIdle(60_000))
            assertEquals(s.log().size, sizes.size)
        } finally {
            w.shutdownNow()
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
            assertEquals(codec.stateHash(plain(g).first), s.finalHash())
            assertEquals(setOf("h3-sim"), threads)
        } finally {
            w.shutdownNow()
        }
    }

    @Test
    fun manySubmittersOnTheThreadedWorkerGetOneReplyEachAndAConsistentLog() {
        val g = Fixture.games[2]
        val w = BattleSession.newWorker()
        try {
            val s = session(g, human = setOf(0, 1), ex = w)
            s.start()
            assertTrue(s.awaitIdle(60_000))
            val submitted = AtomicInteger()
            val replied = AtomicInteger()
            val accepted = AtomicInteger()
            val target = 40
            val threads = (0 until 4).map {
                Thread {
                    var n = 0
                    while (s.log().size < target && !s.isOver() && n++ < 2000) {
                        val snap = s.latest()
                        val done = CountDownLatch(1)
                        submitted.incrementAndGet()
                        s.submit(snap.seq, ai.choose(snap.state)) { r ->
                            replied.incrementAndGet()
                            if (r is SubmitResult.Accepted) accepted.incrementAndGet()
                            done.countDown()
                        }
                        assertTrue(done.await(30, TimeUnit.SECONDS))
                    }
                }
            }
            threads.forEach { it.start() }
            threads.forEach { it.join(120_000) }
            assertTrue(s.awaitIdle(60_000))
            assertTrue(submitted.get() > 0)
            assertEquals(submitted.get(), replied.get())
            val log = s.log()
            assertEquals(log.size - 1, accepted.get()) // every entry but Begin was one accepted submit
            assertTrue(log.size >= target || s.isOver(), "log=${log.size}")
            assertEquals(log.indices.toList(), log.map { it.seq })
            // The log folds to the session's hash, whatever the interleaving was.
            val rng = RngStreams.derive(g.masterSeed, "battle:" + g.initial.battleId)
            var st = g.initial
            for (e in log) st = battle.apply(st, e.command, rng.asDrawSource()).state
            assertEquals(codec.stateHash(st), s.finalHash())
        } finally {
            w.shutdownNow()
        }
    }

    @Test
    fun submitAfterShutdownRepliesShutDownAndHumanSidesAreCopied() {
        val g = Fixture.games.first()
        val sides = mutableSetOf(0, 1)
        val w = BattleSession.newWorker()
        val s = BattleSession(battle, codec, ai, g.initial, g.masterSeed, sides, w, CAP)
        sides.clear() // must not turn the human sides into AI sides
        s.start()
        assertTrue(s.awaitIdle(60_000))
        assertEquals(1, s.log().size, "AI must not play for sides given as human")
        w.shutdown()
        assertTrue(w.awaitTermination(10, TimeUnit.SECONDS))
        var r: SubmitResult? = null
        s.submit(1, BattleCommand.Defend(s.latest().state.active!!)) { r = it }
        assertEquals(SubmitResult.ShutDown, r)
        s.start() // does not throw either
        assertEquals(1, s.log().size)
    }

    @Test
    fun streamIsTheNamedBattleStream() {
        // Every session equals the plain loop on `battle:<id>`; a loop on another label differs for
        // some game, so the comparison can tell the label apart.
        var differs = 0
        for (g in Fixture.games.take(12)) {
            val s = session(g).also { it.start() }
            assertEquals(codec.stateHash(plain(g).first), s.finalHash(), g.name)
            if (codec.stateHash(plain(g, "battle:x" + g.initial.battleId).first) != s.finalHash()) differs++
        }
        assertTrue(differs > 0)
    }
}
