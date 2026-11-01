package h3.sim

import java.lang.reflect.Modifier
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/** Battle-port slice 2: typed state, commands and events versus `battle_states.json` (no apply logic). */
class BattleStateTest {
    private val doc = loadVector("battle_states.json")
    private val packs = doc["packs"].obj()
    private val pack = BattlePolicyPack(
        packs["battle_policy"].obj(),
        packs["bad_morale_numerators"].list().map { it.big().intValueExact() }, packs["rules"].obj()["morale_die"].big().intValueExact(),
    )
    private val codec = BattleCodec(pack)

    private fun enc(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

    private fun checkState(text: String, sha: String, label: String) {
        val state = codec.parseState(MiniJson.parse(text))
        assertEquals(text, codec.canonicalText(state), label)
        assertEquals(sha, codec.stateHash(state), label)
        assertEquals(sha, Canonical.sha256Hex(text.toByteArray(Charsets.US_ASCII)), label)
        // Parsing the typed model's own map gives the same model.
        assertEquals(state, codec.parseState(codec.toMap(state)), label)
    }

    @Test
    fun everyStepRoundTripsByteIdentical() {
        val cases = doc["cases"].list()
        assertTrue(cases.size >= 10)
        var steps = 0
        val commandTypes = HashSet<String>()
        val eventTypes = HashSet<String>()
        for (c in cases) {
            val o = c.obj()
            val name = o["name"] as String
            val init = o["initial"].obj()
            checkState(init["canonical"] as String, init["sha256"] as String, "$name initial")
            for ((i, s) in o["steps"].list().withIndex()) {
                val so = s.obj()
                val label = "$name step $i"
                checkState(so["canonical"] as String, so["sha256"] as String, label)

                val cmd = so["command"]
                commandTypes += cmd.obj()["type"] as String
                assertEquals(enc(cmd), enc(BattleCodec.commandToMap(BattleCodec.parseCommand(cmd))), "$label command")

                for ((j, e) in so["events"].list().withIndex()) {
                    eventTypes += e.obj()["type"] as String
                    assertEquals(enc(e), enc(BattleCodec.eventToMap(BattleCodec.parseEvent(e))), "$label event $j")
                }
                steps++
            }
        }
        assertTrue(steps >= 300, "steps=$steps")
        assertEquals(setOf("Begin", "Move", "Attack", "Shoot", "Wait", "Defend"), commandTypes)
        assertEquals(12, eventTypes.size, "$eventTypes")
    }

    @Test
    fun staticCommandAndEventCases() {
        val cmds = doc["command_cases"].list()
        val evs = doc["event_cases"].list()
        assertTrue(cmds.size >= 7 && evs.size >= 15)
        for (c in cmds) assertEquals(enc(c), enc(BattleCodec.commandToMap(BattleCodec.parseCommand(c))))
        for (e in evs) assertEquals(enc(e), enc(BattleCodec.eventToMap(BattleCodec.parseEvent(e))))
        // Both Attack forms are present and typed differently.
        val attacks = cmds.map { BattleCodec.parseCommand(it) }.filterIsInstance<BattleCommand.Attack>()
        assertEquals(setOf(true, false), attacks.map { it.fromHex == null }.toSet())
    }

    private fun snakeToCamel(s: String): String {
        val parts = s.split('_')
        return parts[0] + parts.drop(1).joinToString("") { it.replaceFirstChar(Char::uppercase) }
    }

    /** Declared (non-static) Java fields = Kotlin constructor properties. */
    private fun props(cls: Class<*>): Set<String> =
        cls.declaredFields.filter { !Modifier.isStatic(it.modifiers) }.map { it.name }.toSet()

    @Test
    fun typedModelCoversEveryPythonField() {
        val schema = doc["schema"].obj().mapValues { (_, v) -> v.list().map { it as String } }
        val models = mapOf(
            "BattleState" to BattleState::class.java, "BattlePolicy" to BattlePolicy::class.java,
            "Stack" to BattleStack::class.java, "Creature" to BattleCreature::class.java,
            "Hero" to BattleHero::class.java,
            "Move" to BattleCommand.Move::class.java, "Attack" to BattleCommand.Attack::class.java,
            "Shoot" to BattleCommand.Shoot::class.java, "Wait" to BattleCommand.Wait::class.java,
            "Defend" to BattleCommand.Defend::class.java,
            "BattleStarted" to BattleEvent.BattleStarted::class.java, "RoundStarted" to BattleEvent.RoundStarted::class.java,
            "TurnStarted" to BattleEvent.TurnStarted::class.java, "MoraleFrozen" to BattleEvent.MoraleFrozen::class.java,
            "MoraleBoost" to BattleEvent.MoraleBoost::class.java, "Moved" to BattleEvent.Moved::class.java,
            "Waited" to BattleEvent.Waited::class.java, "Defended" to BattleEvent.Defended::class.java,
            "LuckRolled" to BattleEvent.LuckRolled::class.java, "DamageDealt" to BattleEvent.DamageDealt::class.java,
            "UnitDied" to BattleEvent.UnitDied::class.java, "BattleEnded" to BattleEvent.BattleEnded::class.java,
        )
        // Every Python dataclass is accounted for (Begin has no fields and is a Kotlin object).
        assertEquals(schema.keys - "Begin", models.keys)
        assertEquals(emptyList(), schema["Begin"])
        for ((py, cls) in models) {
            assertEquals(schema.getValue(py).map(::snakeToCamel).toSet(), props(cls), "$py: Kotlin properties")
        }

        // The canonical map of a real parsed state carries exactly the Python field names.
        val first = doc["cases"].list()[0].obj()["steps"].list().last().obj()["canonical"] as String
        val m = codec.toMap(codec.parseState(MiniJson.parse(first)))
        assertEquals(schema.getValue("BattleState").toSet(), m.keys)
        assertEquals(schema.getValue("BattlePolicy").toSet(), m["policy"].obj().keys)
        val stack = m["stacks"].list()[0].obj()
        assertEquals(schema.getValue("Stack").toSet(), stack.keys)
        assertEquals(schema.getValue("Creature").toSet(), stack["creature"].obj().keys)
        assertEquals(schema.getValue("Hero").toSet(), m["heroes"].list().filterNotNull()[0].obj().keys)
        for (c in doc["command_cases"].list() + doc["event_cases"].list()) {
            val type = c.obj()["type"] as String
            assertEquals((schema.getValue(type) + "type").toSet(), c.obj().keys, type)
        }
    }

    @Test
    fun policyDefaultsComeFromThePack() {
        val d = pack.defaultPolicy()
        val p = packs["battle_policy"].obj()
        assertEquals(p["row_offset"], d.rowOffset)
        assertEquals(p["defend_bonus_den"].big().intValueExact(), d.defendBonusDen)
        assertEquals(packs["bad_morale_numerators"].list().map { it.big().intValueExact() }, d.badMoraleTable)
        assertEquals(p["placement_rows"].list().map { r -> r.list().map { it.big().intValueExact() } }, d.placementRows)
        // Overrides replace one field and keep the rest.
        val o = pack.policy(mapOf("bad_luck" to true))
        assertEquals(d.copy(badLuck = true), o)
        assertFailsWith<IllegalArgumentException> { pack.policy(mapOf("nope" to 1)) }
        // The initial state of every case that uses defaults carries them.
        val init = doc["cases"].list()[0].obj()["initial"].obj()["canonical"] as String
        assertEquals(d, codec.parseState(MiniJson.parse(init)).policy)
        // Non-default policies parse to something different from the defaults.
        val alt = doc["cases"].list().first { it.obj()["name"] == "vcmi-like-0" }
        val altState = codec.parseState(MiniJson.parse(alt.obj()["initial"].obj()["canonical"] as String))
        assertNotEquals(d, altState.policy)
        assertEquals(listOf(2, 4, 6), altState.policy.badMoraleTable)
    }

    @Test
    fun omitWhenDefaultMechanism() {
        val text = doc["cases"].list()[0].obj()["initial"].obj()["canonical"] as String
        val state = codec.parseState(MiniJson.parse(text))
        val omit = BattleCodec(pack, listOf("bad_luck", "row_offset"))
        // At default: the listed fields are left out, the rest stays.
        val omitted = omit.toMap(state)["policy"].obj()
        assertTrue("bad_luck" !in omitted && "row_offset" !in omitted && "speed_tie" in omitted)
        assertEquals(state, omit.parseState(MiniJson.parse(omit.canonicalText(state))))
        // Off default: the field is written.
        val bl = state.copy(policy = state.policy.copy(badLuck = true))
        assertEquals(true, omit.toMap(bl)["policy"].obj()["bad_luck"])
        assertEquals(bl, omit.parseState(MiniJson.parse(omit.canonicalText(bl))))
        // A different hash only when a field is omitted.
        assertNotEquals(codec.stateHash(state), omit.stateHash(state))
        assertFailsWith<IllegalArgumentException> { BattleCodec(pack, listOf("nope")) }
    }

    @Test
    fun parserIsStrict() {
        val text = doc["cases"].list()[0].obj()["initial"].obj()["canonical"] as String
        val m = MiniJson.parse(text).obj()
        assertFailsWith<IllegalArgumentException> { codec.parseState(m + ("extra" to null)) }
        assertFailsWith<IllegalArgumentException> { codec.parseState(m - "round") }
        assertFailsWith<IllegalArgumentException> { codec.parseState(m + ("started" to "yes")) }
        assertFailsWith<IllegalArgumentException> {
            BattleCodec.parseCommand(mapOf("type" to "Wait", "stack" to java.math.BigInteger.ONE, "x" to null))
        }
        assertFailsWith<IllegalArgumentException> { BattleCodec.parseEvent(mapOf("type" to "Nope")) }
    }
    private fun rejectMessage(block: () -> Unit): String? =
        try { block(); null } catch (e: IllegalArgumentException) { e.message ?: "" }

    /** Every policy Python's `BattlePolicy` refuses is refused here, with Python's message. */
    @Test
    fun policyRejectCasesMatchPython() {
        val cases = doc["policy_reject_cases"].list().map { it.obj() }
        assertTrue(cases.size >= 20)
        val bad = cases.mapNotNull { c ->
            val got = rejectMessage { pack.policy(mapOf(c["field"] as String to c["value"])) }
            if (got == c["message"]) null else "${c["field"]}=${c["value"]}: got '$got' want '${c["message"]}'"
        }
        assertTrue(bad.isEmpty(), bad.toString())
    }

    /** Every state Python's `check_state` refuses is refused by the parse, with Python's message. */
    @Test
    fun stateRejectCasesMatchPython() {
        val cases = doc["state_reject_cases"].list().map { it.obj() }
        assertTrue(cases.size >= 25)
        val bad = cases.mapNotNull { c ->
            val got = rejectMessage { codec.parseState(MiniJson.parse(c["canonical"] as String)) }
            if (got == c["message"]) null else "${c["label"]}: got '$got' want '${c["message"]}'"
        }
        assertTrue(bad.isEmpty(), bad.toString())
    }

    private fun refused(field: String, value: Any?, message: String) =
        assertEquals(message, rejectMessage { pack.policy(mapOf(field to value)) }, "$field=$value")

    @Test
    fun speedTieBogusIsRefused() = refused("speed_tie", "bogus", "bad speed_tie")

    @Test
    fun rowOffsetDiagonalIsRefused() = refused("row_offset", "diagonal", "row_offset must be 'odd' or 'even'")

    @Test
    fun defendBonusDenZeroIsRefused() = refused("defend_bonus_den", 0, "bad defend bonus fraction")

    @Test
    fun badMoraleTableDecreasingIsRefused() =
        refused("bad_morale_table", listOf(9, 1, 1), "bad_morale_table must be non-decreasing")

    @Test
    fun rangePenaltyBeyondNegativeIsRefused() = refused("range_penalty_beyond", -5, "bad range_penalty_beyond")

    @Test
    fun placementRowsEmptyIsRefused() =
        refused("placement_rows", emptyList<Any>(), "placement_rows needs 7 rows tuples of size 1..7")

    @Test
    fun waitOrderRangeOriginRoundingAndMinAreRefused() {
        refused("wait_order", "bogus", "bad wait_order")
        refused("range_origin", "tail", "bad range_origin")
        refused("defend_bonus_rounding", "round", "bad defend_bonus_rounding")
        refused("defend_bonus_min", -1, "defend_bonus_min out of range")
        refused("defend_bonus_num", 1L shl 31, "defend_bonus_num out of range")
    }

    @Test
    fun theCapStateIsAcceptedAndOneAboveIsNot() {
        val cap = doc["cases"].list().map { it.obj() }.single { it["name"] == "cap" }
        val text = cap["initial"].obj()["canonical"] as String
        val state = codec.parseState(MiniJson.parse(text))
        assertEquals(Int.MAX_VALUE.toLong(), state.stacks[0].count.toLong() * state.stacks[0].creature.dmgMax)
        val above = state.copy(stacks = listOf(state.stacks[0].copy(creature = state.stacks[0].creature.copy(dmgMax = 2)), state.stacks[1]))
        assertEquals("count x dmg_max exceeds 2**31-1", rejectMessage { codec.parseState(codec.toMap(above)) })
        val aboveHp = state.copy(stacks = listOf(state.stacks[0], state.stacks[1].copy(creature = state.stacks[1].creature.copy(hp = 2))))
        assertEquals("count x hp exceeds 2**31-1", rejectMessage { codec.parseState(codec.toMap(aboveHp)) })
    }
}
