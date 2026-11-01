package h3.sim

import java.math.BigInteger

/** Minimal JSON reader for test vectors: integers become BigInteger, objects LinkedHashMap. */
class MiniJson private constructor(private val s: String) {
    private var i = 0

    companion object {
        fun parse(text: String): Any? {
            val p = MiniJson(text)
            val v = p.value()
            p.ws()
            require(p.i == text.length) { "trailing data at ${p.i}" }
            return v
        }
    }

    internal fun ws() {
        while (i < s.length && s[i].isWhitespace()) i++
    }

    private fun value(): Any? {
        ws()
        return when (val c = s[i]) {
            '{' -> obj()
            '[' -> arr()
            '"' -> str()
            't' -> { i += 4; true }
            'f' -> { i += 5; false }
            'n' -> { i += 4; null }
            else -> {
                require(c == '-' || c.isDigit()) { "bad char $c at $i" }
                val st = i
                i++
                while (i < s.length && s[i].isDigit()) i++
                require(i >= s.length || s[i] !in ".eE") { "float not allowed" }
                BigInteger(s.substring(st, i))
            }
        }
    }

    private fun obj(): Map<String, Any?> {
        val m = LinkedHashMap<String, Any?>()
        i++
        ws()
        if (s[i] == '}') { i++; return m }
        while (true) {
            ws()
            val k = str()
            ws(); i++ // ':'
            m[k] = value()
            ws()
            if (s[i++] == '}') return m
        }
    }

    private fun arr(): List<Any?> {
        val l = ArrayList<Any?>()
        i++
        ws()
        if (s[i] == ']') { i++; return l }
        while (true) {
            l.add(value())
            ws()
            if (s[i++] == ']') return l
        }
    }

    private fun str(): String {
        val sb = StringBuilder()
        i++
        while (true) {
            val c = s[i++]
            when (c) {
                '"' -> return sb.toString()
                '\\' -> when (val e = s[i++]) {
                    'n' -> sb.append('\n'); 'r' -> sb.append('\r'); 't' -> sb.append('\t')
                    'b' -> sb.append('\b'); 'f' -> sb.append('\u000c')
                    'u' -> { sb.append(s.substring(i, i + 4).toInt(16).toChar()); i += 4 }
                    else -> sb.append(e)
                }
                else -> sb.append(c)
            }
        }
    }
}

fun loadVector(name: String): Map<String, Any?> {
    val text = object {}.javaClass.getResourceAsStream("/vectors/$name")!!.readBytes().toString(Charsets.UTF_8)
    @Suppress("UNCHECKED_CAST")
    return MiniJson.parse(text) as Map<String, Any?>
}

@Suppress("UNCHECKED_CAST")
fun Any?.obj() = this as Map<String, Any?>
@Suppress("UNCHECKED_CAST")
fun Any?.list() = this as List<Any?>
fun Any?.big() = this as BigInteger
fun Any?.u64(): ULong = (this as BigInteger).toLong().toULong()
