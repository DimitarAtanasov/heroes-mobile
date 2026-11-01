package h3.sim

/**
 * Battle apply logic (battle-port slice 3): a port of `apply` and its helpers in
 * `tools/h3re/h3re/battle.py` (docs/specs/battle.md sections 1-7). Python is the oracle
 * (ADR-0004); `battle_states.json` pins every step (ADR-0007).
 *
 * Every function keeps the Python function's name (camelCase) and its operation order, in
 * particular the order of RNG calls: morale at activation, then per strike luck before damage
 * (inside [Rules.resolveDamage]), attacker strike, retaliation, second strike. A command is
 * validated completely before the first state change or draw, so a rejected command touches
 * neither the state nor the stream.
 *
 * Integers only (ADR-0002, ADR-0008): state values are `Int`, damage inputs widen to `Long`,
 * fractions are [Rational]; sums and products that could overflow use `Math.*Exact`.
 * No balance numbers here: damage constants come from the [RulesPack] in [rules], rule choices
 * from the [BattlePolicy] stored in the state.
 */

/** Python `IllegalCommand` (a `ValueError`): the command is rejected; state and RNG are untouched. */
open class IllegalCommand(message: String) : IllegalArgumentException(message)

/** Python `PackMismatch`: the state was built under a different rules pack than [Battle.rulesHash]. */
class PackMismatch(message: String) : IllegalCommand(message)

/** Result of [Battle.apply]: the new state and the events, in emission order. */
data class ApplyResult(val state: BattleState, val events: List<BattleEvent>)

/**
 * The battle engine for one rules pack. [rulesHash] is the content hash of the pack behind
 * [rules] (Python `rules.RULES_HASH`); `apply` refuses a state carrying any other hash.
 */
class Battle(val rules: Rules, val rulesHash: String) {

    // ----------------------------------------------------------------------
    // Geometry over the state
    // ----------------------------------------------------------------------

    private fun hc(p: Pair<Int, Int>) = HexCell(p.first, p.second)

    private fun pair(h: HexCell) = Pair(h.col, h.row)

    private fun cellsAt(head: HexCell, side: Int, doubleWide: Boolean) = Hex.cellsAt(head, side, doubleWide)

    fun cells(s: BattleStack): List<HexCell> = cellsAt(hc(s.pos), s.side, s.creature.doubleWide)

    private fun occupancy(state: BattleState, exclude: Int?): Set<HexCell> {
        val occ = HashSet<HexCell>()
        for (s in state.stacks) if (s.alive && s.id != exclude) occ.addAll(cells(s))
        return occ
    }

    /** Python `_reach`: head -> path (start excluded), in Python dict order. */
    private fun reach(state: BattleState, st: BattleStack): Map<HexCell, List<HexCell>> {
        val p = state.policy
        return Hex.reach(
            hc(st.pos), st.side, st.creature.doubleWide, st.creature.flyer, st.creature.speed,
            p.rowOffset, p.edgeColumnsWalkable, state.obstacles.map(::hc).toSet(),
            occupancy(state, st.id),
        )
    }

    /** Python `reachable`: sorted heads the stack can move to. */
    fun reachable(state: BattleState, stackId: Int): List<HexCell> =
        reach(state, state.stacks[stackId]).keys.sorted()

    private fun enemyAdjacent(state: BattleState, st: BattleStack): Boolean {
        val off = state.policy.rowOffset
        val mine = cells(st)
        return state.stacks.any { s -> s.alive && s.side != st.side && Hex.adjacentCells(mine, cells(s), off) }
    }

    // ----------------------------------------------------------------------
    // Turn queue
    // ----------------------------------------------------------------------

    /** Python `_speed_sorted`. Any `speed_tie` other than "attacker_first" uses the alternate ranking. */
    private fun speedSorted(state: BattleState, stacks: List<BattleStack>): List<BattleStack> {
        if (state.policy.speedTie == "attacker_first") {
            // compareByDescending: negating the speed would wrap for Int.MIN_VALUE.
            return stacks.sortedWith(
                compareByDescending<BattleStack> { it.creature.speed }.thenBy { it.side }.thenBy { it.slot },
            )
        }
        // alternate: within a speed, interleave sides starting with the attacker.
        val rank = HashMap<Int, Int>()
        for (spd in stacks.map { it.creature.speed }.toSet()) {
            for (side in intArrayOf(Hex.ATTACKER, Hex.DEFENDER)) {
                val group = stacks.filter { it.creature.speed == spd && it.side == side }.sortedBy { it.slot }
                for ((i, s) in group.withIndex()) rank[s.id] = i
            }
        }
        return stacks.sortedWith(
            compareByDescending<BattleStack> { it.creature.speed }.thenBy { rank.getValue(it.id) }.thenBy { it.side },
        )
    }

    /** Python `_last_mover_sorted`: (order, last side). */
    private fun lastMoverSorted(
        stacks: List<BattleStack>, lastSide0: Int?, descending: Boolean,
    ): Pair<List<BattleStack>, Int?> {
        var lastSide = lastSide0
        val out = ArrayList<BattleStack>()
        val distinct = stacks.map { it.creature.speed }.toSet().sorted()
        val speeds = if (descending) distinct.reversed() else distinct
        for (spd in speeds) {
            val queues = mapOf(
                Hex.ATTACKER to ArrayDeque(stacks.filter { it.creature.speed == spd && it.side == Hex.ATTACKER }
                    .sortedBy { it.slot }),
                Hex.DEFENDER to ArrayDeque(stacks.filter { it.creature.speed == spd && it.side == Hex.DEFENDER }
                    .sortedBy { it.slot }),
            )
            while (queues.getValue(Hex.ATTACKER).isNotEmpty() || queues.getValue(Hex.DEFENDER).isNotEmpty()) {
                var side = if (lastSide == null) Hex.ATTACKER else 1 - lastSide
                if (queues.getValue(side).isEmpty()) side = 1 - side
                out.add(queues.getValue(side).removeFirst())
                lastSide = side
            }
        }
        return Pair(out, lastSide)
    }

    /** Python `turn_order`: ids still to act this round, the active stack first. */
    fun turnOrder(state: BattleState): List<Int> {
        val living = state.stacks.filter { it.alive }
        val done = state.done.toSet()
        val waited = state.waited.toSet()
        var act = state.active
        if (act != null && !state.stacks[act].alive) act = null
        val main = living.filter { it.id !in done && it.id !in waited }
        val wait = living.filter { it.id in waited && it.id !in done }
        val pol = state.policy
        var last = state.lastSide
        val mainSorted: List<BattleStack>
        if (pol.speedTie == "alternate_last_mover") {
            val r = lastMoverSorted(main.filter { it.id != act }, last, true)
            mainSorted = r.first
            last = r.second
        } else {
            mainSorted = speedSorted(state, main).filter { it.id != act }
            if (mainSorted.isNotEmpty()) last = mainSorted.last().side
        }
        val mainIds = mainSorted.map { it.id }
        val waitIds: List<Int> = when (pol.waitOrder) {
            "fifo" -> {
                val aliveWait = wait.map { it.id }.toSet()
                state.waited.filter { it in aliveWait }
            }
            "slow_first_alternate" -> lastMoverSorted(wait.filter { it.id != act }, last, false).first.map { it.id }
            else -> {
                val ids = speedSorted(state, wait).map { it.id }
                if (pol.waitOrder == "reverse_speed") ids.reversed() else ids
            }
        }
        val order = ArrayList((mainIds + waitIds).filter { it != act })
        if (act != null) order.add(0, act)
        return order
    }

    /** Python `round_order`: finished stacks (in finishing order), then the pending queue. */
    fun roundOrder(state: BattleState): List<Int> {
        val alive = state.stacks.filter { it.alive }.map { it.id }.toSet()
        val finished = state.done.filter { it in alive }
        val fin = finished.toSet()
        return finished + turnOrder(state).filter { it !in fin }
    }

    // ----------------------------------------------------------------------
    // Morale, defend bonus, strike inputs
    // ----------------------------------------------------------------------

    fun effectiveMorale(st: BattleStack): Int =
        if (st.creature.noMorale) 0 else maxOf(-3, minOf(3, st.morale))

    /** Python `defend_bonus`: max(min, round(Defense * num / den)), floor or ceil. Widened before adding. */
    fun defendBonus(state: BattleState, st: BattleStack): Long {
        val hero = state.heroes[st.side]
        val base = Math.addExact(st.creature.defense.toLong(), (hero?.defense ?: 0).toLong())
        return policyDefendBonus(state.policy, base)
    }

    /** Python `strike_context`: the one place battle state becomes damage inputs. */
    fun strikeContext(state: BattleState, att: BattleStack, dfn: BattleStack, ranged: Boolean): DamageCtx {
        val pol = state.policy
        val ha = state.heroes[att.side]
        val hd = state.heroes[dfn.side]
        val a = Math.addExact(att.creature.attack.toLong(), (ha?.attack ?: 0).toLong())
        var d = Math.addExact(dfn.creature.defense.toLong(), (hd?.defense ?: 0).toLong())
        if (dfn.defending) d = Math.addExact(d, defendBonus(state, dfn))
        var rangePen = false
        if (ranged && !att.creature.noRangePenalty) {
            val off = pol.rowOffset
            val origin = if (pol.rangeOrigin == "head") listOf(hc(att.pos)) else cells(att)
            val targets = cells(dfn)
            var dist = Int.MAX_VALUE
            for (x in origin) for (y in targets) dist = minOf(dist, Hex.distance(x, y, off))
            rangePen = dist > pol.rangePenaltyBeyond
        }
        val meleePen = !ranged && att.creature.shooter && !att.creature.noMeleePenalty
        return DamageCtx(
            count = att.count.toLong(),
            dmgMin = att.creature.dmgMin.toLong(),
            dmgMax = att.creature.dmgMax.toLong(),
            attack = a,
            defense = d,
            ranged = ranged,
            offense = ha?.offense ?: 0,
            archery = ha?.archery ?: 0,
            armorer = hd?.armorer ?: 0,
            hates = dfn.creature.name in att.creature.hates,
            rangePenalty = rangePen,
            meleePenalty = meleePen,
            luck = att.luck.toLong(),
            badLuck = pol.badLuck,
        )
    }

    /** Python `strike_preview`: (floor, expected, ceiling); consumes no RNG. */
    fun strikePreview(state: BattleState, attId: Int, defId: Int, ranged: Boolean): DamagePreview =
        rules.previewDamage(strikeContext(state, state.stacks[attId], state.stacks[defId], ranged))

    // ----------------------------------------------------------------------
    // apply helpers
    // ----------------------------------------------------------------------

    private fun set(state: BattleState, st: BattleStack): BattleState {
        val stacks = state.stacks.toMutableList()
        stacks[st.id] = st
        return state.copy(stacks = stacks)
    }

    private fun chance(rng: DrawSource, frac: Rational): Boolean = rng.chance(frac.numerator, frac.denominator)

    private fun strike(
        state0: BattleState, attId: Int, defId: Int, ranged: Boolean, retaliation: Boolean,
        rng: DrawSource, events: MutableList<BattleEvent>,
    ): BattleState {
        val a = state0.stacks[attId]
        val d = state0.stacks[defId]
        val res = rules.resolveDamage(strikeContext(state0, a, d, ranged), RollPolicy.ACTUAL_SEED, rng)
        if (res.lucky) events.add(BattleEvent.LuckRolled(a.id, true))
        if (res.unlucky) events.add(BattleEvent.LuckRolled(a.id, false))
        val dmg = res.damage
        val r = applyDamage(d.count.toLong(), d.topHp.toLong(), d.creature.hp.toLong(), dmg)
        val count = Math.toIntExact(r.count)
        val state = set(
            state0,
            d.copy(count = count, topHp = Math.toIntExact(r.topHp), defending = if (count != 0) d.defending else false),
        )
        events.add(
            BattleEvent.DamageDealt(a.id, d.id, dmg, Math.toIntExact(r.killed), ranged, retaliation),
        )
        if (count == 0) events.add(BattleEvent.UnitDied(d.id))
        return state
    }

    private fun melee(state0: BattleState, attId: Int, defId: Int, rng: DrawSource, events: MutableList<BattleEvent>): BattleState {
        var state = strike(state0, attId, defId, false, false, rng, events)
        var d = state.stacks[defId]
        var a = state.stacks[attId]
        if (d.alive && !a.creature.noEnemyRetaliation) {
            if (d.creature.unlimitedRetaliation || d.retaliations > 0) {
                if (!d.creature.unlimitedRetaliation) state = set(state, d.copy(retaliations = d.retaliations - 1))
                state = strike(state, defId, attId, false, true, rng, events)
            }
        }
        a = state.stacks[attId]
        d = state.stacks[defId]
        if (a.creature.strikesTwice && a.alive && d.alive) {
            state = strike(state, attId, defId, false, false, rng, events)
        }
        return state
    }

    /** Python `_check_end`: (state, over). */
    private fun checkEnd(state: BattleState, events: MutableList<BattleEvent>): Pair<BattleState, Boolean> {
        val sides = state.stacks.filter { it.alive }.map { it.side }.toSet()
        if (sides.size == 2) return Pair(state, false)
        // Both sides empty is unreachable; the DEFENDER fallback is defensive only (as in Python).
        val winner = if (sides.isNotEmpty()) sides.single() else Hex.DEFENDER
        events.add(BattleEvent.BattleEnded(winner))
        return Pair(state.copy(winner = winner, active = null, bonusTurn = false, moralePending = false), true)
    }

    /** Python `_activate_next`: pick the next stack, starting rounds and rolling morale. */
    private fun activateNext(state0: BattleState, rng: DrawSource, events: MutableList<BattleEvent>): BattleState {
        var state = state0
        while (true) {
            val order = turnOrder(state.copy(active = null))
            if (order.isEmpty()) {
                val stacks = state.stacks.map { s -> if (s.alive) s.copy(retaliations = 1) else s }
                state = state.copy(round = Math.addExact(state.round, 1), done = emptyList(), waited = emptyList(), stacks = stacks)
                events.add(BattleEvent.RoundStarted(state.round))
                continue
            }
            val sid = order[0]
            var st = state.stacks[sid]
            if (st.defending) {
                st = st.copy(defending = false)
                state = set(state, st)
            }
            val phase = if (sid in state.waited) "wait" else "main"
            state = state.copy(active = sid, bonusTurn = false, moralePending = false, lastSide = st.side)
            events.add(BattleEvent.TurnStarted(sid, phase, false))
            var m = effectiveMorale(st)
            val pol = state.policy
            if (phase == "wait") {
                if (m < 0 && !pol.badMoraleOnWaitActivation) m = 0
                if (m > 0 && !pol.goodMoraleOnWaitActivation) m = 0
            }
            if (m < 0 && chance(rng, rules.badMoraleChance(m.toLong(), pol.badMoraleTable.map { it.toLong() }))) {
                events.add(BattleEvent.MoraleFrozen(sid))
                state = state.copy(done = state.done + sid, active = null)
                continue
            }
            if (m > 0) state = state.copy(moralePending = chance(rng, rules.goodMoraleChance(m.toLong())))
            return state
        }
    }

    private enum class Kind { WAIT, DEFEND, MOVE, SHOOT, ATTACK }

    /** Python `_finish_turn`. */
    private fun finishTurn(state0: BattleState, kind: Kind, rng: DrawSource, events: MutableList<BattleEvent>): BattleState {
        val (s1, over) = checkEnd(state0, events)
        if (over) return s1
        var state = s1
        val sid = checkNotNull(state.active)
        val st = state.stacks[sid]
        val pol = state.policy
        val allowed = when (kind) {
            Kind.WAIT -> pol.goodMoraleAfterWait
            Kind.DEFEND -> pol.goodMoraleAfterDefend
            else -> true
        }
        if (kind == Kind.WAIT) {
            state = state.copy(waited = state.waited + sid)
        } else if (sid !in state.done) {
            state = state.copy(done = state.done + sid)
        }
        if (state.moralePending && allowed && st.alive) {
            // The wait is consumed by the bonus action: the stack is done after it.
            if (kind == Kind.WAIT) state = state.copy(done = state.done + sid)
            events.add(BattleEvent.MoraleBoost(sid))
            state = state.copy(bonusTurn = true, moralePending = false)
            val phase = if (sid in state.waited) "wait" else "main"
            events.add(BattleEvent.TurnStarted(sid, phase, true))
            val m = effectiveMorale(st)
            if (pol.repeatGoodMorale && m > 0) {
                state = state.copy(moralePending = chance(rng, rules.goodMoraleChance(m.toLong())))
            }
            return state
        }
        state = state.copy(active = null, bonusTurn = false, moralePending = false)
        return activateNext(state, rng, events)
    }

    private fun stackOf(cmd: BattleCommand): Int? = when (cmd) {
        BattleCommand.Begin -> null
        is BattleCommand.Move -> cmd.stack
        is BattleCommand.Attack -> cmd.stack
        is BattleCommand.Shoot -> cmd.stack
        is BattleCommand.Wait -> cmd.stack
        is BattleCommand.Defend -> cmd.stack
    }

    /** Precomputed validation data: a move path, or an attack head and path. */
    private class Validated(val head: HexCell? = null, val path: List<HexCell> = emptyList())

    /** Python `_validate`: throws [IllegalCommand] or returns precomputed data. Never draws. */
    private fun validate(state: BattleState, cmd: BattleCommand): Validated {
        if (state.rulesHash != rulesHash) {
            throw PackMismatch("state rules_hash ${state.rulesHash} differs from the local rules pack $rulesHash")
        }
        // Python refuses such a policy at construction; a parse without the morale die cannot,
        // so the bound is checked here, before any draw.
        BattleCodec.checkBadMoraleTable(state.policy.badMoraleTable, Math.toIntExact(rules.pack.moraleDie))
        if (cmd is BattleCommand.Begin) {
            if (state.started) throw IllegalCommand("battle already started")
            return Validated()
        }
        if (!state.started) throw IllegalCommand("battle not started")
        if (state.winner != null) throw IllegalCommand("battle is over")
        val sid = stackOf(cmd)
        if (sid != state.active) throw IllegalCommand("stack ${sid ?: "None"} is not the active stack")
        val st = state.stacks[sid!!]
        val off = state.policy.rowOffset
        when (cmd) {
            is BattleCommand.Wait -> {
                if (sid in state.waited || state.bonusTurn) throw IllegalCommand("cannot wait now")
                return Validated()
            }
            is BattleCommand.Defend -> return Validated()
            is BattleCommand.Move -> {
                val r = reach(state, st)
                val path = r[hc(cmd.dest)] ?: throw IllegalCommand("destination not reachable")
                return Validated(hc(cmd.dest), path)
            }
            is BattleCommand.Shoot, is BattleCommand.Attack -> {
                val target = if (cmd is BattleCommand.Shoot) cmd.target else (cmd as BattleCommand.Attack).target
                if (target < 0 || target >= state.stacks.size) throw IllegalCommand("no such target")
                val tgt = state.stacks[target]
                if (!tgt.alive || tgt.side == st.side) throw IllegalCommand("invalid target")
                if (cmd is BattleCommand.Shoot) {
                    if (!st.creature.shooter || st.shots <= 0) throw IllegalCommand("cannot shoot")
                    if (enemyAdjacent(state, st)) throw IllegalCommand("enemy adjacent: must melee")
                    return Validated()
                }
                val fromHex = (cmd as BattleCommand.Attack).fromHex
                val head = if (fromHex == null) hc(st.pos) else hc(fromHex)
                val path: List<HexCell>
                if (head == hc(st.pos)) {
                    path = emptyList()
                } else {
                    path = reach(state, st)[head] ?: throw IllegalCommand("attack hex not reachable")
                }
                val mine = cellsAt(head, st.side, st.creature.doubleWide)
                if (!Hex.adjacentCells(mine, cells(tgt), off)) throw IllegalCommand("target not adjacent to attack hex")
                return Validated(head, path)
            }
            BattleCommand.Begin -> error("unreachable")
        }
    }

    /**
     * Python `apply(state, cmd, rng) -> (state', events)`. Pure in [state]; draws from [rng]
     * (the `battle:<battle_id>` stream) in the documented order. Throws [IllegalCommand]
     * (or [PackMismatch]) before any draw.
     */
    fun apply(state0: BattleState, cmd: BattleCommand, rng: DrawSource): ApplyResult {
        val data = validate(state0, cmd)
        val events = ArrayList<BattleEvent>()
        var state = state0
        if (cmd is BattleCommand.Begin) {
            state = state.copy(started = true, round = 1)
            events.add(BattleEvent.BattleStarted(state.battleId))
            events.add(BattleEvent.RoundStarted(1))
            state = activateNext(state, rng, events)
            return ApplyResult(state, events)
        }
        val st = state.stacks[stackOf(cmd)!!]
        val kind: Kind
        when (cmd) {
            is BattleCommand.Wait -> {
                events.add(BattleEvent.Waited(st.id))
                kind = Kind.WAIT
            }
            is BattleCommand.Defend -> {
                state = set(state, st.copy(defending = true))
                events.add(BattleEvent.Defended(st.id))
                kind = Kind.DEFEND
            }
            is BattleCommand.Move -> {
                state = set(state, st.copy(pos = cmd.dest))
                events.add(BattleEvent.Moved(st.id, listOf(st.pos) + data.path.map(::pair)))
                kind = Kind.MOVE
            }
            is BattleCommand.Shoot -> {
                val shots = if (st.creature.shootsTwice) 2 else 1
                for (i in 0 until shots) {
                    val cur = state.stacks[st.id]
                    if (cur.shots <= 0 || !state.stacks[cmd.target].alive) break
                    state = set(state, cur.copy(shots = cur.shots - 1))
                    state = strike(state, st.id, cmd.target, true, false, rng, events)
                }
                kind = Kind.SHOOT
            }
            is BattleCommand.Attack -> {
                val head = checkNotNull(data.head)
                if (data.path.isNotEmpty()) {
                    state = set(state, st.copy(pos = pair(head)))
                    events.add(BattleEvent.Moved(st.id, listOf(st.pos) + data.path.map(::pair)))
                }
                state = melee(state, st.id, cmd.target, rng, events)
                kind = Kind.ATTACK
            }
            BattleCommand.Begin -> error("unreachable")
        }
        state = finishTurn(state, kind, rng, events)
        return ApplyResult(state, events)
    }

    companion object {
        /** Python `rules.apply_damage` result: (new count, new top HP, killed). */
        data class Damaged(val count: Long, val topHp: Long, val killed: Long)

        /** Python `rules.apply_damage` (rules.md 6.6 step 4). */
        fun applyDamage(count: Long, topHp: Long, maxHp: Long, damage: Long): Damaged {
            require(maxHp > 0L && count >= 0L) { "invalid stack state" }
            require(damage >= 0L) { "damage must be non-negative" }
            if (count == 0L) {
                require(topHp == 0L) { "empty stack must have top_hp 0" }
                return Damaged(0L, 0L, 0L)
            }
            require(topHp in 1L..maxHp) { "invalid stack state" }
            val total = Math.addExact(Math.multiplyExact(count - 1L, maxHp), topHp)
            val remaining = maxOf(0L, total - damage)
            if (remaining == 0L) return Damaged(0L, 0L, count)
            val newCount = -Math.floorDiv(-remaining, maxHp) // ceil
            val newTop = remaining - Math.multiplyExact(newCount - 1L, maxHp)
            return Damaged(newCount, newTop, count - newCount)
        }
    }
}
