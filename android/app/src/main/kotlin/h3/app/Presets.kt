package h3.app

import h3.presenter.ui.GameRosterEntry
import h3.sim.BattleCreature

/**
 * One built-in skirmish. The stacks are (CRTRAITS data-row index, count) per side, slot order: a preset
 * names its creatures by row, never by name (owner decision Q7, roster-from-crtraits.md).
 */
class Preset(
    val id: String,
    val title: String,
    val blurb: String,
    private val attackers: List<Pair<Int, Int>>,
    private val defenders: List<Pair<Int, Int>>,
    private val obstacles: List<Pair<Int, Int>>,
) {
    /** The distinct rows this preset uses, in first-use order (attackers, then defenders); for `PresetCheck`. */
    val rows: List<Int> get() = (attackers + defenders).map { it.first }.distinct()

    /**
     * The scenario JSON text (docs/specs/battle-scenario.md). The creature table is written from the
     * player's roster (`GameRoster`), so no balance number lives in this file; the scenario names each
     * creature by its roster name. Throws IllegalArgumentException when the roster lacks a row the
     * preset uses (the Setup screen disables such a preset first, `PresetCheck`).
     */
    fun scenarioJson(roster: List<GameRosterEntry>): String {
        val byRow = roster.associateBy { it.row }
        fun creature(row: Int): BattleCreature =
            byRow[row]?.creature ?: throw IllegalArgumentException("creature row $row is not in the roster")
        val sb = StringBuilder()
        sb.append("{\"battle_id\":").append(q(id)).append(",\"creatures\":{")
        rows.forEachIndexed { i, row ->
            val c = creature(row)
            if (i > 0) sb.append(',')
            sb.append(q(c.name)).append(':').append(creatureJson(c))
        }
        sb.append("},\"attackers\":").append(side(attackers, ::creature))
        sb.append(",\"defenders\":").append(side(defenders, ::creature))
        sb.append(",\"obstacles\":[")
        obstacles.forEachIndexed { i, o ->
            if (i > 0) sb.append(',')
            sb.append('[').append(o.first).append(',').append(o.second).append(']')
        }
        sb.append("]}")
        return sb.toString()
    }

    private fun side(list: List<Pair<Int, Int>>, creature: (Int) -> BattleCreature): String =
        list.joinToString(",", "[", "]") { "{\"creature\":" + q(creature(it.first).name) + ",\"count\":" + it.second + "}" }

    companion object {
        private fun q(s: String): String {
            val sb = StringBuilder("\"")
            for (ch in s) {
                if (ch == '"' || ch == '\\') sb.append('\\')
                sb.append(ch)
            }
            return sb.append('"').toString()
        }

        private fun creatureJson(c: BattleCreature): String {
            val sb = StringBuilder("{")
            sb.append("\"attack\":").append(c.attack)
            sb.append(",\"defense\":").append(c.defense)
            sb.append(",\"dmg_min\":").append(c.dmgMin)
            sb.append(",\"dmg_max\":").append(c.dmgMax)
            sb.append(",\"hp\":").append(c.hp)
            sb.append(",\"speed\":").append(c.speed)
            sb.append(",\"shots\":").append(c.shots)
            fun flag(k: String, v: Boolean) { sb.append(",\"").append(k).append("\":").append(if (v) "true" else "false") }
            flag("flyer", c.flyer)
            flag("double_wide", c.doubleWide)
            flag("no_enemy_retaliation", c.noEnemyRetaliation)
            flag("unlimited_retaliation", c.unlimitedRetaliation)
            flag("no_melee_penalty", c.noMeleePenalty)
            flag("no_range_penalty", c.noRangePenalty)
            flag("strikes_twice", c.strikesTwice)
            flag("shoots_twice", c.shootsTwice)
            flag("no_morale", c.noMorale)
            sb.append(",\"hates\":").append(c.hates.joinToString(",", "[", "]") { q(it) })
            return sb.append('}').toString()
        }

        // Default CRTRAITS data rows (owner decision Q7, 2026-11-03; the owner confirms the default):
        // rows 0, 2 and 4, the placeholder creatures of the VCMI-derived sprite table (ADR-0014).
        private const val ROW_A = 0
        private const val ROW_B = 2
        private const val ROW_C = 4

        /** Difficulty is just which preset: Easy tilts the numbers to the player, Hard against. */
        val ALL: List<Preset> = listOf(
            Preset(
                "skirmish-easy", "Easy: outnumber them",
                "Two stacks each. You field twice their numbers.",
                listOf(ROW_A to 24, ROW_B to 12),
                listOf(ROW_A to 10, ROW_B to 6),
                listOf(Pair(8, 2), Pair(8, 8)),
            ),
            Preset(
                "skirmish-even", "Normal: even match",
                "Three stacks each, equal strength, a few rocks in the middle.",
                listOf(ROW_A to 16, ROW_B to 10, ROW_C to 6),
                listOf(ROW_A to 16, ROW_B to 10, ROW_C to 6),
                listOf(Pair(7, 3), Pair(9, 5), Pair(7, 7), Pair(8, 9)),
            ),
            Preset(
                "skirmish-hard", "Hard: outgunned",
                "Three stacks each. They bring more of everything.",
                listOf(ROW_A to 14, ROW_B to 8, ROW_C to 5),
                listOf(ROW_A to 18, ROW_B to 12, ROW_C to 8),
                listOf(Pair(8, 1), Pair(7, 5), Pair(9, 5), Pair(8, 9)),
            ),
        )
    }
}
