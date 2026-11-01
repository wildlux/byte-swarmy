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

## ✅ Completato

Tutti i task completati (Cicli 1–13: sandbox, intent router, LLM tuner,
execute handler, T1–T4 work order, M1–M13, pulizia repo) sono registrati in
**`IMPLEMENTED.md`** — non duplicare qui.
