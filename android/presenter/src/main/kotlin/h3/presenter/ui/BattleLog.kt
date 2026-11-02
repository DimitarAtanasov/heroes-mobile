package h3.presenter.ui

import h3.sim.BattleEvent
import h3.sim.BattleState
import h3.sim.Hex

/** What a log line reports; lets a renderer pick an icon without parsing [BattleLogLine.text]. */
enum class BattleLogKind { START, MOVE, WAIT, DEFEND, MORALE_LOST, MORALE_GAIN, LUCK_GOOD, LUCK_BAD, HIT, SHOOT, RETALIATE, DIED, END }

/**
 * One line of the battle log. [text] is complete on its own (the no-atlas rendering). The parts let a
 * sprite renderer build the same line from pieces: [actorId] and [targetId] are stack ids, the keys are
 * the idle-still atlas keys of their creatures ([UiSpriteKey.idleKey]; null when there is no such
 * stack), [damage] and [killed] are set for HIT, SHOOT and RETALIATE. [side] is the acting side, or the
 * winner for END, or null.
 */
data class BattleLogLine(
    val round: Int,
    val side: Int?,
    val text: String,
    val kind: BattleLogKind = BattleLogKind.START,
    val actorId: Int? = null,
    val targetId: Int? = null,
    val actorKey: String? = null,
    val targetKey: String? = null,
    val damage: Long = 0,
    val killed: Int = 0,
)

/** Consecutive log lines of one round, oldest first. Round 0 is everything before the first round. */
data class BattleLogGroup(val round: Int, val lines: List<BattleLogLine>)

/**
 * Pure, immutable battle log (UI only; never part of a state, command or hash).
 *
 * Each [add] takes the state AFTER one `apply` and the events it produced. The stack ids in the
 * events are looked up in that state for the creature name and side (ids and sides never change
 * during a battle, and dead stacks stay in `stacks`). A leading "Test " is dropped from names, as
 * the board tokens do (the roster names all carry it). `RoundStarted` is not a line: it moves
 * [round], which the following lines carry, and [groups] turns into headers. `TurnStarted` is
 * not logged (the action line says who acted). At most [cap] lines are kept, the newest ones.
 */
data class BattleLog(val lines: List<BattleLogLine>, val round: Int, val cap: Int) {
    init {
        require(cap >= 1) { "cap must be at least 1" }
    }

    /** The log after [events], in order, trimmed to the newest [cap] lines. */
    fun add(after: BattleState, events: List<BattleEvent>): BattleLog {
        var r = round
        val out = ArrayList<BattleLogLine>(lines)
        for (e in events) {
            if (e is BattleEvent.RoundStarted) {
                r = e.round
                continue
            }
            describe(after, e, r)?.let { out.add(it) }
        }
        val kept = if (out.size > cap) out.subList(out.size - cap, out.size) else out
        return BattleLog(ArrayList(kept), r, cap)
    }

    /** Lines grouped by consecutive round, in order. */
    fun groups(): List<BattleLogGroup> {
        val out = ArrayList<BattleLogGroup>()
        var cur = ArrayList<BattleLogLine>()
        for (l in lines) {
            if (cur.isNotEmpty() && cur[0].round != l.round) {
                out.add(BattleLogGroup(cur[0].round, cur))
                cur = ArrayList()
            }
            cur.add(l)
        }
        if (cur.isNotEmpty()) out.add(BattleLogGroup(cur[0].round, cur))
        return out
    }

    companion object {
        const val DEFAULT_CAP = 60

        fun empty(cap: Int = DEFAULT_CAP): BattleLog = BattleLog(emptyList(), 0, cap)

        /** The line for one event in [round], or null for events that are not logged. */
        fun describe(after: BattleState, e: BattleEvent, round: Int): BattleLogLine? {
            fun who(id: Int): String = logStackLabel(after, id)
            fun side(id: Int): Int? = after.stacks.firstOrNull { it.id == id }?.side
            fun key(id: Int): String? = after.stacks.firstOrNull { it.id == id }?.let { UiSpriteKey.idleKey(it.creature.name) }
            fun act(kind: BattleLogKind, id: Int, text: String) = BattleLogLine(round, side(id), text, kind, id, null, key(id), null)
            return when (e) {
                is BattleEvent.BattleStarted -> BattleLogLine(round, null, "Battle begins", BattleLogKind.START)
                is BattleEvent.RoundStarted -> null
                is BattleEvent.TurnStarted -> null
                is BattleEvent.MoraleFrozen -> act(BattleLogKind.MORALE_LOST, e.stack, who(e.stack) + " loses its turn (bad morale)")
                is BattleEvent.MoraleBoost -> act(BattleLogKind.MORALE_GAIN, e.stack, who(e.stack) + " gains an extra turn (good morale)")
                is BattleEvent.Moved -> {
                    val last = e.path.lastOrNull()
                    val to = if (last == null) "" else " to (" + last.first + "," + last.second + ")"
                    act(BattleLogKind.MOVE, e.stack, who(e.stack) + " moves" + to)
                }
                is BattleEvent.Waited -> act(BattleLogKind.WAIT, e.stack, who(e.stack) + " waits")
                is BattleEvent.Defended -> act(BattleLogKind.DEFEND, e.stack, who(e.stack) + " defends")
                is BattleEvent.LuckRolled ->
                    if (e.good) act(BattleLogKind.LUCK_GOOD, e.stack, who(e.stack) + " has good luck")
                    else act(BattleLogKind.LUCK_BAD, e.stack, who(e.stack) + " has bad luck")
                is BattleEvent.DamageDealt -> {
                    val verb = if (e.retaliation) " retaliates against " else if (e.ranged) " shoots " else " hits "
                    val kind = if (e.retaliation) BattleLogKind.RETALIATE else if (e.ranged) BattleLogKind.SHOOT else BattleLogKind.HIT
                    BattleLogLine(
                        round, side(e.attacker), who(e.attacker) + verb + who(e.target) + " for " + e.damage + ", " + e.killed + " killed",
                        kind, e.attacker, e.target, key(e.attacker), key(e.target), e.damage, e.killed,
                    )
                }
                is BattleEvent.UnitDied -> act(BattleLogKind.DIED, e.stack, who(e.stack) + " is wiped out")
                is BattleEvent.BattleEnded -> BattleLogLine(round, e.winner, "Battle over: " + logSideName(e.winner) + " wins", BattleLogKind.END)
            }
        }

        private fun logSideName(side: Int): String = if (side == Hex.ATTACKER) "Attacker" else if (side == Hex.DEFENDER) "Defender" else "Side $side"

        /** "Attacker Pikeman", or "Stack 9" when the id is not in the state. */
        private fun logStackLabel(after: BattleState, id: Int): String {
            val s = after.stacks.firstOrNull { it.id == id } ?: return "Stack $id"
            return logSideName(s.side) + " " + s.creature.name.removePrefix("Test ")
        }
    }
}
