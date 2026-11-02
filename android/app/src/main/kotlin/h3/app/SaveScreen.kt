package h3.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import h3.presenter.ui.SaveSlots

/**
 * The saves list. [rows] come from `SaveSlots.list(readSaveFolder(dir), packs)` (null while loading),
 * autosave first. Tapping a ready row calls [onLoad] with its file name; an unusable row only shows
 * its message. "Save now" calls [onSaveNow] with the next free manual slot of [battleId] (the running
 * game); it is disabled when there is no running game or no free slot. [message] is a one-line notice.
 */
@Composable
fun SaveScreen(
    rows: List<SaveSlots.SlotRow>?,
    battleId: String?,
    message: String?,
    onLoad: (String) -> Unit,
    onSaveNow: (SaveSlots.Slot) -> Unit,
    onBack: () -> Unit,
) {
    val next = if (rows != null && battleId != null) SaveSlots.nextManualNumber(battleId, rows.map { r -> r.fileName }) else null
    val slot = if (battleId != null && next != null) SaveSlots.manualSlot(battleId, next) else null
    Page {
        Text("Saves", style = MaterialTheme.typography.headlineMedium)
        if (message != null) {
            Text(message)
        }
        Spacer(Modifier.height(8.dp))
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            if (rows == null) {
                Text("Loading saves...")
            } else if (rows.isEmpty()) {
                Text("No saves yet.")
            } else {
                for (row in rows) {
                    SaveRowCard(row, onLoad)
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        if (slot == null && rows != null) {
            Text(if (battleId == null) "There is no running game to save." else "This game cannot be saved.")
        }
        Button(
            onClick = { if (slot != null) onSaveNow(slot) },
            enabled = slot != null,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Save now") }
        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back") }
    }
}

@Composable
private fun SaveRowCard(row: SaveSlots.SlotRow, onLoad: (String) -> Unit) {
    val status = row.status
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
            .clickable(enabled = status is SaveSlots.SlotStatus.Ready) { onLoad(row.fileName) },
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(row.title, style = MaterialTheme.typography.titleMedium)
            Text("Battle ${row.battleId}", style = MaterialTheme.typography.bodySmall)
            when (status) {
                is SaveSlots.SlotStatus.Ready -> {
                    Text("Commands: ${status.commands}, rounds: ${status.rounds}")
                    Text("Hash ${status.shortHash}", style = MaterialTheme.typography.bodySmall)
                }
                is SaveSlots.SlotStatus.Unusable -> {
                    Text(status.message, color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}
