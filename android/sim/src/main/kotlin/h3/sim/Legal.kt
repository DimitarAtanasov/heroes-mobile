package h3.sim

/**
 * Legal-command enumeration (battle-port slice 4): a port of `legal_commands` in
 * `tools/h3re/h3re/battle.py`. Python is the oracle (ADR-0004); `battle_states.json` records the
 * full ordered list for every state of every playout (ADR-0007).
 *
 * `strikeContext` and `strikePreview` were ported with `apply` (Battle.kt, slice 3, because the
 * strike pipeline needs them); this slice pins them with recorded previews and DamageCtx fields.
 *
 * Pure and RNG-free: the function takes no stream and never changes the state. The order is part
 * of the contract: Wait (if allowed), Defend, Moves in sorted head order, then for each living
 * enemy in stack-id order the Shoot (if allowed) followed by one Attack per adjacent head, the
 * stack's own position first (`fromHex = null`) and then the reachable heads in sorted order.
 * Integers only; no balance numbers.
 */
fun Battle.legalCommands(state: BattleState): List<BattleCommand> {
    if (!state.started) return listOf(BattleCommand.Begin)
    val active = state.active
    if (state.winner != null || active == null) return emptyList()
    val st = state.stacks[active]
    val out = ArrayList<BattleCommand>()
    if (st.id !in state.waited && !state.bonusTurn) out.add(BattleCommand.Wait(st.id))
    out.add(BattleCommand.Defend(st.id))
    val reach = reachable(state, st.id) // sorted heads, Python `sorted(reach)`
    for (h in reach) out.add(BattleCommand.Move(st.id, Pair(h.col, h.row)))
    val off = state.policy.rowOffset
    val own = HexCell(st.pos.first, st.pos.second)
    val heads = listOf(own) + reach
    val mineNow = cells(st)
    val enemyAdjacent = state.stacks.any { s ->
        s.alive && s.side != st.side && Hex.adjacentCells(mineNow, cells(s), off)
    }
    val canShoot = st.creature.shooter && st.shots > 0 && !enemyAdjacent
    for (tgt in state.stacks) {
        if (!tgt.alive || tgt.side == st.side) continue
        if (canShoot) out.add(BattleCommand.Shoot(st.id, tgt.id))
        val theirs = cells(tgt)
        for (h in heads) {
            val mine = Hex.cellsAt(h, st.side, st.creature.doubleWide)
            if (Hex.adjacentCells(mine, theirs, off)) {
                out.add(BattleCommand.Attack(st.id, tgt.id, if (h == own) null else Pair(h.col, h.row)))
            }
        }
    }
    return out
}
