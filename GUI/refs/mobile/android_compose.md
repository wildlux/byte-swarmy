# Riferimento curato — Android / Jetpack Compose (Kotlin)

# Tipo: statico (non introspettabile con `api_lookup`)
# Nota: i simboli sono verificati solo strutturalmente da
# `tools/mobile_scaffold_check.py`. La build richiede Android SDK,
# non presente in questo ambiente. Nessun flag di "verificato via inspect".

| Simbolo | Uso nel template |
|---|---|
| `ComponentActivity` | activity base (`class MainActivity : ComponentActivity()`) |
| `setContent` | ingresso al contenuto Compose in `onCreate` |
| `MaterialTheme` | tema Material 3 |
| `Surface` | superficie che avvolge la schermata |
| `Column` | layout verticale |
| `Text` | etichetta statica e valore del contatore |
| `Button` | pulsante con `onClick` |
| `Composable` | annotazione `@Composable` |
| `remember` | conserva lo stato tra ricomposizioni |
| `mutableStateOf` | stato osservabile del contatore |

Regole per il modello 3b:
- non aggiungere import o simboli Compose non presenti qui senza verifica
  sulla documentazione Android e un nuovo gate;
- non toccare widget da thread di lavoro: qui non c'è nessun thread;
- i marker `# SLOT:` sono gli unici valori da sostituire.
