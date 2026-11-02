package h3.sim.encounter

import h3.sim.AdvArmySlot
import h3.sim.AdvEncounter
import h3.sim.AdvGuard
import h3.sim.AdvHero
import h3.sim.Adventure
import h3.sim.AdventureCodec
import h3.sim.AdventureCommand
import h3.sim.AdventureEncounterHooks
import h3.sim.AdventureEvent
import h3.sim.AdventureRules
import h3.sim.AdventureState
import h3.sim.AdventureStep
import h3.sim.Battle
import h3.sim.BattleCodec
import h3.sim.BattleCommand
import h3.sim.BattleCreature
import h3.sim.BattleEvent
import h3.sim.BattleHero
import h3.sim.BattleJson
import h3.sim.BattlePolicy
import h3.sim.BattleState
import h3.sim.Canonical
import h3.sim.Datapack
import h3.sim.DrawSource
import h3.sim.Hex
import h3.sim.HexCell
import h3.sim.IllegalCommand
import h3.sim.Pcg32
import h3.sim.RngStreams
import h3.sim.Scenario
import h3.sim.asDrawSource
import h3.sim.legalCommands
import java.math.BigInteger

/**
 * Adventure-map encounters: a hero attacks a neighbouring enemy hero or a neutral guard, the fight is a
 * [Battle] battle, survivors flow back. A port of `tools/h3re/h3re/encounter.py` (docs/specs/encounter.md),
 * conformance-tested against `encounter.json` (docs/specs/conformance-encounter.md). Python is authoritative
 * (ADR-0004, ADR-0007).
 *
 * Dependency direction: this package uses `h3.sim` (the adventure core, the battle); the adventure core knows
 * only the [AdventureEncounterHooks] interface that [EncounterEngine] implements. Python imports lazily the other
 * way; there is no cycle here.
 *
 * Rules as in Python: the `Attack` is validated completely (every check, no draw) before the battle stream is
 * touched; the battle draws only from the passed stream (`battle:<battle_id>`, [EncounterEngine.streamFor]);
 * the auto-combat chooser draws nothing. Integer only. Differences (all documented in the conformance spec):
 * `round_limit` is a [Long] (Python: any int); the battle counter is an [Int] (an overflowing `Attack` is refused
 * with [ArithmeticException] before any draw); an army of more than 7 slots (Python `IndexError`) is out of scope.
 */

/** Python `EncounterPolicy`. No defaults here: the values come from the state (balance numbers are not in code). */
data class EncounterPolicy(val loserFate: String, val slotMapping: String, val roundLimit: Long) {
    init {
        require(loserFate in LOSER_FATES) { "bad loser_fate" }
        require(slotMapping in SLOT_MAPPINGS) { "bad slot_mapping" }
        require(roundLimit >= 1) { "round_limit must be an int >= 1" }
    }

    fun toMap(): Map<String, Any?> = linkedMapOf(
        "loser_fate" to loserFate, "slot_mapping" to slotMapping, "round_limit" to roundLimit,
    )

    companion object {
        val LOSER_FATES = listOf("removed", "winner_takes_tile")
        val SLOT_MAPPINGS = listOf("by_count", "by_slot")

        /** Python `EncounterPolicy(**d)`: the same checks in the same order; a non-int `round_limit` has the same message. */
        fun parse(v: Any?): EncounterPolicy {
            val m = BattleJson.obj(v, "policy")
            BattleJson.exactKeys(m, setOf("loser_fate", "slot_mapping", "round_limit"), "policy")
            val fate = m["loser_fate"] as? String ?: throw IllegalArgumentException("bad loser_fate")
            require(fate in LOSER_FATES) { "bad loser_fate" }
            val mapping = m["slot_mapping"] as? String ?: throw IllegalArgumentException("bad slot_mapping")
            require(mapping in SLOT_MAPPINGS) { "bad slot_mapping" }
            val rl = m["round_limit"]
            val limit = when (rl) {
                is Int -> rl.toLong()
                is Long -> rl
                is BigInteger -> if (rl.bitLength() < 64) rl.toLong() else
                    if (rl.signum() < 0) 0L else throw IllegalArgumentException("round_limit beyond 2**63-1 is not supported")
                else -> throw IllegalArgumentException("round_limit must be an int >= 1")
            }
            return EncounterPolicy(fate, mapping, limit)
        }
    }
}

/**
 * Python `EncounterSetup`: what a game needs to fight battles (the state's `encounter` field). [creatures] is sorted
 * by name in code-point order (Python `sorted`) and unique; build it with [of], which sorts. [rulesHash] is the rules
 * pack the game was set up under (ADR-0001).
 */
class EncounterSetup private constructor(
    val creatures: List<BattleCreature>,
    val policy: EncounterPolicy,
    val battlePolicy: BattlePolicy,
    val rulesHash: String,
) : AdvEncounter {
    override fun toMap(): Map<String, Any?> = linkedMapOf(
        "creatures" to creatures.map { BattleCodec.creatureToMap(it) },
        "policy" to policy.toMap(),
        "battle_policy" to BattleCodec.policyToMap(battlePolicy),
        "rules_hash" to rulesHash,
    )

    override fun equals(other: Any?): Boolean =
        other is EncounterSetup && creatures == other.creatures && policy == other.policy &&
            battlePolicy == other.battlePolicy && rulesHash == other.rulesHash

    override fun hashCode(): Int = creatures.hashCode() * 31 + rulesHash.hashCode()

    override fun toString(): String = "EncounterSetup(${creatures.map { it.name }}, $policy, $rulesHash)"

    companion object {
        /** Python `EncounterSetup(creatures, policy, battle_policy, rules_hash)`: sorts by name, refuses a duplicate name. */
        fun of(creatures: List<BattleCreature>, policy: EncounterPolicy, battlePolicy: BattlePolicy, rulesHash: String): EncounterSetup {
            val cs = creatures.sortedWith { a, b -> Canonical.codePointOrder.compare(a.name, b.name) }
            require(cs.map { it.name }.toSet().size == cs.size) { "duplicate creature name" }
            return EncounterSetup(cs, policy, battlePolicy, rulesHash)
        }
    }
}

// Events ---------------------------------------------------------------------------------------------------------

private fun posList(p: Pair<Int, Int>) = listOf(p.first, p.second)

private fun slotMap(s: AdvArmySlot): Map<String, Any?> = linkedMapOf("creature" to s.creature, "speed" to s.speed, "count" to s.count)

/** Python `BattleFought`. [target] is a hero id ([Int]) or a guard id ([String]); [winner] null at the round limit. */
data class BattleFought(
    val battleId: String,
    val attacker: Int,
    val target: Any,
    val winner: Int?,
    val rounds: Long,
    val log: List<BattleCommand>,
    val battleEvents: List<BattleEvent>,
    val battleHash: String,
) : AdventureEvent {
    override fun toMap(): Map<String, Any?> = linkedMapOf(
        "type" to "BattleFought", "battle_id" to battleId, "attacker" to attacker, "target" to target,
        "winner" to winner, "rounds" to rounds, "log" to log.map { BattleCodec.commandToMap(it) },
        "battle_events" to battleEvents.map { BattleCodec.eventToMap(it) }, "battle_hash" to battleHash,
    )
}

/** Python `ArmyChanged`: [unit] is a hero id ([Int]) or a guard id ([String]). */
data class ArmyChanged(val unit: Any, val army: List<AdvArmySlot>) : AdventureEvent {
    override fun toMap(): Map<String, Any?> = linkedMapOf("type" to "ArmyChanged", "unit" to unit, "army" to army.map(::slotMap))
}

data class HeroDefeated(val hero: Int) : AdventureEvent {
    override fun toMap(): Map<String, Any?> = linkedMapOf("type" to "HeroDefeated", "hero" to hero)
}

data class GuardDefeated(val guard: String) : AdventureEvent {
    override fun toMap(): Map<String, Any?> = linkedMapOf("type" to "GuardDefeated", "guard" to guard)
}

/** Result of [EncounterEngine.fight]: the final battle state, the commands applied (Begin first) and every battle event. */
class Fought(val state: BattleState, val log: List<BattleCommand>, val events: List<BattleEvent>)

// The engine -----------------------------------------------------------------------------------------------------

/**
 * Encounters for one rules pack: the adventure rules (for the adjacency test), the [Battle] engine and the codec that
 * hashes battle states. Implements [AdventureEncounterHooks]: pass it to [Adventure] and [AdventureCodec].
 */
class EncounterEngine(rules: AdventureRules, val battle: Battle, val battleCodec: BattleCodec) : AdventureEncounterHooks {
    /** The content hash of the local rules pack (Python `rules.RULES_HASH`). */
    val rulesHash: String get() = battle.rulesHash

    private val adventure = Adventure(rules)

    // Streams -----------------------------------------------------------------------------------------------------

    /** Id of the next battle in this game: `<game_id>:<n>`, n = battles + 1 (a Long: no wrap at Int.MAX). */
    fun battleId(state: AdventureState): String = "${state.gameId}:${state.battles.toLong() + 1L}"

    /** Python `battle.battle_rng`: the named stream `battle:<battle_id>`. */
    fun battleRng(masterSeed: BigInteger, battleId: String): Pcg32 = RngStreams.derive(masterSeed, "battle:$battleId")

    fun battleRng(masterSeed: Long, battleId: String): Pcg32 = battleRng(BigInteger.valueOf(masterSeed), battleId)

    /** The next battle's stream `battle:<battle_id(state)>`. */
    fun encounterRng(masterSeed: BigInteger, state: AdventureState): Pcg32 = battleRng(masterSeed, battleId(state))

    fun encounterRng(masterSeed: Long, state: AdventureState): Pcg32 = encounterRng(BigInteger.valueOf(masterSeed), state)

    /** The stream `Adventure.apply(state, cmd, rng)` expects: the battle stream for an Attack, `adventure:<game_id>` otherwise. */
    fun streamFor(masterSeed: BigInteger, state: AdventureState, cmd: AdventureCommand): Pcg32 =
        if (cmd is AdventureCommand.Attack) encounterRng(masterSeed, state)
        else RngStreams.derive(masterSeed, "adventure:${state.gameId}")

    fun streamFor(masterSeed: Long, state: AdventureState, cmd: AdventureCommand): Pcg32 =
        streamFor(BigInteger.valueOf(masterSeed), state, cmd)

    /** SHA-256 of a battle state (`battle.state_hash`). */
    fun battleHash(bs: BattleState): String = battleCodec.stateHash(bs)

    // Setup checks --------------------------------------------------------------------------------------------------

    override fun parseSetup(v: Any?): EncounterSetup {
        val m = BattleJson.obj(v, "encounter")
        BattleJson.exactKeys(m, setOf("creatures", "policy", "battle_policy", "rules_hash"), "encounter")
        val creatures = BattleJson.list(m["creatures"], "creatures").map { BattleCodec.creatureFrom(it) }
        val policy = EncounterPolicy.parse(m["policy"])
        val bp = BattleCodec.policyFrom(BattleJson.obj(m["battle_policy"], "battle_policy"), "battle_policy", battle.rules.pack.moraleDie.toInt())
        return EncounterSetup.of(creatures, policy, bp, BattleJson.str(m["rules_hash"], "rules_hash"))
    }

    /** The battle creature for an army slot, or null (unknown name, or its speed differs). */
    private fun creature(setup: EncounterSetup, slot: AdvArmySlot): BattleCreature? {
        for (c in setup.creatures) if (c.name == slot.creature) return if (c.speed == slot.speed) c else null
        return null
    }

    override fun checkGame(state: AdventureState) {
        val setup = state.encounter as? EncounterSetup ?: throw IllegalArgumentException("encounter must be an EncounterSetup")
        val units = ArrayList<Pair<String, List<AdvArmySlot>>>()
        for (h in state.heroes) units.add(Pair("hero ${h.id}", h.army))
        for (g in state.guards) units.add(Pair("guard ${AdventureCodec.pyRepr(g.id)}", g.army))
        for ((what, army) in units) {
            for (slot in army) {
                require(creature(setup, slot) != null) {
                    "$what: no creature ${AdventureCodec.pyRepr(slot.creature)} with speed ${slot.speed} in the setup"
                }
            }
        }
    }

    // Validation (no draws) -----------------------------------------------------------------------------------------

    private fun guardIndex(state: AdventureState, id: String): Int = state.guards.indexOfFirst { it.id == id }

    private fun stackSetups(setup: EncounterSetup, army: List<AdvArmySlot>, side: Int): List<Scenario.Setup> =
        army.mapIndexed { i, slot ->
            val cr = creature(setup, slot) ?: throw IllegalCommand("no content for creature ${AdventureCodec.pyRepr(slot.creature)}")
            var pos: Pair<Int, Int>? = null
            if (setup.policy.slotMapping == "by_slot") {
                val wide = if (cr.doubleWide) 1 else 0
                val col = if (side == Hex.ATTACKER) 1 + wide else Hex.WIDTH - 2 - wide
                pos = Pair(col, setup.battlePolicy.placementRows[6][i])
            }
            Scenario.Setup(cr, slot.count, 0, 0, pos)   // morale 0, luck 0
        }

    /**
     * Python `validate`: checks an Attack and builds its battle (the initial, not yet started [BattleState]). Throws
     * [IllegalCommand] otherwise; draws nothing and changes nothing. The caller has checked that the game started.
     */
    fun buildBattle(state: AdventureState, cmd: AdventureCommand.Attack): BattleState {
        val setup = state.encounter as EncounterSetup
        if (setup.rulesHash != rulesHash) {
            throw IllegalCommand("game rules_hash ${setup.rulesHash} differs from the local rules pack $rulesHash")
        }
        val hid = cmd.hero
        if (hid == null || hid < 0 || hid >= state.heroes.size) throw IllegalCommand("no such hero")
        val hero = state.heroes[hid]
        if (hero.owner != state.current) throw IllegalCommand("hero does not belong to the current player")
        val heroPos = hero.pos ?: throw IllegalCommand("hero is not on the map")
        val army: List<AdvArmySlot>
        val pos: Pair<Int, Int>
        val foeHero: BattleHero?
        when (val t = cmd.target) {
            is Int -> {
                if (t < 0 || t >= state.heroes.size || t == hid) throw IllegalCommand("no such target hero")
                val foe = state.heroes[t]
                pos = foe.pos ?: throw IllegalCommand("target hero is not on the map")
                if (foe.owner == hero.owner) throw IllegalCommand("cannot attack an own hero")
                army = foe.army
                foeHero = BattleHero()
            }
            is String -> {
                val i = guardIndex(state, t)
                if (i < 0) throw IllegalCommand("no such guard")
                pos = state.guards[i].pos
                army = state.guards[i].army
                foeHero = null
            }
            else -> throw IllegalCommand("target must be a hero id or a guard id")
        }
        if (adventure.stepCost(state.grid, heroPos, pos, hero.pathfinding, state.policy) == null) {
            throw IllegalCommand("target is not next to the hero")
        }
        val attackers = stackSetups(setup, hero.army, Hex.ATTACKER)
        val defenders = stackSetups(setup, army, Hex.DEFENDER)
        try {
            return Scenario.createBattle(battleId(state), attackers, defenders, emptyList(), listOf(BattleHero(), foeHero), setup.battlePolicy, rulesHash)
        } catch (e: IllegalCommand) {
            throw e
        } catch (e: IllegalArgumentException) {
            throw IllegalCommand("battle cannot be set up: ${e.message}")
        }
    }

    override fun validate(state: AdventureState, cmd: AdventureCommand.Attack): Any = buildBattle(state, cmd)

    // The fight -----------------------------------------------------------------------------------------------------

    /**
     * Deterministic auto-combat choice (no stream): the attack or shot with the highest expected damage
     * (`strikePreview`), first in `legalCommands` order on ties; else the move that brings the head closest to an
     * enemy cell, if it is closer than now (ties: smallest hex); else Defend.
     */
    fun autoCommand(bs: BattleState): BattleCommand {
        val legal = battle.legalCommands(bs)
        if (!bs.started) return legal[0]
        val st = bs.stacks[bs.active!!]
        var best: Pair<Long, BattleCommand>? = null
        val seen = LinkedHashMap<Pair<Int, Boolean>, Long>()
        for (c in legal) {
            val key = when (c) {
                is BattleCommand.Attack -> Pair(c.target, false)
                is BattleCommand.Shoot -> Pair(c.target, true)
                else -> continue
            }
            val expected = seen.getOrPut(key) { battle.strikePreview(bs, st.id, key.first, key.second).expected }
            if (best == null || expected > best.first) best = Pair(expected, c)
        }
        if (best != null) return best.second
        val off = bs.policy.rowOffset
        val foes = ArrayList<HexCell>()
        for (e in bs.stacks) if (e.alive && e.side != st.side) foes.addAll(battle.cells(e))

        fun gap(head: Pair<Int, Int>): Int = foes.minOf { Hex.distance(HexCell(head.first, head.second), it, off) }

        val moves = legal.filterIsInstance<BattleCommand.Move>()
        if (moves.isNotEmpty()) {
            val m = moves.minWith(compareBy<BattleCommand.Move>({ gap(it.dest) }, { it.dest.first }, { it.dest.second }))
            if (gap(m.dest) < gap(st.pos)) return m
        }
        return BattleCommand.Defend(st.id)
    }

    /**
     * Runs a battle to its end with [autoCommand] on [rng]. Stops with no winner when round `roundLimit + 1` starts.
     */
    fun fight(bs0: BattleState, rng: DrawSource, roundLimit: Long): Fought {
        var bs = bs0
        val log = ArrayList<BattleCommand>()
        val events = ArrayList<BattleEvent>()
        while (bs.winner == null && !(bs.started && bs.round.toLong() > roundLimit)) {
            val cmd = autoCommand(bs)
            val r = battle.apply(bs, cmd, rng)
            bs = r.state
            log.add(cmd)
            events.addAll(r.events)
        }
        return Fought(bs, log, events)
    }

    /** Army slot i <- battle stack slot i of [side]; dead slots drop out. */
    fun survivors(army: List<AdvArmySlot>, bs: BattleState, side: Int): List<AdvArmySlot> {
        val stacks = bs.stacks.filter { it.side == side }
        return army.zip(stacks).filter { (_, s) -> s.count > 0 }.map { (slot, s) -> slot.copy(count = s.count) }
    }

    private fun heroAfter(h: AdvHero, army: List<AdvArmySlot>, events: MutableList<AdventureEvent>): AdvHero {
        if (army.isEmpty()) {
            events.add(HeroDefeated(h.id))
            return h.copy(pos = null, army = emptyList(), mp = 0, mpMax = 0)
        }
        if (army != h.army) {
            events.add(ArmyChanged(h.id, army))
            return h.copy(army = army)
        }
        return h
    }

    /** Fights the battle [prepared] (from [validate]) on [rng] and applies the outcome. */
    override fun resolve(state: AdventureState, cmd: AdventureCommand.Attack, rng: Pcg32?, prepared: Any): AdventureStep {
        val bs = prepared as BattleState
        val pol = (state.encounter as EncounterSetup).policy
        val battles = Math.addExact(state.battles, 1)    // before any draw: an overflow leaves state and stream untouched
        val stream = requireNotNull(rng) { "an Attack needs the battle stream (EncounterEngine.streamFor)" }
        val fought = fight(bs, stream.asDrawSource(), pol.roundLimit)
        val end = fought.state
        val target = cmd.target!!
        val events = ArrayList<AdventureEvent>()
        events.add(BattleFought(
            bs.battleId, cmd.hero!!, target, end.winner, minOf(end.round.toLong(), pol.roundLimit),
            fought.log, fought.events, battleHash(end),
        ))
        val heroes = state.heroes.toMutableList()
        val guards = state.guards.toMutableList()
        val att = heroes[cmd.hero!!]
        heroes[att.id] = heroAfter(att, survivors(att.army, end, Hex.ATTACKER), events)
        val targetPos: Pair<Int, Int>
        if (target is Int) {
            val foe = heroes[target]
            targetPos = foe.pos!!
            heroes[foe.id] = heroAfter(foe, survivors(foe.army, end, Hex.DEFENDER), events)
        } else {
            val i = guardIndex(state, target as String)
            val g = guards[i]
            targetPos = g.pos
            val army = survivors(g.army, end, Hex.DEFENDER)
            if (army.isEmpty()) {
                guards.removeAt(i)
                events.add(GuardDefeated(g.id))
            } else if (army != g.army) {
                guards[i] = g.copy(army = army)
                events.add(ArmyChanged(g.id, army))
            }
        }
        if (end.winner == Hex.ATTACKER && pol.loserFate == "winner_takes_tile") {
            val h = heroes[att.id]
            heroes[att.id] = h.copy(pos = targetPos)
            events.add(AdventureEvent.HeroMoved(h.id, listOf(h.pos!!, targetPos), 0, h.mp))
        }
        return AdventureStep(state.copy(heroes = heroes, guards = guards, battles = battles), events)
    }

    companion object {
        /** The engine for the rules, battle policy and creature packs in [packs]. */
        fun from(rules: AdventureRules, packs: Datapack): EncounterEngine {
            val moraleDie = Math.toIntExact(packs.rules.pack.moraleDie)
            val pack = h3.sim.BattlePolicyPack(packs.policy.values, packs.rules.pack.badMoraleNumerators.map { Math.toIntExact(it) }, moraleDie)
            return EncounterEngine(rules, Battle(h3.sim.Rules(packs.rules.pack), packs.rules.contentHash), BattleCodec(pack))
        }
    }
}
