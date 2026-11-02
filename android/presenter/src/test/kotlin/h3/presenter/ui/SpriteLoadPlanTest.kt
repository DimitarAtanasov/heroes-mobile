package h3.presenter.ui

import h3.presenter.Atlas
import h3.presenter.Premultiply
import h3.presenter.Reason
import h3.sim.Pcg32
import java.io.ByteArrayOutputStream
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

// ---- synthetic fixtures: a stored LOD archive and a raw (format 0) DEF, built here, no game data ----

private fun ByteArrayOutputStream.le32(v: Int) { for (i in 0 until 4) write((v shr (8 * i)) and 0xFF) }

private fun lod(vararg members: Pair<String, ByteArray>): ByteArray = lodWith(members.map { Triple(it.first, it.second, it.second.size) to 0 })

/** Members as ((name, payload, declared unpacked size) to packed size); packed 0 means stored. */
private fun lodWith(members: List<Pair<Triple<String, ByteArray, Int>, Int>>): ByteArray {
    val out = ByteArrayOutputStream()
    out.write(byteArrayOf('L'.code.toByte(), 'O'.code.toByte(), 'D'.code.toByte(), 0))
    out.le32(200); out.le32(members.size)
    out.write(ByteArray(80))
    var off = 92 + 32 * members.size
    for ((m, packed) in members) {
        val (n, data, size) = m
        out.write(n.toByteArray(Charsets.ISO_8859_1).copyOf(16))
        out.le32(off); out.le32(size); out.le32(0); out.le32(packed)
        off += data.size
    }
    for ((m, _) in members) out.write(m.second)
    return out.toByteArray()
}

/** One DEF frame: [pixels] are palette indices, w*h of them, in a fullW x fullH canvas at (x, y). */
private class F(val w: Int, val h: Int, val pixels: ByteArray, val x: Int = 0, val y: Int = 0, val fullW: Int = w, val fullH: Int = h)

private fun solid(w: Int, h: Int, idx: Int) = F(w, h, ByteArray(w * h) { idx.toByte() })

/** Palette: index i has colour (i, 100 + i, 200 - i) in 8-bit RGB. */
private fun def(blocks: List<Pair<Int, List<F>>>): ByteArray {
    val out = ByteArrayOutputStream()
    out.le32(0x42); out.le32(64); out.le32(64); out.le32(blocks.size)
    for (i in 0 until 256) { out.write(i); out.write((100 + i) and 0xFF); out.write((200 - i) and 0xFF) }
    var headerEnd = 16 + 768
    for ((_, fs) in blocks) headerEnd += 16 + 17 * fs.size
    var off = headerEnd
    val offsets = ArrayList<List<Int>>()
    for ((_, fs) in blocks) { offsets.add(fs.map { val o = off; off += 32 + it.w * it.h; o }) }
    for ((bi, b) in blocks.withIndex()) {
        out.le32(b.first); out.le32(b.second.size); out.write(ByteArray(8))
        for (k in b.second.indices) out.write("F${bi}_$k".toByteArray(Charsets.ISO_8859_1).copyOf(13))
        for (o in offsets[bi]) out.le32(o)
    }
    for ((_, fs) in blocks) for (f in fs) {
        out.le32(f.w * f.h); out.le32(0); out.le32(f.fullW); out.le32(f.fullH)
        out.le32(f.w); out.le32(f.h); out.le32(f.x); out.le32(f.y)
        out.write(f.pixels)
    }
    return out.toByteArray()
}

/** A DEF with the idle group at block position 2: frame 0 is a 3x2 block of colour index 9, frame 1 of 12. */
private fun pikeDef(): ByteArray = def(listOf(
    0 to listOf(solid(2, 2, 20)),
    1 to listOf(solid(2, 2, 21)),
    2 to listOf(F(3, 2, ByteArray(6) { 9 }, x = 1, y = 2, fullW = 8, fullH = 9), solid(3, 2, 12)),
    3 to listOf(solid(1, 1, 22)),
))

private fun idleOnlyDef(idx: Int): ByteArray = def(listOf(0 to listOf(solid(1, 1, 30)), 1 to listOf(solid(1, 1, 31)), 2 to listOf(solid(2, 2, idx))))

private fun zlib(raw: ByteArray): ByteArray {
    val d = java.util.zip.Deflater()
    d.setInput(raw); d.finish()
    val buf = ByteArray(raw.size + 64)
    val n = d.deflate(buf)
    d.end()
    return buf.copyOf(n)
}

private val PIKE = "Test Pikeman"
private val SLING = "Test Slinger"
private val GLIDE = "Test Glider"
private val BRUTE = "Test Brute"

private fun pageAt(a: Atlas, key: String, col: Int, row: Int): Int {
    val r = a.rects.getValue(key)
    val p = a.pages[r.page]
    return p.argb[(r.y + row) * p.width + r.x + col]
}

class SpriteLoadPlanTest {
    private val pikeLod = LodSource("H3sprite.lod", lod("CPKMAN.DEF" to pikeDef()))

    // ---- mapping table ----

    @Test
    fun defaultTableMapsOnlyThePlaceholdersItNamesAndNeverTheBrute() {
        assertEquals(listOf(PIKE, SLING, GLIDE), SpriteLoadPlan.DEFAULT_TABLE.keys.toList())
        assertEquals("CPKMAN.DEF", SpriteLoadPlan.defFor(PIKE))
        assertEquals("CLCBOW.DEF", SpriteLoadPlan.defFor(SLING))
        assertEquals("CGRIFF.DEF", SpriteLoadPlan.defFor(GLIDE))
        assertNull(SpriteLoadPlan.defFor(BRUTE))
        for (v in SpriteLoadPlan.DEFAULT_TABLE.values) assertTrue(v.endsWith(".DEF") && v == v.trim() && ' ' !in v, v)
    }

    @Test
    fun lookupIsExactAndAnEmptyMappingCountsAsNone() {
        assertNull(SpriteLoadPlan.defFor("test pikeman"))
        assertNull(SpriteLoadPlan.defFor("Pikeman"))
        assertNull(SpriteLoadPlan.defFor(""))
        assertNull(SpriteLoadPlan.defFor("x", mapOf("x" to "")))
        assertEquals("A.DEF", SpriteLoadPlan.defFor("x", mapOf("x" to "A.DEF")))
    }

    @Test
    fun resolveKeepsFirstAppearanceOrderDropsDuplicatesAndListsUnmapped() {
        val r = SpriteLoadPlan.resolve(listOf(GLIDE, BRUTE, PIKE, GLIDE, "Zed", BRUTE))
        assertEquals(listOf(PlanEntry(GLIDE, "CGRIFF.DEF"), PlanEntry(PIKE, "CPKMAN.DEF")), r.entries)
        assertEquals(listOf(BRUTE, "Zed"), r.unmapped)
        assertEquals(Resolution(emptyList(), emptyList()), SpriteLoadPlan.resolve(emptyList()))
    }

    // ---- happy path ----

    @Test
    fun loadBuildsAnAtlasWhoseIdleStillIsFoundByTheRosterKeys() {
        val res = SpriteLoadPlan.load(listOf(PIKE), listOf(pikeLod))
        assertEquals(emptyList(), res.errors)
        assertEquals(listOf(PIKE), res.loaded)
        val atlas = assertNotNull(res.atlas)
        assertTrue(res.hasSprite(PIKE))
        val r = assertNotNull(UiSpriteKey.idleRect(atlas, PIKE))
        assertEquals(3, r.w); assertEquals(2, r.h)
        assertEquals("creature/test_pikeman/002/0000", UiSpriteKey.idleKey(PIKE))
        // Frame metadata (cropped frame inside its canvas) reaches BoardArt through the atlas.
        val m = assertNotNull(atlas.meta[UiSpriteKey.idleKey(PIKE)])
        assertEquals(listOf(1, 2, 8, 9), listOf(m.offsetX, m.offsetY, m.fullWidth, m.fullHeight))
        // Colour index 9 is (9, 109, 191) opaque; premultiplying an opaque pixel changes nothing.
        assertEquals(Premultiply.pack(9, 109, 191, 255), pageAt(atlas, UiSpriteKey.idleKey(PIKE), 2, 1))
    }

    @Test
    fun onlyTheIdleGroupIsKeptUnlessAllFramesAreAsked() {
        val idle = assertNotNull(SpriteLoadPlan.load(listOf(PIKE), listOf(pikeLod)).atlas)
        assertEquals(listOf("creature/test_pikeman/002/0000", "creature/test_pikeman/002/0001"), idle.rects.keys.sorted())
        val all = assertNotNull(SpriteLoadPlan.load(listOf(PIKE), listOf(pikeLod), idleGroupOnly = false).atlas)
        assertEquals(5, all.rects.size)
        assertTrue(all.bytes() > idle.bytes())
    }

    @Test
    fun shadowAndOverlayPixelsFollowTheDefRules() {
        // Index 1 is shadow (black, alpha 64); index 5 is the player-colour overlay, left transparent.
        val d = def(listOf(0 to listOf(solid(1, 1, 9)), 1 to listOf(solid(1, 1, 9)), 2 to listOf(F(3, 1, byteArrayOf(0, 1, 5)))))
        val atlas = assertNotNull(SpriteLoadPlan.load(listOf(PIKE), listOf(LodSource("a", lod("CPKMAN.DEF" to d)))).atlas)
        val k = UiSpriteKey.idleKey(PIKE)
        assertEquals(0, pageAt(atlas, k, 0, 0))
        assertEquals(Premultiply.pack(0, 0, 0, 64), pageAt(atlas, k, 1, 0))
        assertEquals(0, pageAt(atlas, k, 2, 0))
    }

    @Test
    fun severalCreaturesShareOneAtlasAndOneDecodeOfASharedDef() {
        val table = mapOf(PIKE to "CPKMAN.DEF", SLING to "CPKMAN.DEF", GLIDE to "CGRIFF.DEF")
        val lods = listOf(LodSource("s", lod("CPKMAN.DEF" to pikeDef(), "CGRIFF.DEF" to idleOnlyDef(40))))
        val res = SpriteLoadPlan.load(listOf(PIKE, SLING, GLIDE, BRUTE), lods, table)
        assertEquals(listOf(PIKE, SLING, GLIDE), res.loaded)
        assertEquals(listOf<SpriteLoadError>(SpriteLoadError.NoMapping(BRUTE)), res.errors)
        val atlas = assertNotNull(res.atlas)
        for (n in listOf(PIKE, SLING, GLIDE)) assertNotNull(UiSpriteKey.idleRect(atlas, n), n)
        assertNull(UiSpriteKey.idleRect(atlas, BRUTE))
        assertEquals(Premultiply.pack(40, 140, 160, 255), pageAt(atlas, UiSpriteKey.idleKey(GLIDE), 1, 1))
    }

    @Test
    fun firstArchiveHoldingTheMemberWinsAndMemberNamesIgnoreCase() {
        val a = LodSource("H3sprite.lod", lod("cpkman.def" to idleOnlyDef(50)))
        val b = LodSource("H3ab_spr.lod", lod("CPKMAN.DEF" to idleOnlyDef(60), "CGRIFF.DEF" to idleOnlyDef(70)))
        val res = SpriteLoadPlan.load(listOf(PIKE, GLIDE), listOf(a, b))
        assertEquals(emptyList(), res.errors)
        val atlas = assertNotNull(res.atlas)
        assertEquals(Premultiply.pack(50, 150, 150, 255), pageAt(atlas, UiSpriteKey.idleKey(PIKE), 0, 0))
        assertEquals(Premultiply.pack(70, 170, 130, 255), pageAt(atlas, UiSpriteKey.idleKey(GLIDE), 0, 0))
    }

    @Test
    fun resultIsDeterministicAndIndependentOfInputBytesBeingReused() {
        val lods = listOf(LodSource("s", lod("CPKMAN.DEF" to pikeDef(), "CGRIFF.DEF" to idleOnlyDef(40))))
        val a = SpriteLoadPlan.load(listOf(GLIDE, PIKE), lods)
        val b = SpriteLoadPlan.load(listOf(GLIDE, PIKE), lods)
        val x = assertNotNull(a.atlas); val y = assertNotNull(b.atlas)
        assertEquals(x.rects, y.rects); assertEquals(x.meta, y.meta); assertEquals(a.loaded, b.loaded)
        assertEquals(x.pages.size, y.pages.size)
        for (i in x.pages.indices) assertContentEquals(x.pages[i].argb, y.pages[i].argb)
    }

    // ---- named errors, never a throw ----

    @Test
    fun noMappingAloneGivesNoAtlasAndNoSpriteSoTheTokenIsUsed() {
        val res = SpriteLoadPlan.load(listOf(BRUTE, "Zed"), listOf(pikeLod))
        assertNull(res.atlas)
        assertEquals(emptyList(), res.loaded)
        assertEquals(listOf<SpriteLoadError>(SpriteLoadError.NoMapping(BRUTE), SpriteLoadError.NoMapping("Zed")), res.errors)
        assertFalse(res.hasSprite(BRUTE))
        assertEquals("NO_MAPPING", res.errors[0].code)
        assertNull(UiSpriteKey.idleRect(res.atlas, BRUTE))
    }

    @Test
    fun emptyInputsAreQuiet() {
        val none = SpriteLoadPlan.load(emptyList(), emptyList())
        assertNull(none.atlas); assertEquals(emptyList(), none.errors)
        val noLods = SpriteLoadPlan.load(listOf(PIKE), emptyList())
        assertNull(noLods.atlas)
        assertEquals(listOf<SpriteLoadError>(SpriteLoadError.MissingDef(PIKE, "CPKMAN.DEF")), noLods.errors)
    }

    @Test
    fun missingDefIsReportedPerCreatureAndOthersStillLoad() {
        val res = SpriteLoadPlan.load(listOf(SLING, PIKE), listOf(pikeLod))
        assertEquals(listOf(PIKE), res.loaded)
        assertEquals(listOf<SpriteLoadError>(SpriteLoadError.MissingDef(SLING, "CLCBOW.DEF")), res.errors)
        assertNotNull(UiSpriteKey.idleRect(res.atlas, PIKE))
        assertNull(UiSpriteKey.idleRect(res.atlas, SLING))
    }

    @Test
    fun badArchiveIsNamedAndSkippedWhileAGoodOneStillServes() {
        val junk = LodSource("H3ab_spr.lod", ByteArray(40) { it.toByte() })
        val res = SpriteLoadPlan.load(listOf(PIKE), listOf(junk, pikeLod))
        assertEquals(listOf(PIKE), res.loaded)
        val e = res.errors.single()
        assertIs<SpriteLoadError.BadArchive>(e)
        assertEquals("H3ab_spr.lod", e.lod)
        assertTrue(e.detail.isNotEmpty())
        assertEquals("BAD_ARCHIVE", e.code)
    }

    @Test
    fun onlyBadArchivesGiveBadArchiveThenMissingDef() {
        val res = SpriteLoadPlan.load(listOf(PIKE), listOf(LodSource("x.lod", ByteArray(0))))
        assertNull(res.atlas)
        assertEquals(listOf("BAD_ARCHIVE", "MISSING_DEF"), res.errors.map { it.code })
    }

    @Test
    fun corruptDefIsBadDefForEveryCreatureUsingItAndTheOtherCreatureLoads() {
        val table = mapOf(PIKE to "BAD.DEF", SLING to "BAD.DEF", GLIDE to "CGRIFF.DEF")
        val lods = listOf(LodSource("s", lod("BAD.DEF" to ByteArray(30) { 7 }, "CGRIFF.DEF" to idleOnlyDef(40))))
        val res = SpriteLoadPlan.load(listOf(PIKE, SLING, GLIDE), lods, table)
        assertEquals(listOf(GLIDE), res.loaded)
        assertEquals(listOf("BAD_DEF", "BAD_DEF"), res.errors.map { it.code })
        assertEquals(listOf(PIKE, SLING), res.errors.map { (it as SpriteLoadError.BadDef).creature })
        assertNotNull(UiSpriteKey.idleRect(res.atlas, GLIDE))
    }

    @Test
    fun compressedMembersLoadLikeStoredOnes() {
        val raw = pikeDef()
        val z = zlib(raw)
        val lods = listOf(LodSource("s", lodWith(listOf(Triple("CPKMAN.DEF", z, raw.size) to z.size))))
        val res = SpriteLoadPlan.load(listOf(PIKE), lods)
        assertEquals(emptyList(), res.errors)
        val a = assertNotNull(res.atlas)
        val b = assertNotNull(SpriteLoadPlan.load(listOf(PIKE), listOf(pikeLod)).atlas)
        assertEquals(a.rects, b.rects)
        assertContentEquals(a.pages[0].argb, b.pages[0].argb)
    }

    @Test
    fun corruptCompressedMemberIsBadDefNotAThrow() {
        val garbage = ByteArray(12) { (it * 37 + 5).toByte() }
        val lods = listOf(LodSource("s", lodWith(listOf(Triple("CPKMAN.DEF", garbage, 500) to garbage.size))))
        val res = SpriteLoadPlan.load(listOf(PIKE), lods)
        assertNull(res.atlas)
        val e = assertIs<SpriteLoadError.BadDef>(res.errors.single())
        assertEquals(PIKE, e.creature); assertEquals("CPKMAN.DEF", e.def)
    }

    @Test
    fun defWithoutAnIdleStillIsNoIdleFrame() {
        val noGroup2 = def(listOf(0 to listOf(solid(2, 2, 9)), 1 to listOf(solid(2, 2, 9))))
        val emptyIdle = def(listOf(0 to listOf(solid(1, 1, 9)), 1 to listOf(solid(1, 1, 9)), 2 to listOf(F(0, 0, ByteArray(0)))))
        val lods = listOf(LodSource("s", lod("A.DEF" to noGroup2, "B.DEF" to emptyIdle)))
        val res = SpriteLoadPlan.load(listOf(PIKE, SLING), lods, mapOf(PIKE to "A.DEF", SLING to "B.DEF"))
        assertNull(res.atlas)
        assertEquals(listOf<SpriteLoadError>(SpriteLoadError.NoIdleFrame(PIKE, "A.DEF"), SpriteLoadError.NoIdleFrame(SLING, "B.DEF")), res.errors)
    }

    @Test
    fun atlasFailuresAreNamedAndLeaveNoAtlas() {
        val tooBig = SpriteLoadPlan.load(listOf(PIKE), listOf(pikeLod), maxPage = 2)
        assertNull(tooBig.atlas); assertEquals(emptyList(), tooBig.loaded)
        assertEquals(Reason.FRAME_TOO_LARGE, assertIs<SpriteLoadError.AtlasFailed>(tooBig.errors.single()).reason)

        val over = SpriteLoadPlan.load(listOf(PIKE), listOf(pikeLod), budgetBytes = 8)
        assertNull(over.atlas)
        assertEquals(Reason.OVER_BUDGET, assertIs<SpriteLoadError.AtlasFailed>(over.errors.single()).reason)

        // "Test Pikeman" and "test-pikeman" slug to the same prefix: duplicate frame keys.
        val clash = SpriteLoadPlan.load(listOf(PIKE, "test-pikeman"), listOf(pikeLod), mapOf(PIKE to "CPKMAN.DEF", "test-pikeman" to "CPKMAN.DEF"))
        assertNull(clash.atlas)
        assertEquals(Reason.DUPLICATE_KEY, assertIs<SpriteLoadError.AtlasFailed>(clash.errors.single()).reason)
        assertEquals("ATLAS_FAILED", clash.errors.single().code)
    }

    @Test
    fun errorOrderIsNoMappingThenArchivesThenCreaturesInOrder() {
        val res = SpriteLoadPlan.load(listOf(SLING, BRUTE, PIKE), listOf(LodSource("z", ByteArray(3)), LodSource("q", lod())))
        assertEquals(listOf("NO_MAPPING", "BAD_ARCHIVE", "MISSING_DEF", "MISSING_DEF"), res.errors.map { it.code })
        assertTrue(res.errors.all { it.describe().startsWith(it.code) })
    }

    @Test
    fun hostileBytesNeverThrow() {
        val rng = Pcg32(0x5917EUL, 5UL)
        val good = lod("CPKMAN.DEF" to pikeDef())
        repeat(300) { i ->
            // random archive bytes, and a valid archive with a few flipped bytes (header, directory or payload)
            val random = ByteArray(rng.randint(0, 400).toInt()) { rng.randint(0, 255).toInt().toByte() }
            val flipped = good.copyOf()
            repeat(rng.randint(1, 6).toInt()) { flipped[rng.randint(0, flipped.size - 1L).toInt()] = rng.randint(0, 255).toInt().toByte() }
            val truncated = good.copyOf(rng.randint(0, good.size.toLong()).toInt())
            for (b in listOf(random, flipped, truncated)) {
                val res = SpriteLoadPlan.load(listOf(PIKE, SLING), listOf(LodSource("f$i", b)))
                for (e in res.errors) assertTrue(e.code.isNotEmpty())
                if (res.atlas != null) assertTrue(res.loaded.isNotEmpty())
            }
        }
    }

    // ---- pixel format ----

    @Test
    fun pageBytesAreRgbaInMemoryOrderAndKeepPremultipliedValuesUntouched() {
        val half = Premultiply.pack(200, 100, 50, 128) // premultiplied: r=100 g=50 b=25 a=128
        assertEquals(0x80643219.toInt(), half)
        val bytes = PagePixels.toRgbaBytes(intArrayOf(half, 0, Premultiply.pack(1, 2, 3, 255), -1))
        assertContentEquals(
            byteArrayOf(100, 50, 25, 128.toByte(), 0, 0, 0, 0, 1, 2, 3, 255.toByte(), -1, -1, -1, -1),
            bytes,
        )
        assertEquals(0, PagePixels.toRgbaBytes(IntArray(0)).size)
    }

    @Test
    fun everyAtlasPageConvertsToFourBytesPerPixel() {
        val atlas = assertNotNull(SpriteLoadPlan.load(listOf(PIKE), listOf(pikeLod)).atlas)
        for (p in atlas.pages) {
            val b = PagePixels.toRgbaBytes(p.argb)
            assertEquals(p.width * p.height * 4, b.size)
            for (i in p.argb.indices) {
                val a = p.argb[i]
                assertEquals(listOf((a shr 16) and 0xFF, (a shr 8) and 0xFF, a and 0xFF, (a shr 24) and 0xFF),
                    (0 until 4).map { b[i * 4 + it].toInt() and 0xFF })
            }
        }
    }
}
