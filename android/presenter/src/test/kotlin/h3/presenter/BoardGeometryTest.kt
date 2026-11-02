package h3.presenter

import h3.sim.Hex
import h3.sim.HexCell
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class BoardGeometryTest {
    private val sizes = listOf(800 to 600, 1080 to 1920, 1920 to 1080, 360 to 640, 640 to 360, 100 to 100, 17 to 11, 5 to 3, 3000 to 200)
    private val parities = listOf("even", "odd")
    private val all = (0 until Hex.HEIGHT).flatMap { r -> (0 until Hex.WIDTH).map { c -> HexCell(c, r) } }

    private fun forEachGeo(f: (BoardGeometry, String) -> Unit) {
        for (p in parities) for ((w, h) in sizes) f(BoardGeometry(w, h, p), "$p ${w}x$h")
    }

    @Test
    fun grid_has187Cells() = assertEquals(187, all.size)

    @Test
    fun everyCellCentreHitsItselfAndRoundTrips() = forEachGeo { g, name ->
        for (c in all) {
            val p = g.center(c)
            assertEquals(c, g.hitTest(p.x, p.y), "$name $c")
        }
    }

    @Test
    fun boardFitsInsideViewportWithMargin() = forEachGeo { g, name ->
        for (c in all) for (k in g.corners(c)) {
            assertTrue(k.x >= -1e-6 && k.x <= g.viewW + 1e-6 && k.y >= -1e-6 && k.y <= g.viewH + 1e-6, "$name $c $k")
        }
    }

    @Test
    fun shiftedRowsMatchHexAdjacencyForBothParities() {
        for (p in parities) {
            val g = BoardGeometry(1600, 1200, p)
            for (c in all) {
                val ctr = g.center(c)
                val adj = Hex.neighbours(c, p).toSet()
                // neighbours are exactly the cells whose centre is one pitch away (not further)
                val near = all.filter { o ->
                    val q = g.center(o)
                    o != c && Math.hypot(q.x - ctr.x, q.y - ctr.y) < 50.0 * g.scale
                }.toSet()
                assertEquals(adj, near, "$p $c")
            }
        }
    }

    @Test
    fun parityChangesWhichRowIsShifted() {
        val e = BoardGeometry(800, 600, "even")
        val o = BoardGeometry(800, 600, "odd")
        assertEquals(e.center(HexCell(3, 0)).x, o.center(HexCell(3, 1)).x, 1e-9)
        assertEquals(e.center(HexCell(3, 2)).x, o.center(HexCell(3, 1)).x, 1e-9)
        assertTrue(e.center(HexCell(3, 0)).x > e.center(HexCell(3, 1)).x)
        assertTrue(o.center(HexCell(3, 1)).x > o.center(HexCell(3, 0)).x)
    }

    @Test
    fun pointsInsideAPolygonResolveToItsCellAndCornersAreOnTheBorder() = forEachGeo { g, name ->
        for (c in all) {
            val ctr = g.center(c)
            val cs = g.corners(c)
            assertEquals(6, cs.size)
            for (k in cs) {
                // 70% of the way from the centre to a corner is strictly inside this hex
                val x = ctr.x + (k.x - ctr.x) * 0.7
                val y = ctr.y + (k.y - ctr.y) * 0.7
                assertEquals(c, g.hitTest(x, y), "$name $c")
            }
        }
    }

    @Test
    fun pointsNearSharedEdgesResolveToTheNearestCentreDeterministically() = forEachGeo { g, name ->
        val eps = 1e-3 * g.scale
        for (a in all) for (b in Hex.neighbours(a, g.let { if (it.shiftOdd) "odd" else "even" })) {
            val pa = g.center(a)
            val pb = g.center(b)
            val mx = (pa.x + pb.x) / 2
            val my = (pa.y + pb.y) / 2
            val ux = pb.x - pa.x
            val uy = pb.y - pa.y
            val n = Math.hypot(ux, uy)
            // just on a's side and just on b's side of the midpoint of the centres
            val sa = g.hitTest(mx - ux / n * eps, my - uy / n * eps)
            val sb = g.hitTest(mx + ux / n * eps, my + uy / n * eps)
            assertEquals(a, sa, "$name $a|$b")
            assertEquals(b, sb, "$name $a|$b")
            // the midpoint itself is a tie or a border: deterministic and one of the two
            val m1 = g.hitTest(mx, my)
            assertEquals(m1, g.hitTest(mx, my))
            assertTrue(m1 == a || m1 == b, "$name $a|$b")
        }
    }

    @Test
    fun randomPointsPickTheNearestCentreOfCoveringHexes() {
        // LCG, test-only
        var s = 12345L
        fun next(): Double { s = (s * 6364136223846793005L + 1442695040888963407L); return ((s ushr 11) % 1_000_000L) / 1_000_000.0 }
        forEachGeo { g, name ->
            repeat(400) {
                val x = next() * g.viewW
                val y = next() * g.viewH
                val h = g.hitTest(x, y)
                if (h != null) {
                    val c = g.center(h)
                    val d = Math.hypot(x - c.x, y - c.y)
                    // never farther than the hex circumradius, and no other centre is much closer
                    assertTrue(d <= 28.0 * g.scale + 1e-6, "$name $h")
                }
                assertEquals(h, g.hitTest(x, y), name)
            }
        }
    }

    @Test
    fun pointsOutsideTheBoardReturnNull() = forEachGeo { g, name ->
        assertNull(g.hitTest(-5.0, -5.0), name)
        assertNull(g.hitTest(g.viewW + 5, g.viewH + 5), name)
        assertNull(g.hitTest(Double.NaN, 1.0), name)
        assertNull(g.hitTest(Double.POSITIVE_INFINITY, 1.0), name)
        // far above/below/left/right of the board's own box
        val c = g.center(HexCell(0, 0))
        assertNull(g.hitTest(c.x - 60 * g.scale, c.y), name)
        val l = g.center(HexCell(16, 10))
        assertNull(g.hitTest(l.x + 60 * g.scale, l.y), name)
        assertNull(g.hitTest(c.x, c.y - 40 * g.scale), name)
        assertNull(g.hitTest(l.x, l.y + 40 * g.scale), name)
        // the jagged strip: the corner of the bounding box not covered by any hex
        val bx = if (g.shiftOdd) BoardGeometry.X0 + BoardGeometry.BOARD_W - 2 else BoardGeometry.X0 + 2
        assertNull(g.hitTest(bx * g.scale + g.offX, (BoardGeometry.Y0 + 2) * g.scale + g.offY), name)
    }

    @Test
    fun twoHexUnitResolvesFromEitherCellToTheHead() = forEachGeo { g, name ->
        val att = UnitFootprint(1, HexCell(4, 3), Hex.ATTACKER, true) // cells (4,3),(3,3)
        val def = UnitFootprint(2, HexCell(10, 5), Hex.DEFENDER, true) // cells (10,5),(11,5)
        val one = UnitFootprint(3, HexCell(7, 7), Hex.ATTACKER, false)
        val dead = UnitFootprint(4, HexCell(7, 1), Hex.ATTACKER, false, alive = false)
        val us = listOf(att, def, one, dead)
        fun hit(c: HexCell): UnitHit? = g.center(c).let { g.hitTestUnit(it.x, it.y, us) }
        assertEquals(UnitHit(1, HexCell(4, 3)), hit(HexCell(4, 3)), name)
        assertEquals(UnitHit(1, HexCell(4, 3)), hit(HexCell(3, 3)), name)
        assertEquals(UnitHit(2, HexCell(10, 5)), hit(HexCell(10, 5)), name)
        assertEquals(UnitHit(2, HexCell(10, 5)), hit(HexCell(11, 5)), name)
        assertEquals(UnitHit(3, HexCell(7, 7)), hit(HexCell(7, 7)), name)
        assertNull(hit(HexCell(7, 1)), name)
        assertNull(hit(HexCell(5, 3)), name)
        assertNull(g.hitTestUnit(-10.0, -10.0, us), name)
    }

    @Test
    fun zoomAndPanMoveCentresButHitTestStillInverts() {
        val g = BoardGeometry(800.0, 600.0, "even", margin = 8.0, zoom = 2.0, panX = -50.0, panY = 30.0)
        for (c in all) {
            val p = g.center(c)
            if (p.x in 0.0..800.0 && p.y in 0.0..600.0) assertEquals(c, g.hitTest(p.x, p.y), "$c")
        }
    }

    @Test
    fun rejectsDegenerateViewport() {
        for ((w, h) in listOf(0.0 to 10.0, 10.0 to 0.0, -1.0 to 5.0)) {
            val r = runCatching { BoardGeometry(w, h) }
            assertTrue(r.isFailure)
        }
    }
}
