package h3.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import h3.presenter.TapState
import h3.presenter.ui.BattleLog
import h3.presenter.ui.BattlePanels
import h3.presenter.ui.StackRoster
import h3.presenter.ui.StackRosterRow
import h3.sim.Hex

/**
 * The battle screen: status, turn order, board, roster (both sides), log, preview and the action
 * buttons. Only callbacks leave it ([onFinished], [onQuit], [onSave]); it holds no game logic.
 *
 * [roster] and [log] come from the presenter models; when null the roster is built from the state
 * without a turn order and the log falls back to [GameUi.recent]. [sprites] is the player's own
 * atlas when it is loaded; null draws tokens. The extra parameters have defaults, so the original
 * four-argument call still compiles.
 */
@Composable
fun BattleScreen(
    ui: GameUi?,
    controller: GameController?,
    onFinished: () -> Unit,
    onQuit: () -> Unit,
    onSave: () -> Unit = {},
    roster: StackRoster? = null,
    log: BattleLog? = null,
    sprites: BoardSprites? = null,
) {
    Page {
        if (ui == null || controller == null) {
            Text("Starting...")
        } else {
            BattleBody(ui, controller, onFinished, onQuit, onSave, roster ?: StackRoster.build(ui.state, emptyList()), log, sprites)
        }
    }
}

@Composable
private fun ColumnScope.BattleBody(
    ui: GameUi,
    controller: GameController,
    onFinished: () -> Unit,
    onQuit: () -> Unit,
    onSave: () -> Unit,
    roster: StackRoster,
    log: BattleLog?,
    sprites: BoardSprites?,
) {
    val st = ui.state
    val over = st.winner != null
    val status = when {
        ui.fault != null -> "Engine fault: " + ui.fault
        over -> "Battle over"
        ui.stalled -> "The computer stopped (stalemate guard)"
        ui.humanTurn -> "Round " + st.round + " - your turn"
        else -> "Round " + st.round + " - computer's turn"
    }
    Text(status, style = MaterialTheme.typography.titleMedium)
    ui.message?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    val chips = BattlePanels.turnChips(roster)
    if (chips.isNotEmpty()) Text("Turn order: " + chips.joinToString(" > ") { it.label }, style = MaterialTheme.typography.bodySmall)
    Column(modifier = Modifier.weight(3f).fillMaxWidth()) {
        BoardView(ui = ui, onTapHex = { h -> controller.onTap(h) }, roster = roster, sprites = sprites)
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.weight(2f).fillMaxWidth()) {
        RosterPanel(roster, modifier = Modifier.weight(1f))
        LogPanel(log, ui.recent, modifier = Modifier.weight(1f))
    }
    PreviewPanel(ui, controller)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = { controller.onWait() }, enabled = ui.humanTurn && ui.canWait, modifier = Modifier.weight(1f)) { Text("Wait") }
        OutlinedButton(onClick = { controller.onDefend() }, enabled = ui.humanTurn && ui.canDefend, modifier = Modifier.weight(1f)) { Text("Defend") }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = onSave, modifier = Modifier.weight(1f)) { Text("Save") }
        if (over) {
            Button(onClick = onFinished, modifier = Modifier.weight(1f)) { Text("Result") }
        } else {
            OutlinedButton(onClick = onQuit, modifier = Modifier.weight(1f)) { Text("Quit") }
        }
    }
}

@Composable
private fun RosterPanel(roster: StackRoster, modifier: Modifier = Modifier) {
    Column(modifier = modifier.verticalScroll(rememberScrollState())) {
        RosterSide(BattlePanels.sideTitle(Hex.ATTACKER), roster.attackers)
        Spacer(Modifier.height(4.dp))
        RosterSide(BattlePanels.sideTitle(Hex.DEFENDER), roster.defenders)
    }
}

@Composable
private fun RosterSide(title: String, rows: List<StackRosterRow>) {
    Text(title, style = MaterialTheme.typography.titleMedium)
    for (e in BattlePanels.entries(rows)) {
        val color = if (e.row.active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
        Text(e.title, color = color, style = if (e.row.active) MaterialTheme.typography.titleMedium else MaterialTheme.typography.bodySmall)
        if (e.detail.isNotEmpty()) Text(e.detail, color = color, style = MaterialTheme.typography.bodySmall)
    }
}

/** Newest first, so the latest events are visible without scrolling. */
@Composable
private fun LogPanel(log: BattleLog?, recent: List<String>, modifier: Modifier = Modifier) {
    Column(modifier = modifier.verticalScroll(rememberScrollState())) {
        Text("Log", style = MaterialTheme.typography.titleMedium)
        if (log == null) {
            for (line in recent) Text(line, style = MaterialTheme.typography.bodySmall)
        } else {
            for (g in log.groups().asReversed()) {
                Text(BattlePanels.logHeader(g), style = MaterialTheme.typography.titleMedium)
                for (l in g.lines.asReversed()) Text(l.text, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun PreviewPanel(ui: GameUi, controller: GameController) {
    val t = ui.tap
    if (t !is TapState.Previewing) {
        val hint = if (ui.humanTurn) "Tap a green hex to move or a red unit to attack; tap again to confirm." else " "
        Text(hint, style = MaterialTheme.typography.bodySmall)
        return
    }
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(modifier = Modifier.padding(8.dp)) {
            for ((i, c) in t.candidates.withIndex()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = i == t.selected, onClick = { controller.onSelect(i) })
                    Text(candidateLabel(c.command), modifier = Modifier.clickable { controller.onSelect(i) })
                }
            }
            val p = t.candidates[t.selected].preview
            if (p != null) {
                Text("Damage: " + p.floor + " / " + p.expected + " / " + p.ceiling + " (min / expected / max)")
                Text("Kills: " + p.killsFloor + " / " + p.killsExpected + " / " + p.killsCeiling)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { controller.onConfirm() }) { Text("Confirm") }
                OutlinedButton(onClick = { controller.onCancel() }) { Text("Cancel") }
            }
        }
    }
}

private fun candidateLabel(c: h3.sim.BattleCommand): String = when (c) {
    is h3.sim.BattleCommand.Shoot -> "Shoot"
    is h3.sim.BattleCommand.Attack ->
        if (c.fromHex == null) "Attack from here" else "Attack from (" + c.fromHex!!.first + ", " + c.fromHex!!.second + ")"
    is h3.sim.BattleCommand.Move -> "Move here"
    else -> c.toString()
}
