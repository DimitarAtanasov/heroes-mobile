package h3.app

import h3.presenter.ByteSink
import h3.presenter.ReplayResume
import h3.presenter.ResumeResult
import h3.presenter.ui.SaveSlots
import h3.sim.Datapack
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * The main save files in [dir] (see `SaveSlots.parseFileName`: backup, temp and other files are
 * skipped) as [SaveSlots.SlotFile] entries for `SaveSlots.list`. Blocking file reads: call it off the
 * UI thread, for example through [SaveFolderWriter.readFolder]. A missing folder gives an empty list.
 */
fun readSaveFolder(dir: File): List<SaveSlots.SlotFile> {
    val names = dir.list() ?: return emptyList()
    val out = ArrayList<SaveSlots.SlotFile>()
    for (name in names.sorted()) {
        if (SaveSlots.parseFileName(name) == null) continue
        try {
            out.add(SaveSlots.SlotFile(name, File(dir, name).readBytes()))
        } catch (e: IOException) {
            // The file vanished or cannot be read: it is simply not listed.
        }
    }
    return out
}

/**
 * Writes saves into the folder [dir] (use `File(filesDir, "saves")`) on its own single writer thread,
 * so neither the UI thread nor the session worker waits for the disk. Every write follows
 * `SaveSlots.writePlan` exactly: temp file, fsync, optional copy of the main file to the backup,
 * atomic rename over the main file. Writes, folder reads and callbacks run on that one thread in
 * the order they were queued, so a [readFolder] sees every earlier write. Callbacks run on the writer
 * thread: hop to the main thread before touching UI state. Nothing is ever deleted.
 *
 * [packs] is used to tell a valid main or backup file from a broken one (`ReplayResume.load`).
 */
class SaveFolderWriter(private val dir: File, private val packs: Datapack) {
    private val executor: ExecutorService = Executors.newSingleThreadExecutor { r ->
        val t = Thread(r, "h3-save-writer")
        t.isDaemon = true
        t
    }

    // Writer thread only. Files this writer produced itself, so it need not replay them again.
    private val known = LinkedHashMap<String, SaveSlots.FileState>()

    @Volatile
    var failures: Int = 0
        private set

    @Volatile
    var lastError: String? = null
        private set

    /**
     * The autosave sink for [slot] (`SaveSlots.slot(battleId)`), for `ReplayAutosave`. `write` returns
     * at once; the bytes are written later on the writer thread. A failed write is counted in
     * [failures] and the next autosave tries again with the full log. Throws after [close].
     */
    fun sinkFor(slot: SaveSlots.Slot): ByteSink = ByteSink { bytes ->
        executor.execute { attempt(slot, bytes) }
    }

    /** Writes [bytes] as [slot] (a manual save: `SaveSlots.manualSlot`). [onDone] gets true when the file is in place. */
    fun write(slot: SaveSlots.Slot, bytes: ByteArray, onDone: (Boolean) -> Unit) {
        executor.execute { onDone(attempt(slot, bytes)) }
    }

    /** Reads the folder on the writer thread, after every write queued before this call. */
    fun readFolder(onResult: (List<SaveSlots.SlotFile>) -> Unit) {
        executor.execute { onResult(readSaveFolder(dir)) }
    }

    /** Lets the queued writes finish, then stops the writer thread. Returns at once. */
    fun close() {
        executor.shutdown()
    }

    private fun attempt(slot: SaveSlots.Slot, bytes: ByteArray): Boolean =
        try {
            carryOut(slot, bytes)
            true
        } catch (e: Exception) {
            known.clear()
            failures++
            lastError = e.toString()
            false
        }

    private fun carryOut(slot: SaveSlots.Slot, bytes: ByteArray) {
        dir.mkdirs()
        val main = File(dir, slot.fileName)
        val backup = File(dir, slot.backupName)
        val temp = File(dir, slot.tempName)
        val mainState = stateOf(main)
        val plan = SaveSlots.writePlan(mainState, stateOf(backup))
        var out: FileOutputStream? = null
        try {
            for (step in plan) {
                when (step) {
                    SaveSlots.WriteStep.WriteTemp -> {
                        val s = FileOutputStream(temp)
                        out = s
                        s.write(bytes)
                        s.flush()
                    }
                    SaveSlots.WriteStep.SyncTemp -> {
                        val s = out ?: throw IOException("no temp file to sync")
                        s.fd.sync()
                        s.close()
                        out = null
                    }
                    SaveSlots.WriteStep.CopyMainToBackup -> {
                        main.copyTo(backup, overwrite = true)
                        known[backup.name] = mainState
                    }
                    SaveSlots.WriteStep.RenameTempToMain -> {
                        if (!temp.renameTo(main)) throw IOException("could not rename " + temp.name + " to " + main.name)
                        known[main.name] = SaveSlots.FileState.Valid
                    }
                }
            }
        } finally {
            out?.close()
        }
    }

    private fun stateOf(f: File): SaveSlots.FileState {
        val cached = known[f.name]
        if (cached != null) return cached
        if (!f.exists()) return SaveSlots.FileState.Missing
        return try {
            if (ReplayResume.load(f.readBytes(), packs) is ResumeResult.Ok) SaveSlots.FileState.Valid else SaveSlots.FileState.Invalid
        } catch (e: IOException) {
            SaveSlots.FileState.Invalid
        }
    }
}
