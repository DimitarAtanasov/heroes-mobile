package h3.presenter.ui

import h3.presenter.BoardGeometry
import h3.sim.Hex
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class BoardFitTest {
    private val sizes = listOf(
        360 to 640, 640 to 360, 411 to 891, 891 to 411, 800 to 1280, 1280 to 800, 1920 to 1080,
        1000 to 1000, 100 to 100, 17 to 11, 16 to 10, 5 to 3, 1 to 1, 3000 to 200, 200 to 3000, 0 to 0, 0 to 500, 500 to 0,
    )
    private val margins = listOf(0, 8, 16, 40)

    @Test
    fun integerUnitsMatchTheCanvasGeometryConstants() {
        assertEquals(BoardGeometry.CELL_W, BoardFit.CELL_W_UNITS.toDouble())
        assertEquals(BoardGeometry.ROW_H, BoardFit.ROW_H_UNITS.toDouble())
        assertEquals(BoardGeometry.SHIFT, BoardFit.SHIFT_UNITS.toDouble())
        assertEquals(BoardGeometry.HEX_H, BoardFit.HEX_H_UNITS.toDouble())
    }

    @Test
    fun boardMustFitTheViewportMinusMarginsAndBeAsBigAsPossible() {
        for (m in margins) for ((w, h) in sizes) {
            val f = BoardFit.fit(w, h, m)
            val aw = maxOf(0, w - 2 * m)
            val ah = maxOf(0, h - 2 * m)
            val name = "${w}x$h m=$m"
            assertTrue(f.boardWidthDp <= aw && f.boardHeightDp <= ah, "$name $f")
            // maximal: one more dp of hex width would not fit
            val bigger = BoardFit.forHexDp(f.hexDp + 1, w, h, m)
            assertTrue(bigger.boardWidthDp > aw || bigger.boardHeightDp > ah, "$name not maximal $f")
            // and brute force over every hex size agrees
            val best = (0..3000).last { BoardFit.forHexDp(it, w, h, m).let { b -> b.boardWidthDp <= aw && b.boardHeightDp <= ah } }
            assertEquals(best, f.hexDp, name)
        }
    }

    @Test
    fun boardIsCentredWithIntegerOrigin() {
        for ((w, h) in sizes) {
            val f = BoardFit.fit(w, h, 8)
            assertEquals(Math.floorDiv(w - f.boardWidthDp, 2), f.originXDp)
            assertEquals(Math.floorDiv(h - f.boardHeightDp, 2), f.originYDp)
            assertTrue(f.originXDp >= 0 && f.originYDp >= 0, "$w x $h")
        }
    }

    @Test
    fun sizesFollowTheHexLayout() {
        val f = BoardFit.forHexDp(48, 2000, 2000, 0)
        assertEquals(48, f.hexDp)
        assertEquals(24, f.shiftDp)
        assertEquals(Hex.WIDTH * 48 + 24, f.boardWidthDp)
        assertEquals(45, f.rowPitchDp) // floor(48 * 42 / 44) = floor(45.8)
        assertEquals(62, f.hexHeightDp) // ceil(48 * 56 / 44) = ceil(61.09)
    }

    @Test
    fun oddHexWidthRoundsTheShiftUp() {
        val f = BoardFit.forHexDp(47, 2000, 2000, 0)
        assertEquals(24, f.shiftDp)
        assertEquals(Hex.WIDTH * 47 + 24, f.boardWidthDp)
    }

    @Test
    fun boardHeightIsTenRowPitchesPlusOneHex() {
        for (h in 1..200) {
            val f = BoardFit.forHexDp(h, 5000, 5000, 0)
            assertEquals((Hex.HEIGHT - 1) * f.rowPitchDp + f.hexHeightDp, f.boardHeightDp, "h=$h")
            assertTrue(f.hexHeightDp >= f.rowPitchDp)
        }
    }

    @Test
    fun hexSizeIsMonotonicInTheViewport() {
        var prev = -1
        for (w in 0..1500 step 7) {
            val f = BoardFit.fit(w, 100000, 8)
            assertTrue(f.hexDp >= prev, "w=$w")
            prev = f.hexDp
        }
        prev = -1
        for (h in 0..1500 step 7) {
            val f = BoardFit.fit(100000, h, 8)
            assertTrue(f.hexDp >= prev, "h=$h")
            prev = f.hexDp
        }
    }

    @Test
    fun warnsExactlyBelowTheTouchTarget() {
        assertEquals(48, BoardFit.MIN_TAP_DP)
        for (h in 0..120) {
            assertEquals(h < 48, BoardFit.forHexDp(h, 9000, 9000, 0).belowTapTarget, "h=$h")
        }
    }

    @Test
    fun phonePortraitIsTooSmallTabletLandscapeIsFine() {
        val phone = BoardFit.fit(360, 640, 8)
        assertTrue(phone.belowTapTarget, "$phone")
        assertTrue(phone.hexDp in 1..47)
        val tablet = BoardFit.fit(1280, 800, 8)
        assertFalse(tablet.belowTapTarget, "$tablet")
        assertTrue(tablet.hexDp >= 48)
    }

    @Test
    fun theThresholdViewportsAroundExactlyFortyEightDp() {
        // width needed for hex 48 with zero margin: 17 * 48 + 24 = 840; height: 10 * 45 + 62 = 512 (rowPitch 45, hexH 62)
        val need = BoardFit.forHexDp(48, 0, 0, 0)
        assertFalse(BoardFit.fit(need.boardWidthDp, need.boardHeightDp, 0).belowTapTarget)
        assertTrue(BoardFit.fit(need.boardWidthDp - 1, need.boardHeightDp, 0).belowTapTarget)
        assertTrue(BoardFit.fit(need.boardWidthDp, need.boardHeightDp - 1, 0).belowTapTarget)
    }

    @Test
    fun degenerateViewportsGiveAnEmptyBoardAndAWarning() {
        for ((w, h) in listOf(0 to 0, 0 to 500, 500 to 0, 1 to 1, 2 to 2)) {
            val f = BoardFit.fit(w, h, 8)
            assertEquals(0, f.hexDp, "$w x $h")
            assertEquals(0, f.boardWidthDp)
            assertEquals(0, f.boardHeightDp)
            assertTrue(f.belowTapTarget)
        }
    }

    @Test
    fun negativeInputsAreTreatedAsZeroAndHugeOnesDoNotOverflow() {
        assertEquals(BoardFit.fit(0, 0, 0), BoardFit.fit(-5, -9, -3))
        val huge = BoardFit.fit(Int.MAX_VALUE, Int.MAX_VALUE, 8)
        assertTrue(huge.hexDp > 0 && huge.boardWidthDp > 0 && huge.boardHeightDp > 0)
        assertFalse(huge.belowTapTarget)
    }

    @Test
    fun marginLargerThanTheViewportLeavesNothing() {
        val f = BoardFit.fit(100, 100, 60)
        assertEquals(0, f.hexDp)
        assertTrue(f.belowTapTarget)
    }

    @Test
    fun panModeKeepsTheTapTargetAndReportsOverflow() {
        val f = BoardFit.fit(360, 640, 8)
        val pan = BoardFit.forHexDp(BoardFit.MIN_TAP_DP, 360, 640, 8)
        assertFalse(pan.belowTapTarget)
        assertTrue(pan.overflowsViewport)
        assertTrue(pan.originXDp < 0)
        assertFalse(f.overflowsViewport)
        assertFalse(BoardFit.fit(1280, 800, 8).overflowsViewport)
    }

    @Test
    fun cellCentresStayInsideTheBoardBox() {
        val f = BoardFit.fit(1280, 800, 8)
        for (shiftOdd in listOf(false, true)) for (r in 0 until Hex.HEIGHT) for (c in 0 until Hex.WIDTH) {
            val x = f.cellCenterXDp(c, r, shiftOdd)
            val y = f.cellCenterYDp(r)
            assertTrue(x - f.hexDp / 2 >= f.originXDp - 1 && x + f.hexDp / 2 <= f.originXDp + f.boardWidthDp + 1, "x $c,$r")
            assertTrue(y - f.hexHeightDp / 2 >= f.originYDp - 1 && y + f.hexHeightDp / 2 <= f.originYDp + f.boardHeightDp + 1, "y $c,$r")
        }
        assertEquals(f.originYDp + f.hexHeightDp / 2, f.cellCenterYDp(0))
        assertEquals(f.cellCenterYDp(4) + f.rowPitchDp, f.cellCenterYDp(5))
        assertEquals(f.cellCenterXDp(4, 2, true) + f.hexDp, f.cellCenterXDp(5, 2, true))
    }

    @Test
    fun shiftedRowsFollowTheRowOffsetParity() {
        val f = BoardFit.fit(1280, 800, 8)
        // "even": even rows are shifted, so row 0 sits shiftDp right of row 1 at the same column
        assertEquals(f.cellCenterXDp(3, 1, false) + f.shiftDp, f.cellCenterXDp(3, 0, false))
        assertEquals(f.cellCenterXDp(3, 1, false), f.cellCenterXDp(3, 2, false) - f.shiftDp)
        // "odd": the reverse
        assertEquals(f.cellCenterXDp(3, 0, true) + f.shiftDp, f.cellCenterXDp(3, 1, true))
    }

    @Test
    fun cellCentresMatchTheCanvasGeometryWithinOneDpPerCellOfRounding() {
        // BoardGeometry at margin 0, zoom 1: scale is exact there; ours is the integer fit, so compare in board space.
        val f = BoardFit.forHexDp(44, 2000, 2000, 0) // hexDp == CELL_W_UNITS: scale 1
        val g = BoardGeometry(f.boardWidthDp.toDouble(), f.boardHeightDp.toDouble(), "even", 0.0)
        for (r in 0 until Hex.HEIGHT) for (c in 0 until Hex.WIDTH) {
            val p = g.center(h3.sim.HexCell(c, r))
            val x = f.cellCenterXDp(c, r, false) - f.originXDp
            val y = f.cellCenterYDp(r) - f.originYDp
            assertTrue(Math.abs(x - p.x) <= 1.0 && Math.abs(y - p.y) <= 1.0, "$c,$r ($x,$y) vs $p")
        }
    }

    @Test
    fun unitsToDpRoundsHalfUpAndIsIdentityAtScaleOne() {
        assertEquals(30, BoardFit.forHexDp(44, 2000, 2000, 0).unitsToDp(30))
        val f = BoardFit.forHexDp(48, 2000, 2000, 0)
        assertEquals(0, f.unitsToDp(0))
        assertEquals(48, f.unitsToDp(44))
        assertEquals(1, f.unitsToDp(1)) // 48/44 = 1.09
        assertEquals(23, f.unitsToDp(21)) // 21 * 48 / 44 = 22.9
        assertEquals(11, f.unitsToDp(10)) // 10.9
        assertEquals(1, BoardFit.forHexDp(22, 2000, 2000, 0).unitsToDp(1)) // exactly 0.5 rounds up
        assertEquals(2, BoardFit.forHexDp(22, 2000, 2000, 0).unitsToDp(3)) // exactly 1.5 rounds up
        assertEquals(5, BoardFit.forHexDp(10, 2000, 2000, 0).unitsToDp(22)) // 22 * 10 / 44 = 5.0 exactly
        assertEquals(3, BoardFit.forHexDp(10, 2000, 2000, 0).unitsToDp(13)) // 2.95 -> 3
        assertEquals(2, BoardFit.forHexDp(10, 2000, 2000, 0).unitsToDp(10)) // 2.27 -> 2
        assertEquals(3, BoardFit.forHexDp(11, 2000, 2000, 0).unitsToDp(11)) // 2.75 -> 3
        assertEquals(0, BoardFit.forHexDp(0, 2000, 2000, 0).unitsToDp(44))
    }

    @Test
    fun overflowIsStrictlyGreaterThanTheAvailableArea() {
        val b = BoardFit.forHexDp(48, 5000, 5000, 0)
        assertFalse(BoardFit.forHexDp(48, b.boardWidthDp + 16, b.boardHeightDp + 16, 8).overflowsViewport) // exact fit
        assertTrue(BoardFit.forHexDp(48, b.boardWidthDp + 15, b.boardHeightDp + 16, 8).overflowsViewport)
        assertTrue(BoardFit.forHexDp(48, b.boardWidthDp + 16, b.boardHeightDp + 15, 8).overflowsViewport)
    }

    @Test
    fun originFloorsTowardNegativeInfinityWhenTheBoardOverflowsByAnOddAmount() {
        val b = BoardFit.forHexDp(48, 5000, 5000, 0)
        val f = BoardFit.forHexDp(48, b.boardWidthDp - 7, b.boardHeightDp - 9, 0)
        assertEquals(-4, f.originXDp)
        assertEquals(-5, f.originYDp)
    }
}

