package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Slice 3 (docs/specs/roster-from-crtraits.md, Q5): battle roster, synthetic data only. */
class RosterTest {
    private fun cr(name: String, min: Long, max: Long) = Creature(
        name = name, hp = 10, speed = 5, attack = 3, defense = 3,
        dmgMin = min, dmgMax = max, shots = 0, flags = emptySet(),
    )

    private fun result(vararg cs: Creature) = ContentResult(
        creatures = cs.toList(), extras = emptyMap(), unknown = emptyList(),
        creatureRows = cs.withIndex().associate { (i, c) -> c.name to i },
        noFixedDamage = cs.filter { it.dmgMax == 0L }.map { it.name }.toSet(),
    )

    @Test
    fun noFixedDamageLeftOutFileOrderKept() {
        val r = result(cr("Normal", 2, 5), cr("Nofix", 0, 0), cr("Weak", 0, 3))
        assertEquals(listOf("Normal", "Weak"), Content.battleRoster(r).map { it.name })
    }

    @Test
    fun weakCreatureIsOffered() {
        val r = result(cr("Weak", 0, 3), cr("Normal", 1, 1))
        assertEquals(listOf("Weak", "Normal"), Content.battleRoster(r).map { it.name })
    }

    @Test
    fun emptyInputGivesEmptyRoster() {
        assertTrue(Content.battleRoster(result()).isEmpty())
    }
}
