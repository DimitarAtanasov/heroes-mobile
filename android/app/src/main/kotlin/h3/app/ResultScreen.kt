package h3.app

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
import h3.presenter.ui.ResultOutcome
import h3.presenter.ui.ResultSummary
import h3.presenter.ui.SideTally
import h3.sim.Hex

/**
 * Shows [summary] (build it with `ResultSummary.of(initialState, snapshot)`); null shows "No result".
 * [onAgain] is Play again, [onHome] is Home.
 */
@Composable
fun ResultScreen(summary: ResultSummary?, onAgain: () -> Unit, onHome: () -> Unit) {
    Page {
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Spacer(Modifier.height(32.dp))
            val title = when (summary?.outcome) {
                ResultOutcome.Victory -> "Victory"
                ResultOutcome.Defeat -> "Defeat"
                ResultOutcome.Unfinished -> "Battle not finished"
                null -> "No result"
            }
            Text(title, style = MaterialTheme.typography.displaySmall)
            if (summary != null) {
                Spacer(Modifier.height(16.dp))
                for (tally in summary.sides) {
                    SideTallyCard(tally)
                }
                Spacer(Modifier.height(8.dp))
                Text("Rounds: ${summary.rounds}")
                Text("Commands played: ${summary.commands}")
                Text("State hash: ${summary.shortHash}", style = MaterialTheme.typography.bodySmall)
            }
        }
        Button(onClick = onAgain, modifier = Modifier.fillMaxWidth()) { Text("Play again") }
        OutlinedButton(onClick = onHome, modifier = Modifier.fillMaxWidth()) { Text("Home") }
    }
}

@Composable
private fun SideTallyCard(tally: SideTally) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                if (tally.side == Hex.ATTACKER) "You (blue)" else "The computer (purple)",
                style = MaterialTheme.typography.titleMedium,
            )
            Text("Stacks standing: ${tally.survivingStacks} of ${tally.startStacks}")
            Text("Survivors: ${tally.survivors} of ${tally.startCreatures}")
            Text("Casualties: ${tally.casualties}")
        }
    }
}
