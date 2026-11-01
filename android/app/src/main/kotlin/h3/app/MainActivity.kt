package h3.app

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import h3.sim.Scenario
import java.math.BigInteger

enum class Screen { Home, Setup, Battle, Result, About }

/**
 * Single activity, state-based navigation (no navigation library). The activity handles its own
 * configuration changes (see the manifest), so rotation does not recreate it and the running
 * [GameController] survives. Engine callbacks arrive on the session worker thread and are posted
 * to the main thread before they touch Compose state.
 */
class MainActivity : ComponentActivity() {
    private val main = Handler(Looper.getMainLooper())
    private var engine: AppEngine? = null
    private var engineError: String? = null
    private var controller: GameController? = null
    private var generation = 0 // bumped per game, so a late post from a closed game is dropped

    private fun readAsset(name: String): String = assets.open(name).bufferedReader(Charsets.UTF_8).use { it.readText() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            engine = AppEngine.fromTexts(readAsset("rules.json"), readAsset("battle_policy.json"), readAsset("creatures.json"))
        } catch (e: Exception) {
            engineError = e.toString()
        }
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                Surface(color = MaterialTheme.colorScheme.background) {
                    App()
                }
            }
        }
    }

    override fun onDestroy() {
        controller?.close()
        controller = null
        super.onDestroy()
    }

    @androidx.compose.runtime.Composable
    private fun App() {
        var screen by remember { mutableStateOf(Screen.Home) }
        var ui by remember { mutableStateOf<GameUi?>(null) }
        var setupError by remember { mutableStateOf<String?>(null) }

        fun closeGame() {
            controller?.close()
            controller = null
            generation++
            ui = null
        }

        when (screen) {
            Screen.Home -> HomeScreen(
                engineError = engineError,
                onNew = { setupError = null; screen = Screen.Setup },
                onAbout = { screen = Screen.About },
            )
            Screen.About -> AboutScreen(onBack = { screen = Screen.Home })
            Screen.Setup -> SetupScreen(
                error = setupError,
                onBack = { screen = Screen.Home },
                onStart = { preset, seedText ->
                    val eng = engine
                    val seed = seedText.toBigIntegerOrNull()
                    if (eng == null) {
                        setupError = "Data packs are not loaded."
                    } else if (seed == null) {
                        setupError = "The seed must be a whole number."
                    } else {
                        try {
                            val initial = Scenario.parse(preset.scenarioJson(eng.roster), eng.packs)
                            closeGame()
                            val gen = generation
                            val gc = GameController(eng, initial, seed) { snapshotUi ->
                                // Called on the session worker (or the tap thread): hop to main.
                                main.post { if (gen == generation && controller != null) ui = snapshotUi }
                            }
                            controller = gc
                            ui = gc.current()
                            screen = Screen.Battle
                            gc.start()
                        } catch (e: Exception) {
                            setupError = "Could not start: " + e.message
                        }
                    }
                },
            )
            Screen.Battle -> BattleScreen(
                ui = ui,
                controller = controller,
                onFinished = { screen = Screen.Result },
                onQuit = { closeGame(); screen = Screen.Home },
            )
            Screen.Result -> ResultScreen(
                ui = ui,
                onAgain = { closeGame(); setupError = null; screen = Screen.Setup },
                onHome = { closeGame(); screen = Screen.Home },
            )
        }
    }
}
