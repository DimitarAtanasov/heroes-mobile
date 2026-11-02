package h3.presenter

import h3.sim.BattleEvent
import h3.sim.BattleState
import h3.sim.HexCell

/** Animation speed setting: frame time in ms (android-app.md 4.4); SKIP shows the final state. */
enum class AnimSpeed(val frameMs: Int) { SLOW(100), NORMAL(67), FAST(33), SKIP(0) }

/** Player animation preferences. UI only; never part of a state, command or hash. */
data class AnimationPrefs(val speed: AnimSpeed = AnimSpeed.NORMAL)

enum class SegKind { MOVE_STEP, ATTACK, SHOOT, PROJECTILE, HIT, DAMAGE_NUMBER, DEATH, ROUND_BANNER, TURN_PULSE, LUCK, MORALE_BOOST, MORALE_FROZEN, BATTLE_END }

/**
 * One UI clip, integer milliseconds. [value] carries a number to show (damage, kills, round,
 * winner, 1/0 for good luck); [from]/[to] are board cells for movement and lunges.
 */
data class Segment(
    val startMs: Int, val durationMs: Int, val kind: SegKind, val stack: Int,
    val from: HexCell? = null, val to: HexCell? = null, val value: Long = 0,
) {
    val endMs: Int get() = startMs + durationMs
}

/**
 * Pure builder of the animation timeline (android-app.md 4.4). It reads immutable inputs and
 * returns plain data: it has no clock, takes and returns no BattleCommand, and cannot touch
 * the simulation. Segments are strictly sequential: the first starts at 0, each starts where
 * the previous ended, so the list is sorted and never overlaps.
 *
 * The spec's input is the previous view plus the events of one `apply`; [before] supplies the
 * positions (the final state adds nothing the events do not already say).
 */
object Timeline {
    /** Durations in frames (UI tuning, not balance); times frame ms of the speed setting. */
    object Frames {
        const val MOVE_STEP = 3
        const val ATTACK = 4
        const val SHOOT = 4
        const val PROJECTILE = 4
        const val HIT = 3
        const val DAMAGE_NUMBER = 6
        const val DEATH = 6
        const val ROUND_BANNER = 12
        const val TURN_PULSE = 4
        const val OVERLAY = 6
    }

    /** Longest single event, in frames, for the upper bound of [maxDurationMs]. */
    private const val MAX_EVENT_FRAMES_BASE = Frames.ATTACK + Frames.HIT + Frames.DAMAGE_NUMBER + Frames.PROJECTILE + Frames.SHOOT

    /** A safe bound on the total duration of [events] at [prefs] (Moved paths scale with length). */
    fun maxDurationMs(events: List<BattleEvent>, prefs: AnimationPrefs): Int {
        var frames = 0
        for (e in events) frames += if (e is BattleEvent.Moved) Frames.MOVE_STEP * e.path.size else MAX_EVENT_FRAMES_BASE + Frames.ROUND_BANNER
        return frames * prefs.speed.frameMs
    }

    fun build(before: BattleState, events: List<BattleEvent>, prefs: AnimationPrefs): List<Segment> {
        if (prefs.speed == AnimSpeed.SKIP) return skip(events)
        val ms = prefs.speed.frameMs
        val out = ArrayList<Segment>()
        var t = 0
        fun add(frames: Int, kind: SegKind, stack: Int, from: HexCell? = null, to: HexCell? = null, value: Long = 0) {
            val d = frames * ms
            out.add(Segment(t, d, kind, stack, from, to, value))
            t += d
        }
        val pos = HashMap<Int, HexCell>() // only looked up by key, never iterated
        for (s in before.stacks) pos[s.id] = HexCell(s.pos.first, s.pos.second)

        for (e in events) when (e) {
            is BattleEvent.Moved -> {
                var cur = pos[e.stack]
                for (p in e.path) {
                    val next = HexCell(p.first, p.second)
                    add(Frames.MOVE_STEP, SegKind.MOVE_STEP, e.stack, cur, next)
                    cur = next
                }
                if (cur != null) pos[e.stack] = cur
            }
            is BattleEvent.DamageDealt -> {
                val a = pos[e.attacker]
                val tg = pos[e.target]
                if (e.ranged) {
                    add(Frames.SHOOT, SegKind.SHOOT, e.attacker, a, tg)
                    add(Frames.PROJECTILE, SegKind.PROJECTILE, e.attacker, a, tg)
                } else {
                    add(Frames.ATTACK, SegKind.ATTACK, e.attacker, a, tg)
                }
                add(Frames.HIT, SegKind.HIT, e.target, tg, null, e.killed.toLong())
                add(Frames.DAMAGE_NUMBER, SegKind.DAMAGE_NUMBER, e.target, tg, null, e.damage)
            }
            is BattleEvent.UnitDied -> add(Frames.DEATH, SegKind.DEATH, e.stack, pos[e.stack])
            is BattleEvent.RoundStarted -> add(Frames.ROUND_BANNER, SegKind.ROUND_BANNER, -1, value = e.round.toLong())
            is BattleEvent.TurnStarted -> add(Frames.TURN_PULSE, SegKind.TURN_PULSE, e.stack, pos[e.stack])
            is BattleEvent.LuckRolled -> add(Frames.OVERLAY, SegKind.LUCK, e.stack, pos[e.stack], value = if (e.good) 1 else 0)
            is BattleEvent.MoraleBoost -> add(Frames.OVERLAY, SegKind.MORALE_BOOST, e.stack, pos[e.stack])
            is BattleEvent.MoraleFrozen -> add(Frames.OVERLAY, SegKind.MORALE_FROZEN, e.stack, pos[e.stack])
            is BattleEvent.BattleEnded -> add(0, SegKind.BATTLE_END, -1, value = e.winner.toLong())
            is BattleEvent.BattleStarted, is BattleEvent.Waited, is BattleEvent.Defended -> Unit
        }
        return out
    }

    /**
     * The final-state-only form: no animation, only the hand-off that must not be lost
     * (BattleEnded), as a zero-duration segment at 0.
     */
    fun skip(events: List<BattleEvent>): List<Segment> =
        events.filterIsInstance<BattleEvent.BattleEnded>().map { Segment(0, 0, SegKind.BATTLE_END, -1, value = it.winner.toLong()) }
}
