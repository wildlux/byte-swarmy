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

### GUI / UX
- [ ] **UI Redesign (parziale)** — Live Activity bar aggiunta in alto; resta menu hamburger avanzato / riorganizzazione pannelli.
- [ ] **FM14 — Coda unica GUI→SQLite**: la coda task vive solo in SQLite
  (stato condiviso GUI/orchestratore), niente code in memoria da tenere
  in sync.

### Responsive
- [ ] **T-R3** — `_force_content_size`: `setFixedHeight(300)` triplo →
  `setMinimumHeight(220)` + policy Expanding verticale; verificare che non
  rompa la grid card della Plancia. (Audit 2026-11-13: oggi i 5 widget
  strumenti vivono solo nelle pagine di dettaglio dove `wrap_in_panel_page`
  rilascia già l'altezza max → impatto basso, rimandato.)
- [ ] **Gap vuoto in alto a schermo pieno**: a 1920×1080 ~200px di vuoto
  sopra "Plancia di controllo" (header sezione spinto giù). Riscontrato
  nell'audit offscreen; l'utente non lo ha scelto per ora.

### Qualità / igiene
- [ ] **R1 — Igiene rigenerazione**: per modifiche a `orchestrator.py` /
  `tools.py`: `py_compile` + boot reale sotto watchdog + suite completa.

---

## Fuori scope (per scelta/limiti hardware)
- Skill worker `pyqt6-graphics` / `pyqt6-network`: fuori scope — il 3B non
  le regge; la GUI si fa a mano o con `pyqt6-basics`.
