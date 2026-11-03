package h3.presenter.ui

import h3.sim.BattleCreature
import java.io.ByteArrayOutputStream
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

// ---- synthetic fixtures only: a stored LOD archive and a CRTRAITS-style table built here, no game data ----

private fun ByteArrayOutputStream.le32(v: Int) { for (i in 0 until 4) write((v shr (8 * i)) and 0xFF) }

/** A stored (uncompressed) LOD archive holding [members]; same layout as the SpriteLoadPlanTest helper. */
private fun lod(vararg members: Pair<String, ByteArray>): ByteArray {
    val out = ByteArrayOutputStream()
    out.write(byteArrayOf('L'.code.toByte(), 'O'.code.toByte(), 'D'.code.toByte(), 0))
    out.le32(200); out.le32(members.size)
    out.write(ByteArray(80))
    var off = 92 + 32 * members.size
    for ((n, data) in members) {
        out.write(n.toByteArray(Charsets.ISO_8859_1).copyOf(16))
        out.le32(off); out.le32(data.size); out.le32(0); out.le32(0)
        off += data.size
    }
    for ((_, data) in members) out.write(data)
    return out.toByteArray()
}

/** A small mapping of our own (not the shipped one): name, plural, the battle numbers and the ability list. */
private val MAPPING = """
{"schema_version": 1, "header_rows": 2,
 "columns": [
  {"name": "singular", "kind": "str", "target": "name", "required": true},
  {"name": "plural", "kind": "str", "target": "extra:plural"},
  {"name": "hp", "kind": "int", "target": "hp", "required": true},
  {"name": "speed", "kind": "int", "target": "speed", "required": true},
  {"name": "attack", "kind": "int", "target": "attack", "required": true},
  {"name": "defense", "kind": "int", "target": "defense", "required": true},
  {"name": "dmg_min", "kind": "int", "target": "dmg_min", "required": true},
  {"name": "dmg_max", "kind": "int", "target": "dmg_max", "required": true},
  {"name": "shots", "kind": "int", "target": "shots"},
  {"name": "abilities", "kind": "str", "target": "abilities"}
 ],
 "ability_separator": ",",
 "ability_flags": {"flyer": "flyer", "double wide": "double_wide", "shoots twice": "shoots_twice", "shooter": null}}
"""

/** One data row: name, plural, hp, speed, attack, defense, dmg_min, dmg_max, shots, abilities. */
private fun row(name: String, hp: String = "10", dmgMin: Int = 1, dmgMax: Int = 3, shots: Int = 0, abil: String = ""): List<String> =
    listOf(name, name + "s", hp, "5", "4", "3", dmgMin.toString(), dmgMax.toString(), shots.toString(), abil)

/** CRTRAITS-style bytes: two header rows, then [rows]; tab separated, CR LF records. */
private fun table(vararg rows: List<String>): ByteArray {
    val head = listOf(listOf("Invented creature table"), listOf("Singular", "Plural", "Hit Points"))
    return (head + rows.toList()).joinToString("\r\n", postfix = "\r\n") { it.joinToString("\t") }
        .toByteArray(Charsets.ISO_8859_1)
}

private fun bitmapLod(vararg rows: List<String>): ByteArray = lod("CRTRAITS.TXT" to table(*rows))

class GameRosterTest {
    private fun ok(r: GameRosterResult): List<RosterEntry> = assertIs<GameRosterResult.Ok>(r).entries

    private fun refused(r: GameRosterResult): String = assertIs<GameRosterResult.Refused>(r).text

    @Test
    fun fileOrderNotNameOrderAndIndexEqualsTheDataRow() {
        val entries = ok(GameRoster.load(bitmapLod(row("Zork"), row("Abba"), row("Mump")), MAPPING))
        assertEquals(listOf("Zork", "Abba", "Mump"), entries.map { it.creature.name })
        assertEquals(listOf(0, 1, 2), entries.map { it.row })
    }

    @Test
    fun blankAndEmptyFirstCellRowsAreNotCounted() {
        val entries = ok(GameRoster.load(bitmapLod(row("Zork"), listOf(""), row("Abba"), listOf("", "x"), row("Mump")), MAPPING))
        assertEquals(listOf(0, 1, 2), entries.map { it.row })
        assertEquals(listOf("Zork", "Abba", "Mump"), entries.map { it.creature.name })
    }

    @Test
    fun noFixedDamageIsLeftOutAndLaterRowsKeepTheirIndex() {
        val entries = ok(
            GameRoster.load(
                bitmapLod(row("Norm", dmgMin = 2, dmgMax = 4), row("Nofix", dmgMin = 0, dmgMax = 0), row("Weak", dmgMin = 0, dmgMax = 3)),
                MAPPING,
            ),
        )
        assertEquals(listOf(0, 2), entries.map { it.row })
        assertEquals(listOf("Norm", "Weak"), entries.map { it.creature.name })
        assertEquals(0, entries[1].creature.dmgMin) // a weak creature is offered
    }

    @Test
    fun hpZeroIsOffered() {
        val entries = ok(GameRoster.load(bitmapLod(row("Ghost", hp = "0"), row("Norm")), MAPPING))
        assertEquals(listOf(0, 1), entries.map { it.row })
        assertEquals(0, entries[0].creature.hp)
    }

    @Test
    fun flagsStatsAndShotsAreConverted() {
        val entries = ok(
            GameRoster.load(
                bitmapLod(row("Wing", dmgMin = 2, dmgMax = 5, shots = 12, abil = "Flyer, Double  Wide,shoots twice, shooter")),
                MAPPING,
            ),
        )
        val expected = BattleCreature(
            name = "Wing", attack = 4, defense = 3, dmgMin = 2, dmgMax = 5, hp = 10, speed = 5, shots = 12,
            flyer = true, doubleWide = true, shootsTwice = true,
        )
        assertEquals(listOf(RosterEntry(0, expected)), entries)
        assertEquals(emptyList<String>(), entries[0].creature.hates)
    }

    @Test
    fun noAbilitiesMeansNoFlags() {
        val c = ok(GameRoster.load(bitmapLod(row("Plain")), MAPPING)).single().creature
        assertEquals(BattleCreature("Plain", attack = 4, defense = 3, dmgMin = 1, dmgMax = 3, hp = 10, speed = 5), c)
    }

    @Test
    fun aBadRowRefusesTheWholeImportAndNamesTheRowButNotTheCell() {
        // File rows: 1-2 header, 3 "Good", 4 the bad one (hp is not a number).
        val text = refused(GameRoster.load(bitmapLod(row("Good"), row("Bad", hp = "zq9"), row("Later")), MAPPING))
        assertTrue("row 4" in text, text)
        assertTrue("'hp'" in text, text)
        assertFalse("zq9" in text, text)
        assertFalse("Good" in text || "Bad" in text || "Later" in text, text)
    }

    @Test
    fun aDuplicateNameRefusesWithoutPrintingTheName() {
        val text = refused(GameRoster.load(bitmapLod(row("Secretname"), row("Secretname")), MAPPING))
        assertTrue("row 4" in text, text)
        assertFalse("Secretname" in text, text)
    }

    @Test
    fun missingMemberIsRefused() {
        val text = refused(GameRoster.load(lod("OTHER.TXT" to table(row("Zork"))), MAPPING))
        assertTrue("CRTRAITS.TXT" in text, text)
    }

    @Test
    fun memberNameIgnoresCase() {
        assertEquals(listOf(0), ok(GameRoster.load(lod("crtraits.txt" to table(row("Zork"))), MAPPING)).map { it.row })
    }

    @Test
    fun notALodArchiveIsRefused() {
        val text = refused(GameRoster.load("not an archive at all".toByteArray(Charsets.ISO_8859_1), MAPPING))
        assertTrue(GameDataCheck.BITMAP_ARCHIVE in text, text)
    }

    @Test
    fun headerOnlyIsRefused() {
        refused(GameRoster.load(bitmapLod(), MAPPING))
    }

    @Test
    fun aBrokenMappingIsRefused() {
        refused(GameRoster.load(bitmapLod(row("Zork")), "{\"schema_version\": 2}"))
        refused(GameRoster.load(bitmapLod(row("Zork")), "not json"))
    }

    @Test
    fun allCreaturesWithoutFixedDamageGiveAnEmptyRoster() {
        assertEquals(emptyList<RosterEntry>(), ok(GameRoster.load(bitmapLod(row("Nofix", dmgMin = 0, dmgMax = 0)), MAPPING)))
    }

    @Test
    fun sameInputSameRoster() {
        val bytes = bitmapLod(row("Zork"), row("Abba", shots = 4))
        assertEquals(GameRoster.load(bytes, MAPPING), GameRoster.load(bytes.copyOf(), MAPPING))
    }
}
