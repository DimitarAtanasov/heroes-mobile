package h3.presenter

import h3.sim.BattleCommand
import h3.sim.Canonical
import h3.sim.Datapack
import h3.sim.Replay
import java.math.BigInteger

/**
 * Autosave and resume through the replay file (android-app.md 7.2, docs/specs/replay-autosave.md).
 * Pure JVM: no file I/O. The app implements [ByteSink] with temp file, fsync and atomic rename.
 */
fun interface ByteSink {
    /** Receives the complete newest replay file. May throw; the autosave counts it and goes on. */
    fun write(bytes: ByteArray)
}

/**
 * [AutosaveSink] that re-records the whole replay after every accepted command and hands the bytes
 * to [sink]. Called on the session worker only, so the fields are plain. It never throws: a failed
 * record or write is counted in [failures] and the next command tries again with the full log.
 *
 * [initialCommands] seeds the log when the session was resumed (autosave is not called for
 * `loadLog`). An entry whose seq is not the next one (a gap) is not recorded and counts as a failure.
 */
class ReplayAutosave(
    private val scenarioJson: String,
    private val seed: BigInteger,
    private val packs: Datapack,
    private val sink: ByteSink,
    initialCommands: List<BattleCommand> = emptyList(),
) : AutosaveSink {
    private val commands = ArrayList<BattleCommand>(initialCommands)

    @Volatile
    var failures: Int = 0
        private set

    @Volatile
    var writes: Int = 0
        private set

    @Volatile
    var lastError: String? = null
        private set

    override fun onCommand(entry: LogEntry, snapshot: Snapshot) {
        try {
            if (entry.seq != commands.size) {
                fail("gap: entry seq ${entry.seq}, expected ${commands.size}")
                return
            }
            commands += entry.command
            sink.write(Replay.record(scenarioJson, commands, seed, packs))
            writes++
        } catch (e: Exception) {
            fail(e.toString())
        }
    }

    private fun fail(why: String) {
        failures++
        lastError = why
    }

    companion object {
        /** Autosave for a session that is about to be resumed from [resumed]. */
        fun resuming(resumed: Resumed, seed: BigInteger, packs: Datapack, sink: ByteSink): ReplayAutosave =
            ReplayAutosave(resumed.scenarioJson, seed, packs, sink, resumed.commands)
    }
}

/** A verified save: the scenario (canonical JSON), the master seed and the command log. */
class Resumed(val scenarioJson: String, val seed: BigInteger, val commands: List<BattleCommand>, val finalHash: String)

/** Named failure of [ReplayResume.load]; the first nine keep the `Replay` error class names. */
enum class ResumeError {
    Malformed, Truncated, Tampered, UnsupportedVersion, UnsupportedKind,
    MismatchedRulesPack, MismatchedPolicy, MismatchedCreatures, Diverged,

    /** Any other failure while reading the file; should not happen. */
    Unreadable,
}

sealed interface ResumeResult {
    data class Ok(val resumed: Resumed) : ResumeResult
    data class Failed(val error: ResumeError, val message: String) : ResumeResult
}

object ReplayResume {
    /** Verifies [bytes] as `Replay.load` does (checksum, packs, replay, final hash); never throws. */
    fun load(bytes: ByteArray, packs: Datapack): ResumeResult =
        try {
            val l = Replay.load(bytes, packs)
            val scenario = Canonical.encode(l.scenario).toString(Charsets.US_ASCII)
            ResumeResult.Ok(Resumed(scenario, l.header["seed"] as BigInteger, l.commands, l.header["final_hash"] as String))
        } catch (e: Replay.ReplayError) {
            ResumeResult.Failed(named(e), e.message ?: "")
        } catch (e: Exception) {
            ResumeResult.Failed(ResumeError.Unreadable, e.toString())
        }

    private fun named(e: Replay.ReplayError): ResumeError =
        ResumeError.entries.firstOrNull { it != ResumeError.Unreadable && it.name == e::class.simpleName } ?: ResumeError.Unreadable

    /**
     * Feeds [resumed] to [BattleSession.loadLog] (atomic: all commands or none). The session must be
     * fresh, built from `Scenario.parse(resumed.scenarioJson)` and `resumed.seed`; call this instead of
     * `start()`. Origins are not stored in a replay, so every entry is [Origin.Replay]; the AI cap
     * restarts at zero. [reply] gets the `loadLog` outcome.
     */
    fun into(session: BattleSession, resumed: Resumed, reply: (SubmitResult) -> Unit = {}) {
        session.loadLog(resumed.commands.mapIndexed { i, c -> LogEntry(i, c, Origin.Replay) }, reply)
    }
}
