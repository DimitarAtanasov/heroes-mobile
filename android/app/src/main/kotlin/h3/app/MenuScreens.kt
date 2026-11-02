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
fun HomeScreen(engineError: String?, onNew: () -> Unit, onAbout: () -> Unit) {
    Page {
        Spacer(Modifier.height(48.dp))
        Text("Heroes", style = MaterialTheme.typography.displayMedium)
        Text("Prototype 0.1 - placeholder art", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(32.dp))
        if (engineError != null) {
            Text("Could not load the data packs: " + engineError, color = MaterialTheme.colorScheme.error)
            Spacer(Modifier.height(16.dp))
        }
        Button(onClick = onNew, enabled = engineError == null, modifier = Modifier.fillMaxWidth()) { Text("New skirmish") }
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = onAbout, modifier = Modifier.fillMaxWidth()) { Text("About") }
    }
}

@Composable
fun SetupScreen(
    error: String?,
    onStart: (Preset, String) -> Unit,
    onBack: () -> Unit,
) {
    var selected by remember { mutableStateOf(0) }
    var seed by remember { mutableStateOf("1") }
    Page {
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Text("New skirmish", style = MaterialTheme.typography.headlineMedium)
            Text("You play the blue side; the computer plays purple.")
            Spacer(Modifier.height(16.dp))
            for ((i, p) in Preset.ALL.withIndex()) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .clickable { selected = i },
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(8.dp)) {
                        RadioButton(selected = selected == i, onClick = { selected = i })
                        Column {
                            Text(p.title, style = MaterialTheme.typography.titleMedium)
                            Text(p.blurb, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                value = seed,
                onValueChange = { v -> seed = v.filter { ch -> ch in '0'..'9' }.take(18) },
                label = { Text("Seed (same seed, same battle)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            if (error != null) {
                Spacer(Modifier.height(8.dp))
                Text(error, color = MaterialTheme.colorScheme.error)
            }
        }
        Spacer(Modifier.height(8.dp))
        Button(onClick = { onStart(Preset.ALL[selected], seed) }, modifier = Modifier.fillMaxWidth()) { Text("Start battle") }
        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back") }
    }
}

@Composable
fun AboutScreen(onBack: () -> Unit) {
    Page {
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Text("About", style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(12.dp))
            Text(
                "This program is free software: you can redistribute it and/or modify it under the " +
                    "terms of the GNU General Public License as published by the Free Software " +
                    "Foundation, either version 2 of the License, or (at your option) any later " +
                    "version (GPL-2.0-or-later). It is distributed in the hope that it will be " +
                    "useful, but WITHOUT ANY WARRANTY; without even the implied warranty of " +
                    "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.",
            )
            Spacer(Modifier.height(12.dp))
            Text(
                "This is an independent, clean-room project. It is not affiliated with the rights " +
                    "holders of Heroes of Might and Magic.",
            )
            Spacer(Modifier.height(12.dp))
            Text("No game assets are bundled. All art in this prototype is placeholder shapes and letters.")
            Spacer(Modifier.height(12.dp))
            Text("Source code:")
            Text(SOURCE_URL, color = MaterialTheme.colorScheme.primary)
        }
        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back") }
    }
}
