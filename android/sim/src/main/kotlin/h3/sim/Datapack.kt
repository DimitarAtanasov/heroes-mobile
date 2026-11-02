package h3.sim

import java.math.BigInteger

/**
 * Data-pack loader: a port of `tools/h3re/h3re/datapack.py` (docs/specs/datapack.md, ADR-0004).
 *
 * Strict validation of `rules.json`, `battle_policy.json` and `creatures.json` from their text:
 * unknown or missing keys, floats (any number literal with `.`/`e`/`E`, and NaN/Infinity), bool used
 * as an integer, integers above [MAX_INT] (2^31 - 1), enums, array shapes, duplicate JSON keys.
 * Errors are [DatapackError]; the message is the Python `DataPackError` text, naming the failing
 * path, and [DatapackError.category] classifies it (see [Category]). Ordering is deterministic
 * (creatures sorted by name, `hates` sorted) and each pack carries a content hash: SHA-256 of the
 * canonical JSON of the validated pack, identical to Python's `content_hash`.
 */
class DatapackError(val category: String, message: String) : IllegalArgumentException(message)

/** Error categories; the same strings appear in `vectors/datapack.json`. */
object Category {
    const val INVALID_JSON = "invalid_json"
    const val DUPLICATE_KEY = "duplicate_key"
    const val FLOAT = "float"
    const val TYPE = "type"
    const val UNKNOWN_KEY = "unknown_key"
    const val MISSING_KEY = "missing_key"
    const val RANGE = "range"
    const val LENGTH = "length"
    const val ENUM = "enum"
    const val SCHEMA_VERSION = "schema_version"
    const val TABLE = "table"
    const val DISTINCT = "distinct"
    const val DMG_ORDER = "dmg_order"
    const val DUPLICATE_NAME = "duplicate_name"
    const val UNKNOWN_CREATURE = "unknown_creature"
    const val EMPTY = "empty"
}

/** Validated `rules.json`: the [RulesPack] and its content hash (Python `load_rules_pack(...).content_hash`). */
class RulesDoc(val pack: RulesPack, val canonical: Map<String, Any?>, val contentHash: String)

/** Validated `battle_policy.json`. [values] has every file key; `placement_rows` is a list of int lists. */
class PolicyDoc(val values: Map<String, Any?>, val contentHash: String) {
    /** The policy defaults, using [rules]'s `bad_morale_numerators` as the default bad-morale table. */
    fun battlePolicyPack(rules: RulesDoc): BattlePolicyPack =
        BattlePolicyPack(values, rules.pack.badMoraleNumerators.map { Math.toIntExact(it) })
}

/** Validated `creatures.json`: creatures sorted by name, plus their canonical maps (only keys present in the file). */
class CreaturesDoc(val creatures: List<BattleCreature>, val canonical: List<Map<String, Any?>>)

class Datapack(val rules: RulesDoc, val policy: PolicyDoc, val creatures: CreaturesDoc) {
    /** Python `DataPack.content_hash`: rules plus creatures. */
    val packHash: String get() = Datapack.packHash(rules, creatures)

    companion object {
        const val MAX_INT: Long = (1L shl 31) - 1
        private const val SCHEMA_VERSION = 1L
        private const val MAX_ROW = 10L

        val POLICY_CHOICES: Map<String, List<String>> = mapOf(
            "row_offset" to listOf("odd", "even"),
            "speed_tie" to listOf("attacker_first", "alternate", "alternate_last_mover"),
            "wait_order" to listOf("reverse_speed", "speed", "fifo", "slow_first_alternate"),
            "defend_bonus_rounding" to listOf("floor", "ceil"),
            "range_origin" to listOf("head", "any_cell"),
        )

        private val FRACS = listOf(
            "ad_bonus_per_point", "ad_bonus_cap", "da_penalty_per_point", "da_penalty_cap",
            "hate_bonus", "luck_bonus", "half",
        )
        private val FRAC_TABLES = listOf("offense", "archery", "armorer")
        private val INT_TABLES = listOf("bad_morale_numerators", "vcmi_bad_morale_numerators")
        private val POLICY_BOOLS = listOf(
            "edge_columns_walkable", "good_morale_after_wait", "good_morale_after_defend",
            "repeat_good_morale", "bad_morale_on_wait_activation", "good_morale_on_wait_activation",
            "bad_luck",
        )
        private val POLICY_INTS = listOf(
            Triple("defend_bonus_num", 0L, MAX_INT), Triple("defend_bonus_den", 1L, MAX_INT),
            Triple("defend_bonus_min", 0L, MAX_INT), Triple("range_penalty_beyond", 0L, 1000L),
        )
        private val POLICY_ENUMS = listOf(
            "row_offset", "speed_tie", "wait_order", "defend_bonus_rounding", "range_origin",
        )
        private val CR_REQ = listOf("name", "attack", "defense", "dmg_min", "dmg_max", "hp", "speed")
        private val CR_FLAGS = listOf(
            "flyer", "double_wide", "no_enemy_retaliation", "unlimited_retaliation",
            "no_melee_penalty", "no_range_penalty", "strikes_twice", "shoots_twice", "no_morale",
        )
        private val CR_OPT = CR_FLAGS + listOf("shots", "hates")
        private val CR_INTS = listOf(
            Triple("attack", 0L, 255L), Triple("defense", 0L, 255L), Triple("dmg_min", 1L, 10000L),
            Triple("dmg_max", 1L, 10000L), Triple("hp", 1L, 100000L), Triple("speed", 0L, 100L),
            Triple("shots", 0L, 1000L),
        )

        // ---------------------------------------------------------------- public API

        fun parseRules(text: String, what: String = "rules.json"): RulesDoc = checkRules(PackJson.parse(text, what))

        fun parsePolicy(text: String, what: String = "battle_policy.json"): PolicyDoc =
            checkPolicy(PackJson.parse(text, what))

        fun parseCreatures(text: String, what: String = "creatures.json"): CreaturesDoc =
            checkCreatures(PackJson.parse(text, what))

        fun load(rulesText: String, policyText: String, creaturesText: String): Datapack =
            Datapack(parseRules(rulesText), parsePolicy(policyText), parseCreatures(creaturesText))

        /** Python `DataPack(rules, creatures).content_hash`. */
        fun packHash(rules: RulesDoc, creatures: CreaturesDoc): String =
            Canonical.hash(mapOf("creatures" to creatures.canonical, "rules" to rules.canonical))

        // ---------------------------------------------------------------- helpers

        private fun err(category: String, msg: String): Nothing = throw DatapackError(category, msg)

        private fun typeName(v: Any?): String = when (v) {
            null -> "NoneType"
            is Boolean -> "bool"
            is BigInteger -> "int"
            is String -> "str"
            is List<*> -> "list"
            is Map<*, *> -> "dict"
            else -> v::class.simpleName ?: "object"
        }

        private fun int(v: Any?, path: String, lo: Long, hi: Long): Long {
            if (v !is BigInteger) err(Category.TYPE, "$path: expected integer, got ${typeName(v)}")
            if (v < BigInteger.valueOf(lo) || v > BigInteger.valueOf(hi)) {
                err(Category.RANGE, "$path: $v out of range $lo..$hi")
            }
            return v.toLong()
        }

        private fun obj(v: Any?, path: String, required: List<String>, optional: List<String> = emptyList()): Map<String, Any?> {
            if (v !is Map<*, *>) err(Category.TYPE, "$path: expected object")
            @Suppress("UNCHECKED_CAST")
            val m = v as Map<String, Any?>
            val unknown = (m.keys - required.toSet() - optional.toSet()).sortedWith(PackJson.codePointOrder)
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

        private fun frac(v: Any?, path: String): Pair<Long, Long> {
            val a = list(v, path, 2)
            return Pair(int(a[0], "$path[0]", 0, MAX_INT), int(a[1], "$path[1]", 1, MAX_INT))
        }

        /** a/b <= c/d on positive denominators; products fit in Long (each part < 2^31). */
        private fun fracLe(a: Pair<Long, Long>, b: Pair<Long, Long>): Boolean = a.first * b.second <= b.first * a.second

        private fun schemaVersion(d: Map<String, Any?>, prefix: String) {
            if (int(d["schema_version"], "$prefix.schema_version", 0, MAX_INT) != SCHEMA_VERSION) {
                err(Category.SCHEMA_VERSION, "$prefix.schema_version: unsupported")
            }
        }

        private fun r(f: Pair<Long, Long>): Rational = Rational.of(f.first, f.second)
        private fun fl(f: Pair<Long, Long>): List<Any?> = listOf(f.first, f.second)

        // ---------------------------------------------------------------- rules

        private fun checkRules(d: Any?): RulesDoc {
            val m = obj(d, "rules", FRACS + FRAC_TABLES + INT_TABLES + listOf("morale_die", "schema_version"))
            schemaVersion(m, "rules")
            val die = int(m["morale_die"], "rules.morale_die", 1, 1000)
            val canon = linkedMapOf<String, Any?>("schema_version" to SCHEMA_VERSION, "morale_die" to die)
            val fr = HashMap<String, Pair<Long, Long>>()
            for (k in FRACS) {
                val f = frac(m[k], "rules.$k")
                fr[k] = f
                canon[k] = fl(f)
            }
            val ft = HashMap<String, List<Pair<Long, Long>>>()
            for (k in FRAC_TABLES) {
                val rows = list(m[k], "rules.$k", 4)
                val tab = rows.mapIndexed { i, x -> frac(x, "rules.$k[$i]") }
                if (tab[0] != Pair(0L, 1L)) err(Category.TABLE, "rules.$k[0]: level 0 must be [0, 1]")
                if (!tab.zipWithNext().all { (a, b) -> fracLe(a, b) }) {
                    err(Category.TABLE, "rules.$k: must be non-decreasing")
                }
                ft[k] = tab
                canon[k] = tab.map { fl(it) }
            }
            val it = HashMap<String, List<Long>>()
            for (k in INT_TABLES) {
                val rows = list(m[k], "rules.$k", 3)
                val tab = rows.mapIndexed { i, x -> int(x, "rules.$k[$i]", 0, die) }
                if (!tab.zipWithNext().all { (a, b) -> a <= b }) err(Category.TABLE, "rules.$k: must be non-decreasing")
                it[k] = tab
                canon[k] = tab
            }
            val pack = RulesPack(
                adBonusPerPoint = r(fr.getValue("ad_bonus_per_point")),
                adBonusCap = r(fr.getValue("ad_bonus_cap")),
                daPenaltyPerPoint = r(fr.getValue("da_penalty_per_point")),
                daPenaltyCap = r(fr.getValue("da_penalty_cap")),
                offense = ft.getValue("offense").map { r(it) },
                archery = ft.getValue("archery").map { r(it) },
                armorer = ft.getValue("armorer").map { r(it) },
                hateBonus = r(fr.getValue("hate_bonus")),
                luckBonus = r(fr.getValue("luck_bonus")),
                half = r(fr.getValue("half")),
                moraleDie = die,
                badMoraleNumerators = it.getValue("bad_morale_numerators"),
                vcmiBadMoraleNumerators = it.getValue("vcmi_bad_morale_numerators"),
            )
            return RulesDoc(pack, canon, Canonical.hash(mapOf("creatures" to emptyList<Any?>(), "rules" to canon)))
        }

        // ---------------------------------------------------------------- battle policy

        private fun checkPolicy(d: Any?): PolicyDoc {
            val keys = POLICY_BOOLS + POLICY_INTS.map { it.first } + POLICY_ENUMS + listOf("placement_rows", "schema_version")
            val m = obj(d, "battle_policy", keys)
            schemaVersion(m, "battle_policy")
            val out = linkedMapOf<String, Any?>("schema_version" to SCHEMA_VERSION)
            for (k in POLICY_BOOLS) {
                val v = m[k]
                if (v !is Boolean) err(Category.TYPE, "battle_policy.$k: expected boolean")
                out[k] = v
            }
            for ((k, lo, hi) in POLICY_INTS) out[k] = int(m[k], "battle_policy.$k", lo, hi)
            for (k in POLICY_ENUMS) {
                val v = m[k]
                val choices = POLICY_CHOICES.getValue(k)
                if (v !is String || v !in choices) {
                    err(Category.ENUM, "battle_policy.$k: expected one of ${choices.joinToString(", ")}")
                }
                out[k] = v
            }
            val rows = list(m["placement_rows"], "battle_policy.placement_rows", 7)
            val table = rows.mapIndexed { i, row ->
                val p = "battle_policy.placement_rows[$i]"
                val cells = list(row, p, i + 1).mapIndexed { j, x -> int(x, "$p[$j]", 0, MAX_ROW) }
                if (cells.toSet().size != cells.size) err(Category.DISTINCT, "$p: rows must be distinct")
                cells.map { Math.toIntExact(it) }
            }
            out["placement_rows"] = table
            return PolicyDoc(out, Canonical.hash(mapOf("battle_policy" to out)))
        }

        // ---------------------------------------------------------------- creatures

        private fun checkCreatures(d: Any?): CreaturesDoc {
            val top = obj(d, "creatures", listOf("schema_version", "creatures"))
            schemaVersion(top, "creatures")
            val items = list(top["creatures"], "creatures.creatures")
            if (items.isEmpty()) err(Category.EMPTY, "creatures.creatures: must not be empty")
            val out = LinkedHashMap<String, Map<String, Any?>>()
            items.forEachIndexed { i, c ->
                val p = "creatures[$i]"
                val cm = obj(c, p, CR_REQ, CR_OPT)
                val name = cm["name"]
                if (name !is String || name.isBlank()) err(Category.TYPE, "$p.name: expected non-empty string")
                if (name in out) err(Category.DUPLICATE_NAME, "$p.name: duplicate ${PackJson.pyRepr(name)}")
                val r = linkedMapOf<String, Any?>("name" to name)
                for ((k, lo, hi) in CR_INTS) {
                    if (k in cm || k in CR_REQ) r[k] = int(cm[k], "$p.$k", lo, hi)
                }
                if ((r["dmg_min"] as Long) > (r["dmg_max"] as Long)) err(Category.DMG_ORDER, "$p: dmg_min > dmg_max")
                for (k in CR_FLAGS) {
                    if (k in cm) {
                        val v = cm[k]
                        if (v !is Boolean) err(Category.TYPE, "$p.$k: expected boolean")
                        r[k] = v
                    }
                }
                if ("hates" in cm) {
                    val h = list(cm["hates"], "$p.hates")
                    if (h.any { it !is String } || h.toSet().size != h.size) {
                        err(Category.TYPE, "$p.hates: expected unique strings")
                    }
                    r["hates"] = h.map { it as String }.sortedWith(PackJson.codePointOrder)
                }
                out[name] = r
            }
            for ((name, r) in out) {
                @Suppress("UNCHECKED_CAST")
                for (h in (r["hates"] as List<String>? ?: emptyList())) {
                    if (h !in out) err(Category.UNKNOWN_CREATURE, "creatures.$name.hates: unknown creature ${PackJson.pyRepr(h)}")
                }
            }
            val canon = out.keys.sortedWith(PackJson.codePointOrder).map { out.getValue(it) }
            val built = canon.map { r ->
                fun i(k: String) = Math.toIntExact(r[k] as Long)
                fun b(k: String) = r[k] as Boolean? ?: false
                @Suppress("UNCHECKED_CAST")
                BattleCreature(
                    name = r["name"] as String, attack = i("attack"), defense = i("defense"),
                    dmgMin = i("dmg_min"), dmgMax = i("dmg_max"), hp = i("hp"), speed = i("speed"),
                    shots = if ("shots" in r) i("shots") else 0,
                    flyer = b("flyer"), doubleWide = b("double_wide"),
                    noEnemyRetaliation = b("no_enemy_retaliation"),
                    unlimitedRetaliation = b("unlimited_retaliation"),
                    noMeleePenalty = b("no_melee_penalty"), noRangePenalty = b("no_range_penalty"),
                    strikesTwice = b("strikes_twice"), shootsTwice = b("shoots_twice"),
                    noMorale = b("no_morale"), hates = r["hates"] as List<String>? ?: emptyList(),
                )
            }
            return CreaturesDoc(built, canon)
        }
    }
}

/** Strict JSON reader for packs: integers as BigInteger, floats and duplicate keys rejected (Python `_loads`). */
object PackJson {
    /** Unicode code point order (Python str ordering). */
    val codePointOrder = Comparator<String> { a, b ->
        var i = 0
        var j = 0
        while (i < a.length && j < b.length) {
            val ca = a.codePointAt(i)
            val cb = b.codePointAt(j)
            if (ca != cb) return@Comparator ca.compareTo(cb)
            i += Character.charCount(ca)
            j += Character.charCount(cb)
        }
        (a.length - i).compareTo(b.length - j)
    }

    /** Python `repr` of a str, for the common cases (printable text). */
    fun pyRepr(s: String): String {
        val q = if ('\'' in s && '"' !in s) '"' else '\''
        val sb = StringBuilder().append(q)
        for (c in s) {
            when {
                c == '\\' -> sb.append("\\\\")
                c == q -> sb.append('\\').append(c)
                c == '\n' -> sb.append("\\n")
                c == '\r' -> sb.append("\\r")
                c == '\t' -> sb.append("\\t")
                else -> sb.append(c)
            }
        }
        return sb.append(q).toString()
    }

    fun parse(text: String, what: String): Any? {
        val p = P(text, what)
        try {
            val v = p.value()
            p.ws()
            if (p.i != text.length) p.bad("extra data")
            return v
        } catch (e: DatapackError) {
            throw e
        } catch (e: StackOverflowError) {
            throw DatapackError(Category.INVALID_JSON, "$what: invalid JSON: nesting too deep")
        }
    }

    private class P(val s: String, val what: String) {
        var i = 0

        fun bad(msg: String): Nothing = throw DatapackError(Category.INVALID_JSON, "$what: invalid JSON: $msg at $i")

        fun ws() {
            while (i < s.length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) i++
        }

        fun value(): Any? {
            ws()
            if (i >= s.length) bad("unexpected end")
            return when (val c = s[i]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> lit("true", true)
                'f' -> lit("false", false)
                'n' -> lit("null", null)
                'N' -> lit("NaN", null).also { floatErr("NaN") }
                'I' -> lit("Infinity", null).also { floatErr("Infinity") }
                else -> {
                    if (c == '-' && s.startsWith("-Infinity", i)) floatErr("-Infinity")
                    num()
                }
            }
        }

        fun floatErr(lit: String): Nothing =
            throw DatapackError(Category.FLOAT, "$what: floats are not allowed (got $lit)")

        fun lit(word: String, v: Any?): Any? {
            if (!s.startsWith(word, i)) bad("bad literal")
            i += word.length
            return v
        }

        fun num(): Any? {
            val st = i
            if (i < s.length && s[i] == '-') i++
            if (i >= s.length || !s[i].isAsciiDigit()) bad("bad number")
            if (s[i] == '0') i++ else while (i < s.length && s[i].isAsciiDigit()) i++
            var isFloat = false
            if (i < s.length && s[i] == '.') {
                val save = i
                i++
                if (i >= s.length || !s[i].isAsciiDigit()) { i = save } else {
                    while (i < s.length && s[i].isAsciiDigit()) i++
                    isFloat = true
                }
            }
            if (i < s.length && (s[i] == 'e' || s[i] == 'E')) {
                val save = i
                i++
                if (i < s.length && (s[i] == '+' || s[i] == '-')) i++
                if (i >= s.length || !s[i].isAsciiDigit()) { i = save } else {
                    while (i < s.length && s[i].isAsciiDigit()) i++
                    isFloat = true
                }
            }
            val lit = s.substring(st, i)
            if (isFloat) floatErr(lit)
            return BigInteger(lit)
        }

        fun Char.isAsciiDigit() = this in '0'..'9'

        fun str(): String {
            i++
            val sb = StringBuilder()
            while (true) {
                if (i >= s.length) bad("unterminated string")
                val c = s[i++]
                when {
                    c == '"' -> return sb.toString()
                    c < ' ' -> bad("control character in string")
                    c == '\\' -> {
                        if (i >= s.length) bad("unterminated string")
                        when (val e = s[i++]) {
                            '"' -> sb.append('"')
                            '\\' -> sb.append('\\')
                            '/' -> sb.append('/')
                            'b' -> sb.append('\b')
                            'f' -> sb.append('\u000c')
                            'n' -> sb.append('\n')
                            'r' -> sb.append('\r')
                            't' -> sb.append('\t')
                            'u' -> {
                                if (i + 4 > s.length) bad("bad \\u escape")
                                val h = s.substring(i, i + 4)
                                if (!h.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' }) bad("bad \\u escape")
                                sb.append(h.toInt(16).toChar())
                                i += 4
                            }
                            else -> bad("bad escape \\$e")
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
                ws()
                if (i >= s.length || s[i] != '"') bad("expected key")
                val k = str()
                ws()
                if (i >= s.length || s[i] != ':') bad("expected ':'")
                i++
                val v = value()
                if (k in m) throw DatapackError(Category.DUPLICATE_KEY, "$what: $what: duplicate key ${pyRepr(k)}")
                m[k] = v
                ws()
                if (i >= s.length) bad("unterminated object")
                when (s[i++]) {
                    '}' -> return m
                    ',' -> {}
                    else -> bad("expected ',' or '}'")
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
                if (i >= s.length) bad("unterminated array")
                when (s[i++]) {
                    ']' -> return l
                    ',' -> {}
                    else -> bad("expected ',' or ']'")
                }
            }
        }
    }
}
