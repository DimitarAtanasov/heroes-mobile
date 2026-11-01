package h3.sim

import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** Replay file record/verify versus `vectors/replay.json` (docs/specs/conformance-replay.md). */
class ReplayTest {
    private val doc = ReplayVectors.doc
    private val packs = ReplayVectors.packs

    private fun enc(v: Any?): String = Canonical.encode(v).toString(Charsets.US_ASCII)

    private fun commands(c: Map<String, Any?>): List<BattleCommand> = c["commands"].list().map { BattleCodec.parseCommand(it) }

    private fun ascii(s: String) = s.toByteArray(Charsets.US_ASCII)

    private fun errorName(data: ByteArray, p: Datapack = packs): String? =
        try {
            Replay.verify(data, p)
            null
        } catch (e: Replay.ReplayError) {
            e::class.simpleName
        }

    @Test
    fun recordedBytesAreIdenticalToPython() {
        val cases = doc["scenarios"].list().map { it.obj() }
        assertTrue(cases.size >= 10)
        var cmds = 0
        for (c in cases) {
            val name = c["name"] as String
            val list = commands(c)
            cmds += list.size
            val bytes = Replay.record(c["scenario"] as String, list, c["seed"].big(), packs)
            assertContentEquals(ascii(c["replay"] as String), bytes, name)
            // The Long overload gives the same bytes.
            assertContentEquals(bytes, Replay.record(c["scenario"] as String, list, c["seed"].big().toLong(), packs), name)
        }
        assertTrue(cmds >= 150, "commands=$cmds")
    }

    @Test
    fun pythonReplaysVerifyAndLoad() {
        for (c in doc["scenarios"].list().map { it.obj() }) {
            val name = c["name"] as String
            val data = ascii(c["replay"] as String)
            val header = Replay.verify(data, packs)
            assertEquals(enc(c["header"]), enc(header), name)
            assertEquals(enc(c["header"]), enc(Replay.info(data)), name)
            val loaded = Replay.load(data, packs)
            assertEquals(commands(c), loaded.commands, name)
            assertEquals(header["final_hash"], BattleCodec(
                BattlePolicyPack(packs.policy.values, packs.rules.pack.badMoraleNumerators.map { it.toInt() }, packs.rules.pack.moraleDie.toInt()),
            ).stateHash(loaded.finalState), name)
        }
    }

    @Test
    fun goldenFinalHashIsThePinnedOne() {
        val golden = doc["scenarios"].list().map { it.obj() }.first { it["name"] == "golden" }
        val header = Replay.verify(ascii(golden["replay"] as String), packs)
        assertEquals("fbe9015bde1b6e5c165c08fc1604f98ea7c3cdf09cc38528ec2fda496f040e2b", header["final_hash"])
        assertEquals(BigInteger.valueOf(12345), header["seed"])
        assertEquals("golden", header["battle_id"])
    }

    @Test
    fun damagedFilesGiveTheNamedErrors() {
        val cases = doc["replay_errors"].list().map { it.obj() }
        assertTrue(cases.size >= 50, "cases=${cases.size}")
        val seen = HashSet<String>()
        for (c in cases) {
            val name = c["name"] as String
            val data = if (c.containsKey("replay_hex")) ReplayVectors.hexBytes(c["replay_hex"] as String) else ascii(c["replay"] as String)
            assertEquals(c["error"], errorName(data), name)
            seen += c["error"] as String
        }
        assertEquals(
            setOf("Malformed", "Truncated", "Tampered", "UnsupportedVersion", "UnsupportedKind",
                "MismatchedRulesPack", "MismatchedPolicy", "MismatchedCreatures", "Diverged"),
            seen,
        )
    }

    @Test
    fun everyTruncationCutIsTruncated() {
        val t = doc["truncation"].obj()
        val data = ascii(t["replay"] as String)
        assertEquals(t["length"].big().toInt(), data.size)
        assertEquals("tiny", Replay.verify(data, packs)["battle_id"])
        for (cut in 0 until data.size) {
            val e = assertFailsWith<Replay.Truncated>("cut $cut") { Replay.verify(data.copyOf(cut), packs) }
            assertNotNull(e.message)
        }
        // The same holds for the biggest replay of the set (bounded: every 7th cut plus the last ones).
        val big = doc["scenarios"].list().map { ascii(it.obj()["replay"] as String) }.maxByOrNull { it.size }!!
        for (cut in (0 until big.size step 7) + (big.size - 5 until big.size)) {
            assertFailsWith<Replay.Truncated>("big cut $cut") { Replay.verify(big.copyOf(cut), packs) }
        }
    }

    @Test
    fun packMismatchUnderDifferentPacks() {
        val p = ReplayVectors.packTexts
        val rules = p["rules"] as String
        val policy = p["battle_policy"] as String
        val creatures = p["creatures"] as String
        val data = ascii(doc["scenarios"].list().first().obj()["replay"] as String)
        fun swap(s: String, from: String, to: String): String {
            assertTrue(from in s, from)
            return s.replace(from, to)
        }
        val otherRules = ReplayVectors.packsFrom(swap(rules, "\"hate_bonus\": [1, 2]", "\"hate_bonus\": [1, 3]"), policy, creatures)
        val otherPolicy = ReplayVectors.packsFrom(rules, swap(policy, "\"defend_bonus_den\": 5", "\"defend_bonus_den\": 6"), creatures)
        val otherCreatures = ReplayVectors.packsFrom(rules, policy, swap(creatures, "\"hp\": 12", "\"hp\": 13"))
        assertEquals("MismatchedRulesPack", errorName(data, otherRules))
        assertEquals("MismatchedPolicy", errorName(data, otherPolicy))
        assertEquals("MismatchedCreatures", errorName(data, otherCreatures))
        // info needs no matching packs.
        assertEquals("golden", Replay.info(data)["battle_id"])
    }

    @Test
    fun recordRefusesBadInput() {
        val c = doc["scenarios"].list().map { it.obj() }.first { it["name"] == "golden" }
        val scn = c["scenario"] as String
        val cmds = commands(c)
        val seed = BigInteger.valueOf(12345)
        assertFailsWith<Replay.UnsupportedKind> { Replay.record(scn, cmds, seed, packs, kind = "adventure") }
        assertFailsWith<Replay.UnsupportedKind> { Replay.record(scn, cmds, seed, packs, kind = "duel") }
        assertFailsWith<Replay.Malformed> { Replay.record("""{"battle_id":"x"}""", cmds, seed, packs) }
        assertFailsWith<Replay.Malformed> { Replay.record("[1]", cmds, seed, packs) }
        assertFailsWith<Replay.Malformed> { Replay.record("{", cmds, seed, packs) }
        assertFailsWith<Replay.Malformed> { Replay.record(scn.replaceFirst("\"speed\":", "\"speed\":0.5,\"zz\":"), cmds, seed, packs) }
        // An illegal command in the log.
        assertFailsWith<Replay.Diverged> { Replay.record(scn, cmds.take(3) + BattleCommand.Move(99, Pair(0, 0)), seed, packs) }
        // Nothing but Begin is fine and replays.
        val begin = Replay.record(scn, listOf(BattleCommand.Begin), seed, packs)
        assertEquals(BigInteger.ONE, Replay.verify(begin, packs)["command_count"])
        // Key order and whitespace of the input scenario do not change the bytes.
        val spaced = scn.replace(",", ", ").replace(":", ": ")
        assertContentEquals(Replay.record(scn, cmds, seed, packs), Replay.record(spaced, cmds, seed, packs))
    }
}
