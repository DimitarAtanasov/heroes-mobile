package h3.sim

/**
 * Creature content loader: CRTRAITS-style TXT table -> creature records.
 * Port of tools/h3re/h3re/content.py (spec docs/specs/content.md). Python is the oracle.
 *
 * Validation: the Kotlin datapack validator does not exist yet, so the minimal creature
 * checks (ranges mirroring datapack._check_creatures) live in [DefaultCreatureValidator]
 * behind the [CreatureValidator] interface. Swap in the datapack validator when it lands.
 *
 * Known divergences from Python (documented in docs/specs/conformance-txt.md): integers are
 * Long (overflow is reported as a schema error, Python would accept it in `extras`); only
 * ASCII digits are accepted in numeric cells; creature order is by UTF-16 code unit (Python:
 * code point), identical for BMP names.
 */
enum class ContentErrorCategory(val key: String) {
    MAPPING("mapping"), TABLE("table"), HEADER("header"), MISSING_CELL("missing_cell"),
    EMPTY_CELL("empty_cell"), NOT_INTEGER("not_integer"), SCHEMA("schema"),
    DUPLICATE("duplicate"), NO_ROWS("no_rows"),
}

class ContentError(
    val category: ContentErrorCategory,
    val row: Int?,
    val column: String?,
    message: String,
) : IllegalArgumentException(message)

/** A validated creature record; shots == 0 means absent (as in the Python record). */
data class Creature(
    val name: String,
    val hp: Long,
    val speed: Long,
    val attack: Long,
    val defense: Long,
    val dmgMin: Long,
    val dmgMax: Long,
    val shots: Long,
    val flags: Set<String>,
) {
    /** Same key set as the Python dict: flags are present (true) only when set. */
    fun toMap(): Map<String, Any> {
        val m = LinkedHashMap<String, Any>()
        m["name"] = name; m["hp"] = hp; m["speed"] = speed; m["attack"] = attack
        m["defense"] = defense; m["dmg_min"] = dmgMin; m["dmg_max"] = dmgMax
        if (shots != 0L) m["shots"] = shots
        for (f in flags.sorted()) m[f] = true
        return m
    }
}

fun interface CreatureValidator {
    /** Throws [IllegalArgumentException] naming the offending field. */
    fun validate(c: Creature)
}

object DefaultCreatureValidator : CreatureValidator {
    override fun validate(c: Creature) {
        require(c.name.isNotBlank()) { "creatures[0].name: expected non-empty string" }
        fun rng(k: String, v: Long, lo: Long, hi: Long) =
            require(v in lo..hi) { "creatures[0].$k: out of range $lo..$hi" }
        rng("attack", c.attack, 0, 255); rng("defense", c.defense, 0, 255)
        rng("dmg_min", c.dmgMin, 0, 10000); rng("dmg_max", c.dmgMax, 0, 10000)
        // hp floor 0 for CRTRAITS (owner decision 2026-11-02, content.md); creatures.json keeps 1.
        rng("hp", c.hp, 0, 100000); rng("speed", c.speed, 0, 100); rng("shots", c.shots, 0, 1000)
        require(c.dmgMin <= c.dmgMax) { "creatures[0]: dmg_min > dmg_max" }
    }
}

data class MapColumn(
    val name: String, val kind: String, val target: String?, val required: Boolean, val `when`: String?,
)

class CreatureMapping(
    val headerRows: Int,
    val columns: List<MapColumn>,
    val abilitySeparator: String,
    /** normalised ability text -> flag name, or null = known with no flag */
    val abilityFlags: Map<String, String?>,
) {
    companion object {
        val FLAGS: Set<String> = setOf(
            "flyer", "double_wide", "no_enemy_retaliation", "unlimited_retaliation",
            "no_melee_penalty", "no_range_penalty", "strikes_twice", "shoots_twice", "no_morale",
        )

        /**
         * Build from a parsed JSON tree (objects as Map, arrays as List, integers as Number,
         * e.g. MiniJson output). Mirrors content.load_mapping validation.
         */
        fun fromTree(tree: Any?): CreatureMapping {
            fun bad(m: String): Nothing = throw ContentError(ContentErrorCategory.MAPPING, null, null, "mapping: $m")
            val m = tree as? Map<*, *> ?: bad("not an object")
            if ((m["schema_version"] as? Number)?.toLong() != 1L) bad("unsupported schema_version")
            for (k in listOf("header_rows", "columns", "ability_flags")) if (k !in m) bad("missing key $k")
            val hr = (m["header_rows"] as? Number)?.toInt() ?: bad("header_rows not an integer")
            if (hr < 1) bad("header_rows must be at least 1")
            val cols = (m["columns"] as? List<*> ?: bad("columns not a list")).map { c ->
                val o = c as? Map<*, *> ?: bad("column not an object")
                MapColumn(
                    name = o["name"] as? String ?: bad("column without name"),
                    kind = (o["kind"] as? String)?.also { if (it != "str" && it != "int") bad("bad kind $it") }
                        ?: bad("column without kind"),
                    target = o["target"] as? String,
                    required = o["required"] == true,
                    `when` = o["when"] as? String,
                )
            }
            val flags = LinkedHashMap<String, String?>()
            for ((k, v) in m["ability_flags"] as? Map<*, *> ?: bad("ability_flags not an object")) {
                val f = v as? String
                if (v != null && (f == null || f !in FLAGS)) bad("ability_flags[$k]: unknown flag $v")
                flags[Content.norm(k as String)] = f
            }
            return CreatureMapping(hr, cols, m["ability_separator"] as? String ?: ",", flags)
        }
    }
}

/** (row, creature name, ability text) of an ability text with no mapping entry. */
data class UnknownAbility(val row: Int, val name: String, val text: String)

class ContentResult(
    /** Accepted creatures in CRTRAITS file order (data-row index ascending), not by name. */
    val creatures: List<Creature>,
    /** creature name -> columns with no datapack slot; values are Long or String */
    val extras: Map<String, Map<String, Any>>,
    val unknown: List<UnknownAbility>,
    /**
     * creature name -> zero-based data-row index among creature records (header skipped; blank and
     * empty-name rows not counted), in file order. Side map for sprite lookup; not part of any hash.
     */
    val creatureRows: Map<String, Int> = emptyMap(),
    /**
     * Names of accepted creatures with dmg 0/0 (case C): no fixed damage (the attack comes from an
     * ability). Side set, not part of any hash; battle creation still refuses them (it needs
     * dmg_max >= 1), and [Content.battleRoster] leaves them out (owner decision Q5, 2026-11-02).
     */
    val noFixedDamage: Set<String> = emptySet(),
)

object Content {
    /**
     * Battle roster: the accepted creatures in CRTRAITS file order, without the no-fixed-damage
     * creatures (dmg 0/0, [ContentResult.noFixedDamage]); owner decision Q5, 2026-11-02. Weak
     * creatures (dmg_min 0, dmg_max > 0) stay. Pure; does not touch any hash or battle code.
     */
    fun battleRoster(content: ContentResult): List<Creature> =
        content.creatures.filter { it.name !in content.noFixedDamage }

    /** Python str.isspace() set (used by str.strip()). */
    internal fun isPySpace(c: Char): Boolean =
        c in '\u0009'..'\u000d' || c in '\u001c'..' ' || c == '\u0085' || c == ' ' ||
            c == ' ' || c in ' '..' ' || c == ' ' || c == ' ' ||
            c == ' ' || c == ' ' || c == '　'

    internal fun pyStrip(s: String): String {
        var a = 0
        var b = s.length
        while (a < b && isPySpace(s[a])) a++
        while (b > a && isPySpace(s[b - 1])) b--
        return s.substring(a, b)
    }

    /** lowercase, whitespace runs collapsed to one space, ends stripped */
    internal fun norm(s: String): String {
        val sb = StringBuilder()
        var pendingSpace = false
        for (ch in pyStrip(s).lowercase()) {
            if (isPySpace(ch)) pendingSpace = true
            else {
                if (pendingSpace) sb.append(' ')
                pendingSpace = false
                sb.append(ch)
            }
        }
        return sb.toString()
    }

    /**
     * Python int(str) for ASCII input: optional sign, digits with single underscores between
     * digits. Overflow saturates to Long.MIN/MAX (always outside every schema range).
     */
    private fun pyInt(s: String): Long? {
        var i = 0
        var neg = false
        if (i < s.length && (s[i] == '+' || s[i] == '-')) { neg = s[i] == '-'; i++ }
        if (i >= s.length) return null
        var acc = 0L
        var sat = false
        var prevDigit = false
        while (i < s.length) {
            val c = s[i]
            if (c in '0'..'9') {
                val d = (c - '0').toLong()
                if (!sat) {
                    if (acc > (Long.MAX_VALUE - d) / 10) sat = true else acc = acc * 10 + d
                }
                prevDigit = true
            } else if (c == '_' && prevDigit) {
                prevDigit = false
            } else return null
            i++
        }
        if (!prevDigit) return null
        return if (sat) (if (neg) Long.MIN_VALUE else Long.MAX_VALUE) else if (neg) -acc else acc
    }

    fun parseCreatures(
        data: ByteArray,
        mapping: CreatureMapping,
        roe: Boolean = false,
        encoding: String = Txt.DEFAULT_ENCODING,
        validator: CreatureValidator = DefaultCreatureValidator,
    ): ContentResult {
        val t = try {
            Txt.parse(data, mapping.headerRows, encoding = encoding)
        } catch (e: TxtError) {
            throw ContentError(ContentErrorCategory.TABLE, null, null, "table: ${e.message}")
        }
        if (t.header.size < mapping.headerRows) {
            throw ContentError(ContentErrorCategory.HEADER, null, null, "table: fewer than ${mapping.headerRows} header rows")
        }
        val h = t.header.last().map { pyStrip(it).lowercase() }
        if (h.size < 2 || h[0] != "singular" || h[1] != "plural") {
            throw ContentError(ContentErrorCategory.HEADER, null, null,
                "header row ${t.header.size}: expected Singular, Plural")
        }
        val plural2 = h.size > 2 && h[2] == "plural2"
        val cols = mapping.columns.filter {
            !(it.`when` == "plural2" && !plural2) && !(it.`when` == "not_roe" && roe)
        }

        val records = ArrayList<Creature>()
        val extras = LinkedHashMap<String, Map<String, Any>>()
        val rowNo = HashMap<String, Int>()
        val creatureRows = LinkedHashMap<String, Int>()
        val noFixedDamage = LinkedHashSet<String>()
        val unknown = ArrayList<UnknownAbility>()
        for ((i, row) in t.rows.withIndex()) {
            val r = i + 1 + mapping.headerRows
            if (row.none { pyStrip(it).isNotEmpty() }) continue
            if (pyStrip(row[0]).isEmpty()) continue
            val num = HashMap<String, Long>()
            val ex = LinkedHashMap<String, Any>()
            var name = ""
            var abil = ""
            for ((j, c) in cols.withIndex()) {
                val where = "row $r, column '${c.name}' (index $j)"
                if (j >= row.size) {
                    if (c.required) throw ContentError(ContentErrorCategory.MISSING_CELL, r, c.name, "$where: missing cell")
                    continue
                }
                val cell = row[j]
                val v: Any
                if (c.kind == "str") {
                    val s = pyStrip(cell)
                    if (c.required && s.isEmpty()) throw ContentError(ContentErrorCategory.EMPTY_CELL, r, c.name, "$where: empty")
                    v = s
                } else {
                    val s = pyStrip(cell)
                    if (c.required && s.isEmpty()) throw ContentError(ContentErrorCategory.EMPTY_CELL, r, c.name, "$where: empty")
                    v = if (s.isEmpty()) 0L else pyInt(s)
                        ?: throw ContentError(ContentErrorCategory.NOT_INTEGER, r, c.name,
                            "$where: not an integer: '${s.take(40)}'")
                }
                val tg = c.target ?: continue
                when {
                    tg == "abilities" -> abil = v as String
                    tg.startsWith("extra:") -> ex[tg.substring(6)] = v
                    tg == "name" -> name = v as String
                    else -> num[tg] = v as Long
                }
            }
            val flags = java.util.TreeSet<String>()
            for (a in abil.split(mapping.abilitySeparator)) {
                val key = norm(a)
                if (key.isEmpty()) continue
                if (!mapping.abilityFlags.containsKey(key)) unknown.add(UnknownAbility(r, name, pyStrip(a)))
                else mapping.abilityFlags[key]?.let { flags.add(it) }
            }
            val rec = Creature(
                name = name, hp = num["hp"] ?: 0, speed = num["speed"] ?: 0, attack = num["attack"] ?: 0,
                defense = num["defense"] ?: 0, dmgMin = num["dmg_min"] ?: 0, dmgMax = num["dmg_max"] ?: 0,
                shots = num["shots"] ?: 0, flags = flags,
            )
            try {
                validator.validate(rec)
            } catch (e: IllegalArgumentException) {
                throw ContentError(ContentErrorCategory.SCHEMA, r, null, "row $r: ${e.message}")
            }
            if (name in extras) {
                throw ContentError(ContentErrorCategory.DUPLICATE, r, "singular",
                    "row $r, column 'singular': duplicate name '$name' (first at row ${rowNo[name]})")
            }
            extras[name] = ex
            rowNo[name] = r
            creatureRows[name] = records.size
            if (rec.dmgMax == 0L) noFixedDamage.add(name)
            records.add(rec)
        }
        if (records.isEmpty()) throw ContentError(ContentErrorCategory.NO_ROWS, null, null, "table: no creature rows")
        return ContentResult(records, extras, unknown, creatureRows, noFixedDamage)
    }
}
