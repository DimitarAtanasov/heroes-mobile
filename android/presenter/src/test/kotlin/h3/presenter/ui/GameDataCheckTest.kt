package h3.presenter.ui

import java.io.ByteArrayOutputStream
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

// ---- synthetic fixtures built here; no game data. Names are prefixed gd to stay clear of other files. ----

private const val MARKER = "ZZPAYLOADZZ"

private fun ByteArrayOutputStream.gdLe32(v: Int) { for (i in 0 until 4) write((v shr (8 * i)) and 0xFF) }

/** A stored (uncompressed) LOD archive with the given members, in order. */
private fun gdLod(vararg members: Pair<String, ByteArray>): ByteArray {
    val out = ByteArrayOutputStream()
    out.write(byteArrayOf('L'.code.toByte(), 'O'.code.toByte(), 'D'.code.toByte(), 0))
    out.gdLe32(200); out.gdLe32(members.size)
    out.write(ByteArray(80))
    var off = 92 + 32 * members.size
    for ((name, data) in members) {
        out.write(name.toByteArray(Charsets.ISO_8859_1).copyOf(16))
        out.gdLe32(off); out.gdLe32(data.size); out.gdLe32(0); out.gdLe32(0)
        off += data.size
    }
    for ((_, data) in members) out.write(data)
    return out.toByteArray()
}

private fun gdBytes(s: String): ByteArray = s.toByteArray(Charsets.ISO_8859_1)

/** A bitmap archive with CRTRAITS.TXT (the content is a marker: it must never be decoded or echoed). */
private fun gdBitmap(): ByteArray = gdLod("CRTRAITS.TXT" to gdBytes(MARKER), "OTHER.PCX" to gdBytes("x"))

/** A valid archive without CRTRAITS.TXT. */
private fun gdPlain(): ByteArray = gdLod("SOMETHING.DEF" to gdBytes(MARKER))

/** Header that passes the magic check but claims more entries than the file holds. */
private fun gdCorruptHeader(): ByteArray {
    val out = ByteArrayOutputStream()
    out.write(byteArrayOf('L'.code.toByte(), 'O'.code.toByte(), 'D'.code.toByte(), 0))
    out.gdLe32(200); out.gdLe32(5)
    out.write(ByteArray(80))
    out.write(gdBytes(MARKER))
    return out.toByteArray()
}

private class Fs(val files: List<Pair<String, ByteArray>>) {
    val reads = ArrayList<String>()
    val entries: List<GameFile> get() = files.map { GameFile(it.first, it.second.size.toLong()) }
    fun read(path: String): ByteArray {
        reads.add(path)
        return files.first { it.first == path }.second
    }
}

private fun standardSet(prefix: String = "Data/"): List<Pair<String, ByteArray>> = listOf(
    prefix + "H3bitmap.lod" to gdBitmap(),
    prefix + "H3sprite.lod" to gdPlain(),
    prefix + "H3ab_bmp.lod" to gdPlain(),
    prefix + "H3ab_spr.lod" to gdPlain(),
)

private fun GameDataResult.issues(): List<GameDataIssue> = (this as? GameDataResult.Invalid)?.issues ?: emptyList()

private fun allText(r: GameDataResult): String =
    r.describe() + "|" + r.code + "|" + r.issues().joinToString("|") { it.code + ":" + it.describe() }

class GameDataCheckTest {
    private fun run(fs: Fs, required: List<String> = GameDataCheck.DEFAULT_REQUIRED): GameDataResult =
        GameDataCheck.check(fs.entries, fs::read, required)

    // ---- V1 presence ----

    @Test
    fun theDefaultRequiredSetIsTheFourSodArchives() {
        assertEquals(listOf("H3bitmap.lod", "H3sprite.lod", "H3ab_bmp.lod", "H3ab_spr.lod"), GameDataCheck.DEFAULT_REQUIRED)
    }

    @Test
    fun allFourInDataPass() {
        val fs = Fs(standardSet())
        val r = run(fs)
        val ok = assertIs<GameDataResult.Ok>(r)
        assertEquals("OK", r.code)
        // Sorted by code point of the normalized (lower-cased) name.
        assertEquals(listOf("H3ab_bmp.lod", "H3ab_spr.lod", "H3bitmap.lod", "H3sprite.lod"), ok.files.map { it.name })
        assertEquals(
            listOf("Data/H3ab_bmp.lod", "Data/H3ab_spr.lod", "Data/H3bitmap.lod", "Data/H3sprite.lod").map { p -> fs.files.first { it.first == p }.second.size.toLong() },
            ok.files.map { it.size },
        )
        assertEquals("OK 4 files", r.describe())
    }

    @Test
    fun allFourInTheRootPass() {
        assertIs<GameDataResult.Ok>(run(Fs(standardSet(""))))
    }

    @Test
    fun mixedCaseNamesMatchInRootAndInData() {
        val fs = Fs(
            listOf(
                "DATA/H3BITMAP.LOD" to gdBitmap(),
                "data/h3SPRITE.lod" to gdPlain(),
                "h3ab_BMP.Lod" to gdPlain(),
                "H3AB_SPR.LOD" to gdPlain(),
            ),
        )
        assertIs<GameDataResult.Ok>(run(fs))
    }

    @Test
    fun backslashSeparatorsAreAccepted() {
        val fs = Fs(standardSet("Data\\"))
        assertIs<GameDataResult.Ok>(run(fs))
    }

    @Test
    fun onlyTheRootAndAFolderNamedDataCount() {
        val deep = Fs(standardSet("Game/Data/"))
        assertEquals(4, run(deep).issues().size)
        val sub = Fs(standardSet("Data/Sub/"))
        assertEquals(4, run(sub).issues().size)
        val other = Fs(standardSet("Datum/"))
        assertEquals(4, run(other).issues().size)
        val namesakeDir = Fs(listOf("Data/H3bitmap.lod/inner" to gdBitmap()) + standardSet().drop(1))
        assertEquals(listOf("MISSING_REQUIRED"), run(namesakeDir).issues().map { it.code })
    }

    @Test
    fun lookalikeCharactersDoNotMatchAscii() {
        // dotless i and the Kelvin sign fold to ASCII under Unicode case mapping; they must not here.
        val fs = Fs(
            listOf(
                "Data/H3bıtmap.lod" to gdBitmap(),
                "Data/H3sprite.lod" to gdPlain(),
                "Data/H3ab_bmp.lod" to gdPlain(),
                "Data/H3ab_spr.lod" to gdPlain(),
            ),
        )
        assertEquals(listOf("MISSING_REQUIRED"), run(fs).issues().map { it.code })
    }

    @Test
    fun caseFoldingIsAsciiOnly() {
        // The Kelvin sign lower-cases to ASCII k under Unicode rules; it must not match here.
        val kelvin = Fs(listOf("Data/\u212A.lod" to gdPlain()))
        assertEquals(listOf("MISSING_REQUIRED"), run(kelvin, listOf("k.lod")).issues().map { it.code })
        val ascii = Fs(listOf("Data/K.LOD" to gdPlain()))
        assertIs<GameDataResult.Ok>(run(ascii, listOf("k.lod")))
    }

    @Test
    fun eachRequiredFileMissingIsReportedByName() {
        val names = listOf("H3bitmap.lod", "H3sprite.lod", "H3ab_bmp.lod", "H3ab_spr.lod")
        for (missing in names) {
            val fs = Fs(standardSet().filterNot { it.first == "Data/$missing" })
            val issues = run(fs).issues()
            assertEquals(1, issues.size, missing)
            val m = assertIs<GameDataIssue.MissingRequired>(issues[0])
            assertEquals(missing, m.file)
            assertEquals("MISSING_REQUIRED", m.code)
            assertTrue(m.describe().contains(missing), m.describe())
            assertFalse(fs.reads.contains("Data/$missing"))
        }
    }

    @Test
    fun noFilesAtAllReportsAllFourSortedByName() {
        val issues = run(Fs(emptyList())).issues()
        assertEquals(
            listOf("H3ab_bmp.lod", "H3ab_spr.lod", "H3bitmap.lod", "H3sprite.lod"),
            issues.map { (it as GameDataIssue.MissingRequired).file },
        )
    }

    @Test
    fun dataFolderWinsOverRootAndDuplicatesAreStable() {
        val files = listOf(
            "H3sprite.lod" to gdBytes("root copy is junk, not a LOD at all, padded to be long enough to pass the floor ......................"),
            "Data/H3sprite.lod" to gdPlain(),
            "data/H3SPRITE.LOD" to gdPlain(),
        ) + standardSet().filterNot { it.first.endsWith("H3sprite.lod") }
        val a = Fs(files)
        assertIs<GameDataResult.Ok>(run(a))
        assertEquals(1, a.reads.count { it.lowercase().endsWith("h3sprite.lod") })
        assertEquals("Data/H3sprite.lod", a.reads.first { it.lowercase().endsWith("h3sprite.lod") })
        // Same input in another order: same read, same result.
        val b = Fs(files.reversed())
        assertIs<GameDataResult.Ok>(run(b))
        assertEquals("Data/H3sprite.lod", b.reads.first { it.lowercase().endsWith("h3sprite.lod") })
    }

    @Test
    fun theRequiredSetIsAParameter() {
        val fs = Fs(listOf("Data/H3sprite.lod" to gdPlain()))
        val dup = assertIs<GameDataResult.Ok>(run(fs, listOf("h3sprite.LOD", "H3SPRITE.lod")))
        assertEquals(listOf(CheckedFile("h3sprite.LOD", gdPlain().size.toLong())), dup.files)
        assertEquals(1, run(Fs(emptyList()), listOf("Extra.lod", "EXTRA.LOD")).issues().size)
        val r = run(fs, listOf("H3sprite.lod", "Extra.lod"))
        assertEquals(listOf("Extra.lod"), r.issues().map { (it as GameDataIssue.MissingRequired).file })
        // An empty required set has nothing to check (and so no CRTRAITS check).
        assertEquals("OK 0 files", run(Fs(emptyList()), emptyList()).describe())
    }

    @Test
    fun issuesSortByCodePointNotByUtf16Unit() {
        // U+1F600 is the surrogate pair D83D DE00; U+FF21 is a single unit above it. By code point
        // U+FF21 < U+1F600; by UTF-16 unit order it would be the other way round.
        val r = run(Fs(emptyList()), listOf("😀.lod", "Ａ.lod"))
        assertEquals(listOf("Ａ.lod", "😀.lod"), r.issues().map { (it as GameDataIssue.MissingRequired).file })
    }

    // ---- V2 size and parse ----

    @Test
    fun aFileBelowTheHeaderSizeIsNotAnArchiveAndIsNotRead() {
        for (size in listOf(0L, 1L, 91L)) {
            val fs = Fs(standardSet().drop(1))
            val entries = fs.entries + GameFile("Data/H3bitmap.lod", size)
            val r = GameDataCheck.check(entries, fs::read)
            val i = assertIs<GameDataIssue.NotAnArchive>(r.issues().single(), "size $size")
            assertEquals("NOT_AN_ARCHIVE", i.code)
            assertEquals("H3bitmap.lod", i.file)
            assertEquals(size, i.size)
            assertFalse(fs.reads.contains("Data/H3bitmap.lod"), "size $size must not be read")
        }
    }

    @Test
    fun aNegativeSizeIsNotAnArchive() {
        val fs = Fs(standardSet().drop(1))
        val r = GameDataCheck.check(fs.entries + GameFile("Data/H3bitmap.lod", -1L), fs::read)
        assertIs<GameDataIssue.NotAnArchive>(r.issues().single())
    }

    @Test
    fun ninetyTwoBytesIsTheSmallestSizeThatIsRead() {
        val header92 = gdLod()
        assertEquals(92, header92.size)
        val fs = Fs(listOf("Data/H3sprite.lod" to header92))
        assertIs<GameDataResult.Ok>(run(fs, listOf("H3sprite.lod")))
        assertEquals(listOf("Data/H3sprite.lod"), fs.reads)
        val fs91 = Fs(listOf("Data/H3sprite.lod" to header92.copyOf(91)))
        assertIs<GameDataIssue.NotAnArchive>(run(fs91, listOf("H3sprite.lod")).issues().single())
    }

    @Test
    fun theSizeCapIs512MiBInclusive() {
        assertEquals(536_870_912L, GameDataCheck.MAX_CHECKABLE_BYTES)
        val good = gdPlain()
        var reads = 0
        val read = { _: String -> reads++; good }
        // Exactly at the cap: read and checked.
        val atCap = GameDataCheck.check(listOf(GameFile("H3sprite.lod", 536_870_912L)), read, listOf("H3sprite.lod"))
        assertIs<GameDataResult.Ok>(atCap)
        assertEquals(1, reads)
        // One byte over: refused before any read.
        val over = GameDataCheck.check(listOf(GameFile("H3sprite.lod", 536_870_913L)), read, listOf("H3sprite.lod"))
        val i = assertIs<GameDataIssue.TooLargeToCheck>(over.issues().single())
        assertEquals("TOO_LARGE_TO_CHECK", i.code)
        assertEquals(536_870_913L, i.size)
        assertEquals(1, reads, "an over-cap file must not be read")
        val huge = GameDataCheck.check(listOf(GameFile("H3sprite.lod", Long.MAX_VALUE)), read, listOf("H3sprite.lod"))
        assertIs<GameDataIssue.TooLargeToCheck>(huge.issues().single())
        assertEquals(1, reads)
    }

    @Test
    fun outOfMemoryFromTheReaderIsTooLargeToCheck() {
        val fs = Fs(standardSet())
        val r = GameDataCheck.check(fs.entries, { p -> if (p.endsWith("H3sprite.lod")) throw OutOfMemoryError(MARKER) else fs.read(p) })
        val i = assertIs<GameDataIssue.TooLargeToCheck>(r.issues().single())
        assertEquals("H3sprite.lod", i.file)
    }

    @Test
    fun aReaderFailureIsUnreadableAndOthersStillRun() {
        val fs = Fs(standardSet())
        val r = GameDataCheck.check(fs.entries, { p -> if (p.endsWith("H3ab_bmp.lod")) throw java.io.IOException(MARKER) else fs.read(p) })
        val i = assertIs<GameDataIssue.Unreadable>(r.issues().single())
        assertEquals("UNREADABLE", i.code)
        assertEquals("H3ab_bmp.lod", i.file)
        assertEquals(4, fs.reads.size + 1)
    }

    @Test
    fun badMagicIsNotAnArchive() {
        val notLod = gdBytes("PK\u0003\u0004" + "x".repeat(200))
        val fs = Fs(standardSet().map { if (it.first.endsWith("H3ab_spr.lod")) it.first to notLod else it })
        val i = assertIs<GameDataIssue.NotAnArchive>(run(fs).issues().single())
        assertEquals("H3ab_spr.lod", i.file)
        assertEquals(204L, i.size)
    }

    @Test
    fun aValidMagicWithABrokenDirectoryIsCorrupt() {
        val bad = gdCorruptHeader()
        val fs = Fs(standardSet().map { if (it.first.endsWith("H3ab_spr.lod")) it.first to bad else it })
        val i = assertIs<GameDataIssue.CorruptArchive>(run(fs).issues().single())
        assertEquals("CORRUPT_ARCHIVE", i.code)
        assertEquals("H3ab_spr.lod", i.file)
        assertEquals(bad.size.toLong(), i.size)
    }

    @Test
    fun aTruncatedRealArchiveIsCorrupt() {
        val truncated = gdPlain().copyOf(100)
        val fs = Fs(standardSet().map { if (it.first.endsWith("H3sprite.lod")) it.first to truncated else it })
        assertIs<GameDataIssue.CorruptArchive>(run(fs).issues().single())
        val cut = gdPlain().copyOf(95)
        val fs2 = Fs(standardSet().map { if (it.first.endsWith("H3sprite.lod")) it.first to cut else it })
        assertIs<GameDataIssue.CorruptArchive>(run(fs2).issues().single())
    }

    @Test
    fun anyFailureInsideOpenIsContainedAndOutOfMemoryIsTooLarge() {
        val fs = Fs(listOf("Data/H3sprite.lod" to gdPlain()))
        val req = listOf("H3sprite.lod")
        val oom = GameDataCheck.check(fs.entries, fs::read, req) { throw OutOfMemoryError(MARKER) }
        assertIs<GameDataIssue.TooLargeToCheck>(oom.issues().single())
        for (ex in listOf<Throwable>(IndexOutOfBoundsException(MARKER), IllegalStateException(MARKER), StackOverflowError())) {
            val r = GameDataCheck.check(fs.entries, fs::read, req) { throw ex }
            assertIs<GameDataIssue.CorruptArchive>(r.issues().single(), ex.toString())
            assertFalse(allText(r).contains(MARKER))
        }
    }

    @Test
    fun aReaderReturningFewerBytesThanListedIsStillClassified() {
        val fs = Fs(standardSet().drop(1))
        val entries = fs.entries + GameFile("Data/H3bitmap.lod", 5000L)
        val r = GameDataCheck.check(entries, { p -> if (p.endsWith("H3bitmap.lod")) ByteArray(10) else fs.read(p) })
        assertIs<GameDataIssue.NotAnArchive>(r.issues().single())
    }

    // ---- V3 CRTRAITS.TXT ----

    @Test
    fun crtraitsMissingFromTheBitmapArchiveIsReported() {
        val fs = Fs(standardSet().map { if (it.first.endsWith("H3bitmap.lod")) it.first to gdPlain() else it })
        val i = assertIs<GameDataIssue.MissingMember>(run(fs).issues().single())
        assertEquals("MISSING_MEMBER", i.code)
        assertEquals("H3bitmap.lod", i.archive)
        assertEquals("CRTRAITS.TXT", i.member)
        assertEquals("MISSING_MEMBER H3bitmap.lod: CRTRAITS.TXT", i.describe())
    }

    @Test
    fun crtraitsMatchesCaseInsensitivelyAndIsNeverDecoded() {
        // Lower-case member name; its content is not a table, and it is declared compressed with
        // garbage (packed size 1 but never inflated): a read would throw, a contains must not.
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf('L'.code.toByte(), 'O'.code.toByte(), 'D'.code.toByte(), 0))
        out.gdLe32(200); out.gdLe32(1); out.write(ByteArray(80))
        out.write(gdBytes("crtraits.txt").copyOf(16))
        out.gdLe32(124); out.gdLe32(999); out.gdLe32(0); out.gdLe32(1)
        out.write(0x7F)
        val bitmap = out.toByteArray()
        val fs = Fs(standardSet().map { if (it.first.endsWith("H3bitmap.lod")) it.first to bitmap else it })
        assertIs<GameDataResult.Ok>(run(fs))
    }

    @Test
    fun crtraitsInAnotherArchiveDoesNotCount() {
        val fs = Fs(
            standardSet().map {
                when {
                    it.first.endsWith("H3bitmap.lod") -> it.first to gdPlain()
                    it.first.endsWith("H3sprite.lod") -> it.first to gdBitmap()
                    else -> it
                }
            },
        )
        assertEquals(listOf("MISSING_MEMBER"), run(fs).issues().map { it.code })
    }

    @Test
    fun aBrokenBitmapArchiveGetsOneIssueNotAlsoAMissingMember() {
        val fs = Fs(standardSet().map { if (it.first.endsWith("H3bitmap.lod")) it.first to gdCorruptHeader() else it })
        assertEquals(listOf("CORRUPT_ARCHIVE"), run(fs).issues().map { it.code })
    }

    @Test
    fun crtraitsIsNotCheckedWhenTheBitmapArchiveIsNotRequired() {
        val fs = Fs(listOf("Data/H3bitmap.lod" to gdPlain(), "Data/H3sprite.lod" to gdPlain()))
        assertIs<GameDataResult.Ok>(run(fs, listOf("H3sprite.lod")))
        assertTrue(fs.reads.none { it.endsWith("H3bitmap.lod") })
    }

    @Test
    fun eachFileIsReadAtMostOnce() {
        val fs = Fs(standardSet())
        run(fs)
        assertEquals(fs.reads.sorted(), fs.reads.distinct().sorted())
        assertEquals(4, fs.reads.size)
    }

    // ---- .pak hint (open decision G5) ----

    @Test
    fun pakFilesAddAnHdHintToMissingRequiredOnly() {
        val withoutPak = run(Fs(emptyList())).issues()
        val withPak = run(Fs(listOf("Data/H3bitmap.pak" to gdPlain(), "Data/H3sprite.PAK" to gdPlain()))).issues()
        assertEquals(4, withPak.size)
        for (i in withPak) {
            val m = assertIs<GameDataIssue.MissingRequired>(i)
            assertTrue(m.hdHint)
            assertTrue(m.describe().contains("HD Edition"), m.describe())
            assertEquals("MISSING_REQUIRED", m.code)
        }
        for (i in withoutPak) {
            assertFalse((i as GameDataIssue.MissingRequired).hdHint)
            assertFalse(i.describe().contains("HD"), i.describe())
        }
        // The code is the same with and without the hint.
        assertEquals(withoutPak.map { it.code }, withPak.map { it.code })
    }

    @Test
    fun pakFilesRefuseNothingWhenTheRequiredSetIsComplete() {
        val files = standardSet() + ("Data/H3bitmap.pak" to gdPlain()) + ("HD_Launcher.pak" to gdPlain())
        val r = run(Fs(files))
        val ok = assertIs<GameDataResult.Ok>(r)
        assertEquals(4, ok.files.size)
        assertFalse(r.describe().contains("HD"))
    }

    @Test
    fun theHdHintIsNotAddedToOtherIssues() {
        val files = standardSet().map { if (it.first.endsWith("H3sprite.lod")) it.first to gdCorruptHeader() else it } +
            ("Data/H3bitmap.pak" to gdPlain())
        val i = run(Fs(files)).issues().single()
        assertIs<GameDataIssue.CorruptArchive>(i)
        assertFalse(i.describe().contains("HD"), i.describe())
    }

    // ---- payload and exception text never leak ----

    @Test
    fun noDescribeEverContainsPayloadOrExceptionText() {
        val results = ArrayList<GameDataResult>()
        // Marker in member bytes of an otherwise valid set.
        results.add(run(Fs(standardSet())))
        // Marker in a corrupt archive, a bad-magic file, a missing-member archive, a tiny file.
        results.add(run(Fs(standardSet().map { if (it.first.endsWith("H3sprite.lod")) it.first to gdCorruptHeader() else it })))
        results.add(run(Fs(standardSet().map { if (it.first.endsWith("H3ab_bmp.lod")) it.first to gdBytes(MARKER.repeat(20)) else it })))
        results.add(run(Fs(standardSet().map { if (it.first.endsWith("H3bitmap.lod")) it.first to gdPlain() else it })))
        results.add(run(Fs(listOf("Data/H3sprite.lod" to gdBytes(MARKER))), listOf("H3sprite.lod")))
        // Marker in exception messages.
        val fs = Fs(standardSet())
        for (ex in listOf<Throwable>(java.io.IOException(MARKER), RuntimeException(MARKER), OutOfMemoryError(MARKER), IllegalStateException(MARKER))) {
            results.add(GameDataCheck.check(fs.entries, { _ -> throw ex }))
        }
        // A reader that returns a hostile array whose parse fails with its own message.
        results.add(run(Fs(standardSet().map { if (it.first.endsWith("H3sprite.lod")) it.first to (gdPlain().copyOf(100)) else it })))
        var sawIssue = false
        for (r in results) {
            val text = allText(r)
            assertFalse(text.contains(MARKER), text)
            assertFalse(text.contains("truncated"), text) // LodFormatError wording must not be echoed either
            assertFalse(text.contains("bad magic"), text)
            assertFalse(text.contains("directory"), text)
            if (r is GameDataResult.Invalid) sawIssue = true
        }
        assertTrue(sawIssue)
    }

    @Test
    fun describeTextsAreStable() {
        assertEquals("MISSING_REQUIRED H3bitmap.lod", GameDataIssue.MissingRequired("H3bitmap.lod", false).describe())
        assertEquals("NOT_AN_ARCHIVE H3bitmap.lod (91 bytes)", GameDataIssue.NotAnArchive("H3bitmap.lod", 91L).describe())
        assertEquals("CORRUPT_ARCHIVE H3sprite.lod (200 bytes)", GameDataIssue.CorruptArchive("H3sprite.lod", 200L).describe())
        assertEquals("TOO_LARGE_TO_CHECK H3sprite.lod (536870913 bytes)", GameDataIssue.TooLargeToCheck("H3sprite.lod", 536_870_913L).describe())
        assertEquals("UNREADABLE H3sprite.lod (200 bytes)", GameDataIssue.Unreadable("H3sprite.lod", 200L).describe())
        assertTrue(GameDataIssue.MissingRequired("H3bitmap.lod", true).describe().startsWith("MISSING_REQUIRED H3bitmap.lod"))
        assertTrue(GameDataIssue.MissingRequired("H3bitmap.lod", true).describe().contains(".pak"))
    }

    @Test
    fun theInvalidResultJoinsIssueLinesInOrder() {
        val r = run(Fs(emptyList()))
        assertEquals("INVALID", r.code)
        assertEquals(
            "MISSING_REQUIRED H3ab_bmp.lod\nMISSING_REQUIRED H3ab_spr.lod\nMISSING_REQUIRED H3bitmap.lod\nMISSING_REQUIRED H3sprite.lod",
            r.describe(),
        )
    }

    // ---- ordering and determinism ----

    @Test
    fun issuesFollowTheNormalizedNameWhateverTheInputOrder() {
        val files = standardSet().filterNot { it.first.endsWith("H3ab_spr.lod") || it.first.endsWith("H3sprite.lod") } +
            ("Data/H3sprite.lod" to gdCorruptHeader())
        val expected = run(Fs(files)).issues().map { it.describe() }
        assertEquals(listOf("MISSING_REQUIRED H3ab_spr.lod", "CORRUPT_ARCHIVE H3sprite.lod (${gdCorruptHeader().size} bytes)"), expected)
        val shuffled = listOf(files[2], files[0], files[1])
        assertEquals(expected, run(Fs(shuffled)).issues().map { it.describe() })
        val reqRev = GameDataCheck.DEFAULT_REQUIRED.reversed()
        assertEquals(expected, run(Fs(files), reqRev).issues().map { it.describe() })
    }

    @Test
    fun theSameInputGivesTheSameResultAndTheSameReads() {
        val files = standardSet().map { if (it.first.endsWith("H3ab_bmp.lod")) it.first to gdCorruptHeader() else it }
        val a = Fs(files)
        val b = Fs(files)
        val ra = run(a)
        val rb = run(b)
        assertEquals(ra, rb)
        assertEquals(allText(ra), allText(rb))
        assertEquals(a.reads, b.reads)
        // Reads go in sorted normalized-name order.
        assertEquals(listOf("Data/H3ab_bmp.lod", "Data/H3ab_spr.lod", "Data/H3bitmap.lod", "Data/H3sprite.lod"), a.reads)
    }

    @Test
    fun neverThrowsOnHostileInput() {
        val fs = Fs(standardSet())
        val weird = listOf(
            GameFile("", 0L), GameFile("/", 1L), GameFile("//Data//", 100L), GameFile("Data/", 5L),
            GameFile("..", 3L), GameFile("Data/\u0000", 3L), GameFile("Data/H3bitmap.lod", Long.MIN_VALUE),
        )
        val r = GameDataCheck.check(weird + fs.entries, fs::read)
        assertTrue(r is GameDataResult.Invalid || r is GameDataResult.Ok)
        // Empty and slash-only paths never match, and a double slash still means "Data/<name>".
        val r2 = GameDataCheck.check(listOf(GameFile("Data//H3sprite.lod", 500L)), { gdPlain() }, listOf("H3sprite.lod"))
        assertIs<GameDataResult.Ok>(r2)
    }
}
