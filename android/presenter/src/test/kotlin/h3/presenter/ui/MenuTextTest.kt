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
