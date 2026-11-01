package h3.sim

/**
 * Clean-room HoMM3 .DEF sprite container decoder: a port of tools/h3re/h3re/defimg.py
 * (the Python reference; docs/specs/def.md, docs/specs/conformance-def.md). Integer-only,
 * no Android APIs. Every read is bounds-checked and failures throw [DefException].
 */
class DefException(message: String) : Exception(message)

class DefFrame(
    val name: String,
    val offset: Long,
    val size: Long,
    val fmt: Int,
    val fullWidth: Int,
    val fullHeight: Int,
    val width: Int,
    val height: Int,
    val x: Int,
    val y: Int,
    /** width*height palette indices (0..255, as unsigned bytes), row-major. */
    val pixels: ByteArray,
)

class DefBlock(val blockId: Long, val frames: List<DefFrame>)

class DefFile(
    val type: Long,
    val width: Long,
    val height: Long,
    /** 256 RGB triples, 768 bytes. */
    val palette: ByteArray,
    val blocks: List<DefBlock>,
) {
    /** RGBA of the frame image (width x height), see [Def.toRgba]. */
    fun toRgba(frame: DefFrame, shadowAlpha: Boolean = true): ByteArray =
        Def.toRgba(frame.pixels, palette, shadowAlpha)

    /** RGBA of the full-size canvas (fullWidth x fullHeight) with the frame placed on it. */
    fun toRgbaCanvas(frame: DefFrame, shadowAlpha: Boolean = true): ByteArray =
        Def.toRgba(Def.frameToCanvas(frame), palette, shadowAlpha)
}

object Def {
    const val MAX_BLOCKS = 256L
    const val MAX_ENTRIES = 4096L
    const val MAX_DIM = 8192L
    const val MAX_TOTAL_PIXELS: Long = 64L * 1024 * 1024
    const val COLOR_TOLERANCE = 8
    const val OVERLAY_INDEX = 5

    /** Reference colours of the reserved palette indices 0-7. */
    val SPECIAL_COLORS: Array<IntArray> = arrayOf(
        intArrayOf(0, 255, 255), intArrayOf(255, 150, 255), intArrayOf(255, 100, 255),
        intArrayOf(255, 50, 255), intArrayOf(255, 0, 255), intArrayOf(255, 255, 0),
        intArrayOf(180, 0, 255), intArrayOf(0, 255, 0),
    )

    /** Target alpha per special index; -1 keeps the opaque palette colour. */
    val SPECIAL_ALPHA: IntArray = intArrayOf(0, 64, 64, 128, 128, -1, 128, 64)

    private class Reader(val data: ByteArray, val base: Long = 0L, val limit: Long = data.size.toLong()) {
        fun check(off: Long, n: Long, what: String) {
            if (off < 0 || n < 0 || off + n > limit) {
                throw DefException("truncated data reading $what: need $n bytes at offset $off, size $limit")
            }
        }

        fun u8(off: Long, what: String): Int {
            check(off, 1, what)
            return data[(base + off).toInt()].toInt() and 0xFF
        }

        fun u16(off: Long, what: String): Int {
            check(off, 2, what)
            val p = (base + off).toInt()
            return (data[p].toInt() and 0xFF) or ((data[p + 1].toInt() and 0xFF) shl 8)
        }

        fun u32(off: Long, what: String): Long {
            check(off, 4, what)
            val p = (base + off).toInt()
            return (data[p].toLong() and 0xFF) or ((data[p + 1].toLong() and 0xFF) shl 8) or
                ((data[p + 2].toLong() and 0xFF) shl 16) or ((data[p + 3].toLong() and 0xFF) shl 24)
        }

        fun i32(off: Long, what: String): Int = u32(off, what).toInt()

        /** A sub-window [off, off+n) of this reader (re-based to 0). */
        fun window(off: Long, n: Long, what: String): Reader {
            check(off, n, what)
            return Reader(data, base + off, n)
        }
    }

    /** Output sink for decoded indices. */
    private class Out(n: Int) {
        val buf = ByteArray(n)
        var len = 0
    }

    private fun decodeRuns(r: Reader, start: Long, count: Int, out: Out, what: String): Long {
        var pos = start
        var got = 0
        while (got < count) {
            val b = r.u8(pos, what)
            pos++
            val code = b shr 5
            val n = (b and 0x1F) + 1
            if (got + n > count) throw DefException("$what: run overruns line ($got+$n > $count)")
            if (code == 7) {
                r.check(pos, n.toLong(), what)
                System.arraycopy(r.data, (r.base + pos).toInt(), out.buf, out.len, n)
                pos += n
            } else {
                java.util.Arrays.fill(out.buf, out.len, out.len + n, code.toByte())
            }
            out.len += n
            got += n
        }
        return pos
    }

    private fun decodeFrame(r0: Reader, off: Long, name: String, budget: LongArray): DefFrame {
        val size = r0.u32(off, "frame size")
        val fmt = r0.u32(off + 4, "frame format")
        val fw = r0.u32(off + 8, "frame full width")
        val fh = r0.u32(off + 12, "frame full height")
        var w = r0.u32(off + 16, "frame width")
        var h = r0.u32(off + 20, "frame height")
        var x = r0.i32(off + 24, "frame x")
        var y = r0.i32(off + 28, "frame y")
        if (fmt > 3) throw DefException("frame '$name': unknown compression format $fmt")
        for (v in longArrayOf(fw, fh, w, h)) {
            if (v > MAX_DIM) throw DefException("frame '$name': dimension $v too large")
        }
        val legacy = fmt == 1L && w > fw && h > fh
        var dstart = off + 32
        if (legacy) {
            w = fw
            h = fh
            x = 0
            y = 0
            dstart = off + 16
        }
        r0.check(off + 32, size, "frame '$name' data (declared size)")
        if (fmt == 0L && size != w * h) {
            throw DefException("frame '$name': raw size $size != width*height ${w * h}")
        }
        val npix = w * h
        if (npix > budget[0]) {
            throw DefException("frame '$name': decoded pixel budget exceeded ($npix > ${budget[0]} remaining)")
        }
        budget[0] -= npix
        val r = r0.window(dstart, size + (off + 32 - dstart), "frame data")
        val wi = w.toInt()
        val hi = h.toInt()
        val out = Out(wi * hi)
        if (wi == 0 || hi == 0) {
            // nothing to decode
        } else when (fmt.toInt()) {
            0 -> {
                r.check(0, npix, "raw frame pixels")
                System.arraycopy(r.data, r.base.toInt(), out.buf, 0, wi * hi)
                out.len = wi * hi
            }
            1 -> for (row in 0 until hi) {
                var pos = r.u32(4L * row, "line offset")
                var got = 0
                while (got < wi) {
                    val code = r.u8(pos, "rle code")
                    val n = r.u8(pos + 1, "rle length") + 1
                    pos += 2
                    if (got + n > wi) throw DefException("frame '$name': run overruns line $row")
                    if (code == 0xFF) {
                        r.check(pos, n.toLong(), "rle raw run")
                        System.arraycopy(r.data, (r.base + pos).toInt(), out.buf, out.len, n)
                        pos += n
                    } else {
                        java.util.Arrays.fill(out.buf, out.len, out.len + n, code.toByte())
                    }
                    out.len += n
                    got += n
                }
            }
            2 -> {
                var pos = r.u16(0, "line offset").toLong()
                for (row in 0 until hi) pos = decodeRuns(r, pos, wi, out, "frame '$name' line $row")
            }
            else -> {
                val stride = 2L * (wi / 32)
                for (row in 0 until hi) {
                    val lo = r.u16(stride * row, "line offset").toLong()
                    decodeRuns(r, lo, wi, out, "frame '$name' line $row")
                }
            }
        }
        return DefFrame(name, off, size, fmt.toInt(), fw.toInt(), fh.toInt(), wi, hi, x, y, out.buf)
    }

    /**
     * Parse a .DEF file. Frames sharing an offset are decoded once; the pixels decoded across
     * distinct frames may not exceed [maxPixels]. Malformed input throws [DefException].
     */
    fun parse(data: ByteArray, maxPixels: Long = MAX_TOTAL_PIXELS): DefFile {
        val r = Reader(data)
        val dtype = r.u32(0, "type")
        val width = r.u32(4, "width")
        val height = r.u32(8, "height")
        val nblocks = r.u32(12, "block count")
        if (nblocks > MAX_BLOCKS) throw DefException("implausible block count $nblocks")
        r.check(16, 768, "palette")
        val palette = data.copyOfRange(16, 16 + 768)
        var pos = 16L + 768
        val blocks = ArrayList<DefBlock>()
        val budget = longArrayOf(maxPixels)
        val cache = HashMap<Long, DefFrame>()
        for (b in 0 until nblocks.toInt()) {
            val bid = r.u32(pos, "block id")
            val n = r.u32(pos + 4, "block entry count")
            if (n > MAX_ENTRIES) throw DefException("implausible entry count $n in block $bid")
            pos += 16
            val names = ArrayList<String>()
            for (i in 0 until n.toInt()) {
                r.check(pos + 13L * i, 13, "frame name")
                val p = (pos + 13L * i).toInt()
                var e = 0
                while (e < 13 && data[p + e].toInt() != 0) e++
                names.add(String(data, p, e, Charsets.ISO_8859_1))
            }
            pos += 13L * n
            val offs = LongArray(n.toInt()) { r.u32(pos + 4L * it, "frame offset") }
            pos += 4L * n
            val frames = ArrayList<DefFrame>()
            for (i in offs.indices) {
                val fr = cache.getOrPut(offs[i]) { decodeFrame(r, offs[i], names[i], budget) }
                frames.add(DefFrame(names[i], fr.offset, fr.size, fr.fmt, fr.fullWidth, fr.fullHeight,
                    fr.width, fr.height, fr.x, fr.y, fr.pixels))
            }
            blocks.add(DefBlock(bid, frames))
        }
        return DefFile(dtype, width, height, palette, blocks)
    }

    /**
     * Place the frame on its fullWidth x fullHeight canvas; uncovered pixels get [transparent],
     * parts outside the canvas are clipped.
     */
    fun frameToCanvas(frame: DefFrame, transparent: Int = 0): ByteArray {
        val fw = frame.fullWidth
        val fh = frame.fullHeight
        val canvas = ByteArray(fw * fh)
        if (transparent != 0) java.util.Arrays.fill(canvas, transparent.toByte())
        for (row in 0 until frame.height) {
            val cy = frame.y.toLong() + row
            if (cy < 0 || cy >= fh) continue
            val x0 = maxOf(0L, frame.x.toLong())
            val x1 = minOf(fw.toLong(), frame.x.toLong() + frame.width)
            if (x0 >= x1) continue
            val src = row * frame.width + (x0 - frame.x).toInt()
            System.arraycopy(frame.pixels, src, canvas, (cy * fw + x0).toInt(), (x1 - x0).toInt())
        }
        return canvas
    }

    fun frameIsEmpty(frame: DefFrame): Boolean =
        frame.width == 0 || frame.height == 0 || frame.fullWidth == 0 || frame.fullHeight == 0

    private fun matches(palette: ByteArray, idx: Int, ref: IntArray): Boolean {
        for (c in 0 until 3) {
            val d = (palette[idx * 3 + c].toInt() and 0xFF) - ref[c]
            if (d > COLOR_TOLERANCE || -d > COLOR_TOLERANCE) return false
        }
        return true
    }

    /**
     * Indices to RGBA. Index 0 is transparent; with [shadowAlpha] indices 1-4, 6, 7 become black
     * with [SPECIAL_ALPHA] (2 and 3 only if the palette colour is within [COLOR_TOLERANCE]
     * per channel of [SPECIAL_COLORS]); index 5 and indices >= 8 keep their opaque palette colour.
     */
    fun toRgba(pixels: ByteArray, palette: ByteArray, shadowAlpha: Boolean = true): ByteArray {
        val out = ByteArray(pixels.size * 4)
        for (i in pixels.indices) {
            val p = pixels[i].toInt() and 0xFF
            val o = i * 4
            if (p == 0) continue
            var a = if (shadowAlpha && p < 8) SPECIAL_ALPHA[p] else -1
            if (a >= 0 && (p == 2 || p == 3) && !matches(palette, p, SPECIAL_COLORS[p])) a = -1
            if (a < 0) {
                out[o] = palette[p * 3]
                out[o + 1] = palette[p * 3 + 1]
                out[o + 2] = palette[p * 3 + 2]
                out[o + 3] = 0xFF.toByte()
            } else {
                out[o + 3] = a.toByte()
            }
        }
        return out
    }
}
