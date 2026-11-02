package h3.sim

import java.math.BigInteger
import java.security.MessageDigest

/**
 * Canonical JSON (ADR-0001). Byte-identical to Python
 * `json.dumps(v, sort_keys=True, separators=(",", ":")).encode("utf-8")`
 * with the default `ensure_ascii=True`: output is pure ASCII, non-ASCII
 * characters become lowercase `\uXXXX` (UTF-16 units, so astral characters
 * are surrogate pairs), keys are sorted by Unicode code point.
 *
 * Accepted values: null, Boolean, Int, Long, BigInteger, String,
 * List/Array-free collections (List), Map with String keys. Floats and
 * anything else are rejected (ADR-0002).
 */
object Canonical {
    fun encode(value: Any?): ByteArray = StringBuilder().also { write(value, it) }.toString().toByteArray(Charsets.US_ASCII)

    fun hash(value: Any?): String = sha256Hex(encode(value))

    fun sha256Hex(data: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(data).toHex()

    fun ByteArray.toHex(): String {
        val sb = StringBuilder(size * 2)
        for (b in this) {
            val v = b.toInt() and 0xff
            sb.append(HEX[v shr 4]).append(HEX[v and 15])
        }
        return sb.toString()
    }

    private const val HEX = "0123456789abcdef"

    /** Order by Unicode code point (Python str ordering), not UTF-16 code unit. */
    internal val codePointOrder = Comparator<String> { a, b ->
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

    private fun write(v: Any?, sb: StringBuilder) {
        when (v) {
            null -> sb.append("null")
            is Boolean -> sb.append(if (v) "true" else "false")
            is Int, is Long, is BigInteger -> sb.append(v.toString())
            is String -> string(v, sb)
            is List<*> -> {
                sb.append('[')
                var first = true
                for (e in v) {
                    if (!first) sb.append(',')
                    first = false
                    write(e, sb)
                }
                sb.append(']')
            }
            is Map<*, *> -> {
                val keys = v.keys.map { it as? String ?: throw IllegalArgumentException("non-string key: $it") }
                    .sortedWith(codePointOrder)
                sb.append('{')
                var first = true
                for (k in keys) {
                    if (!first) sb.append(',')
                    first = false
                    string(k, sb)
                    sb.append(':')
                    write(v[k], sb)
                }
                sb.append('}')
            }
            else -> throw IllegalArgumentException("not canonical-serialisable: ${v::class}")
        }
    }

    private fun string(s: String, sb: StringBuilder) {
        sb.append('"')
        for (c in s) {
            when {
                c == '"' -> sb.append("\\\"")
                c == '\\' -> sb.append("\\\\")
                c == '\n' -> sb.append("\\n")
                c == '\r' -> sb.append("\\r")
                c == '\t' -> sb.append("\\t")
                c == '\b' -> sb.append("\\b")
                c == '\u000c' -> sb.append("\\f")
                c.code in 0x20..0x7e -> sb.append(c)
                else -> {
                    val x = c.code
                    sb.append("\\u")
                    sb.append(HEX[(x shr 12) and 15]).append(HEX[(x shr 8) and 15])
                    sb.append(HEX[(x shr 4) and 15]).append(HEX[x and 15])
                }
            }
        }
        sb.append('"')
    }
}
