package h3.sim

/**
 * Battle presenter, view v2: a port of `tools/h3re/h3re/present.py` (docs/specs/presenter.md).
 * Python is the oracle (ADR-0004); `present.json` pins [viewJson] byte for byte, plus the tap
 * candidate lists (ADR-0007, docs/specs/conformance-present.md).
 *
 * Read-only and RNG-free: it takes no stream, never changes a state and never changes its hash.
 * Integers, booleans, strings, lists and maps only (no floats). Output order of lists is part of
 * the contract; map key order is not (the canonical text sorts keys).
 */
class Present(private val battle: Battle) {

    private fun hx(h: HexCell): List<Int> = listOf(h.col, h.row)
    private fun hx(p: Pair<Int, Int>): List<Int> = listOf(p.first, p.second)
    private fun hc(p: Pair<Int, Int>) = HexCell(p.first, p.second)

    fun commandToDict(cmd: BattleCommand): Map<String, Any?> = when (cmd) {
        is BattleCommand.Begin -> linkedMapOf("type" to "begin")
        is BattleCommand.Wait -> linkedMapOf("type" to "wait", "stack" to cmd.stack)
        is BattleCommand.Defend -> linkedMapOf("type" to "defend", "stack" to cmd.stack)
        is BattleCommand.Move -> linkedMapOf("type" to "move", "stack" to cmd.stack, "dest" to hx(cmd.dest))
        is BattleCommand.Shoot -> linkedMapOf("type" to "shoot", "stack" to cmd.stack, "target" to cmd.target)
        is BattleCommand.Attack -> linkedMapOf(
            "type" to "attack", "stack" to cmd.stack, "target" to cmd.target,
            "from_hex" to cmd.fromHex?.let { hx(it) },
        )
    }

    private fun totalHp(s: BattleStack): Long =
        if (s.count > 0) (s.count - 1).toLong() * s.creature.hp + s.topHp else 0L

    private fun stackView(state: BattleState, s: BattleStack): Map<String, Any?> {
        val c = s.creature
        val hero = state.heroes[s.side]
        return linkedMapOf(
            "id" to s.id, "side" to s.side, "slot" to s.slot,
            "creature" to c.name, "count" to s.count, "alive" to s.alive,
            "top_hp" to s.topHp, "unit_hp" to c.hp, "hp" to totalHp(s),
            "attack" to c.attack + (hero?.attack ?: 0),
            "defense" to c.defense + (hero?.defense ?: 0),
            "defend_bonus" to (if (s.defending) battle.defendBonus(state, s) else 0),
            "dmg_min" to c.dmgMin, "dmg_max" to c.dmgMax,
            "retaliations" to s.retaliations,
            "strikes_twice" to c.strikesTwice, "shoots_twice" to c.shootsTwice,
            "no_enemy_retaliation" to c.noEnemyRetaliation,
            "unlimited_retaliation" to c.unlimitedRetaliation,
            "speed" to c.speed, "shots" to s.shots, "shooter" to c.shooter,
            "double_wide" to c.doubleWide, "flyer" to c.flyer,
            "defending" to s.defending, "morale" to s.morale, "luck" to s.luck,
            "active" to (s.id == state.active),
            "pos" to hx(s.pos),
            "cells" to battle.cells(s).map { hx(it) },
        )
    }

    private fun grid(state: BattleState): List<List<Map<String, Any?>>> {
        val occ = LinkedHashMap<HexCell, Pair<Int, String>>()
        for (s in state.stacks) {
            if (!s.alive) continue
            battle.cells(s).forEachIndexed { i, cell -> occ[cell] = Pair(s.id, if (i == 0) "head" else "tail") }
        }
        val obstacles = state.obstacles.map(::hc).toSet()
        val walkEdges = state.policy.edgeColumnsWalkable
        return (0 until Hex.HEIGHT).map { r ->
            (0 until Hex.WIDTH).map { c ->
                val o = occ[HexCell(c, r)]
                linkedMapOf<String, Any?>(
                    "c" to c, "r" to r,
                    "playable" to (walkEdges || c in 1..(Hex.WIDTH - 2)),
                    "obstacle" to (HexCell(c, r) in obstacles),
                    "stack" to o?.first, "part" to o?.second,
                )
            }
        }
    }

    private fun queue(state: BattleState): List<Map<String, Any?>> {
        val done = state.done.toSet()
        val waited = state.waited.toSet()
        return battle.roundOrder(state).map { i ->
            val status = when {
                i == state.active -> "active"
                i in done -> "done"
                i in waited -> "waited"
                else -> "pending"
            }
            linkedMapOf("stack" to i, "status" to status)
        }
    }

    private fun preview(state: BattleState, att: Int, tgt: Int, ranged: Boolean): Map<String, Any?> {
        val p = battle.strikePreview(state, att, tgt, ranged)
        val t = state.stacks[tgt]
        fun kills(d: Long): Long =
            if (t.count > 0) Battle.applyDamage(t.count.toLong(), t.topHp.toLong(), t.creature.hp.toLong(), d).killed else 0L
        return linkedMapOf(
            "floor" to p.floor, "expected" to p.expected, "ceiling" to p.ceiling,
            "kills" to linkedMapOf("floor" to kills(p.floor), "expected" to kills(p.expected), "ceiling" to kills(p.ceiling)),
        )
    }

    /** Paths of the active stack's reachable heads (Python `B._reach`), empty when nobody acts. */
    private fun paths(state: BattleState): Map<HexCell, List<List<Int>>> {
        val active = state.active
        if (!state.started || state.winner != null || active == null) return emptyMap()
        val st = state.stacks[active]
        val occ = LinkedHashSet<HexCell>()
        for (s in state.stacks) if (s.alive && s.id != st.id) occ.addAll(battle.cells(s))
        val p = state.policy
        val reach = Hex.reach(
            hc(st.pos), st.side, st.creature.doubleWide, st.creature.flyer, st.creature.speed,
            p.rowOffset, p.edgeColumnsWalkable, state.obstacles.map(::hc).toSet(), occ,
        )
        return reach.mapValues { (_, path) -> path.map { hx(it) } }
    }

    private class HexEntry(val hex: HexCell) {
        var move: Map<String, Any?>? = null
        var target: MutableMap<String, Any?>? = null
    }

    private fun actions(state: BattleState): Map<String, Any?> {
        val cmds = battle.legalCommands(state)
        val paths = paths(state)
        val globalCmds = ArrayList<Map<String, Any?>>()
        val byHex = java.util.TreeMap<HexCell, HexEntry>()
        fun slot(h: HexCell) = byHex.getOrPut(h) { HexEntry(h) }
        fun targetSlot(tid: Int): MutableMap<String, Any?> {
            val e = slot(hc(state.stacks[tid].pos))
            return e.target ?: linkedMapOf<String, Any?>(
                "stack" to tid, "shoot" to null, "attacks" to ArrayList<Map<String, Any?>>(),
            ).also { e.target = it }
        }
        for (cmd in cmds) {
            val d = commandToDict(cmd)
            when (cmd) {
                is BattleCommand.Begin, is BattleCommand.Wait, is BattleCommand.Defend ->
                    globalCmds.add(linkedMapOf("command" to d))
                is BattleCommand.Move ->
                    slot(hc(cmd.dest)).move = linkedMapOf("command" to d, "path" to paths.getValue(hc(cmd.dest)))
                is BattleCommand.Shoot ->
                    targetSlot(cmd.target)["shoot"] = linkedMapOf(
                        "command" to d, "preview" to preview(state, cmd.stack, cmd.target, true),
                    )
                is BattleCommand.Attack -> {
                    val st = state.stacks[cmd.stack]
                    val frm = cmd.fromHex ?: st.pos
                    @Suppress("UNCHECKED_CAST")
                    (targetSlot(cmd.target)["attacks"] as MutableList<Map<String, Any?>>).add(
                        linkedMapOf(
                            "from_hex" to hx(frm), "command" to d,
                            "path" to (if (cmd.fromHex == null) emptyList() else paths.getValue(hc(frm))),
                            "preview" to preview(state, cmd.stack, cmd.target, false),
                        ),
                    )
                }
            }
        }
        return linkedMapOf(
            "global" to globalCmds,
            "by_hex" to byHex.values.map { e ->
                linkedMapOf("hex" to hx(e.hex), "move" to e.move, "target" to e.target)
            },
        )
    }

    /** Versioned, read-only view-model of [state] (presenter.md). */
    fun view(state: BattleState): Map<String, Any?> {
        val phase = when {
            state.winner != null -> "over"
            !state.started -> "not_started"
            else -> "active"
        }
        return linkedMapOf(
            "view_version" to VIEW_VERSION,
            "battle_id" to state.battleId,
            "phase" to phase,
            "round" to state.round,
            "winner" to state.winner,
            "active" to (if (phase == "active") state.active else null),
            "bonus_turn" to state.bonusTurn,
            "morale_pending" to state.moralePending,
            "grid" to linkedMapOf(
                "width" to Hex.WIDTH, "height" to Hex.HEIGHT, "rows" to grid(state),
                "row_offset" to state.policy.rowOffset,
                "edge_columns_walkable" to state.policy.edgeColumnsWalkable,
            ),
            "stacks" to state.stacks.map { stackView(state, it) },
            "queue" to queue(state),
            "actions" to actions(state),
        )
    }

    /** Canonical JSON text of [view]: sorted keys, no spaces. */
    fun viewJson(state: BattleState): String = Canonical.encode(view(state)).toString(Charsets.US_ASCII)

    private fun enemyAt(state: BattleState, h: HexCell): Int? {
        val active = state.active ?: return null
        val me = state.stacks[active].side
        for (s in state.stacks) if (s.alive && s.side != me && h in battle.cells(s)) return s.id
        return null
    }

    /** Commands a tap on [hex] can mean, in `legalCommands` order. */
    fun candidateCommands(state: BattleState, hex: Pair<Int, Int>): List<BattleCommand> {
        val h = hc(hex)
        val tgt = enemyAt(state, h)
        val out = ArrayList<BattleCommand>()
        for (cmd in battle.legalCommands(state)) {
            when (cmd) {
                is BattleCommand.Move -> if (hc(cmd.dest) == h) out.add(cmd)
                is BattleCommand.Attack -> if (tgt != null && cmd.target == tgt) out.add(cmd)
                is BattleCommand.Shoot -> if (tgt != null && cmd.target == tgt) out.add(cmd)
                else -> {}
            }
        }
        return out
    }

    /** The `actions.by_hex` entry for a tapped hex (any cell of a stack), or null. */
    fun candidateActions(state: BattleState, hex: Pair<Int, Int>): Map<String, Any?>? {
        val h = hc(hex)
        val tgt = enemyAt(state, h)
        val key = if (tgt == null) hx(h) else hx(state.stacks[tgt].pos)
        @Suppress("UNCHECKED_CAST")
        return (actions(state)["by_hex"] as List<Map<String, Any?>>).firstOrNull { it["hex"] == key }
    }

    companion object {
        const val VIEW_VERSION = 2
    }
}
