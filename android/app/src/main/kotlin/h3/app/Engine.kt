package h3.app

import h3.sim.Battle
import h3.sim.BattleAi
import h3.sim.BattleCodec
import h3.sim.BattlePolicyPack
import h3.sim.BattleCreature
import h3.sim.Datapack
import h3.sim.Rules

/**
 * The engine objects the app needs, built from the three bundled data packs. Same wiring as the
 * engine's own scenario loader (Scenario.kt, BattleEngine), on public API only. Pure JVM: no
 * Android imports, so it compiles and runs under :presenter's tests too.
 */
class AppEngine(val packs: Datapack) {
    val battle: Battle = Battle(Rules(packs.rules.pack), packs.rules.contentHash)
    val codec: BattleCodec = BattleCodec(
        BattlePolicyPack(
            packs.policy.values,
            packs.rules.pack.badMoraleNumerators.map { Math.toIntExact(it) },
            Math.toIntExact(packs.rules.pack.moraleDie),
        ),
    )
    val ai: BattleAi = BattleAi(battle, codec)
    val roster: List<BattleCreature> get() = packs.creatures.creatures

    companion object {
        fun fromTexts(rulesJson: String, policyJson: String, creaturesJson: String): AppEngine =
            AppEngine(Datapack.load(rulesJson, policyJson, creaturesJson))
    }
}
