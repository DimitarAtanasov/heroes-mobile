package h3.presenter.ui

import h3.sim.Hex

/**
 * Integer dp sizing of the 17x11 hex board for a viewport (UI only, no state, no hash).
 *
 * The layout ratios are those of `BoardGeometry` (cell width 44, row pitch 42, shift 22, hex
 * height 56 board units), kept here as integers so the screen can size the board without
 * floats: for a hex width of `hexDp`, a shifted row sits `ceil(hexDp / 2)` to the right, rows
 * are `floor(hexDp * 42 / 44)` apart and a hex is `ceil(hexDp * 56 / 44)` tall. So
 * `boardWidthDp = 17 * hexDp + shiftDp` and `boardHeightDp = 10 * rowPitchDp + hexHeightDp`.
 * Rounding is explicit per quantity and always conservative where it matters: [fit] picks the
 * largest `hexDp` whose board fits the viewport minus the margins.
 *
 * [belowTapTarget] is true when `hexDp < MIN_TAP_DP` (48 dp, the usual minimum touch target):
 * the board is then drawable but hexes are too small to tap reliably, and the screen should offer
 * zoom and pan ([forHexDp] with [MIN_TAP_DP], whose [overflowsViewport] is then true) or a hint.
 */
data class BoardFit(
    val hexDp: Int,
    val shiftDp: Int,
    val rowPitchDp: Int,
    val hexHeightDp: Int,
    val boardWidthDp: Int,
    val boardHeightDp: Int,
    /** Top-left of the board box in viewport dp; negative when the board overflows (pan mode). */
    val originXDp: Int,
    val originYDp: Int,
    val belowTapTarget: Boolean,
    /** True when the board is wider or taller than the viewport minus its margins. */
    val overflowsViewport: Boolean,
) {
    /**
     * Size in dp of something [units] board units long (a sprite drawn for the 44-unit cell, a count
     * plate), rounded half up: `floor((units * hexDp + 22) / 44)`. The exact scale is hexDp / 44.
     */
    fun unitsToDp(units: Int): Int = Math.floorDiv(units * hexDp + CELL_W_UNITS / 2, CELL_W_UNITS)

    /**
     * Centre x of cell ([col], [row]) in viewport dp. [shiftOdd] is true when odd rows are the shifted
     * ones (`BattlePolicy.rowOffset == "odd"`), false for "even"; a shifted row sits [shiftDp] right.
     */
    fun cellCenterXDp(col: Int, row: Int, shiftOdd: Boolean): Int =
        originXDp + hexDp / 2 + col * hexDp + if (((row and 1) == 1) == shiftOdd) shiftDp else 0

    /** Centre y of row [row] in viewport dp. */
    fun cellCenterYDp(row: Int): Int = originYDp + hexHeightDp / 2 + row * rowPitchDp

    companion object {
        /** Minimum comfortable touch target, in dp. */
        const val MIN_TAP_DP = 48
        const val DEFAULT_MARGIN_DP = 8

        // Layout ratios, integer board units (a test pins them to the canvas geometry).
        const val CELL_W_UNITS = 44
        const val ROW_H_UNITS = 42
        const val SHIFT_UNITS = 22
        const val HEX_H_UNITS = 56

        /** Inputs are clamped to this, so products below stay far from Int overflow. */
        private const val MAX_VIEW_DP = 1_000_000

        private fun ceilDivPos(a: Int, b: Int): Int = -Math.floorDiv(-a, b)

        private fun clampDp(v: Int): Int = if (v < 0) 0 else if (v > MAX_VIEW_DP) MAX_VIEW_DP else v

        /** Largest hex width whose board fits the viewport minus [marginDp] on every side. */
        fun fit(viewWidthDp: Int, viewHeightDp: Int, marginDp: Int = DEFAULT_MARGIN_DP): BoardFit {
            val availW = availableDp(viewWidthDp, marginDp)
            val availH = availableDp(viewHeightDp, marginDp)
            // Closed-form guess from the exact ratios, then settled against the real rounded sizes.
            var h = minOf(Math.floorDiv(2 * availW, 2 * Hex.WIDTH + 1), Math.floorDiv(availH * CELL_W_UNITS, boardHeightUnits()))
            while (!boardFits(h, availW, availH)) h--
            while (boardFits(h + 1, availW, availH)) h++
            return forHexDp(h, viewWidthDp, viewHeightDp, marginDp)
        }

        /** The board for a chosen [hexDp] (for example [MIN_TAP_DP] in pan mode), centred in the viewport. */
        fun forHexDp(hexDp: Int, viewWidthDp: Int, viewHeightDp: Int, marginDp: Int = DEFAULT_MARGIN_DP): BoardFit {
            val h = clampDp(hexDp)
            val vw = clampDp(viewWidthDp)
            val vh = clampDp(viewHeightDp)
            val shift = shiftFor(h)
            val pitch = pitchFor(h)
            val hexH = heightFor(h)
            val bw = Hex.WIDTH * h + shift
            val bh = (Hex.HEIGHT - 1) * pitch + hexH
            return BoardFit(
                hexDp = h, shiftDp = shift, rowPitchDp = pitch, hexHeightDp = hexH,
                boardWidthDp = bw, boardHeightDp = bh,
                originXDp = Math.floorDiv(vw - bw, 2), originYDp = Math.floorDiv(vh - bh, 2),
                belowTapTarget = h < MIN_TAP_DP,
                overflowsViewport = bw > availableDp(vw, marginDp) || bh > availableDp(vh, marginDp),
            )
        }

        private fun availableDp(viewDp: Int, marginDp: Int): Int {
            val m = clampDp(marginDp)
            val left = clampDp(viewDp) - 2 * m
            return if (left < 0) 0 else left
        }

        private fun shiftFor(h: Int): Int = ceilDivPos(h * SHIFT_UNITS, CELL_W_UNITS)
        private fun pitchFor(h: Int): Int = Math.floorDiv(h * ROW_H_UNITS, CELL_W_UNITS)
        private fun heightFor(h: Int): Int = ceilDivPos(h * HEX_H_UNITS, CELL_W_UNITS)

        /** Board height in units: (HEIGHT - 1) row pitches plus one hex. */
        private fun boardHeightUnits(): Int = (Hex.HEIGHT - 1) * ROW_H_UNITS + HEX_H_UNITS

        private fun boardFits(h: Int, availW: Int, availH: Int): Boolean {
            if (h <= 0) return true
            val bw = Hex.WIDTH * h + shiftFor(h)
            val bh = (Hex.HEIGHT - 1) * pitchFor(h) + heightFor(h)
            return bw <= availW && bh <= availH
        }
    }
}
