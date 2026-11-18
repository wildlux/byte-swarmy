# TODO — BYTE-SWARMY

> **Flusso documentale**: il task nasce qui → si esegue → si registra in
> `DOCS/IMPLEMENTED.md` (Cycle N) → si cancella da qui.
>
> **Storia completa**: Fasi 1–9, M1–M10, P1–P15, suite T1–T10 e T11–T21,
> routing, code map, clarifier, chiusura orchestratore — tutto travasato in
> `DOCS/IMPLEMENTED.md` (Cycles 13–22). Report consolidato: `REPORT.md`.

Stato: **tutto il piano approvato è completato** (le 85 voci del vecchio
todo sono registrate in `DOCS/IMPLEMENTED.md`). Da oggi (2026-11-18)
c'è una roadmap viva: la scala verso il goal middle senior
(`DOCS/MIGLIORAMENTI.md`, radar grafico E) — le priorità P1/P2/P3 qui sotto.

---

## 🎯 Roadmap verso Middle Senior (dal radar, 2026-11-18)

> Ogni item ha un criterio di done **misurabile**. Filosofia:
> deterministico-first, una voce per sessione, mai generazioni monolitiche.

### P1 — Prerequisiti del goal (misurare per governare)

1. [ ] **Metrica "primo colpo %"** — il criterio del goal (≥70% primo
      tentativo) oggi NON è misurato: prima la baseline, poi il goal.
      Criterio done: ogni task-done registra se chiuso al primo colpo o
      dopo correction (state/session_report); `verify_cycle.sh` stampa
      `primo_colpo: X/Y`. Zero LLM (~30 righe in worker/orchestrator).
2. [ ] **Gate import-check — 0 allucinazioni API misurabili** —
      pyflakes ha dimostrato di funzionare (12 undefined nel nostro
      stesso repo, C85). Criterio done: write_file/patch_code eseguono
      un check AST/pyflakes sui file Python scritti; simboli indefiniti
      → done rifiutato con lista dei simboli (come il test-gate C78);
      test dedicato in tests/test_toolset_gates.py.

### P2 — Chiudere i gap del radar (2/4 → 3-4/4)

3. [ ] **Scaffolding GUI deterministico** (gap più grande: 1/4) —
      template PyQt6 curati (finestra+layout+segnali+thread) che il
      worker RIEMPIE invece di inventare; skill py-gui-scaffold che
      punta al template. Criterio done: 3 template in GUI/refs/templates/
      + skill + test snapshot + 1 task GUI reale chiuso al primo colpo
      con il template.
4. [ ] **Memoria/contesto: misurare l'impatto reale** — l'import
      sistemato (C85) ha reso il contesto persistente funzionante per
      la prima volta; oggi è attivo ma non sappiamo se serve. Criterio
      done: A/B 10 task con/senza contesto iniettato → verdetto in
      DOCS/BENCH.md (mantieni, riduci o dismetti).
5. [ ] **Fedeltà API: espandere refs ai moduli interni** — refs per
      orchestrator/ledger/scheduler (come toolset_api); script che
      valida che ogni simbolo citato nei ref esista davvero
      (deterministico, parte di gen_grafici.py o separato).
6. [ ] **Clarifier: estendere oltre GUI** — pattern per test
      ("scrivi test per X": runner? marker?), persistenza (sqlite? json?),
      handler di sistema. Criterio done: 3 pattern nuovi + test.

### P3 — Sottofondi

7. [ ] **Decision tree v2 (architettura 1/4 — limite onesto del 3b)** —
      3-4 regole nuove derivate dai fallimenti registrati (M8).
      Criterio done: regole in py-arch-decision + test + 1 task
      architetturale piccolo chiuso.
8. [ ] **Modello più forte per le task GUI** — test comparativo
      qwen2.5-coder:7b/14b SOLO per il routing GUI (macchina fredda,
      ventole al max, sessione corta). Criterio done: tabella
      comparativa 3b vs 7b su 3 task GUI identici in DOCS/BENCH.md.
9. [ ] **Leva termica cpupower** (già proposta, mai implementata) —
      cap di frequenza per run lunghi; richiede sudo, documentare come
      prerequisito in README (sezione termica).

---

## 🚀 Programma "come i migliori" — GLM / Claude / OpenAI / DeepSeek / Qwen (2026-11-18)

> Le tecniche con cui i lab più forti saltano di qualità, adattate ai
> nostri vincoli (3B locale, GTX 1050 4GB, termica 60°C, zero budget).
> **L'ordine è quello vero dei lab**: prima evals, poi dati, poi
> training, poi inference-time, poi distillazione. Il nostro "RL" è il
> correction loop + gate: ogni successo verificato è un reward.

### Fase A — Evals prima di tutto (lo standard di TUTTI i lab)

10. [ ] **Eval suite interna (mini-SWE-bench del progetto)** — i task
      reali dei Cycle 70-85 diventano test-case con soluzione di
      riferimento; runner misura primo colpo % **per asse del radar**
      (non solo media). Criterio done: `evals/` con ≥12 casi + runner
      + report per famiglia. Dipende da: P1-1 (metrica primo colpo).

### Fase B — Data engine (il vero segreto di Qwen e DeepSeek: qualità > quantità)

11. [ ] **Corpus di triple verificate** — ogni sessione salva
      (prompt, output, verdetto gate) in `state/feedback_corpus/`
      (+ tool-trace del worker). È il carburante di tutto il resto.
      Criterio done: schema JSONL + writer nel worker + contatore
      per-sessione nel report. Zero LLM.
12. [ ] **Curazione deterministica** — dedup, stratificazione per
      difficoltà/asse, SOLO esempli gate-verificati; report qualità
      (n, per asse, n duplicati scartati). Criterio done: script
      `tools/curate_corpus.py` + report esportato.

### Fase C — Self-improvement: STaR/ReST (il loop R1 di DeepSeek in miniatura)

13. [ ] **Feasibility QLoRA 3b + GO/NO-GO onesto** — GPU 4GB (1GB
      libera) = borderline: unload ollama → ~3GB liberi; 1 run piccolo
      (500 esempi, 1 epoca) di notte a macchina fredda. Vincolo duro:
      ventole al max + guardia ≥90°C (già esiste). Criterio done:
      feasibility report (VRAM reali, tempo/epoca) + verdict GO/NO-GO
      scritto qui. NO-GO ammesso e onesto.
14. [ ] **(se GO) SFT su successi verificati** — LoRA 3b sul corpus
      curato (successi + correction come hard-negatives, stile V-STaR);
      valutazione SOLO sull'eval suite Fase A (mai eyeball). Criterio
      done: adapter salvato + A/B eval con/without LoRA in BENCH.md;
      se non batte la baseline → NON si integra (lezione fast lane).

### Fase D — Inference-time scaling (self-consistency OpenAI / reranking DeepSeek)

15. [ ] **Best-of-N con gate come giudice** — per task hard (GUI,
      architettura): N=3 candidati in parallelo, il gate (deterministico)
      sceglie il migliore o rifiuta tutti. Criterio done: flag
      `best_of_n` in config + benchmark costo/qualità (3x token vs
      primo colpo %) in BENCH.md.
16. [ ] **Sweep num_ctx + flash-attention** — 2048/3072/4096 con
      `flash_attention_kv` su llama.cpp: più contesto = meno
      dimenticanze (misurato: il bug requirements era conteso
      parzialmente per contesto corto). Criterio done: tabella
      qualità/tempo in BENCH.md, soglia aggiornata se vince.

### Fase E — Distillazione (DeepSeek: R1→modelli piccoli)

17. [ ] **Distill occasionale** — UN task hard eseguito da un modello
      più grande (7b/14b via ollama, macchina fredda), soluzione
      verificata dal gate → la coppia (prompt, soluzione) entra nel
      corpus Fase B → il 3b impara dall'esempio senza mai girarlo in
      produzione. Criterio done: `tools/distill_task.py` + ≥3 esempi
      nel corpus.

### Fase F — Memoria delle soluzioni (memory di Claude/ChatGPT, versione deterministica)

18. [ ] **Retrieval di soluzioni passate** — TF-IDF/keyword su task
      già chiusi (NO RAG neurale — coerente col verdetto Cycle 78):
      "task simile a X, soluzione che è passata al gate qui". Criterio
      done: tool `retrieve_similar_task()` + A/B (con/senza) su 10 task.

### Fase G — Prompt optimization data-driven (DSPy-style)

19. [ ] **A/B automatico delle varianti prompt** — refs on/off,
      posizione REFS, formato PLAN: testate sull'eval suite (Fase A),
      si promuove solo la variante che vince misurato. Criterio done:
      `tools/eval_prompt_variants.py` + 1 esperimento chiuso con
      verdetto in BENCH.md.

### Fase H — LLM-as-judge controllato (Constitutional/RLEF light, Anthropic-style)

20. [ ] **Timestral come giudice di qualità (mai sovrano)** — quando il
      gate passa ma la qualità è dubbia, il decision model valuta;
      logga accordo/disaccordo col gate. MAI override automatico: il
      gate deterministico resta l'unica autorità (principio del
      sistema). Criterio done: giudice opzionale + report accordo
      gate↔giudice su 20 casi.

**Cosa NON facciamo (onestà):** PPO/RL infrastrutturale, reward-model
training, cluster multi-GPU — fuori dai vincoli hardware e termici.
Il nostro "reinforcement" è già il correction loop: dati verificati >
compute grezzo.


## Aperti

### 📅 Domani (2026-11-17) — ordine di esecuzione concordato

Macchina fredda: prima il benchmark, poi il resto. Ogni step con la
regola termica (stadiale, `--cooldown 30 --thermal-limit 60`).

1. [x] **`tools/verify_cycle.sh` — prima esecuzione end-to-end** ✅
      (Cycle 74): py_compile OK (6 file) · boot smoke OK (rc=124) ·
      test_runner 64 file / 60 OK / 4 KO / 756 pass / 3 fail / 3 skip
      in 387s. I 3 fail sono pre-esistenti e NON causati da miei cambi:
      - `test_reuse.py` (assert 3072→2048 stale, corretto ora: Cycle 67
        aveva cambiato num_ctx planner a 2048 ma il test non fu aggiornato)
      - `test_user_workflow.py::TestToolbarToggle` (flake già noto)
      - `test_functional_swarm.py` (timeout 120s, flaky su hardware)
      Disciplina rispettata: una FAIL end-to-end viene indagata, non
      ignorata — qui il FAIL era "test vecchi", non regressione.
2. [x] **Benchmark di validazione della corsia veloce (fast lane)** —
      ✅ **CHIUSO con verdetto onesto** (Cycle 66, decisione utente
      "stop definitivo"): fast lane NON validata → `enabled = false`
      permanente. Motivi misurati in `DOCS/BENCH.md` §8: (1) il limite
      60°C viene sforato nelle fasi (79-80°C) anche con `num_thread=2`
      — il turbo della i7-7700HQ compensa, pendenza 0,27-0,29°C/s
      invariata; l'unica leva reale è il cap di frequenza (sudo) o
      altra macchina; (2) fast lane 0/2 con fallback al correction
      loop (campione insufficiente ma zero evidenze pro); (3) ~22
      min/sessione dominate dalle attese di raffreddamento. Restano
      attivi e riusabili: `temp_before/after` per fase nel JSON,
      pausa termica adattiva, driver + reporter, dati parziali.
3. [x] **Micro-ciclo config** — ✅ FATTO (Cycle 67, v0.3.15):
      `num_ctx` planner 3072 → 2048 (allineato al default tipizzato);
      `[hardware].keep_alive_sec = 900` NUOVO (warmup al boot utile 15
      min invece di 5, modello caldo tra task; RAM reale 7.6GB — 3.3
      liberi, i ~2.5GB residenti ci stanno e si scaricano da soli);
      toggle verificati: Timestral ce l'ha già (`[thermal].enabled`),
      SystemMonitor e Lifecycle sono PASSIVI (zero thread, zero costo
      da fermo) → toggle non necessari, nessun codice toccato.
      llama-server diretto con --prompt-cache resta FASE 3 (item #6),
      da misurare solo dopo un eventuale riscontro di carico reale.

### 🏛️ Strategia refactoring — Registro del debito (debt ledger) (Cycle 68)

Idea utente: DB per tracciare i pezzi da rifattorizzare + skill per il
dialogo LLM↔SQL. È la metà mancante di `CORE/code_map.py` (che mappa
cosa ESISTE via AST→SQLite): il ledger tiene traccia di cosa VA
RIFATTORIZZATO. Già dentro il progetto: SQLite usato in 5 punti
(memory_event_store, sml_database, code_map, task_queue, resilience).

- [x] **REGOLA DI PARITÀ GUI (Cycle 70)**: OGNI funzione del ledger
      è usufruibile dalla Plancia (`GUI/debt_ledger_panel.py`) —
      stats, list, add, next (🎯), mark, context (🔍), refresh
      on-demand senza timer nuovi (disciplina Cycle 63).
- [x] Regole di design (deterministiche, documentate nel modulo):
      1) l'LLM non scrive SQL libero — dialoga con API/CLI Python;
      2) `file_hash` alla registrazione → item `stale` se il file
      cambia (anti-stantio: un ledger stantio è peggio di niente);
      3) un item per sessione, stadiale — il "next" arriva da una
      query, non da un'idea (pianificazione fredda, adatta al
      limite 60°C).
- [x] **`CORE/debt_ledger.py`** — schema + API (`add`, `next`, `list`,
      `mark`, `stats`) + CLI (`add/next/list/done/stats/context`) +
      integrazione `code_map` (`context_for_file` fail-open).
      DB: `state/debt_ledger.db`.
- [x] **Test** `tests/test_debt_ledger.py` — priorità, stale-on-change,
      done skip, fail-open senza codemap.
- [x] **Skill** `.opencode/skill/debt-ledger/SKILL.md` — flusso
      registrare → next → verificare → chiudere, riusabile in ogni
      sessione futura. ✅ Cycle 74: scritta (regole + CLI + ciclo di
      sessione + regola parità GUI + esempio reale 13,4s).
- [x] Docs: IMPLEMENTED Cycle 68, README versione.
- [x] **Primo test reale del flusso, a tempo (Cycle 69)**: alimentare la
      coda con item veri già noti + eseguire il primo con il flusso
      della skill (`next → progress → context → stadio → done`) e
      misurare il tempo reale. Obiettivo utente: "molto meno tempo" —
      la coda elimina l'esplorazione LLM: il lavoro è già scritto in
      SQL, la sessione esegue. Include la dimostrazione live della
      regola stale (due item sullo stesso file: il primo eseguito
      invalida il secondo → ri-registrazione).

### 🦋 Prismalux — ESPERIMENTO CHIUSO, clone rimosso (Cycle 74, 2026-11-17)

**Obiettivo dell'utente**: vedere se si poteva importare qualcosa come
software e riusarlo — fatto. **Decisione utente**: il clone esce da
byte-swarmy e si elimina (i 3 commit locali non pushati vanno persi,
confermato esplicitamente). `project/prismalux/` rimosso.

Cosa resta a byte-swarmy (il valore dell'esperimento è nel sistema,
non nel clone):
- [x] **Skill `project-radiography`** — radiografia fredda riusabile
      per qualunque progetto futuro
- [x] **Fix skill-hijack** (find_skill matchava keywords generiche →
      il worker seguiva ricette sbagliate) + test di regressione
- [x] **Runner `tools/swarm_refactor_session.py`** (agent fresh,
      gate termiche, guardia ≥90°C, threshold configurabile)
- [x] **Verdetto onesto**: il worker 3b NON è capace per modifiche
      minime a codice esistente; le gate proteggono i test ma non i
      file dati → per quella classe serve l'esecutore deterministico
- [x] **Lezione UEFI** + `VENTOLA/` (controllo ventole, prerequisito
      dei run LLM su questa macchina)
- [x] Radiografia riusabile come metodo (312 cpp/180 h/164 py,
      6 god-file, 123 marker — dati storici in DOCS/IMPLEMENTED.md)

### Test agentico — programmino Qt/PyQt6 via swarm (Cycle 50)

- [x] **Test agentico Qt/PyQt6** ✅ Cycle 76: **VERDETTO FAIL** (4° run LLM,
      4° fallimento). Task: creare `VENTOLA/hello_qt.py` (finestra +
      QLabel contatore + QPushButton). Il worker ha ignorato il file
      target e scritto `project/main.py` (10 byte) + `patch_code.py`
      (bloccato da regression gate); `hello_qt.py` NON è stato creato.
      Temp 41→79°C in 105s; guardia 90°C non scattata. Danno pulito
      (main.py ripristinato, patch_code.py/tests/test_patch_code_regression.py
      rimossi). Conclusione: il worker 3b non è capace neppure di creare
      un file PyQt6 da zero — coerenza con il verdetto sui bare-except.
      **Il test ha prodotto il suo deliverable (un verdetto onesto), non
      un'app funzionante.** Restano solo item deterministici (capability).

### Capability agentica — test→benchmark feedback + doc summarization (Cycle 51)

- [x] **Capability: test execution → benchmark feedback** ✅ Cycle 78:
      implementato in `CORE/worker.py` (done=true viene rifiutato se la
      suite è stata eseguita e fallisce; i fallimenti vengono iniettati
      come prompt di correzione, max 2 retry, poi allow done con warning).
      I risultati dei test diventano così un segnale di feedback che
      guida il loop, non solo un warning. Connesso a `_summarize_result`
      (già esistente) per l'estrazione intelligente.
- [x] **Capability: doc reading → summary** ✅ Cycle 78: nuovo tool
      `read_document(path)` in `CORE/tools.py` (testo diretto per
      .txt/.md/.py/.json/.csv/.log/.html/.xml + PDF via pdftotext con
      layout; troncamento a max_file_size_readable), registrato in
      `allowed_tools`, dispatch in `worker._call_tool`, descrizione nel
      prompt, e summarization dedicata in `_summarize_result`
      (prime 5 righe + titoli/capitoli). Il worker può ora leggere
      documenti lunghi senza saturare il contesto.

- [x] **Middle capability: escalation 3B→4B** ✅ Cycle 52: fallback del
  worker_coder (junior) → `worker_coder_big` (middle, qwen3-coder:4b) invece
  di scendere al più piccolo (worker_general 1.5B). Salto di capacità al
  tier "middle".

### Tool LLM — diario di bordo (Cycle 52+)

- [x] **Tool `diary_llm`** ✅ Cycle 53: nuovo tool che lascia un diario di
  bordo (problem, context, attempts, failures, learnings, optimization) al
  termine di un task; persistenza in `state/diary/`. Implementato con scrittura
  sicura + sanitizzazione task_id. ✅ Cycle 53.
- [x] **Diary: DB vs file** ✅ Cycle 78: **decisione documentata** —
      il diario LLM resta **file markdown** per il contesto
      self-optimization (attuale, basta per il contesto del worker); DB
      (SQLite) solo per analytics/query strutturate, da introdurre SOLO
      quando c'è un caso d'uso reale di query (oggi non c'è). Motivazione:
      il file è leggibile/editabile a mano, versionabile, zero schema
      da migrare; il DB aggiungerebbe complessità senza beneficio
      misurabile (regola "measure, don't add").

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
