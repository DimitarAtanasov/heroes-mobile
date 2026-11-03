package h3.presenter.ui

import h3.sim.BattleCreature
import h3.sim.Content
import h3.sim.ContentError
import h3.sim.Creature
import h3.sim.CreatureMapping
import h3.sim.DatapackError
import h3.sim.LodArchive
import h3.sim.LodError
import h3.sim.PackJson

/** One creature of the battle roster and its CRTRAITS data-row index (the sprite key; roster-from-crtraits.md). */
data class GameRosterEntry(val row: Int, val creature: BattleCreature)

/** The outcome of [GameRoster.load]: the roster, or one sentence saying why the file was refused. */
sealed class GameRosterResult {
    /** The battle roster in file order (data-row index ascending), without the no-fixed-damage creatures. */
    data class Ok(val entries: List<GameRosterEntry>) : GameRosterResult()

    /** [text] names the archive, member, row, column and error category only, never file contents. */
    data class Refused(val text: String) : GameRosterResult()
}

/**
 * The battle roster from the player's own `CRTRAITS.TXT` inside `H3bitmap.lod` (roster-from-crtraits.md,
 * slice 4; ADR-0011 D3 amended 2026-11-03). Pure: the caller reads the archive and the mapping text
 * (`data/txt_maps/crtraits.json`) and passes them in; nothing here touches a file, a clock or a thread.
 *
 * Reading is [LodArchive], [Content.parseCreatures] and [Content.battleRoster]. A bad row refuses the
 * whole file (owner decision Q1): the data-row index is positional, so a partial roster would shift
 * every later index. Creatures with no fixed damage (0/0) are left out; weak ones (dmg_min 0) and hp 0
 * are kept (Q5). The returned text never holds a cell value or a creature name (the loader's own
 * messages can; they are not used).
 */
object GameRoster {
    /** Shown when the archive could not be read from disk at all (the app's I/O failed, not the parse). */
    const val READ_FAILED_TEXT = "Your game's ${GameDataCheck.BITMAP_ARCHIVE} could not be read."

    fun load(bitmapLod: ByteArray, mappingJson: String): GameRosterResult {
        val mapping = try {
            CreatureMapping.fromTree(PackJson.parse(mappingJson, "crtraits.json"))
        } catch (e: ContentError) {
            return GameRosterResult.Refused("The creature table mapping of this build is broken.")
        } catch (e: DatapackError) {
            return GameRosterResult.Refused("The creature table mapping of this build is broken.")
        }
        val archive = try {
            LodArchive.open(bitmapLod)
        } catch (e: LodError) {
            return GameRosterResult.Refused("Your game's ${GameDataCheck.BITMAP_ARCHIVE} is not a readable archive.")
        }
        val member = GameDataCheck.CRTRAITS_MEMBER
        if (member !in archive) {
            return GameRosterResult.Refused("Your game's ${GameDataCheck.BITMAP_ARCHIVE} has no $member.")
        }
        val bytes = try {
            archive.read(member)
        } catch (e: LodError) {
            return GameRosterResult.Refused("$member in your game's ${GameDataCheck.BITMAP_ARCHIVE} could not be unpacked.")
        }
        val content = try {
            Content.parseCreatures(bytes, mapping)
        } catch (e: ContentError) {
            return GameRosterResult.Refused(refusedText(e))
        }
        val entries = Content.battleRoster(content).map { c ->
            GameRosterEntry(content.creatureRows.getValue(c.name), toBattleCreature(c))
        }
        return GameRosterResult.Ok(entries)
    }

    /** A loader record as a battle creature. The loader's ranges (content.md) all fit in Int; `hates` is empty. */
    fun toBattleCreature(c: Creature): BattleCreature = BattleCreature(
        name = c.name,
        attack = Math.toIntExact(c.attack),
        defense = Math.toIntExact(c.defense),
        dmgMin = Math.toIntExact(c.dmgMin),
        dmgMax = Math.toIntExact(c.dmgMax),
        hp = Math.toIntExact(c.hp),
        speed = Math.toIntExact(c.speed),
        shots = Math.toIntExact(c.shots),
        flyer = "flyer" in c.flags,
        doubleWide = "double_wide" in c.flags,
        noEnemyRetaliation = "no_enemy_retaliation" in c.flags,
        unlimitedRetaliation = "unlimited_retaliation" in c.flags,
        noMeleePenalty = "no_melee_penalty" in c.flags,
        noRangePenalty = "no_range_penalty" in c.flags,
        strikesTwice = "strikes_twice" in c.flags,
        shootsTwice = "shoots_twice" in c.flags,
        noMorale = "no_morale" in c.flags,
    )

    /** Row, column and category of [e]; its message is not used, because it can quote a cell or a name. */
    private fun refusedText(e: ContentError): String {
        val where = listOfNotNull(e.row?.let { "row $it" }, e.column?.let { "column '$it'" })
        val at = if (where.isEmpty()) "" else " at " + where.joinToString(", ")
        return "Your game's ${GameDataCheck.CRTRAITS_MEMBER} was refused$at: ${e.category.key}."
    }
}
