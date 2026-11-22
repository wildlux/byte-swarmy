# Riferimento curato — SwiftUI (iOS)

# Tipo: statico (non introspettabile con `api_lookup`)
# Nota: i simboli sono verificati solo strutturalmente da
# `tools/mobile_scaffold_check.py`. La build richiede Xcode/iOS SDK,
# non presenti in questo ambiente. Nessun flag di "verificato via inspect".

| Simbolo | Uso nel template |
|---|---|
| `View` | protocollo conformato da `ContentView` |
| `State` | property wrapper `@State` per lo stato locale |
| `Text` | etichetta statica e valore del contatore |
| `VStack` | impaginazione verticale |
| `Button` | pulsante con closure `tapCount += 1` |
| `padding` | modifier applicato allo stack |

Regole per il modello 3b:
- non aggiungere simboli SwiftUI non presenti in questa tabella senza
  verifica con documentazione Apple e nuovo gate;
- non usare `@Environment`, `NavigationStack` o API di versione specifica
  nei template base: la build non è verificabile qui;
- i marker `# SLOT:` sono gli unici valori da sostituire.
