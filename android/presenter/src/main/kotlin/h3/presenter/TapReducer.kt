package h3.presenter

import h3.sim.Battle
import h3.sim.BattleCommand
import h3.sim.BattleState
import h3.sim.HexCell
import h3.sim.Present
import h3.sim.legalCommands

/**
 * Damage preview of one candidate (view v2 `preview`): the damage range and the kills each bound
 * would cause. Integers only.
 */
data class PreviewNumbers(
    val floor: Long, val expected: Long, val ceiling: Long,
    val killsFloor: Long, val killsExpected: Long, val killsCeiling: Long,
)

/** One command a tap can mean. [preview] is null for moves. */
data class Candidate(val command: BattleCommand, val preview: PreviewNumbers?)

/** Inputs of the tap interaction (android-app.md 5.1). Hexes are integer board cells. */
sealed interface TapEvent {
    data class Tap(val hex: HexCell) : TapEvent
    data class LongPress(val hex: HexCell) : TapEvent
    data class Select(val index: Int) : TapEvent
    data object Cancel : TapEvent
}

/** UI state of the preview-then-confirm interaction. Immutable. */
sealed interface TapState {
    data object Idle : TapState

    /**
     * [hex] is the canonical target hex: the destination for a move, the stack's head cell for a
     * target (any cell of a two-hex unit resolves to it). [candidates] is in `legalCommands` order.
     */
    data class Previewing(val hex: HexCell, val candidates: List<Candidate>, val selected: Int) : TapState {
        val command: BattleCommand get() = candidates[selected].command
    }

    /** Terminal result: send exactly [command] to the session. */
    data class Confirmed(val command: BattleCommand) : TapState
}

/**
 * Pure reducer for the preview-then-confirm interaction. It reads only the engine's presenter
 * view ([Present.candidateCommands], [Present.candidateActions]) and never builds a command from
 * parts: a confirmed command is always an element of the current `legalCommands` list.
 *
 * Rules:
 *  - Tap on a hex with no candidate: no-op (state unchanged).
 *  - Tap on a legal hex or target while not previewing it: Previewing (re-targets from another one).
 *  - Tap on the hex being previewed: Confirmed, provided the previewed command is still legal in
 *    the given state; otherwise the preview is rebuilt from the current state.
 *  - LongPress on a legal hex: Previewing, never confirms (inspect).
 *  - Select(i): choose among the candidates of the current preview.
 *  - Cancel: Idle. Any event in Confirmed starts again from Idle.
 */
class TapReducer(private val battle: Battle) {
    private val present = Present(battle)

    fun reduce(ui: TapState, event: TapEvent, state: BattleState): TapState {
        val cur = if (ui is TapState.Confirmed) TapState.Idle else ui
        return when (event) {
            TapEvent.Cancel -> TapState.Idle
            is TapEvent.Select ->
                if (cur is TapState.Previewing && event.index in cur.candidates.indices) cur.copy(selected = event.index) else cur
            is TapEvent.LongPress -> preview(state, event.hex) ?: cur
            is TapEvent.Tap -> {
                val next = preview(state, event.hex) ?: return cur
                if (cur is TapState.Previewing && cur.hex == next.hex &&
                    cur.command in battle.legalCommands(state)
                ) {
                    TapState.Confirmed(cur.command)
                } else {
                    next
                }
            }
        }
    }

    private fun preview(state: BattleState, hex: HexCell): TapState.Previewing? {
        val cell = Pair(hex.col, hex.row)
        val cmds = present.candidateCommands(state, cell)
        if (cmds.isEmpty()) return null
        val entry = present.candidateActions(state, cell) ?: return null
        val previews = previewsOf(entry)
        val cands = cmds.map { Candidate(it, previews[present.commandToDict(it)]) }
        @Suppress("UNCHECKED_CAST")
        val head = (entry["hex"] as List<Int>).let { HexCell(it[0], it[1]) }
        val sel = cands.indexOfFirst { it.command is BattleCommand.Shoot }.takeIf { it >= 0 }
            ?: cands.indexOfFirst { (it.command as? BattleCommand.Attack)?.fromHex == null && it.command is BattleCommand.Attack }
                .takeIf { it >= 0 }
            ?: 0
        return TapState.Previewing(head, cands, sel)
    }

    @Suppress("UNCHECKED_CAST")
    private fun previewsOf(entry: Map<String, Any?>): Map<Map<String, Any?>, PreviewNumbers> {
        val out = LinkedHashMap<Map<String, Any?>, PreviewNumbers>()
        val target = entry["target"] as Map<String, Any?>? ?: return out
        val shoot = target["shoot"] as Map<String, Any?>?
        if (shoot != null) out[shoot["command"] as Map<String, Any?>] = numbers(shoot["preview"] as Map<String, Any?>)
        for (a in target["attacks"] as List<Map<String, Any?>>) {
            out[a["command"] as Map<String, Any?>] = numbers(a["preview"] as Map<String, Any?>)
        }
        return out
    }

    @Suppress("UNCHECKED_CAST")
    private fun numbers(p: Map<String, Any?>): PreviewNumbers {
        fun l(v: Any?) = (v as Number).toLong()
        val k = p["kills"] as Map<String, Any?>
        return PreviewNumbers(
            l(p["floor"]), l(p["expected"]), l(p["ceiling"]),
            l(k["floor"]), l(k["expected"]), l(k["ceiling"]),
        )
    }
}
