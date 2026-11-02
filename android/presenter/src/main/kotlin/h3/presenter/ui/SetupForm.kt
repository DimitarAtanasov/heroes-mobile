package h3.presenter.ui

/** Error of the preset field. [code] is stable, for the UI to map to text. */
enum class PresetError(val code: String) {
    /** There is no preset to choose from (`presetCount <= 0`). */
    NoPresets("preset.none"),

    /** The index is not in `0 until presetCount`. */
    OutOfRange("preset.out_of_range"),
}

/** Error of the seed field. At most one is reported; the first that applies, in this order. */
enum class SeedError(val code: String) {
    /** The text is empty. */
    Empty("seed.empty"),

    /** Some character is not an ASCII digit `0`..`9` (no sign, space, separator or other script). */
    NotDigits("seed.not_digits"),

    /** All digits, but the value is above 2^63-1. */
    TooLarge("seed.too_large"),
}

/** A valid form, ready to start: the preset index and the seed (0..2^63-1). */
data class StartRequest(val presetIndex: Int, val seed: Long)

/**
 * Pure state of the Setup screen: which preset and the seed as typed. Immutable. Nothing here
 * throws: bad input is kept as typed and reported through [presetError] / [seedError], one code per
 * field. [seedText] is never trimmed or normalised. Leading zeros are fine ("0007" is 7).
 * Integer-only; the seed is parsed digit by digit with an overflow guard.
 */
data class SetupForm(
    val presetCount: Int,
    val presetIndex: Int = 0,
    val seedText: String = DEFAULT_SEED,
) {
    fun selectPreset(index: Int): SetupForm = copy(presetIndex = index)

    fun withSeedText(text: String): SetupForm = copy(seedText = text)

    val presetError: PresetError?
        get() = when {
            presetCount <= 0 -> PresetError.NoPresets
            presetIndex < 0 || presetIndex >= presetCount -> PresetError.OutOfRange
            else -> null
        }

    val seedError: SeedError? get() = setupSeedParse(seedText).second

    /** The parsed seed, or null while [seedError] is set. */
    val seedValue: Long? get() = setupSeedParse(seedText).first

    val isValid: Boolean get() = presetError == null && seedError == null

    /** What Start should use, or null while any field has an error. */
    fun start(): StartRequest? {
        val seed = seedValue
        return if (presetError == null && seed != null) StartRequest(presetIndex, seed) else null
    }

    companion object {
        const val DEFAULT_SEED = "1"
    }
}

/** Value xor error for a seed text. Never throws; no overflow: the accumulator stays <= Long.MAX_VALUE. */
private fun setupSeedParse(text: String): Pair<Long?, SeedError?> {
    if (text.isEmpty()) return Pair(null, SeedError.Empty)
    for (ch in text) {
        if (ch < '0' || ch > '9') return Pair(null, SeedError.NotDigits)
    }
    var acc = 0L
    for (ch in text) {
        val d = ch - '0'
        // acc * 10 + d <= MAX  <=>  acc <= (MAX - d) / 10  (both sides are non-negative)
        if (acc > (Long.MAX_VALUE - d) / 10L) return Pair(null, SeedError.TooLarge)
        acc = acc * 10L + d
    }
    return Pair(acc, null)
}
