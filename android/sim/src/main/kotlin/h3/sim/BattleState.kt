package h3.sim

import java.math.BigInteger

/**
 * Typed battle state model and canonical encoding (battle-port slice 2).
 *
 * Mirrors `tools/h3re/h3re/battle.py`: `BattleState`, `BattlePolicy`, `Stack`, `Creature`, `Hero`,
 * the commands and the events. The state is immutable. `Canonical`-form conversion
 * ([BattleCodec.toMap] / [BattleCodec.parseState]) reproduces `battle.canonical()` byte for byte
 * (ADR-0001, ADR-0005), including the omit-at-default list for policy fields.
 *
 * Numbers are 32-bit `Int` (ADR-0008); sums and hashes elsewhere use `Long`. Balance numbers are
 * not in this file: policy defaults come from the policy pack (`data/battle_policy.json`) and the
 * rules pack (`bad_morale_numerators`) handed to [BattlePolicyPack] (ADR-0004).
 *
 * Positions are `Pair<Int, Int>` = (col, row). Hex geometry is not defined here.
 * No apply logic in this slice.
 */

/** Python `Creature`. The Kotlin defaults are structural (zero / false), as in the dataclass. */
data class BattleCreature(
    val name: String,
    val attack: Int,
    val defense: Int,
    val dmgMin: Int,
    val dmgMax: Int,
    val hp: Int,
    val speed: Int,
    val shots: Int = 0,
    val flyer: Boolean = false,
    val doubleWide: Boolean = false,
    val noEnemyRetaliation: Boolean = false,
    val unlimitedRetaliation: Boolean = false,
    val noMeleePenalty: Boolean = false,
    val noRangePenalty: Boolean = false,
    val strikesTwice: Boolean = false,
    val shootsTwice: Boolean = false,
    val noMorale: Boolean = false,
    val hates: List<String> = emptyList(),
) {
    val shooter: Boolean get() = shots > 0
}

/** Python `Hero` (battle-relevant skills). */
data class BattleHero(
    val attack: Int = 0,
    val defense: Int = 0,
    val offense: Int = 0,
    val archery: Int = 0,
    val armorer: Int = 0,
)

/** Python `Stack`. */
data class BattleStack(
    val id: Int,
    val side: Int,
    val slot: Int,
    val creature: BattleCreature,
    val count: Int,
    val topHp: Int,
    val pos: Pair<Int, Int>,
    val shots: Int,
    val retaliations: Int,
    val defending: Boolean,
    val morale: Int,
    val luck: Int,
) {
    val alive: Boolean get() = count > 0
}

/** Python `BattlePolicy`. No field has a hard-coded default: see [BattlePolicyPack.defaultPolicy]. */
data class BattlePolicy(
    val rowOffset: String,
    val edgeColumnsWalkable: Boolean,
    val placementRows: List<List<Int>>,
    val speedTie: String,
    val waitOrder: String,
    val defendBonusNum: Int,
    val defendBonusDen: Int,
    val defendBonusMin: Int,
    val defendBonusRounding: String,
    val goodMoraleAfterWait: Boolean,
    val goodMoraleAfterDefend: Boolean,
    val repeatGoodMorale: Boolean,
    val badMoraleOnWaitActivation: Boolean,
    val goodMoraleOnWaitActivation: Boolean,
    val badMoraleTable: List<Int>,
    val badLuck: Boolean,
    val rangePenaltyBeyond: Int,
    val rangeOrigin: String,
)

/** Python `BattleState`. [rulesHash] has no default: it is the content hash of the rules pack in use. */
data class BattleState(
    val battleId: String,
    val policy: BattlePolicy,
    val heroes: List<BattleHero?>,
    val obstacles: List<Pair<Int, Int>>,
    val stacks: List<BattleStack>,
    val round: Int = 0,
    val started: Boolean = false,
    val active: Int? = null,
    val done: List<Int> = emptyList(),
    val waited: List<Int> = emptyList(),
    val bonusTurn: Boolean = false,
    val moralePending: Boolean = false,
    val winner: Int? = null,
    val rulesHash: String,
    val lastSide: Int? = null,
)

/**
 * Python `defend_bonus` for a Defense sum [base] (creature plus hero, already widened):
 * max(min, round(base * num / den)), floor or ceil. Long throughout: |base| <= 2**32 and
 * num <= 2**31-1, so the product stays below 2**63 (ADR-0008).
 */
internal fun policyDefendBonus(p: BattlePolicy, base: Long): Long {
    val num = Math.multiplyExact(base, p.defendBonusNum.toLong())
    val den = p.defendBonusDen.toLong()
    val b = if (p.defendBonusRounding == "floor") Math.floorDiv(num, den) else Math.negateExact(Math.floorDiv(Math.negateExact(num), den))
    return maxOf(p.defendBonusMin.toLong(), b)
}

/** Commands (Python `Begin`, `Move`, ...). */
sealed interface BattleCommand {
    data object Begin : BattleCommand
    data class Move(val stack: Int, val dest: Pair<Int, Int>) : BattleCommand
    data class Attack(val stack: Int, val target: Int, val fromHex: Pair<Int, Int>? = null) : BattleCommand
    data class Shoot(val stack: Int, val target: Int) : BattleCommand
    data class Wait(val stack: Int) : BattleCommand
    data class Defend(val stack: Int) : BattleCommand
}

/** Events emitted by `battle.apply`. */
sealed interface BattleEvent {
    data class BattleStarted(val battleId: String) : BattleEvent
    data class RoundStarted(val round: Int) : BattleEvent
    data class TurnStarted(val stack: Int, val phase: String, val bonus: Boolean) : BattleEvent
    data class MoraleFrozen(val stack: Int) : BattleEvent
    data class MoraleBoost(val stack: Int) : BattleEvent
    data class Moved(val stack: Int, val path: List<Pair<Int, Int>>) : BattleEvent
    data class Waited(val stack: Int) : BattleEvent
    data class Defended(val stack: Int) : BattleEvent
    data class LuckRolled(val stack: Int, val good: Boolean) : BattleEvent
    data class DamageDealt(
        val attacker: Int,
        val target: Int,
        /** Can exceed `Int` (ADR-0008 cap rule: only the inputs are capped, not the product). */
        val damage: Long,
        val killed: Int,
        val ranged: Boolean,
        val retaliation: Boolean,
    ) : BattleEvent
    data class UnitDied(val stack: Int) : BattleEvent
    data class BattleEnded(val winner: Int) : BattleEvent
}

/**
 * The policy defaults, read from `data/battle_policy.json` (parsed map) plus the rules pack's
 * default bad-morale table. Python takes `bad_morale_table` from `rules.BAD_MORALE_NUMERATORS`,
 * so it is not in the policy file.
 */
class BattlePolicyPack(
    policyJson: Map<String, Any?>,
    val badMoraleNumerators: List<Int>,
    /**
     * The rules pack's `morale_die`, the upper bound of every bad-morale table entry. Null when
     * the caller does not pass it: the bound is then checked by [Battle.apply] before any draw.
     */
    val moraleDie: Int? = null,
) {
    private val policy: BattlePolicy

    init {
        val m = policyJson.filterKeys { it != "schema_version" }
        BattleJson.exactKeys(m, POLICY_FILE_KEYS, "policy pack")
        policy = BattleCodec.policyFrom(m + ("bad_morale_table" to badMoraleNumerators), "policy pack", moraleDie)
    }

    /** Python `BattlePolicy()` (the `DEFAULT_POLICY`). */
    fun defaultPolicy(): BattlePolicy = policy

    /** The defaults with some policy fields replaced, keyed by Python field name (like `BattlePolicy(**kw)`). */
    fun policy(overrides: Map<String, Any?>): BattlePolicy {
        val base = BattleCodec.policyToMap(policy).toMutableMap()
        for ((k, v) in overrides) {
            require(k in base) { "unknown policy field: $k" }
            base[k] = v
        }
        return BattleCodec.policyFrom(base, "policy", moraleDie)
    }

    companion object {
        private val POLICY_FILE_KEYS = BattleCodec.POLICY_KEYS - "bad_morale_table"
    }
}

/** Strict reading helpers over parsed JSON (integers arrive as [BigInteger], or [Int]/[Long] from encoders). */
internal object BattleJson {
    fun exactKeys(m: Map<String, Any?>, keys: Set<String>, what: String) {
        require(m.keys == keys) {
            "$what: keys differ; missing ${keys - m.keys}, unexpected ${m.keys - keys}"
        }
    }

    fun obj(v: Any?, what: String): Map<String, Any?> {
        require(v is Map<*, *>) { "$what: expected object" }
        @Suppress("UNCHECKED_CAST")
        return v as Map<String, Any?>
    }

    fun list(v: Any?, what: String): List<Any?> {
        require(v is List<*>) { "$what: expected array" }
        return v
    }

    /** A 32-bit Int (ADR-0008). Out of range is an [IllegalArgumentException] "<what> out of range", as in Python. */
    fun int(v: Any?, what: String): Int {
        val l = long(v, what)
        require(l in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong()) { "$what out of range" }
        return l.toInt()
    }

    fun long(v: Any?, what: String): Long = when (v) {
        is BigInteger -> {
            require(v.bitLength() < 64) { "$what out of range" }
            v.toLong()
        }
        is Int -> v.toLong()
        is Long -> v
        else -> throw IllegalArgumentException("$what: expected integer")
    }

    fun intOrNull(v: Any?, what: String): Int? = if (v == null) null else int(v, what)

    fun bool(v: Any?, what: String): Boolean {
        require(v is Boolean) { "$what: expected boolean" }
        return v
    }

    fun str(v: Any?, what: String): String {
        require(v is String) { "$what: expected string" }
        return v
    }

    fun pos(v: Any?, what: String): Pair<Int, Int> {
        val l = list(v, what)
        require(l.size == 2) { "$what: expected [col, row]" }
        return Pair(int(l[0], what), int(l[1], what))
    }

    fun posOrNull(v: Any?, what: String): Pair<Int, Int>? = if (v == null) null else pos(v, what)

    fun ints(v: Any?, what: String): List<Int> = list(v, what).map { int(it, what) }
}

/**
 * Canonical conversion for the battle model. [toMap] yields exactly the structure
 * `battle.canonical()` serialises (tuples are lists, `None` is null); [Canonical.encode] turns it
 * into bytes. [omitWhenDefault] is Python's `_OMIT_WHEN_DEFAULT` (policy field names): a listed
 * field is left out while it equals the pack default. It is empty today (ADR-0005).
 */
class BattleCodec(
    val pack: BattlePolicyPack,
    val omitWhenDefault: List<String> = emptyList(),
) {
    init {
        require(omitWhenDefault.all { it in POLICY_KEYS }) { "unknown omit-when-default policy field" }
    }

    private val defaultPolicyMap: Map<String, Any?> = policyToMap(pack.defaultPolicy())

    fun toMap(s: BattleState): Map<String, Any?> {
        val policy = policyToMap(s.policy).toMutableMap()
        for (name in omitWhenDefault) if (policy[name] == defaultPolicyMap[name]) policy.remove(name)
        return linkedMapOf(
            "battle_id" to s.battleId,
            "policy" to policy,
            "heroes" to s.heroes.map { h -> h?.let(::heroToMap) },
            "obstacles" to s.obstacles.map(::posList),
            "stacks" to s.stacks.map(::stackToMap),
            "round" to s.round,
            "started" to s.started,
            "active" to s.active,
            "done" to s.done,
            "waited" to s.waited,
            "bonus_turn" to s.bonusTurn,
            "morale_pending" to s.moralePending,
            "winner" to s.winner,
            "rules_hash" to s.rulesHash,
            "last_side" to s.lastSide,
        )
    }

    /** Canonical text (ASCII) of the state: `battle.canonical(state).decode("ascii")`. */
    fun canonicalText(s: BattleState): String = Canonical.encode(toMap(s)).toString(Charsets.US_ASCII)

    /** SHA-256 hex of the canonical bytes: `battle.state_hash`. */
    fun stateHash(s: BattleState): String = Canonical.hash(toMap(s))

    fun parseState(v: Any?): BattleState {
        val m = BattleJson.obj(v, "state")
        BattleJson.exactKeys(m, STATE_KEYS, "state")
        val pm = BattleJson.obj(m["policy"], "policy").toMutableMap()
        for (name in omitWhenDefault) if (name !in pm) pm[name] = defaultPolicyMap[name]
        return BattleState(
            battleId = BattleJson.str(m["battle_id"], "battle_id"),
            policy = policyFrom(pm, "policy", pack.moraleDie),
            heroes = BattleJson.list(m["heroes"], "heroes").map { h -> h?.let { heroFrom(it) } },
            obstacles = BattleJson.list(m["obstacles"], "obstacles").map { BattleJson.pos(it, "obstacle") },
            stacks = BattleJson.list(m["stacks"], "stacks").map { stackFrom(it) },
            round = BattleJson.int(m["round"], "round"),
            started = BattleJson.bool(m["started"], "started"),
            active = BattleJson.intOrNull(m["active"], "active"),
            done = BattleJson.ints(m["done"], "done"),
            waited = BattleJson.ints(m["waited"], "waited"),
            bonusTurn = BattleJson.bool(m["bonus_turn"], "bonus_turn"),
            moralePending = BattleJson.bool(m["morale_pending"], "morale_pending"),
            winner = BattleJson.intOrNull(m["winner"], "winner"),
            rulesHash = BattleJson.str(m["rules_hash"], "rules_hash"),
            lastSide = BattleJson.intOrNull(m["last_side"], "last_side"),
        ).also(::checkState)
    }

    companion object {
        val STATE_KEYS = setOf(
            "battle_id", "policy", "heroes", "obstacles", "stacks", "round", "started", "active",
            "done", "waited", "bonus_turn", "morale_pending", "winner", "rules_hash", "last_side",
        )
        val POLICY_KEYS = setOf(
            "row_offset", "edge_columns_walkable", "placement_rows", "speed_tie", "wait_order",
            "defend_bonus_num", "defend_bonus_den", "defend_bonus_min", "defend_bonus_rounding",
            "good_morale_after_wait", "good_morale_after_defend", "repeat_good_morale",
            "bad_morale_on_wait_activation", "good_morale_on_wait_activation", "bad_morale_table",
            "bad_luck", "range_penalty_beyond", "range_origin",
        )
        val STACK_KEYS = setOf(
            "id", "side", "slot", "creature", "count", "top_hp", "pos", "shots", "retaliations",
            "defending", "morale", "luck",
        )
        val CREATURE_KEYS = setOf(
            "name", "attack", "defense", "dmg_min", "dmg_max", "hp", "speed", "shots", "flyer",
            "double_wide", "no_enemy_retaliation", "unlimited_retaliation", "no_melee_penalty",
            "no_range_penalty", "strikes_twice", "shoots_twice", "no_morale", "hates",
        )
        val HERO_KEYS = setOf("attack", "defense", "offense", "archery", "armorer")

        private fun posList(p: Pair<Int, Int>): List<Int> = listOf(p.first, p.second)

        fun policyToMap(p: BattlePolicy): Map<String, Any?> = linkedMapOf(
            "row_offset" to p.rowOffset,
            "edge_columns_walkable" to p.edgeColumnsWalkable,
            "placement_rows" to p.placementRows,
            "speed_tie" to p.speedTie,
            "wait_order" to p.waitOrder,
            "defend_bonus_num" to p.defendBonusNum,
            "defend_bonus_den" to p.defendBonusDen,
            "defend_bonus_min" to p.defendBonusMin,
            "defend_bonus_rounding" to p.defendBonusRounding,
            "good_morale_after_wait" to p.goodMoraleAfterWait,
            "good_morale_after_defend" to p.goodMoraleAfterDefend,
            "repeat_good_morale" to p.repeatGoodMorale,
            "bad_morale_on_wait_activation" to p.badMoraleOnWaitActivation,
            "good_morale_on_wait_activation" to p.goodMoraleOnWaitActivation,
            "bad_morale_table" to p.badMoraleTable,
            "bad_luck" to p.badLuck,
            "range_penalty_beyond" to p.rangePenaltyBeyond,
            "range_origin" to p.rangeOrigin,
        )

        /** Python `BattlePolicy(**m)`: the choices and fractions `__post_init__` refuses are refused here too. */
        fun policyFrom(m: Map<String, Any?>, what: String, moraleDie: Int? = null): BattlePolicy {
            BattleJson.exactKeys(m, POLICY_KEYS, what)
            return checkPolicy(BattlePolicy(
                rowOffset = BattleJson.str(m["row_offset"], "row_offset"),
                edgeColumnsWalkable = BattleJson.bool(m["edge_columns_walkable"], "edge_columns_walkable"),
                placementRows = BattleJson.list(m["placement_rows"], "placement_rows")
                    .map { BattleJson.ints(it, "placement_rows") },
                speedTie = BattleJson.str(m["speed_tie"], "speed_tie"),
                waitOrder = BattleJson.str(m["wait_order"], "wait_order"),
                defendBonusNum = BattleJson.int(m["defend_bonus_num"], "defend_bonus_num"),
                defendBonusDen = BattleJson.int(m["defend_bonus_den"], "defend_bonus_den"),
                defendBonusMin = BattleJson.int(m["defend_bonus_min"], "defend_bonus_min"),
                defendBonusRounding = BattleJson.str(m["defend_bonus_rounding"], "defend_bonus_rounding"),
                goodMoraleAfterWait = BattleJson.bool(m["good_morale_after_wait"], "good_morale_after_wait"),
                goodMoraleAfterDefend = BattleJson.bool(m["good_morale_after_defend"], "good_morale_after_defend"),
                repeatGoodMorale = BattleJson.bool(m["repeat_good_morale"], "repeat_good_morale"),
                badMoraleOnWaitActivation = BattleJson.bool(
                    m["bad_morale_on_wait_activation"], "bad_morale_on_wait_activation"),
                goodMoraleOnWaitActivation = BattleJson.bool(
                    m["good_morale_on_wait_activation"], "good_morale_on_wait_activation"),
                badMoraleTable = BattleJson.ints(m["bad_morale_table"], "bad_morale_table"),
                badLuck = BattleJson.bool(m["bad_luck"], "bad_luck"),
                rangePenaltyBeyond = BattleJson.int(m["range_penalty_beyond"], "range_penalty_beyond"),
                rangeOrigin = BattleJson.str(m["range_origin"], "range_origin"),
            ), moraleDie)
        }

        // datapack.POLICY_CHOICES (data/battle_policy.json validation), in the same order.
        val ROW_OFFSETS = setOf("odd", "even")
        val SPEED_TIES = setOf("attacker_first", "alternate", "alternate_last_mover")
        val WAIT_ORDERS = setOf("reverse_speed", "speed", "fifo", "slow_first_alternate")
        val RANGE_ORIGINS = setOf("head", "any_cell")
        val ROUNDINGS = setOf("floor", "ceil")

        /**
         * Python `BattlePolicy.__post_init__`, check for check and message for message. [moraleDie]
         * null skips only the upper bound of the bad-morale entries ([Battle.apply] checks it).
         */
        fun checkPolicy(p: BattlePolicy, moraleDie: Int?): BattlePolicy {
            require(p.rowOffset in ROW_OFFSETS) { "row_offset must be 'odd' or 'even'" }
            require(p.speedTie in SPEED_TIES) { "bad speed_tie" }
            require(p.waitOrder in WAIT_ORDERS) { "bad wait_order" }
            require(p.rangeOrigin in RANGE_ORIGINS) { "bad range_origin" }
            checkBadMoraleTable(p.badMoraleTable, moraleDie)
            require(p.defendBonusRounding in ROUNDINGS) { "bad defend_bonus_rounding" }
            require(p.defendBonusDen > 0 && p.defendBonusNum >= 0) { "bad defend bonus fraction" }
            require(p.placementRows.size == 7 && p.placementRows.withIndex().all { (i, r) -> r.size == i + 1 }) {
                "placement_rows needs 7 rows tuples of size 1..7"
            }
            require(p.rangePenaltyBeyond >= 0) { "bad range_penalty_beyond" }
            // ADR-0008 bounds; the upper bound is the Int range, already enforced by the parse.
            require(p.defendBonusMin >= 0) { "defend_bonus_min out of range" }
            return p
        }

        /** Python `rules.check_bad_morale_table`; [die] null skips the upper bound. */
        fun checkBadMoraleTable(table: List<Int>, die: Int?) {
            require(table.size == 3 && table.all { it >= 0 && (die == null || it <= die) }) {
                "bad_morale_table needs 3 integers in 0..${die ?: "morale_die"}"
            }
            require(table.zipWithNext().all { (a, b) -> a <= b }) { "bad_morale_table must be non-decreasing" }
        }

        private fun bounded(v: Long, name: String, lo: Long, hi: Long) {
            require(v in lo..hi) { "$name out of range" }
        }

        private val MIN = Int.MIN_VALUE.toLong()
        private val MAX = Int.MAX_VALUE.toLong()

        /**
         * Python `battle.check_state` (battle.md "State invariants and integer caps", ADR-0008):
         * same checks, same order, same messages. Every parsed state passes through it.
         */
        fun checkState(s: BattleState) {
            require(s.heroes.size == 2) { "heroes must be a pair" }
            for (o in s.obstacles) require(Hex.inGrid(HexCell(o.first, o.second))) { "obstacle off grid" }
            val perSide = IntArray(2)
            for ((i, st) in s.stacks.withIndex()) {
                require(st.id == i) { "stack id differs from its index" }
                require(st.side == Hex.ATTACKER || st.side == Hex.DEFENDER) { "stack side must be 0 or 1" }
                perSide[st.side]++
                bounded(st.slot.toLong(), "stack slot", 0L, 6L)
                val cr = st.creature
                bounded(cr.dmgMin.toLong(), "creature dmg_min", 1L, MAX)
                bounded(cr.dmgMax.toLong(), "creature dmg_max", 1L, MAX)
                bounded(cr.hp.toLong(), "creature hp", 1L, MAX)
                bounded(cr.speed.toLong(), "creature speed", 0L, MAX)
                bounded(cr.shots.toLong(), "creature shots", 0L, MAX)
                require(cr.dmgMin <= cr.dmgMax) { "invalid damage range" }
                bounded(st.count.toLong(), "stack count", 0L, MAX)
                if (st.count == 0) {
                    require(st.topHp == 0) { "empty stack must have top_hp 0" }
                } else {
                    bounded(st.topHp.toLong(), "stack top_hp", 1L, cr.hp.toLong())
                }
                bounded(st.shots.toLong(), "stack shots", 0L, MAX)
                bounded(st.retaliations.toLong(), "stack retaliations", 0L, MAX)
                require(Hex.cellsAt(HexCell(st.pos.first, st.pos.second), st.side, cr.doubleWide).all(Hex::inGrid)) {
                    "stack position off grid"
                }
                // Both factors are in 0..2**31-1, so the Long products cannot overflow.
                require(st.count.toLong() * cr.dmgMax.toLong() <= MAX) { "count x dmg_max exceeds 2**31-1" }
                require(st.count.toLong() * cr.hp.toLong() <= MAX) { "count x hp exceeds 2**31-1" }
                val hero = s.heroes[st.side]
                bounded(cr.attack.toLong() + (hero?.attack ?: 0).toLong(), "attack sum", MIN, MAX)
                val d = cr.defense.toLong() + (hero?.defense ?: 0).toLong()
                bounded(d, "defense sum", MIN, MAX)
                bounded(Math.addExact(d, policyDefendBonus(s.policy, d)), "defense sum", MIN, MAX)
            }
            require(perSide.all { it in 1..7 }) { "each side needs 1..7 stacks" }
            val n = s.stacks.size.toLong()
            bounded(s.round.toLong(), "round", 0L, MAX)
            s.active?.let { bounded(it.toLong(), "active", 0L, n - 1L) }
            for (v in s.done) bounded(v.toLong(), "done", 0L, n - 1L)
            for (v in s.waited) bounded(v.toLong(), "waited", 0L, n - 1L)
            require(s.winner == null || s.winner == 0 || s.winner == 1) { "winner must be 0, 1 or None" }
            require(s.lastSide == null || s.lastSide == 0 || s.lastSide == 1) { "last_side must be 0, 1 or None" }
        }

        fun heroToMap(h: BattleHero): Map<String, Any?> = linkedMapOf(
            "attack" to h.attack, "defense" to h.defense, "offense" to h.offense,
            "archery" to h.archery, "armorer" to h.armorer,
        )

        fun heroFrom(v: Any?): BattleHero {
            val m = BattleJson.obj(v, "hero")
            BattleJson.exactKeys(m, HERO_KEYS, "hero")
            return BattleHero(
                attack = BattleJson.int(m["attack"], "hero attack"),
                defense = BattleJson.int(m["defense"], "hero defense"),
                offense = BattleJson.int(m["offense"], "hero offense"),
                archery = BattleJson.int(m["archery"], "hero archery"),
                armorer = BattleJson.int(m["armorer"], "hero armorer"),
            )
        }

        fun creatureToMap(c: BattleCreature): Map<String, Any?> = linkedMapOf(
            "name" to c.name, "attack" to c.attack, "defense" to c.defense,
            "dmg_min" to c.dmgMin, "dmg_max" to c.dmgMax, "hp" to c.hp, "speed" to c.speed,
            "shots" to c.shots, "flyer" to c.flyer, "double_wide" to c.doubleWide,
            "no_enemy_retaliation" to c.noEnemyRetaliation,
            "unlimited_retaliation" to c.unlimitedRetaliation,
            "no_melee_penalty" to c.noMeleePenalty, "no_range_penalty" to c.noRangePenalty,
            "strikes_twice" to c.strikesTwice, "shoots_twice" to c.shootsTwice,
            "no_morale" to c.noMorale, "hates" to c.hates,
        )

        fun creatureFrom(v: Any?): BattleCreature {
            val m = BattleJson.obj(v, "creature")
            BattleJson.exactKeys(m, CREATURE_KEYS, "creature")
            return BattleCreature(
                name = BattleJson.str(m["name"], "name"),
                attack = BattleJson.int(m["attack"], "creature attack"),
                defense = BattleJson.int(m["defense"], "creature defense"),
                dmgMin = BattleJson.int(m["dmg_min"], "creature dmg_min"),
                dmgMax = BattleJson.int(m["dmg_max"], "creature dmg_max"),
                hp = BattleJson.int(m["hp"], "creature hp"),
                speed = BattleJson.int(m["speed"], "creature speed"),
                shots = BattleJson.int(m["shots"], "creature shots"),
                flyer = BattleJson.bool(m["flyer"], "flyer"),
                doubleWide = BattleJson.bool(m["double_wide"], "double_wide"),
                noEnemyRetaliation = BattleJson.bool(m["no_enemy_retaliation"], "no_enemy_retaliation"),
                unlimitedRetaliation = BattleJson.bool(m["unlimited_retaliation"], "unlimited_retaliation"),
                noMeleePenalty = BattleJson.bool(m["no_melee_penalty"], "no_melee_penalty"),
                noRangePenalty = BattleJson.bool(m["no_range_penalty"], "no_range_penalty"),
                strikesTwice = BattleJson.bool(m["strikes_twice"], "strikes_twice"),
                shootsTwice = BattleJson.bool(m["shoots_twice"], "shoots_twice"),
                noMorale = BattleJson.bool(m["no_morale"], "no_morale"),
                hates = BattleJson.list(m["hates"], "hates").map { BattleJson.str(it, "hates") },
            )
        }

        fun stackToMap(s: BattleStack): Map<String, Any?> = linkedMapOf(
            "id" to s.id, "side" to s.side, "slot" to s.slot, "creature" to creatureToMap(s.creature),
            "count" to s.count, "top_hp" to s.topHp, "pos" to posList(s.pos), "shots" to s.shots,
            "retaliations" to s.retaliations, "defending" to s.defending, "morale" to s.morale,
            "luck" to s.luck,
        )

        fun stackFrom(v: Any?): BattleStack {
            val m = BattleJson.obj(v, "stack")
            BattleJson.exactKeys(m, STACK_KEYS, "stack")
            return BattleStack(
                id = BattleJson.int(m["id"], "stack id"),
                side = BattleJson.int(m["side"], "stack side"),
                slot = BattleJson.int(m["slot"], "stack slot"),
                creature = creatureFrom(m["creature"]),
                count = BattleJson.int(m["count"], "stack count"),
                topHp = BattleJson.int(m["top_hp"], "stack top_hp"),
                pos = BattleJson.pos(m["pos"], "pos"),
                shots = BattleJson.int(m["shots"], "stack shots"),
                retaliations = BattleJson.int(m["retaliations"], "stack retaliations"),
                defending = BattleJson.bool(m["defending"], "defending"),
                morale = BattleJson.int(m["morale"], "stack morale"),
                luck = BattleJson.int(m["luck"], "stack luck"),
            )
        }

        /** Python `soak.encode_command`: `{"type": ClassName, <fields>}`; works for events too. */
        fun commandToMap(c: BattleCommand): Map<String, Any?> = when (c) {
            BattleCommand.Begin -> mapOf("type" to "Begin")
            is BattleCommand.Move -> mapOf("type" to "Move", "stack" to c.stack, "dest" to posList(c.dest))
            is BattleCommand.Attack -> mapOf(
                "type" to "Attack", "stack" to c.stack, "target" to c.target,
                "from_hex" to c.fromHex?.let(::posList))
            is BattleCommand.Shoot -> mapOf("type" to "Shoot", "stack" to c.stack, "target" to c.target)
            is BattleCommand.Wait -> mapOf("type" to "Wait", "stack" to c.stack)
            is BattleCommand.Defend -> mapOf("type" to "Defend", "stack" to c.stack)
        }

        fun parseCommand(v: Any?): BattleCommand {
            val m = BattleJson.obj(v, "command")
            fun keys(vararg k: String) = BattleJson.exactKeys(m, setOf("type") + k, "command")
            fun i(k: String) = BattleJson.int(m[k], k)
            return when (val t = BattleJson.str(m["type"], "type")) {
                "Begin" -> { keys(); BattleCommand.Begin }
                "Move" -> { keys("stack", "dest"); BattleCommand.Move(i("stack"), BattleJson.pos(m["dest"], "dest")) }
                "Attack" -> {
                    keys("stack", "target", "from_hex")
                    BattleCommand.Attack(i("stack"), i("target"), BattleJson.posOrNull(m["from_hex"], "from_hex"))
                }
                "Shoot" -> { keys("stack", "target"); BattleCommand.Shoot(i("stack"), i("target")) }
                "Wait" -> { keys("stack"); BattleCommand.Wait(i("stack")) }
                "Defend" -> { keys("stack"); BattleCommand.Defend(i("stack")) }
                else -> throw IllegalArgumentException("unknown command type: $t")
            }
        }

        fun eventToMap(e: BattleEvent): Map<String, Any?> = when (e) {
            is BattleEvent.BattleStarted -> mapOf("type" to "BattleStarted", "battle_id" to e.battleId)
            is BattleEvent.RoundStarted -> mapOf("type" to "RoundStarted", "round" to e.round)
            is BattleEvent.TurnStarted -> mapOf(
                "type" to "TurnStarted", "stack" to e.stack, "phase" to e.phase, "bonus" to e.bonus)
            is BattleEvent.MoraleFrozen -> mapOf("type" to "MoraleFrozen", "stack" to e.stack)
            is BattleEvent.MoraleBoost -> mapOf("type" to "MoraleBoost", "stack" to e.stack)
            is BattleEvent.Moved -> mapOf("type" to "Moved", "stack" to e.stack, "path" to e.path.map(::posList))
            is BattleEvent.Waited -> mapOf("type" to "Waited", "stack" to e.stack)
            is BattleEvent.Defended -> mapOf("type" to "Defended", "stack" to e.stack)
            is BattleEvent.LuckRolled -> mapOf("type" to "LuckRolled", "stack" to e.stack, "good" to e.good)
            is BattleEvent.DamageDealt -> mapOf(
                "type" to "DamageDealt", "attacker" to e.attacker, "target" to e.target,
                "damage" to e.damage, "killed" to e.killed, "ranged" to e.ranged,
                "retaliation" to e.retaliation)
            is BattleEvent.UnitDied -> mapOf("type" to "UnitDied", "stack" to e.stack)
            is BattleEvent.BattleEnded -> mapOf("type" to "BattleEnded", "winner" to e.winner)
        }

        fun parseEvent(v: Any?): BattleEvent {
            val m = BattleJson.obj(v, "event")
            fun keys(vararg k: String) = BattleJson.exactKeys(m, setOf("type") + k, "event")
            fun i(k: String) = BattleJson.int(m[k], k)
            fun b(k: String) = BattleJson.bool(m[k], k)
            return when (val t = BattleJson.str(m["type"], "type")) {
                "BattleStarted" -> { keys("battle_id"); BattleEvent.BattleStarted(BattleJson.str(m["battle_id"], "battle_id")) }
                "RoundStarted" -> { keys("round"); BattleEvent.RoundStarted(i("round")) }
                "TurnStarted" -> {
                    keys("stack", "phase", "bonus")
                    BattleEvent.TurnStarted(i("stack"), BattleJson.str(m["phase"], "phase"), b("bonus"))
                }
                "MoraleFrozen" -> { keys("stack"); BattleEvent.MoraleFrozen(i("stack")) }
                "MoraleBoost" -> { keys("stack"); BattleEvent.MoraleBoost(i("stack")) }
                "Moved" -> {
                    keys("stack", "path")
                    BattleEvent.Moved(i("stack"), BattleJson.list(m["path"], "path").map { BattleJson.pos(it, "path") })
                }
                "Waited" -> { keys("stack"); BattleEvent.Waited(i("stack")) }
                "Defended" -> { keys("stack"); BattleEvent.Defended(i("stack")) }
                "LuckRolled" -> { keys("stack", "good"); BattleEvent.LuckRolled(i("stack"), b("good")) }
                "DamageDealt" -> {
                    keys("attacker", "target", "damage", "killed", "ranged", "retaliation")
                    BattleEvent.DamageDealt(
                        i("attacker"), i("target"), BattleJson.long(m["damage"], "damage"), i("killed"),
                        b("ranged"), b("retaliation"),
                    )
                }
                "UnitDied" -> { keys("stack"); BattleEvent.UnitDied(i("stack")) }
                "BattleEnded" -> { keys("winner"); BattleEvent.BattleEnded(i("winner")) }
                else -> throw IllegalArgumentException("unknown event type: $t")
            }
        }
    }
}
