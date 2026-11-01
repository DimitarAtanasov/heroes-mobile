package h3.sim

import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

private val DEF_DOC by lazy { loadVector("def.json") }

private fun hex(s: String): ByteArray = ByteArray(s.length / 2) { s.substring(2 * it, 2 * it + 2).toInt(16).toByte() }
private fun ByteArray.hexStr(): String = joinToString("") { "%02x".format(it.toInt() and 0xFF) }
private fun sha(b: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(b).hexStr()
private fun Map<String, Any?>.int(k: String): Int = this[k].big().toInt()
private fun Map<String, Any?>.long(k: String): Long = this[k].big().toLong()

class DefTest {
    private val cases = DEF_DOC["cases"].list().map { it.obj() }

    private fun parse(c: Map<String, Any?>): DefFile {
        val data = hex(c["hex"] as String)
        return if (c.containsKey("max_pixels")) Def.parse(data, c.long("max_pixels")) else Def.parse(data)
    }

    @Test
    fun constants() {
        val k = DEF_DOC["constants"].obj()
        assertEquals(k.long("max_blocks"), Def.MAX_BLOCKS)
        assertEquals(k.long("max_entries"), Def.MAX_ENTRIES)
        assertEquals(k.long("max_dim"), Def.MAX_DIM)
        assertEquals(k.long("max_total_pixels"), Def.MAX_TOTAL_PIXELS)
        assertEquals(k.int("color_tolerance"), Def.COLOR_TOLERANCE)
        assertEquals(k.int("overlay_index"), Def.OVERLAY_INDEX)
        assertEquals(k["special_alpha"].list().map { it.big().toInt() }, Def.SPECIAL_ALPHA.toList())
        assertEquals(k["special_colors"].list().map { c -> c.list().map { it.big().toInt() } },
            Def.SPECIAL_COLORS.map { it.toList() })
    }

    @Test
    fun casesMatchPython() {
        assertTrue(cases.size > 200)
        var ok = 0
        var err = 0
        for (c in cases) {
            val name = c["name"] as String
            if (c.containsKey("error")) {
                err++
                assertFailsWith<DefException>(name) { parse(c) }
                continue
            }
            ok++
            val exp = c["ok"].obj()
            val d = parse(c)
            assertEquals(exp.long("type"), d.type, name)
            assertEquals(exp.long("width"), d.width, name)
            assertEquals(exp.long("height"), d.height, name)
            assertContentEquals(hex(c["hex"] as String).copyOfRange(16, 16 + 768), d.palette, name)
            val eb = exp["blocks"].list().map { it.obj() }
            assertEquals(eb.size, d.blocks.size, name)
            for ((bi, b) in eb.withIndex()) {
                assertEquals(b.long("id"), d.blocks[bi].blockId, name)
                val ef = b["frames"].list().map { it.obj() }
                assertEquals(ef.size, d.blocks[bi].frames.size, name)
                for ((fi, e) in ef.withIndex()) checkFrame("$name b$bi f$fi", d, d.blocks[bi].frames[fi], e)
            }
        }
        assertTrue(ok > 100 && err > 40, "ok=$ok err=$err")
    }

    private fun checkFrame(tag: String, d: DefFile, f: DefFrame, e: Map<String, Any?>) {
        assertEquals(e["name_hex"], f.name.toByteArray(Charsets.ISO_8859_1).hexStr(), tag)
        assertEquals(e.long("offset"), f.offset, tag)
        assertEquals(e.long("size"), f.size, tag)
        assertEquals(e.int("fmt"), f.fmt, tag)
        assertEquals(e.int("full_width"), f.fullWidth, tag)
        assertEquals(e.int("full_height"), f.fullHeight, tag)
        assertEquals(e.int("width"), f.width, tag)
        assertEquals(e.int("height"), f.height, tag)
        assertEquals(e.int("x"), f.x, tag)
        assertEquals(e.int("y"), f.y, tag)
        assertEquals(f.width * f.height, f.pixels.size, tag)
        assertEquals(e["pixels_sha256"], sha(f.pixels), tag)
        e["pixels_hex"]?.let { assertEquals(it, f.pixels.hexStr(), tag) }
        val canvas = Def.frameToCanvas(f)
        assertEquals(e["canvas_sha256"], sha(canvas), tag)
        e["canvas_hex"]?.let { assertEquals(it, canvas.hexStr(), tag) }
        assertEquals(e["rgba_sha256"], sha(d.toRgba(f, true)), tag)
        assertEquals(e["rgba_noshadow_sha256"], sha(d.toRgba(f, false)), tag)
        assertEquals(e["canvas_rgba_sha256"], sha(d.toRgbaCanvas(f, true)), tag)
        assertEquals(e["canvas_rgba_noshadow_sha256"], sha(d.toRgbaCanvas(f, false)), tag)
        e["rgba_hex"]?.let { assertEquals(it, d.toRgba(f, true).hexStr(), tag) }
        e["canvas_rgba_hex"]?.let { assertEquals(it, d.toRgbaCanvas(f, true).hexStr(), tag) }
    }

    @Test
    fun truncationsEveryCutPoint() {
        val base = hex(DEF_DOC["truncation_base_hex"] as String)
        val t = DEF_DOC["truncations"].list().map { it.list() }
        assertEquals(base.size + 1, t.size)
        var oks = 0
        for (row in t) {
            val cut = row[0].big().toInt()
            val data = base.copyOfRange(0, cut)
            if (row[1] == "error") {
                assertFailsWith<DefException>("cut $cut") { Def.parse(data) }
            } else {
                oks++
                assertEquals(row[2].big().toInt(), Def.parse(data).blocks.sumOf { it.frames.size }, "cut $cut")
            }
        }
        assertTrue(oks >= 1)
    }

    @Test
    fun sharedFramesAndBudgetAreByName() {
        val c = cases.first { it["name"] == "shared_offsets_multi_block" }
        val d = parse(c)
        val a0 = d.blocks[0].frames[0]
        val a1 = d.blocks[0].frames[1]
        assertTrue(a0.pixels === a1.pixels)
        assertEquals(listOf("A0", "A1"), listOf(a0.name, a1.name))
        assertEquals(3, d.blocks.size)
        assertEquals(0, d.blocks[2].frames.size)
    }

    @Test
    fun specialAlphaTable() {
        val pal = ByteArray(768)
        for (i in 0 until 256) { pal[i * 3] = 10; pal[i * 3 + 1] = 20; pal[i * 3 + 2] = 30 }
        for (i in 0 until 8) for (c in 0 until 3) pal[i * 3 + c] = Def.SPECIAL_COLORS[i][c].toByte()
        val px = ByteArray(10) { it.toByte() }
        val rgba = Def.toRgba(px, pal, true)
        assertEquals(listOf(0, 64, 64, 128, 128, 255, 128, 64, 255, 255), (0 until 10).map { rgba[4 * it + 3].toInt() and 0xFF })
        // index 3 off by 9 on one channel: stays opaque; by 8: shadow
        pal[9] = (255 - 9).toByte()
        assertEquals(255, Def.toRgba(byteArrayOf(3), pal)[3].toInt() and 0xFF)
        pal[9] = (255 - 8).toByte()
        assertEquals(128, Def.toRgba(byteArrayOf(3), pal)[3].toInt() and 0xFF)
        assertEquals(255, Def.toRgba(byteArrayOf(3), pal, false)[3].toInt() and 0xFF)
    }
}
