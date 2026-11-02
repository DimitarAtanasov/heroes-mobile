package h3.app

import h3.presenter.AutosaveSink
import h3.presenter.BattleSession
import h3.presenter.Origin
import h3.presenter.ReplayResume
import h3.presenter.Resumed
import h3.presenter.Snapshot
import h3.presenter.SubmitResult
import h3.presenter.TapEvent
import h3.presenter.TapReducer
import h3.presenter.TapState
import h3.sim.BattleCommand
import h3.sim.BattleEvent
import h3.sim.BattleState
import h3.sim.Hex
import h3.sim.HexCell
import h3.presenter.ui.BattleLog
import h3.sim.Replay
import h3.sim.legalCommands
import java.math.BigInteger

/** Everything a screen needs to draw one moment of the battle. Immutable. */
data class GameUi(
    val seq: Int,
    val state: BattleState,
    val hash: String,
    val tap: TapState,
    val humanTurn: Boolean,
    /** Head cells the active stack can move to. */
    val moveHexes: Set<HexCell>,
    /** Stack ids the active stack can attack or shoot. */
    val targetIds: Set<Int>,
    val canWait: Boolean,
    val canDefend: Boolean,
    val message: String?,
    val fault: String?,
    val stalled: Boolean,
    val recent: List<String>,
    /** The capped battle log (see BattleLog); screens group it by round. */
    val log: BattleLog,
)

/**
 * Glue between the screens and [BattleSession]. The human plays the attacker side; the greedy AI
 * plays the defender on the session worker. [onChange] is called from the worker thread (after an
 * AI reply or an accepted command) AND from the caller's thread (after a tap), so the app must
 * marshal it to the main thread. All fields are guarded by [lock]; [onChange] runs outside it.
 * No Android imports here.
 */
class GameController(
    private val engine: AppEngine,
    /** The state the battle started from; the result screen compares it with the final state. */
    val initialState: BattleState,
    /** Canonical scenario JSON, needed to write replay (save) files. */
    private val scenarioJson: String,
    private val masterSeed: BigInteger,
    /** Autosave after every accepted command (a ReplayAutosave), or null for none. */
    autosave: AutosaveSink?,
    private val onChange: (GameUi) -> Unit,
) {
    private val worker = BattleSession.newWorker()
    private val session = BattleSession(
        engine.battle, engine.codec, engine.ai, initialState, masterSeed,
        setOf(Hex.ATTACKER), worker, MAX_AI_COMMANDS, autosave,
    )
    private val reducer = TapReducer(engine.battle)
    private val lock = Any()
    private var tap: TapState = TapState.Idle
    private var message: String? = null
    private var recent: List<String> = emptyList()
    private var battleLog: BattleLog = BattleLog.empty()

    init {
        session.addListener { snap -> onSnapshot(snap) }
    }

    /** Queues Begin; the first snapshot arrives through [onChange]. */
    fun start() {
        session.start()
    }

    /** Resumes from a verified save instead of [start]: feeds the whole log to the fresh session. */
    fun resume(resumed: Resumed, reply: (h3.presenter.SubmitResult) -> Unit = {}) {
        ReplayResume.into(session, resumed, reply)
    }

    /** The replay file bytes of the game so far (for a manual save). Safe to call from any thread. */
    fun replayBytes(): ByteArray =
        Replay.record(scenarioJson, session.log().map { it.command }, masterSeed, engine.packs)

    /** The newest view, safe to call from any thread. */
    fun current(): GameUi = synchronized(lock) { build(session.latest()) }

    fun finalHash(): String = session.finalHash()

    fun close() {
        worker.shutdownNow()
    }

    private fun onSnapshot(snap: Snapshot) {
        val ui = synchronized(lock) {
            tap = TapState.Idle
            message = null
            val lines = snap.events.map { describe(it) }
            if (lines.isNotEmpty()) recent = (lines + recent).take(MAX_RECENT)
            battleLog = battleLog.add(snap.state, snap.events)
            build(snap)
        }
        onChange(ui)
    }

    /** A tap on a board cell. Ignored unless it is the human's turn. */
    fun onTap(hex: HexCell) {
        val snap = session.latest()
        var toSend: BattleCommand? = null
        val ui = synchronized(lock) {
            if (!isHumanTurn(snap)) return
            val next = reducer.reduce(tap, TapEvent.Tap(hex), snap.state)
            if (next is TapState.Confirmed) {
                toSend = next.command
                tap = TapState.Idle
            } else {
                tap = next
            }
            message = null
            build(snap)
        }
        onChange(ui)
        toSend?.let { send(snap.seq, it) }
    }

    fun onSelect(index: Int) {
        val snap = session.latest()
        val ui = synchronized(lock) {
            tap = reducer.reduce(tap, TapEvent.Select(index), snap.state)
            build(snap)
        }
        onChange(ui)
    }

    fun onCancel() {
        val snap = session.latest()
        val ui = synchronized(lock) {
            tap = TapState.Idle
            message = null
            build(snap)
        }
        onChange(ui)
    }

    /** Confirm button: sends the command of the current preview, as a second tap would. */
    fun onConfirm() {
        val snap = session.latest()
        var cmd: BattleCommand? = null
        synchronized(lock) {
            val t = tap
            if (t is TapState.Previewing && isHumanTurn(snap)) cmd = t.command
            tap = TapState.Idle
        }
        cmd?.let { send(snap.seq, it) }
    }

    fun onWait() = sendActive { BattleCommand.Wait(it) }

    fun onDefend() = sendActive { BattleCommand.Defend(it) }

    private fun sendActive(make: (Int) -> BattleCommand) {
        val snap = session.latest()
        val a = snap.state.active
        if (a == null || !isHumanTurn(snap)) return
        send(snap.seq, make(a))
    }

    private fun send(expectedSeq: Int, cmd: BattleCommand) {
        session.submit(expectedSeq, cmd, Origin.Human) { r ->
            val text = rejection(r)
            if (text != null) {
                val ui = synchronized(lock) {
                    message = text
                    build(session.latest())
                }
                onChange(ui)
            }
        }
    }

    private fun rejection(r: SubmitResult): String? = when (r) {
        is SubmitResult.Accepted -> null
        is SubmitResult.Stale -> "The position changed; tap again."
        is SubmitResult.Illegal -> "Illegal move: " + r.reason
        is SubmitResult.NotYourTurn -> "Not your turn."
        SubmitResult.Over -> "The battle is over."
        SubmitResult.Stalled -> "The AI stopped (stalemate guard)."
        is SubmitResult.Faulted -> "Engine fault: " + r.reason
        SubmitResult.ShutDown -> "The game was closed."
    }

    private fun isHumanTurn(snap: Snapshot): Boolean {
        val st = snap.state
        val a = st.active ?: return false
        return snap.fault == null && st.started && st.winner == null && st.stacks[a].side == Hex.ATTACKER
    }

    private fun build(snap: Snapshot): GameUi {
        val st = snap.state
        val human = isHumanTurn(snap)
        val moves = LinkedHashSet<HexCell>()
        val targets = LinkedHashSet<Int>()
        var canWait = false
        var canDefend = false
        if (human) {
            for (c in engine.battle.legalCommands(st)) {
                when (c) {
                    is BattleCommand.Move -> moves.add(HexCell(c.dest.first, c.dest.second))
                    is BattleCommand.Attack -> targets.add(c.target)
                    is BattleCommand.Shoot -> targets.add(c.target)
                    is BattleCommand.Wait -> canWait = true
                    is BattleCommand.Defend -> canDefend = true
                    BattleCommand.Begin -> {}
                }
            }
        }
        return GameUi(
            snap.seq, st, snap.stateHash, tap, human, moves, targets, canWait, canDefend,
            message, snap.fault ?: session.fault(), session.isStalled(), recent, battleLog,
        )
    }

    private fun describe(e: BattleEvent): String = when (e) {
        is BattleEvent.RoundStarted -> "Round " + e.round
        is BattleEvent.DamageDealt -> "Stack " + e.attacker + " hits stack " + e.target + " for " + e.damage + ", " + e.killed + " killed"
        is BattleEvent.UnitDied -> "Stack " + e.stack + " is wiped out"
        is BattleEvent.BattleEnded -> "Battle over"
        is BattleEvent.Waited -> "Stack " + e.stack + " waits"
        is BattleEvent.Defended -> "Stack " + e.stack + " defends"
        is BattleEvent.Moved -> "Stack " + e.stack + " moves"
        else -> e.toString()
    }

    companion object {
        const val MAX_AI_COMMANDS = 5000
        const val MAX_RECENT = 6
    }
}
