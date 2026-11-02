package h3.presenter.ui

import h3.presenter.ResumeError
import h3.presenter.ResumeResult
import h3.presenter.Resumed
import h3.sim.Canonical
import h3.sim.Datapack
import h3.sim.Replay
import java.math.BigInteger

/**
 * Save slot decisions as pure functions (android-app.md 7.2, replay-autosave.md): which file a
 * battle is saved in, which steps one write takes, which file to resume from, and what to tell the
 * person when a save cannot be used. The module does no file I/O; the app carries the decisions out.
 */
object SaveSlots {
    const val EXTENSION = ".h3r"
    const val BACKUP_SUFFIX = ".bak"
    const val TEMP_SUFFIX = ".tmp"

    /** Longest accepted battle id, so a file name stays well under common limits. */
    const val MAX_ID_LENGTH = 100

    /** Highest manual save number of one battle (`<battle_id>.m<number>.h3r`). */
    const val MAX_MANUAL_NUMBER = 999

    /** The three file names of one save, all inside the saves folder. */
    data class Slot(val battleId: String, val fileName: String, val backupName: String, val tempName: String)

    /**
     * The autosave slot of [battleId]: `<battle_id>.h3r`, the previous generation `<battle_id>.h3r.bak` and
     * the write temp file `<battle_id>.h3r.tmp`. Null when the id is not a safe file name: it must be 1 to
     * [MAX_ID_LENGTH] characters of ASCII letters, digits, `_` and `-`. No dot, so a battle id can never
     * look like a manual save name or an extension and can never leave the saves folder. Such a battle
     * simply cannot be saved.
     */
    fun slot(battleId: String): Slot? {
        if (battleId.isEmpty() || battleId.length > MAX_ID_LENGTH) return null
        if (!battleId.all { isNameChar(it) }) return null
        return named(battleId, battleId + EXTENSION)
    }

    /**
     * The manual save slot `<battle_id>.m<number>.h3r` for [number] in 1..[MAX_MANUAL_NUMBER]; null for an
     * unsafe id or a number out of range. The name depends only on its arguments (no clock): the caller
     * passes the counter, usually [nextManualNumber]. A manual name is never an autosave name. A manual
     * save is written once under a fresh name, so its write is `writePlan(Missing, Missing)`.
     */
    fun manualSlot(battleId: String, number: Int): Slot? {
        if (slot(battleId) == null || number < 1 || number > MAX_MANUAL_NUMBER) return null
        return named(battleId, battleId + ".m" + number + EXTENSION)
    }

    private fun named(battleId: String, file: String) = Slot(battleId, file, file + BACKUP_SUFFIX, file + TEMP_SUFFIX)

    private fun isNameChar(c: Char): Boolean =
        c in 'a'..'z' || c in 'A'..'Z' || c in '0'..'9' || c == '_' || c == '-'

    /** A main save file name read back: [number] is null for the autosave. */
    data class ParsedName(val battleId: String, val number: Int?)

    /**
     * Reads a file name made by [slot] or [manualSlot] (its `fileName`). Null for anything else: backup and
     * temp files, other files, non-canonical numbers (`m01`, `m0`, `m1000`) and unsafe ids.
     */
    fun parseFileName(name: String): ParsedName? {
        if (!name.endsWith(EXTENSION)) return null
        val stem = name.substring(0, name.length - EXTENSION.length)
        val dot = stem.indexOf('.')
        if (dot < 0) return if (slot(stem) != null) ParsedName(stem, null) else null
        val id = stem.substring(0, dot)
        val tail = stem.substring(dot + 1)
        if (slot(id) == null || tail.length !in 2..10 || tail[0] != 'm') return null
        val digits = tail.substring(1)
        if (digits[0] == '0' || !digits.all { it in '0'..'9' }) return null
        val n = digits.toInt()
        return if (n <= MAX_MANUAL_NUMBER) ParsedName(id, n) else null
    }

    /**
     * The counter for the next manual save of [battleId]: one past the highest manual number among
     * [fileNames] (the saves folder listing, any order). Numbers are not reused after a delete. Null when
     * the id is unsafe or [MAX_MANUAL_NUMBER] is taken.
     */
    fun nextManualNumber(battleId: String, fileNames: List<String>): Int? {
        if (slot(battleId) == null) return null
        var top = 0
        for (f in fileNames) {
            val p = parseFileName(f) ?: continue
            val n = p.number ?: continue
            if (p.battleId == battleId && n > top) top = n
        }
        return if (top >= MAX_MANUAL_NUMBER) null else top + 1
    }

    /** What the app found on disk. [Valid] means the file passes `ReplayResume.load`. */
    enum class FileState { Missing, Valid, Invalid }

    /** One step of a save write, to be carried out in the order of [writePlan]. */
    enum class WriteStep {
        /** Write the new bytes to the slot's temp file. */
        WriteTemp,

        /** fsync the temp file. */
        SyncTemp,

        /** Copy (not move) the current main file over the backup file. */
        CopyMainToBackup,

        /** Atomically rename the temp file over the main file. */
        RenameTempToMain,
    }

    /**
     * The steps of one write, given the state of the main file and of the backup before it.
     *
     * The backup is the previous generation, so a good main file is copied over it first. The main
     * file is never removed before the final atomic rename, so a crash at any step leaves the old or
     * the new generation. An unreadable main file is kept as the backup (nothing is deleted by the
     * app) unless the backup is good: a good backup is never replaced by a broken file. A missing
     * main file has nothing to keep.
     */
    fun writePlan(main: FileState, backup: FileState): List<WriteStep> {
        val keepMain = when (main) {
            FileState.Missing -> false
            FileState.Valid -> true
            FileState.Invalid -> backup != FileState.Valid
        }
        return if (keepMain) {
            listOf(WriteStep.WriteTemp, WriteStep.SyncTemp, WriteStep.CopyMainToBackup, WriteStep.RenameTempToMain)
        } else {
            listOf(WriteStep.WriteTemp, WriteStep.SyncTemp, WriteStep.RenameTempToMain)
        }
    }

    /** Which save to resume from. A null error means that file does not exist. */
    sealed interface ResumeChoice {
        data class FromMain(val resumed: Resumed) : ResumeChoice

        /** The main file was missing ([mainError] null) or unusable; the previous generation is used. */
        data class FromBackup(val resumed: Resumed, val mainError: ResumeError?) : ResumeChoice

        data object NothingToResume : ResumeChoice

        /** Files exist but neither verifies. A null error means that file does not exist. */
        data class Unresumable(val mainError: ResumeError?, val backupError: ResumeError?) : ResumeChoice
    }

    /**
     * Picks the save to resume from the load results of the main file and the backup (null = no such
     * file): the main file when it verifies, else the backup when it does, else nothing. Neither file
     * is ever deleted by this decision.
     */
    fun chooseResume(main: ResumeResult?, backup: ResumeResult?): ResumeChoice {
        if (main is ResumeResult.Ok) return ResumeChoice.FromMain(main.resumed)
        val mainError = (main as? ResumeResult.Failed)?.error
        if (backup is ResumeResult.Ok) return ResumeChoice.FromBackup(backup.resumed, mainError)
        val backupError = (backup as? ResumeResult.Failed)?.error
        if (mainError == null && backupError == null) return ResumeChoice.NothingToResume
        return ResumeChoice.Unresumable(mainError, backupError)
    }

    /** The line to show for [choice], or null when there is nothing to say (a clean resume or no save). */
    fun notice(choice: ResumeChoice): String? = when (choice) {
        is ResumeChoice.FromMain -> null
        ResumeChoice.NothingToResume -> null
        is ResumeChoice.FromBackup -> {
            val why = choice.mainError?.let { message(it) + " " } ?: ""
            why + "The previous save was used, so the last move may be missing."
        }
        is ResumeChoice.Unresumable -> message(choice.mainError ?: choice.backupError ?: ResumeError.Unreadable)
    }

    // ---- the slot list ("choose exact save") ----

    /** A file found in the saves folder: its name and bytes. */
    class SlotFile(val fileName: String, val bytes: ByteArray)

    enum class SlotKind { Autosave, Manual }

    sealed interface SlotStatus {
        /**
         * A verified save. [resumed] is what to load. [commands] and the hashes come from the file header
         * (`final_hash` is [Resumed.finalHash]); [rounds] is the round of the final state, which is not
         * in the header, so it costs one replay (done while verifying).
         */
        data class Ready(val resumed: Resumed, val commands: Int, val rounds: Int, val shortHash: String, val fullHash: String) : SlotStatus

        /** A file that does not verify; [message] is [SaveSlots.message] of [error]. The file is kept. */
        data class Unusable(val error: ResumeError, val message: String) : SlotStatus
    }

    /**
     * One entry of the slot list. [battleId] is the header's for a [SlotStatus.Ready] row and the file
     * name's for an unusable one. [number] is the manual save number, null for the autosave.
     */
    data class SlotRow(val fileName: String, val kind: SlotKind, val number: Int?, val battleId: String, val status: SlotStatus) {
        val title: String get() = if (number == null) "Autosave" else "Manual save $number"
    }

    /**
     * The list for the "load game" screen from the [files] of the saves folder: only main save files
     * (see [parseFileName]; `.bak`, `.tmp` and unrelated files are left out). Autosaves come first, then
     * manual saves; within each group by file name battle id, then number. The result does not depend
     * on the order of [files]. Every file is verified as [h3.presenter.ReplayResume.load] does (the same
     * errors and messages); none is ever deleted or changed.
     */
    fun list(files: List<SlotFile>, packs: Datapack): List<SlotRow> {
        val parsed = files.mapNotNull { f -> parseFileName(f.fileName)?.let { Pair(f, it) } }
        val order = compareBy<Pair<SlotFile, ParsedName>>({ if (it.second.number == null) 0 else 1 }, { it.second.battleId }, { it.second.number ?: 0 }, { it.first.fileName })
        return parsed.sortedWith(order).map { (f, p) -> rowOf(f, p, packs) }
    }

    private fun rowOf(f: SlotFile, p: ParsedName, packs: Datapack): SlotRow {
        val kind = if (p.number == null) SlotKind.Autosave else SlotKind.Manual
        return try {
            val l = Replay.load(f.bytes, packs)
            val scenario = Canonical.encode(l.scenario).toString(Charsets.US_ASCII)
            val hash = l.header["final_hash"] as String
            val resumed = Resumed(scenario, l.header["seed"] as BigInteger, l.commands, hash)
            val ready = SlotStatus.Ready(resumed, l.commands.size, l.finalState.round, hash.take(ResultSummary.SHORT_HASH_LENGTH), hash)
            SlotRow(f.fileName, kind, p.number, l.header["battle_id"] as String, ready)
        } catch (e: Exception) {
            val err = (e as? Replay.ReplayError)?.let { nameOf(it) } ?: ResumeError.Unreadable
            SlotRow(f.fileName, kind, p.number, p.battleId, SlotStatus.Unusable(err, message(err)))
        }
    }

    /** Same mapping as `ReplayResume.load`: the error class name is the [ResumeError] name. */
    private fun nameOf(e: Replay.ReplayError): ResumeError =
        ResumeError.entries.firstOrNull { it != ResumeError.Unreadable && it.name == e::class.simpleName } ?: ResumeError.Unreadable

    /** The outcome of choosing one row of the list. */
    sealed interface SlotSelection {
        /** Resume from [resumed] (feed it to `ReplayResume.into` on a fresh session). */
        data class Load(val fileName: String, val resumed: Resumed) : SlotSelection

        /** The chosen save does not verify; show [message]. Nothing is loaded and the file is kept. */
        data class Refused(val fileName: String, val error: ResumeError, val message: String) : SlotSelection

        /** [fileName] is not in the list (the backup and temp files are never choosable). */
        data class NotListed(val fileName: String) : SlotSelection
    }

    /** Chooses exactly the row named [fileName] from [rows]; there is no fallback to another file. */
    fun select(rows: List<SlotRow>, fileName: String): SlotSelection {
        val row = rows.firstOrNull { it.fileName == fileName } ?: return SlotSelection.NotListed(fileName)
        return when (val st = row.status) {
            is SlotStatus.Ready -> SlotSelection.Load(fileName, st.resumed)
            is SlotStatus.Unusable -> SlotSelection.Refused(fileName, st.error, st.message)
        }
    }

    /** The user-facing text for [error]; the technical message of the failure is never shown. */
    fun message(error: ResumeError): String = when (error) {
        ResumeError.Malformed -> "This save is not a readable game file. The file was kept."
        ResumeError.Truncated -> "This save is incomplete, perhaps because the app stopped while writing it. The file was kept."
        ResumeError.Tampered -> "This save failed its integrity check, so it was changed or damaged. The file was kept."
        ResumeError.UnsupportedVersion -> "This save uses a file format version this app does not support. The file was kept."
        ResumeError.UnsupportedKind -> "This file is not a battle save. The file was kept."
        ResumeError.MismatchedRulesPack -> "This save was made with different game rules than this version of the app uses. The file was kept."
        ResumeError.MismatchedPolicy -> "This save was made with different battle settings than this version of the app uses. The file was kept."
        ResumeError.MismatchedCreatures -> "This save was made with different creature data than this version of the app uses. The file was kept."
        ResumeError.Diverged -> "Replaying this save does not reach the recorded result, so it cannot be trusted. The file was kept."
        ResumeError.Unreadable -> "This save could not be read for an unknown reason. The file was kept."
    }
}
