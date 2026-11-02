package h3.presenter.ui

import h3.presenter.BattleSession
import h3.presenter.ByteSink
import h3.presenter.ReplayAutosave
import h3.presenter.ReplayResume
import h3.presenter.Resumed
import h3.presenter.ResumeError
import h3.presenter.ResumeResult
import h3.sim.Battle
import h3.sim.BattleAi
import h3.sim.BattleCodec
import h3.sim.BattlePolicyPack
import h3.sim.Datapack
import h3.sim.Replay
import h3.sim.Rules
import h3.sim.Scenario
import h3.sim.big
import h3.sim.list
import h3.sim.loadVector
import h3.sim.obj
import java.math.BigInteger
import java.util.concurrent.Executor
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Save slot naming, the `.bak` rule, resume choice and messages (android-app.md 7.2, replay-autosave.md). */
class SaveSlotsTest {
    // ---- pure decisions ----

    @Test
    fun theSlotIsNamedAfterTheBattleId() {
        val s = assertNotNull(SaveSlots.slot("skirmish-easy"))
        assertEquals("skirmish-easy", s.battleId)
        assertEquals("skirmish-easy.h3r", s.fileName)
        assertEquals("skirmish-easy.h3r.bak", s.backupName)
        assertEquals("skirmish-easy.h3r.tmp", s.tempName)
        assertEquals(".h3r", SaveSlots.EXTENSION)
        for (ok in listOf("golden", "pos-demo", "soak_b3", "A1", "a-b", "x".repeat(SaveSlots.MAX_ID_LENGTH))) {
            assertEquals("$ok.h3r", SaveSlots.slot(ok)?.fileName, ok)
        }
    }

    @Test
    fun idsThatCouldEscapeTheSavesFolderOrBreakAFileNameHaveNoSlot() {
        val bad = listOf(
            "", ".", "..", "../x", "a/b", "a\\b", "/abs", ".hidden", "a..b", "a.b", "a.m1", "a b", "a:b", "a\u0000b", "a\nb",
            "café", "x".repeat(SaveSlots.MAX_ID_LENGTH + 1), "a*b", "a?b", "a\"b",
        )
        for (id in bad) assertNull(SaveSlots.slot(id), "id " + id.replace("\u0000", "<NUL>").replace("\n", "<LF>"))
    }

    @Test
    fun theWritePlanRotatesTheBackupOnlyWhenItIsSafeToDoSo() {
        val tmp = listOf(SaveSlots.WriteStep.WriteTemp, SaveSlots.WriteStep.SyncTemp)
        val rename = SaveSlots.WriteStep.RenameTempToMain
        val copy = SaveSlots.WriteStep.CopyMainToBackup
        val missing = SaveSlots.FileState.Missing
        val valid = SaveSlots.FileState.Valid
        val invalid = SaveSlots.FileState.Invalid
        // No main file yet: nothing to keep.
        for (b in SaveSlots.FileState.entries) assertEquals(tmp + rename, SaveSlots.writePlan(missing, b), "missing/$b")
        // A good main file becomes the backup, whatever the backup was.
        for (b in SaveSlots.FileState.entries) assertEquals(tmp + copy + rename, SaveSlots.writePlan(valid, b), "valid/$b")
        // An unreadable main file is kept as the backup unless that would replace a good backup.
        assertEquals(tmp + copy + rename, SaveSlots.writePlan(invalid, missing))
        assertEquals(tmp + copy + rename, SaveSlots.writePlan(invalid, invalid))
        assertEquals(tmp + rename, SaveSlots.writePlan(invalid, valid))
    }

    @Test
    fun everyResumeErrorHasItsOwnMessageThatSaysTheFileIsKept() {
        val all = ResumeError.entries.map { SaveSlots.message(it) }
        assertEquals(10, all.size)
        assertEquals(all.size, all.distinct().size, "messages must differ: $all")
        for ((e, m) in ResumeError.entries.zip(all)) {
            assertTrue(m.isNotBlank() && m.length <= 200, "$e: $m")
            assertTrue("kept" in m, "$e: $m")
            assertTrue(m.first().isUpperCase() && m.last() == '.', "$e: $m")
            assertTrue(e.name !in m && "Exception" !in m, "$e: $m") // no developer vocabulary
        }
    }

    private fun resumed(tag: String) = Resumed("{}", BigInteger.ONE, emptyList(), tag.repeat(8))

    private fun failed(e: ResumeError) = ResumeResult.Failed(e, "technical detail that must not be shown")

    @Test
    fun resumeUsesTheMainFileThenTheBackupThenGivesUp() {
        val m = resumed("a")
        val b = resumed("b")
        // Good main wins, even when the backup is also good or broken.
        assertEquals(SaveSlots.ResumeChoice.FromMain(m), SaveSlots.chooseResume(ResumeResult.Ok(m), ResumeResult.Ok(b)))
        assertEquals(SaveSlots.ResumeChoice.FromMain(m), SaveSlots.chooseResume(ResumeResult.Ok(m), failed(ResumeError.Tampered)))
        assertEquals(SaveSlots.ResumeChoice.FromMain(m), SaveSlots.chooseResume(ResumeResult.Ok(m), null))
        // A broken or missing main falls back to a good backup and remembers why.
        assertEquals(
            SaveSlots.ResumeChoice.FromBackup(b, ResumeError.Truncated),
            SaveSlots.chooseResume(failed(ResumeError.Truncated), ResumeResult.Ok(b)),
        )
        assertEquals(SaveSlots.ResumeChoice.FromBackup(b, null), SaveSlots.chooseResume(null, ResumeResult.Ok(b)))
        // Nothing usable.
        assertEquals(SaveSlots.ResumeChoice.NothingToResume, SaveSlots.chooseResume(null, null))
        assertEquals(
            SaveSlots.ResumeChoice.Unresumable(ResumeError.Diverged, ResumeError.Malformed),
            SaveSlots.chooseResume(failed(ResumeError.Diverged), failed(ResumeError.Malformed)),
        )
        assertEquals(
            SaveSlots.ResumeChoice.Unresumable(ResumeError.Diverged, null),
            SaveSlots.chooseResume(failed(ResumeError.Diverged), null),
        )
        assertEquals(
            SaveSlots.ResumeChoice.Unresumable(null, ResumeError.Unreadable),
            SaveSlots.chooseResume(null, failed(ResumeError.Unreadable)),
        )
    }

    @Test
    fun noticesNameTheMainFilesProblemAndNeverShowTechnicalText() {
        val m = resumed("a")
        assertNull(SaveSlots.notice(SaveSlots.ResumeChoice.FromMain(m)))
        assertNull(SaveSlots.notice(SaveSlots.ResumeChoice.NothingToResume))
        val fromBak = assertNotNull(SaveSlots.notice(SaveSlots.ResumeChoice.FromBackup(m, ResumeError.Tampered)))
        assertTrue(SaveSlots.message(ResumeError.Tampered) in fromBak && "previous" in fromBak, fromBak)
        val fromBakMissing = assertNotNull(SaveSlots.notice(SaveSlots.ResumeChoice.FromBackup(m, null)))
        assertTrue("previous" in fromBakMissing, fromBakMissing)
        val both = assertNotNull(SaveSlots.notice(SaveSlots.ResumeChoice.Unresumable(ResumeError.Diverged, ResumeError.Malformed)))
        assertEquals(SaveSlots.message(ResumeError.Diverged), both)
        // Only the backup exists and is broken: say that one's problem.
        assertEquals(SaveSlots.message(ResumeError.Malformed), SaveSlots.notice(SaveSlots.ResumeChoice.Unresumable(null, ResumeError.Malformed)))
        assertNotEquals(SaveSlots.notice(SaveSlots.ResumeChoice.FromBackup(m, ResumeError.Truncated)), fromBak)
    }

    // ---- manual saves: naming ----

    @Test
    fun manualSavesGetUniqueDeterministicNamesFromACounter() {
        val m = assertNotNull(SaveSlots.manualSlot("skirmish-easy", 3))
        assertEquals("skirmish-easy", m.battleId)
        assertEquals("skirmish-easy.m3.h3r", m.fileName)
        assertEquals("skirmish-easy.m3.h3r.bak", m.backupName)
        assertEquals("skirmish-easy.m3.h3r.tmp", m.tempName)
        assertEquals(m, SaveSlots.manualSlot("skirmish-easy", 3))
        assertNull(SaveSlots.manualSlot("skirmish-easy", 0))
        assertNull(SaveSlots.manualSlot("skirmish-easy", -1))
        assertNull(SaveSlots.manualSlot("skirmish-easy", SaveSlots.MAX_MANUAL_NUMBER + 1))
        assertNotNull(SaveSlots.manualSlot("skirmish-easy", SaveSlots.MAX_MANUAL_NUMBER))
        assertNull(SaveSlots.manualSlot("../x", 1))
        // No two (battle, kind, number) share a file name, and each name reads back as what made it.
        val ids = listOf("a", "a-m1", "a_m1", "m1", "skirmish-even", "A")
        val names = ArrayList<String>()
        val parsed = ArrayList<SaveSlots.ParsedName>()
        for (id in ids) {
            names += SaveSlots.slot(id)!!.fileName
            parsed += SaveSlots.ParsedName(id, null)
            for (n in listOf(1, 2, 10, 11, 100, SaveSlots.MAX_MANUAL_NUMBER)) {
                names += SaveSlots.manualSlot(id, n)!!.fileName
                parsed += SaveSlots.ParsedName(id, n)
            }
        }
        assertEquals(names.size, names.toSet().size)
        assertEquals(parsed, names.map { SaveSlots.parseFileName(it) })
    }

    @Test
    fun onlyMainSaveFilesParseAndOnlyInTheCanonicalForm() {
        assertEquals(SaveSlots.ParsedName("golden", null), SaveSlots.parseFileName("golden.h3r"))
        assertEquals(SaveSlots.ParsedName("golden", 12), SaveSlots.parseFileName("golden.m12.h3r"))
        for (n in listOf(
            "", "golden", ".h3r", "golden.h3r.bak", "golden.h3r.tmp", "golden.m1.h3r.bak", "golden.m1.h3r.tmp", "readme.txt",
            "golden.m0.h3r", "golden.m01.h3r", "golden.m1000.h3r", "golden.mx.h3r", "golden.m.h3r", "golden.m+1.h3r", "golden.m-1.h3r",
            "golden.m1.m2.h3r", "a.b.h3r", "../golden.h3r", "gold en.h3r", "golden.H3R",
        )) assertNull(SaveSlots.parseFileName(n), n)
    }

    @Test
    fun theNextManualNumberIsOnePastTheHighestOfThatBattleWhateverTheOrder() {
        val files = listOf(
            "x.h3r", "x.m1.h3r", "x.m5.h3r", "y.m9.h3r", "x.m5.h3r.bak", "x.m7.h3r.tmp", "x.m3.h3r", "notes.txt", "x.m2x.h3r",
        )
        assertEquals(6, SaveSlots.nextManualNumber("x", files))
        assertEquals(6, SaveSlots.nextManualNumber("x", files.reversed()))
        assertEquals(10, SaveSlots.nextManualNumber("y", files))
        assertEquals(1, SaveSlots.nextManualNumber("z", files))
        assertEquals(1, SaveSlots.nextManualNumber("x", emptyList()))
        assertEquals(1, SaveSlots.nextManualNumber("x", listOf("x.h3r")))
        assertNull(SaveSlots.nextManualNumber("x", listOf("x.m${SaveSlots.MAX_MANUAL_NUMBER}.h3r")))
        assertNull(SaveSlots.nextManualNumber("../x", emptyList()))
    }

    // ---- round trip through the real session, autosave and loader ----

    private val doc = loadVector("replay.json")
    private val texts = doc["packs"].obj()
    private val packs = Datapack.load(texts["rules"] as String, texts["battle_policy"] as String, texts["creatures"] as String)
    private val codec = BattleCodec(
        BattlePolicyPack(packs.policy.values, packs.rules.pack.badMoraleNumerators.map { it.toInt() }, packs.rules.pack.moraleDie.toInt()),
    )
    private val battle = Battle(Rules(packs.rules.pack), packs.rules.contentHash)
    private val ai = BattleAi(battle, codec)
    private val direct = Executor { it.run() }

    private class Scn(val name: String, val json: String, val seed: BigInteger)

    private val scenarios = doc["scenarios"].list().map { it.obj() }.map { Scn(it["name"] as String, it["scenario"] as String, it["seed"].big()) }

    /**
     * A folder in memory and an app-side writer that carries out [SaveSlots.writePlan]. When [killWrite] (1-based)
     * is set, the process "dies" in that write after [killStep] steps: nothing more is written.
     */
    private class MemFolder(
        private val slot: SaveSlots.Slot, private val packs: Datapack, private val killWrite: Int = 0, private val killStep: Int = 0,
    ) : ByteSink {
        val files = LinkedHashMap<String, ByteArray>()
        var writes = 0
        private var dead = false

        private fun state(name: String): SaveSlots.FileState {
            val b = files[name] ?: return SaveSlots.FileState.Missing
            return if (ReplayResume.load(b, packs) is ResumeResult.Ok) SaveSlots.FileState.Valid else SaveSlots.FileState.Invalid
        }

        override fun write(bytes: ByteArray) {
            if (dead) return
            writes++
            val plan = SaveSlots.writePlan(state(slot.fileName), state(slot.backupName))
            for ((i, step) in plan.withIndex()) {
                if (writes == killWrite && i >= killStep) {
                    dead = true
                    return
                }
                when (step) {
                    SaveSlots.WriteStep.WriteTemp -> files[slot.tempName] = bytes
                    SaveSlots.WriteStep.SyncTemp -> {}
                    SaveSlots.WriteStep.CopyMainToBackup -> files[slot.backupName] = files.getValue(slot.fileName)
                    SaveSlots.WriteStep.RenameTempToMain -> files[slot.fileName] = files.remove(slot.tempName)!!
                }
            }
        }
    }

    private class Played(val s: BattleSession, val folder: MemFolder, val hashes: List<String>, val slot: SaveSlots.Slot)

    /** AI against AI in a real session whose autosave writes into a [MemFolder]. */
    private fun play(c: Scn, killWrite: Int = 0, killStep: Int = 0): Played {
        val slot = assertNotNull(SaveSlots.slot(Scenario.parse(c.json, packs).battleId), c.name)
        val folder = MemFolder(slot, packs, killWrite, killStep)
        val auto = ReplayAutosave(c.json, c.seed, packs, folder)
        val s = BattleSession(battle, codec, ai, Scenario.parse(c.json, packs), c.seed, emptySet(), direct, 5000, auto)
        val hashes = arrayListOf(s.latest().stateHash)
        s.addListener { hashes += it.stateHash }
        s.start()
        assertEquals(null, s.fault(), c.name)
        assertEquals(0, auto.failures, c.name)
        return Played(s, folder, hashes, slot)
    }

    private fun load(bytes: ByteArray?): ResumeResult? = bytes?.let { ReplayResume.load(it, packs) }

    @Test
    fun aFinishedGameSavedThroughTheSlotLoadsBackToTheSameFinalHash() {
        var games = 0
        for (c in scenarios) {
            val p = play(c)
            assertTrue(p.s.isOver(), c.name)
            val n = p.s.log().size
            assertEquals(n, p.folder.writes, c.name)
            assertEquals(setOf(p.slot.fileName, p.slot.backupName), p.folder.files.keys.toSet(), "${c.name}: no temp file is left")
            val main = assertIs<ResumeResult.Ok>(load(p.folder.files[p.slot.fileName]), c.name)
            assertEquals(p.s.finalHash(), main.resumed.finalHash, c.name)
            assertEquals(p.hashes.last(), main.resumed.finalHash, c.name)
            assertEquals(n, main.resumed.commands.size, c.name)
            // The backup is the previous generation: the game one command earlier.
            val bak = assertIs<ResumeResult.Ok>(load(p.folder.files[p.slot.backupName]), c.name)
            assertEquals(p.hashes[n - 1], bak.resumed.finalHash, c.name)
            assertEquals(n - 1, bak.resumed.commands.size, c.name)
            assertEquals(SaveSlots.ResumeChoice.FromMain(main.resumed), SaveSlots.chooseResume(main, bak))
            games++
        }
        assertTrue(games >= 10, "games=$games")
    }

    @Test
    fun aDamagedMainFileFallsBackToTheBackupAndTheGameResumesFromIt() {
        val c = scenarios.first { it.name == "golden" }
        val p = play(c)
        val n = p.s.log().size
        val damaged = p.folder.files.getValue(p.slot.fileName).copyOf().also { it[it.size / 2] = (it[it.size / 2].toInt() xor 1).toByte() }
        val choice = SaveSlots.chooseResume(load(damaged), load(p.folder.files[p.slot.backupName]))
        val fb = assertIs<SaveSlots.ResumeChoice.FromBackup>(choice)
        assertNotNull(fb.mainError)
        assertEquals(p.hashes[n - 1], fb.resumed.finalHash)
        assertNotNull(SaveSlots.notice(choice))
        // Resume into a fresh session: the state is the one before the last command.
        val fresh = BattleSession(battle, codec, null, Scenario.parse(fb.resumed.scenarioJson, packs), fb.resumed.seed, setOf(0, 1), direct, 5000)
        ReplayResume.into(fresh, fb.resumed)
        assertEquals(p.hashes[n - 1], fresh.finalHash())
        assertEquals(n - 1, fresh.log().size)
    }

    @Test
    fun aCrashAtAnyStepOfAnyWriteLeavesTheOldOrTheNewGenerationAndNeverNothing() {
        val c = scenarios.first { it.name == "golden" }
        val n = play(c).s.log().size
        var kills = 0
        for (k in 1..n) for (j in 0 until (if (k == 1) 3 else 4)) { // the first write has no main to back up
            val p = play(c, k, j)
            val label = "k=$k j=$j"
            val main = load(p.folder.files[p.slot.fileName])
            // Steps 0 until j ran in write k; the rename is the last step, so the process died before it.
            val expectedCommands = k - 1
            if (expectedCommands == 0) {
                assertNull(main, label) // died before the very first rename: no main file, only a temp file at most
            } else {
                val ok = assertIs<ResumeResult.Ok>(main, label)
                assertEquals(p.hashes[expectedCommands], ok.resumed.finalHash, label)
            }
            val bak = load(p.folder.files[p.slot.backupName])
            if (bak != null) assertIs<ResumeResult.Ok>(bak, "backup $label")
            kills++
        }
        assertEquals(3 + (n - 1) * 4, kills)
    }

    // ---- the slot list and choosing one ----

    /** Rows as comparable text ([Resumed] has no equality). */
    private fun shape(rows: List<SaveSlots.SlotRow>): List<String> = rows.map { r ->
        val st = r.status
        val tail = when (st) {
            is SaveSlots.SlotStatus.Ready -> "ready ${st.commands} ${st.rounds} ${st.fullHash} ${st.resumed.commands.size}"
            is SaveSlots.SlotStatus.Unusable -> "unusable ${st.error} ${st.message}"
        }
        "${r.fileName} ${r.kind} ${r.number} ${r.battleId} ${r.title} $tail"
    }

    private fun recordPrefix(p: Played, c: Scn, k: Int): ByteArray =
        Replay.record(c.json, p.s.log().take(k).map { it.command }, c.seed, packs)

    private fun stateAfter(c: Scn, bytes: ByteArray): Pair<String, Int> {
        val ok = ReplayResume.load(bytes, packs) as ResumeResult.Ok
        val fresh = BattleSession(battle, codec, null, Scenario.parse(ok.resumed.scenarioJson, packs), ok.resumed.seed, setOf(0, 1), direct, 5000)
        ReplayResume.into(fresh, ok.resumed)
        return fresh.finalHash() to fresh.latest().state.round
    }

    private class Listing(val files: List<SaveSlots.SlotFile>, val goldenFull: ByteArray, val golden5: ByteArray, val golden3: ByteArray, val other: ByteArray)

    private fun listing(): Listing {
        val g = scenarios.first { it.name == "golden" }
        val o = scenarios.first { it.name == "soak-default-0" }
        val pg = play(g)
        val po = play(o)
        val full = pg.folder.files.getValue(pg.slot.fileName)
        val g5 = recordPrefix(pg, g, 5)
        val g3 = recordPrefix(pg, g, 3)
        val oth = recordPrefix(po, o, 4)
        val broken = g3.copyOf().also { it[it.size / 2] = (it[it.size / 2].toInt() xor 1).toByte() }
        val files = listOf(
            SaveSlots.SlotFile(po.slot.fileName.replace(".h3r", ".m1.h3r"), oth),
            SaveSlots.SlotFile(pg.slot.backupName, g3), // the previous generation is not a slot of its own
            SaveSlots.SlotFile("golden.m10.h3r", g3),
            SaveSlots.SlotFile("golden.m3.h3r", broken),
            SaveSlots.SlotFile("notes.txt", ByteArray(3)),
            SaveSlots.SlotFile(pg.slot.tempName, g5), // an unfinished write
            SaveSlots.SlotFile("golden.m2.h3r", g5),
            SaveSlots.SlotFile(pg.slot.fileName, full),
        )
        return Listing(files, full, g5, g3, oth)
    }

    @Test
    fun theSlotListHasTheAutosaveFirstThenManualSavesInAStableOrder() {
        val l = listing()
        val rows = SaveSlots.list(l.files, packs)
        assertEquals(5, rows.size)
        assertEquals(listOf("golden.h3r", "golden.m2.h3r", "golden.m3.h3r", "golden.m10.h3r", "soak-b0.m1.h3r"), rows.map { it.fileName })
        assertEquals(
            listOf(SaveSlots.SlotKind.Autosave) + List(4) { SaveSlots.SlotKind.Manual },
            rows.map { it.kind },
        )
        assertEquals(listOf(null, 2, 3, 10, 1), rows.map { it.number })
        assertEquals(listOf("Autosave", "Manual save 2", "Manual save 3", "Manual save 10", "Manual save 1"), rows.map { it.title })
        // The same list whatever order the folder listing came in.
        assertEquals(shape(rows), shape(SaveSlots.list(l.files.reversed(), packs)))
        assertEquals(shape(rows), shape(SaveSlots.list(l.files.sortedBy { it.fileName }, packs)))
    }

    @Test
    fun aReadySlotShowsBattleIdCommandCountRoundAndShortHashFromTheFile() {
        val l = listing()
        val rows = SaveSlots.list(l.files, packs)
        fun ready(name: String) = assertIs<SaveSlots.SlotStatus.Ready>(rows.first { it.fileName == name }.status, name)
        for ((name, bytes, n) in listOf(Triple("golden.h3r", l.goldenFull, null), Triple("golden.m2.h3r", l.golden5, 5), Triple("golden.m10.h3r", l.golden3, 3))) {
            val st = ready(name)
            val g = scenarios.first { it.name == "golden" }
            val (hash, round) = stateAfter(g, bytes)
            assertEquals(hash, st.fullHash, name)
            assertEquals(hash.take(8), st.shortHash, name)
            assertEquals(8, st.shortHash.length)
            assertEquals(round, st.rounds, name)
            if (n != null) assertEquals(n, st.commands, name)
            assertEquals(ReplayResume.load(bytes, packs).let { (it as ResumeResult.Ok).resumed.commands.size }, st.commands, name)
            assertEquals("golden", rows.first { it.fileName == name }.battleId)
            // The list verifies exactly as the loader does.
            val viaLoader = (ReplayResume.load(bytes, packs) as ResumeResult.Ok).resumed
            assertEquals(viaLoader.scenarioJson, st.resumed.scenarioJson, name)
            assertEquals(viaLoader.seed, st.resumed.seed, name)
            assertEquals(viaLoader.commands, st.resumed.commands, name)
            assertEquals(viaLoader.finalHash, st.resumed.finalHash, name)
        }
        assertEquals("soak-b0", rows.last().battleId)
        assertEquals(4, ready(rows.last().fileName).commands)
        assertNotEquals(ready("golden.m2.h3r").fullHash, ready("golden.m10.h3r").fullHash)
    }

    @Test
    fun aBrokenSlotIsListedWithTheMessageForItsError() {
        val rows = SaveSlots.list(listing().files, packs)
        val broken = rows.first { it.fileName == "golden.m3.h3r" }
        val st = assertIs<SaveSlots.SlotStatus.Unusable>(broken.status)
        assertEquals(ResumeError.Tampered, st.error)
        assertEquals(SaveSlots.message(ResumeError.Tampered), st.message)
        assertEquals("golden", broken.battleId) // from the file name, the header cannot be trusted
        // Other damage kinds are named too, never thrown.
        val cut = SaveSlots.list(listOf(SaveSlots.SlotFile("golden.m1.h3r", ByteArray(0))), packs).single().status
        assertEquals(ResumeError.Truncated, assertIs<SaveSlots.SlotStatus.Unusable>(cut).error)
        val junk = SaveSlots.list(listOf(SaveSlots.SlotFile("golden.m1.h3r", "hello".toByteArray())), packs).single().status
        assertEquals(ResumeError.Malformed, assertIs<SaveSlots.SlotStatus.Unusable>(junk).error)
    }

    @Test
    fun choosingASlotLoadsExactlyThatSaveOrRefusesWithItsMessage() {
        val l = listing()
        val rows = SaveSlots.list(l.files, packs)
        val g = scenarios.first { it.name == "golden" }
        val sel = assertIs<SaveSlots.SlotSelection.Load>(SaveSlots.select(rows, "golden.m2.h3r"))
        assertEquals("golden.m2.h3r", sel.fileName)
        assertEquals(5, sel.resumed.commands.size)
        val fresh = BattleSession(battle, codec, null, Scenario.parse(sel.resumed.scenarioJson, packs), sel.resumed.seed, setOf(0, 1), direct, 5000)
        var reply: h3.presenter.SubmitResult? = null
        ReplayResume.into(fresh, sel.resumed) { reply = it }
        assertIs<h3.presenter.SubmitResult.Accepted>(reply)
        assertEquals(stateAfter(g, l.golden5).first, fresh.finalHash())
        // The autosave and a different manual save are different games.
        val auto = assertIs<SaveSlots.SlotSelection.Load>(SaveSlots.select(rows, "golden.h3r"))
        assertTrue(auto.resumed.commands.size > 5)
        val other = assertIs<SaveSlots.SlotSelection.Load>(SaveSlots.select(rows, "golden.m10.h3r"))
        assertEquals(3, other.resumed.commands.size)
        // A broken slot is refused with the message of its error and nothing is loaded.
        val bad = assertIs<SaveSlots.SlotSelection.Refused>(SaveSlots.select(rows, "golden.m3.h3r"))
        assertEquals(ResumeError.Tampered, bad.error)
        assertEquals(SaveSlots.message(ResumeError.Tampered), bad.message)
        // Names that are not in the list (including the backup and temp files) cannot be chosen.
        for (n in listOf("golden.h3r.bak", "golden.h3r.tmp", "golden.m99.h3r", "nope", "")) {
            assertEquals(SaveSlots.SlotSelection.NotListed(n), SaveSlots.select(rows, n), n)
        }
    }

    @Test
    fun manualSaveCapIsExactly999() {
        assertEquals(999, SaveSlots.MAX_MANUAL_NUMBER)
        assertNotNull(SaveSlots.manualSlot("skirmish-easy", 999))
        assertNull(SaveSlots.manualSlot("skirmish-easy", 1000))
        assertNull(SaveSlots.nextManualNumber("x", listOf("x.m999.h3r")))
        assertEquals(999, SaveSlots.nextManualNumber("x", listOf("x.m998.h3r")))
    }
}
