package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

internal fun hexBytes(h: String): ByteArray =
    ByteArray(h.length / 2) { h.substring(2 * it, 2 * it + 2).toInt(16).toByte() }

private val TXT_DOC by lazy { loadVector("txt.json") }

class TxtTest {
    private fun rows(v: Any?): List<List<String>> = v.list().map { r -> r.list().map { it as String } }

    @Test
    fun conformanceVectors() {
        val cases = TXT_DOC["cases"].list()
        assertTrue(cases.size >= 300, "vector count ${cases.size}")
        var errors = 0
        for (c in cases.map { it.obj() }) {
            val name = c["name"] as String
            val data = hexBytes(c["data_hex"] as String)
            val hr = c["header_rows"].big().toInt()
            val enc = (c["encoding"] as String?) ?: Txt.DEFAULT_ENCODING
            val lenient = (c["lenient_newlines"] as Boolean?) ?: false
            val quoting = (c["quoting"] as Boolean?) ?: true
            val maxBytes = c["max_bytes"]?.big()?.toInt() ?: Txt.MAX_BYTES
            val maxLines = c["max_lines"]?.big()?.toInt() ?: Txt.MAX_LINES
            val err = c["error"] as String?
            if (err != null) {
                errors++
                val e = assertFailsWith<TxtError>(name) { Txt.parse(data, hr, maxBytes, maxLines, enc, lenient, quoting) }
                assertEquals(err, e.category.key, name)
            } else {
                val t = Txt.parse(data, hr, maxBytes, maxLines, enc, lenient, quoting)
                val exp = c["expect"].obj()
                assertEquals(rows(exp["header"]), t.header, "$name header")
                assertEquals(rows(exp["rows"]), t.rows, "$name rows")
            }
        }
        assertTrue(errors >= 8)
    }

    @Test
    fun bareLfIsDataUnlessLenient() {
        val d = "a\nb\r\nc".toByteArray(Charsets.ISO_8859_1)
        assertEquals(listOf(listOf("a\nb"), listOf("c")), Txt.parse(d).rows)
        assertEquals(listOf(listOf("a"), listOf("b"), listOf("c")), Txt.parse(d, lenientNewlines = true).rows)
    }

    @Test
    fun quotingRules() {
        val d = "\"x\"\"y\"\t\"p\tq\"\r\n".toByteArray(Charsets.ISO_8859_1)
        assertEquals(listOf(listOf("x\"y", "p\tq")), Txt.parse(d).rows)
        assertEquals(listOf(listOf("\"x\"\"y\"", "\"p", "q\"")), Txt.parse(d, quoting = false).rows)
    }

    @Test
    fun caps() {
        assertFailsWith<TxtError> { Txt.parse(ByteArray(5), maxBytes = 4) }
        assertFailsWith<TxtError> { Txt.parse(ByteArray(0), headerRows = -1) }
        assertEquals(TxtTable(emptyList(), emptyList()), Txt.parse(ByteArray(0), 3))
    }
}
