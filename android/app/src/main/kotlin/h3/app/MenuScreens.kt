package h3.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import h3.presenter.ui.APP_VERSION_TEXT
import h3.presenter.ui.MenuModel
import h3.presenter.ui.SetupForm
import h3.presenter.ui.StartRequest
import h3.presenter.ui.setupFormMessage

/**
 * Home. All state is hoisted: [model] decides whether Continue is enabled, [engineError] is the
 * data pack load failure (null when fine). [onLoad] opens the save list.
 */
@Composable
fun HomeScreen(
    model: MenuModel,
    engineError: String?,
    onNew: () -> Unit,
    onContinue: () -> Unit,
    onLoad: () -> Unit,
    onAbout: () -> Unit,
) {
    Page {
        Spacer(Modifier.height(48.dp))
        Text("Heroes", style = MaterialTheme.typography.displayMedium)
        Text(APP_VERSION_TEXT, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(32.dp))
        if (engineError != null) {
            Text("Could not load the data packs: $engineError", color = MaterialTheme.colorScheme.error)
            Spacer(Modifier.height(16.dp))
        }
        Button(onClick = onNew, enabled = engineError == null, modifier = Modifier.fillMaxWidth()) { Text("New skirmish") }
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = onContinue, enabled = model.continueEnabled, modifier = Modifier.fillMaxWidth()) { Text("Continue") }
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = onLoad, enabled = engineError == null, modifier = Modifier.fillMaxWidth()) { Text("Load game") }
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = onAbout, modifier = Modifier.fillMaxWidth()) { Text("About") }
    }
}

/**
 * Setup. [form] is the hoisted [SetupForm] (its presetCount should be presets.size); every edit goes
 * out through [onForm]. [startError] is a failure of the last Start (null when none). Start is enabled
 * only while the form is valid and hands the validated [StartRequest] to [onStart].
 */
@Composable
fun SetupScreen(
    form: SetupForm,
    presets: List<Preset>,
    startError: String?,
    onForm: (SetupForm) -> Unit,
    onStart: (StartRequest) -> Unit,
    onBack: () -> Unit,
) {
    Page {
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Text("New skirmish", style = MaterialTheme.typography.headlineMedium)
            Text("You play the blue side; the computer plays purple.")
            Spacer(Modifier.height(16.dp))
            for ((i, p) in presets.withIndex()) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .clickable { onForm(form.selectPreset(i)) },
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(8.dp)) {
                        RadioButton(selected = form.presetIndex == i, onClick = { onForm(form.selectPreset(i)) })
                        Column {
                            Text(p.title, style = MaterialTheme.typography.titleMedium)
                            Text(p.blurb, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                value = form.seedText,
                onValueChange = { v -> onForm(form.withSeedText(v)) },
                label = { Text("Seed (same seed, same battle)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            val message = setupFormMessage(form)
            if (message != null) {
                Spacer(Modifier.height(8.dp))
                Text(message, color = MaterialTheme.colorScheme.error)
            }
            if (startError != null) {
                Spacer(Modifier.height(8.dp))
                Text(startError, color = MaterialTheme.colorScheme.error)
            }
        }
        Spacer(Modifier.height(8.dp))
        Button(
            onClick = { form.start()?.let(onStart) },
            enabled = form.isValid,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Start battle") }
        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back") }
    }
}

/** About: licence notice, version text and the source link text. Signature unchanged. */
@Composable
fun AboutScreen(onBack: () -> Unit) {
    Page {
        Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            Text("About", style = MaterialTheme.typography.headlineMedium)
            Text("Version: $APP_VERSION_TEXT")
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
