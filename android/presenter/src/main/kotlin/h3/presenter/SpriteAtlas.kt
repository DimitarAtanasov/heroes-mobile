package h3.presenter

import h3.sim.Def
import h3.sim.DefFile

/**
 * Pure-JVM sprite atlas builder (docs/specs/sprite-atlas.md, android-app.md 4.3 and 4.5).
 * Integer-only: rectangles, premultiplication and byte estimates use Int/Long arithmetic.
 */

/** One source image: straight (non-premultiplied) RGBA, row-major, 4 bytes per pixel. */
class AtlasFrame(
    val key: String,
    val width: Int,
    val height: Int,
    val rgba: ByteArray,
    /** Offset of the cropped image inside its full canvas; carried through, not used for packing. */
    val offsetX: Int = 0,
    val offsetY: Int = 0,
    val fullWidth: Int = width,
    val fullHeight: Int = height,
    /** Optional player-colour overlay, width*height bytes, nonzero = overlay pixel. */
    val overlay: ByteArray? = null,
) {
    init {
        require(width >= 0 && height >= 0) { "negative size for $key" }
        require(rgba.size == width * height * 4) { "rgba size mismatch for $key" }
        require(overlay == null || overlay.size == width * height) { "overlay size mismatch for $key" }
    }
}

data class Rect(val page: Int, val x: Int, val y: Int, val w: Int, val h: Int)

data class FrameMeta(val offsetX: Int, val offsetY: Int, val fullWidth: Int, val fullHeight: Int)

class Page(val width: Int, val height: Int, val argb: IntArray)

class MaskPage(val width: Int, val height: Int, val alpha8: ByteArray) {
    fun bytes(): Long = alpha8.size.toLong()
}

class Atlas(
    val pages: List<Page>,
    /** Frames of zero area get page = -1. */
    val rects: Map<String, Rect>,
    val meta: Map<String, FrameMeta> = emptyMap(),
) {
    /** Memory estimate: 4 bytes per ARGB pixel of every page. */
    fun bytes(): Long = pages.sumOf { it.width.toLong() * it.height.toLong() * 4L }

    fun checkBudget(limitBytes: Long): BudgetCheck {
        val b = bytes()
        return if (b <= limitBytes) BudgetCheck.Within(b, limitBytes) else BudgetCheck.Exceeded(b, limitBytes)
    }
}

sealed class BudgetCheck {
    data class Within(val bytes: Long, val limit: Long) : BudgetCheck()
    data class Exceeded(val bytes: Long, val limit: Long) : BudgetCheck()
}

sealed class BuildResult {
    data class Ok(val atlas: Atlas) : BuildResult()
    data class Failed(val reason: Reason, val message: String) : BuildResult()
}

enum class Reason { DUPLICATE_KEY, FRAME_TOO_LARGE, OVER_BUDGET }

object Premultiply {
    /** Round-to-nearest c*a/255 as (c*a + 127) / 255; exact since c*a/255 never has a .5 fraction. */
    fun channel(c: Int, a: Int): Int = (c * a + 127) / 255

    fun pack(r: Int, g: Int, b: Int, a: Int): Int =
        (a shl 24) or (channel(r, a) shl 16) or (channel(g, a) shl 8) or channel(b, a)

    fun pixel(rgba: ByteArray, pixelIndex: Int): Int {
        val o = pixelIndex * 4
        return pack(rgba[o].toInt() and 0xFF, rgba[o + 1].toInt() and 0xFF,
            rgba[o + 2].toInt() and 0xFF, rgba[o + 3].toInt() and 0xFF)
    }
}

class AtlasBuilder(
    val maxPage: Int = DEFAULT_MAX_PAGE,
    val padding: Int = DEFAULT_PADDING,
    val budgetBytes: Long = DEFAULT_BUDGET_BYTES,
) {
    private val frames = ArrayList<AtlasFrame>()

    init {
        require(maxPage > 0 && padding >= 0) { "bad atlas config" }
    }

    fun add(frame: AtlasFrame): AtlasBuilder { frames.add(frame); return this }

    fun addAll(fs: Iterable<AtlasFrame>): AtlasBuilder { frames.addAll(fs); return this }

    private class Shelf(val y: Int, val h: Int, var usedX: Int)
    private class PageState { val shelves = ArrayList<Shelf>(); var nextY = 0; var maxX = 0 }

    fun build(): BuildResult {
        val seen = HashSet<String>()
        for (f in frames) if (!seen.add(f.key)) return BuildResult.Failed(Reason.DUPLICATE_KEY, "duplicate frame key ${f.key}")
        // Sort key: height desc, width desc, key asc (String.compareTo, UTF-16 code units).
        val sorted = frames.sortedWith(compareByDescending<AtlasFrame> { it.height }
            .thenByDescending { it.width }.thenBy { it.key })
        val states = ArrayList<PageState>()
        val rects = LinkedHashMap<String, Rect>()
        for (f in sorted) {
            if (f.width == 0 || f.height == 0) { rects[f.key] = Rect(-1, 0, 0, f.width, f.height); continue }
            val cw = f.width + padding
            val ch = f.height + padding
            if (cw > maxPage || ch > maxPage) {
                return BuildResult.Failed(Reason.FRAME_TOO_LARGE,
                    "frame ${f.key} ${f.width}x${f.height} (+$padding padding) exceeds page ${maxPage}x$maxPage")
            }
            rects[f.key] = place(states, f, cw, ch)
        }
        val pages = states.map { st ->
            Page(st.maxX, st.nextY, IntArray(st.maxX * st.nextY))
        }
        val byKey = frames.associateBy { it.key }
        for ((k, r) in rects) {
            if (r.page < 0) continue
            val f = byKey.getValue(k)
            val pg = pages[r.page]
            for (row in 0 until r.h) for (col in 0 until r.w) {
                pg.argb[(r.y + row) * pg.width + r.x + col] = Premultiply.pixel(f.rgba, row * r.w + col)
            }
        }
        val meta = LinkedHashMap<String, FrameMeta>()
        for (f in sorted) meta[f.key] = FrameMeta(f.offsetX, f.offsetY, f.fullWidth, f.fullHeight)
        val atlas = Atlas(pages, rects, meta)
        return when (val c = atlas.checkBudget(budgetBytes)) {
            is BudgetCheck.Exceeded -> BuildResult.Failed(Reason.OVER_BUDGET,
                "atlas needs ${c.bytes} bytes, budget is ${c.limit}")
            is BudgetCheck.Within -> BuildResult.Ok(atlas)
        }
    }

    private fun place(states: ArrayList<PageState>, f: AtlasFrame, cw: Int, ch: Int): Rect {
        for ((pi, st) in states.withIndex()) {
            for (sh in st.shelves) {
                if (ch <= sh.h && sh.usedX + cw <= maxPage) return take(st, sh, pi, f, cw)
            }
            if (st.nextY + ch <= maxPage) {
                val sh = Shelf(st.nextY, ch, 0)
                st.shelves.add(sh); st.nextY += ch
                return take(st, sh, pi, f, cw)
            }
        }
        val st = PageState()
        states.add(st)
        val sh = Shelf(0, ch, 0)
        st.shelves.add(sh); st.nextY = ch
        return take(st, sh, states.size - 1, f, cw)
    }

    private fun take(st: PageState, sh: Shelf, page: Int, f: AtlasFrame, cw: Int): Rect {
        val r = Rect(page, sh.usedX, sh.y, f.width, f.height)
        sh.usedX += cw
        if (sh.usedX > st.maxX) st.maxX = sh.usedX
        return r
    }

    companion object {
        const val DEFAULT_MAX_PAGE = 2048
        const val DEFAULT_PADDING = 1
        /** android-app.md 4.3: decoded sprite bitmaps capped at 96 MB. */
        const val DEFAULT_BUDGET_BYTES = 96L * 1024 * 1024
    }
}

object MaskPages {
    /** One 8-bit page per atlas page, same size; 255 where a frame's overlay is set, else 0. */
    fun build(atlas: Atlas, frames: Iterable<AtlasFrame>): List<MaskPage> {
        val masks = atlas.pages.map { MaskPage(it.width, it.height, ByteArray(it.width * it.height)) }
        for (f in frames) {
            val r = atlas.rects[f.key] ?: continue
            val ov = f.overlay ?: continue
            if (r.page < 0) continue
            val m = masks[r.page]
            for (row in 0 until r.h) for (col in 0 until r.w) {
                if (ov[row * r.w + col].toInt() != 0) m.alpha8[(r.y + row) * m.width + r.x + col] = 0xFF.toByte()
            }
        }
        return masks
    }
}

object DefFrames {
    /** Zero-padded so lexicographic key order equals (block, index) order. */
    fun key(prefix: String, block: Int, index: Int): String =
        "$prefix/${block.toString().padStart(3, '0')}/${index.toString().padStart(4, '0')}"

    /**
     * Frames of a parsed DEF. The colour image comes from [DefFile.toRgba]; palette index
     * [Def.OVERLAY_INDEX] pixels are cleared to transparent in it and recorded in the overlay mask.
     */
    fun from(prefix: String, def: DefFile): List<AtlasFrame> {
        val out = ArrayList<AtlasFrame>()
        for ((bi, block) in def.blocks.withIndex()) for ((fi, fr) in block.frames.withIndex()) {
            val rgba = def.toRgba(fr)
            val ov = ByteArray(fr.width * fr.height)
            for (i in ov.indices) if ((fr.pixels[i].toInt() and 0xFF) == Def.OVERLAY_INDEX) {
                ov[i] = 0xFF.toByte()
                for (c in 0 until 4) rgba[i * 4 + c] = 0
            }
            out.add(AtlasFrame(key(prefix, bi, fi), fr.width, fr.height, rgba,
                fr.x, fr.y, fr.fullWidth, fr.fullHeight, ov))
        }
        return out
    }
}
