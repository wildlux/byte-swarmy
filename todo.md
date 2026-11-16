# TODO — BYTE-SWARMY

> **Flusso documentale**: il task nasce qui → si esegue → si registra in
> `DOCS/IMPLEMENTED.md` (Cycle N) → si cancella da qui.
>
> **Storia completa**: Fasi 1–9, M1–M10, P1–P15, suite T1–T10 e T11–T21,
> routing, code map, clarifier, chiusura orchestratore — tutto travasato in
> `DOCS/IMPLEMENTED.md` (Cycles 13–22). Report consolidato: `REPORT.md`.

Stato: **tutto il piano approvato è completato** (le 85 voci del vecchio
todo sono registrate in `DOCS/IMPLEMENTED.md`; qui restano solo i task aperti).

---

## Aperti

### 📅 Domani (2026-11-17) — ordine di esecuzione concordato

Macchina fredda: prima il benchmark, poi il resto. Ogni step con la
regola termica (stadiale, `--cooldown 30 --thermal-limit 60`).

1. [~] **`tools/verify_cycle.sh` — script del ciclo di verifica standard**
      (furbata onesta: automazione deterministica, NON un LLM che genera
      comandi). Un solo comando che incapsula la sequenza ripetuta a ogni
      ciclo: `py_compile` dei file toccati → test mirati → boot smoke
      (`state/pause.flag` + `CORE.orchestrator`). Zero LLM, zero calore,
      ~18s fissi, stessa disciplina rigorosa. Uso futuro: i cicli si
      verificano con `./tools/verify_cycle.sh <file_modificati...>`
      invece di 3-4 comandi separati. **Creato e bash-checked (Cycle 66);
      TODO: prima esecuzione end-to-end.**
2. [~] **Benchmark di validazione della corsia veloce (fast lane)** —
      ▶️ **IN ESECUZIONE con protocollo sessioni fredde** (opzione A,
      scelta utente: la fast lane "è di un'utilità disarmante"). Driver
      `tools/bench_cold_sessions.py`: 1 task per sessione, macchina
      fredda ≤45.5°C prima di ogni sessione, 60°C mai sforato. Il
      **piano d'azione con criteri di verdetto pre-scritti** è in
      `DOCS/BENCH.md` § "PIANO D'AZIONE — Cycle 66" (living doc, si
      aggiorna a fine driver). Contesto Cycle 66: 2/2 run abortite su
      ext-01 → benchmark completo in una sessione impossibile; pausa
      adattiva implementata e testata; `enabled = false` (rollback
      fatto), fix elegibilità committato.
3. [ ] **Micro-ciclo config**: `num_ctx` planner 3072 → 2048 (item #5
      efficientamento) + verifica se Timestral/SystemMonitor/Lifecycle
      hanno già toggle config (item #4). Config-only, zero Ollama.
      + **caching**: valutare `[hardware].keep_alive_sec` esplicito
      (es. 300s) per tenere worker_coder caldo tra task — l'unica
      manovra KV-cache gratuita su Ollama (costo: ~2GB RAM residenti;
      la KV cache quantizzata q8_0 + FA è già attiva, Furbata D).
      llama-server diretto con --prompt-cache resta FASE 3 (item #6),
      da misurare solo dopo l'esito della fast lane.

### Test agentico — programmino Qt/PyQt6 via swarm (Cycle 50)

- [ ] **Test agentico Qt/PyQt6**: far creare al swarm un programmino PyQt6
  semplice (es. Finestra + QPushButton + label) come prova pratica della
  capability di scrittura codice; misura se il risultato è "funzionante".

### Capability agentica — test→benchmark feedback + doc summarization (Cycle 51)

- [ ] **Capability: test execution → benchmark feedback**: estendere il
  flusso worker (`run_test_suite` → `_summarize_result`) per far sì che i
  risultati dei test vengano riusati come feedback di benchmark/decisione
  nel task loop.
- [ ] **Capability: doc reading → summary**: aggiungere al worker un tool di
  lettura documenti (es. PDF via bash/pdftotext) + riassunto come contesto,
  invece del documento intero.

- [x] **Middle capability: escalation 3B→4B** ✅ Cycle 52: fallback del
  worker_coder (junior) → `worker_coder_big` (middle, qwen3-coder:4b) invece
  di scendere al più piccolo (worker_general 1.5B). Salto di capacità al
  tier "middle".

### Tool LLM — diario di bordo (Cycle 52+)

- [x] **Tool `diary_llm`** ✅ Cycle 53: nuovo tool che lascia un diario di
  bordo (problem, context, attempts, failures, learnings, optimization) al
  termine di un task; persistenza in `state/diary/`. Implementato con scrittura
  sicura + sanitizzazione task_id. ✅ Cycle 53.
- [ ] **Diary: DB vs file**: decidere DB (SQLite + query via API/socket) vs
  file markdown per il diario LLM; oggi il file basta per il contesto
  self-optimization, il DB solo per analytics/query strutturate.

### Efficientamento energetico (proposto dopo il benchmark Cycle 59)

Ottimizzazioni per ridurre il consumo energetico, in ordine di impatto
decrescente. Il benchmark ha dimostrato che il harness è 13.6x più lento
del modello nudo (192s vs 14s per task) — la vera leva è la semplificazione.

### Regola termica permanente (🆕 Cycle 65)

> **Mini-test, mai generazioni monolitiche.** Ogni test che chiama l'LLM
> (benchmark, e2e worker, test generation) si fa a STADI brevi con verifica
> host-side tra uno e l'altro, per non surriscaldare il portatile:
> 1. **Scheletro** (classe vuota / funzioni test_* con `pass`) →
>    `pytest --collect-only` o `py_compile` (~gratis, zero LLM);
> 2. **Definizioni** (corpi minimi, assert essenziali) → verifica;
> 3. **Implementazione completa** → mai in un'unica generazione lunga.
>
> Ogni stadio genera ≤ ~300 token. Nel benchmark: un task = uno stadio,
> con `--cooldown 30 --thermal-limit 60` tra task. Errori di import o di
> struttura si scoprono allo stadio 1 SENZA pagare le generazioni
> successive. Implementata in `CORE/test_generator.py` (scheletro →
> corpi, collect-check tra gli stadi).

1. [~] **Eliminare il correction loop (single-shot)**: sostituire il ReAct
      loop (10 step) con single-shot (prompt → genera → compila → retry una
      volta). Riduzione consumo stimata ~90%. ✅ **Cycle 64** — corsia
      veloce implementata (`CORE/worker.py: _execute_fast_lane`), prompt
      nudo del benchmark, max 2 tentativi, difese deterministiche intatte
      (AST scanner, safe path, runtime verifier). **Default OFF** in attesa
      del benchmark di validazione a macchina fredda (regola "measure,
      don't add"). Attivazione: `[fast_lane] enabled = true` in config.toml.
2. [ ] **Ridurre il prefill del worker**: rimuovere tool non usati dal prompt,
      comprimere descrizioni. Riduzione stimata ~30-50% per step.
3. [x] **Consolidare i timer della GUI**: ✅ **Cycle 63** — un solo
      heartbeat (1s) al posto di 5 timer (500ms/1500ms/1500ms/3000ms);
      subprocess costosi (nvidia-smi + ollama ps) da ogni 1.5s a ogni 3s,
      zoom catch-up solo se zoom != 100, timer SIGINT 200ms → 500ms.
      Stima ~5-10% CPU costante in meno a riposo.
4. [ ] **Spegnere componenti inutili via config**: disabilitare Timestral,
      SystemMonitor, LifecycleManager quando non necessari.
5. [ ] **Ridurre num_ctx del planner**: 3072 → 2048 (come orchestrator).
6. [ ] **Caching KV cache (llama.cpp)**: salvare il cache del system prompt
      e riutilizzarlo tra chiamate. Richiede passaggio a llama.cpp diretto.
7. [ ] **Batch scritture disco**: batch delle write_file, commit solo alla
      fine del task.
  ✅ **Cycle 62** (semplificazione Fase 1): inventario CORE/, rimossi 3 moduli
  orfani (`sml_database`, `preflight_cli`, `loop_detector` fuso in
  `worker.py`), spostato `example_mcp_server.py` in `tests/`. CORE/ scende
  da ~50 a ~47 file. Nessuna metrica peggiorata (270 passed, 1000 subtests,
  boot smoke OK). Regola rispettata: Timestral LLM Tuner non toccato.

### Miglioramenti senior da applicare (dalla code review) — priorità decrescente

Interventi strutturali che chiudono i gap identificati; non sono "feature
nuove", ma migliori al sistema:

1. [x] **Classificatore di rischio deterministico + blocco umano per task ad
      alto impatto**: ✅ **Cycle 56**: modulo `SAFETY/risk_classifier.py` con
      regole deterministiche (path toccati → alto; diff > 50 righe / > 3 file →
      alto; refactoring architetturale / cambio API pubblica → alto); task
      `high`/`critical` → `awaiting_human_approval` + GUI prompt di
      conferma; log in `logs/security.log`.
2. [x] **Runtime verification harness per i diff generati**: ✅ **Cycle 56**:
      dopo ogni `write_file` e prima dell'audit, smoke test sul file
      (py_compile; test via pytest); per GUI/orchestrator: avvio headless
      controllato + timeout (boot smoke); su fail → feedback specifico nel
      correction loop. Modulo `CORE/runtime_verifier.py`.
3. [x] **Test generation per i nuovi percorsi di esecuzione**: ✅ **Cycle 57**:
      al worker, per ogni nuovo percorso scritto (write_file su modulo .py),
      generare + eseguire test di regressione via pytest; se non generabile o
      se fallisce → feedback specifico nel correction loop. Modulo
      `CORE/test_generator.py`, iniettato in `CORE/worker.py` (`execute`).
4. [x] **Semplificazione architetturale**: ✅ **Cycle 58**: inventario CORE/MONITORing,
      fusione `exception_handler.py` + `state_recovery.py` → `CORE/resilience.py`;
      rimossi i 4 moduli orfani (non importati da nessun codice di produzione)
      `exception_handler`, `state_recovery`, `benchmark`, `MONITORING/predictive`.
      Import nei test aggiornati (`test_usability_hardcore` ora importa da
      `CORE.resilience`). Nessuna metrica peggiorata (tutte le suite verdi).
5. [x] **Benchmark esterni e validazione indipendente**: ✅ **Cycle 59** (eseguito e misurato):
      nuovo modulo `CORE/external_benchmark.py` con 8 task di refactoring atomici
      su `bench_target/` (mini-repo esterno). Dual mode: harness vs modello nudo.
      **Risultato onesto**: modello nudo migliore del harness (50% vs 12.5% primo
      colpo; 14s vs 192s medio/task). Criterio di uscita Fase 0 NON raggiunto:
      tempo umano netto negativo → fermarsi e semplificare prima di aggiungere
      feature. Report in `DOCS/BENCH.md`, JSON in `state/benchmarks/`.
      Test: `tests/test_external_benchmark.py` (11 test, mock senza Ollama).
6. [x] **Fuzzing mirato sulla sicurezza**: ✅ **Cycle 60**: modulo
      `tests/fuzz_security.py` con generatore custom (seed fisso) che fuzza
      `validate_bash_command` (metacaratteri shell offuscati, path traversal
      su comandi allowlistati, comandi fuori allowlist), `ToolSet.write_file`
      (path traversal, null byte, path troppo lungo, nomi strani dentro
      project/) e `MCPClient._parse_tool_result` (payload mancanti, troppo
      lunghi, tipi sbagliati, JSON malformato, None). Invariante: nessun
      bypass di sicurezza, nessun crash non gestito. Nessun regression test
      aggiuntivo necessario in test_security.py (nessun bypass trovato).
7. [x] **Migliorare l'esperienza utente della GUI per il flusso di approvazione
      umana**: ✅ **Cycle 61**: coda approvazioni (`awaiting_human_approval`)
      dentro `GUI/task_scheduler_panel.py` con titolo, livello di rischio e
      motivo (parsed dal reason del risk gate), pulsanti Approva/Rifiuta con
      feedback/Sospendi per task singolo, approvazione in blocco solo per
      rischio basso/medio (con conferma esplicita per alto/critico), log delle
      azioni utente in `logs/user_actions.log`. Notifica badge `🔒 N` sulla top
      bar di `GUI/control_center.py` (aggiornata ogni 3s) quando ci sono
      approvazioni in sospeso. Funzioni di transizione stato in
      `GUI/task_queue.py`: `approve_task`, `reject_task`, `suspend_task`.

### Responsive
*(nessun item aperto — T-R3 e gap vuoto risolti nel Cycle 29)*

---

## 🆕 Token reduction (nuove tecniche — proposte 2026-11-14)

Priorità 1–8 per ridurre il prompt del worker di Byte-Swarmy (~4–5KB → ~1.5–2KB/step,
guadagno 50–60%, senza perdita di funzionalità). Vedi conversazione per dettagli.


Ordine consigliato: T1 → T2 → T4 → T5 → T9 → T3 → T7 → T8 → T6 (ultimo, sforzo alto) — TUTTI IMPLEMENTATI tranne T6.

---

## 🆕 Token reduction (nuove tecniche — avanzate, proposte 2026-11-14)

Priorità per ridurre ulteriormente il prompt del worker (~2KB → ~1KB/step) e il tempo
di inferenza. Vedi conversazione per dettagli.


Ordine consigliato: T10 → T11 → T13 → T15 → T12 → T14 → T16 → T17 (ultimo, sforzo alto).

---

## 🆕 Token reduction (nuove tecniche — avanzate 2, proposte 2026-11-14)

- [~] **T23 — KV cache condiviso tra task simili**: NON FATTO — fuori
  scope (Ollama già gestisce il KV cache del prefisso).
- [~] **T24 — Batch tool calls**: NON FATTO — fuori scope (guadagno
  reale ma refactor+rischio ordering alti).
- [~] **T25 — Prompt pruning per rilevanza**: NON FATTO — fuori scope
  (complessità alta, guadagno variabile).
- [~] **T26 — Quantizzazione prompt (llama.cpp)**: NON FATTO — fuori
  scope (richiede bypass Ollama con llama-cpp-python).

Ordine consigliato: T18 → T19 → T20 → T21 → T11/T12 (già in lista) →
T22 → T24 → T23 → T25 → T26 (ultimo, sforzo alto).

> **CHIUSO (2026-11-14)**: programma token reduction terminato con 22/26
> tecniche implementate (T1–T22). T23–T26 spostate in fuori scope:
> guadagno marginale o sforzo/rischio non giustificato sull'architettura
> attuale (vedi sezione Fuori scope).

---

## 🔧 Manutenzione & strumenti


## Regola workflow (da Cycle 46b)
- **Ogni report/misura va documentato in `DOCS/`** (es. `DOCS/BENCH.md`
  per i bench, `DOCS/IMPLEMENTED.md` per i cicli); i JSON grezzi restano
  in `state/benchmarks/` (gitignored). Nessun report solo in chat.
  Regola anche in `AGENT.md` §Regole (punto 6).

## Furbate candidate (verificate contro il codice, Cycle 47?)
Ottimizzazioni proposte dopo la prima misura bench — ognuna con il punto
del codice reale su cui agire. Da scegliere con l'utente:
(nessuna aperta: menu chiuso — vedi "Furbate completate (menu chiuso)")

### Bench post-furbate (Cycle 47b)

### Furbate completate (menu chiuso)

**Menu furbate (A–F): COMPLETO — tutte le furbate implementate e misurate.**

---

## Fuori scope (per scelta/limiti hardware)
- Skill worker `pyqt6-graphics` / `pyqt6-network`: fuori scope — il 3B non
  le regge; la GUI si fa a mano o con `pyqt6-basics`.
- Token reduction T23 (KV cache condiviso): Ollama gestisce già il KV
  cache del prefisso system prompt — guadagno ~zero.
- Token reduction T24 (batch tool calls): guadagno reale potenziale
  (50–70% round-trip in meno) ma richiede refactor di formato risposta +
  loop ReAct + gestione ordering; rischio regression alto.
- Token reduction T25 (pruning per rilevanza): richiede scoring delle
  sezioni; complessità alta per guadagno variabile.
- Token reduction T26 (quantizzazione KV llama.cpp): richiede di
  bypassare Ollama con llama-cpp-python — cambio architetturale.
