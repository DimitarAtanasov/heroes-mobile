package h3.presenter.ui

import h3.sim.Hex

/** One roster row as text: [title] is the first line, [detail] the second. */
data class RosterEntry(val row: StackRosterRow, val title: String, val detail: String)

/** One slot of the turn-order strip: [label] is short enough for a chip ("A Pikeman"). */
data class TurnChip(val id: Int, val side: Int, val label: String, val active: Boolean)

/**
 * Pure text for the battle side panels (roster, turn order, log headers). UI only: it reads
 * roster and log models and changes nothing, so the composables hold no string logic.
 */
object BattlePanels {
    /** Entries for [rows], same order. A dead stack stays listed, marked as such. */
    fun entries(rows: List<StackRosterRow>): List<RosterEntry> = rows.map { entry(it) }

    fun entry(row: StackRosterRow): RosterEntry {
        if (!row.alive) return RosterEntry(row, row.name + " (wiped out)", "")
        val title = row.count.toString() + " " + row.name
        val tail = if (row.defending) ", defending" else ""
        val detail = "HP " + row.topHp + "/" + row.maxHp + ", total " + row.totalHp + tail
        return RosterEntry(row, title, detail)
    }

    /** The turn order as chips: living stacks still to act, next one first. */
    fun turnChips(roster: StackRoster): List<TurnChip> {
        val rows = roster.attackers + roster.defenders
        val out = ArrayList<TurnChip>()
        for (id in roster.turnOrder) {
            val row = rows.firstOrNull { it.id == id } ?: continue
            val prefix = if (row.side == Hex.ATTACKER) "A " else "D "
            out.add(TurnChip(row.id, row.side, prefix + row.name, row.active))
        }
        return out
    }

    /** Header of a log group: "Start" before the first round, else "Round N". */
    fun logHeader(group: BattleLogGroup): String = if (group.round <= 0) "Start" else "Round " + group.round

    /** Section titles of the roster panel. */
    fun sideTitle(side: Int): String = if (side == Hex.ATTACKER) "You (attacker)" else "Computer (defender)"
}
