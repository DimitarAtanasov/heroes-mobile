package h3.app

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import h3.presenter.ReplayAutosave
import h3.presenter.ui.GameRosterEntry
import h3.presenter.ui.GameRosterResult
import h3.presenter.ui.ImportPlan
import h3.presenter.ui.ImportResult
import h3.presenter.ui.MenuModel
import h3.presenter.ui.PresetCheck
import h3.presenter.ui.ResultSummary
import h3.presenter.ui.SaveSlots
import h3.presenter.ui.SetupForm
import h3.presenter.ui.SpriteReload
import h3.presenter.ui.StackRoster
import h3.presenter.ui.StartRequest
import h3.sim.Scenario
import java.io.File
import java.math.BigInteger

enum class Screen { Home, Setup, Battle, Result, About, Saves, Import }

/** The row-keyed creature sprite table in the assets (staged by `copyH3Data` from `data/`). */
private const val SPRITE_TABLE_ASSET = "sprite_map.json"

/** Logcat tag for the sprite notes (codes, counts, file and DEF names; never file contents). */
private const val SPRITE_LOG_TAG = "h3.sprites"

/**
 * Single activity, state-based navigation (no navigation library). The activity handles its own
 * configuration changes (see the manifest), so rotation does not recreate it and the running
 * [GameController] survives. Engine callbacks arrive on the session worker thread and are posted
 * to the main thread before they touch Compose state. Save files are only touched on the
 * [SaveFolderWriter] thread.
 *
 * The battle roster is the player's own CRTRAITS.TXT, read from the imported `H3bitmap.lod` on the
 * [GameDataStore] thread ([GameDataStore.loadRoster]). Without it Home shows only the import prompt
 * (ADR-0011 D3, amended 2026-11-03); the bundled `creatures.json` only feeds the replay pack hashes.
 */
class MainActivity : ComponentActivity() {
    private val main = Handler(Looper.getMainLooper())
    private var engine: AppEngine? = null
    private var engineError: String? = null
    private var controller: GameController? = null
    private var saver: SaveFolderWriter? = null
    private var dataStore: GameDataStore? = null // the player's own game files; I/O on its own thread
    private var sprites by mutableStateOf<BoardSprites?>(null) // the player's own sprites, when found
    private var mappingJson: String? = null // txt_maps/crtraits.json from the assets
    // The player's battle roster: null = no H3bitmap.lod imported (or not read yet), else Ok or Refused.
    private var rosterResult by mutableStateOf<GameRosterResult?>(null)
    private var generation = 0 // bumped per game, so a late post from a closed game is dropped

    private fun readAsset(name: String): String = assets.open(name).bufferedReader(Charsets.UTF_8).use { it.readText() }

    // Starts the sprite worker on the current gamedata for [roster]; sets [sprites] on the main thread when it
    // finishes. The caller must not be the main thread (the file listing in SpriteLoader.start is I/O): it runs
    // from the roster callback on the data-store thread. The worker reads the bundled row-keyed table
    // sprite_map.json (ADR-0014), so the asset read and the parse happen there too. Each note (table parse
    // errors, the row-count mismatch line, load errors) goes to logcat; none of them changes the menus.
    private fun loadSprites(roster: List<GameRosterEntry>) {
        SpriteLoader.start(
            roots = listOf(File(noBackupFilesDir, "gamedata")), // not filesDir: that can go to cloud backup
            roster = roster,
            readTable = { readAsset(SPRITE_TABLE_ASSET) },
        ) { sp, notes ->
            for (n in notes) Log.w(SPRITE_LOG_TAG, n)
            main.post { sprites = sp }
        }
    }

    // Reads the roster on the data-store thread, posts it to the main thread, then (still on the data-store
    // thread) starts the sprite worker for it. Called at launch and again after a check left valid data.
    private fun loadRoster() {
        val store = dataStore ?: return
        val mapping = mappingJson ?: return
        store.loadRoster(mapping) { r ->
            main.post { rosterResult = r }
            val entries = (r as? GameRosterResult.Ok)?.entries
            if (entries != null) loadSprites(entries)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        dataStore = GameDataStore(noBackupFilesDir)
        try {
            val eng = AppEngine.fromTexts(readAsset("rules.json"), readAsset("battle_policy.json"), readAsset("creatures.json"))
            engine = eng
            saver = SaveFolderWriter(File(filesDir, "saves"), eng.packs)
            mappingJson = readAsset("txt_maps/crtraits.json")
            // Reads the player's own CRTRAITS.TXT under gamedata; with none, the roster stays null.
            loadRoster()
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
        saver?.close()
        saver = null
        dataStore?.close()
        dataStore = null
        super.onDestroy()
    }

    @androidx.compose.runtime.Composable
    private fun App() {
        var screen by remember { mutableStateOf(Screen.Home) }
        var ui by remember { mutableStateOf<GameUi?>(null) }
        var setupError by remember { mutableStateOf<String?>(null) }
        var form by remember { mutableStateOf(SetupForm(Preset.ALL.size)) }
        var rows by remember { mutableStateOf<List<SaveSlots.SlotRow>?>(null) }
        var saveMessage by remember { mutableStateOf<String?>(null) }
        var summary by remember { mutableStateOf<ResultSummary?>(null) }
        var importStatus by remember { mutableStateOf<ImportPlan.DataStatus?>(null) }
        var importResult by remember { mutableStateOf<ImportResult?>(null) }

        val rosterEntries = (rosterResult as? GameRosterResult.Ok)?.entries
        val rosterNote = (rosterResult as? GameRosterResult.Refused)?.text

        // Setup is reached only with a roster (MenuModel); without one, Home shows the import prompt.
        fun openSetup() {
            setupError = null
            screen = if (rosterEntries != null) Screen.Setup else Screen.Home
        }

        fun closeGame() {
            controller?.close()
            controller = null
            generation++
            ui = null
        }

        // Reads the saves folder on the writer thread and lists it there (one replay per file),
        // then posts the rows to the main thread.
        fun refreshSaves() {
            val sv = saver
            val eng = engine
            if (sv == null || eng == null) {
                rows = emptyList()
                return
            }
            sv.readFolder { files ->
                val listed = SaveSlots.list(files, eng.packs)
                main.post { rows = listed }
            }
        }

        // Starts a game (new, or resumed from a verified save) and shows the battle screen.
        fun launch(scenarioJson: String, seed: BigInteger, resumedFrom: h3.presenter.Resumed?) {
            val eng = engine
            val sv = saver
            if (eng == null || sv == null) {
                setupError = "Data packs are not loaded."
                return
            }
            try {
                val initial = Scenario.parse(scenarioJson, eng.packs)
                val slot = SaveSlots.slot(initial.battleId)
                closeGame()
                val gen = generation
                val auto = if (slot == null) null else if (resumedFrom != null) {
                    ReplayAutosave.resuming(resumedFrom, seed, eng.packs, sv.sinkFor(slot))
                } else {
                    ReplayAutosave(scenarioJson, seed, eng.packs, sv.sinkFor(slot))
                }
                val gc = GameController(eng, initial, scenarioJson, seed, auto) { snapshotUi ->
                    // Called on the session worker (or the tap thread): hop to main.
                    main.post { if (gen == generation && controller != null) ui = snapshotUi }
                }
                controller = gc
                ui = gc.current()
                summary = null
                screen = Screen.Battle
                if (resumedFrom != null) gc.resume(resumedFrom) else gc.start()
            } catch (e: Exception) {
                setupError = "Could not start: " + e.message
                screen = Screen.Setup
            }
        }

        // Asks the data store (its own thread) for the status of the player's game files.
        fun refreshImportStatus() {
            dataStore?.status { st -> main.post { importStatus = st } }
        }

        fun openSaves() {
            saveMessage = null
            rows = null
            refreshSaves()
            screen = Screen.Saves
        }

        fun loadSave(fileName: String) {
            val current = rows ?: return
            when (val sel = SaveSlots.select(current, fileName)) {
                is SaveSlots.SlotSelection.Load -> launch(sel.resumed.scenarioJson, sel.resumed.seed, sel.resumed)
                is SaveSlots.SlotSelection.Refused -> saveMessage = sel.message
                is SaveSlots.SlotSelection.NotListed -> saveMessage = "That save is no longer in the list."
            }
        }

        when (screen) {
            Screen.Home -> {
                val autosaveReady = rows?.any { r -> r.kind == SaveSlots.SlotKind.Autosave && r.status is SaveSlots.SlotStatus.Ready } == true
                val model = MenuModel.initial(autosaveReady && engineError == null, rosterReady = rosterEntries != null)
                androidx.compose.runtime.LaunchedEffect(Unit) { refreshSaves() }
                HomeScreen(
                    model = model,
                    engineError = engineError,
                    rosterNote = rosterNote,
                    onNew = { openSetup() },
                    onContinue = {
                        val auto = rows?.firstOrNull { r -> r.kind == SaveSlots.SlotKind.Autosave }
                        if (auto != null) loadSave(auto.fileName)
                    },
                    onLoad = { openSaves() },
                    onImport = { importStatus = null; importResult = null; refreshImportStatus(); screen = Screen.Import },
                    onAbout = { screen = Screen.About },
                )
            }
            Screen.About -> AboutScreen(onBack = { screen = Screen.Home })
            Screen.Import -> ImportScreen(
                status = importStatus,
                progress = null,
                result = importResult,
                onCheckAgain = {
                    dataStore?.checkInPlace { r ->
                        main.post { importResult = r }
                        if (SpriteReload.needed(r)) loadRoster() // roster, then sprites; queued on the data-store thread
                        refreshImportStatus()
                    }
                },
                onBack = { screen = Screen.Home },
            )
            Screen.Setup -> SetupScreen(
                // Blocks are recomputed from the current roster on every composition, so they are never stale.
                form = form.withBlocks(Preset.ALL.map { p -> PresetCheck.check(p.rows, rosterEntries ?: emptyList()) }),
                presets = Preset.ALL,
                startError = setupError,
                onForm = { f -> form = f },
                onBack = { screen = Screen.Home },
                onStart = { req: StartRequest ->
                    val entries = rosterEntries
                    if (engine == null) {
                        setupError = "Data packs are not loaded."
                    } else if (entries == null) {
                        setupError = "Import your game data first."
                    } else {
                        try {
                            launch(Preset.ALL[req.presetIndex].scenarioJson(entries), BigInteger.valueOf(req.seed), null)
                        } catch (e: IllegalArgumentException) {
                            setupError = "Could not start: " + e.message
                        }
                    }
                },
            )
            Screen.Battle -> BattleScreen(
                ui = ui,
                controller = controller,
                roster = ui?.let { u -> engine?.let { e -> StackRoster.build(e.battle, u.state) } },
                log = ui?.log,
                sprites = sprites,
                onSave = { openSaves() },
                onFinished = {
                    val gc = controller
                    val last = ui
                    summary = if (gc != null && last != null) ResultSummary.of(gc.initialState, last.state, last.seq, last.hash) else null
                    screen = Screen.Result
                },
                onQuit = { closeGame(); screen = Screen.Home },
            )
            Screen.Result -> ResultScreen(
                summary = summary,
                onAgain = { closeGame(); openSetup() },
                onHome = { closeGame(); screen = Screen.Home },
            )
            Screen.Saves -> SaveScreen(
                rows = rows,
                battleId = controller?.initialState?.battleId,
                message = saveMessage,
                onLoad = { name -> loadSave(name) },
                onSaveNow = { slot ->
                    val gc = controller
                    val sv = saver
                    if (gc == null || sv == null) {
                        saveMessage = "There is no running game to save."
                    } else {
                        sv.write(slot, gc.replayBytes()) { ok ->
                            main.post {
                                saveMessage = if (ok) "Game saved." else "Could not write the save."
                                refreshSaves()
                            }
                        }
                    }
                },
                onBack = { screen = if (controller != null) Screen.Battle else Screen.Home },
            )
        }
    }
}
