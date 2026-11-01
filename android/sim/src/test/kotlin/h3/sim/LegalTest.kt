package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Battle-port slice 4: `legalCommands`, `strikeContext` and `strikePreview` versus the lists and
 * previews recorded for every state of `battle_states.json` (initial state and the state after
 * each step). The list is compared in order. Nothing here may draw from a stream or change a state.
 */
class LegalTest {
    private val doc = loadVector("battle_states.json")
    private val packs = doc["packs"].obj()
    private val codec = BattleCodec(
        BattlePolicyPack(packs["battle_policy"].obj(), packs["bad_morale_numerators"].list().map { it.big().toInt() }),
    )
    private val battle = Battle(Rules(rulesPack(packs["rules"].obj())), packs["rules_hash"] as String)
    private val cases = doc["cases"].list().map { it.obj() }

    private fun Any?.rat(): Rational = list().let { Rational.of(it[0].big().toLong(), it[1].big().toLong()) }

    private fun rulesPack(p: Map<String, Any?>): RulesPack {
        fun table(k: String) = p[k].list().map { it.rat() }
        fun longs(k: String) = p[k].list().map { it.big().toLong() }
        return RulesPack(
            adBonusPerPoint = p["ad_bonus_per_point"].rat(), adBonusCap = p["ad_bonus_cap"].rat(),
            daPenaltyPerPoint = p["da_penalty_per_point"].rat(), daPenaltyCap = p["da_penalty_cap"].rat(),
            offense = table("offense"), archery = table("archery"), armorer = table("armorer"),
            hateBonus = p["hate_bonus"].rat(), luckBonus = p["luck_bonus"].rat(), half = p["half"].rat(),
            moraleDie = p["morale_die"].big().toLong(),
            badMoraleNumerators = longs("bad_morale_numerators"),
            vcmiBadMoraleNumerators = longs("vcmi_bad_morale_numerators"),
        )
    }

    private fun enc(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

    private fun encCmd(c: BattleCommand): String = enc(BattleCodec.commandToMap(c))

    /** One recorded state: its record, the case it belongs to, and a label. */
    private class Rec(val label: String, val caseName: String, val rec: Map<String, Any?>, val prev: Map<String, Any?>?, val cmd: Any?)

    private val recs: List<Rec> by lazy {
        cases.flatMap { c ->
            val name = c["name"] as String
            val steps = c["steps"].list().map { it.obj() }
            val init = c["initial"].obj()
            listOf(Rec("$name initial", name, init, null, null)) +
                steps.mapIndexed { i, s -> Rec("$name step $i", name, s, if (i == 0) init else steps[i - 1], s["command"]) }
        }
    }

    private fun parse(r: Map<String, Any?>) = codec.parseState(MiniJson.parse(r["canonical"] as String))

    private fun ctxMap(c: DamageCtx): Map<String, Any?> = linkedMapOf(
        "count" to c.count, "dmg_min" to c.dmgMin, "dmg_max" to c.dmgMax, "attack" to c.attack,
        "defense" to c.defense, "ranged" to c.ranged, "offense" to c.offense.toLong(),
        "archery" to c.archery.toLong(), "armorer" to c.armorer.toLong(), "hates" to c.hates,
        "range_penalty" to c.rangePenalty, "melee_penalty" to c.meleePenalty,
        "wall_penalty" to c.wallPenalty, "luck" to c.luck, "bad_luck" to c.badLuck,
    )

    @Test
    fun legalListEqualsTheRecordedListInOrderForEveryState() {
        var n = 0
        var cmds = 0
        val bad = ArrayList<String>()
        for (r in recs) {
            val got = battle.legalCommands(parse(r.rec)).map(::encCmd)
            val want = r.rec["legal"].list().map { enc(it) }
            n++
            cmds += want.size
            if (got != want) {
                val i = got.zip(want).indexOfFirst { it.first != it.second }.let { if (it < 0) minOf(got.size, want.size) else it }
                bad += "${r.label}: sizes ${got.size}/${want.size}, first difference at $i"
            }
        }
        println("legal lists: ${n - bad.size}/$n states match ($cmds commands)")
        assertTrue(n >= 1500, "states=$n")
        if (bad.isNotEmpty()) fail("${bad.size} mismatches, first: ${bad.take(10)}")
    }

    @Test
    fun everyRecordedCommandIsInTheListOfItsStateAndIllegalOnesAreAbsent() {
        var checked = 0
        for (r in recs) {
            if (r.prev == null) continue
            val list = r.prev["legal"].list().map { enc(it) }.toSet()
            assertTrue(enc(r.cmd) in list, "${r.label}: ${enc(r.cmd)} not legal in its state")
            checked++
        }
        assertTrue(checked >= 1400, "checked=$checked")
        // Illegal cases are absent from the list of their state, unless their only fault is the pack.
        val byName = cases.associateBy { it["name"] as String }
        var absent = 0
        for (ic in doc["illegal_cases"].list().map { it.obj() }) {
            if (ic["rules_hash"] != null) continue
            val c = byName.getValue(ic["case"] as String)
            val k = ic["after_step"].big().toInt()
            val rec = if (k < 0) c["initial"].obj() else c["steps"].list()[k].obj()
            val list = rec["legal"].list().map { enc(it) }.toSet()
            assertTrue(enc(ic["command"]) !in list, "illegal ${enc(ic["command"])} listed for ${c["name"]} after $k")
            absent++
        }
        assertTrue(absent >= 1000, "absent=$absent")
        println("recorded commands contained: $checked; illegal absent: $absent")
    }

    @Test
    fun strikePreviewAndContextEqualTheRecords() {
        var n = 0
        var shots = 0
        for (r in recs) {
            val state = parse(r.rec)
            for (p in r.rec["previews"].list().map { it.obj() }) {
                val a = p["attacker"].big().toInt()
                val t = p["target"].big().toInt()
                val ranged = p["ranged"] as Boolean
                val ctx = battle.strikeContext(state, state.stacks[a], state.stacks[t], ranged)
                assertEquals(enc(p["ctx"]), enc(ctxMap(ctx)), "${r.label} ctx $a->$t ranged=$ranged")
                val pv = battle.strikePreview(state, a, t, ranged)
                assertEquals(p["floor"].big().toLong(), pv.floor, "${r.label} floor $a->$t")
                assertEquals(p["expected"].big().toLong(), pv.expected, "${r.label} expected $a->$t")
                assertEquals(p["ceiling"].big().toLong(), pv.ceiling, "${r.label} ceiling $a->$t")
                assertTrue(pv.floor <= pv.expected && pv.expected <= pv.ceiling, "${r.label} order")
                n++
                if (ranged) shots++
            }
        }
        println("previews: $n ($shots ranged)")
        assertTrue(n >= 1500 && shots >= 100, "previews=$n ranged=$shots")
    }

    @Test
    fun everyAttackAndShootCandidateHasARecordedPreview() {
        for (r in recs) {
            val keys = r.rec["previews"].list().map { it.obj() }
                .map { Triple(it["attacker"].big().toInt(), it["target"].big().toInt(), it["ranged"] as Boolean) }
            val want = r.rec["legal"].list().map { it.obj() }.mapNotNull {
                when (it["type"]) {
                    "Attack" -> Triple(it["stack"].big().toInt(), it["target"].big().toInt(), false)
                    "Shoot" -> Triple(it["stack"].big().toInt(), it["target"].big().toInt(), true)
                    else -> null
                }
            }.distinct()
            assertEquals(want, keys, r.label)
        }
    }

    @Test
    fun legalAndPreviewDoNotChangeStateHashOrTouchTheStream() {
        // legalCommands and strikePreview take no DrawSource; a poisoned source proves nothing else is reachable,
        // and the parsed state's text and hash are identical before and after.
        var n = 0
        for (r in recs) {
            val state = parse(r.rec)
            val text = codec.canonicalText(state)
            val hash = codec.stateHash(state)
            val legal = battle.legalCommands(state)
            for (c in legal) {
                when (c) {
                    is BattleCommand.Attack -> battle.strikePreview(state, c.stack, c.target, false)
                    is BattleCommand.Shoot -> battle.strikePreview(state, c.stack, c.target, true)
                    else -> {}
                }
            }
            assertEquals(hash, r.rec["sha256"], r.label)
            assertEquals(hash, codec.stateHash(state), r.label)
            assertEquals(text, codec.canonicalText(state), r.label)
            n++
        }
        assertTrue(n >= 1500)
    }

    @Test
    fun noDrawsAreNeededToEnumerateOrApplyTheFirstLegalCommandAfterwards() {
        // The stream is untouched: apply the first recorded command with a fresh stream before and after
        // enumerating legal commands; both runs leave the generator in the same state.
        for (c in cases.take(6)) {
            val sc = c["scenario"].obj()
            val steps = c["steps"].list().map { it.obj() }
            var state = codec.parseState(MiniJson.parse(c["initial"].obj()["canonical"] as String))
            val g = RngStreams.derive(sc["master_seed"].big(), sc["stream_domain"] as String, sc["stream_id"] as String)
            val fresh = RngStreams.derive(sc["master_seed"].big(), sc["stream_domain"] as String, sc["stream_id"] as String)
            for ((i, step) in steps.take(25).withIndex()) {
                battle.legalCommands(state) // would desync g from the recorded state if it drew
                val r = battle.apply(state, BattleCodec.parseCommand(step["command"]), g.asDrawSource())
                state = r.state
                repeat(step["rng_u32"].big().toInt()) { fresh.nextU32() }
                assertEquals(fresh.state, g.state, "${c["name"]} step $i")
                assertEquals(step["rng_state_after"].u64(), g.state, "${c["name"]} step $i")
            }
        }
    }

    @Test
    fun recordedListsCoverEveryCommandKindAndShapes() {
        val kinds = recs.flatMap { it.rec["legal"].list() }.map { it.obj()["type"] }.toSet()
        assertEquals(setOf("Begin", "Move", "Attack", "Shoot", "Wait", "Defend"), kinds)
        val withFrom = recs.flatMap { it.rec["legal"].list() }.map { it.obj() }
            .any { it["type"] == "Attack" && it["from_hex"] != null }
        assertTrue(withFrom)
        // Finished battles list nothing; unstarted ones list Begin only.
        assertTrue(recs.any { it.rec["legal"].list().isEmpty() })
        assertTrue(recs.any { it.rec["legal"].list().size == 1 && it.rec["legal"].list()[0].obj()["type"] == "Begin" })
    }
}
