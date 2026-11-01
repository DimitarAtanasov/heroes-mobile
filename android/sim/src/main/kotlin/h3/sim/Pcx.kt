package h3.sim

// Kotlin port of tools/h3re/h3re/pcx.py (layout in docs/specs/pcx.md).
// The PNG writer is not ported: it belongs to the presentation layer.

const val PCX_HEADER_SIZE = 12
const val PCX_PALETTE_SIZE = 768
const val PCX_MAX_DIM = 8192L

enum class PcxMode { INDEXED, BGR24 }

/** Malformed PCX bitmap (Python PcxError). */
class PcxError(message: String) : Exception(message)

/**
 * Parsed bitmap. [pixels] holds palette indices (INDEXED) or stored BGR triples (BGR24),
 * row-major. [palette] is 768 bytes of RGB for INDEXED and null for BGR24.
 */
class PcxImage(
    val width: Int,
    val height: Int,
    val mode: PcxMode,
    val pixels: ByteArray,
    val palette: ByteArray?,
) {
    /** Packed 8-bit RGB, width * height * 3 bytes, row-major. */
    fun toRgb(): ByteArray = when (mode) {
        PcxMode.INDEXED -> {
            val pal = checkNotNull(palette)
            val out = ByteArray(pixels.size * 3)
            for (i in pixels.indices) {
                val p = (pixels[i].toInt() and 0xFF) * 3
                out[i * 3] = pal[p]
                out[i * 3 + 1] = pal[p + 1]
                out[i * 3 + 2] = pal[p + 2]
            }
            out
        }
        PcxMode.BGR24 -> {
            // Stored order is BGR: swap the first and third byte of every triple.
            val out = ByteArray(pixels.size)
            var i = 0
            while (i < pixels.size) {
                out[i] = pixels[i + 2]
                out[i + 1] = pixels[i + 1]
                out[i + 2] = pixels[i]
                i += 3
            }
            out
        }
    }
}

/** Parses a HoMM3 PCX bitmap. Throws [PcxError] on malformed input. */
fun parsePcx(data: ByteArray): PcxImage {
    if (data.size < PCX_HEADER_SIZE) {
        throw PcxError("truncated header: need $PCX_HEADER_SIZE bytes, have ${data.size}")
    }
    val size = u32le(data, 0)
    val width = u32le(data, 4)
    val height = u32le(data, 8)
    if (width == 0L || height == 0L) throw PcxError("empty image dimensions ${width}x$height")
    if (width > PCX_MAX_DIM || height > PCX_MAX_DIM) {
        throw PcxError("dimensions ${width}x$height exceed cap $PCX_MAX_DIM")
    }
    val n = width * height
    val w = width.toInt()
    val h = height.toInt()
    val body = PCX_HEADER_SIZE

    if (size == n) {
        val need = body.toLong() + n + PCX_PALETTE_SIZE
        if (data.size < need) {
            throw PcxError("truncated indexed data: need $need bytes, have ${data.size}")
        }
        // The palette is always the LAST 768 bytes of the file, as the engine reads it.
        // Bytes between the pixels and the palette are not used.
        val pixels = data.copyOfRange(body, body + n.toInt())
        val palette = data.copyOfRange(data.size - PCX_PALETTE_SIZE, data.size)
        return PcxImage(w, h, PcxMode.INDEXED, pixels, palette)
    }
    if (size == 3 * n) {
        val need = body.toLong() + size
        if (data.size < need) {
            throw PcxError("truncated 24-bit data: need $need bytes, have ${data.size}")
        }
        return PcxImage(w, h, PcxMode.BGR24, data.copyOfRange(body, body + size.toInt()), null)
    }
    throw PcxError("data size $size matches neither $n (indexed) nor ${3 * n} (24-bit) for ${width}x$height")
}

/** Little-endian uint32 at [pos], as Long. */
private fun u32le(data: ByteArray, pos: Int): Long {
    var v = 0L
    for (i in 3 downTo 0) v = (v shl 8) or (data[pos + i].toLong() and 0xFFL)
    return v
}
