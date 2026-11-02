package h3.presenter.ui

import h3.presenter.Atlas
import h3.presenter.DefFrames
import h3.presenter.Rect
import h3.sim.Battle
import h3.sim.BattleStack
import h3.sim.BattleState
import h3.sim.Hex

/**
 * Pure keys for the sprite atlas, derived from the creature name alone (the creature-to-DEF mapping
 * of android-app.md G3 is the loader's job; it builds frames with `DefFrames.from(prefix(name), def)`
 * for the player's own game files, and nothing here reads any). The same key serves both sides: the
 * defender is drawn mirrored ([StackRosterRow.flipX]), not from a second sprite.
 */
object UiSpriteKey {
    /** DEF group 2 is "idle" (android-app.md 4.3); frame 0 is the still shown on the board and roster. */
    const val IDLE_GROUP = 2

    /** `creature/<slug>`: lower-case ASCII letters and digits, any other run becomes one `_`. */
    fun prefix(creatureName: String): String {
        val sb = StringBuilder()
        var gap = false
        for (c in creatureName) {
            val low = if (c in 'A'..'Z') c + ('a' - 'A') else c
            if (low in 'a'..'z' || low in '0'..'9') {
                if (gap && sb.isNotEmpty()) sb.append('_')
                gap = false
                sb.append(low)
            } else {
                gap = true
            }
        }
        return "creature/" + if (sb.isEmpty()) "unknown" else sb.toString()
    }

    /** Atlas key of the idle still: `<prefix>/002/0000` (same format as `DefFrames.key`). */
    fun idleKey(creatureName: String): String = DefFrames.key(prefix(creatureName), IDLE_GROUP, 0)

    /** The atlas rectangle of the idle still of [creatureName] (see [rectOf]). */
    fun idleRect(atlas: Atlas?, creatureName: String): Rect? = rectOf(atlas, idleKey(creatureName))

    /** The atlas rectangle of [key], or null when there is no atlas, no such key or an empty frame. */
    fun rectOf(atlas: Atlas?, key: String): Rect? {
        val r = atlas?.rects?.get(key) ?: return null
        return if (r.page < 0 || r.w <= 0 || r.h <= 0) null else r
    }

    /** First letter of the shown name, upper case ASCII, "?" when there is none (the no-atlas glyph). */
    fun fallbackLetter(shownName: String): String {
        val n = shownName.trim()
        if (n.isEmpty()) return "?"
        val c = n[0]
        return (if (c in 'a'..'z') c - ('a' - 'A') else c).toString()
    }

    /** Count plate text: the count up to 9999, then thousands floored with a `k` (10000 -> "10k"). */
    fun countBadge(count: Int): String =
        if (count <= 0) "" else if (count < 10_000) count.toString() else (count / 1000).toString() + "k"
}

/**
 * One roster row: a stack as the side panel shows it. [turnPos] is the 0-based place in the turn
 * order (the active stack is 0), or null when the stack is not queued (acted already, or dead).
 */
data class StackRosterRow(
    val id: Int,
    val side: Int,
    val name: String,
    val count: Int,
    /** Health of the top unit of the stack. */
    val topHp: Int,
    /** Full health of one unit of this creature. */
    val maxHp: Int,
    /** Total health of the whole stack: (count - 1) * maxHp + topHp, 0 when dead. */
    val totalHp: Long,
    val alive: Boolean,
    val active: Boolean,
    val turnPos: Int?,
    /** Sprite data (pure strings and flags; see [UiSpriteKey]). Valid with or without an atlas. */
    val spritePrefix: String,
    val idleKey: String,
    /** True for the defender: its sprite faces left, drawn as a horizontal flip of the right-facing one. */
    val flipX: Boolean,
    val doubleWide: Boolean,
    val defending: Boolean,
    /** Count plate text; empty for a dead stack. */
    val countBadge: String,
    /** Letter drawn in the token when no sprite is available. */
    val fallbackLetter: String,
) {
    /** The atlas rectangle to draw, or null: draw a token with [fallbackLetter] then. */
    fun spriteRect(atlas: Atlas?): Rect? = UiSpriteKey.rectOf(atlas, idleKey)
}

/**
 * Rows per side in slot order (then id), plus the turn order of living stacks. Pure UI data: it
 * reads a [BattleState] and changes nothing. Dead stacks stay as rows (alive = false) so the panel
 * does not jump. A leading "Test " is dropped from names, as for the board tokens.
 */
data class StackRoster(
    val attackers: List<StackRosterRow>,
    val defenders: List<StackRosterRow>,
    /** Ids of living stacks still to act, in order; equals the rows' [StackRosterRow.turnPos]. */
    val turnOrder: List<Int>,
) {
    /** The id of the living active stack, or null. */
    val activeId: Int? get() = (attackers + defenders).firstOrNull { it.active }?.id

    companion object {
        /** Roster using the engine's own turn order for [state] (`Battle.turnOrder`). */
        fun build(battle: Battle, state: BattleState): StackRoster = build(state, battle.turnOrder(state))

        /**
         * Roster for an explicit [order]. Ids that are unknown or dead are dropped, and a repeated
         * id keeps its first place.
         */
        fun build(state: BattleState, order: List<Int>): StackRoster {
            val alive = state.stacks.filter { it.alive }.map { it.id }
            val queued = ArrayList<Int>()
            for (id in order) if (id in alive && id !in queued) queued.add(id)
            val act = state.active
            fun row(s: BattleStack): StackRosterRow {
                val pos = queued.indexOf(s.id)
                val hp = s.creature.hp
                val shown = s.creature.name.removePrefix("Test ")
                return StackRosterRow(
                    id = s.id, side = s.side, name = shown, count = s.count,
                    topHp = s.topHp, maxHp = hp,
                    totalHp = if (s.alive) (s.count - 1).toLong() * hp + s.topHp else 0L,
                    alive = s.alive, active = s.alive && s.id == act, turnPos = if (pos < 0) null else pos,
                    spritePrefix = UiSpriteKey.prefix(s.creature.name), idleKey = UiSpriteKey.idleKey(s.creature.name),
                    flipX = s.side != Hex.ATTACKER, doubleWide = s.creature.doubleWide, defending = s.defending,
                    countBadge = if (s.alive) UiSpriteKey.countBadge(s.count) else "", fallbackLetter = UiSpriteKey.fallbackLetter(shown),
                )
            }
            val sorted = state.stacks.sortedWith(compareBy({ it.slot }, { it.id }))
            return StackRoster(
                attackers = sorted.filter { it.side == Hex.ATTACKER }.map(::row),
                defenders = sorted.filter { it.side != Hex.ATTACKER }.map(::row),
                turnOrder = queued,
            )
        }
    }
}
