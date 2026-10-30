# 📋 BYTE-SWARMY — TODO

Regola operativa: **prima si scrive il task qui, poi si esegue**. Ogni modifica
al codice deve avere una riga con stato `[ ]` / `[x]`. I task devono essere
piccoli, atomici e verificabili. Per modifiche a `orchestrator.py`/`tools.py`:
`py_compile` + boot reale sotto watchdog + suite completa (R1).

Stato attuale: **sistema operativo end-to-end**, 58/58 test pass
(27 security + 22 sandbox + 3 escape-gate + 6 intent).

---

## 🎯 Priorità alta (sicurezza e stabilità)

- [ ] **9.1b Fix allowlist per binari locali** — L'execute handler funziona
  ma `run_bash` blocca l'esecuzione di binari compilati (es. `./hello_world`)
  perché non sono nella allowlist di `security.py`. Aggiungere `./` o
  gestire i binari in `project/`.
- [ ] **M2. Exception Hardening centralizzato** — Policy unificata per gli
  errori delle chiamate LLM/tool; un Worker che ritorna "ERROR" deve essere
  analizzato, non solo marcato `retry`.
- [ ] **M4. State Recovery da event-store** — Al riavvio la coda persiste ma
  il contesto dei worker si perde; implementare il ripristino reale dal log
  immutabile (`memory_provider.py`).
- [ ] **M6. Mascheratura selettiva `/etc`** — Montare solo i file necessari
  invece di esporre tutto `/etc` world-readable.
- [ ] **M7. Quota disco su `project/`** — Il check ogni 30 s non vede un `dd`
  che riempie 50 GB in 10 s. Usare `quota`/`fallocate` o un size limit nel
  sandbox.

## 🔧 Priorità media (qualità e usabilità)

- [ ] **9.4 Timestral predittivo** — EMA/regressione pesata su campioni
  (temp, load) in stdlib; stima "minuti alla soglia" integrata come ADVICE.
- [ ] **9.9 Memoria persistente avanzata** — Estrazione preferenze utente
  (type hints, stile, lingua, framework) dai task completati.
- [ ] **9.11 Benchmark automatico dei modelli** — Suite fissa
  (code/riassunto/classificazione) con metriche tok/s, latenza, esito →
  `state/model_benchmarks.json`.
- [ ] **M3. Static Checks (Bandit/Mypy)** — Gate obbligatori.
- [ ] **UI Redesign** — Menu hamburger, Live Activity in alto, rimozione
  status bar (da fare a mano o con refactor strutturato, non regex).

## 🔌 Priorità bassa (USB e MCP)

- [ ] **9.7 MCP E2E** — Collaudo completo.
- [ ] **M10. USB Protocol Parser** — Traduzione descrittori/endpoint/payload.
- [ ] **M11. USB Differential Analysis** — Confronto automatico tra catture.
- [ ] **M8. Utente dedicato `byteswarmy`** — Richiede sudo.
- [ ] **M9. usbmon/tshark ambiente** — Automatizzare installazione.

## 🧹 Igiene continua

- [ ] **R1.** `py_compile` + boot reale sotto watchdog per modifiche strutturali.
- [ ] **R2.** Test di interazione reale per i gate di sicurezza.
- [ ] **R3.** Verificare funzionalità duplicate se un file supera ~500 righe.
- [ ] **FM14** — Unificare la coda GUI→SQLite in sola lettura.

## ✅ Completato (riepilogo)

- Sandbox sicuro (escape `/etc` bloccato, 11/11 subtest pass).
- M1 Anti-escape guardrail (detect_artifacts, 3/3 test pass).
- IntentRouter multilingue IT/EN/ZH (28 intent, 314 trigger).
- Streaming token real-time nel Live Activity Panel.
- Swarm command handlers diretti (8 comandi, no LLM).
- 9.1 Execute handler deterministico (gcc/python/make, no LLM).
- Decision model `tev1:4b` per task generici.
- Memoria persistente tra task.
- Model selector intelligente + tab Modelli nella GUI.
- Dynamic KV cache estimation (formula reale).
- Timestral LLM parameter optimizer (4 profili termici).
- QSS Theme system (light/dark, toggle Ctrl+Shift+T).
- Planner SQLite bug fix (subtask ora persistono correttamente).
- Migrazione a package maiuscoli (CORE/INTENT/SAFETY/MONITORING/GUI/CONFIG).
- 58/58 test pass.
