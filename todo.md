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
- [ ] **T8 — Formato JSON compatto**: `TASK: ... | DESC: ... | RULES: ...`
  invece di markdown multi-riga. Guadagno ~0.2KB/step.

Ordine consigliato: T1 → T2 → T4 → T5 → T9 → T3 → T7 → T8 → T6 (ultimo, sforzo alto).

---

## Fuori scope (per scelta/limiti hardware)
- Skill worker `pyqt6-graphics` / `pyqt6-network`: fuori scope — il 3B non
  le regge; la GUI si fa a mano o con `pyqt6-basics`.
