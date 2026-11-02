# 🛠️ Implementation Log — BYTE-SWARMY

This file tracks every significant feature, fix, and architectural change implemented in the system. It serves as a historical record to keep the main READMEs clean and focused on usage.

## 🔐 Sprint Sicurezza + Igiene (2026-11-02)
- [x] **T2.2 Cabla Timestral su Attori**: `MONITORING/thermal_manager.py`
  nuovo helper `load_timestral_overrides()` (legge la sezione `timestral`
  di `CONFIG/actors.json`, fail-open `{}`); `CORE/orchestrator.py` — le
  soglie del `TimestralGatekeeper` sono ora `actors.json > config.toml >
  default T3`, con log "[timestral] attori override" se presenti;
  `SAMPLE_INTERVAL` configurabile dal pannello (min 5s).
- [x] **T2.3 Scheduler Worker**: nuovo `CORE/scheduler_worker.py` —
  `SchedulerLogic` (pura, tempo fake per test: oneshot `datetime`,
  `interval_sec` via `last_run`, daily "HH:MM" con `last_run_date`
  anti-doppio-scatto-in-giornata) + `SchedulerWorker` (thread daemonico,
  stop cooperativo via `Event.wait` — mai `time.sleep`); tick 60s legge
  `CONFIG/scheduled_tasks.json`, inietta nella `TaskQueue` (source
  "scheduler") e aggiorna `last_run`/`last_run_date`/`done` in JSON.
  Il thread parte in `Orchestrator.__init__` e si ferma in `_shutdown()`.
- [x] **T2.4 Modelli Ollama reali in combo**: `GUI/actors_panel.py` niente
  più lista statica: `ollama_list_models()` (`ollama list`, prima colonna,
  timeout 3s, fallback `[]`) + fallback su `OLLAMA_MODELS` se vuota;
  verificato offscreen: la combo mostra i 6 modelli installati reali.
- [x] **T3.6 Test scheduler/settings/attori**: `tests/test_scheduler.py`
  (20 test: matching oneshot/interval/daily con tempo fake, doppio-run
  bloccato sul file JSON), `tests/test_settings_store.py` (6: default
  senza remote, I/O su tmp, JSON corrotto fail-open, no leak token),
  `tests/test_actors_panel.py` (6 offscreen). Igiene 14/14 OK.
- [x] **T1.1+T1.2 Token preclusi da git**: `CONFIG/settings.json` untracked
  (`git rm --cached`, il file su remote non conteneva segreti: nessuna
  rotazione necessaria) e `CONFIG/{settings,actors,scheduled_tasks,git_settings,security_baseline}.json`
  aggiunti a `.gitignore` — gli auto-sync `./sync.sh` non li committeranno più.
- [x] **T1.3 Token via env vars**: in `GUI/control_center.py::_do_git_save`
  la env `BSWARM_GITHUB_TOKEN`/`BSWARM_GITLAB_TOKEN` ha **sempre priorità**
  sul token salvato su disco; README aggiornato con le istruzioni `export`.
- [x] **R3 Duplicati**: rimossi dalla root le copie stale dei pannelli GUI
  (`control_center.py`, `actors_panel.py`, `settings_panel.py`,
  `settings_store.py`, `task_scheduler_panel.py`, `control_center.diff`) —
  le versioni live sono in `GUI/` (`avvia.sh` lancia `GUI.control_center`);
  rimossi PNG di screenshot generati (`*_after/before.png`) e `GUI/_archivio_test/TEST_GUI_QT_{10,11}.py`
  identici a `TEST_GUI_SEPARATA/`; rimossi junk risussi `GUI/fix_remaining.py`,
  `GUI/main_window_old.py.bak`. Igiene test: 14/14 OK.
- [x] **T3.1 Codice morto toolbar**: rimossi i pulsanti Pausa/Stop
  mai-generati dopo `return bar` in `GUI/control_center.py` (le versioni
  vive sono già cablate a riga ~1777).
- [x] **Tool `travasa_todo.py`**: sposta automaticamente le voci `- [x]`
  di `todo.md` in `IMPLEMENTED.md` (sezione "Completati (spostati da
  todo.md)", dedup, `--dry-run`, `<dir>` per test su fixture). Igiene.

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
- [x] **Entry points**: `avvia.sh`/`ferma.sh` now use `python -m SAFETY.watchdog`, `python -m CORE.orchestrator`, `python -m GUI.main_window`. `main.py` is the CLI entry point.
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

## 🚀 Cycle 13 — Work Order: Pre-Flight, Correction, Thermal Gatekeeper & GUI Zero-Click (2026-10-31)

- [x] **T1 Pre-Flight Check & Persistenza** (`CORE/decision_feedback.py`): tabella `decision_feedback` su SQLite con schema Work Order (`id PK`, `timestamp`, `original_prompt`, `invalid_parameters JSON`, `decision_reason`, `user_corrected`). Gate deterministico **prima** di qualsiasi consultazione LLM (zero token per errori formali). Validazione via `validate_task_parameters()`: parametri invalidi → INSERT su SQLite + `needs_revision`; validi → `queued` + `task_id`. Prompt troncato a 500 caratteri (vincolo globale). Adapter `ask_verdict` su `GenericTaskPlanner` per il decision model opzionale. Hook `preflight_and_queue()` nell'orchestratore. CLI `CORE/preflight_cli.py` per la GUI via QProcess (non bloccante). 7 test, DoD verificato: parametro errato → SQLite + 0 chiamate LLM.
- [x] **T2 Post-Execution Feedback Loop** (`CORE/correction.py`): `build_correction_prompt(original_task, previous_code, stderr)` con sanitizzazione path assoluti (`/home/.../` → `[PATH]`), errore limitato a 5 frame / 500 caratteri, prompt direttivo. `TaskQueue.fail_with_correction()`: tentativo 1-3 → status `pending` + prompt sovrascritto; 4° → `failed_definitively` senza loop infinito. Integrato nel dispatcher (`_process_worker_failure`). Bug preesistente `{feedback}` in `_build_initial_prompt` corretto (parametro `correction`). 7 test, DoD verificato: retry count ≤ 3 con prompt corretto, 4° definitivo.
- [x] **T3 Timestral Gatekeeper** (`MONITORING/thermal_manager.py` + orchestator hook): latch con isteresi: CPU ≥ 75 °C o GPU ≥ 80 °C → `paused=True`; ripresa solo quando max(cpu,gpu) < 65 °C. `TimestralGatekeeper` classe pura (nessun I/O/sleep). `ThermalSample` dal `TimestralManager.last_sample`. `TaskQueue.pause_thermal()`/`resume_thermal()` gestiscono lo stato `thermal_paused`. Gate inserito nel `_tick` (non bloccante: polling via tick esistente, nessun `time.sleep`). 6 test, DoD: 80 °C forzato → pausa, rientro a 60 °C → ripresa.
- [x] **T4 GUI Zero-Click Refactoring** (`GUI/main_window.py`): nuova `MainWindow` senza `QTabWidget`. Layout: **Top Bar** fissa (pallino stato orchestratore, temperatura CPU/GPU, modello attivo, toggle orchestratore, tema), **Body** `QSplitter` orizzontale (| coda task 1 | log pane 2 |), **Bottom Bar** `QLineEdit` + "Invia" → `QProcess` → `CORE/preflight_cli.py` (non bloccante, Signal/Slot nativi). `TaskQueueModel` con `QAbstractTableModel` + polling refresh 2 secondi. Menu "Strumenti" apre le vecchie tab (MCP, Modelli, Config, Timestral, Test) come dialog modali (widget riusati). Screenshot offscreen verificato: input, invio, accodamento, log scrolling.
- [x] **GUI: menu hamburger + pulsante orchestratore verde (2026-11-01)**: `main_window.py` — menu bar nativa "Strumenti" sostituita da pulsante `☰` (objectName `hamburger`, primo elemento della Top Bar) che apre un `QMenu` a tendina con le stesse voci (menu bar nativa spesso finisce nel global menu Wayland/GNOME-KDE). Pulsante Orchestratore.colorato dinamicamente via property `data-running` + unpolish/polish: **verde quando avviato**, rosso quando fermo (`GUI/theme/{dark,light}.qss`), stato applicato sia in `_refresh_all` sia subito nel click handler. Verificato offscreen: prop `false→true→false`, testo e dot coerenti.
- [x] **Suite test: 85 test (85/85 OK)**: 27 security + 22 sandbox + 3 escape-gate + 6 intent + 9 execute-handler + 7 decision-feedback + 7 correction-loop + 6 thermal-gatekeeper + 14 repo-hygiene.
- [x] **Hardening dotfile + test dedicati (2026-11-01)**: `SAFETY/security.py` — matching dei componenti sensibili ora case-insensitive (`_SENSITIVE_PARTS_CF`/`_SENSITIVE_NAMES_CF`): anche `.SSH`, `.Bashrc`, `ID_RSA` sono bloccati come i corrispettivi minuscoli. Nuovo `tests/test_dotfile_security.py` (18 test): dot-path sensibili bloccati in lettura+scrittura, nessun over-blocking su `.gitignore`, traversal `..` verso dotfile reali, symlink in scrittura sempre rifiutati (zero-symlink, anti-TOCTOU), esfiltrazione bash (`cat .env`, `grep .gnupg`) anche con varianti di casing, `is_sensitive_path` fail-closed. Suite security/sandbox/escape riverse OK (49 test).
- [x] **Pulizia repo (2026-11-01)**: rimossi script one-shot (`feature7_timestral_tuner.py`, `fix_timestral_advice_file.py`), duplicati (`GUI/{dark,light}.qss`, `intents.json` root, immagini derivate), `GUI/control_center.py`, dir runtime stray in `GUI/`, `Archivio.zip`, file corrotto del desktop; runtime untracked (`tasks/*.db`, `DATABASE/` unita in `tasks/`); `.gitignore` riscritto senza sezioni duplicate; `tests/test_repo_hygiene.py` (14 test) per verificare che la pulizia resti.

## 🔓 Open follow-ups
MCP E2E testing, USB protocol parser, USB differential analysis, dedicated user `byteswarmy`, usbmon/tshark automation, unification of GUI→SQLite queue (FM14). Elenco aggiornato in `todo.md`.

## 📋 Completati (spostati da todo.md) — 2026-11-02

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

- [x] **T3.1 Codice morto toolbar** — Cancellare righe ~1811-1822 di
  `GUI/control_center.py` (codice dopo `return bar` — i pulsanti Pausa/Stop
  orchestratore non vengono mai creati). Oppure spostarle sopra il `return`
  se si vogliono davvero i pulsanti Pausa/Stop in toolbar.

- [x] **R3.** Verificare funzionalità duplicate se un file supera ~500 righe.

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

- [x] **T3.6 Test automatizzati nuovi moduli** — Aggiungere a
  `tests/run_tests.py`:
  - `tests/test_settings_store.py` (save/load/migration)
  - `tests/test_actors_panel.py` (3 attori + parametri validi)
  - `tests/test_scheduler.py` (logica one-shot/interval/daily senza
    thread reale — solo logica pura)

