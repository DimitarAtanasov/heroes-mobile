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

@Composable
fun BattleScreen(
    ui: GameUi?,
    controller: GameController?,
    onFinished: () -> Unit,
    onQuit: () -> Unit,
) {
    Page {
        if (ui == null || controller == null) {
            Text("Starting...")
        } else {
            BattleBody(ui, controller, onFinished, onQuit)
        }
    }
}

@Composable
private fun ColumnScope.BattleBody(ui: GameUi, controller: GameController, onFinished: () -> Unit, onQuit: () -> Unit) {
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
    Column(modifier = Modifier.weight(1f).fillMaxWidth()) {
        BoardView(ui = ui, onTapHex = { h -> controller.onTap(h) })
    }
    PreviewPanel(ui, controller)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(onClick = { controller.onWait() }, enabled = ui.humanTurn && ui.canWait, modifier = Modifier.weight(1f)) { Text("Wait") }
        OutlinedButton(onClick = { controller.onDefend() }, enabled = ui.humanTurn && ui.canDefend, modifier = Modifier.weight(1f)) { Text("Defend") }
        if (over) {
            Button(onClick = onFinished, modifier = Modifier.weight(1f)) { Text("Result") }
        } else {
            OutlinedButton(onClick = onQuit, modifier = Modifier.weight(1f)) { Text("Quit") }
        }
    }
    for (line in ui.recent.take(3)) Text(line, style = MaterialTheme.typography.bodySmall)
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
