package h3.presenter

import h3.sim.BattleCommand
import h3.sim.BattleState
import h3.sim.HexCell
import h3.sim.Present
import h3.sim.legalCommands
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlin.test.fail

class TapReducerTest {
    private val battle = Fixture.battle
    private val reducer = TapReducer(battle)
    private val present = Present(battle)

    private fun cell(p: Pair<Int, Int>) = HexCell(p.first, p.second)

    /** A started state whose active stack can Move (some state of the recorded cases). */
    private fun firstState(pred: (BattleState) -> Boolean): BattleState =
        Fixture.states.firstOrNull(pred) ?: fail("no recorded state matches")

    private fun live(s: BattleState) = s.started && s.winner == null && s.active != null

    private fun movesOf(s: BattleState) = battle.legalCommands(s).filterIsInstance<BattleCommand.Move>()
    private fun attacksOf(s: BattleState) = battle.legalCommands(s).filterIsInstance<BattleCommand.Attack>()

    private val moveState by lazy { firstState { live(it) && movesOf(it).isNotEmpty() } }
    private val attackState by lazy { firstState { live(it) && attacksOf(it).isNotEmpty() } }
    private val shootState by lazy {
        firstState { live(it) && battle.legalCommands(it).any { c -> c is BattleCommand.Shoot } }
    }

    private fun tap(ui: TapState, h: HexCell, s: BattleState) = reducer.reduce(ui, TapEvent.Tap(h), s)

    @Test
    fun idleTapOnMoveHexPreviewsThenSecondTapConfirmsTheExactCommand() {
        val s = moveState
        val mv = movesOf(s).first()
        val h = cell(mv.dest)
        val p = tap(TapState.Idle, h, s)
        assertIs<TapState.Previewing>(p)
        assertEquals(h, p.hex)
        assertEquals(mv, p.command)
        assertEquals(null, p.candidates.single().preview)
        assertEquals(TapState.Confirmed(mv), tap(p, h, s))
    }

    @Test
    fun tapOnNonActionableHexIsANoOpInEveryState() {
        val s = moveState
        val legal = battle.legalCommands(s).filterIsInstance<BattleCommand.Move>().map { it.dest }.toSet()
        val bad = (0 until 15).flatMap { r -> (0 until 17).map { c -> HexCell(c, r) } }
            .first { Pair(it.col, it.row) !in legal && present.candidateCommands(s, Pair(it.col, it.row)).isEmpty() }
        assertSame(TapState.Idle, tap(TapState.Idle, bad, s))
        val prev = tap(TapState.Idle, cell(movesOf(s).first().dest), s)
        assertSame(prev, tap(prev, bad, s))
        val conf = TapState.Confirmed(BattleCommand.Defend(0))
        assertSame(TapState.Idle, tap(conf, bad, s))
        assertSame(TapState.Idle, reducer.reduce(TapState.Idle, TapEvent.Cancel, s))
        assertSame(TapState.Idle, reducer.reduce(TapState.Idle, TapEvent.Select(0), s))
    }

    @Test
    fun tapElsewhereRetargetsAndDoesNotConfirm() {
        val s = firstState { live(it) && movesOf(it).size >= 2 }
        val (a, b) = movesOf(s).take(2).map { cell(it.dest) }
        val pa = tap(TapState.Idle, a, s)
        val pb = tap(pa, b, s)
        assertIs<TapState.Previewing>(pb)
        assertEquals(b, pb.hex)
        // and back: the first tap on a is a preview again, not a confirm
        assertIs<TapState.Previewing>(tap(pb, a, s))
    }

    @Test
    fun cancelAndLongPressAndSelect() {
        val s = moveState
        val h = cell(movesOf(s).first().dest)
        val p = tap(TapState.Idle, h, s)
        assertSame(TapState.Idle, reducer.reduce(p, TapEvent.Cancel, s))
        assertSame(TapState.Idle, reducer.reduce(TapState.Confirmed(BattleCommand.Begin), TapEvent.Cancel, s))
        // long press never changes the preview state (android-app.md 5.1): the app shows the card
        assertSame(TapState.Idle, reducer.reduce(TapState.Idle, TapEvent.LongPress(h), s))
        assertSame(p, reducer.reduce(p, TapEvent.LongPress(h), s))
        val other = cell(movesOf(s).last().dest)
        assertSame(p, reducer.reduce(p, TapEvent.LongPress(other), s))
        val q = reducer.reduce(p, TapEvent.Select(0), s)
        assertSame(q, reducer.reduce(q, TapEvent.LongPress(h), s))
        assertSame(TapState.Idle, reducer.reduce(TapState.Confirmed(BattleCommand.Begin), TapEvent.LongPress(h), s))
        // select outside the candidates is ignored
        assertSame(p, reducer.reduce(p, TapEvent.Select(5), s))
        assertSame(p, reducer.reduce(p, TapEvent.Select(-1), s))
    }

    @Test
    fun doubleWideTargetResolvesBothCellsToOneTarget() {
        val s = firstState { st ->
            live(st) && attacksOf(st).any { battle.cells(st.stacks[it.target]).size == 2 }
        }
        val tgt = s.stacks[attacksOf(s).first { battle.cells(s.stacks[it.target]).size == 2 }.target]
        val (head, tail) = battle.cells(tgt)
        assertTrue(head != tail)
        val viaHead = tap(TapState.Idle, head, s)
        val viaTail = tap(TapState.Idle, tail, s)
        assertIs<TapState.Previewing>(viaTail)
        assertEquals(viaHead, viaTail)
        assertEquals(head, viaTail.hex)
        // tail then head, or head then tail, confirm the same command
        val c1 = tap(viaTail, head, s)
        val c2 = tap(viaHead, tail, s)
        assertIs<TapState.Confirmed>(c1)
        assertEquals(c1, c2)
        assertTrue(c1.command is BattleCommand.Attack || c1.command is BattleCommand.Shoot)
    }

    @Test
    fun attackCandidatesCarryPreviewsAndDefaultIsNoMoveAttack() {
        // A melee target with both the attack without moving and attacks from other hexes.
        var found = 0
        for (s in Fixture.states.filter(::live)) {
            for (t in attacksOf(s).filter { it.fromHex == null }.map { it.target }.distinct()) {
                val p = tap(TapState.Idle, battle.cells(s.stacks[t]).first(), s)
                assertIs<TapState.Previewing>(p)
                if (p.candidates.any { it.command is BattleCommand.Shoot }) continue
                if (p.candidates.size < 2) continue
                for (c in p.candidates) {
                    val pv = c.preview ?: fail("no preview for ${c.command}")
                    assertTrue(pv.floor <= pv.expected && pv.expected <= pv.ceiling)
                    assertTrue(pv.killsFloor <= pv.killsExpected && pv.killsExpected <= pv.killsCeiling)
                }
                assertEquals(BattleCommand.Attack(s.active!!, t, null), p.command)
                if (++found >= 10) return
            }
        }
        assertTrue(found > 0, "no melee target with several attack candidates in the recorded states")
    }

    @Test
    fun shooterTargetDefaultsToShootAndSelectSwitchesCandidate() {
        // A shoot target that also has melee candidates (at least two candidates in all).
        var found = 0
        for (s in Fixture.states.filter(::live)) {
            for (sh in battle.legalCommands(s).filterIsInstance<BattleCommand.Shoot>()) {
                val p = tap(TapState.Idle, battle.cells(s.stacks[sh.target]).first(), s)
                assertIs<TapState.Previewing>(p)
                assertEquals(sh, p.command)
                if (p.candidates.size < 2) continue
                val i = p.candidates.indexOfFirst { it.command != sh }
                val q = reducer.reduce(p, TapEvent.Select(i), s)
                assertIs<TapState.Previewing>(q)
                assertEquals(p.candidates[i].command, q.command)
                assertEquals(TapState.Confirmed(p.candidates[i].command), tap(q, p.hex, s))
                assertEquals(TapState.Confirmed(sh), tap(p, p.hex, s))
                if (++found >= 5) return
            }
        }
        assertTrue(found > 0, "no shoot target with two or more candidates in the recorded states")
    }

    @Test
    fun tapOnThePreviewedHexAfterTheTargetMovedAwayDoesNotConfirmTheAttack() {
        // Preview a no-move attack on T at hex h; then T moves to another hex next to the attacker,
        // so the attack is still legal, but h is now an empty hex (a move). The second tap on h must
        // give the move preview, not confirm an attack on a stack that is no longer under the finger.
        val (s, st, h) = AttackMovedScenario.find(battle)
        val p = tap(TapState.Idle, h, s)
        assertIs<TapState.Previewing>(p)
        val atk = p.command
        assertIs<BattleCommand.Attack>(atk)
        assertTrue(atk in battle.legalCommands(st), "precondition: the attack is still legal")
        val fresh = tap(TapState.Idle, h, st)
        assertIs<TapState.Previewing>(fresh)
        assertTrue(fresh.candidates.none { it.command == atk })
        assertEquals(fresh, tap(p, h, st))
    }

    @Test
    fun confirmedCommandIsAlwaysLegalAndStaleConfirmRebuildsPreview() {
        val s = moveState
        val h = cell(movesOf(s).first().dest)
        val p = tap(TapState.Idle, h, s)
        // The state moves on: pick a later state where h is no longer a legal destination.
        val later = Fixture.states.first { st ->
            live(st) && present.candidateCommands(st, Pair(h.col, h.row)).isEmpty()
        }
        assertSame(p, tap(p, h, later)) // no candidates now: no-op, never a stale confirm
        for (st in Fixture.states.filter(::live).take(300)) {
            val cmds = battle.legalCommands(st)
            for (m in cmds.filterIsInstance<BattleCommand.Move>().take(3)) {
                val h1 = cell(m.dest)
                val c = tap(tap(TapState.Idle, h1, st), h1, st)
                assertIs<TapState.Confirmed>(c)
                assertTrue(c.command in cmds)
            }
        }
    }

    @Test
    fun staleSelectedCommandIsNeverConfirmedWhenTheHexIsStillActionable() {
        // Preview in state s, then the battle moves on to a state st where the same hex is still
        // actionable. A second tap confirms only if the previewed command is still one of the hex's
        // candidates in st; otherwise it rebuilds the preview for st. Moves, attacks and shoots.
        val live = Fixture.states.filter(::live).take(150)
        val stale = HashMap<String, Int>()
        val kind = { c: BattleCommand -> c::class.simpleName!! }
        for (s in live) {
            val cmds = battle.legalCommands(s)
            val hexes = cmds.filterIsInstance<BattleCommand.Move>().take(2).map { cell(it.dest) } +
                cmds.mapNotNull { (it as? BattleCommand.Attack)?.target ?: (it as? BattleCommand.Shoot)?.target }
                    .distinct().map { battle.cells(s.stacks[it]).first() }
            for (h in hexes) {
                val p = tap(TapState.Idle, h, s)
                assertIs<TapState.Previewing>(p)
                val k = kind(p.command)
                if ((stale[k] ?: 0) >= 20) continue
                for (st in live) {
                    if (st === s) continue
                    val fresh = tap(TapState.Idle, h, st)
                    if (fresh !is TapState.Previewing || fresh.hex != p.hex) continue
                    val after = tap(p, h, st)
                    if (fresh.candidates.any { it.command == p.command }) {
                        assertEquals(TapState.Confirmed(p.command), after)
                    } else {
                        assertTrue(after !is TapState.Confirmed, "a stale ${p.command} was confirmed")
                        assertEquals(fresh, after)
                        stale[k] = (stale[k] ?: 0) + 1
                    }
                }
            }
        }
        for (k in listOf("Move", "Attack", "Shoot")) assertTrue((stale[k] ?: 0) > 0, "no stale $k preview found: $stale")
    }

    @Test
    fun reducerIsDeterministicAndDoesNotTouchTheState() {
        val s = attackState
        val before = Fixture.codec.stateHash(s)
        val h = battle.cells(s.stacks[attacksOf(s).first().target]).first()
        val a = tap(tap(TapState.Idle, h, s), h, s)
        val b = tap(tap(TapState.Idle, h, s), h, s)
        assertEquals(a, b)
        assertEquals(before, Fixture.codec.stateHash(s))
    }
}
