package h3.presenter.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ImportTextTest {
    @Test
    fun statusLinesAreLiterals() {
        assertEquals("Checking game data...", ImportText.statusLine(null))
        assertEquals("Game data found.", ImportText.statusLine(ImportPlan.DataStatus.Found))
        assertEquals("Game data missing. The game runs with placeholder art.", ImportText.statusLine(ImportPlan.DataStatus.Missing))
        assertEquals("Game data changed since it was checked. Check it again.", ImportText.statusLine(ImportPlan.DataStatus.Changed))
    }

    @Test
    fun progressLineUsesIntegerPercent() {
        assertEquals("Copying: 0%", ImportText.progressLine(ImportPlan.Progress(0, 10)))
        assertEquals("Copying: 33%", ImportText.progressLine(ImportPlan.Progress(1, 3)))
        assertEquals("Copying: 100%", ImportText.progressLine(ImportPlan.Progress(3, 3)))
    }

    @Test
    fun mibRoundsUpWithoutOverflow() {
        assertEquals(0L, ImportText.mib(0L))
        assertEquals(1L, ImportText.mib(1L))
        assertEquals(1L, ImportText.mib(1_048_576L))
        assertEquals(2L, ImportText.mib(1_048_577L))
        assertEquals(8_796_093_022_208L, ImportText.mib(Long.MAX_VALUE))
    }

    @Test
    fun oneSentencePerIssue() {
        val r = ImportResult.Invalid(
            listOf(
                GameDataIssue.MissingRequired("H3sprite.lod", false),
                GameDataIssue.CorruptArchive("H3bitmap.lod", 500),
                GameDataIssue.NotAnArchive("H3ab_bmp.lod", 10),
                GameDataIssue.TooLargeToCheck("H3ab_spr.lod", 600_000_000),
                GameDataIssue.Unreadable("H3ab_spr.lod", 5),
                GameDataIssue.MissingMember("H3bitmap.lod", "CRTRAITS.TXT"),
            ),
        )
        assertEquals(
            listOf(
                "H3sprite.lod was not found.",
                "H3bitmap.lod is damaged. Copy it again from your install.",
                "H3ab_bmp.lod is not a Heroes III archive.",
                "H3ab_spr.lod is too large to check on this device.",
                "H3ab_spr.lod could not be read.",
                "H3bitmap.lod does not contain CRTRAITS.TXT. It may come from another game version.",
            ),
            r.sentences(),
        )
        assertEquals("INVALID", r.code)
        assertTrue(r.isError)
        assertEquals(
            "MISSING_REQUIRED H3sprite.lod; CORRUPT_ARCHIVE H3bitmap.lod (500 bytes); NOT_AN_ARCHIVE H3ab_bmp.lod (10 bytes); " +
                "TOO_LARGE_TO_CHECK H3ab_spr.lod (600000000 bytes); UNREADABLE H3ab_spr.lod (5 bytes); " +
                "MISSING_MEMBER H3bitmap.lod: CRTRAITS.TXT",
            r.details(),
        )
    }

    @Test
    fun hdHintSentenceNamesTheEdition() {
        val s = ImportResult.Invalid(listOf(GameDataIssue.MissingRequired("H3bitmap.lod", true))).sentences()
        assertEquals(
            listOf("H3bitmap.lod is missing and .pak files were found: the HD Edition cannot be read. Use a Complete or Shadow of Death install."),
            s,
        )
    }

    @Test
    fun sourceProblems() {
        val missing = ImportResult.SourceProblem(ImportPlan.Selection.MissingSource("H3sprite.lod"))
        assertEquals("MISSING_SOURCE", missing.code)
        assertEquals(listOf("H3sprite.lod was not found in the folder."), missing.sentences())
        assertEquals("MISSING_SOURCE H3sprite.lod", missing.details())

        val amb = ImportResult.SourceProblem(ImportPlan.Selection.AmbiguousSource("H3bitmap.lod", listOf("Data/H3BITMAP.LOD", "Data/h3bitmap.lod")))
        assertEquals("AMBIGUOUS_SOURCE", amb.code)
        assertEquals(listOf("More than one file matches H3bitmap.lod. Remove the extra copies."), amb.sentences())
        assertEquals("AMBIGUOUS_SOURCE H3bitmap.lod: Data/H3BITMAP.LOD, Data/h3bitmap.lod", amb.details())

        val bad = ImportResult.SourceProblem(ImportPlan.Selection.InvalidName("a/b"))
        assertEquals("INVALID_NAME", bad.code)
        assertEquals("INVALID_NAME a/b", bad.details())

        val size = ImportResult.SourceProblem(ImportPlan.Selection.UnknownSize("Data/x.lod"))
        assertEquals("UNKNOWN_SIZE", size.code)
        assertEquals(listOf("The size of Data/x.lod could not be read."), size.sentences())
        assertEquals("UNKNOWN_SIZE Data/x.lod", size.details())
    }

    @Test
    fun spaceMessageNamesBothNumbers() {
        val r = ImportResult.NotEnoughSpace(3_145_729L, 1_048_576L)
        assertEquals("NOT_ENOUGH_SPACE", r.code)
        assertEquals(listOf("Not enough free space: the copy needs 4 MB and 1 MB is free."), r.sentences())
        assertEquals("NOT_ENOUGH_SPACE needed 3145729 bytes, free 1048576 bytes", r.details())
    }

    @Test
    fun ioAndChangedResults() {
        assertEquals(listOf("Copying failed. Check the free space and try again."), ImportResult.IoFailed(IoStage.Copy, "H3bitmap.lod").sentences())
        assertEquals("IO_FAILED Copy H3bitmap.lod", ImportResult.IoFailed(IoStage.Copy, "H3bitmap.lod").details())
        assertEquals("IO_FAILED Recover", ImportResult.IoFailed(IoStage.Recover, null).details())
        assertEquals(listOf("Leftovers of an earlier import could not be cleaned up."), ImportResult.IoFailed(IoStage.Recover, null).sentences())
        assertEquals(listOf("The folder could not be read."), ImportResult.IoFailed(IoStage.Scan, null).sentences())
        assertEquals(listOf("The record of the imported files could not be written."), ImportResult.IoFailed(IoStage.Manifest, null).sentences())
        assertEquals(listOf("The new files could not be put in place."), ImportResult.IoFailed(IoStage.Swap, null).sentences())
        assertEquals("IO_FAILED", ImportResult.IoFailed(IoStage.Swap, null).code)
        val ch = ImportResult.SourceChanged("H3sprite.lod")
        assertEquals("SOURCE_CHANGED", ch.code)
        assertEquals(listOf("H3sprite.lod changed while it was being copied. Try again."), ch.sentences())
        assertEquals("SOURCE_CHANGED H3sprite.lod", ch.details())
    }

    @Test
    fun validResultIsNotAnError() {
        val r = ImportResult.Valid(listOf(CheckedFile("H3bitmap.lod", 100), CheckedFile("H3sprite.lod", 200)))
        assertFalse(r.isError)
        assertEquals("OK", r.code)
        assertEquals(listOf("Game data is in place."), r.sentences())
        assertEquals("OK 2 files: H3bitmap.lod (100 bytes), H3sprite.lod (200 bytes)", r.details())
    }

    @Test
    fun sideloadHintNamesTheWholeWay() {
        val h = ImportText.SIDELOAD_HINT
        assertTrue("debug builds only" in h)
        assertTrue("adb push Data /data/local/tmp/Data" in h)
        assertTrue("adb shell run-as h3.app" in h)
        assertTrue("no_backup/gamedata/Data/" in h)
        assertTrue("Check again" in h)
    }
}
