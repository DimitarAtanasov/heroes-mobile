package h3.presenter.ui

/** Error of the preset field. [code] is stable, for the UI to map to text. */
enum class PresetError(val code: String) {
    /** There is no preset to choose from (`presetCount <= 0`). */
    NoPresets("preset.none"),

    /** The index is not in `0 until presetCount`. */
    OutOfRange("preset.out_of_range"),

    /** The chosen preset needs a creature the player's roster cannot field; see [SetupForm.presetBlock]. */
    Unavailable("preset.unavailable"),
}

/** Why a preset cannot start with the player's roster. [row] is the CRTRAITS data-row index the preset names. */
sealed class PresetBlock {
    abstract val row: Int

    /** No roster entry has [row] (past the end of the file, or a no-fixed-damage creature left out). */
    data class MissingRow(override val row: Int) : PresetBlock()

    /** The creature of [row] has 0 hit points; battle creation refuses it (owner decision Q5). */
    data class ZeroHp(override val row: Int) : PresetBlock()
}

/**
 * Whether a preset, which names its creatures by CRTRAITS data-row index (owner decision Q7), can start
 * with the player's roster. Pure; nothing is substituted for a missing row.
 */
object PresetCheck {
    /** The first of [rows] (in their order) that no entry of [roster] has, or null when all are there. */
    fun missingRow(rows: List<Int>, roster: List<GameRosterEntry>): Int? {
        val have = roster.mapTo(LinkedHashSet()) { it.row }
        return rows.firstOrNull { it !in have }
    }

    /** The first problem of [rows] in their order (a missing row, or a creature with 0 hit points), or null. */
    fun check(rows: List<Int>, roster: List<GameRosterEntry>): PresetBlock? {
        val byRow = roster.associateBy { it.row }
        for (row in rows) {
            val e = byRow[row] ?: return PresetBlock.MissingRow(row)
            if (e.creature.hp <= 0) return PresetBlock.ZeroHp(row)
        }
        return null
    }
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
 * Pure state of the Setup screen: which preset, the seed as typed, and per preset index the reason it
 * cannot start ([blocks]; null or a missing entry means it can). Immutable. Nothing here
 * throws: bad input is kept as typed and reported through [presetError] / [seedError], one code per
 * field. [seedText] is never trimmed or normalised. Leading zeros are fine ("0007" is 7).
 * Integer-only; the seed is parsed digit by digit with an overflow guard.
 */
data class SetupForm(
    val presetCount: Int,
    val presetIndex: Int = 0,
    val seedText: String = DEFAULT_SEED,
    val blocks: List<PresetBlock?> = emptyList(),
) {
    fun selectPreset(index: Int): SetupForm = copy(presetIndex = index)

    /** The same form with new per-preset blocks (for example after the roster changed). */
    fun withBlocks(newBlocks: List<PresetBlock?>): SetupForm = copy(blocks = newBlocks)

    /** Why the chosen preset cannot start, or null (also null while the index is out of range). */
    val presetBlock: PresetBlock?
        get() = if (presetIndex in 0 until presetCount) blocks.getOrNull(presetIndex) else null

    fun withSeedText(text: String): SetupForm = copy(seedText = text)

    val presetError: PresetError?
        get() = when {
            presetCount <= 0 -> PresetError.NoPresets
            presetIndex < 0 || presetIndex >= presetCount -> PresetError.OutOfRange
            presetBlock != null -> PresetError.Unavailable
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
