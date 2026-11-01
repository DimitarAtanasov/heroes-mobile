package h3.sim

import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

private val BATTLE_DOC by lazy { loadVector("battle_states.json") }

/**
 * Battle-port slice 3: `Battle.apply` versus every recorded step of `battle_states.json`.
 *
 * Each step is replayed on its own: the state before it is parsed from the vector (the initial
 * state or the previous step's canonical text), the `battle:<battle_id>` stream is freshly derived
 * from the case's master seed and advanced by the `rng_u32_before` raw outputs Python had consumed,
 * and the recorded command is applied. Canonical text, SHA-256, events and the generator state
 * after the step must all equal the recorded ones. Steps are grouped by the stage the vector
 * assigns (A: Begin/Move/Wait/Defend and the queue; B: Attack/Shoot without morale or luck;
 * C: steps that roll morale or luck); stage D is the rejected commands.
 */
class BattleTest {
    private val doc = BATTLE_DOC
    private val packs = doc["packs"].obj()
    private val policyPack = BattlePolicyPack(
        packs["battle_policy"].obj(),
        packs["bad_morale_numerators"].list().map { it.big().intValueExact() }, packs["rules"].obj()["morale_die"].big().intValueExact(),
    )
    private val codec = BattleCodec(policyPack)
    private val battle = Battle(Rules(rulesPack(packs["rules"].obj())), packs["rules_hash"] as String)
    private val cases = doc["cases"].list().map { it.obj() }

    private fun Any?.rat(): Rational = list().let { Rational.of(it[0].big().toLong(), it[1].big().toLong()) }

    private fun rulesPack(p: Map<String, Any?>): RulesPack {
        fun table(k: String) = p[k].list().map { it.rat() }
        fun longs(k: String) = p[k].list().map { it.big().toLong() }
        return RulesPack(
            adBonusPerPoint = p["ad_bonus_per_point"].rat(),
            adBonusCap = p["ad_bonus_cap"].rat(),
            daPenaltyPerPoint = p["da_penalty_per_point"].rat(),
            daPenaltyCap = p["da_penalty_cap"].rat(),
            offense = table("offense"),
            archery = table("archery"),
            armorer = table("armorer"),
            hateBonus = p["hate_bonus"].rat(),
            luckBonus = p["luck_bonus"].rat(),
            half = p["half"].rat(),
            moraleDie = p["morale_die"].big().toLong(),
            badMoraleNumerators = longs("bad_morale_numerators"),
            vcmiBadMoraleNumerators = longs("vcmi_bad_morale_numerators"),
        )
    }

    private fun enc(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

    private fun parse(text: String): BattleState = codec.parseState(MiniJson.parse(text))

    private fun steps(c: Map<String, Any?>) = c["steps"].list().map { it.obj() }

    /** The case's stream, freshly derived as Python did, advanced by [skip] raw outputs. */
    private fun stream(c: Map<String, Any?>, skip: Int): Pcg32 {
        val sc = c["scenario"].obj()
        val g = RngStreams.derive(sc["master_seed"].big(), sc["stream_domain"] as String, sc["stream_id"] as String)
        assertEquals("battle:${sc["battle_id"]}", sc["stream_domain"])
        repeat(skip) { g.nextU32() }
        return g
    }

    private fun stateBefore(c: Map<String, Any?>, i: Int): String =
        if (i < 0) c["initial"].obj()["canonical"] as String else steps(c)[i]["canonical"] as String

    /** Compares one applied step with its record; returns null on a match, else what differs. */
    private fun compare(step: Map<String, Any?>, r: ApplyResult, g: Pcg32): String? {
        val text = codec.canonicalText(r.state)
        if (text != step["canonical"]) return "canonical differs"
        if (codec.stateHash(r.state) != step["sha256"]) return "sha256 differs"
        val got = r.events.map { enc(BattleCodec.eventToMap(it)) }
        val want = step["events"].list().map { enc(it) }
        if (got != want) return "events differ: got $got want $want"
        if (g.state != step["rng_state_after"].u64()) return "rng state differs (draw count or order)"
        return null
    }

    private data class Outcome(val label: String, val stage: String, val error: String?)

    private fun replayStep(c: Map<String, Any?>, i: Int): Outcome {
        val step = steps(c)[i]
        val label = "${c["name"]} step $i ${step["command"].obj()["type"]}"
        val stage = step["stage"] as String
        val g = stream(c, step["rng_u32_before"].big().intValueExact())
        val r = try {
            battle.apply(parse(stateBefore(c, i - 1)), BattleCodec.parseCommand(step["command"]), g.asDrawSource())
        } catch (e: RuntimeException) {
            return Outcome(label, stage, "threw $e")
        }
        return Outcome(label, stage, compare(step, r, g))
    }

    private val allOutcomes: List<Outcome> by lazy {
        cases.flatMap { c -> steps(c).indices.map { replayStep(c, it) } }
    }

    private fun checkStage(stage: String, minSteps: Int) {
        val mine = allOutcomes.filter { it.stage == stage }
        val bad = mine.filter { it.error != null }
        println("stage $stage: ${mine.size - bad.size}/${mine.size} steps match")
        assertTrue(mine.size >= minSteps, "stage $stage has only ${mine.size} steps")
        if (bad.isNotEmpty()) fail("stage $stage: ${bad.size} mismatches, first: ${bad.take(10).map { "${it.label}: ${it.error}" }}")
    }

    @Test
    fun stageA_beginMoveWaitDefendAndTurnQueue() = checkStage("A", 150)

    @Test
    fun stageB_attackShootDamageAndRetaliation() = checkStage("B", 150)

    @Test
    fun stageC_moraleAndLuck() = checkStage("C", 500)

    @Test
    fun everyRecordedStepHasAStageAndAllCommandAndEventTypesOccur() {
        val total = cases.sumOf { steps(it).size }
        assertEquals(total, allOutcomes.size)
        assertEquals(setOf("A", "B", "C"), allOutcomes.map { it.stage }.toSet())
        println("all stages: ${allOutcomes.count { it.error == null }}/$total steps match")
        assertTrue(total >= 1000, "steps=$total")
        val all = cases.flatMap(::steps)
        assertEquals(setOf("Begin", "Move", "Attack", "Shoot", "Wait", "Defend"), all.map { it["command"].obj()["type"] }.toSet())
        assertEquals(12, all.flatMap { s -> s["events"].list().map { it.obj()["type"] } }.toSet().size)
    }

    /** Whole playouts on one stream, each step from the engine's own previous state. */
    @Test
    fun playoutsReplayOnOneStream() {
        for (c in cases) {
            var state = parse(c["initial"].obj()["canonical"] as String)
            assertEquals(c["initial"].obj()["sha256"], codec.stateHash(state))
            val g = stream(c, 0)
            for ((i, step) in steps(c).withIndex()) {
                val r = battle.apply(state, BattleCodec.parseCommand(step["command"]), g.asDrawSource())
                val err = compare(step, r, g)
                if (err != null) fail("${c["name"]} step $i: $err")
                state = r.state
            }
            val last = steps(c).last()
            assertEquals(last["sha256"], codec.stateHash(state))
        }
    }

    @Test
    fun goldenPlayoutReachesThePinnedHash() {
        val c = cases.single { it["name"] == "golden-scripted" }
        var state = parse(c["initial"].obj()["canonical"] as String)
        val g = stream(c, 0)
        for (step in steps(c)) state = battle.apply(state, BattleCodec.parseCommand(step["command"]), g.asDrawSource()).state
        assertTrue(state.winner != null)
        // tests/test_battle.py GoldenTest.PINNED (ADR-0001 re-pin history).
        assertEquals("fbe9015bde1b6e5c165c08fc1604f98ea7c3cdf09cc38528ec2fda496f040e2b", codec.stateHash(state))
    }

    @Test
    fun stageD_illegalCommandsTouchNeitherStateNorStream() {
        val illegal = doc["illegal_cases"].list().map { it.obj() }
        val byName = cases.associateBy { it["name"] as String }
        val bad = ArrayList<String>()
        for ((k, ic) in illegal.withIndex()) {
            val c = byName.getValue(ic["case"] as String)
            var state = parse(stateBefore(c, ic["after_step"].big().intValueExact()))
            (ic["rules_hash"] as String?)?.let { state = state.copy(rulesHash = it) }
            val g = stream(c, ic["rng_u32_before"].big().intValueExact())
            val rngBefore = g.state
            val label = "illegal $k (${ic["case"]} after ${ic["after_step"]}, ${enc(ic["command"])})"
            // The state is immutable, so "unchanged" is checked where it can fail: the state the
            // command is applied to is the recorded one, and the engine makes no draw call at all.
            if (ic["rules_hash"] == null && codec.canonicalText(state) != stateBefore(c, ic["after_step"].big().intValueExact())) {
                bad += "$label: parsed state is not the recorded state"
            }
            var draws = 0
            val counting = object : DrawSource {
                override fun randint(lo: Long, hi: Long): Long { draws++; return g.randint(lo, hi) }
                override fun chance(num: Long, den: Long): Boolean { draws++; return g.chance(num, den) }
            }
            try {
                battle.apply(state, BattleCodec.parseCommand(ic["command"]), counting)
                bad += "$label: accepted"
            } catch (e: IllegalCommand) {
                if (e::class.simpleName != ic["error"]) bad += "$label: ${e::class.simpleName} != ${ic["error"]}"
                if (e.message != ic["message"]) bad += "$label: message '${e.message}' != '${ic["message"]}'"
            }
            if (draws != 0) bad += "$label: $draws draw calls before the rejection"
            if (g.state != rngBefore) bad += "$label: rng advanced"
        }
        println("stage D: ${illegal.size - bad.size}/${illegal.size} illegal cases match")
        assertTrue(illegal.size >= 1000, "illegal=${illegal.size}")
        assertTrue(illegal.any { it["error"] == "PackMismatch" })
        if (bad.isNotEmpty()) fail("stage D: ${bad.size} mismatches, first: ${bad.take(10)}")
    }

    @Test
    fun applyDamageMatchesTheDocumentedCases() {
        assertEquals(Battle.Companion.Damaged(0L, 0L, 0L), Battle.applyDamage(0L, 0L, 10L, 5L))
        assertEquals(Battle.Companion.Damaged(3L, 7L, 0L), Battle.applyDamage(3L, 10L, 10L, 3L))
        assertEquals(Battle.Companion.Damaged(2L, 10L, 1L), Battle.applyDamage(3L, 10L, 10L, 10L))
        assertEquals(Battle.Companion.Damaged(0L, 0L, 3L), Battle.applyDamage(3L, 4L, 10L, 99L))
        for (bad in listOf(
            { Battle.applyDamage(-1L, 0L, 10L, 1L) }, { Battle.applyDamage(1L, 0L, 10L, 1L) },
            { Battle.applyDamage(1L, 11L, 10L, 1L) }, { Battle.applyDamage(1L, 1L, 10L, -1L) },
            { Battle.applyDamage(0L, 1L, 10L, 1L) }, { Battle.applyDamage(1L, 1L, 0L, 1L) },
        )) {
            try { bad(); fail("expected IllegalArgumentException") } catch (_: IllegalArgumentException) {}
        }
    }

    @Test
    fun streamDerivationIsTheNamedBattleStream() {
        // battle_rng(seed, id) == derive_stream(seed, "battle:<id>"): the recorded first step of
        // every case starts from a fresh stream (zero draws consumed before Begin).
        for (c in cases) assertEquals(BigInteger.ZERO, steps(c)[0]["rng_u32_before"].big())
    }
    @Test
    fun capCaseDealsMoreThanIntDamageAsALong() {
        val c = cases.single { it["name"] == "cap" }
        var state = parse(c["initial"].obj()["canonical"] as String)
        val g = stream(c, 0)
        val dmg = ArrayList<Long>()
        for (step in steps(c)) {
            val r = battle.apply(state, BattleCodec.parseCommand(step["command"]), g.asDrawSource())
            r.events.filterIsInstance<BattleEvent.DamageDealt>().forEach { dmg.add(it.damage) }
            state = r.state
        }
        assertTrue(dmg.isNotEmpty() && dmg.max() > Int.MAX_VALUE.toLong(), "damage=$dmg")
        val recorded = steps(c).flatMap { it["events"].list() }.map { it.obj() }
            .filter { it["type"] == "DamageDealt" }.map { it["damage"].big().longValueExact() }
        assertEquals(recorded, dmg)
    }

    @Test
    fun badMoraleTableAboveTheDieIsRefusedBeforeAnyDraw() {
        // A pack without the morale die cannot bound the table at parse time; apply refuses it
        // before the first draw (it used to throw inside activateNext after the strike draws).
        val noDie = BattleCodec(BattlePolicyPack(packs["battle_policy"].obj(),
            packs["bad_morale_numerators"].list().map { it.big().intValueExact() }))
        // The cap case has no negative morale, so without the guard Begin would succeed.
        val c = cases.single { it["name"] == "cap" }
        val m = MiniJson.parse(c["initial"].obj()["canonical"] as String).obj().toMutableMap()
        val die = packs["rules"].obj()["morale_die"].big().intValueExact()
        m["policy"] = m["policy"].obj() + ("bad_morale_table" to listOf(1, 2, die + 1))
        val state = noDie.parseState(m)
        var draws = 0
        val src = object : DrawSource {
            override fun randint(lo: Long, hi: Long): Long { draws++; return lo }
            override fun chance(num: Long, den: Long): Boolean { draws++; return false }
        }
        val e = kotlin.test.assertFailsWith<IllegalArgumentException> { battle.apply(state, BattleCommand.Begin, src) }
        assertEquals("bad_morale_table needs 3 integers in 0..$die", e.message)
        assertEquals(0, draws)
        // With the die, the parse itself refuses it.
        kotlin.test.assertFailsWith<IllegalArgumentException> { codec.parseState(m) }
    }
}
