package h3.app

import h3.presenter.ui.CheckedFile
import h3.presenter.ui.GameDataCheck
import h3.presenter.ui.GameDataLayout
import h3.presenter.ui.GameDataResult
import h3.presenter.ui.GameFile
import h3.presenter.ui.GameRoster
import h3.presenter.ui.GameRosterResult
import h3.presenter.ui.ImportPlan
import h3.presenter.ui.ImportResult
import h3.presenter.ui.IoStage
import java.io.DataInputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException

/**
 * The player's own game data on disk (android-app.md 3.2 and 3.5): status, an in-place check of
 * sideloaded files, and a crash-safe copy from a source folder. All decisions are the pure
 * [ImportPlan] and [GameDataCheck]; this class only does the file work. It imports nothing from
 * `android.*`, so it compiles and is tested on the JVM.
 *
 * [root] is the app's no-backup folder (`noBackupFilesDir`). Under it: `gamedata` (the set the app
 * reads: the required files either directly in it or in a `Data` folder, plus `manifest.json`),
 * `gamedata.import` (a copy being built) and `gamedata.old` (the previous set during the swap).
 *
 * Threading: ONE single-thread executor named [THREAD_NAME] does all I/O, in call order. Every
 * callback runs on that thread, so post to the main thread before touching UI state. A call made
 * after [close] is ignored and its callback never runs. Nothing here throws to the caller: every
 * failure is a named [ImportResult] (stage and file names only; no file bytes, no exception text).
 *
 * Recovery: [ImportPlan.recover] runs when the store is created and before every status, check and
 * import, and its actions are carried out on disk, so a crash at any step leaves the old or the
 * new complete set and no `.part` file.
 */
class GameDataStore(private val root: File) {
    companion object {
        const val THREAD_NAME = "gamedata-io"

        /** Written to `manifest.json` as `validator_version`; raise it when the checks change. */
        const val VALIDATOR_VERSION = 1

        private const val COPY_BUFFER_BYTES = 65_536
        private const val MAX_MANIFEST_BYTES = 65_536L
    }

    private val executor: ExecutorService = Executors.newSingleThreadExecutor { r ->
        val t = Thread(r, THREAD_NAME)
        t.isDaemon = true
        t
    }

    /**
     * Test seam: called on the I/O thread before step `index` of an import; returning true stops the
     * import at once, touching nothing (a simulated process death: no cleanup, no recovery).
     */
    @Volatile
    internal var crashBeforeStep: (Int, ImportPlan.Step) -> Boolean = { _, _ -> false }

    init {
        post { recoverNow() }
    }

    /** Recovers, then reports [ImportPlan.DataStatus] of `gamedata` against its `manifest.json`. */
    fun status(onResult: (ImportPlan.DataStatus) -> Unit) {
        post {
            val s = try {
                recoverNow()
                statusNow()
            } catch (e: Throwable) {
                ImportPlan.DataStatus.Missing
            }
            onResult(s)
        }
    }

    /**
     * Validates the files already in `gamedata` (sideloaded, in the root or in `Data/`) with
     * [GameDataCheck.check]. On success `manifest.json` is written atomically (temp file, sync,
     * rename), so [status] reports Found afterwards; the result is [ImportResult.Valid]. Otherwise
     * [ImportResult.Invalid] or [ImportResult.IoFailed], and nothing is written.
     */
    fun checkInPlace(onResult: (ImportResult) -> Unit) {
        post {
            val r = try {
                if (!recoverNow()) ImportResult.IoFailed(IoStage.Recover, null) else checkLive()
            } catch (e: Throwable) {
                ImportResult.IoFailed(IoStage.Scan, null)
            }
            onResult(r)
        }
    }

    /**
     * Copies the required files from [sourceDir] (the install root holding `Data/`, or the `Data`
     * folder itself) into `gamedata`: plan, space check, copy to `.part`, sync, rename, validate the
     * copies, `manifest.json` last, then swap. [onProgress] gets integer progress (at 0, on each change
     * of the whole percent, and at the end). [onDone] gets exactly one result. Nothing is replaced
     * unless every step succeeded; after a failure the leftovers are cleaned at once.
     */
    fun importFrom(sourceDir: File, onProgress: (ImportPlan.Progress) -> Unit, onDone: (ImportResult) -> Unit) {
        post {
            val r = try {
                doImport(sourceDir, onProgress)
            } catch (e: Throwable) {
                try { recoverNow() } catch (e2: Throwable) { /* the next start recovers */ }
                ImportResult.IoFailed(IoStage.Copy, null)
            }
            onDone(r)
        }
    }

    /**
     * The battle roster from `H3bitmap.lod` in `gamedata` (root or `Data/`, found with the
     * [GameDataLayout] rule), built by [GameRoster.load] with [mappingJson] (`txt_maps/crtraits.json`).
     * [onResult] runs on the I/O thread and gets null when there is no such archive (nothing imported:
     * the app shows only the import prompt), or the roster or its refusal. Never throws; a read
     * failure is [GameRoster.READ_FAILED_TEXT].
     */
    fun loadRoster(mappingJson: String, onResult: (GameRosterResult?) -> Unit) {
        post {
            val r: GameRosterResult? = try {
                recoverNow()
                val live = dir(ImportPlan.LIVE_DIR)
                val listing = listEntries(live)?.map { it.path } ?: emptyList()
                val name = GameDataLayout.resolveArchives(listing, listOf(GameDataCheck.BITMAP_ARCHIVE)).firstOrNull()
                if (name == null) null else GameRoster.load(readBounded(File(live, name)), mappingJson)
            } catch (e: Throwable) {
                GameRosterResult.Refused(GameRoster.READ_FAILED_TEXT)
            }
            onResult(r)
        }
    }

    /** Lets queued work finish, then stops the I/O thread. Returns at once. */
    fun close() {
        executor.shutdown()
    }

    private fun post(task: () -> Unit) {
        try {
            executor.execute(task)
        } catch (e: RejectedExecutionException) {
            // Closed: the call is ignored.
        }
    }

    // ---- folders ----

    private fun dir(name: String): File = File(root, name)

    /** Files of [folder] and of its `Data` subfolder (any case) as pure-plan entries; null when it cannot be listed. */
    private fun listEntries(folder: File): List<ImportPlan.SourceEntry>? {
        val top = folder.listFiles() ?: return null
        val out = ArrayList<ImportPlan.SourceEntry>()
        for (c in top.sortedBy { it.name }) {
            if (c.isFile) {
                out.add(ImportPlan.SourceEntry(c.name, c.length()))
            } else if (c.isDirectory && c.name.equals(ImportPlan.DATA_DIR_NAME, ignoreCase = true)) {
                val inner = c.listFiles() ?: continue
                for (g in inner.sortedBy { it.name }) {
                    if (g.isFile) out.add(ImportPlan.SourceEntry(c.name + "/" + g.name, g.length()))
                }
            }
        }
        return out
    }

    // ---- status ----

    private fun readManifest(folder: File): ImportPlan.Manifest? {
        return try {
            val f = File(folder, ImportPlan.MANIFEST_NAME)
            if (!f.isFile || f.length() > MAX_MANIFEST_BYTES) return null
            val text = String(f.readBytes(), Charsets.UTF_8)
            (ImportPlan.decodeManifest(text) as? ImportPlan.ManifestParse.Parsed)?.manifest
        } catch (e: Exception) {
            null
        } catch (e: OutOfMemoryError) {
            null
        }
    }

    private fun statusNow(): ImportPlan.DataStatus {
        val live = dir(ImportPlan.LIVE_DIR)
        if (!live.isDirectory) return ImportPlan.DataStatus.Missing
        val manifest = readManifest(live) ?: return ImportPlan.DataStatus.Missing
        val entries = listEntries(live) ?: return ImportPlan.DataStatus.Missing
        val sizes = LinkedHashMap<String, Long>()
        for (f in manifest.files) {
            when (val s = ImportPlan.select(entries, listOf(f.name))) {
                is ImportPlan.Selection.Chosen -> sizes[f.name] = s.files[0].size
                is ImportPlan.Selection.MissingSource -> {}
                // Ambiguous, unusable name or unknown size: a size no manifest can list, so it reads as Changed.
                else -> sizes[f.name] = -1L
            }
        }
        return ImportPlan.status(manifest, sizes)
    }

    // ---- recovery ----

    /** Carries out [ImportPlan.recover]. False when an action failed (the next call decides again from disk). */
    private fun recoverNow(): Boolean {
        val live = dir(ImportPlan.LIVE_DIR)
        val staging = dir(ImportPlan.STAGING_DIR)
        val old = dir(ImportPlan.OLD_DIR)
        val liveOk = live.exists() && old.exists() && statusNow() == ImportPlan.DataStatus.Found
        for (action in ImportPlan.recover(live.exists(), staging.exists(), old.exists(), liveOk)) {
            val ok = when (action) {
                ImportPlan.RecoverAction.DeleteStaging -> staging.deleteRecursively()
                ImportPlan.RecoverAction.DeleteOld -> old.deleteRecursively()
                ImportPlan.RecoverAction.DeleteLive -> live.deleteRecursively()
                ImportPlan.RecoverAction.RestoreOld -> old.renameTo(live)
            }
            if (!ok) return false
        }
        return true
    }

    // ---- reading and checking ----

    /** The whole file, never more than the validator's cap. OutOfMemoryError is left to the validator. */
    private fun readBounded(f: File): ByteArray {
        val len = f.length()
        if (len > GameDataCheck.MAX_CHECKABLE_BYTES) throw IOException("too large")
        val buf = ByteArray(len.toInt())
        DataInputStream(FileInputStream(f)).use { it.readFully(buf) }
        return buf
    }

    private fun checkFolder(folder: File): GameDataResult {
        val entries = listEntries(folder) ?: emptyList()
        return GameDataCheck.check(entries.map { GameFile(it.path, it.size) }, { p -> readBounded(File(folder, p)) })
    }

    private fun checkLive(): ImportResult {
        val live = dir(ImportPlan.LIVE_DIR)
        return when (val res = checkFolder(live)) {
            is GameDataResult.Invalid -> ImportResult.Invalid(res.issues)
            is GameDataResult.Ok -> {
                val m = ImportPlan.Manifest(VALIDATOR_VERSION, res.files.map { ImportPlan.ManifestFile(it.name, it.size) })
                if (writeManifestAtomically(live, ImportPlan.encodeManifest(m))) {
                    ImportResult.Valid(res.files)
                } else {
                    ImportResult.IoFailed(IoStage.Manifest, ImportPlan.MANIFEST_NAME)
                }
            }
        }
    }

    /** Temp file, sync, rename over `manifest.json`. */
    private fun writeManifestAtomically(folder: File, content: String): Boolean {
        val tmp = File(folder, ImportPlan.MANIFEST_NAME + ImportPlan.PART_SUFFIX)
        return try {
            FileOutputStream(tmp).use { s ->
                s.write(content.toByteArray(Charsets.UTF_8))
                s.flush()
                s.fd.sync()
            }
            if (tmp.renameTo(File(folder, ImportPlan.MANIFEST_NAME))) {
                true
            } else {
                tmp.delete()
                false
            }
        } catch (e: IOException) {
            tmp.delete()
            false
        }
    }

    // ---- import ----

    private fun stageOf(step: ImportPlan.Step): IoStage = when (step) {
        is ImportPlan.Step.CopyToPart, is ImportPlan.Step.RenamePart -> IoStage.Copy
        is ImportPlan.Step.SyncFile -> if (step.path.endsWith(ImportPlan.MANIFEST_NAME)) IoStage.Manifest else IoStage.Copy
        is ImportPlan.Step.WriteManifest -> IoStage.Manifest
        is ImportPlan.Step.MoveLiveToOld, is ImportPlan.Step.PromoteStaging, is ImportPlan.Step.DeleteOld -> IoStage.Swap
    }

    private fun fileNameOf(step: ImportPlan.Step): String = when (step) {
        is ImportPlan.Step.CopyToPart -> step.target.removeSuffix(ImportPlan.PART_SUFFIX).substringAfterLast('/')
        is ImportPlan.Step.SyncFile -> step.path.removeSuffix(ImportPlan.PART_SUFFIX).substringAfterLast('/')
        is ImportPlan.Step.RenamePart -> step.to.substringAfterLast('/')
        is ImportPlan.Step.WriteManifest -> ImportPlan.MANIFEST_NAME
        is ImportPlan.Step.MoveLiveToOld -> step.to
        is ImportPlan.Step.PromoteStaging -> step.to
        is ImportPlan.Step.DeleteOld -> step.path
    }

    private fun doImport(sourceDir: File, onProgress: (ImportPlan.Progress) -> Unit): ImportResult {
        if (!recoverNow()) return ImportResult.IoFailed(IoStage.Recover, null)
        val entries = listEntries(sourceDir) ?: return ImportResult.IoFailed(IoStage.Scan, null)
        val files = when (val sel = ImportPlan.select(entries, GameDataCheck.DEFAULT_REQUIRED)) {
            is ImportPlan.Selection.Chosen -> sel.files
            else -> return ImportResult.SourceProblem(sel)
        }
        root.mkdirs()
        val needed = ImportPlan.neededBytes(files)
        when (val space = ImportPlan.checkSpace(needed, root.usableSpace)) {
            is ImportPlan.SpaceCheck.NotEnoughSpace -> return ImportResult.NotEnoughSpace(space.needed, space.free)
            is ImportPlan.SpaceCheck.Ok -> {}
        }
        val steps = ImportPlan.plan(files, VALIDATOR_VERSION, dir(ImportPlan.LIVE_DIR).exists())
        val staging = dir(ImportPlan.STAGING_DIR)
        if (!staging.mkdirs()) return ImportResult.IoFailed(IoStage.Copy, ImportPlan.STAGING_DIR)

        var crashed = false
        var checked: List<CheckedFile>? = null
        var done = 0L
        var lastPercent = 0
        onProgress(ImportPlan.Progress(0L, needed))

        fun fail(r: ImportResult): ImportResult {
            if (!crashed) {
                try { recoverNow() } catch (e: Throwable) { /* the next start recovers */ }
            }
            return r
        }

        var current: ImportPlan.Step? = null
        try {
            for ((i, step) in steps.withIndex()) {
                current = step
                if (crashBeforeStep(i, step)) {
                    crashed = true
                    return ImportResult.IoFailed(stageOf(step), null)
                }
                when (step) {
                    is ImportPlan.Step.CopyToPart -> {
                        var copied = 0L
                        FileInputStream(File(sourceDir, step.source)).use { ins ->
                            FileOutputStream(dir(step.target)).use { outs ->
                                val buf = ByteArray(COPY_BUFFER_BYTES)
                                while (copied <= step.size) {
                                    val n = ins.read(buf)
                                    if (n < 0) break
                                    outs.write(buf, 0, n)
                                    copied += n
                                    done += n
                                    val p = ImportPlan.Progress(done, needed)
                                    if (p.percent != lastPercent) {
                                        lastPercent = p.percent
                                        onProgress(p)
                                    }
                                }
                            }
                        }
                        if (copied != step.size) return fail(ImportResult.SourceChanged(fileNameOf(step)))
                    }
                    is ImportPlan.Step.SyncFile -> FileOutputStream(dir(step.path), true).use { it.fd.sync() }
                    is ImportPlan.Step.RenamePart ->
                        if (!dir(step.from).renameTo(dir(step.to))) return fail(ImportResult.IoFailed(IoStage.Copy, fileNameOf(step)))
                    is ImportPlan.Step.WriteManifest -> {
                        // Validate the finished copies before the record that makes the set complete.
                        if (checked == null) {
                            when (val res = checkFolder(staging)) {
                                is GameDataResult.Invalid -> return fail(ImportResult.Invalid(res.issues))
                                is GameDataResult.Ok -> checked = res.files
                            }
                        }
                        FileOutputStream(dir(step.path)).use {
                            it.write(step.content.toByteArray(Charsets.UTF_8))
                            it.flush()
                        }
                    }
                    is ImportPlan.Step.MoveLiveToOld ->
                        if (!dir(step.from).renameTo(dir(step.to))) return fail(ImportResult.IoFailed(IoStage.Swap, fileNameOf(step)))
                    is ImportPlan.Step.PromoteStaging ->
                        if (!dir(step.from).renameTo(dir(step.to))) return fail(ImportResult.IoFailed(IoStage.Swap, fileNameOf(step)))
                    is ImportPlan.Step.DeleteOld -> {
                        // The new set is live; a leftover old folder is removed by the next recovery.
                        dir(step.path).deleteRecursively()
                    }
                }
            }
        } catch (e: Throwable) {
            val s = current
            return fail(ImportResult.IoFailed(if (s == null) IoStage.Copy else stageOf(s), if (s == null) null else fileNameOf(s)))
        }
        if (lastPercent != 100) onProgress(ImportPlan.Progress(needed, needed))
        return ImportResult.Valid(checked ?: emptyList())
    }
}
