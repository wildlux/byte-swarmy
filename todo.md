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

### Responsive
- [ ] **T-R3** — `_force_content_size`: `setFixedHeight(300)` triplo →
  `setMinimumHeight(220)` + policy Expanding verticale; verificare che non
  rompa la grid card della Plancia. (Audit 2026-11-13: oggi i 5 widget
  strumenti vivono solo nelle pagine di dettaglio dove `wrap_in_panel_page`
  rilascia già l'altezza max → impatto basso, rimandato.)

---

## Fuori scope (per scelta/limiti hardware)
- Skill worker `pyqt6-graphics` / `pyqt6-network`: fuori scope — il 3B non
  le regge; la GUI si fa a mano o con `pyqt6-basics`.
