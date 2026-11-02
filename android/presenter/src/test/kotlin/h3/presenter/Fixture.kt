package h3.presenter

import h3.sim.Battle
import h3.sim.BattleAi
import h3.sim.BattleCodec
import h3.sim.BattlePolicyPack
import h3.sim.BattleState
import h3.sim.MiniJson
import h3.sim.Rational
import h3.sim.Rules
import h3.sim.RulesPack
import h3.sim.big
import h3.sim.list
import h3.sim.loadVector
import h3.sim.obj
import java.math.BigInteger

/** One recorded AI game of `battle_ai.json`: initial state, seeds and the recorded final hash. */
class Game(
    val name: String, val initial: BattleState, val masterSeed: BigInteger, val aiSeed: Long,
    val finalHash: String, val finalSteps: Int, val winner: Int?, val perturbed: Boolean,
)

/** Engine objects built from the conformance vectors (the same packs the sim tests use). */
object Fixture {
    private val doc = loadVector("battle_ai.json")
    private val packs = doc["packs"].obj()

    val codec = BattleCodec(
        BattlePolicyPack(packs["battle_policy"].obj(), packs["bad_morale_numerators"].list().map { it.big().toInt() }),
    )
    val battle = Battle(Rules(rulesPack(packs["rules"].obj())), packs["rules_hash"] as String)
    val ai = BattleAi(battle, codec)

    val games: List<Game> = doc["games"].list().map { it.obj() }.map { g ->
        val sc = g["scenario"].obj()
        val fin = g["final"].obj()
        Game(
            g["name"] as String, codec.parseState(MiniJson.parse(g["initial"].obj()["canonical"] as String)),
            sc["master_seed"].big(), sc["ai_seed"].big().toLong(), fin["sha256"] as String,
            fin["steps"].big().toInt(), fin["winner"]?.big()?.toInt(), sc["perturbed"] as Boolean,
        )
    }

    /** Every recorded state (from `battle_states.json`) of every case, for interaction scans. */
    val states: List<BattleState> by lazy {
        val d = loadVector("battle_states.json")
        d["cases"].list().map { it.obj() }.flatMap { c ->
            (listOf(c["initial"].obj()) + c["steps"].list().map { it.obj() }).map {
                codec.parseState(MiniJson.parse(it["canonical"] as String))
            }
        }
    }

    private fun Any?.rat(): Rational = list().let { Rational.of(it[0].big().toLong(), it[1].big().toLong()) }

    private fun rulesPack(p: Map<String, Any?>): RulesPack {
        fun table(k: String) = p[k].list().map { it.rat() }
        fun longs(k: String) = p[k].list().map { it.big().toLong() }
        return RulesPack(
            adBonusPerPoint = p["ad_bonus_per_point"].rat(), adBonusCap = p["ad_bonus_cap"].rat(),
            daPenaltyPerPoint = p["da_penalty_per_point"].rat(), daPenaltyCap = p["da_penalty_cap"].rat(),
            offense = table("offense"), archery = table("archery"), armorer = table("armorer"),
            hateBonus = p["hate_bonus"].rat(), luckBonus = p["luck_bonus"].rat(), half = p["half"].rat(),
            moraleDie = p["morale_die"].big().toLong(),
            badMoraleNumerators = longs("bad_morale_numerators"),
            vcmiBadMoraleNumerators = longs("vcmi_bad_morale_numerators"),
        )
    }
}
