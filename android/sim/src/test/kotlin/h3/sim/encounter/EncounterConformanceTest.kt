package h3.sim.encounter

import h3.sim.AdventureCodec
import h3.sim.AdventureCommand
import h3.sim.AdventureRules
import h3.sim.AdventureState
import h3.sim.Adventure
import h3.sim.BattleCodec
import h3.sim.Canonical
import h3.sim.Datapack
import h3.sim.IllegalCommand
import h3.sim.MiniJson
import h3.sim.Pcg32
import h3.sim.big
import h3.sim.list
import h3.sim.loadVector
import h3.sim.obj
import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlin.test.fail

internal fun Any?.s(): String = this as String

internal fun enc(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

internal object EncVectors {
    val doc: Map<String, Any?> by lazy { loadVector("encounter.json") }
    val packs: Datapack by lazy {
        val p = doc["packs"].obj()
        Datapack.load(p["rules"].s(), p["battle_policy"].s(), p["creatures"].s())
    }
    val rules: AdventureRules by lazy { AdventureRules.from(doc["constants"]) }
    val engine: EncounterEngine by lazy { EncounterEngine.from(rules, packs) }
    val codec: AdventureCodec by lazy { AdventureCodec(rules, engine) }
    val adventure: Adventure by lazy { Adventure(rules, engine) }
    val cases: List<Map<String, Any?>> by lazy { doc["cases"].list().map { it.obj() } }

    fun parse(text: String, check: Boolean = true): AdventureState = codec.parseState(MiniJson.parse(text), check)

    /** [state, inc] of a stream as decimal strings (Python ints beyond Long). */
    fun pos(g: Pcg32): List<String> = listOf(g.state.toString(), g.inc.toString())

    fun pos(v: Any?): List<String> = v.list().map { it.big().toString() }

    fun cmd(v: Any?): AdventureCommand = AdventureCodec.parseCommand(v)
}

/** Conformance of the Kotlin encounter module and adventure stage E against `vectors/encounter.json` (docs/specs/conformance-encounter.md). */
class EncounterConformanceTest {
    private val doc = EncVectors.doc
    private val engine = EncVectors.engine
    private val codec = EncVectors.codec
    private val adv = EncVectors.adventure
    private val cases = EncVectors.cases

    private fun steps(c: Map<String, Any?>) = c["steps"].list().map { it.obj() }

    private fun before(c: Map<String, Any?>, i: Int): String {
        var k = i - 1
        while (k >= 0 && steps(c)[k].containsKey("error")) k--
        return if (k < 0) c["initial"].obj()["canonical"].s() else steps(c)[k]["canonical"].s()
    }

    @Test
    fun packsMatchPython() {
        val p = doc["packs"].obj()
        assertEquals(p["rules_hash"], EncVectors.packs.rules.contentHash)
        assertEquals(p["policy_hash"], EncVectors.packs.policy.contentHash)
        assertEquals(p["creatures_hash"], EncVectors.packs.packHash)
        assertEquals(EncVectors.packs.rules.contentHash, engine.rulesHash)
    }

    @Test
    fun vectorIsNonTrivial() {
        assertTrue(cases.size >= 25)
        val all = cases.flatMap { steps(it) }
        assertTrue(all.size >= 700)
        assertEquals(setOf("Begin", "Move", "EndTurn", "Attack"), all.map { it["command"].obj()["type"] }.toSet())
        val types = all.flatMap { s -> (s["events"]?.list() ?: emptyList()).map { it.obj()["type"] } }.toSet()
        assertTrue(types.containsAll(setOf("BattleFought", "ArmyChanged", "HeroDefeated", "GuardDefeated", "HeroMoved")), "$types")
        val fought = all.flatMap { s -> (s["events"]?.list() ?: emptyList()).map { it.obj() }.filter { it["type"] == "BattleFought" } }
        assertTrue(fought.size >= 100)
        assertEquals(setOf(null, BigInteger.ZERO, BigInteger.ONE), fought.map { it["winner"] }.toSet())
    }

    @Test
    fun stageA_codecRoundTripAndHash() {
        var n = 0
        for (c in cases) {
            val texts = listOf(c["initial"].obj()) + steps(c).filter { !it.containsKey("error") }
            for (t in texts) {
                val s = EncVectors.parse(t["canonical"].s())
                assertEquals(t["canonical"], codec.canonicalText(s), "${c["name"]}")
                assertEquals(t["sha256"], codec.stateHash(s), "${c["name"]}")
                n++
            }
        }
        assertTrue(n > 400, "n=$n")
    }

    @Test
    fun stageB_everyStepReplaysFromThePreviousState() {
        val failures = ArrayList<String>()
        var total = 0
        var attacks = 0
        for (c in cases) {
            val seed = c["seed"].big()
            for ((i, step) in steps(c).withIndex()) {
                total++
                val label = "${c["name"]} step $i ${enc(step["command"])}"
                try {
                    val s = EncVectors.parse(before(c, i))
                    val canonBefore = codec.canonicalText(s)
                    val cmd = EncVectors.cmd(step["command"])
                    val g = engine.streamFor(seed, s, cmd)
                    val fresh = engine.streamFor(seed, s, cmd)
                    assertEquals(step["stream"], if (cmd is AdventureCommand.Attack) "battle" else "adventure", label)
                    if (cmd is AdventureCommand.Attack && step.containsKey("battle_sha256")) {
                        attacks++
                        if (engine.battleHash(engine.buildBattle(s, cmd)) != step["battle_sha256"]) failures.add("$label: initial battle differs")
                    }
                    if (step.containsKey("error")) {
                        val e = assertFailsWith<IllegalCommand>(label) { adv.apply(s, cmd, g) }
                        if (e.message != step["error"]) failures.add("$label: message '${e.message}' want '${step["error"]}'")
                        if (EncVectors.pos(g) != EncVectors.pos(step["rng_after"])) failures.add("$label: stream moved")
                        if (EncVectors.pos(g) != EncVectors.pos(fresh)) failures.add("$label: stream not untouched")
                        if (codec.canonicalText(s) != canonBefore) failures.add("$label: state changed")
                        continue
                    }
                    val r = adv.apply(s, cmd, g)
                    when {
                        codec.canonicalText(r.state) != step["canonical"] -> failures.add("$label: canonical differs")
                        codec.stateHash(r.state) != step["sha256"] -> failures.add("$label: hash differs")
                        enc(r.events.map { it.toMap() }) != enc(step["events"]) -> failures.add("$label: events differ")
                        EncVectors.pos(g) != EncVectors.pos(step["rng_after"]) -> failures.add("$label: stream position differs")
                    }
                    if (cmd !is AdventureCommand.Attack && EncVectors.pos(g) != EncVectors.pos(fresh)) failures.add("$label: adventure stream drawn")
                } catch (e: Exception) {
                    failures.add("$label: ${e::class.simpleName}: ${e.message}")
                }
            }
        }
        if (failures.isNotEmpty()) fail("${failures.size}/$total steps fail; first: ${failures.take(5)}")
        assertTrue(attacks >= 100, "attacks=$attacks")
    }

    @Test
    fun variantsGiveThePythonVerdict() {
        val vs = doc["variants"].list().map { it.obj() }
        assertTrue(vs.size >= 25)
        var rejected = 0
        var accepted = 0
        val failures = ArrayList<String>()
        for (v in vs) {
            val s = EncVectors.parse(v["canonical"].s(), check = false)
            assertEquals(v["canonical"], codec.canonicalText(s), "${v["name"]}")
            assertEquals(v["sha256"], codec.stateHash(s), "${v["name"]}")
            val seed = v["seed"].big()
            for (a in v["attempts"].list().map { it.obj() }) {
                val label = "${v["name"]} ${enc(a["command"])}"
                val cmd = EncVectors.cmd(a["command"])
                val g = engine.streamFor(seed, s, cmd)
                val fresh = EncVectors.pos(engine.streamFor(seed, s, cmd))
                if (a.containsKey("error")) {
                    rejected++
                    val e = try { adv.apply(s, cmd, g); null } catch (e: IllegalCommand) { e }
                    when {
                        e == null -> failures.add("$label: accepted, want '${a["error"]}'")
                        e.message != a["error"] -> failures.add("$label: '${e.message}' want '${a["error"]}'")
                        EncVectors.pos(g) != fresh -> failures.add("$label: stream touched")
                    }
                } else {
                    accepted++
                    val r = adv.apply(s, cmd, g)
                    if (codec.stateHash(r.state) != a["ok"]) failures.add("$label: hash differs")
                }
                if (EncVectors.pos(g) != EncVectors.pos(a["rng_after"])) failures.add("$label: stream position differs")
            }
        }
        if (failures.isNotEmpty()) fail("${failures.size} attempts fail; first: ${failures.take(5)}")
        assertTrue(rejected > 500 && accepted >= 10, "rejected=$rejected accepted=$accepted")
    }

    @Test
    fun checkGameMatchesPython() {
        var bad = 0
        val cs = doc["check_game"].list().map { it.obj() }
        assertTrue(cs.size >= 14)
        for (c in cs) {
            val text = c["canonical"].s()
            val err = c["error"]
            if (err == null) {
                EncVectors.parse(text)
            } else {
                bad++
                val e = assertFailsWith<IllegalArgumentException>("${c["name"]}") { EncVectors.parse(text) }
                assertEquals(err as String, e.message, "${c["name"]}")
            }
            // the state is well formed apart from the content check
            val s = EncVectors.parse(text, check = false)
            assertEquals(text, codec.canonicalText(s), "${c["name"]}")
        }
        assertTrue(bad >= 10)
    }

    @Test
    fun setupsAndPoliciesMatchPython() {
        val cs = doc["setups"].list().map { it.obj() }
        assertTrue(cs.size >= 45)
        var bad = 0
        for (c in cs) {
            val name = c["name"].s()
            if (c["error"] != null) {
                bad++
                val e = assertFailsWith<IllegalArgumentException>(name) { engine.parseSetup(c["setup"]) }
                assertEquals(c["error"], e.message, name)
            } else {
                val setup = engine.parseSetup(c["setup"])
                assertEquals(c["canonical"], enc(setup.toMap()), name)
            }
        }
        assertTrue(bad >= 25, "bad=$bad")
    }

    @Test
    fun autoCommandPicksWhatPythonPicks() {
        val cs = doc["auto_cases"].list().map { it.obj() }
        assertTrue(cs.size >= 400)
        val bcodec: BattleCodec = engine.battleCodec
        val kinds = LinkedHashSet<Any?>()
        for ((i, c) in cs.withIndex()) {
            val bs = bcodec.parseState(MiniJson.parse(c["battle"].s()))
            assertEquals(c["sha256"], bcodec.stateHash(bs), "case $i")
            val cmd = engine.autoCommand(bs)
            assertEquals(enc(c["command"]), enc(BattleCodec.commandToMap(cmd)), "case $i")
            kinds.add(c["command"].obj()["type"])
        }
        assertEquals(setOf<Any?>("Begin", "Move", "Attack", "Shoot", "Defend"), kinds)
        // states where a stack can move but no move brings its head closer: Python defends
        val stalls = cs.filter { it["stall"] == true }
        assertTrue(stalls.size >= 5, "stalls=${stalls.size}")
        assertTrue(stalls.all { it["command"].obj()["type"] == "Defend" })
    }

    @Test
    fun streamsAndBattleIds() {
        val cs = doc["streams"].list().map { it.obj() }
        assertTrue(cs.size >= 7)
        for (c in cs) {
            val s = EncVectors.parse(c["canonical"].s())
            val seed = c["seed"].big()
            assertEquals(c["battle_id"], engine.battleId(s))
            val b = engine.encounterRng(seed, s)
            assertEquals(c["battle_draws"].list().map { it.big().toLong() }, List(4) { b.nextU32() })
            val a = engine.streamFor(seed, s, AdventureCommand.EndTurn(0))
            assertEquals(c["adventure_draws"].list().map { it.big().toLong() }, List(4) { a.nextU32() })
            val att = engine.streamFor(seed, s, AdventureCommand.Attack(0, "wolves"))
            assertEquals(c["battle_draws"].list().map { it.big().toLong() }, List(4) { att.nextU32() })
        }
    }

    @Test
    fun goldenHashesArePinned() {
        val g = doc["golden"].obj()
        val pin = "512b53ca56c4c5611e718b4b23129984ab5a3c0f6e0de4a7feb48c620568bd60"
        assertEquals(pin, g["pin"])
        val golden = cases.first { it["name"] == "golden" }
        // replay the whole scripted run from the initial state, not step by step from recorded states
        var s = EncVectors.parse(golden["initial"].obj()["canonical"].s())
        val winners = ArrayList<Any?>()
        for (step in steps(golden)) {
            val cmd = EncVectors.cmd(step["command"])
            val r = adv.apply(s, cmd, engine.streamFor(golden["seed"].big(), s, cmd))
            for (e in r.events) if (e is BattleFought) winners.add(e.winner)
            s = r.state
        }
        assertEquals(pin, codec.stateHash(s))
        assertEquals(3, s.day, "day")
        assertEquals(4, s.battles, "battles")
        assertEquals<List<Any?>>(listOf(0, 1, 1, 1), winners)
        assertEquals<List<Any?>>(g["winners"].list().map { it.big().toInt() }, winners)
        // the reversed-inputs run is the same game
        val rev = cases.first { it["name"] == "golden-reversed" }
        assertEquals(golden["initial"], rev["initial"])
        assertEquals(golden["steps"], rev["steps"])
        assertNotNull(g["battle_hashes"])
    }
}
