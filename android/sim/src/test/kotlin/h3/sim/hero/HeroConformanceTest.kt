package h3.sim.hero

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
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

internal fun Any?.str(): String = this as String
internal fun Any?.lng(): Long = (this as BigInteger).toLong()
internal fun Any?.i32(): Int = Math.toIntExact((this as BigInteger).toLong())

/** Canonical text of a vector or engine value: BigInteger, Int and Long all print as JSON integers. */
internal fun canonText(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

/** A draw source that counts calls and delegates to a real stream. */
internal class CountingDraw(private val rng: Pcg32) : HeroDraw {
    var calls = 0
    override fun range(lo: Long, hi: Long): Long {
        calls++
        return rng.range(lo, hi)
    }
}

/** A draw source that fails the test if it is touched (commands that must not draw). */
internal object NoDraw : HeroDraw {
    override fun range(lo: Long, hi: Long): Long = throw AssertionError("rng used: range($lo, $hi)")
}

internal fun eventMap(e: HeroEvent): Map<String, Any?> = when (e) {
    is XPGained -> linkedMapOf("type" to "XPGained", "hero" to e.hero, "amount" to e.amount, "xp" to e.xp)
    is LevelGained -> linkedMapOf("type" to "LevelGained", "hero" to e.hero, "level" to e.level)
    is PrimaryGained -> linkedMapOf("type" to "PrimaryGained", "hero" to e.hero, "skill" to e.skill, "value" to e.value)
    is SkillOffered -> linkedMapOf(
        "type" to "SkillOffered", "hero" to e.hero, "level" to e.level,
        "offers" to e.offers.map { linkedMapOf<String, Any?>("skill" to it.skill, "level" to it.level) },
    )
    is SkillLearned -> linkedMapOf("type" to "SkillLearned", "hero" to e.hero, "skill" to e.skill, "level" to e.level)
}

internal fun commandOf(c: Any?): HeroCommand {
    val m = c.obj()
    return when (val t = m["type"].str()) {
        "GainXP" -> GainXP(m["hero"].str(), m["amount"].lng())
        "ChooseSkill" -> ChooseSkill(m["hero"].str(), m["index"].lng())
        else -> throw AssertionError("unknown command type $t")
    }
}

private fun pairs(v: Any?): List<Pair<String, Long>> = v.list().map { p -> p.list().let { Pair(it[0].str(), it[1].lng()) } }

internal fun policyOf(v: Any?): HeroPolicy = v.obj().let { HeroPolicy(it["offer_mode"].str(), it["offer_fill"].str()) }

/** Rebuild a state from its canonical tree (a vector `state`), including hand-built ones the loader would refuse. */
internal fun stateFromCanonical(v: Any?): HeroState {
    val m = v.obj()
    val r = m["rules"].obj()
    val c = m["class_def"].obj()
    val h = m["hero"].obj()
    return HeroState(
        policyOf(m["policy"]),
        HeroRules(
            r["xp_table"].list().map { it.lng() }, r["max_secondary"].i32(), r["skill_levels"].i32(),
            r["primary_high_from_level"].i32(), r["skills"].list().map { it.str() },
        ),
        HeroClass(
            c["id"].str(), c["start_primary"].list().map { it.i32() }, c["primary_low"].list().map { it.lng() },
            c["primary_high"].list().map { it.lng() }, pairs(c["secondary_weights"]),
        ),
        Hero(
            h["id"].str(), h["hero_class"].str(), h["level"].i32(), h["xp"].lng(), h["attack"].i32(),
            h["defense"].i32(), h["power"].i32(), h["knowledge"].i32(),
            h["secondary"].list().map { SecondarySkill(it.obj()["skill"].str(), it.obj()["level"].i32()) },
            h["offer"].list().map { SkillOffer(it.obj()["skill"].str(), it.obj()["level"].i32()) },
        ),
    )
}

internal object HeroVectors {
    val doc: Map<String, Any?> by lazy { loadVector("hero.json") }
    val packs: Map<String, Any?> by lazy { doc["packs"].obj() }

    fun content(name: String): HeroContent = HeroCore.parseHeroPackText(packs.getValue(name).str(), "hero.json")

    fun create(c: Map<String, Any?>): HeroState = HeroCore.createHero(
        c["hero"].str(), c["class"].str(), content(c["pack"].str()), pairs(c["secondary"]), policyOf(c["policy"]),
    )
}

/** Conformance of the Kotlin hero core against `vectors/hero.json` (docs/specs/conformance-hero.md). */
class HeroConformanceTest {
    private val doc get() = HeroVectors.doc

    @Test
    fun shippedPacksParseAndTheTestPackHashMatchesThePin() {
        for (name in HeroVectors.packs.keys) HeroVectors.content(name)
        val g = doc["golden"].obj()
        val hash = HeroCore.contentHash(HeroVectors.content("test"))
        assertEquals(g["content_hash"].str(), hash)
        assertTrue(hash.startsWith("2720746c773ed8ad"))
    }

    @Test
    fun validPacks() {
        val cases = doc["pack_valid"].list().map { it.obj() }
        assertTrue(cases.size >= 15)
        val hashes = LinkedHashMap<String, String>()
        for (c in cases) {
            val name = c["name"].str()
            val content = HeroCore.parseHeroPackText(c["text"].str(), "hero.json")
            val hash = HeroCore.contentHash(content)
            assertEquals(c["hash"].str(), hash, name)
            assertEquals(c["classes"].list().map { it.str() }, content.classes.map { it.id }, name)
            assertEquals(c["skills"].list().map { it.str() }, content.rules.skills, name)
            assertEquals(c["xp_table"].list().map { it.lng() }, content.rules.xpTable, name)
            hashes[name] = hash
            c["same_hash_as"]?.let { assertEquals(hashes.getValue(it.str()), hash, name) }
        }
    }

    @Test
    fun invalidPacksGiveThePythonMessageAndCategory() {
        val cases = doc["pack_invalid"].list().map { it.obj() }
        assertTrue(cases.size >= 150)
        val seen = LinkedHashSet<String>()
        for (c in cases) {
            val name = c["name"].str()
            val e = assertFailsWith<DatapackError>(name) { HeroCore.parseHeroPackText(c["text"].str(), "hero.json") }
            assertEquals(c["category"].str(), e.category, name)
            // the JSON parser texts differ between Python and Kotlin: invalid_json is compared by category only
            if (c["category"].str() != "invalid_json") assertEquals(c["message"].str(), e.message, name)
            seen.add(e.category)
        }
        assertEquals(13, seen.size)
    }

    @Test
    fun levelForXp() {
        for (c in doc["level_for_xp"].list().map { it.obj() }) {
            assertEquals(c["level"].i32(), HeroCore.levelForXp(c["xp"].lng(), c["table"].list().map { it.lng() }), canonText(c))
        }
    }

    @Test
    fun policies() {
        var bad = 0
        for (c in doc["policies"].list().map { it.obj() }) {
            val msg = c["message"]
            if (msg == null) {
                val p = HeroPolicy(c["offer_mode"].str(), c["offer_fill"].str())
                assertEquals(c["offer_mode"].str(), p.offerMode)
            } else {
                bad++
                val e = assertFailsWith<HeroValueError>(canonText(c)) { HeroPolicy(c["offer_mode"].str(), c["offer_fill"].str()) }
                assertEquals(msg.str(), e.message)
                assertEquals(HeroValueError.POLICY, e.category)
            }
        }
        assertTrue(bad >= 5)
    }

    @Test
    fun createHero() {
        val cats = LinkedHashSet<String>()
        for (c in doc["create"].list().map { it.obj() }) {
            val name = c["name"].str()
            val err = c["error"]
            if (err == null) {
                val s = HeroVectors.create(c)
                assertEquals(c["hash"].str(), HeroCore.stateHash(s), name)
                assertEquals(c["canonical"].str(), HeroCore.canonicalText(s), name)
            } else {
                val e = assertFailsWith<HeroValueError>(name) { HeroVectors.create(c) }
                assertEquals(err.obj()["message"].str(), e.message, name)
                assertEquals(err.obj()["category"].str(), e.category, name)
                cats.add(e.category)
            }
        }
        assertEquals(5, cats.size)
    }

    @Test
    fun namedStreams() {
        for (c in doc["streams"].list().map { it.obj() }) {
            val r = HeroCore.heroRng(c["seed"].big(), c["hero"].str())
            assertEquals(c["state"].u64(), r.state, canonText(c))
            val got = listOf(r.range(0, 1000), r.range(0, 1000), r.range(0, 1000), r.range(0, (1L shl 31) - 1), r.range(0, 1L shl 32))
            assertEquals(c["draws"].list().map { it.lng() }, got, canonText(c))
            assertEquals(c["after"].u64(), r.state)
        }
    }

    @Test
    fun tracesStepByStep() {
        val traces = doc["traces"].list().map { it.obj() }
        assertTrue(traces.size >= 100)
        var steps = 0
        var illegal = 0
        for (t in traces) {
            val name = t["name"].str()
            var s = HeroVectors.create(t)
            val rng = HeroCore.heroRng(t["seed"].big(), t["hero"].str())
            assertEquals(t["initial_hash"].str(), HeroCore.stateHash(s), name)
            assertEquals(t["initial_rng"].u64(), rng.state, name)
            val draw = CountingDraw(rng)
            for ((i, st) in t["steps"].list().map { it.obj() }.withIndex()) {
                steps++
                val cmd = commandOf(st["cmd"])
                val err = st["error"]
                if (err != null) {
                    illegal++
                    val before = HeroCore.stateHash(s)
                    val calls = draw.calls
                    val stateBefore = rng.state
                    val e = assertFailsWith<IllegalCommand>("$name step $i") { HeroCore.apply(s, cmd, draw) }
                    assertEquals(err.str(), e.message, "$name step $i")
                    assertEquals(calls, draw.calls, "$name step $i drew")
                    assertEquals(stateBefore, rng.state)
                    assertEquals(before, HeroCore.stateHash(s))
                } else {
                    val r = HeroCore.apply(s, cmd, draw)
                    assertEquals(canonText(st["events"]), canonText(r.events.map { eventMap(it) }), "$name step $i events")
                    s = r.state
                }
                assertEquals(st["hash"].str(), HeroCore.stateHash(s), "$name step $i hash")
                assertEquals(st["rng"].u64(), rng.state, "$name step $i rng")
            }
            assertEquals(t["final_canonical"].str(), HeroCore.canonicalText(s), name)
        }
        assertTrue(steps >= 2000, "steps $steps")
        assertTrue(illegal >= 100, "illegal $illegal")
    }

    @Test
    fun offerSweep() {
        val sweep = doc["offer_sweep"].list().map { it.obj() }
        assertTrue(sweep.size >= 300)
        val content = HeroVectors.content("test")
        for (c in sweep) {
            var s = HeroCore.createHero("h1", c["class"].str(), content, pairs(c["secondary"]), policyOf(c["policy"]))
            s = HeroCore.apply(s, GainXP("h1", 1000), HeroCore.heroRng(c["seed"].big(), "h1")).state
            assertEquals(canonText(c["offer"]), canonText(s.hero.offer.map { listOf(it.skill, it.level) }), canonText(c))
            assertEquals(listOf(s.hero.attack, s.hero.defense, s.hero.power, s.hero.knowledge), c["primary"].list().map { it.i32() })
            assertEquals(c["hash"].str(), HeroCore.stateHash(s), canonText(c))
        }
    }

    @Test
    fun handBuiltStates() {
        val cases = doc["states"].list().map { it.obj() }
        assertTrue(cases.size >= 80)
        var errors = 0
        for (c in cases) {
            val name = c["name"].str()
            val s = stateFromCanonical(c["state"])
            assertEquals(canonText(c["state"]), HeroCore.canonicalText(s), "$name canonical")
            assertEquals(c["hash"].str(), HeroCore.stateHash(s), name)
            val rng = HeroCore.heroRng(c["seed"].big(), s.hero.id)
            assertEquals(c["rng_before"].u64(), rng.state, name)
            val draw = CountingDraw(rng)
            val cmd = commandOf(c["cmd"])
            val err = c["error"]
            if (err != null) {
                errors++
                val e = assertFailsWith<IllegalCommand>(name) { HeroCore.apply(s, cmd, draw) }
                assertEquals(err.str(), e.message, name)
                assertEquals(0, draw.calls, "$name drew")
            } else {
                val r = HeroCore.apply(s, cmd, draw)
                assertEquals(canonText(c["events"]), canonText(r.events.map { eventMap(it) }), "$name events")
                assertEquals(c["hash_after"].str(), HeroCore.stateHash(r.state), "$name hash after")
            }
            assertEquals(c["rng_after"].u64(), rng.state, "$name rng")
        }
        assertTrue(errors >= 30)
    }

    @Test
    fun goldenRun() {
        val g = doc["golden"].obj()
        val pinned = "f18f5ebb1e249b9b4f35d707add6b89a01b19310554a723d3b048a19583022f9"
        assertEquals(pinned, g["hash"].str())
        var s = HeroVectors.create(g)
        val rng = HeroCore.heroRng(g["seed"].big(), "h1")
        var events = 0
        for (amount in g["amounts"].list().map { it.lng() }) {
            var r = HeroCore.apply(s, GainXP("h1", amount), rng)
            events += r.events.size
            s = r.state
            while (s.hero.offer.isNotEmpty()) {
                r = HeroCore.apply(s, ChooseSkill("h1", (s.hero.level % s.hero.offer.size).toLong()), rng)
                events += r.events.size
                s = r.state
            }
        }
        assertEquals(pinned, HeroCore.stateHash(s))
        assertEquals(49, events)
        assertEquals(12, s.hero.level)
        assertEquals(26499L, s.hero.xp)
        assertEquals(listOf(7, 5, 4, 1), listOf(s.hero.attack, s.hero.defense, s.hero.power, s.hero.knowledge))
        assertEquals(
            listOf("skill.anvil" to 3, "skill.gale" to 3, "skill.brook" to 2, "skill.hollow" to 1, "skill.ember" to 2, "skill.ivy" to 1),
            s.hero.secondary.map { it.skill to it.level },
        )
        assertNotNull(g["secondary_final"])
    }
}
