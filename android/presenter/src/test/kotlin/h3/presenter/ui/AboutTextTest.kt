package h3.presenter.ui

import kotlin.test.Test
import kotlin.test.assertTrue

/** Pins the legal phrases the About screen must keep (project laws 1 and 9). */
class AboutTextTest {
    @Test
    fun licenseNoticeNamesTheGplAndDisclaimsWarranty() {
        assertTrue("GPL-2.0-or-later" in AboutText.LICENSE_NOTICE)
        assertTrue("GNU General Public License" in AboutText.LICENSE_NOTICE)
        assertTrue("WITHOUT ANY WARRANTY" in AboutText.LICENSE_NOTICE)
    }

    @Test
    fun statesNotAffiliated() {
        assertTrue("not affiliated" in AboutText.AFFILIATION_NOTICE)
        assertTrue("independent, clean-room" in AboutText.AFFILIATION_NOTICE)
    }

    @Test
    fun statesNoGameAssetsBundled() {
        assertTrue("No game assets are bundled" in AboutText.ASSETS_NOTICE)
        assertTrue("placeholder" in AboutText.ASSETS_NOTICE)
    }
}
