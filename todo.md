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
14 repo-hygiene + 18 dotfile-security).

GUI Control Center (v0.5.1+): credits overlay funzionante, brand "Byte SwarmY"
in toolbar, tab progetti aperti con pulsante ➕, sidebar "Archivio progetto"
dinamica, splitter Code Explorer / Backup Code, pannelli Impostazioni +
Attori + Code Task Scheduler, tema chiaro/scuro, push Git reale sui remote
configurati. **Cablatura parziale** dei pannelli su CORE/ — vedi sezione
"GUI: cablaggio funzionale" sotto.

---

## 🚨 Priorità 1 — Sicurezza & Bloccanti (subito)

Token e impostazioni non devono finire su GitHub. Effettua prima di tutto.

- [x] **T1.1 .gitignore** — Aggiungere `CONFIG/settings.json`,
  `CONFIG/actors.json`, `CONFIG/scheduled_tasks.json`, `CONFIG/git_settings.json`,
  `CONFIG/security_baseline.json`
  al `.gitignore`. Verifica: `git status` non mostra più questi file.
- [x] **T1.2 Audit git log** — Verifica che i file sopra non siano già stati
  committati. Comando: `git log --all --oneline -- CONFIG/settings.json
  CONFIG/actors.json`. Se trovati: `git rm --cached CONFIG/settings.json
  && git commit -m "remove leaked settings"`. Eventualmente ruota i token
  già esposti.
- [x] **T1.3 Token Git in env vars** — Leggere i token da
  `os.environ.get("BSWARM_GITHUB_TOKEN", "")` (e `BSWARM_GITLAB_TOKEN`)
  in `_git_push_one`; fallback a `CONFIG/settings.json` se la env var
  non esiste (backward compat). Aggiornare README con istruzioni `export`.

## 🟠 Priorità 2 — Roba che la UI promette ma non fa

I pannelli salvano impostazioni su JSON ma nessuno li legge. Cablare.

- [x] **T2.1 Card plancia temabili** — Rimuovere `color:#1a1a1a` hardcoded
  da `title_lbl` in `PlanciaCard` (riga ~740 di `GUI/control_center.py`).
  Spostare i colori in variabili lette dal tema attivo. In dark theme i
  titoli delle card sono illeggibili (nero su bianco). Screenshot in
  entrambi i temi per verificare.
- [x] **T2.2 Cabla Timestral** — Leggere `CONFIG/actors.json` in
  `MONITORING/thermal_manager.py`. Se esiste, fare override dei parametri
  di `CONFIG/config.toml` (soglie CPU/GPU, tok/s min, durata pausa, ecc.).
  Test: cambia soglia 80→70, riavvia orchestratore, verifica nei log
  termici che il valore nuovo è applicato.
- [x] **T2.3 `CORE/scheduler_worker.py`** — Creare un thread che parte
  dall'orchestratore e gira in background. Ogni 60s legge
  `CONFIG/scheduled_tasks.json`:
  - oneshot: se `datetime <= now`, inietta task in `tasks/queue.db` e
    segna `done=true`
  - interval: se `last_run + interval <= now`, inietta + aggiorna
    `last_run`
  - daily: se `time == HH:MM` e `last_run_date != today`, inietta +
    aggiorna
  - Aggiungere campi `last_run` e `done` nel JSON
  - Test: schedula task "fra 30 secondi", verifica che finisca nel DB.
- [x] **T2.4 Modelli Ollama reali nella combo** — In `GUI/actors_panel.py`
  sostituire la lista statica `OLLAMA_MODELS` con una chiamata
  `subprocess.run(["ollama", "list"])`. Parser della prima colonna
  dell'output. Fallback alla lista hardcoded se `ollama` non esiste o
  fallisce. Test: esegui con `ollama list` che restituisce 3 modelli →
  vedi 3 voci nella combo (più eventuali extra che hai installato).

## 🟡 Priorità 3 — Nice to have (qualità percepita)

Non blocca, ma migliora molto la qualità percepita dell'app.

- [x] **T3.1 Codice morto toolbar** — Cancellare righe ~1811-1822 di
  `GUI/control_center.py` (codice dopo `return bar` — i pulsanti Pausa/Stop
  orchestratore non vengono mai creati). Oppure spostarle sopra il `return`
  se si vogliono davvero i pulsanti Pausa/Stop in toolbar.
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
- [x] **T3.6 Test automatizzati nuovi moduli** — Aggiungere a
  `tests/run_tests.py`:
  - `tests/test_settings_store.py` (save/load/migration)
  - `tests/test_actors_panel.py` (3 attori + parametri validi)
  - `tests/test_scheduler.py` (logica one-shot/interval/daily senza
    thread reale — solo logica pura)
  - `tests/test_push_dialogs.py` (C1/C2: conferma + riepilogo push)

## 🟢 Round 1 — Igiene & UX (post attacco principale)

- [x] **B1+B2+B3+B4 Igiene repo** — `.gitignore` aggiornato con:
  `CONFIG/*.json` (settings, actors, scheduled_tasks, git_settings,
  security_baseline), `/*.png` `/*.jpeg` `/*.jpg` (solo root, IMG/
  preservata), `*.bak *.orig *.swp *~`. Script `scripts/clean_repo.sh`
  per `git rm --cached` automatico + commit "chore: clean repo".
- [x] **C1 Conferma push** — `_do_git_save` apre dialog "Conferma push
  Git" con lista dei remote + operazioni che verranno eseguite (git add
  -A + commit + push). Default button: No. Annulla → nessun push.
- [x] **C2 Riepilogo errori push** — dopo il loop sui remote:
  - 0 errori → `QMessageBox.information` "✅ Push completato"
  - parziali → `QMessageBox.warning` "Push parziale: N/M OK"
  - tutti falliti → `QMessageBox.critical` "Push fallito su tutti"
  `_git_push_one` ritorna `None` (successo) o stringa (errore).

---

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

## 🐝 GUI Control Center — cablaggio funzionale (post v0.5.1)

Stato di cablaggio dei nuovi pannelli sui moduli CORE:

| Pannello GUI              | Persistenza                  | Cablato su CORE?            |
|---------------------------|------------------------------|-----------------------------|
| Credits / Ringraziamenti   | n/a (statico)                | n/a — display only           |
| Impostazioni (tema/lingua) | `CONFIG/settings.json`       | ✅ Tema applicato live       |
| Impostazioni (Git remotes) | `CONFIG/settings.json`       | ✅ `_do_git_save` push reale |
| Attori (LLM/Decision/Tim.) | `CONFIG/actors.json`         | ❌ **T2.2 — da cablare**     |
| Code Task Scheduler        | `CONFIG/scheduled_tasks.json`| ❌ **T2.3 — da cablare**     |

Lingua (it/en): tooltip "Work in progress" onesto, vedi **T3.5**.

## ✅ Completato

Tutti i task completati (Cicli 1–13: sandbox, intent router, LLM tuner,
execute handler, T1–T4 work order, M1–M13, pulizia repo) sono registrati in
**`IMPLEMENTED.md`** — non duplicare qui.

### GUI v0.5+ — completato in questa sessione (post v0.5.1)

- [x] Credits overlay 2 colonne + tema scuro forzato + link GitHub/PayPal
- [x] Brand "Byte SwarmY" accanto al logo ape in toolbar
- [x] Tab progetti aperti con pulsante ➕ (QFileDialog)
- [x] Sidebar "Archivio progetto" dinamica (path del tab corrente)
- [x] Tab byte-swarmy hardcoded rimosso (solo cartelle reali)
- [x] Pulsante cartella gialla 📁 rimosso dalla toolbar
- [x] Code Explorer zoom +/- e reset ⟳ cablati (prima erano artefatti)
- [x] Splitter Code Explorer / Backup Code (era verticale, troppo largo)
- [x] Tab più alti (padding 10px 16px + min-height 22px)
- [x] Pannello Impostazioni interattivo (sostituisce testo statico)
- [x] Pannello Modelli → Attori (LLM + Decision Model + Timestral)
- [x] Pannello Coda Task → Code Task Scheduler (uno-shot/ricorrente/giornaliero)
- [x] Card plancia rinominate con descrizioni esplicative (Code Task,
  Modelli → Attori, Configurazione)
- [x] Menu contestuali (QMenu, QMessageBox) in tema scuro
- [x] `_do_git_save` reale: `git add + commit + push` con token iniettato
- [x] "Code Explorer" → "Navigatore di codice Interattivo"
- [x] Sidebar "TASK" → "Lavori e compiti"
- [x] "Logs CI/CD & Clean Code" spostato DENTRO la Plancia di controllo
- [x] Sezione "🧪 Test di integrità del software" in Plancia (IntegrityTestsPanel)
- [x] Sezione "🛡️ Sicurezza del software & anti-manomissione" in Plancia
      (SoftwareSecurityPanel con baseline hash SHA256 + check permessi)
- [x] × (close button) dei tab spostata più a sinistra (padding + QTabBar::close-button)
- [x] Card "🔄 CI/CD" in Plancia → CICDPipelinePanel (build/test/deploy reali)
- [x] Card "✨ Clean & Architecture Code" in Plancia → CleanCodePanel
      (analisi AST: funzioni lunghe, complessità ciclomatica, LOC)
- [x] "Logs CI/CD & Clean Code" → "Log - Diario di Bordo"
