package h3.presenter.ui

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

// Cross-check: the import path (ImportPlan.select) and the sprite path (GameDataLayout.resolveArchives,
// which SpriteLoader.findLodFiles calls) must pick the same member for the same listing. Synthetic names only.
// The sprite loader lives in :app and cannot be called from this JVM module, so a second test reads its
// source and pins that it goes through the shared rule (see the SpriteLoader contract tests below).

private class XcScenario(val label: String, val listing: List<String>)

private val XC_SCENARIOS = listOf(
    XcScenario("root, mixed case", listOf("h3SPRITE.LOD", "H3AB_spr.Lod")),
    XcScenario("Data folder, mixed case", listOf("DATA/H3sprite.LOD", "data/h3ab_SPR.lod")),
    XcScenario("Data beats root", listOf("H3sprite.lod", "Data/h3sprite.LOD", "h3ab_spr.lod", "DATA/H3AB_SPR.LOD")),
    XcScenario("case-only duplicate (ambiguous)", listOf("Data/H3sprite.lod", "Data/h3sprite.lod", "Data/H3ab_spr.lod")),
    XcScenario("case-only duplicate at root", listOf("H3sprite.lod", "H3SPRITE.LOD", "H3ab_spr.lod")),
    XcScenario("a name not in the list", listOf("Data/H3sprite.lod", "Data/Other.lod")),
    XcScenario("one wanted name only", listOf("Data/H3ab_spr.lod", "Unrelated.txt")),
    XcScenario("too deep", listOf("Install/Data/H3sprite.lod", "Data/Sub/H3ab_spr.lod")),
    XcScenario("empty", emptyList()),
)

private fun xcImport(listing: List<String>, name: String): ImportPlan.Selection =
    ImportPlan.select(listing.map { ImportPlan.SourceEntry(it, 1L) }, listOf(name))

/** What the import path picks for [name] alone: the chosen member path, or null for any refusal. */
private fun xcImportPick(listing: List<String>, name: String): String? =
    (xcImport(listing, name) as? ImportPlan.Selection.Chosen)?.files?.single()?.sourcePath

class SpriteImportNameCrossCheckTest {
    @Test
    fun bothPathsPickTheSameMemberForEveryNameAndScenario() {
        val names = GameDataLayout.SPRITE_ARCHIVES + "H3unlisted.lod"
        for (s in XC_SCENARIOS) {
            for (n in names) {
                assertEquals(xcImportPick(s.listing, n), GameDataLayout.resolveArchiveName(s.listing, n), s.label + " / " + n)
            }
        }
    }

    @Test
    fun resolveArchivesEqualsTheImportPicksInWantedOrder() {
        for (s in XC_SCENARIOS) {
            val expected = GameDataLayout.SPRITE_ARCHIVES.mapNotNull { xcImportPick(s.listing, it) }
            assertEquals(expected, GameDataLayout.resolveArchives(s.listing, GameDataLayout.SPRITE_ARCHIVES), s.label)
        }
    }

    @Test
    fun wholeImportSelectionAgreesWithTheSpritePathWhenItSucceeds() {
        for (s in XC_SCENARIOS) {
            val sel = ImportPlan.select(s.listing.map { ImportPlan.SourceEntry(it, 1L) }, GameDataLayout.SPRITE_ARCHIVES)
            if (sel is ImportPlan.Selection.Chosen) {
                assertEquals(sel.files.map { it.sourcePath }, GameDataLayout.resolveArchives(s.listing, GameDataLayout.SPRITE_ARCHIVES), s.label)
            }
        }
    }

    @Test
    fun pinnedLiteralAnswersSoTheComparisonCannotBeVacuous() {
        val mixed = XC_SCENARIOS.first { it.label == "Data beats root" }.listing
        assertEquals(
            listOf("Data/h3sprite.LOD", "DATA/H3AB_SPR.LOD"),
            GameDataLayout.resolveArchives(mixed, GameDataLayout.SPRITE_ARCHIVES),
        )
        val dup = XC_SCENARIOS.first { it.label == "case-only duplicate (ambiguous)" }.listing
        assertIs<ImportPlan.Selection.AmbiguousSource>(xcImport(dup, "H3sprite.lod"))
        assertNull(GameDataLayout.resolveArchiveName(dup, "H3sprite.lod"))
        assertEquals("Data/H3ab_spr.lod", GameDataLayout.resolveArchiveName(dup, "H3ab_spr.lod"))
        assertIs<ImportPlan.Selection.MissingSource>(xcImport(dup, "H3unlisted.lod"))
        assertNull(GameDataLayout.resolveArchiveName(dup, "H3unlisted.lod"))
        // Both outcomes occur in the table, so "same" is not "always null".
        assertTrue(XC_SCENARIOS.any { xcImportPick(it.listing, "H3sprite.lod") != null })
        assertTrue(XC_SCENARIOS.any { xcImportPick(it.listing, "H3sprite.lod") == null })
    }

    // ---- SpriteLoader contract (source reading; fails, never skips, when the file cannot be found) ----

    private fun spriteLoaderSource(): String {
        var dir: File? = File(System.getProperty("user.dir")).absoluteFile
        while (dir != null) {
            val f = File(dir, "android/app/src/main/kotlin/h3/app/SpriteLoader.kt")
            if (f.isFile) return f.readText()
            val g = File(dir, "app/src/main/kotlin/h3/app/SpriteLoader.kt")
            if (g.isFile) return g.readText()
            dir = dir.parentFile
        }
        throw AssertionError("SpriteLoader.kt not found above " + System.getProperty("user.dir"))
    }

    private fun code(src: String): String =
        src.lines().filterNot { val t = it.trim(); t.startsWith("*") || t.startsWith("/*") || t.startsWith("//") }.joinToString("\n")

    @Test
    fun spriteLoaderUsesTheSharedArchiveListAndResolver() {
        val src = code(spriteLoaderSource())
        assertTrue(Regex("""val\s+LOD_NAMES\s*=\s*GameDataLayout\.SPRITE_ARCHIVES\b""").containsMatchIn(src), "LOD_NAMES must be SPRITE_ARCHIVES")
        assertTrue(Regex("""GameDataLayout\.resolveArchives\(\s*relativePaths\(\s*\w+\s*\)\s*,\s*LOD_NAMES\s*\)""").containsMatchIn(src), "findLodFiles must call the shared resolver")
        assertNotNull(Regex("""fun\s+findLodFiles""").find(src))
    }

    @Test
    fun spriteLoaderHasNoOwnNameComparison() {
        val src = code(spriteLoaderSource())
        for (banned in listOf("equals(", "ignoreCase", "lowercase", "uppercase", "toLowerCase", "toUpperCase", "endsWith", "startsWith")) {
            assertTrue(!src.contains(banned), "SpriteLoader compares names itself: " + banned)
        }
    }
}
