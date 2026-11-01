package h3.presenter

import h3.sim.Battle
import h3.sim.BattleAi
import h3.sim.BattleCodec
import h3.sim.BattleCommand
import h3.sim.BattleEvent
import h3.sim.BattleState
import h3.sim.IllegalCommand
import h3.sim.Pcg32
import h3.sim.Present
import h3.sim.RngStreams
import h3.sim.asDrawSource
import java.math.BigInteger
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executor
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Who produced a command. Only the log and the human-turn gate look at it. */
enum class Origin { Human, Ai, Replay, Session }

/** One accepted command: [seq] is its index in the log (the first command has seq 0). */
data class LogEntry(val seq: Int, val command: BattleCommand, val origin: Origin)

/**
 * Immutable result of one accepted command (or the initial state, [seq] 0, [command] null).
 * [seq] is the number of commands applied so far. [events] is a read-only copy.
 */
class Snapshot internal constructor(
    val seq: Int,
    val state: BattleState,
    val stateHash: String,
    val command: BattleCommand?,
    val origin: Origin?,
    val events: List<BattleEvent>,
    private val present: Present,
) {
    /** The presenter view v2 of [state], built on demand (pure). */
    fun view(): Map<String, Any?> = present.view(state)
}

/** Outcome of [BattleSession.submit]. A rejection changes neither the state nor the stream. */
sealed interface SubmitResult {
    data class Accepted(val snapshot: Snapshot) : SubmitResult
    data class Stale(val expectedSeq: Int, val currentSeq: Int) : SubmitResult
    data class Illegal(val reason: String) : SubmitResult
    data class NotYourTurn(val activeSide: Int?) : SubmitResult
    data object Over : SubmitResult
}

/** Autosave hook (android-app.md 7.2). The module does no file I/O; the app implements this. */
fun interface AutosaveSink {
    /** Called on the worker after every accepted command, in order, before listeners. */
    fun onCommand(entry: LogEntry, snapshot: Snapshot)
}

/**
 * Owns one battle: the state, the `battle:<battle_id>` stream, the command log and the AI.
 *
 * All mutation runs on [worker]. With a single-thread executor that is the one sim worker; tests
 * inject a direct executor and everything runs synchronously on the caller. Submissions are a
 * FIFO queue of `(expectedSeq, command, origin)`; one whose [expectedSeq] differs from the log size
 * is rejected as [SubmitResult.Stale] (this also rejects duplicates). After every accepted command
 * the session plays AI sides until a human side (or the end) is reached; every step is logged,
 * hashed, passed to [AutosaveSink] and published to listeners in registration order. The AI stops
 * when the log reaches [maxAiCommands] (a stalemate guard; the conformance games use 90).
 *
 * Determinism: the state is the fold of `Battle.apply` over the log from [initial] with the stream
 * `RngStreams.derive(masterSeed, "battle:" + battleId)`. Timing and listeners cannot change it.
 */
class BattleSession(
    private val battle: Battle,
    private val codec: BattleCodec,
    private val ai: BattleAi.GreedyAi,
    initial: BattleState,
    masterSeed: BigInteger,
    private val humanSides: Set<Int> = emptySet(),
    private val worker: Executor,
    private val autosave: AutosaveSink? = null,
    private val maxAiCommands: Int = Int.MAX_VALUE,
) {
    private class Submission(
        val expectedSeq: Int, val command: BattleCommand, val origin: Origin, val reply: (SubmitResult) -> Unit,
    )

    private val present = Present(battle)
    private val rng: Pcg32 = RngStreams.derive(masterSeed, "battle:" + initial.battleId)
    private val queue = java.util.concurrent.ConcurrentLinkedQueue<Submission>()
    private val listeners = CopyOnWriteArrayList<(Snapshot) -> Unit>()
    private val lock = Any()
    private var draining = false
    private val log = ArrayList<LogEntry>()

    @Volatile
    private var current: Snapshot = Snapshot(0, initial, codec.stateHash(initial), null, null, emptyList(), present)

    /** Number of listener calls that threw; a failing listener never stops the session. */
    @Volatile
    var listenerFailures: Int = 0
        private set

    /** The newest snapshot (safe from any thread). */
    fun latest(): Snapshot = current

    /** State hash of the newest snapshot; after the battle ends this is the final hash. */
    fun finalHash(): String = current.stateHash

    fun isOver(): Boolean = current.state.winner != null

    /** Copy of the command log. */
    fun log(): List<LogEntry> = synchronized(lock) { ArrayList(log) }

    /** Listeners are called on the worker in registration order, once per accepted command. */
    fun addListener(l: (Snapshot) -> Unit) {
        listeners.add(l)
    }

    /** Sends `Begin` (origin [Origin.Session]) if the battle has not started, then runs the AI. */
    fun start() {
        worker.execute {
            synchronized(lock) {
                if (!current.state.started) {
                    queue.add(Submission(log.size, BattleCommand.Begin, Origin.Session) {})
                }
            }
            drain()
        }
    }

    /**
     * Queues a command for the worker. [reply] is called on the worker with the outcome. The
     * command is judged against [expectedSeq] when it is dequeued, not when it is submitted.
     */
    fun submit(expectedSeq: Int, command: BattleCommand, origin: Origin = Origin.Human, reply: (SubmitResult) -> Unit = {}) {
        queue.add(Submission(expectedSeq, command, origin, reply))
        worker.execute { drain() }
    }

    /** Blocks until everything queued on [worker] before this call has run. For tests and shutdown. */
    fun awaitIdle(timeoutMillis: Long): Boolean {
        val done = CountDownLatch(1)
        worker.execute { done.countDown() }
        return done.await(timeoutMillis, TimeUnit.MILLISECONDS)
    }

    private fun drain() {
        synchronized(lock) {
            if (draining) return // re-entrant call (a listener submitted); the outer loop continues
            draining = true
            try {
                while (true) {
                    val s = queue.poll()
                    if (s != null) {
                        s.reply(handle(s))
                        continue
                    }
                    if (!playAi()) break
                }
            } finally {
                draining = false
            }
        }
    }

    private fun handle(s: Submission): SubmitResult {
        val cur = current
        if (s.expectedSeq != log.size) return SubmitResult.Stale(s.expectedSeq, log.size)
        if (cur.state.winner != null) return SubmitResult.Over
        if (s.origin == Origin.Human) {
            val a = cur.state.active
            val side = if (a == null) null else cur.state.stacks[a].side
            if (side == null || side !in humanSides) return SubmitResult.NotYourTurn(side)
        }
        return commit(s.command, s.origin)
    }

    /** Plays one AI command when the active stack is on an AI side. False when nothing to do. */
    private fun playAi(): Boolean {
        val st = current.state
        if (!st.started || st.winner != null || log.size >= maxAiCommands) return false
        val a = st.active ?: return false
        val side = st.stacks[a].side
        if (side in humanSides) return false
        val cmd = ai.choose(st, side)
        val r = commit(cmd, Origin.Ai)
        check(r is SubmitResult.Accepted) { "AI produced a rejected command: $r" }
        return true
    }

    private fun commit(cmd: BattleCommand, origin: Origin): SubmitResult {
        val before = current
        val result = try {
            battle.apply(before.state, cmd, rng.asDrawSource())
        } catch (e: IllegalCommand) {
            return SubmitResult.Illegal(e.message ?: "illegal command")
        }
        val entry = LogEntry(log.size, cmd, origin)
        log.add(entry)
        val snap = Snapshot(
            log.size, result.state, codec.stateHash(result.state), cmd, origin, java.util.List.copyOf(result.events), present,
        )
        current = snap
        autosave?.onCommand(entry, snap)
        for (l in listeners) {
            try {
                l(snap)
            } catch (_: RuntimeException) {
                listenerFailures++
            }
        }
        return SubmitResult.Accepted(snap)
    }

    companion object {
        /** A daemon single-thread executor named `h3-sim`: the production worker. */
        fun newWorker(): ExecutorService = Executors.newSingleThreadExecutor { r ->
            Thread(r, "h3-sim").also { it.isDaemon = true }
        }
    }
}
