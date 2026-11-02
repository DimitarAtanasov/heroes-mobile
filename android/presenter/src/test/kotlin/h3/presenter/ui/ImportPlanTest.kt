package h3.presenter.ui

import h3.presenter.ui.ImportPlan.DataStatus
import h3.presenter.ui.ImportPlan.Manifest
import h3.presenter.ui.ImportPlan.ManifestError
import h3.presenter.ui.ImportPlan.ManifestFile
import h3.presenter.ui.ImportPlan.ManifestParse
import h3.presenter.ui.ImportPlan.Progress
import h3.presenter.ui.ImportPlan.RecoverAction
import h3.presenter.ui.ImportPlan.Selection
import h3.presenter.ui.ImportPlan.SelectedFile
import h3.presenter.ui.ImportPlan.SourceEntry
import h3.presenter.ui.ImportPlan.SpaceCheck
import h3.presenter.ui.ImportPlan.Step
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * The import plan: source choice, space check, ordered crash-safe steps, recovery, status, manifest and
 * progress (android-app.md 3.2 steps 5 to 8, 3.5 last paragraph). All expectations are literals; none is
 * computed from the constants or the table under test (memory: pin-literals-not-constants).
 */
class ImportPlanTest {
    private fun e(path: String, size: Long) = SourceEntry(path, size)

    private fun chosen(r: Selection): List<SelectedFile> = assertIs<Selection.Chosen>(r).files

    // ---- source selection ----

    @Test
    fun dataFolderWinsOverTheRoot() {
        val a = e("H3bitmap.lod", 10)
        val b = e("Data/H3bitmap.lod", 20)
        val expected = listOf(SelectedFile("H3bitmap.lod", "Data/H3bitmap.lod", 20))
        assertEquals(expected, chosen(ImportPlan.select(listOf(a, b), listOf("H3bitmap.lod"))))
        assertEquals(expected, chosen(ImportPlan.select(listOf(b, a), listOf("H3bitmap.lod"))))
    }

    @Test
    fun theRootIsUsedWhenThereIsNoDataFolderCopy() {
        // The user picked the Data folder itself, so the files sit at the root of the listing.
        val r = ImportPlan.select(listOf(e("H3bitmap.lod", 10), e("Maps/a.h3m", 3)), listOf("H3bitmap.lod"))
        assertEquals(listOf(SelectedFile("H3bitmap.lod", "H3bitmap.lod", 10)), chosen(r))
    }

    @Test
    fun matchingIgnoresCaseButTheDestinationNameIsTheRequiredName() {
        val r = ImportPlan.select(listOf(e("data/H3BITMAP.LOD", 7)), listOf("H3bitmap.lod"))
        assertEquals(listOf(SelectedFile("H3bitmap.lod", "data/H3BITMAP.LOD", 7)), chosen(r))
    }

    @Test
    fun resultFollowsTheRequiredOrderNotTheListingOrder() {
        val entries = listOf(e("Data/b.lod", 2), e("Data/a.lod", 1), e("Data/c.lod", 3))
        val r = chosen(ImportPlan.select(entries, listOf("c.lod", "a.lod", "b.lod")))
        assertEquals(listOf("c.lod", "a.lod", "b.lod"), r.map { it.name })
        assertEquals(listOf(3L, 1L, 2L), r.map { it.size })
    }

    @Test
    fun namesThatDifferOnlyInCaseAreAmbiguous() {
        val r = ImportPlan.select(listOf(e("Data/h3bitmap.lod", 1), e("Data/H3bitmap.lod", 2)), listOf("H3bitmap.lod"))
        assertEquals(Selection.AmbiguousSource("H3bitmap.lod", listOf("Data/H3bitmap.lod", "Data/h3bitmap.lod")), r)
        val root = ImportPlan.select(listOf(e("x.lod", 1), e("X.LOD", 2)), listOf("x.lod"))
        assertEquals(Selection.AmbiguousSource("x.lod", listOf("X.LOD", "x.lod")), root)
    }

    @Test
    fun aSecondCopyInTheRootDoesNotHideAmbiguityInData() {
        val r = ImportPlan.select(
            listOf(e("Data/a.lod", 1), e("DATA/A.LOD", 2), e("a.lod", 3)),
            listOf("a.lod"),
        )
        assertEquals(Selection.AmbiguousSource("a.lod", listOf("DATA/A.LOD", "Data/a.lod")), r)
    }

    @Test
    fun theSameEntryListedTwiceIsAmbiguous() {
        val r = ImportPlan.select(listOf(e("Data/a.lod", 1), e("Data/a.lod", 1)), listOf("a.lod"))
        assertEquals(Selection.AmbiguousSource("a.lod", listOf("Data/a.lod", "Data/a.lod")), r)
    }

    @Test
    fun aMissingFileIsNamed() {
        val r = ImportPlan.select(listOf(e("Data/a.lod", 1)), listOf("a.lod", "b.lod", "c.lod"))
        assertEquals(Selection.MissingSource("b.lod"), r)
        assertEquals(Selection.MissingSource("a.lod"), ImportPlan.select(emptyList(), listOf("a.lod")))
    }

    @Test
    fun onlyTheTopOfDataAndTheRootCount() {
        val entries = listOf(e("Other/Data/a.lod", 1), e("Data/Sub/a.lod", 2), e("Backup/a.lod", 3), e("Data/", 4), e("a.lod.bak", 5))
        assertEquals(Selection.MissingSource("a.lod"), ImportPlan.select(entries, listOf("a.lod")))
    }

    @Test
    fun anEmptyRequiredListSelectsNothing() {
        assertEquals(emptyList(), chosen(ImportPlan.select(listOf(e("a.lod", 1)), emptyList())))
    }

    @Test
    fun unsafeOrCollidingRequiredNamesAreRefused() {
        val entries = listOf(e("a.lod", 1))
        for (bad in listOf("", ".", "..", "a/b", "a\\b", "manifest.json", "MANIFEST.JSON", "x.part", "X.PART", "a\u0000b", "a\nb", "n".repeat(256))) {
            assertEquals(Selection.InvalidName(bad), ImportPlan.select(entries, listOf(bad)), "name [$bad]")
        }
        assertEquals(Selection.InvalidName("A.LOD"), ImportPlan.select(entries, listOf("a.lod", "A.LOD")))
        // 255 characters is the longest accepted name.
        val longest = "n".repeat(255)
        assertEquals(listOf(longest), chosen(ImportPlan.select(listOf(e(longest, 1)), listOf(longest))).map { it.name })
    }

    @Test
    fun aNegativeSizeIsRefusedAndZeroIsFine() {
        assertEquals(Selection.UnknownSize("Data/a.lod"), ImportPlan.select(listOf(e("Data/a.lod", -1)), listOf("a.lod")))
        assertEquals(listOf(0L), chosen(ImportPlan.select(listOf(e("Data/a.lod", 0)), listOf("a.lod"))).map { it.size })
    }

    // ---- space check ----

    @Test
    fun neededEqualToFreeIsOkAndOneMoreIsNot() {
        assertEquals(SpaceCheck.Ok(100), ImportPlan.checkSpace(100, 100))
        assertEquals(SpaceCheck.NotEnoughSpace(101, 100), ImportPlan.checkSpace(101, 100))
        assertEquals(SpaceCheck.Ok(99), ImportPlan.checkSpace(99, 100))
        assertEquals(SpaceCheck.Ok(0), ImportPlan.checkSpace(0, 0))
        assertEquals(SpaceCheck.NotEnoughSpace(0, -1), ImportPlan.checkSpace(0, -1))
        assertEquals(SpaceCheck.Ok(1_500_000_000_000), ImportPlan.checkSpace(1_500_000_000_000, 1_500_000_000_000))
    }

    @Test
    fun neededIsTheSumOfTheSizesInLong() {
        fun f(size: Long) = SelectedFile("n", "p", size)
        assertEquals(0L, ImportPlan.neededBytes(emptyList()))
        assertEquals(12L, ImportPlan.neededBytes(listOf(f(3), f(4), f(5))))
        // Past the Int range.
        assertEquals(12_000_000_000L, ImportPlan.neededBytes(listOf(f(4_000_000_000), f(4_000_000_000), f(4_000_000_000))))
    }

    @Test
    fun theSumSaturatesInsteadOfWrappingAndIsNeverEnough() {
        fun f(size: Long) = SelectedFile("n", "p", size)
        val needed = ImportPlan.neededBytes(listOf(f(Long.MAX_VALUE), f(1)))
        assertEquals(9_223_372_036_854_775_807L, needed)
        assertEquals(9_223_372_036_854_775_807L, ImportPlan.neededBytes(listOf(f(Long.MAX_VALUE - 1), f(5), f(5))))
        assertEquals(SpaceCheck.NotEnoughSpace(Long.MAX_VALUE, Long.MAX_VALUE), ImportPlan.checkSpace(needed, Long.MAX_VALUE))
        // A wrap would have been negative and would have passed.
        assertTrue(needed > 0)
    }

    // ---- ordered steps ----

    private val a = SelectedFile("A.lod", "Data/a.lod", 5)
    private val b = SelectedFile("B.lod", "B.LOD", 7)

    @Test
    fun theStepsOfAReimportArePinned() {
        val steps = ImportPlan.plan(listOf(a, b), validatorVersion = 3, liveExists = true)
        val manifest = """{"files":[{"name":"A.lod","size":5},{"name":"B.lod","size":7}],"validator_version":3}"""
        val expected = listOf(
            Step.CopyToPart("Data/a.lod", "gamedata.import/A.lod.part", 5),
            Step.SyncFile("gamedata.import/A.lod.part"),
            Step.RenamePart("gamedata.import/A.lod.part", "gamedata.import/A.lod"),
            Step.CopyToPart("B.LOD", "gamedata.import/B.lod.part", 7),
            Step.SyncFile("gamedata.import/B.lod.part"),
            Step.RenamePart("gamedata.import/B.lod.part", "gamedata.import/B.lod"),
            Step.WriteManifest("gamedata.import/manifest.json", manifest),
            Step.SyncFile("gamedata.import/manifest.json"),
            Step.MoveLiveToOld("gamedata", "gamedata.old"),
            Step.PromoteStaging("gamedata.import", "gamedata"),
            Step.DeleteOld("gamedata.old"),
        )
        assertEquals(expected, steps)
    }

    @Test
    fun theFirstImportHasNoLiveFolderToMoveAndNoOldFolderToDelete() {
        val steps = ImportPlan.plan(listOf(a), validatorVersion = 1, liveExists = false)
        val manifest = """{"files":[{"name":"A.lod","size":5}],"validator_version":1}"""
        val expected = listOf(
            Step.CopyToPart("Data/a.lod", "gamedata.import/A.lod.part", 5),
            Step.SyncFile("gamedata.import/A.lod.part"),
            Step.RenamePart("gamedata.import/A.lod.part", "gamedata.import/A.lod"),
            Step.WriteManifest("gamedata.import/manifest.json", manifest),
            Step.SyncFile("gamedata.import/manifest.json"),
            Step.PromoteStaging("gamedata.import", "gamedata"),
        )
        assertEquals(expected, steps)
    }

    @Test
    fun theManifestIsWrittenAfterTheLastRenameAndBeforeAnySwap() {
        val steps = ImportPlan.plan(listOf(a, b), 1, liveExists = true)
        val lastRename = steps.indexOfLast { it is Step.RenamePart }
        val manifest = steps.indexOfFirst { it is Step.WriteManifest }
        val firstSwap = steps.indexOfFirst { it is Step.MoveLiveToOld || it is Step.PromoteStaging }
        assertEquals(5, lastRename)
        assertEquals(6, manifest)
        assertEquals(8, firstSwap)
        assertEquals(1, steps.count { it is Step.WriteManifest })
    }

    @Test
    fun theManifestListsTheFilesSortedByNameWhateverTheCopyOrder() {
        val steps = ImportPlan.plan(listOf(b, a), 2, liveExists = false)
        val w = steps.filterIsInstance<Step.WriteManifest>().single()
        assertEquals("""{"files":[{"name":"A.lod","size":5},{"name":"B.lod","size":7}],"validator_version":2}""", w.content)
        assertEquals(listOf("B.lod", "A.lod"), steps.filterIsInstance<Step.RenamePart>().map { it.to.removePrefix("gamedata.import/") })
    }

    // ---- recovery ----

    private fun recover(live: Boolean, staging: Boolean, old: Boolean, ok: Boolean) =
        ImportPlan.recover(live = live, staging = staging, old = old, liveManifestOk = ok)

    @Test
    fun recoveryTablePinnedForAllEightCombinationsAndBothFlagValues() {
        val none = emptyList<RecoverAction>()
        val ds = RecoverAction.DeleteStaging
        val dold = RecoverAction.DeleteOld
        val dl = RecoverAction.DeleteLive
        val ro = RecoverAction.RestoreOld
        // live, staging, old, liveManifestOk -> actions, in this order.
        val rows = listOf(
            Row(false, false, false, false, none), Row(false, false, false, true, none),
            Row(false, false, true, false, listOf(ro)), Row(false, false, true, true, listOf(ro)),
            Row(false, true, false, false, listOf(ds)), Row(false, true, false, true, listOf(ds)),
            Row(false, true, true, false, listOf(ds, ro)), Row(false, true, true, true, listOf(ds, ro)),
            Row(true, false, false, false, none), Row(true, false, false, true, none),
            Row(true, false, true, false, listOf(dl, ro)), Row(true, false, true, true, listOf(dold)),
            Row(true, true, false, false, listOf(ds)), Row(true, true, false, true, listOf(ds)),
            Row(true, true, true, false, listOf(dl, ro, ds)), Row(true, true, true, true, listOf(ds, dold)),
        )
        assertEquals(16, rows.size)
        for (r in rows) {
            assertEquals(r.expected, recover(r.live, r.staging, r.old, r.ok), "live=${r.live} staging=${r.staging} old=${r.old} ok=${r.ok}")
        }
    }

    private data class Row(val live: Boolean, val staging: Boolean, val old: Boolean, val ok: Boolean, val expected: List<RecoverAction>)

    @Test
    fun stagingIsNeverPromotedByRecoveryAndNeverSurvivesIt() {
        for (live in listOf(false, true)) for (old in listOf(false, true)) for (ok in listOf(false, true)) {
            val actions = recover(live, staging = true, old = old, ok = ok)
            assertTrue(RecoverAction.DeleteStaging in actions, "live=$live old=$old ok=$ok")
        }
    }

    // ---- crash simulation: a model of the three folders, a crash after every step ----

    private enum class Content { OldSet, NewSet, Partial }

    private class Disk(var live: Content?, var staging: Content? = null, var old: Content? = null) {
        fun copy() = Disk(live, staging, old)
        val liveOk get() = live == Content.OldSet || live == Content.NewSet
    }

    private fun run(d: Disk, s: Step) {
        when (s) {
            is Step.CopyToPart, is Step.RenamePart -> d.staging = Content.Partial
            is Step.SyncFile -> check(d.staging != null)
            is Step.WriteManifest -> { check(d.staging != null); d.staging = Content.NewSet }
            is Step.MoveLiveToOld -> { check(d.live != null && d.old == null); d.old = d.live; d.live = null }
            is Step.PromoteStaging -> { check(d.live == null && d.staging != null); d.live = d.staging; d.staging = null }
            is Step.DeleteOld -> d.old = null
        }
    }

    private fun apply(d: Disk, a: RecoverAction) {
        when (a) {
            RecoverAction.DeleteStaging -> d.staging = null
            RecoverAction.DeleteOld -> d.old = null
            RecoverAction.DeleteLive -> d.live = null
            RecoverAction.RestoreOld -> { check(d.live == null && d.old != null); d.live = d.old; d.old = null }
        }
    }

    private fun recoverAll(d: Disk) {
        for (a in ImportPlan.recover(d.live != null, d.staging != null, d.old != null, d.liveOk)) apply(d, a)
    }

    @Test
    fun aCrashAfterAnyStepRecoversToTheOldOrTheNewCompleteSetNeverAPartialOne() {
        for (prior in listOf<Content?>(null, Content.OldSet)) {
            val steps = ImportPlan.plan(listOf(a, b), 1, liveExists = prior != null)
            val promote = steps.indexOfFirst { it is Step.PromoteStaging }
            for (k in 0..steps.size) {
                val d = Disk(prior)
                for (i in 0 until k) {
                    run(d, steps[i])
                    assertTrue(d.live != Content.Partial, "partial set visible after step $i")
                }
                recoverAll(d)
                val expected = if (k <= promote) prior else Content.NewSet
                assertEquals(expected, d.live, "prior=$prior crash after $k steps")
                assertEquals(null, d.staging, "staging left, prior=$prior k=$k")
                assertEquals(null, d.old, "old left, prior=$prior k=$k")
                assertEquals(emptyList(), ImportPlan.recover(d.live != null, d.staging != null, d.old != null, d.liveOk), "not stable, k=$k")
            }
        }
    }

    @Test
    fun aCrashDuringRecoveryItselfStillEndsOnACompleteSet() {
        val steps = ImportPlan.plan(listOf(a, b), 1, liveExists = true)
        for (k in 0..steps.size) {
            val start = Disk(Content.OldSet)
            for (i in 0 until k) run(start, steps[i])
            val actions = ImportPlan.recover(start.live != null, start.staging != null, start.old != null, start.liveOk)
            for (j in 0..actions.size) {
                val d = start.copy()
                for (i in 0 until j) apply(d, actions[i])
                assertTrue(d.live != Content.Partial)
                recoverAll(d)
                assertTrue(d.liveOk, "k=$k j=$j")
                assertEquals(null, d.staging)
                assertEquals(null, d.old)
            }
        }
    }

    @Test
    fun aDamagedLiveFolderBesideAnOldOneIsReplacedByTheOldOne() {
        // live exists but its manifest is not ok, and the previous generation is still there.
        val d = Disk(live = Content.Partial, old = Content.OldSet)
        recoverAll(d)
        assertEquals(Disk(Content.OldSet).let { Triple(it.live, it.staging, it.old) }, Triple(d.live, d.staging, d.old))
    }

    // ---- status ----

    private val manifest = Manifest(1, listOf(ManifestFile("A.lod", 5), ManifestFile("B.lod", 7)))

    @Test
    fun statusFoundMissingChanged() {
        assertEquals(DataStatus.Found, ImportPlan.status(manifest, mapOf("A.lod" to 5L, "B.lod" to 7L)))
        assertEquals(DataStatus.Found, ImportPlan.status(manifest, mapOf("A.lod" to 5L, "B.lod" to 7L, "extra.bin" to 1L)))
        assertEquals(DataStatus.Missing, ImportPlan.status(manifest, mapOf("A.lod" to 5L)))
        assertEquals(DataStatus.Missing, ImportPlan.status(manifest, emptyMap()))
        assertEquals(DataStatus.Changed, ImportPlan.status(manifest, mapOf("A.lod" to 5L, "B.lod" to 8L)))
        assertEquals(DataStatus.Changed, ImportPlan.status(manifest, mapOf("A.lod" to 4L, "B.lod" to 7L)))
        assertEquals(DataStatus.Changed, ImportPlan.status(manifest, mapOf("A.lod" to 0L, "B.lod" to 7L)))
    }

    @Test
    fun aMissingFileOutranksAChangedOneRegardlessOfOrder() {
        assertEquals(DataStatus.Missing, ImportPlan.status(manifest, mapOf("A.lod" to 99L)))
        assertEquals(DataStatus.Missing, ImportPlan.status(manifest, mapOf("B.lod" to 99L)))
    }

    @Test
    fun noManifestOrAnEmptyOneIsMissingAndNamesAreCaseSensitive() {
        assertEquals(DataStatus.Missing, ImportPlan.status(null, mapOf("A.lod" to 5L)))
        assertEquals(DataStatus.Missing, ImportPlan.status(Manifest(1, emptyList()), mapOf("A.lod" to 5L)))
        assertEquals(DataStatus.Missing, ImportPlan.status(manifest, mapOf("a.lod" to 5L, "b.lod" to 7L)))
    }

    // ---- manifest ----

    @Test
    fun encodingIsCanonicalCompactSortedJson() {
        val m = Manifest(2, listOf(ManifestFile("b.lod", 1), ManifestFile("A.lod", 22), ManifestFile("a.lod", 3)))
        assertEquals(
            """{"files":[{"name":"A.lod","size":22},{"name":"a.lod","size":3},{"name":"b.lod","size":1}],"validator_version":2}""",
            ImportPlan.encodeManifest(m),
        )
        assertEquals("""{"files":[],"validator_version":0}""", ImportPlan.encodeManifest(Manifest(0, emptyList())))
    }

    @Test
    fun namesAreSortedByCodePointNotByUtf16Unit() {
        // U+FF5E (one UTF-16 unit, 0xFF5E) sorts before U+10000 (a surrogate pair, first unit 0xD800) by
        // code point, but after it by UTF-16 units.
        val m = Manifest(1, listOf(ManifestFile("\uff5e", 1), ManifestFile("\ud800\udc00", 2)))
        assertEquals(
            """{"files":[{"name":"\uff5e","size":1},{"name":"\ud800\udc00","size":2}],"validator_version":1}""",
            ImportPlan.encodeManifest(m),
        )
    }

    @Test
    fun stringsAreEscapedAndOutputIsAscii() {
        val m = Manifest(1, listOf(ManifestFile("q\"x\u00e9\u007f\t", 1)))
        assertEquals("""{"files":[{"name":"q\"x\u00e9\u007f\u0009","size":1}],"validator_version":1}""", ImportPlan.encodeManifest(m))
    }

    @Test
    fun decodeReadsWhatEncodeWrites() {
        val m = Manifest(7, listOf(ManifestFile("A.lod", 5), ManifestFile("q\"x\u00e9\ud800\udc00", 9_000_000_000), ManifestFile("z", 0)))
        assertEquals(ManifestParse.Parsed(m), ImportPlan.decodeManifest(ImportPlan.encodeManifest(m)))
        val unsorted = Manifest(7, listOf(ManifestFile("z", 0), ManifestFile("A.lod", 5)))
        val back = assertIs<ManifestParse.Parsed>(ImportPlan.decodeManifest(ImportPlan.encodeManifest(unsorted))).manifest
        assertEquals(listOf("A.lod", "z"), back.files.map { it.name })
    }

    @Test
    fun decodeAcceptsWhitespaceAndAnyKeyOrder() {
        val text = " {\n \"validator_version\" : 4 ,\r\n\t\"files\":[ { \"size\":5 , \"name\":\"A.lod\" } ] } \n"
        assertEquals(ManifestParse.Parsed(Manifest(4, listOf(ManifestFile("A.lod", 5)))), ImportPlan.decodeManifest(text))
        assertEquals(
            ManifestParse.Parsed(Manifest(1, listOf(ManifestFile("\u00e9\u00e9", 1)))),
            ImportPlan.decodeManifest("""{"files":[{"name":"\u00e9\u00E9","size":1}],"validator_version":1}"""),
        )
    }

    @Test
    fun decodeLimits() {
        val ok = ImportPlan.decodeManifest("""{"files":[{"name":"a","size":9223372036854775807}],"validator_version":2147483647}""")
        assertEquals(ManifestParse.Parsed(Manifest(Int.MAX_VALUE, listOf(ManifestFile("a", Long.MAX_VALUE)))), ok)
        assertEquals(
            ManifestParse.Failed(ManifestError.NumberTooLarge, 29),
            ImportPlan.decodeManifest("""{"files":[{"name":"a","size":9223372036854775808}],"validator_version":1}"""),
        )
        assertEquals(
            ManifestParse.Failed(ManifestError.NumberTooLarge, 53),
            ImportPlan.decodeManifest("""{"files":[{"name":"a","size":1}],"validator_version":2147483648}"""),
        )
    }

    private fun fail(text: String): ManifestParse.Failed = assertIs<ManifestParse.Failed>(ImportPlan.decodeManifest(text), text)

    private val head = """{"files":[{"name":"a","size":1}],"validator_version":1}"""

    @Test
    fun namedParseErrorsWithOffsets() {
        assertEquals(ManifestParse.Failed(ManifestError.UnexpectedEnd, 0), fail(""))
        assertEquals(ManifestParse.Failed(ManifestError.UnexpectedEnd, 3), fail("   "))
        assertEquals(ManifestParse.Failed(ManifestError.WrongType, 0), fail("[]"))
        assertEquals(ManifestParse.Failed(ManifestError.Syntax, 0), fail("x"))
        assertEquals(ManifestParse.Failed(ManifestError.TrailingData, 56), fail("$head x"))
        assertEquals(ManifestParse.Failed(ManifestError.UnknownKey, 1), fail("""{"extra":1}"""))
        assertEquals(ManifestParse.Failed(ManifestError.DuplicateKey, 23), fail("""{"validator_version":1,"validator_version":2}"""))
        assertEquals(ManifestParse.Failed(ManifestError.MissingKey, 22), fail("""{"validator_version":1}"""))
        assertEquals(ManifestParse.Failed(ManifestError.MissingKey, 32), fail("""{"files":[{"name":"a","size":1}]}"""))
        assertEquals(ManifestParse.Failed(ManifestError.NoFiles, 9), fail("""{"files":[],"validator_version":1}"""))
        assertEquals(ManifestParse.Failed(ManifestError.WrongType, 29), fail("""{"files":[{"name":"a","size":"1"}],"validator_version":1}"""))
        assertEquals(ManifestParse.Failed(ManifestError.WrongType, 53), fail("""{"files":[{"name":"a","size":1}],"validator_version":"1"}"""))
        assertEquals(ManifestParse.Failed(ManifestError.MissingKey, 21), fail("""{"files":[{"name":"a"}],"validator_version":1}"""))
    }

    @Test
    fun parseErrorKindsForBrokenValues() {
        fun kind(text: String) = fail(text).error
        val pre = """{"files":[{"name":"a","size":"""
        val post = """}],"validator_version":1}"""
        assertEquals(ManifestError.BadNumber, kind(pre + "-1" + post))
        assertEquals(ManifestError.BadNumber, kind(pre + "01" + post))
        assertEquals(ManifestError.BadNumber, kind(pre + "1.5" + post))
        assertEquals(ManifestError.BadNumber, kind(pre + "1e3" + post))
        assertEquals(ManifestError.BadNumber, kind(pre + "1E3" + post))
        assertEquals(ManifestError.WrongType, kind(pre + "true" + post))
        assertEquals(ManifestError.WrongType, kind(pre + "null" + post))
        assertEquals(ManifestError.WrongType, kind(pre + "[1]" + post))
        assertEquals(ManifestError.Syntax, kind(pre + "+" + post))
        assertEquals(ManifestError.UnexpectedEnd, kind(pre))
        val n = """{"files":[{"size":1,"name":"""
        val np = """}],"validator_version":1}"""
        assertEquals(ManifestError.BadString, kind(n + "\"a\\qb\"" + np))
        assertEquals(ManifestError.BadString, kind(n + "\"a\\u12g4\"" + np))
        assertEquals(ManifestError.BadString, kind(n + "\"a\\u12\"" + np))
        assertEquals(ManifestError.BadString, kind(n + "\"a\tb\"" + np))
        assertEquals(ManifestError.UnexpectedEnd, kind(n + "\"abc"))
        assertEquals(ManifestError.BadName, kind(n + "\"\"" + np))
        assertEquals(ManifestError.BadName, kind(n + "\"a/b\"" + np))
        assertEquals(ManifestError.BadName, kind(n + "\"..\"" + np))
        assertEquals(ManifestError.BadName, kind(n + "\"manifest.json\"" + np))
        assertEquals(ManifestError.BadName, kind(n + "\"a.part\"" + np))
        assertEquals(ManifestError.BadName, kind(n + "\"a\\u0000b\"" + np))
        assertEquals(ManifestError.DuplicateName, kind("""{"files":[{"name":"a","size":1},{"name":"a","size":1}],"validator_version":1}"""))
        assertEquals(ManifestError.DuplicateName, kind("""{"files":[{"name":"a","size":1},{"name":"A","size":1}],"validator_version":1}"""))
        assertEquals(ManifestError.UnknownKey, kind("""{"files":[{"name":"a","size":1,"sha":"x"}],"validator_version":1}"""))
        assertEquals(ManifestError.DuplicateKey, kind("""{"files":[{"name":"a","name":"b","size":1}],"validator_version":1}"""))
        assertEquals(ManifestError.MissingKey, kind("""{"files":[{"name":"a"}],"validator_version":1}"""))
    }

    @Test
    fun decodeNeverThrowsAndEveryTruncationFails() {
        val full = ImportPlan.encodeManifest(Manifest(3, listOf(ManifestFile("A.lod", 5), ManifestFile("B\u00e9.lod", 77))))
        assertIs<ManifestParse.Parsed>(ImportPlan.decodeManifest(full))
        for (n in 0 until full.length) {
            assertIs<ManifestParse.Failed>(ImportPlan.decodeManifest(full.substring(0, n)), "prefix $n")
        }
        val noise = listOf('"', '\\', '{', '}', '[', ']', ',', ':', '-', '0', '9', 'e', '.', 'u', '\u0000', '\uD800', ' ')
        for (i in full.indices) for (c in noise) {
            val r = ImportPlan.decodeManifest(full.substring(0, i) + c + full.substring(i + 1))
            assertTrue(r is ManifestParse.Parsed || r is ManifestParse.Failed)
        }
    }

    // ---- progress ----

    @Test
    fun percentIsAnIntegerFloor() {
        assertEquals(0, Progress(0, 10).percent)
        assertEquals(33, Progress(1, 3).percent)
        assertEquals(66, Progress(2, 3).percent)
        assertEquals(100, Progress(3, 3).percent)
        assertEquals(99, Progress(99, 100).percent)
        assertEquals(0, Progress(1, 200).percent)
        assertEquals(99, Progress(199, 200).percent)
        assertEquals(50, Progress(5, 10).percent)
        assertEquals(10, Progress(1, 10).percent)
    }

    @Test
    fun percentIsTotalZeroSafeAndClamped() {
        assertEquals(0, Progress(0, 0).percent)
        assertEquals(0, Progress(5, 0).percent)
        assertEquals(0, Progress(5, -3).percent)
        assertEquals(0, Progress(-5, 10).percent)
        assertEquals(100, Progress(20, 10).percent)
    }

    @Test
    fun percentDoesNotOverflowOnHugeByteCounts() {
        assertEquals(49, Progress(Long.MAX_VALUE / 2, Long.MAX_VALUE).percent)
        assertEquals(99, Progress(Long.MAX_VALUE - 1, Long.MAX_VALUE).percent)
        assertEquals(100, Progress(Long.MAX_VALUE, Long.MAX_VALUE).percent)
        assertEquals(75, Progress(3_000_000_000_000_000_000, 4_000_000_000_000_000_000).percent)
        assertFalse(Progress(1, Long.MAX_VALUE).percent < 0)
    }
}
