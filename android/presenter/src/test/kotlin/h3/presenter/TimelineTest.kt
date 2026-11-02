package h3.presenter

import h3.sim.BattleCommand
import h3.sim.BattleEvent
import h3.sim.BattleState
import h3.sim.HexCell
import h3.sim.RngStreams
import h3.sim.asDrawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class TimelineTest {
    private val codec = Fixture.codec
    private val battle = Fixture.battle
    private val cap = 90

    /** Every (state before, events) step of the golden playouts, same loop as BattleSessionTest.plain. */
    private fun steps(): List<Triple<String, BattleState, List<BattleEvent>>> {
        val out = ArrayList<Triple<String, BattleState, List<BattleEvent>>>()
        for (g in Fixture.games) {
            val rng = RngStreams.derive(g.masterSeed, "battle:" + g.initial.battleId)
            val greedy = Fixture.ai.GreedyAi(g.aiSeed)
            var st = g.initial
            var n = 0
            while ((st.winner == null || !st.started) && n < cap) {
                val side = st.active?.let { st.stacks[it].side }
                val cmd: BattleCommand = if (!st.started) BattleCommand.Begin else greedy.choose(st, side)
                val r = battle.apply(st, cmd, rng.asDrawSource())
                out.add(Triple(g.name, st, r.events))
                st = r.state
                n++
            }
        }
        return out
    }

    private val allSteps by lazy { steps() }

    private fun checkWellFormed(name: String, segs: List<Segment>) {
        var t = 0
        for (s in segs) {
            assertTrue(s.durationMs >= 0, "$name negative duration $s")
            assertEquals(t, s.startMs, "$name gap or overlap at $s")
            t = s.endMs
        }
    }

    @Test
    fun buildAndSkipNeverChangeTheStateAndTotalsAreDeterministicBoundedAndMonotone() {
        assertTrue(allSteps.size > 1000, "steps=${allSteps.size}")
        var withMoves = 0
        var withDamage = 0
        val kinds = HashSet<SegKind>()
        for ((name, before, events) in allSteps) {
            val hashBefore = codec.stateHash(before)
            val copy = codec.parseState(h3.sim.MiniJson.parse(h3.sim.Canonical.encode(codec.toMap(before)).toString(Charsets.US_ASCII)))
            for (sp in AnimSpeed.entries) {
                val prefs = AnimationPrefs(sp)
                val a = Timeline.build(before, events, prefs)
                val b = Timeline.build(copy, events, prefs)
                assertEquals(a, b, "$name $sp deterministic")
                checkWellFormed("$name $sp", a)
                val total = a.lastOrNull()?.endMs ?: 0
                assertTrue(total <= Timeline.maxDurationMs(events, prefs), "$name $sp bound")
                if (sp == AnimSpeed.SKIP) {
                    assertEquals(0, total)
                    assertEquals(Timeline.skip(events), a)
                }
                for (s in a) kinds.add(s.kind)
            }
            assertEquals(hashBefore, codec.stateHash(before), "$name hash after build/skip")
            Timeline.skip(events)
            assertEquals(before, copy, name)
            // slower speed never shortens the total
            fun total(sp: AnimSpeed) = Timeline.build(before, events, AnimationPrefs(sp)).lastOrNull()?.endMs ?: 0
            assertTrue(total(AnimSpeed.SLOW) >= total(AnimSpeed.NORMAL) && total(AnimSpeed.NORMAL) >= total(AnimSpeed.FAST), name)
            if (events.any { it is BattleEvent.Moved }) withMoves++
            if (events.any { it is BattleEvent.DamageDealt }) withDamage++
        }
        assertTrue(withMoves > 100 && withDamage > 100, "moves=$withMoves damage=$withDamage")
        for (k in listOf(SegKind.MOVE_STEP, SegKind.ATTACK, SegKind.HIT, SegKind.DAMAGE_NUMBER, SegKind.DEATH, SegKind.ROUND_BANNER, SegKind.TURN_PULSE)) {
            assertTrue(k in kinds, "kind $k never produced")
        }
    }

    @Test
    fun skipKeepsOnlyTheBattleEndHandOff() {
        var ended = 0
        for ((name, _, events) in allSteps) {
            val s = Timeline.skip(events)
            assertEquals(events.count { it is BattleEvent.BattleEnded }, s.size, name)
            assertTrue(s.all { it.kind == SegKind.BATTLE_END && it.durationMs == 0 && it.startMs == 0 }, name)
            ended += s.size
        }
        assertTrue(ended >= 1)
    }

    @Test
    fun moveSegmentsWalkTheEventPathFromTheRecordedPosition() {
        for ((name, before, events) in allSteps) {
            val segs = Timeline.build(before, events, AnimationPrefs(AnimSpeed.NORMAL))
            val moved = events.filterIsInstance<BattleEvent.Moved>()
            val steps = segs.filter { it.kind == SegKind.MOVE_STEP }
            assertEquals(moved.sumOf { it.path.size }, steps.size, name)
            var i = 0
            for (m in moved) {
                var cur = before.stacks[m.stack].pos
                for (p in m.path) {
                    val s = steps[i++]
                    assertEquals(HexCell(cur.first, cur.second), s.from, name)
                    assertEquals(HexCell(p.first, p.second), s.to, name)
                    assertEquals(67 * Timeline.Frames.MOVE_STEP, s.durationMs, name)
                    cur = p
                }
            }
        }
    }

    @Test
    fun damageNumbersCarryTheEngineDamageAndRoundBannersTheRound() {
        for ((name, before, events) in allSteps) {
            val segs = Timeline.build(before, events, AnimationPrefs(AnimSpeed.FAST))
            assertEquals(events.filterIsInstance<BattleEvent.DamageDealt>().map { it.damage },
                segs.filter { it.kind == SegKind.DAMAGE_NUMBER }.map { it.value }, name)
            assertEquals(events.filterIsInstance<BattleEvent.RoundStarted>().map { it.round.toLong() },
                segs.filter { it.kind == SegKind.ROUND_BANNER }.map { it.value }, name)
            assertEquals(events.count { it is BattleEvent.UnitDied }, segs.count { it.kind == SegKind.DEATH }, name)
        }
    }

    @Test
    fun segmentsFollowEventOrder() {
        // two events: reordering the input reorders the output (order is the event order, stable)
        val (_, before, _) = allSteps.first { (_, _, ev) -> ev.count { it is BattleEvent.RoundStarted || it is BattleEvent.TurnStarted } >= 2 }
        val ev = listOf(BattleEvent.RoundStarted(7), BattleEvent.UnitDied(before.stacks[0].id))
        val a = Timeline.build(before, ev, AnimationPrefs())
        assertEquals(listOf(SegKind.ROUND_BANNER, SegKind.DEATH), a.map { it.kind })
        val b = Timeline.build(before, ev.reversed(), AnimationPrefs())
        assertEquals(listOf(SegKind.DEATH, SegKind.ROUND_BANNER), b.map { it.kind })
        assertEquals(0, a[0].startMs)
        assertEquals(a[0].endMs, a[1].startMs)
    }

    @Test
    fun apiNeverMentionsCommands() {
        val methods = Timeline::class.java.declaredMethods
        for (m in methods) {
            assertTrue(m.parameterTypes.none { BattleCommand::class.java.isAssignableFrom(it) }, m.name)
            assertTrue(!BattleCommand::class.java.isAssignableFrom(m.returnType), m.name)
        }
    }
}
