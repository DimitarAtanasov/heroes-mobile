package h3.presenter.ui

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SpriteReloadTest {
    @Test
    fun validResultNeedsReload() {
        assertTrue(SpriteReload.needed(ImportResult.Valid(listOf(CheckedFile("a.lod", 1L)))))
        assertTrue(SpriteReload.needed(ImportResult.Valid(emptyList())))
    }

    @Test
    fun failuresDoNotReload() {
        assertFalse(SpriteReload.needed(ImportResult.Invalid(emptyList())))
        assertFalse(SpriteReload.needed(ImportResult.NotEnoughSpace(10L, 5L)))
        assertFalse(SpriteReload.needed(ImportResult.SourceChanged("a.lod")))
        assertFalse(SpriteReload.needed(ImportResult.IoFailed(IoStage.Scan, null)))
    }
}
