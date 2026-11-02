package h3.presenter.ui

import h3.presenter.Fixture
import h3.sim.BattleCreature
import h3.sim.BattleStack
import h3.sim.BattleState
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class BattlePanelsTest {
    private fun creature(name: String) = BattleCreature(name, 5, 5, 1, 3, 10, 5)

    private fun stack(id: Int, side: Int, name: String, count: Int, topHp: Int = 10, defending: Boolean = false) =
        BattleStack(id, side, id, creature(name), count, topHp, Pair(1 + id, 2), 0, 1, defending, 0, 0)

    private val st: BattleState = Fixture.games[0].initial.copy(
        stacks = listOf(
            stack(0, 0, "Test Pikeman", 7, topHp = 4),
            stack(1, 1, "Test Imp", 20, defending = true),
            stack(2, 1, "Griffin", 0),
        ),
        round = 2, started = true, active = 1, done = emptyList(), waited = emptyList(), winner = null,
    )
    private val roster = StackRoster.build(st, listOf(1, 0))

    @Test
    fun livingEntryShowsCountNameAndHealth() {
        val e = BattlePanels.entry(roster.attackers[0])
        assertEquals("7 Pikeman", e.title)
        assertEquals("HP 4/10, total 64", e.detail)
        assertEquals(0, e.row.id)
    }

    @Test
    fun defendingIsShownAndDeadStacksStayListed() {
        assertEquals("HP 10/10, total 200, defending", BattlePanels.entry(roster.defenders[0]).detail)
        val dead = BattlePanels.entries(roster.defenders)[1]
        assertEquals("Griffin (wiped out)", dead.title)
        assertEquals("", dead.detail)
        assertEquals(2, BattlePanels.entries(roster.defenders).size)
    }

    @Test
    fun turnChipsFollowTheTurnOrderWithSidePrefixAndActiveFlag() {
        val chips = BattlePanels.turnChips(roster)
        assertEquals(listOf("D Imp", "A Pikeman"), chips.map { it.label })
        assertEquals(listOf(true, false), chips.map { it.active })
        assertEquals(listOf(1, 0), chips.map { it.id })
        assertEquals(listOf(1, 0), chips.map { it.side })
    }

    @Test
    fun noTurnOrderGivesNoChips() {
        assertTrue(BattlePanels.turnChips(StackRoster.build(st, emptyList())).isEmpty())
    }

    @Test
    fun logHeaderNamesTheRound() {
        assertEquals("Start", BattlePanels.logHeader(BattleLogGroup(0, emptyList())))
        assertEquals("Round 3", BattlePanels.logHeader(BattleLogGroup(3, emptyList())))
    }

    @Test
    fun sideTitles() {
        assertEquals("You (attacker)", BattlePanels.sideTitle(0))
        assertEquals("Computer (defender)", BattlePanels.sideTitle(1))
    }
}
