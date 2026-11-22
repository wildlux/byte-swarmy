// Template Kotlin + Jetpack Compose — schermata Android minima (F1).
// Copiare e sostituire i valori marcati `# SLOT:`. Nessun timestamp.
// Verifica strutturale: .venv/bin/python tools/mobile_scaffold_check.py
// Build NON verificata: serve Android SDK (non presente qui).

// SLOT: package dell'app
package com.example.mobile

// SLOT: titolo della schermata
private const val SCREEN_TITLE = "Hello Android"

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface {
                    MobileScreen()
                }
            }
        }
    }
}

@Composable
fun MobileScreen() {
    // SLOT: testo del pulsante
    val buttonText = "Continua"
    val count = remember { mutableStateOf(0) }
    Column {
        Text(SCREEN_TITLE)
        Text("Tap: ${count.value}")
        Button(onClick = { count.value += 1 }) {
            Text(buttonText)
        }
    }
}
