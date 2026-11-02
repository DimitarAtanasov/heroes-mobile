package h3.sim

import java.math.BigInteger

/**
 * Battle scenario parsing and initial-state creation (milestone A5; docs/specs/conformance-replay.md).
 *
 * A port of `battle_cli.parse_scenario` and `battle.create_battle` (Python is the oracle,
 * ADR-0004). [Scenario.parse] reads the scenario JSON text (schema: docs/specs/battle-scenario.md)
 * and builds the initial, not yet started [BattleState]: placement rows, the integer caps of
 * `check_state` and the validation errors included. `Battle.kt` has no `createBattle`, so the
 * equivalent lives here, on public APIs only.
 *
 * Errors are [ScenarioError] with the Python `CliError` text (`"scenario.attackers[0].count must be
 * an integer"`, `"scenario: stack 0 cannot be placed at (1, 5)"`). Where Python accepts an
 * arbitrary-size integer and fails later in `check_state`, Kotlin fails at the 32-bit conversion with
 * `"<path> out of range"` (the error is still a [ScenarioError]; only the text differs).
 */
class ScenarioError(message: String) : IllegalArgumentException(message)

/** The pieces of a [Datapack] a battle needs, built once per call. */
internal class BattleEngine(packs: Datapack) {
    val rulesHash: String = packs.rules.contentHash
    val moraleDie: Int = Math.toIntExact(packs.rules.pack.moraleDie)
    val policyPack = BattlePolicyPack(
        packs.policy.values, packs.rules.pack.badMoraleNumerators.map { Math.toIntExact(it) }, moraleDie,
    )
    val codec = BattleCodec(policyPack)
    val battle = Battle(Rules(packs.rules.pack), rulesHash)
}

object Scenario {
    /** Python `parse_scenario(json.loads(text))`: the initial state of the scenario in [json]. */
    fun parse(json: String, packs: Datapack): BattleState {
        val tree = try {
            ScenarioJson.parse(json, rejectFloats = false)
        } catch (e: ScenarioJson.Syntax) {
            throw ScenarioError("invalid JSON: ${e.message}")
        } catch (e: ScenarioJson.Rejected) {
            throw ScenarioError("invalid JSON: ${e.message}")
        }
        return parseTree(tree, BattleEngine(packs))
    }

    internal fun parseTree(tree: Any?, engine: BattleEngine): BattleState {
        try {
            return build(tree, engine)
        } catch (e: ScenarioError) {
            throw e
        } catch (e: IllegalArgumentException) {
            // Ints beyond 32 bits and the like, from BattleJson.
            throw ScenarioError("scenario: ${e.message}")
        } catch (e: ArithmeticException) {
            throw ScenarioError("scenario: ${e.message}")
        }
    }

    // ------------------------------------------------------------------ parsing

    private val TOP_KEYS = setOf("battle_id", "creatures", "attackers", "defenders", "obstacles", "heroes", "policy")
    private val STACK_KEYS = setOf("creature", "count", "morale", "luck", "pos")
    private val CREATURE_REQUIRED = listOf("attack", "defense", "dmg_min", "dmg_max", "hp", "speed")
    private val CREATURE_INTS = setOf("attack", "defense", "dmg_min", "dmg_max", "hp", "speed", "shots")
    private val CREATURE_BOOLS = setOf(
        "flyer", "double_wide", "no_enemy_retaliation", "unlimited_retaliation", "no_melee_penalty",
        "no_range_penalty", "strikes_twice", "shoots_twice", "no_morale",
    )
    private val CREATURE_KEYS = CREATURE_INTS + CREATURE_BOOLS + "hates"
    private val HERO_KEYS = setOf("attack", "defense", "offense", "archery", "armorer")
    private val POLICY_INTS = setOf(
        "defend_bonus_num", "defend_bonus_den", "defend_bonus_min", "range_penalty_beyond",
    )
    private val POLICY_STRS = setOf(
        "row_offset", "speed_tie", "wait_order", "defend_bonus_rounding", "range_origin",
    )
    private val POLICY_BOOLS = setOf(
        "edge_columns_walkable", "good_morale_after_wait", "good_morale_after_defend",
        "repeat_good_morale", "bad_morale_on_wait_activation", "good_morale_on_wait_activation", "bad_luck",
    )
    private val POLICY_TUPLES = setOf("placement_rows", "bad_morale_table")

    private fun repr(v: Any?): String = when (v) {
        is String -> PackJson.pyRepr(v)
        null -> "None"
        true -> "True"
        false -> "False"
        else -> v.toString()
    }

    private fun obj(v: Any?, path: String): Map<String, Any?> {
        if (v !is Map<*, *>) throw ScenarioError("$path must be an object")
        @Suppress("UNCHECKED_CAST")
        return v as Map<String, Any?>
    }

    private fun checkKeys(o: Map<String, Any?>, path: String, allowed: Set<String>) {
        val unknown = o.keys.filter { it !in allowed }.sortedWith(PackJson.codePointOrder)
        if (unknown.isNotEmpty()) throw ScenarioError("$path: unknown key ${PackJson.pyRepr(unknown[0])}")
    }

    private fun int(v: Any?, path: String): Int {
        if (v !is BigInteger) throw ScenarioError("$path must be an integer")
        if (v.bitLength() > 31) throw ScenarioError("$path out of range")
        return v.toInt()
    }

    private fun pair(v: Any?, path: String): Pair<Int, Int> {
        if (v !is List<*> || v.size != 2) throw ScenarioError("$path must be a [col, row] pair")
        return Pair(int(v[0], "$path[0]"), int(v[1], "$path[1]"))
    }

    /** Python `_freeze`: nested lists stay lists, leaves must be bool, int or str. */
    private fun freeze(v: Any?, path: String): Any? = when (v) {
        is List<*> -> v.mapIndexed { i, e -> freeze(e, "$path[$i]") }
        is Boolean, is BigInteger, is String -> v
        else -> throw ScenarioError("$path contains an unsupported value")
    }

    private fun bool(v: Any?, path: String): Boolean {
        if (v !is Boolean) throw ScenarioError("$path must be true or false")
        return v
    }

    private fun str(v: Any?, path: String): String {
        if (v !is String) throw ScenarioError("$path must be a string")
        return v
    }

    private fun tuple(v: Any?, path: String): Any? {
        if (v !is List<*>) throw ScenarioError("$path must be a list")
        return freeze(v, path)
    }

    private fun creature(name: String, o: Map<String, Any?>, path: String): BattleCreature {
        checkKeys(o, path, CREATURE_KEYS)
        for (k in CREATURE_REQUIRED) if (k !in o) throw ScenarioError("$path: missing key ${PackJson.pyRepr(k)}")
        val ints = LinkedHashMap<String, Int>()
        val bools = LinkedHashMap<String, Boolean>()
        var hates: List<*> = emptyList<Any?>()
        for ((k, v) in o) {
            val p = "$path.$k"
            when (k) {
                in CREATURE_INTS -> ints[k] = int(v, p)
                in CREATURE_BOOLS -> bools[k] = bool(v, p)
                else -> hates = tuple(v, p) as List<*>
            }
        }
        for (h in hates) if (h !is String) throw ScenarioError("$path.hates must contain creature names")
        return BattleCreature(
            name = name,
            attack = ints.getValue("attack"), defense = ints.getValue("defense"),
            dmgMin = ints.getValue("dmg_min"), dmgMax = ints.getValue("dmg_max"),
            hp = ints.getValue("hp"), speed = ints.getValue("speed"), shots = ints["shots"] ?: 0,
            flyer = bools["flyer"] ?: false, doubleWide = bools["double_wide"] ?: false,
            noEnemyRetaliation = bools["no_enemy_retaliation"] ?: false,
            unlimitedRetaliation = bools["unlimited_retaliation"] ?: false,
            noMeleePenalty = bools["no_melee_penalty"] ?: false,
            noRangePenalty = bools["no_range_penalty"] ?: false,
            strikesTwice = bools["strikes_twice"] ?: false, shootsTwice = bools["shoots_twice"] ?: false,
            noMorale = bools["no_morale"] ?: false,
            hates = hates.map { it as String },
        )
    }

    /** One stack of a side; `internal` because `h3.sim.encounter` builds its battles through [createBattle]. */
    internal class Setup(val creature: BattleCreature, val count: Int, val morale: Int, val luck: Int, val pos: Pair<Int, Int>?)

    private fun stack(v: Any?, creatures: Map<String, BattleCreature>, path: String): Setup {
        val o = obj(v, path)
        checkKeys(o, path, STACK_KEYS)
        if ("creature" !in o || "count" !in o) throw ScenarioError("$path: needs 'creature' and 'count'")
        val name = o["creature"]
        if (name !is String || name !in creatures) {
            throw ScenarioError("$path.creature: unknown creature ${repr(name)}")
        }
        val pos = if (o["pos"] != null) pair(o["pos"], "$path.pos") else null
        val count = int(o["count"], "$path.count")
        val morale = if ("morale" in o) int(o["morale"], "$path.morale") else 0
        val luck = if ("luck" in o) int(o["luck"], "$path.luck") else 0
        return Setup(creatures.getValue(name), count, morale, luck, pos)
    }

    private fun side(v: Any?, creatures: Map<String, BattleCreature>, path: String): List<Setup> {
        if (v !is List<*> || v.size !in 1..7) throw ScenarioError("$path must be a list of 1 to 7 stacks")
        return v.mapIndexed { i, s -> stack(s, creatures, "$path[$i]") }
    }

    private fun hero(v: Any?, path: String): BattleHero {
        val o = obj(v, path)
        checkKeys(o, path, HERO_KEYS)
        val ints = LinkedHashMap<String, Int>()
        for ((k, x) in o) ints[k] = int(x, "$path.$k")
        return BattleHero(
            attack = ints["attack"] ?: 0, defense = ints["defense"] ?: 0, offense = ints["offense"] ?: 0,
            archery = ints["archery"] ?: 0, armorer = ints["armorer"] ?: 0,
        )
    }

    private fun policy(v: Any?, engine: BattleEngine): BattlePolicy {
        val o = obj(v, "scenario.policy")
        checkKeys(o, "scenario.policy", POLICY_INTS + POLICY_STRS + POLICY_BOOLS + POLICY_TUPLES)
        val overrides = LinkedHashMap<String, Any?>()
        for ((k, x) in o) {
            val p = "scenario.policy.$k"
            overrides[k] = when (k) {
                in POLICY_INTS -> int(x, p)
                in POLICY_STRS -> str(x, p)
                in POLICY_BOOLS -> bool(x, p)
                else -> tuple(x, p)
            }
        }
        try {
            return engine.policyPack.policy(overrides)
        } catch (e: IllegalArgumentException) {
            throw ScenarioError("scenario.policy: ${e.message}")
        }
    }

    private fun build(data: Any?, engine: BattleEngine): BattleState {
        val top = obj(data, "scenario")
        checkKeys(top, "scenario", TOP_KEYS)
        for (k in listOf("battle_id", "creatures", "attackers", "defenders")) {
            if (k !in top) throw ScenarioError("scenario: missing key ${PackJson.pyRepr(k)}")
        }
        val battleId = top["battle_id"]
        if (battleId !is String || battleId.isEmpty()) throw ScenarioError("scenario.battle_id must be a non-empty string")

        val creatures = LinkedHashMap<String, BattleCreature>()
        for ((name, o) in obj(top["creatures"], "scenario.creatures")) {
            if (name.isEmpty()) throw ScenarioError("scenario.creatures: creature names must be non-empty")
            val path = "scenario.creatures[${PackJson.pyRepr(name)}]"
            val c = creature(name, obj(o, path), path)
            creatures[name] = c
        }
        val attackers = side(top["attackers"], creatures, "scenario.attackers")
        val defenders = side(top["defenders"], creatures, "scenario.defenders")

        val rawObstacles = top["obstacles"] ?: if ("obstacles" in top) null else emptyList<Any?>()
        if (rawObstacles !is List<*>) throw ScenarioError("scenario.obstacles must be a list")
        val obstacles = rawObstacles.mapIndexed { i, o -> pair(o, "scenario.obstacles[$i]") }

        val rawHeroes: Any? = if ("heroes" in top) top["heroes"] else listOf(null, null)
        if (rawHeroes !is List<*> || rawHeroes.size != 2) {
            throw ScenarioError("scenario.heroes must be a list of two entries (null or hero object)")
        }
        val heroes = rawHeroes.mapIndexed { i, h -> if (h == null) null else hero(h, "scenario.heroes[$i]") }

        val policy = policy(if ("policy" in top) top["policy"] else emptyMap<String, Any?>(), engine)

        try {
            return createBattle(battleId, attackers, defenders, obstacles, heroes, policy, engine.rulesHash)
        } catch (e: ScenarioError) {
            throw e
        } catch (e: IllegalArgumentException) {
            throw ScenarioError("scenario: ${e.message}")
        }
    }

    // ------------------------------------------------------------ create_battle

    private fun tupleRepr(p: Pair<Int, Int>) = "(${p.first}, ${p.second})"

    /** Python `battle.create_battle`: the initial (not yet started) state. Shared with `h3.sim.encounter.EncounterEngine`. */
    internal fun createBattle(
        battleId: String, attackers: List<Setup>, defenders: List<Setup>,
        obstacles: List<Pair<Int, Int>>, heroes: List<BattleHero?>, policy: BattlePolicy, rulesHash: String,
    ): BattleState {
        require(attackers.size in 1..7 && defenders.size in 1..7) { "each side needs 1..7 stacks" }
        require(heroes.size == 2) { "heroes must be a pair" }
        val obs = obstacles.toSortedSet(compareBy<Pair<Int, Int>>({ it.first }, { it.second })).toList()
        for (o in obs) require(Hex.inGrid(HexCell(o.first, o.second))) { "obstacle off grid: ${tupleRepr(o)}" }
        val stacks = ArrayList<BattleStack>()
        val occupied = LinkedHashSet<HexCell>()
        for (o in obs) occupied.add(HexCell(o.first, o.second))
        for ((sd, army) in listOf(Hex.ATTACKER to attackers, Hex.DEFENDER to defenders)) {
            val rows = policy.placementRows[army.size - 1]
            for ((slot, s) in army.withIndex()) {
                val cr = s.creature
                require(s.count > 0 && cr.hp > 0 && cr.speed >= 0) { "invalid stack setup" }
                require(cr.dmgMin >= 1 && cr.dmgMin <= cr.dmgMax) { "invalid damage range" }
                val wide = if (cr.doubleWide) 1 else 0
                val head = s.pos ?: if (sd == Hex.ATTACKER) Pair(1 + wide, rows[slot]) else Pair(Hex.WIDTH - 2 - wide, rows[slot])
                val cells = Hex.cellsAt(HexCell(head.first, head.second), sd, cr.doubleWide)
                for (c in cells) {
                    require(Hex.playable(c, policy.edgeColumnsWalkable) && c !in occupied) {
                        "stack ${stacks.size} cannot be placed at ${tupleRepr(head)}"
                    }
                }
                occupied.addAll(cells)
                stacks.add(BattleStack(
                    id = stacks.size, side = sd, slot = slot, creature = cr, count = s.count, topHp = cr.hp,
                    pos = head, shots = cr.shots, retaliations = 1, defending = false, morale = s.morale, luck = s.luck,
                ))
            }
        }
        val state = BattleState(
            battleId = battleId, policy = policy, heroes = heroes, obstacles = obs, stacks = stacks,
            rulesHash = rulesHash,
        )
        BattleCodec.checkState(state)
        return state
    }
}

/**
 * A strict JSON reader with the behaviour `replay.py` relies on from Python's `json`: integers are
 * [BigInteger], duplicate keys keep the last value, only ` \t\n\r` is whitespace, control characters in
 * strings are errors. Errors: [Syntax] (`extraData` true when a complete value is followed by more text,
 * Python's "Extra data") and [Rejected] (a float or NaN/Infinity met in `rejectFloats` mode, in file order).
 * With `rejectFloats` false a number with a fraction or exponent becomes a [JsonFraction] marker.
 */
internal object ScenarioJson {
    class Syntax(val extraData: Boolean, message: String) : Exception(message)
    class Rejected(message: String) : Exception(message)

    /** A number literal with a fraction or exponent; never an integer. */
    class JsonFraction(val text: String)

    fun parse(text: String, rejectFloats: Boolean): Any? {
        val p = P(text, rejectFloats)
        try {
            p.ws()
            val v = p.value()
            p.ws()
            if (p.i != text.length) throw Syntax(true, "Extra data at ${p.i}")
            return v
        } catch (e: StackOverflowError) {
            throw Rejected("nesting too deep")
        }
    }

    private class P(val s: String, val reject: Boolean) {
        var i = 0

        fun bad(msg: String): Nothing = throw Syntax(false, "$msg at $i")

        fun ws() {
            while (i < s.length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) i++
        }

        fun value(): Any? {
            if (i >= s.length) bad("Expecting value")
            return when (s[i]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> lit("true", true)
                'f' -> lit("false", false)
                'n' -> lit("null", null)
                'N' -> { lit("NaN", null); throw Rejected("non-finite number") }
                'I' -> { lit("Infinity", null); throw Rejected("non-finite number") }
                else -> {
                    if (s.startsWith("-Infinity", i)) throw Rejected("non-finite number")
                    num()
                }
            }
        }

        fun lit(word: String, v: Any?): Any? {
            if (!s.startsWith(word, i)) bad("Expecting value")
            i += word.length
            return v
        }

        fun digit(k: Int) = k < s.length && s[k] in '0'..'9'

        fun num(): Any? {
            val st = i
            if (i < s.length && s[i] == '-') i++
            if (!digit(i)) { i = st; bad("Expecting value") }
            if (s[i] == '0') i++ else while (digit(i)) i++
            val intEnd = i
            var frac = false
            if (i < s.length && s[i] == '.' && digit(i + 1)) {
                i++
                while (digit(i)) i++
                frac = true
            }
            if (i < s.length && (s[i] == 'e' || s[i] == 'E')) {
                var k = i + 1
                if (k < s.length && (s[k] == '+' || s[k] == '-')) k++
                if (digit(k)) {
                    while (digit(k)) k++
                    i = k
                    frac = true
                }
            }
            if (frac) {
                if (reject) throw Rejected("floats are not allowed")
                return JsonFraction(s.substring(st, i))
            }
            i = intEnd
            return BigInteger(s.substring(st, intEnd))
        }

        fun str(): String {
            i++
            val sb = StringBuilder()
            while (true) {
                if (i >= s.length) bad("Unterminated string")
                val c = s[i++]
                when {
                    c == '"' -> return sb.toString()
                    c < ' ' -> bad("Invalid control character")
                    c == '\\' -> {
                        if (i >= s.length) bad("Unterminated string")
                        when (s[i++]) {
                            '"' -> sb.append('"')
                            '\\' -> sb.append('\\')
                            '/' -> sb.append('/')
                            'b' -> sb.append('\b')
                            'f' -> sb.append('\u000c')
                            'n' -> sb.append('\n')
                            'r' -> sb.append('\r')
                            't' -> sb.append('\t')
                            'u' -> {
                                if (i + 4 > s.length) bad("Invalid \\uXXXX escape")
                                val h = s.substring(i, i + 4)
                                if (!h.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' }) bad("Invalid \\uXXXX escape")
                                sb.append(h.toInt(16).toChar())
                                i += 4
                            }
                            else -> bad("Invalid \\escape")
                        }
                    }
                    else -> sb.append(c)
                }
            }
        }

        fun obj(): Map<String, Any?> {
            val m = LinkedHashMap<String, Any?>()
            i++
            ws()
            if (i < s.length && s[i] == '}') { i++; return m }
            while (true) {
                if (i >= s.length || s[i] != '"') bad("Expecting property name enclosed in double quotes")
                val k = str()
                ws()
                if (i >= s.length || s[i] != ':') bad("Expecting ':' delimiter")
                i++
                ws()
                m[k] = value()
                ws()
                if (i >= s.length) bad("Expecting ',' delimiter")
                when (s[i++]) {
                    '}' -> return m
                    ',' -> ws()
                    else -> { i--; bad("Expecting ',' delimiter") }
                }
            }
        }

        fun arr(): List<Any?> {
            val l = ArrayList<Any?>()
            i++
            ws()
            if (i < s.length && s[i] == ']') { i++; return l }
            while (true) {
                l.add(value())
                ws()
                if (i >= s.length) bad("Expecting ',' delimiter")
                when (s[i++]) {
                    ']' -> return l
                    ',' -> ws()
                    else -> { i--; bad("Expecting ',' delimiter") }
                }
            }
        }
    }
}
