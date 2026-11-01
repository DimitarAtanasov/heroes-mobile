package h3.presenter

import h3.sim.Def
import h3.sim.Pcg32
import h3.sim.loadVector
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertTrue

private fun hex(s: String): ByteArray = ByteArray(s.length / 2) { s.substring(2 * it, 2 * it + 2).toInt(16).toByte() }

private fun solid(key: String, w: Int, h: Int, seed: Int, alpha: Int = 255, overlay: Boolean = false): AtlasFrame {
    val px = ByteArray(w * h * 4)
    for (i in 0 until w * h) {
        px[i * 4] = (seed * 31 + i * 7).toByte(); px[i * 4 + 1] = (seed * 17 + i * 13).toByte()
        px[i * 4 + 2] = (seed + i * 3).toByte(); px[i * 4 + 3] = (alpha - (i % 3)).coerceIn(0, 255).toByte()
    }
    val ov = if (overlay) ByteArray(w * h) { if (it % 2 == 0) 1 else 0 } else null
    return AtlasFrame(key, w, h, px, overlay = ov)
}

private fun ok(b: AtlasBuilder): Atlas = assertIs<BuildResult.Ok>(b.build()).atlas

private fun randomFrames(rng: Pcg32, maxPage: Int): List<AtlasFrame> {
    val n = rng.randint(1, 40).toInt()
    val hi = (maxPage - 1).coerceAtMost(40).toLong()
    return (0 until n).map { i ->
        val w = rng.randint(0, hi).toInt()
        val h = rng.randint(0, hi).toInt()
        val px = ByteArray(w * h * 4) { rng.randint(0, 255).toInt().toByte() }
        val ov = if (rng.chance(1, 2)) ByteArray(w * h) { if (rng.chance(1, 3)) 1 else 0 } else null
        AtlasFrame("f$i", w, h, px, rng.randint(-5, 5).toInt(), rng.randint(-5, 5).toInt(), w + 3, h + 3, ov)
    }
}

private fun shuffled(rng: Pcg32, l: List<AtlasFrame>): List<AtlasFrame> {
    val a = l.toMutableList()
    for (i in a.size - 1 downTo 1) { val j = rng.randint(0, i.toLong()).toInt(); val t = a[i]; a[i] = a[j]; a[j] = t }
    return a
}

private fun assertSameAtlas(a: Atlas, b: Atlas) {
    assertEquals(a.rects, b.rects)
    assertEquals(a.meta, b.meta)
    assertEquals(a.pages.size, b.pages.size)
    for (i in a.pages.indices) {
        assertEquals(a.pages[i].width, b.pages[i].width)
        assertEquals(a.pages[i].height, b.pages[i].height)
        assertContentEquals(a.pages[i].argb, b.pages[i].argb)
    }
}

/** Invariants: inside page, no overlap, gap >= padding, round-trip pixels exact. */
private fun checkInvariants(atlas: Atlas, frames: List<AtlasFrame>, maxPage: Int, pad: Int) {
    val real = atlas.rects.values.filter { it.page >= 0 }
    for (r in real) {
        val p = atlas.pages[r.page]
        assertTrue(r.x >= 0 && r.y >= 0 && r.x + r.w <= p.width && r.y + r.h <= p.height, "inside $r")
        assertTrue(p.width <= maxPage && p.height <= maxPage)
    }
    for (i in real.indices) for (j in i + 1 until real.size) {
        val a = real[i]; val b = real[j]
        if (a.page != b.page) continue
        val sepX = a.x + a.w + pad <= b.x || b.x + b.w + pad <= a.x
        val sepY = a.y + a.h + pad <= b.y || b.y + b.h + pad <= a.y
        assertTrue(sepX || sepY, "overlap/padding between $a and $b")
    }
    for (f in frames) {
        val r = atlas.rects.getValue(f.key)
        assertEquals(f.width, r.w); assertEquals(f.height, r.h)
        if (r.page < 0) continue
        val p = atlas.pages[r.page]
        for (y in 0 until r.h) for (x in 0 until r.w) {
            assertEquals(Premultiply.pixel(f.rgba, y * r.w + x), p.argb[(r.y + y) * p.width + r.x + x], "${f.key} $x,$y")
        }
    }
}

class SpriteAtlasTest {
    @Test
    fun premultiplyTableMatchesHandComputedReference() {
        // (alpha, channel, expected) computed by hand as round(c*a/255).
        val table = listOf(
            Triple(0, 255, 0), Triple(0, 0, 0),
            Triple(1, 255, 1), Triple(1, 128, 1), Triple(1, 127, 0),
            Triple(127, 255, 127), Triple(127, 128, 64), Triple(127, 2, 1), Triple(127, 1, 0),
            Triple(128, 255, 128), Triple(128, 127, 64), Triple(128, 1, 1),
            Triple(254, 255, 254), Triple(254, 128, 127), Triple(254, 2, 2), Triple(254, 1, 1),
            Triple(255, 255, 255), Triple(255, 1, 1), Triple(255, 0, 0),
        )
        for ((a, c, e) in table) assertEquals(e, Premultiply.channel(c, a), "a=$a c=$c")
        assertEquals(0xFF336699.toInt(), Premultiply.pack(0x33, 0x66, 0x99, 0xFF))
        // alpha 128, rgb (255,127,1) -> (128,64,1)
        assertEquals(0x80_80_40_01.toInt(), Premultiply.pack(255, 127, 1, 128))
        assertEquals(0, Premultiply.pack(255, 255, 255, 0))
    }

    @Test
    fun layoutIsExactForKnownInput() {
        val a = ok(AtlasBuilder(maxPage = 16).add(solid("a", 4, 4, 1)).add(solid("b", 6, 3, 2)).add(solid("c", 4, 4, 3)))
        // sorted: a(4x4), c(4x4), b(6x3) (height desc, width desc, key asc -> a, c, then b? b is shorter)
        assertEquals(Rect(0, 0, 0, 4, 4), a.rects["a"])
        assertEquals(Rect(0, 5, 0, 4, 4), a.rects["c"])
        assertEquals(Rect(0, 0, 5, 6, 3), a.rects["b"])   // 10 + 7 > 16: opens a second shelf
        assertEquals(10, a.pages[0].width)
        assertEquals(9, a.pages[0].height)
    }

    @Test
    fun noOverlapInsidePagePaddingAndRoundTrip() {
        val frames = (0 until 30).map { solid("k$it", 3 + it % 9, 2 + (it * 5) % 11, it, 200 - it) }
        val atlas = ok(AtlasBuilder(maxPage = 40).addAll(frames))
        assertTrue(atlas.pages.size > 1)
        checkInvariants(atlas, frames, 40, 1)
    }

    @Test
    fun paddingConfigurableAndPaddingPixelsStayEmpty() {
        val frames = listOf(solid("a", 5, 5, 1), solid("b", 5, 5, 2))
        val atlas = ok(AtlasBuilder(maxPage = 64, padding = 3).addAll(frames))
        checkInvariants(atlas, frames, 64, 3)
        val p = atlas.pages[0]
        val ra = atlas.rects.getValue("a"); val rb = atlas.rects.getValue("b")
        assertEquals(3, rb.x - (ra.x + ra.w))
        for (y in 0 until p.height) for (x in ra.x + ra.w until rb.x) assertEquals(0, p.argb[y * p.width + x])
    }

    @Test
    fun insertionOrderDoesNotChangeAtlas() {
        val rng = Pcg32(7UL, 1UL)
        val frames = randomFrames(rng, 64)
        val base = ok(AtlasBuilder(maxPage = 64).addAll(frames))
        repeat(5) { assertSameAtlas(base, ok(AtlasBuilder(maxPage = 64).addAll(shuffled(rng, frames)))) }
    }

    @Test
    fun sortKeyTieBreaksByWidthThenKey() {
        val atlas = ok(AtlasBuilder(maxPage = 64)
            .add(solid("z", 4, 4, 1)).add(solid("a", 4, 4, 2)).add(solid("w", 8, 4, 3)))
        assertEquals(0, atlas.rects.getValue("w").x)      // widest first
        assertEquals(9, atlas.rects.getValue("a").x)      // then key ascending
        assertEquals(14, atlas.rects.getValue("z").x)
    }

    @Test
    fun maskAlignedToRectsAndMatchesOverlay() {
        val frames = listOf(solid("a", 5, 4, 1, overlay = true), solid("b", 3, 3, 2), solid("c", 4, 6, 3, overlay = true))
        val atlas = ok(AtlasBuilder(maxPage = 32).addAll(frames))
        val masks = MaskPages.build(atlas, frames)
        assertEquals(atlas.pages.size, masks.size)
        for (i in masks.indices) { assertEquals(atlas.pages[i].width, masks[i].width); assertEquals(atlas.pages[i].height, masks[i].height) }
        var set = 0
        for (f in frames) {
            val r = atlas.rects.getValue(f.key); val m = masks[r.page]
            for (y in 0 until r.h) for (x in 0 until r.w) {
                val want = if (f.overlay != null && f.overlay!![y * r.w + x].toInt() != 0) 255 else 0
                assertEquals(want, m.alpha8[(r.y + y) * m.width + r.x + x].toInt() and 0xFF)
                if (want != 0) set++
            }
        }
        assertEquals(10 + 12, set)
        // everything outside rects is zero
        val inside = atlas.rects.values.sumOf { it.w * it.h }
        assertTrue(masks.sumOf { m -> m.alpha8.count { it.toInt() != 0 } } <= inside)
        assertEquals(set, masks.sumOf { m -> m.alpha8.count { it.toInt() != 0 } })
    }

    @Test
    fun oversizeFrameFailsCleanly() {
        val r = AtlasBuilder(maxPage = 16).add(solid("big", 16, 4, 1)).build()   // 16 + 1 padding > 16
        val f = assertIs<BuildResult.Failed>(r)
        assertEquals(Reason.FRAME_TOO_LARGE, f.reason)
        assertTrue("big" in f.message)
        // exactly fits: 15 + 1 padding
        ok(AtlasBuilder(maxPage = 16).add(solid("fit", 15, 15, 1)))
    }

    @Test
    fun duplicateKeyAndEmptyFrames() {
        val d = AtlasBuilder().add(solid("a", 2, 2, 1)).add(solid("a", 3, 3, 2)).build()
        assertEquals(Reason.DUPLICATE_KEY, assertIs<BuildResult.Failed>(d).reason)
        val e = ok(AtlasBuilder().add(AtlasFrame("empty", 0, 5, ByteArray(0))))
        assertEquals(Rect(-1, 0, 0, 0, 5), e.rects["empty"])
        assertEquals(0, e.pages.size)
        assertEquals(0L, e.bytes())
    }

    @Test
    fun budgetEstimateAndFailure() {
        val frames = listOf(solid("a", 10, 10, 1))
        val atlas = ok(AtlasBuilder(maxPage = 64).addAll(frames))
        assertEquals(11L * 11L * 4L, atlas.bytes())
        assertEquals(BudgetCheck.Within(484, 484), atlas.checkBudget(484))
        assertEquals(BudgetCheck.Exceeded(484, 483), atlas.checkBudget(483))
        val r = AtlasBuilder(maxPage = 64, budgetBytes = 483).addAll(frames).build()
        val f = assertIs<BuildResult.Failed>(r)
        assertEquals(Reason.OVER_BUDGET, f.reason)
        assertTrue("484" in f.message && "483" in f.message)
        assertEquals(96L * 1024 * 1024, AtlasBuilder.DEFAULT_BUDGET_BYTES)
    }

    @Test
    fun metaCarriesOffsets() {
        val f = AtlasFrame("m", 2, 2, ByteArray(16), 3, -4, 10, 12)
        assertEquals(FrameMeta(3, -4, 10, 12), ok(AtlasBuilder().add(f)).meta["m"])
    }

    @Test
    fun defVectorFramesRoundTripWithOverlayMask() {
        val cases = loadVector("def.json")["cases"].let { @Suppress("UNCHECKED_CAST") (it as List<Map<String, Any?>>) }
        var defs = 0; var withOverlay = 0
        for (c in cases) {
            if (!c.containsKey("ok")) continue
            val def = Def.parse(hex(c["hex"] as String))
            val frames = DefFrames.from(c["name"] as String, def)
            if (frames.isEmpty()) continue
            defs++
            val atlas = ok(AtlasBuilder(maxPage = 4096, budgetBytes = Long.MAX_VALUE).addAll(frames))
            checkInvariants(atlas, frames, 4096, 1)
            val masks = MaskPages.build(atlas, frames)
            for (f in frames) {
                val r = atlas.rects.getValue(f.key)
                if (r.page < 0) continue
                val fr = def.blocks.flatMap { it.frames }[frames.indexOf(f)]
                for (i in 0 until r.w * r.h) {
                    val isOv = (fr.pixels[i].toInt() and 0xFF) == Def.OVERLAY_INDEX
                    val m = masks[r.page].alpha8[(r.y + i / r.w) * masks[r.page].width + r.x + i % r.w].toInt() and 0xFF
                    assertEquals(if (isOv) 255 else 0, m)
                    if (isOv) { withOverlay++; assertEquals(0, atlas.pages[r.page].argb[(r.y + i / r.w) * atlas.pages[r.page].width + r.x + i % r.w]) }
                }
            }
        }
        assertTrue(defs > 50, "decoded $defs DEF fixtures")
        assertTrue(withOverlay > 0, "at least one fixture exercises palette index 5")
    }

    @Test
    fun defFrameKeysSortByBlockThenIndex() {
        assertTrue(DefFrames.key("c", 2, 10) < DefFrames.key("c", 10, 2))
        assertTrue(DefFrames.key("c", 1, 2) < DefFrames.key("c", 1, 10))
    }

    @Test
    fun propertyRandomFrameSets() {
        val rng = Pcg32(0xA71A5UL, 3UL)
        repeat(150) { iter ->
            val maxPage = rng.randint(48, 128).toInt()
            val pad = rng.randint(0, 3).toInt()
            val frames = randomFrames(rng, maxPage - 4)
            val atlas = ok(AtlasBuilder(maxPage = maxPage, padding = pad).addAll(frames))
            checkInvariants(atlas, frames, maxPage, pad)
            assertSameAtlas(atlas, ok(AtlasBuilder(maxPage = maxPage, padding = pad).addAll(shuffled(rng, frames))))
            val masks = MaskPages.build(atlas, frames)
            for (f in frames) {
                val ov = f.overlay ?: continue
                val r = atlas.rects.getValue(f.key); if (r.page < 0) continue
                for (i in 0 until r.w * r.h) {
                    val m = masks[r.page].alpha8[(r.y + i / r.w) * masks[r.page].width + r.x + i % r.w].toInt() and 0xFF
                    assertEquals(if (ov[i].toInt() != 0) 255 else 0, m, "iter $iter")
                }
            }
        }
    }

    @Test
    fun frameSizeValidation() {
        assertFailsWith<IllegalArgumentException> { AtlasFrame("x", 2, 2, ByteArray(15)) }
        assertFailsWith<IllegalArgumentException> { AtlasFrame("x", 2, 2, ByteArray(16), overlay = ByteArray(3)) }
    }
}
