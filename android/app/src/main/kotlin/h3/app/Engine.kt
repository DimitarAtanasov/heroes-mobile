package h3.app

import h3.sim.Battle
import h3.sim.BattleAi
import h3.sim.BattleCodec
import h3.sim.BattlePolicyPack
import h3.sim.Datapack
import h3.sim.Rules

/**
 * The engine objects the app needs, built from the three bundled data packs. Same wiring as the
 * engine's own scenario loader (Scenario.kt, BattleEngine), on public API only. Pure JVM: no
 * Android imports, so it compiles and runs under :presenter's tests too.
 *
 * The packs include the fixture `creatures.json` only for the replay pack hashes: a replay header's
 * `creatures_hash` stays the hash of that fixture pack, so existing saves still load (owner decision
 * Q8, roster-from-crtraits.md). It is not the battle roster: that comes from the player's own
 * CRTRAITS.TXT (`GameRoster`; ADR-0011 D3, amended 2026-11-03).
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

    companion object {
        fun fromTexts(rulesJson: String, policyJson: String, creaturesJson: String): AppEngine =
            AppEngine(Datapack.load(rulesJson, policyJson, creaturesJson))
    }
}
