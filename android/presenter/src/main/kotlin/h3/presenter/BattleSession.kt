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
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executor
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.TimeUnit

/** Who produced a command. Only the log and the human-turn gate look at it. */
enum class Origin { Human, Ai, Replay, Session }

/** One accepted command: [seq] is its index in the log (the first command has seq 0). */
data class LogEntry(val seq: Int, val command: BattleCommand, val origin: Origin)

/**
 * Immutable result of one accepted command (or the initial state, [seq] 0, [command] null).
 * [seq] is the number of commands applied so far. [events] is a read-only copy. A non-null
 * [fault] marks the terminal snapshot of a faulted session: the state of the last accepted
 * command, no command, no events.
 */
class Snapshot internal constructor(
    val seq: Int,
    val state: BattleState,
    val stateHash: String,
    val command: BattleCommand?,
    val origin: Origin?,
    val events: List<BattleEvent>,
    private val present: Present,
    val fault: String? = null,
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

    /** An AI side is to move but the AI has played `maxAiCommands` commands: the game is stuck. */
    data object Stalled : SubmitResult

    /** The engine or the AI failed; the session is terminal and accepts nothing more. */
    data class Faulted(val reason: String) : SubmitResult

    /** The worker refused the task (it was shut down). Nothing was queued. */
    data object ShutDown : SubmitResult
}

/** Autosave hook (android-app.md 7.2). The module does no file I/O; the app implements this. */
fun interface AutosaveSink {
    /** Called on the worker after every accepted command, in order, before listeners. */
    fun onCommand(entry: LogEntry, snapshot: Snapshot)
}

/**
 * Owns one battle: the state, the `battle:<battle_id>` stream and the command log.
 *
 * All mutation runs on [worker], one drain loop at a time. Submissions are a FIFO queue of
 * `(expectedSeq, command, origin)`; one whose [expectedSeq] differs from the log size is rejected
 * as [SubmitResult.Stale] (this also rejects duplicates). Whenever the active stack is on an AI
 * side the session plays the AI before it looks at the queue, so the log does not depend on when
 * submissions arrive. The AI is [BattleAi.choose], a pure function of the state (ADR-0012); a null
 * [ai] means no AI (non-human sides are then driven by Ai or Replay submissions). Every step is
 * logged, hashed, passed to [AutosaveSink] and published to listeners in registration order. The AI
 * stops after [maxAiCommands] AI commands (a stalemate guard); then [isStalled] is true.
 *
 * Determinism: the state is the fold of `Battle.apply` over the log from [initial] with the stream
 * `RngStreams.derive(masterSeed, "battle:" + battleId)`. Timing and listeners cannot change it.
 */
class BattleSession(
    private val battle: Battle,
    private val codec: BattleCodec,
    private val ai: BattleAi?,
    private val initial: BattleState,
    private val masterSeed: BigInteger,
    humanSides: Set<Int>,
    private val worker: Executor,
    private val maxAiCommands: Int,
    private val autosave: AutosaveSink? = null,
) {
    init {
        require(maxAiCommands >= 0) { "maxAiCommands must be >= 0" }
    }

    private class Submission(
        val expectedSeq: Int, val command: BattleCommand?, val origin: Origin, val load: List<LogEntry>?,
        val reply: (SubmitResult) -> Unit,
    )

    private val humanSides: Set<Int> = java.util.Set.copyOf(humanSides)
    private val present = Present(battle)
    private var rng: Pcg32 = stream()
    private val queue = ConcurrentLinkedQueue<Submission>()
    private val listeners = CopyOnWriteArrayList<(Snapshot) -> Unit>()
    private val lock = Any()
    private var draining = false // guarded by lock: at most one drain loop runs
    private var aiCommands = 0

    @Volatile
    private var entries: List<LogEntry> = emptyList()

    @Volatile
    private var current: Snapshot = Snapshot(0, initial, codec.stateHash(initial), null, null, emptyList(), present)

    @Volatile
    private var fault: String? = null

    /** Number of listener or reply calls that threw; a failing listener never stops the session. */
    @Volatile
    var listenerFailures: Int = 0
        private set

    /** Number of autosave calls that threw; the command stays accepted and listeners still run. */
    @Volatile
    var autosaveFailures: Int = 0
        private set

    private fun stream(): Pcg32 = RngStreams.derive(masterSeed, "battle:" + initial.battleId)

    /** The newest snapshot (safe from any thread). */
    fun latest(): Snapshot = current

    /** State hash of the newest snapshot; after the battle ends this is the final hash. */
    fun finalHash(): String = current.stateHash

    fun isOver(): Boolean = current.state.winner != null

    /** The reason the session faulted, or null. A faulted session accepts nothing more. */
    fun fault(): String? = fault

    /** True when an AI side is to move and the AI has used up [maxAiCommands]. */
    fun isStalled(): Boolean = fault == null && aiTurnBlocked(current.state)

    /** The command log: an immutable list, published after each command (never blocks). */
    fun log(): List<LogEntry> = entries

    /** Listeners are called on the worker in registration order, once per accepted command. */
    fun addListener(l: (Snapshot) -> Unit) {
        listeners.add(l)
    }

    /** Queues `Begin` (origin [Origin.Session]) if the initial state has not started; runs the AI. */
    fun start() {
        if (!initial.started) {
            enqueue(Submission(0, BattleCommand.Begin, Origin.Session, null) {})
        } else {
            execute()
        }
    }

    /**
     * Queues a command for the worker. [reply] is called exactly once: on the worker with the
     * outcome, or on the caller with [SubmitResult.ShutDown] if the worker refuses the task. The
     * command is judged against [expectedSeq] when it is dequeued, not when it is submitted.
     */
    fun submit(expectedSeq: Int, command: BattleCommand, origin: Origin = Origin.Human, reply: (SubmitResult) -> Unit = {}) {
        enqueue(Submission(expectedSeq, command, origin, null, reply))
    }

    /**
     * Resumes a recorded game: applies [log] (seq 0, 1, ... in order) to the initial state with the
     * AI disabled, atomically. Every entry must be accepted by the engine; on the first failure the
     * session is left untouched and [reply] gets [SubmitResult.Illegal] naming the step. Valid only
     * while the session log is empty ([SubmitResult.Stale] otherwise), so call it before [start]. On
     * success the log holds the entries with their origins, listeners get one snapshot (the end
     * state), autosave is not called, and the AI resumes if an AI side is to move.
     */
    fun loadLog(log: List<LogEntry>, reply: (SubmitResult) -> Unit = {}) {
        enqueue(Submission(0, null, Origin.Replay, java.util.List.copyOf(log), reply))
    }

    /** Blocks until everything queued on [worker] before this call has run. For tests and shutdown. */
    fun awaitIdle(timeoutMillis: Long): Boolean {
        val done = CountDownLatch(1)
        try {
            worker.execute { done.countDown() }
        } catch (_: RejectedExecutionException) {
            return false
        }
        return done.await(timeoutMillis, TimeUnit.MILLISECONDS)
    }

    private fun enqueue(s: Submission) {
        queue.add(s)
        try {
            worker.execute { drain() }
        } catch (_: RejectedExecutionException) {
            if (queue.remove(s)) safeReply(s, SubmitResult.ShutDown)
        }
    }

    private fun execute() {
        try {
            worker.execute { drain() }
        } catch (_: RejectedExecutionException) {
            // shut down: nothing to run
        }
    }

    /**
     * One drain loop at a time ([lock] guards only the [draining] flag). Apply, autosave,
     * listeners and replies run outside the lock, in that order for each command.
     */
    private fun drain() {
        synchronized(lock) {
            if (draining) return // the running loop (possibly an outer, re-entrant one) sees the queue
            draining = true
        }
        try {
            while (true) {
                val played = try {
                    playAi()
                } catch (e: Exception) {
                    faulted("session failed: $e")
                    false
                }
                if (played) continue
                val s = queue.poll()
                if (s != null) {
                    val r = try {
                        handle(s)
                    } catch (e: Exception) {
                        faulted("session failed: $e")
                    }
                    safeReply(s, r)
                    continue
                }
                synchronized(lock) {
                    if (queue.isEmpty()) {
                        draining = false
                        return
                    }
                }
            }
        } catch (t: Throwable) {
            synchronized(lock) { draining = false }
            throw t
        }
    }

    private fun handle(s: Submission): SubmitResult {
        fault?.let { return SubmitResult.Faulted(it) }
        val cur = current
        val size = entries.size
        if (s.expectedSeq != size) return SubmitResult.Stale(s.expectedSeq, size)
        if (s.load != null) return load(s.load)
        if (cur.state.winner != null) return SubmitResult.Over
        if (s.origin == Origin.Human) {
            val a = cur.state.active
            val side = if (a == null) null else cur.state.stacks[a].side
            if (side == null || side !in humanSides) {
                return if (aiTurnBlocked(cur.state)) SubmitResult.Stalled else SubmitResult.NotYourTurn(side)
            }
        }
        return commit(s.command!!, s.origin)
    }

    private fun aiTurnBlocked(st: BattleState): Boolean {
        if (ai == null || !st.started || st.winner != null) return false
        val a = st.active ?: return false
        return st.stacks[a].side !in humanSides && aiCommands >= maxAiCommands
    }

    /** Plays one AI command when the active stack is on an AI side. False when nothing to do. */
    private fun playAi(): Boolean {
        val chooser = ai ?: return false
        if (fault != null) return false
        val st = current.state
        if (!st.started || st.winner != null || aiCommands >= maxAiCommands) return false
        val a = st.active ?: return false
        if (st.stacks[a].side in humanSides) return false
        val cmd = try {
            chooser.choose(st)
        } catch (e: Exception) {
            faulted("AI failed: $e")
            return false
        }
        val r = commit(cmd, Origin.Ai)
        if (r !is SubmitResult.Accepted) {
            if (r !is SubmitResult.Faulted) faulted("AI produced a rejected command $cmd: $r")
            return false
        }
        return true
    }

    private fun load(log: List<LogEntry>): SubmitResult {
        val r = stream()
        var st = initial
        var ais = 0
        for ((i, e) in log.withIndex()) {
            if (e.seq != i) return SubmitResult.Illegal("step $i: entry has seq ${e.seq}")
            st = try {
                battle.apply(st, e.command, r.asDrawSource()).state
            } catch (x: IllegalCommand) {
                return SubmitResult.Illegal("step $i: ${x.message}")
            } catch (x: Exception) {
                return SubmitResult.Illegal("step $i: engine failed: $x")
            }
            if (e.origin == Origin.Ai) ais++
        }
        rng = r
        aiCommands = ais
        entries = log
        val last = log.lastOrNull()
        val snap = Snapshot(log.size, st, codec.stateHash(st), last?.command, last?.origin, emptyList(), present)
        current = snap
        publish(snap)
        return SubmitResult.Accepted(snap)
    }

    private fun commit(cmd: BattleCommand, origin: Origin): SubmitResult {
        val before = current
        val result = try {
            battle.apply(before.state, cmd, rng.asDrawSource())
        } catch (e: IllegalCommand) {
            return SubmitResult.Illegal(e.message ?: "illegal command")
        } catch (e: Exception) {
            // The stream may have advanced part way: the session cannot continue.
            return faulted("engine failed on $cmd: $e")
        }
        val entry = LogEntry(entries.size, cmd, origin)
        val snap = Snapshot(
            entry.seq + 1, result.state, codec.stateHash(result.state), cmd, origin, java.util.List.copyOf(result.events), present,
        )
        entries = java.util.List.copyOf(entries + entry)
        if (origin == Origin.Ai) aiCommands++
        current = snap
        if (autosave != null) {
            try {
                autosave.onCommand(entry, snap)
            } catch (_: Exception) {
                autosaveFailures++
            }
        }
        publish(snap)
        return SubmitResult.Accepted(snap)
    }

    private fun faulted(reason: String): SubmitResult {
        if (fault == null) {
            fault = reason
            val c = current
            val snap = Snapshot(c.seq, c.state, c.stateHash, null, null, emptyList(), present, reason)
            current = snap
            publish(snap)
        }
        return SubmitResult.Faulted(fault!!)
    }

    private fun publish(snap: Snapshot) {
        for (l in listeners) {
            try {
                l(snap)
            } catch (_: Exception) {
                listenerFailures++
            }
        }
    }

    private fun safeReply(s: Submission, r: SubmitResult) {
        try {
            s.reply(r)
        } catch (_: Exception) {
            listenerFailures++
        }
    }

    companion object {
        /** A daemon single-thread executor named `h3-sim`: the production worker. */
        fun newWorker(): ExecutorService = Executors.newSingleThreadExecutor { r ->
            Thread(r, "h3-sim").also { it.isDaemon = true }
        }
    }
}
