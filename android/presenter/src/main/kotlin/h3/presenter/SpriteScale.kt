package h3.presenter

/**
 * Integer upscaling of atlas frames (sprite-atlas.md, "Upscaling"): the DEF art drawn at 2x to 4x
 * for the board. Pure and deterministic: integers only, no platform APIs.
 *
 * Colour and alpha are bilinear. Colour is averaged premultiplied, so a transparent neighbour does
 * not darken an edge. The overlay mask is sampled nearest, so the player-colour edge stays crisp.
 * A scale of 1 returns the frame itself.
 */
object SpriteScale {
    const val MAX_SCALE = 4

    fun scale(frame: AtlasFrame, k: Int): AtlasFrame {
        require(k in 1..MAX_SCALE) { "scale $k outside 1..$MAX_SCALE" }
        if (k == 1) return frame
        val w = frame.width
        val h = frame.height
        val dw = w * k
        val dh = h * k
        val rgba = ByteArray(dw * dh * 4)
        val ov = frame.overlay?.let { ByteArray(dw * dh) }
        // Destination pixel centre maps to source position (2*d + 1 - k) / (2k) in source pixels.
        // Weights are integers over den per axis, so the blend has no rounding until the end.
        val den = 2 * k
        val tot = den.toLong() * den
        for (dy in 0 until dh) {
            val ty = 2 * dy + 1 - k
            val y0 = Math.floorDiv(ty, den)
            val fy = Math.floorMod(ty, den)
            val ya = (y0).coerceIn(0, h - 1)
            val yb = (y0 + 1).coerceIn(0, h - 1)
            for (dx in 0 until dw) {
                val tx = 2 * dx + 1 - k
                val x0 = Math.floorDiv(tx, den)
                val fx = Math.floorMod(tx, den)
                val xa = x0.coerceIn(0, w - 1)
                val xb = (x0 + 1).coerceIn(0, w - 1)
                var sumA = 0L
                var sumR = 0L
                var sumG = 0L
                var sumB = 0L
                for (s in 0 until 4) {
                    val sy = if (s < 2) ya else yb
                    val sx = if (s % 2 == 0) xa else xb
                    val wy = if (s < 2) den - fy else fy
                    val wx = if (s % 2 == 0) den - fx else fx
                    val wgt = (wx * wy).toLong()
                    if (wgt == 0L) continue
                    val i = (sy * w + sx) * 4
                    val a = (frame.rgba[i + 3].toInt() and 0xFF) * wgt
                    sumA += a
                    sumR += (frame.rgba[i].toInt() and 0xFF) * a
                    sumG += (frame.rgba[i + 1].toInt() and 0xFF) * a
                    sumB += (frame.rgba[i + 2].toInt() and 0xFF) * a
                }
                val o = (dy * dw + dx) * 4
                val alpha = (sumA + tot / 2) / tot
                rgba[o + 3] = alpha.toByte()
                if (sumA > 0) {
                    rgba[o] = ((sumR + sumA / 2) / sumA).toByte()
                    rgba[o + 1] = ((sumG + sumA / 2) / sumA).toByte()
                    rgba[o + 2] = ((sumB + sumA / 2) / sumA).toByte()
                }
                if (ov != null) {
                    val src = (dy / k) * w + dx / k
                    ov[dy * dw + dx] = if (frame.overlay!![src].toInt() != 0) 0xFF.toByte() else 0
                }
            }
        }
        return AtlasFrame(
            frame.key, dw, dh, rgba,
            frame.offsetX * k, frame.offsetY * k, frame.fullWidth * k, frame.fullHeight * k, ov,
        )
    }
}
