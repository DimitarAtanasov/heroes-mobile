package h3.presenter

import h3.sim.BattleCommand
import h3.sim.BattleState
import h3.sim.HexCell
import h3.sim.legalCommands

/** Finds a no-move attack preview at hex h in s, and a copy st where the target moved to another adjacent hex. */
object AttackMovedScenario {
    fun find(battle: h3.sim.Battle): Triple<BattleState, BattleState, HexCell> {
        val present = h3.sim.Present(battle)
        for (s in Fixture.states) {
            if (!s.started || s.winner != null || s.active == null) continue
            val legal = battle.legalCommands(s)
            for (a in legal.filterIsInstance<BattleCommand.Attack>().filter { it.fromHex == null }) {
                val t = s.stacks[a.target]
                if (t.creature.doubleWide) continue
                val h = HexCell(t.pos.first, t.pos.second)
                val p = present.candidateCommands(s, t.pos)
                if (p.firstOrNull { it == a } == null) continue
                for (r in 0 until 11) for (c in 0 until 17) {
                    val n = Pair(c, r)
                    if (n == t.pos) continue
                    val st = s.copy(stacks = s.stacks.map { if (it.id == t.id) it.copy(pos = n) else it })
                    val occ = st.stacks.filter { it.alive && it.id != t.id }.flatMap { battle.cells(it) }
                    if (HexCell(c, r) in occ || n in st.obstacles) continue
                    val l2 = try { battle.legalCommands(st) } catch (_: Exception) { continue }
                    if (a !in l2) continue
                    if (present.candidateCommands(st, t.pos).isEmpty()) continue
                    return Triple(s, st, h)
                }
            }
        }
        error("no attack-target-moved scenario in the recorded states")
    }
}
