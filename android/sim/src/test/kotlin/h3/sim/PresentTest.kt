package h3.sim

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Presenter view v2 (`Present.kt`) versus `present.json` (docs/specs/conformance-present.md).
 * States come from `battle_states.json` (same case names, index 0 = initial state, i+1 = after
 * step i). Every view text must be byte-identical to Python's `view_json`; the state hash must
 * be unchanged by building a view; tap candidates are checked for all 187 hexes of sampled states.
 */
private object Shared {
    val states = loadVector("battle_states.json")
    val present = loadVector("present.json")
    private var cs: Map<String, List<BattleState>>? = null
    private var en: List<Triple<String, Map<String, Any?>, BattleState>>? = null

    @Synchronized
    fun caseStates(codec: BattleCodec): Map<String, List<BattleState>> = cs ?: states["cases"].list().map { it.obj() }.associate { c ->
        val recs = listOf(c["initial"].obj()) + c["steps"].list().map { it.obj() }
        (c["name"] as String) to recs.map { codec.parseState(MiniJson.parse(it["canonical"] as String)) }
    }.also { cs = it }

    @Synchronized
    fun entries(
        codec: BattleCodec, caseStates: Map<String, List<BattleState>>, present: Map<String, Any?>,
    ): List<Triple<String, Map<String, Any?>, BattleState>> = en ?: present["cases"].list().map { it.obj() }.flatMap { c ->
        val name = c["name"] as String
        val sts = caseStates.getValue(name)
        val list = c["states"].list().map { it.obj() }
        assertEquals(sts.size, list.size, "$name state count")
        list.map { Triple(name, it, sts[it["index"].big().toInt()]) }
    }.also { en = it }
}

class PresentTest {
    private val states get() = Shared.states
    private val present get() = Shared.present
    private val packs = states["packs"].obj()
    private val codec = BattleCodec(
        BattlePolicyPack(packs["battle_policy"].obj(), packs["bad_morale_numerators"].list().map { it.big().toInt() }),
    )
    private val battle = Battle(Rules(rulesPack(packs["rules"].obj())), packs["rules_hash"] as String)
    private val pres = Present(battle)

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

    private val caseStates: Map<String, List<BattleState>> get() = Shared.caseStates(codec)
    private val entries: List<Triple<String, Map<String, Any?>, BattleState>>
        get() = Shared.entries(codec, caseStates, present)

    @Test
    fun viewJsonIsByteIdenticalAndHashesMatch() {
        var n = 0
        var texts = 0
        for ((name, e, st) in entries) {
            val label = "$name #${e["index"]}"
            val h0 = codec.stateHash(st)
            assertEquals(e["state_sha256"], h0, "$label state hash (wrong state loaded)")
            val text = pres.viewJson(st)
            assertEquals(e["view_sha256"], Canonical.sha256Hex(text.toByteArray(Charsets.US_ASCII)), "$label view sha256")
            val want = e["view_json"] as String?
            if (want != null) {
                assertEquals(want, text, "$label view text")
                texts++
            }
            assertEquals(h0, codec.stateHash(st), "$label hash changed by view")
            assertEquals(text, pres.viewJson(st), "$label not deterministic")
            n++
        }
        println("views: $n sha256 matched, $texts full texts byte-identical")
        assertTrue(n >= 1300, "views=$n")
        assertTrue(texts >= 150, "texts=$texts")
    }

    @Test
    fun viewDoesNotMutateTheState() {
        for ((_, e, st) in entries.filterIndexed { i, _ -> i % 7 == 0 }) {
            val copy = st.copy()
            pres.view(st)
            pres.candidateActions(st, Pair(8, 5))
            assertEquals(copy, st, "state ${e["index"]}")
        }
    }

    @Test
    fun tapCandidatesMatchForEveryHex() {
        var states = 0
        var listed = 0
        for ((name, e, st) in entries) {
            val taps = e["taps"] ?: continue
            val byHex = taps.list().map { it.obj() }.associateBy { Pair(it["hex"].list()[0].big().toInt(), it["hex"].list()[1].big().toInt()) }
            for (r in 0 until Hex.HEIGHT) for (c in 0 until Hex.WIDTH) {
                val label = "$name #${e["index"]} hex ($c,$r)"
                val got = pres.candidateCommands(st, Pair(c, r)).map { enc(pres.commandToDict(it)) }
                val ent = pres.candidateActions(st, Pair(c, r))
                val want = byHex[Pair(c, r)]
                if (want == null) {
                    assertEquals(emptyList(), got, label)
                    assertNull(ent, label)
                } else {
                    assertEquals(want["commands"].list().map { enc(it) }, got, "$label commands")
                    val sha = want["action_sha256"]
                    if (sha == null) assertNull(ent, label)
                    else assertEquals(sha, Canonical.sha256Hex(enc(ent).toByteArray(Charsets.US_ASCII)), "$label action")
                    listed++
                }
            }
            states++
        }
        println("tap states: $states, non-empty hexes: $listed")
        assertTrue(states >= 350 && listed >= 20000, "states=$states listed=$listed")
    }

    @Test
    fun viewShapeV2() {
        var moves = 0
        var odd = 0
        for ((_, _, st) in entries) {
            val v = pres.view(st)
            assertEquals(2, v["view_version"])
            val g = v["grid"].obj()
            assertEquals(st.policy.rowOffset, g["row_offset"])
            if (st.policy.rowOffset == "odd") odd++
            for (h in v["actions"].obj()["by_hex"].list().map { it.obj() }) {
                val m = h["move"] ?: continue
                val path = m.obj()["path"].list()
                assertEquals(h["hex"], path.last())
                moves++
            }
        }
        assertTrue(moves > 500 && odd > 0, "moves=$moves odd=$odd")
    }
}
