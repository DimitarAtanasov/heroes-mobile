package h3.presenter

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

private fun frame(w: Int, h: Int, vararg px: Int, overlay: IntArray? = null): AtlasFrame {
    // px is r,g,b,a per pixel, straight alpha.
    val rgba = ByteArray(w * h * 4) { px[it].toByte() }
    val ov = overlay?.let { o -> ByteArray(o.size) { o[it].toByte() } }
    return AtlasFrame("k", w, h, rgba, overlay = ov)
}

private fun px(f: AtlasFrame, x: Int, y: Int): List<Int> {
    val i = (y * f.width + x) * 4
    return (0 until 4).map { f.rgba[i + it].toInt() and 0xFF }
}

class SpriteScaleTest {
    @Test
    fun scaleOneReturnsTheSameFrame() {
        val f = frame(1, 1, 1, 2, 3, 255)
        assertSame(f, SpriteScale.scale(f, 1))
    }

    @Test
    fun uniformOpaqueFrameStaysUniformAtEveryScale() {
        val f = frame(2, 2, *IntArray(16) { if (it % 4 == 3) 255 else 40 + it % 4 })
        for (k in 2..SpriteScale.MAX_SCALE) {
            val s = SpriteScale.scale(f, k)
            assertEquals(2 * k, s.width); assertEquals(2 * k, s.height)
            for (y in 0 until s.height) for (x in 0 until s.width) {
                assertEquals(listOf(40, 41, 42, 255), px(s, x, y), "k=$k at $x,$y")
            }
        }
    }

    @Test
    fun transparentNeighbourDoesNotDarkenTheEdgeColour() {
        // Left pixel opaque red, right pixel fully transparent black.
        val f = frame(2, 1, 200, 0, 0, 255, 0, 0, 0, 0)
        val s = SpriteScale.scale(f, 2)
        // Destination x=0 is entirely the opaque pixel.
        assertEquals(listOf(200, 0, 0, 255), px(s, 0, 0))
        // Destination x=1 mixes 3/4 opaque with 1/4 transparent: colour stays 200, alpha 255*3/4.
        assertEquals(200, px(s, 1, 0)[0])
        assertEquals(191, px(s, 1, 0)[3])
    }

    @Test
    fun overlayIsSampledNearestSoItsEdgeStaysCrisp() {
        val f = frame(2, 1, 9, 9, 9, 255, 9, 9, 9, 255, overlay = intArrayOf(1, 0))
        val s = SpriteScale.scale(f, 2)
        val ov = assertNotNullOverlay(s)
        // Two rows of 4 destination pixels: the first two columns come from source pixel 0.
        assertEquals(listOf(1, 1, 0, 0), ov.take(4).map { it.toInt() and 0xFF }.map { if (it != 0) 1 else 0 })
        assertEquals(listOf(1, 1, 0, 0), ov.drop(4).map { it.toInt() and 0xFF }.map { if (it != 0) 1 else 0 })
    }

    @Test
    fun offsetsAndFullCanvasScaleWithTheImage() {
        val f = AtlasFrame("k", 1, 2, ByteArray(8), offsetX = 1, offsetY = 2, fullWidth = 8, fullHeight = 9)
        val s = SpriteScale.scale(f, 3)
        assertEquals(3, s.width); assertEquals(6, s.height)
        assertEquals(listOf(3, 6, 24, 27), listOf(s.offsetX, s.offsetY, s.fullWidth, s.fullHeight))
        assertEquals("k", s.key)
    }

    @Test
    fun zeroAreaFramesStayEmpty() {
        val f = AtlasFrame("k", 0, 3, ByteArray(0))
        val s = SpriteScale.scale(f, 2)
        assertEquals(0, s.width); assertEquals(6, s.height); assertEquals(0, s.rgba.size)
    }

    @Test
    fun scaleOutsideTheRangeIsRefused() {
        val f = frame(1, 1, 0, 0, 0, 255)
        assertFailsWith<IllegalArgumentException> { SpriteScale.scale(f, 0) }
        assertFailsWith<IllegalArgumentException> { SpriteScale.scale(f, SpriteScale.MAX_SCALE + 1) }
    }

    private fun assertNotNullOverlay(s: AtlasFrame): ByteArray = s.overlay ?: error("overlay dropped")
}
