package h3.sim

import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlin.test.fail

private val ADVENTURE_DOC by lazy { loadVector("adventure.json") }

/**
 * Adventure port: `Adventure.apply` versus every recorded step of `adventure.json`
 * (docs/specs/conformance-adventure.md).
 *
 * Stage A: every recorded state (initial and after each step) parses and re-encodes to the same
 * canonical text and SHA-256. Stage B: Move steps (pathfinding, costs, last-step rules, the
 * moving hero's reachable map) under every recorded policy. Stage C: Begin and EndTurn (day and
 * week tick, income, growth, movement reset). Stage D: rejected commands leave state and stream
 * untouched and carry Python's message. Each step is replayed from the previous recorded state.
 */
class AdventureTest {
    private val doc = ADVENTURE_DOC
    private val rules = AdventureRules.from(doc["constants"])
    private val codec = AdventureCodec(rules)
    private val adv = Adventure(rules)
    private val cases = doc["cases"].list().map { it.obj() }

    private fun parse(text: String): AdventureState = codec.parseState(MiniJson.parse(text))
    private fun steps(c: Map<String, Any?>) = c["steps"].list().map { it.obj() }
    private fun before(c: Map<String, Any?>, i: Int): String =
        if (i == 0) c["initial"].obj()["canonical"] as String else steps(c)[i - 1]["canonical"] as String
    private fun enc(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

    private fun stream(c: Map<String, Any?>): Pcg32 {
        val sc = c["scenario"].obj()
        return RngStreams.derive(sc["master_seed"].big(), sc["stream_domain"] as String)
    }

    private fun reachDigest(s: AdventureState, hero: Int): Pair<String, Int> {
        val r = adv.reachable(s, hero)
        val items = r.entries.map { (t, v) -> listOf(listOf(t.first, t.second), v.first, v.second.map { listOf(it.first, it.second) }) }
        return Pair(Canonical.hash(items), items.size)
    }

    /** Replays the steps of [stage]; returns (matched, total). */
    private fun replayStage(stage: String): Pair<Int, Int> {
        var total = 0
        val failures = ArrayList<String>()
        for (c in cases) {
            for ((i, step) in steps(c).withIndex()) {
                if (step["stage"] != stage) continue
                total++
                val label = "${c["name"]} step $i ${enc(step["command"])}"
                try {
                    val s = parse(before(c, i))
                    val cmd = AdventureCodec.parseCommand(step["command"])
                    if (cmd is AdventureCommand.Move) {
                        val (h, n) = reachDigest(s, cmd.hero!!)
                        if (h != step["reach_sha256"] || n != step["reach_size"].big().toInt()) {
                            failures.add("$label: reachable map differs ($n tiles)"); continue
                        }
                    }
                    val g = stream(c)
                    val r = adv.apply(s, cmd, g)
                    val fresh = stream(c)
                    when {
                        codec.canonicalText(r.state) != step["canonical"] -> failures.add("$label: canonical differs")
                        codec.stateHash(r.state) != step["sha256"] -> failures.add("$label: hash differs")
                        enc(r.events.map { it.toMap() }) != enc(step["events"]) -> failures.add("$label: events differ")
                        g.state != fresh.state -> failures.add("$label: stream advanced")
                    }
                } catch (e: Exception) {
                    failures.add("$label: ${e::class.simpleName}: ${e.message}")
                }
            }
        }
        if (failures.isNotEmpty()) fail("stage $stage: ${failures.size}/$total steps fail; first: ${failures.take(5)}")
        return Pair(total, total)
    }

    @Test
    fun vectorIsNonTrivial() {
        assertTrue(cases.size >= 20)
        val all = cases.flatMap { steps(it) }
        assertTrue(all.size >= 1000)
        assertEquals(setOf("Begin", "Move", "EndTurn"), all.map { it["command"].obj()["type"] }.toSet())
        assertEquals(
            setOf("DayStarted", "WeekStarted", "PoolGrew", "TurnStarted", "IncomeReceived", "MovementReset", "HeroMoved", "TurnEnded"),
            all.flatMap { s -> s["events"].list().map { it.obj()["type"] } }.toSet(),
        )
    }

    @Test
    fun stageA_codecRoundTripAndHash() {
        var n = 0
        for (c in cases) {
            val texts = listOf(c["initial"].obj()) + steps(c)
            for (t in texts) {
                val s = parse(t["canonical"] as String)
                assertEquals(t["canonical"], codec.canonicalText(s), "${c["name"]}")
                assertEquals(t["sha256"], codec.stateHash(s), "${c["name"]}")
                n++
            }
        }
        assertTrue(n > 1000)
    }

    @Test
    fun stageB_moves() { assertTrue(replayStage("B").first > 500) }

    @Test
    fun stageC_beginEndTurnDayWeek() { assertTrue(replayStage("C").first > 200) }

    @Test
    fun wholeCasesReplayFromTheInitialState() {
        for (c in cases) {
            var s = parse(c["initial"].obj()["canonical"] as String)
            val g = stream(c)
            for (step in steps(c)) s = adv.apply(s, AdventureCodec.parseCommand(step["command"]), g).state
            assertEquals(steps(c).last()["sha256"], codec.stateHash(s), c["name"] as String)
            val fin = c["final_rng_state"].list()
            assertEquals(fin[0].big(), BigInteger(g.state.toString()), c["name"] as String)
        }
    }

    @Test
    fun goldenFourteenDayHashIsThePythonPin() {
        val golden = cases.first { it["name"] == "golden" }
        val s = parse(steps(golden).last()["canonical"] as String)
        assertEquals(15, s.day)
        // tests/test_adventure.py GoldenTest.PINNED
        assertEquals("179c570020d05be9a53c265a76517a4bb9f398c92f37d19485d30f804f703420", codec.stateHash(s))
    }

    @Test
    fun stageD_illegalCommandsTouchNeitherStateNorStream() {
        val illegal = doc["illegal_cases"].list().map { it.obj() }
        assertTrue(illegal.size >= 500)
        val byName = cases.associateBy { it["name"] as String }
        val failures = ArrayList<String>()
        for ((k, ic) in illegal.withIndex()) {
            val c = byName.getValue(ic["case"] as String)
            val after = ic["after_step"].big().toInt()
            val text = before(c, after + 1)
            val s = parse(text)
            val g = stream(c)
            val label = "illegal $k (${ic["case"]} after ${ic["after_step"]}, ${enc(ic["command"])})"
            try {
                adv.apply(s, AdventureCodec.parseCommand(ic["command"]), g)
                failures.add("$label: accepted")
            } catch (e: IllegalCommand) {
                if (e.message != ic["message"]) failures.add("$label: message '${e.message}' != '${ic["message"]}'")
            }
            if (codec.canonicalText(s) != text) failures.add("$label: state changed")
            if (g.state != stream(c).state) failures.add("$label: stream advanced")
        }
        if (failures.isNotEmpty()) fail("stage D: ${failures.size}/${illegal.size} fail; first: ${failures.take(5)}")
    }

    @Test
    fun commandFieldsAreStrictIntegers() {
        val s = parse(steps(cases.first())[0]["canonical"] as String)
        val begun = s.day == 1
        assertTrue(begun)
        fun msg(cmd: Map<String, Any?>) = assertFailsWith<IllegalCommand> { adv.apply(s, AdventureCodec.parseCommand(cmd)) }.message
        // A non-integer number (a JSON reader that yields doubles) is never an integer field.
        assertEquals("no such hero", msg(mapOf("type" to "Move", "hero" to java.lang.Double.valueOf("0"), "dest" to listOf(BigInteger.ONE, BigInteger.ONE))))
        assertEquals("not a tile: (1, 1.5)", msg(mapOf("type" to "Move", "hero" to BigInteger.ZERO, "dest" to listOf(BigInteger.ONE, java.lang.Double.valueOf("1.5")))))
        assertEquals("not player False's turn", msg(mapOf("type" to "EndTurn", "player" to false)))
        assertEquals("not player None's turn", msg(mapOf("type" to "EndTurn", "player" to null)))
        assertFailsWith<IllegalArgumentException> { AdventureCodec.parseCommand(mapOf("type" to "Teleport", "hero" to BigInteger.ZERO, "target" to "g")) }
        assertFailsWith<IllegalArgumentException> { AdventureCodec.parseCommand(mapOf("type" to "Move", "hero" to BigInteger.ZERO)) }
    }

    @Test
    fun badPoliciesAndStatesAreRefused() {
        val text = cases.first()["initial"].obj()["canonical"] as String
        fun mutated(edit: (MutableMap<String, Any?>) -> Unit): String? {
            @Suppress("UNCHECKED_CAST")
            val m = MiniJson.parse(text) as MutableMap<String, Any?>
            edit(m)
            return try { codec.parseState(m); null } catch (e: IllegalArgumentException) { e.message }
        }
        @Suppress("UNCHECKED_CAST")
        fun pol(m: MutableMap<String, Any?>) = m["policy"] as MutableMap<String, Any?>
        assertEquals("bad cost_from", mutated { pol(it)["cost_from"] = "both" })
        assertEquals("bad last_step", mutated { pol(it)["last_step"] = "never" })
        assertEquals("diagonal_num and diagonal_den need ints in 1..10000", mutated { pol(it)["diagonal_den"] = BigInteger.ZERO })
        assertEquals("pathfinding_pct needs 4 values in 0..100", mutated { pol(it)["pathfinding_pct"] = listOf(BigInteger.ZERO, BigInteger.valueOf(101), BigInteger.ZERO, BigInteger.ZERO) })
        assertEquals("road_cost needs a cost in 1..10000 for each road type", mutated { pol(it)["road_cost"] = listOf(listOf("dirt", BigInteger.ONE)) })
        assertEquals("road_cost has a duplicate road type", mutated {
            pol(it)["road_cost"] = listOf(listOf("dirt", BigInteger.ONE), listOf("dirt", BigInteger.TWO), listOf("gravel", BigInteger.ONE))
        })
        assertEquals("diagonal_moves: expected boolean", mutated { pol(it)["diagonal_moves"] = BigInteger.ONE })
        assertEquals("day: expected integer", mutated { it["day"] = true })
        assertEquals("day out of range", mutated { it["day"] = BigInteger.TWO.pow(31) })
        assertEquals("state: encounters are not ported (encounter.md)", mutated { it["encounter"] = null })
    }

    @Test
    fun policyCasesMatchPythonVerdictAndMessage() {
        val pcs = doc["policy_cases"].list().map { it.obj() }
        assertTrue(pcs.size >= 30)
        assertTrue(pcs.any { it["error"] == null } && pcs.any { it["error"] != null })
        val failures = ArrayList<String>()
        for (pc in pcs) {
            val pol = pc["policy"].obj()
            try {
                val p = codec.policyFrom(pol)
                when {
                    pc["error"] != null -> failures.add("${pc["name"]}: accepted, want '${pc["error"]}'")
                    enc(codec.policyToMap(p)) != enc(pol) -> failures.add("${pc["name"]}: round trip differs")
                }
            } catch (e: IllegalArgumentException) {
                if (e.message != pc["error"]) failures.add("${pc["name"]}: '${e.message}' != '${pc["error"]}'")
            }
        }
        if (failures.isNotEmpty()) fail("policy cases: ${failures.size}/${pcs.size} fail; first: ${failures.take(5)}")
    }

    @Test
    fun policyFieldsThatAreNotIntegersAreRefusedLikeBools() {
        val base = doc["policies"].obj().getValue("default").obj()
        fun msg(k: String, v: Any?) = assertFailsWith<IllegalArgumentException> { codec.policyFrom(base + (k to v)) }.message
        val diag = "diagonal_num and diagonal_den need ints in 1..10000"
        // A JSON reader that yields doubles, or a Boolean: never an integer policy field.
        assertEquals(diag, msg("diagonal_num", java.lang.Double.valueOf("141")))
        assertEquals(diag, msg("diagonal_den", true))
        assertEquals("move_cost_floor needs an int in 1..10000", msg("move_cost_floor", java.lang.Double.valueOf("100")))
        assertEquals("pathfinding_flat needs 4 ints in 0..10000", msg("pathfinding_flat", listOf(BigInteger.ZERO, java.lang.Double.valueOf("1"), BigInteger.TWO, BigInteger.TEN)))
        assertEquals("pathfinding_pct needs 4 values in 0..100", msg("pathfinding_pct", listOf(BigInteger.ZERO, false, BigInteger.TWO, BigInteger.TEN)))
        assertEquals("road_cost needs a cost in 1..10000 for each road type", msg("road_cost", listOf(listOf("cobblestone", true), listOf("dirt", BigInteger.TEN), listOf("gravel", BigInteger.TEN))))
    }

    @Test
    fun dearestLegalUnbudgetedPathDoesNotOverflowInt() {
        // Orthogonal 10^4 (floor) x diagonal ratio 10^4 = 10^8 per step; 24 diagonal steps = 2.4e9 > Int.
        val m = BigInteger.valueOf(10_000)
        val base = doc["policies"].obj().getValue("default").obj()
        val pol = codec.policyFrom(base + mapOf("diagonal_mode" to "ratio", "diagonal_num" to m, "diagonal_den" to BigInteger.ONE, "move_cost_floor" to m))
        val n = 25
        val tiles = (0 until n * n).map { AdvTile("swamp", "none", ((it % n) + (it / n)) % 2 == 1) }
        val hero = AdvHero(0, 0, Pair(0, 0), listOf(AdvArmySlot("c", 5, 1)), 0, 1, 0, 0, false)
        val s = AdventureState("big", pol, AdvGrid(n, n, tiles), listOf(AdvPlayer()), listOf(hero), emptyList())
        val (cost, path) = adv.findPath(s, 0, Pair(n - 1, n - 1))!!
        assertEquals(24L * 10_000 * 10_000, cost.toLong())
        assertEquals(25, path.size)
    }

    @Test
    fun pyReprMatchesPythonForStringsAndDicts() {
        fun r(v: Any?) = AdventureCodec.pyRepr(v)
        assertEquals("\"it's\"", r("it's"))
        assertEquals("'say \"hi\"'", r("say \"hi\""))
        assertEquals("'both \\' and \"'", r("both ' and \""))
        assertEquals("'a\\tb\\nc\\rd\\\\'", r("a\tb\nc\rd\\"))
        assertEquals("'\\x00\\x1f\\x7f\\x80\\x9f\\xa0\\xad'", r("\u0000\u001f\u007f\u0080\u009f\u00a0\u00ad"))
        assertEquals("'caf\u00e9\\u2028\\u3000\\ue000\\ud800'", r("caf\u00e9\u2028\u3000\ue000\ud800"))
        assertEquals("'\ufb01\uD83D\uDE00\\U0010ffff\\U000e0001'", r("\ufb01\uD83D\uDE00\uDBFF\uDFFF\uDB40\uDC01"))
        assertEquals("'\u2ffc\u31ef${String(Character.toChars(0x2ebf0))}'", r("\u2ffc\u31ef${String(Character.toChars(0x2ebf0))}"))   // Unicode 15.1 additions are printable
        assertEquals("{}", r(emptyMap<String, Any?>()))
        assertEquals("{'a': 1, \"c'd\": [None, True, {'x': []}]}", r(linkedMapOf("a" to BigInteger.ONE, "c'd" to listOf(null, true, linkedMapOf("x" to emptyList<Any?>())))))
        assertEquals("({'a': 1}, 2)", AdventureCodec.pyRepr(listOf(linkedMapOf("a" to BigInteger.ONE), BigInteger.TWO), true))
        assertEquals("(1,)", AdventureCodec.pyRepr(listOf(BigInteger.ONE), true))
    }

    @Test
    fun guardsBlockTilesAndAreOmittedAtDefault() {
        val c = cases.first { it["name"] == "golden" }
        val s = parse(steps(c)[0]["canonical"] as String)
        val h = s.heroes[0]
        val target = adv.reachable(s, 0).keys.first()
        val withGuard = s.copy(guards = listOf(AdvGuard("g", target, listOf(AdvArmySlot("x", 5, 1)))))
        assertTrue(target !in adv.reachable(withGuard, 0))
        assertTrue("\"guards\"" in codec.canonicalText(withGuard))
        assertTrue("\"guards\"" !in codec.canonicalText(s) && "\"battles\"" !in codec.canonicalText(s))
        assertEquals(codec.canonicalText(withGuard), codec.canonicalText(parse(codec.canonicalText(withGuard))))
        assertEquals(h, withGuard.heroes[0])
    }
}
