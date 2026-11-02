package h3.sim.town

import h3.sim.Category
import h3.sim.DatapackError
import h3.sim.Pcg32
import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/** Unit tests of the town core on the `data/towns_test.json` pack (carried by the vector file as `packs.test`). */
class TownTest {
    private val text = TownVectors.packs.getValue("test").str()
    private val content = TownCore.parseTownPackText(text, "towns.json")
    private val cap = (1L shl 31) - 1
    private val fern = "faction.fernwood"
    private val salt = "faction.saltmarsh"
    private val rich = Resources(100000, 200, 200, 20, 20, 20, 20)

    private fun game(
        towns: List<TownSetup> = listOf(TownSetup("t1", fern, 0, listOf("hall.1"))),
        players: List<Resources> = listOf(rich),
        policy: TownPolicy = DEFAULT_POLICY,
        c: TownContent = content,
    ) = TownCore.createGame("g", c, players, towns, policy)

    private fun build(s: TownState, town: String, b: String, player: Long = 0L, rng: Pcg32? = null) =
        TownCore.apply(s, Build(player, town, b), rng)

    private fun newDay(s: TownState) = TownCore.apply(s, NewDay).state

    private fun illegal(s: TownState, cmd: TownCommand, msg: String) {
        val rng = TownCore.townRng(1, "g")
        val before = rng.state
        val e = assertFailsWith<IllegalCommand> { TownCore.apply(s, cmd, rng) }
        assertEquals(msg, e.message)
        assertEquals(before, rng.state)
    }

    private fun pack(edit: (String) -> String) = TownCore.parseTownPackText(edit(text), "towns.json")

    private fun bad(edit: (String) -> String): DatapackError =
        assertFailsWith<DatapackError> { TownCore.parseTownPackText(edit(text), "towns.json") }

    // ---- golden --------------------------------------------------------------------------------

    @Test
    fun goldenRunMatchesTheSpecPin() {
        val script = listOf(
            listOf(Triple(0L, "north", "keep.1"), Triple(1L, "south", "wall.1"), Triple(1L, "east", "den.1")),
            listOf(Triple(0L, "north", "den.1"), Triple(1L, "south", "pool.1"), Triple(1L, "east", "nest.2")),
            listOf(Triple(0L, "north", "market"), Triple(1L, "south", "hall.2"), Triple(1L, "east", "hive")),
            listOf(Triple(0L, "north", "keep.2"), Triple(1L, "south", "reef.2"), Triple(1L, "east", "market")),
            listOf(Triple(0L, "north", "hive"), Triple(1L, "south", "wall.2")),
            listOf(Triple(0L, "north", "nest.2"), Triple(1L, "east", "den.1u")),
            listOf(Triple(0L, "north", "hall.2")),
        )
        var s = game(
            towns = listOf(
                TownSetup("north", fern, 0, listOf("hall.1")), TownSetup("south", salt, 1, listOf("hall.1")),
                TownSetup("east", fern, 1, listOf("hall.1", "keep.1")),
            ),
            players = listOf(Resources(gold = 30000, wood = 60, ore = 60, mercury = 4, gems = 2), Resources(gold = 25000, wood = 20, ore = 50, mercury = 2, sulfur = 5)),
        ).copy(gameId = "golden")
        for (day in script) {
            for ((p, t, b) in day) s = build(s, t, b, p).state
            s = newDay(s)
        }
        assertEquals("0360ce8861ca3b4a12f8210f0d8111b57c328becb8c433d41c59d6a6d257aae7", TownCore.stateHash(s))
        assertEquals(8L, s.day)
        assertEquals(Resources(gold = 30000 - 5000 - 400 - 500 - 2500 - 1000 - 1000 - 2500, wood = 60 - 20 - 5 - 5, ore = 60 - 20 - 5 - 5, mercury = 2, gems = 2), s.players[0])
        assertEquals(
            Resources(gold = 25000 - 5000 - 400 - 300 - 1000 - 2500 - 1000 - 800 - 500 - 2500 - 900, wood = 20 - 5 - 5 - 5, ore = 50 - 20 - 5 - 3 - 5, sulfur = 5),
            s.players[1],
        )
        val pools = s.towns.flatMap { TownCore.growthPools(s, it.id) }
        assertEquals(
            listOf(
                GrowthPool("north:dwelling1", 0, 13 + 6 + 4), GrowthPool("north:dwelling2", 0, 7 + 3),
                GrowthPool("south:dwelling1", 0, 9 + 4), GrowthPool("south:dwelling2", 0, 6 + 3),
                GrowthPool("east:dwelling1", 0, 13 + 4), GrowthPool("east:dwelling2", 0, 7),
            ),
            pools,
        )
        assertTrue(TownCore.contentHash(content).startsWith("629836f9f419a851"))
    }

    // ---- growth: the one rounding step ---------------------------------------------------------

    @Test
    fun citadelRoundingOnAnOddBase() {
        val half = Pair(1L, 2L)
        assertEquals(19L, TownCore.weeklyGrowth(13, half, 0, TownPolicy("floor")))
        assertEquals(20L, TownCore.weeklyGrowth(13, half, 0, TownPolicy("ceil")))
        assertEquals(20L, TownCore.weeklyGrowth(13, half, 0, TownPolicy("nearest")))
    }

    @Test
    fun nearestRoundsHalvesUpAndAgreesWithBigIntegerArithmetic() {
        // independent oracle: java.math, not the Long path
        fun oracle(base: Long, n: Long, d: Long, mode: String): BigInteger {
            val num = BigInteger.valueOf(base) * BigInteger.valueOf(n)
            val den = BigInteger.valueOf(d)
            val floor = num.divide(den) - (if (num.signum() < 0 && num.mod(den).signum() != 0) BigInteger.ONE else BigInteger.ZERO)
            return when (mode) {
                "floor" -> floor
                "ceil" -> if (num.mod(den).signum() == 0) floor else floor + BigInteger.ONE
                else -> (num * BigInteger.TWO + den).divide(den * BigInteger.TWO).let { q ->
                    val t = num * BigInteger.TWO + den
                    if (t.signum() < 0 && t.mod(den * BigInteger.TWO).signum() != 0) q - BigInteger.ONE else q
                }
            }
        }
        val bases = listOf(0L, 1, 2, 3, 5, 7, 13, 99, 1001, cap, cap - 1, 46341, 1L shl 40)
        val fractions = listOf(0L to 1L, 1L to 2L, 1L to 1L, 1L to 3L, 2L to 3L, 3L to 2L, 7L to 3L, cap to cap - 1, cap - 1 to cap, cap to 1L, 1L to cap, 2L to 4L)
        for (mode in listOf("floor", "ceil", "nearest")) {
            for (b in bases) for ((n, d) in fractions) {
                if (b == 1L shl 40 && n > 1L shl 20) continue // beyond Long: documented
                assertEquals(oracle(b, n, d, mode).toLong(), TownCore.roundCastleBonus(b, Pair(n, d), mode), "$mode $b $n/$d")
            }
        }
        assertEquals(3L, TownCore.roundCastleBonus(5, Pair(1, 2), "nearest"))
        assertEquals(-2L, TownCore.roundCastleBonus(5, Pair(-1, 2), "nearest")) // -2.5 rounds up to -2
        assertEquals(-3L, TownCore.roundCastleBonus(5, Pair(-1, 2), "floor"))
        assertEquals(-2L, TownCore.roundCastleBonus(5, Pair(-1, 2), "ceil"))
    }

    @Test
    fun hordeIsNotScaledAndTheLargestBonusWins() {
        assertEquals(13L + 6 + 4, TownCore.weeklyGrowth(13, Pair(1, 2), 4))
        val tiny = TownCore.parseTownPackText(TownVectors.packs.getValue("tiny").str(), "towns.json")
        val chain = listOf("fort", "cit", "cas", "d1", "h1a", "h1b", "bless", "bless2").let { l ->
            TownState("g", DEFAULT_POLICY, tiny, listOf(Resources()), listOf(Town("t", "f.a", 0, l.sortedWith(compareBy { it }))))
        }
        // fort is upgraded by cit, cit by cas: only cas (3/4) is active; bless (2/3) and bless2 (2/4) are smaller
        assertEquals(listOf("bless", "bless2", "cas", "d1", "h1a", "h1b"), TownCore.activeBuildings(chain, "t"))
        assertEquals(listOf(GrowthPool("t:dwelling1", 0, 5 + 3 + (2 + 3))), TownCore.growthPools(chain, "t"))
    }

    @Test
    fun carriedOverPoolsTakeTheLastEntryAndIgnoreOtherIds() {
        val s = game(towns = listOf(TownSetup("north", fern, 0, listOf("hall.1", "keep.1", "den.1"))))
        val cur = listOf(GrowthPool("north:dwelling1", 1, 0), GrowthPool("zz:dwelling1", 9, 9), GrowthPool("north:dwelling1", 7, 0))
        assertEquals(listOf(GrowthPool("north:dwelling1", 7, 13)), TownCore.growthPools(s, "north", cur))
        assertEquals(listOf(GrowthPool("north:dwelling1", 0, 13)), TownCore.growthPools(s, "north", emptyList()))
    }

    @Test
    fun overflowAndZeroDenominatorAreErrorsNotWrapping() {
        assertFailsWith<ArithmeticException> { TownCore.weeklyGrowth(Long.MAX_VALUE, Pair(2, 1), 0) }
        assertFailsWith<ArithmeticException> { TownCore.weeklyGrowth(Long.MAX_VALUE, Pair(0, 1), 1) }
        assertFailsWith<ArithmeticException> { TownCore.weeklyGrowth(1L shl 62, Pair(2, 1), 0) }
        val e = assertFailsWith<ArithmeticException> { TownCore.weeklyGrowth(5, Pair(1, 0), 0) }
        assertEquals("Fraction(1, 0)", e.message)
        // the extreme the loader allows still fits
        assertEquals(
            (BigInteger.valueOf(cap) * BigInteger.valueOf(cap) + BigInteger.valueOf(cap) * BigInteger.TWO).toLong(),
            TownCore.weeklyGrowth(cap, Pair(cap, 1), cap, TownPolicy("nearest")),
        )
    }

    // ---- building ------------------------------------------------------------------------------

    @Test
    fun buildPaysTheCostAndKeepsBuiltSorted() {
        val s = game()
        val r = build(s, "t1", "market")
        assertEquals(listOf("hall.1", "market"), r.state.towns[0].built)
        assertTrue(r.state.towns[0].builtToday)
        assertEquals(Resources(rich.gold - 500, rich.wood - 5, rich.ore, rich.mercury, rich.sulfur, rich.crystal, rich.gems), r.state.players[0])
        assertEquals(listOf<TownEvent>(BuildingBuilt("t1", "market", 0, Resources(gold = 500, wood = 5), r.state.players[0])), r.events)
        assertFalse(s.towns[0].builtToday, "the old state is untouched")
        assertEquals(rich, s.players[0])
    }

    @Test
    fun oneBuildPerTownPerDayNotPerPlayer() {
        var s = game(towns = listOf(TownSetup("a", fern, 0), TownSetup("b", fern, 0)))
        s = build(s, "a", "hall.1").state
        s = build(s, "b", "hall.1").state
        illegal(s, Build(0, "a", "keep.1"), "town 'a' already built today")
        illegal(s, Build(0, "b", "keep.1"), "town 'b' already built today")
        s = newDay(s)
        assertEquals(2L, s.day)
        assertFalse(s.towns.any { it.builtToday })
        s = build(s, "a", "keep.1").state
    }

    @Test
    fun illegalCommandsKeepTheStateAndTheStream() {
        val s = game(players = listOf(rich, Resources(gold = 10)), towns = listOf(TownSetup("t", fern, 0, listOf("hall.1")), TownSetup("u", fern, 1, listOf("hall.1"))))
        illegal(s, Build(-1, "t", "market"), "no such player -1")
        illegal(s, Build(2, "t", "market"), "no such player 2")
        illegal(s, Build(1L shl 40, "t", "market"), "no such player 1099511627776")
        illegal(s, Build(0, "x", "market"), "no such town 'x'")
        illegal(s, Build(0, "it's", "market"), "no such town \"it's\"")
        illegal(s, Build(1, "t", "market"), "player 1 does not own town 't'")
        illegal(s, Build(0, "t", "zzz"), "no such building 'zzz'")
        illegal(s, Build(0, "t", "wall.1"), "no such building 'wall.1'")
        illegal(s, Build(0, "t", "hall.1"), "'hall.1' already built")
        illegal(s, Build(0, "t", "hall.3"), "'hall.3': missing hall.2, keep.1")
        illegal(s, Build(1, "u", "market"), "player 1 cannot afford 'market'")
        val snapshot = s.copy()
        assertEquals(snapshot, s)
    }

    @Test
    fun theCheckOrderIsPlayerTownOwnerBuildingBuiltTodayRequirementsUniqueAfford() {
        // built today beats missing requirements; missing requirements beat affordability
        var s = game(players = listOf(Resources()), towns = listOf(TownSetup("t", fern, 0)))
        s = build(s, "t", "hall.1").state
        illegal(s, Build(0, "t", "hall.2"), "town 't' already built today")
        s = newDay(s)
        illegal(s, Build(0, "t", "hall.2"), "'hall.2': missing market")
        illegal(s, Build(0, "t", "market"), "player 0 cannot afford 'market'")
    }

    @Test
    fun aPlayerOwnsOneCapitalAcrossAllTownsAndInsideOneTown() {
        val chain = listOf("hall.1", "market", "hall.2", "keep.1", "keep.2", "keep.3", "hall.3")
        val s = game(
            players = listOf(rich, rich),
            towns = listOf(TownSetup("a", fern, 0, chain), TownSetup("b", fern, 0, chain), TownSetup("c", fern, 1, chain)),
        )
        val a = build(s, "a", "hall.4").state
        illegal(a, Build(0, "b", "hall.4"), "player 0 already has a 'capital' building")
        build(a, "c", "hall.4", 1) // another player may
        // two unrelated buildings carrying the same tag cannot both be built in one town either
        val twin = TownCore.parseTownPackText(TownVectors.packs.getValue("twin").str(), "towns.json")
        val t = game(players = listOf(rich), towns = listOf(TownSetup("a", "f.one", 0)), c = twin)
        val t1 = build(t, "a", "cap.a").state
        illegal(newDay(t1), Build(0, "a", "cap.b"), "player 0 already has a 'capital' building")
    }

    @Test
    fun theTownCoreDoesNotDraw() {
        val rng = TownCore.townRng(2026, "g")
        val before = rng.state
        var s = game()
        s = build(s, "t1", "market", 0, rng).state
        s = TownCore.apply(s, NewDay, rng).state
        assertEquals(before, rng.state)
        assertNotEquals(TownCore.townRng(2026, "g").state, TownCore.townRng(2026, "h").state)
        assertNotEquals(TownCore.townRng(2026, "g").state, TownCore.townRng(2027, "g").state)
    }

    @Test
    fun newDayAtTheTopOfTheRangeIsAnErrorAndLeavesTheState() {
        val s = game().copy(day = Long.MAX_VALUE)
        assertFailsWith<ArithmeticException> { TownCore.apply(s, NewDay) }
        assertEquals(Long.MAX_VALUE, s.day)
        assertEquals(Long.MAX_VALUE, TownCore.apply(s.copy(day = Long.MAX_VALUE - 1), NewDay).state.day)
    }

    // ---- incomes and queries -------------------------------------------------------------------

    @Test
    fun anUpgradeReplacesTheIncomeOfTheBuildingItUpgrades() {
        var s = game(towns = listOf(TownSetup("t", fern, 0, listOf("hall.1"))))
        assertEquals(Resources(gold = 500), TownCore.townIncome(s, "t"))
        s = newDay(build(s, "t", "market").state)
        s = newDay(build(s, "t", "hall.2").state)
        assertEquals(Resources(gold = 1000), TownCore.townIncome(s, "t"))
        assertEquals(listOf("hall.2", "market"), TownCore.activeBuildings(s, "t"))
        assertEquals(listOf("keep.1"), TownCore.missingRequirements(s, "t", "hall.3"))
    }

    @Test
    fun playerIncomeSumsOwnedTowns() {
        val s = game(
            players = listOf(rich, rich),
            towns = listOf(TownSetup("a", fern, 0, listOf("hall.1")), TownSetup("b", salt, 1, listOf("hall.1", "hall.2")), TownSetup("c", fern, 0, listOf("hall.1"))),
        )
        assertEquals(Resources(gold = 1000), TownCore.playerIncome(s, 0))
        assertEquals(Resources(gold = 1000), TownCore.playerIncome(s, 1))
        assertEquals(Resources(), TownCore.playerIncome(s, 5))
    }

    @Test
    fun unknownNamesRaiseThePythonErrorClasses() {
        val s = game()
        assertEquals("no such town 'q'", assertFailsWith<IllegalCommand> { TownCore.activeBuildings(s, "q") }.message)
        val k = assertFailsWith<TownKeyError> { TownCore.missingRequirements(s, "t1", "it's") }
        assertEquals("\"it's\"", k.message)
        assertEquals("it's", k.key)
        val f = assertFailsWith<TownKeyError> { TownCore.findBuilding(content, "faction.none", "market") }
        assertEquals("'faction.none'", f.message)
    }

    // ---- create_game ---------------------------------------------------------------------------

    private fun raw(vararg v: Any?) = RawResources(v.toList())

    private fun valueError(msg: String, players: Any?, towns: Any?) {
        val e = assertFailsWith<TownValueError> { TownCore.createGameChecked("g", content, players, towns) }
        assertEquals(msg, e.message)
    }

    @Test
    fun createGameRejectsWrongTypesLikePythonsTypeIsInt() {
        val ok = listOf(BigInteger.ONE, BigInteger.ONE, BigInteger.ONE, BigInteger.ONE, BigInteger.ONE, BigInteger.ONE, BigInteger.ONE)
        val msg = "players need resources: a Resources of ints 0..2147483647"
        val one = listOf(RawSetup("t", fern, BigInteger.ZERO, emptyList<String>()))
        TownCore.createGameChecked("g", content, listOf(RawResources(ok)), one)
        for (badValue in listOf<Any?>(true, false, "1", null, BigInteger.valueOf(-1), BigInteger.valueOf(cap + 1), BigInteger.TWO.pow(70), listOf(1))) {
            for (i in 0 until 7) {
                val v = ok.toMutableList<Any?>()
                v[i] = badValue
                valueError(msg, listOf(RawResources(v)), one)
            }
        }
        valueError(msg, listOf(Resources(gold = -1)), one)
        valueError(msg, listOf(Resources(gold = cap + 1)), one)
        TownCore.createGameChecked("g", content, listOf(Resources(gold = cap)), one)
        valueError("players need resources: a non-empty sequence of Resources", emptyList<Any?>(), one)
        valueError("players need resources: a non-empty sequence of Resources", "abc", one)
        valueError(msg, listOf(null), one)
        valueError(msg, listOf(listOf(1, 2, 3, 4, 5, 6, 7)), one)
        for (o in listOf<Any?>(true, false, "0", null, listOf(0))) {
            valueError("town 't': owner must be an int, got ${TownText.repr(o)}", listOf(RawResources(ok)), listOf(RawSetup("t", fern, o, emptyList<String>())))
        }
        valueError("town 't': faction must be a string", listOf(RawResources(ok)), listOf(RawSetup("t", 5, BigInteger.ZERO, emptyList<String>())))
        valueError("town 't': built must be a sequence of building ids", listOf(RawResources(ok)), listOf(RawSetup("t", fern, BigInteger.ZERO, "hall.1")))
        valueError("town 't': built must be a sequence of building ids", listOf(RawResources(ok)), listOf(RawSetup("t", fern, BigInteger.ZERO, listOf("hall.1", 5))))
        valueError("town id must be a non-empty string, got 1", listOf(RawResources(ok)), listOf(RawSetup(1, fern, BigInteger.ZERO, emptyList<String>())))
        valueError("town id must be a non-empty string, got '\\u3000'", listOf(RawResources(ok)), listOf(RawSetup("\u3000", fern, BigInteger.ZERO, emptyList<String>())))
        valueError("towns must be a sequence of TownSetup", listOf(RawResources(ok)), "t")
        valueError("towns must be TownSetup values, got None", listOf(RawResources(ok)), listOf(null))
        valueError("town 't': no such owner 1180591620717411303424", listOf(RawResources(ok)), listOf(RawSetup("t", fern, BigInteger.TWO.pow(70), emptyList<String>())))
    }

    @Test
    fun createGameChecksInPythonOrder() {
        val p = listOf(rich)
        // duplicate id before faction lookup, faction before owner, owner before buildings, then requirements
        valueError("duplicate town id 't'", p, listOf(TownSetup("t", fern, 0), TownSetup("t", "none", 0)))
        valueError("town 't': unknown faction 'none'", p, listOf(TownSetup("t", "none", 9, listOf("zzz"))))
        valueError("town 't': no such owner 9", p, listOf(TownSetup("t", fern, 9, listOf("zzz"))))
        valueError("town 't': unknown or duplicate building", p, listOf(TownSetup("t", fern, 0, listOf("hall.1", "hall.1"))))
        valueError("town 't': 'hall.2' requires hall.1, market", p, listOf(TownSetup("t", fern, 0, listOf("hall.2"))))
        // a town after a bad one is never looked at
        valueError("town 'a': 'market' requires hall.1", p, listOf(TownSetup("a", fern, 0, listOf("market")), TownSetup("", fern, 0)))
        valueError("town id must be a non-empty string, got ''", p, listOf(TownSetup("a", fern, 0), TownSetup("", fern, 0, listOf("zzz"))))
    }

    @Test
    fun theGameIdIsCoercedLikePythonsStr() {
        val one = listOf(TownSetup("t", fern, 0))
        fun id(v: Any?) = TownCore.createGameChecked(v, content, listOf(rich), one).gameId
        assertEquals("5", id(BigInteger.valueOf(5)))
        assertEquals("None", id(null))
        assertEquals("True", id(true))
        assertEquals("[1, 'a']", id(listOf(BigInteger.ONE, "a")))
        assertEquals("{'a': None}", id(linkedMapOf("a" to null)))
        assertEquals("h\u00E9", id("h\u00E9"))
    }

    // ---- canonical form and hash ---------------------------------------------------------------

    @Test
    fun stateHashCoversPolicyAndContent() {
        val a = TownCore.stateHash(game())
        assertNotEquals(a, TownCore.stateHash(game(policy = TownPolicy("ceil"))))
        assertNotEquals(a, TownCore.stateHash(game(c = pack { it.replace("\"cost\": {\"gold\": 500, \"wood\": 5}", "\"cost\": {\"gold\": 501, \"wood\": 5}") })))
        assertEquals(a, TownCore.stateHash(game(towns = listOf(TownSetup("t1", fern, 0, listOf("hall.1"))))))
        assertEquals(TownCore.stateHash(game(towns = listOf(TownSetup("t1", fern, 0, listOf("market", "hall.1"))))), TownCore.stateHash(game(towns = listOf(TownSetup("t1", fern, 0, listOf("hall.1", "market"))))))
        assertTrue(TownCore.canonicalText(game()).startsWith("{\"content\":{\"factions\":[{\"buildings\":[{\"base_growth\":13,\"cost\":{\"crystal\":0,"))
    }

    @Test
    fun canonicalTextEscapesNonAsciiAsUtf16UnitsAndSortsKeys() {
        val s = TownCore.createGame("g\u00E9\uD83D\uDE00", content, listOf(rich), listOf(TownSetup("t\u200B", fern, 0)))
        val t = TownCore.canonicalText(s)
        assertTrue("\"game_id\":\"g\\u00e9\\ud83d\\ude00\"" in t)
        assertTrue("\"id\":\"t\\u200b\"" in t)
        t.toByteArray(Charsets.US_ASCII)
    }

    // ---- loader --------------------------------------------------------------------------------

    @Test
    fun packsAreSortedByCodePointNotByUtf16Unit() {
        val c = TownCore.parseTownPackText(TownVectors.packs.getValue("unicode").str(), "towns.json")
        assertEquals(listOf("fac.\u00E9", "fac.\uFFEE", "fac.\uD800\uDC00"), c.factions.map { it.id })
        assertEquals(listOf("d.\u00E9", "d.\uFFEE", "h.\uD800\uDC00", "hall.\u00E9", "hall.\uFFEE", "hall.\uD800\uDC00", "keep.\u4E2D", "keep.\uD83D\uDE00"), c.factions[0].buildings.map { it.id })
    }

    @Test
    fun floatsNansDuplicateKeysAndBoolsAreRejected() {
        assertEquals(Category.FLOAT, bad { it.replace("\"base_growth\": 13", "\"base_growth\": 13.0") }.category)
        assertEquals(Category.FLOAT, bad { it.replace("\"bonus\": 4", "\"bonus\": NaN") }.category)
        assertEquals(Category.FLOAT, bad { it.replace("\"bonus\": 4", "\"bonus\": 4e0") }.category)
        val dup = bad { it.replace("\"schema_version\": 1,", "\"schema_version\": 1, \"schema_version\": 1,") }
        assertEquals(Category.DUPLICATE_KEY, dup.category)
        assertEquals("towns.json: towns.json: duplicate key 'schema_version'", dup.message)
        val b = bad { it.replace("\"fort\": true", "\"fort\": 1") }
        assertEquals("towns.factions[0].buildings[5].fort: expected boolean", b.message)
        val g = bad { it.replace("\"base_growth\": 13", "\"base_growth\": true") }
        assertEquals("towns.factions[0].buildings[8].dwelling.base_growth: expected integer, got bool", g.message)
        assertEquals("towns.schema_version: unsupported", bad { it.replace("\"schema_version\": 1", "\"schema_version\": 2") }.message)
    }

    @Test
    fun loaderIntegersAreBoundedByIntMax() {
        val e = bad { it.replace("\"base_growth\": 13", "\"base_growth\": 2147483648") }
        assertEquals(Category.RANGE, e.category)
        assertEquals("towns.factions[0].buildings[8].dwelling.base_growth: 2147483648 out of range 0..2147483647", e.message)
        pack { it.replace("\"base_growth\": 13", "\"base_growth\": 2147483647") }
        val huge = bad { it.replace("\"base_growth\": 13", "\"base_growth\": 99999999999999999999999999") }
        assertEquals(Category.RANGE, huge.category)
        assertEquals(Category.LENGTH, bad { it.replace("[1, 2]", "[1, 2, 3]") }.category)
    }

    @Test
    fun theFirstFailingCheckDecidesTheMessage() {
        // unknown reference is reported before the upgrade rule, in id order
        val e = bad { it.replace("\"requires\": [\"hall.1\", \"market\"],\n         \"upgrades\": \"hall.1\"", "\"requires\": [\"market\", \"zzz\"],\n         \"upgrades\": \"hall.1\"") }
        assertEquals("faction.fernwood.hall.2: unknown building 'zzz'", e.message)
        assertEquals(TownCategory.UNKNOWN_BUILDING, e.category)
        val cyc = bad { it.replace("{\"id\": \"hall.1\", \"cost\": {}, \"requires\": [], \"income\": {\"gold\": 500}},", "{\"id\": \"hall.1\", \"cost\": {}, \"requires\": [\"hall.2\"], \"income\": {\"gold\": 500}},") }
        assertEquals(TownCategory.CYCLE, cyc.category)
        assertEquals("faction.fernwood: requirement cycle among den.1u, hall.1, hall.2, hall.3, hall.4, market", cyc.message)
    }

    // ---- python text helpers -------------------------------------------------------------------

    @Test
    fun reprFollowsPython() {
        assertEquals("'abc'", TownText.repr("abc"))
        assertEquals("\"it's\"", TownText.repr("it's"))
        assertEquals("'a\\'b\"c'", TownText.repr("a'b\"c"))
        assertEquals("'a\\\\b'", TownText.repr("a\\b"))
        assertEquals("'a\\tb\\nc\\rd'", TownText.repr("a\tb\nc\rd"))
        assertEquals("'\\x01\\x7f\\x85\\xad'", TownText.repr("\u0001\u007f\u0085\u00AD"))
        assertEquals("'\\u200b\\u2028\\ue000'", TownText.repr("\u200B\u2028\uE000"))
        assertEquals("'\\U000e0001\\U0010ffff'", TownText.repr("\uDB40\uDC01\uDBFF\uDFFF"))
        assertEquals("'\u00E9\u4E2D\uD83D\uDE00'", TownText.repr("\u00E9\u4E2D\uD83D\uDE00"))
        assertEquals("'\\xa0'", TownText.repr("\u00A0"))
        assertEquals("None", TownText.repr(null as Any?))
        assertEquals("[True, 1, {'a': None}]", TownText.repr(listOf(true, BigInteger.ONE, linkedMapOf("a" to null))))
    }

    @Test
    fun blankFollowsPythonStrip() {
        for (s in listOf("", " ", "\t\n\r", "\u00A0", "\u1680", "\u2003", "\u2028", "\u3000", "\u001c", "\u0085", "\u001f")) assertTrue(TownText.blank(s), s.map { it.code }.toString())
        for (s in listOf("a", " a ", "\u200B", "\u0000", "\u180E", "\uFEFF")) assertFalse(TownText.blank(s), s.map { it.code }.toString())
    }
}
