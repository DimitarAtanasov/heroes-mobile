package h3.presenter.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

// Synthetic JSON only: the names are the existing placeholder roster, the sources are made up.

private fun entry(creature: String, def: String, source: String) =
    """{"creature": ${q(creature)}, "def": ${q(def)}, "source": ${q(source)}}"""

private fun q(s: String) = "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

private fun doc(vararg entries: String, version: String = "1") =
    """{"schema_version": $version, "entries": [${entries.joinToString(",")}]}"""

private fun failed(text: String): List<SpriteTableError> =
    assertIs<SpriteTableResult.Failed>(SpriteTable.parse(text)).errors

private fun codes(text: String): List<String> = failed(text).map { it.code }

class SpriteTableTest {
    private val src = "synthetic note 1"

    @Test
    fun validTableKeepsFileOrder() {
        val r = SpriteTable.parse(
            doc(
                entry("Test Slinger", "CLCBOW.DEF", src),
                entry("Test Pikeman", "CPKMAN.DEF", src),
            ),
        )
        val ok = assertIs<SpriteTableResult.Ok>(r)
        assertEquals(listOf("Test Slinger", "Test Pikeman"), ok.table.keys.toList())
        assertEquals("CPKMAN.DEF", ok.table["Test Pikeman"])
    }

    @Test
    fun emptyEntriesIsAnEmptyTable() {
        val ok = assertIs<SpriteTableResult.Ok>(SpriteTable.parse(doc()))
        assertEquals(emptyMap(), ok.table)
    }

    @Test
    fun parsedTableDrivesDefFor() {
        val ok = assertIs<SpriteTableResult.Ok>(SpriteTable.parse(doc(entry("Test Pikeman", "CPKMAN.DEF", src))))
        assertEquals("CPKMAN.DEF", SpriteLoadPlan.defFor("Test Pikeman", ok.table))
        assertEquals(null, SpriteLoadPlan.defFor("test pikeman", ok.table))
        assertEquals(null, SpriteLoadPlan.defFor("Test Slinger", ok.table))
    }

    @Test
    fun missingSourceKeyIsBadShape() {
        val t = """{"schema_version": 1, "entries": [{"creature": "Test Pikeman", "def": "CPKMAN.DEF"}]}"""
        assertEquals(listOf("BAD_SHAPE"), codes(t))
    }

    @Test
    fun emptyOrBlankSourceRejected() {
        assertEquals(listOf("MISSING_SOURCE"), codes(doc(entry("Test Pikeman", "CPKMAN.DEF", ""))))
        assertEquals(listOf("MISSING_SOURCE"), codes(doc(entry("Test Pikeman", "CPKMAN.DEF", " \t "))))
    }

    @Test
    fun nonStringSourceIsBadShape() {
        val t = """{"schema_version": 1, "entries": [{"creature": "A", "def": "A.DEF", "source": 7}]}"""
        val e = failed(t).single()
        assertEquals("BAD_SHAPE", e.code)
        assertEquals("BAD_SHAPE entries[0].source: expected string", e.describe())
    }

    @Test
    fun duplicateCreatureRejectedAndNamesLaterIndex() {
        val e = failed(
            doc(
                entry("Test Pikeman", "CPKMAN.DEF", src),
                entry("Test Slinger", "CLCBOW.DEF", src),
                entry("Test Pikeman", "CGRIFF.DEF", src),
            ),
        ).single()
        assertEquals(SpriteTableError.DuplicateCreature(2, "Test Pikeman"), e)
    }

    @Test
    fun creatureNamesDifferingByCaseAreDistinct() {
        val r = SpriteTable.parse(doc(entry("Test Pikeman", "A.DEF", src), entry("test pikeman", "B.DEF", src)))
        assertEquals(2, assertIs<SpriteTableResult.Ok>(r).table.size)
    }

    @Test
    fun emptyCreatureRejected() {
        assertEquals(listOf("EMPTY_CREATURE"), codes(doc(entry("", "A.DEF", src))))
    }

    @Test
    fun defMustEndInDefExactly() {
        for (bad in listOf("CPKMAN", "CPKMAN.def", "CPKMAN.DEF.txt", "CPKMAN.PCX", ".DEF", "")) {
            assertEquals(listOf("BAD_DEF_NAME"), codes(doc(entry("Test Pikeman", bad, src))), "def=$bad")
        }
    }

    @Test
    fun defWithPathSeparatorRejected() {
        for (bad in listOf("sub/CPKMAN.DEF", "sub\\CPKMAN.DEF", "/CPKMAN.DEF", "..\\CPKMAN.DEF")) {
            assertEquals(listOf("DEF_HAS_PATH"), codes(doc(entry("Test Pikeman", bad, src))), "def=$bad")
        }
    }

    @Test
    fun unknownSchemaVersionRejected() {
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "2")))
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "0")))
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "\"1\"")))
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "true")))
    }

    @Test
    fun missingOrUnknownTopLevelKeys() {
        assertEquals(listOf("BAD_SHAPE"), codes("""{"entries": []}"""))
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 1}"""))
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 1, "entries": [], "extra": 1}"""))
        assertEquals(listOf("BAD_SHAPE"), codes("[]"))
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 1, "entries": {}}"""))
    }

    @Test
    fun unknownEntryKeyRejected() {
        val t = """{"schema_version": 1, "entries": [
            {"creature": "A", "def": "A.DEF", "source": "s", "note": "x"}]}"""
        val e = failed(t).single()
        assertEquals("BAD_SHAPE entries[0]: unknown key note", e.describe())
    }

    @Test
    fun entryThatIsNotAnObjectRejected() {
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 1, "entries": ["A"]}"""))
    }

    @Test
    fun invalidJsonNeverThrows() {
        for (bad in listOf("", "{", "not json", """{"schema_version": 1, "entries": [}""", "{\"a\": 1} x")) {
            assertEquals(listOf("INVALID_JSON"), codes(bad), "text=$bad")
        }
    }

    @Test
    fun floatAndDuplicateJsonKeyAreInvalidJson() {
        assertEquals(listOf("INVALID_JSON"), codes("""{"schema_version": 1.0, "entries": []}"""))
        assertEquals(listOf("INVALID_JSON"), codes("""{"schema_version": 1, "schema_version": 1, "entries": []}"""))
    }

    @Test
    fun allEntryErrorsAreCollectedInOrderAndNoTableIsReturned() {
        val errs = failed(
            doc(
                entry("A", "A.DEF", ""),
                entry("B", "dir/B.DEF", src),
                entry("C", "C.DEF", src),
                entry("C", "D.DEF", src),
            ),
        )
        assertEquals(
            listOf(
                SpriteTableError.MissingSource(0, "A"),
                SpriteTableError.DefHasPath(1, "B", "dir/B.DEF"),
                SpriteTableError.DuplicateCreature(3, "C"),
            ),
            errs,
        )
    }

    @Test
    fun describeStartsWithTheStableCode() {
        for (e in failed(doc(entry("A", "A", "")))) assertEquals(e.code, e.describe().substringBefore(' ').removeSuffix(":"))
    }
}
