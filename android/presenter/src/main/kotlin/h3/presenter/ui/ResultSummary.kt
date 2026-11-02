package h3.presenter.ui

import h3.presenter.Snapshot
import h3.sim.BattleState
import h3.sim.Hex

/** How the battle ended for the person holding the device. */
enum class ResultOutcome { Victory, Defeat, Unfinished }

/**
 * One side's numbers for the result screen. All counts are creatures except the two stack counts.
 * Invariant: [survivors] + [casualties] == [startCreatures].
 */
data class SideTally(
    val side: Int,
    val startStacks: Int,
    val startCreatures: Long,
    /** Stacks of this side that still have at least one creature at the end. */
    val survivingStacks: Int,
    val survivors: Long,
    val casualties: Long,
)

/**
 * Everything the Result screen shows (docs/specs/app-shell.md), computed from the initial and the
 * final [BattleState]. Pure and integer-only; it reads no clock and does no I/O.
 *
 * [sides] is in ascending side order. [shortHash] is the first [SHORT_HASH_LENGTH] characters of
 * [fullHash] (the whole text when it is shorter).
 */
data class ResultSummary(
    val winner: Int?,
    val outcome: ResultOutcome,
    val sides: List<SideTally>,
    val rounds: Int,
    val commands: Int,
    val shortHash: String,
    val fullHash: String,
) {
    /** The tally of [side], or null when that side had no stacks at the start. */
    fun tally(side: Int): SideTally? = sides.firstOrNull { it.side == side }

    companion object {
        const val SHORT_HASH_LENGTH = 8

        /**
         * Summary of a battle that went from [initial] to [last]. [commands] is the number of commands
         * applied (the snapshot `seq`), [hash] the final state hash. [humanSide] decides Victory or
         * Defeat; the winner itself is [BattleState.winner] of [last], null while the battle is open.
         *
         * Stacks are matched by id. A stack missing from [last] lost everyone; a count above the
         * start (not reachable in the engine) is treated as no loss; stacks that [initial] did not
         * have are ignored. So survivors plus casualties always equal the start.
         *
         * @throws IllegalArgumentException when [commands] is negative or the states are of different battles.
         */
        fun of(initial: BattleState, last: BattleState, commands: Int, hash: String, humanSide: Int = Hex.ATTACKER): ResultSummary {
            require(commands >= 0) { "commands must be >= 0, got $commands" }
            require(initial.battleId == last.battleId) { "states belong to different battles: ${initial.battleId} / ${last.battleId}" }
            val winner = last.winner
            val outcome = when {
                winner == null -> ResultOutcome.Unfinished
                winner == humanSide -> ResultOutcome.Victory
                else -> ResultOutcome.Defeat
            }
            val tallies = initial.stacks.map { it.side }.distinct().sorted().map { side -> tallyOf(initial, last, side) }
            return ResultSummary(winner, outcome, tallies, last.round, commands, hash.take(SHORT_HASH_LENGTH), hash)
        }

        /** Summary for a session's newest [Snapshot]; the command count is its `seq`. */
        fun of(initial: BattleState, last: Snapshot, humanSide: Int = Hex.ATTACKER): ResultSummary =
            of(initial, last.state, last.seq, last.stateHash, humanSide)

        private fun tallyOf(initial: BattleState, last: BattleState, side: Int): SideTally {
            val mine = initial.stacks.filter { it.side == side }
            var creatures = 0L
            var survivors = 0L
            var standing = 0
            for (s in mine) {
                val now = last.stacks.firstOrNull { it.id == s.id }?.count ?: 0
                val kept = now.coerceIn(0, maxOf(s.count, 0))
                creatures += maxOf(s.count, 0)
                survivors += kept
                if (kept > 0) standing++
            }
            return SideTally(side, mine.size, creatures, standing, survivors, creatures - survivors)
        }
    }
}
