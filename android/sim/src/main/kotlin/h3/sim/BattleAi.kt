package h3.sim

import java.math.BigInteger

/**
 * Greedy battle AI: a port of `tools/h3re/h3re/battle_ai.py` (Python is the oracle, ADR-0004;
 * `battle_ai.json` records decisions, ADR-0007, docs/specs/conformance-ai.md).
 *
 * Policy: attack or shoot with the best expected net damage (damage dealt, capped by what the
 * target has left, minus expected retaliation, +1 for a kill); otherwise move toward the nearest
 * enemy; otherwise Defend, but never more than [MAX_DEFENDS] times in a row (then Wait, or the
 * closest Move). Ties are broken with the stream `ai:<side>`, never the battle stream.
 *
 * Damage is previewed with `Rules.resolveDamage(ctx, RollPolicy.EXPECTED)` (an integer, no draw).
 * Integers only.
 */
class BattleAi(private val battle: Battle, private val codec: BattleCodec) {

    private fun stackHp(s: BattleStack): Long =
        if (s.count > 0) (s.count - 1).toLong() * s.creature.hp + s.topHp else 0L

    private fun preview(state: BattleState, att: BattleStack, dfn: BattleStack, ranged: Boolean): Long =
        battle.rules.resolveDamage(battle.strikeContext(state, att, dfn, ranged), RollPolicy.EXPECTED).damage

    private fun scoreAttack(state: BattleState, att: BattleStack, cmd: BattleCommand): Long {
        val target = if (cmd is BattleCommand.Attack) cmd.target else (cmd as BattleCommand.Shoot).target
        val tgt = state.stacks[target]
        val ranged = cmd is BattleCommand.Shoot
        var shots = 1L
        if (ranged && att.creature.shootsTwice) shots = 2
        if (!ranged && att.creature.strikesTwice) shots = 2
        val tgtHp = stackHp(tgt)
        val dealt = minOf(preview(state, att, tgt, ranged) * shots, tgtHp)
        var value = dealt
        if (!ranged && dealt < tgtHp && !att.creature.noEnemyRetaliation &&
            (tgt.creature.unlimitedRetaliation || tgt.retaliations > 0)
        ) {
            val r = Battle.applyDamage(tgt.count.toLong(), tgt.topHp.toLong(), tgt.creature.hp.toLong(), dealt)
            if (r.count > 0) {
                val shrunk = tgt.copy(count = r.count.toInt(), topHp = r.topHp.toInt())
                value -= minOf(preview(state, shrunk, att, false), stackHp(att))
            }
        } else if (dealt >= tgtHp) {
            value += 1 // a kill removes the target's future damage
        }
        return value
    }

    private fun enemyDist(state: BattleState, st: BattleStack, head: Pair<Int, Int>): Int {
        val off = state.policy.rowOffset
        val mine = Hex.cellsAt(HexCell(head.first, head.second), st.side, st.creature.doubleWide)
        var best = Int.MAX_VALUE
        for (e in state.stacks) {
            if (!e.alive || e.side == st.side) continue
            for (a in mine) for (b in battle.cells(e)) best = minOf(best, Hex.distance(a, b, off))
        }
        check(best != Int.MAX_VALUE) { "no enemy" }
        return best
    }

    private fun decide(
        state: BattleState, side: Int?, defends: Int, rngFactory: (Int) -> Pcg32, stateless: Boolean,
    ): BattleCommand {
        val legal = battle.legalCommands(state)
        require(legal.isNotEmpty()) { "no legal commands (battle over)" }
        if (!state.started) return legal[0]
        val st = state.stacks[state.active!!]
        require(side == null || st.side == side) { "active stack belongs to side ${st.side}, not $side" }
        var rng: Pcg32? = null
        fun pick(c: List<BattleCommand>): BattleCommand {
            if (c.size == 1) return c[0]
            val r = rng ?: rngFactory(st.side).also { rng = it }
            return c[r.range(0, c.size.toLong()).toInt()]
        }

        val attacks = legal.filter { it is BattleCommand.Attack || it is BattleCommand.Shoot }
            .map { it to scoreAttack(state, st, it) }
        if (attacks.isNotEmpty()) {
            val best = attacks.maxOf { it.second }
            return pick(attacks.filter { it.second == best }.map { it.first })
        }
        val cur = enemyDist(state, st, st.pos)
        val moves = legal.filterIsInstance<BattleCommand.Move>().map { it to enemyDist(state, st, it.dest) }
        if (moves.isNotEmpty()) {
            val d = moves.minOf { it.second }
            if (d < cur) return pick(moves.filter { it.second == d }.map { it.first })
        }
        val stalled = if (stateless) state.round > STATELESS_DEFEND_ROUND else defends >= MAX_DEFENDS
        if (!stalled) return BattleCommand.Defend(st.id)
        val waits = legal.filterIsInstance<BattleCommand.Wait>()
        if (waits.isNotEmpty()) return waits[0]
        if (moves.isNotEmpty()) {
            val d = moves.minOf { it.second }
            return pick(moves.filter { it.second == d }.map { it.first })
        }
        return BattleCommand.Defend(st.id)
    }

    /** Stateless greedy choice (tie-break stream seeded from the state hash). */
    fun choose(state: BattleState, side: Int? = null): BattleCommand {
        val seed = BigInteger(codec.stateHash(state).substring(0, 16), 16)
        return decide(state, side, 0, { s -> RngStreams.derive(seed, "ai:$s") }, true)
    }

    /** Stateful greedy chooser: tracks consecutive Defends per side. */
    inner class GreedyAi(private val sideSeed: Long) {
        private val streams = LinkedHashMap<Int, Pcg32>()
        private val defends = intArrayOf(0, 0)

        /** Consecutive Defends so far by [side] (0 or 1). */
        fun defends(side: Int): Int = defends[side]

        private fun stream(side: Int): Pcg32 = streams.getOrPut(side) { RngStreams.derive(sideSeed, "ai:$side") }

        fun choose(state: BattleState, side: Int? = null): BattleCommand {
            val active = state.active
            val cmd = decide(state, side, defends[if (active != null) state.stacks[active].side else 0], ::stream, false)
            if (state.started && active != null) {
                val s = state.stacks[active].side
                defends[s] = if (cmd is BattleCommand.Defend) defends[s] + 1 else 0
            }
            return cmd
        }
    }

    companion object {
        const val MAX_DEFENDS = 2
        const val STATELESS_DEFEND_ROUND = 8
    }
}
