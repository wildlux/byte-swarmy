// Template SwiftUI — schermata iOS minima (F1 / mobile-scaffold).
// Copiare e sostituire i valori marcati `# SLOT:`. Nessun timestamp.
// Verifica strutturale: .venv/bin/python tools/mobile_scaffold_check.py
// Build NON verificata: serve Xcode/iOS SDK (non presenti qui).

// SLOT: titolo della schermata
private let screenTitle = "Hello iOS"
// SLOT: testo del pulsante
private let buttonTitle = "Continua"

import SwiftUI

struct ContentView: View {
    // SLOT: contatore iniziale
    @State private var tapCount = 0

    var body: some View {
        VStack(spacing: 12) {
            Text(screenTitle)
            Text("Tap: \(tapCount)")
            Button(buttonTitle) {
                tapCount += 1
            }
        }
        .padding()
    }
}
