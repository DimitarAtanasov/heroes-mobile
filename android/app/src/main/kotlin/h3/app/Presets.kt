package h3.app

import h3.sim.BattleCreature

/** One built-in skirmish. [stacks] are (creature name, count) per side, slot order. */
class Preset(
    val id: String,
    val title: String,
    val blurb: String,
    private val attackers: List<Pair<String, Int>>,
    private val defenders: List<Pair<String, Int>>,
    private val obstacles: List<Pair<Int, Int>>,
) {
    /**
     * The scenario JSON text (docs/specs/battle-scenario.md). The creature table is written from the
     * bundled placeholder roster, so no balance number lives in this file. Throws
     * IllegalArgumentException when the roster lacks a creature the preset names.
     */
    fun scenarioJson(roster: List<BattleCreature>): String {
        val byName = roster.associateBy { it.name }
        val used = (attackers + defenders).map { it.first }.distinct()
        val sb = StringBuilder()
        sb.append("{\"battle_id\":").append(q(id)).append(",\"creatures\":{")
        used.forEachIndexed { i, n ->
            val c = byName[n] ?: throw IllegalArgumentException("creature '$n' is not in the roster")
            if (i > 0) sb.append(',')
            sb.append(q(n)).append(':').append(creatureJson(c))
        }
        sb.append("},\"attackers\":").append(side(attackers))
        sb.append(",\"defenders\":").append(side(defenders))
        sb.append(",\"obstacles\":[")
        obstacles.forEachIndexed { i, o ->
            if (i > 0) sb.append(',')
            sb.append('[').append(o.first).append(',').append(o.second).append(']')
        }
        sb.append("]}")
        return sb.toString()
    }

    private fun side(list: List<Pair<String, Int>>): String =
        list.joinToString(",", "[", "]") { "{\"creature\":" + q(it.first) + ",\"count\":" + it.second + "}" }

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

        private const val PIKE = "Test Pikeman"
        private const val SLING = "Test Slinger"
        private const val GLIDE = "Test Glider"
        private const val BRUTE = "Test Brute"

        /** Difficulty is just which preset: Easy tilts the numbers to the player, Hard against. */
        val ALL: List<Preset> = listOf(
            Preset(
                "skirmish-easy", "Easy: outnumber them",
                "Two stacks each. You field twice their numbers.",
                listOf(PIKE to 24, SLING to 12),
                listOf(PIKE to 10, SLING to 6),
                listOf(Pair(8, 2), Pair(8, 8)),
            ),
            Preset(
                "skirmish-even", "Normal: even match",
                "Three stacks each, equal strength, a few rocks in the middle.",
                listOf(PIKE to 16, SLING to 10, GLIDE to 6),
                listOf(PIKE to 16, SLING to 10, GLIDE to 6),
                listOf(Pair(7, 3), Pair(9, 5), Pair(7, 7), Pair(8, 9)),
            ),
            Preset(
                "skirmish-hard", "Hard: outgunned",
                "They bring a two-hex Brute and more of everything.",
                listOf(PIKE to 14, SLING to 8, GLIDE to 5),
                listOf(PIKE to 18, SLING to 12, GLIDE to 8, BRUTE to 4),
                listOf(Pair(8, 1), Pair(7, 5), Pair(9, 5), Pair(8, 9)),
            ),
        )
    }
}
