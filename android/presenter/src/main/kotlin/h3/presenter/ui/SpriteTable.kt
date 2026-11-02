package h3.presenter.ui

import h3.sim.DatapackError
import h3.sim.PackJson
import java.math.BigInteger

/**
 * Parser for the owner-written creature-to-DEF table `data/sprite_map.json` (sprite-atlas.md,
 * "Creature sprite table (0.2)"; android-app.md section 14 Q2 option (a)). Pure: the caller reads the
 * file and passes its text; nothing here touches a file, a clock or the environment, and the repo
 * ships no entries. Bad input never throws: it comes back as [SpriteTableResult.Failed] with stable
 * [SpriteTableError.code]s. The result is all or nothing, so a half-valid table is never used.
 *
 * The table is keyed by `row`: the zero-based position of the creature among the accepted creature
 * records of `CRTRAITS.TXT` (header, blank rows and empty-first-cell rows not counted; ADR-0014), equal to
 * the VCMI creature index. The output is row
 * to DEF member name, in file order. JSON is read with [PackJson], the strict reader the data packs
 * use (integers only, duplicate object keys rejected).
 */
sealed class SpriteTableError {
    abstract val code: String
    abstract fun describe(): String

    /** The text is not valid strict JSON (also: floats, duplicate object keys). [detail] names the cause. */
    data class InvalidJson(val detail: String) : SpriteTableError() {
        override val code get() = "INVALID_JSON"
        override fun describe() = "$code: $detail"
    }

    /** `schema_version` is not an integer, or not a version this build reads. */
    data class BadSchemaVersion(val detail: String) : SpriteTableError() {
        override val code get() = "BAD_SCHEMA_VERSION"
        override fun describe() = "$code: $detail"
    }

    /** A wrong type, a missing key or an unknown key at [path] (for example `entries[2].def`). */
    data class BadShape(val path: String, val detail: String) : SpriteTableError() {
        override val code get() = "BAD_SHAPE"
        override fun describe() = "$code $path: $detail"
    }

    /** `row` of the entry at [index] is not a non-negative integer that fits an Int. */
    data class BadRow(val index: Int, val detail: String) : SpriteTableError() {
        override val code get() = "BAD_ROW"
        override fun describe() = "$code entries[$index]: $detail"
    }

    /** The entry has an empty or blank `source` (ADR-0003: every fact cites its source). */
    data class MissingSource(val index: Int, val row: Int) : SpriteTableError() {
        override val code get() = "MISSING_SOURCE"
        override fun describe() = "$code entries[$index]: row $row"
    }

    /** [row] appears in more than one entry; [index] is the later one. */
    data class DuplicateRow(val index: Int, val row: Int) : SpriteTableError() {
        override val code get() = "DUPLICATE_ROW"
        override fun describe() = "$code entries[$index]: row $row"
    }

    /** `def` does not end in `.DEF` (exact case) or has nothing before the extension. */
    data class BadDefName(val index: Int, val row: Int, val def: String) : SpriteTableError() {
        override val code get() = "BAD_DEF_NAME"
        override fun describe() = "$code entries[$index]: row $row: $def"
    }

    /** `def` contains a path separator (`/` or `\`): it must be a bare archive member name. */
    data class DefHasPath(val index: Int, val row: Int, val def: String) : SpriteTableError() {
        override val code get() = "DEF_HAS_PATH"
        override fun describe() = "$code entries[$index]: row $row: $def"
    }
}

/** Outcome of [SpriteTable.parse]: the table, or every error found (never both). */
sealed class SpriteTableResult {
    /** [table] maps row to DEF member name, in file order; sources are validated, not kept. */
    class Ok(val table: Map<Int, String>) : SpriteTableResult()

    class Failed(val errors: List<SpriteTableError>) : SpriteTableResult()
}

object SpriteTable {
    /** The only `schema_version` this build reads. */
    const val SCHEMA_VERSION = 2L

    private val TOP_KEYS = listOf("schema_version", "entries")
    private val ENTRY_KEYS = listOf("row", "def", "source")
    private const val DEF_EXT = ".DEF"

    fun parse(text: String): SpriteTableResult {
        val tree = try {
            PackJson.parse(text, "sprite_map.json")
        } catch (e: DatapackError) {
            return fail(SpriteTableError.InvalidJson("${e.category}: ${e.message}"))
        }

        val top = tree as? Map<*, *> ?: return fail(SpriteTableError.BadShape("$", "expected object"))
        keyErrors(top, "$", TOP_KEYS)?.let { return SpriteTableResult.Failed(it) }

        val version = top["schema_version"]
        if (version !is BigInteger) {
            return fail(SpriteTableError.BadSchemaVersion("expected integer $SCHEMA_VERSION"))
        }
        if (version != BigInteger.valueOf(SCHEMA_VERSION)) {
            return fail(SpriteTableError.BadSchemaVersion("unsupported $version, expected $SCHEMA_VERSION"))
        }

        val entries = top["entries"] as? List<*>
            ?: return fail(SpriteTableError.BadShape("entries", "expected array"))

        val errors = ArrayList<SpriteTableError>()
        val table = LinkedHashMap<Int, String>()
        for ((i, raw) in entries.withIndex()) {
            val path = "entries[$i]"
            val e = raw as? Map<*, *>
            if (e == null) {
                errors.add(SpriteTableError.BadShape(path, "expected object"))
                continue
            }
            val keyErr = keyErrors(e, path, ENTRY_KEYS)
            if (keyErr != null) {
                errors.addAll(keyErr)
                continue
            }
            val rowRaw = e["row"]
            val def = e["def"]
            val source = e["source"]
            var typed = true
            for ((k, v) in listOf("def" to def, "source" to source)) {
                if (v !is String) {
                    errors.add(SpriteTableError.BadShape("$path.$k", "expected string"))
                    typed = false
                }
            }
            val row = rowOf(rowRaw)
            if (row == null) {
                errors.add(SpriteTableError.BadRow(i, "expected non-negative integer, got $rowRaw"))
                typed = false
            }
            if (!typed) continue
            row as Int
            def as String
            source as String

            var ok = true
            if (source.isBlank()) {
                errors.add(SpriteTableError.MissingSource(i, row))
                ok = false
            }
            if ('/' in def || '\\' in def) {
                errors.add(SpriteTableError.DefHasPath(i, row, def))
                ok = false
            } else if (!def.endsWith(DEF_EXT) || def.length == DEF_EXT.length) {
                errors.add(SpriteTableError.BadDefName(i, row, def))
                ok = false
            }
            if (ok && row in table) {
                errors.add(SpriteTableError.DuplicateRow(i, row))
                ok = false
            }
            if (ok) table[row] = def
        }
        return if (errors.isEmpty()) SpriteTableResult.Ok(table) else SpriteTableResult.Failed(errors)
    }

    /** [raw] as a row, or null unless it is an integer in 0..Int.MAX_VALUE. */
    private fun rowOf(raw: Any?): Int? {
        if (raw !is BigInteger || raw.signum() < 0 || raw > BigInteger.valueOf(Int.MAX_VALUE.toLong())) return null
        return raw.toInt()
    }

    private fun fail(e: SpriteTableError) = SpriteTableResult.Failed(listOf(e))

    /** Unknown and missing keys of [m] against [keys], or null when the key set is exactly [keys]. */
    private fun keyErrors(m: Map<*, *>, path: String, keys: List<String>): List<SpriteTableError>? {
        val out = ArrayList<SpriteTableError>()
        for (k in m.keys.map { it as String }.sortedWith(PackJson.codePointOrder)) {
            if (k !in keys) out.add(SpriteTableError.BadShape(path, "unknown key $k"))
        }
        for (k in keys) if (k !in m) out.add(SpriteTableError.BadShape(path, "missing key $k"))
        return if (out.isEmpty()) null else out
    }
}
