package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

private val CONTENT_DOC by lazy { loadVector("content.json") }

class ContentTest {
    private val mapping by lazy { CreatureMapping.fromTree(CONTENT_DOC["mapping"]) }

    private fun norm(v: Any?): Any? = when (v) {
        is java.math.BigInteger -> v.toLong()
        is Map<*, *> -> v.entries.associate { (k, x) -> k as String to norm(x) }
        is List<*> -> v.map { norm(it) }
        else -> v
    }

    @Test
    fun conformanceVectors() {
        val cases = CONTENT_DOC["cases"].list()
        assertTrue(cases.size >= 40)
        var ok = 0
        var bad = 0
        for (c in cases.map { it.obj() }) {
            val name = c["name"] as String
            val data = hexBytes(c["data_hex"] as String)
            val roe = c["roe"] as Boolean
            val enc = c["encoding"] as String
            val err = c["error"]?.obj()
            if (err != null) {
                bad++
                val e = assertFailsWith<ContentError>(name) { Content.parseCreatures(data, mapping, roe, enc) }
                assertEquals(err["category"], e.category.key, "$name category")
                assertEquals((err["row"] as java.math.BigInteger?)?.toInt(), e.row, "$name row")
                assertEquals(err["column"], e.column, "$name column")
                if (e.row != null) assertTrue(e.message!!.startsWith("row ${e.row}"), "$name message names row: ${e.message}")
                if (e.column != null) assertTrue(e.message!!.contains("column '${e.column}'"), "$name message names column")
            } else {
                ok++
                val r = Content.parseCreatures(data, mapping, roe, enc)
                val exp = c["expect"].obj()
                assertEquals(norm(exp["creatures"]), r.creatures.map { it.toMap() }, "$name creatures")
                assertEquals(norm(exp["extras"]), r.extras, "$name extras")
                assertEquals(
                    norm(exp["unknown"]),
                    r.unknown.map { listOf(it.row.toLong(), it.name, it.text) }, "$name unknown",
                )
            }
        }
        assertTrue(ok >= 15 && bad >= 15, "ok=$ok bad=$bad")
    }

    /** Same synthetic fixture as test_content.py test_creature_rows_data_row_index. */
    @Test
    fun creatureRowsDataRowIndex() {
        fun row(name: String): List<String> =
            listOf(name, "Xs") + List(6) { "0" } + listOf("100") +
                listOf(50, 60, 7, 0, 10, 4, 5, 4, 1, 3, 0, 0, 1, 5).map { it.toString() } +
                listOf("long text", "")
        val head = listOf(listOf("Creature table"), listOf("Singular", "Plural", "Wood", "Mercury"))
        val rows = listOf(row("Zork"), listOf(""), row("Blip"), listOf("", "x"), row("Mump"))
        val text = (head + rows).joinToString("\r\n", postfix = "\r\n") { it.joinToString("\t") }
        val r = Content.parseCreatures(text.toByteArray(Charsets.ISO_8859_1), mapping)
        assertEquals(mapOf("Zork" to 0, "Blip" to 1, "Mump" to 2), r.creatureRows)
        assertEquals(listOf("Blip", "Mump", "Zork"), r.creatures.map { it.name })
    }

    @Test
    fun mappingRejectsUnknownFlagAndVersion() {
        @Suppress("UNCHECKED_CAST")
        val m = (norm(CONTENT_DOC["mapping"]) as Map<String, Any?>).toMutableMap()
        val bad = m.toMutableMap()
        bad["ability_flags"] = mapOf("x" to "teleport")
        assertEquals(ContentErrorCategory.MAPPING, assertFailsWith<ContentError> { CreatureMapping.fromTree(bad) }.category)
        bad["ability_flags"] = m["ability_flags"]
        bad["schema_version"] = 2L
        assertEquals(ContentErrorCategory.MAPPING, assertFailsWith<ContentError> { CreatureMapping.fromTree(bad) }.category)
    }

    @Test
    fun injectedValidatorIsUsed() {
        val c = CONTENT_DOC["cases"].list().map { it.obj() }.first { it["name"] == "two_creatures_sorted" }
        val e = assertFailsWith<ContentError> {
            Content.parseCreatures(hexBytes(c["data_hex"] as String), mapping,
                validator = CreatureValidator { throw IllegalArgumentException("nope") })
        }
        assertEquals(ContentErrorCategory.SCHEMA, e.category)
        assertEquals(3, e.row)
        assertNull(e.column)
    }
}
