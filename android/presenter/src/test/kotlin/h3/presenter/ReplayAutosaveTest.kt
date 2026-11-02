package h3.presenter

import h3.sim.Battle
import h3.sim.BattleAi
import h3.sim.BattleCodec
import h3.sim.BattleCommand
import h3.sim.BattlePolicyPack
import h3.sim.Canonical
import h3.sim.Datapack
import h3.sim.MiniJson
import h3.sim.Replay
import h3.sim.Rules
import h3.sim.Scenario
import h3.sim.big
import h3.sim.list
import h3.sim.loadVector
import h3.sim.obj
import java.io.IOException
import java.math.BigInteger
import java.util.concurrent.Executor
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

/** Autosave and resume through the replay format (docs/specs/replay-autosave.md), on the `replay.json` scenarios. */
class ReplayAutosaveTest {
    private val doc = loadVector("replay.json")
    private val texts = doc["packs"].obj()
    private val rulesText = texts["rules"] as String
    private val policyText = texts["battle_policy"] as String
    private val creaturesText = texts["creatures"] as String
    private val packs = Datapack.load(rulesText, policyText, creaturesText)
    private val codec = BattleCodec(
        BattlePolicyPack(packs.policy.values, packs.rules.pack.badMoraleNumerators.map { it.toInt() }, packs.rules.pack.moraleDie.toInt()),
    )
    private val battle = Battle(Rules(packs.rules.pack), packs.rules.contentHash)
    private val ai = BattleAi(battle, codec)
    private val direct = Executor { it.run() }

    private class Case(val name: String, val scenario: String, val seed: BigInteger, val commands: List<BattleCommand>, val python: ByteArray)

    private val cases = doc["scenarios"].list().map { it.obj() }.map { c ->
        Case(
            c["name"] as String, c["scenario"] as String, c["seed"].big(),
            c["commands"].list().map { BattleCodec.parseCommand(it) }, (c["replay"] as String).toByteArray(Charsets.US_ASCII),
        )
    }

    private class MemSink : ByteSink {
        val writes = ArrayList<ByteArray>()
        override fun write(bytes: ByteArray) { writes += bytes }
    }

    /** One finished or stalled game: the session, what its sink received and the state hash after each command. */
    private class Run(val c: Case, val s: BattleSession, val auto: ReplayAutosave, val sink: MemSink, val hashes: List<String>)

    private fun session(c: Case, humans: Set<Int>, withAi: Boolean, auto: AutosaveSink?, cap: Int = CAP): BattleSession =
        BattleSession(battle, codec, if (withAi) ai else null, Scenario.parse(c.scenario, packs), c.seed, humans, direct, cap, auto)

    private fun play(c: Case, mode: String, sink: ByteSink = MemSink()): Run {
        val auto = ReplayAutosave(c.scenario, c.seed, packs, sink)
        val s = session(c, if (mode == "ai") emptySet() else if (mode == "human") setOf(0) else setOf(0, 1), mode != "script", auto)
        val hashes = arrayListOf(s.latest().stateHash)
        s.addListener { hashes += it.stateHash }
        s.start()
        when (mode) {
            "script" -> for (cmd in c.commands.drop(1)) {
                var r: SubmitResult? = null
                s.submit(s.log().size, cmd) { r = it }
                assertIs<SubmitResult.Accepted>(r, "${c.name} script step")
            }
            "human" -> {
                var guard = 0
                while (!s.isOver() && !s.isStalled() && s.fault() == null && guard++ < 400) {
                    val snap = s.latest()
                    var r: SubmitResult? = null
                    s.submit(snap.seq, ai.choose(snap.state)) { r = it }
                    assertIs<SubmitResult.Accepted>(r, "${c.name} human step ${snap.seq}")
                }
            }
        }
        assertEquals(null, s.fault(), c.name)
        return Run(c, s, auto, sink as? MemSink ?: MemSink(), hashes)
    }

    private fun rec(c: Case, cmds: List<BattleCommand>) = Replay.record(c.scenario, cmds, c.seed, packs)
    private fun cmds(es: List<LogEntry>) = es.map { it.command }
    private val modes = listOf("script", "ai", "human")

    @Test
    fun autosaveBytesEqualRecordOfTheFinalLogAfterEveryCommand() {
        var finished = 0
        var total = 0
        for (c in cases) for (m in modes) {
            val r = play(c, m)
            val log = r.s.log()
            assertEquals(log.size, r.sink.writes.size, "${c.name}/$m writes")
            assertEquals(0, r.auto.failures, "${c.name}/$m")
            assertEquals(0, r.s.autosaveFailures)
            for (i in log.indices) assertContentEquals(rec(c, cmds(log.take(i + 1))), r.sink.writes[i], "${c.name}/$m write $i")
            assertContentEquals(rec(c, cmds(log)), r.sink.writes.last(), "${c.name}/$m final")
            total += log.size
            if (r.s.isOver()) finished++
        }
        assertTrue(finished >= 12, "finished=$finished")
        assertTrue(total >= 500, "commands=$total")
    }

    @Test
    fun scriptedGamesWriteExactlyThePythonBytes() {
        assertTrue(cases.size >= 10)
        for (c in cases) {
            val r = play(c, "script")
            assertEquals(c.commands, cmds(r.s.log()), c.name)
            assertContentEquals(c.python, r.sink.writes.last(), c.name)
            assertEquals(c.commands.size, r.sink.writes.size, c.name)
        }
    }

    @Test
    fun resumeInAFreshSessionGivesTheSameStateHashAndLog() {
        for (c in cases) for (m in modes) {
            val r = play(c, m)
            val ok = ReplayResume.load(r.sink.writes.last(), packs)
            assertIs<ResumeResult.Ok>(ok, "${c.name}/$m")
            assertEquals(r.hashes.last(), ok.resumed.finalHash, "${c.name}/$m")
            val fresh = session(c, setOf(0, 1), false, null)
            var reply: SubmitResult? = null
            ReplayResume.into(fresh, ok.resumed) { reply = it }
            assertIs<SubmitResult.Accepted>(reply, "${c.name}/$m")
            assertEquals(r.s.finalHash(), fresh.finalHash(), "${c.name}/$m hash")
            assertEquals(r.s.log().map { it.seq to it.command }, fresh.log().map { it.seq to it.command }, "${c.name}/$m log")
            assertEquals(r.s.isOver(), fresh.isOver())
        }
    }

    /** Replays the original log's remaining commands into [s] (the AI session plays its own). */
    private fun continueFrom(s: BattleSession, orig: List<LogEntry>, label: String) {
        var guard = 0
        while (s.log().size < orig.size && guard++ < 1000) {
            val e = orig[s.log().size]
            assertTrue(e.origin != Origin.Ai, "$label: the AI should have played step ${e.seq}")
            var r: SubmitResult? = null
            s.submit(e.seq, e.command, Origin.Human) { r = it }
            assertIs<SubmitResult.Accepted>(r, "$label step ${e.seq}")
        }
    }

    @Test
    fun crashAfterCommandKResumesToStateKAndTheGameContinuesToTheSameFinalHash() {
        var continued = 0
        for (c in cases) for (m in modes) {
            val r = play(c, m)
            val n = r.s.log().size
            val ks = (1..n).filter { it == n || it <= 3 || it % maxOf(1, n / 20) == 0 }
            for (k in ks) {
                val label = "${c.name}/$m k=$k"
                val ok = ReplayResume.load(r.sink.writes[k - 1], packs)
                assertIs<ResumeResult.Ok>(ok, label)
                // The state after k: no AI, so nothing moves after the load.
                val still = session(c, setOf(0, 1), false, null)
                ReplayResume.into(still, ok.resumed)
                assertEquals(k, still.log().size, label)
                assertEquals(r.hashes[k], still.finalHash(), label)
                assertEquals(cmds(r.s.log().take(k)), cmds(still.log()), label)
                if (!r.s.isOver()) continue
                // The same configuration as the original, resumed with its own autosave.
                val sink2 = MemSink()
                val auto2 = ReplayAutosave.resuming(ok.resumed, c.seed, packs, sink2)
                val humans = if (m == "script") setOf(0, 1) else if (m == "ai") emptySet() else setOf(0)
                val s2 = session(c, humans, m != "script", auto2)
                ReplayResume.into(s2, ok.resumed)
                continueFrom(s2, r.s.log(), label)
                assertEquals(r.s.finalHash(), s2.finalHash(), label)
                assertEquals(cmds(r.s.log()), cmds(s2.log()), label)
                assertEquals(0, auto2.failures, label)
                assertEquals(n - k, sink2.writes.size, "$label new writes")
                if (k < n) assertContentEquals(r.sink.writes.last(), sink2.writes.last(), "$label bytes")
                continued++
            }
        }
        assertTrue(continued >= 100, "continued=$continued")
    }

    @Test
    fun truncatedFilesAtEveryCutPointAreTruncated() {
        for (c in cases.filter { it.name in setOf("golden", "soak-default-2", "explicit-pos", "soak-mix-fifo-0") }) {
            val full = play(c, "script").sink.writes.last()
            for (cut in 0 until full.size) {
                val res = ReplayResume.load(full.copyOf(cut), packs)
                assertIs<ResumeResult.Failed>(res, "${c.name} cut $cut")
                assertEquals(ResumeError.Truncated, res.error, "${c.name} cut $cut")
            }
            assertIs<ResumeResult.Ok>(ReplayResume.load(full, packs))
            // Trailing garbage is not a truncation.
            assertEquals(ResumeError.Malformed, (ReplayResume.load(full + "x".toByteArray(), packs) as ResumeResult.Failed).error)
        }
    }

    @Test
    fun tamperedFilesAreNamedFailuresNeverExceptions() {
        val named = ResumeError.entries.toSet() - ResumeError.Unreadable
        var tampered = 0
        for (c in cases.filter { it.name in setOf("golden", "soak-default-1", "explicit-pos") }) {
            val full = play(c, "script").sink.writes.last()
            for (pos in full.indices step 3) for (x in intArrayOf(0x01, 0x20)) {
                val bad = full.copyOf()
                bad[pos] = (bad[pos].toInt() xor x).toByte()
                val res = ReplayResume.load(bad, packs)
                assertIs<ResumeResult.Failed>(res, "${c.name} pos $pos")
                assertTrue(res.error in named, "${c.name} pos $pos: ${res.error} ${res.message}")
                if (res.error == ResumeError.Tampered) tampered++
            }
        }
        assertTrue(tampered > 100, "tampered=$tampered")
    }

    @Suppress("UNCHECKED_CAST")
    private fun reseal(bytes: ByteArray, edit: (header: MutableMap<String, Any?>, body: MutableMap<String, Any?>) -> Unit): ByteArray {
        val d = MiniJson.parse(bytes.toString(Charsets.US_ASCII)) as Map<String, Any?>
        val header = (d["header"] as Map<String, Any?>).toMutableMap()
        val body = (d["body"] as Map<String, Any?>).toMutableMap()
        edit(header, body)
        val sum = Canonical.hash(mapOf("header" to header, "body" to body))
        return Canonical.encode(mapOf("header" to header, "body" to body, "checksum" to sum))
    }

    @Test
    fun sealedButWrongFilesAreDivergedVersionOrKindFailures() {
        val c = cases.first { it.name == "golden" }
        val full = play(c, "script").sink.writes.last()
        assertIs<ResumeResult.Ok>(ReplayResume.load(reseal(full) { _, _ -> }, packs), "reseal is the identity")
        val wrongHash = ReplayResume.load(reseal(full) { h, _ -> h["final_hash"] = "0".repeat(64) }, packs)
        assertEquals(ResumeError.Diverged, (wrongHash as ResumeResult.Failed).error)
        val dropped = ReplayResume.load(reseal(full) { h, b ->
            b["commands"] = (b["commands"] as List<*>).dropLast(1); h["command_count"] = BigInteger.valueOf(14)
        }, packs)
        assertEquals(ResumeError.Diverged, (dropped as ResumeResult.Failed).error) // final hash no longer matches
        val v2 = ReplayResume.load(reseal(full) { h, _ -> h["format_version"] = BigInteger.TWO }, packs)
        assertEquals(ResumeError.UnsupportedVersion, (v2 as ResumeResult.Failed).error)
        val kind = ReplayResume.load(reseal(full) { h, _ -> h["kind"] = "adventure" }, packs)
        assertEquals(ResumeError.UnsupportedKind, (kind as ResumeResult.Failed).error)
        val illegal = ReplayResume.load(reseal(full) { _, b ->
            val cs = (b["commands"] as List<*>).toMutableList()
            cs[1] = mapOf("type" to "Move", "stack" to BigInteger.valueOf(99), "dest" to listOf(BigInteger.ONE, BigInteger.ONE))
            b["commands"] = cs
        }, packs)
        assertIs<ResumeResult.Failed>(illegal)
        assertTrue(illegal.error == ResumeError.Diverged || illegal.error == ResumeError.Malformed, "${illegal.error} ${illegal.message}")
        assertEquals(ResumeError.Truncated, (ReplayResume.load(ByteArray(0), packs) as ResumeResult.Failed).error)
        assertEquals(ResumeError.Malformed, (ReplayResume.load("hello".toByteArray(), packs) as ResumeResult.Failed).error)
    }

    @Test
    fun aPackMismatchIsReportedAsSuch() {
        val c = cases.first { it.name == "golden" }
        val full = play(c, "script").sink.writes.last()
        fun other(r: String = rulesText, p: String = policyText, cr: String = creaturesText) = Datapack.load(r, p, cr)
        val rules = other(r = rulesText.replace("\"morale_die\": 24", "\"morale_die\": 20"))
        val policy = other(p = policyText.replace("\"bad_luck\": false", "\"bad_luck\": true"))
        val creatures = other(cr = creaturesText.replace("\"attack\": 6", "\"attack\": 7"))
        assertEquals(ResumeError.MismatchedRulesPack, (ReplayResume.load(full, rules) as ResumeResult.Failed).error)
        assertEquals(ResumeError.MismatchedPolicy, (ReplayResume.load(full, policy) as ResumeResult.Failed).error)
        assertEquals(ResumeError.MismatchedCreatures, (ReplayResume.load(full, creatures) as ResumeResult.Failed).error)
        assertIs<ResumeResult.Ok>(ReplayResume.load(full, packs))
    }

    @Test
    fun aSinkThatThrowsNeverStopsTheGame() {
        for (c in cases) for (m in modes) {
            val clean = play(c, m)
            for (kind in 0..2) {
                var calls = 0
                val sink = ByteSink {
                    calls++
                    when (kind) {
                        0 -> throw IOException("disk full")
                        1 -> throw IllegalStateException("boom")
                        else -> if (calls % 3 != 0) throw IOException("flaky")
                    }
                }
                val r = play(c, m, sink)
                assertEquals(clean.s.finalHash(), r.s.finalHash(), "${c.name}/$m/$kind")
                assertEquals(cmds(clean.s.log()), cmds(r.s.log()), "${c.name}/$m/$kind")
                assertEquals(calls, r.s.log().size, "every command still reached the sink")
                assertEquals(if (kind == 2) calls - calls / 3 else calls, r.auto.failures, "${c.name}/$m/$kind")
                assertEquals(0, r.s.autosaveFailures)
                if (kind == 0) assertEquals("java.io.IOException: disk full", r.auto.lastError)
            }
        }
    }

    @Test
    fun aFlakySinkLeavesTheNextSuccessfulWriteHoldingTheWholeLog() {
        val c = cases.first { it.name == "soak-default-1" }
        val got = ArrayList<ByteArray>()
        var calls = 0
        val r = play(c, "script", ByteSink { if (++calls <= 5) throw IOException("x") else got += it })
        assertContentEquals(rec(c, cmds(r.s.log())), got.last())
        assertEquals(5, r.auto.failures)
        assertEquals(r.s.log().size - 5, r.auto.writes)
        assertIs<ResumeResult.Ok>(ReplayResume.load(got.first(), packs)) // the first success already holds commands 0..5
        assertEquals(6, (ReplayResume.load(got.first(), packs) as ResumeResult.Ok).resumed.commands.size)
    }

    @Test
    fun anUnrecordableScenarioCountsFailuresAndTheGameGoesOn() {
        val c = cases.first { it.name == "golden" }
        val sink = MemSink()
        val auto = ReplayAutosave("{not json", c.seed, packs, sink)
        val s = session(c, setOf(0, 1), false, auto)
        s.start()
        for (cmd in c.commands.drop(1)) s.submit(s.log().size, cmd)
        assertEquals(c.commands.size, s.log().size)
        assertEquals(c.commands.size, auto.failures)
        assertTrue(sink.writes.isEmpty())
        assertEquals(0, s.autosaveFailures)
    }

    @Test
    fun aGapInTheEntriesIsAFailureNotAFile() {
        val c = cases.first { it.name == "golden" }
        val sink = MemSink()
        val auto = ReplayAutosave(c.scenario, c.seed, packs, sink)
        val s = session(c, emptySet(), false, null)
        auto.onCommand(LogEntry(3, BattleCommand.Begin, Origin.Session), s.latest())
        assertEquals(1, auto.failures)
        assertTrue(sink.writes.isEmpty())
        auto.onCommand(LogEntry(0, BattleCommand.Begin, Origin.Session), s.latest())
        assertEquals(1, sink.writes.size)
    }

    @Test
    fun anIllegalResumeLeavesTheSessionUntouched() {
        val c = cases.first { it.name == "golden" }
        val s = session(c, setOf(0, 1), false, null)
        var reply: SubmitResult? = null
        ReplayResume.into(s, Resumed(c.scenario, c.seed, listOf(BattleCommand.Begin, BattleCommand.Begin), "x")) { reply = it }
        assertIs<SubmitResult.Illegal>(reply)
        assertEquals(0, s.log().size)
        assertFalse(s.isOver())
    }

    private companion object { const val CAP = 400 }
}
