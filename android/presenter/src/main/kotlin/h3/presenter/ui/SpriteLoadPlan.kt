package h3.presenter.ui

import h3.presenter.Atlas
import h3.presenter.AtlasBuilder
import h3.presenter.AtlasFrame
import h3.presenter.BuildResult
import h3.presenter.DefFrames
import h3.presenter.Reason
import h3.sim.Def
import h3.sim.DefFile
import h3.sim.LodArchive

/**
 * Pure sprite loading plan (android-app.md 4.3 and 7.3): from the bytes of the player's own LOD
 * archives (supplied by the caller, who does the file I/O) and the creature names of the roster,
 * decide which DEF each creature needs, decode those DEFs and build one [Atlas] keyed exactly as
 * [UiSpriteKey] expects, so `StackRosterRow.spriteRect(atlas)` finds the idle still.
 *
 * Nothing here reads a file, a clock or the environment, and no game data lives in the repo: the
 * tests build synthetic archives. Every failure is a named [SpriteLoadError] in the result; this
 * code never throws on bad archive or DEF bytes. A creature without a usable sprite is simply
 * absent from the atlas, and the board draws its token (the same fallback as no atlas at all).
 */
class LodSource(
    /** File name for messages only (for example `H3sprite.lod`). */
    val name: String,
    val bytes: ByteArray,
)

/** What went wrong for one archive or creature. [code] is stable and may be shown or logged. */
sealed class SpriteLoadError {
    abstract val code: String
    abstract fun describe(): String

    /** The archive could not be parsed; its members are not available. */
    data class BadArchive(val lod: String, val detail: String) : SpriteLoadError() {
        override val code get() = "BAD_ARCHIVE"
        override fun describe() = "$code $lod: $detail"
    }

    /** The table has no DEF for this creature (expected for any creature outside the table). */
    data class NoMapping(val creature: String) : SpriteLoadError() {
        override val code get() = "NO_MAPPING"
        override fun describe() = "$code $creature"
    }

    /** The mapped DEF is in none of the supplied archives. */
    data class MissingDef(val creature: String, val def: String) : SpriteLoadError() {
        override val code get() = "MISSING_DEF"
        override fun describe() = "$code $creature: $def"
    }

    /** The DEF (or its member read) is corrupt, or its frames could not be turned into atlas frames. */
    data class BadDef(val creature: String, val def: String, val detail: String) : SpriteLoadError() {
        override val code get() = "BAD_DEF"
        override fun describe() = "$code $creature: $def: $detail"
    }

    /** The DEF decoded but has no non-empty frame 0 in the idle group, so there is nothing to draw. */
    data class NoIdleFrame(val creature: String, val def: String) : SpriteLoadError() {
        override val code get() = "NO_IDLE_FRAME"
        override fun describe() = "$code $creature: $def"
    }

    /** The atlas could not be packed (duplicate key, frame too large or over budget): no sprites at all. */
    data class AtlasFailed(val reason: Reason, val detail: String) : SpriteLoadError() {
        override val code get() = "ATLAS_FAILED"
        override fun describe() = "$code $reason: $detail"
    }
}

/**
 * Outcome of [SpriteLoadPlan.load]. [atlas] is null when no creature got a sprite or the atlas
 * failed; [loaded] lists the creature names (first-appearance order) that have an idle still in
 * [atlas]; [errors] is everything that went wrong, in a fixed order.
 */
class SpriteLoadResult(val atlas: Atlas?, val loaded: List<String>, val errors: List<SpriteLoadError>) {
    fun hasSprite(creatureName: String): Boolean = atlas != null && creatureName in loaded
}

/** One creature and the DEF member chosen for it. */
data class PlanEntry(val creature: String, val def: String)

/** [entries] in first-appearance order of the creature names; [unmapped] are the names the table lacks. */
data class Resolution(val entries: List<PlanEntry>, val unmapped: List<String>)

object SpriteLoadPlan {
    /**
     * Creature name (as in `data/creatures.json`, so with its "Test " prefix) to DEF member name, for
     * the four shipped placeholder creatures only. This is NOT a creature table of the game.
     *
     * OPEN DECISION G3 / Q2 (android-app.md sections 2 and 14): where the real creature-to-sprite
     * mapping comes from (owner-written facts with an ADR-0003 citation, or derived from the
     * player's install) is undecided. Until then:
     *  - The three DEF names below are UNVERIFIED stand-ins, written from memory of the game's file
     *    naming and never checked against real files (none are available to the project). A wrong
     *    name costs nothing: the DEF is reported as [SpriteLoadError.MissingDef] and the board draws
     *    the token. They need owner confirmation or replacement.
     *  - "Test Brute" is deliberately absent, to keep the no-mapping path (token) in real use.
     *  - A real mapping is keyed by `CRTRAITS.TXT` row, not by (localised) name; names are used here
     *    only because the placeholder roster has no rows.
     */
    val DEFAULT_TABLE: Map<String, String> = linkedMapOf(
        "Test Pikeman" to "CPKMAN.DEF",
        "Test Slinger" to "CLCBOW.DEF",
        "Test Glider" to "CGRIFF.DEF",
    )

    /** The DEF member for [creatureName], or null when the table has none. Exact, case-sensitive match. */
    fun defFor(creatureName: String, table: Map<String, String> = DEFAULT_TABLE): String? =
        table[creatureName]?.takeIf { it.isNotEmpty() }

    /**
     * Which DEF each distinct creature needs. Duplicate names are dropped (first wins), the order is
     * the order of [creatureNames].
     */
    fun resolve(creatureNames: List<String>, table: Map<String, String> = DEFAULT_TABLE): Resolution {
        val entries = ArrayList<PlanEntry>()
        val unmapped = ArrayList<String>()
        for (n in creatureNames.distinct()) {
            val d = defFor(n, table)
            if (d == null) unmapped.add(n) else entries.add(PlanEntry(n, d))
        }
        return Resolution(entries, unmapped)
    }

    /**
     * Decodes the DEFs named by the table for [creatureNames] out of [lods] and packs them into one
     * atlas. [lods] are searched in the given order and the first archive holding a member wins
     * (member names compare case-insensitively, as in `lod.md`). With [idleGroupOnly] (the default)
     * only the frames of the idle group are kept, which is all the board draws and keeps the
     * decoded size small; pass false to keep every frame. Never throws for bad archive or DEF bytes.
     */
    fun load(
        creatureNames: List<String>,
        lods: List<LodSource>,
        table: Map<String, String> = DEFAULT_TABLE,
        idleGroupOnly: Boolean = true,
        maxPage: Int = AtlasBuilder.DEFAULT_MAX_PAGE,
        budgetBytes: Long = AtlasBuilder.DEFAULT_BUDGET_BYTES,
    ): SpriteLoadResult {
        val res = resolve(creatureNames, table)
        val errors = ArrayList<SpriteLoadError>()
        for (n in res.unmapped) errors.add(SpriteLoadError.NoMapping(n))
        if (res.entries.isEmpty()) return SpriteLoadResult(null, emptyList(), errors)

        val archives = ArrayList<LodArchive>()
        for (l in lods) {
            try {
                archives.add(LodArchive.open(l.bytes))
            } catch (e: Exception) {
                errors.add(SpriteLoadError.BadArchive(l.name, e.message ?: e.javaClass.simpleName))
            }
        }

        // One decode per distinct DEF name; a failed decode is remembered and reported per creature.
        val defs = LinkedHashMap<String, Decoded>()
        val frames = ArrayList<AtlasFrame>()
        val loaded = ArrayList<String>()
        for (entry in res.entries) {
            val def = defs.getOrPut(entry.def) { decode(entry.def, archives) }
            when (def) {
                is Decoded.Missing -> { errors.add(SpriteLoadError.MissingDef(entry.creature, entry.def)); continue }
                is Decoded.Bad -> { errors.add(SpriteLoadError.BadDef(entry.creature, entry.def, def.detail)); continue }
                is Decoded.Ok -> {
                    val mine = try {
                        creatureFrames(entry.creature, def.file, idleGroupOnly)
                    } catch (e: Exception) {
                        errors.add(SpriteLoadError.BadDef(entry.creature, entry.def, e.message ?: e.javaClass.simpleName))
                        continue
                    }
                    val idle = UiSpriteKey.idleKey(entry.creature)
                    if (mine.none { it.key == idle && it.width > 0 && it.height > 0 }) {
                        errors.add(SpriteLoadError.NoIdleFrame(entry.creature, entry.def))
                        continue
                    }
                    frames.addAll(mine)
                    loaded.add(entry.creature)
                }
            }
        }
        if (frames.isEmpty()) return SpriteLoadResult(null, emptyList(), errors)

        return when (val built = AtlasBuilder(maxPage = maxPage, budgetBytes = budgetBytes).addAll(frames).build()) {
            is BuildResult.Ok -> SpriteLoadResult(built.atlas, loaded, errors)
            is BuildResult.Failed -> {
                errors.add(SpriteLoadError.AtlasFailed(built.reason, built.message))
                SpriteLoadResult(null, emptyList(), errors)
            }
        }
    }

    private sealed class Decoded {
        object Missing : Decoded()
        data class Bad(val detail: String) : Decoded()
        class Ok(val file: DefFile) : Decoded()
    }

    private fun decode(def: String, archives: List<LodArchive>): Decoded {
        val arc = archives.firstOrNull { def in it } ?: return Decoded.Missing
        return try {
            Decoded.Ok(Def.parse(arc.read(def)))
        } catch (e: Exception) {
            Decoded.Bad(e.message ?: e.javaClass.simpleName)
        }
    }

    private fun creatureFrames(creature: String, file: DefFile, idleGroupOnly: Boolean): List<AtlasFrame> {
        val all = DefFrames.from(UiSpriteKey.prefix(creature), file)
        if (!idleGroupOnly) return all
        // Keys are `<prefix>/<group:3>/<index:4>`; the idle group is the block at position IDLE_GROUP.
        val groupPrefix = UiSpriteKey.idleKey(creature).substringBeforeLast('/') + "/"
        return all.filter { it.key.startsWith(groupPrefix) }
    }
}

/** Pixel format helpers for turning an atlas page into a platform bitmap. */
object PagePixels {
    /**
     * Bytes of a page in the order Android's `Bitmap.Config.ARGB_8888` keeps in memory: per pixel
     * R, G, B, A. [argb] is `Atlas` page data: packed ints that are already premultiplied
     * ([h3.presenter.Premultiply]). Feeding these bytes to `Bitmap.copyPixelsFromBuffer` copies
     * them unchanged, which is right because the bitmap is premultiplied too. `Bitmap.createBitmap(int[]...)`
     * or `setPixels` would treat the ints as straight colours and premultiply a second time.
     */
    fun toRgbaBytes(argb: IntArray): ByteArray {
        val out = ByteArray(argb.size * 4)
        for (i in argb.indices) {
            val p = argb[i]
            out[i * 4] = (p shr 16).toByte()
            out[i * 4 + 1] = (p shr 8).toByte()
            out[i * 4 + 2] = p.toByte()
            out[i * 4 + 3] = (p shr 24).toByte()
        }
        return out
    }
}
