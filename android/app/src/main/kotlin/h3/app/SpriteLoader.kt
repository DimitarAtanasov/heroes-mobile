package h3.app

import android.graphics.Bitmap
import h3.presenter.ui.GameDataLayout
import h3.presenter.ui.LodSource
import h3.presenter.ui.PagePixels
import h3.presenter.ui.SpriteLoadPlan
import java.io.File
import java.nio.ByteBuffer

/**
 * Loads the player's own creature sprites for the board at runtime, from game files the player put
 * on the device (android-app.md 3 and 4.3). Nothing is bundled and nothing here is read unless the
 * files exist: with no data the loader does nothing and the board keeps drawing tokens. The logic
 * (which DEF belongs to which creature, decoding, atlas packing, named errors) is
 * [SpriteLoadPlan] in `:presenter`, tested on the JVM; this file only does file reads, the thread
 * and the Bitmap conversion.
 *
 * Where the data lives: the `copyH3Data` Gradle task stages only the three JSON data packs, never
 * game files. The import flow of android-app.md 3.2 (not built yet) copies the player's `Data`
 * folder to `noBackupFilesDir/gamedata/`. So the caller passes the candidate roots; each root may
 * be the install root (holding `Data/`) or the `Data` folder itself, and names match ignoring case.
 */
object SpriteLoader {
    /** Sprite archives in search order; the first one holding a DEF wins. Both are optional here. */
    val LOD_NAMES = GameDataLayout.SPRITE_ARCHIVES

    /** Integer upscale of the DEF art on the board (sprite-atlas.md, "Upscaling"). */
    const val SPRITE_SCALE = 2

    /**
     * The sprite archives found under the first root that has any, in [LOD_NAMES] order. Empty
     * when nothing is staged (the normal case on a fresh install). Never throws. Which file is meant
     * is decided by [GameDataLayout.resolveArchives], the same rule the import uses; this code only
     * lists the root and one folder level below it.
     */
    fun findLodFiles(roots: List<File>): List<File> {
        for (root in roots) {
            val found = GameDataLayout.resolveArchives(relativePaths(root), LOD_NAMES).map { File(root, it) }
            if (found.isNotEmpty()) return found
        }
        return emptyList()
    }

    /** Files directly in [root] and files directly in its subfolders, as `/` separated relative paths. */
    private fun relativePaths(root: File): List<String> {
        val out = ArrayList<String>()
        for (child in children(root)) {
            if (child.isFile) {
                out.add(child.name)
            } else if (child.isDirectory) {
                for (grandchild in children(child)) if (grandchild.isFile) out.add(child.name + "/" + grandchild.name)
            }
        }
        return out
    }

    private fun children(dir: File): List<File> = try {
        dir.listFiles()?.toList() ?: emptyList()
    } catch (e: SecurityException) {
        emptyList()
    }

    /**
     * Starts loading on a background daemon thread and returns it, or returns null (quietly, no
     * callback) when [creatureNames] is empty or no sprite archive is staged under [roots].
     *
     * When a thread is returned, [onDone] is called exactly once, ON THAT THREAD: post to the main
     * thread before touching Compose state. Its first argument is the sprites, or null when none
     * could be built (every creature then keeps its token); the second is one line per problem
     * (`SpriteLoadError.describe()`, plus `SPRITES_FAILED ...` for I/O or memory failures), which the
     * caller may ignore. Lines name creatures, DEF and archive file names only, never file contents.
     * [creatureNames] are the roster names exactly as `BattleCreature.name` (for example `eng.roster.map { it.name }`),
     * because the atlas keys derive from them (`UiSpriteKey`).
     */
    fun start(
        roots: List<File>,
        creatureNames: List<String>,
        onDone: (BoardSprites?, List<String>) -> Unit,
    ): Thread? {
        if (creatureNames.isEmpty()) return null
        val files = findLodFiles(roots)
        if (files.isEmpty()) return null
        val worker = Thread({
            val out = loadBlocking(files, creatureNames)
            onDone(out.sprites, out.notes)
        }, "sprite-loader")
        worker.isDaemon = true
        worker.start()
        return worker
    }

    internal class Loaded(val sprites: BoardSprites?, val notes: List<String>)

    /** The blocking part of [start]; also usable from a test or another worker. Never throws. */
    internal fun loadBlocking(files: List<File>, creatureNames: List<String>): Loaded {
        try {
            val lods = files.map { LodSource(it.name, it.readBytes()) }
            val result = SpriteLoadPlan.load(creatureNames, lods, scale = SPRITE_SCALE)
            val notes = result.errors.map { it.describe() }
            val atlas = result.atlas ?: return Loaded(null, notes)
            val pages = ArrayList<Bitmap>()
            for (p in atlas.pages) pages.add(toBitmap(p.width, p.height, p.argb))
            return Loaded(BoardSprites(atlas, pages), notes)
        } catch (e: Exception) {
            return Loaded(null, listOf("SPRITES_FAILED " + e.javaClass.simpleName))
        } catch (e: OutOfMemoryError) {
            // The archives are read whole (LodArchive takes a ByteArray); on a small heap that can fail.
            // Sprites are optional, so degrade to tokens instead of crashing the app.
            return Loaded(null, listOf("SPRITES_FAILED OutOfMemoryError"))
        }
    }

    /**
     * One atlas page to a bitmap, without premultiplying twice.
     *
     * [h3.presenter.Page.argb] is already premultiplied (`Premultiply.pack`). `Bitmap.createBitmap(int[], ...)`
     * and `setPixels` take STRAIGHT (non-premultiplied) colours and premultiply them themselves,
     * so feeding them these ints would darken every soft edge and shadow pixel a second time.
     * `copyPixelsFromBuffer` instead copies the raw bytes in the bitmap's own format, and an
     * `ARGB_8888` bitmap is premultiplied by default and stores R, G, B, A bytes per pixel in memory,
     * which is what [PagePixels.toRgbaBytes] produces. No `setPremultiplied` call is needed.
     */
    private fun toBitmap(width: Int, height: Int, argb: IntArray): Bitmap {
        val bmp = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        bmp.copyPixelsFromBuffer(ByteBuffer.wrap(PagePixels.toRgbaBytes(argb)))
        return bmp
    }
}
