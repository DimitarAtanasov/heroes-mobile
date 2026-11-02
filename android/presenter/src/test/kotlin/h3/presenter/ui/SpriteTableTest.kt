package h3.presenter.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

// Synthetic JSON only: the rows are arbitrary numbers and the sources are made up.

private fun entry(row: String, def: String, source: String) =
    """{"row": $row, "def": ${q(def)}, "source": ${q(source)}}"""

// Escapes tab too: strict JSON (PackJson) rejects a raw control character inside a string.
private fun q(s: String) = "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\t", "\\t") + "\""

private fun doc(vararg entries: String, version: String = "2") =
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
                entry("7", "CLCBOW.DEF", src),
                entry("3", "CPKMAN.DEF", src),
                entry("0", "CGRIFF.DEF", src),
            ),
        )
        val ok = assertIs<SpriteTableResult.Ok>(r)
        assertEquals(listOf(7, 3, 0), ok.table.keys.toList())
        assertEquals("CPKMAN.DEF", ok.table[3])
    }

    @Test
    fun emptyEntriesIsAnEmptyTable() {
        val ok = assertIs<SpriteTableResult.Ok>(SpriteTable.parse(doc()))
        assertEquals(emptyMap(), ok.table)
    }

    @Test
    fun otherSchemaVersionsAreRejected() {
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "1")))
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "3")))
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "0")))
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "\"2\"")))
        assertEquals(listOf("BAD_SCHEMA_VERSION"), codes(doc(version = "true")))
    }

    @Test
    fun negativeRowRejected() {
        val e = failed(doc(entry("-1", "A.DEF", src))).single()
        assertIs<SpriteTableError.BadRow>(e)
        assertEquals("BAD_ROW", e.code)
    }

    @Test
    fun nonIntegerRowRejected() {
        for (bad in listOf("\"5\"", "true", "null", "[]", "{}", "2147483648")) {
            assertEquals(listOf("BAD_ROW"), codes(doc(entry(bad, "A.DEF", src))), "row=$bad")
        }
    }

    @Test
    fun floatRowIsInvalidJson() {
        assertEquals(listOf("INVALID_JSON"), codes(doc(entry("1.5", "A.DEF", src))))
    }

    @Test
    fun duplicateRowRejectedAndNamesLaterIndex() {
        val e = failed(
            doc(
                entry("4", "CPKMAN.DEF", src),
                entry("5", "CLCBOW.DEF", src),
                entry("4", "CGRIFF.DEF", src),
            ),
        ).single()
        assertEquals(SpriteTableError.DuplicateRow(2, 4), e)
        assertEquals("DUPLICATE_ROW", e.code)
    }

    @Test
    fun missingSourceKeyIsBadShape() {
        val t = """{"schema_version": 2, "entries": [{"row": 1, "def": "CPKMAN.DEF"}]}"""
        assertEquals(listOf("BAD_SHAPE"), codes(t))
    }

    @Test
    fun emptyOrBlankSourceRejected() {
        assertEquals(listOf("MISSING_SOURCE"), codes(doc(entry("1", "CPKMAN.DEF", ""))))
        assertEquals(listOf("MISSING_SOURCE"), codes(doc(entry("1", "CPKMAN.DEF", " \t "))))
    }

    @Test
    fun nonStringSourceIsBadShape() {
        val t = """{"schema_version": 2, "entries": [{"row": 1, "def": "A.DEF", "source": 7}]}"""
        val e = failed(t).single()
        assertEquals("BAD_SHAPE entries[0].source: expected string", e.describe())
    }

    @Test
    fun oldCreatureKeyIsRejected() {
        val t = """{"schema_version": 2, "entries": [{"creature": "A", "def": "A.DEF", "source": "s"}]}"""
        assertEquals(listOf("BAD_SHAPE", "BAD_SHAPE"), codes(t))
    }

    @Test
    fun defMustEndInDefExactly() {
        for (bad in listOf("CPKMAN", "CPKMAN.def", "CPKMAN.DEF.txt", "CPKMAN.PCX", ".DEF", "")) {
            assertEquals(listOf("BAD_DEF_NAME"), codes(doc(entry("1", bad, src))), "def=$bad")
        }
    }

    @Test
    fun defWithPathSeparatorRejected() {
        for (bad in listOf("sub/CPKMAN.DEF", "sub\\CPKMAN.DEF", "/CPKMAN.DEF", "..\\CPKMAN.DEF")) {
            assertEquals(listOf("DEF_HAS_PATH"), codes(doc(entry("1", bad, src))), "def=$bad")
        }
    }

    @Test
    fun missingOrUnknownTopLevelKeys() {
        assertEquals(listOf("BAD_SHAPE"), codes("""{"entries": []}"""))
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 2}"""))
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 2, "entries": [], "extra": 1}"""))
        assertEquals(listOf("BAD_SHAPE"), codes("[]"))
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 2, "entries": {}}"""))
    }

    @Test
    fun unknownEntryKeyRejected() {
        val t = """{"schema_version": 2, "entries": [
            {"row": 1, "def": "A.DEF", "source": "s", "note": "x"}]}"""
        val e = failed(t).single()
        assertEquals("BAD_SHAPE entries[0]: unknown key note", e.describe())
    }

    @Test
    fun entryThatIsNotAnObjectRejected() {
        assertEquals(listOf("BAD_SHAPE"), codes("""{"schema_version": 2, "entries": [1]}"""))
    }

    @Test
    fun invalidJsonNeverThrows() {
        for (bad in listOf("", "{", "not json", """{"schema_version": 2, "entries": [}""", "{\"a\": 1} x")) {
            assertEquals(listOf("INVALID_JSON"), codes(bad), "text=$bad")
        }
    }

    @Test
    fun floatAndDuplicateJsonKeyAreInvalidJson() {
        assertEquals(listOf("INVALID_JSON"), codes("""{"schema_version": 2.0, "entries": []}"""))
        assertEquals(listOf("INVALID_JSON"), codes("""{"schema_version": 2, "schema_version": 2, "entries": []}"""))
        val dupRowKey = """{"schema_version": 2, "entries": [{"row": 1, "row": 2, "def": "A.DEF", "source": "s"}]}"""
        assertEquals(listOf("INVALID_JSON"), codes(dupRowKey))
    }

    @Test
    fun allEntryErrorsAreCollectedInOrderAndNoTableIsReturned() {
        val errs = failed(
            doc(
                entry("1", "A.DEF", ""),
                entry("2", "dir/B.DEF", src),
                entry("3", "C.DEF", src),
                entry("3", "D.DEF", src),
                entry("-4", "E.DEF", src),
            ),
        )
        assertEquals(
            listOf(
                SpriteTableError.MissingSource(0, 1),
                SpriteTableError.DefHasPath(1, 2, "dir/B.DEF"),
                SpriteTableError.DuplicateRow(3, 3),
                SpriteTableError.BadRow(4, "expected non-negative integer, got -4"),
            ),
            errs,
        )
    }

    @Test
    fun describeStartsWithTheStableCode() {
        for (e in failed(doc(entry("1", "A", "")))) assertEquals(e.code, e.describe().substringBefore(' ').removeSuffix(":"))
    }
}
