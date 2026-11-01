package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Boundary table for `Pcg32.chance`, mirrored in tools/h3re/tests/test_rng.py
 * (`CHANCE_EDGES`). Proves the "equivalent mutant" claim: a non-positive
 * numerator or num >= den returns without consuming a draw.
 */
class RngEdgeTest {
    private class Edge(val num: Long, val den: Long, val want: Boolean?, val draws: Int)

    private val edges = listOf(
        Edge(0, 1, false, 0), Edge(0, 5, false, 0), Edge(-1, 5, false, 0), Edge(-5, 1, false, 0),
        Edge(-(1L shl 62), 7, false, 0), Edge(1, 1, true, 0), Edge(5, 5, true, 0), Edge(2, 1, true, 0),
        Edge(6, 5, true, 0), Edge(1L shl 62, 7, true, 0), Edge(-1, 1, false, 0),
        Edge(1, 2, null, 1), Edge(1, 5, null, 1), Edge(4, 5, null, 1), Edge(3, 10, null, 1),
    )

    @Test
    fun boundaryTableConsumesExactlyTheExpectedDraws() {
        for (e in edges) {
            val g = Pcg32(11UL, 3UL)
            val ref = Pcg32(11UL, 3UL)
            val before = g.state
            val got = g.chance(e.num, e.den)
            if (e.want != null) assertEquals(e.want, got, "chance(${e.num}, ${e.den})")
            repeat(e.draws) { ref.nextU32() }
            if (e.draws == 0) assertEquals(before, g.state, "state moved for chance(${e.num}, ${e.den})")
            assertEquals(ref.state, g.state, "draw count for chance(${e.num}, ${e.den})")
            assertEquals(ref.nextU32(), g.nextU32(), "next draw after chance(${e.num}, ${e.den})")
        }
    }

    @Test
    fun zeroAndNegativeNumeratorIsFalseWithoutDraw() {
        for (den in listOf(1L, 2L, 7L, 1000L)) for (num in listOf(0L, -1L, -den, Long.MIN_VALUE)) {
            val g = Pcg32(5UL, 5UL)
            val before = g.state
            assertFalse(g.chance(num, den))
            assertEquals(before, g.state)
        }
    }

    @Test
    fun numAtLeastDenIsTrueWithoutDraw() {
        for (den in listOf(1L, 2L, 7L, 1000L)) for (num in listOf(den, den + 1, Long.MAX_VALUE)) {
            val g = Pcg32(5UL, 5UL)
            val before = g.state
            assertTrue(g.chance(num, den))
            assertEquals(before, g.state)
        }
    }

    @Test
    fun interiorProbabilityDrawsExactlyOnce() {
        for (e in edges.filter { it.draws == 1 }) {
            val g = Pcg32(21UL, 1UL)
            val ref = Pcg32(21UL, 1UL)
            // rejection sampling may redraw, so compare with range(0, den) directly
            val r = ref.range(0, e.den)
            assertEquals(r < e.num, g.chance(e.num, e.den))
            assertEquals(ref.state, g.state)
        }
    }

    @Test
    fun nonPositiveDenominatorThrowsBeforeAnyDraw() {
        for (den in listOf(0L, -1L, -7L)) for (num in listOf(-1L, 0L, 1L, 10L)) {
            val g = Pcg32(5UL, 5UL)
            val before = g.state
            assertFailsWith<IllegalArgumentException> { g.chance(num, den) }
            assertEquals(before, g.state)
        }
    }
}
