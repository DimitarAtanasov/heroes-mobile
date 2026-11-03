package h3.presenter.ui

/**
 * How many rows the sprite table and the battle roster disagree on (sprite-atlas.md, "Creature sprite
 * table"; roster-from-crtraits.md slice 5): [tableOnly] distinct table rows that are not a roster row,
 * [rosterOnly] distinct roster rows with no table entry. Counts only, so a log line never names a
 * creature, a DEF or a row of the player's file.
 *
 * The roster is the battle roster ([GameRosterResult.Ok]), which leaves out the creatures with no
 * fixed damage, so table rows for those count as [tableOnly] too.
 */
data class RowMismatch(val tableOnly: Int, val rosterOnly: Int) {
    val matches: Boolean get() = tableOnly == 0 && rosterOnly == 0

    fun describe(): String = "SPRITE_ROWS table_only=$tableOnly roster_only=$rosterOnly"
}

/**
 * The parsed table, the `(row, creature name)` pairs for [SpriteLoadPlan.loadByRow], and the lines to
 * log. [table] is null when the table text was refused: the board then keeps its tokens and [notes]
 * holds every [SpriteTableError.describe] line, with [pairs] empty.
 */
class PreparedSprites(val table: Map<Int, String>?, val pairs: List<Pair<Int, String>>, val notes: List<String>)

/**
 * The pure part of wiring the row-keyed sprite table into the app (ADR-0014): from the bundled
 * `sprite_map.json` text and the player's roster, what to load and what to log. The app does the
 * asset read, the archive reads and the thread; nothing here touches a file, a clock or a thread.
 */
object SpriteRows {
    /** One `(row, BattleCreature.name)` pair per roster entry, in roster order; the name is the atlas key. */
    fun pairs(entries: List<GameRosterEntry>): List<Pair<Int, String>> = entries.map { it.row to it.creature.name }

    /** Row disagreement between [table] and [entries], counting each distinct row once. */
    fun mismatch(table: Map<Int, String>, entries: List<GameRosterEntry>): RowMismatch {
        val rosterRows = entries.map { it.row }.toSet()
        return RowMismatch(
            tableOnly = table.keys.count { it !in rosterRows },
            rosterOnly = rosterRows.count { it !in table },
        )
    }

    /**
     * Parses [tableText] with [SpriteTable.parse]. On success: the table, the pairs of [entries], and
     * one [RowMismatch.describe] line when the rows do not match (none when they do). On failure: no
     * table, no pairs, one line per parse error. Never throws.
     */
    fun prepare(tableText: String, entries: List<GameRosterEntry>): PreparedSprites =
        when (val r = SpriteTable.parse(tableText)) {
            is SpriteTableResult.Failed -> PreparedSprites(null, emptyList(), r.errors.map { it.describe() })
            is SpriteTableResult.Ok -> {
                val m = mismatch(r.table, entries)
                PreparedSprites(r.table, pairs(entries), if (m.matches) emptyList() else listOf(m.describe()))
            }
        }
}
