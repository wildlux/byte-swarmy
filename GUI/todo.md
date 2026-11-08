# 📋 BYTE-SWARMY — TODO

Regola operativa: **prima si scrive il task qui, poi si esegue**. Ogni modifica
al codice deve avere una riga con stato `[ ]` / `[x]`. I task devono essere
piccoli, atomici e verificabili. Per modifiche a `orchestrator.py`/`tools.py`:
`py_compile` + boot reale sotto watchdog + suite completa (R1).

Stato attuale: **sistema operativo end-to-end**, 263 test veloci pass
(+ suite LLM lente: e2e/functional/mcp/timestral/intent/monthly) dopo la
sessione 2026-11-05/06 — vedi sezione 🆕 in fondo.

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

- [x] **9.7 MCP E2E** — `tests/test_mcp_e2e.py` (4 test, pass nella suite completa 281).
- [x] **M10. USB Protocol Parser** — `CORE/usb_protocol.py` + `tests/test_usb_protocol.py` (25 test USB pass).
- [x] **M11. USB Differential Analysis** — `CORE/usb_differential.py` + test dedicati pass.
- [ ] **M8. Utente dedicato `byteswarmy`** — Richiede sudo.
- [ ] **M9. usbmon/tshark ambiente** — Automatizzare installazione.

## 🧹 Igiene continua

- [ ] **R1.** `py_compile` + boot reale sotto watchdog per modifiche strutturali (pratica adottata: orchestratore va comunque RIAVVIATO dopo le modifiche).
- [x] **R2.** Test di interazione reale per i gate di sicurezza — `tests/test_security.py` (ToolSet reale: comandi bloccati, traversal, symlink, allowlist).
- [ ] **R3.** Verificare funzionalità duplicate se un file supera ~500 righe — `control_center.py` è ~5000 righe: da spezzare (DevicePanel/CenterArea/CreditsOverlay/editor in moduli separati).
- [ ] **FM14** — Unificare la coda GUI→SQLite in sola lettura.

## 🧪 Da valutare (aperti di recente)

- [ ] **Audit LLM vero** — `AuditWorker.SYSTEM` è dead code: `audit()` è euristico. Implementare la review LLM reale (con decision APPROVE/REJECT).
+ [x] **Audit LLM vero** — `AuditWorker.audit()` ora implementa review LLM reale con decision APPROVE/REJECT (fallback euristico).
- [ ] **Escalation automatica per task** — il consiglio di escalation è scritto nei dettagli; valutare override del modello PER task (oggi il modello viene da actors.json/config).
- [ ] **Minimi verticali Plancia** — la finestra viene forzata in altezza dai minimi interni (~1100px): valutare scroll o collasso di default.
+ [x] **Minimi verticali Plancia** — rimosso `setMinimumSize(900, 650)` da MainWindow; le card e i pannelli si adattano al contenuto. Finestra ridimensionabile liberamente.

## ✅ Sessione 2026-11-05/06 (completata — 263 test veloci)

- [x] **Fix workflow utente**: pulsante ▶ toolbar morto (return prematuro) → toggle pausa/riprendi REALE (pause.flag); IndentationError in main_window.py.
- [x] **Agenti**: envelope `tool(...)` fixato (ast.literal_eval + prompt rework), allowlist allineata (29 tool), 4 nuovi tool file (delete/move/list/slice), protocollo normalizzato in INGLESE, regola "progetto autonomo" (requirements.txt + avvia.sh).
- [x] **Modelli piccoli che salvano**: max_tokens 400→1024, parse dict Python-style, envelope (path, content) → write_file.
- [x] **Retry configurabili**: `[orchestrator] max_task_retries` + `retry_cooldown_sec` (colonna retry_after in queue.db).
- [x] **3 flussi utente**: CPU/GPU cliccabili → Attori; dettagli task con codice navigabile + ▶ Esegui (py/sh/c/cpp/html, fuori sandbox); "Apri risultato" apre la CARTELLA (filtro .git/__pycache__, priorità main/avvia); avvia.sh generato SEMPRE a task approvato.
- [x] **Escalation LLM**: a fallimento definitivo, consiglio light→medium→heavy scritto nei dettagli (reason).
- [x] **Temi**: 19 temi (9 chiari per inversione HSL), switch live reale (QSS per nome, non più binario), selettore diviso chiari/scuri, contrasto WCAG ≥4.5:1 su tutti, niente parti bianche (esteso coverage per tema + filtro spazzatura file task).
- [x] **Crediti**: sfondo immagine visibile (vetro smerigliato), loghi 88x56, ESC per uscire.
- [x] **Hardware**: capacità multi-modello CALCOLATA dai 3 attori (LLM/Decision/Timestral, timestral force-CPU), righe CPU/GPU cliccabili, pannello compatto.
- [x] **Attori/Scheduler**: modelli ordinati alfabeticamente+grandezza con nota d'uso, modifica task schedulati (tasto destro → form).
- [x] **Keyboard**: ESC crediti, "/" focus comando (testati); CPU/GPU click testato.
- [x] **mappa pesi→modelli in CORE/constants.py** (unica fonte CORE+GUI).

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
- ButtonBridge remoto (list/click/screenshot) + test workflow end-to-end.
- 263 test veloci pass + suite LLM lente.
