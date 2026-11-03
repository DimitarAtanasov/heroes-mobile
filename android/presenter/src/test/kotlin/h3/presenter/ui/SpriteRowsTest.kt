package h3.presenter.ui

import h3.sim.BattleCreature
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

// Synthetic data only: invented creature names, invented DEF names, arbitrary row numbers.

private fun e(row: Int, name: String) =
    GameRosterEntry(row, BattleCreature(name, attack = 1, defense = 1, dmgMin = 1, dmgMax = 2, hp = 5, speed = 4))

private fun tableJson(vararg rows: Pair<Int, String>) =
    """{"schema_version": 2, "entries": [""" +
        rows.joinToString(",") { (r, d) -> """{"row": $r, "def": "$d", "source": "synthetic"}""" } + "]}"

class SpriteRowsTest {
    @Test
    fun pairsKeepRosterOrderAndCarryTheRowAndTheBattleName() {
        val roster = listOf(e(9, "Qux"), e(2, "Fob"), e(40, "Zed"))
        assertEquals(listOf(9 to "Qux", 2 to "Fob", 40 to "Zed"), SpriteRows.pairs(roster))
        assertEquals(emptyList(), SpriteRows.pairs(emptyList()))
    }

    @Test
    fun mismatchCountsRowsOnEachSideOnly() {
        val roster = listOf(e(0, "Aaa"), e(1, "Bbb"), e(5, "Ccc"), e(6, "Ddd"))
        val table = linkedMapOf(1 to "XA.DEF", 5 to "XB.DEF", 70 to "XC.DEF", 71 to "XD.DEF", 72 to "XE.DEF")
        val m = SpriteRows.mismatch(table, roster)
        assertEquals(3, m.tableOnly) // 70, 71, 72
        assertEquals(2, m.rosterOnly) // 0, 6
        assertTrue(!m.matches)
    }

    @Test
    fun mismatchLineHoldsCountsOnlyNoNamesNoRowsNoDefs() {
        val m = SpriteRows.mismatch(mapOf(3 to "XQ.DEF"), listOf(e(4, "Secretname")))
        val line = m.describe()
        assertEquals("SPRITE_ROWS table_only=1 roster_only=1", line)
        assertTrue("Secretname" !in line && "XQ" !in line)
    }

    @Test
    fun exactMatchAndRepeatedRosterRowsCountOnce() {
        val roster = listOf(e(3, "Aaa"), e(3, "Bbb"), e(8, "Ccc"))
        val m = SpriteRows.mismatch(linkedMapOf(8 to "XA.DEF", 3 to "XB.DEF"), roster)
        assertEquals(RowMismatch(0, 0), m)
        assertTrue(m.matches)
    }

    @Test
    fun prepareOkGivesTableAndPairsAndNoNoteWhenRowsMatch() {
        val roster = listOf(e(4, "Aaa"), e(7, "Bbb"))
        val p = SpriteRows.prepare(tableJson(7 to "XB.DEF", 4 to "XA.DEF"), roster)
        val table = assertNotNull(p.table)
        assertEquals("XA.DEF", table[4])
        assertEquals(listOf(4 to "Aaa", 7 to "Bbb"), p.pairs)
        assertEquals(emptyList(), p.notes)
    }

    @Test
    fun prepareOkWithMismatchLogsOneCountLine() {
        val roster = listOf(e(4, "Aaa"), e(5, "Bbb"))
        val p = SpriteRows.prepare(tableJson(4 to "XA.DEF", 90 to "XZ.DEF"), roster)
        assertNotNull(p.table)
        assertEquals(listOf("SPRITE_ROWS table_only=1 roster_only=1"), p.notes)
    }

    @Test
    fun prepareFailedFallsBackToTokensAndListsEveryParseError() {
        val bad = """{"schema_version": 2, "entries": [""" +
            """{"row": -1, "def": "XA.DEF", "source": "s"},""" +
            """{"row": 2, "def": "XB.DEF", "source": " "}]}"""
        val p = SpriteRows.prepare(bad, listOf(e(2, "Aaa")))
        assertNull(p.table)
        assertEquals(emptyList(), p.pairs)
        val expected = (SpriteTable.parse(bad) as SpriteTableResult.Failed).errors.map { it.describe() }
        assertEquals(2, expected.size)
        assertEquals(expected, p.notes)
    }

    @Test
    fun prepareOnBrokenJsonIsAFailureNotAThrow() {
        val p = SpriteRows.prepare("{ not json", listOf(e(0, "Aaa")))
        assertNull(p.table)
        assertEquals(1, p.notes.size)
        assertTrue(p.notes[0].startsWith("INVALID_JSON"))
    }

    @Test
    fun preparedPairsDriveLoadByRowToNoMappingForRosterOnlyRows() {
        // No archives: the mapped row reaches the archive search (nothing found), the unmapped row is NO_MAPPING.
        val roster = listOf(e(1, "Aaa"), e(2, "Bbb"))
        val p = SpriteRows.prepare(tableJson(1 to "XA.DEF"), roster)
        val res = SpriteLoadPlan.loadByRow(p.pairs, emptyList(), assertNotNull(p.table))
        assertNull(res.atlas)
        assertEquals(listOf("NO_MAPPING", "MISSING_DEF"), res.errors.map { it.code })
    }
}
