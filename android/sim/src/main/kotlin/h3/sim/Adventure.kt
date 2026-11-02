package h3.sim

import java.math.BigInteger
import java.util.PriorityQueue

/**
 * Adventure-map core: movement and economy. A port of `tools/h3re/h3re/adventure.py`
 * (docs/specs/adventure.md), conformance-tested against `adventure.json`
 * (docs/specs/conformance-adventure.md). Python is authoritative (ADR-0004, ADR-0007).
 *
 * Same design as [Battle]: the state is immutable, `apply(state, cmd, rng)` is the only way to
 * advance it, an illegal command throws [IllegalCommand] before anything changes. Nothing here is
 * random: the `adventure:<game_id>` stream is accepted and never drawn from. Integer only
 * (`Int`/`Long` with `Math.*Exact`); every rounding is [AdventurePolicy.div] in the mode the policy names.
 *
 * The content-free tables (terrain costs, roads, speed to movement points, Logistics, mine output)
 * are not in this file: they are handed in as [AdventureRules], read from the same values the
 * Python module holds (the vector file's `constants` block).
 *
 * Encounters (encounter.md, stage E): `Attack` and the state's `encounter` setup are handled through
 * [AdventureEncounterHooks], an interface this file defines and `h3.sim.encounter.EncounterEngine`
 * implements, so the dependency runs one way only (encounter -> adventure; Python imports lazily the other
 * way). Without hooks a state carrying `encounter` is refused by [AdventureCodec.parseState] and an `Attack`
 * on a state without an encounter setup is "battles are not enabled in this game". Guards block tiles.
 */

data class AdvResources(
    val gold: Long = 0, val wood: Long = 0, val ore: Long = 0, val mercury: Long = 0,
    val sulfur: Long = 0, val crystal: Long = 0, val gems: Long = 0,
) {
    operator fun plus(o: AdvResources) = AdvResources(
        Math.addExact(gold, o.gold), Math.addExact(wood, o.wood), Math.addExact(ore, o.ore),
        Math.addExact(mercury, o.mercury), Math.addExact(sulfur, o.sulfur),
        Math.addExact(crystal, o.crystal), Math.addExact(gems, o.gems),
    )

    fun toMap(): Map<String, Any?> = linkedMapOf(
        "gold" to gold, "wood" to wood, "ore" to ore, "mercury" to mercury,
        "sulfur" to sulfur, "crystal" to crystal, "gems" to gems,
    )

    companion object {
        val KEYS = setOf("gold", "wood", "ore", "mercury", "sulfur", "crystal", "gems")
        fun from(v: Any?, what: String): AdvResources {
            val m = BattleJson.obj(v, what)
            BattleJson.exactKeys(m, KEYS, what)
            fun l(k: String) = BattleJson.long(m[k], "$what.$k")
            return AdvResources(l("gold"), l("wood"), l("ore"), l("mercury"), l("sulfur"), l("crystal"), l("gems"))
        }
    }
}

/** The content-free constants of `adventure.py` (rules.md 2-3). */
data class AdventureRules(
    val terrainCost: Map<String, Int>,
    val impassable: List<String>,
    val roads: List<String>,
    val speedMp: List<Int>,
    val logisticsPct: List<Int>,
    val mineOutput: Map<String, AdvResources>,
) {
    init {
        require(roads.isNotEmpty() && roads[0] == "none") { "roads: first entry must be none" }
        require(speedMp.isNotEmpty() && logisticsPct.size == 4) { "bad movement tables" }
    }

    companion object {
        fun from(v: Any?): AdventureRules {
            val m = BattleJson.obj(v, "constants")
            val tc = LinkedHashMap<String, Int>()
            for ((k, c) in BattleJson.obj(m["terrain_cost"], "terrain_cost").entries.sortedBy { it.key }) {
                tc[k] = BattleJson.int(c, "terrain_cost")
            }
            val mo = LinkedHashMap<String, AdvResources>()
            for ((k, r) in BattleJson.obj(m["mine_output"], "mine_output").entries.sortedBy { it.key }) {
                mo[k] = AdvResources.from(r, "mine_output")
            }
            return AdventureRules(
                terrainCost = tc,
                impassable = BattleJson.list(m["impassable"], "impassable").map { BattleJson.str(it, "impassable") },
                roads = BattleJson.list(m["roads"], "roads").map { BattleJson.str(it, "roads") },
                speedMp = BattleJson.ints(m["speed_mp"], "speed_mp"),
                logisticsPct = BattleJson.ints(m["logistics_pct"], "logistics_pct"),
                mineOutput = mo,
            )
        }
    }
}

/** Python `AdventurePolicy`; [roadCost] is sorted by road name (canonical form). */
data class AdventurePolicy(
    val roadCost: List<Pair<String, Int>>,
    val roadNeedsBoth: Boolean,
    val roadRateFrom: String,
    val costFrom: String,
    val diagonalMoves: Boolean,
    val diagonalMode: String,
    val diagonalNum: Int,
    val diagonalDen: Int,
    val diagonalRounding: String,
    val diagonalCornerCut: Boolean,
    val lastStep: String,
    val diagonalException: Boolean,
    val zeroRemainder: Boolean,
    val pathfindingMode: String,
    val pathfindingFlat: List<Int>,
    val moveCostFloor: Int,
    val pathfindingPct: List<Int>,
    val pathfindingRounding: String,
    val incomeOnFirstDay: Boolean,
) {
    /**
     * Python `__post_init__`, same order and messages. [roads] is the rules' road list. [illTyped]
     * names the fields that had the wrong type in the source JSON: an integer field that was a bool,
     * a float or not a number (Python requires `type(x) is int`), a flag that was not a bool
     * (`type(x) is bool`); the value kept for them is not looked at.
     */
    fun validate(roads: List<String>, illTyped: Set<String> = emptySet()) {
        for (name in FLAGS) require(name !in illTyped) { "$name must be a bool" }
        require(costFrom in setOf("dest", "source")) { "bad cost_from" }
        require(roadRateFrom in setOf("source", "dest", "max")) { "bad road_rate_from" }
        require(diagonalMode in setOf("sqrt2", "ratio")) { "bad diagonal_mode" }
        require(pathfindingMode in setOf("flat", "percent")) { "bad pathfinding_mode" }
        require(pathfindingFlat.size == 4 && "pathfinding_flat" !in illTyped && pathfindingFlat.all { it in 0..POLICY_INT_MAX }) {
            "pathfinding_flat needs 4 ints in 0..$POLICY_INT_MAX"
        }
        require("move_cost_floor" !in illTyped && moveCostFloor in 1..POLICY_INT_MAX) { "move_cost_floor needs an int in 1..$POLICY_INT_MAX" }
        require(lastStep in setOf("forbid", "allow_if_any", "allow_if_fresh")) { "bad last_step" }
        for (r in listOf(diagonalRounding, pathfindingRounding)) require(r in ROUNDING) { "bad rounding mode '$r'" }
        require("diagonal_den" !in illTyped && "diagonal_num" !in illTyped && diagonalDen in 1..POLICY_INT_MAX && diagonalNum in 1..POLICY_INT_MAX) {
            "diagonal_num and diagonal_den need ints in 1..$POLICY_INT_MAX"
        }
        require(pathfindingPct.size == 4 && "pathfinding_pct" !in illTyped && pathfindingPct.all { it in 0..100 }) { "pathfinding_pct needs 4 values in 0..100" }
        val names = roadCost.map { it.first }
        require(names.toSet().size == names.size) { "road_cost has a duplicate road type" }
        require(names == roads.drop(1).sortedWith(Canonical.codePointOrder) && "road_cost" !in illTyped && roadCost.all { it.second in 1..POLICY_INT_MAX }) {
            "road_cost needs a cost in 1..$POLICY_INT_MAX for each road type"
        }
    }

    companion object {
        val ROUNDING = listOf("floor", "ceil", "nearest")

        /** Python `_POLICY_FLAGS`, in field order: checked first by [validate]. */
        val FLAGS = listOf(
            "road_needs_both", "diagonal_moves", "diagonal_corner_cut",
            "diagonal_exception", "zero_remainder", "income_on_first_day",
        )

        /** Python `POLICY_INT_MAX`: keeps every step cost and budgeted sum inside Int (ADR-0008, adventure.md 6). */
        const val POLICY_INT_MAX = 10_000

        /** Python `_div`. */
        fun div(n: Long, d: Long, mode: String): Long = when (mode) {
            "floor" -> Math.floorDiv(n, d)
            "ceil" -> Math.negateExact(Math.floorDiv(Math.negateExact(n), d))
            else -> Math.floorDiv(Math.addExact(Math.multiplyExact(2L, n), d), Math.multiplyExact(2L, d))
        }
    }
}

data class AdvTile(val terrain: String, val road: String = "none", val blocked: Boolean = false)

data class AdvGrid(val width: Int, val height: Int, val tiles: List<AdvTile>) {
    fun tile(p: Pair<Int, Int>): AdvTile = tiles[p.second * width + p.first]
    fun inside(p: Pair<Int, Int>): Boolean = p.first in 0 until width && p.second in 0 until height
}

data class AdvArmySlot(val creature: String, val speed: Int, val count: Int)

data class AdvHero(
    val id: Int,
    val owner: Int,
    val pos: Pair<Int, Int>?,
    val army: List<AdvArmySlot>,
    val logistics: Int,
    val pathfinding: Int,
    val mp: Int,
    val mpMax: Int,
    val movedToday: Boolean,
)

data class AdvPlayer(
    val resources: AdvResources = AdvResources(),
    val mines: List<String> = emptyList(),
    val extraIncome: AdvResources = AdvResources(),
)

data class AdvGrowthPool(val id: String, val available: Long, val growth: Long)

data class AdvGuard(val id: String, val pos: Pair<Int, Int>, val army: List<AdvArmySlot>)

/** The state's `encounter` field (Python `encounter.EncounterSetup`), opaque to this file: only its canonical map is needed. */
interface AdvEncounter {
    fun toMap(): Map<String, Any?>
}

/**
 * What the adventure core needs from the encounter module (Python's lazy `encounter.validate`,
 * `encounter.resolve`, `encounter.check_game`). Implemented in `h3.sim.encounter`.
 */
interface AdventureEncounterHooks {
    /** The `encounter` entry of a canonical state; [IllegalArgumentException] (Python `ValueError`) when malformed. */
    fun parseSetup(v: Any?): AdvEncounter

    /** Python `check_game`: [IllegalArgumentException] unless every army on the map has content in the setup. */
    fun checkGame(state: AdventureState)

    /** Python `encounter.validate`: every check of an Attack, no draw. Returns what [resolve] needs (the initial battle). */
    fun validate(state: AdventureState, cmd: AdventureCommand.Attack): Any

    /** Python `encounter.resolve`: fight on [rng] (the `battle:<battle_id>` stream) and apply the outcome. */
    fun resolve(state: AdventureState, cmd: AdventureCommand.Attack, rng: Pcg32?, prepared: Any): AdventureStep
}

data class AdventureState(
    val gameId: String,
    val policy: AdventurePolicy,
    val grid: AdvGrid,
    val players: List<AdvPlayer>,
    val heroes: List<AdvHero>,
    val pools: List<AdvGrowthPool>,
    val day: Long = 0,
    val current: Int = 0,
    val guards: List<AdvGuard> = emptyList(),
    val battles: Int = 0,
    val encounter: AdvEncounter? = null,
)

/**
 * Commands. A field that was not a well-typed integer (a bool, a string, a float, a list that is
 * not an `(x, y)` pair of integers) is `null`, with its Python `repr` kept for the message, so
 * [Adventure] rejects it at the same point and with the same text as Python's `_validate`.
 */
sealed interface AdventureCommand {
    data object Begin : AdventureCommand
    data class Move(val hero: Int?, val dest: Pair<Int, Int>?, val destRepr: String = "") : AdventureCommand {
        constructor(hero: Int, dest: Pair<Int, Int>) : this(hero as Int?, dest as Pair<Int, Int>?, "")
    }
    data class EndTurn(val player: Int?, val playerRepr: String) : AdventureCommand {
        constructor(player: Int) : this(player, player.toString())
    }

    /**
     * Python `Attack(hero, target)`. [target] is a hero id ([Int]), a guard id ([String]) or `null` for anything
     * else (bool, float, list, ...), which Python refuses as "target must be a hero id or a guard id"; an integer
     * beyond the Int range is carried as -1 (no such target hero, as in Python). [hero] null is "no such hero".
     */
    data class Attack(val hero: Int?, val target: Any?) : AdventureCommand
}

/** Not sealed: `h3.sim.encounter` adds `BattleFought`, `ArmyChanged`, `HeroDefeated` and `GuardDefeated`. */
interface AdventureEvent {
    fun toMap(): Map<String, Any?>

    data class DayStarted(val day: Long, val week: Long, val dayOfWeek: Int, val month: Long) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>("type" to "DayStarted", "day" to day, "week" to week, "day_of_week" to dayOfWeek, "month" to month)
    }
    data class WeekStarted(val week: Long, val month: Long, val newMonth: Boolean) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>("type" to "WeekStarted", "week" to week, "month" to month, "new_month" to newMonth)
    }
    data class PoolGrew(val pool: String, val added: Long, val available: Long) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>("type" to "PoolGrew", "pool" to pool, "added" to added, "available" to available)
    }
    data class TurnStarted(val player: Int, val day: Long) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>("type" to "TurnStarted", "player" to player, "day" to day)
    }
    data class IncomeReceived(val player: Int, val income: AdvResources) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>("type" to "IncomeReceived", "player" to player, "income" to income.toMap())
    }
    data class MovementReset(val hero: Int, val mp: Int) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>("type" to "MovementReset", "hero" to hero, "mp" to mp)
    }
    data class HeroMoved(val hero: Int, val path: List<Pair<Int, Int>>, val cost: Int, val mpLeft: Int) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>(
            "type" to "HeroMoved", "hero" to hero, "path" to path.map { listOf(it.first, it.second) }, "cost" to cost, "mp_left" to mpLeft,
        )
    }
    data class TurnEnded(val player: Int) : AdventureEvent {
        override fun toMap() = linkedMapOf<String, Any?>("type" to "TurnEnded", "player" to player)
    }
}

/** Canonical form of [AdventureState]: byte-identical to Python `adventure.canonical` (ADR-0001, ADR-0005). */
class AdventureCodec(private val rules: AdventureRules, private val encounters: AdventureEncounterHooks? = null) {
    fun toMap(s: AdventureState): Map<String, Any?> {
        val m = linkedMapOf<String, Any?>(
            "game_id" to s.gameId,
            "policy" to policyToMap(s.policy),
            "grid" to linkedMapOf<String, Any?>(
                "width" to s.grid.width, "height" to s.grid.height,
                "tiles" to s.grid.tiles.map { linkedMapOf<String, Any?>("terrain" to it.terrain, "road" to it.road, "blocked" to it.blocked) },
            ),
            "players" to s.players.map {
                linkedMapOf<String, Any?>("resources" to it.resources.toMap(), "mines" to it.mines, "extra_income" to it.extraIncome.toMap())
            },
            "heroes" to s.heroes.map {
                linkedMapOf<String, Any?>(
                    "id" to it.id, "owner" to it.owner, "pos" to it.pos?.let { p -> listOf(p.first, p.second) },
                    "army" to it.army.map(::slotToMap), "logistics" to it.logistics, "pathfinding" to it.pathfinding,
                    "mp" to it.mp, "mp_max" to it.mpMax, "moved_today" to it.movedToday,
                )
            },
            "pools" to s.pools.map { linkedMapOf<String, Any?>("id" to it.id, "available" to it.available, "growth" to it.growth) },
            "day" to s.day,
            "current" to s.current,
        )
        // Omitted while at their default (Python _OMIT_WHEN_DEFAULT), so the golden hash holds.
        if (s.guards.isNotEmpty()) {
            m["guards"] = s.guards.map {
                linkedMapOf<String, Any?>("id" to it.id, "pos" to listOf(it.pos.first, it.pos.second), "army" to it.army.map(::slotToMap))
            }
        }
        if (s.battles != 0) m["battles"] = s.battles
        if (s.encounter != null) m["encounter"] = s.encounter.toMap()
        return m
    }

    fun canonicalText(s: AdventureState): String = Canonical.encode(toMap(s)).toString(Charsets.US_ASCII)

    fun stateHash(s: AdventureState): String = Canonical.hash(toMap(s))

    /** [checkEncounter] false skips Python `check_game` (hand-built states whose armies lack content). */
    fun parseState(v: Any?, checkEncounter: Boolean = true): AdventureState {
        val m = BattleJson.obj(v, "state")
        val optional = setOf("guards", "encounter", "battles")
        require(m.keys.containsAll(STATE_KEYS) && (m.keys - STATE_KEYS).all { it in optional }) {
            "state: keys differ; missing ${STATE_KEYS - m.keys}, unexpected ${m.keys - STATE_KEYS - optional}"
        }
        require("encounter" !in m || encounters != null) { "state: encounters are not ported (encounter.md)" }
        val encounter = if ("encounter" in m) encounters!!.parseSetup(m["encounter"]) else null
        val policy = policyFrom(BattleJson.obj(m["policy"], "policy"))
        val gm = BattleJson.obj(m["grid"], "grid")
        BattleJson.exactKeys(gm, setOf("width", "height", "tiles"), "grid")
        val tiles = BattleJson.list(gm["tiles"], "tiles").map {
            val t = BattleJson.obj(it, "tile")
            BattleJson.exactKeys(t, setOf("terrain", "road", "blocked"), "tile")
            AdvTile(BattleJson.str(t["terrain"], "terrain"), BattleJson.str(t["road"], "road"), BattleJson.bool(t["blocked"], "blocked"))
        }
        val grid = AdvGrid(BattleJson.int(gm["width"], "width"), BattleJson.int(gm["height"], "height"), tiles)
        require(grid.width > 0 && grid.height > 0 && tiles.size.toLong() == grid.width.toLong() * grid.height) { "grid size mismatch" }
        for (t in tiles) {
            require(t.terrain in rules.terrainCost || t.terrain in rules.impassable) { "unknown terrain '${t.terrain}'" }
            require(t.road in rules.roads) { "unknown road '${t.road}'" }
        }
        val players = BattleJson.list(m["players"], "players").map {
            val p = BattleJson.obj(it, "player")
            BattleJson.exactKeys(p, setOf("resources", "mines", "extra_income"), "player")
            val mines = BattleJson.list(p["mines"], "mines").map { x -> BattleJson.str(x, "mine") }
            for (x in mines) require(x in rules.mineOutput) { "unknown mine '$x'" }
            AdvPlayer(AdvResources.from(p["resources"], "resources"), mines, AdvResources.from(p["extra_income"], "extra_income"))
        }
        require(players.isNotEmpty()) { "need at least one player" }
        val heroes = BattleJson.list(m["heroes"], "heroes").mapIndexed { i, it ->
            val h = BattleJson.obj(it, "hero")
            BattleJson.exactKeys(h, HERO_KEYS, "hero")
            val hero = AdvHero(
                id = BattleJson.int(h["id"], "id"), owner = BattleJson.int(h["owner"], "owner"),
                pos = BattleJson.posOrNull(h["pos"], "pos"),
                army = BattleJson.list(h["army"], "army").map(::slotFrom),
                logistics = BattleJson.int(h["logistics"], "logistics"), pathfinding = BattleJson.int(h["pathfinding"], "pathfinding"),
                mp = BattleJson.int(h["mp"], "mp"), mpMax = BattleJson.int(h["mp_max"], "mp_max"),
                movedToday = BattleJson.bool(h["moved_today"], "moved_today"),
            )
            require(hero.id == i) { "hero $i: id must equal its index" }
            require(hero.owner in players.indices) { "hero $i: no such owner" }
            require(hero.logistics in 0..3 && hero.pathfinding in 0..3) { "hero $i: skill level out of range" }
            require(hero.mp >= 0 && hero.mpMax >= 0) { "hero $i: negative movement points" }
            if (hero.pos != null) {
                checkArmy(hero.army, "hero $i")
                require(passable(grid, hero.pos)) { "hero $i cannot stand at ${hero.pos}" }
            }
            hero
        }
        val pools = BattleJson.list(m["pools"], "pools").map {
            val p = BattleJson.obj(it, "pool")
            BattleJson.exactKeys(p, setOf("id", "available", "growth"), "pool")
            AdvGrowthPool(BattleJson.str(p["id"], "id"), BattleJson.long(p["available"], "available"), BattleJson.long(p["growth"], "growth"))
        }
        require(pools.map { it.id }.toSet().size == pools.size && pools.all { it.available >= 0 && it.growth >= 0 }) { "bad growth pools" }
        val guards = if ("guards" in m) BattleJson.list(m["guards"], "guards").map {
            val g = BattleJson.obj(it, "guard")
            BattleJson.exactKeys(g, setOf("id", "pos", "army"), "guard")
            val guard = AdvGuard(BattleJson.str(g["id"], "id"), BattleJson.pos(g["pos"], "pos"), BattleJson.list(g["army"], "army").map(::slotFrom))
            checkArmy(guard.army, "guard '${guard.id}'")
            require(passable(grid, guard.pos)) { "guard '${guard.id}' cannot stand at ${guard.pos}" }
            guard
        } else emptyList()
        // Python sorts ids by code point; String.sorted() is UTF-16 code-unit order (differs for astral ids).
        val guardIds = guards.map { it.id }
        require(guardIds == guardIds.sortedWith(Canonical.codePointOrder) && guardIds.toSet().size == guards.size) { "guards must be sorted by unique id" }
        val day = BattleJson.long(m["day"], "day")
        val current = BattleJson.int(m["current"], "current")
        require(day >= 0 && current in players.indices) { "bad day or current player" }
        val battles = if ("battles" in m) BattleJson.int(m["battles"], "battles") else 0
        val occupied = (heroes.mapNotNull { it.pos } + guards.map { it.pos })
        require(occupied.toSet().size == occupied.size) { "two pieces on one tile" }
        val state = AdventureState(BattleJson.str(m["game_id"], "game_id"), policy, grid, players, heroes, pools, day, current, guards, battles, encounter)
        if (encounter != null && checkEncounter) encounters!!.checkGame(state)
        return state
    }

    fun policyToMap(p: AdventurePolicy): Map<String, Any?> = linkedMapOf(
        "road_cost" to p.roadCost.map { listOf(it.first, it.second) },
        "road_needs_both" to p.roadNeedsBoth, "road_rate_from" to p.roadRateFrom, "cost_from" to p.costFrom,
        "diagonal_moves" to p.diagonalMoves, "diagonal_mode" to p.diagonalMode, "diagonal_num" to p.diagonalNum,
        "diagonal_den" to p.diagonalDen, "diagonal_rounding" to p.diagonalRounding,
        "diagonal_corner_cut" to p.diagonalCornerCut, "last_step" to p.lastStep,
        "diagonal_exception" to p.diagonalException, "zero_remainder" to p.zeroRemainder,
        "pathfinding_mode" to p.pathfindingMode, "pathfinding_flat" to p.pathfindingFlat,
        "move_cost_floor" to p.moveCostFloor, "pathfinding_pct" to p.pathfindingPct,
        "pathfinding_rounding" to p.pathfindingRounding, "income_on_first_day" to p.incomeOnFirstDay,
    )

    fun policyFrom(m: Map<String, Any?>): AdventurePolicy {
        BattleJson.exactKeys(m, POLICY_KEYS, "policy")
        // Python ints are unbounded and a policy integer must be a plain int: a bool, a float or
        // any other value is recorded in [illTyped], an integer beyond Int is clamped to the Int
        // range (every bound is far inside it, so the verdict and the message are Python's).
        // A flag must be a plain bool: anything else (0, 1, null, a string, a float) is recorded too.
        val illTyped = LinkedHashSet<String>()
        fun lenient(v: Any?, field: String): Int {
            val big = when (v) {
                is BigInteger -> v
                is Int -> BigInteger.valueOf(v.toLong())
                is Long -> BigInteger.valueOf(v)
                else -> { illTyped.add(field); return 0 }
            }
            return big.max(BigInteger.valueOf(Int.MIN_VALUE.toLong())).min(BigInteger.valueOf(Int.MAX_VALUE.toLong())).toInt()
        }
        fun lenientList(v: Any?, field: String): List<Int> = BattleJson.list(v, field).map { lenient(it, field) }
        val roads = BattleJson.list(m["road_cost"], "road_cost").map {
            val e = BattleJson.list(it, "road_cost")
            require(e.size == 2) { "road_cost entries must be (road, cost) pairs" }
            Pair(BattleJson.str(e[0], "road_cost"), lenient(e[1], "road_cost"))
        }.sortedWith { a, b -> Canonical.codePointOrder.compare(a.first, b.first) }
        fun b(k: String): Boolean {
            val v = m[k]
            if (v is Boolean) return v
            illTyped.add(k)
            return false
        }
        fun s(k: String) = BattleJson.str(m[k], k)
        fun i(k: String) = lenient(m[k], k)
        val p = AdventurePolicy(
            roadCost = roads, roadNeedsBoth = b("road_needs_both"), roadRateFrom = s("road_rate_from"),
            costFrom = s("cost_from"), diagonalMoves = b("diagonal_moves"), diagonalMode = s("diagonal_mode"),
            diagonalNum = i("diagonal_num"), diagonalDen = i("diagonal_den"), diagonalRounding = s("diagonal_rounding"),
            diagonalCornerCut = b("diagonal_corner_cut"), lastStep = s("last_step"),
            diagonalException = b("diagonal_exception"), zeroRemainder = b("zero_remainder"),
            pathfindingMode = s("pathfinding_mode"), pathfindingFlat = lenientList(m["pathfinding_flat"], "pathfinding_flat"),
            moveCostFloor = i("move_cost_floor"), pathfindingPct = lenientList(m["pathfinding_pct"], "pathfinding_pct"),
            pathfindingRounding = s("pathfinding_rounding"), incomeOnFirstDay = b("income_on_first_day"),
        )
        p.validate(rules.roads, illTyped)
        return p
    }

    private fun passable(g: AdvGrid, p: Pair<Int, Int>): Boolean =
        g.inside(p) && !g.tile(p).blocked && g.tile(p).terrain !in rules.impassable

    private fun checkArmy(army: List<AdvArmySlot>, what: String) {
        require(army.size in 1..7 && army.all { it.count > 0 && it.speed >= 0 }) { "$what: invalid army" }
    }

    private fun slotToMap(s: AdvArmySlot): Map<String, Any?> = linkedMapOf("creature" to s.creature, "speed" to s.speed, "count" to s.count)

    private fun slotFrom(v: Any?): AdvArmySlot {
        val m = BattleJson.obj(v, "army slot")
        BattleJson.exactKeys(m, setOf("creature", "speed", "count"), "army slot")
        return AdvArmySlot(BattleJson.str(m["creature"], "creature"), BattleJson.int(m["speed"], "speed"), BattleJson.int(m["count"], "count"))
    }

    companion object {
        val STATE_KEYS = setOf("game_id", "policy", "grid", "players", "heroes", "pools", "day", "current")
        val HERO_KEYS = setOf("id", "owner", "pos", "army", "logistics", "pathfinding", "mp", "mp_max", "moved_today")
        val POLICY_KEYS = setOf(
            "road_cost", "road_needs_both", "road_rate_from", "cost_from", "diagonal_moves", "diagonal_mode",
            "diagonal_num", "diagonal_den", "diagonal_rounding", "diagonal_corner_cut", "last_step",
            "diagonal_exception", "zero_remainder", "pathfinding_mode", "pathfinding_flat", "move_cost_floor",
            "pathfinding_pct", "pathfinding_rounding", "income_on_first_day",
        )

        fun commandToMap(c: AdventureCommand): Map<String, Any?> = when (c) {
            AdventureCommand.Begin -> linkedMapOf("type" to "Begin")
            is AdventureCommand.Move -> linkedMapOf("type" to "Move", "hero" to c.hero, "dest" to c.dest?.let { listOf(it.first, it.second) })
            is AdventureCommand.EndTurn -> linkedMapOf("type" to "EndTurn", "player" to c.player)
            is AdventureCommand.Attack -> linkedMapOf("type" to "Attack", "hero" to c.hero, "target" to c.target)
        }

        /**
         * A command from its JSON form (`soak.encode_command`). Ill-typed fields become `null` (see
         * [AdventureCommand]); an integer outside the Int range is an unknown hero, an unknown player
         * or a tile off the map, as it is in Python. A missing field or unknown type is an
         * [IllegalArgumentException] (Python raises TypeError/AttributeError there, not IllegalCommand).
         */
        fun parseCommand(v: Any?): AdventureCommand {
            val m = BattleJson.obj(v, "command")
            return when (val t = m["type"]) {
                "Begin" -> { BattleJson.exactKeys(m, setOf("type"), "Begin"); AdventureCommand.Begin }
                "Move" -> {
                    BattleJson.exactKeys(m, setOf("type", "hero", "dest"), "Move")
                    val d = m["dest"]
                    val dest = if (d is List<*> && d.size == 2 && d.all(::isInteger)) Pair(intOr(d[0], -1)!!, intOr(d[1], -1)!!) else null
                    AdventureCommand.Move(intOr(m["hero"], null), dest, pyRepr(d, true))
                }
                "EndTurn" -> {
                    BattleJson.exactKeys(m, setOf("type", "player"), "EndTurn")
                    AdventureCommand.EndTurn(intOr(m["player"], null), pyRepr(m["player"], true))
                }
                "Attack" -> {
                    BattleJson.exactKeys(m, setOf("type", "hero", "target"), "Attack")
                    val t = m["target"]
                    val target: Any? = if (t is String) t else if (isInteger(t)) intOr(t, -1) else null
                    AdventureCommand.Attack(intOr(m["hero"], null), target)
                }
                else -> throw IllegalArgumentException("unknown command type: $t")
            }
        }

        private fun isInteger(v: Any?) = v is BigInteger || v is Int || v is Long

        /** An integer field as Int; [outOfRange] when it is an integer beyond Int; null when it is not an integer. */
        private fun intOr(v: Any?, outOfRange: Int?): Int? {
            if (!isInteger(v)) return null
            val b = when (v) { is BigInteger -> v; is Long -> BigInteger.valueOf(v); else -> BigInteger.valueOf((v as Int).toLong()) }
            return if (b.bitLength() < 32) b.toInt() else outOfRange
        }

        /**
         * Python `repr` of a str: single quotes unless the text has a `'` and no `"`; `\\`, the quote,
         * `\t \n \r` escaped; other C0 controls, DEL and every non-printable code point as `\xNN`,
         * `\uNNNN` or `\UNNNNNNNN`. Printable means Python's `str.isprintable`: not Unicode category
         * Cc, Cf, Cs, Co, Cn, Zl, Zp or Zs (except the ASCII space). Cn depends on the Unicode version:
         * checked equal to Python 3.13 (Unicode 15.1) for every code point on JDK 21 (15.0) with the patch below;
         * a Python on a newer Unicode (3.14: 16.0) can differ for the newest assignments.
         */
        private fun strRepr(v: String): String {
            val quote = if ('\'' in v && '"' !in v) '"' else '\''
            val sb = StringBuilder().append(quote)
            var i = 0
            while (i < v.length) {
                val cp = v.codePointAt(i)
                i += Character.charCount(cp)
                when {
                    cp == quote.code || cp == '\\'.code -> sb.append('\\').appendCodePoint(cp)
                    cp == '\t'.code -> sb.append("\\t")
                    cp == '\n'.code -> sb.append("\\n")
                    cp == '\r'.code -> sb.append("\\r")
                    cp < 0x20 || cp == 0x7f -> sb.append("\\x").append(hex(cp, 2))
                    cp < 0x7f -> sb.appendCodePoint(cp)
                    isPrintable(cp) -> sb.appendCodePoint(cp)
                    cp <= 0xff -> sb.append("\\x").append(hex(cp, 2))
                    cp <= 0xffff -> sb.append("\\u").append(hex(cp, 4))
                    else -> sb.append("\\U").append(hex(cp, 8))
                }
            }
            return sb.append(quote).toString()
        }

        private fun hex(cp: Int, width: Int): String = Integer.toHexString(cp).padStart(width, '0')

        /** Assigned in Unicode 15.1 (Python 3.13); a JDK on Unicode 15.0 (JDK 21) still calls them unassigned. */
        private fun isUnicode151Addition(cp: Int) = cp in 0x2ffc..0x2fff || cp == 0x31ef || cp in 0x2ebf0..0x2ee5d

        private fun isPrintable(cp: Int): Boolean = if (isUnicode151Addition(cp)) true else when (Character.getType(cp).toByte()) {
            Character.CONTROL, Character.FORMAT, Character.SURROGATE, Character.PRIVATE_USE, Character.UNASSIGNED,
            Character.LINE_SEPARATOR, Character.PARAGRAPH_SEPARATOR, Character.SPACE_SEPARATOR -> false
            else -> true
        }

        /** Python `repr` of a decoded command value (`soak.decode_command` turns a top-level list into a tuple). */
        fun pyRepr(v: Any?, top: Boolean = false): String = when (v) {
            null -> "None"
            is Boolean -> if (v) "True" else "False"
            is BigInteger, is Int, is Long -> v.toString()
            is String -> strRepr(v)
            is Map<*, *> -> v.entries.joinToString(", ", "{", "}") { (k, x) -> pyRepr(k) + ": " + pyRepr(x) }
            is List<*> -> {
                val inner = v.joinToString(", ") { pyRepr(it) }
                if (top) (if (v.size == 1) "($inner,)" else "($inner)") else "[$inner]"
            }
            else -> v.toString()
        }
    }
}

/** One step's result. */
data class AdventureStep(val state: AdventureState, val events: List<AdventureEvent>)

class Adventure(private val rules: AdventureRules, private val encounters: AdventureEncounterHooks? = null) {
    private data class Parts(val cost: Int, val orth: Int, val diagonal: Boolean)

    private class Label(val spent: Long, val steps: Int, val path: List<Pair<Int, Int>>) : Comparable<Label> {
        override fun compareTo(other: Label): Int {
            if (spent != other.spent) return spent.compareTo(other.spent)
            if (steps != other.steps) return steps.compareTo(other.steps)
            val n = minOf(path.size, other.path.size)
            for (k in 0 until n) {
                val a = path[k]
                val b = other.path[k]
                if (a.first != b.first) return a.first.compareTo(b.first)
                if (a.second != b.second) return a.second.compareTo(b.second)
            }
            return path.size.compareTo(other.path.size)
        }
    }

    /** Python `calendar`: (week, day_of_week, month) for day >= 1. The day is a Long (Python's is unbounded), so week and month are too. */
    fun calendar(day: Long): Triple<Long, Int, Long> = Triple((day - 1) / 7 + 1, ((day - 1) % 7).toInt() + 1, (day - 1) / 28 + 1)

    fun baseMovement(army: List<AdvArmySlot>): Int {
        require(army.isNotEmpty()) { "hero needs an army" }
        val slowest = army.minOf { it.speed }
        return rules.speedMp[maxOf(0, minOf(slowest, rules.speedMp.size - 1))]
    }

    /** Daily land points: base + base * Logistics% // 100 (exact for the table values). */
    fun maxMovement(h: AdvHero): Int {
        val base = baseMovement(h.army).toLong()
        return Math.toIntExact(Math.addExact(base, Math.floorDiv(Math.multiplyExact(base, rules.logisticsPct[h.logistics].toLong()), 100L)))
    }

    fun passable(g: AdvGrid, p: Pair<Int, Int>): Boolean =
        g.inside(p) && !g.tile(p).blocked && g.tile(p).terrain !in rules.impassable

    private fun orthCost(g: AdvGrid, a: Pair<Int, Int>, b: Pair<Int, Int>, pathfinding: Int, pol: AdventurePolicy): Int {
        val ta = g.tile(a)
        val tb = g.tile(b)
        val ra = ta.road != "none"
        val rb = tb.road != "none"
        if ((ra && rb) || (!pol.roadNeedsBoth && (ra || rb))) {
            fun rate(r: String) = pol.roadCost.first { it.first == r }.second
            val ca = if (ra) rate(ta.road) else null
            val cb = if (rb) rate(tb.road) else null
            if (ca == null) return cb!!
            if (cb == null) return ca
            return when (pol.roadRateFrom) { "source" -> ca; "dest" -> cb; else -> maxOf(ca, cb) }
        }
        val terrain = if (pol.costFrom == "dest") tb.terrain else ta.terrain
        var cost = rules.terrainCost.getValue(terrain)
        if (cost > 100 && pathfinding != 0) {
            cost = if (pol.pathfindingMode == "flat") {
                maxOf(Math.subtractExact(cost, pol.pathfindingFlat[pathfinding]), pol.moveCostFloor)
            } else {
                val pen = (cost - 100).toLong()
                val cut = AdventurePolicy.div(Math.multiplyExact(pen, pol.pathfindingPct[pathfinding].toLong()), 100L, pol.pathfindingRounding)
                Math.toIntExact(100L + pen - cut)
            }
        }
        return cost
    }

    private fun diagonal(cost: Int, pol: AdventurePolicy): Int {
        if (pol.diagonalMode == "sqrt2") {
            val sq = Math.multiplyExact(Math.multiplyExact(2L, cost.toLong()), cost.toLong())
            return BigInteger.valueOf(sq).sqrt().intValueExact()   // floor(cost * sqrt 2), exact
        }
        return Math.toIntExact(AdventurePolicy.div(Math.multiplyExact(cost.toLong(), pol.diagonalNum.toLong()), pol.diagonalDen.toLong(), pol.diagonalRounding))
    }

    private fun stepParts(g: AdvGrid, a: Pair<Int, Int>, b: Pair<Int, Int>, pathfinding: Int, pol: AdventurePolicy): Parts? {
        val dx = b.first - a.first
        val dy = b.second - a.second
        if ((dx == 0 && dy == 0) || maxOf(Math.abs(dx), Math.abs(dy)) != 1) return null
        if (!passable(g, a) || !passable(g, b)) return null
        val diag = dx != 0 && dy != 0
        if (diag) {
            if (!pol.diagonalMoves) return null
            if (!pol.diagonalCornerCut && !(passable(g, Pair(a.first + dx, a.second)) && passable(g, Pair(a.first, a.second + dy)))) return null
        }
        val orth = orthCost(g, a, b, pathfinding, pol)
        return Parts(if (diag) diagonal(orth, pol) else orth, orth, diag)
    }

    /** Python `step_cost`: cost of one step ignoring the remaining-points rule, or null. */
    fun stepCost(g: AdvGrid, a: Pair<Int, Int>, b: Pair<Int, Int>, pathfinding: Int, pol: AdventurePolicy): Int? =
        stepParts(g, a, b, pathfinding, pol)?.cost

    private fun paid(p: Parts, left: Int, fresh: Boolean, pol: AdventurePolicy): Int? {
        if (left >= p.cost) {
            if (pol.zeroRemainder && left - p.cost > 0 && left - p.cost < p.cost) return left
            return p.cost
        }
        if (pol.lastStep == "allow_if_any" || (pol.lastStep == "allow_if_fresh" && fresh)) return left
        if (pol.diagonalException && p.diagonal && left >= p.orth) return left
        return null
    }

    /** Python `_search`: Dijkstra, smallest (spent, steps, path) label wins. */
    private fun search(s: AdventureState, hero: AdvHero, budget: Int?): Map<Pair<Int, Int>, Pair<Long, List<Pair<Int, Int>>>> {
        val grid = s.grid
        val pol = s.policy
        val occupied = LinkedHashSet<Pair<Int, Int>>()
        for (h in s.heroes) if (h.id != hero.id && h.pos != null) occupied.add(h.pos)
        for (g in s.guards) occupied.add(g.pos)
        val start = hero.pos!!
        val best = LinkedHashMap<Pair<Int, Int>, Label>()
        best[start] = Label(0L, 0, listOf(start))
        val heap = PriorityQueue<Label>()
        heap.add(best.getValue(start))
        val done = LinkedHashSet<Pair<Int, Int>>()
        while (heap.isNotEmpty()) {
            val lab = heap.poll()
            val cur = lab.path.last()
            if (cur in done) continue
            done.add(cur)
            if (budget != null && lab.spent >= budget.toLong()) continue
            for ((dx, dy) in DIRS) {
                val nxt = Pair(cur.first + dx, cur.second + dy)
                if (nxt in occupied || nxt in done) continue
                val parts = stepParts(grid, cur, nxt, hero.pathfinding, pol) ?: continue
                var c = parts.cost
                if (budget != null) {
                    val fresh = lab.spent == 0L && !hero.movedToday
                    c = paid(parts, budget - lab.spent.toInt(), fresh, pol) ?: continue
                }
                val label = Label(Math.addExact(lab.spent, c.toLong()), lab.steps + 1, lab.path + nxt)
                val old = best[nxt]
                if (old == null || label < old) {
                    best[nxt] = label
                    heap.add(label)
                }
            }
        }
        val out = LinkedHashMap<Pair<Int, Int>, Pair<Long, List<Pair<Int, Int>>>>()
        for (t in best.keys.sortedWith(compareBy({ it.first }, { it.second }))) {
            if (t != start) out[t] = Pair(best.getValue(t).spent, best.getValue(t).path)
        }
        return out
    }

    /** Python `find_path`: cheapest path ignoring today's points, or null. The cost is a Long: unbudgeted sums can pass Int. */
    fun findPath(s: AdventureState, heroId: Int, dest: Pair<Int, Int>): Pair<Long, List<Pair<Int, Int>>>? {
        val h = s.heroes[heroId]
        if (h.pos == null) return null
        return search(s, h, null)[dest]
    }

    /** Python `reachable`: tile -> (cost, path) for every tile reachable today, sorted by tile. */
    fun reachable(s: AdventureState, heroId: Int): Map<Pair<Int, Int>, Pair<Int, List<Pair<Int, Int>>>> {
        val h = s.heroes[heroId]
        if (h.pos == null) return emptyMap()
        // Every spent value is within the budget (Int), so the narrowing is exact.
        return search(s, h, h.mp).mapValues { (_, v) -> Pair(Math.toIntExact(v.first), v.second) }
    }

    fun dailyIncome(p: AdvPlayer): AdvResources {
        var total = p.extraIncome
        for (m in p.mines) total += rules.mineOutput.getValue(m)
        return total
    }

    private fun startDay(s0: AdventureState, events: MutableList<AdventureEvent>): AdventureState {
        val (week, dow, month) = calendar(s0.day)
        events.add(AdventureEvent.DayStarted(s0.day, week, dow, month))
        if (dow == 1 && week > 1) {     // rules.md 1: not on the very first week
            events.add(AdventureEvent.WeekStarted(week, month, (week - 1) % 4 == 0L))
            val pools = s0.pools.map {
                val p = it.copy(available = Math.addExact(it.available, it.growth))
                events.add(AdventureEvent.PoolGrew(p.id, p.growth, p.available))
                p
            }
            return s0.copy(pools = pools)
        }
        return s0
    }

    private fun startTurn(s0: AdventureState, events: MutableList<AdventureEvent>): AdventureState {
        var s = s0
        val pid = s.current
        events.add(AdventureEvent.TurnStarted(pid, s.day))
        if (s.day > 1 || s.policy.incomeOnFirstDay) {
            val player = s.players[pid]
            val inc = dailyIncome(player)
            s = s.copy(players = s.players.mapIndexed { i, p -> if (i == pid) p.copy(resources = p.resources + inc) else p })
            events.add(AdventureEvent.IncomeReceived(pid, inc))
        }
        val heroes = s.heroes.map { h ->
            if (h.owner == pid && h.pos != null) {
                val mp = maxMovement(h)
                events.add(AdventureEvent.MovementReset(h.id, mp))
                h.copy(mp = mp, mpMax = mp, movedToday = false)
            } else h
        }
        return s.copy(heroes = heroes)
    }

    private fun validate(s: AdventureState, cmd: AdventureCommand): Any? {
        if (cmd is AdventureCommand.Begin) {
            if (s.day != 0L) throw IllegalCommand("game already started")
            return null
        }
        if (s.day == 0L) throw IllegalCommand("game not started")
        when (cmd) {
            is AdventureCommand.EndTurn -> {
                if (cmd.player == null || cmd.player != s.current) throw IllegalCommand("not player ${cmd.playerRepr}'s turn")
                return null
            }
            is AdventureCommand.Move -> {
                val id = cmd.hero
                if (id == null || id < 0 || id >= s.heroes.size) throw IllegalCommand("no such hero")
                if (s.heroes[id].owner != s.current) throw IllegalCommand("hero does not belong to the current player")
                if (s.heroes[id].pos == null) throw IllegalCommand("hero is not on the map")
                val dest = cmd.dest ?: throw IllegalCommand("not a tile: ${cmd.destRepr}")
                return reachable(s, id)[dest] ?: throw IllegalCommand("destination not reachable today")
            }
            is AdventureCommand.Attack -> {
                // Python's first check of encounter.validate; here because the hooks are optional.
                if (s.encounter == null) throw IllegalCommand("battles are not enabled in this game")
                return (encounters ?: throw IllegalStateException("Attack on a game with an encounter setup needs the encounter hooks")).validate(s, cmd)
            }
            else -> throw IllegalCommand("unknown command $cmd")
        }
    }

    /**
     * Python `apply`. [rng] is the `adventure:<game_id>` stream, reserved and never drawn from, except for an
     * `Attack`: there it is the battle stream `battle:<battle_id>` (`EncounterEngine.streamFor`), which the battle
     * draws from. Throws [IllegalCommand] with the state untouched.
     */
    fun apply(state: AdventureState, cmd: AdventureCommand, rng: Pcg32? = null): AdventureStep {
        val data = validate(state, cmd)
        val events = ArrayList<AdventureEvent>()
        val s = when (cmd) {
            AdventureCommand.Begin -> startTurn(startDay(state.copy(day = 1L, current = 0), events), events)
            is AdventureCommand.Move -> {
                @Suppress("UNCHECKED_CAST")
                val move = data as Pair<Int, List<Pair<Int, Int>>>
                val (cost, path) = move
                val h0 = state.heroes[cmd.hero!!]
                val h = h0.copy(pos = path.last(), mp = Math.subtractExact(h0.mp, cost), movedToday = true)
                events.add(AdventureEvent.HeroMoved(h.id, path, cost, h.mp))
                state.copy(heroes = state.heroes.map { if (it.id == h.id) h else it })
            }
            is AdventureCommand.Attack -> return encounters!!.resolve(state, cmd, rng, data!!)
            is AdventureCommand.EndTurn -> {
                events.add(AdventureEvent.TurnEnded(state.current))
                val nxt = state.current + 1
                val s1 = if (nxt == state.players.size) {
                    startDay(state.copy(day = Math.addExact(state.day, 1L), current = 0), events)
                } else state.copy(current = nxt)
                startTurn(s1, events)
            }
        }
        return AdventureStep(s, events)
    }

    companion object {
        private val DIRS = listOf(
            Pair(-1, -1), Pair(0, -1), Pair(1, -1), Pair(-1, 0), Pair(1, 0), Pair(-1, 1), Pair(0, 1), Pair(1, 1),
        )
    }
}
