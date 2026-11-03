package h3.presenter.ui

import h3.sim.BattleCreature
import java.math.BigInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class SetupFormTest {
    private val form = SetupForm(presetCount = 3)

    private fun seedErr(text: String) = form.withSeedText(text).seedError
    private fun seedVal(text: String) = form.withSeedText(text).seedValue

    @Test
    fun defaultsAreFirstPresetAndSeedOne() {
        assertEquals(0, form.presetIndex)
        assertEquals("1", form.seedText)
        assertNull(form.presetError)
        assertNull(form.seedError)
        assertTrue(form.isValid)
        assertEquals(StartRequest(0, 1L), form.start())
    }

    @Test
    fun selectPresetChangesOnlyThePreset() {
        val f = form.withSeedText("77").selectPreset(2)
        assertEquals(2, f.presetIndex)
        assertEquals("77", f.seedText)
        assertEquals(StartRequest(2, 77L), f.start())
    }

    @Test
    fun presetRange() {
        for (i in 0..2) assertNull(form.selectPreset(i).presetError, "index $i")
        for (i in listOf(-1, 3, 4, Int.MIN_VALUE, Int.MAX_VALUE)) {
            val f = form.selectPreset(i)
            assertEquals(PresetError.OutOfRange, f.presetError, "index $i")
            assertEquals(i, f.presetIndex)
            assertNull(f.start())
            assertTrue(!f.isValid)
        }
    }

    @Test
    fun noPresetsMeansNoPresetsError() {
        for (n in listOf(0, -1, Int.MIN_VALUE)) {
            val f = SetupForm(presetCount = n)
            assertEquals(PresetError.NoPresets, f.presetError, "count $n")
            assertNull(f.start())
        }
        assertEquals(PresetError.NoPresets, SetupForm(0, presetIndex = 5).presetError)
    }

    @Test
    fun lastPresetOfALongerList() {
        val f = SetupForm(presetCount = Int.MAX_VALUE, presetIndex = Int.MAX_VALUE - 1)
        assertNull(f.presetError)
        assertEquals(PresetError.OutOfRange, f.selectPreset(Int.MAX_VALUE).presetError)
    }

    @Test
    fun emptySeed() {
        assertEquals(SeedError.Empty, seedErr(""))
        assertNull(seedVal(""))
    }

    @Test
    fun notDigits() {
        val bad = listOf(
            "abc", "12a", "a12", "1 2", " 1", "1 ", "-1", "+1", "1.5", "1e3", "0x10", "1_000", "1,000",
            "\n", "1\n", "١٢٣", "１２", "²", "\u0000", "😀",
        )
        for (t in bad) {
            assertEquals(SeedError.NotDigits, seedErr(t), "text '${t.replace("\n", "\\n")}'")
            assertNull(seedVal(t))
        }
    }

    @Test
    fun acceptedValues() {
        assertEquals(0L, seedVal("0"))
        assertEquals(1L, seedVal("1"))
        assertEquals(7L, seedVal("0007"))
        assertEquals(0L, seedVal("0".repeat(5000)))
        assertEquals(5L, seedVal("0".repeat(5000) + "5"))
        assertEquals(4294967296L, seedVal("4294967296"))
        assertEquals(Long.MAX_VALUE - 1, seedVal("9223372036854775806"))
        assertEquals(Long.MAX_VALUE, seedVal("9223372036854775807"))
        assertEquals(Long.MAX_VALUE, seedVal("0000" + "9223372036854775807"))
        assertEquals(1_000_000_000_000_000_000L, seedVal("1000000000000000000"))
    }

    @Test
    fun tooLarge() {
        val big = listOf(
            "9223372036854775808", "9223372036854775810", "9223372036854775817", "9300000000000000000",
            "10000000000000000000", "18446744073709551615", "18446744073709551616",
            "99999999999999999999", "1" + "0".repeat(10000),
        )
        for (t in big) {
            assertEquals(SeedError.TooLarge, seedErr(t), "text ${t.take(30)}")
            assertNull(seedVal(t))
        }
    }

    @Test
    fun oneCodePerFieldAndNotDigitsBeatsTooLarge() {
        assertEquals(SeedError.NotDigits, seedErr("99999999999999999999x"))
        assertEquals(SeedError.NotDigits, seedErr("x99999999999999999999"))
    }

    @Test
    fun bothFieldsReportedIndependently() {
        val f = form.selectPreset(9).withSeedText("zz")
        assertEquals(PresetError.OutOfRange, f.presetError)
        assertEquals(SeedError.NotDigits, f.seedError)
        assertNull(f.start())
        assertNull(f.selectPreset(1).presetError)
        assertEquals(SeedError.NotDigits, f.selectPreset(1).seedError)
        assertNull(f.withSeedText("5").seedError)
        assertEquals(PresetError.OutOfRange, f.withSeedText("5").presetError)
    }

    @Test
    fun errorCodesAreStableAndDistinct() {
        assertEquals(listOf("seed.empty", "seed.not_digits", "seed.too_large"), SeedError.values().map { it.code })
        assertEquals(listOf("preset.none", "preset.out_of_range", "preset.unavailable"), PresetError.values().map { it.code })
    }

    @Test
    fun fuzzAgainstBigIntegerOracle() {
        val alphabet = "0123456789-+ .e١"
        var seed = 2024L
        fun next(n: Int): Int {
            seed = seed * 6364136223846793005L + 1442695040888963407L
            return Math.floorMod(seed ushr 33, n.toLong()).toInt()
        }
        val limit = BigInteger.valueOf(Long.MAX_VALUE)
        repeat(20000) {
            val len = next(24)
            val digitsOnly = next(3) != 0
            val sb = StringBuilder()
            repeat(len) {
                sb.append(if (digitsOnly) alphabet[next(10)] else alphabet[next(alphabet.length)])
            }
            val text = sb.toString()
            val f = form.withSeedText(text)
            val ascii = text.all { it in '0'..'9' }
            when {
                text.isEmpty() -> assertEquals(SeedError.Empty, f.seedError, text)
                !ascii -> assertEquals(SeedError.NotDigits, f.seedError, text)
                BigInteger(text) > limit -> assertEquals(SeedError.TooLarge, f.seedError, text)
                else -> {
                    assertNull(f.seedError, text)
                    assertEquals(BigInteger(text).toLong(), f.seedValue, text)
                }
            }
            assertEquals(f.seedError == null, f.seedValue != null)
        }
    }

    // ---- presets by CRTRAITS row (roster-from-crtraits.md, Q7) ----

    private fun entry(row: Int, hp: Int = 10) =
        RosterEntry(row, BattleCreature("Row$row", attack = 1, defense = 1, dmgMin = 1, dmgMax = 2, hp = hp, speed = 4))

    private val roster = listOf(entry(0), entry(2), entry(3, hp = 0), entry(4))

    @Test
    fun missingRowIsTheFirstAbsentRowInPresetOrder() {
        assertNull(PresetCheck.missingRow(listOf(0, 2, 4), roster))
        assertEquals(1, PresetCheck.missingRow(listOf(0, 1, 5), roster))
        assertEquals(5, PresetCheck.missingRow(listOf(5, 1), roster))
        assertEquals(0, PresetCheck.missingRow(listOf(0), emptyList()))
        assertNull(PresetCheck.missingRow(emptyList(), emptyList()))
    }

    @Test
    fun checkReportsMissingRowsAndZeroHpInPresetOrder() {
        assertNull(PresetCheck.check(listOf(0, 2, 4), roster))
        assertEquals(PresetBlock.MissingRow(1), PresetCheck.check(listOf(0, 1), roster))
        assertEquals(PresetBlock.ZeroHp(3), PresetCheck.check(listOf(0, 3, 1), roster))
        assertEquals(PresetBlock.MissingRow(1), PresetCheck.check(listOf(1, 3), roster))
    }

    @Test
    fun aBlockedPresetDisablesStart() {
        val blocks = listOf(null, PresetBlock.MissingRow(4), null)
        val f = SetupForm(presetCount = 3, blocks = blocks)
        assertNull(f.presetError)
        assertEquals(StartRequest(0, 1L), f.start())
        val b = f.selectPreset(1)
        assertEquals(PresetError.Unavailable, b.presetError)
        assertEquals(PresetBlock.MissingRow(4), b.presetBlock)
        assertNull(b.start())
        assertTrue(!b.isValid)
        assertEquals(StartRequest(2, 1L), b.selectPreset(2).start())
    }

    @Test
    fun rangeErrorsWinOverBlocksAndShortBlockListsMeanEnabled() {
        val f = SetupForm(presetCount = 2, blocks = listOf(PresetBlock.ZeroHp(0)))
        assertEquals(PresetError.OutOfRange, f.selectPreset(5).presetError)
        assertNull(f.selectPreset(5).presetBlock)
        assertNull(f.selectPreset(1).presetError) // no entry for index 1: enabled
        assertEquals(PresetError.Unavailable, f.presetError)
    }

    @Test
    fun withBlocksKeepsTheSelectionAndTheSeed() {
        val f = form.selectPreset(2).withSeedText("9").withBlocks(listOf(null, null, PresetBlock.MissingRow(7)))
        assertEquals(2, f.presetIndex)
        assertEquals("9", f.seedText)
        assertEquals(PresetError.Unavailable, f.presetError)
        assertNull(f.withBlocks(emptyList()).presetError)
    }

    @Test
    fun withSeedTextKeepsTheRawText() {
        assertEquals("  12x ", form.withSeedText("  12x ").seedText)
    }
}
