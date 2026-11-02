package h3.sim.hero

import h3.sim.Canonical
import h3.sim.Category
import h3.sim.Datapack
import h3.sim.DatapackError
import h3.sim.PackJson
import h3.sim.Pcg32
import h3.sim.RngStreams
import java.math.BigInteger

/**
 * Hero core: a port of `tools/h3re/h3re/hero.py` (docs/specs/hero.md, docs/specs/conformance-hero.md).
 * Python is the oracle (ADR-0004); `vectors/hero.json` pins every behaviour (ADR-0007).
 *
 * Lives in its own subpackage on purpose: `adventure.py` also defines `Hero` and `IllegalCommand`, and
 * `h3.sim.IllegalCommand` (Battle.kt) already exists; none of them may collide with these names.
 *
 * Every function keeps the Python function's name (camelCase) and its operation order, in particular
 * the order of RNG draws per level: primary skill, then the upgrade offer, then the new-skill offer.
 * A command is validated completely before the first draw, so a rejected command touches neither the
 * state nor the stream. Integers only (ADR-0002): weights, XP and the XP table are `Long` (all capped
 * at 2^31-1 by the loader or by `apply`), counts and levels `Int`; sums use `Math.*Exact`.
 */

/** Largest value a pack integer, an XP total or a weight total may take: the JVM `Int.MAX` (ADR-0004). */
const val HERO_MAX_INT: Long = Datapack.MAX_INT

/** Primary skills in draw order (rules.md 5.1). */
val PRIMARY: List<String> = listOf("attack", "defense", "power", "knowledge")

/** Pack-error categories of the hero loader beyond [Category] (a weight total that is not positive or above the cap). */
object HeroCategory {
    const val TOTAL = "total"
}

/** Python `ValueError` from `HeroPolicy` or `create_hero`; [category] is a stable tag used by the vectors. */
class HeroValueError(val category: String, message: String) : IllegalArgumentException(message) {
    companion object {
        const val POLICY = "policy"
        const val UNKNOWN_CLASS = "unknown_class"
        const val UNKNOWN_SKILL = "unknown_skill"
        const val DUPLICATE_SKILL = "duplicate_skill"
        const val BAD_LEVEL = "bad_level"
        const val TOO_MANY = "too_many"
    }
}

/** Python `IllegalCommand`: the command is rejected; state untouched, no RNG draw. */
class IllegalCommand(message: String) : IllegalArgumentException(message)

// --------------------------------------------------------------------------
// Python text helpers
// --------------------------------------------------------------------------

internal object PyText {
    /** Python `str.isspace` for one BMP character (the set `str.strip()` removes). */
    fun isSpace(c: Char): Boolean {
        val x = c.code
        return x in 9..13 || x in 0x1c..0x20 || x == 0x85 || x == 0xa0 || x == 0x1680 ||
            x in 0x2000..0x200a || x == 0x2028 || x == 0x2029 || x == 0x202f || x == 0x205f || x == 0x3000
    }

    /** `not s.strip()`. */
    fun blank(s: String): Boolean = s.all { isSpace(it) }

    private fun printable(cp: Int): Boolean {
        if (cp == 0x20) return true
        return when (Character.getType(cp).toByte()) {
            Character.CONTROL, Character.FORMAT, Character.SURROGATE, Character.PRIVATE_USE,
            Character.UNASSIGNED, Character.LINE_SEPARATOR, Character.PARAGRAPH_SEPARATOR,
            Character.SPACE_SEPARATOR -> false
            else -> true
        }
    }

    private fun hex(v: Int, width: Int): String {
        val h = Integer.toHexString(v)
        return "0".repeat(width - h.length) + h
    }

    /** Python `repr(str)`. */
    fun repr(s: String): String {
        val q = if ('\'' in s && '"' !in s) '"' else '\''
        val sb = StringBuilder().append(q)
        var i = 0
        while (i < s.length) {
            val cp = s.codePointAt(i)
            i += Character.charCount(cp)
            when {
                cp == '\\'.code -> sb.append("\\\\")
                cp == q.code -> sb.append('\\').append(q)
                cp == '\n'.code -> sb.append("\\n")
                cp == '\r'.code -> sb.append("\\r")
                cp == '\t'.code -> sb.append("\\t")
                printable(cp) -> sb.appendCodePoint(cp)
                cp < 0x100 -> sb.append("\\x").append(hex(cp, 2))
                cp < 0x10000 -> sb.append("\\u").append(hex(cp, 4))
                else -> sb.append("\\U").append(hex(cp, 8))
            }
        }
        return sb.append(q).toString()
    }

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
// Policy and content
// --------------------------------------------------------------------------

private val OFFER_MODES = listOf("upgrade_and_new", "weighted_pair")
private val OFFER_FILLS = listOf("other_kind", "single")

/** Switchable rules for [uncertain] items (docs/specs/hero.md section 6). */
data class HeroPolicy(
    val offerMode: String = "upgrade_and_new",
    val offerFill: String = "other_kind",
) {
    init {
        if (offerMode !in OFFER_MODES) throw HeroValueError(HeroValueError.POLICY, "bad offer_mode ${PyText.repr(offerMode)}")
        if (offerFill !in OFFER_FILLS) throw HeroValueError(HeroValueError.POLICY, "bad offer_fill ${PyText.repr(offerFill)}")
    }
}

val DEFAULT_POLICY = HeroPolicy()

data class HeroRules(
    val xpTable: List<Long>,
    val maxSecondary: Int,
    val skillLevels: Int,
    val primaryHighFromLevel: Int,
    val skills: List<String>,
)

data class HeroClass(
    val id: String,
    val startPrimary: List<Int>,
    val primaryLow: List<Long>,
    val primaryHigh: List<Long>,
    val secondaryWeights: List<Pair<String, Long>>,
)

data class HeroContent(val rules: HeroRules, val classes: List<HeroClass>)

// --------------------------------------------------------------------------
// State, commands, events
// --------------------------------------------------------------------------

data class SecondarySkill(val skill: String, val level: Int)

data class SkillOffer(val skill: String, val level: Int)

data class Hero(
    val id: String,
    val heroClass: String,
    val level: Int,
    val xp: Long,
    val attack: Int,
    val defense: Int,
    val power: Int,
    val knowledge: Int,
    val secondary: List<SecondarySkill> = emptyList(),
    val offer: List<SkillOffer> = emptyList(),
)

data class HeroState(val policy: HeroPolicy, val rules: HeroRules, val classDef: HeroClass, val hero: Hero)

sealed interface HeroCommand {
    val hero: String
}

data class GainXP(override val hero: String, val amount: Long) : HeroCommand

data class ChooseSkill(override val hero: String, val index: Long) : HeroCommand

sealed interface HeroEvent

data class XPGained(val hero: String, val amount: Long, val xp: Long) : HeroEvent

data class LevelGained(val hero: String, val level: Int) : HeroEvent

data class PrimaryGained(val hero: String, val skill: String, val value: Int) : HeroEvent

data class SkillOffered(val hero: String, val level: Int, val offers: List<SkillOffer>) : HeroEvent

data class SkillLearned(val hero: String, val skill: String, val level: Int) : HeroEvent

/** Result of [HeroCore.apply]. */
data class HeroApplyResult(val state: HeroState, val events: List<HeroEvent>)

/** The one draw the hero core makes: Python `rng.range(lo, hi)`, half-open. Tests supply failing sources. */
fun interface HeroDraw {
    fun range(lo: Long, hi: Long): Long
}

fun Pcg32.asHeroDraw(): HeroDraw = HeroDraw { lo, hi -> this.range(lo, hi) }

// --------------------------------------------------------------------------
// Pack loader (Python parse_hero_pack / load_hero_pack)
// --------------------------------------------------------------------------

object HeroCore {

    private const val SCHEMA_VERSION = 1L

    private val KEYS = listOf(
        "schema_version", "xp_table", "max_secondary", "skill_levels",
        "primary_high_from_level", "skills", "classes",
    )
    private val CLASS_KEYS = listOf("id", "start_primary", "primary_low", "primary_high", "secondary")

    private fun err(category: String, msg: String): Nothing = throw DatapackError(category, msg)

    private fun int(v: Any?, path: String, lo: Long, hi: Long): Long {
        if (v !is BigInteger) err(Category.TYPE, "$path: expected integer, got ${PyText.typeName(v)}")
        if (v < BigInteger.valueOf(lo) || v > BigInteger.valueOf(hi)) {
            err(Category.RANGE, "$path: $v out of range $lo..$hi")
        }
        return v.toLong()
    }

    private fun obj(v: Any?, path: String, required: List<String>): Map<String, Any?> {
        if (v !is Map<*, *>) err(Category.TYPE, "$path: expected object")
        @Suppress("UNCHECKED_CAST")
        val m = v as Map<String, Any?>
        val unknown = (m.keys - required.toSet()).sortedWith(PackJson.codePointOrder)
        if (unknown.isNotEmpty()) err(Category.UNKNOWN_KEY, "$path: unknown key(s) ${unknown.joinToString(", ")}")
        val missing = (required.toSet() - m.keys).sortedWith(PackJson.codePointOrder)
        if (missing.isNotEmpty()) err(Category.MISSING_KEY, "$path: missing key(s) ${missing.joinToString(", ")}")
        return m
    }

    private fun list(v: Any?, path: String, n: Int? = null): List<Any?> {
        if (v !is List<*>) err(Category.TYPE, "$path: expected array")
        if (n != null && v.size != n) err(Category.LENGTH, "$path: expected $n items, got ${v.size}")
        return v
    }

    /** A weight total is the span of one `rng.range` draw: it must fit a JVM Int (ADR-0004). */
    private fun checkTotal(w: List<Long>, path: String, positive: Boolean) {
        val total = w.fold(0L) { a, b -> Math.addExact(a, b) }
        if (positive && total <= 0) err(HeroCategory.TOTAL, "$path: weights must have a positive total")
        if (total > HERO_MAX_INT) err(HeroCategory.TOTAL, "$path: weight total $total above $HERO_MAX_INT")
    }

    private fun weights(v: Any?, path: String): List<Long> {
        val w = list(v, path, PRIMARY.size).mapIndexed { i, x -> int(x, "$path[$i]", 0, HERO_MAX_INT) }
        checkTotal(w, path, true)
        return w
    }

    private fun checkClass(c: Any?, path: String, skills: List<String>): HeroClass {
        val m = obj(c, path, CLASS_KEYS)
        val cid = m["id"]
        if (cid !is String || PyText.blank(cid)) err(Category.TYPE, "$path.id: expected non-empty string")
        val start = list(m["start_primary"], "$path.start_primary", PRIMARY.size)
            .mapIndexed { i, x -> Math.toIntExact(int(x, "$path.start_primary[$i]", 0, 1000)) }
        val sec = obj(m["secondary"], "$path.secondary", skills)
        val pairs = skills.map { s -> Pair(s, int(sec[s], "$path.secondary.$s", 0, HERO_MAX_INT)) }
        checkTotal(pairs.map { it.second }, "$path.secondary", false)
        val low = weights(m["primary_low"], "$path.primary_low")
        val high = weights(m["primary_high"], "$path.primary_high")
        return HeroClass(cid, start, low, high, pairs)
    }

    /** Validate an already-decoded hero pack ([PackJson] values) and return a [HeroContent]. */
    fun parseHeroPack(o: Any?): HeroContent {
        val m = obj(o, "hero", KEYS)
        if (int(m["schema_version"], "hero.schema_version", 0, HERO_MAX_INT) != SCHEMA_VERSION) {
            err(Category.SCHEMA_VERSION, "hero.schema_version: unsupported")
        }
        val xp = list(m["xp_table"], "hero.xp_table").mapIndexed { i, x -> int(x, "hero.xp_table[$i]", 0, HERO_MAX_INT) }
        if (xp.isEmpty()) err(Category.EMPTY, "hero.xp_table: must not be empty")
        if (xp[0] != 0L) err(Category.TABLE, "hero.xp_table: must start at 0")
        if (xp.zipWithNext().any { (a, b) -> a >= b }) err(Category.TABLE, "hero.xp_table: must be strictly increasing")
        val rawSkills = list(m["skills"], "hero.skills")
        rawSkills.forEachIndexed { i, s ->
            if (s !is String || PyText.blank(s)) err(Category.TYPE, "hero.skills[$i]: expected non-empty string")
        }
        if (rawSkills.toSet().size != rawSkills.size) err(Category.DUPLICATE_NAME, "hero.skills: duplicate skill")
        val skills = rawSkills.map { it as String }.sortedWith(PackJson.codePointOrder)
        val rules = HeroRules(
            xpTable = xp,
            maxSecondary = Math.toIntExact(int(m["max_secondary"], "hero.max_secondary", 0, 1000)),
            skillLevels = Math.toIntExact(int(m["skill_levels"], "hero.skill_levels", 1, 100)),
            primaryHighFromLevel = Math.toIntExact(
                int(m["primary_high_from_level"], "hero.primary_high_from_level", 2, HERO_MAX_INT),
            ),
            skills = skills,
        )
        val byId = LinkedHashMap<String, HeroClass>()
        list(m["classes"], "hero.classes").forEachIndexed { i, c ->
            val hc = checkClass(c, "hero.classes[$i]", skills)
            if (hc.id in byId) err(Category.DUPLICATE_NAME, "hero.classes: duplicate class ${PyText.repr(hc.id)}")
            byId[hc.id] = hc
        }
        if (byId.isEmpty()) err(Category.EMPTY, "hero.classes: must not be empty")
        return HeroContent(rules, byId.keys.sortedWith(PackJson.codePointOrder).map { byId.getValue(it) })
    }

    /**
     * Python `load_hero_pack` on the text of a file: floats, NaN and duplicate keys are rejected,
     * errors are prefixed with [what] (the file's base name).
     */
    fun parseHeroPackText(text: String, what: String): HeroContent = parseHeroPack(PackJson.parse(text, what))

    // ----------------------------------------------------------------------
    // Canonical form, hashes
    // ----------------------------------------------------------------------

    private fun rulesMap(r: HeroRules): Map<String, Any?> = linkedMapOf(
        "xp_table" to r.xpTable,
        "max_secondary" to r.maxSecondary,
        "skill_levels" to r.skillLevels,
        "primary_high_from_level" to r.primaryHighFromLevel,
        "skills" to r.skills,
    )

    private fun classMap(c: HeroClass): Map<String, Any?> = linkedMapOf(
        "id" to c.id,
        "start_primary" to c.startPrimary,
        "primary_low" to c.primaryLow,
        "primary_high" to c.primaryHigh,
        "secondary_weights" to c.secondaryWeights.map { listOf(it.first, it.second) },
    )

    private fun skillMap(skill: String, level: Int): Map<String, Any?> = linkedMapOf("skill" to skill, "level" to level)

    private fun heroMap(h: Hero): Map<String, Any?> = linkedMapOf(
        "id" to h.id,
        "hero_class" to h.heroClass,
        "level" to h.level,
        "xp" to h.xp,
        "attack" to h.attack,
        "defense" to h.defense,
        "power" to h.power,
        "knowledge" to h.knowledge,
        "secondary" to h.secondary.map { skillMap(it.skill, it.level) },
        "offer" to h.offer.map { skillMap(it.skill, it.level) },
    )

    /** The canonical-JSON tree of the state (Python `asdict`), keys unsorted; [Canonical.encode] sorts them. */
    fun stateMap(s: HeroState): Map<String, Any?> = linkedMapOf(
        "policy" to linkedMapOf<String, Any?>("offer_mode" to s.policy.offerMode, "offer_fill" to s.policy.offerFill),
        "rules" to rulesMap(s.rules),
        "class_def" to classMap(s.classDef),
        "hero" to heroMap(s.hero),
    )

    fun canonical(s: HeroState): ByteArray = Canonical.encode(stateMap(s))

    fun canonicalText(s: HeroState): String = canonical(s).toString(Charsets.US_ASCII)

    fun stateHash(s: HeroState): String = Canonical.hash(stateMap(s))

    /** SHA-256 of the canonical JSON of validated content (Python `content_hash`). */
    fun contentHash(c: HeroContent): String = Canonical.hash(
        linkedMapOf<String, Any?>("rules" to rulesMap(c.rules), "classes" to c.classes.map { classMap(it) }),
    )

    fun findClass(content: HeroContent, classId: String): HeroClass? = content.classes.firstOrNull { it.id == classId }

    /** The hero's named stream `hero:<hero_id>` (Python `hero_rng`). */
    fun heroRng(masterSeed: BigInteger, heroId: String): Pcg32 = RngStreams.derive(masterSeed, "hero:$heroId")

    fun heroRng(masterSeed: Long, heroId: String): Pcg32 = heroRng(BigInteger.valueOf(masterSeed), heroId)

    // ----------------------------------------------------------------------
    // Rules
    // ----------------------------------------------------------------------

    /** Highest level whose XP threshold is reached; the level stays at the table's top beyond it. */
    fun levelForXp(xp: Long, xpTable: List<Long>): Int = xpTable.count { it <= xp }

    /** One draw: index i with probability weights[i] / sum(weights). */
    private fun weightedIndex(rng: HeroDraw, weights: List<Long>): Int {
        var r = rng.range(0L, weights.fold(0L) { a, b -> Math.addExact(a, b) })
        for ((i, w) in weights.withIndex()) {
            if (r < w) return i
            r -= w
        }
        throw IllegalStateException("unreachable")
    }

    /** Up to [n] distinct candidates, weighted, without replacement. */
    private fun draw(rng: HeroDraw, cands: List<SkillOffer>, weight: Map<String, Long>, n: Int): List<SkillOffer> {
        val pool = ArrayList(cands)
        val out = ArrayList<SkillOffer>()
        while (pool.isNotEmpty() && out.size < n) {
            out.add(pool.removeAt(weightedIndex(rng, pool.map { weight.getValue(it.skill) })))
        }
        return out
    }

    private fun offers(state: HeroState, h: Hero, rng: HeroDraw): List<SkillOffer> {
        val rules = state.rules
        val pol = state.policy
        val weight = LinkedHashMap<String, Long>()
        for ((s, w) in state.classDef.secondaryWeights) weight[s] = w
        val held = LinkedHashMap<String, Int>()
        for (s in h.secondary) held[s.skill] = s.level
        val ups = rules.skills
            .filter { it in held && held.getValue(it) < rules.skillLevels && weight.getValue(it) > 0 }
            .map { SkillOffer(it, Math.addExact(held.getValue(it), 1)) }
        var news: List<SkillOffer> = emptyList()
        if (h.secondary.size < rules.maxSecondary) {
            news = rules.skills.filter { it !in held && weight.getValue(it) > 0 }.map { SkillOffer(it, 1) }
        }
        if (pol.offerMode == "weighted_pair") return draw(rng, ups + news, weight, 2)
        if (ups.isNotEmpty() && news.isNotEmpty()) {
            val up = draw(rng, ups, weight, 1)[0]
            val nw = draw(rng, news, weight, 1)[0]
            return listOf(up, nw)
        }
        return draw(rng, if (ups.isNotEmpty()) ups else news, weight, if (pol.offerFill == "other_kind") 2 else 1)
    }

    private fun primaryValue(h: Hero, i: Int): Int = when (i) {
        0 -> h.attack
        1 -> h.defense
        2 -> h.power
        else -> h.knowledge
    }

    private fun withPrimary(h: Hero, i: Int, v: Int): Hero = when (i) {
        0 -> h.copy(attack = v)
        1 -> h.copy(defense = v)
        2 -> h.copy(power = v)
        else -> h.copy(knowledge = v)
    }

    /**
     * Take every level the XP allows, stopping at the first pending offer.
     * Per level, draw order: primary skill, then the offers (upgrade first).
     */
    private fun advance(state: HeroState, rng: HeroDraw, events: MutableList<HeroEvent>): HeroState {
        var h = state.hero
        val rules = state.rules
        val cls = state.classDef
        val target = levelForXp(h.xp, rules.xpTable)
        while (h.offer.isEmpty() && h.level < target) {
            val lvl = Math.addExact(h.level, 1)
            val table = if (lvl >= rules.primaryHighFromLevel) cls.primaryHigh else cls.primaryLow
            val idx = weightedIndex(rng, table)
            h = withPrimary(h.copy(level = lvl), idx, Math.addExact(primaryValue(h, idx), 1))
            events.add(LevelGained(h.id, lvl))
            events.add(PrimaryGained(h.id, PRIMARY[idx], primaryValue(h, idx)))
            val offs = offers(state.copy(hero = h), h, rng)
            if (offs.isNotEmpty()) {
                h = h.copy(offer = offs)
                events.add(SkillOffered(h.id, lvl, offs))
            }
        }
        return state.copy(hero = h)
    }

    // ----------------------------------------------------------------------
    // Setup
    // ----------------------------------------------------------------------

    /**
     * A level-1 hero with 0 XP and the class's starting primary skills. [secondary]: starting
     * (skill, level) pairs, kept in the given order. Errors are [HeroValueError].
     */
    fun createHero(
        heroId: String,
        classId: String,
        content: HeroContent,
        secondary: List<Pair<String, Long>> = emptyList(),
        policy: HeroPolicy = DEFAULT_POLICY,
    ): HeroState {
        val cls = findClass(content, classId)
            ?: throw HeroValueError(HeroValueError.UNKNOWN_CLASS, "unknown hero class ${PyText.repr(classId)}")
        val rules = content.rules
        val sec = ArrayList<SecondarySkill>()
        val seen = LinkedHashSet<String>()
        for ((skill, level) in secondary) {
            if (skill !in rules.skills) {
                throw HeroValueError(HeroValueError.UNKNOWN_SKILL, "unknown skill ${PyText.repr(skill)}")
            }
            if (skill in seen) {
                throw HeroValueError(HeroValueError.DUPLICATE_SKILL, "duplicate skill ${PyText.repr(skill)}")
            }
            if (level < 1L || level > rules.skillLevels.toLong()) {
                throw HeroValueError(HeroValueError.BAD_LEVEL, "bad skill level $level for ${PyText.repr(skill)}")
            }
            seen.add(skill)
            sec.add(SecondarySkill(skill, level.toInt()))
        }
        if (sec.size > rules.maxSecondary) {
            throw HeroValueError(HeroValueError.TOO_MANY, "at most ${rules.maxSecondary} secondary skills")
        }
        val (a, d, p, k) = cls.startPrimary
        return HeroState(policy, rules, cls, Hero(heroId, cls.id, 1, 0L, a, d, p, k, sec))
    }

    // ----------------------------------------------------------------------
    // apply
    // ----------------------------------------------------------------------

    /** Total of non-negative weights, or null when one is negative or the total exceeds [HERO_MAX_INT]. */
    private fun cappedTotal(w: List<Long>): Long? {
        var t = 0L
        for (x in w) {
            if (x < 0L || x > HERO_MAX_INT - t) return null
            t += x
        }
        return t
    }

    /**
     * Raise [IllegalCommand] unless every weight a level-up may draw from is valid. Runs before the
     * first draw, so a bad hand-built state cannot make `rng.range` fail after the stream advanced.
     */
    private fun checkDrawInputs(state: HeroState) {
        val cls = state.classDef
        val rules = state.rules
        for ((name, w) in listOf("primary_low" to cls.primaryLow, "primary_high" to cls.primaryHigh)) {
            val t = if (w.size == PRIMARY.size) cappedTotal(w) else null
            if (t == null || t <= 0L) throw IllegalCommand("class ${PyText.repr(cls.id)}: bad $name weights")
        }
        val sw = cls.secondaryWeights
        if (!(sw.map { it.first } == rules.skills && cappedTotal(sw.map { it.second }) != null)) {
            throw IllegalCommand("class ${PyText.repr(cls.id)}: bad secondary weights")
        }
    }

    private fun validate(state: HeroState, cmd: HeroCommand) {
        val h = state.hero
        if (cmd.hero != h.id) throw IllegalCommand("not hero ${PyText.repr(cmd.hero)}")
        val xp: Long
        when (cmd) {
            is GainXP -> {
                if (cmd.amount <= 0L) throw IllegalCommand("XP amount must be a positive integer")
                if (h.offer.isNotEmpty()) throw IllegalCommand("level-up offer pending: choose a skill first")
                if (cmd.amount > HERO_MAX_INT - h.xp) throw IllegalCommand("XP would exceed $HERO_MAX_INT")
                xp = h.xp + cmd.amount
            }
            is ChooseSkill -> {
                if (h.offer.isEmpty()) throw IllegalCommand("no pending offer")
                if (cmd.index < 0L || cmd.index >= h.offer.size.toLong()) throw IllegalCommand("no such offer ${cmd.index}")
                xp = h.xp
            }
        }
        if (levelForXp(xp, state.rules.xpTable) > h.level) checkDrawInputs(state)
    }

    /**
     * Apply one command. [rng] must be the hero's stream `heroRng(masterSeed, state.hero.id)`.
     * Throws [IllegalCommand] before any draw.
     */
    fun apply(state: HeroState, cmd: HeroCommand, rng: HeroDraw): HeroApplyResult {
        validate(state, cmd)
        var h = state.hero
        val events = ArrayList<HeroEvent>()
        when (cmd) {
            is GainXP -> {
                h = h.copy(xp = h.xp + cmd.amount)
                events.add(XPGained(h.id, cmd.amount, h.xp))
            }
            is ChooseSkill -> {
                val o = h.offer[cmd.index.toInt()]
                val sec = if (o.level == 1) {
                    h.secondary + SecondarySkill(o.skill, 1)
                } else {
                    h.secondary.map { if (it.skill == o.skill) SecondarySkill(it.skill, o.level) else it }
                }
                h = h.copy(secondary = sec, offer = emptyList())
                events.add(SkillLearned(h.id, o.skill, o.level))
            }
        }
        val next = advance(state.copy(hero = h), rng, events)
        return HeroApplyResult(next, events)
    }

    fun apply(state: HeroState, cmd: HeroCommand, rng: Pcg32): HeroApplyResult = apply(state, cmd, rng.asHeroDraw())
}
