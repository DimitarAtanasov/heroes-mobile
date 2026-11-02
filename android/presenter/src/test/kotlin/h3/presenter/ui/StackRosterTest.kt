package h3.presenter.ui

import h3.presenter.AtlasBuilder
import h3.presenter.AtlasFrame
import h3.presenter.BuildResult
import h3.presenter.Fixture
import h3.sim.BattleCommand
import h3.sim.BattleCreature
import h3.sim.BattleStack
import h3.sim.BattleState
import h3.sim.RngStreams
import h3.sim.asDrawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class StackRosterTest {
    private fun creature(name: String, hp: Int = 10) = BattleCreature(name, 5, 5, 1, 3, hp, 5)

    private fun stack(id: Int, side: Int, slot: Int, name: String, count: Int, topHp: Int = 10, hp: Int = 10) =
        BattleStack(id, side, slot, creature(name, hp), count, topHp, Pair(1 + id, 2), 0, 1, false, 0, 0)

    private val base: BattleState = Fixture.games[0].initial

    /** Ids 0,1 attackers (slots 1,0 on purpose), 2,3 defenders, 4 a dead defender. */
    private val st: BattleState = base.copy(
        stacks = listOf(
            stack(0, 0, 1, "Test Pikeman", 7, topHp = 4),
            stack(1, 0, 0, "Test Archer", 3),
            stack(2, 1, 0, "Test Imp", 20, topHp = 1, hp = 4),
            stack(3, 1, 1, "Griffin", 2, topHp = 25, hp = 25),
            stack(4, 1, 2, "Test Gog", 0),
        ),
        round = 2, started = true, active = 2, done = listOf(1), waited = emptyList(), winner = null,
    )

    @Test
    fun rowsPerSideInSlotOrderWithNamesCountsAndHealth() {
        val r = StackRoster.build(st, listOf(2, 0, 3))
        assertEquals(listOf(1, 0), r.attackers.map { it.id })
        assertEquals(listOf(2, 3, 4), r.defenders.map { it.id })
        val pike = r.attackers[1]
        assertEquals("Pikeman", pike.name)
        assertEquals(7, pike.count)
        assertEquals(4, pike.topHp)
        assertEquals(10, pike.maxHp)
        assertEquals((7L - 1) * 10 + 4, pike.totalHp)
        assertEquals("Griffin", r.defenders[1].name)
        assertEquals((20L - 1) * 4 + 1, r.defenders[0].totalHp)
        assertEquals(0, r.attackers[1].side)
        assertEquals(1, r.defenders[0].side)
    }

    @Test
    fun activeMarkerIsOnTheActiveStackOnly() {
        val r = StackRoster.build(st, listOf(2, 0, 3))
        assertEquals(listOf(2), (r.attackers + r.defenders).filter { it.active }.map { it.id })
        assertTrue(r.defenders[0].active)
        assertEquals(2, r.activeId)
    }

    @Test
    fun noActiveMarkerWhenNothingIsActiveOrActiveIsDead() {
        val none = StackRoster.build(st.copy(active = null), listOf(0, 2))
        assertTrue((none.attackers + none.defenders).none { it.active })
        assertNull(none.activeId)
        val dead = StackRoster.build(st.copy(active = 4), listOf(0, 2))
        assertTrue((dead.attackers + dead.defenders).none { it.active })
        assertNull(dead.activeId)
    }

    @Test
    fun turnPositionIsIndexInOrderAndNullWhenNotQueued() {
        val r = StackRoster.build(st, listOf(2, 0, 3))
        assertEquals(0, r.defenders[0].turnPos)
        assertEquals(1, r.attackers[1].turnPos)
        assertEquals(2, r.defenders[1].turnPos)
        assertNull(r.attackers[0].turnPos)
        assertEquals(listOf(2, 0, 3), r.turnOrder)
    }

    @Test
    fun deadStackIsKeptButFlaggedAndNeverQueued() {
        val r = StackRoster.build(st, listOf(2, 4, 0))
        val dead = r.defenders[2]
        assertFalse(dead.alive)
        assertNull(dead.turnPos)
        assertEquals(0, dead.totalHp)
        assertEquals(listOf(2, 0), r.turnOrder)
        assertEquals(2, r.defenders.count { it.alive })
    }

    @Test
    fun unknownIdsInTheOrderAreDropped() {
        assertEquals(listOf(2), StackRoster.build(st, listOf(99, 2, -1)).turnOrder)
    }

    @Test
    fun duplicateIdsInTheOrderKeepTheFirst() {
        val r = StackRoster.build(st, listOf(2, 0, 2))
        assertEquals(listOf(2, 0), r.turnOrder)
        assertEquals(0, r.defenders[0].turnPos)
    }

    @Test
    fun emptyBattleGivesEmptySides() {
        val r = StackRoster.build(st.copy(stacks = emptyList(), active = null, done = emptyList()), emptyList())
        assertTrue(r.attackers.isEmpty() && r.defenders.isEmpty() && r.turnOrder.isEmpty())
    }

    @Test
    fun buildFromBattleUsesTheEnginesTurnOrder() {
        val r = StackRoster.build(Fixture.battle, st)
        assertEquals(Fixture.battle.turnOrder(st).filter { st.stacks[it].alive }, r.turnOrder)
        assertEquals(2, r.turnOrder.first())
        assertEquals(0, r.defenders[0].turnPos)
    }

    @Test
    fun goldenPlayoutsRosterMatchesStateAtEveryStep() {
        for (g in Fixture.games) {
            val rng = RngStreams.derive(g.masterSeed, "battle:" + g.initial.battleId)
            val greedy = Fixture.ai.GreedyAi(g.aiSeed)
            var s = g.initial
            var n = 0
            while ((s.winner == null || !s.started) && n < 120) {
                val rows = StackRoster.build(Fixture.battle, s)
                val all = rows.attackers + rows.defenders
                assertEquals(s.stacks.size, all.size, g.name)
                assertEquals(s.stacks.map { it.id }.sorted(), all.map { it.id }.sorted(), g.name)
                for (row in all) {
                    val real = s.stacks[row.id]
                    assertEquals(real.side, row.side)
                    assertEquals(real.count, row.count)
                    assertEquals(real.topHp, row.topHp)
                    assertEquals(real.alive, row.alive)
                    assertEquals(real.creature.name.removePrefix("Test "), row.name)
                    assertEquals(row.id == s.active && real.alive, row.active, "${g.name} step $n")
                }
                assertTrue(rows.attackers.all { it.side == 0 } && rows.defenders.all { it.side == 1 })
                assertEquals(all.count { it.active }, if (s.active != null && s.stacks[s.active!!].alive) 1 else 0)
                // turn positions are exactly 0..k-1 over the queued rows
                val pos = all.mapNotNull { it.turnPos }.sorted()
                assertEquals((0 until pos.size).toList(), pos, g.name)
                assertEquals(rows.turnOrder, rows.turnOrder.indices.map { i -> all.first { it.turnPos == i }.id })
                if (s.active != null && s.stacks[s.active!!].alive) assertEquals(s.active, rows.turnOrder.first())
                val side = s.active?.let { s.stacks[it].side }
                val cmd: BattleCommand = if (!s.started) BattleCommand.Begin else greedy.choose(s, side)
                s = Fixture.battle.apply(s, cmd, rng.asDrawSource()).state
                n++
            }
        }
    }

    @Test
    fun spriteDataIsPureAndSideIndependent() {
        val r = StackRoster.build(st, listOf(2, 0, 3))
        val imp = r.defenders[0]
        assertEquals("creature/test_imp", imp.spritePrefix)
        assertEquals("creature/test_imp/002/0000", imp.idleKey)
        assertTrue(imp.flipX)
        assertFalse(r.attackers[1].flipX)
        assertEquals("creature/griffin/002/0000", r.defenders[1].idleKey)
        assertEquals("I", imp.fallbackLetter)
        assertEquals("G", r.defenders[1].fallbackLetter)
        assertEquals("20", imp.countBadge)
        assertEquals("", r.defenders[2].countBadge) // dead stack
    }

    @Test
    fun slugAndBadgeRules() {
        assertEquals("creature/archangel", UiSpriteKey.prefix("Archangel"))
        assertEquals("creature/iron_golem_2", UiSpriteKey.prefix("  Iron-Golem (2) "))
        assertEquals("creature/unknown", UiSpriteKey.prefix(""))
        assertEquals("creature/unknown", UiSpriteKey.prefix("!!!"))
        assertEquals("creature/a_b", UiSpriteKey.prefix("a  --  B"))
        assertEquals("creature/x/002/0000", UiSpriteKey.idleKey("X"))
        assertEquals("?", UiSpriteKey.fallbackLetter(""))
        assertEquals("?", UiSpriteKey.fallbackLetter("   "))
        assertEquals("Z", UiSpriteKey.fallbackLetter("zombie"))
        assertEquals("", UiSpriteKey.countBadge(0))
        assertEquals("", UiSpriteKey.countBadge(-3))
        assertEquals("1", UiSpriteKey.countBadge(1))
        assertEquals("9999", UiSpriteKey.countBadge(9999))
        assertEquals("10k", UiSpriteKey.countBadge(10_000))
        assertEquals("12k", UiSpriteKey.countBadge(12_999))
    }

    @Test
    fun doubleWideAndDefendingComeFromTheStack() {
        val wide = stack(0, 0, 0, "Test Brute", 2).let { it.copy(creature = it.creature.copy(doubleWide = true), defending = true) }
        val r = StackRoster.build(st.copy(stacks = listOf(wide, stack(1, 1, 0, "Test Imp", 1)), active = 0, done = emptyList()), listOf(0, 1))
        assertTrue(r.attackers[0].doubleWide && r.attackers[0].defending)
        assertFalse(r.defenders[0].doubleWide || r.defenders[0].defending)
    }

    private fun frameOf(key: String, w: Int, h: Int) = AtlasFrame(key, w, h, ByteArray(w * h * 4) { 7 })

    @Test
    fun spriteRectIsNullWithoutAnAtlasAndWithAnAtlasThatLacksTheKey() {
        val row = StackRoster.build(st, listOf(2, 0)).defenders[0]
        assertNull(row.spriteRect(null))
        val other = (AtlasBuilder().add(frameOf("creature/other/002/0000", 4, 4)).build() as BuildResult.Ok).atlas
        assertNull(row.spriteRect(other))
        assertNull(UiSpriteKey.idleRect(null, "Test Imp"))
    }

    @Test
    fun spriteRectFindsTheIdleFrameAndIgnoresEmptyFrames() {
        val row = StackRoster.build(st, listOf(2, 0)).defenders[0]
        val atlas = (AtlasBuilder().add(frameOf(row.idleKey, 5, 6)).add(frameOf("creature/test_pikeman/002/0000", 0, 0)).build() as BuildResult.Ok).atlas
        val r = row.spriteRect(atlas)!!
        assertEquals(5, r.w)
        assertEquals(6, r.h)
        assertEquals(atlas.rects.getValue(row.idleKey), r)
        assertEquals(r, UiSpriteKey.idleRect(atlas, "Test Imp"))
        val pike = StackRoster.build(st, listOf(2, 0)).attackers[1]
        assertNull(pike.spriteRect(atlas)) // zero-area frame: page -1, treated as absent
    }
}

