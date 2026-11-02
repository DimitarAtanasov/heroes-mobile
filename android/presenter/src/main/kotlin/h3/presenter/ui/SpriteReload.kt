package h3.presenter.ui

/** Decides when the board sprites must be loaded again after the player's game data changed. */
object SpriteReload {
    /** True only when [result] left a complete, validated game data set in place ([ImportResult.Valid]). */
    fun needed(result: ImportResult): Boolean = result is ImportResult.Valid
}
