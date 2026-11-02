package h3.presenter.ui

import h3.presenter.AtlasBuilder
import h3.presenter.AtlasFrame
import h3.presenter.BuildResult
import h3.presenter.Fixture
import h3.sim.BattleCreature
import h3.sim.BattleStack
import h3.sim.BattleState
import h3.sim.HexCell
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class BoardArtTest {
    private fun creature(name: String, wide: Boolean = false) = BattleCreature(name, 5, 5, 1, 3, 10, 5, doubleWide = wide)

    private fun stack(id: Int, side: Int, name: String, count: Int, pos: Pair<Int, Int>, wide: Boolean = false) =
        BattleStack(id, side, id, creature(name, wide), count, 10, pos, 0, 1, false, 0, 0)

    /** 0 attacker Pikeman at (3,4); 1 defender Imp at (3,2); 2 defender Griffin (two-hex) at (10,2); 3 dead; 4 attacker at (1,4). */
    private val st: BattleState = Fixture.games[0].initial.copy(
        stacks = listOf(
            stack(0, 0, "Test Pikeman", 12, 3 to 4),
            stack(1, 1, "Test Imp", 10000, 3 to 2),
            stack(2, 1, "Griffin", 4, 10 to 2, wide = true),
            stack(3, 1, "Test Gog", 0, 5 to 5),
            stack(4, 0, "Test Archer", 3, 1 to 4),
        ),
        round = 1, started = true, active = 0, done = emptyList(), waited = emptyList(), winner = null,
    )
    private val roster = StackRoster.build(st, listOf(0, 1, 2, 4))
    private val fit = BoardFit.fit(880, 540)

    private fun frame(key: String, w: Int, h: Int, ox: Int = 0, oy: Int = 0, fw: Int = w, fh: Int = h) =
        AtlasFrame(key, w, h, ByteArray(w * h * 4) { 9 }, ox, oy, fw, fh)

    private fun centresOf(b: BoardStack): List<ArtPoint> =
        b.cells.map { ArtPoint(fit.cellCenterXDp(it.col, it.row, false), fit.cellCenterYDp(it.row)) }

    @Test
    fun boardStacksDropDeadOnesAndSortByRowThenColThenId() {
        val b = BoardArt.boardStacks(st, roster)
        assertEquals(listOf(1, 2, 4, 0), b.map { it.row.id })
        assertTrue(b.none { it.row.id == 3 })
        assertEquals(HexCell(10, 2), b[1].head)
    }

    @Test
    fun boardStacksCarryTheCoveredCellsHeadFirst() {
        val b = BoardArt.boardStacks(st, roster)
        val wide = b.first { it.row.id == 2 }
        assertEquals(2, wide.cells.size)
        assertEquals(wide.head, wide.cells[0])
        assertEquals(1, b.first { it.row.id == 0 }.cells.size)
    }

    @Test
    fun aStackWithoutARosterRowIsSkipped() {
        val partial = StackRoster.build(st.copy(stacks = st.stacks.take(1)), emptyList())
        assertEquals(listOf(0), BoardArt.boardStacks(st, partial).map { it.row.id })
    }

    @Test
    fun tokenFallbackWithoutAnAtlas() {
        val b = BoardArt.boardStacks(st, roster).first { it.row.id == 0 }
        val a = BoardArt.layout(b, centresOf(b), fit, null)
        assertNull(a.sprite)
        assertEquals("P", a.letter)
        assertEquals(fit.unitsToDp(BoardArt.TOKEN_RADIUS_UNITS), a.tokenRadius)
        assertEquals(1, a.tokenCentres.size)
        assertTrue(a.tokenRadius > 0)
        assertEquals(2 * a.tokenRadius, a.tokenLinkWidth)
        // the outline of a token encloses the disc
        val c = a.tokenCentres[0]
        assertEquals(ArtRect(c.x - a.tokenRadius, c.y - a.tokenRadius, c.x + a.tokenRadius, c.y + a.tokenRadius), a.outline)
    }

    @Test
    fun twoHexTokenOutlineCoversBothDiscs() {
        val b = BoardArt.boardStacks(st, roster).first { it.row.id == 2 }
        val a = BoardArt.layout(b, centresOf(b), fit, null)
        assertEquals(2, a.tokenCentres.size)
        for (c in a.tokenCentres) {
            assertTrue(a.outline.left <= c.x - a.tokenRadius && a.outline.right >= c.x + a.tokenRadius)
            assertTrue(a.outline.top <= c.y - a.tokenRadius && a.outline.bottom >= c.y + a.tokenRadius)
        }
        assertTrue(a.outline.width > 2 * a.tokenRadius)
    }

    @Test
    fun countPlateUsesTheBadgeAndSitsCentredUnderTheStack() {
        val bs = BoardArt.boardStacks(st, roster)
        val pike = bs.first { it.row.id == 0 }
        val p = BoardArt.layout(pike, centresOf(pike), fit, null).plate!!
        assertEquals("12", p.text)
        assertEquals(p.rect.left + Math.floorDiv(p.rect.width, 2), p.textX)
        assertEquals(centresOf(pike)[0].x, p.textX)
        assertTrue(p.rect.width > 0 && p.rect.height > 0)
        assertTrue(p.textBaselineY <= p.rect.bottom && p.textBaselineY > p.rect.top)
        val imp = bs.first { it.row.id == 1 }
        val big = BoardArt.layout(imp, centresOf(imp), fit, null).plate!!
        assertEquals("10k", big.text)
        assertTrue(big.rect.width > p.rect.width) // a longer badge gets a wider plate
    }

    @Test
    fun twoHexPlateIsCentredBetweenTheCells() {
        val b = BoardArt.boardStacks(st, roster).first { it.row.id == 2 }
        val cs = centresOf(b)
        val p = BoardArt.layout(b, cs, fit, null).plate!!
        assertEquals(Math.floorDiv(cs[0].x + cs[1].x, 2), p.textX)
    }

    @Test
    fun spriteIsDrawnFromTheAtlasRectAndMirroredForTheDefenderOnly() {
        val bs = BoardArt.boardStacks(st, roster)
        val pike = bs.first { it.row.id == 0 }
        val imp = bs.first { it.row.id == 1 }
        val atlas = (AtlasBuilder()
            .add(frame(pike.row.idleKey, 40, 60))
            .add(frame(imp.row.idleKey, 30, 50)).build() as BuildResult.Ok).atlas
        val a = BoardArt.layout(pike, centresOf(pike), fit, atlas)
        val s = assertNotNull(a.sprite)
        val r = pike.row.spriteRect(atlas)!!
        assertEquals(ArtRect(r.x, r.y, r.x + r.w, r.y + r.h), s.src)
        assertEquals(r.page, s.page)
        assertFalse(s.flipX)
        assertEquals(fit.unitsToDp(40), s.dst.width)
        assertEquals(fit.unitsToDp(60), s.dst.height)
        assertEquals(s.dst, a.outline)
        val d = BoardArt.layout(imp, centresOf(imp), fit, atlas)
        assertTrue(assertNotNull(d.sprite).flipX)
        assertEquals(centresOf(imp)[0].x, d.sprite!!.pivotX)
    }

    @Test
    fun spriteFeetStandOnTheBaseAndAreCentredWithoutMeta() {
        val pike = BoardArt.boardStacks(st, roster).first { it.row.id == 0 }
        val atlas = (AtlasBuilder().add(frame(pike.row.idleKey, 40, 60)).build() as BuildResult.Ok).atlas
        // frames built by AtlasBuilder carry meta (full canvas = frame size): bottom on the base line
        val c = centresOf(pike)[0]
        val s = BoardArt.layout(pike, listOf(c), fit, atlas).sprite!!
        assertEquals(c.y + fit.unitsToDp(BoardArt.BASE_DROP_UNITS), s.dst.bottom)
        assertEquals(c.x - Math.floorDiv(fit.unitsToDp(40), 2), s.dst.left)
    }

    @Test
    fun croppedFrameIsOffsetInsideItsFullCanvas() {
        val pike = BoardArt.boardStacks(st, roster).first { it.row.id == 0 }
        val atlas = (AtlasBuilder().add(frame(pike.row.idleKey, 20, 30, ox = 8, oy = 12, fw = 40, fh = 60)).build() as BuildResult.Ok).atlas
        val c = centresOf(pike)[0]
        val s = BoardArt.layout(pike, listOf(c), fit, atlas).sprite!!
        val fullLeft = c.x - Math.floorDiv(fit.unitsToDp(40), 2)
        val fullTop = c.y + fit.unitsToDp(BoardArt.BASE_DROP_UNITS) - fit.unitsToDp(60)
        assertEquals(fullLeft + fit.unitsToDp(8), s.dst.left)
        assertEquals(fullTop + fit.unitsToDp(12), s.dst.top)
        assertEquals(fit.unitsToDp(20), s.dst.width)
    }

    @Test
    fun missingOrEmptyFramesFallBackToTheToken() {
        val pike = BoardArt.boardStacks(st, roster).first { it.row.id == 0 }
        val other = (AtlasBuilder().add(frame("creature/other/002/0000", 4, 4)).build() as BuildResult.Ok).atlas
        assertNull(BoardArt.layout(pike, centresOf(pike), fit, other).sprite)
        val empty = (AtlasBuilder().add(frame(pike.row.idleKey, 0, 0)).build() as BuildResult.Ok).atlas
        assertNull(BoardArt.layout(pike, centresOf(pike), fit, empty).sprite)
    }

    @Test
    fun layoutIsDeterministicAndScalesWithTheFit() {
        val b = BoardArt.boardStacks(st, roster).first { it.row.id == 0 }
        assertEquals(BoardArt.layout(b, centresOf(b), fit, null), BoardArt.layout(b, centresOf(b), fit, null))
        val small = BoardFit.fit(220, 135)
        val big = BoardFit.fit(1760, 1080)
        val cs = listOf(ArtPoint(50, 50))
        assertTrue(BoardArt.layout(b, cs, small, null).tokenRadius < BoardArt.layout(b, cs, big, null).tokenRadius)
    }

    @Test
    fun layoutNeedsAtLeastOneCentre() {
        val b = BoardArt.boardStacks(st, roster)[0]
        assertFailsWith<IllegalArgumentException> { BoardArt.layout(b, emptyList(), fit, null) }
    }
}
