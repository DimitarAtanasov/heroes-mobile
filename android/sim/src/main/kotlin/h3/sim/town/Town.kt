package h3.sim.town

import h3.sim.Canonical
import h3.sim.Category
import h3.sim.Datapack
import h3.sim.DatapackError
import h3.sim.PackJson
import h3.sim.Pcg32
import h3.sim.RngStreams
import java.math.BigInteger

/**
 * Town core: a port of `tools/h3re/h3re/town.py` (docs/specs/town.md, docs/specs/conformance-town.md).
 * Python is the oracle (ADR-0004); `vectors/town.json` pins every behaviour (ADR-0007).
 *
 * Lives in its own subpackage with its own [Resources], [GrowthPool] and [IllegalCommand] on purpose:
 * `h3.sim` (Adventure.kt, Battle.kt) and `h3.sim.hero` define neighbours with similar names; none may collide.
 *
 * Every function keeps the Python function's name (camelCase) and its check order, because the first failing
 * check decides the error text. Integers only (ADR-0002): amounts, costs, growth and the day are `Long`
 * (every pack integer is capped at 2^31-1 by the loader, `createGame` caps treasuries), levels `Int`; sums and
 * products use `Math.*Exact`. The single rounding step of weekly growth is [TownCore.roundCastleBonus]. Nothing is
 * random: `apply` accepts the stream `town:<game_id>` and never draws from it. Collections that reach state or
 * events are ordered lists; sorting is by code point (Python `sorted` on str), never by UTF-16 unit.
 */

/** Largest value a pack integer or a treasury field may take: the JVM `Int.MAX` (ADR-0004). */
const val TOWN_MAX_INT: Long = Datapack.MAX_INT

/** The seven resources in canonical order (Python `adventure.RESOURCE_NAMES`). */
val RESOURCE_NAMES: List<String> = listOf("gold", "wood", "ore", "mercury", "sulfur", "crystal", "gems")

/** Pack-error categories of the town loader beyond [Category] (tags used by the vectors). */
object TownCategory {
    const val UNKNOWN_BUILDING = "unknown_building"
    const val UPGRADE = "upgrade"
    const val CYCLE = "cycle"
    const val PLAYER_UNIQUE = "player_unique"
    const val DWELLING = "dwelling"
    const val HORDE = "horde"
}

/** Python `IllegalCommand` (a `ValueError`): the command is rejected; state untouched. */
class IllegalCommand(message: String) : IllegalArgumentException(message)

/** Python `ValueError` from `TownPolicy` or `create_game`. */
class TownValueError(message: String) : IllegalArgumentException(message)

/** Python `KeyError`: [key] is the missing faction or building id; the message is its `repr`, as `str(KeyError)`. */
class TownKeyError(val key: String) : NoSuchElementException(TownText.repr(key))

// --------------------------------------------------------------------------
// Python text helpers (own copy: Adventure.kt and the hero package are owned elsewhere)
// --------------------------------------------------------------------------

internal object TownText {
    /** Python `str.isspace` for one BMP character (the set `str.strip()` removes). */
    fun isSpace(c: Char): Boolean {
        val x = c.code
        return x in 9..13 || x in 0x1c..0x20 || x == 0x85 || x == 0xa0 || x == 0x1680 ||
            x in 0x2000..0x200a || x == 0x2028 || x == 0x2029 || x == 0x202f || x == 0x205f || x == 0x3000
    }

    /** `not s.strip()`. */
    fun blank(s: String): Boolean = s.all { isSpace(it) }

    /** Assigned in Unicode 15.1 (Python 3.13); a JDK on Unicode 15.0 (JDK 21) still calls them unassigned. */
    private fun isUnicode151Addition(cp: Int) = cp in 0x2ffc..0x2fff || cp == 0x31ef || cp in 0x2ebf0..0x2ee5d

    private fun isPrintable(cp: Int): Boolean = if (isUnicode151Addition(cp)) true else when (Character.getType(cp).toByte()) {
        Character.CONTROL, Character.FORMAT, Character.SURROGATE, Character.PRIVATE_USE, Character.UNASSIGNED,
        Character.LINE_SEPARATOR, Character.PARAGRAPH_SEPARATOR, Character.SPACE_SEPARATOR -> false
        else -> true
    }

    private fun hex(cp: Int, width: Int): String = Integer.toHexString(cp).padStart(width, '0')

    /** Python `repr(str)`: single quotes unless the text has a `'` and no `"`; non-printable code points escaped. */
    fun repr(v: String): String {
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

    /** Python `repr` of a decoded JSON value (and of the Kotlin integers). */
    fun repr(v: Any?): String = when (v) {
        null -> "None"
        is Boolean -> if (v) "True" else "False"
        is BigInteger, is Int, is Long -> v.toString()
        is String -> repr(v)
        is Map<*, *> -> v.entries.joinToString(", ", "{", "}") { (k, x) -> repr(k) + ": " + repr(x) }
        is List<*> -> v.joinToString(", ", "[", "]") { repr(it) }
        else -> v.toString()
    }

    /** Python `str(v)` of the same values. */
    fun str(v: Any?): String = if (v is String) v else repr(v)

    /** Python `type(v).__name__` for a decoded JSON value. */
    fun typeName(v: Any?): String = when (v) {
        null -> "NoneType"
        is Boolean -> "bool"
        is BigInteger -> "int"
        is String -> "str"
        is List<*> -> "list"
        is Map<*, *> -> "dict"
        else -> v::class.simpleName ?: "object"
    }
}

// --------------------------------------------------------------------------
// Resources, growth pools, policy
// --------------------------------------------------------------------------

data class Resources(
    val gold: Long = 0L,
    val wood: Long = 0L,
    val ore: Long = 0L,
    val mercury: Long = 0L,
    val sulfur: Long = 0L,
    val crystal: Long = 0L,
    val gems: Long = 0L,
) {
    /** The seven amounts in [RESOURCE_NAMES] order. */
    fun values(): List<Long> = listOf(gold, wood, ore, mercury, sulfur, crystal, gems)

    operator fun plus(o: Resources): Resources = of(values().zip(o.values()).map { (a, b) -> Math.addExact(a, b) })

    internal fun minus(o: Resources): Resources = of(values().zip(o.values()).map { (a, b) -> Math.subtractExact(a, b) })

    internal fun covers(cost: Resources): Boolean = values().zip(cost.values()).all { (a, b) -> a >= b }

    companion object {
        fun of(v: List<Long>): Resources = Resources(v[0], v[1], v[2], v[3], v[4], v[5], v[6])
    }
}

/** Weekly growth hook (Python `adventure.GrowthPool`): a dwelling as plain numbers. */
data class GrowthPool(val id: String, val available: Long, val growth: Long)

private val ROUNDING = listOf("floor", "ceil", "nearest")

/** Switchable rules for [uncertain] items (docs/specs/town.md section 6). */
data class TownPolicy(val citadelRounding: String = "floor") {
    init {
        if (citadelRounding !in ROUNDING) throw TownValueError("bad citadel_rounding ${TownText.repr(citadelRounding)}")
    }
}

val DEFAULT_POLICY = TownPolicy()

// --------------------------------------------------------------------------
// Content, state, commands, events
// --------------------------------------------------------------------------

data class Building(
    val id: String,
    val cost: Resources,
    val requires: List<String>,
    val upgrades: String = "",
    val income: Resources = Resources(),
    val fort: Boolean = false,
    val growthBonus: Pair<Long, Long> = Pair(0L, 1L),
    val dwellingLevel: Int = 0,
    val creature: String = "",
    val baseGrowth: Long = 0L,
    val hordeLevel: Int = 0,
    val hordeBonus: Long = 0L,
    val playerUnique: String = "",
)

data class Faction(val id: String, val buildings: List<Building>)

data class TownContent(val factions: List<Faction>)

data class TownSetup(val id: String, val faction: String, val owner: Long, val built: List<String> = emptyList())

/** [createGameChecked] input of a [TownSetup] whose fields may have any decoded type (saves, vectors). */
class RawSetup(val id: Any?, val faction: Any?, val owner: Any?, val built: Any?)

/** [createGameChecked] input of a treasury whose seven values (in [RESOURCE_NAMES] order) may have any decoded type. */
class RawResources(val values: List<Any?>)

data class Town(
    val id: String,
    val faction: String,
    val owner: Long,
    val built: List<String>,
    val builtToday: Boolean = false,
)

data class TownState(
    val gameId: String,
    val policy: TownPolicy,
    val content: TownContent,
    val players: List<Resources>,
    val towns: List<Town>,
    val day: Long = 1L,
)

sealed interface TownCommand

data class Build(val player: Long, val town: String, val building: String) : TownCommand

object NewDay : TownCommand

sealed interface TownEvent

data class BuildingBuilt(
    val town: String,
    val building: String,
    val player: Long,
    val cost: Resources,
    val treasury: Resources,
) : TownEvent

data class TownDayStarted(val day: Long) : TownEvent

/** A dwelling that is active in a town: Python `(level, creature, base_growth)`. */
data class Dwelling(val level: Int, val creature: String, val baseGrowth: Long)

/** Result of [TownCore.apply]. */
data class TownApplyResult(val state: TownState, val events: List<TownEvent>)

object TownCore {

    private const val SCHEMA_VERSION = 1L
    private val CP = PackJson.codePointOrder

    // ----------------------------------------------------------------------
    // Pack loader (Python parse_town_pack / load_town_pack)
    // ----------------------------------------------------------------------

    private fun err(category: String, msg: String): Nothing = throw DatapackError(category, msg)

    private fun int(v: Any?, path: String, lo: Long, hi: Long): Long {
        if (v !is BigInteger) err(Category.TYPE, "$path: expected integer, got ${TownText.typeName(v)}")
        if (v < BigInteger.valueOf(lo) || v > BigInteger.valueOf(hi)) err(Category.RANGE, "$path: $v out of range $lo..$hi")
        return v.toLong()
    }

    private fun obj(v: Any?, path: String, required: List<String>, optional: List<String> = emptyList()): Map<String, Any?> {
        if (v !is Map<*, *>) err(Category.TYPE, "$path: expected object")
        @Suppress("UNCHECKED_CAST")
        val m = v as Map<String, Any?>
        val unknown = m.keys.filter { it !in required && it !in optional }.sortedWith(CP)
        if (unknown.isNotEmpty()) err(Category.UNKNOWN_KEY, "$path: unknown key(s) ${unknown.joinToString(", ")}")
        val missing = required.filter { it !in m }.sortedWith(CP)
        if (missing.isNotEmpty()) err(Category.MISSING_KEY, "$path: missing key(s) ${missing.joinToString(", ")}")
        return m
    }

    private fun list(v: Any?, path: String, n: Int? = null): List<Any?> {
        if (v !is List<*>) err(Category.TYPE, "$path: expected array")
        if (n != null && v.size != n) err(Category.LENGTH, "$path: expected $n items, got ${v.size}")
        return v
    }

    private fun frac(v: Any?, path: String): Pair<Long, Long> {
        val a = list(v, path, 2)
        return Pair(int(a[0], "$path[0]", 0, TOWN_MAX_INT), int(a[1], "$path[1]", 1, TOWN_MAX_INT))
    }

    private fun str(v: Any?, path: String): String {
        if (v !is String || TownText.blank(v)) err(Category.TYPE, "$path: expected non-empty string")
        return v
    }

    private fun resources(v: Any?, path: String): Resources {
        val m = obj(v, path, emptyList(), RESOURCE_NAMES)
        return Resources.of(RESOURCE_NAMES.map { n -> int(if (n in m) m[n] else BigInteger.ZERO, "$path.$n", 0, TOWN_MAX_INT) })
    }

    private val B_REQ = listOf("id", "cost", "requires")
    private val B_OPT = listOf("upgrades", "income", "fort", "growth_bonus", "dwelling", "horde", "player_unique")

    private fun checkBuilding(b: Any?, path: String): Building {
        val m = obj(b, path, B_REQ, B_OPT)
        val id = str(m["id"], "$path.id")
        val cost = resources(m["cost"], "$path.cost")
        val reqs = list(m["requires"], "$path.requires").mapIndexed { i, r -> str(r, "$path.requires[$i]") }
        if (reqs.toSet().size != reqs.size) err(Category.DUPLICATE_NAME, "$path.requires: duplicate entry")
        var out = Building(id, cost, reqs.sortedWith(CP))
        if ("upgrades" in m) out = out.copy(upgrades = str(m["upgrades"], "$path.upgrades"))
        if ("income" in m) out = out.copy(income = resources(m["income"], "$path.income"))
        if ("fort" in m) {
            val f = m["fort"]
            if (f !is Boolean) err(Category.TYPE, "$path.fort: expected boolean")
            out = out.copy(fort = f)
        }
        if ("growth_bonus" in m) out = out.copy(growthBonus = frac(m["growth_bonus"], "$path.growth_bonus"))
        if ("dwelling" in m) {
            val d = obj(m["dwelling"], "$path.dwelling", listOf("level", "creature", "base_growth"))
            out = out.copy(
                dwellingLevel = Math.toIntExact(int(d["level"], "$path.dwelling.level", 1, 1000)),
                creature = str(d["creature"], "$path.dwelling.creature"),
                baseGrowth = int(d["base_growth"], "$path.dwelling.base_growth", 0, TOWN_MAX_INT),
            )
        }
        if ("horde" in m) {
            val h = obj(m["horde"], "$path.horde", listOf("level", "bonus"))
            out = out.copy(
                hordeLevel = Math.toIntExact(int(h["level"], "$path.horde.level", 1, 1000)),
                hordeBonus = int(h["bonus"], "$path.horde.bonus", 0, TOWN_MAX_INT),
            )
        }
        if ("player_unique" in m) out = out.copy(playerUnique = str(m["player_unique"], "$path.player_unique"))
        return out
    }

    /** All buildings [bid] needs, directly or transitively (the graph is acyclic), sorted. */
    private fun closure(bid: String, byId: Map<String, Building>): List<String> {
        val out = ArrayList<String>()
        val todo = ArrayList(byId.getValue(bid).requires)
        while (todo.isNotEmpty()) {
            val r = todo.removeAt(todo.size - 1)
            if (r !in out) {
                out.add(r)
                todo.addAll(byId.getValue(r).requires)
            }
        }
        return out.sortedWith(CP)
    }

    private fun checkFaction(f: Any?, path: String): Faction {
        val m = obj(f, path, listOf("id", "buildings"))
        val fid = str(m["id"], "$path.id")
        val blds = list(m["buildings"], "$path.buildings").mapIndexed { i, b -> checkBuilding(b, "$path.buildings[$i]") }
        if (blds.isEmpty()) err(Category.EMPTY, "$path.buildings: must not be empty")
        val byId = LinkedHashMap<String, Building>()
        for (b in blds) {
            if (b.id in byId) err(Category.DUPLICATE_NAME, "$fid: duplicate building ${TownText.repr(b.id)}")
            byId[b.id] = b
        }
        val ids = byId.keys.sortedWith(CP)
        val upgradedBy = LinkedHashMap<String, String>()
        for (bid in ids) {
            val b = byId.getValue(bid)
            for (r in b.requires + (if (b.upgrades.isNotEmpty()) listOf(b.upgrades) else emptyList())) {
                if (r !in byId) err(TownCategory.UNKNOWN_BUILDING, "$fid.$bid: unknown building ${TownText.repr(r)}")
            }
            if (b.upgrades.isNotEmpty()) {
                if (b.upgrades == bid || b.upgrades !in b.requires) {
                    err(TownCategory.UPGRADE, "$fid.$bid: upgrades ${TownText.repr(b.upgrades)} must also be required")
                }
                if (b.upgrades in upgradedBy) {
                    err(TownCategory.UPGRADE, "$fid.$bid: ${TownText.repr(b.upgrades)} is upgraded by more than one building")
                }
                upgradedBy[b.upgrades] = bid
            }
        }
        // Acyclic: place buildings whose requirements are all placed, in id order.
        val placed = LinkedHashSet<String>()
        while (placed.size < ids.size) {
            val ready = ids.filter { it !in placed && byId.getValue(it).requires.all { r -> r in placed } }
            if (ready.isEmpty()) {
                err(TownCategory.CYCLE, "$fid: requirement cycle among ${ids.filter { it !in placed }.joinToString(", ")}")
            }
            placed.addAll(ready)
        }
        for (bid in ids) {
            val tag = byId.getValue(bid).playerUnique
            if (tag.isNotEmpty() && closure(bid, byId).any { byId.getValue(it).playerUnique == tag }) {
                err(TownCategory.PLAYER_UNIQUE, "$fid.$bid: player_unique ${TownText.repr(tag)} is also on a building it requires")
            }
        }
        val roots = LinkedHashMap<Int, String>()
        for (bid in ids) {
            val b = byId.getValue(bid)
            if (b.dwellingLevel != 0) {
                if (closure(bid, byId).none { byId.getValue(it).fort }) err(TownCategory.DWELLING, "$fid.$bid: a dwelling needs a fort")
                val up = if (b.upgrades.isNotEmpty()) byId.getValue(b.upgrades) else null
                if (up != null && up.dwellingLevel != b.dwellingLevel) {
                    err(TownCategory.DWELLING, "$fid.$bid: a dwelling upgrades only a dwelling of its level")
                }
                if (up == null) {
                    if (b.dwellingLevel in roots) {
                        err(TownCategory.DWELLING, "$fid: dwelling level ${b.dwellingLevel} has more than one base dwelling")
                    }
                    roots[b.dwellingLevel] = bid
                }
            } else if (b.upgrades.isNotEmpty() && byId.getValue(b.upgrades).dwellingLevel != 0) {
                err(TownCategory.DWELLING, "$fid.$bid: only a dwelling may upgrade a dwelling")
            }
        }
        for (bid in ids) {
            val lv = byId.getValue(bid).hordeLevel
            if (lv != 0 && lv !in roots) err(TownCategory.HORDE, "$fid.$bid: horde level $lv has no dwelling")
        }
        return Faction(fid, ids.map { byId.getValue(it) })
    }

    /** Validate an already-decoded town pack ([PackJson] values) and return a [TownContent]. */
    fun parseTownPack(o: Any?): TownContent {
        val m = obj(o, "towns", listOf("schema_version", "factions"))
        if (int(m["schema_version"], "towns.schema_version", 0, TOWN_MAX_INT) != SCHEMA_VERSION) {
            err(Category.SCHEMA_VERSION, "towns.schema_version: unsupported")
        }
        val facs = list(m["factions"], "towns.factions").mapIndexed { i, f -> checkFaction(f, "towns.factions[$i]") }
        if (facs.isEmpty()) err(Category.EMPTY, "towns.factions: must not be empty")
        val byId = LinkedHashMap<String, Faction>()
        for (f in facs) {
            if (f.id in byId) err(Category.DUPLICATE_NAME, "towns: duplicate faction ${TownText.repr(f.id)}")
            byId[f.id] = f
        }
        return TownContent(byId.keys.sortedWith(CP).map { byId.getValue(it) })
    }

    /**
     * Python `load_town_pack` on the text of a file: floats, NaN and duplicate keys are rejected,
     * those errors are prefixed with [what] (the file's base name).
     */
    fun parseTownPackText(text: String, what: String): TownContent = parseTownPack(PackJson.parse(text, what))

    // ----------------------------------------------------------------------
    // Canonical form, hashes
    // ----------------------------------------------------------------------

    private fun resMap(r: Resources): Map<String, Any?> {
        val m = LinkedHashMap<String, Any?>()
        for ((n, v) in RESOURCE_NAMES.zip(r.values())) m[n] = v
        return m
    }

    private fun buildingMap(b: Building): Map<String, Any?> = linkedMapOf(
        "id" to b.id,
        "cost" to resMap(b.cost),
        "requires" to b.requires,
        "upgrades" to b.upgrades,
        "income" to resMap(b.income),
        "fort" to b.fort,
        "growth_bonus" to listOf(b.growthBonus.first, b.growthBonus.second),
        "dwelling_level" to b.dwellingLevel,
        "creature" to b.creature,
        "base_growth" to b.baseGrowth,
        "horde_level" to b.hordeLevel,
        "horde_bonus" to b.hordeBonus,
        "player_unique" to b.playerUnique,
    )

    /** The canonical-JSON tree of the content (Python `asdict(content)`), keys unsorted; [Canonical.encode] sorts them. */
    fun contentMap(c: TownContent): Map<String, Any?> = linkedMapOf(
        "factions" to c.factions.map { f -> linkedMapOf("id" to f.id, "buildings" to f.buildings.map { buildingMap(it) }) },
    )

    /** The canonical-JSON tree of the state (Python `asdict`), keys unsorted. */
    fun stateMap(s: TownState): Map<String, Any?> = linkedMapOf(
        "game_id" to s.gameId,
        "policy" to linkedMapOf<String, Any?>("citadel_rounding" to s.policy.citadelRounding),
        "content" to contentMap(s.content),
        "players" to s.players.map { resMap(it) },
        "towns" to s.towns.map { t ->
            linkedMapOf<String, Any?>(
                "id" to t.id, "faction" to t.faction, "owner" to t.owner, "built" to t.built, "built_today" to t.builtToday,
            )
        },
        "day" to s.day,
    )

    fun canonical(s: TownState): ByteArray = Canonical.encode(stateMap(s))

    fun canonicalText(s: TownState): String = canonical(s).toString(Charsets.US_ASCII)

    fun stateHash(s: TownState): String = Canonical.hash(stateMap(s))

    /** SHA-256 of the canonical JSON of validated content (Python `content_hash`). */
    fun contentHash(c: TownContent): String = Canonical.hash(contentMap(c))

    /** The town core's named stream `town:<game_id>` (never drawn from). */
    fun townRng(masterSeed: BigInteger, gameId: String): Pcg32 = RngStreams.derive(masterSeed, "town:$gameId")

    fun townRng(masterSeed: Long, gameId: String): Pcg32 = townRng(BigInteger.valueOf(masterSeed), gameId)

    // ----------------------------------------------------------------------
    // Lookups
    // ----------------------------------------------------------------------

    private fun faction(content: TownContent, fid: String): Faction =
        content.factions.firstOrNull { it.id == fid } ?: throw TownKeyError(fid)

    /** Python `find_building`: [TownKeyError] for an unknown faction (its id) or building (its id). */
    fun findBuilding(content: TownContent, factionId: String, buildingId: String): Building =
        faction(content, factionId).buildings.firstOrNull { it.id == buildingId } ?: throw TownKeyError(buildingId)

    private fun townOf(state: TownState, id: String): Town =
        state.towns.firstOrNull { it.id == id } ?: throw IllegalCommand("no such town ${TownText.repr(id)}")

    private fun buildingsOf(state: TownState, town: Town): List<Building> = faction(state.content, town.faction).buildings

    /** Built buildings that no built building upgrades, in content order. */
    private fun active(state: TownState, town: Town): List<Building> {
        val blds = buildingsOf(state, town).filter { it.id in town.built }
        val gone = blds.filter { it.upgrades.isNotEmpty() }.map { it.upgrades }
        return blds.filter { it.id !in gone }
    }

    // ----------------------------------------------------------------------
    // Growth: the one rounding step
    // ----------------------------------------------------------------------

    /** Python `Fraction(num, den)`: lowest terms, positive denominator; [ArithmeticException] "Fraction(n, 0)" for den 0. */
    private fun reduced(num: Long, den: Long): Pair<Long, Long> {
        if (den == 0L) throw ArithmeticException("Fraction($num, 0)")
        var a = Math.abs(num)
        var b = Math.abs(den)
        while (b != 0L) {
            val t = a % b
            a = b
            b = t
        }
        val g = if (a == 0L) 1L else a
        val sign = if (den < 0L) -1L else 1L
        return Pair(sign * (num / g), sign * (den / g))
    }

    /** The one rounding step of weekly growth: `base * bonus` (an exact fraction) in the policy's [mode]. */
    fun roundCastleBonus(base: Long, bonus: Pair<Long, Long>, mode: String): Long {
        val (num, den) = reduced(bonus.first, bonus.second)
        val n = Math.multiplyExact(base, num)
        return when (mode) {
            "floor" -> Math.floorDiv(n, den)
            "ceil" -> Math.negateExact(Math.floorDiv(Math.negateExact(n), den))
            else -> Math.floorDiv(Math.addExact(Math.multiplyExact(2L, n), den), Math.multiplyExact(2L, den)) // nearest, halves up
        }
    }

    /** rules.md 4: `base + base * castle_bonus + horde`. [bonus] is `(num, den)`. */
    fun weeklyGrowth(base: Long, bonus: Pair<Long, Long>, horde: Long, policy: TownPolicy = DEFAULT_POLICY): Long =
        Math.addExact(Math.addExact(base, roundCastleBonus(base, bonus, policy.citadelRounding)), horde)

    /** `Fraction(a) > Fraction(b)`. */
    private fun greater(a: Pair<Long, Long>, b: Pair<Long, Long>): Boolean {
        val (an, ad) = reduced(a.first, a.second)
        val (bn, bd) = reduced(b.first, b.second)
        return Math.multiplyExact(an, bd) > Math.multiplyExact(bn, ad)
    }

    // ----------------------------------------------------------------------
    // Queries
    // ----------------------------------------------------------------------

    fun missingRequirements(state: TownState, townId: String, buildingId: String): List<String> {
        val town = townOf(state, townId)
        val b = findBuilding(state.content, town.faction, buildingId)
        return b.requires.filter { it !in town.built }
    }

    fun activeBuildings(state: TownState, townId: String): List<String> = active(state, townOf(state, townId)).map { it.id }

    /** Daily income of the town's active buildings (an upgrade replaces the building it upgrades). */
    fun townIncome(state: TownState, townId: String): Resources =
        active(state, townOf(state, townId)).fold(Resources()) { total, b -> total + b.income }

    fun playerIncome(state: TownState, player: Long): Resources =
        state.towns.filter { it.owner == player }.fold(Resources()) { total, t -> total + townIncome(state, t.id) }

    /** `(level, creature, base_growth)` of each active dwelling, sorted as Python sorts the tuples. */
    fun dwellings(state: TownState, townId: String): List<Dwelling> {
        val cmp = Comparator<Dwelling> { a, b ->
            if (a.level != b.level) a.level.compareTo(b.level)
            else if (a.creature != b.creature) CP.compare(a.creature, b.creature)
            else a.baseGrowth.compareTo(b.baseGrowth)
        }
        return active(state, townOf(state, townId)).filter { it.dwellingLevel != 0 }
            .map { Dwelling(it.dwellingLevel, it.creature, it.baseGrowth) }.sortedWith(cmp)
    }

    /**
     * Weekly growth of each dwelling level (id `<town>:dwelling<level>`, ascending level). `available` is carried
     * over from the pool with the same id in [current] (the last one wins; 0 if none).
     */
    fun growthPools(state: TownState, townId: String, current: List<GrowthPool> = emptyList()): List<GrowthPool> {
        val town = townOf(state, townId)
        val act = active(state, town)
        var bonus = Pair(0L, 1L)
        for (b in act) if (greater(b.growthBonus, bonus)) bonus = b.growthBonus // castle bonuses do not stack
        val have = LinkedHashMap<String, Long>()
        for (p in current) have[p.id] = p.available
        val out = ArrayList<GrowthPool>()
        for (d in dwellings(state, townId)) {
            val horde = act.filter { it.hordeLevel == d.level }.fold(0L) { a, b -> Math.addExact(a, b.hordeBonus) }
            val pid = "${town.id}:dwelling${d.level}"
            out.add(GrowthPool(pid, have[pid] ?: 0L, weeklyGrowth(d.baseGrowth, bonus, horde, state.policy)))
        }
        return out
    }

    private fun uniqueCount(state: TownState, player: Long, tag: String): Int =
        state.towns.filter { it.owner == player }.sumOf { t -> buildingsOf(state, t).count { it.id in t.built && it.playerUnique == tag } }

    // ----------------------------------------------------------------------
    // Setup
    // ----------------------------------------------------------------------

    private fun isInt(v: Any?): Boolean = v is BigInteger || v is Long || v is Int

    private fun big(v: Any?): BigInteger = if (v is BigInteger) v else BigInteger.valueOf((v as Number).toLong())

    private val BAD_TREASURY = "players need resources: a Resources of ints 0..$TOWN_MAX_INT"

    private fun treasury(p: Any?): Resources {
        val vals: List<Any?> = when (p) {
            is Resources -> p.values()
            is RawResources -> p.values
            else -> throw TownValueError(BAD_TREASURY)
        }
        if (vals.size != RESOURCE_NAMES.size) throw TownValueError(BAD_TREASURY)
        val out = ArrayList<Long>()
        for (v in vals) {
            if (!isInt(v)) throw TownValueError(BAD_TREASURY)
            val x = big(v)
            if (x.signum() < 0 || x > BigInteger.valueOf(TOWN_MAX_INT)) throw TownValueError(BAD_TREASURY)
            out.add(x.toLong())
        }
        return Resources.of(out)
    }

    /** Typed entry of [createGameChecked]: the arguments cannot have a wrong type, so only the value checks remain. */
    fun createGame(
        gameId: String,
        content: TownContent,
        players: List<Resources>,
        towns: List<TownSetup>,
        policy: TownPolicy = DEFAULT_POLICY,
    ): TownState = createGameChecked(gameId, content, players, towns, policy)

    /**
     * Python `create_game`: the initial state (day 1). Every argument may have any decoded type, as in Python where
     * `type(v) is int` rejects bools and floats; the checks and their order are the Python ones. [players] is a list
     * of [Resources] or [RawResources], [towns] a list of [TownSetup] or [RawSetup]; anything else is rejected with
     * the Python message. Errors are [TownValueError].
     */
    fun createGameChecked(gameId: Any?, content: TownContent, players: Any?, towns: Any?, policy: TownPolicy = DEFAULT_POLICY): TownState {
        if (players !is List<*> || players.isEmpty()) throw TownValueError("players need resources: a non-empty sequence of Resources")
        val treasuries = players.map { treasury(it) }
        if (towns !is List<*>) throw TownValueError("towns must be a sequence of TownSetup")
        val built = ArrayList<Town>()
        val seen = LinkedHashSet<String>()
        for (s in towns) {
            val raw = when (s) {
                is TownSetup -> RawSetup(s.id, s.faction, s.owner, s.built)
                is RawSetup -> s
                else -> throw TownValueError("towns must be TownSetup values, got ${TownText.repr(s)}")
            }
            val id = raw.id
            if (id !is String || TownText.blank(id)) throw TownValueError("town id must be a non-empty string, got ${TownText.repr(id)}")
            val fid = raw.faction
            if (fid !is String) throw TownValueError("town ${TownText.repr(id)}: faction must be a string")
            if (!isInt(raw.owner)) throw TownValueError("town ${TownText.repr(id)}: owner must be an int, got ${TownText.repr(raw.owner)}")
            val names0 = raw.built
            if (names0 !is List<*> || names0.any { it !is String }) {
                throw TownValueError("town ${TownText.repr(id)}: built must be a sequence of building ids")
            }
            if (id in seen) throw TownValueError("duplicate town id ${TownText.repr(id)}")
            seen.add(id)
            val fac = content.factions.firstOrNull { it.id == fid }
                ?: throw TownValueError("town ${TownText.repr(id)}: unknown faction ${TownText.repr(fid)}")
            val owner = big(raw.owner)
            if (owner.signum() < 0 || owner >= BigInteger.valueOf(treasuries.size.toLong())) {
                throw TownValueError("town ${TownText.repr(id)}: no such owner $owner")
            }
            val names = names0.map { it as String }.sortedWith(CP)
            val known = fac.buildings.map { it.id }
            if (names.toSet().size != names.size || names.any { it !in known }) {
                throw TownValueError("town ${TownText.repr(id)}: unknown or duplicate building")
            }
            for (b in fac.buildings) {
                if (b.id in names && b.requires.any { it !in names }) {
                    throw TownValueError("town ${TownText.repr(id)}: ${TownText.repr(b.id)} requires ${b.requires.joinToString(", ")}")
                }
            }
            built.add(Town(id, fid, owner.toLong(), names))
        }
        val state = TownState(TownText.str(gameId), policy, content, treasuries, built)
        for (t in state.towns) {
            for (b in buildingsOf(state, t)) {
                if (b.id in t.built && b.playerUnique.isNotEmpty() && uniqueCount(state, t.owner, b.playerUnique) > 1) {
                    throw TownValueError("player ${t.owner} has more than one ${TownText.repr(b.playerUnique)} building")
                }
            }
        }
        return state
    }

    // ----------------------------------------------------------------------
    // apply
    // ----------------------------------------------------------------------

    private fun validateBuild(state: TownState, cmd: Build): Pair<Town, Building> {
        if (!(cmd.player >= 0L && cmd.player < state.players.size.toLong())) throw IllegalCommand("no such player ${cmd.player}")
        val town = townOf(state, cmd.town)
        if (town.owner != cmd.player) throw IllegalCommand("player ${cmd.player} does not own town ${TownText.repr(town.id)}")
        val b = try {
            findBuilding(state.content, town.faction, cmd.building)
        } catch (e: TownKeyError) {
            throw IllegalCommand("no such building ${TownText.repr(cmd.building)}")
        }
        if (b.id in town.built) throw IllegalCommand("${TownText.repr(b.id)} already built")
        if (town.builtToday) throw IllegalCommand("town ${TownText.repr(town.id)} already built today")
        val missing = b.requires.filter { it !in town.built }
        if (missing.isNotEmpty()) throw IllegalCommand("${TownText.repr(b.id)}: missing ${missing.joinToString(", ")}")
        if (b.playerUnique.isNotEmpty() && uniqueCount(state, cmd.player, b.playerUnique) != 0) {
            throw IllegalCommand("player ${cmd.player} already has a ${TownText.repr(b.playerUnique)} building")
        }
        if (!state.players[cmd.player.toInt()].covers(b.cost)) {
            throw IllegalCommand("player ${cmd.player} cannot afford ${TownText.repr(b.id)}")
        }
        return Pair(town, b)
    }

    /**
     * Apply one command. Throws [IllegalCommand] (or [TownKeyError] for a hand-built state whose town names a faction
     * the content lacks) before anything changes. [rng] (the stream `town:<id>`) is reserved and never drawn from.
     */
    fun apply(state: TownState, cmd: TownCommand, rng: Pcg32? = null): TownApplyResult {
        if (cmd is NewDay) {
            val day = Math.addExact(state.day, 1L)
            val next = state.copy(day = day, towns = state.towns.map { it.copy(builtToday = false) })
            return TownApplyResult(next, listOf(TownDayStarted(day)))
        }
        val build = cmd as Build
        val (town, b) = validateBuild(state, build)
        val left = state.players[build.player.toInt()].minus(b.cost)
        val players = state.players.mapIndexed { i, p -> if (i.toLong() == build.player) left else p }
        val towns = state.towns.map { t ->
            if (t.id == town.id) t.copy(built = (t.built + b.id).sortedWith(CP), builtToday = true) else t
        }
        return TownApplyResult(state.copy(players = players, towns = towns), listOf(BuildingBuilt(town.id, b.id, build.player, b.cost, left)))
    }
}
