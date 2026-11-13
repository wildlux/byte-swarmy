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
- [ ] **R3 — Split `GUI/control_center.py`** (~5000 righe) in moduli per
  area (sidebar, centro, editor, debug bar), comportamento invariato.
- [ ] **FM14 — Coda unica GUI→SQLite**: la coda task vive solo in SQLite
  (stato condiviso GUI/orchestratore), niente code in memoria da tenere
  in sync.
- [ ] **UI Redesign** — menu hamburger, Live Activity in alto.

### Responsive (T-R2..T-R5, da DOCS/todo.md)
- [ ] **T-R2** `GUI/control_center.py` — colonne a larghezza fissa: sidebar
  coda `setFixedWidth(280)` → `setMinimumWidth(200)` + stretch; colonna
  editor `setFixedWidth(500)` → `setMinimumWidth(300)` + stretch.
- [ ] **T-R3** — `_force_content_size`: `setFixedHeight(300)` triplo →
  `setMinimumHeight(220)` + policy Expanding verticale; verificare che non
  rompa la grid card della Plancia.
- [ ] **T-R4** — `PlanciaCard.setFixedHeight(110)`: decidere con l'utente
  se tenere 110px fisso (compattezza) o `setMinimumHeight(110)`.
- [ ] **T-R5** — barre fisse (top bar 64px, command bar 52px, header
  sezione 48px): verificare artefatti al resize.
- Nota: prima di toccare aree con dimensioni fisse, chiedere all'utente
  quali sezioni vede realmente tagliate/artefatte al maximize/resize.

### Qualità / igiene
- [ ] **R1 — Igiene rigenerazione**: per modifiche a `orchestrator.py` /
  `tools.py`: `py_compile` + boot reale sotto watchdog + suite completa.

### Integrazioni / sicurezza
- [ ] **MCP E2E testing** — test end-to-end del bridge MCP.
- [ ] **USB protocol parser** — parsing del protocollo USB.
- [ ] **USB differential analysis** — analisi differenziale tra capture USB.
- [ ] **Utente dedicato `byteswarmy`** (root-level, `setup-hardening.sh`) +
  automazioni usbmon/tshark sotto utente non-root dedicato.

---

## Fuori scope (per scelta/limiti hardware)
- Skill worker `pyqt6-graphics` / `pyqt6-network`: fuori scope — il 3B non
  le regge; la GUI si fa a mano o con `pyqt6-basics`.
