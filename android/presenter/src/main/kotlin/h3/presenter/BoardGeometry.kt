package h3.presenter

import h3.sim.BattleState
import h3.sim.Hex
import h3.sim.HexCell

/** One stack as the hit-test sees it: its id, head cell, side and width. Dead stacks are skipped. */
data class UnitFootprint(val id: Int, val head: HexCell, val side: Int, val doubleWide: Boolean, val alive: Boolean = true) {
    /** Head first, then tail (`Hex.cellsAt`). */
    fun cells(): List<HexCell> = Hex.cellsAt(head, side, doubleWide)
}

/** A tap resolved to a unit: the stack id and its head cell (the canonical target hex). */
data class UnitHit(val id: Int, val head: HexCell)

/** A point in screen pixels. */
data class Pt(val x: Double, val y: Double)

fun footprints(state: BattleState): List<UnitFootprint> =
    state.stacks.map { UnitFootprint(it.id, HexCell(it.pos.first, it.pos.second), it.side, it.creature.doubleWide, it.alive) }

/**
 * Screen geometry of the 17x11 battle board (android-app.md 4.1 and 5.2), pointy-top hexes.
 *
 * Pixel math is Double on purpose: this is UI code, not the simulation. The only values that
 * reach the engine are the Int cells ([HexCell]) returned by [hitTest] and [hitTestUnit]; no
 * pixel, scale or float ever enters a command, a state or a hash.
 *
 * Board space follows the spec: cells are [CELL_W] apart horizontally, rows [ROW_H] apart, a
 * shifted row is offset [SHIFT] to the right, and the first cell's box starts at ([X0], [Y0]).
 * Which rows are shifted comes from the view's `row_offset`: "odd" shifts odd rows, anything
 * else ("even", the default) shifts even rows. That matches `Hex.toAxial`/`Hex.neighbours`
 * (a test checks every adjacency). A hex polygon is the cell box (CELL_W wide, [HEX_H] tall)
 * with pointed top and bottom, so the polygons tile the plane exactly.
 *
 * Screen = board * scale + offset, scale = fit-to-viewport (with [margin]) times [zoom], offset
 * centred plus [panX]/[panY]. Hit testing inverts that transform.
 */
class BoardGeometry(
    val viewW: Double,
    val viewH: Double,
    rowOffset: String = "even",
    margin: Double = 8.0,
    val zoom: Double = 1.0,
    val panX: Double = 0.0,
    val panY: Double = 0.0,
) {
    constructor(viewW: Int, viewH: Int, rowOffset: String = "even") : this(viewW.toDouble(), viewH.toDouble(), rowOffset)

    /** True when odd rows are the shifted ones. */
    val shiftOdd: Boolean = rowOffset == "odd"
    val scale: Double
    val offX: Double
    val offY: Double

    init {
        require(viewW > 0.0 && viewH > 0.0) { "viewport must be positive" }
        require(zoom > 0.0) { "zoom must be positive" }
        val m = minOf(margin.coerceAtLeast(0.0), minOf(viewW, viewH) / 4.0)
        val fit = minOf((viewW - 2 * m) / BOARD_W, (viewH - 2 * m) / BOARD_H)
        scale = fit * zoom
        offX = (viewW - BOARD_W * scale) / 2.0 + panX - X0 * scale
        offY = (viewH - BOARD_H * scale) / 2.0 + panY - Y0 * scale
    }

    private fun shifted(row: Int): Boolean = ((row and 1) == 1) == shiftOdd

    /** Centre of [h] in board space. */
    private fun boardCx(h: HexCell) = X0 + CELL_W / 2.0 + h.col * CELL_W + if (shifted(h.row)) SHIFT else 0.0
    private fun boardCy(h: HexCell) = Y0 + HEX_H / 2.0 + h.row * ROW_H

    /** Centre of [h] in screen pixels. Defined for any cell, in the grid or not. */
    fun center(h: HexCell): Pt = Pt(boardCx(h) * scale + offX, boardCy(h) * scale + offY)

    /** The six polygon corners of [h] in screen pixels, clockwise from the top point. */
    fun corners(h: HexCell): List<Pt> {
        val cx = boardCx(h)
        val cy = boardCy(h)
        val hw = CELL_W / 2.0
        val q = HEX_H / 4.0
        val hh = HEX_H / 2.0
        return listOf(
            cx to cy - hh, cx + hw to cy - q, cx + hw to cy + q,
            cx to cy + hh, cx - hw to cy + q, cx - hw to cy - q,
        ).map { (x, y) -> Pt(x * scale + offX, y * scale + offY) }
    }

    /**
     * The cell under screen point ([x], [y]), or null outside every hex polygon (which includes
     * the jagged strips of the bounding box). Candidates are the cells of the three nearest rows
     * whose polygon contains the point (borders count); the nearest centre wins, ties break by
     * (row, col), so the result is deterministic. Exact for the polygons, both parities.
     */
    fun hitTest(x: Double, y: Double): HexCell? {
        if (!x.isFinite() || !y.isFinite()) return null
        val bx = (x - offX) / scale
        val by = (y - offY) / scale
        val r0 = Math.floor((by - Y0) / ROW_H).toInt()
        var best: HexCell? = null
        var bestD = Double.MAX_VALUE
        for (r in (r0 - 1)..(r0 + 1)) {
            if (r !in 0 until Hex.HEIGHT) continue
            val s = if (shifted(r)) SHIFT else 0.0
            val c0 = Math.floor((bx - X0 - s) / CELL_W).toInt()
            for (c in (c0 - 1)..(c0 + 1)) {
                if (c !in 0 until Hex.WIDTH) continue
                val h = HexCell(c, r)
                val dx = bx - boardCx(h)
                val dy = by - boardCy(h)
                if (!inside(dx, dy)) continue
                val d = dx * dx + dy * dy
                // rows and columns ascend, so a strict < keeps the lowest (row, col) on ties
                if (d < bestD) { best = h; bestD = d }
            }
        }
        return best
    }

    /** Resolves a tap on either cell of a living unit to that unit and its head. */
    fun hitTestUnit(x: Double, y: Double, units: List<UnitFootprint>): UnitHit? {
        val h = hitTest(x, y) ?: return null
        for (u in units) if (u.alive && h in u.cells()) return UnitHit(u.id, u.head)
        return null
    }

    companion object {
        const val CELL_W = 44.0
        const val ROW_H = 42.0
        const val SHIFT = 22.0
        const val HEX_H = 56.0 // ROW_H * 4 / 3: pointed top and bottom, tiles with ROW_H pitch
        const val X0 = 14.0
        const val Y0 = 86.0
        /** Bounding box of the whole grid in board space. */
        const val BOARD_W = Hex.WIDTH * CELL_W + SHIFT
        const val BOARD_H = (Hex.HEIGHT - 1) * ROW_H + HEX_H

        /** (dx, dy) from the centre lies in the pointy hex (border inclusive). */
        private fun inside(dx: Double, dy: Double): Boolean {
            val ax = Math.abs(dx)
            val ay = Math.abs(dy)
            return ax <= CELL_W / 2.0 && ay <= HEX_H / 2.0 - (HEX_H / 4.0) * ax / (CELL_W / 2.0)
        }
    }
}
