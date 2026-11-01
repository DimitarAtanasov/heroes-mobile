package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/** Shared pack loading for the scenario and replay tests: the pack texts embedded in `replay.json`. */
internal object ReplayVectors {
    val doc by lazy { loadVector("replay.json") }

    fun packsFrom(rules: String, policy: String, creatures: String): Datapack = Datapack.load(rules, policy, creatures)

    val packTexts by lazy { doc["packs"].obj() }

    val packs: Datapack by lazy {
        packsFrom(packTexts["rules"] as String, packTexts["battle_policy"] as String, packTexts["creatures"] as String)
    }

    fun hexBytes(h: String): ByteArray = ByteArray(h.length / 2) { h.substring(2 * it, 2 * it + 2).toInt(16).toByte() }
}

/** Scenario JSON to initial state versus `vectors/replay.json` (docs/specs/conformance-replay.md). */
class ScenarioTest {
    private val doc = ReplayVectors.doc
    private val packs = ReplayVectors.packs

    @Test
    fun packHashesMatchPython() {
        val p = ReplayVectors.packTexts
        assertEquals(p["rules_hash"], packs.rules.contentHash)
        assertEquals(p["policy_hash"], packs.policy.contentHash)
        assertEquals(p["creatures_hash"], packs.packHash)
    }

    @Test
    fun validScenariosBuildTheSameInitialState() {
        val cases = doc["scenarios"].list().map { it.obj() }
        assertTrue(cases.size >= 10, "cases=${cases.size}")
        val codec = BattleCodec(BattlePolicyPack(
            packs.policy.values, packs.rules.pack.badMoraleNumerators.map { it.toInt() }, packs.rules.pack.moraleDie.toInt()))
        for (c in cases) {
            val name = c["name"] as String
            val state = Scenario.parse(c["scenario"] as String, packs)
            assertEquals(c["initial_canonical"], codec.canonicalText(state), name)
            assertEquals(c["initial_hash"], codec.stateHash(state), name)
            assertEquals(false, state.started, name)
        }
    }

    @Test
    fun invalidScenariosAreRefusedWithPythonMessages() {
        val cases = doc["scenario_errors"].list().map { it.obj() }
        assertTrue(cases.size >= 60, "cases=${cases.size}")
        var exact = 0
        for (c in cases) {
            val name = c["name"] as String
            val e = assertFailsWith<ScenarioError>(name) { Scenario.parse(c["scenario"] as String, packs) }
            if (c["exact"] == true) {
                assertEquals(c["error"], e.message, name)
                exact++
            } else {
                assertTrue(e.message!!.startsWith("scenario"), "$name: ${e.message}")
            }
        }
        assertTrue(exact >= 60, "exact=$exact")
    }

    @Test
    fun malformedJsonTextIsAScenarioError() {
        for (t in listOf("", "{", "{\"a\":}", "[1,]", "nul", "{\"battle_id\":\"x\"} x", "NaN")) {
            assertFailsWith<ScenarioError>(t) { Scenario.parse(t, packs) }
        }
    }

    @Test
    fun placementRowsAndDoubleWideHeads() {
        // One single-wide and one double-wide stack per side, default placement rows.
        val text = """{"battle_id":"pl","creatures":{"a":{"attack":1,"defense":1,"dmg_min":1,"dmg_max":2,"hp":5,"speed":3},
            "w":{"attack":1,"defense":1,"dmg_min":1,"dmg_max":2,"hp":5,"speed":3,"double_wide":true}},
            "attackers":[{"creature":"a","count":1},{"creature":"w","count":1}],
            "defenders":[{"creature":"w","count":1},{"creature":"a","count":1}]}"""
        val s = Scenario.parse(text, packs)
        val rows = s.policy.placementRows[1]
        assertEquals(listOf(Pair(1, rows[0]), Pair(2, rows[1]), Pair(14, rows[0]), Pair(15, rows[1])), s.stacks.map { it.pos })
        assertEquals(listOf(0, 0, 1, 1), s.stacks.map { it.side })
        assertEquals(listOf(0, 1, 0, 1), s.stacks.map { it.slot })
        assertEquals(listOf(5, 5, 5, 5), s.stacks.map { it.topHp })
    }
}
