package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

private val HEX_DOC by lazy { loadVector("hex.json") }

private fun Any?.cell(): HexCell = list().let { HexCell(it[0].big().intValueExact(), it[1].big().intValueExact()) }
private fun Any?.cells(): List<HexCell> = list().map { it.cell() }
private fun Map<String, Any?>.int(k: String): Int = this[k].big().intValueExact()
private fun Map<String, Any?>.bool(k: String): Boolean = this[k] as Boolean

class HexTest {
    private val allCells = (0 until Hex.HEIGHT).flatMap { r -> (0 until Hex.WIDTH).map { c -> HexCell(c, r) } }

    @Test
    fun gridSize() {
        assertEquals(Hex.WIDTH, HEX_DOC["width"].big().intValueExact())
        assertEquals(Hex.HEIGHT, HEX_DOC["height"].big().intValueExact())
    }

    @Test
    fun neighboursBothParities() {
        val cases = HEX_DOC["neighbours"].list()
        assertEquals(2 * 187, cases.size)
        for (c in cases) {
            val o = c.obj()
            val h = o["hex"].cell()
            assertEquals(o["out"].cells(), Hex.neighbours(h, o["row_offset"] as String), "${o["row_offset"]} $h")
        }
    }

    @Test
    fun axialConversions() {
        for (c in HEX_DOC["axial"].list()) {
            val o = c.obj()
            val off = o["row_offset"] as String
            val h = o["hex"].cell()
            assertEquals(Pair(o.int("q"), o.int("r")), Hex.toAxial(h, off), "$off $h")
            assertEquals(h, Hex.fromAxial(o.int("q"), o.int("r"), off))
        }
        val fa = HEX_DOC["from_axial"].list()
        assertTrue(fa.size > 1000)
        for (c in fa) {
            val o = c.obj()
            val off = o["row_offset"] as String
            assertEquals(o["out"].cell(), Hex.fromAxial(o.int("q"), o.int("r"), off), "$off ${o["q"]} ${o["r"]}")
        }
    }

    @Test
    fun inGrid() {
        for (c in HEX_DOC["in_grid"].list()) {
            val o = c.obj()
            assertEquals(o.bool("out"), Hex.inGrid(o["hex"].cell()), "${o["hex"]}")
        }
    }

    @Test
    fun distanceAllPairsBothParities() {
        val dist = HEX_DOC["distance"].obj()
        for (off in listOf("even", "odd")) {
            val m = dist[off].list()
            assertEquals(187 * 187, m.size)
            var i = 0
            for (a in allCells) for (b in allCells) {
                assertEquals(m[i].big().intValueExact(), Hex.distance(a, b, off), "$off $a $b")
                i++
            }
        }
    }

    @Test
    fun footprints() {
        val cases = HEX_DOC["cells"].list()
        assertTrue(cases.size >= 100)
        for (c in cases) {
            val o = c.obj()
            val head = o["head"].cell()
            val side = o.int("side")
            val dw = o.bool("double_wide")
            assertEquals(o["cells"].cells(), Hex.cellsAt(head, side, dw), "$o")
            val tail = Hex.tail(head, side, dw)
            if (!dw) assertNull(tail)
            for (e in listOf(false, true)) {
                val expected = o["fits_empty"].obj()[if (e) "True" else "False"] as Boolean
                val got = Hex.cellsAt(head, side, dw).all { Hex.playable(it, e) }
                assertEquals(expected, got, "$o edge=$e")
                assertEquals(expected, Hex.fits(head, side, dw, e, emptySet(), emptySet()), "$o edge=$e")
            }
        }
    }

    @Test
    fun adjacency() {
        val cases = HEX_DOC["adjacent"].list()
        assertEquals(400, cases.size)
        var trues = 0
        for (c in cases) {
            val o = c.obj()
            val got = Hex.adjacentCells(o["a"].cells(), o["b"].cells(), o["row_offset"] as String)
            assertEquals(o.bool("out"), got, "$o")
            if (got) trues++
        }
        assertTrue(trues > 50 && trues < 400)
    }

    @Test
    fun reachAndPathsMatchPython() {
        val cases = HEX_DOC["reach"].list()
        assertTrue(cases.size >= 500)
        var flyers = 0
        var twoHex = 0
        var deadSeen = 0
        for ((idx, c) in cases.withIndex()) {
            val o = c.obj()
            val side = o.int("side")
            val dw = o.bool("double_wide")
            val flyer = o.bool("flyer")
            if (flyer) flyers++
            if (dw) twoHex++
            val occ = HashSet<HexCell>()
            for (u in o["others"].list()) {
                val uo = u.obj()
                if (!uo.bool("alive")) { deadSeen++; continue }
                occ.addAll(Hex.cellsAt(uo["head"].cell(), uo.int("side"), uo.bool("double_wide")))
            }
            val reach = Hex.reach(
                o["pos"].cell(), side, dw, flyer, o.int("speed"), o["row_offset"] as String,
                o.bool("edge_columns_walkable"), o["obstacles"].cells().toSet(), occ,
            )
            val wantKeys = o["reachable"].cells()
            assertEquals(wantKeys, reach.keys.sorted(), "case $idx")
            val wantPaths = o["paths"].list().map { it.cells() }
            assertEquals(wantPaths, wantKeys.map { reach.getValue(it) }, "case $idx paths")
            assertEquals(wantKeys, Hex.reachable(
                o["pos"].cell(), side, dw, flyer, o.int("speed"), o["row_offset"] as String,
                o.bool("edge_columns_walkable"), o["obstacles"].cells().toSet(), occ,
            ), "case $idx reachable")
        }
        assertTrue(flyers > 50 && twoHex > 50 && deadSeen > 50)
    }

    @Test
    fun deadStacksDoNotBlock() {
        val pos = HexCell(5, 5)
        val blocker = Hex.livingOccupancy(listOf(Triple(HexCell(6, 5), 1, false)), listOf(true))
        val dead = Hex.livingOccupancy(listOf(Triple(HexCell(6, 5), 1, false)), listOf(false))
        assertEquals(setOf(HexCell(6, 5)), blocker)
        assertTrue(dead.isEmpty())
        val withBlock = Hex.reach(pos, 0, false, false, 1, "even", false, emptySet(), blocker)
        val withDead = Hex.reach(pos, 0, false, false, 1, "even", false, emptySet(), dead)
        assertFalse(HexCell(6, 5) in withBlock)
        assertTrue(HexCell(6, 5) in withDead)
    }

    @Test
    fun edgeColumnsAndFlyersByHandBuiltCases() {
        val pos = HexCell(2, 5)
        val noEdge = Hex.reachable(pos, 0, false, false, 3, "even", false, emptySet(), emptySet())
        assertTrue(noEdge.none { it.col == 0 })
        val edge = Hex.reachable(pos, 0, false, false, 3, "even", true, emptySet(), emptySet())
        assertTrue(edge.any { it.col == 0 })
        // A flyer jumps a wall but cannot land on an obstacle.
        val wall = (0 until Hex.HEIGHT).map { HexCell(3, it) }.toSet()
        val walker = Hex.reachable(pos, 0, false, false, 4, "even", false, wall, emptySet())
        val flyer = Hex.reachable(pos, 0, false, true, 4, "even", false, wall, emptySet())
        assertTrue(walker.none { it.col >= 3 })
        assertTrue(flyer.any { it.col >= 4 })
        assertTrue(flyer.none { it in wall })
    }
}
