package h3.presenter.ui

/**
 * The words of the game data import screen, as pure functions of the pure import types
 * (android-app.md 3.2 and 3.5). One user-facing sentence per named error, and one details line the
 * player can copy. Sentences and details name files, sizes and stages only: never file contents and
 * never exception text (the store that produces an [ImportResult] does not keep either).
 */
object ImportText {
    private const val MIB = 1_048_576L

    /** The sideload hint shown on the import screen (debug builds only, no file picker). */
    val SIDELOAD_HINT: String =
        "Sideload (debug builds only): push your Heroes III Data folder to the device with adb, then copy it " +
            "into the app's private folder. On your computer, run:\n" +
            "1. adb push Data /data/local/tmp/Data\n" +
            "2. adb shell run-as h3.app mkdir -p no_backup/gamedata/Data\n" +
            "3. adb shell run-as h3.app cp -r /data/local/tmp/Data/. no_backup/gamedata/Data/\n" +
            "Then tap Check again."

    /** The status line; [status] is null while the first check is running. */
    fun statusLine(status: ImportPlan.DataStatus?): String = when (status) {
        null -> "Checking game data..."
        ImportPlan.DataStatus.Found -> "Game data found."
        ImportPlan.DataStatus.Missing -> "Game data missing. The game runs with placeholder art."
        ImportPlan.DataStatus.Changed -> "Game data changed since it was checked. Check it again."
    }

    /** Copy progress as one line, from integer percent. */
    fun progressLine(p: ImportPlan.Progress): String = "Copying: ${p.percent}%"

    /** Whole mebibytes, rounded up, without overflow. */
    fun mib(bytes: Long): Long {
        if (bytes <= 0L) return 0L
        return bytes / MIB + (if (bytes % MIB != 0L) 1L else 0L)
    }

    fun sentence(issue: GameDataIssue): String = when (issue) {
        is GameDataIssue.MissingRequired ->
            if (issue.hdHint) {
                "${issue.file} is missing and .pak files were found: the HD Edition cannot be read. Use a Complete or Shadow of Death install."
            } else {
                "${issue.file} was not found."
            }
        is GameDataIssue.NotAnArchive -> "${issue.file} is not a Heroes III archive."
        is GameDataIssue.CorruptArchive -> "${issue.file} is damaged. Copy it again from your install."
        is GameDataIssue.TooLargeToCheck -> "${issue.file} is too large to check on this device."
        is GameDataIssue.Unreadable -> "${issue.file} could not be read."
        is GameDataIssue.MissingMember ->
            "${issue.archive} does not contain ${issue.member}. It may come from another game version."
    }

    fun sentence(selection: ImportPlan.Selection): String = when (selection) {
        is ImportPlan.Selection.Chosen -> "All files were found."
        is ImportPlan.Selection.MissingSource -> "${selection.name} was not found in the folder."
        is ImportPlan.Selection.AmbiguousSource -> "More than one file matches ${selection.name}. Remove the extra copies."
        is ImportPlan.Selection.InvalidName -> "The file name ${selection.name} cannot be used."
        is ImportPlan.Selection.UnknownSize -> "The size of ${selection.path} could not be read."
    }

    fun details(selection: ImportPlan.Selection): String = when (selection) {
        is ImportPlan.Selection.Chosen -> "SOURCE_OK ${selection.files.size} files"
        is ImportPlan.Selection.MissingSource -> "MISSING_SOURCE ${selection.name}"
        is ImportPlan.Selection.AmbiguousSource -> "AMBIGUOUS_SOURCE ${selection.name}: ${selection.paths.joinToString(", ")}"
        is ImportPlan.Selection.InvalidName -> "INVALID_NAME ${selection.name}"
        is ImportPlan.Selection.UnknownSize -> "UNKNOWN_SIZE ${selection.path}"
    }

    fun codeOf(selection: ImportPlan.Selection): String = when (selection) {
        is ImportPlan.Selection.Chosen -> "SOURCE_OK"
        is ImportPlan.Selection.MissingSource -> "MISSING_SOURCE"
        is ImportPlan.Selection.AmbiguousSource -> "AMBIGUOUS_SOURCE"
        is ImportPlan.Selection.InvalidName -> "INVALID_NAME"
        is ImportPlan.Selection.UnknownSize -> "UNKNOWN_SIZE"
    }
}

/** The part of the import that failed on disk. */
enum class IoStage { Recover, Scan, Copy, Manifest, Swap }

/**
 * What a check or an import came to. Every value is plain data: [code] is stable, [sentences] has one
 * user-facing sentence per named error, [details] is one line of file names and sizes for the player to
 * copy. [isError] is false only for [Valid].
 */
sealed interface ImportResult {
    val code: String
    val isError: Boolean
    fun sentences(): List<String>
    fun details(): String

    /** The files passed every check and `manifest.json` is in place. */
    data class Valid(val files: List<CheckedFile>) : ImportResult {
        override val code get() = "OK"
        override val isError get() = false
        override fun sentences() = listOf("Game data is in place.")
        override fun details() = "OK ${files.size} files: " + files.joinToString(", ") { "${it.name} (${it.size} bytes)" }
    }

    /** The validator refused the files; [issues] is never empty. */
    data class Invalid(val issues: List<GameDataIssue>) : ImportResult {
        override val code get() = "INVALID"
        override val isError get() = true
        override fun sentences() = issues.map { ImportText.sentence(it) }
        override fun details() = issues.joinToString("; ") { it.describe() }
    }

    /** The folder to import from does not hold the files; [selection] is never `Chosen`. */
    data class SourceProblem(val selection: ImportPlan.Selection) : ImportResult {
        override val code get() = ImportText.codeOf(selection)
        override val isError get() = true
        override fun sentences() = listOf(ImportText.sentence(selection))
        override fun details() = ImportText.details(selection)
    }

    data class NotEnoughSpace(val needed: Long, val free: Long) : ImportResult {
        override val code get() = "NOT_ENOUGH_SPACE"
        override val isError get() = true
        override fun sentences() =
            listOf("Not enough free space: the copy needs ${ImportText.mib(needed)} MB and ${ImportText.mib(free)} MB is free.")
        override fun details() = "NOT_ENOUGH_SPACE needed $needed bytes, free $free bytes"
    }

    /** A source file had another size after the copy than when it was listed. */
    data class SourceChanged(val file: String) : ImportResult {
        override val code get() = "SOURCE_CHANGED"
        override val isError get() = true
        override fun sentences() = listOf("$file changed while it was being copied. Try again.")
        override fun details() = "SOURCE_CHANGED $file"
    }

    /** A disk step failed; [file] is a file or folder name, or null. */
    data class IoFailed(val stage: IoStage, val file: String?) : ImportResult {
        override val code get() = "IO_FAILED"
        override val isError get() = true
        override fun sentences() = listOf(
            when (stage) {
                IoStage.Recover -> "Leftovers of an earlier import could not be cleaned up."
                IoStage.Scan -> "The folder could not be read."
                IoStage.Copy -> "Copying failed. Check the free space and try again."
                IoStage.Manifest -> "The record of the imported files could not be written."
                IoStage.Swap -> "The new files could not be put in place."
            },
        )
        override fun details() = if (file == null) "IO_FAILED ${stage.name}" else "IO_FAILED ${stage.name} $file"
    }
}
