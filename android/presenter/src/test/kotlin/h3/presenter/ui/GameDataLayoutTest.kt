package h3.presenter.ui

import java.io.ByteArrayOutputStream
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

// ---- synthetic fixtures; no game data. Names are prefixed gl to stay clear of other test files. ----

private fun glLe32(o: ByteArrayOutputStream, v: Int) { for (i in 0 until 4) o.write((v shr (8 * i)) and 0xFF) }

/** A tiny valid stored LOD with one member: enough for GameDataCheck on a sprite archive. */
private fun glLod(): ByteArray {
    val o = ByteArrayOutputStream()
    o.write(byteArrayOf('L'.code.toByte(), 'O'.code.toByte(), 'D'.code.toByte(), 0))
    glLe32(o, 200); glLe32(o, 1)
    o.write(ByteArray(80))
    val data = "x".toByteArray(Charsets.ISO_8859_1)
    o.write("A.DEF".toByteArray(Charsets.ISO_8859_1).copyOf(16))
    glLe32(o, 92 + 32); glLe32(o, data.size); glLe32(o, 0); glLe32(o, 0)
    o.write(data)
    return o.toByteArray()
}

private val GL_LOD = glLod()

/** What GameDataCheck says about [listing] when only the two sprite archives are required. */
private fun glCheckAccepts(listing: List<String>): Boolean {
    val files = listing.map { GameFile(it, GL_LOD.size.toLong()) }
    val r = GameDataCheck.check(files, { GL_LOD }, listOf("H3sprite.lod", "H3ab_spr.lod"))
    return r is GameDataResult.Ok
}

/** [sprite] and [abSpr] are the literal paths expected from the layout rule, or null for not found. */
private class GlFixture(
    val label: String,
    val listing: List<String>,
    val sprite: String?,
    val abSpr: String?,
    val checkAccepts: Boolean,
)

private fun glLayoutFindsAll(f: GlFixture): Boolean =
    GameDataLayout.resolveArchiveName(f.listing, "H3sprite.lod") != null &&
        GameDataLayout.resolveArchiveName(f.listing, "H3ab_spr.lod") != null

/** Layouts on which the layout rule and GameDataCheck agree (accepted by both or by neither). */
private val GL_AGREE = listOf(
    GlFixture("root layout", listOf("H3sprite.lod", "H3ab_spr.lod"), "H3sprite.lod", "H3ab_spr.lod", true),
    GlFixture("Data layout", listOf("Data/H3sprite.lod", "Data/H3ab_spr.lod"), "Data/H3sprite.lod", "Data/H3ab_spr.lod", true),
    GlFixture(
        "mixed case, root file and DATA folder",
        listOf("h3SPRITE.LOD", "DATA/h3ab_spr.LoD"),
        "h3SPRITE.LOD",
        "DATA/h3ab_spr.LoD",
        true,
    ),
    GlFixture(
        "both present, Data wins (any case of the folder)",
        listOf("H3sprite.lod", "Data/H3sprite.lod", "H3ab_spr.lod", "data/H3ab_spr.lod"),
        "Data/H3sprite.lod",
        "data/H3ab_spr.lod",
        true,
    ),
    GlFixture(
        "Data wins even when listed after the root",
        listOf("Data/H3ab_spr.lod", "H3ab_spr.lod", "Data/H3sprite.lod", "H3sprite.lod"),
        "Data/H3sprite.lod",
        "Data/H3ab_spr.lod",
        true,
    ),
    GlFixture(
        "Data holds one archive, the root the other",
        listOf("Data/H3sprite.lod", "H3ab_spr.lod"),
        "Data/H3sprite.lod",
        "H3ab_spr.lod",
        true,
    ),
    GlFixture(
        "nested under an install folder: not found",
        listOf("Install/Data/H3sprite.lod", "Install/Data/H3ab_spr.lod"),
        null,
        null,
        false,
    ),
    GlFixture("one folder too deep under Data: not found", listOf("Data/Sub/H3sprite.lod", "Data/Sub/H3ab_spr.lod"), null, null, false),
    GlFixture("one folder under the root: not found", listOf("Sub/H3sprite.lod", "Sub/H3ab_spr.lod"), null, null, false),
    GlFixture("only one archive present", listOf("Data/H3sprite.lod"), "Data/H3sprite.lod", null, false),
    GlFixture("neither present", emptyList(), null, null, false),
    GlFixture(
        "near names are not matches",
        listOf("Data/H3sprite.lod.bak", "H3ab_spr.lodx", "Data/xH3sprite.lod", "Data/H3sprite.lo"),
        null,
        null,
        false,
    ),
    GlFixture(
        "non-ASCII look-alikes are not matches (ASCII fold only)",
        listOf("Data/H3spr\u0131te.lod", "Data/H3ab_\u017Fpr.lod"),
        null,
        null,
        false,
    ),
    GlFixture(
        "a Data folder with a look-alike name is not Data",
        listOf("Data2/H3sprite.lod", "Dat/H3ab_spr.lod"),
        null,
        null,
        false,
    ),
)

/**
 * Layouts on which GameDataCheck is more lenient than the import rule. The importer (ImportPlan.select)
 * refuses these sources, and its copy names every file flat in the live folder, so the validated folder
 * never has them; the loader follows the import rule. Pinned so a change on either side is noticed.
 */
private val GL_DRIFT = listOf(
    GlFixture(
        "case-only duplicates in Data: ambiguous for the layout, first by code point for the check",
        listOf("Data/H3sprite.lod", "Data/h3sprite.lod", "Data/H3ab_spr.lod"),
        null,
        "Data/H3ab_spr.lod",
        true,
    ),
    GlFixture(
        "case-only duplicates at the root",
        listOf("H3sprite.lod", "H3SPRITE.LOD", "H3ab_spr.lod", "h3ab_spr.lod"),
        null,
        null,
        true,
    ),
    GlFixture(
        "the same path listed twice",
        listOf("Data/H3sprite.lod", "Data/H3sprite.lod", "Data/H3ab_spr.lod"),
        null,
        "Data/H3ab_spr.lod",
        true,
    ),
    GlFixture(
        "Data holds duplicates, so the root is not consulted",
        listOf("Data/H3sprite.lod", "Data/H3SPRITE.LOD", "H3sprite.lod", "Data/H3ab_spr.lod"),
        null,
        "Data/H3ab_spr.lod",
        true,
    ),
    GlFixture(
        "backslash paths: the check splits on them, the import does not",
        listOf("Data\\H3sprite.lod", "Data\\H3ab_spr.lod"),
        null,
        null,
        true,
    ),
    GlFixture(
        "backslash under an install folder",
        listOf("Install\\Data\\H3sprite.lod", "Install\\Data\\H3ab_spr.lod"),
        null,
        null,
        false,
    ),
    GlFixture(
        "dot segments: the check drops them, the import does not",
        listOf("./Data/H3sprite.lod", "./Data/H3ab_spr.lod"),
        null,
        null,
        true,
    ),
)

class GameDataLayoutTest {
    @Test
    fun spriteArchivesArePinnedAndRequiredByTheImport() {
        assertEquals(listOf("H3sprite.lod", "H3ab_spr.lod"), GameDataLayout.SPRITE_ARCHIVES)
        for (n in GameDataLayout.SPRITE_ARCHIVES) assertTrue(n in GameDataCheck.DEFAULT_REQUIRED, n)
    }

    @Test
    fun eachFixtureResolvesToTheLiteralPaths() {
        for (f in GL_AGREE + GL_DRIFT) {
            assertEquals(f.sprite, GameDataLayout.resolveArchiveName(f.listing, "H3sprite.lod"), f.label)
            assertEquals(f.abSpr, GameDataLayout.resolveArchiveName(f.listing, "H3ab_spr.lod"), f.label)
        }
    }

    @Test
    fun gameDataCheckVerdictsArePinnedWithLiterals() {
        for (f in GL_AGREE + GL_DRIFT) assertEquals(f.checkAccepts, glCheckAccepts(f.listing), f.label)
    }

    @Test
    fun checkAcceptsIffLayoutFindsEveryArchiveOnTheAgreeingLayouts() {
        for (f in GL_AGREE) assertEquals(glCheckAccepts(f.listing), glLayoutFindsAll(f), f.label)
        // Guard the table itself: both outcomes are present.
        assertTrue(GL_AGREE.any { glLayoutFindsAll(it) })
        assertTrue(GL_AGREE.any { !glLayoutFindsAll(it) })
    }

    @Test
    fun importAcceptedMeansTheLoaderFinds() {
        // The safe direction over every fixture: whenever the import rule accepts the two names, the layout finds both.
        for (f in GL_AGREE + GL_DRIFT) {
            val sel = ImportPlan.select(f.listing.map { ImportPlan.SourceEntry(it, 1L) }, GameDataLayout.SPRITE_ARCHIVES)
            if (sel is ImportPlan.Selection.Chosen) {
                assertEquals(listOf(f.sprite, f.abSpr), sel.files.map { it.sourcePath }, f.label)
                assertTrue(glLayoutFindsAll(f), f.label)
            } else {
                assertFalse(glLayoutFindsAll(f), f.label)
            }
        }
    }

    @Test
    fun layoutIsTheImportRuleNotACopy() {
        // Same answer as ImportPlan.select for each name on every fixture, including its ambiguity refusals.
        for (f in GL_AGREE + GL_DRIFT) {
            for (n in GameDataLayout.SPRITE_ARCHIVES) {
                val sel = ImportPlan.select(f.listing.map { ImportPlan.SourceEntry(it, 0L) }, listOf(n))
                val expected = (sel as? ImportPlan.Selection.Chosen)?.files?.get(0)?.sourcePath
                assertEquals(expected, GameDataLayout.resolveArchiveName(f.listing, n), f.label + " " + n)
            }
        }
    }

    @Test
    fun theSameCaseOnlyDuplicateIsAmbiguousForImportAndLayout() {
        val listing = listOf("Data/H3sprite.lod", "Data/h3sprite.lod")
        val sel = ImportPlan.select(listing.map { ImportPlan.SourceEntry(it, 1L) }, listOf("H3sprite.lod"))
        val amb = assertIs<ImportPlan.Selection.AmbiguousSource>(sel)
        assertEquals(listOf("Data/H3sprite.lod", "Data/h3sprite.lod"), amb.paths)
        assertNull(GameDataLayout.resolveArchiveName(listing, "H3sprite.lod"))
    }

    @Test
    fun dataWinsOverTheRootEvenForDifferentSpelling() {
        val listing = listOf("h3sprite.lod", "DATA/H3SPRITE.LOD")
        assertEquals("DATA/H3SPRITE.LOD", GameDataLayout.resolveArchiveName(listing, "H3sprite.lod"))
    }

    @Test
    fun rootIsUsedOnlyWhenDataHasNoMatch() {
        assertEquals("h3sprite.lod", GameDataLayout.resolveArchiveName(listOf("Data/other.lod", "h3sprite.lod"), "H3sprite.lod"))
    }

    @Test
    fun theResultKeepsTheListedSpelling() {
        assertEquals("DATA/h3ab_spr.LoD", GameDataLayout.resolveArchiveName(listOf("DATA/h3ab_spr.LoD"), "H3ab_spr.lod"))
    }

    @Test
    fun unsafeOrEmptyWantedNamesAreNotFound() {
        val listing = listOf("Data/H3sprite.lod", "Data/a", "")
        assertNull(GameDataLayout.resolveArchiveName(listing, ""))
        assertNull(GameDataLayout.resolveArchiveName(listing, "Data/H3sprite.lod"))
        assertNull(GameDataLayout.resolveArchiveName(listing, ".."))
        assertNull(GameDataLayout.resolveArchiveName(emptyList(), "H3sprite.lod"))
    }

    @Test
    fun resolveArchivesKeepsTheWantedOrderAndSkipsMissing() {
        val listing = listOf("Data/H3ab_spr.lod", "H3sprite.lod")
        assertEquals(
            listOf("H3sprite.lod", "Data/H3ab_spr.lod"),
            GameDataLayout.resolveArchives(listing, GameDataLayout.SPRITE_ARCHIVES),
        )
        assertEquals(listOf("Data/H3ab_spr.lod"), GameDataLayout.resolveArchives(listOf("Data/H3ab_spr.lod"), GameDataLayout.SPRITE_ARCHIVES))
        assertEquals(emptyList(), GameDataLayout.resolveArchives(listOf("x/H3sprite.lod"), GameDataLayout.SPRITE_ARCHIVES))
    }

    @Test
    fun theListingOrderDoesNotChangeTheResult() {
        val listing = listOf("h3sprite.lod", "Data/H3ab_spr.lod", "DATA/H3sprite.lod", "H3AB_SPR.LOD")
        val a = GameDataLayout.resolveArchives(listing, GameDataLayout.SPRITE_ARCHIVES)
        val b = GameDataLayout.resolveArchives(listing.reversed(), GameDataLayout.SPRITE_ARCHIVES)
        assertEquals(listOf("DATA/H3sprite.lod", "Data/H3ab_spr.lod"), a)
        assertEquals(a, b)
    }
}
