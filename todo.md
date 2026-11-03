# 📋 BYTE-SWARMY — TODO

Regola operativa: **prima si scrive il task qui, poi si esegue**. Ogni modifica
al codice deve avere una riga con stato `[ ]` / `[x]`. I task devono essere
piccoli, atomici e verificabili. Per modifiche a `orchestrator.py`/`tools.py`:
`py_compile` + boot reale sotto watchdog + suite completa (R1).

Le voci completate vengono spostate in `IMPLEMENTED.md` (log storico per cicli).
Automatizzazione: `python travasa_todo.py` (prova con `--dry-run`) sposta le
righe `- [x]` di questo file nella sezione "Completati (spostati da todo.md)"
di `IMPLEMENTED.md`, deduplicando (idempotente).

Stato attuale: **sistema operativo end-to-end**, suite pass
(27 security + 22 sandbox + 3 escape-gate + 6 intent + 9 execute-handler +
7 decision-feedback + 7 correction-loop + 6 thermal-gatekeeper +
14 repo-hygiene + 18 dotfile-security + 8 push-dialogs + 19 timestral-full +
19 hardware-strategy = 179 test totali).

GUI Control Center: pannelli Impostazioni + Attori + Code Task Scheduler +
CI/CD + Clean Code + Integrità + Sicurezza tutti cablati. Timestral **100%
cablato** (A1+A2+A3+A4). Push Git con conferma + riepilogo errori (C1+C2).
**Strategia Hardware** (GPU+CPU / Solo GPU / Solo CPU / CPU→GPU) con
auto-detect GPU via `nvidia-smi` (H1+H2). **Pesi modelli** light/medium/
heavy per LLM e Decision Model; Timestral sempre light + force_cpu=True
(H3+H4). Orchestratore legge strategia + pesi e decide target CPU/GPU
(H5).

**Brutal honest follow-up**: i test `test_timestral_full.py` sono test di
unità/isolation (verificano `TimestralGatekeeper` e `load_timestral_overrides`
in isolamento). I test A3/A4 usano `_make_orch_with_overrides()` + una
**replica** della logica di `_thermal_gate_pass`, non chiamano il vero
metodo dell'Orchestrator. Questo significa: se cambi il codice reale e non
aggiorni la replica, il test passa ma il codice reale è rotto. Vedi
**Round 3** sotto per i task di integrazione reali.

---

## 🔵 Round 3 — Integrazione GUI + Orchestrator (test reali)

I test attuali sono di unità. Per arrivare al 9.5/10 vero servono test
di integrazione che chiamino i metodi reali dell'Orchestrator e testino
la GUI con click simulati (`QTest`).

- [ ] **I1 Test `_thermal_gate_pass` vero (non replica)** — Riscrivere
  i 4 test A3 (`test_a3_*`) in `tests/test_timestral_full.py` usando
  `Orchestrator.__new__(Orchestrator)` per creare un'istanza senza
  `__init__` (che vuole DB/Ollama/config), impostare gli attributi
  manualmente (`thermal_gate`, `timestral.last_sample`, `check_only_if_gpu`,
  `pause_decision_model_too`, `queue`, `log` mockati) e chiamare il VERO
  `orch._thermal_gate_pass()`. Così se cambi il codice reale il test
  cattura la regressione. ~30 min.
- [ ] **I2 Test `_thermal_gate_pass` con pause_decision_model_too** —
  Aggiungere 2 test che verificano A4 per davvero: orchestratore con
  `pause_decision_model_too=True` + `generic_planner.set_paused` mockato
  → dopo pausa termica `set_paused(True)` è chiamato, dopo ripresa
  `set_paused(False)`. ~20 min.
- [ ] **I3 Test GUI ActorsPanel con QTest** — `tests/test_actors_gui.py`
  con `QTest.mouseClick` + `QTest.keyClicks`: apre `ActorsPanel`, cambia
  `Soglia RIPRESA` da 65 a 70, clicca `Salva configurazione attori`,
  verifica che `CONFIG/actors.json` contenga `resume_temp_threshold=70`.
  Mock di `QMessageBox.information` per evitare dialog bloccante.
  ~45 min.
- [ ] **I4 Test GUI SettingsPanel con QTest** — `tests/test_settings_gui.py`:
  apre `SettingsPanel`, aggiunge un remote Git (nome `origin`, URL
  `https://github.com/test/repo.git`, token `ghp_test`), clicca
  `Aggiungi/Aggiorna remote`, verifica che `CONFIG/settings.json`
  contenga il remote con il token. ~30 min.
- [ ] **I5 Test GUI TaskSchedulerPanel con QTest** — `tests/test_scheduler_gui.py`:
  apre `TaskSchedulerPanel`, compila titolo+prompt, seleziona tipo
  `interval`, imposta 60s, clicca `Aggiungi task`, verifica
  `CONFIG/scheduled_tasks.json` contenga il task. ~30 min.
- [ ] **I6 Test end-to-end Timestral** — `tests/test_timestral_e2e.py`:
  crea `actors.json` con `cpu_temp_threshold=50` (bassa), avvia
  orchestratore con sample finto `cpu_temp=60`, verifica che
  `queue.pause_thermal()` sia chiamato. ~45 min.
- [ ] **I7 Test integrazione strategia hardware** — `tests/test_hardware_e2e.py`:
  simula cambio strategia da `cpu_only` a `gpu+cpu` in settings.json,
  verifica che l'orchestratore cambi il routing di LLM da CPU a GPU
  (mock `ollama` per evitare chiamate reali). ~30 min.

## 🟢 Round 4 — Strategia hardware + pesi modelli (H1-H5)


## 🟡 Priorità 3 — Nice to have residui

- [ ] **T3.2 File editor + Code Explorer cablato** — Cliccare un file
  nella sidebar → vedi sempre "Nessun file caricato" nel Code Explorer.
  Creare un editor docked di default (anche un `QPlainTextEdit` read-only)
  e collegare `code_explorer.load_file(path)` a ogni click sul file tree.
- [ ] **T3.3 Log reali in BackupCodeLogs** — Sostituire i sample
  hardcoded del `BackupCodeLogs` con `git log --since="1 day ago"
  --oneline` dal repo. Filtrare per remote se possibile, altrimenti
  mostrare tutti i commit nel tab "Git". I tab GitHub/GitLab possono
  usare `gh` CLI o le API REST con token configurato.
- [ ] **T3.4 Decision Model → architettura reale** — Vere 2 fasi: prima
  il decision model decide cosa fare, poi l'LLM esegue. Richiede refactor
  di `CORE/orchestrator.py` e `CORE/task_dispatcher.py`. **Complesso** —
  salta se non è priorità.
- [ ] **T3.5 i18n vero (inglese)** — Definire `_ = lambda s: s` per ora,
  marcare le stringhe principali (titoli card, pulsanti comuni) con
  `_("...")`. Creare `GUI/i18n.py` con dizionario it/en. Rimuovere il
  tooltip "Work in progress" quando fatto. **Molte stringhe** — salta se
  non è priorità.
- [ ] **C3 Validazione URL Git** — Nel pulsante "🔌 Test connessione"
  (che esiste) usa `git ls-remote` con URL+token. Aggiungere: dopo
  "Aggiungi/Aggiorna remote" chiede "Vuoi testare ora?" → se sì esegue
  automaticamente. ~20 min.
- [ ] **D1 Documenta architettura GUI** — Crea `DOCS/ARCHITETTURA_GUI.md`
  con: schema 5 pannelli, schema 3 file JSON (chi scrive, chi legge),
  schema flusso GUI → JSON → CORE → effetto reale, tabella "stato
  cablaggio" (tutti ✅). ~20 min.

## 🔌 Priorità bassa (USB e MCP)

- [ ] **M8. Utente dedicato `byteswarmy`** — Richiede sudo.

## 🧹 Igiene continua

- [ ] **R2.** Test di interazione reale per i gate di sicurezza.
- [ ] **R3.** Verificare funzionalità duplicate se un file supera ~500 righe.
- [ ] **FM14** — Unificare la coda GUI→SQLite in sola lettura.

---

## ✅ Completato

Tutti i task completati sono registrati in **`IMPLEMENTED.md`** — non
duplicare qui. Per spostare i `[x]` automaticamente: `python travasa_todo.py`
(prova `--dry-run` prima).

**Round 1 + Round 2 completati** (sicurezza, igiene, UX, Timestral completo):
vedi `IMPLEMENTED.md` sezione "Completati (spostati da todo.md) — Round 1 +
Round 2 (2026-11-02)".
