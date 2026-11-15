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
