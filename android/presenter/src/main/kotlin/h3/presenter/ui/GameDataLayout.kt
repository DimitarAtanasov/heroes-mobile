package h3.presenter.ui

/**
 * Where a game-data archive lives inside a folder, as one pure rule shared by the importer and the
 * sprite loader (android-app.md 3.2 and 4.3). There is no second implementation: [resolveArchiveName]
 * calls [ImportPlan.select], so what the import accepts is what the loader finds. That rule: the file
 * is `Data/<name>` (first segment `Data` in any case) or, if none, `<name>` at the root; names compare
 * with an ASCII case fold; `Data/` wins over the root; two matches in the winning place (for example
 * `H3sprite.lod` and `h3sprite.lod`) are ambiguous and count as not found; deeper folders are not
 * searched; only `/` separates folders (a `\` stays part of a name).
 *
 * No file I/O: the app lists the folder as relative paths and carries the result out.
 */
object GameDataLayout {
    /** The sprite archives the board loader reads, in search order. Both are subsets of [GameDataCheck.DEFAULT_REQUIRED]. */
    val SPRITE_ARCHIVES: List<String> = listOf("H3sprite.lod", "H3ab_spr.lod")

    /**
     * The path from [listing] (relative, `/` separated, any order) that is the archive [wanted], exactly
     * as listed, or null when there is none, when it is ambiguous, or when [wanted] is not a safe file name.
     */
    fun resolveArchiveName(listing: List<String>, wanted: String): String? {
        val entries = listing.map { ImportPlan.SourceEntry(it, 0L) }
        val chosen = ImportPlan.select(entries, listOf(wanted)) as? ImportPlan.Selection.Chosen ?: return null
        return chosen.files[0].sourcePath
    }

    /** The paths found for [wanted], in the order of [wanted]; a name that is not found is left out. */
    fun resolveArchives(listing: List<String>, wanted: List<String>): List<String> =
        wanted.mapNotNull { resolveArchiveName(listing, it) }
}
