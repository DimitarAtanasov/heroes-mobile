package h3.sim.town

import h3.sim.Canonical
import h3.sim.DatapackError
import h3.sim.Pcg32
import h3.sim.big
import h3.sim.list
import h3.sim.loadVector
import h3.sim.obj
import h3.sim.u64
import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

internal fun Any?.str(): String = this as String
internal fun Any?.lng(): Long = (this as BigInteger).toLong()
internal fun Any?.i32(): Int = Math.toIntExact((this as BigInteger).toLong())

/** Canonical text of a vector or engine value: BigInteger, Int and Long all print as JSON integers. */
internal fun canonText(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

internal fun resMap(r: Resources): Map<String, Any?> {
    val m = LinkedHashMap<String, Any?>()
    for ((n, v) in RESOURCE_NAMES.zip(r.values())) m[n] = v
    return m
}

internal fun eventMap(e: TownEvent): Map<String, Any?> = when (e) {
    is BuildingBuilt -> linkedMapOf(
        "type" to "BuildingBuilt", "town" to e.town, "building" to e.building, "player" to e.player,
        "cost" to resMap(e.cost), "treasury" to resMap(e.treasury),
    )
    is TownDayStarted -> linkedMapOf("type" to "TownDayStarted", "day" to e.day)
}

internal fun commandOf(c: Any?): TownCommand {
    val m = c.obj()
    return when (val t = m["type"].str()) {
        "Build" -> Build(m["player"].lng(), m["town"].str(), m["building"].str())
        "NewDay" -> NewDay
        else -> throw AssertionError("unknown command type $t")
    }
}

/** The Python exception class name of a Kotlin error (the vectors record `type(e).__name__`). */
internal fun kindOf(e: Throwable): String = when (e) {
    is IllegalCommand -> "IllegalCommand"
    is TownValueError -> "ValueError"
    is TownKeyError -> "KeyError"
    is ArithmeticException -> if (e.message!!.startsWith("Fraction(")) "ZeroDivisionError" else "ArithmeticException"
    else -> e::class.simpleName ?: "?"
}

internal fun assertError(expected: Any?, e: Throwable, what: String) {
    val m = expected.obj()
    assertEquals(m["kind"].str(), kindOf(e), "$what kind")
    assertEquals(m["message"].str(), e.message, "$what message")
}

internal fun resOf(v: Any?): Resources = Resources.of(v.list().map { it.lng() })

internal fun policyOf(v: Any?): TownPolicy = TownPolicy(v.obj()["citadel_rounding"].str())

/** A descriptor's `players`: a list of `{"res": [7 values]}` / `{"raw": v}`, or `{"raw": v}` for the whole. */
internal fun playersOf(d: Any?): Any? =
    if (d is Map<*, *>) d["raw"] else d.list().map { x -> x.obj().let { m -> if ("res" in m) RawResources(m["res"].list()) else m["raw"] } }

internal fun townsOf(d: Any?): Any? = if (d is Map<*, *>) d["raw"] else d.list().map { x ->
    x.obj().let { m ->
        if ("setup" in m) m["setup"].obj().let { RawSetup(it["id"], it["faction"], it["owner"], it["built"]) } else m["raw"]
    }
}

/** Typed arguments of a descriptor whose values all have the right types (successful `create` cases and traces). */
internal fun typedPlayers(d: Any?): List<Resources> = d.list().map { resOf(it.obj()["res"]) }

internal fun typedTowns(d: Any?): List<TownSetup> = d.list().map {
    it.obj()["setup"].obj().let { s -> TownSetup(s["id"].str(), s["faction"].str(), s["owner"].lng(), s["built"].list().map { b -> b.str() }) }
}

internal object TownVectors {
    val doc: Map<String, Any?> by lazy { loadVector("town.json") }
    val packs: Map<String, Any?> by lazy { doc["packs"].obj() }

    fun content(name: String): TownContent = TownCore.parseTownPackText(packs.getValue(name).str(), "towns.json")

    /** A `game_id` is any JSON value (Python `str(game_id)` coerces it). */
    fun create(c: Map<String, Any?>): TownState = TownCore.createGameChecked(
        c["game_id"], content(c["pack"].str()), playersOf(c["players"]), townsOf(c["towns"]), policyOf(c["policy"]),
    )

    fun runQuery(s: TownState, q: Map<String, Any?>): Any? {
        val a = q["args"].list()
        return when (val fn = q["fn"].str()) {
            "active_buildings" -> TownCore.activeBuildings(s, a[0].str())
            "town_income" -> TownCore.townIncome(s, a[0].str()).values()
            "player_income" -> TownCore.playerIncome(s, a[0].lng()).values()
            "dwellings" -> TownCore.dwellings(s, a[0].str()).map { listOf(it.level, it.creature, it.baseGrowth) }
            "growth_pools" -> TownCore.growthPools(
                s, a[0].str(), a[1].list().map { p -> p.list().let { GrowthPool(it[0].str(), it[1].lng(), it[2].lng()) } },
            ).map { listOf(it.id, it.available, it.growth) }
            "missing_requirements" -> TownCore.missingRequirements(s, a[0].str(), a[1].str())
            else -> throw AssertionError("unknown query $fn")
        }
    }

    fun checkQuery(s: TownState, q: Map<String, Any?>, what: String) {
        val err = q["error"]
        if (err != null) {
            val e = assertFailsWith<Throwable>("$what ${q["fn"]} ${canonText(q["args"])}") { runQuery(s, q) }
            assertError(err, e, "$what ${q["fn"]} ${canonText(q["args"])}")
        } else {
            assertEquals(canonText(q["result"]), canonText(runQuery(s, q)), "$what ${q["fn"]} ${canonText(q["args"])}")
        }
    }

    /** Resources from a canonical tree object (keys are sorted in the file, so read them by name). */
    fun resByName(r: Any?): Resources = r.obj().let { o -> Resources.of(RESOURCE_NAMES.map { o.getValue(it).lng() }) }

    fun building(m: Map<String, Any?>): Building {
        val g = m["growth_bonus"].list()
        return Building(
            m["id"].str(), resByName(m["cost"]), m["requires"].list().map { it.str() }, m["upgrades"].str(),
            resByName(m["income"]), m["fort"] as Boolean, Pair(g[0].lng(), g[1].lng()), m["dwelling_level"].i32(),
            m["creature"].str(), m["base_growth"].lng(), m["horde_level"].i32(), m["horde_bonus"].lng(), m["player_unique"].str(),
        )
    }

    /** Rebuild a state from its canonical tree, including hand-built ones the loader and `createGame` would refuse. */
    fun stateFromCanonical(v: Any?): TownState {
        val m = v.obj()
        return TownState(
            m["game_id"].str(), policyOf(m["policy"]),
            TownContent(m["content"].obj()["factions"].list().map { f ->
                f.obj().let { fo -> Faction(fo["id"].str(), fo["buildings"].list().map { building(it.obj()) }) }
            }),
            m["players"].list().map { resByName(it) },
            m["towns"].list().map { t ->
                t.obj().let { o ->
                    Town(o["id"].str(), o["faction"].str(), o["owner"].lng(), o["built"].list().map { it.str() }, o["built_today"] as Boolean)
                }
            },
            m["day"].lng(),
        )
    }
}

/** Conformance of the Kotlin town core against `vectors/town.json` (docs/specs/conformance-town.md). */
class TownConformanceTest {
    private val doc get() = TownVectors.doc

    @Test
    fun shippedPacksParse() {
        for (name in TownVectors.packs.keys) TownVectors.content(name)
        val hash = TownCore.contentHash(TownVectors.content("test"))
        assertEquals(doc["golden"].obj()["content_hash"].str(), hash)
        assertTrue(hash.startsWith("629836f9f419a851"))
    }

    @Test
    fun validPacks() {
        val cases = doc["pack_valid"].list().map { it.obj() }
        assertTrue(cases.size >= 30)
        val hashes = LinkedHashMap<String, String>()
        for (c in cases) {
            val name = c["name"].str()
            val content = TownCore.parseTownPackText(c["text"].str(), "towns.json")
            val hash = TownCore.contentHash(content)
            assertEquals(c["hash"].str(), hash, name)
            assertEquals(
                canonText(c["factions"]),
                canonText(content.factions.map { f -> linkedMapOf("id" to f.id, "buildings" to f.buildings.map { it.id }) }),
                name,
            )
            hashes[name] = hash
            c["same_hash_as"]?.let { assertEquals(hashes.getValue(it.str()), hash, name) }
        }
    }

    @Test
    fun invalidPacksGiveThePythonMessageAndCategory() {
        val cases = doc["pack_invalid"].list().map { it.obj() }
        assertTrue(cases.size >= 200)
        val seen = LinkedHashSet<String>()
        for (c in cases) {
            val name = c["name"].str()
            val e = assertFailsWith<DatapackError>(name) { TownCore.parseTownPackText(c["text"].str(), "towns.json") }
            assertEquals(c["category"].str(), e.category, name)
            // the JSON parser texts differ between Python and Kotlin: invalid_json is compared by category only
            if (c["category"].str() != "invalid_json") assertEquals(c["message"].str(), e.message, name)
            seen.add(e.category)
        }
        assertEquals(17, seen.size, seen.toString())
    }

    @Test
    fun policies() {
        var bad = 0
        for (c in doc["policies"].list().map { it.obj() }) {
            val msg = c["message"]
            if (msg == null) {
                assertEquals(c["citadel_rounding"].str(), TownPolicy(c["citadel_rounding"].str()).citadelRounding)
            } else {
                bad++
                val e = assertFailsWith<TownValueError>(canonText(c)) { TownPolicy(c["citadel_rounding"].str()) }
                assertEquals(msg.str(), e.message)
            }
        }
        assertTrue(bad >= 15)
    }

    @Test
    fun weeklyGrowth() {
        val cases = doc["weekly_growth"].list().map { it.obj() }
        assertTrue(cases.size >= 1000)
        var errors = 0
        for (c in cases) {
            val b = c["bonus"].list()
            val call = { TownCore.weeklyGrowth(c["base"].lng(), Pair(b[0].lng(), b[1].lng()), c["horde"].lng(), TownPolicy(c["mode"].str())) }
            val err = c["error"]
            if (err != null) {
                errors++
                assertError(err, assertFailsWith<ArithmeticException>(canonText(c)) { call() }, canonText(c))
            } else {
                assertEquals(c["result"].lng(), call(), canonText(c))
            }
        }
        assertEquals(6, errors)
    }

    @Test
    fun namedStreams() {
        for (c in doc["streams"].list().map { it.obj() }) {
            val r = TownCore.townRng(c["seed"].big(), c["game_id"].str())
            assertEquals(c["state"].u64(), r.state, canonText(c))
            val got = listOf(r.range(0, 1000), r.range(0, 1000), r.range(0, 1000), r.range(0, (1L shl 31) - 1), r.range(0, 1L shl 32))
            assertEquals(c["draws"].list().map { it.lng() }, got, canonText(c))
            assertEquals(c["after"].u64(), r.state)
        }
    }

    @Test
    fun createGame() {
        val kinds = LinkedHashSet<String>()
        var ok = 0
        for (c in doc["create"].list().map { it.obj() }) {
            val name = c["name"].str()
            val err = c["error"]
            if (err == null) {
                ok++
                val s = TownVectors.create(c)
                assertEquals(c["hash"].str(), TownCore.stateHash(s), name)
                assertEquals(c["canonical"].str(), TownCore.canonicalText(s), name)
                // the typed entry point gives the same state when every value has the right type
                val gid = c["game_id"]
                if (gid is String && c["players"] is List<*> && c["towns"] is List<*>) {
                    val t = TownCore.createGame(gid, TownVectors.content(c["pack"].str()), typedPlayers(c["players"]), typedTowns(c["towns"]), policyOf(c["policy"]))
                    assertEquals(c["hash"].str(), TownCore.stateHash(t), "$name typed")
                }
            } else {
                val e = assertFailsWith<TownValueError>(name) { TownVectors.create(c) }
                assertError(err, e, name)
                kinds.add(e.message!!.substringBefore(':').substringBefore(',').take(24))
            }
        }
        assertTrue(ok >= 30, "ok $ok")
        assertTrue(kinds.size >= 12, kinds.toString())
    }

    @Test
    fun tracesStepByStep() {
        val traces = doc["traces"].list().map { it.obj() }
        assertTrue(traces.size >= 70)
        var steps = 0
        var illegal = 0
        for (t in traces) {
            val name = t["name"].str()
            var s = TownVectors.create(t)
            val rng = TownCore.townRng(t["seed"].big(), TownText.str(t["game_id"]))
            assertEquals(t["initial_hash"].str(), TownCore.stateHash(s), name)
            assertEquals(t["initial_rng"].u64(), rng.state, name)
            for (q in t["initial_queries"].list()) TownVectors.checkQuery(s, q.obj(), "$name initial")
            for ((i, st) in t["steps"].list().map { it.obj() }.withIndex()) {
                steps++
                val cmd = commandOf(st["cmd"])
                val err = st["error"]
                val before = s
                val streamBefore = rng.state
                if (err != null) {
                    illegal++
                    val e = assertFailsWith<RuntimeException>("$name step $i") { TownCore.apply(s, cmd, rng) }
                    assertError(err, e, "$name step $i")
                    assertEquals(before, s)
                } else {
                    val r = TownCore.apply(s, cmd, rng)
                    assertEquals(canonText(st["events"]), canonText(r.events.map { eventMap(it) }), "$name step $i events")
                    s = r.state
                    for (q in st["queries"].list()) TownVectors.checkQuery(s, q.obj(), "$name step $i")
                }
                assertEquals(streamBefore, rng.state, "$name step $i stream touched")
                assertEquals(st["hash"].str(), TownCore.stateHash(s), "$name step $i hash")
                assertEquals(st["rng"].u64(), rng.state, "$name step $i rng")
            }
            assertEquals(t["final_canonical"].str(), TownCore.canonicalText(s), name)
            for (q in t["final_queries"].list()) TownVectors.checkQuery(s, q.obj(), "$name final")
        }
        assertTrue(steps >= 2000, "steps $steps")
        assertTrue(illegal >= 500, "illegal $illegal")
    }

    @Test
    fun queryCases() {
        val cases = doc["queries"].list().map { it.obj() }
        assertTrue(cases.size >= 25)
        var errors = 0
        for (c in cases) {
            val s = TownVectors.stateFromCanonical(c["state"])
            assertEquals(c["hash"].str(), TownCore.stateHash(s), c["name"].str())
            if (c["query"].obj()["error"] != null) errors++
            TownVectors.checkQuery(s, c["query"].obj(), c["name"].str())
        }
        assertTrue(errors >= 10)
    }

    @Test
    fun handBuiltStates() {
        val cases = doc["states"].list().map { it.obj() }
        assertTrue(cases.size >= 80)
        var errors = 0
        var keyErrors = 0
        var queryErrors = 0
        for (c in cases) {
            val name = c["name"].str()
            val s = TownVectors.stateFromCanonical(c["state"])
            assertEquals(canonText(c["state"]), TownCore.canonicalText(s), "$name canonical")
            assertEquals(c["hash"].str(), TownCore.stateHash(s), name)
            val rng = TownCore.townRng(c["seed"].big(), s.gameId)
            assertEquals(c["rng_before"].u64(), rng.state, name)
            val qs = c["queries"].list().map { it.obj() }
            for (q in qs) {
                if (q["error"] != null) queryErrors++
                TownVectors.checkQuery(s, q, "$name before")
            }
            val cmdTree = c["cmd"]
            if (cmdTree != null) {
                val cmd = commandOf(cmdTree)
                val err = c["error"]
                if (err != null) {
                    errors++
                    if (err.obj()["kind"] == "KeyError") keyErrors++
                    assertError(err, assertFailsWith<RuntimeException>(name) { TownCore.apply(s, cmd, rng) }, name)
                } else {
                    val r = TownCore.apply(s, cmd, rng)
                    assertEquals(canonText(c["events"]), canonText(r.events.map { eventMap(it) }), "$name events")
                    assertEquals(c["hash_after"].str(), TownCore.stateHash(r.state), "$name hash after")
                    assertEquals(c["canonical_after"].str(), TownCore.canonicalText(r.state), "$name canonical after")
                    for (q in c["queries_after"].list()) TownVectors.checkQuery(r.state, q.obj(), "$name after")
                }
            }
            assertEquals(c["rng_after"].u64(), rng.state, "$name rng")
        }
        assertTrue(errors >= 15, "errors $errors")
        assertTrue(keyErrors >= 1)
        assertTrue(queryErrors >= 20, "query errors $queryErrors")
    }

    @Test
    fun goldenRun() {
        val g = doc["golden"].obj()
        val pinnedState = "0360ce8861ca3b4a12f8210f0d8111b57c328becb8c433d41c59d6a6d257aae7"
        val pinnedGrowth = "b4108c58f2e6e95cbaa19fbfb7694e66a74067558840c614cbffc71c96549322"
        assertEquals(pinnedState, g["hash"].str())
        assertEquals(pinnedGrowth, g["growth_digest"].str())

        fun run(policy: TownPolicy): Triple<TownState, Int, List<GrowthPool>> {
            var s = TownCore.createGame("golden", TownVectors.content("test"), typedPlayers(g["players"]), typedTowns(g["towns"]), policy)
            val rng: Pcg32 = TownCore.townRng(2026, "golden")
            var events = 0
            for (day in g["script"].list()) {
                for (c in day.list()) {
                    val (p, t, b) = c.list()
                    val r = TownCore.apply(s, Build(p.lng(), t.str(), b.str()), rng)
                    s = r.state
                    events += r.events.size
                }
                val r = TownCore.apply(s, NewDay, rng)
                s = r.state
                events += r.events.size
            }
            return Triple(s, events, s.towns.flatMap { TownCore.growthPools(s, it.id) })
        }

        val (s, events, pools) = run(DEFAULT_POLICY)
        assertEquals(pinnedState, TownCore.stateHash(s))
        assertEquals(g["events"].i32(), events)
        assertEquals(24, events)
        assertEquals(8L, s.day)
        assertEquals(canonText(g["pools"]), canonText(pools.map { listOf(it.id, it.available, it.growth) }))
        assertEquals(canonText(g["treasuries"]), canonText(s.players.map { it.values() }))

        val digest = listOf("floor", "ceil", "nearest").map { mode ->
            listOf(mode, run(TownPolicy(mode)).third.map { listOf(it.id, it.available, it.growth) })
        }
        assertEquals(pinnedGrowth, Canonical.hash(digest))
        assertEquals(canonText(g["growth_modes"]), canonText(digest))
    }
}
