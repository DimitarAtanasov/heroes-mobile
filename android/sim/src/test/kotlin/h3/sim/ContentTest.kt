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

    /** Same synthetic fixture as test_content.py test_zero_damage_row_kept_index_counts_no_fixed_damage. */
    @Test
    fun zeroDamageRowKeptIndexCountsNoFixedDamage() {
        fun row(name: String, lo: Int, hi: Int): List<String> =
            listOf(name, "Xs") + List(6) { "0" } + listOf("100") +
                listOf(50, 60, 7, 0, 10, 4, 5, 4, lo, hi, 0, 0, 1, 5).map { it.toString() } +
                listOf("long text", "")
        val head = listOf(listOf("Creature table"), listOf("Singular", "Plural", "Wood", "Mercury"))
        val rows = listOf(row("Zork", 1, 3), listOf(""), row("Wisp", 0, 0), listOf("", "x"), row("Mump", 2, 4))
        val text = (head + rows).joinToString("\r\n", postfix = "\r\n") { it.joinToString("\t") }
        val r = Content.parseCreatures(text.toByteArray(Charsets.ISO_8859_1), mapping)
        assertEquals(mapOf("Zork" to 0, "Wisp" to 1, "Mump" to 2), r.creatureRows)
        assertEquals(setOf("Wisp"), r.noFixedDamage)
        assertEquals(listOf("Mump", "Wisp", "Zork"), r.creatures.map { it.name })
    }

    @Test
    fun dmgMaxFloorIsZeroOnlyForNoFixedDamage() {
        // Owner decision 2026-11-02: CRTRAITS dmg_max floor is 0, only for dmg 0/0 (no fixed
        // damage). dmg_min >= 1 with dmg_max 0 stays refused until the owner picks a form for it.
        fun cr(lo: Long, hi: Long) = Creature("Zork", 10, 4, 5, 4, lo, hi, 0, emptySet())
        DefaultCreatureValidator.validate(cr(0, 0))
        for ((lo, hi) in listOf(-1L to 3L, 5L to 4L, 1L to 0L, 3L to 10001L, 10001L to 10001L)) {
            assertFailsWith<IllegalArgumentException>("$lo..$hi") { DefaultCreatureValidator.validate(cr(lo, hi)) }
        }
    }

    @Test
    fun hpFloorIsZeroForCrtraits() {
        // Owner decision 2026-11-02: CRTRAITS hp floor 0; hp -1 still refused. Battle unchanged.
        fun cr(hp: Long, lo: Long = 1, hi: Long = 3) = Creature("Zork", hp, 4, 5, 4, lo, hi, 0, emptySet())
        DefaultCreatureValidator.validate(cr(0))
        DefaultCreatureValidator.validate(cr(0, 0, 0))
        assertFailsWith<IllegalArgumentException> { DefaultCreatureValidator.validate(cr(-1)) }
    }

    /** Twin of test_content.py test_no_fixed_damage_creature_refused_by_battle: dmg_max 0 still refused by battle. */
    @Test
    fun noFixedDamageCreatureRefusedByBattle() {
        for ((lo, hi) in listOf(0 to 0, 1 to 0)) {
            val sc = """{"battle_id":"t","attackers":[{"creature":"w","count":5}],
                "defenders":[{"creature":"z","count":5}],
                "creatures":{"w":{"attack":1,"defense":1,"dmg_min":$lo,"dmg_max":$hi,"hp":5,"speed":3},
                "z":{"attack":1,"defense":1,"dmg_min":1,"dmg_max":2,"hp":5,"speed":3}}}"""
            val e = assertFailsWith<ScenarioError>("$lo..$hi") { Scenario.parse(sc, ReplayVectors.packs) }
            assertEquals("scenario: invalid damage range", e.message)
        }
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
    fun dmgMinFloorIsZero() {
        // Owner decision 2026-11-02: dmg_min floor is 0 (real CRTRAITS rows have 0).
        fun cr(lo: Long, hi: Long) = Creature("Zork", 10, 4, 5, 4, lo, hi, 0, emptySet())
        for ((lo, hi) in listOf(0L to 3L, 0L to 1L, 3L to 3L, 10000L to 10000L)) {
            DefaultCreatureValidator.validate(cr(lo, hi))
        }
        for ((lo, hi) in listOf(-1L to 3L, 5L to 4L, 10001L to 10001L)) {
            assertFailsWith<IllegalArgumentException>("$lo..$hi") { DefaultCreatureValidator.validate(cr(lo, hi)) }
        }
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
