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
- [ ] **T22 — Compressore LLM del prompt**: passare il prompt a un modello
  piccolo (1.5B) per comprimerlo prima di inviarlo al worker. Riduzione
  30-50% token, ma aggiunge latenza. Solo per prompt >2KB.
- [ ] **T23 — KV cache condiviso tra task simili**: estrarre il template
  del task (tipo + linguaggio) e cachare il prompt base. Margine (Ollama
  già gestisce il KV cache del prefisso).
- [ ] **T24 — Batch tool calls**: permettere al modello di produrre più
  tool call in un turno (array di azioni). Riduce round-trip 50-70%.
  Rischio: ordering (write prima, test dopo).
- [ ] **T25 — Prompt pruning per rilevanza**: score ogni sezione del prompt
  per rilevanza rispetto al step corrente; rimuovere le sezioni con score
  basso. Complessità alta.
- [ ] **T26 — Quantizzazione prompt (llama.cpp)**: quantizzazione Q4 del
  KV cache. Non controllabile via Ollama. Solo con llama-cpp-python.

Ordine consigliato: T18 → T19 → T20 → T21 → T11/T12 (già in lista) →
T22 → T24 → T23 → T25 → T26 (ultimo, sforzo alto).

---

## Fuori scope (per scelta/limiti hardware)
- Skill worker `pyqt6-graphics` / `pyqt6-network`: fuori scope — il 3B non
  le regge; la GUI si fa a mano o con `pyqt6-basics`.
