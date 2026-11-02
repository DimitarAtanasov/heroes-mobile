package h3.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import h3.presenter.ui.ImportPlan
import h3.presenter.ui.ImportResult
import h3.presenter.ui.ImportText

/**
 * The game data screen (android-app.md 3.2 and 3.5). All state is hoisted and all words come from
 * [ImportText]: [status] is the found, missing or changed line (null while the first check runs),
 * [progress] is shown while a copy runs (null otherwise), [result] is the outcome of the last check
 * or import (null before one): one sentence per named error and one details line of file names and
 * sizes. "Check again" calls [onCheckAgain]; the sideload hint is always shown (debug builds only).
 */
@Composable
fun ImportScreen(
    status: ImportPlan.DataStatus?,
    progress: ImportPlan.Progress?,
    result: ImportResult?,
    onCheckAgain: () -> Unit,
    onBack: () -> Unit,
) {
    Page {
        Text("Game data", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Text(ImportText.statusLine(status), style = MaterialTheme.typography.titleMedium)
            if (progress != null) {
                Spacer(Modifier.height(8.dp))
                Text(ImportText.progressLine(progress))
            }
            if (result != null) {
                Spacer(Modifier.height(12.dp))
                val color = if (result.isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface
                for (s in result.sentences()) {
                    Text(s, color = color)
                }
                Spacer(Modifier.height(4.dp))
                Text(result.details(), style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(16.dp))
            Text(ImportText.SIDELOAD_HINT, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(8.dp))
        Button(onClick = onCheckAgain, modifier = Modifier.fillMaxWidth()) { Text("Check again") }
        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back") }
    }
}
