package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * Greedy battle AI versus `battle_ai.json` (docs/specs/conformance-ai.md): every recorded
 * decision point (stateless `choose` on the canonical state), and whole AI-vs-AI games replayed
 * with the stateful chooser (per-side Defend counts, both choosers at every step), ending in the
 * recorded final state hash. The AI is never handed the battle stream; the test also checks that
 * the stream is exactly where Python left it.
 */
class BattleAiTest {
    private val doc = loadVector("battle_ai.json")
    private val packs = doc["packs"].obj()
    private val codec = BattleCodec(
        BattlePolicyPack(packs["battle_policy"].obj(), packs["bad_morale_numerators"].list().map { it.big().toInt() }),
    )
    private val battle = Battle(Rules(rulesPack(packs["rules"].obj())), packs["rules_hash"] as String)
    private val ai = BattleAi(battle, codec)
    private val games = doc["games"].list().map { it.obj() }

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
    private fun parse(text: String): BattleState = codec.parseState(MiniJson.parse(text))
    private fun steps(g: Map<String, Any?>) = g["steps"].list().map { it.obj() }

    @Test
    fun statelessChooseMatchesEveryRecordedState() {
        var n = 0
        val bad = ArrayList<String>()
        for (g in games) {
            for ((i, s) in steps(g).withIndex()) {
                val text = s["canonical"] as String? ?: continue
                val st = parse(text)
                n++
                if (codec.stateHash(st) != s["sha256"]) bad += "${g["name"]} $i: hash"
                val before = codec.canonicalText(st)
                val got = encCmd(ai.choose(st))
                if (got != enc(s["stateless"])) bad += "${g["name"]} $i: got $got want ${enc(s["stateless"])}"
                if (codec.canonicalText(st) != before) bad += "${g["name"]} $i: choose changed the state"
            }
        }
        println("AI decision points: ${n - bad.size}/$n match")
        assertTrue(n >= 300, "decision points=$n")
        if (bad.isNotEmpty()) fail("${bad.size} mismatches, first: ${bad.take(8)}")
    }

    private fun replay(g: Map<String, Any?>): Int {
        val name = g["name"] as String
        val sc = g["scenario"].obj()
        val brng = RngStreams.derive(sc["master_seed"].big(), sc["stream_domain"] as String, sc["stream_id"] as String)
        val greedy = ai.GreedyAi(sc["ai_seed"].big().toLong())
        var state = parse(g["initial"].obj()["canonical"] as String)
        assertEquals(g["initial"].obj()["sha256"], codec.stateHash(state), name)
        var n = 0
        for ((i, s) in steps(g).withIndex()) {
            val label = "$name step $i"
            assertEquals(s["sha256"], codec.stateHash(state), "$label state hash")
            val active = state.active
            val side = if (active == null) null else state.stacks[active].side
            assertEquals(s["side"]?.big()?.toInt(), side, "$label side")
            assertEquals(s["defends_before"].big().toInt(), greedy.defends(side ?: 0), "$label defends before")
            val streamBefore = brng.state
            val stateless = ai.choose(state)
            val stateful = greedy.choose(state, side)
            assertEquals(streamBefore, brng.state, "$label: AI touched the battle stream")
            assertEquals(enc(s["stateless"]), encCmd(stateless), "$label stateless")
            assertEquals(enc(s["stateful"]), encCmd(stateful), "$label stateful")
            val applied = BattleCodec.parseCommand(s["applied"])
            state = battle.apply(state, applied, brng.asDrawSource()).state
            n++
        }
        val fin = g["final"].obj()
        assertEquals(fin["steps"].big().toInt(), n, "$name steps")
        assertEquals(fin["sha256"], codec.stateHash(state), "$name final state hash")
        assertEquals(fin["winner"]?.big()?.toInt(), state.winner, "$name winner")
        assertEquals(fin["round"].big().toInt(), state.round, "$name round")
        assertEquals(fin["rng_state"].u64(), brng.state, "$name battle stream position")
        assertEquals(fin["rng_inc"].u64(), brng.inc, "$name battle stream increment")
        return n
    }

    @Test
    fun wholeGamesReproducePythonDecisionsAndFinalHashes() {
        var steps = 0
        var finished = 0
        for (g in games) {
            steps += replay(g)
            if (g["final"].obj()["winner"] != null) finished++
        }
        println("AI games: ${games.size} replayed, $steps decisions, $finished finished with a winner")
        assertTrue(games.size >= 60, "games=${games.size}")
        assertTrue(steps >= 2000, "steps=$steps")
        assertTrue(finished >= 40, "finished=$finished")
    }

    @Test
    fun defendCapAndStallBranchesAreCovered() {
        val seen = HashSet<String>()
        for (g in games) for (s in steps(g)) {
            seen += "${s["defends_before"].big()}:${s["stateful"].obj()["type"]}"
            seen += "sl:${s["stateless"].obj()["type"]}"
        }
        for (k in listOf("0:Defend", "1:Defend", "2:Wait", "2:Move", "0:Attack", "0:Shoot", "sl:Defend", "sl:Wait")) {
            assertTrue(k in seen, "missing $k in $seen")
        }
        assertEquals(2, BattleAi.MAX_DEFENDS)
        assertEquals(doc["max_defends"].big().toInt(), BattleAi.MAX_DEFENDS)
        assertEquals(doc["stateless_defend_round"].big().toInt(), BattleAi.STATELESS_DEFEND_ROUND)
    }

    @Test
    fun beginBeforeStartAndWrongSideIsRejected() {
        val g = games.first()
        val st = parse(g["initial"].obj()["canonical"] as String)
        assertEquals(BattleCommand.Begin, ai.choose(st))
        assertEquals(BattleCommand.Begin, ai.GreedyAi(1).choose(st))
        val started = battle.apply(st, BattleCommand.Begin, RngStreams.derive(1, "x").asDrawSource()).state
        val side = started.stacks[started.active!!].side
        ai.choose(started, side)
        assertFailsWith<IllegalArgumentException> { ai.choose(started, 1 - side) }
    }
}
