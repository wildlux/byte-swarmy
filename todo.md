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
14 repo-hygiene + 18 dotfile-security + 20 scheduler +
6 settings-store + 6 actors-panel).

GUI Control Center (v0.5.1+): credits overlay funzionante, brand "Byte SwarmY"
in toolbar, tab progetti aperti con pulsante ➕, sidebar "Archivio progetto"
dinamica, splitter Code Explorer / Backup Code, pannelli Impostazioni +
Attori + Code Task Scheduler, tema chiaro/scuro, push Git reale sui remote
configurati. **Cablatura parziale** dei pannelli su CORE/ — vedi sezione
"GUI: cablaggio funzionale" sotto.

---

## 🚨 Priorità 1 — Sicurezza & Bloccanti (subito)

Token e impostazioni non devono finire su GitHub. Effettua prima di tutto.


---

## 🟠 Priorità 2 — Roba che la UI promette ma non fa

I pannelli salvano impostazioni su JSON ma nessuno li legge. Cablare.

- [ ] **T2.1 Card plancia temabili** — Rimuovere `color:#1a1a1a` hardcoded
  da `title_lbl` in `PlanciaCard` (riga ~740 di `GUI/control_center.py`).
  Spostare i colori in variabili lette dal tema attivo. In dark theme i
  titoli delle card sono illeggibili (nero su bianco). Screenshot in
  entrambi i temi per verificare.

---

## 🟡 Priorità 3 — Nice to have (qualità percepita)

Non blocca, ma migliora molto la qualità percepita dell'app.

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
