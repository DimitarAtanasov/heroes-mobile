package h3.presenter.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotSame
import kotlin.test.assertSame
import kotlin.test.assertTrue

class MenuModelTest {
    private val all = MenuRoute.values().toList()

    /** Every legal (from, to) edge, on a model that has an autosave. */
    private val legal = setOf(
        MenuRoute.Home to MenuRoute.Setup,
        MenuRoute.Home to MenuRoute.About,
        MenuRoute.Home to MenuRoute.Battle,
        MenuRoute.Setup to MenuRoute.Battle,
        MenuRoute.Battle to MenuRoute.Result,
        MenuRoute.Result to MenuRoute.Setup,
    )

    /** A model whose current route is [r], reached only through legal moves. */
    private fun at(r: MenuRoute, autosave: Boolean = true): MenuModel {
        val m = MenuModel.initial(autosave)
        return when (r) {
            MenuRoute.Home -> m
            MenuRoute.Setup -> m.forward(MenuRoute.Setup)
            MenuRoute.About -> m.forward(MenuRoute.About)
            MenuRoute.Battle -> m.forward(MenuRoute.Setup).forward(MenuRoute.Battle)
            MenuRoute.Result -> m.forward(MenuRoute.Setup).forward(MenuRoute.Battle).forward(MenuRoute.Result)
        }
    }

    @Test
    fun initialIsHomeWithNoHistory() {
        val m = MenuModel.initial(false)
        assertEquals(listOf(MenuRoute.Home), m.stack)
        assertEquals(MenuRoute.Home, m.current)
        assertFalse(m.canGoBack)
        assertSame(m, m.back())
    }

    @Test
    fun continueEnabledOnlyWithAutosave() {
        assertFalse(MenuModel.initial(false).continueEnabled)
        assertTrue(MenuModel.initial(true).continueEnabled)
        assertTrue(MenuModel.initial(false).withAutosave(true).continueEnabled)
        assertFalse(MenuModel.initial(true).withAutosave(false).continueEnabled)
    }

    @Test
    fun withAutosaveKeepsTheStack() {
        val m = at(MenuRoute.Setup, autosave = false).withAutosave(true)
        assertEquals(listOf(MenuRoute.Home, MenuRoute.Setup), m.stack)
        assertTrue(m.autosaveExists)
    }

    @Test
    fun withAutosaveSameValueReturnsSameInstance() {
        val m = MenuModel.initial(true)
        assertSame(m, m.withAutosave(true))
    }

    @Test
    fun continueFromHomeNeedsAutosave() {
        val without = MenuModel.initial(false)
        assertFalse(without.canForward(MenuRoute.Battle))
        assertSame(without, without.forward(MenuRoute.Battle))
        val with = MenuModel.initial(true)
        assertTrue(with.canForward(MenuRoute.Battle))
        val b = with.forward(MenuRoute.Battle)
        assertEquals(listOf(MenuRoute.Home, MenuRoute.Battle), b.stack)
    }

    @Test
    fun setupToBattleDropsSetupFromHistory() {
        val b = at(MenuRoute.Setup).forward(MenuRoute.Battle)
        assertEquals(listOf(MenuRoute.Home, MenuRoute.Battle), b.stack)
        assertEquals(MenuRoute.Home, b.back().current)
    }

    @Test
    fun battleToResultReplacesBattle() {
        val r = at(MenuRoute.Battle).forward(MenuRoute.Result)
        assertEquals(listOf(MenuRoute.Home, MenuRoute.Result), r.stack)
        assertEquals(listOf(MenuRoute.Home), r.back().stack)
    }

    @Test
    fun resultToSetupPlaysAgain() {
        val s = at(MenuRoute.Result).forward(MenuRoute.Setup)
        assertEquals(listOf(MenuRoute.Home, MenuRoute.Setup), s.stack)
    }

    @Test
    fun aboutAndSetupReturnHomeOnBack() {
        assertEquals(listOf(MenuRoute.Home), at(MenuRoute.About).back().stack)
        assertEquals(listOf(MenuRoute.Home), at(MenuRoute.Setup).back().stack)
        assertEquals(listOf(MenuRoute.Home), at(MenuRoute.Battle).back().stack)
    }

    @Test
    fun transitionMatrixIsExactlyTheLegalEdges() {
        for (from in all) for (to in all) {
            val m = at(from)
            val ok = (from to to) in legal
            assertEquals(ok, m.canForward(to), "canForward $from -> $to")
            val n = m.forward(to)
            if (ok) {
                assertEquals(to, n.current, "forward $from -> $to")
                assertNotSame(m, n)
            } else {
                assertSame(m, n, "illegal forward $from -> $to must be a no-op")
            }
        }
    }

    @Test
    fun forwardDoesNotMutateTheOriginal() {
        val m = MenuModel.initial(true)
        m.forward(MenuRoute.Setup)
        assertEquals(listOf(MenuRoute.Home), m.stack)
        val s = at(MenuRoute.Setup)
        s.back()
        assertEquals(listOf(MenuRoute.Home, MenuRoute.Setup), s.stack)
    }

    @Test
    fun equalityFollowsStackAndAutosave() {
        assertEquals(MenuModel.initial(true), MenuModel.initial(true))
        assertEquals(MenuModel.initial(true).hashCode(), MenuModel.initial(true).hashCode())
        assertTrue(MenuModel.initial(true) != MenuModel.initial(false))
        assertTrue(at(MenuRoute.Setup) != at(MenuRoute.About))
    }

    @Test
    fun randomWalkKeepsInvariants() {
        var seed = 12345L
        fun next(n: Int): Int {
            seed = (seed * 6364136223846793005L + 1442695040888963407L)
            return Math.floorMod(seed ushr 33, n.toLong()).toInt()
        }
        var m = MenuModel.initial(false)
        repeat(5000) {
            m = when (next(4)) {
                0 -> m.back()
                1 -> m.withAutosave(next(2) == 0)
                else -> m.forward(all[next(all.size)])
            }
            assertEquals(MenuRoute.Home, m.stack.first())
            assertTrue(m.stack.size in 1..2, "stack ${m.stack}")
            assertEquals(m.stack.last(), m.current)
            assertEquals(m.stack.size > 1, m.canGoBack)
            assertEquals(1, m.stack.count { it == MenuRoute.Home })
        }
    }

    @Test
    fun battleIsOnlyReachableFromHomeWithAutosaveOrFromSetup() {
        var seed = 99L
        fun next(n: Int): Int {
            seed = (seed * 6364136223846793005L + 1442695040888963407L)
            return Math.floorMod(seed ushr 33, n.toLong()).toInt()
        }
        var m = MenuModel.initial(false)
        repeat(5000) {
            val before = m
            m = when (next(3)) {
                0 -> m.back()
                1 -> m.forward(all[next(all.size)])
                else -> m.withAutosave(next(2) == 0)
            }
            if (before.current != MenuRoute.Battle && m.current == MenuRoute.Battle) {
                assertTrue(
                    before.current == MenuRoute.Setup || (before.current == MenuRoute.Home && before.autosaveExists),
                    "entered Battle from ${before.current} autosave=${before.autosaveExists}",
                )
            }
        }
    }
}
