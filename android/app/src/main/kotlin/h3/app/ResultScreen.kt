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
fun ResultScreen(ui: GameUi?, onAgain: () -> Unit, onHome: () -> Unit) {
    Page {
        Spacer(Modifier.height(32.dp))
        val w = ui?.state?.winner
        val title = when (w) {
            0 -> "Victory"
            1 -> "Defeat"
            else -> "No result"
        }
        Text(title, style = MaterialTheme.typography.displaySmall)
        if (w != null) Text(if (w == 0) "You (blue) won." else "The computer (purple) won.")
        Spacer(Modifier.height(16.dp))
        if (ui != null) {
            Text("Rounds: " + ui.state.round)
            Text("Commands played: " + ui.seq)
            Text("Final state hash:")
            Text(ui.hash, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(24.dp))
        Button(onClick = onAgain, modifier = Modifier.fillMaxWidth()) { Text("New skirmish") }
        OutlinedButton(onClick = onHome, modifier = Modifier.fillMaxWidth()) { Text("Home") }
    }
}
