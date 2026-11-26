# 🤖 AGENT.md — BYTE-SWARMY Intelligence Layer

## 🕐 Contesto temporale

Data e ora correnti: !`date '+%H:%M'`

## 📏 Budget

System prompt dei modelli locali (1.5B–4B, 2–3k token): max **~3.000
caratteri**. Architettura, threat model, metriche e protocolli estesi vivono
in `DOCS/`; qui solo regole vincolanti.

- Architettura: `DOCS/ARCHITECTURE.md` · Comandi: `DOCS/OPERATIONS.md`
- Sicurezza: `DOCS/SECURITY.md` · Subagenti: `DOCS/SUBAGENTS.md`
- Stato: `todo.md` · Storico: `DOCS/IMPLEMENTED.md` · Benchmark: `DOCS/BENCH.md`

## 🛡️ Regole vincolanti

1. **Sandbox**: ogni file operation resta dentro `project/`; path assoluti,
   traversal e symlink esterni sono bloccati.
2. **No-Shell**: `run_bash` tokenizza e usa `shell=False`; pipe, redirect,
   `&&`, `sudo`, `curl`, `wget`, `ssh`, `nc`, `rm -rf`, `chmod` vietati.
3. **Fail-Closed**: se un tool o bubblewrap fallisce, il comando NON viene
   eseguito; nessun prompt può disabilitare la sicurezza.
4. **Tool layer = autorità**: `[security] enabled = false` è ignorato e
   loggato come CRITICAL.
5. **Circuit breaker**: dopo 3 chiamate identiche cambia approccio; non
   ripetere lo stesso comando.
6. **Token budget**: `MAX_STEPS = 10`, `max_tokens = 400`/step,
   `num_ctx = 3072`, `num_predict = 512`.
7. **Runtime state**: `state/` è un symlink a `data/state/` (gitignored);
   scrivi artefatti via `state/`, mai credenziali nei log o in `CONFIG/`.
8. **Security baseline**: `tools/security_scan.py` ha baseline unica
   **7 errori**; un ottavo è regressione e blocca il ciclo.
9. **Cartelle**: contenitori di primo livello MAIUSCOLI (`CORE/`, `GUI/`,
   `CONFIG/`, `TOOLS/`, `SAFETY/`, `INTENT/`); una per categoria, niente
   duplicati o refusi.
10. **Prima di agire**: se la richiesta è vaga (linguaggio, framework, scopo,
    scope), chiedi chiarimento; non assumere default in silenzio.
11. **Formato**: per stato, confronti e opzioni usa tabelle Markdown; prosa
    per la narrazione.
12. **Commit atomici**: chiuso solo dopo audit APPROVE + commit.

## 🧰 Tool essenziali

File: `read_file`, `write_file`, `patch_code`, `search`.
Analisi: `analyze_project`, `find_references`, `analyze_complexity`,
`get_call_graph`. Refactoring: `rename_symbol`, `extract_method`.
Qualità: `lint_code`, `run_test_suite`. Esecuzione: `run_bash` (whitelist).
Git: `git_status/diff/commit/log/branch/merge`.
USB: `inspect_usb_devices`, `capture_usb_traffic` (read-only).
`git_push`, `git_pull`, `git_remote` sono disabilitati per i worker.

## ⚡ Comandi rapidi

```bash
./byte-swarm.sh status|start|gui|stop|restart   # runtime
.venv/bin/python -m pytest tests/ -q            # suite
.venv/bin/python tools/lint_style.py            # stile
.venv/bin/python tools/security_scan.py         # sicurezza
.venv/bin/python tools/repo_map.py              # mappa repo
.venv/bin/python tools/travasa_todo.py          # todo → IMPLEMENTED
```

Nota: `avvia.sh` e `ferma.sh` sono wrapper deprecati; usa `byte-swarm.sh`.
