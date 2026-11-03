package h3.presenter.ui

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class MenuTextTest {
    @Test
    fun noErrorMeansNoText() {
        assertNull(presetErrorText(null))
        assertNull(seedErrorText(null))
        assertNull(setupFormMessage(SetupForm(presetCount = 3)))
    }

    @Test
    fun everyErrorHasItsOwnNonEmptyText() {
        val texts = PresetError.values().map { presetErrorText(it) } + SeedError.values().map { seedErrorText(it) }
        for (t in texts) assertTrue(!t.isNullOrBlank())
        assertEquals(texts.size, texts.toSet().size)
    }

    @Test
    fun seedMessagesFollowTheFormErrors() {
        val form = SetupForm(presetCount = 3)
        assertEquals(seedErrorText(SeedError.Empty), setupFormMessage(form.withSeedText("")))
        assertEquals(seedErrorText(SeedError.NotDigits), setupFormMessage(form.withSeedText("-5")))
        assertEquals(seedErrorText(SeedError.TooLarge), setupFormMessage(form.withSeedText("9223372036854775808")))
        assertNull(setupFormMessage(form.withSeedText("9223372036854775807")))
    }

    @Test
    fun presetMessageComesBeforeSeedMessage() {
        val bad = SetupForm(presetCount = 3, presetIndex = 5, seedText = "")
        assertEquals(presetErrorText(PresetError.OutOfRange), setupFormMessage(bad))
        assertEquals(presetErrorText(PresetError.NoPresets), setupFormMessage(SetupForm(presetCount = 0)))
    }

    @Test
    fun aBlockedPresetNamesItsRow() {
        assertEquals("Needs creature row 4, not in your game's creatures", presetBlockText(PresetBlock.MissingRow(4)))
        assertEquals("Needs creature row 0, not in your game's creatures", presetBlockText(PresetBlock.MissingRow(0)))
        val hp = presetBlockText(PresetBlock.ZeroHp(2))
        assertTrue("row 2" in hp && "0 hit points" in hp, hp)
        assertNull(presetBlockText(null))
    }

    @Test
    fun theFormMessageOfABlockedPresetIsItsBlockText() {
        val f = SetupForm(presetCount = 2, blocks = listOf(PresetBlock.MissingRow(4), null))
        assertEquals("Needs creature row 4, not in your game's creatures", setupFormMessage(f))
        assertNull(setupFormMessage(f.selectPreset(1)))
        // A blocked preset's message comes before a seed error.
        assertEquals(presetBlockText(PresetBlock.MissingRow(4)), setupFormMessage(f.withSeedText("")))
    }

    @Test
    fun theImportPromptIsNotEmpty() {
        assertTrue(IMPORT_PROMPT_TEXT.isNotBlank())
    }

    @Test
    fun messageIsNullExactlyWhenTheFormIsValid() {
        val form = SetupForm(presetCount = 2)
        for (seed in listOf("", "1", "abc", "0007", "99999999999999999999")) {
            for (idx in -1..2) {
                val f = form.selectPreset(idx).withSeedText(seed)
                assertEquals(f.isValid, setupFormMessage(f) == null)
            }
        }
        assertNotEquals("", APP_VERSION_TEXT)
    }
}
