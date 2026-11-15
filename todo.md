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

*(nessun item aperto — tutto il piano approvato è completato)*

### Responsive
*(nessun item aperto — T-R3 e gap vuoto risolti nel Cycle 29)*

---

## 🆕 Token reduction (nuove tecniche — proposte 2026-11-14)

Priorità 1–8 per ridurre il prompt del worker di Byte-Swarmy (~4–5KB → ~1.5–2KB/step,
guadagno 50–60%, senza perdita di funzionalità). Vedi conversazione per dettagli.

- [x] **T1 — Tool list dinamica per tipo task**: mostra solo i tool rilevanti
  (creazione → write_file/read_file/lint/run_test; refactoring → patch/rename/extract/find_refs;
  analisi → analyze_*/search; git → git_*). Guadagno ~1.1KB/step. ✅ IMPLEMENTATO in Cycle 34.
- [x] **T2 — Regole compatte**: comprimi le 10 regole del worker da ~1KB a ~0.3KB.
  Guadagno ~0.7KB/step. ✅ IMPLEMENTATO in Cycle 33.
- [x] **T3 — Project state on-demand**: cap file da 20 a 10 in `_project_state()`.
  Guadagno ~0.5KB/step. ✅ IMPLEMENTATO in Cycle 34.
- [x] **T4 — Skill block condizionale + cap 1500**: iniettare solo i passi (STEPS),
  non il template completo; cap a 1500 chars invece di 2500. Guadagno fino a 1KB/step. ✅ IMPLEMENTATO in Cycle 33.
- [x] **T5 — Tool result truncation aggressiva**: troncare a 300 chars (vs 500);
  read_file solo prime 20 righe + ultime 5; run_test_suite solo summary.
  Guadagno ~0.5KB/step. ✅ IMPLEMENTATO in Cycle 33.
- [x] **T6 — Deduplicazione tra step**: prompt fisso completo solo al primo
  step (`_build_system(task)`); step successivi usano `_build_system_compact()`
  (~0.3KB vs ~1.2KB). Guadagno ~2.5KB/step. ✅ IMPLEMENTATO in Cycle 35.
- [x] **T7 — Persistent context lazy**: ridotto da 15 file a 8, 5 errori a 3,
  5 task a 3 in `build_context_for_prompt()`. ✅ IMPLEMENTATO in Cycle 34.
- [x] **T9 — Codici tool a prefisso naturale**: abbreviare i nomi tool con
  prefissi che il modello già conosce come completamento del nome completo
  (read=read_file, write=write_file, patch=patch_code, commit=git_commit,
  bash=run_bash, search=search, status=git_status, diff=git_diff, log=git_log,
  branch=git_branch, merge=git_merge, lint=lint_code, test=run_test_suite,
  analyze=analyze_project, refs=find_references, complex=analyze_complexity,
  graph=get_call_graph, extract=extract_method, rename=rename_symbol,
  read_slice=read_file_slice, delete=delete_file, move=move_file,
  list=list_files, usb=inspect_usb_devices, capture=capture_usb_traffic).
  Guardia: se il modello usa il nome completo, funziona comunque (fallback).
  Guadagno ~0.3KB/step prompt + ~0.1KB/step risposta. ✅ IMPLEMENTATO in Cycle 33.
- [x] **T8 — Formato JSON compatto**: `TASK: ... | DESC: ... | RULES: ...`
  invece di markdown multi-riga. Guadagno ~0.2KB/step. ✅ IMPLEMENTATO in Cycle 36.

Ordine consigliato: T1 → T2 → T4 → T5 → T9 → T3 → T7 → T8 → T6 (ultimo, sforzo alto) — TUTTI IMPLEMENTATI tranne T6.

---

## 🆕 Token reduction (nuove tecniche — avanzate, proposte 2026-11-14)

Priorità per ridurre ulteriormente il prompt del worker (~2KB → ~1KB/step) e il tempo
di inferenza. Vedi conversazione per dettagli.

- [x] **T10 — Prompt caching per tipo task**: pre-calcolare il system prompt una volta
  per tipo task (creation/refactoring/analysis/git/usb) e cacharlo in un dict a livello
  di classe. Prefisso identico → cache hit al 100% su Ollama → il modello non
  re-elabora i tool ad ogni step. Guadagno: tempo di inferenza (non token). ✅ IMPLEMENTATO in Cycle 35.
- [x] **T11 — Tool result summarization intelligente**: invece di troncare a 300 chars
  ([:300]), usare estrazione intelligente: read_file → prime 10 righe + righe con
  def/class/import; run_test_suite → solo N passed/M failed + primi 3 errori;
  run_bash → ultime 5 righe; git_diff → solo nomi file + righe +/- di sintassi.
  Guadagno: ~0.2–0.5KB/step + migliora la qualità (info rilevanti invece di
  troncamento cieco). ✅ IMPLEMENTATO in Cycle 37.
- [x] **T12 — Abbreviazione percorsi**: usare percorsi relativi brevi (main.py invece
  di project/main.py) nel prompt. Rimuovere il prefisso project/ (il worker sa già
  di essere in project/). Guadagno: ~0.1KB/step, cumulativo su 10 step. ✅ IMPLEMENTATO in Cycle 37 (esempi JSON + project_state già relativi).
- [x] **T13 — Adaptive max_tokens**: adattare max_tokens per step: tool call semplice
  (read, search) → 256; write_file (contenuto lungo) → 1024; step finale (done=true)
  → 128. Guadagno: 30–50% tempo su step semplici. ✅ IMPLEMENTATO in Cycle 37 (1024 primo step, 512 successivi).
- [x] **T14 — Rimozione esempi dal prompt**: rimuovere o ridurre a 2 gli esempi di
  comandi buoni ("ls .", "cat main.py", ...). Ridondanti per modelli addestrati su
  dati di coding. Guadagno: ~0.2KB/step. ✅ IMPLEMENTATO in Cycle 33 (regole compatte).
- [x] **T15 — Context window pruning**: rimuovere ## PROJECT STATE dopo il primo step
  (il modello lo ha già visto); tenere solo i file modificati in questo task.
  Guadagno: ~0.3KB/step dal 2° step in poi. ✅ IMPLEMENTATO in Cycle 33 (project state solo in initial prompt, non in step prompts).
- [x] **T16 — Prompt fisso + delta (architettura ReAct)**: prompt fisso completo solo al
  primo step; step successivi usano system prompt compatto (~0.3KB) + task title
  re-iniettato per prevenire task drift. Guadagno ~2.5KB/step. ✅ IMPLEMENTATO in Cycle 38.
- [x] **T17 — Model-specific prompt tuning**: formati diversi per modelli diversi
  (Qwen: compatto; Llama: strutturato con esempi; DeepSeek: chain-of-thought).
  Rilevamento famiglia via `_model_family()` (legge il nome del modello dal
  config). Cache key include la famiglia (prompt diversi per famiglia).
  Guadagno: +20–30% qualità. ✅ IMPLEMENTATO in Cycle 39.

Ordine consigliato: T10 → T11 → T13 → T15 → T12 → T14 → T16 → T17 (ultimo, sforzo alto).

---

## 🆕 Token reduction (nuove tecniche — avanzate 2, proposte 2026-11-14)

- [x] **T18 — JSON chiavi corte**: `_parse_action()` accetta sia chiavi corte
  (t/a/d/r) che standard (thought/action/done/result). Guadagno ~50 token/task.
  ✅ IMPLEMENTATO in Cycle 42.
- [x] **T19 — Deduplicazione tool call identiche**: `_call_tool` cacha l'ultima
  tool call (nome + args) e restituisce il risultato cachato se ripetuta.
  Guadagno: evita round-trip ridondanti. ✅ IMPLEMENTATO in Cycle 42.
- [x] **T20 — Prompt pruning per step**: rimuovere le regole già assorbite
  dal modello dopo il 3° step (solo "Reply with JSON"). Implementato in
  `_build_system_compact(step)` — dopo step 3 restituisce un prompt minimale
  (2 righe). Guadagno ~0.1KB/step dal 3°. ✅ IMPLEMENTATO in Cycle 43.
- [x] **T21 — Early stopping**: fermare la generazione quando il JSON è
  completo (parsing parziale durante lo streaming). Guadagno 30-60% tempo
  su step semplici. ✅ IMPLEMENTATO in Cycle 43.
- [x] **T22 — Compressore LLM del prompt**: implementato come compressore
  SOLO del contesto persistente (`_compress_context`), con cache per hash
  (una chiamata LLM per versione del contesto, riusata su più task),
  guardia client-reale (nei test resta deterministico) e model key routed
  (nessuna rotazione extra su 4GB VRAM). NOTA ONESTA: il contesto è già
  capped a ~1KB da T7 (8/3/3) → la compressione resta una valvola di
  sicurezza che scatta solo se il contesto supera 1500 chars. La versione
  originale (comprimere l'intero prompt per task) è stata scartata:
  prefill pagato 2x + rotazione modello = rallentamento netto.
  ✅ IMPLEMENTATO in Cycle 44.
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

- [x] **verify_all.py** (`tools/verify_all.py`): verifica autonoma in un
  comando — py_compile di tutti i sorgenti + suite pytest per-file con
  timeout individuale (esclusi i test live che toccano la coda reale) +
  boot reale orchestratore (pause.flag, exit 124 atteso) + benchmark
  worker ReAct con Ollama (auto-skip se offline). ✅ Cycle 45.
- [x] **bench_worker.py** (`tools/bench_worker.py`): benchmark del loop
  ReAct con modello reale in sandbox (`state/bench_sandbox/`), timing
  per ogni chiamata LLM, JSON in `state/benchmarks/`, confronto con
  baseline (`--save-baseline` dopo un'ottimizzazione per misurare il
  prima/dopo). ✅ Cycle 45.
- [x] **Watchdog orfano**: `SAFETY/watchdog.py` inoltra SIGTERM al
  figlio orchestratore (prima: stop lanciatore lasciava l'orchestratore
  vivo orfano → doppio orchestratori); sweep di difesa in
  `byte-swarm.sh stop`. ✅ Cycle 45.
- [x] **test_e2e pid guard**: guardia anti pid-reuse (cmdline
  orchestrator|watchdog, stessa semantica launcher) + catch OSError. ✅ Cycle 45.
- [x] **Regressioni GUI pre-esistenti** (Cycle 45 per-file map: 5 file
  fail): DevicePanel fallback + alias (`GUI/device_panel.py`), guardie
  RuntimeError su timer distrutti (`GUI/cc_shutdown.py`), alias
  `theme_combo` (`GUI/settings_panel.py`), zoom identità a 100% +
  invalidazione cache al cambio tema (`GUI/cc_zoom.py`,
  `GUI/center_area.py`), **causa vera white-panels dark** = icone
  "pagina bianca" QFileIconProvider → palette a tema
  (`GUI/theme/theme.py`) + tint icone (`GUI/file_manager.py`,
  `GUI/file_tree_drawer.py`), checkbox riga senza bianco hardcoded
  (`GUI/task_item_row.py`), selettori `QTreeView::indicator` nei temi
  scuri, re-export `_looks_like_file_path` (`CORE/orchestrator.py`),
  escalation test dinamico (`tests/test_user_workflow.py`). ✅ Cycle 46.
- [x] **Skill py-refactor-rename** (rinomina multi-file): creata
  `SKILLS/py-refactor-rename.md` — test_refactoring_live la aspettava
  e `skill_executor` salta la mappa codice per `py-refactor-*`. ✅ Cycle 46.
- [x] **Igiene repo**: config.toml.bak eliminato e backup rediretti in
  `backups/` (4 scrittori GUI/CORE — la GUI aperta ricreava il .bak a
  ogni salvataggio), sml_models.db untracked + gitignore, root
  settings.json → `CONFIG/tool_settings.json`, DATI_COMPLESSI.json →
  `CONFIG/` (path script aggiornato), dotfile runtime ammessi dal test
  igiene. ✅ Cycle 46.
- [x] **Prima misura bench pre-T1 vs baseline** (worktree `b9bb4e6`,
  stesso modello e task): token input −72% (2516→668 ch system
  costante), artifact 0/2 → 2/2. Il confronto wall è confondato dal
  fatto che pre-T1 i task FALLIVANO (loop read_file senza output).
  Numeri in `DOCS/IMPLEMENTED.md` Cycle 46b. ✅ Cycle 46b.

## Regola workflow (da Cycle 46b)
- **Ogni report/misura va documentato in `DOCS/`** (es. `DOCS/BENCH.md`
  per i bench, `DOCS/IMPLEMENTED.md` per i cicli); i JSON grezzi restano
  in `state/benchmarks/` (gitignored). Nessun report solo in chat.
  Regola anche in `AGENT.md` §Regole (punto 6).

## Furbate candidate (verificate contro il codice, Cycle 47?)
Ottimizzazioni proposte dopo la prima misura bench — ognuna con il punto
del codice reale su cui agire. Da scegliere con l'utente:
- [x] **A. Warmup all'avvio + keep_alive da config** ✅ Cycle 47:
  orchestrator pre-carica `warmup_model` (thread background) +
  `keep_alive_sec` esplicito rispettato nelle richieste
  (`CORE/ollama_client.py`: `_explicit_keep_alive`, `warmup`).
- [x] **B. Scheduling sticky per modello** ✅ Cycle 47:
  FIFO con affinity al modello caricato — `_pick_task` consulta
  `peek_pending(8)` e `claim_by_id` (stesso claim atomico di next_pending).
- [x] **C. Audit gate deterministico** ✅ Cycle 47:
  config `[audit].deterministic_gate = true` → AST check sui file scritti
  prima dell'audit LLM (APPROVE se compilano, REJECT con SyntaxError esatto).
- [ ] **E. num_ctx A/B bench**: 8192 → 4096/6144 ora che i prompt sono
  compatti (meno KV cache = più velocità su 4GB); misurato con
  `tools/bench_worker.py`, report in `DOCS/BENCH.md`.
- [x] **F. Watchdog primo token** ✅ Cycle 47:
  streaming abort con `FirstTokenTimeout` dopo `[ollama].first_token_timeout`
  (60s) senza token → task in fallback su worker_general.

### Bench post-furbate (Cycle 47b)
- [x] **Bench post-furbate** (auto dentro verify_all): wall −5,4% (74,59→70,53s),
  bench-create −9,6% (load cold nascosto dal warmup), token invariati.
  Report in `DOCS/BENCH.md` Cycle 47b. ✅ Cycle 47b.

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
