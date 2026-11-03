package h3.presenter.ui

/** Version line shown on Home and About. Placeholder art only (docs/specs/app-shell.md). */
const val APP_VERSION_TEXT = "Prototype 0.1 (placeholder art)"

/** Short user message for a preset error, or null when there is none. */
fun presetErrorText(error: PresetError?): String? = when (error) {
    null -> null
    PresetError.NoPresets -> "No skirmish is available."
    PresetError.OutOfRange -> "Choose one of the listed skirmishes."
    PresetError.Unavailable -> "This skirmish needs a creature your game's creatures cannot provide."
}

/** Why a preset is disabled, naming its CRTRAITS row (never a creature name); null when it is not. */
fun presetBlockText(block: PresetBlock?): String? = when (block) {
    null -> null
    is PresetBlock.MissingRow -> "Needs creature row ${block.row}, not in your game's creatures"
    is PresetBlock.ZeroHp -> "Needs creature row ${block.row}, which has 0 hit points in your game's creatures"
}

/** Home, in place of "New skirmish", while no CRTRAITS.TXT has been imported (ADR-0011 D3, amended 2026-11-03). */
const val IMPORT_PROMPT_TEXT =
    "Import your game data to play. Battles use the creatures from your own game files; nothing is bundled."

/** Short user message for a seed error, or null when there is none. */
fun seedErrorText(error: SeedError?): String? = when (error) {
    null -> null
    SeedError.Empty -> "Enter a seed."
    SeedError.NotDigits -> "The seed may only contain the digits 0 to 9."
    SeedError.TooLarge -> "The seed is too large (the largest is 9223372036854775807)."
}

/**
 * The one message the Setup screen shows for [form]: the preset's first (a blocked preset names its row),
 * then the seed's; null when valid.
 */
fun setupFormMessage(form: SetupForm): String? =
    presetBlockText(form.presetBlock) ?: presetErrorText(form.presetError) ?: seedErrorText(form.seedError)
