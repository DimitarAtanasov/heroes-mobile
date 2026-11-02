package h3.presenter.ui

import h3.sim.LOD_HEADER_SIZE
import h3.sim.LodArchive
import h3.sim.LodFormatError

/**
 * Pure validation of an imported game-data folder (android-app.md 3.4 and 3.5, steps V1 to V3).
 * The app supplies the file list (relative path and size, from its scan) and a reader that returns
 * the bytes of one listed file; this code does no file I/O, reads no clock or environment, and
 * never throws: every failure is a named [GameDataIssue] in the result.
 *
 * Checks, per required file, in sorted order of the normalized name:
 *  - V1: the file is present, in the root or directly in a folder named `Data`, names compared
 *    case-insensitively (ASCII folding only; `/` and `\` both separate folders). When a name is in
 *    both places, `Data/` wins.
 *  - V2: its listed size is at least [MIN_ARCHIVE_BYTES] and at most [MAX_CHECKABLE_BYTES]; the
 *    bytes start with the LOD magic; [LodArchive.open] accepts them.
 *  - V3: `H3bitmap.lod` has a member named `CRTRAITS.TXT`. Only [LodArchive.contains] is used: the
 *    content is never read or decoded here (that is V4, another slice).
 *
 * `.pak` files only add an HD hint to [GameDataIssue.MissingRequired] (open decision G5): no
 * result is refused on that basis. Details name files and sizes only, never exception messages,
 * member bytes or other payload. The reader is called at most once per required file.
 */
data class GameFile(
    /** Path relative to the folder the player picked, for example `Data/H3bitmap.lod`. */
    val path: String,
    val size: Long,
)

/** One required file that passed every check: the required name as given, and its listed size. */
data class CheckedFile(val name: String, val size: Long)

/** What went wrong for one file. [code] is stable and may be shown or logged. */
sealed class GameDataIssue {
    abstract val code: String
    abstract fun describe(): String

    /** No file of that name in the root or in `Data/`. [hdHint] is true when `.pak` files were listed. */
    data class MissingRequired(val file: String, val hdHint: Boolean) : GameDataIssue() {
        override val code get() = "MISSING_REQUIRED"
        override fun describe() =
            if (hdHint) {
                "$code $file (.pak files were found: the HD Edition cannot be read, pick a Complete or Shadow of Death install)"
            } else {
                "$code $file"
            }
    }

    /** Smaller than a LOD header, or the bytes do not start with the LOD magic. */
    data class NotAnArchive(val file: String, val size: Long) : GameDataIssue() {
        override val code get() = "NOT_AN_ARCHIVE"
        override fun describe() = "$code $file ($size bytes)"
    }

    /** The LOD magic is there but the archive does not parse (header, directory or entry bounds). */
    data class CorruptArchive(val file: String, val size: Long) : GameDataIssue() {
        override val code get() = "CORRUPT_ARCHIVE"
        override fun describe() = "$code $file ($size bytes)"
    }

    /** Over [GameDataCheck.MAX_CHECKABLE_BYTES], or the device ran out of memory reading it. */
    data class TooLargeToCheck(val file: String, val size: Long) : GameDataIssue() {
        override val code get() = "TOO_LARGE_TO_CHECK"
        override fun describe() = "$code $file ($size bytes)"
    }

    /** The reader failed for this file. */
    data class Unreadable(val file: String, val size: Long) : GameDataIssue() {
        override val code get() = "UNREADABLE"
        override fun describe() = "$code $file ($size bytes)"
    }

    /** A parsed archive lacks a required member. */
    data class MissingMember(val archive: String, val member: String) : GameDataIssue() {
        override val code get() = "MISSING_MEMBER"
        override fun describe() = "$code $archive: $member"
    }
}

/** Outcome of [GameDataCheck.check]: [Ok] when no issue was found, otherwise [Invalid] with every issue. */
sealed class GameDataResult {
    abstract val code: String
    abstract fun describe(): String

    data class Ok(val files: List<CheckedFile>) : GameDataResult() {
        override val code get() = "OK"
        override fun describe() = "OK ${files.size} files"
    }

    /** [issues] is never empty, in the order of the normalized file name. */
    data class Invalid(val issues: List<GameDataIssue>) : GameDataResult() {
        override val code get() = "INVALID"
        override fun describe() = issues.joinToString("\n") { it.describe() }
    }
}

object GameDataCheck {
    /** The four archives of a Shadow of Death install (names still to confirm on a real install, G5). */
    val DEFAULT_REQUIRED: List<String> = listOf("H3bitmap.lod", "H3sprite.lod", "H3ab_bmp.lod", "H3ab_spr.lod")

    /** Smaller than this cannot hold a LOD header. */
    const val MIN_ARCHIVE_BYTES: Long = LOD_HEADER_SIZE.toLong()

    /**
     * Largest file this check reads, 512 MiB. LodArchive works on a byte array, so the file is read
     * whole; a bigger one is reported instead of risking the process. Inclusive.
     */
    const val MAX_CHECKABLE_BYTES: Long = 536_870_912L

    /** The archive that must hold [CRTRAITS_MEMBER] (check V3), compared by normalized name. */
    const val BITMAP_ARCHIVE: String = "H3bitmap.lod"
    const val CRTRAITS_MEMBER: String = "CRTRAITS.TXT"

    private const val DATA_FOLDER = "data"
    private const val PAK_SUFFIX = ".pak"

    /**
     * Checks [required] (each a plain file name) against [files]. [read] gets the `path` of a listed
     * file exactly as listed and returns its bytes. [open] parses them and is a seam for tests only.
     * Never throws.
     */
    fun check(
        files: List<GameFile>,
        read: (String) -> ByteArray,
        required: List<String> = DEFAULT_REQUIRED,
        open: (ByteArray) -> LodArchive = { LodArchive.open(it) },
    ): GameDataResult {
        val candidates = ArrayList<Candidate>()
        var hasPak = false
        for (f in files) {
            val segs = segments(f.path)
            if (segs.isEmpty()) continue
            if (fold(segs.last()).endsWith(PAK_SUFFIX)) hasPak = true
            val rank = when {
                segs.size == 1 -> 1
                segs.size == 2 && fold(segs[0]) == DATA_FOLDER -> 0
                else -> continue
            }
            candidates.add(Candidate(fold(segs.last()), rank, f))
        }

        // Required names, deduplicated by normalized name (first wins) and sorted by code point.
        val wanted = ArrayList<Pair<String, String>>()
        for (name in required) {
            val key = fold(name)
            if (wanted.none { it.first == key }) wanted.add(key to name)
        }
        wanted.sortWith { a, b -> compareCodePoints(a.first, b.first) }

        val issues = ArrayList<GameDataIssue>()
        val checked = ArrayList<CheckedFile>()
        for ((key, name) in wanted) {
            val found = candidates.filter { it.name == key }.minWithOrNull(CANDIDATE_ORDER)
            if (found == null) {
                issues.add(GameDataIssue.MissingRequired(name, hasPak))
                continue
            }
            val issue = checkOne(name, key, found.file, read, open)
            if (issue == null) checked.add(CheckedFile(name, found.file.size)) else issues.add(issue)
        }
        return if (issues.isEmpty()) GameDataResult.Ok(checked) else GameDataResult.Invalid(issues)
    }

    private fun checkOne(
        name: String,
        key: String,
        file: GameFile,
        read: (String) -> ByteArray,
        open: (ByteArray) -> LodArchive,
    ): GameDataIssue? {
        val size = file.size
        if (size < MIN_ARCHIVE_BYTES) return GameDataIssue.NotAnArchive(name, size)
        if (size > MAX_CHECKABLE_BYTES) return GameDataIssue.TooLargeToCheck(name, size)

        val bytes = try {
            read(file.path)
        } catch (e: OutOfMemoryError) {
            return GameDataIssue.TooLargeToCheck(name, size)
        } catch (e: Throwable) {
            return GameDataIssue.Unreadable(name, size)
        }
        // The magic is tested here, on the bytes, so the kind of error never depends on the wording
        // of an exception message.
        if (!hasLodMagic(bytes)) return GameDataIssue.NotAnArchive(name, size)

        val archive = try {
            open(bytes)
        } catch (e: OutOfMemoryError) {
            return GameDataIssue.TooLargeToCheck(name, size)
        } catch (e: LodFormatError) {
            return GameDataIssue.CorruptArchive(name, size)
        } catch (e: Throwable) {
            // Hostile bytes that escape LodFormatError are still a corrupt archive, not a crash.
            return GameDataIssue.CorruptArchive(name, size)
        }
        if (key == fold(BITMAP_ARCHIVE) && CRTRAITS_MEMBER !in archive) {
            return GameDataIssue.MissingMember(name, CRTRAITS_MEMBER)
        }
        return null
    }

    private class Candidate(val name: String, val rank: Int, val file: GameFile)

    /** `Data/` before the root, then the path by code point, then the size: a total order. */
    private val CANDIDATE_ORDER = Comparator<Candidate> { a, b ->
        if (a.rank != b.rank) return@Comparator a.rank.compareTo(b.rank)
        val c = compareCodePoints(a.file.path, b.file.path)
        if (c != 0) c else a.file.size.compareTo(b.file.size)
    }

    private fun hasLodMagic(b: ByteArray): Boolean =
        b.size >= 4 && b[0] == 'L'.code.toByte() && b[1] == 'O'.code.toByte() && b[2] == 'D'.code.toByte() && b[3] == 0.toByte()

    /** Path segments: split on `/` and `\`, empty and `.` segments dropped. */
    private fun segments(path: String): List<String> {
        val out = ArrayList<String>()
        val cur = StringBuilder()
        for (i in 0..path.length) {
            val ch = if (i < path.length) path[i] else '/'
            if (ch == '/' || ch == '\\') {
                val s = cur.toString()
                if (s.isNotEmpty() && s != ".") out.add(s)
                cur.setLength(0)
            } else {
                cur.append(ch)
            }
        }
        return out
    }

    /** ASCII-only lower-casing: A to Z only, so no Unicode case mapping can make two names equal. */
    private fun fold(s: String): String {
        val sb = StringBuilder(s.length)
        for (ch in s) sb.append(if (ch in 'A'..'Z') ch + 32 else ch)
        return sb.toString()
    }

    /** Order by Unicode code point (String.compareTo orders UTF-16 units, which differs above U+FFFF). */
    private fun compareCodePoints(a: String, b: String): Int {
        var i = 0
        var j = 0
        while (i < a.length && j < b.length) {
            val x = a.codePointAt(i)
            val y = b.codePointAt(j)
            if (x != y) return x.compareTo(y)
            i += Character.charCount(x)
            j += Character.charCount(y)
        }
        return (a.length - i).compareTo(b.length - j)
    }
}
