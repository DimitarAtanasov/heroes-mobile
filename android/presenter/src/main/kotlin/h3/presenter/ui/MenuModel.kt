package h3.presenter.ui

/** The five screens of the app shell (docs/specs/app-shell.md). */
enum class MenuRoute { Home, Setup, Battle, Result, About }

/**
 * Pure navigation state: a back stack of [MenuRoute] plus whether an autosave exists (which is what
 * enables "Continue"). Immutable; every transition returns a model and never throws. An illegal
 * [forward] returns the same instance, and [back] at the root does too.
 *
 * The stack is always `[Home]` or `[Home, X]`. Legal [forward] edges:
 *  - Home -> Setup, About; Home -> Battle only while [autosaveExists] (Continue)
 *  - Setup -> Battle; Battle -> Result; Result -> Setup (play again)
 * From Home a forward pushes; from any other screen it replaces the top, so [back] from Setup,
 * About, Battle (quit) and Result always lands on Home and a finished battle is never re-entered.
 * Pure JVM, no state outside the instance.
 */
class MenuModel private constructor(
    private val routes: List<MenuRoute>,
    val autosaveExists: Boolean,
) {
    /** Bottom first; the last element is [current]. A read-only copy. */
    val stack: List<MenuRoute> get() = routes.toList()

    val current: MenuRoute get() = routes[routes.size - 1]

    val canGoBack: Boolean get() = routes.size > 1

    /** The Home "Continue" button is enabled exactly when an autosave exists. */
    val continueEnabled: Boolean get() = autosaveExists

    fun canForward(to: MenuRoute): Boolean = menuEdgeAllowed(current, to, autosaveExists)

    fun forward(to: MenuRoute): MenuModel {
        if (!canForward(to)) return this
        val kept = if (current == MenuRoute.Home) routes else routes.subList(0, routes.size - 1)
        return MenuModel(kept + to, autosaveExists)
    }

    fun back(): MenuModel =
        if (!canGoBack) this else MenuModel(routes.subList(0, routes.size - 1), autosaveExists)

    fun withAutosave(exists: Boolean): MenuModel =
        if (exists == autosaveExists) this else MenuModel(routes, exists)

    override fun equals(other: Any?): Boolean =
        other is MenuModel && other.routes == routes && other.autosaveExists == autosaveExists

    override fun hashCode(): Int = 31 * routes.hashCode() + (if (autosaveExists) 1 else 0)

    override fun toString(): String = "MenuModel($routes, autosave=$autosaveExists)"

    companion object {
        fun initial(autosaveExists: Boolean = false): MenuModel =
            MenuModel(listOf(MenuRoute.Home), autosaveExists)
    }
}

private fun menuEdgeAllowed(from: MenuRoute, to: MenuRoute, autosaveExists: Boolean): Boolean =
    when (from) {
        MenuRoute.Home -> when (to) {
            MenuRoute.Setup, MenuRoute.About -> true
            MenuRoute.Battle -> autosaveExists
            MenuRoute.Home, MenuRoute.Result -> false
        }
        MenuRoute.Setup -> to == MenuRoute.Battle
        MenuRoute.Battle -> to == MenuRoute.Result
        MenuRoute.Result -> to == MenuRoute.Setup
        MenuRoute.About -> false
    }
