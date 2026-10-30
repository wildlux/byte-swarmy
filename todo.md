# 📋 BYTE-SWARMY — TODO

Regola operativa: **prima si scrive il task qui, poi si esegue**. Ogni modifica
al codice deve avere una riga con stato `[ ]` / `[x]`. I task devono essere
piccoli, atomici e verificabili. Per modifiche a `orchestrator.py`/`tools.py`:
`py_compile` + boot reale sotto watchdog + suite completa (R1).

Stato attuale: **sistema operativo end-to-end**, 55/55 test pass
(27 security + 22 sandbox + 6 intent). Tutte le features dei cicli 1–10
completate (vedi `IMPLEMENTED.md`).

---

## 🎯 Priorità alta (sicurezza e stabilità)

- [ ] **M1. Guardrail anti-escape in `write_file`/`patch_code`** — Gate AST/regex
  che rifiuta script contenenti artefatti di escape fuori contesto (`\"` fuori
  da stringa, `\` a fine riga non da continuazione legittima). ~30 min di
  lavoro; il bug più costoso del progetto è prevenibile qui.
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

- [ ] **9.1 Handler deterministico per `type=execute`** — Parsing della
  descrizione (`gcc X.c -o Y`, `python X.py`) + esecuzione via
  `tools.run_bash`, senza LLM. Cortocircuita planner/worker/auditor (stesso
  pattern degli swarm commands).
- [ ] **9.4 Timestral predittivo** — EMA/regressione pesata su campioni
  (temp, load) in stdlib; stima "minuti alla soglia" integrata come ADVICE
  (le regole fisse restano il fallback autoritativo).
- [ ] **9.9 Memoria persistente avanzata** — Estrazione preferenze utente
  (type hints, stile, lingua, framework) dai task completati; iniezione nel
  prompt del worker via `build_context_for_prompt`.
- [ ] **9.11 Benchmark automatico dei modelli** — Suite fissa
  (code/riassunto/classificazione) con metriche tok/s, latenza, esito →
  `state/model_benchmarks.json`; suggerimento di placement nel tab Modelli.
- [ ] **M3. Static Checks (Bandit/Mypy)** — Gate obbligatori: se il codice
  non passa l'analisi statica non viene nemmeno provato l'avvio.

## 🔌 Priorità bassa (USB e MCP)

- [ ] **9.7 MCP E2E** — Collaudo: server di esempio → task accodato con
  `source=mcp:<server>` → esecuzione dello swarm.
- [ ] **M10. USB Protocol Parser** — Traduzione descrittori/endpoint/payload.
- [ ] **M11. USB Differential Analysis** — Confronto automatico tra due
  catture per isolare i pacchetti di un'azione specifica.
- [ ] **M8. Utente dedicato `byteswarmy`** — Richiede sudo; resta una depth
  defense addizionale da fare manualmente via `setup-hardening.sh`.
- [ ] **M9. usbmon/tshark ambiente** — Automatizzare l'installazione delle
  dipendenze kernel per `capture_usb_traffic`.

## 🧹 Igiene continua

- [ ] **R1.** Ogni modifica strutturale (`orchestrator.py`, `tools.py`) deve
  finire con `py_compile` + boot reale sotto watchdog, non solo unit test.
- [ ] **R2.** Mai considerare "fatto" un gate di sicurezza senza un test che
  lo provi a livello di interazione reale (modello + pipeline).
- [ ] **R3.** Se un file supera le ~500 righe, prima di aggiungere altro:
  verificare che la funzionalità non esista già (vedi `run`/`_tick`
  duplicati del Ciclo 7).
- [ ] **FM14 (parziale)** — La coda ha due fonti di verità: GUI scrive/legge
  `tasks/queue.json`, orchestratore legge/scrive `tasks/queue.db`. Unificare
  la lettura della coda da parte della GUI via `TaskQueue` SQLite in sola
  lettura (la GUI legge già dal DB per il Live Activity Panel).

## ✅ Completato (riepilogo)

Tutte le features dei cicli 1–10 sono completate. Vedi `IMPLEMENTED.md` per
il log storico dettagliato. In particolare:
- Sandbox sicuro (escape `/etc` bloccato, 11/11 subtest pass).
- IntentRouter multilingue IT/EN/ZH (28 intent, 314 trigger).
- Streaming token real-time nel Live Activity Panel.
- Swarm command handlers diretti (8 comandi, no LLM).
- Decision model `tev1:4b` per task generici.
- Memoria persistente tra task.
- Model selector intelligente + tab Modelli nella GUI.
- Dynamic KV cache estimation (formula reale, non hardcoded).
- Migrazione a package maiuscoli (CORE/INTENT/SAFETY/MONITORING/GUI/CONFIG).
- 55/55 test pass.
