package h3.sim

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

private fun unhex(s: String): ByteArray = ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }

private fun hexOf(b: ByteArray): String = b.joinToString("") { "%02x".format(it.toInt() and 0xFF) }

private fun le32(v: Int): ByteArray = ByteArray(4) { ((v shr (8 * it)) and 0xFF).toByte() }

class PcxTest {
    private fun cases(): List<Any?> = loadVector("pcx.json")["cases"].list()

    @Test
    fun conformanceVectorsReplay() {
        val all = cases()
        assertTrue(all.size >= 40, "vector count ${all.size}")
        for (c in all) {
            val o = c.obj()
            val name = o["name"] as String
            val blob = unhex(o["hex"] as String)
            val exp = o["expect"].obj()
            if (exp["ok"] == false) {
                val e = assertFailsWith<PcxError>(name) { parsePcx(blob) }
                assertEquals(exp["error"] as String, "PcxError", name)
                assertTrue(e.message != null, name)
                continue
            }
            val img = parsePcx(blob)
            assertEquals(exp["width"].big().toInt(), img.width, name)
            assertEquals(exp["height"].big().toInt(), img.height, name)
            assertEquals(if (exp["mode"] == "indexed") PcxMode.INDEXED else PcxMode.BGR24, img.mode, name)
            assertEquals(exp["pixels"] as String, hexOf(img.pixels), "$name pixels")
            val pal = exp["palette"]
            if (pal == null) {
                assertNull(img.palette, name)
            } else {
                assertEquals(pal as String, hexOf(checkNotNull(img.palette)), "$name palette")
            }
            assertEquals(exp["rgb"] as String, hexOf(img.toRgb()), "$name rgb")
        }
    }

    @Test
    fun paletteIsTheLast768BytesOfTheFile() {
        val pal = ByteArray(768) { (it * 5).toByte() }
        val pixels = byteArrayOf(9, 8, 7, 6)
        val blob = le32(4) + le32(2) + le32(2) + pixels + ByteArray(40) { 0x11 } + pal
        val img = parsePcx(blob)
        assertContentEquals(pixels, img.pixels)
        assertContentEquals(pal, img.palette)
    }

    @Test
    fun bgrPixelsAreSwappedToRgb() {
        val img = parsePcx(le32(3) + le32(1) + le32(1) + byteArrayOf(1, 2, 3))
        assertEquals(PcxMode.BGR24, img.mode)
        assertNull(img.palette)
        assertContentEquals(byteArrayOf(3, 2, 1), img.toRgb())
    }

    @Test
    fun malformedInputsRaisePcxError() {
        assertFailsWith<PcxError> { parsePcx(ByteArray(0)) }
        assertFailsWith<PcxError> { parsePcx(le32(4) + le32(0) + le32(2) + ByteArray(4) + ByteArray(768)) }
        assertFailsWith<PcxError> { parsePcx(le32(4) + le32(8193) + le32(1) + ByteArray(4) + ByteArray(768)) }
        assertFailsWith<PcxError> { parsePcx(le32(4) + le32(1) + le32(8193) + ByteArray(4) + ByteArray(768)) }
        assertFailsWith<PcxError> { parsePcx(le32(5) + le32(2) + le32(2) + ByteArray(5) + ByteArray(768)) }
    }
}
