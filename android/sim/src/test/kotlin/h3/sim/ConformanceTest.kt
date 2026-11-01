package h3.sim

import h3.sim.Canonical.toHex
import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ConformanceTest {
    private fun runOps(g: Pcg32, ops: List<Any?>): List<Any> = ops.map { o ->
        val op = o.list()
        when (op[0] as String) {
            "u32" -> g.nextU32()
            "range" -> g.range(op[1].big().toLong(), op[2].big().toLong())
            "randint" -> g.randint(op[1].big().toLong(), op[2].big().toLong())
            "chance" -> g.chance(op[1].big().toLong(), op[2].big().toLong())
            else -> error("op $op")
        }
    }

    private fun expected(out: List<Any?>): List<Any> = out.map { if (it is BigInteger) it.toLong() else it!! }

    @Test
    fun publishedVector() {
        val p = loadVector("rng.json")["published"].obj()
        val g = Pcg32(p["seed"].u64(), p["seq"].u64())
        assertEquals(p["u32"].list().map { it.big().toLong() }, List(6) { g.nextU32() })
    }

    @Test
    fun pcgRawDraws() {
        val cases = loadVector("rng.json")["pcg32_u32"].list()
        assertTrue(cases.size >= 8)
        for (c in cases) {
            val o = c.obj()
            val g = Pcg32(o["seed"].u64(), o["seq"].u64())
            assertEquals(o["state"].u64(), g.state)
            assertEquals(o["inc"].u64(), g.inc)
            assertEquals(o["u32"].list().map { it.big().toLong() }, List(1000) { g.nextU32() }, "seed ${o["seed"]}")
        }
    }

    @Test
    fun pcgMixedOps() {
        for (c in loadVector("rng.json")["pcg32_ops"].list()) {
            val o = c.obj()
            val g = Pcg32(o["seed"].u64(), o["seq"].u64())
            assertEquals(expected(o["out"].list()), runOps(g, o["ops"].list()), "seed ${o["seed"]}")
        }
    }

    @Test
    fun derivedStreams() {
        val cases = loadVector("rng.json")["derived"].list()
        assertTrue(cases.size >= 20)
        for (c in cases) {
            val o = c.obj()
            val g = RngStreams.derive(o["master"].big(), o["domain"] as String, o["id"] as String)
            val label = "${o["master"]} ${o["domain"]} ${o["id"]}"
            assertEquals(o["state"].u64(), g.state, label)
            assertEquals(o["inc"].u64(), g.inc, label)
            assertEquals(expected(o["out"].list()), runOps(g, o["ops"].list()), label)
        }
    }

    @Test
    fun canonicalJsonCorpus() {
        val cases = loadVector("canonical_json.json")["cases"].list()
        assertTrue(cases.size >= 30)
        for (c in cases) {
            val o = c.obj()
            val bytes = Canonical.encode(o["value"])
            assertEquals(o["hex"] as String, bytes.toHex(), o["name"] as String)
            assertEquals(o["sha256"] as String, Canonical.sha256Hex(bytes), o["name"] as String)
        }
    }

    @Test
    fun stateHashVectors() {
        val cases = loadVector("state_hash.json")["cases"].list()
        assertTrue(cases.isNotEmpty())
        for (c in cases) {
            val o = c.obj()
            val text = o["canonical"] as String
            // Parse the canonical state and re-encode: must be byte-identical.
            val bytes = Canonical.encode(MiniJson.parse(text))
            assertEquals(text, bytes.toString(Charsets.US_ASCII), o["name"] as String)
            assertEquals(o["sha256"] as String, Canonical.sha256Hex(bytes), o["name"] as String)
        }
    }

    @Test
    fun rejectsFloatsAndNonStringKeys() {
        kotlin.test.assertFailsWith<IllegalArgumentException> { Canonical.encode(1.5) }
        kotlin.test.assertFailsWith<IllegalArgumentException> { Canonical.encode(mapOf(1 to 2)) }
    }
}
