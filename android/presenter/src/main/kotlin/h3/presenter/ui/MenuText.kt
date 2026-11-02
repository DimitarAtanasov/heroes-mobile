package h3.presenter.ui

/** Version line shown on Home and About. Placeholder art only (docs/specs/app-shell.md). */
const val APP_VERSION_TEXT = "Prototype 0.1 (placeholder art)"

/** Short user message for a preset error, or null when there is none. */
fun presetErrorText(error: PresetError?): String? = when (error) {
    null -> null
    PresetError.NoPresets -> "No skirmish is available."
    PresetError.OutOfRange -> "Choose one of the listed skirmishes."
}

/** Short user message for a seed error, or null when there is none. */
fun seedErrorText(error: SeedError?): String? = when (error) {
    null -> null
    SeedError.Empty -> "Enter a seed."
    SeedError.NotDigits -> "The seed may only contain the digits 0 to 9."
    SeedError.TooLarge -> "The seed is too large (the largest is 9223372036854775807)."
}

/** The one message the Setup screen shows for [form]: the preset's first, then the seed's; null when valid. */
fun setupFormMessage(form: SetupForm): String? = presetErrorText(form.presetError) ?: seedErrorText(form.seedError)
