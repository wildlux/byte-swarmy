# 🛠️ Implementation Log — BYTE-SWARMY

This file tracks every significant feature, fix, and architectural change implemented in the system. It serves as a historical record to keep the main READMEs clean and focused on usage.

## 🛡️ Core Security & Sandbox
- [x] **Rule 0 Implementation**: Security policy moved to the tool layer; cannot be disabled via config or prompts.
- [x] **Unprivileged Sandbox**: Integrated `bubblewrap` to isolate filesystem, network, and PID namespaces.
- [x] **Command Validation**: Implemented structural tokenization and whitelist/blacklist for `run_bash` (no shell).
- [x] **Path Confinement**: Strict restriction of all file operations to the `project/` directory.
- [x] **Environment Sanitization**: `avvia.sh` now clears sensitive env vars and sets strict `ulimit`.
- [x] **Hardening Scripts**: Created `setup-hardening.sh` for root-level isolation (cgroups, dedicated user).
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
- [x] **Dependency fix**: `rapidfuzz` added to `requirements_gui.txt` and `setup.sh` (was required but never declared).
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

## 🔓 Open follow-ups
UI redesign (menu hamburger, Live Activity in alto), MCP E2E testing, USB protocol parser, USB differential analysis, dedicated user `byteswarmy`, usbmon/tshark automation, unification of GUI→SQLite queue (FM14).
