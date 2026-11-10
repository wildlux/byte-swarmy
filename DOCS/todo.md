# 📋 BYTE-SWARMY — TODO

Regola operativa: **prima si scrive il task qui, poi si esegue**. Ogni modifica
al codice deve avere una riga con stato `[ ]` / `[x]`. I task devono essere
piccoli, atomici e verificabili. Per modifiche a `orchestrator.py`/`tools.py`:
`py_compile` + boot reale sotto watchdog + suite completa (R1).

Stato attuale: **sistema operativo end-to-end**, 58/58 test pass
(27 security + 22 sandbox + 3 escape-gate + 6 intent).

---

## 🎯 Priorità alta (sicurezza e stabilità)

- [x] **9.1b Fix allowlist per binari locali** — `./binari` locali ora permessi in `security.py`.
- [x] **M2. Exception Hardening centralizzato** — `CORE/exception_handler.py` con policy classificazione errori.
- [x] **M4. State Recovery da event-store** — `CORE/state_recovery.py` per ripristino contesto worker.
- [x] **M6. Mascheratura selettiva `/etc`** — Verificato: 5/5 file montati selettivamente.
- [x] **M7. Quota disco su `project/`** — Check 500MB default in `tools.py` prima di `write_file`.
- [x] **M1. Guardrail anti-escape** — Verificato `detect_artifacts` in `ast_scanner.py`. 3/3 test pass.

## 🔧 Priorità media (qualità e usabilità)

- [x] **9.1 Handler deterministico per `type=execute`** — `CORE/execute_handler.py` (gcc/python/make, no LLM).
- [x] **9.4 Timestral predittivo** — `MONITORING/predictive.py` con EMA e regressione lineare.
- [x] **9.9 Memoria persistente avanzata** — `extract_preferences()` in `persistent_memory.py` (pattern matching).
- [x] **9.11 Benchmark automatico dei modelli** — `CORE/benchmark.py` (3 test, score 100/100 su qwen2.5-coder).
- [x] **M3. Static Checks (Bandit/Mypy)** — Verificato: già integrati in `lint_code` (`tools.py`).
- [x] **Feature 7: Timestral LLM Tuner** — `CORE/llm_tuner.py` con 4 profili termici (fast/normal/slow/pause).
- [ ] **UI Redesign** — Menu hamburger, Live Activity in alto, rimozione status bar (da fare a mano).

## 🔌 Priorità bassa (USB e MCP)

- [ ] **9.7 MCP E2E** — Collaudo completo.
- [ ] **M10. USB Protocol Parser** — Traduzione descrittori/endpoint/payload.
- [ ] **M11. USB Differential Analysis** — Confronto automatico tra catture.
- [ ] **M8. Utente dedicato `byteswarmy`** — Richiede sudo.
- [ ] **M9. usbmon/tshark ambiente** — Automatizzare installazione.

## 🧹 Igiene continua

- [ ] **R1.** `py_compile` + boot reale sotto watchdog per modifiche strutturali.
- [x] **R2.** Test di interazione reale per i gate di sicurezza — verify con test security pass.
- [ ] **R3.** Verificare funzionalità duplicate se un file supera ~500 righe — `control_center.py` è ~5000 righe: da spezzare.
- [ ] **FM14** — Unificare la coda GUI→SQLite in sola lettura.

## ✅ Completato (riepilogo)

Tutte le features dei cicli 1–11 sono completate. Vedi `IMPLEMENTED.md` per
il log storico dettagliato. In particolare:
- Sandbox sicuro (escape `/etc` bloccato, 11/11 subtest pass).
- M1 Anti-escape guardrail (detect_artifacts, 3/3 test pass).
- IntentRouter multilingue IT/EN/ZH (28 intent, 314 trigger).
- Streaming token real-time nel Live Activity Panel.
- Swarm command handlers diretti (8 comandi, no LLM).
- 9.1 Execute handler deterministico (gcc/python/make, no LLM).
- Decision model `tev1:4b` per task generici.
- Memoria persistente tra task + estrazione preferenze utente.
- Model selector intelligente + tab Modelli nella GUI.
- Dynamic KV cache estimation (formula reale).
- Timestral LLM parameter optimizer (4 profili termici).
- Timestral predittivo (EMA + regressione lineare).
- Exception hardening centralizzato.
- State recovery da event-store SQLite.
- Benchmark automatico modelli (100/100 score).
- Quota disco su project/ (500MB).
- QSS Theme system (light/dark, toggle Ctrl+Shift+T).
- Planner SQLite bug fix (subtask ora persistono correttamente).
- Migrazione a package maiuscoli (CORE/INTENT/SAFETY/MONITORING/GUI/CONFIG).
- 58/58 test pass.

## 📐 Responsive a proporzioni (Atomica 2 aperta — sessione corrente)

Obiettivo utente: le aree "no-scroll/schermate fisse" devono comportarsi come
griglie in percentuale (stile bootstrap: desktop→mobile) al maximize/resize,
senza artefatti né contenuti tagliati. NON implementare bootstrap.

Censimento `setFixed*` (fontsize completo in `grep -n "setFixed\|setMinimum\|setMaximumHeight" GUI/*.py`):
- `GUI/control_center.py`: 54 occorrenze — chiave:
  - `UNIFORM_CONTENT_HEIGHT = 300` (riga ~4693, `_force_content_size`) i 5
    preview strumenti in Plancia; le detail page poi forzano min 480/max MAX
    (riga ~4952) → doppia dimens. da unificare in proporzione.
  - `PlanciaCard.setFixedHeight(110)` (riga ~1046) + policy verticale Fixed.
  - `setFixedWidth(280)` sidebar coda (riga ~2880), `setFixedWidth(500)`
    colonna editor (riga ~5082) → su finestre strette taglia il centro.
  - barre fisse: top bar 64px (2096), command bar 52px (2392), header
    sezione 48px (957) — accettabili come "bar" ma da verificare a fine.
- `GUI/control_center.py`: 8 occorrenze (da censire una a una).
- Verificato con probe geometry: Plancia e detail stack si adattano
  (viewport = window), quindi gli artefatti visibili sono nelle aree
  sopra elencate (width fisse o content colllassabile) — chiedere
  all'utente quali vedi realmente.

Task atomici responsive (uno per commit, test tema verdi a ogni passo):

[x] **T-R1 (fatto, commit b497335)** `GUI/control_center.py`:
    `ctx_bar.setFixedWidth(90)` → `setMinimumWidth(60)` così si comprime
    su finestre strette senza tagliare.

[ ] **T-R2** `GUI/control_center.py` — colonne fisse larghezza:
    `setFixedWidth(280)` sidebar coda (riga ~2880) → `setMinimumWidth(200)`
    + stretch; `setFixedWidth(500)` colonna editor (riga ~5082) →
    `setMinimumWidth(300)` + stretch. Su finestre strette non tagliano più
    il centro.

[ ] **T-R3** `GUI/control_center.py` — `_force_content_size` 300px
    (riga ~4693): da `setFixedHeight(300)` triplo a `setMinimumHeight(220)`
    + policy Expanding verticale, così il content si adatta alla finestra.
    Verificare che non rompa la grid card della Plancia.

[ ] **T-R4** `GUI/control_center.py` — `PlanciaCard.setFixedHeight(110)`
    (riga ~1046): valutare con l'utente se tenere 110px fisso (compattezza)
    o passare a `setMinimumHeight(110)` per crescita su schermi alti.

[ ] **T-R5** `GUI/control_center.py` — barre fisse top bar 64px (2096),
    command bar 52px (2392), header sezione 48px (957): accettabili come
    "bar", da verificare a fine se creano artefatti al resize.

Nota: prima di toccare aree con dimensioni fisse, chiedere all'utente
quali sezioni vede realmente tagliate/artefatte al maximize/resize, per
non toccare ciò che va già bene.
