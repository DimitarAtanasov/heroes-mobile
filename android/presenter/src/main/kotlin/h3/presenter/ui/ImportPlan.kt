package h3.presenter.ui

import java.math.BigInteger
import java.util.TreeSet

/**
 * The game data import as pure decisions (android-app.md 3.2 steps 5 to 8, 3.5 last paragraph): which
 * source files to copy, whether they fit, the ordered crash-safe steps, what to do with leftovers after a
 * crash, the found, missing or changed status, the manifest text and integer progress. The module does no
 * file I/O, reads no clock and starts no thread: the app carries the steps out and reports back.
 *
 * Folders, all inside `noBackupFilesDir`: [LIVE_DIR] is the set the app reads, [STAGING_DIR] is where an
 * import is built, [OLD_DIR] holds the previous set during the swap.
 */
object ImportPlan {
    const val LIVE_DIR = "gamedata"
    const val STAGING_DIR = "gamedata.import"
    const val OLD_DIR = "gamedata.old"
    const val PART_SUFFIX = ".part"
    const val MANIFEST_NAME = "manifest.json"

    /** Name of the folder searched before the root of the picked source. */
    const val DATA_DIR_NAME = "Data"

    /** Longest accepted file name, so a path stays well under common limits. */
    const val MAX_NAME_LENGTH = 255

    // ---- names ----

    /**
     * True when [name] can be a file name inside the data folder: 1 to [MAX_NAME_LENGTH] characters, no `/`,
     * `\` or control character, not `.` or `..`, and not a name the import itself uses (`manifest.json`,
     * or anything ending in `.part`, compared without regard to ASCII case). A name that passes can never
     * leave the folder or collide with a temp or manifest file.
     */
    fun isSafeName(name: String): Boolean {
        if (name.isEmpty() || name.length > MAX_NAME_LENGTH || name == "." || name == "..") return false
        for (c in name) if (c < ' ' || c == '\u007f' || c == '/' || c == '\\') return false
        val folded = fold(name)
        return folded != MANIFEST_NAME && !folded.endsWith(PART_SUFFIX)
    }

    /** ASCII-only case fold: no locale, and names outside ASCII compare exactly. */
    private fun fold(s: String): String {
        val b = StringBuilder(s.length)
        for (c in s) b.append(if (c in 'A'..'Z') c + 32 else c)
        return b.toString()
    }

    private fun sameName(a: String, b: String): Boolean = a.length == b.length && fold(a) == fold(b)

    /** Order by Unicode code point (not by UTF-16 unit), as the Python and Kotlin canonical forms do. */
    private val codePointOrder = Comparator<String> { x, y ->
        var i = 0
        var j = 0
        while (i < x.length && j < y.length) {
            val a = x.codePointAt(i)
            val b = y.codePointAt(j)
            if (a != b) return@Comparator if (a < b) -1 else 1
            i += Character.charCount(a)
            j += Character.charCount(b)
        }
        val restX = x.length - i
        val restY = y.length - j
        if (restX == 0 && restY == 0) 0 else if (restX == 0) -1 else 1
    }

    // ---- 1. source selection ----

    /** One file of the picked source: its path relative to the picked folder (`/` separated) and size. */
    data class SourceEntry(val path: String, val size: Long)

    /** A file to import: the required [name] (also its name in the data folder), where it is, its size. */
    data class SelectedFile(val name: String, val sourcePath: String, val size: Long)

    sealed interface Selection {
        /** One [SelectedFile] per required name, in the order of the required list. */
        data class Chosen(val files: List<SelectedFile>) : Selection

        /** No entry matches [name]. */
        data class MissingSource(val name: String) : Selection

        /** Several entries match [name] in the same place; [paths] are sorted by code point. */
        data class AmbiguousSource(val name: String, val paths: List<String>) : Selection

        /** [name] is not a safe file name, or repeats an earlier required name apart from case. */
        data class InvalidName(val name: String) : Selection

        /** The provider gave a negative size for [path]. */
        data class UnknownSize(val path: String) : Selection
    }

    /**
     * Chooses the files to import from [entries] (any order). For each of [required], in order, the match
     * is a path `Data/<name>` (the first segment `Data` in any case) or, if there is none, `<name>` at the
     * root (the user picked the `Data` folder itself). Names are compared with an ASCII case fold. `Data/`
     * wins over the root even if the root has a different file of that name. More than one match in the
     * winning place, which includes the same path listed twice, is [Selection.AmbiguousSource]: the app
     * must not guess between `H3bitmap.lod` and `h3bitmap.lod`. Deeper folders are not searched. The first
     * problem found, in the order of [required], is returned.
     */
    fun select(entries: List<SourceEntry>, required: List<String>): Selection {
        val seen = ArrayList<String>()
        val files = ArrayList<SelectedFile>()
        for (name in required) {
            if (!isSafeName(name) || seen.any { sameName(it, name) }) return Selection.InvalidName(name)
            seen.add(name)
            val inData = ArrayList<SourceEntry>()
            val inRoot = ArrayList<SourceEntry>()
            for (entry in entries) {
                val parts = entry.path.split('/')
                if (parts.size == 2 && sameName(parts[0], DATA_DIR_NAME) && sameName(parts[1], name)) {
                    inData.add(entry)
                } else if (parts.size == 1 && sameName(parts[0], name)) {
                    inRoot.add(entry)
                }
            }
            val found = if (inData.isNotEmpty()) inData else inRoot
            if (found.isEmpty()) return Selection.MissingSource(name)
            if (found.size > 1) return Selection.AmbiguousSource(name, found.map { it.path }.sortedWith(codePointOrder))
            val only = found[0]
            if (only.size < 0) return Selection.UnknownSize(only.path)
            files.add(SelectedFile(name, only.path, only.size))
        }
        return Selection.Chosen(files)
    }

    // ---- 2. space check ----

    sealed interface SpaceCheck {
        data class Ok(val needed: Long) : SpaceCheck

        /** Both numbers go into the user-facing message (android-app.md 3.5). */
        data class NotEnoughSpace(val needed: Long, val free: Long) : SpaceCheck
    }

    /**
     * The bytes the copy needs: the sum of the sizes, which saturates at [Long.MAX_VALUE] instead of
     * wrapping. The manifest is small and not counted. An old set is kept until the swap, so the caller
     * passes the allocatable bytes as they are during the copy.
     */
    fun neededBytes(files: List<SelectedFile>): Long {
        var sum = 0L
        for (f in files) {
            val s = f.size.coerceAtLeast(0L)
            if (s > Long.MAX_VALUE - sum) return Long.MAX_VALUE
            sum += s
        }
        return sum
    }

    /**
     * [SpaceCheck.NotEnoughSpace] when [needed] is more than [free]; exactly [free] is [SpaceCheck.Ok].
     * A saturated [needed] ([Long.MAX_VALUE]) never fits.
     */
    fun checkSpace(needed: Long, free: Long): SpaceCheck =
        if (needed == Long.MAX_VALUE || needed > free) SpaceCheck.NotEnoughSpace(needed, free) else SpaceCheck.Ok(needed)

    // ---- 3. ordered steps ----

    /** One step of the import, carried out by the app in the order of [plan]. Paths are relative to `noBackupFilesDir`. */
    sealed interface Step {
        /** Stream [source] (a [SelectedFile.sourcePath] of the picked tree) into the new file [target]. */
        data class CopyToPart(val source: String, val target: String, val size: Long) : Step

        /** fsync the file at [path]. */
        data class SyncFile(val path: String) : Step

        /** Atomically rename the finished temp file [from] to [to], inside the staging folder. */
        data class RenamePart(val from: String, val to: String) : Step

        /** Write [content] to the new file [path]. */
        data class WriteManifest(val path: String, val content: String) : Step

        /** Atomically rename the live folder [from] to [to]. Left out when there is no live folder. */
        data class MoveLiveToOld(val from: String, val to: String) : Step

        /** Atomically rename the finished staging folder [from] to the live name [to]. */
        data class PromoteStaging(val from: String, val to: String) : Step

        /** Delete the previous set at [path] and everything in it. Left out when there was none. */
        data class DeleteOld(val path: String) : Step
    }

    /**
     * The steps for [files] (from [select]; their names are safe). Per file: copy to
     * `gamedata.import/<name>.part`, sync, rename to `gamedata.import/<name>`, so a finished file is never
     * half written and the copy can resume per file. Then `manifest.json` is written and synced LAST: a
     * staging folder holding it is complete. Then the swap: live to `gamedata.old` (only if [liveExists]),
     * `gamedata.import` to `gamedata`, delete `gamedata.old` (only if [liveExists]).
     * Every rename is atomic and the live folder is never edited in place, so a crash at any step leaves
     * the old or the new complete set once [recover] has run. Run [recover] and carry out its actions
     * before planning a new import, so the three folders are in a known state.
     */
    fun plan(files: List<SelectedFile>, validatorVersion: Int, liveExists: Boolean): List<Step> {
        val steps = ArrayList<Step>()
        for (f in files) {
            val target = "$STAGING_DIR/${f.name}"
            val part = target + PART_SUFFIX
            steps.add(Step.CopyToPart(f.sourcePath, part, f.size))
            steps.add(Step.SyncFile(part))
            steps.add(Step.RenamePart(part, target))
        }
        val manifestPath = "$STAGING_DIR/$MANIFEST_NAME"
        val manifest = Manifest(validatorVersion, files.map { ManifestFile(it.name, it.size) })
        steps.add(Step.WriteManifest(manifestPath, encodeManifest(manifest)))
        steps.add(Step.SyncFile(manifestPath))
        if (liveExists) steps.add(Step.MoveLiveToOld(LIVE_DIR, OLD_DIR))
        steps.add(Step.PromoteStaging(STAGING_DIR, LIVE_DIR))
        if (liveExists) steps.add(Step.DeleteOld(OLD_DIR))
        return steps
    }

    // ---- 4. recovery ----

    /** One cleanup action after a crash, to be carried out in the order [recover] returns. */
    enum class RecoverAction {
        /** Delete `gamedata.import` and everything in it. */
        DeleteStaging,

        /** Delete `gamedata.old` and everything in it. */
        DeleteOld,

        /** Delete `gamedata` and everything in it (only when its manifest is not ok and `gamedata.old` exists). */
        DeleteLive,

        /** Rename `gamedata.old` to `gamedata` (only when `gamedata` does not exist). */
        RestoreOld,
    }

    /**
     * What to do at start, and before every import, with the three folders left by a crash. [live],
     * [staging] and [old] say whether `gamedata`, `gamedata.import` and `gamedata.old` exist;
     * [liveManifestOk] says whether `gamedata` has a manifest that parses and whose files all exist with
     * the listed sizes (`status` is `Found`), and only matters when both `gamedata` and `gamedata.old`
     * exist. Policy: staging is never promoted here (only [plan] does that), so a half-built set can never
     * become visible; `gamedata.old` is the last complete set while it exists next to a missing or
     * unusable `gamedata`. Every action is safe to repeat and to be interrupted: the next start decides
     * again from what is on disk, and the result is stable (a second call returns an empty list).
     *
     * ```
     * live staging old  ok  | actions (in order)           | state at the crash
     * no   no      no   -   | none                         | nothing imported yet
     * no   no      yes  -   | RestoreOld                   | swap stopped after live -> old, staging lost
     * no   yes     no   -   | DeleteStaging                | first import, copy or swap not finished
     * no   yes     yes  -   | DeleteStaging, RestoreOld    | swap stopped after live -> old
     * yes  no      no   -   | none                         | normal
     * yes  no      yes  yes | DeleteOld                    | swap stopped after staging -> live
     * yes  no      yes  no  | DeleteLive, RestoreOld       | live unusable, previous set kept
     * yes  yes     no   -   | DeleteStaging                | re-import, copy or manifest not finished
     * yes  yes     yes  yes | DeleteStaging, DeleteOld     | import started without recovery
     * yes  yes     yes  no  | DeleteLive, RestoreOld,      | as above, live unusable
     *                       |   DeleteStaging              |
     * ```
     * (`-` means the flag is not looked at.) After the actions `gamedata` is the old complete set, the
     * new complete set, or missing when nothing was ever imported; `gamedata.import` and `gamedata.old`
     * are gone. A live folder with a bad manifest and no old set is left alone: [status] reports it and
     * the app shows placeholder mode with the re-import banner.
     */
    fun recover(live: Boolean, staging: Boolean, old: Boolean, liveManifestOk: Boolean): List<RecoverAction> = when {
        !live && !old -> if (staging) listOf(RecoverAction.DeleteStaging) else emptyList()
        !live -> if (staging) listOf(RecoverAction.DeleteStaging, RecoverAction.RestoreOld) else listOf(RecoverAction.RestoreOld)
        !old -> if (staging) listOf(RecoverAction.DeleteStaging) else emptyList()
        liveManifestOk -> if (staging) listOf(RecoverAction.DeleteStaging, RecoverAction.DeleteOld) else listOf(RecoverAction.DeleteOld)
        staging -> listOf(RecoverAction.DeleteLive, RecoverAction.RestoreOld, RecoverAction.DeleteStaging)
        else -> listOf(RecoverAction.DeleteLive, RecoverAction.RestoreOld)
    }

    // ---- 5. status ----

    enum class DataStatus { Found, Missing, Changed }

    /**
     * The cheap start-up check: every manifest file must exist ([actualSizes] maps names to the current
     * sizes, and extra names are ignored) with the listed size. [DataStatus.Missing] when there is no
     * manifest, it lists no file, or any listed file is absent (this outranks a changed size);
     * [DataStatus.Changed] when all exist and a size differs; else [DataStatus.Found]. Names are compared
     * exactly.
     */
    fun status(manifest: Manifest?, actualSizes: Map<String, Long>): DataStatus {
        if (manifest == null || manifest.files.isEmpty()) return DataStatus.Missing
        var changed = false
        for (f in manifest.files) {
            val actual = actualSizes[f.name] ?: return DataStatus.Missing
            if (actual != f.size) changed = true
        }
        return if (changed) DataStatus.Changed else DataStatus.Found
    }

    // ---- 6. progress ----

    /** Bytes copied of bytes to copy. */
    data class Progress(val done: Long, val total: Long) {
        /**
         * `floor(100 * done / total)` in 0..100, exact for any Long. 0 when [total] is 0 or negative or
         * [done] is not positive; 100 when [done] has reached [total].
         */
        val percent: Int
            get() {
                if (total <= 0 || done <= 0) return 0
                if (done >= total) return 100
                return BigInteger.valueOf(done).multiply(BigInteger.valueOf(100)).divide(BigInteger.valueOf(total)).toInt()
            }
    }

    // ---- manifest ----

    data class ManifestFile(val name: String, val size: Long)

    /** What `gamedata/manifest.json` holds: the imported files and the validator version that accepted them. */
    data class Manifest(val validatorVersion: Int, val files: List<ManifestFile>)

    /**
     * The canonical text of [m]: compact JSON, object keys in code point order (`files`,
     * `validator_version`; `name`, `size`), files sorted by name by code point, integers only, and ASCII
     * output (a quote or backslash is escaped, every other character below U+0020 or above U+007E as
     * `\u` plus four lower-case hex digits per UTF-16 unit). The same manifest always gives the same text.
     */
    fun encodeManifest(m: Manifest): String {
        val b = StringBuilder()
        b.append("{\"files\":[")
        val sorted = m.files.sortedWith(compareBy<ManifestFile, String>(codePointOrder) { it.name }.thenBy { it.size })
        for ((n, f) in sorted.withIndex()) {
            if (n > 0) b.append(',')
            b.append("{\"name\":")
            appendString(b, f.name)
            b.append(",\"size\":").append(f.size).append('}')
        }
        b.append("],\"validator_version\":").append(m.validatorVersion).append('}')
        return b.toString()
    }

    private fun appendString(b: StringBuilder, s: String) {
        b.append('"')
        for (c in s) {
            when {
                c == '"' -> b.append("\\\"")
                c == '\\' -> b.append("\\\\")
                c < ' ' || c > '~' -> {
                    b.append("\\u")
                    val v = c.code
                    for (shift in intArrayOf(12, 8, 4, 0)) b.append(HEX[(v shr shift) and 15])
                }
                else -> b.append(c)
            }
        }
        b.append('"')
    }

    private const val HEX = "0123456789abcdef"

    /** Why a manifest text was refused; [ManifestParse.Failed.offset] is the index in the text. */
    enum class ManifestError {
        /** The text stops inside a value (or is empty). */
        UnexpectedEnd,

        /** A character that is not allowed there. */
        Syntax,

        /** A bad escape, a bad `\u` sequence or a raw control character in a string. */
        BadString,

        /** Not a plain non-negative integer: a sign, a leading zero, a fraction or an exponent. */
        BadNumber,

        /** An integer above the largest [Long] (sizes) or [Int] (version). */
        NumberTooLarge,

        /** A value of the wrong kind (a string where a number belongs, and so on). */
        WrongType,

        UnknownKey,
        DuplicateKey,
        MissingKey,

        /** `files` is empty. */
        NoFiles,

        /** A file name that fails [isSafeName]. */
        BadName,

        /** Two file names equal apart from ASCII case. */
        DuplicateName,

        /** Something other than white space after the closing brace. */
        TrailingData,
    }

    sealed interface ManifestParse {
        data class Parsed(val manifest: Manifest) : ManifestParse

        data class Failed(val error: ManifestError, val offset: Int) : ManifestParse
    }

    /**
     * Reads manifest text. Accepts any white space and any key order (the canonical form is what
     * [encodeManifest] writes), and nothing else: no unknown keys, no duplicates, no floats, no negative
     * numbers. File order is kept as written. Never throws: every problem is a [ManifestParse.Failed].
     */
    fun decodeManifest(text: String): ManifestParse = try {
        ManifestParse.Parsed(ManifestReader(text).readManifest())
    } catch (f: ManifestFailure) {
        ManifestParse.Failed(f.error, f.offset)
    }

    private class ManifestFailure(val error: ManifestError, val offset: Int) : RuntimeException(null, null, false, false)

    private class ManifestReader(private val t: String) {
        private var i = 0

        private fun fail(error: ManifestError, at: Int = i): Nothing = throw ManifestFailure(error, at)

        private fun skipSpace() {
            while (i < t.length && (t[i] == ' ' || t[i] == '\t' || t[i] == '\n' || t[i] == '\r')) i++
        }

        /** A token other than the expected one: a value of another kind, or garbage. */
        private fun wrongToken(): Nothing {
            if (i >= t.length) fail(ManifestError.UnexpectedEnd)
            fail(if (t[i] in "\"[{-0123456789tfn") ManifestError.WrongType else ManifestError.Syntax)
        }

        private fun expect(c: Char) {
            skipSpace()
            if (i >= t.length || t[i] != c) wrongToken()
            i++
        }

        fun readManifest(): Manifest {
            var version: Int? = null
            var files: List<ManifestFile>? = null
            val close = readObject { key, keyAt ->
                when (key) {
                    "validator_version" -> {
                        if (version != null) fail(ManifestError.DuplicateKey, keyAt)
                        skipSpace()
                        version = readNumber(Int.MAX_VALUE.toLong()).toInt()
                    }
                    "files" -> {
                        if (files != null) fail(ManifestError.DuplicateKey, keyAt)
                        files = readFiles()
                    }
                    else -> fail(ManifestError.UnknownKey, keyAt)
                }
            }
            val v = version ?: fail(ManifestError.MissingKey, close)
            val f = files ?: fail(ManifestError.MissingKey, close)
            skipSpace()
            if (i < t.length) fail(ManifestError.TrailingData)
            return Manifest(v, f)
        }

        /** Reads `{ "key": value, ... }`, calling [member] after each key's colon. Returns the index of the `}`. */
        private fun readObject(member: (String, Int) -> Unit): Int {
            expect('{')
            skipSpace()
            if (i < t.length && t[i] == '}') return i++
            while (true) {
                skipSpace()
                val keyAt = i
                val key = readString()
                expect(':')
                member(key, keyAt)
                skipSpace()
                if (i >= t.length) fail(ManifestError.UnexpectedEnd)
                val c = t[i]
                if (c == '}') return i++
                if (c != ',') fail(ManifestError.Syntax)
                i++
            }
        }

        private fun readFiles(): List<ManifestFile> {
            skipSpace()
            val arrayAt = i
            expect('[')
            skipSpace()
            if (i < t.length && t[i] == ']') fail(ManifestError.NoFiles, arrayAt)
            val seen = TreeSet<String>()
            val out = ArrayList<ManifestFile>()
            while (true) {
                out.add(readFile(seen))
                skipSpace()
                if (i >= t.length) fail(ManifestError.UnexpectedEnd)
                val c = t[i]
                if (c == ']') {
                    i++
                    return out
                }
                if (c != ',') fail(ManifestError.Syntax)
                i++
            }
        }

        private fun readFile(seen: TreeSet<String>): ManifestFile {
            skipSpace()
            var name: String? = null
            var size: Long? = null
            val close = readObject { key, keyAt ->
                when (key) {
                    "name" -> {
                        if (name != null) fail(ManifestError.DuplicateKey, keyAt)
                        skipSpace()
                        val at = i
                        val n = readString()
                        if (!isSafeName(n)) fail(ManifestError.BadName, at)
                        if (!seen.add(fold(n))) fail(ManifestError.DuplicateName, at)
                        name = n
                    }
                    "size" -> {
                        if (size != null) fail(ManifestError.DuplicateKey, keyAt)
                        skipSpace()
                        size = readNumber(Long.MAX_VALUE)
                    }
                    else -> fail(ManifestError.UnknownKey, keyAt)
                }
            }
            return ManifestFile(name ?: fail(ManifestError.MissingKey, close), size ?: fail(ManifestError.MissingKey, close))
        }

        private fun readNumber(limit: Long): Long {
            if (i >= t.length) fail(ManifestError.UnexpectedEnd)
            val start = i
            if (t[i] == '-') fail(ManifestError.BadNumber, start)
            if (t[i] !in '0'..'9') wrongToken()
            var acc = 0L
            var tooLarge = false
            while (i < t.length && t[i] in '0'..'9') {
                val d = (t[i] - '0').toLong()
                if (!tooLarge) {
                    if (acc > (limit - d) / 10) tooLarge = true else acc = acc * 10 + d
                }
                i++
            }
            if (t[start] == '0' && i - start > 1) fail(ManifestError.BadNumber, start)
            if (i < t.length && (t[i] == '.' || t[i] == 'e' || t[i] == 'E')) fail(ManifestError.BadNumber, start)
            if (tooLarge) fail(ManifestError.NumberTooLarge, start)
            return acc
        }

        private fun readString(): String {
            if (i >= t.length) fail(ManifestError.UnexpectedEnd)
            if (t[i] != '"') wrongToken()
            i++
            val b = StringBuilder()
            while (true) {
                if (i >= t.length) fail(ManifestError.UnexpectedEnd)
                val c = t[i]
                when {
                    c == '"' -> {
                        i++
                        return b.toString()
                    }
                    c < ' ' -> fail(ManifestError.BadString)
                    c == '\\' -> {
                        i++
                        if (i >= t.length) fail(ManifestError.UnexpectedEnd)
                        when (t[i]) {
                            '"' -> b.append('"')
                            '\\' -> b.append('\\')
                            '/' -> b.append('/')
                            'b' -> b.append('\b')
                            'f' -> b.append('\u000c')
                            'n' -> b.append('\n')
                            'r' -> b.append('\r')
                            't' -> b.append('\t')
                            'u' -> {
                                var v = 0
                                for (k in 1..4) {
                                    if (i + k >= t.length) fail(ManifestError.UnexpectedEnd, t.length)
                                    val h = hexValue(t[i + k])
                                    if (h < 0) fail(ManifestError.BadString, i + k)
                                    v = v * 16 + h
                                }
                                b.append(v.toChar())
                                i += 4
                            }
                            else -> fail(ManifestError.BadString)
                        }
                        i++
                    }
                    else -> {
                        b.append(c)
                        i++
                    }
                }
            }
        }

        private fun hexValue(c: Char): Int = when (c) {
            in '0'..'9' -> c - '0'
            in 'a'..'f' -> c - 'a' + 10
            in 'A'..'F' -> c - 'A' + 10
            else -> -1
        }
    }
}
