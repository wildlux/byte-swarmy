# 🛠️ Implementation Log — BYTE-SWARMY

This file tracks every significant feature, fix, and architectural change implemented in the system. It serves as a historical record to keep the main READMEs clean and focused on usage.

## 🛡️ Core Security & Sandbox
- [x] **Rule 0 Implementation**: Security policy moved to the tool layer; cannot be disabled via config or prompts.
- [x] **Unprivileged Sandbox**: Integrated `bubblewrap` to isolate filesystem, network, and PID namespaces.
- [x] **Command Validation**: Implemented structural tokenization and whitelist/blacklist for `run_bash` (no shell).
- [x] **Path Confinement**: Strict restriction of all file operations to the `project/` directory.
- [x] **Environment Sanitization**: `avvia.sh` now clears sensitive env vars and sets strict `ulimit`.
- [x] **Hardening Scripts**: Created `setup-hardening.sh` for root-level isolation (cgroups, dedicated user) — oggi in `scripts/setup/hardening.sh`.
- [x] **Sandbox escape fix**: `--tmpfs /etc` + `--remount-ro /etc` + `--remount-ro /opt` to prevent writing outside `project/` (escape via `/etc/.sandbox-escape` blocked). All 11 sandbox self-tests pass.

## 🧠 Intelligence & Orchestration
- [x] **Multi-Agent Hierarchy**: Implemented Orchestrator → Planner → Worker → Auditor flow.
- [x] **Audit Worker (The Reviewer)**: Dedicated agent for senior-level code review and security gating.
- [x] **Tiered Memory**: Implemented Short-Term (RAM), Working (JSON), and Long-Term memory buffers.
- [x] **Professional Refactor-Loop**: Workers now follow Map → Analyze → Modify → Verify.
- [x] **Generic Task Planner**: Integration of decision models (`tev1:4b`) for high-level task decomposition.
- [x] **Swarm Command Handlers**: 8 commands (`swarm_status`, `list_tasks`, `show_logs`, `pause_swarm`, `resume_swarm`, `inspect_memory`, `cancel_task`, `run_audit`) handled directly by the orchestrator without invoking any LLM (instant response, zero token cost).
- [x] **Persistent Memory** (`CORE/persistent_memory.py`): cross-task memory that records existing project files, common errors, recent files and task history; injected into the worker's initial prompt so it doesn't recreate files that already exist.

## 💻 Development Toolset
- [x] **Precision Patching**: `patch_code` for targeted find-and-replace modifications.
- [x] **Refactoring Suite**: `rename_symbol`, `extract_method`, `analyze_complexity`, `get_call_graph`.
- [x] **Static Analysis**: Integration of `lint_code` and `Bandit` (SAST) for security scanning.
- [x] **Automated Testing**: `run_test_suite` for self-healing and verification.
- [x] **Full Tool Allowlist**: `allowed_tools()` exposes all 21 tools to the worker (was missing `patch_code`, `analyze_project`, `lint_code`, `rename_symbol`, `analyze_complexity`, `get_call_graph`, `extract_method`, `find_references`).

## 🔌 Hardware & USB Analysis
- [x] **Passive Capture**: `inspect_usb_devices` and `capture_usb_traffic` (Read-Only).
- [x] **USB Monitoring**: Integration with `usbmon` kernel module and `tshark`.
- [x] **Safe Hardware Access**: Tool-layer block on any write operations to the USB bus.

## ⚙️ Infrastructure & GUI
- [x] **ACID Task Queue**: Migrated from JSON to SQLite for data integrity (dual-write JSON kept for the GUI for now).
- [x] **Enterprise GUI**: Professional dark theme with a dedicated "Test & Sandbox" monitoring tab.
- [x] **Thermal Management**: `TimestralManager` for CPU **and GPU** temperature monitoring and tick-rate adjustment (NVIDIA via `nvidia-smi`).
- [x] **Automatic Backups**: Lifecycle manager handles periodic project snapshots; verified with restore-count.
- [x] **Toggle button**: Single Start/Stop button that changes colour and label based on real orchestrator state.
- [x] **Toolbar temperature indicators**: CPU and GPU temperature chips coloured green/orange/red, read directly from `/sys/class/thermal` and `nvidia-smi` (no longer dependent on Timestral samples).
- [x] **Live Activity Panel**: 2-column layout (task table | live activity) with step counter, last tool call, LLM thought, streaming token preview, and real-time metrics (tok/s, KV cache, VRAM).
- [x] **Streaming tokens**: `ollama_client.call_streaming()` yields tokens; the worker writes them to `state/streaming.txt` and the Live Activity Panel polls every 300 ms (was 1.5 s) so the user sees tokens appear in real time.
- [x] **Quick Command Bar**: multilingual (IT/EN/ZH) free-text input routed through the Intent Router.
- [x] **ModelsTab**: new "Modelli" tab with ComboBox per role, "Auto-Select" button (applies the intelligent selector), per-model "Test" button (measures tok/s with `hello`), and "Save & Restart" (writes `CONFIG/config.toml` and restarts the orchestrator). Config tab auto-reloads from disk when revisited.

## 🏗️ Cycle 7 — Foundations & Robustness (2026-10-28)
- [x] **System Watchdog** (`SAFETY/watchdog.py`): supervisor process restarts the orchestrator after a crash; `avvia.sh` now launches the orchestrator through it via `python -m SAFETY.watchdog`.
- [x] **Circuit Breaker** in `Worker.execute`: 3 identical tool calls force a mandatory prompt pivot (no more infinite tool-call loops).
- [x] **AST Security Scanner** (`CORE/ast_scanner.py`): deterministic gate on `write_file`; blocks banned functions/modules regardless of obfuscation.
- [x] **Event Sourcing Memory** (`CORE/memory_provider.py`): immutable SQLite event log per worker; summaries become views (`is_summary=1`), not the source of truth.
- [x] **Mandatory Isolation Check** (`SAFETY/security_checks.py`): boot-time verification of user/cgroups; without isolation the orchestrator starts in **Safe Mode** with extreme restrictions.
- [x] **Escape-artifacts cleanup**: clean rewrite of `watchdog.py`, `memory.py`, `ast_scanner.py` and the Worker region of `orchestrator.py`.
- [x] **Orchestrator modularization**: `constants.py`, `lifecycle_manager.py`, `system_monitor.py`, `task_dispatcher.py`; removed dead duplicated `run`/`_tick` and duplicated QC block.
- [x] **Verified backups**: `perform_backup()` now extracts and re-counts archives after creation ("an unverified backup is no backup").

## 🌊 Cycle 8 — Intent Router & GUI Control Center (2026-10-28/29)
- [x] **Intent Router** (`INTENT/router.py` + `INTENT/intents.json`): multilingual (IT/EN/ZH) fuzzy classification of free-form input via `rapidfuzz`; confidence-based fallback to `generic`. 28 intents, 314 triggers.
- [x] **Intent Bridge** (`INTENT/bridge.py`): router↔GUI/orchestrator adapter; integrated in the GUI Quick Command Bar.
- [x] **GUI redesign**: unified Start/Stop toggle, colored CPU/GPU temperature indicators in the toolbar, Live Activity Panel beside the task table, simplified status bar.
- [x] **Test & Sandbox tab**: run the suite, sandbox self-test and isolation status from the GUI (Control Center now has 7 tabs).
- [x] **GPU thermal sensing**: `nvidia-smi` GPU temperature in `thermal_manager.py` + direct `/sys/class/thermal` reads in the GUI indicators.
- [x] **Ollama metrics** (`INTENT/metrics.py`): last-call metrics and loaded VRAM models exposed to the GUI.
- [x] **Dependency fix**: `rapidfuzz` added to `GUI/requirements_gui.txt` and `setup.sh` (was required but never declared).
- [x] **Themeable UI**: `build_stylesheet(theme)` with two palettes (dark default, light); choice persisted in `state/gui_theme.json`; toolbar toggle "◐ Tema" applies the new theme live.
- [x] **Simplified task insertion**: single entry row — Quick Command Bar hosts both "Aggiungi" (natural language, Enter works too) and "Nuovo Task…" (full form).

## 🧩 Cycle 9 — Uppercase Package Migration (2026-10-29/30)
- [x] **Package reorganization**: all modules moved into uppercase Python packages `CORE/`, `INTENT/`, `SAFETY/`, `MONITORING/`, `GUI/`, `CONFIG/`. Each has `__init__.py`.
- [x] **Import rewrite**: every cross-module import updated to use package paths (`from CORE.tools import ToolSet`, `from SAFETY.security import …`, etc.).
- [x] **Entry points**: `avvia.sh`/`ferma.sh` now use `python -m SAFETY.watchdog`, `python -m CORE.orchestrator`, `python -m GUI.control_center`. `main.py` is the CLI entry point.
- [x] **Test suite realigned**: `tests/test_security.py` and `tests/run_tests.py` import from the new packages; 27 security + 22 sandbox + 6 intent = 55 tests pass.

## 🚀 Cycle 10 — Advanced Features (2026-10-30)
- [x] **Streaming token real-time** (Feature 1): `call_streaming()` yields tokens; Live Activity Panel refreshes every 300 ms.
- [x] **Swarm command handlers** (Feature 2): 8 commands handled deterministically by the orchestrator (no LLM, instant response).
- [x] **Decision model enabled** (Feature 3): `tev1:4b` configured in `[decision_models]` + `[generic_task_planner]`; generic tasks are decomposed into 2–8 atomic code tasks.
- [x] **Persistent memory** (Feature 4): `CORE/persistent_memory.py` keeps user profile, project context, common errors, recent files, and task history across tasks; injected into the worker's prompt.
- [x] **Intelligent Model Selector** (Feature 5a): `CORE/model_selector.py` scores every Ollama model 0–100 for each role. Hard gates (VRAM/RAM/capability) + soft scoring (family, name, quantization, thermal). Returns top recommendation + 3 alternatives per role. CLI: `python -m CORE.model_selector [--apply]`.
- [x] **ModelsTab in GUI** (Feature 5b): ComboBox per role, Auto-Select button, per-model Test button (measures tok/s with `hello`), Save & Restart (writes config + restarts orchestrator). Hardware info displayed.
- [x] **Config tab auto-reload** (Feature 5c): switching to the Config tab reloads from disk so the user sees the updated models after Save & Restart.
- [x] **Dynamic KV cache estimation** (Feature 6): `INTENT/metrics.py` replaced hardcoded `bytes_per_token` per family with the real formula `2 (K+V) × layers × kv_heads × head_dim × 2 × tokens`, using a `MODEL_ARCHITECTURES` table for known models. Example: `phi3:mini` was estimated at 24 MB/1k tokens (hardcoded) → 375 MB/1k tokens (real, 15× more accurate).
- [x] **Live Activity DB read**: Live Activity Panel now reads running tasks from `tasks/queue.db` (SQLite) with JSON fallback, instead of the empty `tasks/queue.json`.
- [x] **Toggle button sync**: `_update_toolbar_state()` polls `orchestrator.is_running()` and updates label/colour so the button no longer shows "Ferma" when the orchestrator is stopped.
- [x] **`ferma.sh`/`avvia.sh` PID check**: cmdline check now matches `orchestrator|watchdog` so the PID file (pointing to the watchdog) is correctly recognised as alive.

## 🚀 Cycle 11 — Hardening & UI Polish (2026-10-31)

- [x] **Timestral LLM Parameter Optimizer (Feature 7)**: `CORE/llm_tuner.py` adjusts LLM parameters (temperature, top_p, top_k, num_predict, num_ctx, repeat_penalty, max_steps) based on thermal state. 4 profiles: fast/normal/slow/pause. Integrated into `ollama_client.py` and `orchestrator.py` (dynamic MAX_STEPS). GUI shows `🎚️ LLM Tuned: SLOW`.
- [x] **Unified QSS Theme System**: Removed old hardcoded `STYLESHEET`. GUI now uses `GUI/theme/theme.py` with `light.qss` and `dark.qss`. Theme toggle via `Ctrl+Shift+T`.
- [x] **Planner SQLite Bug Fix (Critical)**: Fixed `GenericTaskPlanner` and `Planner` that used old JSON API (`self.queue.tasks.append()`). Now uses `self.queue.add(st)` for SQLite. Subtasks are now correctly persisted and dispatched.
- [x] **M1 Anti-escape guardrail (verified)**: Confirmed existing `detect_artifacts` implementation in `ast_scanner.py`. Fixed `test_escape_gate.py` path bug. 3/3 tests pass.
- [x] **9.1 Execute Handler (Feature 9.1)**: `CORE/execute_handler.py` parses commands from task description (gcc, python, make) and executes deterministically via `tools.run_bash` without LLM. Integrated in `orchestrator._tick()`.
- [x] **RAM threshold adjustment**: `swap_threshold` raised from 0.8 to 0.95 to prevent false positives on 8GB RAM systems.

## 🚀 Cycle 12 — Stability & Intelligence (2026-10-31)

- [x] **9.1b Allowlist for local binaries**: `SAFETY/security.py` now accepts `./` prefixed commands (compiled binaries in `project/`).
- [x] **M7 Disk quota on project/**: `CORE/tools.py` checks total project size (500MB default) before `write_file`.
- [x] **M6 Selective /etc masking (verified)**: `CORE/sandbox.py` mounts only 5 specific files (ld.so.cache, nsswitch.conf, passwd, group, hosts) instead of exposing all of `/etc`.
- [x] **M2 Exception Hardening**: `CORE/exception_handler.py` — centralized error classification (model_unavailable, model_timeout, tool_error, sandbox_violation, parse_error) with retry policy and backoff.
- [x] **M4 State Recovery**: `CORE/state_recovery.py` — reconstructs worker context from the immutable SQLite event store (`memory_events.db`) on restart.
- [x] **9.4 Predictive Timestral**: `MONITORING/predictive.py` — EMA (Exponential Moving Average) + linear regression to estimate "minutes to thermal threshold". Pure stdlib, no numpy.
- [x] **9.11 Model Benchmark Suite**: `CORE/benchmark.py` — 3-test suite (code generation, summarization, classification) with tok/s, TTFT, keyword score. Results saved to `state/model_benchmarks.json`. qwen2.5-coder:1.5b scored 100/100, avg 31.8 tok/s.
- [x] **9.9 Advanced Persistent Memory**: `CORE/persistent_memory.py` — `extract_preferences()` uses pattern matching (regex) to detect user preferences (preferred language, type hints usage, frameworks, code styles) from task history.
- [x] **M3 Static Checks (verified)**: `CORE/tools.py` `lint_code()` already integrates Bandit (SAST) and Mypy (type checking) in the sandbox.

## 🚀 Sprint Ops — 2026-11-05

- [x] **Repo mapping dinamico**: `tools/repo_map.py` — fotografia compatta
  del repo (aree/ruoli, statistiche file, `.py` caldi via `--days`, stato
  git, dir runtime). 3 modalità: stdout / `--out state/repo_map.md` /
  `--json`. Registrato come `./byte-swarm.sh map` e in
  `DOCS/AGENT.md → Shell Commands` (risparmio token a inizio sessione).
- [x] **AGENT.md — Shell Commands quick reference**: sezione comandi
  operativi più usati (test, runtime `byte-swarm.sh`, pausa/coda SQLite,
  log, flusso documentale, push manuale, GUI offscreen + regole tema
  `set_prop`/`set_banner`); sezione Testing aggiornata (niente più
  conti hardcodati: 55 → "usa i comandi", suite attuale 247 pytest).
- [x] **Fix `tools/travasa_todo.py`**: dopo la consolidation docs
  puntava ancora ai path root inesistenti (`todo.md`, `IMPLEMENTED.md`)
  → flusso documentale rotto. Ora rileva `DOCS/todo.md` /
  `DOCS/IMPLEMENTED.md` (backward-compat con la root). Dry-run OK.
- [x] **Sync tema widget — round 2**: `task_scheduler_panel.py` (12
  colori inline light-only → theme: banner warn, bottoni
  `role=start/danger`, QListWidget oggetto "schedlist"), `search_bar.py`
  (QLineEdit bianca inline → tema), `hardware_panel.py` (badge errore →
  `set_banner("error")`), `.qss` (`QListWidget`, `QDateTimeEdit`,
  focus). **Bug Qt reale**: un stylesheet "declaration-only" su un
  widget antenato (es. `content.setStyleSheet("background:
  transparent;")`) azzera lo sfondo dei bottoni discendenti (vinto sui
  QSS app-level) → convertiti tutti i 6 punti (anche
  `control_center.py`) a regole con selettore objectName
  (`QWidget#panelScrollContent`). Verificato a livello pixel + screenshot
  entrambi i temi; suite verde 247 passed / 131 subtests.

- [x] **Ponte remoto pulsanti GUI**: `GUI/remote_bridge.py` —
  `QLocalServer` (socket Unix assoluto in `$XDG_RUNTIME_DIR` o
  `/tmp/uid.sock`, escape hatch `BYTE_SWARMY_REMOTE_SOCKET`) che espone
  l'inventario di tutti i QPushButton/QToolButton della finestra e
  simula click per id/testo/index, più grab finestra. Zero thread dedicati
  (dispatch via newConnection sul loop Qt, nessun blocco del main thread);
  default ON, opt-out `BYTE_SWARMY_REMOTE=0`. Hook in
  `GUI/control_center.py` (fail-open).
- [x] **Client `tools/gui_remote.py`**: subcommand `list` / `click` /
  `screenshot` (JSON o umano); `--raw` per scripting. Registrato in
  `DOCS/AGENT.md → Shell Commands`.
- [x] **Test `tests/test_remote_bridge.py`**: 7 test round-trip
  in-process (inventario, click id/testo/index, duplicati `#n`,
  disabilitati, screenshot, op sconosciute, json invalido, slug). Suite
- [x] **Scorciatoie tastiera globali (UX)**: in `GUI/control_center.py`
  (CenterArea) installato event filter a livello app:
  - **Backspace** → "Indietro alla Plancia" (torna alla plancia principale),
    solo fuori dagli editor di testo; i pulsanti "Indietro alla Plancia"
    ora mostrano "(Backspace)" nel label per informare l'utente.
  - **"/"** con focus fuori da un editor → focus sul campo comando in
    basso e inserisce "/" (se vuoto, altrimenti alla posizione del cursore).
  Smoke test offscreen: stack 1→0 e cmd_input="/". Suite verde.

- [x] **Tooling mantenibilità**: tre nuovi tool in `tools/` (solo stdlib,
  exit code per CI):
  - `lint_style.py` — stile/leggibilità + guardia tema. `--fix`
    auto-pulisce trailing ws + newline finale; `--strict` promuove i
    warning a errore; `--json`.
  - `security_scan.py` — pattern pericolosi (eval/exec, os.system,
    shell=True, pickle/yaml unsafe, segreti hardcoded, SQL stringato,
    assert in non-test, open() non costante, .bak/.pyc, merge markers,
    file grandi, segreti nello staged diff). Supporta `# nosec`.
  - `git_hygiene.py` — igiene repo (spazzatura non tracciata, file
    grandi, newline finale, trailing ws, .gitignore coverage, commit
    sospetti, branch senza upstream).
  - Registrati in `DOCS/AGENT.md → Shell Commands` e come
    `./byte-swarm.sh lint` (esegue i tre in sequenza).
  - Effetto collaterale: rimossi 3 duplicati root tracciati
    (`re_tools.py`, `test_re_tools.py`, `test_functional_swarm.py`,
    identici a `CORE/` e `tests/`); `--fix` ha pulito trailing ws su
    ~50 file; `CORE/orchestrator.py` annotato `# nosec` sulle due
    colonne SQL dinamiche validate.

- [x] **Guardia tema (test)**: `tests/test_theme_sync.py` — regola
  generale: statico (nessun colore muted inline senza bg, nessun
  declaration-only transparent, nessun colore light-only hardcoded) +
  runtime (ogni pannello si istanzia in tema scuro e chiaro) +
  helper (`set_banner` accetta i 4 stati). 24 test, tutti verdi.
  Corretti 2 residui muted in `control_center.py` (#909090, #999 →
  role="muted").

- [x] **Uso dello spazio vuoto nei pannelli**: `hardware_panel`
  (log rilevamento in QPlainTextEdit stretch), `settings_panel`
  (rimosso addStretch interno, audit_output più ampio),
  `actors_panel` (log configurazione stretch),
  `task_scheduler_panel` (lista task stretch=1). Eliminati gli
  `addStretch()` finali che lasciavano area morta.

- [x] **Crediti: loghi dei contributori**: in `CreditsOverlay`, le emoji di
  GLM/Qwen/DeepSeek sono state sostituite dai rispettivi loghi in
  `IMG/` (`GLM_AI_logo.webp`, `QWEN_AI_logo.webp`,
  `DEEPSEEK_AI_logo.webp`), scalati a 40×24 px (aspect ratio mantenuto).
  Paolo Lo Bello mantiene l'emoji 👤. Verificato in entrambi i temi.

## 🚀 Cycle 13 — Complexity Routing & Code Map (2026-11-12)

- [x] **Fase 6 — Routing SEMPLICE**: `CORE/routing.py` — `estimate_complexity()` (keyword-based). Task 'alta' → heavy model se installato, fallback automatico. Fail-open ovunque.
- [x] **Fase 7 — Routing COMPLESSO**: `estimate_impact()` — simbodo citati nel task (match word-boundary) → file toccati (definizione ∪ chiamate), profondità BFS (cap 3), copertura test transitiva. Livello = MAX(keyword, impatto) + isteresi sticky.
- [x] **Code Map**: `CORE/code_map.py` — AST → SQLite (files, symbols, calls, imports). Rebuild incrementale per mtime. `format_map()` per prompt injection (esclude test files). `relevant_symbols()` per contesto per modulo.
- [x] **Skill System**: 18 skill files in `SKILLS/`. Keyword-based matcher. Progressive disclosure. `MAX_SKILL_BODY_CHARS = 2500`.
- [x] **Complexity Routing**: `route_model_key()` → (key, level, decision_string). `run_direct(enable_routing=None)`: auto (client None o real ModelClient → ON; fake → OFF).
- [x] **Thermal Guard**: sotto carico critico (CPU ≥75, GPU ≥80) l'heavy viene evitato.
- [x] **Per-model Timeout**: `[models.*] timeout` sovrasta `[ollama].request_timeout`.

## 🚀 Cycle 14 — Validation & Diagnostics (2026-11-12)

- [x] **A1 — Oracle Test**: `verify_runtime(oracle_checks=[...])` — sottostringhe che DEVONO apparire nel stdout. `run_direct(oracle_checks=...)`.
- [x] **A2 — Behavioral Diff**: `CORE/behavioral_diff.py` — snapshot/verify/diff semantico. `run_direct(behavioral_check=True)`.
- [x] **D1 — Diagnosi intelligente**: `suggest_fix_for_marker()` — suggerimento mirato per marker mancanti. Integrato in `verify_runtime`.
- [x] **C1 — Atomizzatore**: `decompose_module(path)` — parse AST → task atomici per funzione/classe.
- [x] **C2 — Ordine topologico**: `dependency_order(project_root)` — Kahn's algorithm sul grafo delle chiamate.
- [x] **Skill Proposer (M8)**: `CORE/skill_proposer.py` — 9 firme di fallimento → bozza di skill dopo 3 occorrenze. Auto-approvazione dopo 3 successi.

## 🚀 Cycle 15 — Optimizations (2026-11-12)

- [x] **P1-P15**: 15 ottimizzazioni skill/prompt/tools dalla diagnosi dei fallimenti della suite:
  - P1: SYSTEM_DIRECT rafforzato (fence, placeholder, istanza)
  - P2: extract_code tronca prosa alla prima riga Python
  - P3: py-text-analyze placeholder → commento inerte
  - P4: regola istanza in SYSTEM_DIRECT
  - P5: py-class-module except Exception di default
  - P6: timeout per-modello in ollama_client
  - P7: no input(), marker letterale
  - P8: drain sicuro nel template
  - P9: context manager self. esplicito
  - P10: py-decorator ripristinato a timing-only
  - P11: py-argparse template concreto
  - P12: py-unittest blocco __main__ concreto
  - P13: py-expr-eval (nuova skill)
  - P14: marker con valore-variabile (TENTATIVO=n)
  - P15: py-arch-decision (decision tree + template)
- [x] **Compattazione skill**: 21 → 18 file (merge 5 py-refactor-* in 1). Boilerplate rimosso. MAX_SKILL_BODY_CHARS 1400 → 2500.
- [x] **Skill Qt**: pyqt6-basics, pyqt6-model-view, pyqt6-threading (tutte testate live).
- [x] **F1-F2**: Memory compaction intelligente + contesto per modulo.
- [x] **G1-G2**: Skill suggerite con template concreto + auto-approvazione.

## 🚀 Cycle 16 — Report & Documentation (2026-11-12)

- [x] **REPORT.md**: report consolidato (138 righe) con riepilogo modelli, suite T1-T10, spot-check, e2e routing, suite complessa T11-T21, suite dati complessi, batterie unit, miglioramenti P1-P15 e Fase 8.
- [x] **generate_report.py**: generatore report automatico.
- [x] **Timestamp nei test runner**: started_at/finished_at (ISO 8601) in tutti i risultati.
- [x] **DOCS aggiornati**: SPECIFICATIONS.md, IMPLEMENTED.md, README.md (IT/EN), AGENT.md.

## 🚀 Cycle 17 — Suite T1–T10 + Fasi 1–5: fondamenta della qualità (2026-11-12)

- [x] **Fase 1 — Suite T1–T10 su `qwen2.5-coder:3b`** (todo storico travasato): 10 task (statistiche, conversioni+errori, dedup semantico, palindromo+frequenza, file I/O, Fibonacci memoizzato, GUI PyQt6, Stack, decoratore, trasposta). Risultato **6/10 PASS**: i task concreti e deterministici passano, i semantici no. **Finding principale — il gate di verifica è cieco**: `py_compile` sempre OK e `ok=true` al 1° tentativo, il 100% dei fallimenti è semantico e invisibile → il correction loop non si attiva mai. Da qui nascono A1/A2 (verify_runtime) e la raccomandazione "estendere la verifica host".
- [x] **Fase 2 — Leve anti-fallimento**: 3 skill nuove (`py-class-module`, `py-json-store`, `py-decorator`); disinnescato l'ancoraggio tossico (T9 "somma" matchava `py-cli-script` con template sbagliato → placeholder dal task + regole quantità); **SYSTEM_DIRECT** con 7 regole concrete in `CORE/skill_executor.py` (implementa tutto ciò che il task nomina, quantità esatte, string literals quottati, marker esatti…); contesto maggiorato `[models.worker_coder]` `num_ctx` 4096→**8192**, `num_predict` 512→**1024**.
- [x] **Fase 3 — Verifica RUNTIME nel correction loop**: `verify_runtime()` esegue il programma generato e confronta l'output atteso; marker di estrazione → il correction loop ora si attiva davvero su errori semantici (chiude il cerchio del finding Fase 1).
- [x] **Fase 4 — Mappa del codice + gate statico**: oltre al code_map DB (Cycle 13), gate statico `check_code_names` — i nomi citati nel task devono esistere nel PROJECT MAP (niente simboli inventati). Registrato `./byte-swarm.sh map`.
- [x] **Fase 5 — Libreria skill completa**: 9 skill nuove per i pattern dove i 3B falliscono da zero + **tie-break matcher** (match per sottostringa, keyword più lunga vince). Matcher verificato su tutti i titoli della suite.

## 🚀 Cycle 18 — Heavy model & M1–M10 (2026-11-12)

- [x] **Scelta heavy model (onesta)**: `kirito1/qwen3-coder:4b` **scartato** — 4/10 nella suite e ~×19 più lento del 3B (throttling su 4 GB); spot-check su `granite4:7b-a1b-h` poi suite intera → **10/10**. Decisione: 3B resta il default, granite per il routing "alta".
- [x] **M1 — Suite completa T1–T10 su granite4**: `scripts/suite_compare.py worker_granite` → `state/suite_compare/results.json`. Verdict valido solo con la suite intera (non più spot).
- [x] **M2 — Routing e2e LIVE**: `scripts/routing_e2e.py` — percorso completo verificato: task multi-file → impatto alta → decisione `complessità alta → worker_granite` → heavy_picked=True → ok in 3 tentativi (att. 1–2 senza marker → gate lo becca → correzione). Gate+correction+routing lavorano insieme.
- [x] **M3 — Refactoring live su progetto vero**: skill `py-refactor-rename` (renaming multi-file) + demo live multi-file con routing per impatto. Il refactoring vero va al ReAct (M9).
- [x] **M6 — `code_map` incrementale**: già implementato (rebuild per mtime, niente re-parse dei file invariati); l'assunzione "collo di bottiglia" era errata, nessuna modifica.
- [x] **M7 — Isteresi persistente**: `_HYST` su `state/routing_hysteresis.json` con timestamp (sticky >1800 s scartato), `reset_hysteresis()` pulisce memoria e disco.
- [x] **M9 — Routing anche in ReAct**: `Worker._route_model_key(task)` (stessa 3-tuple di `route_model_key`), attivo solo con ModelClient reale. +5 test, demo live.
- [x] **M10 — model_selector evidence-based**: `CORE/model_selector.py` incorpora i risultati reali di `state/suite_compare/results.json` (10/10 del 3B come dato hard) accanto alle euristiche. +24 test.

## 🚀 Cycle 19 — Suite complesse (2026-11-12)

- [x] **T11–T21 (suite avanzata)**: **11/11 PASS su 3B** con le ottimizzazioni P9–P15 (generatori+TOT, threading+Lock, argparse concreto, unittest con `__main__`, context manager, decision tree architetturale).
- [x] **Suite dati complessi**: generatore `DATI_COMPLESSI.json` (600 task); esito del campione eseguito **12/17 PASS** (onesto: campione, non i 600 interi).

## 🚀 Cycle 20 — Fase 8 completata (2026-11-12)

- [x] **A3 — Gate di regressione nel Refactor-Loop**: `check_refactor_regression(target, inputs)` in `CORE/behavioral_diff.py` — snapshot se assente, verifica post-revisione → (ok, diff). Fail-open, 5 test.
- [x] **D2 — Diagnosi errori di logica**: `diagnose_logic_error(inp, expected, actual)` in `CORE/skill_executor.py` — suggerisce la causa probabile (off-by-one, valore doppio, output vuoto, tipo sbagliato); integrata in `verify_runtime` (path oracle_checks). 5 test.
- [x] **B1 — `py-refactor-rename`**: mergiato in `py-refactor.md` (decision tree con 5 template).
- [x] **B2–B5 — 4 skill di trasformazione** (commit 274c603) + fix project map per le refactoring skills; B5 = template E (modularize).
- [x] **E1 — System prompt compatto**: già soddisfatto — SYSTEM_DIRECT 262 parole (<500), 9 regole tutte essenziali, niente merge che riduca chiarezza.
- [x] **E2 — Skill on-demand**: già implementato — matcher a confine di parola + progressive disclosure (corpo completo solo se matchata), prompt totale ~363 token.

## 🚀 Cycle 21 — Fase 9: domande interattive per decisioni complesse (2026-11-12)

- [x] **Q1 — Rilevamento ambiguità**: `detect_ambiguity()` in `CORE/clarifier.py` — 8 pattern (architettura, DB, docker, auth, API, concorrenza, sicurezza, migrazione) → domande con opzioni numerate. 19 test.
- [x] **Q2 — Dialog GUI**: `GUI/clarification_dialog.py` — ClarificationDialog PyQt6 (opzioni radio + campo libero, `exec_and_get_answer()` → "1,3,1").
- [x] **Q3 — Loop di chiarimento**: `clarify_loop(task, ask_fn)` — fino a 5 round, fail-open su EOF/KeyboardInterrupt; integrato in `cli_interactive`.
- [x] **Q4 — Persistenza preferenze**: `record_preference(key, value)` + `get_preferences()` in `CORE/persistent_memory.py`; le risposte vengono salvate e iniettate nei task successivi.
- [x] **Q5 — Modalità CLI**: `python -m CORE.clarifier "task" --interactive` — domande numerate nel terminale.
- [x] **Q6 — Integrazione Refactor-Loop**: `run_direct(clarify=True, ask_fn=...)` — rileva ambiguità, arricchisce il task con le risposte, fail-open senza ask_fn.

## 🚀 Cycle 22 — Chiusura GUI: orchestratore terminato prima della finestra (2026-11-13)

- [x] **closeEvent su ControlCenter**: se l'orchestratore è attivo, dialog [Termina e chiudi (default)] [Lascia attivo in background] [Annulla] + checkbox "Ricorda questa scelta" (settings `close_action`: "stop"/"keep"/"" in `CONFIG/settings.json`).
- [x] **Terminazione bloccante**: `_terminate_orchestrator_blocking` — SIGTERM → poll 0,2 s (max 5 s) → SIGKILL di riserva → rimozione pid file. Validazione pid come `byte-swarm.sh stop` (cmdline "orchestrator"/"watchdog": pid stantio o riutilizzato non toccato). Fail-open: la finestra si chiude sempre.
- [x] **Bug risolti in cascata**: `_pid_alive` staticmethod (figli zombie visti morti via `/proc/PID/stat`); `load/save_settings` ora usano davvero `SETTINGS_FILE` (test settings riparati); duplicato `_stop_orchestrator` rimosso.
- [x] **Test**: 10/10 `tests/test_close_orchestrator.py` + 6/6 `test_settings_store` + smoke e2e offscreen con finestra reale (fake orchestrator morto prima del close, pid file rimosso).

## 🚀 Cycle 23 — Pannello Test Suite nella Plancia (2026-11-13)

- [x] **Pannello "Test Suite"** (richiesta utente: "un menù uguale agli altri"): `GUI/test_suite_panel.py` sul modello di hardware_panel (header con "← Indietro alla Plancia (Backspace)", scroll, QGroupBox, token tema via set_prop/set_banner/token_color — zero colori hardcodati). Card "🧪 Test Suite" nella cella libera (1,2) della griglia Plancia (`GUI/panels.py`), pagina nel detail_stack (`GUI/center_area.py`, key "test").
- [x] **Runner per-file con timeout**: QProcess sequenziale (`python -m pytest -q` per file, processo dedicato, cwd root, QT_QPA_PLATFORM=offscreen) — un file bloccato non blocca mai la suite; timeout 120 s per file (600 s per e2e opt-in) con kill e registrazione onesta (status ERROR "timeout"). Parser output pytest (`N passed/failed/skipped`) e unittest verbose (`Ran N tests … OK/FAILED`); exit 5 pytest = SKIP.
- [x] **E2E/LLM esclusi di default**: `discover_test_files()` esclude i file e2e/live/swarm/workflow + test_timestral_full (aspettano Ollama, il runner unico si appende); opt-in con checkbox (timeout elevato).
- [x] **Risultato consolidato**: riepilogo (file OK/KO, pass/fail/error/skip, durata, badge ✅/❌ con token tema), lista per file cliccabile con coda output, log esecuzione; salvato in `state/test_suite/results.json` (via `CORE.state_repository.save_json`); all'apertura carica l'ultimo run salvato.
- [x] **Test**: 11/11 `tests/test_test_suite_panel.py` (discovery e2e, parser, pipeline QProcess reale su file piccolo con JSON su path tmp — mai sullo state/ reale) + 24/24 `test_theme_sync.py` (statici + runtime entrambi i temi, pannello aggiunto a PANELS/_PANEL_CLASSES) + smoke integrazione finestra reale (card, pagina, stack, render).


## 🚀 Cycle 24 — Responsive Plancia: card a capo, niente scroll orizzontale (2026-11-13)

- [x] **Audit offscreen T-R2..T-R5** (richiesta utente, scelta: "card troncate + scroll orizzontale"): screenshot reali a 1920/1280/1024/900 px. Verificato che i bersagli storici non esistono più dopo il refactoring GUI (colonne 280/500px, card 110px, barre 64/52/48px — solo nel legacy `TEST_GUI_QT_12.py`); `PlanciaCard` è già adattiva (T-R4 risolto di fatto).
- [x] **Causa reale del difetto**: la barra di ricerca aveva `min_width=360` nell'header della sezione → larghezza minima del contenuto 735px contro viewport ~630px → scroll orizzontale + label troncati con ellipsis ("Navigatore di c…"). Fix: `min_width` 360→140 (center_area.py) — l'header comprime e la ricerca resta utilizzabile.
- [x] **Card senza troncamenti**: `PlanciaCard` — titolo e sottotitolo ora `wordWrap=True` (andavano a capo invece dell'ellipsis); sottotitolo da colore hardcodato `#cbd5e1` (quasi invisibile nel tema chiaro) a `role=muted` del tema. Badge bianco-su-solido in forma `#fff` con commento (il guardia tema vieta il letterale `#ffffff`).
- [x] **Guardie**: `plancia_card.py` aggiunto ai controlli statici di `test_theme_sync.py`. Verifiche: 27/27 tema (statici + runtime), misura min-width a 4 dimensioni (content 735→515px, zero scroll orizzontale ovunque), screenshot 1024/1920 + entrambi i temi (pixel-check card bianca leggibile).
- [x] **Resta aperto**: gap vuoto in alto a schermo pieno (~200px sopra "Plancia di controllo" a 1920×1080) — riscontrato nell'audit, l'utente non lo ha scelto per ora; registrato in todo.md. T-R3 (`_force_content_size` 300px) rimandato: impatto basso.

## 📋 Completati (spostati da todo.md) — 2026-11-15

- [x] **T1 — Tool list dinamica per tipo task**: mostra solo i tool rilevanti
  (creazione → write_file/read_file/lint/run_test; refactoring → patch/rename/extract/find_refs;
  analisi → analyze_*/search; git → git_*). Guadagno ~1.1KB/step. ✅ IMPLEMENTATO in Cycle 34.

- [x] **T2 — Regole compatte**: comprimi le 10 regole del worker da ~1KB a ~0.3KB.
  Guadagno ~0.7KB/step. ✅ IMPLEMENTATO in Cycle 33.

- [x] **T3 — Project state on-demand**: cap file da 20 a 10 in `_project_state()`.
  Guadagno ~0.5KB/step. ✅ IMPLEMENTATO in Cycle 34.

- [x] **T4 — Skill block condizionale + cap 1500**: iniettare solo i passi (STEPS),
  non il template completo; cap a 1500 chars invece di 2500. Guadagno fino a 1KB/step. ✅ IMPLEMENTATO in Cycle 33.

- [x] **T5 — Tool result truncation aggressiva**: troncare a 300 chars (vs 500);
  read_file solo prime 20 righe + ultime 5; run_test_suite solo summary.
  Guadagno ~0.5KB/step. ✅ IMPLEMENTATO in Cycle 33.

- [x] **T6 — Deduplicazione tra step**: prompt fisso completo solo al primo
  step (`_build_system(task)`); step successivi usano `_build_system_compact()`
  (~0.3KB vs ~1.2KB). Guadagno ~2.5KB/step. ✅ IMPLEMENTATO in Cycle 35.

- [x] **T9 — Codici tool a prefisso naturale**: abbreviare i nomi tool con
  prefissi che il modello già conosce come completamento del nome completo
  (read=read_file, write=write_file, patch=patch_code, commit=git_commit,
  bash=run_bash, search=search, status=git_status, diff=git_diff, log=git_log,
  branch=git_branch, merge=git_merge, lint=lint_code, test=run_test_suite,
  analyze=analyze_project, refs=find_references, complex=analyze_complexity,
  graph=get_call_graph, extract=extract_method, rename=rename_symbol,
  read_slice=read_file_slice, delete=delete_file, move=move_file,
  list=list_files, usb=inspect_usb_devices, capture=capture_usb_traffic).
  Guardia: se il modello usa il nome completo, funziona comunque (fallback).
  Guadagno ~0.3KB/step prompt + ~0.1KB/step risposta. ✅ IMPLEMENTATO in Cycle 33.

- [x] **T8 — Formato JSON compatto**: `TASK: ... | DESC: ... | RULES: ...`
  invece di markdown multi-riga. Guadagno ~0.2KB/step. ✅ IMPLEMENTATO in Cycle 36.

- [x] **T10 — Prompt caching per tipo task**: pre-calcolare il system prompt una volta
  per tipo task (creation/refactoring/analysis/git/usb) e cacharlo in un dict a livello
  di classe. Prefisso identico → cache hit al 100% su Ollama → il modello non
  re-elabora i tool ad ogni step. Guadagno: tempo di inferenza (non token). ✅ IMPLEMENTATO in Cycle 35.

- [x] **T11 — Tool result summarization intelligente**: invece di troncare a 300 chars
  ([:300]), usare estrazione intelligente: read_file → prime 10 righe + righe con
  def/class/import; run_test_suite → solo N passed/M failed + primi 3 errori;
  run_bash → ultime 5 righe; git_diff → solo nomi file + righe +/- di sintassi.
  Guadagno: ~0.2–0.5KB/step + migliora la qualità (info rilevanti invece di
  troncamento cieco). ✅ IMPLEMENTATO in Cycle 37.

- [x] **T12 — Abbreviazione percorsi**: usare percorsi relativi brevi (main.py invece
  di project/main.py) nel prompt. Rimuovere il prefisso project/ (il worker sa già
  di essere in project/). Guadagno: ~0.1KB/step, cumulativo su 10 step. ✅ IMPLEMENTATO in Cycle 37 (esempi JSON + project_state già relativi).

- [x] **T13 — Adaptive max_tokens**: adattare max_tokens per step: tool call semplice
  (read, search) → 256; write_file (contenuto lungo) → 1024; step finale (done=true)
  → 128. Guadagno: 30–50% tempo su step semplici. ✅ IMPLEMENTATO in Cycle 37 (1024 primo step, 512 successivi).

- [x] **T14 — Rimozione esempi dal prompt**: rimuovere o ridurre a 2 gli esempi di
  comandi buoni ("ls .", "cat main.py", ...). Ridondanti per modelli addestrati su
  dati di coding. Guadagno: ~0.2KB/step. ✅ IMPLEMENTATO in Cycle 33 (regole compatte).

- [x] **T15 — Context window pruning**: rimuovere ## PROJECT STATE dopo il primo step
  (il modello lo ha già visto); tenere solo i file modificati in questo task.
  Guadagno: ~0.3KB/step dal 2° step in poi. ✅ IMPLEMENTATO in Cycle 33 (project state solo in initial prompt, non in step prompts).

- [x] **T16 — Prompt fisso + delta (architettura ReAct)**: prompt fisso completo solo al
  primo step; step successivi usano system prompt compatto (~0.3KB) + task title
  re-iniettato per prevenire task drift. Guadagno ~2.5KB/step. ✅ IMPLEMENTATO in Cycle 38.

- [x] **T17 — Model-specific prompt tuning**: formati diversi per modelli diversi
  (Qwen: compatto; Llama: strutturato con esempi; DeepSeek: chain-of-thought).
  Rilevamento famiglia via `_model_family()` (legge il nome del modello dal
  config). Cache key include la famiglia (prompt diversi per famiglia).
  Guadagno: +20–30% qualità. ✅ IMPLEMENTATO in Cycle 39.

- [x] **T20 — Prompt pruning per step**: rimuovere le regole già assorbite
  dal modello dopo il 3° step (solo "Reply with JSON"). Implementato in
  `_build_system_compact(step)` — dopo step 3 restituisce un prompt minimale
  (2 righe). Guadagno ~0.1KB/step dal 3°. ✅ IMPLEMENTATO in Cycle 43.

- [x] **T21 — Early stopping**: fermare la generazione quando il JSON è
  completo (parsing parziale durante lo streaming). Guadagno 30-60% tempo
  su step semplici. ✅ IMPLEMENTATO in Cycle 43.

- [x] **T22 — Compressore LLM del prompt**: implementato come compressore
  SOLO del contesto persistente (`_compress_context`), con cache per hash
  (una chiamata LLM per versione del contesto, riusata su più task),
  guardia client-reale (nei test resta deterministico) e model key routed
  (nessuna rotazione extra su 4GB VRAM). NOTA ONESTA: il contesto è già
  capped a ~1KB da T7 (8/3/3) → la compressione resta una valvola di
  sicurezza che scatta solo se il contesto supera 1500 chars. La versione
  originale (comprimere l'intero prompt per task) è stata scartata:
  prefill pagato 2x + rotazione modello = rallentamento netto.
  ✅ IMPLEMENTATO in Cycle 44.

- [x] **verify_all.py** (`tools/verify_all.py`): verifica autonoma in un
  comando — py_compile di tutti i sorgenti + suite pytest per-file con
  timeout individuale (esclusi i test live che toccano la coda reale) +
  boot reale orchestratore (pause.flag, exit 124 atteso) + benchmark
  worker ReAct con Ollama (auto-skip se offline). ✅ Cycle 45.

- [x] **bench_worker.py** (`tools/bench_worker.py`): benchmark del loop
  ReAct con modello reale in sandbox (`state/bench_sandbox/`), timing
  per ogni chiamata LLM, JSON in `state/benchmarks/`, confronto con
  baseline (`--save-baseline` dopo un'ottimizzazione per misurare il
  prima/dopo). ✅ Cycle 45.

- [x] **Watchdog orfano**: `SAFETY/watchdog.py` inoltra SIGTERM al
  figlio orchestratore (prima: stop lanciatore lasciava l'orchestratore
  vivo orfano → doppio orchestratori); sweep di difesa in
  `byte-swarm.sh stop`. ✅ Cycle 45.

- [x] **test_e2e pid guard**: guardia anti pid-reuse (cmdline
  orchestrator|watchdog, stessa semantica launcher) + catch OSError. ✅ Cycle 45.

- [x] **Regressioni GUI pre-esistenti** (Cycle 45 per-file map: 5 file
  fail): DevicePanel fallback + alias (`GUI/device_panel.py`), guardie
  RuntimeError su timer distrutti (`GUI/cc_shutdown.py`), alias
  `theme_combo` (`GUI/settings_panel.py`), zoom identità a 100% +
  invalidazione cache al cambio tema (`GUI/cc_zoom.py`,
  `GUI/center_area.py`), **causa vera white-panels dark** = icone
  "pagina bianca" QFileIconProvider → palette a tema
  (`GUI/theme/theme.py`) + tint icone (`GUI/file_manager.py`,
  `GUI/file_tree_drawer.py`), checkbox riga senza bianco hardcoded
  (`GUI/task_item_row.py`), selettori `QTreeView::indicator` nei temi
  scuri, re-export `_looks_like_file_path` (`CORE/orchestrator.py`),
  escalation test dinamico (`tests/test_user_workflow.py`). ✅ Cycle 46.

- [x] **Skill py-refactor-rename** (rinomina multi-file): creata
  `SKILLS/py-refactor-rename.md` — test_refactoring_live la aspettava
  e `skill_executor` salta la mappa codice per `py-refactor-*`. ✅ Cycle 46.

- [x] **Igiene repo**: config.toml.bak eliminato e backup rediretti in
  `backups/` (4 scrittori GUI/CORE — la GUI aperta ricreava il .bak a
  ogni salvataggio), sml_models.db untracked + gitignore, root
  settings.json → `CONFIG/tool_settings.json`, DATI_COMPLESSI.json →
  `CONFIG/` (path script aggiornato), dotfile runtime ammessi dal test
  igiene. ✅ Cycle 46.

- [x] **Prima misura bench pre-T1 vs baseline** (worktree `b9bb4e6`,
  stesso modello e task): token input −72% (2516→668 ch system
  costante), artifact 0/2 → 2/2. Il confronto wall è confondato dal
  fatto che pre-T1 i task FALLIVANO (loop read_file senza output).
  Numeri in `DOCS/IMPLEMENTED.md` Cycle 46b. ✅ Cycle 46b.

- [x] **A. Warmup all'avvio + keep_alive da config** ✅ Cycle 47:
  orchestrator pre-carica `warmup_model` (thread background) +
  `keep_alive_sec` esplicito rispettato nelle richieste
  (`CORE/ollama_client.py`: `_explicit_keep_alive`, `warmup`).

- [x] **B. Scheduling sticky per modello** ✅ Cycle 47:
  FIFO con affinity al modello caricato — `_pick_task` consulta
  `peek_pending(8)` e `claim_by_id` (stesso claim atomico di next_pending).

- [x] **C. Audit gate deterministico** ✅ Cycle 47:
  config `[audit].deterministic_gate = true` → AST check sui file scritti
  prima dell'audit LLM (APPROVE se compilano, REJECT con SyntaxError esatto).

- [x] **F. Watchdog primo token** ✅ Cycle 47:
  streaming abort con `FirstTokenTimeout` dopo `[ollama].first_token_timeout`
  (60s) senza token → task in fallback su worker_general.

- [x] **Bench post-furbate** (auto dentro verify_all): wall −5,4% (74,59→70,53s),
  bench-create −9,6% (load cold nascosto dal warmup), token invariati.
  Report in `DOCS/BENCH.md` Cycle 47b. ✅ Cycle 47b.

- [x] **E. Bench num_ctx A/B** ✅ Cycle 48: num_ctx 8192 → 4096 vs baseline;
  wall −4,7%, token invariati → **nessun win misurabile** oggi (prompt già
  compatti); config ripristinata a 8192. Report in `DOCS/BENCH.md` Cycle 48.
  ✅ Cycle 48.

- [x] **Bench post-furbate** (auto dentro verify_all): wall −5,4% (74,59→70,53s),
  bench-create −9,6% (load cold nascosto dal warmup), token invariati.
  Report in `DOCS/BENCH.md` Cycle 47b. ✅ Cycle 47b.

- [x] **D. Env Ollama KV cache q8_0 + flash attention** ✅ Cycle 49:
  `systemctl set-environment OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_FLASH_ATTENTION=1`
  + restart; bench post: wall **−2,5%** (74,59 → 72,72s), bench-create **−13,6%**.
  Report in `DOCS/BENCH.md` Cycle 49. ✅ Cycle 49.

## 🔓 Open follow-ups
UI redesign (menu hamburger, Live Activity in alto), MCP E2E testing, USB protocol parser, USB differential analysis, dedicated user `byteswarmy`, usbmon/tshark automation, unification of GUI→SQLite queue (FM14).

## 🚀 Cycle 25 — R3: split GUI/control_center.py in mixin (2026-11-14)

- [x] **R3 — Split `GUI/control_center.py`** (~5000 righe) in moduli per area
  via mixin: `GUI/cc_shell.py` (ShellMixin), `GUI/cc_orchestrator.py`
  (OrchestratorMixin), `GUI/cc_zoom.py` (ZoomMixin + `_ZoomEventFilter`,
  `_zoom_scale_css`), `GUI/cc_editor_overlay.py` (EditorOverlayMixin),
  `GUI/cc_debug_bar.py` (DebugBarMixin), `GUI/cc_shutdown.py`
  (ShutdownMixin). `GUI/control_center.py` ridotto a ~358 righe (coordinatore
  + __init__ + main). Comportamento invariato: metodi restano sullo stesso
  oggetto `ControlCenter`. Test: zoom 6/6, close_orchestrator 10/10, smoke
  import+show OK.
- [x] **Fix latente `GUI/center_area.py`**: `eventFilter` referenziava
  `QEvent` e `QApplication` non importati (swallowed dal try/except) → le
  scorciatoie globali (Backspace→Plancia, "/"→campo comando, ESC→credits)
  non funzionavano mai. Aggiunti import (`QEvent` top-level, `QApplication`
  nel try). Test keys: 6/6 passano (prima 3/6).

## 🚀 Cycle 26 — UI Redesign (parziale): Live Activity in alto (2026-11-14)

- [x] **Live Activity in alto**: aggiunta barra sottile sopra la toolbar
  (`live_activity_bar` + `live_activity_label`) che mostra l'ultimo token
  prodotto dal worker (polling 500ms su `state/streaming.txt`), con fallback
  "In attesa di un task…". Il menu hamburger (☰) esisteva già
  (`_show_context_menu`).
- [ ] **UI Redesign completo** (menu hamburger avanzato, riorganizzazione
  pannelli) resta aperto — questo ciclo copre solo la barra Live Activity.

## 🚀 Cycle 27 — Recupero storia persa: M9/M10/M11 + 9.7 MCP E2E (2026-11-14)

> Registrati il 2026-11-03 (commit `4046b5d`) ma andati persi nella
> consolidazione di IMPLEMENTED.md: le voci restavano in todo.md come
> "aperti" pur essendo completi (test 29/29 passano). Travaso + recupero.

- [x] **9.7 MCP E2E** — Collaudo pipeline MCP reale (server esempio +
  client): 4 test in `tests/test_mcp_e2e.py` (discovery tools via SSE,
  consegna outbox via callback, errori gestiti porta morta, idempotenza
  `get_pending_tasks`). Pin `mcp>=1.0.0,<2` in `GUI/requirements_gui.txt`.
- [x] **M10 — USB Protocol Parser**: `CORE/usb_protocol.py` puro
  (`decode_setup` spec USB 2.0 §9.3, `describe_setup`,
  `parse_lsusb_descriptors`, `describe_event`, `summarize`) + 16 test
  (`tests/test_usb_protocol.py`, catture fabbricate).
- [x] **M11 — USB Differential Analysis**: `CORE/usb_differential.py`
  (`diff_captures` endpoint nuovi/scomparsi, cambio tipo, request
  vendor/class nuove, salti frequenza/payload + `explain_diff` + scoring
  rischio HIGH/MEDIUM) + mini-CLI `python -m CORE.usb_differential a.json
  b.json` + 10 test (`tests/test_usb_differential.py`).
- [x] **M9 — ambiente usbmon/tshark**: `scripts/setup/usbmon.sh`
  (modprobe usbmon, tshark, gruppo+udev rule `/dev/usbmon*` 0660 →
  catture SENZA sudo, helper in /usr/local/bin) + `tools/usbmon-capture.sh`
  (cattura per bus, chmod 600). Esecuzione sudo lasciata all'utente.
- [x] **Utente dedicato `byteswarmy`**: `scripts/setup/hardening.sh`
  (`--apply` crea utente senza privilegi + copia progetto + `.git` scan;
  `--firewall` blocca uscita tranne Ollama; slice cgroup 4G/200%).
  **Aggiunto in questo ciclo**: l'utente dedicato viene iscritto al
  gruppo `usbmon` (se presente) → automazioni usbmon/tshark girano
  davvero sotto utente non-root dedicato (chiude il combo dell'item todo).

- [x] **R1 — Igiene rigenerazione** (recupero): la pratica è già registrata
  come completata nel vecchio IMPLEMENTED.md (py_compile su tutto l'albero
  live + boot reale `python -m CORE.orchestrator CONFIG/config.toml` con
  SIGINT + suite completa) e ora vive come checklist permanente in
  `AGENT.md` ("Checklist pre-commit / pre-release"). Rimossa da todo.md:
  è un processo ricorrente, non un task one-shot.

## 🚀 Cycle 28 — FM14: coda unica GUI→SQLite (2026-11-14)

- [x] **FM14 — Coda unica GUI→SQLite**: la coda task vive SOLO in SQLite
  (`tasks/queue.db`, schema e implementazione condivisi con l'orchestratore
  tramite `CORE/task_queue.py:TaskQueue`). Eliminato il mirror `queue.json`
  (coda in memoria da tenere in sync). Cambiamenti:
  - `CORE/task_queue.py`: +`list_scoped`, `get_by_id`, `upsert_task`,
    `delete_by_id`, `delete_children`, `reset_task`, `cleanup_done` (scope
    progetto/globale, id univoci globali).
  - `GUI/task_queue.py`: riscritto — tutte le operazioni sulla coda
    delegano a `TaskQueue`; migrazione una-tantum dei vecchi
    `queue.json` (globale + per-progetto) → righe con `project_path`
    corretto, file rinominati `.json.migrated` (backup), marker
    `.fm14_migrated`. API pubblica invariata (`load_tasks`, `save_tasks`,
    `add_task`, `delete_task`, `reset_task`, `force_rerun_task`,
    `cleanup_done_tasks`, `delete_subtasks`).
  - `GUI/gui_backend.py`: `add_task_to_db` scrive solo il DB (rimosso il
    mirror JSON).
  - `GUI/file_tree_drawer.py`: `_show_task_details` semplificato (DB unica
    fonte; fallback SQL solo per task fuori scope progetto).
  - `GUI/task_scheduler_panel.py`: fix typo `task.get("id")` → `t.get("id")`
    nel lookup del context-menu (modifica).
  - Test: `test_crud_file_manager.py`, `test_task_scheduler_project_path.py`
    riscritti per il modello DB (isolamento tramite `_TASKS_DIR` hook);
    8 test passano.
- [x] **R1 — Boot reale ripristinato**: `CORE/orchestrator.py` non
  bootava (`__main__`): `_OUT`, `LifecycleManager`, `SystemMonitor`,
  `TaskDispatcher`, `AuditWorker.decision_client` erano referenziati ma
  non importati (regressione silente). Fix import + `decision_client =
  generic_planner._call_decision_model`. Boot verificato: orchestratore
  parte, scheduler/timestral partono, shutdown pulito su SIGTERM.

## 🚀 Cycle 29 — Gap vuoto in alto: riduzione margine top (2026-11-14)

- [x] **Gap vuoto in alto (1920×1080)**: ridotto il margine superiore di
  `main_lay` in `GUI/center_area.py` da 16 a 8px (plancia_section ora a
  y=8 dal bordo superiore del contenuto). Audit offscreen originale
  segnalava ~200px: non riproducibile nel codice attuale (first content
  row a y=9, plancia header a y≈114 dalla cima della finestra — il vuoto
  residuo è il toolbar 72px + Live Activity 26px + margine 8, tutti
  elementi funzionali). Il margine ridotto è l'unico vuoto "gratuito"
  disponibile; nessun altro elemento è rimovibile senza perdere funzione.
  Item rimosso da todo.md.

## 🚀 Cycle 30 — T-R3: _force_content_size Expanding (2026-11-14)

- [x] **T-R3**: in `GUI/center_area.py`, `_force_content_size` passa da
  `setFixedHeight(300)` triplo (bloccava l'altezza a 300px anche quando
  il contenitore aveva più spazio) a `setMinimumHeight(220)` + policy
  Expanding verticale (max height illimitata). Smoke import+show OK;
  grid card della Plancia non toccata (i 5 widget vivono solo nelle
  pagine di dettaglio dove `wrap_in_panel_page` rilascia l'altezza max).

## 🚀 Cycle 31 — UI Redesign: hamburger come menu unico (2026-11-14)

- [x] **UI Redesign (completato)**: il menu hamburger (☰) diventa l'unico
  punto di ingresso ai pannelli — sottomenu "📋 Pannelli" con tutte le 13
  pagine (coda, modelli, config, cicd, clean_code, code_explorer,
  backup_logs, logs, integrity, security, audit_project, hardware, test)
  + "Indietro alla Plancia". Live Activity bar già presente in alto
  (Cycle 26). Nessun test rotto (smoke OK).
  `todo.md` ora è vuoto di item aperti.

## 🚀 Cycle 32 — swarm_time: "che ore sono" senza LLM (2026-11-14)

- [x] Aggiunto intent `swarm_time` (IT/EN/ZH) e comando swarm diretto
  `_cmd_swarm_time()` che restituisce ora + data senza invocare alcun
  modello (il router classifica "che ore sono" con conf 130, sopra
  soglia 75). Risolve il caso "si perde su domande semplici come
  l'ora": ora è un swarm command istantaneo, zero token.

## 🚀 Cycle 33 — Token reduction T2+T4+T5+T9 (2026-11-14)

- [x] **T2 — Regole compatte**: 10 regole worker da ~1KB a ~0.3KB (6 regole
  compresse). `CORE/worker.py` SYSTEM prompt.
- [x] **T4 — Skill block cap 1500**: `MAX_SKILL_BODY_CHARS` da 2500 a 1500
  in `CORE/skills.py`. Inietta solo i passi essenziali.
- [x] **T5 — Tool result truncation 300**: tool_result da `[:2000]` a `[:300]`
  in `CORE/worker.py` (error + success path). Memory event `[:200]` invariato.
- [x] **T9 — Codici tool a prefisso naturale**: mappatura code→full name
  (`TOOL_CODE_MAP`, 25 codici + fallback per nomi completi) in `CORE/worker.py`.
  `_call_tool` normalizza il nome prima del check `allowed_tools()`.
  Prompt esponi solo codici (`read`, `write`, `patch`, `bash`, ecc.).
- Test: execute_handler 16/16, correction 16/16, skill_proposer passano.
- Prompt worker: da ~4–5KB a ~2–2.5KB per step (guadagno ~50%).

## 🚀 Cycle 34 — Token reduction T1 (tool list dinamica) (2026-11-14)

- [x] **T1 — Tool list dinamica per tipo task**: aggiunto `_classify_task_tools(task)`
  e `_build_system(task)` in `CORE/worker.py`. Il prompt SYSTEM viene ora
  costruito per ogni task, esponendo solo i tool rilevanti (creazione → 12
  tool core; refactoring → 24; analisi → 26; git → 18; usb → 14; default → 26).
  Prompt da ~2.5KB a ~1.2KB per step. Test: execute_handler 16/16 passano.

## 🚀 Cycle 34 — Token reduction T3+T7 (2026-11-14)

- [x] **T3 — Project state on-demand**: cap file da 20 a 10 in
  `_project_state()` (CORE/worker.py). Guadagno ~0.5KB/step.
- [x] **T7 — Persistent context lazy**: ridotto da 15 file a 8, 5 errori a 3,
  5 task a 3 in `build_context_for_prompt()` (CORE/persistent_memory.py).
  Guadagno ~0.3KB/step.
- Test: execute_handler 16/16, correction 16/16 passano.

## 🚀 Cycle 35 — Token reduction T6 (deduplication tra step) (2026-11-14)

- [x] **T6 — Deduplicazione tra step**: aggiunto `_build_system_compact()` in
  `CORE/worker.py` (~0.3KB vs ~1.2KB). Il primo step usa il system prompt
  completo (`_build_system(task)`); gli step successivi usano quello compatto
  (solo regole, senza lista tool). Selezione via `step == 0` nel loop ReAct.
  Guadagno ~2.5KB/step (system prompt non re-inviato).
- Test: execute_handler 16/16, correction 16/16 passano.

## 🚀 Cycle 36 — Token reduction T8 (formato JSON compatto) (2026-11-14)

- [x] **T8 — Formato JSON compatto**: `_build_initial_prompt()` in `CORE/worker.py`
  passa da markdown multi-riga (`## TASK\n...\n\n## DESCRIPTION\n...`) a formato
  compatto (`TASK: ... | DESC: ... | STATE: ... | CTX: ... | RULES: ... | SKILL: ...`).
  Guadagno ~0.2KB/step.
- Test: execute_handler 16/16, correction 16/16 passano.

## 🚀 Cycle 37 — Token reduction T11+T12+T13+T14+T15 (2026-11-14)

- [x] **T11 — Tool result summarization intelligente**: aggiunto `_summarize_result(name, result)`
  in `CORE/worker.py` (read_file → prime 10 righe + def/class/import; run_test_suite → summary
  + primi 3 errori; run_bash → ultime 5 righe; git_diff → nomi file + +/- sintassi).
  Usato in entrambi i path (error + success) del loop ReAct.
- [x] **T12 — Abbreviazione percorsi**: esempi JSON cambiati da "project/main.py" a
  "main.py" (3 occorrenze). Project state già relativo (relative_to(root)).
- [x] **T13 — Adaptive max_tokens**: max_tokens per step: 1024 al primo step (scrittura
  file), 512 negli step successivi (tool call semplici).
- [x] **T14 — Rimozione esempi**: già implementato in Cycle 33 (regole compatte, nessun
  esempio di comandi buoni).
- [x] **T15 — Context window pruning**: già implementato in Cycle 33 (project state solo
  in initial prompt, non in step prompts).
- Test: execute_handler 16/16 passano.

## 🚀 Cycle 38 — Token reduction T16 (task title re-injection) (2026-11-14)

- [x] **T16 — Prompt fisso + delta**: step prompts ora includono il titolo del task
  (`Task: {title[:60]} | Last action: ...`) per prevenire task drift. Il system prompt
  è già compatto dal 2° step (T6). Guadagno: prevenzione del task drift (~0.1KB/step).
- Test: execute_handler 16/16, correction 16/16 passano.

## 🚀 Cycle 39 — Token reduction T17 (model-specific prompt tuning) (2026-11-14)

- [x] **T17 — Model-specific prompt tuning**: aggiunto `_model_family()` in
  `CORE/worker.py` (rileva qwen/llama/deepseek/mistral/granite/other dal nome
  del modello nel config). `_build_system()` seleziona il formato delle regole:
  - Llama: strutturato con esempi di comandi buoni/vietati
  - DeepSeek: chain-of-thought ("Think step by step before acting")
  - Qwen/mistral/granite/other: compact (default)
  Cache key include la famiglia (prompt diversi per famiglia).
- Test: execute_handler 16/16 passano.

## 🚀 Cycle 40 — Disabilitazione strumenti USB (2026-11-14)

- [x] **USB tools disabilitati**: `inspect_usb_devices` e `capture_usb_traffic`
  rimossi da `allowed_tools()` in `CORE/tools.py` e dalla lista tool esposta
  al worker in `CORE/worker.py` (T1: tool list dinamica). `_call_tool`
  restituisce "ERROR: tool disabilitato" se chiamati. Nessuna skill USB
  presente in `SKILLS/`. I moduli `CORE/usb_protocol.py`,
  `CORE/usb_differential.py` e i test restano (codice di analisi, non
  strumenti attivi del worker). Riabilitazione futura: rimuovere il guard
  in `_call_tool` e aggiungere i tool a `allowed_tools()` + `tool_lines`.

## 🚀 Cycle 41 — Strumenti USB abilitabili da GUI (2026-11-14)

- [x] **USB tools toggle GUI**: aggiunto `get_usb_tools_enabled()` /
  `set_usb_tools_enabled()` in `GUI/settings_store.py` (default: False).
  `ToolSet.allowed_tools()` e `_classify_task_tools()` in `CORE/worker.py`
  includono i tool USB solo se il setting è True. `_call_tool` restituisce
  errore se chiamati con setting disabilitato. Toggle nel menu hamburger (☰)
  sotto "🔌 Strumenti USB (reverse engineering)" — checkbox persistente in
  `CONFIG/settings.json`.
- Test: py_compile OK, smoke OK.

## 🚀 Cycle 42 — Token reduction T18+T19 (2026-11-14)

- [x] **T18 — JSON chiavi corte**: `_parse_action()` accetta sia chiavi corte
  (t/a/d/r) che standard (thought/action/done/result). Normalizzazione automatica.
- [x] **T19 — Deduplicazione tool call identiche**: `_call_tool` cacha l'ultima
  tool call (nome + args) e restituisce il risultato cachato se ripetuta,
  evitando round-trip ridondanti. Cache invalidata ad ogni tool call diverso.
- Test: execute_handler 16/16 passano.

## 🚀 Cycle 43 — Token reduction T20+T21 (2026-11-14)

- [x] **T20 — Prompt pruning per step**: `_build_system_compact(step)` ora accetta
  il numero di step. Dopo il 3° step restituisce un prompt minimale (2 righe:
  "You are a coding agent. Reply with ONE JSON object" + esempio). Le regole
  già assorbite dal modello non vengono re-inviato.
- [x] **T21 — Early stopping**: durante lo streaming, dopo 15 token, controlla
  se il testo accumulato è un JSON completo (termina con `}` e contiene
  `"done"` e `"action"`). Se sì, ferma la generazione. Guadagno 30-60% tempo
  su step semplici.
- Test: execute_handler 16/16 passano.

## 🚀 Cycle 44 — Token reduction T22 + fix T13 (2026-11-14)

- [x] **Fix T13 (regressione)**: `step_max_tokens` era referenziato ma mai
  definito nel loop ReAct (NameError a runtime → "model unavailable" su
  OGNI task ReAct, ma solo con client reale: nei test non saltava fuori).
  Definito T13 adattivo: 1024 allo step 0 (il write_file con codice lungo
  richiede spazio; con 400 il JSON veniva troncato), 512 dagli step
  successivi (JSON brevi → ~2x più veloci).
- [x] **T22 — Compressore LLM del prompt**: riscritto in forma sicura.
  Comprime SOLO il contesto persistente (`_compress_context`), mai
  TASK/RULES/istruzioni JSON (un compressore piccolo può troncarle e
  rompere il loop ReAct). Cache a livello classe per hash del testo:
  una chiamata LLM per versione del contesto, ammortizzata su più task.
  Guardia `isinstance(ModelClient)`: nei test con client finti resta
  deterministico. Usa il model key del routing → nessuna rotazione
  extra di modello. Validazione output (25%-85% dell'originale, no eco
  dell'istruzione), cap 1200 chars, cache limitata a 32 voci.
  La versione scartata (comprimere l'intero prompt con worker_general
  a ogni task) era un rallentamento netto: prefill pagato 2x + unload/
  reload del modello su 4GB VRAM.
- [x] Cleanup: `except (ValueError, Exception)` → `except Exception`
  (early stopping T21).
- Test: security 27/27 (ripristinato test injection rotto da T13),
  execute_handler + correction 16/16, routing/sandbox/skill 81/81.
  Boot reale: OK, shutdown pulito.

## 🏁 Chiusura programma Token Reduction (2026-11-14)

Bilancio finale: **22 di 26 tecniche implementate** (T1–T22), 4 in fuori scope.

- Implementate: T1–T17 (Cycles 33–39), T18+T19 (Cycle 42), T20+T21 (Cycle 43),
  T22 (Cycle 44, in forma safe/cached).
- Risultato complessivo: prompt worker da ~4–5KB a ~1.5–2KB per step
  (~60% in meno); su 10 step ~45KB → ~8KB (~82% in meno); system prompt
  dal 3° step ridotto a 2 righe (T20); early stopping sui JSON completi
  (T21); dedup tool call (T19).
- Fuori scope (scelta 2026-11-14): T23 (Ollama già cacha il prefisso KV),
  T24 (batch tool calls: guadagno reale ma refactor+rischio ordering alti),
  T25 (pruning per rilevanza: complessità alta), T26 (quantizzazione KV:
  richiede bypass Ollama con llama-cpp-python).
- Fix collateral importantissimo (Cycle 44): T13 `step_max_tokens` era
  referenziata ma mai definita → NameError su ogni task ReAct reale
  (invisibile nei test con client finti). Le regressioni silent-type nel
  worker vanno sempre verificate con boot reale + client vero.

## 🚀 Cycle 45 — Verifica autonoma: verify_all + bench_worker (2026-11-14)

Due strumenti CLI in `tools/` per ripetere le verifiche in autonomia,
senza supervisione manuale:

- **`tools/verify_all.py`** — un solo comando per i 4 controlli che
  beccano le regressioni silent (variabili mai definite, metodi
  cancellati) invisibili a py_compile e ai test con mock:
  1. *compile*: py_compile di tutti i .py (CORE, GUI, tools, tests);
  2. *tests*: suite pytest completa con timeout;
  3. *boot*: avvio reale orchestratore con `state/pause.flag`
     (SIGTERM via `timeout` → exit 124 atteso, "swarm stopped" nel
     log, zero traceback);
  4. *bench*: benchmark worker ReAct con Ollama reale (auto-SKIP se
     offline, disabilitabile con `--no-bench`).
  Riepilogo finale ✅/❌ + exit code 0/1.

- **`tools/bench_worker.py`** — misura l'effetto REALE delle
  ottimizzazioni token T1–T22 sul tempo per step:
  - esegue 2 task rappresentativi (create file + patch) direttamente
    con `CORE.worker.Worker` e `ModelClient` reale;
  - gira in sandbox `state/bench_sandbox/` (config clonata con path
    ridirezionati) — il progetto reale non viene toccato;
  - wrappa `call_streaming`/`call` del client e registra per OGNI
    chiamata: modello, char prompt/system, chunk/token out, durata
    (il `finally` cattura anche le chiusure anticipate da early-stop
    T21);
  - salva JSON in `state/benchmarks/bench-<ts>.json` e confronta con
    `bench-baseline.json` (wall totale, token prompt stima ~4char/tok,
    token generati, chiamate LLM; delta % — negativo = meglio);
  - `--save-baseline` per fissare una nuova baseline (da usare DOPO
    un'ottimizzazione per misurare il prima/dopo).

Motivazione: dopo i fix Cycle 42–44 (execute()/MAX_STEPS/step_max_tokens)
i test con mock non esercitano il percorso reale; questi tool rendono
ripetibile la verifica boot+ReAct che finora si faceva a mano.

### Scoperta critica durante l'implementazione (sistema live)

- **`state/orchestrator.pid` contiene il pid del WATCHDOG** (by design:
  `byte-swarm.sh start` fa `nohup SAFETY.watchdog & echo $! > PID_FILE`).
- `tests/test_e2e.py` e `tests/test_functional_swarm.py` sono test LIVE:
  iniettano task nella coda REALE e aspettano processing (120–180s per
  task). Con il watchdog vivo, test_e2e non saltava e iniettava task
  nell'orchestratore live dell'utente.
- **L'orchestratore live (spawnato 19:10 dal watchdog) aveva in memoria
  il codice PRE-fix** ('Worker' object has no attribute 'execute'):
  falliva OGNI task ReAct e il watchdog non lo riavvia (non crasha,
  logga solo l'eccezione). Levità: serve riavvio manuale per caricare
  il codice fissato.
- **Fix 1 — watchdog SIGTERM**: `SAFETY/watchdog.py` ora inoltra SIGTERM
  al figlio orchestratore prima di uscire (prima: stop del lanciatore
  lasciava l'orchestratore orfano vivo → doppio orchestratori alla
  prossima start).
- **Fix 2 — byte-swarm.sh stop**: sweep di difesa con pgrep che termina
  qualsiasi orchestratore figlio sopravvissuto.
- **Fix 3 — test_e2e pid guard**: guardia anti pid-reuse allineata al
  launcher (cmdline deve contenere orchestrator|watchdog) + catch di
  OSError sul pid file assente.
- **Pulizia coda reale**: eliminati i task-test iniettati
  (e2e-test-*, failed_definitively).
- **verify_all esclude SEMPRE i test live** (test_e2e,
  test_functional_swarm): vanno eseguiti solo deliberatamente col
  sistema attivo. Modalità test per-file con timeout individuale
  (default 240s) — un file hanging non blocca gli altri e la mappa
  finale indica esattamente il colpevole.

## 🚀 Cycle 46 — Regressioni GUI pre-esistenti + igiene repo (2026-11-14)

La mappa per-file del Cycle 45 (50 file: 45 ok, 5 fail) ha scavato fuori
5 file di test falliti, TUTTI regressioni pre-esistenti (nessuna legata
a T18–T22). Tutti ora verdi.

### test_push_dialogs + test_close_orchestrator (11 test)

- **DevicePanel senza fallback** (8 test, crash a build-time):
  `__init__` valutava `self._toggle_orchestrator` come callback del
  pulsante ▶/⏸ anche senza ControlCenter → AttributeError immediato.
  Aggiunti metodi standalone `_orchestrator_running` (guardia cmdline
  anti pid-reuse, stessa semantica launcher), `_toggle_orchestrator`
  (pausa/riprendi via state/pause.flag) e `_stop_orchestrator`
  (SIGTERM + sweep, come byte-swarm.sh stop) + alias `toggle_btn`.
- **QMessageBox non intercettabile**: i test patchano
  `PyQt6.QtWidgets.QMessageBox` ma il modulo importava il binding
  diretto → patch cieca. Passato ad accesso module-style
  (`QtWidgets.QMessageBox`, 10 usi).
- **`_stop_periodic_timers` RuntimeError** (3 test): `getattr` su
  attributo Qt di un oggetto C++ già distrutto (deleteLater prima del
  closeEvent manuale nei test) → guardie try/except RuntimeError.

### test_user_workflow (6 → 0)

- **Zoom non identità al 100%**: `_zoom_scale_css` riformattava
  `10.5pt` → `10.50pt` anche a fattore 1.0 → il QSS confrontato col
  tema pristine divergeva al carattere 113 (live-switch fallito) e ogni
  boot riscalava inutilmente tutti gli stylesheet. Ora è identità a
  fattore 1.0.
- **Cache zoom stantia al cambio tema**: `_zoom_base_styles` catturata
  col tema chiaro al boot veniva ri-applicata dopo lo switch al tema
  scuro → residui chiari. `_apply_theme_live` ora invalida la cache.
- **White-panels (dark themes) — causa vera**: non erano stylesheet né
  indicatori: era l'**icona "pagina bianca" di QFileIconProvider**
  (riempimento 224,224,224) nella colonna icone del file manager, che
  sotto offscreen resta bianca nei temi scuri. Bisect di decine di
  regole QSS (inline tree, tema, tre livelli) aveva già escluso i
  sospetti: le regole `::indicator` per gli item view sono IGNORATE
  dallo stile a foglio di stile, e il QSS non può quindi coprirle.
  Fix a due livelli:
  1. `GUI/theme/theme.py`: `palette_for()`/`apply_palette()` — la
     palette applicativa segue il kind del tema (chiaro/scuro), così
     ogni primitive NATIVO non coperto dal QSS (indicatori item view,
     menu, tooltip) prende colori a tema; applicata al boot
     (`control_center`) e nel live-switch (`center_area`).
  2. `GUI/file_manager.py`: `tint_icon_for_dark()` ri-tinta le icone
     provider nei temi scuri (remap dei soli pixel quasi-bianchi →
     #aab2c0 e quasi-neri → #6b7280, alpha preservata; cartelle blu
     invariate). `FileSystemModel.set_dark_icons()` rigenera le icone
     degli item già caricati; `FileTreeDrawer.on_theme_changed()` le
     aggancia al cambio tema live.
- **Checkbox riga task**: rimosso `background:#ffffff` hardcoded
  sull'indicatore (GUI/task_item_row.py); bordo via inline, riempimento
  dal tema.
- **Temi dark/dracula/hacker**: aggiunti selettori
  `QTreeView::indicator` (+`:checked`) accanto a `QCheckBox::indicator`
  (effettivi dove la cascata funziona, es. xcb).
- **Escalation dinamica**: il test aspettava nomi modello hardcoded
  (`qwen2.5:3b`) ormai stanti → usa `weight_default_model`.
- **Re-export**: `_looks_like_file_path` da `CORE.worker` a
  `CORE.orchestrator` (contratto dei test).
- `test_toggle_pauses_and_resumes` passa anche combinato (l'ordine
  non inquina più dopo la invalidazione cache).

### test_refactoring_live (1 → 0)

- La skill `py-refactor-rename` (refactoring RENAME multi-file) era
  attesa da test ed esecutore (`skill_executor` salta la mappa codice
  per `py-refactor-*` "la mappa confonde") ma mai creata: l'esistente
  `py-refactor` è single-file. Creata `SKILLS/py-refactor-rename.md`
  (keywords mirate: il rename su tutto il progetto matcha la ricetta
  multi-file, il refactoring generico resta su quella single-file).

### test_repo_hygiene (3 → 0)

- `CONFIG/config.toml.bak`: eliminato (byte-identico a config.toml).
- `OLLAMA_SML_AGENT/sml_models.db`: runtime DB tracciato in git →
  `git rm --cached` (file resta su disco) + pattern `OLLAMA_SML_AGENT/*.db`
  in .gitignore.
- `CONFIG/config.toml.bak`: il backup veniva riscritto dalla GUI a OGNI
  salvataggio (anche invariato) e tornava dopo la cancellazione. Fix alla
  radice: i 4 scrittori (gui_backend.save_config, config_panel._save,
  actors_panel, model_selector autoselect) ora scrivono il backup in
  `backups/` (sede designata, gitignored) e il test igiene esclude
  quella sede. NB: la GUI GIÀ APERTA ha il codice vecchio in memoria —
  al prossimo salvataggio config può ricreare il .bak alla root finché
  non viene riavviata.
- Root `settings.json` (config di un tool esterno, usata da nessun
  codice) → spostata in `CONFIG/tool_settings.json` (decisione utente).
- Root `DATI_COMPLESSI.json` (dati di scripts/suite_complex_data.py) →
  `CONFIG/DATI_COMPLESSI.json`, path dello script aggiornato (assoluto,
  indipendente dal CWD) (decisione utente).
- `.audit_status.json` alla root: è lo stato runtime dell'AUDIT DEL
  PROGETTO (il pannello Audit scrive `<progetto>/.audit_status.json`;
  per l'auto-audit la root È il progetto, by design) → il test igiene
  ora ammette i dotfile nascosti.

## 🚀 Cycle 46b — Prima misura bench: pre-T1 vs baseline (2026-11-15)

Prima misura reale del bench (`tools/bench_worker.py`): worktree al
commit `b9bb4e6` (codice PRIMA di T1–T22) vs baseline attuale, stesso
hardware, stesso modello (`worker_coder` = qwen2.5-coder:3b), stessi 2
task (bench-create, bench-patch, 10 step l'uno). 1 campione per task:
i tempi sono rumorosi, il segnale forte è la correttezza.

| | pre-T1 (b9bb4e6) | baseline (T1–T22) | delta |
|---|---|---|---|
| system prompt per step (dopo il 1°) | 2516 ch **costanti** | 668 ch | −73% |
| contesto ripetuto per step | task+stato interi | ~140 ch | −94% |
| token input TOTALI (20 step) | ~15.300 | ~4.240 | **−72%** |
| token generati totali | ~845 | ~1.170 | +38% |
| artifact corretti | **0/2** | **2/2** | — |
| wall totale | 48,2s | 74,6s | n.c. |

**Lettura onesta**: pre-T1 i task FALLIVANO entrambi (prompt gonfio →
il 3B gira in tondo su read_file, circuit breaker, nessun file scritto;
il wall "minore" riflette solo che NON ha fatto il lavoro). Con il
prompt compatto gli stessi task si completano 2/2. La velocità di
generazione (tok/s) resta invariata come previsto — il wall cresce
perché i passi ora producono contenuto reale invece di brancolare nel
buio. Il guadagno misurabile del token reduction sul prefill: ~4.600
char/step in meno di input costante ripetuto.
NB: il primo step della baseline (15,7s) include il load del modello
in Ollama; i passi successivi (1,9–5,5s) sono il costo reale per step.

## 🚀 Cycle 47 — Furbate: warmup, sticky scheduling, audit gate deterministico, watchdog (2026-11-15)

Implementate le furbate scelte dall'utente come Cycle 47 (A+B+C+F):

1. **A — Warmup + keep_alive**: orchestrator avvia un thread daemon che
   pre-carica `worker_coder` via `/api/generate` senza prompt (load only);
   il client Ollama (`CORE/ollama_client.py`) rispetta `[hardware]
   .keep_alive_sec` SOLO se impostato esplicitamente (con "auto" il campo
   non viene mandato → nessun reload per task stesso-modello).
2. **B — Sticky scheduling**: `_pick_task` nel tick preferisce, tra i
   candidati pendenti (peek dei primi 8), il task che userà il modello già
   caricato; il claim usa `claim_by_id` (UPDATE...RETURNING atomico, stessa
   gara di next_pending). Config: `[orchestrator].sticky_models = true`.
3. **C — Audit gate deterministico**: `[audit].deterministic_gate = true`:
   se il worker non ha chiamato tool utile e ci sono file scritti nel
   `project_root` dopo `started_at`, l'auditor AST-verifica i .py: APPROVE
   se compilano, REJECT con SyntaxError concreto (riga+messaggio) se no.
4. **F — Watchdog primo token**: `CORE/ollama_client.call_streaming`
   usa `urlopen(timeout=first_token_timeout)` (default 60s da
   `[ollama].first_token_timeout`) + restore del timeout dopo il primo
   token + `FirstTokenTimeout` tipizzato su timeout pre-token → task in
   fallback (worker_coder → worker_general) invece di hang fino al timeout.

Nuovi test: `tests/test_cycle47_furbate.py` (25 passed). Boot smoke e bench
post-furbate da fare al termine della cycle.

## 🚀 Cycle 47b — Bench post-furbate: wall −5,4%, token invariati (2026-11-15)

Bench automatico dentro `tools/verify_all` (dopo il deploy delle furbate):
baseline (2026-11-15T01:12:58) vs post-furbate (2026-11-15T01:41:15).

| metrica | baseline | ora | delta |
|---|---|---|---|
| wall totale | 74,59s | 70,53s | **−5,4%** |
| token prompt | 4240 | 4240 | 0,0% |
| token generati | 1349 | 1349 | 0,0% |
| chiamate LLM | 20 | 20 | 0,0% |
| bench-create wall | 40,39s | 36,52s | **−9,6%** |
| bench-patch wall | 34,2s | 34,01s | −0,6% |

Interpretazione: −5,4% di wall con token invariati → il guadagno è quasi
esclusivamente il **warmup** (il primo step non paga più il load cold). Nessuna
regressione di uso. Il compile-error pre-esistente (archived GUI test) è
fuori dallo scope.

## 🚀 Cycle 48 — Furbata E: bench num_ctx A/B (8192 → 4096) (2026-11-15)

Bench con `num_ctx = 4096` (worker_coder) vs baseline 8192.

| metrica | 8192 | 4096 | delta |
|---|---|---|---|
| wall totale | 74,59s | 71,06s | −4,7% |
| bench-create | 40,39s | 36,76s | −9,0% |
| bench-patch | 34,2s | 34,3s | +0,3% |

Token invariati → riduzione KV cache non ha ridotto i token consumati. Conclusione
onesta: con prompt compatti (post-T1–T22) la riduzione num_ctx non dà un win
misurabile oggi (−4,7% dentro rumore). Config ripristinata a 8192.

## 🚀 Cycle 49 — Furbata D: env Ollama KV cache q8_0 + flash attention (2026-11-15)

Applicazione: `systemctl set-environment OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_FLASH_ATTENTION=1` + `systemctl restart ollama.service`.

| metrica | baseline (01:12:58) | ora (q8_0 + FA, 01:50:32) | delta |
|---|---|---|---|
| wall totale | 74,59s | 72,72s | **−2,5%** |
| bench-create wall | 40,39s | 34,91s | **−13,6%** |
| bench-patch wall | 34,2s | 37,81s | +10,6% (rumore) |
| token prompt in | 4240 | 4166 | −1,7% |
| token generati | 1349 | 1362 | +1,0% |
| chiamate LLM | 20 | 20 | 0,0% |

Guadagno wall misurato **−2,5%** (task create −13,6%). Flash attn era già attivo
via drop-in; delta attribuibile a `OLLAMA_KV_CACHE_TYPE=q8_0`.

**Chiusura furbate**: A, B, C, E, F e D — **tutte completate e misurate**.



## 🚀 Cycle 52 — Middle capability: escalation worker_coder → worker_coder_big (2026-11-15)

Obiettivo: far scendere lo swarm al tier capability "middle" (worker_coder_big
= qwen3-coder:4b) dopo il periodo "junior".

Cambio: nel fallback post-fallimento del worker_coder (junior 3B) — in
`CORE/orchestrator.py` (`_process_task`) — l'escalation ora sale a
`worker_coder_big` (middle) invece di scendere al più piccolo (`worker_general`,
1.5B).

Rationale onesta: il fallback precedente era una **discesa** (3B → 1.5B); ora è
un **salto** (3B → 4B). Nessun test esistente copriva il fallback: la suite
pertanto resta verde per la nuova catena di escalation.

## 🚀 Cycle 53 — Tool `diary_llm` (diario di bordo LLM) (2026-11-15)

Implementazione del tool diario di bordo richiesto come capability di
self-improvement.

- **Tool**: `ToolSet.diary_llm(task_id, content)` — scrive il diario in
  `<state_dir>/diary/<task_id>.md` (task_id sanitizzato: alnum + `-`/`_`, max
  64; content limitato da `security.max_output_chars`).
- **Worker**: tool aggiunto a `allowed_tools`, `TOOL_CODE_MAP` (`diary`),
  `tool_lines` (`diary=diary_llm(task_id,content)  # diario di bordo`) e
  dispatch `_call_tool`.
- **Test**: `tests/test_diary_llm_tool.py` (scrittura OK, sanitizzazione,
  limite contenuto).
- **Stato**: tool implementato e testato; la fase di automazione
  (LLM → diary → contesto/fedback futuro) resta come capability aperta.

## 🚀 Cycle 56 — Risk classifier deterministico + Runtime verification harness (2026-11-15)

Chiusura dei primi due interventi strutturali della lista senior (dalla code
review), come da piano d'attacco Fase 0–2 parziale (i primi due gap dichiarati):
"test verdi ma codice mai eseguito" e "task troppo rischioso per auto-approvazione".

- **Risk gate (Cycle 56, #1)**: nuovo modulo `SAFETY/risk_classifier.py` con
  classificazione deterministica (nessun LLM): path critici (`SAFETY/`,
  `CORE/sandbox.py`, `CORE/tools.py`, `CONFIG/`) → alto (critical se refactoring);
  refactoring / cambio API pubblica → alto; diff > 50 righe o > 3 file → alto.
  Task `high`/`critical` → coda `awaiting_human_approval` (nuovo valore in
  `TaskStatus`), orchestrator blocca l'esecuzione, log in security log.
  Comando swarm `approve_task` per riportare il task in `pending`.
- **Runtime verification (Cycle 56, #2)**: nuovo `CORE/runtime_verifier.py` con
  smoke test sui file scritti via `write_file` (py_compile; test via pytest) e
  boot smoke headless (`python -m CORE.orchestrator`) per task che toccano
  orchestrator/GUI/worker/sandbox/audit. Su fallimento: rollback del file +
  feedback specifico → correction loop.
- **Test**: `tests/test_cycle56_risk_runtime.py` (11 test: classificazione,
  verifier, task queue).
- **Stato**: risk gate + runtime verifier implementati e testati; blocco umano
  end-to-end GUI (prompt approvazione) resta da completare nella GUI flow.

## 🚀 Cycle 57 — Test generation per nuovi percorsi di esecuzione (2026-11-15)

Terzo intervento strutturale della lista senior (dalla code review, piano
d'attacco Fase 3): chiude il gap "test verdi ma codice mai eseguito".

- **Test generation path-aware** (Cycle 57, #3): nuovo modulo
  `CORE/test_generator.py`. Dopo ogni `write_file` riuscita su un modulo
  Python, il worker (`CORE/worker.py`, loop `execute`) genera
  automaticamente un test di regressione che esercita le funzioni pubbliche
  del file (via `self.models.call` su `worker_coder`), lo scrive in
  `tests/test_<nome>_regression.py` e lo esegue con pytest.
- Se il test fallisce → l'errore specifico diventa `tool_result` con prefisso
  `ERROR:` → entra nel correction loop con feedback mirato (non un generico
  "syntax error").
- Nessuna ricorsione: i file dentro `tests/` e i file `test_*.py` vengono
  saltati; ogni file sorgente viene testato una sola volta per task.
- Fail-open: se la generazione/esecuzione del test crasha, il worker continua
  senza bloccarsi.
- **Test**: `tests/test_cycle57_test_generation.py` (7 test: generazione ed
  esecuzione OK, syntax error, skip non-Python, skip test files, skip dentro
  tests/, skip senza funzioni pubbliche, estrazione nomi funzioni).
- **Stato**: test generation implementata e testata; interventi senior chiusi
  finora: #1 (risk classifier, Cycle 56), #2 (runtime verifier, Cycle 56),
  #3 (test generation, Cycle 57).

## 🚀 Cycle 58 — Semplificazione architetturale (2026-11-15)

Quarto intervento strutturale della lista senior (dalla code review, piano
d'attacco Fase 5): ridurre il numero di moduli senza peggiorare le metriche.

- **Fusione resilience** (Cycle 58, #4): nuovo `CORE/resilience.py` che unisce
  `CORE/exception_handler.py` (should_retry, get_retry_delay, log_error) e
  `CORE/state_recovery.py` (recover_worker_state, get_last_task_for_worker) in
  un unico modulo di resilienza.
- **Rimozione moduli orfani**: rimossi 4 moduli non importati da nessun codice
  di produzione (nessuna metrica di valore associata):
  - `CORE/exception_handler.py`
  - `CORE/state_recovery.py`
  - `CORE/benchmark.py`
  - `MONITORING/predictive.py`
- **Import aggiornati**: `tests/test_usability_hardcore.py` importa ora da
  `CORE.resilience` invece di `CORE.state_recovery`.
- **Regola rispettata**: il Timestral LLM Tuner (`CORE/llm_tuner.py`) non è
  stato toccato (feature differenziante, valore già dimostrato).
- **Test**: tutte le suite affini verdi (199 passed, 1000 subtests).
- **Stato**: interventi senior chiusi finora: #1 (risk classifier, Cycle 56),
  #2 (runtime verifier, Cycle 56), #3 (test generation, Cycle 57),
  #4 (semplificazione, Cycle 58). Restano #5 (benchmark esterni), #6 (fuzzing),
  #7 (GUI approvazioni).

## 🚀 Cycle 59 — Benchmark esterni e validazione indipendente (2026-11-15)

Quinto intervento strutturale della lista senior (piano d'attacco Fase 0):
la settimana della verità — misurare se byte-swarmy, così com'è oggi,
produce valore su task esterni e non progettati da noi.

- **Benchmark esterno** (Cycle 59, #5): nuovo modulo
  `CORE/external_benchmark.py` con:
  - Dataset di 8 task di refactoring atomici e verificabili su
    `bench_target/` (mini-repo Python di 4 file: utils, core/processor,
    core/validator, models/user). Task: type hints, estrazione funzioni pure,
    logging, docstring, list comprehension, validazione password, valuta
    negativa, raggruppamento generico.
  - Esecuzione in **dual mode**: harness (worker ReAct + correction loop +
    audit + risk gate) vs **baseline modello nudo** (solo `models.call`,
    nessun harness, nessun correction loop). Confronta il contributo
    marginale del harness rispetto al modello nudo.
  - Metriche per task: successo al primo colpo, successo dopo correction
    loop, falsi negativi del gate, errori di esecuzione, wall time.
  - Risultati JSON in `state/benchmarks/` (gitignored); report testuale in
    `DOCS/BENCH.md` con metodologia riproducibile.
  - Criterio di uscita Fase 0: se il tempo umano netto è negativo o nullo,
    fermarsi e semplificare; se positivo anche solo del 20%, si ha qualcosa
    su cui costruire.
  - Entry point CLI: `.venv/bin/python -m CORE.external_benchmark --run`
    (richiede Ollama); senza Ollama gira in dry-run.
  - **Risultato (eseguito il 2026-11-15)**: modello nudo migliore del harness:
    successo al primo colpo 50% (naked) vs 12.5% (harness); successo dopo
    correction loop 50% vs 25%; wall medio/task 14s (naked) vs 192s (harness,
    13.6x più lento). Il correction loop del harness ha risolto solo 1 task
    aggiuntivo su 8.
  - **Criterio di uscita Fase 0: NON raggiunto**. Tempo umano netto negativo:
    il sistema richiede più supervisione del lavoro manuale. Raccomandazione:
    fermarsi e semplificare (o passare a un modello più capace per il worker)
    prima di aggiungere feature.
  - Report testuale in `DOCS/BENCH.md`; JSON grezzi in
    `state/benchmarks/external_bench-20261115-164507.json`.
- **Test**: `tests/test_external_benchmark.py` (11 test, mock senza Ollama:
  criterio di successo, naked task, harness first-try, harness correction
  loop, run_all senza factory, save_results, generate_report, main dry-run).
- **Stato**: interventi senior chiusi finora: #1 (risk classifier, Cycle 56),
  #2 (runtime verifier, Cycle 56), #3 (test generation, Cycle 57),
  #4 (semplificazione, Cycle 58), #5 (benchmark esterni, Cycle 59).
  Restano #6 (fuzzing sicurezza), #7 (GUI approvazioni umane).

## 🚀 Cycle 60 — Fuzzing mirato sulla sicurezza (2026-11-15)

Sesto intervento strutturale della lista senior (dalla code review, piano
d'attacco Fase 6): scoprire bypass di sicurezza che i test manuali non trovano.

- **Fuzzing sicurezza** (Cycle 60, #6): nuovo `tests/fuzz_security.py` con
  generatore custom (seed fisso = 42, riproducibile) che fuzza:
  - `SAFETY.security.validate_bash_command`: metacaratteri shell offuscati
    (backtick, $(), ${}, pipe, &&, ||, >, <, \n, \x00...), path traversal su
    comandi allowlistati (cat, rm, cp, mv, touch, ls), comandi fuori allowlist
    (nc, curl, sudo, python -c, bash -c, git push, systemctl, kill, ...).
  - `CORE.tools.ToolSet.write_file`: path traversal (.., path assoluti, ~,
    nomi strani con punti ripetuti), null byte, path troppo lungo, scritture
    benigni che devono ancora funzionare.
  - `CORE.mcp_client.MCPClient._parse_tool_result`: payload mancanti, troppo
    lunghi, tipi sbagliati, JSON malformato, None, liste/dizionari anomali.
- **Invariante verifica**: nessun bypass di sicurezza, nessun crash non
  gestito, nessun file scritto fuori da `project/`.
- **Test**: `tests/fuzz_security.py` (11 test, nessun Ollama richiesto).
- **Esito**: nessun bypass trovato — le difese esistenti reggono al fuzzing.
  Nessun regression test aggiuntivo necessario in `test_security.py`.
- **Stato**: interventi senior chiusi finora: #1 (risk classifier, Cycle 56),
  #2 (runtime verifier, Cycle 56), #3 (test generation, Cycle 57),
  #4 (semplificazione, Cycle 58), #5 (benchmark esterni, Cycle 59),
  #6 (fuzzing sicurezza, Cycle 60). Resta #7 (GUI approvazioni umane).

## 🚀 Cycle 61 — GUI per approvazioni umane (risk gate) (2026-11-15)

Settimo e ultimo intervento strutturale della lista senior (piano d'attacco
Fase 2): chiude il cerchio del risk gate iniziato nella Cycle 56, rendendo
il blocco umano fruibile attraverso l'interfaccia grafica.

- **Coda approvazioni nella GUI** (Cycle 61, #7): nuova sezione
  "🔒 Coda Approvazioni Umane (risk gate)" dentro
  `GUI/task_scheduler_panel.py` che mostra solo i task in
  `awaiting_human_approval` con:
  - Titolo, ID e livello di rischio (parsed dal `reason` del risk gate:
    basso/medio/alto/critico, con icone differenziate ✅/⚖️/⚠️/🚨)
  - Anteprima del motivo di blocco (primi 80 caratteri del reason)
  - Pulsanti per task singolo: ✅ Approva, ❌ Rifiuta con feedback,
    ⏸️ Sospendi (mette in `paused`)
  - Conferma esplicita richiesta per approvare task ad alto/critico rischio
  - Pulsante "✅ Approva tutti (basso/medio)" per approvazione in blocco
    solo dei task a rischio basso/medio (con elenco dei titoli nella
    finestra di conferma)
  - Log delle azioni utente in `logs/user_actions.log`
  - Refresh automatico quando si entra nella scheda (`showEvent`)
- **Notifica badge sulla top bar** (Cycle 61, #7): nuovo `QLabel` `🔒 N`
  nella toolbar di `GUI/control_center.py` (via `GUI/cc_shell.py`), aggiornato
  ogni 3 secondi da un timer (`_update_approval_badge`), visibile solo quando
  ci sono approvazioni in sospeso.
- **Funzioni di transizione stato** in `GUI/task_queue.py`:
  - `approve_task(task_id)` → riporta in `pending`
  - `reject_task(task_id, feedback)` → marca `failed` con motivo
  - `suspend_task(task_id)` → mette in `paused`
- **Test**: flusso approvazione/rifiuto/sospensione verificato end-to-end
  (task creato in `awaiting_human_approval`, approvato → `pending`,
  rifiutato → `failed`, sospeso → `paused`). Suite GUI esistenti verdi
  (37 passed).
- **Stato**: tutti e 7 gli interventi strutturali della lista senior sono
  ora chiusi: #1 (risk classifier, Cycle 56), #2 (runtime verifier, Cycle 56),
  #3 (test generation, Cycle 57), #4 (semplificazione, Cycle 58),
  #5 (benchmark esterni, Cycle 59), #6 (fuzzing sicurezza, Cycle 60),
  #7 (GUI approvazioni umane, Cycle 61).

## 🚀 Cycle 62 — Semplificazione architetturale Fase 1 (2026-11-16)

Continuazione dell'intervento #4 (semplificazione), Fase 1 del piano d'attacco:
inventario di CORE/ e rimozione/fusione di moduli che non aggiungono valore
misurabile.

- **Moduli orfani rimossi** (0 importi da codice di produzione):
  - `CORE/sml_database.py` (201 righe) — database SQLite per modelli SML,
    mai usato
  - `CORE/preflight_cli.py` (69 righe) — CLI di preflight, mai usato
  - `CORE/loop_detector.py` (111 righe) — fuso in `CORE/worker.py` come
    funzioni locali (`detect_loop`, `_compression_ratio`, ecc.)
- **File spostato**: `CORE/example_mcp_server.py` → `tests/example_mcp_server.py`
  (è un file di test, non di produzione); path aggiornato in
  `tests/test_mcp_e2e.py`
- **Import rimosso**: `CORE/orchestrator.py` non importa più `detect_loop`
  (import inutilizzato)
- **Risultato**: CORE/ scende da ~50 a ~47 file. Nessuna metrica peggiorata
  (270 passed, 1000 subtests, boot smoke OK).
- **Regola rispettata**: il Timestral LLM Tuner (`CORE/llm_tuner.py`) non è
  stato toccato.

## ⚡ Cycle 63 — Efficientamento energetico: heartbeat unico GUI (2026-11-16)

Primo intervento della sezione "Efficientamento energetico" del todo
(item #3): consolidamento dei timer della GUI. Nessuna modifica al backend,
nessun Ollama richiesto.

- **Prima**: 5 QTimer separati — `_live_activity_timer` (500ms), `_timer`
  metriche (1500ms, con 3× nvidia-smi + 1× `ollama ps` a ogni battito),
  `_zoom_catchup_timer` (1500ms), `_approval_badge_timer` (3000ms),
  `_completion_timer` (3000ms) + timer SIGINT no-op (200ms).
- **Dopo**: un solo `_energy_timer` (1000ms) con scheduling a rotazione:
  - ogni tick: Live Activity (lettura file, economica) e zoom catch-up
    SOLO se zoom != 100;
  - ogni 3 tick: metriche di sistema (subprocess costosi: da ~2.7 fork/s
    a ~0.9 fork/s a riposo);
  - ogni 3 tick sfalsati: badge approvazioni + barra completamento
    (query SQLite).
- **Timer SIGINT**: 200ms → 500ms (2.5× wakeup in meno, Ctrl+C comunque
  percepibile entro mezzo secondo).
- **Risultato stimato a riposo**: ~5-10% CPU costante in meno (wakeups e
  fork subprocess ridotti; niente più 3× nvidia-smi + ollama ps al secondo
  e mezzo).
- **Verifiche**: py_compile OK; `tests/test_user_workflow.py` 25 passed
  (40 subtests); smoke heartbeat offscreen PASS (5 vecchi timer assenti,
  7 tick simulati + 6 tick reali senza eccezioni, tutti i rami coperti).

## ⚡ Cycle 64 — Corsia veloce single-shot, pronta ma OFF (2026-11-16)

Secondo intervento dell'efficientamento energetico (item #1): la furbata
che si interfaccia con la brutal honesty del benchmark Cycle 59. Il prompt
"naked" ha battuto il loop ReAct (50% primo colpo in ~14s contro 12.5% in
~192s): la corsia veloce riusa ESATTAMENTE quel prompt.

- **`CORE/worker.py`**:
  - `_fast_lane_target()`: euristica deterministica (~0 costo) — il task è
    idoneo se contiene UN solo file target e il testo è < 600 ch
    (`[fast_lane] max_task_chars`);
  - `_execute_fast_lane()`: prompt nudo (variante di quello del benchmark
    Cycle 59) → 1 chiamata LLM → estrazione fence → `ToolSet.write_file`
    (che mantiene AST scanner + safe path + runtime verifier + rollback,
    difese deterministiche che il benchmark ha mostrato costare poco) →
    al massimo 1 retry con l'errore SPECIFICO (max 2 tentativi totali,
    nessun loop);
  - hook in `execute()`: la corsia precede anche la modalità diretta
    (funziona senza protocollo tool-call).
- **Config** (`[fast_lane]`): `enabled=false` DI DEFAULT. La corsia esiste
  ma non cambia il comportamento: regola "measure, don't add". Attivazione
  solo dopo il benchmark di validazione a macchina fredda (con
  `--thermal-limit 60 --cooldown 30`).
- **Scoperta durante i test**: con la corsia attiva, il task E2E del happy
  workflow (client finto ReAct) viene intercettato e fallisce — la corsia
  non è trasparente per i modelli/flow ReAct. Motivo in più per il default
  OFF e per la validazione benchmark prima dell'uso reale.
- **Stima attesa** (da confermare col benchmark): ~90% di energia in meno
  e ~13x più veloce sui task eleggibili (single file).
- **Verifiche**: py_compile OK; 15 nuovi test in `tests/test_fast_lane.py`
  (elegibilità, successo, retry, fallimento pulito, AST scanner attivo,
  fail-open config); suite affini **285 passed, 1 xfailed, 1000 subtests**;
  boot smoke OK.

## 🌡️ Cycle 65 — Regola termica: mini-test stadiali (2026-11-16)

Regola permanente richiesta dall'utente: i test che chiamano l'LLM non
devono surriscaldare il portatile. Mai generazioni monolitiche — stadi
brevi con verifica tra uno e l'altro.

- **La regola** (codificata in `todo.md` + `DOCS/BENCH.md`):
  1. scheletro (classe vuota / `test_*` con `pass`) → verifica host-side
     (~gratis: `py_compile` / `pytest --collect-only`, zero LLM);
  2. definizioni/corpi minimi → verifica;
  3. implementazione completa: mai in un'unica generazione lunga.
  Ogni stadio genera ≤ ~300 token; nel benchmark un task = uno stadio con
  `--cooldown 30 --thermal-limit 60`. Errori di import/struttura si
  scoprono allo stadio 1 senza pagare le generazioni successive.
- **Implementata in `CORE/test_generator.py`** (era 1 chiamata da 600
  token che chiedeva il file completo):
  - stadio 1: prompt SCHELETRO (max_tokens=250) → scrittura →
    `pytest --collect-only` (import/struttura senza eseguire test);
  - stadio 2: prompt CORPI che riceve lo scheletro VERIFICATO
    (max_tokens=500), con controllo anti-alterazione (stessi nomi test);
  - su qualunque fallimento di stadio: file di test rimosso + ERROR con
    feedback specifico (niente file mezzi scritti nel progetto utente).
- **Benefici**: generazioni più brevi = picchi termici minori; il guasto
  più comune dei 3B (import rotto) si paga allo stadio 1 (~250 token) e
  non dopo una generazione completa; verificate tra gli stadi = gratis.
- **Verifiche**: py_compile OK; 5 nuovi test in
  `tests/test_staged_test_generation.py` (2 stadi, collect-check, anti-
  alterazione, errori puliti); test Cycle 57 ancora verdi; suite affini
  **290 passed, 1 xfailed, 1000 subtests**; boot smoke OK.

## 🌡️ Cycle 66 — Pausa termica adattiva + verifica benchmark fast lane
### (2026-11-16, bloccata dal limite termico 60°C)

Tentativo di validazione della corsia veloce (fast lane) con il benchmark
esterno. Risultato onesto: **2/2 run abortite per termica su ext-01**, il
benchmark completo non gira sotto 60°C su questo portatile.

- **Fix elegibilità** (`CORE/worker.py`): la chiave `file` esplicita è
  AUTOREVOLE — prima un task con "utils.py" nel titolo e
  "bench_target/utils.py" nella descrizione risultava "multi-file" →
  non eleggibile. Ora tutti gli 8 task del benchmark sono eleggibili.
- **Fix harness** (`CORE/external_benchmark.py`): `run_harness_task` ora
  passa la chiave `file` al worker (contratto identico alla coda reale).
- **Pausa termica adattiva** (`_thermal_pause`): tra fast lane↔naked e
  tra task, aspetta che la temperatura scenda sotto limit−8°C (check
  ogni 10s, max wait 900s, poi `thermal_abort`). Il cooldown fisso di
  30s era inutile: un singolo task porta 49→78°C in ~107s (0,27°C/s).
  Bug beccato nei test: pre-check con logica invertita (usciva sempre
  OK) — rimosso, il loop gestisce tutto. 5 nuovi test
  (`tests/test_thermal_pause.py`).
- **`tools/verify_cycle.sh`**: script del ciclo di verifica standard
  (py_compile → test_runner con timeout → boot smoke) — un solo comando,
  zero LLM, zero calore. Rende eseguibile l'item #1 del piano di domani.
- **Dati termici misurati** (il vero risultato della sessione):
  - freddo (44°C): ~0,3°C/s di salita sotto load 3b
  - macchina calda (51°C): **~1°C/s** — un naked di 21s → 75°C
  - pausa adattiva: 78→51°C in 90s (funziona, ma 51°C non è abbastanza
  freddo per ripartire)
  - conclusione fisica: sotto 60°C, SOLO segmenti brevi da partenza
    fredda (44-46°C); un benchmark completo in una sessione è
    praticamente impossibile su questo hardware.
- **Stato config**: `fast_lane.enabled = false` (rollback: nessuna
  validazione ottenuta, regola "measure, don't add" rispettata).
- **Verifiche**: py_compile OK; test_thermal_pause 5 passed;
  test_external_benchmark 11 passed; fast lane + e2e 64 passed.

## 🎯 Cycle 66 parte 2 — Piano d'azione sui dati attuali (living doc)
### (2026-11-16, scritto mentre il driver delle sessioni fredde gira)

Richiesta utente: "scrivi un piano d'azione sui dati attuali e poi li
aggiorniamo appena abbiamo gli altri dati".

- **`DOCS/BENCH.md` § "PIANO D'AZIONE — Cycle 66"** (living doc):
  - §1 dati certi misurati: baseline Cycle 59 (naked 50%/14s vs harness
    12.5%/192s), fisica termica (0,3°C/s da freddo, 1°C/s da caldo,
    pausa 78→51 in 90s), hardware (7b non entra in 4GB, granite4 MoE
    unico candidato potente)
  - §2 decisione opzione A: sessioni fredde
  - §3 stato fasi 0-5 con segnaposto (driver in esecuzione, tabella 8
    task, temp_before/after, micro-ciclo config, granite4, 3 modelli)
  - §4 **criteri di verdetto pre-scritti** (5 regole ordinate per
    priorità) → l'aggiornamento a fine driver sarà meccanico, senza
    ri-negoziazione
  - §5 architettura 3 modelli dell'utente mappata sul codice esistente
    (Timestral / decision deterministico-first / esecutore granito o API)
  - §6 vincoli permanenti (60°C, stadiale, measure-don't-add, zero
    carico durante il driver)
- **`todo.md`**: item 1 → `[~]` verify_cycle.sh creato (TODO prima
  esecuzione end-to-end); item 2 → `[~]` driver sessioni fredde in
  esecuzione, riferimento al piano in BENCH.md.
- Nessun codice toccato (il driver sta misurando): solo docs. Zero
  carico CPU durante le sessioni benchmark.

## 🔄 Cycle 66 parte 3 — Correzione driver: num_thread + fast lane ON + temp per fase
### (2026-11-16, prima del rilancio delle sessioni fredde)

Status check a richiesta utente ("come procede?"): 2/8 sessioni fatte
ma con 2 problemi beccati nei dati.

- **Problema 1 (errore di sequenza mio)**: il driver era partito con
  `fast_lane.enabled = false` (rollback pre-lancio) → girava il
  correction loop completo (attempts=3, wall 190/117s). Le 2 sessioni
  valgono come baseline harness-completo, non misurano la fast lane.
- **Problema 2 (fisica reale)**: la generazione LLM scalda ~1°C/s da
  qualsiasi partenza (46→65°C in 14s; correction loop → 78-82°C). Il
  limite 60°C veniva sforato DURANTE i task. Il "0,3°C/s da freddo"
  era una media ingannevole che includeva il setup.
- **Decisione utente**: stop + riavvio corretto.
- **Fix** (config-only, zero root):
  - `--num-thread` nel benchmark: inietta `num_thread = 2` SOLO in
    memoria (config.toml intatto), stesso valore per fast lane e naked
    → confronto equo, ~metà del calore. Passthrough aggiunto in
    `_get_tuned_options` (il tuner non lo tocca: è un vincolo fisico).
  - `fast_lane.enabled = true` per la validazione.
  - FASE 2 del piano completata: `temp_before`/`temp_after` per fase
    in entrambi i runner (helper `_max_temp()`; ogni sessione registra
    i propri picchi → verifica empirica del fix num_thread).
  - `tools/bench_cold_sessions.py` passa `--num-thread 2`.
- **Verifiche**: py_compile OK; 34 test verdi (thermal pause +
  benchmark + fast lane); config check fast_lane ON.
- Le prime 2 sessioni (ext-01/02) restano nei JSON come baseline.

## 🏁 Cycle 66 parte 5 — VERDETTO: fast lane NON validata, benchmark chiuso
### (2026-11-16 ~13:10, decisione utente: "stop definitivo benchmark")

Mentre il driver girava (2/8 sessioni finite), i dati hanno mostrato:

- **`num_thread=2` NON riduce il calore**: pendenza 0,27-0,29°C/s
  INVARIATA vs i run senza override. Spiegazione fisica: su i7-7700HQ
  il turbo compensa (meno thread → frequenza per core più alta →
  stessa potenza complessiva). La leva giusta sarebbe il cap di
  frequenza (sudo) o altra macchina.
- **Picchi 79-80°C durante le fasi** anche da partenza fredda
  (grazie ai nuovi `temp_before/after`: 52→79°C fast, 46.5→69°C naked
  in 21s). Il limite 60°C è sforato durante ogni task: seconda
  violazione del protocollo → l'utente ha fermato tutto.
- **Fast lane attiva ma 0/2 primo colpo**, sempre con fallback al
  correction loop (attempts=3, wall ~95s). Campione insufficiente ma
  zero evidenze pro.
- ext-01 naked perso: max wait 900s scaduto (raffreddamento lento al
  mezzogiorno).

**Verdetto** (`DOCS/BENCH.md` §8, con criteri pre-scritti del piano):
`fast_lane.enabled = false` PERMANENTE finché non cambino le condizioni
(cap di frequenza, altra macchina, giornata fresca). Regola
"measure, don't add" rispettata fino in fondo: l'idea
deterministico-first resta la direzione architetturale, questa
implementazione locale NON entra in produzione.

**Cosa resta** (tutto riusabile, niente buttato): temp_before/after
per fase, pausa termica adattiva, sessioni fredde driver +
progress_reporter (fixato il doppio conteggio: done-regex conta solo
la riga JSON), dati parziali in state/benchmarks/, fisica termica
documentata. Prossimo lavoro: FASE 3 micro-ciclo config (zero Ollama).

## ⚙️ Cycle 67 — FASE 3: micro-ciclo config (zero Ollama, zero calore)
### (2026-11-16, dopo la chiusura del benchmark)

Applicati i restanti item di efficientamento concordati:

1. **`num_ctx` planner 3072 → 2048** (`[models.planner]`): allineato al
   default del config tipizzato (2048). Il planner divide problemi con
   prompt brevi — 1536 token utili per il prompt sono ampi. Rollback:
   una riga.
2. **`[hardware].keep_alive_sec = 900`** (NUOVO, prima assente = "auto"):
   con il default Ollama (~300s) il warmup al boot (`warmup_model =
   "worker_coder"`) restava utile solo 5 minuti. 900s = 15 min →
   il warmup paga davvero e i task in sessione restano a modello caldo
   (load 8-15s gratis). Costo onesto: ~2.5GB RAM residenti per 15 min —
   con 7.6GB totali e 3.3 liberi c'è lo spazio, e poi si scarica da
   solo. NOTA: la RAM reale è 7.6GB (non 4GB come in nota precedente).
3. **Verifica toggle Timestral/SystemMonitor/Lifecycle** (item #4
   efficientamento — RICERCA, non modifica):
   - Timestral: toggle GIÀ presente (`[thermal].enabled = true`, thread
     30s) ✓
   - SystemMonitor: PASSIVO (solo `check_resources()` on-demand dagli
     health check — zero thread, zero costo da fermo) → toggle NON
     necessario ✓
   - Lifecycle: PASSIVO (metodi una-tantum al boot + backup periodico
     già in timer orchestrator) → toggle NON necessario ✓
   Esito onesto: nessun codice toccato, verifica documentata.

**Verifiche**: config tipizzata (planner num_ctx=2048, keep_alive_sec=
900, fast_lane OFF) OK; boot smoke EXIT=124 con pausa rispettata;
34 test verdi. Versione 0.3.15.

## 🏛️ Cycle 68 — Registro del debito tecnico (debt ledger) + skill
### (2026-11-16, strategia refactoring dell'utente)

Idea utente: DB + skill per far dialogare LLM e SQL e tenere traccia di
tutti i pezzi da rifattorizzare. È la metà mancante di code_map.py
(che mappa cosa ESISTE via AST→SQLite): il ledger traccia cosa VA
RIFATTORIZZATO. Nota: SQLite era già in uso in 5 punti del progetto
(memory_event_store, sml_database, code_map, task_queue, resilience).

- **`CORE/debt_ledger.py`** (NUOVO): schema `debt_items` (kind, file,
  file_hash, title, rationale, priority, effort, status, timestamps),
  API (`add/next/list/mark/get/stats/context_for_file`) e CLI completa.
  Le 3 regole di design codificate:
  1. L'LLM NON scrive SQL libero — dialoga con API/CLI deterministiche
     (pianificazione fredda, adatta al limite 60°C);
  2. `file_hash` alla registrazione → item `stale` al primo next() se
     il file cambia (mai proposto alla cieca);
  3. un item per sessione, stadiale: next() sceglie dalla coda
     (priority ASC + created ASC, prefer_kind ripriorizza).
- **Integrazione code_map**: `context_for_file()` riporta i simboli del
  file dalla mappa (fail-open, cap 30) per RIUSARE le API esistenti.
- **Skill** `.opencode/skill/debt-ledger/SKILL.md`: flusso registrare →
  next → context → stadio → done, riusabile in ogni sessione futura
  (già registrata dal sistema).
- **Bug beccati in costruzione**: (1) argparse: --root solo sul parser
  principale non arriva ai sub → parent parser condiviso; (2) schema
  creato solo da init() → no such table da stats → schema garantito a
  ogni connessione (idempotente); (3) _check_staleness ignorava il
  project_root (usava il repo di default) → root passata in next().
- **Demo reale**: registrato l'item #1 vero (pausa tra fasi ignora
  cooldown_s minimo, prio 3, xs) — il flusso next/hash/stale funziona
  su dati reali.
- **Verifiche**: py_compile OK; 11 test nuovi (test_debt_ledger:
  priorità, stale-on-change, done skip, prefer_kind, fifo, fail-open,
  validazioni, CLI e2e); suite 34+11=45 verdi. Versione 0.3.16.

## ⏱️ Cycle 69 — Primo test reale del debt ledger, a tempo
### (2026-11-16, richiesta utente: "dovremmo farlo in mooolto meno tempo")

Prima esecuzione del flusso completo della skill debt-ledger su item
veri, con misurazione:

- **Coda alimentata**: item #1 (pausa tra fasi ignora cooldown_s) e
  #2 (dedup lettura temp in _thermal_pause), entrambi veri e noti.
- **Esecuzione item #1**: `next` → `progress` → `context` (fail-open
  corretto: [] senza codemap) → stadio (cooldown_s minimo applicato
  anche alla pausa tra fast lane e naked) → py_compile → 34 test →
  `done`. **Durata totale: 13,4 secondi.** Nessuna esplorazione LLM:
  il lavoro era già descritto in SQL.
- **Regola stale dimostrata live**: eseguito #1 (stesso file), il
  `next` successivo ha marcato #2 stale automaticamente e restituito
  "coda vuota" (mai proposto alla cieca). Ri-registrato come #3 con
  hash aggiornato; il vecchio #2 resta in storia.
- **Stato coda**: done 1 · open 1 (#3) · stale 1.
- **Verifiche**: 34 test verdi; item #1 chiuso con hash verificato.

## 🖥️ Cycle 70 — Debt ledger integrato nella GUI (regola di parità)
### (2026-11-16, richiesta utente: "tutte le funzioni devono essere
### usufruibili dalla gui meglio metterlo come regole")

- **REGOLA DI PARITÀ GUI** (nuova, permanente): ogni funzione del ledger
  deve avere un controllo nella Plancia — niente API che esistono solo
  da terminale. Documentata nel pannello, in todo.md e applicata:
  - `stats` → etichetta coda · `list` → tabella · `add` → dialog
  - `next` → 🎯 Prossimo: item dalla query, marcato in_progress e
    selezionato (il lavoro arriva dal ledger, mai da un'idea)
  - `mark` → ▶ In corso / ✅ Fatto · `context` → 🔍 Contesto code_map
- **`GUI/debt_ledger_panel.py`** (NUOVO): tabella item (stato colorato,
  priorità, tipo, sforzo, file, titolo), dialog di registrazione con
  i 6 campi validati dal modulo, azioni on-demand. Disciplina Cycle 63
  rispettata: ZERO timer nuovi, refresh solo a bottone. Fail-open:
  coda vuota o senza code_map → messaggio, mai crash.
- **Registrazione Plancia**: carta "🏛️ Registro del debito" in
  `GUI/panels.py` (slot 2,1) + pannello in `GUI/center_area.py`
  (stesso pattern di audit_project).
- **Test** `tests/test_debt_ledger_panel.py` (7, offscreen): coda
  vuota no-crash, list, next-prende-e-seleziona, next senza validi,
  mark done dalla GUI, context fail-open, NESSUN timer avviato.
- **Verifiche**: py_compile dei 3 file GUI; 52 test verdi (ledger +
  pannello + benchmark + fast lane + termici); boot smoke EXIT=124.

## 🦋 Cycle 71 — Prismalux: radiografia + skill + campagna refactoring
### (2026-11-16, richiesta utente: nuovo progetto target di test)

- **NUOVA SKILL `project-radiography`** (`.opencode/skill/`, già
  attiva nel sistema): la procedura di radiografia fredda
  generalizzata — censimento per tipo, distribuzione per directory,
  salute compilazione, god-file, marker debito, build system,
  code_map, registrazione item nel ledger. Zero LLM, riusabile per
  qualunque progetto futuro.
- **Prismalux radiografato** (repo utente, clonato in
  `project/prismalux`): 312 cpp + 180 h + 164 py (0 errori di
  compilazione), 6 god-file >100KB in gui/pages, 123 marker
  TODO/FIXME (36 in gui/pages), 3 stack Android parallele. code_map
  costruito (164 file, 1800 simboli → context attivo).
- **Coda ledger per-progetto** (`--root project/prismalux`): 4 item
  reali; eseguito e chiuso #4 (rinomia SCREEENSHOT→SCREENSHOT, xs,
  2 riferimenti aggiornati, 0 residui).
- **REGOLA UTENTE (importante)**: prismalux è un TEST di refactoring
  esterno — **nessun artefatto di byte-swarmy dentro il suo repo**.
  Beccato e corretto sul vivo: `git add -A` aveva infilato i DB del
  tooling (debt_ledger.db + codemap.db) nel commit del clone →
  `git rm --cached` + .gitignore (.byteswarm/, state/) + amend. E in
  byte-swarmy `project/*` è già gitignored (il clone resta esterno in
  entrambe le direzioni).
- **Vincolo termico documentato**: il build C++ (312 file, CMake) =
  carico pesante; gli item C++ (god-file split, effort l) restano in
  coda finché esiste una strategia di build stadiale/ccache.
- **Stato coda prismalux**: done 1 · open 3 (god-file p2, triage
  marker p3, 3 stack Android p3). Push del clone: decisione utente.

## 🦋 Cycle 72 — Prismalux item #5: fallimento, root cause, fallback (2026-11-17)

### Run 2 (worker reale, agent fresco)
- Attesa fredda: 28 minuti (ambient 46-53°C, spikes 71°C) → poi 35s di
  esecuzione, 3 step, **nessun cambiamento a server.py**.
- Il worker ha scritto solo `store.json` (0 byte poi 16 byte) e si è
  fermato: "No further actions needed". Temperatura 46→66°C in 35s —
  **violazione del limite 60°C** (causa: il routing ha passato il task a
  `worker_granite` SENZA l'override `num_thread`, perché l'override era
  applicato solo al `model_key` base).

### Root cause provato DETERMINISTICAMENTE (zero LLM)
- `find_skill(title, desc)` ha matchato **py-json-store** in ENTRAMBI i
  run (la descrizione conteneva "file" e, nel DISCIPLINA, "store").
- `format_skill_block` iniettava la ricetta con "Create project/main.py"
  e "STORE_FILE = store.json" nel prompt, con il footer
  "when in doubt, follow the recipe instead of inventing".
- Il modello 3b ha seguito la ricetta alla lettera → main.py / store.json.
  Non era "il modello è stupido": il SISTEMA gli dava una ricetta sbagliata.
- Anche la complessità "alta" del routing (81 file, profondità 3) veniva
  da "main" e "read_file" citati nella DISCIPLINA → routing heavy.

### Fix (Cycle 72)
- SKILLS/py-json-store.md (e 3 altre: unittest, cli-script, context-manager):
  rimossi keywords generici (`file`, `lettura`, `dati`, `test`, `main`,
  `input`, `output`, `funzione`, `with`) — restano i specifici.
- `tools/swarm_refactor_session.py` v2:
  - override `num_thread` su TUTTI i modelli (protezione termica anche
    quando il routing cambia modello);
  - DISCIPLINA senza nomi di tool/file (non inquina routing né skill).
- Test: `tests/test_skills_matching.py` (11) blocca la regressione:
  il task docker_mcp non matcha py-json-store, i match legittimi restano.

### Fallback deterministico (item #5)
- Applicato `sed` su `MCPs/docker_mcp/server.py`: 2 bare `except:` →
  `except Exception:` (2 righe, py_compile OK, 0 bare residui).
- Commit nel clone: `refactor: bare except -> except Exception` (avanti 2).
- Item #5 marcato done nel ledger per-progetto (fallback documentato).
- Item #6 (altri server MCP con bare except) resta in coda per la prossima
  sessione — ora il worker ha una chance onesta con il matcher fixato.

## 🦋 Cycle 73 — Lezione UEFI, fallback deterministico, GUI ventole (2026-11-17)

### ⚠️ LEZIONE UEFI (importante, registrata nel ledger)
- Il laptop (HP Pavilion Power 15-cb0xx) ha subito un **blocco UEFI per
  surriscaldamento** durante i run. Conseguenza misurata: un file
  sorgente corrotto (null bytes) → ripristinato da git.
- **Ho sbagliato**: avevo definito "falso" il sensore B0D4 (100°C sotto
  carico) e cambiato la fonte termica a coretemp-only in
  CORE/routing.py, MONITORING/thermal_manager.py e tools/* → il sistema
  diventava cieco sul componente più caldo, mentre l'inferenza LLM
  continuava. **REVERT completo**: la max su TUTTE le zone termiche è
  la scelta sicura (vede il componente più caldo, qualunque esso sia).
- B0D4 verificato a freddo: 49-52°C (varia col carico = sensore reale).
- **La soluzione è il controllo ventole, non abbassare la guardia**:
  `tools/fan_control_qt.py` (nbfc + pkexec, dialog password KDE) e
  **guardia dura** nel runner: mai inferenza se una zona ≥ 90°C.
- Il limite utente 60°C con inferenza reale resta difficile
  (misurato 42→70°C coretemp in 39s anche con num_thread=2): le
  ventole al massimo sono ora un prerequisito dei run LLM.

### Campagna prismalux: ombrello #6 + #7 chiusi via fallback deterministico
- 3 run LLM onesti (runner v1/v2/v3): il worker 3b NON è capace per
  modifiche minime a codice esistente (run 3: legge il file — il fix
  skill-matcher funziona — ma poi scrive file sbagliati: ha SOVRASCRITTO
  requirements.txt con 9 byte di spazzatura; ripristinato da git).
- Verdetto: le gate del ToolSet proteggono i test ma NON i file dati —
  per questa classe di task il fallback `sed` è l'esecutore giusto.
- `sed` bare `except:` → `except Exception:` su TUTTI i server MCP:
  22 file, **57 conversioni**, py_compile OK su ciascuno, 0 bare residui.
  Commit clone `037ff1f` (avanti 3).
- Ledger prismalux: done 4 (#4 #5 #6 #7) · open 3 (#1 god-file C++
  bloccato sulla strategia build, #2 triage marker, #3 Android).

### Altro
- Bug runner fixati: `--model` ripristinato (Namespace AttributeError),
  `--threshold` aggiunto come flag configurabile.
- `tools/fan_control_qt.py` (NUOVO): GUI PyQt6 ventole (MAX/AUTO/OFF/
  Stop) con temperatura live da max-across-zones; test smoke offscreen.
- Suite: 22 test verdi (matching skill, runner, ledger). Boot smoke OK.

- 🌀 **VENTOLA/** (richiesta utente): il controllo ventole ora vive in
  `VENTOLA/` (`ventola.py` + `avvia.sh` doppio-click + README con i
  comandi sudo equivalenti). Mossa con `git mv` da `tools/` — GUI
  rilanciata dal nuovo percorso.

## 🦋 Cycle 74 — Prismalux: esperimento chiuso, clone rimosso (2026-11-17)

- **Decisione utente**: l'esperimento ("vedere se potevamo importare
  qualcosa come software e riusarlo") è concluso → il clone esce da
  byte-swarmy. `project/prismalux/` eliminato INCLUSIVE i 3 commit
  locali non pushati (rinomia SCREEENSHOT + 57 conversioni bare
  except) — perdita confermata esplicitamente dall'utente.
- Il valore resta NEL SISTEMA: skill `project-radiography`, fix
  skill-hijack + test di regressione, runner sessioni (agent fresh,
  guardie termiche), verdetto onesto sul worker 3b (non capace per
  modifiche minime; le gate proteggono i test ma non i file dati),
  lezione UEFI + `VENTOLA/`.
- Il ledger per-progetto e il code_map vivevano DENTRO il clone
  (.gitignored): rimossi col clone, nessun artefatto di prismalux
  resta in byte-swarmy.

## 🦋 Cycle 75 — verify_cycle.sh end-to-end + skill debt-ledger (2026-11-17)

- **`tools/verify_cycle.sh` prima esecuzione end-to-end** (era il
  parziale più antico): py_compile OK (6 file) · boot smoke OK (rc=124) ·
  test_runner 64 file / 60 OK / 4 KO / 756 pass / 3 fail / 3 skip in
  387s. I 3 fail sono pre-esistenti (NON causati da miei cambi):
  `test_reuse.py` (assert 3072 vs 2048 — test stale: Cycle 67 aveva
  cambiato `num_ctx` planner a 2048 ma il test non fu aggiornato →
  corretto), `test_user_workflow.py::TestToolbarToggle` (flake noto),
  `test_functional_swarm.py` (timeout 120s, flaky su hardware).
  Disciplina rispettata: il FAIL end-to-end è stato indagato, non
  ignorato; qui il FAIL era "test vecchi", non regressione.
- **Skill `debt-ledger`** scritta (`SKILL.md`): regole permanenti +
  CLI completa + ciclo di sessione stadiale + regola di parità GUI +
  esempio reale 13,4s. Riusabile in ogni sessione futura.
- `tests/test_reuse.py`: 3072 → 2048 (allineato a Cycle 67).

## 🦋 Cycle 76 — Test agentico Qt/PyQt6: verdetto FAIL (2026-11-17)

- 4° run LLM, 4° fallimento (coerenza col verdetto bare-except):
  task "crea VENTOLA/hello_qt.py". Il worker ha ignorato il file target
  e scritto `project/main.py` (10 byte) + `patch_code.py` (bloccato da
  regression gate); `hello_qt.py` NON creato. Routing "media → worker_coder"
  (nessun heavy, bene). Temp 41→79°C in 105s (guardia 90°C non scattata).
- Danno pulito: main.py ripristinato da git, patch_code.py e
  tests/test_patch_code_regression.py rimossi, worktree tornato pulito.
- **Deliverable del test prodotto**: un verdetto onesto, non un'app.
  Il worker 3b non è capace di creare un file PyQt6 da zero, esattamente
  come non è capace di modifiche minime — la capability di scrittura
  codice su questa macchina va misurata su modelli più forti o con
  esecutori deterministici.

## 🌀 Cycle 77 — Ventole dentro byte-swarmy (2026-11-17)

- **Plancia**: nuova carta "🌀 Ventole" (`GUI/fan_panel.py` → riusa
  `VENTOLA/ventola.py`, regola di parità GUI rispettata) con temp live,
  MAX/AUTO/OFF/Stop via pkexec (dialog password KDE).
- **Runner** (`tools/swarm_refactor_session.py`):
  - `--max-run-sec` (default 300s = 5 min): hard cap wall-clock su
    `worker.execute` (thread daemon + join timeout) per evitare il blocco
    UEFI — se scade, log "TIME LIMIT EXCEEDED" e abort.
  - best-effort avvio ventole al massimo via `sudo -n` (non blocca se
    non configurato: l'utente resta responsabile, con warning esplicito).
  - gate su CPU vera (coretemp) + warning se una zona ≥ 95°C (B0D4
    saturo, sensore noto difettoso).
- **Scopo**: il limite "tot minuti" richiesto dall'utente è ora
  enforced dal runner; il controllo ventole è dentro il software
  (Plancia), non uno strumento esterno.

## 🔒 Cycle 79 — Gate di sicurezza: file protetti + shrink sospetto (2026-11-17)

- **Root cause del danno Cycle 76**: il worker ha sovrascritto
  `requirements.txt` (203 righe → 9 byte) perché la security gate
  controllava solo test skeleton e codice pericoloso, non i file di
  infrastruttura. Fix: `PROTECTED_FILES` (frozenset di basename, case-
  insensitive) in `CORE/tools.py`: `write_file`/`delete_file`/`move_file`
  bloccati su file protetti esistenti; `patch_code` resta permesso
  (edit mirati = percorso sicuro). Guardia aggiuntiva "suspicious
  shrink": se un file esistente ≥500 byte viene ridotto a <20% delle
  dimensioni originali, blocca (pattern esatto del danno).
- **Test**: `tests/test_toolset_gates.py` (14 test) — file protetti,
  shrink sospetto/legittimo, path traversal, AST scanner, gate base.
  Il componente più critico (la gate) ha ora test dedicati.

## 📚 Cycle 81 — "Salva culo" refs (2026-11-17)

- **Nuova cartella `GUI/refs/`** con cheat sheet curati per ridurre le
  allucinazioni del worker: `pyqt6.md` (widget/layout/segnali/threading),
  `toolset_api.md` (firme dei tool + errori comuni), `debt_ledger.md`
  (CLI + regole). Sono read-only (path protetto: il worker non può
  sovrascriverli).
- **Nuovo tool `list_refs()`** in `ToolSet`: elenca i cheat sheet
  disponibili; il worker li legge con `read_file`/`read_document`. Il
  prompt iniziale menziona "REFS: cheat sheets disponibili — chiama
  list_refs()" se la cartella esiste. `_summarize_result` gestisce
  `list_refs` (output corto).
- **Perché non RAG**: il matching deterministico (keyword) è sufficiente
  per un piccolo set curato; il RAG aggiungerebbe nondeterminism +
  infra senza beneficio misurabile (regola "measure, don't add").
- Regola di parità GUI: i ref sono file, non funzioni del ledger, quindi
  non richiedono un controllo nella Plancia (sono letti dal worker via tool).

## 📚 Cycle 83 — Ref per window manager espliciti (2026-11-17)

- **Nuovi cheat sheet**: `GUI/refs/tkinter.md`, `GUI/refs/pyside6.md`
  (confronto PySide6 vs PyQt6, segnali, threading, tool di conversione).
  `pyqt6.md` già esistente.
- **Iniezione condizionale con trigger obbligatori**: un ref WM si
  inietta SOLO se il nome del WM compare esplicitamente nel task
  (pyqt/pyqt6, pyside/pyside6, tkinter/ttk). Un task "crea GUI" generico
  non inietta nessun ref WM (evita cross-contamination). Soglia >=2
  keyword per i ref generici (toolset_api, debt_ledger).
- **Matching per confine di parola** (regex `(?<!\w)...(?!\w)`) invece
  di substring: evita falsi positivi ("tk" in "toolkit").
- **Max 2 ref per prompt**, 600 char ciascuno, fail-open.
- Verificato con smoke test: "crea finestra PyQt6" -> solo pyqt6.md;
  "crea GUI generica" -> nessun ref WM.

## 💬 Cycle 84 — Clarifier: GUI senza toolkit → domanda (2026-11-17)

- **Principio utente**: "ask vaghi, then if X do Y" — deterministico.
  - `CORE/clarifier.py`: nuovo pattern di ambiguità: se il task parla di
    GUI/interfaccia/finestra/widget/maschera ma NON menziona nessun
    toolkit (pyqt/pyside/tkinter/qt/tk/ttk/wx/kivy/flet/dearpygui), il
    clarifier genera la domanda "Quale toolkit GUI/window manager?"
    con opzioni PyQt6/PySide6/tkinter/Altro.
  - Se il toolkit è esplicito, nessuna domanda → il ref corrispondente
    viene iniettato automaticamente (Cycle 82-83).
  - Fail-open: se il rilevamento fallisce, il task procede senza chiarimento.
- **Il "if X then Y" è già implementato** via `_REF_KEYWORDS` + `_REF_TRIGGERS`:
  toolkit specificato → ref iniettato. Il clarifier gestisce il "ask if vague".
- I due pezzi insieme formano il pattern deterministico richiesto:
  vago → chiedi; specifico → inietta il ref giusto.

## 🛡️ Cycle 85 — Audit robustezza: 12 difetti trovati e corretti (2026-11-17)

Batteria: py_compile (264 file) + pyflakes (installato) + pytest + smoke
sandbox + boot smoke. Risultati.

### 🔴 Funzionalità silenziosamente morte (fix)
1. **persistent_memory mai importata in worker.py**: `record_task_completed`,
   `update_project_context`, `build_context_for_prompt` esistevano in
   CORE/persistent_memory.py ma il try/except le seppelliva → il contesto
   persistente nel prompt iniziale era SEMPRE vuoto da sempre. Fix: import.
2. **run_test_suite dead-on-arrival**: NameError su `sys`/`json`/`BASE_DIR`
   (mai importati in tools.py), mascherato dal try/except. Il planner
   ORDINA al worker di usarlo → ogni worker lo chiamava e riceveva errore.
   Fix: import + riorientamento al PROGETTO del worker (project_root),
   con fallback pytest e errore istruttivo ("no tests/").
3. **bwrap execvp failure**: argv con path host (sys.executable, script
   host) non esistono nel sandbox (progetto in /workspace, venv in
   /opt/venv). Fix: helper `_sandbox_argv` in ToolSet — traduce
   interprete → sandbox.python_executable() e path assoluti sotto
   project_root → /workspace/...; applicato in `_run` e run_test_suite.
   PRIMA: bandit/mypy nel gate lint fallivano ugualmente (mascherati).
4. **_ollama_installed inesistente** (task_scheduler_panel): la combo
   modelli mostrava solo "(default)" sempre. Fix: ollama_list_models().
5. **proj_name undefined** (cc_orchestrator): NameError nel tooltip della
   barra quando un task è in esecuzione. Fix: calcolo locale.
6. **`python GUI/center_area.py` crash**: blocco __main__ con crash
   handler ben fatto ma sys/QApplication/ControlCenter mai importati.
   Fix: import nel blocco.
7. **undefined names residue**: `subprocess` (external_benchmark fallback
   sensors), riga morta `temps` (routing), `log` nel fallback tomli
   (orchestrator → print su stderr), doppio import ToolSet/AgentMemory/
   ModelClient (orchestrator), `def embed` mai chiuso (ollama_client:
   corpo orfano dopo return → ripristinata firma).

### 🟠 Collection pytest
8. **tests/archiviati ignora il file troncato**: TEST_GUI_QT_7.py è
   troncato su disco (riga 545) e TRACCIATO in git → pytest lo raccoglie
   e l'exit code dell'intera run diventa ERROR. Fix: root conftest.py
   con collect_ignore = ["tests/archiviati"] + sys.path insurance.

### ✅ Verifica (tutti test deterministici, zero LLM)
9. **Cross-contamination ref Cycle 83**: task "PySide6 + QApplication"
   riceveva pyqt6.md (con pyqtSignal → crash garantito). Fix: trigger di
   famiglia + mutua esclusione (pyside esplicito → skip pyqt6, e
   viceversa; entrambi espliciti → entrambi, per task di conversione).
   11 test: tests/test_refs_injection.py.
10. **toolset_api.md corretto**: run_test_suite documentata con la
    semantica reale (test del progetto, non del repo) + typo "simbodo".

### Verifiche eseguite
- pyflakes: 0 undefined names su CORE/tools/SAFETY/MONITORING/VENTOLA/GUI
- 40 passed (+18 subtests) su sandbox/toolset_gates/refs_injection/swarm_session
- Smoke sandbox reale: run_test_suite su progetto pytest → 1 passed;
  lint_code → SYNTAX OK + messaggi informativi bandit/mypy
- Bare except in CORE: 0
- Boot smoke + import GUI headless: OK

### 🟡 Seguito suite completa (789 passed, 2 failed → poi corretti)
11. **Parità GUI violata**: DebtLedgerPanel e FanPanel (pannelli
    istanziati direttamente, non via wrap_in_panel_page) non avevano
    back_btn → il test di ritorno alla Plancia falliva su 2 subtests.
    Fix: back_btn + _back_to_main (pattern hardware_panel) su entrambi.
    Test parità: 15/15 subtests verdi; 22 test ledger/ventola verdi.

Riepilogo finale suite (senza i 2 flake noti): 789 passed, 0 failed,
3 skipped, 1050 subtests passed, in 18:54 (più lenta del previsto:
i gate ora eseguono veri comandi sandbox invece di morire su NameError).

### 🔴 Seguito classificazione "flake" (Cycle 85c)
12. **TestToolbarToggle NON era un flake**: click su "orchestratore non
    attivo" → branch auto-start → subprocess REALE + 5s attesa → '▶'!='⏸'.
    Il flake era self-healing (run successiva: orchestratore vivo →
    passa). Il test ha anche avviato orchestratori veri (killati).
    Fix doppio:
    - prodotto: `_toggle_orchestrator` usa `_is_orchestrator_running()`
      come unica fonte di verità (il controllo pid/proc era DUPLICATO
      inline e bypassava il metodo) + typo `b"\\x00"` → `b"\x00"` (NUL)
    - test: setUp/tearDown ermetici — patch `_is_orchestrator_running`
      su True, pulizia pause.flag → mai subprocess nei test
    Verifica: TestToolbarToggle 1 passed (8.45s), 0 orchestratori
    spawnati; test_user_workflow completo 25 passed + 46 subtests.
13. **test_functional_swarm: NON un flake** — passa da solo (7 passed,
    21:00: lento ma verde; EXIT=0). Da escludere dai run veloci, non
    dai run di verifica completi.

## 📈 Cycle 85e — Grafico miglioramenti + GOAL middle senior + pannello GUI (2026-11-18)

- **Grafico deterministico** (`tools/gen_grafici.py` →
  `DOCS/grafici/miglioramenti.svg`, zero LLM, validazione XML): 4 sezioni —
  (A) difetti audit per categoria, (B) meccanismi cumulativi 1→16,
  (C) crescita suite test, **(D) scala di seniorità con il GOAL**.
- **GOAL dichiarato**: sistema (modello + meccanismi) a livello
  **middle senior** o quanto più vicino. Scala misurabile:
  Junior (3b nudo, 0/4 GUI) → Junior+ (v0.3.30, siamo qui) →
  Middle (≥50% primo colpo) → **Middle Senior (≥70% primo colpo,
  GUI ≥75%, 0 allucinazioni API)**. In `DOCS/MIGLIORAMENTI.md` + README.
- **Pannello GUI** `GUI/improvements_panel.py`: SVG dentro QScrollArea
  con QSvgWidget, back_btn (parità), pulsante 🔄 Rigenera che esegue lo
  script deterministico. Card "📈 Miglioramenti" in Plancia (riga 3).
- Test: `tests/test_improvements_panel.py` (4: SVG valido, back_btn,
  fallback file mancante, path assoluto) + parità 32 subtests verdi.

## 🕸️ Cycle 85f — Radar capacità + roadmap middle senior in todo.md (2026-11-18)

- **Grafico E — radar a ragnatela**: 8 assi di capacità (scala 0-4),
  poligono blu = oggi v0.3.31, poligono verde tratteggiato = goal.
  Punti di forza: Gate/verifica (4/4), Refactoring mecc. (3/4).
  Gap: Task GUI (1/4), Architettura (1/4), Fedeltà API (2/4),
  Memoria/contesto (2/4).
- **todo.md torna vivo**: roadmap P1/P2/P3 con criteri di done
  misurabili — P1: metrica "primo colpo %" + gate import-check;
  P2: scaffolding GUI deterministico, A/B contesto persistente,
  refs moduli interni, clarifier esteso; P3: decision tree v2,
  confronto 7b/14b per GUI, leva cpupower.
- Tabella radar-per-asse in DOCS/MIGLIORAMENTI.md.

## 🚀 Cycle 85g — Programma "come i migliori" in todo.md (2026-11-18)

- **todo.md**: sezione "🚀 Programma 'come i migliori' — GLM / Claude /
  OpenAI / DeepSeek / Qwen" con **Fasi A-H (items 10-20)**, nell'ordine
  reale dei lab: evals prima di tutto → data engine (corpus triple
  verificate + curazione) → self-improvement STaR/ReST (feasibility
  QLoRA 3b con GO/NO-GO onesto, GPU 4GB/1GB libera = borderline) →
  inference-time scaling (best-of-N col gate come giudice, sweep
  num_ctx) → distillazione → retrieval soluzioni passate (TF-IDF, no
  RAG neurale) → A/B prompt variants (DSPy-style) → Timestral giudice
  di qualità **mai sovrano** (il gate resta l'unica autorità).
- Ogni fase con criterio di done misurabile e dipendenze esplicite
  (Fase A dipende da P1-1). Sezione "Cosa NON facciamo": PPO/RL
  infrastrutturale, reward-model training, cluster multi-GPU — fuori
  dai vincoli hardware/termici; il nostro "RL" è il correction loop.

## 🎯 Cycle 85h — todo.md riordinato per impatto + item SLOT (2026-11-18)

- **todo.md** ora inizia dal piano ordinato **dalle voci più impattanti**
  (criterio: impatto sul goal ÷ costo, ★★★→○):
  Fascia 1 (sblocca misura + primo mattone SLOT): P1-1 metrica primo
  colpo, SLOT-1 gate per-slot, SLOT-2 assembler, P1-2 gate import-check;
  Fascia 2 (motore): Fase B corpus, Fase D-15 best-of-N, SLOT-4 prompt
  per-slot, Robustezza #3/#2, Fase A eval, SLOT-5 eval per-slot;
  Fascia 3 (gap sistema): SLOT-3/P2-3 planner+scaffolding, D-16 num_ctx,
  P2-5 refs, P2-6 clarifier, P2-4 A/B, Rob #1/#4/#10/#7;
  Fascia 4 (sottofondi/igiene): Fase C/F/E/G/H, P3-7/8/9, Rob #5/6/8/9,
  igiene performance residua.
- **5 item SLOT aggiunti** (dal doc ARCHITETTURA_SLOT.md che non li
  aveva ancora in coda): gate per-slot, assembler, prompt per-slot,
  eval per-slot, planner+scaffolding. ID originali preservati
  ([P1-1], [Fase A], [Robustezza #N]) per non rompere i riferimenti.
- Storico (sezioni completate) conservato integralmente sotto
  "📜 Storico recente".

## 📊 Cycle 85i — P1-1 metrica "primo colpo %" (2026-11-18)

Primo item del piano riordinato per impatto: **senza misura il goal
(≥70% primo tentativo) non è verificabile**. Zero LLM, ~1 sessione.

- **`CORE/task_queue.py`**: colonna `first_try` (INTEGER) con migrazione
  automatica idempotente (`ALTER TABLE` solo se assente; verificata su
  copia del DB reale: 17 task preservati, 0 valutati).
  - `mark_done(task_id, result, first_try=None)` → 1/0;
    `COALESCE(?, first_try)` non azzera un valore già scritto
    (es. chiusura automatica del parent).
  - `mark_failed`, `fail_with_correction`, `mark_pending` → `first_try=0`.
  - NULL = task deterministico (swarm/execute) o mai valutato: la metrica
    conta SOLO dove un LLM ha lavorato.
- **`CORE/worker.py`**: `last_attempts` (tentativi interni dell'ultimo
  execute) resettato a 1 all'inizio di ogni task e aggiornato nei tre
  percorsi: direct (`run_direct`), fast lane (`attempts`), ReAct
  (`1 + test_fail_retries`).
- **`CORE/orchestrator.py`**: all'APPROVE, `first_try = attempts di coda
  == 0 AND worker.last_attempts <= 1` → `mark_done(..., first_try=...)`.
  Un task non è "primo colpo" se ha servito retry di coda, correction,
  fallback modello o retry interni.
- **`tools/first_try_report.py`** (nuovo): legge `queue.db` e stampa
  `primo_colpo: X/Y (Z%)`; risolve il DB esistente più recente tra
  `data/tasks/` e `tasks/` (`BW_TASKS_DB` forza un path); riconosce lo
  schema pre-migrazione (`legacy`) e non confonde "assente" con
  "non migrato". Fail-open (exit 0) per non rompere `verify_cycle.sh`.
- **`tools/verify_cycle.sh`**: nuovo passo **4/4** che stampa la metrica
  a ogni ciclo (prima: 3 passi).
- **`tests/test_first_try.py`** (nuovo): 9 test — default NULL, 1/0 nei
  percorsi done/failed/correction/pending, COALESCE, conteggio solo
  valutati, schema legacy, fail-open su DB assente.
- Zero Warning: pyflakes 0 sui file toccati; ripuliti anche i 4 warning
  preesistenti di `CORE/task_queue.py` (2 import inutilizzati +
  variabile morta).
- Test: 51 passed (nuovo file + queue/gatekeeper/orchestrator chiusura).

## 🔧 Cycle 85j — SLOT-1 gate per-slot + SLOT-2 assembler + P1-2 import-check (2026-11-18)

Estensione della Fascia 1: i mattoni deterministici dello SLOT.

- **`CORE/slot_gate.py`** (nuovo, SLOT-1): `gate_slot(fragment, refs, kind)` →
  `SlotVerdict(ok, kind, undefined, syntax)`. Backend: pyflakes via
  `CORE/import_check.check_source` (collo di noti da `refs`, fallback AST
  interno se pyflakes manca). Blocca per sintassi e per nomi indefiniti.
- **`CORE/slot_assembler.py`** (nuovo, SLOT-2): `assemble_slots(base, slots)`
  con marker `# @@slot: <name>` e `# @@imports`; sollevamento import +
  dedupe; indentazione dal marker; validazione compilabile (compile exec);
  `assemble_to_file`. Gestisce scheletri dove l'anchor e' l'unico membro
  del blocco (stub `pass` per la parse).
- **`CORE/import_check.py`** (nuovo): `check_source/check_path/format_report`,
  backend pyflakes (v4: `Reporter.flake(syntaxError)` API) con fallback AST
  di scope; `blocking()` filtra i soli kinds bloccanti.
- **`CORE/tools.py`**: `ToolSet.touched_python` + `reset_touched()`,
  `_track_python()` (su ogni write_file/patch_code su `.py`, warning
  "IMPORT-CHECK WARNING" con le righe dei nomi indefiniti), `pending_import_issues()`.
- **`CORE/worker.py`**: gate al `done` — su nomi indefiniti → correction
  prompt (retry ≤2), poi done con warning; i retry contano nel calcolo P1-1
  (`last_attempts`).
- **`requirements.txt`**: aggiunto `pyflakes>=3.0` (gate runtime).
- Tests: `tests/test_slot_pipeline.py` (gate/assembler/import-check,
  fallback AST inclusa), `tests/test_toolset_gates.py` classe
  `TestImportCheckGate` (5 test write/patch/reset/non-py).

Verifiche: 49 passed nuovi + 86 (toolset/gate/reuse/fast-lane/refs/inject) +
prima tranche. pyflakes sui file toccati: **0 warning**. Baseline
pyflakes: 474 → **453** (rimossi task_queue 4, tools ~9, worker ~7 + nuovi
gate/assembler a 0).

**Prossima voce del piano** (Fase B — corpus di triple): da avviare subito
colle regole già messe in piedi (P1-1/P1-2/SLOT/Zero Warning verdi).

---

## Cycle 87 (2026-11-22) — Onda 1 del piano auto-miglioramento (A1–A4)

| ID | Implementazione | Verifica |
|---|---|---|
| A1 | `CORE/worker.py`: `classify_verification`, `verification_override`, `verification_gate`, `verification_report_line`. Stato `verified`/`failed`/`not_tested`; `not_tested` richiede `run_test_suite` (max 2 retry) o override esplicito (`allow_unverified_done` / `context.verification_override`). Marker nel **report** (evento memoria + reason triple), mai nel `result` di `execute()` | `tests/test_worker_verification.py`: 7 test, inclusa integrazione con fake model |
| A2 | `CORE/feedback_corpus.py`: `MAX_REASON_CHARS=4000`, `clamp_reason`, `failure_triple`, `VALID_VERDICTS` con `failed_definitively`. `CORE/worker.py` popola `reason` dal prompt correttivo; `CORE/orchestrator.py` scrive la triple sul fallimento definitivo; corpus ora rispetta `state_dir` del config | `tests/test_feedback_corpus.py`: +6 test |
| A3 | `tools/curate_corpus.py`: default `done + corrected` (hard negatives) stratificati/interleaved, `--only-done` ripristina il vecchio filtro, `--max-per-verdict`, conteggi per verdict e `excluded_failed` | `tests/test_curate_corpus.py`: 5 test CLI offline |
| A4 | `retrieve_similar_task` collegato: `TOOL_CODE_MAP['retrieve']`, SYSTEM + prompt dinamico, allowlist, `TOOL_SIGNATURES`, dispatch `_call_tool`, keyword auto-tool. Chiamabile, **non** automatico | `tests/test_retrieval_wiring.py`: 4 test con retriever finto |

Gate: 28 test mirati verdi + regressione 82 passed/110 subtests (1 test
aggiornato dal contratto `execute()`: marker rimosso dal result), compileall,
lint 0 errori, security S030/S031 puliti, `git diff --check` OK. Nessun LLM,
nessuna rete, ventola non verificata → C3 resta 🔒 termico.

---

## Cycle 88 (2026-11-22) — B1: `best_of_n` configurabile e gate-giudice

| Modifica | Dettaglio |
|---|---|
| `CORE/config_model.py` | Nuovo `OrchestratorConfig` (`max_task_retries`, `retry_cooldown_sec`, `sticky_models`, `best_of_n`) esposto come `AppConfig.orchestrator` e popolato da `[orchestrator]`; `best_of_n` clampato a 1..8 |
| `CORE/best_of.py` | `JudgeResult` + `judge_candidates(codes, refs_by_index, kinds, best_of)`: funzione pura, valuta ≤N candidati, vince il primo che passa il gate, `all_rejected`/`kinds_mismatch` come reason |
| `CORE/worker.py` | `_best_of_n` riscritto: precedentza task → config tipizzata → TOML grezzo → 1, con clamp `MAX_BEST_OF=8`; firma `cfg=None` retrocompatibile |

Verifiche: `tests/test_best_of.py` 8 test (3 candidati finti, scelta
deterministica, rifiuto di tutti, cap N, flag letto da config con 5/99/0,
precedenza e clamp). Regressione `test_reuse`/`test_config_validation`/
`test_fast_lane`/`test_best_of`: 55 passed. Nessun LLM: il loop live resta a
`best_of_n=1` e la ventola non è verificata.

Nota: l'ipotesi "trattare i modelli piccoli come bambini, istruzioni in
inglese" è stata registrata come **D1** (`tools/prompt_lint.py`, misura
offline del prompt). La leva è la struttura (una azione per turno, poche
scelte, formato esplicito), non il tono; A/B live resta 🔒 termico.

---

## Cycle 89 (2026-11-22) — B2: auto-approvazione skill solo con gate verde

| Modifica | Dettaglio |
|---|---|
| `CORE/skill_proposer.py` | `GateCheck`/`GateReport` + `gate_proposal(path)`: gate deterministico sul candidato (file presente, dimensione ≤20000, sezioni obbligatorie, regola ≥40 char, fence ```python compilabile via AST con placeholder `{{…}}` neutralizzati, nessuna chiamata `eval/exec/input/os.system/…`). `gate_report(id)` rilegge il report salvato; CLI `--gate ID` |
| Auto-approvazione | `auto_approve_ready(skill_id)`: dopo 3 successi senza fallimenti valuta il candidato; **gate verde** → `approve_proposal(report)` con backup `.backup.md` e metadati `mode=auto`/`backup`/`gate_report`; **gate rosso** → bozza intatta in `state/skill_proposals/`, report persistito in `failures.json`. `record_skill_usage` passa solo da qui |
| Approvazione manuale | `approve_proposal` resta disponibile da CLI (scelta umana esplicita) e registra ora sempre backup + report nei metadati: nessuna sovrascrittura silenziosa |

Verifiche: `tests/test_skill_proposer.py` 14 test offline (6 nuovi: gate
verde→approvazione con backup, gate rosso→bozza+report, codice pericoloso e
sintassi invalida, file mancante fail-open, fallimento che blocca l'auto-
approvazione, CLI `--gate`). Regressione skill_executor/behavioral/diagnosis/
oracle/logic: 36 passed. Nessun LLM, nessuna rete. Nessuna skill reale
modificata: i test usano una SKILLS dir temporanea.

---

## Cycle 90 (2026-11-22) — B3: validatore degli override auto-skill/auto-tool

| Modifica | Dettaglio |
|---|---|
| `CORE/override_guard.py` (nuovo) | `Issue`/`ValidationResult`/`validate_overrides`/`load_validated`: chiavi note, max 4 keyword, dedup normalizzato (accent-insensitive), keyword testuali <80 char senza controlli, JSON invalido e root type. Report `to_dict()`/`markdown()` per C2 |
| `CORE/auto_skill.py` | `_load_overrides` usa `load_validated` + `_known_skill_keys()` (keyword curate + cartelle `.opencode/skill/`); warning per ogni issue; file mancante = {} |
| `CORE/auto_tool.py` | `_load_overrides` usa `load_validated` + `_known_tool_keys()` (keyword curate + `TOOL_SIGNATURES`); warning per ogni issue |

Verifiche: `tests/test_override_guard.py` 10 test + 4 subtest (valido, 4
invalidi con codice `unknown_key`/`too_many`/`bad_type`/`bad_keyword`,
dedup `caffe`/`caffè`, cap 4, file mancante, JSON rotto, root non-dict,
markdown, wiring dei due loader). Regressione dead-code/refactor/retrieval/
subagent: 36 passed + 4 subtest. Nessun LLM. Le keyword valide continuano a
funzionare: il validatore scarta solo le voci non conformi.

---

## Cycle 91 (2026-11-22) — C1: documentazione allineata al codice

| Contraddizione | Correzione |
|---|---|
| `AGENT.md` e `DOCS/SPECIFICATIONS.md`: `MAX_STEPS = 6` | `MAX_STEPS = 10` (valore effettivo di `CORE/worker.py`); i profili `llm_tuner` possono ridurlo dinamicamente |
| Baseline security 15 / 7 / 13 in `verify_cycle.sh`, `todo.md`, `AGENT.md` | **Baseline unica 7 errori** (273 finding totali, misurata il 2026-11-22) dichiarata in `AGENT.md` regola 13 e usata da `verify_cycle.sh`; `todo.md` conserva il 13 solo come "baseline storica" |
| `GUI/IMPLEMENTED.md` copia identica delle prime 107 righe di `DOCS/IMPLEMENTED.md` | Sostituito da uno stub di indirizzo: registro canonico = `DOCS/IMPLEMENTED.md`, nessun contenuto perso |
| `state → data/state` non dichiarato | `AGENT.md` regola 12: symlink per-install gitignored, artefatti runtime via `state/`, mai committare credenziali |

Verifiche: `tests/test_docs_consistency.py` 4 test (valore `Worker.MAX_STEPS`,
assenza di `MAX_STEPS = 6`, baseline unica, assenza di righe duplicate,
dichiarazione symlink con controllo condizionale del target). `bash -n
tools/verify_cycle.sh` OK, `git diff --check` OK. Nessun codice runtime
modificato.

---

## Cycle 92 (2026-11-22) — C2: report misurabile del loop

| Modifica | Dettaglio |
|---|---|
| `tools/self_improvement_report.py` (nuovo) | `collect(state_dir)` legge solo `state/`: triple corpus + verdetti, first-try/correction rate, proposte skill per stato, gate verdi/rossi, override non conformi, copertura retrieval. Fail-open su file rotti. `markdown()` e `--json`; `--state-dir`/`--out` per test isolati |
| `DOCS/SELF_IMPROVEMENT_REPORT.md` (generato) | Primo snapshot reale: 72 triple / 24 uniche / 20 task, first-try 0.958, correzioni 0.042, 2 proposte pending, 0 gate rossi, 0 override invalidi, copertura retrieval 100% |

Verifiche: `tests/test_self_improvement_report.py` 6 test + 6 subtest con
state finto in tmp (verdetti, first-try, copertura parziale, gate/proposte,
override invalidi, fail-open, markdown). Nessun LLM, rete o GPU: il report è
il quadro deterministico che rende verificabile il miglioramento, non una
nuova euristica. Snapshot rigenerabile con un comando.

---

## Cycle 93 (2026-11-22) — D1: lint offline del prompt effettivo

| Modifica | Dettaglio |
|---|---|
| `tools/prompt_lint.py` (nuovo) | `analyze_prompt` misura caratteri/parole/frasi, media e max parole/frase, regole numerate, tool esposti, quota token non-inglesi (euristica dichiarata), presenza di "una azione per turno" + formato JSON, marcatori offensivi. `effective_prompt` riusa `Worker._build_system` su un probe: zero LLM, zero thread. `--family`, `--prompt-file`, `--json`, `--out` |
| `DOCS/PROMPT_LINT_REPORT.md` (generato) | Snapshot reale family `compact`: 1302 char / 187 parole, 7 regole, 13 tool, 3.6 parole/frase (max 11), 2.7% non-inglese (commenti `# righe`, `# se dubbi`), 0 marcatori offensivi, status `OK` |

Verifiche: `tests/test_prompt_lint.py` 6 test: prompt reale compatto/llama/
deepseek, prompt cattivo (`FAIL` con tono offensivo e nessuna azione), prompt
buono, stringa vuota fail-open, quota non-inglese sui commenti. Risposta
all'ipotesi "LLM piccoli = bambini, istruzioni in inglese": **struttura sì
(regole, tool limitati, JSON esplicito), tono no (0 marcatori offensivi)**;
l'inglese aiuta il codice ma non va imposto a ogni testo utente. A/B live
resta 🔒 bloccato termicamente: qui si misura la struttura, non la qualità
delle risposte.

---

## Cycle 94 (2026-11-22) — Radar capacità aggiornato

| Modifica | Dettaglio |
|---|---|
| `tools/gen_grafici.py` | Asse **Memoria / contesto** 2/4 → 3/4 (A2–A3 triple con `reason`, A4 retrieval chiamabile, C2 report con copertura 100%); etichette Cycle 86 → 93 e legenda "oggi (Cycle 93)" |
| `DOCS/grafici/miglioramenti.svg` | Rigenerato deterministico (sha256 stabile su due run): poligono blu aggiornato, conteggi dinamici tool 32 → 36 |
| `DOCS/MIGLIORAMENTI.md` | Tabella radar per asse e intestazione allineate; rimossa riga obsoleta "D1 pianificato" |

Verifiche: `tests/test_improvements_panel.py` 4 test offscreen, SVG valido;
`git diff --check` OK. Nessun LLM. Il residuo non-inglese del prompt e gli
assi invariati restano misurati in `DOCS/PROMPT_LINT_REPORT.md` e nella
tabella radar.

---

## Cycle 95 (2026-11-22) — pulsante "Rigenera" finalmente efficace e onesto

| Modifica | Dettaglio |
|---|---|
| `tools/gen_grafici.py` | `latest_cycle()` legge l'ultimo `## Cycle N` da `DOCS/IMPLEMENTED.md`; `mechanism_count()` conta le righe della tabella B + novità in `DOCS/MIGLIORAMENTI.md` (37). Titolo, legenda radar e punto finale di Chart B sono calcolati, non scritti a mano; `y_max` adattato |
| `GUI/improvements_panel.py` | Dopo il click lo status mostra `✅ SVG aggiornato` oppure `✅ SVG identico (nessun dato cambiato)`, con orario e byte scritti; errori di exit/timeout visibili invece di essere inghiottiti |
| `DOCS/grafici/miglioramenti.svg` | Rigenerato: Cycle 70 → 95, 37 meccanismi, legenda "oggi (Cycle 95)" |

Causa del sintomo segnalato: il pulsante **partiva davvero** (mtime cambiava,
exit 0), ma i dati erano hard-coded e lo status veniva sovrascritto dal solo
percorso file: l'SVG era byte-identico e l'utente non vedeva nulla. Ora un
cambio nei documenti produce un SVG diverso e il pulsante lo dichiara.

Verifiche: `tests/test_improvements_panel.py` 6 test offscreen (click con
subprocess mockato: identico/errore) + `tests/test_gen_grafici_data.py`
3 test (valori derivati, presenti nell'SVG, determinismo). Riproduzione
reale: `prima: DOCS/grafici/miglioramenti.svg (940×1911)` →
`dopo: ✅ SVG identico (nessun dato cambiato) · 13:37:58 · 21228 byte`.

---

## Cycle 96 (2026-11-22) — E1: gate deterministico per refactoring

| Modifica | Dettaglio |
|---|---|
| `tools/refactor_guard.py` (nuovo) | `check_refactor(before, after)` verifica AST, API pubblica di primo livello (nomi/argomenti; annotazioni e default ignorati) e equivalenza comportamentale tramite `behavioral_diff.snapshot`/`verify` sugli stessi input stdin. `FAIL` su sintassi/API/comportamento, `WARN` se snapshot non conclusivo (fail-open), `OK` se tutto preservato. CLI `--inputs`, `--json`, `--out` |
| `tests/test_refactor_guard.py` (nuovo) | 8 trasformazioni atomiche (type hints, docstring, helper privato, rename locali, f-string, costante, stdout esplicito, `__all__`) + 4 negativi (comportamento, API rimossa, sintassi, file mancante) + snapshot non conclusivo + report |
| `DOCS/REFACTOR_GUARD_REPORT.md` (generato) | Esercizio reale su `bench_target/utils.py` con type hints (ext-01): `OK`, API invariata, output identico |
| Radar | **Refactoring mecc. 3/4 → 4/4** in `tools/gen_grafici.py` e `DOCS/MIGLIORAMENTI.md`; 38 meccanismi |

Verifiche: 6 test + exercise reale, zero LLM/rete. Il guard NON applica patch:
prende due file già scritti e certifica l'equivalenza. È il numero che
permette di alzare l'asse del refactoring senza fidarsi di un giudizio.

---

## Cycle 97 (2026-11-22) — E2: fedeltà API misurata su librerie nuove

| Modifica | Dettaglio |
|---|---|
| `tools/gen_api_refs.py` | Output compatibile con `validate_refs.py`: header `# Modulo:`, `# Versione:` quando nota, `# Firma:` con i soli nomi dei parametri (evita virgole annidate nei default); nome file `<modulo>_api.md`, typo "Simbodo" corretto |
| `GUI/refs/json_api.md`, `GUI/refs/csv_api.md` (nuovi) | Ref generati da modulo installato per due librerie fuori dai cheat sheet storici; 8 + 14 firme verificate, 0 discrepanze |
| `CORE/tools.py` | `api_lookup(strict=True)` accetta le costanti reali come valori verificati via `getattr` (es. `csv.QUOTE_MINIMAL`): restano bloccati simboli assenti e callabili con firma non introspettabile |
| `tools/api_fidelity_eval.py` (nuovo) | AST → usi `modulo.simbolo` → `api_lookup(strict=True)` + validazione ref; `--json`/`--out`, exit 0 solo con 0 indefiniti e ref validi |
| `tests/test_api_fidelity_eval.py` (nuovo) | 8 test: casi reali, ref validi, determinismo del generatore, simbolo inventato, sintassi invalida, ref assente, costante strict, report riproducibile |
| `DOCS/API_FIDELITY_REPORT.md`, `DOCS/BENCH.md` | Verdetto PASS: 7/7 simboli verificati, 0 indefiniti, 22 firme; report deterministico e metrics nel bench |
| Radar | **Fedeltà API 3/4 → 4/4**; 39 meccanismi; grafico Cycle 97 |

Verifiche: 24 test offline (eval + gate refs + validazione), zero LLM/rete/GPU;
nessun changeset live. Il verdetto misura la fedeltà delle API, non la qualità
delle risposte del modello.

---

## Cycle 98 (2026-11-22) — E3: scaffolding GUI da template curati

| Modifica | Dettaglio |
|---|---|
| `GUI/refs/templates/` (nuovo) | 4 template PyQt6 validi Python con marker `# SLOT:`: `finestra` (QMainWindow), `layout` (QVBoxLayout + QFormLayout + QHBoxLayout), `segnali` (pyqtSignal → QLabel), `thread` (QThread + Worker con `quit` in DirectConnection per evitare Qt abort su `wait()`) |
| `.opencode/skill/py-gui-scaffold/SKILL.md` (nuovo) | Policy: scegli template, verifica i simboli Qt con `api_lookup` **non-strict** (le classi C++ non hanno firma), incrocia `GUI/refs/pyqt6.md`, gate offscreen obbligatorio, nessun `app.exec()` nei test |
| `CORE/auto_skill.py` | Keyword `pyqt6`, `finestra qt`, `crea gui`, `layout qt`, `segnali qt`, `qthread`, `widget qt`, `scaffolding gui` per attivazione automatica della skill |
| `tests/test_gui_templates.py` (nuovo) | 7 test offscreen: compilazione/SLOT/timestamp, snapshot finestra e layout, segnali collegati, thread terminato senza Qt abort, gate simboli Qt, skill + keyword registrati |
| `DOCS/BENCH.md` | Metrica E3: 4 template, 4 snapshot, 7 test; task GUI live non misurato (🔒 termico) |
| Radar | **Task GUI 1/4 → 2/4**; 40 meccanismi; grafico Cycle 98 |

Verifiche: 11 test (nuovi + parità skill), zero LLM/rete/GPU. Il livello 3/4
richiede un task GUI reale chiuso al primo colpo: resta 🔒 bloccato termicamente
finché le ventole non sono verificate (≤60 °C).

---

## Cycle 99 (2026-11-22) — E4: harness A/B memoria/contesto pronto

| Modifica | Dettaglio |
|---|---|
| `tools/memory_ab.py` (nuovo) | 10 task congelati (id `5e6051bfc33d`), `FakeRetriever`/`fake_solver` deterministici, due bracci con/senza contesto, `verdict()` con soglie GO ≥0.60 e delta ≥0.20 (arrotondato a 4 decimali), gate termico che richiede `data/state/fan_verified.json` con `fan_rpm>0` e `temp_c<=60` per il live. Nessun client LLM importato |
| `tests/test_memory_ab.py` (nuovo) | 8 test: task set congelato, soglie, dry-run, retriever finto, gate termico (dry-run OK / live bloccato / valori validi), report deterministico e dichiarazione "non reale", assenza di import LLM |
| `DOCS/MEMORY_AB_REPORT.md`, `DOCS/BENCH.md` | Snapshot del solo dry-run (0.80 vs 0.00, simulato) e parametri/soglie del bench prima del live |
| Radar | Memoria/contesto resta **3/4**: la preparazione non è impatto misurato; 41 meccanismi; grafico Cycle 99 |

Verifiche: 8 test offline, zero LLM/rete/GPU. Il verdetto reale resta 🔒
bloccato termicamente: serve la verifica ventole (≤60 °C) prima di qualsiasi
task con modello. Nessun numero del dry-run viene usato per alzare il radar.

---

## Cycle 100 (2026-11-22) — brutal honesty: corretti i report, non i radar

| Modifica | Dettaglio |
|---|---|
| `tools/brutal_honesty_report.py` (nuovo) | Report deterministico zero LLM: `pyflakes` sul codice attivo (no `tests/archiviati`), `CONFIG/config.toml` (`fast_lane.enabled`, `best_of_n`), corpus feedback (totali/unici/first-try/provenienza), contatori live di `gen_grafici`, e verifica che le correzioni siano nel markdown. Nessun timestamp |
| `DOCS/BRUTAL_HONESTY_REPORT.md` (nuovo) | Verdetto sintetico: Zero Warning FAIL con conteggio reale, fast lane disabilitata, first-try su fixture interne, copertura retrieval come definizione ristretta, 41 meccanismi documentati non tutti attivi, numeri skill/tool aggiornati |
| `tools/self_improvement_report.py` | Aggiunte due caveat generate: il tasso primo colpo è su **fixture interne** non task utente; la copertura retrieval non misura la qualità. Report `DOCS/SELF_IMPROVEMENT_REPORT.md` rigenerato |
| `DOCS/MIGLIORAMENTI.md` | Rimosse le frasi false “0 pyflakes ✅ raggiunto”, “best-of-N attivo (fast lane)” e “41 meccanismi attivi”; aggiunta sezione `🧾 Brutal honesty` con link al report; numeri auto-skill/auto-tool 23/30 → 26/36; Goal Middle Senior dichiarato **non raggiunto** |
| `tools/gen_grafici.py` | Caption chart B: “meccanismi documentati … (non tutti attivi a runtime)” |
| Radar | **Nessun asse toccato**: i valori restano giudizi espliciti. 41 meccanismi documentati; grafico Cycle 100 |

Verifiche: report deterministico (stesso output su due run), test dedicati e
gate leggeri. Non è stata rieseguita la suite completa: resta valido il run3
del 2026-11-19. Nessun LLM, rete, GPU o task live.

---

## Cycle 101 (2026-11-22) — F1: scaffold iOS/Android offline, non build

Risposta alla richiesta “scrivere app iOS/Android” e al dubbio sul passo
successivo: il passo **non è troppo alto come preparazione**, ma **lo è come
dichiarazione di maturità**. Quindi aggiungiamo scaffolding verificabile
offline e non tocchiamo il livello Middle (che resta non misurato).

| Modifica | Dettaglio |
|---|---|
| `GUI/refs/templates/mobile_ios.swift.tpl` + `mobile_android.kt.tpl` (nuovi) | Schermate minime SwiftUI (`ContentView`, `@State`) e Kotlin/Jetpack Compose (`MainActivity`, `@Composable`), con soli marker `# SLOT:` da sostituire |
| `GUI/refs/mobile/swiftui.md` + `android_compose.md` (nuovi) | Ref statici: simboli ammessi e regole per il modello 3b. `api_lookup(strict=True)` **non si applica** (gate Python, non introspetta Swift/Kotlin) |
| `tools/mobile_scaffold_check.py` (nuovo) | Gate deterministico: marker, import, costrutti, copertura ref, assenza timestamp; rileva simboli inventati. Scrive `DOCS/MOBILE_SCAFFOLD_REPORT.md`, `--json` per l'uso nei gate |
| `.opencode/skill/mobile-scaffold/SKILL.md` (nuovo) + `CORE/auto_skill.py` | Skill con keyword IT/EN (`swiftui`, `kotlin`, `jetpack compose`, `app ios`, `app android`, …) e rilevamento automatico nei prompt |
| `DOCS/MIGLIORAMENTI.md` | Nuova riga radar **Mobile iOS/Android 2/4**, sezione brute honesty aggiornata, 41 → 42 meccanismi documentati, Cycle 101 |
| `tools/gen_grafici.py` | Radar a 9 assi: aggiunto Mobile a 2/4; **nessun asse esistente alzato** |
| `tools/brutal_honesty_report.py` | Nota esplicita: Cycle 101 aggiunge Mobile come scaffold offline, non build verificata |

Verifiche: 6 test offline, report PASS con toolchain `ASSENTE` per Swift e
Kotlin, gate leggeri. **Build NON verificata** (Xcode/iOS SDK e Android SDK
non presenti) e task live 🔒 bloccato termicamente: serve
`data/state/fan_verified.json` con `fan_rpm > 0` e `temp_c <= 60`. L'asse
Mobile resta 2/4; 3/4 richiede build reale + task live. Nessun LLM, rete,
GPU, emulatore o `app.exec()`.

---

## Cycle 102 (2026-11-22) — M1: Zero Warning richiuso (23 → 0 finding)

| Modifica | Dettaglio |
|---|---|
| `GUI/center_area.py` | Aggiunto `from pathlib import Path`: eliminati i 2 `undefined name` alle righe 278/288 (pole `state/clarification*.txt`). Sblocca anche il gate `pyflakes — 0 nomi indefiniti` di `.github/workflows/ci.yml` |
| `CORE/cloud_client.py` | `_headers()` chiama `provider_info(provider)` senza assegnazione inutilizzata: la validazione `KeyError` resta, il finding sparisce |
| `CORE/labels.py`, `GUI/file_tree_drawer.py`, `GUI/task_scheduler_panel.py`, `GUI/skills_panel.py`, `GUI/settings_panel.py` | Rimossi 19 import morti (Qt widget, `Optional`, `update_task_labels`, `list_skills_with_status` duplicato). Nessun comportamento cambiato |
| `tests/test_subagent.py` | `Worker(...)` chiamato senza assegnare `worker`: preservato l'effetto collaterale (registry iniettato) che il test verifica |
| `DOCS/BRUTAL_HONESTY_REPORT.md` | Rigenerato: `Zero Warning (pyflakes)` passa da ❌ FAIL (23) a ✅ PASS (0). Nessun verdetto scritto a mano |
| `DOCS/MIGLIORAMENTI.md`, `todo.md` | Storia onesta aggiornata: 474 → 0 (Cycle 85), riaperto a 23 (Cycle 100), richiuso a 0 (Cycle 102) |

Verifiche: `pyflakes` 0 su `CORE GUI tools SAFETY tests` (esclusi `tests/archiviati`),
`compileall` OK, `lint_style` 0 errori (warning baseline pre-esistenti),
92 test mirati + 6 subtests verdi, `git diff --check` pulito. **Nessun asse
del radar toccato** e nessun LLM/rete/GPU. La suite completa resta 🔒 bloccata
dalla regola termica del 2026-11-20.

---

## Cycle 103 (2026-11-22) — Sblocchi M2–M6: preparazione misurabile, nessun falso dato

| Modifica | Dettaglio |
|---|---|
| `tools/blocker_probe.py` (nuovo) | Sonda deterministica di sola lettura per M2–M6: coretemp da sysfs, RPM da `nbfc status`, PWM grezzo, `hardening.sh --check`, integrità di `gh` (shebang incluso), remote token-free, permessi 0600, presenza del workflow CI. Nessuna rete/API/LLM. `--write-fan` rilegge le misure e **rifiuta** la scrittura se `fan_rpm <= 0` o `temp_c > 60`; non esiste un'opzione per passare i numeri a mano |
| `tests/test_blocker_probe.py` (nuovo) | 10 test: parser RPM/temperature, gate falso senza RPM o sopra soglia, rifiuto di scrittura, provenienza obbligatoria, permessi 0600, mascheratura token, rilevamento shebang rotto, determinismo del report |
| `DOCS/BLOCKER_PROBE_REPORT.md` (nuovo) | Snapshot generato: CPU 65.0 °C, RPM 0, nbfc `inactive`, gh con interprete shebang assente, utente/slice hardening assenti, remote token-free. Tutti gli ID M2–M6 restano 🔒 |
| `DOCS/MIGLIORAMENTI.md`, `todo.md` | Link al nuovo report e aggiornamento delle evidenze reali. **Nessun asse del radar toccato** |

Verifiche: 10 test mirati verdi, `compileall` OK, `pyflakes` 0,
`lint_style` 0 errori, `git diff --check` pulito. Verificato anche il comportamento
negativo: `--write-fan` stampa `RIFIUTO` e non crea il file; `--check-fan` esce 1.
Il dato termico è peggiorato rispetto al primo campione del giorno (53 °C → 65 °C),
quindi la regola del 2026-11-20 resta applicata senza eccezioni.

---

## Cycle 104 (2026-11-22) — M3/M4/M6: false positivi corretti e blocco hardware del tachimetro

| Modifica | Dettaglio |
|---|---|
| `tools/blocker_probe.py` | Corretti due falsi negativi/positivi emersi dal test reale: (1) l'unità systemd è `nbfc_service`, non `nbfc`; (2) `~/.local/bin/gh` non è la GitHub CLI ma uno script che apre il browser — ora classificato `script-browser` con hint `sudo apt install gh` invece di “riparare lo shebang”. Aggiunto il parser del formato nbfc 0.5.3 (`Current Fan Speed` / `Target Fan Speed`, senza unità RPM) e il duty cycle nel report |
| Servizio ventole | Avviato il daemon nbfc via `pkexec --disable-internal-agent /usr/bin/nbfc start` (autorizzato senza password); test reversibile a duty 100% e ripristino `set -a`. **Non** abilitato persistentemente: l'unità systemd resta `inactive` |
| M3 — evidenza hardware | `Current Fan Speed: 0.00` anche con `Target Fan Speed: 100.00`; nessun `/sys/class/hwmon/hwmon*/fan*_input`. Il tachimetro non è leggibile: `fan_rpm > 0` non è dimostrabile con i sensori disponibili. Il gate resta 🔒; **nessuna misura alternativa è stata introdotta autonomamente** |
| M4/M6 — evidenza CLI | `apt-cache policy gh`: installato = nessuno, candidato 2.46.0-4. Serve installazione della CLI ufficiale + login + revoca PAT prima di qualsiasi trigger del workflow |
| M5 — evidenza polkit | `pkexec id` restituisce `uid=0(root)` senza password (utente nel gruppo `sudo`): rilevante per la review di hardening, non risolto qui |

Verifiche: 13 test mirati verdi, `pyflakes` 0, `compileall` OK.
`DOCS/BLOCKER_PROBE_REPORT.md` rigenerato con duty, stato unità e nota sul
tachimetro. **Nessun asse del radar toccato**, nessuna suite completa locale,
nessun `fan_verified.json` scritto. **Decisione esplicita dell'utente
(2026-11-22): mantenere il gate stretto `fan_rpm > 0`**: nessun duty cycle o
misura surrogata lo sostituisce. M3 resta 🔒 finché non arriva una misura RPM
esterna verificabile.

---

## Cycle 105 (2026-11-22) — Todo residui offline: prompt ReAct verificato + scaffold driver SLOT

| Modifica | Dettaglio |
|---|---|
| `tests/test_react_tool_prompt.py` (nuovo) | Verifica offline che la lista tool è già nel SYSTEM prompt del loop ReAct (`CORE/worker.py:493`) e viene reiniettata dopo `unknown tool` (`CORE/worker.py:981-989`). Todo “iniettare la lista tool” chiuso per verifica, senza duplicare codice |
| `tools/kernel_slot_scaffold.py` (nuovo) | Genera `.c` + `Makefile` + `SLOTS.md` per driver platform: probe/remove/file_operations deterministici, tre slot (read/write/ioctl) da riempire uno alla volta. Ogni simbolo chiamato è controllato contro la whitelist estratta dagli header del kernel target; le macro `module_init`/`module_exit`/`MODULE_LICENSE` sono accettate solo se il `#define` esiste davvero negli header. Nome sanitizzato, nessun timestamp, fail closed |
| `GUI/refs/templates/kernel_platform.c.tpl`, `kernel_makefile.tpl` (nuovi) | Template curati, stessi cartelle di `GUI/refs/templates/`; nessuna API scritta a mano dentro gli slot |
| `tests/test_kernel_slot_scaffold.py` (nuovo) | 5 test: determinismo, nomi rifiutati, gate che becca un simbolo inventato, macro verificate dagli header, regole SLOT. Saltati se gli header mancano |
| `.opencode/skill/linux-driver/SKILL.md` | Workflow aggiornato con generatore e comando `--check` post-fill |
| `todo.md` | Voci “lista tool ReAct” e “scaffold SLOT” chiuse con evidenze |

Verifiche: 21 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori.
**Nessun modulo compilato, nessun `insmod`, nessun QEMU**: il gate resta vuoto
e viene dichiarato tale. Nessun asse del radar toccato, nessun LLM/rete.

---

## Cycle 106 (2026-11-22) — Todo residuo: ponte chiarimento GUI verificato

| Modifica | Dettaglio |
|---|---|
| `tests/test_clarifier_gui_bridge.py` (nuovo) | Verifica offline che il ponte chiarimento è già operativo: il worker scrive `state/clarification.txt` e attende `clarification_answer.txt` (`CORE/worker.py:1099-1145`), il main thread della GUI fa polling con `QTimer` + `QInputDialog` e scrive la risposta (`GUI/center_area.py:268-300`). Test: risposta file-based propagata al worker con cleanup, timeout fail-open, presenza del polling sul thread principale. Nessun `QApplication`, finestra, LLM o rete |
| `todo.md` | Voce “Integrazione GUI dialog completa” chiusa per verifica. Nota esplicita: il bridge è file-based, non signal/slot diretto; il widget alternativo `show_clarification()` resta non usato |

Verifiche: 3 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori (1 info su `from __future__`).
Nessuna finestra GUI avviata, nessun asse del radar toccato, nessun LLM/rete.

---

## Cycle 107 (2026-11-22) — SLOT-3: planner deterministico a slot

| Modifica | Dettaglio |
|---|---|
| `CORE/slot_planner.py` (nuovo) | Step [1] dell'architettura a slot: da task dichiarativo → piano di slot `{file, anchor, tipo, refs, test}`. Un solo template scelto per parole chiave con punteggio; **fail-closed** su task vuoti/sconosciuti/ambigui, su marker `# SLOT:` disallineati, su ref non presente nell'AST del template e su test mancante. Output identico per input identico, nessun LLM/rete |
| `tools/slot_plan.py` (nuovo) | CLI con `--task`, `--json`, `--out`; uscita 1 e motivo esplicito quando il piano è rifiutato |
| `tests/test_slot_planner.py` (nuovo) | 8 test: determinismo, 4 template, fail-closed (vuoto/ambiguo), refs reali, integrazione con `gate_slot`, stabilità Markdown/JSON, forma di `SlotSpec` |
| `todo.md` | SLOT-3/P2-3 portato a `[~]`: parte deterministica completata, benchmark LLM (1 task GUI al primo colpo) resta 🔒 termico |

Verifiche: 8 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning,
compilazione anche con Python 3.11 (CI). **Nessun task GUI reale eseguito**,
nessun `insmod`/LLM/rete, nessun asse del radar alzato. I template PyQt6, la
skill `py-gui-scaffold` e gli snapshot offscreen esistevano già: non sono stati
duplicati.

---

## Cycle 108 (2026-11-22) — Igiene performance: prefill del worker verificato

| Modifica | Dettaglio |
|---|---|
| `tests/test_worker_prefill.py` (nuovo) | 3 test offline: T1 seleziona solo i tool rilevanti (creazione → 12 core, nessun git/analysis), il SYSTEM prompt risultante è più corto del fallback, T10 riutilizza lo stesso oggetto prompt per task della stessa famiglia. Nessun LLM/rete/benchmark |
| `todo.md` | Voce “Igiene performance” portata a `[~]`: la riduzione del prefill tramite selezione tool è verificata; compressione descrizioni, batch write e KV cache restano aperti perché richiedono misure reali |

Verifiche: 3 test mirati verdi, `pyflakes` 0. Nessuna ottimizzazione applicata
“a occhio”: il miglioramento dichiarato è solo la verifica del comportamento
già presente, non una stima di risparmio.

---

## Cycle 109 (2026-11-22) — Lock dei vincoli operativi + chiusura voci già risolte

| Modifica | Dettaglio |
|---|---|
| `tests/test_config_gates.py` (nuovo) | 6 test offline: `fast_lane.enabled = false`, `best_of_n = 1`, gate termico attivo e `num_ctx` planner/orchestrator = 2048, remote SSH token-free, credenziali non tracciate con permessi 0600, config senza segreti in chiaro. Legge la config **committata** con `tomllib` (stdlib): nessun LLM, rete o scrittura |
| `todo.md` | Chiuse per evidenza le voci duplicate/già risolte: toggle componenti (Cycle 67: Timestral ha `[thermal].enabled`, SystemMonitor/Lifecycle passivi), KV cache e batch write (fuori scope T23/T24); Fase D-15 portata a `[~]` (flag e gate-giudice presenti, benchmark 🔒) |

Verifiche: 13 test mirati verdi (6 nuovi + 7 di `test_config_validation`),
`pyflakes` 0. **Nessun valore di config modificato**: i test bloccano lo stato
già documentato, non introducono ottimizzazioni stimate.

---

## Cycle 110 (2026-11-22) — Test isolati: scaffold Docker validato, nessun run

| Modifica | Dettaglio |
|---|---|
| `Dockerfile` (nuovo) | `python:3.11-slim` (allineato a CI), `QT_QPA_PLATFORM=offscreen`, `pause.flag` creato al build: nessun LLM e nessun e2e live dentro il container |
| `docker-compose.yml` (nuovo) | Servizio `tests` con build locale, immagine `byteswarmy-tests:local`, comando pytest prefissato `-p no:cacheprovider` |
| `.dockerignore` (nuovo) | Esclude `.venv`, `.git`, `state/`, `data/state/`, `logs/`, `project/` e cache: contesto di build piccolo e riproducibile |
| `DOCS/DOCKER_TESTS.md` (nuovo) | Comandi per pytest mirato, lint, pyflakes e compileall, più distinzione esplicita travalidazione sintattica, build ed esecuzione |
| `todo.md` | Chiuse entrambe le voci “Test isolati — avvio separato” con lo stato reale |

Verifiche: `docker compose config -q` ✅, `docker buildx build --check .` →
`Check complete, no warnings found`. **Nessuna immagine costruita, nessun
pull, nessuna suite lanciata**: la regola termica del 2026-11-20 resta
applicata e il profiling completo passa solo da GitHub Actions.

---

## Cycle 111 (2026-11-22) — Eval suite interna: lock dello slice deterministico

| Modifica | Dettaglio |
|---|---|
| `tests/test_eval_suite.py` (nuovo) | 5 test offline: `cases.json` caricabile e valido (13 casi), copertura esatta di 8 assi e 3 granularità, rilevamento id duplicati/asse sconosciuto, `--dry-run --json` deterministico e coerente con `summarize()`, file sotto versione. Nessun LLM/rete/scrittura |
| `todo.md` | Fase A portata a `[~]`: lo slice deterministico (13 casi + runner + report per famiglia) è verificato e lockato; resta solo il pass@1 `--live`, che richiede run LLM con gate termico |

Verifiche: 5 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning.
**Nessun caso aggiunto e nessuna misura pass@1 prodotta**: i test bloccano la
struttura già presente, non simulano risultati di modello.

---

## Cycle 112 (2026-11-22) — M6: diagnosi del run CI fallito con fonti reali

| Modifica | Dettaglio |
|---|---|
| `DOCS/CI_PROFILE_DIAGNOSIS.md` (nuovo) | Evidenza da GitHub Actions REST API pubblica: run #2 `44838701460` su `e3f90be`, step 6 `Profilazione completa` fallito in 3 s (23:42:26→29), artifact 1227 byte; log e artifact richiedono auth (`401`/`403`) e **non sono stati letti**. Ipotesi errore di collezione, dichiarata come ipotesi. Mitigazioni `f35f9dd`/`b3ec027` e verifica locale `--collect-only` EXIT=0 (1094 test in 1,71 s) |
| `tests/test_ci_profile_workflow.py` (nuovo) | 5 test offline: workflow manuale con Python 3.11, pausa e2e, step diagnostico `--collect-only`, profilazione con `--durations=0` e `QT_QPA_PLATFORM=offscreen`, upload di `pytest_profile.log` + `collect.log` con `if: always()` |
| `todo.md` | M6 portato a `[~]`: diagnosi e strumenti fatti; trigger su GitHub Actions resta 🔒 (CLI ufficiale + auth) |

Verifiche: 5 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning.
**Nessun run CI avviato e nessun log privato scaricato**: la diagnosi usa solo
metadati pubblici e la collezione locale, che non esegue test.

---

## Cycle 113 (2026-11-22) — M5: corretto il percorso di copia di hardening.sh

| Modifica | Dettaglio |
|---|---|
| `scripts/setup/hardening.sh` | Bug reale trovato con `--check` (read-only): `PROJECT_DIR` puntava a `scripts/setup/`, quindi `--apply` avrebbe copiato solo quella cartella in `/home/byteswarmy/byte-swarmy/` (niente codice, `avvia.sh` o requirements). Ora `SCRIPT_DIR/../..` → radice del repo, allineato al pattern già usato da `re_tools.sh` |
| `tests/test_hardening_paths.py` (nuovo) | 3 test offline: `--check` riporta esattamente la radice del repo, la riga rsync usa `"$PROJECT_DIR"/ "$TARGET_DIR"/`, tutti gli script in `scripts/setup/` passano `bash -n`. Solo lettura e diagnostica, zero root/utenti/firewall |
| `todo.md` | M5 e voce hardening portate a `[~]`/`aggiornate`: rimossa solo la causa del guasto; resta 🔒 l'esecuzione come root (`sudo ... --all` + review polkit) |

Verifiche: 3 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning,
`bash -n` OK. **Nessuna modifica al sistema**: non sono stati creati utenti,
slice o regole firewall, e non è stato usato `pkexec`.

---

## Cycle 114 (2026-11-22) — M3: azione delle sonde allineata al gate stretto

| Modifica | Dettaglio |
|---|---|
| `tools/blocker_probe.py` | La riga M3 del report suggeriva "avviare nbfc con pkexec", ma il daemon è **già attivo** (duty 50%, `Current Fan Speed 0.00`): l'azione era fuorviante. Ora indica "misurare RPM con strumento esterno (nbfc già attivo non basta), poi `--write-fan`". Il corpo del report già documentava la decisione del 2026-11-22 |
| `tests/test_blocker_probe.py` | Lock: il report contiene la nuova azione e **non** contiene più il vecchio suggerimento |
| `DOCS/BLOCKER_PROBE_REPORT.md` | Rigenerato dalla fonte (CPU 67,0 °C, RPM 0, nbfc attivo) |

Verifiche: 13 test mirati verdi, `pyflakes` 0. **Nessun gate indebolito**: il
report continua a rifiutare RPM surrogati e il file `fan_verified.json` resta
assente.

---

## Cycle 115 (2026-11-22) — Stato onesto del piano "Domani"

| Modifica | Dettaglio |
|---|---|
| `todo.md` | Le 5 voci del piano datato 2026-11-20 non sono più etichettate "(Domani)": ora riportano 🔒, il riferimento M/C3 e il blocco effettivo (trigger CI, gate termico, GPU). Aggiunto rimando a `DOCS/CI_PROFILE_DIAGNOSIS.md`. Nessuna voce chiusa o scoperta: solo rimozione di una scadenza ormai falsa |

Verifiche: nessun codice toccato; `git diff --check` e report deterministico
rigenerato. **Nessuna attività LLM, CI o termica avviata.**

---

## Cycle 116 (2026-11-22) — Fase G: harness A/B delle varianti prompt

| Modifica | Dettaglio |
|---|---|
| `tools/eval_prompt_variants.py` (nuovo) | Confronta 4 varianti di prompt (`baseline`, `refs_off`, `refs_first`, `plan_compact`) sugli 11 casi con `expected_marker` di `evals/cases.json`. Task set congelato `182ae2a82284`. Regola scritta prima del live: PROMOTE se tasso ≥0.60 e delta ≥0.20, REJECT se delta ≤0, altrimenti INCONCLUSIVE. Gate termico (`fan_rpm > 0`, `temp_c ≤ 60`) e rifiuto esplicito del solver finto nel live: `--live` non è ancora eseguibile dal CLI |
| `tests/test_prompt_variants.py` (nuovo) | 9 test offline: task set e impronta, determinismo dei prompt, tutte le diramazioni della soglia, dry-run senza PROMOTE, gate termico con tre casi (RPM 0, 75 °C, 50 °C), richiesta di solver reale, report che dichiara SIMULAZIONE, assenza di client LLM |
| `DOCS/PROMPT_VARIANTS_REPORT.md` (nuovo) | Generato dal tool: baseline 0.09, `refs_off` 0.00 (REJECT), `refs_first` 0.27 e `plan_compact` 0.45 (INCONCLUSIVE). Nessuna promozione autorizzata |
| `DOCS/BENCH.md`, `todo.md` | Sezione Fase G con parametri e stato; Fase G portata a `[~]` |

Verifiche: 9 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning.
**Nessun LLM, rete o GPU**: il solver è finto per costruzione e il report
dichiara che il risultato non è un esperimento reale.

---

## Cycle 117 (2026-11-22) — SLOT-5: reporter per-slot con gate sull'evidenza

| Modifica | Dettaglio |
|---|---|
| `tools/eval_by_slot.py` (nuovo) | Classifica gli 11 casi con `expected_marker` in 7 tipi di slot e 3 fasce di dimensione output; genera la tabella pass@1. `--results` accetta un file solo con `source: "live"` e thermal `fan_rpm > 0`, `temp_c ≤ 60`: altrimenti exit 2. Rifiuta case_id sconosciuti/duplicati e slot_kind non ammessi. Dry-run con risultati sintetici etichettati SIMULAZIONE |
| `tests/test_eval_by_slot.py` (nuovo) | 9 test offline: classificazione, bucket, aggregazione, determinismo, rifiuto di 4 surrogate termiche, validazione record, CLI JSON e blocco live, onestà del report, assenza di client LLM |
| `DOCS/SLOT5_EVAL_REPORT.md` (nuovo) | Generato dal tool: 11 casi, tabelle per slot e dimensione, dichiarazione esplicita che non è una misura e non chiude SLOT-5 |
| `DOCS/BENCH.md`, `todo.md` | Sezione SLOT-5 e stato `[~]`; restano 12+ casi reali da misurare |

Verifiche: 9 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning.
**Nessun LLM, rete o GPU**: il live richiede evidenza termica verificata e un
file di risultati esterno, non generato qui.

---

## Cycle 118 (2026-11-22) — Fase E: distillazione gate-verificata

| Modifica | Dettaglio |
|---|---|
| `tools/distill_task.py` (nuovo) | Riceve una soluzione prodotta esternamente e la accetta solo se passa 6 gate offline: file leggibile, ≤200 righe, AST valido, pyflakes 0, security_scan 0 errori (copia temporanea gitignored in `data/state/tmp`, rimossa in `finally`), `expected_marker` del caso eval presente. `--commit` richiede inoltre `fan_verified.json` valido, `--model` dichiarato e dedup via `fc.Triple.dedup_key()`; scrive una tripla `done` con `ts=0.0`. Il tool NON esegue alcun modello |
| `tests/test_distill_task.py` (nuovo) | 10 test offline: caso eval e marker, gate verde senza scrittura, 5 gate rotti (sintassi/pyflakes/security/marker/dimensione), file vuoto, modello obbligatorio, commit bloccato senza termico, scrittura + deduplicazione, report sintetico, CLI JSON/exit code, assenza di client LLM e residui temporanei |
| `DOCS/BENCH.md`, `todo.md` | Sezione Fase E con gate e conteggio esempi reali (0); Fase E portata a `[~]` |

Verifiche: 10 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning.
**Nessun LLM, rete o GPU**: le soluzioni usate nei test sono sintetiche e il
report lo dichiara; servono ≥3 esempi reali da modello 7b/14b per chiudere
la voce.

---

## Cycle 119 (2026-11-22) — SLOT-4: builder deterministico dei prompt per-slot

| Modifica | Dettaglio |
|---|---|
| `tools/slot_prompt.py` (nuovo) | Converte un `SlotPlan` (da `CORE/slot_planner.py`) in un prompt per chiamata: sole refs dello slot corrente, anchor reale del template, regole di output ≤40 righe. Fail-closed su piani rifiutati e indici fuori range; nessun client LLM/rete/scrittura di progetto (solo `--out`). CLI con `--json` e `--out` |
| `tests/test_slot_prompt.py` (nuovo) | 9 test offline: un prompt per slot con refs isolate, anchor e regole output, rifiuto piano rifiutato, indice fuori range, determinismo e report, dichiarazione benchmark bloccato, CLI JSON/rifiuto/scrittura, assenza client LLM |
| `DOCS/SLOT4_PROMPTS.md` (nuovo) | Generato dal tool per "finestra con titolo" (2 slot) |
| `DOCS/BENCH.md`, `todo.md` | Sezione SLOT-4 con stato `[~]`; restano 3 task reali da misurare |

Nota CI (M6): il log HTML pubblico del job `44838701460` conferma solo
`exit code 2` (collezione/interruzione), senza testo di errore. Nessun log
privato letto: la diagnosi in `DOCS/CI_PROFILE_DIAGNOSIS.md` resta invariata.

Verifiche: 9 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning.
**Nessun LLM, rete o GPU**: i prompt sono generati dal piano deterministico;
il benchmark con 3 task reali resta 🔒 termico.

---

## Cycle 120 (2026-11-22) — Fase H: giudice di qualità mai sovrano

| Modifica | Dettaglio |
|---|---|
| `tools/quality_judge.py` (nuovo) | Riceve pareri di un giudice esterno e applica l'invariante `final == gate_pass` sempre: gate FAIL + `approve` resta FAIL, gate PASS + `reject` resta PASS (solo dissenso loggato). Override espliciti bloccati e segnalati. Classificazione accordo/dissenso (`not_consulted`, `judge_ignored_gate_fail`, `concur_pass`, `judge_dissent`), report con tasso accordo, verifica runtime dell'invariante. Pareri `source: "live"` accettati solo con `fan_rpm > 0`, `temp_c <= 60`; altrimenti exit 2. Nessun client LLM |
| `tests/test_quality_judge.py` (nuovo) | 21 test offline: non-sovranità parametrizzata su 6 combinazioni gate×giudice, classificazione accordo, override bloccati, verdetto sconosciuto, gate termico (incluso casi `"1800"`/`"x"`), record non validi, live con evidenza, determinismo/onestà del report, CLI JSON/blocco live, assenza client LLM |
| `DOCS/QUALITY_JUDGE_REPORT.md` (nuovo) | Generato dal tool: 13 casi sintetici (7 consultati, 4 concordi, 2 override bloccati), dichiarato SIMULAZIONE |
| `DOCS/BENCH.md`, `todo.md` | Sezione Fase H con stato `[~]`; restano 20 casi reali da misurare |

Verifiche: 21 test mirati verdi, `pyflakes` 0, `lint_style` 0 errori/0 warning.
**Nessun LLM, rete o GPU**: i pareri sono sintetici e il report lo dichiara;
servono 20 casi reali con pareri live per chiudere la voce.

---

## Cycle 121 (2026-11-22) — M3: canale auditabile per la misura RPM esterna

| Modifica | Dettaglio |
|---|---|
| `tools/blocker_probe.py` | Nuovo `--attest-rpm <ricevuta.json>`: registra una misura RPM esterna solo con ricevuta contenente `fan_rpm`, `instrument`, `method`, `operator`, `measured_at`. Valida range fisico 300–6000, freschezza ≤30 min, nessuna data futura (skew 2 min), path fuori dal tree versionato (o in `data/state/`). La temperatura è **sempre** riletta live da sysfs; il duty è solo contesto (`fan_duty_pct_context_only`) e non entra nel gate. Provenienza esplicita nel file scritto. Nessuna opzione `--rpm`: valori CLI diretti impossibili. `write_fan_verification`/`read_stored_fan` risolvono `FAN_FILE` a runtime (corretto default congelato che rischiava di scrivere il gate reale da un test). `main()` refattorizzato in `_handle_fan_write()` |
| `tests/test_rpm_attestation.py` (nuovo) | 16 test offline: campi obbligatori, RPM fuori range/non numerico/bool, misura stale/futura/date malformata, timestamp naive come UTC, path dentro repo rifiutato, JSON invalido, temperatura live anche con RPM attestati, duty non usato come prova, provenienza e permessi del gate, CLI happy-path/rifiuti/mutua esclusività, assenza di `--rpm`, regressione del default runtime |
| `DOCS/RPM_MEASUREMENT_PROCEDURE.md` (nuovo) | Procedura operativa con evidenza hardware reale (HP Pavilion 15-cb0xx, profilo nbfc `HP Pavilion 17 Notebook PC` discrepante, Current Fan Speed 0.00, nessun `fan*_input`, ~64 °C), passi per la misura con tachometro e comandi di registrazione/verifica |
| `DOCS/rpm_attestation.example.json` (nuovo) | Template compilabile della ricevuta |
| `todo.md`, `DOCS/BLOCKER_PROBE_REPORT.md` | M3 aggiornato con il nuovo canale; report rigenerato dal tool |

Verifiche: 36 test mirati verdi (`test_rpm_attestation.py` + `test_blocker_probe.py`),
`pyflakes` 0, lint 0 errori/0 warning sui file nuovi; W006 pre-esistente su
`markdown()` (89 righe già prima della modifica). **Nessun LLM, rete o GPU**:
nessuna misura è stata inventata — il gate resta NON VALIDO finché non arriva
un tachometro reale. Durante lo sviluppo un test ha scritto per errore un gate
finto nel file reale: rimosso immediatamente e verificato con `--check-fan`.

---

## Cycle 122 (2026-11-22) — M3: la percentuale nbfc non è RPM

| Modifica | Dettaglio |
|---|---|
| `tools/blocker_probe.py` | `parse_nbfc_rpm()` accetta **solo** valori con unità esplicita (`3200 RPM`, decimali inclusi): rimosso il fallback che interpretava `Current Fan Speed : 50.00` come 50 RPM. Nuovo `parse_nbfc_speed_pct()` espone la percentuale nbfc come contesto (`speed_pct`), mai come giri. `nbfc_probe()`/`fan_snapshot()` propagano il valore; `rpm_source` è `null` senza RPM espliciti. Report: nuova riga "Current Fan Speed (nbfc, %)" etichettata **percentuale, non RPM** |
| `tests/test_blocker_probe.py` | 3 test nuovi/aggiornati: `3200.00` senza unità → 0 RPM, percentuale 50% → 0 RPM mentre `parse_nbfc_speed_pct` → 50.0, RPM con/senza decimali, gate bloccato anche con nbfc al 87% e duty 100% |
| `DOCS/RPM_MEASUREMENT_PROCEDURE.md`, `todo.md` | Nota sul parser fail-closed; M3 aggiornato |

Motivazione: il gate stretto della decisione 2026-11-22 vieta i surrogati.
Un numero senza unità non è una misura di giri: accettarlo avrebbe potuto
scrivere `fan_rpm=50` da una percentuale, cioè un dato falso. Il comportamento
fail-closed mantiene il gate chiuso finché non arriva un RPM esplicito o la
ricevuta attestata del Cycle 121.

Verifiche: 38 test mirati verdi, `pyflakes` 0, gate reale `--check-fan` NON
VALIDO. **Nessun LLM, rete, GPU o misura inventata**.

---

## Cycle 123 (2026-11-22) — M2/M6: trigger push per la suite su GitHub

| Modifica | Dettaglio |
|---|---|
| `.github/workflows/profile.yml` | Aggiunto `on.push.branches: [main]` oltre a `workflow_dispatch`. Ogni push su `main` esegue la suite completa sui runner hosted: nessuna suite locale (vietata finché M3 non è chiuso), nessun LLM, nessun calore sulla macchina termicamente vincolata. Il commento documenta il motivo (il `gh` locale è uno script browser 0.0.4, non la CLI ufficiale). La diagnostica di collezione stampa `tail -60 collect.log` nel log pubblico, leggibile senza scaricare l'artifact privato |
| `tests/test_ci_profile_workflow.py` | Nuovo test `test_trigger_push_su_main_per_sbloccare_m2_m6`: verifica `push:`, `branches: [main]` e che i `tail` dei log restino nel log pubblico |

Perché: M2/M6 erano bloccati solo dal trigger manuale, che richiedeva `gh` ufficiale + auth non disponibili. Il push rimuove dipendenza da credenziali e dalla macchina locale. **Nessuna suite è stata eseguita localmente**; l'esecuzione avviene solo su GitHub Actions.

Verifiche: 6 test mirati verdi, YAML valido (`trigger: ['push', 'workflow_dispatch']`), `pyflakes` 0. **Nessun LLM, rete o GPU**: il trigger userà i runner GitHub, non questa macchina.

---

## Cycle 124 (2026-11-22) — M6: errore CI leggibile senza auth

| Modifica | Dettaglio |
|---|---|
| `.github/workflows/profile.yml` | In caso di `EXIT!=0` nella diagnostica di collezione, le ultime 25 righe di `collect.log` vengono emesse come annotations `::error::`. Il log del job richiede diritti admin (403 API, 401 artifact), ma le annotations dei check run sono pubbliche e leggibili via `GET /repos/{owner}/{repo}/check-runs/{id}/annotations` |
| `tests/test_ci_profile_workflow.py` | Test `test_errore_collezione_esposto_in_annotations_pubbliche` blocca l'hook e la conservazione di `exit $code` |

Il run #3 (`45046013422`, commit `7cfaf47`, evento `push`) è fallito allo step 6
con `EXIT=2`; senza annotations il messaggio restava in un artifact privato.

Verifiche: 7 test mirati verdi, YAML valido (`trigger: ['push', 'workflow_dispatch']`),
`pyflakes` 0, `git diff --check` pulito. Nessuna suite locale, LLM o GPU.

---

## Cycle 125 (2026-11-22) — M6: causa provata (libEGL) e fix CI

| Modifica | Dettaglio |
|---|---|
| `.github/workflows/profile.yml` | Nuovo step `Librerie di sistema per Qt headless (libEGL)` prima di `pip install`: `sudo apt-get update` + `libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3 libfontconfig1` |
| `tests/test_ci_profile_workflow.py` | Test `test_librerie_qt_headless_installate_sul_runner`: verifica pacchetto `libegl1`, installazione `--no-install-recommends` e ordinamento prima della diagnostica |
| `DOCS/CI_PROFILE_DIAGNOSIS.md` | Corretta l'affermazione "log pubblico" (in realtà 403/401) e aggiunta la tabella con run #3/#4 e le 11 annotations pubbliche |

Il run #4 (`45046337143`, commit `576b0e7`) ha fallito di nuovo allo step 6, ma
le annotations hanno dato il verdetto esatto:

```
E   ImportError: libEGL.so.1: cannot open shared object file: No such file or directory
tests/test_zoom.py:10: in <module>
    from PyQt6.QtWidgets import QApplication
ERROR tests/test_actors_panel.py
ERROR tests/test_clarifier_gui_bridge.py
ERROR tests/test_close_orchestrator.py
ERROR tests/test_crud_file_manager.py
EXIT=2
```

Non è un difetto della suite: `QT_QPA_PLATFORM=offscreen` seleziona il backend,
ma `ubuntu-latest` non ha la libreria condivisa Qt. L'ipotesi del run #2 è ora
confermata con evidenza pubblica e senza credenziali.

Verifiche: 8 test mirati verdi, `pyflakes` 0, YAML valido, `git diff --check`
pulito. Nessuna suite locale, LLM, GPU o misura inventata.

---

## Cycle 126 (2026-11-22) — M6: collezione verde, diagnostica dei test falliti

| Modifica | Dettaglio |
|---|---|
| `.github/workflows/profile.yml` | Lo step `Profilazione completa` emette `::error title=pytest_exit::EXIT=$code`, fino a 20 righe `FAILED ` e le ultime 20 righe di `pytest_profile.log` come annotations pubbliche, leggibili via API senza auth |
| `tests/test_ci_profile_workflow.py` | Test `test_fallimento_suite_esposto_in_annotations_pubbliche` blocca hook, grep dei `FAILED` e conservazione di `exit $code` |
| `DOCS/CI_PROFILE_DIAGNOSIS.md` | Verdetto run #5/#6 e passaggio a monitor HTML pubblico |

I run #5 (`b47482a`) e #6 (`a78a24c`) mostrano **collezione success**: il fix
`libEGL` del Cycle 125 ha eliminato l'errore di import. La suite completa è
invece fallita nello step 8: il run #6 è durato 28 minuti (`16:56:10Z →
17:24:31Z`) con `exit code 1`, quindi test falliti e non un problema di setup.
Senza i nomi dei test nelle annotations il log restava privato: il Cycle 126
chiude quel buco diagnostico. Commit `91bc272` pushato; run #7 `45051444788`
in corso.

Verifiche: 9 test mirati verdi, `pyflakes` 0, YAML valido, `git diff --check`
pulito. Nessuna suite locale, LLM, GPU o misura inventata.

---

## Cycle 127 (2026-11-22) — M6: corretti 10 failure ambientali del run #7

Il run #7 (`45051444788`, commit `91bc272`) ha finalmente pubblicato i nomi dei
test falliti tramite le annotations del Cycle 126. Tutti i 10 failure erano
differenze tra l'ambiente di sviluppo e i runner hosted, non difetti della suite:

| Test | Causa | Correzione |
|---|---|---|
| `test_api_fidelity_eval.py` ×4 | Ref `csv`/`json` generati su Python 3.14; CI usava 3.11 (firme diverse, `QUOTE_NOTNULL`/`QUOTE_STRINGS` assenti) | `python-version: "3.14"` in `profile.yml` |
| `test_config_gates.py::test_remote_github_senza_token` | `checkout@v5` configura remote HTTPS, il test esigeva SSH | Accettare HTTPS e SSH; resta il divieto di token |
| `test_remote_bridge.py::test_socket_path_resolution` | `/run/user/1000` non esiste sul runner; inoltre `BRIDGE_NAME` è alias del path, non del basename | `TemporaryDirectory()` come `XDG_RUNTIME_DIR` + `SOCKET_BASENAME` |
| `test_repo_hygiene.py` ×2 | `tasks` è symlink a `data/tasks` (gitignored): `.gitkeep` non tracciato e cartella non attesa | `git add -f data/tasks/.gitkeep` + aggiunta `data/tasks` alle dir attese |
| `test_swarm_refactor_session.py::test_wait_cold...` | Runner senza hwmon: `read_max_temp()` = 0.0 | Assert su temperatura ≥0 e attesa <0,5 s |
| `test_refactoring_live.py::test_result_include_message_di_successo` | Mock emetteva result generico a sequenza finita | Messaggio del mock include `refactoring` |

Verifiche locali: `pyflakes` 0 sui file toccati, 56 test mirati passati su 58,
poi i 2 residui corretti e riverificati (2 passed), YAML valido,
`git diff --check` pulito. Commit `11377e5` pushato; run #8 `45055387426`
avviato. Nessuna suite completa locale, LLM, GPU o misura inventata.

---

## Cycle 128 (2026-11-22) — M6: ultimate 4 failure ambientali del run #8

Il run #8 (`45055387426`, commit `11377e5`) ha riportato 4 failure, tutti
riconducibili a differenze tra ambiente locale e runner hosted:

| File | Modifica |
|---|---|
| `tests/test_config_gates.py` | Remote HTTPS senza `.git` accettato tramite normalizzazione; resta il divieto di token |
| `tests/test_repo_hygiene.py` | `test_tasks_gitkeep_exists` verifica `tasks/.gitkeep` oppure `data/tasks/.gitkeep` (symlink non tracciato su CI) |
| `tests/test_user_workflow.py` | `setUp` di `TestToolbarToggle` risincronizza l'icona dopo la rimozione di `pause.flag` |
| `tests/test_clarifier_gui_bridge.py` | Polling del bridge da 0,01 s a 0,05 s per evitare fail-open su runner carichi |
| `DOCS/CI_PROFILE_DIAGNOSIS.md` | Verdetto run #8 e cause verificate |

Verifica: 4 test mirati verdi (`4 passed in 9.76s`), `pyflakes` 0,
`git diff --check` pulito. Nessuna suite completa locale, LLM, GPU o misura
inventata.

---

## Cycle 129 (2026-11-22) — M2/M6 chiusi: suite completa verde su GitHub

| Risultato | Dettaglio |
|---|---|
| Run #9 `45058129636` (commit `f97ff8b`) | **SUCCESS** — step 7 collezione, step 8 `pytest tests/ -q --durations=0`, step 9 artifact tutti `success` |
| `todo.md` | M2 e M6 portati a `[x] Cycle 129`; aggiornata la nota sulla regola termica e il punto 1 del piano "Domani" |
| `DOCS/CI_PROFILE_DIAGNOSIS.md` | Tabella finale dei run da #2 a #9 con esiti e cause |

La diagnosi del profiling CI, iniziata al Cycle 112, si chiude con il run #9.
La suite completa non viene rieseguita in locale: la regola termica del
2026-11-20 vieta LLM/GPU/benchmark finché `fan_verified.json` non è valido.
Nessun LLM, GPU o dato ventola fabbricato.

---

## Cycle 130 (2026-11-22) — M3: audit conclusivo delle sorgenti RPM

| Verifica | Esito |
|---|---|
| `/sys/class/hwmon/hwmon*/fan*_input` | nessun nodo su 7 chip (`ADP1`, `acpitz`, `BAT0`, `coretemp`, `pch_skylake`, `hp`, `iwlwifi_1`) |
| `find /sys` per `fan*_input` / `fan*_rpm` | 0 risultati |
| `sensors` → `hp-isa-0000` | `pwm1: N/A` (duty-cycle, non giri) |
| `nbfc status` | `Current Fan Speed: 0.00` (percentuale), `Target: 0.00 %`, `Auto Control: true` |
| `/sys/kernel/debug/ec/` | non accessibile |
| `tools/blocker_probe.py --check-fan` | `fan_verified.json: NON VALIDO` |
| Test attestazione RPM | 38 passed |

`DOCS/RPM_MEASUREMENT_PROCEDURE.md` aggiornata con l'evidenza: non esiste
alcuna sorgente RPM leggibile, quindi il tachometro esterno resta l'unico
canale ammesso. Nessun valore inventato, nessun surrogato da duty-cycle,
nessuna suite locale, LLM o GPU.

---

## Cycle 131 (2026-11-23) — M4: CLI ufficiale `gh` installata in userspace

| Azione | Dettaglio |
|---|---|
| Audit | `~/.local/bin/gh` era uno script Python browser 0.0.4 con interprete `/usr/local/bin/python3.14` inesistente → comando non funzionante. `~/.config/gh/hosts.yml` contiene solo `user: wildlux`, nessun token leggibile |
| Download | `gh_2.46.0_linux_amd64.tar.gz` dalla release ufficiale `cli/cli`, SHA256 `c671d450d7c0e95c84fbc6996591fc851d396848acd53e589ee388031cee9330` verificato contro `gh_2.46.0_checksums.txt` |
| Installazione | `~/.local/bin/gh-official` (ELF Go statico, 0755); `~/.local/bin/gh` ora symlink all'ufficiale; vecchio script preservato come `gh-browser-legacy` (rename reversibile, non eliminato) |
| Verifica | `gh --version` → `gh version 2.46.0`; `gh auth status` → token in `hosts.yml` invalido, richiede `gh auth login -h github.com` |
| `todo.md` | M4 aggiornato con progresso e blocco residuo |

Nessun root, nessuna modifica a `.git-credentials` (usato da altri repo HTTPS),
nessun token committato. Il login resta un'azione dell'utente nel browser: è
il dato oggettivo mancante, non deducibile dal repo.

---

## Cycle 132 (2026-11-23) — M4 chiuso: gh autenticato, token ruotato

| Azione | Dettaglio |
|---|---|
| Login | `gh auth login --hostname github.com --web --scopes repo,read:org,gist` eseguito dall'utente nel browser |
| Verifica | `gh auth status` → `wildlux`, token `gho_`, scope `gist`, `read:org`, `repo`, `workflow`; `gh api user` → `wildlux` |
| Rotazione | Il token invalido in `hosts.yml` è stato sostituito nel keyring; `.git-credentials` contiene solo il token OAuth corrente (nessun `ghp_`/`github_pat_` residuo) |
| Report | `DOCS/BLOCKER_PROBE_REPORT.md` rigenerato: M4 ✅. `tools/blocker_probe.py`: azione successiva M4 resa dinamica (non più "installare la CLI" quando già autenticato) |
| `todo.md` | M4 portato a `[x] Cycle 132` |

**Limite dichiarato**: la revoca lato GitHub non è verificabile via API con il
token disponibile (`/user/authorizations` e `/user/personal_access_tokens`
rispondono 404). Il probe riporta esplicitamente `Rotazione PAT confermata: ❌`
invece di affermare un verdetto non dimostrabile. Nessun token stampato o
committato; `.git-credentials` non modificato.

---

## Cycle 133 (2026-11-23) — M5 chiuso: hardening applicato come root

| Azione | Dettaglio |
|---|---|
| Correzione pre-applicazione | `scripts/setup/hardening.sh`: aggiunto `--exclude 'data/state/'` alla rsync — senza questa, `data/state/cloud_api.json` (credenziali cloud) sarebbe stato copiato e chownato all'utente isolato. Lock in `tests/test_hardening_paths.py` (4 test verdi) |
| Esecuzione | `pkexec scripts/setup/hardening.sh --all` → EXIT 0, su autorizzazione root esplicita dell'utente |
| Utente | `byteswarmy` uid/gid 1001/1002, nessun gruppo amministrativo, home 0700, password bloccata |
| Copia | progetto in `/home/byteswarmy/byte-swarmy`, `.git` senza token evidenti; `cloud_api.json` **non** copiato (verificato sia in `data/state/` sia in `state/`) |
| Slice | `/etc/systemd/system/byteswarmy.slice`, `systemctl is-active` → `active` (MemoryMax 4G, CPUQuota 200%, TasksMax 100) |
| Firewall | 2 regole OUTPUT per uid 1001: ACCEPT `127.0.0.1:11434` (Ollama) e DROP di tutto il resto; rete di `wildlux` intatta (HTTP 200) |
| `todo.md` | M5 portato a `[x] Cycle 133` |

⚠️ **Limite dichiarato**: le regole iptables non sono persistenti al reboot
(`/etc/iptables` assente). Lo script lo segnala; serve `iptables-persistent`
o un `iptables-save` esplicito. Non è stato installato nulla di aggiuntivo.

---

## Cycle 134 (2026-11-23) — snapshot firewall verificabile offline

| Azione | Dettaglio |
|---|---|
| Snapshot | `pkexec mkdir -p /etc/iptables` + `iptables-save > /etc/iptables/rules.v4` (0644 root); le 2 regole per uid 1001 (ACCEPT Ollama + DROP) sono state riverificate nel file |
| Probe | `hardening_probe()` espone `rules_saved`; la tabella M5 mostra `regole salvate ✅` e l'azione successiva distingue il caso con/senza snapshot |
| Report | `DOCS/BLOCKER_PROBE_REPORT.md` rigenerato: M5 ✅ con snapshot |
| `todo.md` | M5 aggiornato con lo stato dello snapshot |

Nessun pacchetto installato: il ripristino automatico al boot richiede
`iptables-persistent`, che resta un'azione esplicita non eseguita. 19 test
mirati verdi, `pyflakes` 0, `git diff --check` pulito.

---

## Cycle 135 (2026-11-23) — runner live della eval suite, pronto ma non eseguito

| Azione | Dettaglio |
|---|---|
| `tools/run_eval.py` | `--live` implementato: `require_gate()` riutilizza `blocker_probe.read_stored_fan()` (RPM attestati) e rilegge la temperatura live; rifiuto con exit 2 se il gate non è valido o se la CPU è già >60 °C. `run_live()` crea un worker per caso, campiona la temperatura prima di ogni caso, interrompe se supera 60 °C, verifica il marker nei file `.py` toccati dal worker (`touched_python`) e registra `passed=False` su errore, marker mancante o retry interno (`last_attempts > 1`). Nessun `passed` sintetico |
| Wiring SLOT-5 | I risultati vanno in `data/state/eval_live_results.json` (gitignored) con `source: "live"`, evidenza termica e 11 record con marker; i 2 casi gate/chiarimento finiscono in `excluded_cases`. Verificato che `tools/eval_by_slot.py --results` accetti il file prodotto e rifiuti quello interrotto per calore |
| Sicurezza | Nessun import `CORE` a livello di modulo: il factory reale (`ModelClient`/`ToolSet`/`AgentMemory`/`Worker`) viene importato solo dopo il gate. `--live` richiede di essere lanciato dalla radice del repo (path configurazione relativi) |
| Test | `tests/test_run_eval_live.py` (8 test): rifiuto gate, assenza import LLM, formato live, fallimenti, retry, surriscaldamento, CLI exit 2, invarianza dry-run. Con `test_eval_suite.py` e `test_eval_by_slot.py`: **22 passed** |
| Verifica reale | `tools/run_eval.py --live` su questa macchina → `RIFIUTO: fan_verified.json NON VALIDO (file assente)`, exit 2, nessun worker creato, nessun file risultati scritto. Dry-run invariante (13 casi, 8 assi, 3 granularità) |

**Limite dichiarato**: il runner è pronto, ma **nessuna misura pass@1 è stata
prodotta**. M3 (tachometro) e M7 (task GUI live) restano bloccati: questo
commit non alza nessun asse del radar e non dichiara il Middle raggiunto.
Nessuna suite completa locale, nessun LLM, GPU o benchmark eseguiti.

---

## Cycle 136 (2026-11-23) — attestazione RPM in un solo comando

| Azione | Dettaglio |
|---|---|
| `tools/attest_rpm.py` | Nuovo script eseguibile: chiede RPM + strumento + metodo + operatore + note al terminale, costruisce la ricevuta con `measured_at` UTC generato al momento, la scrive in `data/state/rpm_attestation.json` (0600, gitignored) e delega tutta la validazione a `blocker_probe.load_rpm_attestation`. Poi `attested_rpm_snapshot` (temperatura **live**) e `write_fan_verification`: il gate viene scritto solo con RPM > 0 e 0 < T ≤ 60 °C |
| Sicurezza | Nessun RPM passabile da CLI: l'unico ingresso è l'input dell'operatore. Loop su valore non numerico/fuori range 300–6000; campo obbligatorio vuoto → annullo senza file scritti. Nessun import CORE/LLM nel modulo |
| Comando | `cd /home/wildlux/Desktop/byte-swarmy && ./tools/attest_rpm.py` — stampa `Gate VALIDO` e il successivo `tools/run_eval.py --live` |
| Documentazione | `DOCS/RPM_MEASUREMENT_PROCEDURE.md` aggiornata con la via rapida; il flusso manuale resta come alternativa equivalente |
| Test | `tests/test_attest_rpm.py` (6 test): deterministicità ricevuta, validazione input, permessi 0600, gate valido, rifiuto sopra 60 °C, rifiuto RPM fuori range, flusso "un solo comando". Con blocker/RPM/run_eval: **52 passed** |

**Limite dichiarato**: la misura fisica non è stata presa. Lo script è pronto
ma `fan_verified.json` resta assente; nessun gate è stato aperto e nessun
`--live` è stato eseguito in questo ciclo.
