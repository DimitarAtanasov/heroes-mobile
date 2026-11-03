package h3.presenter.ui

/** The five screens of the app shell (docs/specs/app-shell.md). */
enum class MenuRoute { Home, Setup, Battle, Result, About }

/**
 * Pure navigation state: a back stack of [MenuRoute] plus whether an autosave exists (which is what
 * enables "Continue") and whether the player's battle roster is loaded ([rosterReady]; without it Home
 * shows only the import prompt, ADR-0011 D3 amended 2026-11-03). Immutable; every transition returns a model and never throws. An illegal
 * [forward] returns the same instance, and [back] at the root does too.
 *
 * The stack is always `[Home]` or `[Home, X]`. Legal [forward] edges:
 *  - Home -> About; Home -> Setup only while [rosterReady]; Home -> Battle only while [autosaveExists] (Continue)
 *  - Setup -> Battle; Battle -> Result; Result -> Setup (play again) only while [rosterReady]
 * From Home a forward pushes; from any other screen it replaces the top, so [back] from Setup,
 * About, Battle (quit) and Result always lands on Home and a finished battle is never re-entered.
 * Pure JVM, no state outside the instance.
 */
class MenuModel private constructor(
    private val routes: List<MenuRoute>,
    val autosaveExists: Boolean,
    val rosterReady: Boolean,
) {
    /** Bottom first; the last element is [current]. A read-only copy. */
    val stack: List<MenuRoute> get() = routes.toList()

    val current: MenuRoute get() = routes[routes.size - 1]

    val canGoBack: Boolean get() = routes.size > 1

    /** The Home "Continue" button is enabled exactly when an autosave exists. */
    val continueEnabled: Boolean get() = autosaveExists

    /** "New skirmish" is offered exactly when the roster is loaded. */
    val newEnabled: Boolean get() = rosterReady

    /** Home shows the import prompt in place of "New skirmish" exactly when there is no roster. */
    val importPromptShown: Boolean get() = !rosterReady

    fun canForward(to: MenuRoute): Boolean = menuEdgeAllowed(current, to, autosaveExists, rosterReady)

    fun forward(to: MenuRoute): MenuModel {
        if (!canForward(to)) return this
        val kept = if (current == MenuRoute.Home) routes else routes.subList(0, routes.size - 1)
        return MenuModel(kept + to, autosaveExists, rosterReady)
    }

    fun back(): MenuModel =
        if (!canGoBack) this else MenuModel(routes.subList(0, routes.size - 1), autosaveExists, rosterReady)

    fun withAutosave(exists: Boolean): MenuModel =
        if (exists == autosaveExists) this else MenuModel(routes, exists, rosterReady)

    fun withRoster(ready: Boolean): MenuModel =
        if (ready == rosterReady) this else MenuModel(routes, autosaveExists, ready)

    override fun equals(other: Any?): Boolean =
        other is MenuModel && other.routes == routes && other.autosaveExists == autosaveExists &&
            other.rosterReady == rosterReady

    override fun hashCode(): Int =
        (31 * routes.hashCode() + (if (autosaveExists) 1 else 0)) * 2 + (if (rosterReady) 1 else 0)

    override fun toString(): String = "MenuModel($routes, autosave=$autosaveExists, roster=$rosterReady)"

    companion object {
        fun initial(autosaveExists: Boolean = false, rosterReady: Boolean = true): MenuModel =
            MenuModel(listOf(MenuRoute.Home), autosaveExists, rosterReady)
    }
}

private fun menuEdgeAllowed(from: MenuRoute, to: MenuRoute, autosaveExists: Boolean, rosterReady: Boolean): Boolean =
    when (from) {
        MenuRoute.Home -> when (to) {
            MenuRoute.Setup -> rosterReady
            MenuRoute.About -> true
            MenuRoute.Battle -> autosaveExists
            MenuRoute.Home, MenuRoute.Result -> false
        }
        MenuRoute.Setup -> to == MenuRoute.Battle
        MenuRoute.Battle -> to == MenuRoute.Result
        MenuRoute.Result -> to == MenuRoute.Setup && rosterReady
        MenuRoute.About -> false
    }
