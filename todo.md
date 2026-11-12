# TODO — Suite di test complessi: programmazione Python con LLM piccoli

> **Obiettivo**: stress-testare la pipeline di generazione (skill `py-cli-script` / `pyqt6-gui-window`,
> modalità diretta senza tool, correction loop) con il worker `qwen2.5-coder:3b`.
> **Progetto di test**: `project/PR_TEST_progetto/main.py` (sovrascritto a ogni task).
> **Verifica**: ① `py_compile` ② esecuzione ③ output atteso deterministico.
> 🔹 = skill attiva (matcher) · ⚪ = senza skill (fallback) · 🔶 = avanzato (probabile correction loop)

---

## Coda dei task

- [x] **T1 — Statistiche numeriche** 🔹 base ✅ **1 tentativo, PASS** (usa `statistics.mean/median/mode`; media=4 esatto — il criterio "4.0" era impreciso, il valore è corretto)
  - Task: `fammi un software in python che calcola media, mediana e moda di una lista di numeri. Usa la lista [4, 2, 7, 2, 5] come dati di esempio e stampa i tre valori.`
  - Atteso in output: `4.0` (media), `4` (mediana), `2` (moda)
  - Testa: match skill py-cli-script + riempimento template

- [x] **T2 — Convertitore di temperature con gestione errori** 🔹 base ✅ **1 tentativo, PASS** (77.00 °F + "Errore: Input non numerico." gestito, exit=0)
  - Task: `convertitore che trasforma gradi celsius in fahrenheit con gestione degli errori per input non numerico. Converti 25 gradi e stampa il risultato, poi prova a convertire la stringa "abc" gestendo l'errore senza crash.`
  - Atteso: `77.0` per 25 °C, e una riga di errore gestita (niente traceback) per "abc"
  - Testa: skill + try/except generato correttamente

- [x] **T3 — Classe Collezione con protocollo iteratore** ⚪ intermedio ❌ **FAIL semantico (2/2 esecuzioni, sistematico)**: omette `add("a")` → LEN=2 e iterazione senza "a". I dunder methods sono perfetti. Causa probabile: "aggiungi a, b, c" → il 3B legge "a" come nome variabile. **Lezione**: la verifica host (py_compile) non vede gli errori semantici; i task vanno scritti con elementi quottati (`'a'`) o output esatti.
  - Task: `Creare una classe Collezione che implementa __len__, __contains__ e __iter__. Nel main: aggiungi "a", "b", "c", stampa LEN=3, verifica che contenga "b" stampando HAS=True e itera gli elementi stampandoli uno per riga.`
  - Atteso: `LEN=3`, `HAS=True`, tre righe `a` `b` `c`
  - Testa: fallback senza skill (nessuna keyword nel titolo) + dunder methods

- [x] **T4 — Palindromo e frequenza delle parole** 🔹 intermedio ❌ **FAIL semantico**: non rimuove la punteggiatura → `PALINDROMO=False` (errato: "itopinonavevanonipoti" È palindroma, il punto finale rompe il confronto) e "parola più frequente" = frase intera. Il punto era arrivato dal testo del task ("...nipoti. Stampa..."). **Lezione**: i task vanno formulati senza ambiguità di punteggiatura o con criterio "ignora la punteggiatura".
  - Task: `software che verifica se una frase è palindroma ignorando spazi e maiuscole, e conta la frequenza delle parole. Frase: "I topi non avevano nipoti". Stampa PALINDROMO=True e la parola più frequente.`
  - Atteso: `PALINDROMO=True` (i-topi-non-avevano-nipoti) e frequenza su parole ripetute
  - Testa: pulizia stringa (spazi/maiuscole) + conteggio dizionario

- [x] **T5 — Rubrica con salvataggio su file JSON** ⚪ intermedio ❌ **FAIL semantico ×2**: ① percorso **relativo** `"rubrica.json"` → file creato nella root del repo invece che nella cartella progetto (la verifica dalla root non lo vede in `project/`); ② match esatto `persona["nome"] == "Mario"` fallisce contro `"Mario Rossi"` → nessun `TROVATO=12345` stampato. JSON write/read corretti, exit=0. **Lezione**: i task con file I/O vanno testati con cwd corretto e match per prefissione/sottostringa nel criterio di accettazione.
  - Task: `Gestione rubrica con persistenza su file json: aggiungi Mario Rossi 12345 e Luca Bianchi 67890, salva su rubrica.json, rileggi dal file e cerca "Mario" stampando TROVATO=12345.`
  - Atteso: file `rubrica.json` creato + output `TROVATO=12345`
  - Testa: file I/O + json + CRUD senza skill (richiede più passi logici)

- [x] **T6 — Fibonacci memoizzato** 🔹 intermedio ✅ **1 tentativo, PASS** (`12586269025` esatto; memoizzazione con dict `memo={}` corretta — nota: usa mutable default come convenzione, ma funzionale)
  - Task: `calcolo della sequenza di fibonacci con memoizzazione (dizionario). Stampa il valore per n=50.`
  - Atteso: `12586269025`
  - Testa: ricorsione + memoizzazione (i modelli piccoli spesso sbagliano il valore)

- [x] **T7 — Finestra GUI PyQt6: lista della spesa** 🔹 intermedio ✅ **1 tentativo, PASS** (py_compile OK; offscreen entra nel loop eventi, exit 124 al timeout = nessun crash; titolo ✓ QLineEdit ✓ 2 pulsanti con wiring ✓. Nota: gli action stampano su console invece di popolare un QListWidget visibile — struttura presente, persistenza visiva parziale)
  - Task: `crea una finestra gui con un campo testo, un pulsante che aggiunge l'articolo a una lista e un pulsante che pulisce la lista. Titolo: Lista della spesa.`
  - Atteso: `py_compile` OK + avvio offscreen senza crash (entra nel loop eventi, kill a timeout)
  - Testa: skill pyqt6-gui-window + widget wiring

- [x] **T8 — Classe Stack con eccezioni personalizzate** ⚪ 🔶 avanzato ✅ **1 tentativo, PASS** (`OVERFLOW=ok` + `UNDERFLOW=ok`, exit=0, niente traceback; pop stampa 2/1/0). Nota: il modello usa il messaggio dell'eccezione per portare l'output ("OVERFLOW=ok" come argomento di raise) — non ortodosso ma funzionale; **`peek` richiesto ma assente** (2/3 metodi).
  - Task: `Classe Stack con capacity=3, metodi push/pop/peek, eccezioni personalizzate StackOverflowError e StackUnderflowError. Nel main: push di 4 elementi gestendo l'overflow stampando OVERFLOW=ok, poi pop di tutti e gestisci lo stack vuoto stampando UNDERFLOW=ok.`
  - Atteso: `OVERFLOW=ok` e `UNDERFLOW=ok`, niente traceback
  - Testa: OOP + eccezioni custom + doppio flusso di errore (difficile per un 3B)

- [x] **T9 — Decoratore per il tempo di esecuzione** ⚪ 🔶 avanzato ❌ **FAIL semantico (2/2, sistematico)**: ① **nessun decoratore** (concetto centrale del task assente, misura inline con `time.time()`); ② range sbagliato — run 1: `somma(1,2)+…+somma(9,10)`=55, run 2: `somma(1,2)`=3, invece di somma 1..100000; ③ run 1 anche unità errate ("ms" ma misura secondi). Sospetto ancoraggio al task-storico del progetto ("sommare 2 numeri") che trascina `somma(a,b)`. **Lezione**: i concetti astratti (decorator/closure) sono oltre la capacità del 3B; il matcher non li aggancia a nessuna skill.
  - Task: `Decoratore misura_tempo che stampa i millisecondi di esecuzione di una funzione. Applicalo a una funzione che somma i numeri da 1 a 100000 e stampa SOMMA=5000050000.`
  - Atteso: `SOMMA=5000050000` + una riga con tempo in ms
  - Testa: decorator + functools/closure (concetto astratto per modelli piccoli)

- [x] **T10 — Trasposta di una matrice** 🔹 🔶 avanzato ✅ **1 tentativo, PASS** (righe `[1, 4]` `[2, 5]` `[3, 6]`; logica vera: list comprehension con inversione `matrice[j][i]`, niente print cablati)
  - Task: `software per trasporre una matrice: matrice [[1,2,3],[4,5,6]] trasformata in [[1,4],[2,5],[3,6]], stampa ogni riga della trasposta su una riga separata.`
  - Atteso: righe `1 4`, `2 5`, `3 6` (o list comprehension equivalente verificata per valori)
  - Testa: logica su strutture bidimensionali (indice invertito — errore tipico dei piccoli)

---

## Risultati

| Task | Tentativi | py_compile | Output atteso | Esito |
|------|-----------|------------|----------------|-------|
| T1 | 1 | ✓ | 4 / 4 / 2 | ✅ PASS |
| T2 | 1 | ✓ | 77.00 + errore gestito | ✅ PASS |
| T3 | 1 (×2 run) | ✓ | LEN=2 ≠ 3, manca "a" | ❌ FAIL (semantico, sistematico) |
| T4 | 1 | ✓ | PALINDROMO=False (errato), frequenza sulla frase intera | ❌ FAIL (semantico) |
| T5 | 1 | ✓ | TROVATO assente; file creato in root (non in project/) | ❌ FAIL (semantico ×2) |
| T6 | 1 | ✓ | 12586269025 | ✅ PASS |
| T7 | 1 | ✓ | loop eventi offscreen OK (124), widget presenti | ✅ PASS (nota: niente QListWidget visibile) |
| T8 | 1 | ✓ | OVERFLOW=ok + UNDERFLOW=ok | ✅ PASS (nota: peek assente) |
| T9 | 1 (×2 run) | ✓ | SOMMA=55 poi 3; no decoratore; unità errate | ❌ FAIL (semantico, sistematico) |
| T10 | 1 | ✓ | righe 1 4 / 2 5 / 3 6 | ✅ PASS |

---

## Conclusioni della suite

**Risultato: 6/10 PASS (60%)** con qwen2.5-coder:3b, max-retries 3.

**Finding principale — il gate di verifica è cieco**: in tutti i 10 task l'executor ha
riportato `ok=true` al 1° tentativo (py_compile sempre OK) e **il 100% dei fallimenti è
semantico**, invisibile al gate attuale. Il correction loop non si è mai attivato: senza
una verifica sull'output, non c'è nulla da correggere.

### Ripartizione fallimenti
- **Sistematici (2/2 run identici)**: T3 (interpreta "aggiungi a, b, c" trattando "a" come variabile), T9 (concetti astratti — decoratore — oltre la capacità del 3B + ancoraggio al task "somma 2 numeri")
- **Stocastici/una tantum**: T4 (punteggiatura dal testo del task), T5 (percorso relativo + match esatto)

### Cosa passa bene (6/10)
- Statistiche, conversioni + gestione errori, Fibonacci memoizzato, Stack con eccezioni custom, GUI PyQt6 base, trasposta matrice — i task **concreti e deterministici**.

### Cosa fallisce
- **Elementi quotati ambiguamente** (T3), **punteggiatura nel testo del task** (T4), **multi-step file I/O con cwd** (T5), **astrazioni (decorator)** (T9).

### Raccomandazioni operative
1. **Estendere la verifica host**: oltre a `py_compile`, eseguire il programma e confrontare l'output con l'atteso quando il task lo specifica → il correction loop diventerebbe efficace (T3/T4/T5/T9 avevano output osservabile e sbagliato: correggibili al feedback).
2. **Formulare i task** con elementi quottati (`'a'`), niente punteggiatura ambigua, output atteso esatto nel testo.
3. **Concetti astratti**: fuori portata per i 3B — serve una skill dedicata o un modello più grande per T9-class tasks.
4. **File I/O**: usare percorsi assoluti o eseguire la verifica dentro la cartella progetto.

---

## Fase 2 — Skill aggiuntive + system prompt migliorato + contesto maggiorato

**Leve applicate** (a valle dei fallimenti Fase 1):
1. **3 nuove skill** in `SKILLS/`: `py-class-module` (OOP/dunder/eccezioni), `py-json-store`
   (persistenza JSON CRUD), `py-decorator` (timing decorator). Matcher verificato su tutti
   i 10 titoli: routing corretto.
2. **Disinnescato l'ancoraggio tossico**: T9 ("Decoratore … somma i numeri…") matchava
   `py-cli-script` (keyword "somma") il cui template era `def somma(a, b): return a + b`
   → ecco `somma(1,2)`. Template ora con placeholder presi dal task + regole quantità esatte.
3. **SYSTEM_DIRECT migliorato** (`CORE/skill_executor.py`): 7 regole concrete contro i
   fallimenti osservati (implementa TUTTO ciò che il task nomina; quantità/range esatti;
   elementi quottati = string literals; pulizia testo palindromo vs conteggio parole;
   match per sottostringa; marker di output esatti).
4. **Contesto maggiorato** (`CONFIG/config.toml` `[models.worker_coder]`): `num_ctx`
   4096 → **8192**, `num_predict` 512 → **1024** (file completi non più troncati; qwen2.5-coder:3b li regge).

### Risultati Fase 2 (seed=42, max-retries 3)

| Test | Fase 1 | Fase 2 | Run | Note |
|------|--------|--------|-----|------|
| T3 classe Collezione | ❌ sistematico 2/2 | ✅ **PASS** | 1 | LEN= 3, HAS=True, iterazione `a b c` completa |
| T4 palindromo+frequenza | ❌ | ⚠️ **metà** | 3 | `PALINDROMO=True` ✓ (regola punteggiatura); frequenza ancora sulla stringa fusa 3/3 (rimuove gli spazi PRIMA di split — limite 3B su operazioni a 2 stadi) |
| T5 rubrica JSON | ❌ ×2 difetti | ✅ **PASS** | 1 | `TROVATO=12345` + `rubrica.json` corretto (skill + regola substring; verifica con cwd=project/) |
| T9 decoratore | ❌ sistematico 2/2 | ✅ **PASS** | 1 | decoratore definito e applicato con `@`, `SOMMA=5000050000` esatto, tempo in ms |
| T1 (controllo) | ✅ | ✅ | 1 | nessuna regressione (4.0 / 4 / [2] — ora multimode) |
| T8 (controllo) | ✅ | ✅ (dopo 2 fix template) | 3 | regressione iniziale: try/except espulso a livello modulo + len() senza __len__ → template rafforzato (placeholder condizionale + regole) → OVERFLOW/UNDERFLOW=ok, peek presente |

### Bilancio Fase 2
- **9/10 task a pieni punti** (era 6/10) + T4 a metà (palindromo risolto, frequenza sistematica ❌).
- Le skill nuove hanno risolto **i 3 casi sistematici di classe diversa** (OOP, JSON, decorator) al **primo run**.
- Il system prompt esplicito ha risolto punteggiatura (T4-palindromo) e match substring (T5).
- **Conferma del finding Fase 1**: le 2 regressioni T8 intermedie erano **runtime-only**
  (NameError, TypeError) e `py_compile` le ha fatte passare → la verifica runtime con
  output atteso resta il pezzo che manca al correction loop.
- Il matcher delle skill è un'arma a doppio taglio: T9 prova che una skill SBAGLIATA
  (keyword parziale "somma") è peggio di nessuna skill — tenere i template generici
  e le keyword specifiche.

---

## Fase 3 — Verifica RUNTIME nel correction loop (chiudi il cerchio)

**Obiettivo**: il gate host diventa `py_compile → ESECUZIONE REALE`. Oggi py_compile
passa anche il codice che crasha a runtime (NameError/TypeError visti in Fase 2) e non
vede l'output sbagliato (T3 LEN=2, T5 TROVATO assente, T9 SOMMA=55).

### Progettazione
1. `extract_expected_markers(task_text)` — marker `NAME=value` nel testo del task
   (solo nomi MAIUSCOLI ≥2 char: `LEN=3`, `PALINDROMO=True`, `SOMMA=5000050000`;
   esclude input tipo `n=50` o valori in liste). Max 8, dedup.
2. `verify_runtime(code, path, markers, timeout=15)` — esegue con `sys.executable`,
   **cwd = cartella progetto** (i file relativi finiscono nel posto giusto), env
   `QT_QPA_PLATFORM=offscreen`. Fallisce su: ① exit ≠ 0 ② traceback in stderr
   ③ marker mancanti nel stdout (normalizzato `LEN= 3`→`LEN=3`).
   **GUI** (QApplication/mainloop nel codice): il timeout È il successo (entrata
   nel loop eventi).
3. `run_direct`: dopo py_compile OK → runtime check; fallimento runtime →
   `build_correction_prompt(..., direct=True)` (nuova variante del tail: NIENTE
   JSON ReAct, ma "ritorna il file corretto in un blocco ```python").
4. Risultato arricchito: chiave `stdout` (per CLI/debug).

### Task
- [ ] Implementazione: `extract_expected_markers` + `verify_runtime` + integrazione `run_direct` + tail direct in `build_correction_prompt`
- [ ] Test unità senza LLM: marker sui 10 titoli (attesi: T3 LEN+HAS, T4 PALINDROMO, T5 TROVATO, T8 OVERFLOW+UNDERFLOW, T9 SOMMA, altri vuoti); runtime ×5 (ok / NameError / marker mancante / GUI timeout=successo / loop infinito); loop FakeClient bad→good (attempts=2, correction prompt con errore runtime e niente JSON tail)
- [ ] Live (setup completo Fase 3): T3, T4, T5, T9 → attesi PASS attempt 1
- [ ] **Demo del loop**: T9 SENZA la skill `py-decorator` (condizione Fase 1 + verifica runtime) → attempt 1 deve FALLIRE runtime (SOMMA sbagliata) → il correction prompt la può aggiustare?
- [ ] Risultati + bilancio finale in questa sezione

### Risultati Fase 3

**Implementato**: `extract_expected_markers()` (marker `NAME=value` dal task, solo
nomi MAIUSCOLI — `n=50` e liste esclusi per design), `verify_runtime()` (esecuzione
con cwd=progetto, QT offscreen, exit/traceback/marker; GUI: timeout=successo;
ANSI dei traceback Python 3.13+ ripuliti), integrazione in `run_direct` con tail
direct (`build_correction_prompt(..., direct=True)` — niente JSON ReAct) e chiave
diagnostica `history` nel risultato.

- [x] Implementazione — test unità 12/12 verdi (marker ×10 titoli, runtime ×6 casi, loop FakeClient attempts=2 con correzione)
- [x] Live setup completo: **T3 ✅ 3 attempt** (gate ha respinto 2 output sbagliati prima del verde) · **T4 ✅ 3 attempt** (attempt 1 = `PALINDROMO=False`, il fallimento sistematico Fase 1 → catturato → corretto!; attempt 2 NameError → catturato) · **T5 ✅ 1 attempt** · **T9 ✅ 1 attempt** (`SOMMA=5000050000`)
- [x] Demo loop (T9 **senza** skill = condizione Fase 1): attempt 1 template mal riempito → py_compile ❌ · attempt 2 NameError → runtime ❌ · attempt 3 perde il SOMMA → runtime ❌ "output atteso mancante: SOMMA=5000050000" · **ok=false ONESTO dopo 3 correction** (in Fase 1 la stessa condizione = `ok=true` con SOMMA=55 sbagliato e nessuno che lo vedeva)
- [x] Regressioni: **T1 ✅ 1 attempt** (via senza marker) · **T7 ✅ 1 attempt** (via GUI: timeout=successo nel loop)

### Bilancio Fase 3 — cerchio chiuso
1. **Il correction loop ora si attiva davvero**: prima non partiva MAI (py_compile passava sempre); ora cattura crash runtime (NameError/TypeError visti in Fase 2) e output sbagliato (PALINDROMO=False, SOMMA=55).
2. **T4-palindromo è stato AUTO-CORRETTO dal feedback runtime** — fallimento sistematico Fase 1 → risolto in 3 attempt senza toccare skill né prompt.
3. **Il sistema non mente più**: ok=true solo quando il programma gira E produce i marker attesi; ok=false con la lista precisa di cosa non andava (history).
4. **Limite onesto del 3B nell'autocorrezione**: senza skill, 3 tentativi non bastano (deriva tra correzioni); con la skill giusta: 1 attempt. La verifica runtime dà il feedback — la capacità di sfruttarlo dipende dal modello.
5. **T4-frequenza resta fuori dai marker** (il criterio "parola più frequente" è mal definito: la frase non ha parole ripetute) — classificata ⚠️ come in Fase 2.
6. **Bug fissato durante l'implementazione**: path relativo + cwd → percorso raddoppiato (risolto con `.resolve()`); ANSI dei traceback Python 3.13+ sporcavano il correction prompt (stripping aggiunto).

**Score finale della suite: 9/10 PASS + ½ (T4-palindromo ora auto-corretto dal loop; T4-frequenza l'unico residuo, criterio mal definito) — su 13 esecuzioni totali di Fase 3: 6 ok, 1 fallimento onesto dichiarato (demo senza skill), 0 bugie.**

---

## Fase 4 — Mappa del codice in un database (idea utente: "un agente che usa un DB per mappare il codice")

**Implementato**: `CORE/code_map.py` — AST (stdlib, zero dipendenze) → SQLite per
progetto in `<progetto>/.byteswarm/codemap.db`, rebuild **incrementale** per mtime
(solo i file cambiati vengono riparsati, i file spariti vengono ripuliti).

- **Simboli mappati**: classi (con metodi raggruppati), funzioni, firme senza default,
  docstring (prima riga), riga; chiamate (chiamante→chiamato, per il futuro grafo) e import.
- **Nel prompt**: sezione `## PROJECT MAP — RIUSA questi nomi e firme` (cap 1200 char),
  con il file target **escluso** (sta per essere riscritto: i suoi simboli sono rumore).
- **Gate STATICO nel loop** (prima del runtime): `check_code_names()` = scope analysis
  approssimata che becca i nomi **usati ma mai definiti/importati** (NameError latenti
  come il `coll.pop()` a livello modulo di Fase 2) SENZA eseguire; il correction prompt
  riporta anche i "Simboli disponibili nel progetto". Le annotazioni pigre di Python 3.14
  (PEP 649) sono escluse (non valutate a runtime → niente falsi positivi).
- **Skill aggiornate**: regola "se la PROJECT MAP ha già la classe/funzione richiesta,
  IMPORTA e usa, non ridefinire".

### Test
- [x] Unità: rebuild ×2 file con classi/metodi/funzioni/import · incrementale (solo file cambiato) · PROJECT MAP con exclude · check_code_names ×7 (good / T8-coll / helper inesistente / import mancante / annotazioni pigre / scope for-with-except-lambda-comprehension)
- [x] Integrazione FakeClient: prompt con PROJECT MAP ✓ · correction con STATIC CHECK + simboli disponibili ✓ · progetto vuoto → niente sezione ✓
- [x] Live: task di RIUSO su progetto esistente (`utils.py` con `class Statistiche`)

### Risultati live (task di riuso su progetto esistente)
| Run | attempts | Comportamento |
|---|---|---|
| 1° | 2 ✅ | map ancorata il **nome** (`Statistiche`, non reinventato) MA classe **riimplementata** in main.py; attempt 1 senza metodo `media` → gate runtime → corretto |
| 2° (dopo regola riuso) | 2 ✅ | idem — il 3B segue il template della skill più che la regola di import |
| T6 controllo | 1 ✅ | nessuna regressione con PROJECT MAP nel prompt (F(50) esatto) |

### Bilancio Fase 4
1. **Il gate statico è immediatamente utile**: NameError latenti catturati prima di girare, correction prompt che dice ANCHE quali simboli esistono davvero.
2. **La mappa nel prompt previene le allucinazioni di API inesistenti** — l'ancoraggio del nome ha funzionato al primo colpo.
3. **Riuso vero (import) vs ridefinizione**: sul 3B il template della skill pesa più della regola di riuso — resta un limite di capacità, non di pipeline; con modelli più grandi la mappa paga di più (ed è il pezzo chiave per multi-file).
4. **Base pronta per il futuro**: il grafo chiamate chiamante→chiamato è già nel DB (per decomposizione task e impatto-modifiche), la mappa è il punto di aggancio naturale per il retrieval su progetti grandi.

---

## Fase 5 — Libreria skill completa (pattern ricorrenti dove i 3B falliscono da zero)

**Leva**: una skill = ricetta che riduce le scelte libere (T9: fallimento sistematico 2/2 → PASS al 1° run con la skill giusta). Nuove skill in `SKILLS/`:

- [x] `py-inheritance` — ereditarietà/super/override
- [x] `py-generators` — yield/stream pigri (mai lista in memoria se non chiesto)
- [x] `py-context-manager` — `__enter__/__exit__` con firma esatta, `return False` (non ingoiare eccezioni)
- [x] `py-threading` — Thread+join+Lock (stato condiviso protetto, mai ordine assunto)
- [x] `py-argparse` — CLI argomenti (mai parsing manuale di sys.argv)
- [x] `py-regex` — pattern raw string, findall/search/match
- [x] `py-http-api` — urllib con timeout + gestione URLError/HTTPError (mai crash di rete)
- [x] `py-unittest` — TestCase con assert di successo E di errore
- [x] `py-text-analyze` — il pattern T4: estrazione parole via regex (punteggiatura sparita per costruzione) PRIMA del conteggio + palindromo (chiude l'ultimo gap della suite)
- [x] Test matcher: 21/21 — le nuove skill prendono i LORO titoli senza rubare i vecchi (T1→py-cli-script, T3/T8→py-class-module, T7→pyqt6, T5→py-json-store, T9→py-decorator). **Tie-break migliorato in `CORE/skills.py`**: a parità di score vince la skill con la keyword matchata più lunga (più specifica) — prima il pareggio 45–45 generatore/console-script si risolveva per ordine alfabetico
- [x] Live: task generatore, task threading, T4-frequenza con la nuova skill (risultati sotto)

## Fase 6 — Routing SEMPLICE per complessità

**Leva**: task complessi → modello più capace SE installato, altrimenti fallback automatico.

- [x] `CORE/routing.py`: `estimate_complexity(text)` + `route_model_key()` (heavy solo se livello ALTA **e** installato — fail-open al modello base) + `explain()` per il log
  - Regola semantica: **ALTA** = ≥1 concetto ADVANCED (fallimento sistematico provato: T9 decoratore 2/2) **oppure ≥3 MEDIUM** (multi-concept, lezione T5) · **MEDIA** = 1–2 MEDIUM o testo >220 char · **BASSA** = nessun segnale
  - Matching a **confine di parola** (`(?<!\w)kw(?!\w)`): niente doppi conteggi ("decoratore" ≠ "decorator"); ricorsione/memoizzazione ESCLUSE (T6 fibonacci passa sul base al 1° tentativo in due fasi — concetto gestito)
- [x] `CONFIG/config.toml`: sezione **`[complexity_routing]`** (enabled, `heavy_model = "worker_coder_big"`) + `[models.worker_coder_big]` = `kirito1/qwen3-coder:4b`. ⚠️ NON `[routing]`: quella sezione era GIÀ presente (orchestrator: direct/ReAct + `direct_keywords`) — il primo run live è crashato su "Cannot declare routing twice"; rinominata per non toccare lo schema esistente
- [x] Integrazione `run_direct`: routing attivo SOLO in live (`client is None`; client iniettato = test → routing off, determinismo); TUTTI i return arricchiti con `model` (chiave effettiva) e `route` (decisione leggibile); log `[routing] …` via logging
- [x] Test: complessità su tabella (T1 bassa, T2 bassa, T3 media, T5 alta, T6 media, T7 media, T8 media, T9 alta, THR alta, GEN alta, banale bassa, lungo media) · route 4 regole (alta+installato→heavy, alta+non installato→base, media→base, disabled→base, senza config→base) · matcher 21/21 invariato · integrazione FakeClient (routing OFF, model/route nel dict)

### Risultati Fasi 5–6

**Tutti i test verdi**: matcher 21/21 · routing 12+6 casi · integrazione FakeClient · regressione 35/35 + 7/7 · 14 skill caricate.

**Run live** (worker_coder = qwen2.5-coder:3b · worker_coder_big = kirito1/qwen3-coder:4b, **ora installato** ⬇✓):

| Task | Route | Modello | Tentativi | Esito |
|---|---|---|---|---|
| Generatore (yield, TOT=110) | alta → heavy | **worker_coder_big** | 2 | ✅ PASS — yield vero, while lazy, `TOT=110` |
| Threading (2 liste, Lock, TOT=36) | alta → heavy | **worker_coder_big** | 3 | ✅ PASS — Thread+Lock+join corretti, `TOT=36` |
| T4 palindromo+frequenza (titolo originale) | bassa → base | **worker_coder** | **1** | ✅ PASS — `PALINDROMO=True` + frequenza su parole VERE ("i"), gap sistematico della suite CHIUSO |

**Scoperte dal vivo (→ skill raffinate)**:
1. **Il 4B chiacchiera**: qwen3-coder:4b al 1° tentativo produce testo ("Okay, let's tackle…") senza fence → `py_compile` lo becca → correction → codice pulito. Il gate host è ciò che rende usabile un modello che non obbedisce al system prompt.
2. **Placeholder verbosi = trappola per il 4B**: il 4B ha copiato LETTERALMENTE `{{ MARKER, e.g. f"TOT={sum(results)}" }}` due volte di fila (il 3B li reggeva). Fix su 6 skill (threading/argparse/inheritance/regex/http-api): placeholder nudo `{{ MARKER }}` + regola "Replace EVERY {{...}} placeholder" con esempio concreto. Il threading live è passato con il template raffinato.
3. **T4 chiuso con la skill, sul 3B, senza routing**: la ricetta `py-text-analyze` (estrazione parole PRIMA del conteggio) converte l'ultimo fallimento sistematico della suite in PASS al 1° tentativo — stessa dinamica di T9 in Fase 3.

**Bilancio**: skill = giù in complessità percettiva; routing = su in capacità del modello; il gate (compile→static→runtime) è il componente che tiene insieme i due nei due sensi. Restano per Fase 7: regressione completa suite T1–T10 sul 4B (ora fattibile), routing complesso su grafo del code_map.

## Fase 7 — Routing COMPLESSO (grafo del code_map)

**Idea (utente)**: usare il DATABASE della mappa (Fase 4) per decidere il modello in base all'IMPATTO REALE del task sul progetto, non solo alle parole del titolo.

- [x] **Impatto dal grafo** — `estimate_impact(text, project_root, exclude_files)` in `CORE/routing.py`:
  - simboli citati nel task (match a confine-parola, case-sensitive, min 3 char) contro il DB
  - file toccati = definizione ∪ chiamate dirette (file target escluso: sta per essere riscritto)
  - profondità BFS a valle (callee→caller, cap 3) + flag `tests` (un test che chiama un chiamante copre il simbolo citato)
  - livello: `''` (nessuna citazione) · `media` (1 file) · `alta` (≥2 file OR profondità ≥3)
- [x] **Regola di decisione**: livello finale = MAX(keyword, impatto) + **isteresi** (una volta heavy, `media` resta heavy; solo `bassa` torna al base — niente sfarfallio tra task consecutivi). `reset_hysteresis()` per test/batch
- [x] **Integrazione**: `run_direct(enable_routing=None)` — auto: attivo con client None (CLI) **o ModelClient reale** (worker GUI, che ora passa `self.models`); finto da test → OFF (determinismo). `route_model_key()` restituisce `(key, level, decisione_leggibile)`; il worker la registra in log + evento memoria (`model=` e `route=` nel meta)
- [x] Accessor `code_map.calls()` per il grafo chiamate
- [ ] **Valutazione**: suite T1–T10 su entrambi i modelli (stessa pipeline, routing OFF) → `scripts/suite_compare.py` → `state/suite_compare/results.json` *(in esecuzione)*

**Prova live (routing attivo)**: task di riuso su `PR_TEST_progetto` — `route: "complessità media → worker_coder | impatto media (1 file, profondità 0, simboli citati: Statistiche, media, mediana)"` — il grafo ha visto i 3 simboli in `utils.py`, il task è restato sul base, PASS al 1° tentativo.

### Risultati suite comparativa T1–T10 (routing OFF, stessa pipeline)

`state/suite_compare/results.json` · runner `scripts/suite_compare.py` · tentativi max 3

| Task | 3B (worker_coder) | 4B (worker_coder_big) | Delta tempo |
|---|---|---|---|
| T1 statistiche | ✅ 2 att, 22 s | ❌ 3 att, 262 s | ×12 |
| T2 convertitore | ✅ 1 att, 10 s | ✅ 2 att, 165 s | ×17 |
| T3 Collezione | ✅ 1 att, 9 s | ❌ 3 att, 301 s | — |
| T4 palindromo+frequenza | ✅ 1 att, 11 s | ❌ 3 att, 315 s | — |
| T5 rubrica JSON | ✅ 1 att, 10 s | ✅ 1 att, 56 s | ×5 |
| T6 fibonacci | ✅ 1 att, 8 s | ✅ 3 att, 249 s | ×32 |
| T7 GUI PyQt6 | ✅ 1 att, 27 s | ✅ 3 att, 324 s | ×12 |
| T8 Stack+eccezioni | ✅ 2 att, 23 s | ❌ 2 att, 405 s | — |
| T9 decoratore | ✅ 1 att, 11 s | ❌ 1 att, 300 s (timeout LLM) | — |
| T10 matrice | ✅ 1 att, 7 s | ❌ 1 att, 300 s (timeout LLM) | — |
| **Totale** | **10/10 ✅ · 139 s** | **4/10 ✅ · 2.678 s** | **×19 più lento** |

**Tassonomia fallimenti 4B** (ogni fallimento ONESTAMENTE beccato dai gate — mai codice rotto passato):
1. **Prosa prima del codice** ×4 (T1/T3/T4/T8 @1: "Okay, let's tackle…") → **fixata**: SYSTEM_DIRECT "la prima riga DEVE essere ```python" + `extract_code` tronca la prosa alla prima riga Python
2. **Placeholder copiato letterale** ×1 (T4@2: `{{ PRINT THE EXACT MARKERS }}`) → **fixata**: py-text-analyze usa righe-commento inerti al posto di placeholder in prosa
3. **try senza except** ×1 (T3@2) → **fixata**: py-class-module con `except Exception` di default + regola "mai cancellare un except"
4. **Classe senza istanza** ×1 (T1@2: `Statistiche.media(lista)`) → **fixata**: SYSTEM_DIRECT regola 8 "usa un'ISTANZA"
5. **Timeout LLM** ×3 (T8@2, T9@1, T10@1 — 300 s esatti = limite client) → **infrastruttura**: la generazione 4B non finisce entro 300 s su questa macchina (throttling osservato: T8 405 s, ventola rallentata — conferma utente); temperatura ora 52–64 °C

**Conclusione onesta**: su QUESTA macchina (4 GB, throttling sotto carico) il 4B NON è un heavy valido: 4/10 vs 10/10, ×19 più lento, e va in timeout sui task lunghi. Il 3B + skill + gate host è il sistema migliore. Candidato heavy alternativo: `granite4:7b-a1b-h` (MoE ~1B attivi, 4,2 GB) → verdict sotto.

### Spot-check heavy: 4B vs granite4 (codice nuovo, post P1–P5)

`state/suite_compare/spotcheck.json` · runner `scripts/spotcheck_heavy.py` · routing OFF

| Run | Esito | Tempo | Note |
|---|---|---|---|
| 4B / T9 (decoratore) | ❌ FAIL 1 att | 304,6 s | timeout LLM ~300 s ANCORA con il system prompt nuovo: la generazione 4B non finisce su questa macchina |
| granite4 / T9 | ✅ ok 1 att | **31,2 s** | `SOMMA=5000050000` corretto + tempo di esecuzione stampato |
| granite4 / T1 (statistiche) | ✅ ok 1 att | **10,1 s** | `Media: 4.0 Mediana: 4 Moda: [2]` — il 3B aveva fatto T1 in 2 tentativi (22 s) |

**Verdict `[complexity_routing]`**: `heavy_model = "worker_granite"` (SCELTO e impostato in config.toml). granite4:7b-a1b-h è veloce quanto il base (10–31 s), corretto al 1° tentativo su entrambi gli spot, e passa dove il 4B non riesce nemmeno a finire la generazione. RAM: 7,6 GB totali, rotazione ollama scarica il modello precedente → 4,2 GB ci stanno (verificato live, nessun thrashing). Il 4B `kirito1/qwen3-coder:4b` resta in config come `[models.worker_coder_big]` NON heavy (disattivabile/installabile dal pannello, timeout per-modello 600 s).

**Audit pattern-trappola skill (post P3/P5)**: scansionate tutte le 14 skill di `SKILLS/` — nessun altro placeholder condizionale-in-prosa (`{{ ONLY IF … }}`, `{{ PRINT THE … }}`); i rimasti sono tutti segnaposto legittimi da riempire o commenti inerti. Trappola estinta.

### Ottimizzazioni skill/prompt/tools (dalla diagnosi dei fallimenti)

**P1 — SYSTEM_DIRECT (prompt)**: il 4B brucia tentativi su prosa iniziale ("Okay, let's tackle…") senza fence → regola dura "la PRIMA riga dell'output DEVE essere ```python" + "un {{...}} lasciato nel codice è un errore di sintassi: sostituiscili TUTTI".
**P2 — extract_code (tool)**: niente fence + prosa prima → oggi il testo intero va in py_compile e muore. Fix: nel fallback senza fence, tronca tutto ciò che precede la prima riga Python reale (`^(import |from |def |class |print\()`).
**P3 — py-text-analyze (skill)**: la riga-placeholder `{{ PRINT THE EXACT MARKERS THE TASK REQUESTS }}` è stata copiata LETTERALMENTE dal 4B → sostituirla con un print concreto + regola.
**P4 — regola istanza (prompt)**: il 4B chiama `Statistiche.media(lista)` senza istanza (AttributeError) → in SYSTEM_DIRECT: "se il PROJECT MAP ha una class, usa un'ISTANZA (obj = Class(); obj.method())".
**P5 — try/except fragili (skill)**: T3@2 "expected 'except' or 'finally'" → rinforzare il template py-class-module con il blocco try/except completo da non spezzare.
**P6 — timeout per-modello (tool, `CORE/ollama_client.py`)**: i 3 timeout T8/T9/T10 erano `LLM call failed: timed out` a 300 s esatti (limite globale `[ollama].request_timeout`). Fix: ogni `[models.*]` può ora avere `timeout = N` che sovrasta il default (`model_cfg.get("timeout", self.timeout)` in `call()` e `call_streaming()`); `worker_coder_big` → 600 s. Unit + regressione verdi.

**Stato**: P1–P6 ✅ applicati e verificati (unit + regressione 35/35 e 7/7 + spot-check live). Audit skill: nessun'altra trappola presente.
