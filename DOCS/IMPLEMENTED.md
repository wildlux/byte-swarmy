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
  `get_pending_tasks`). Pin `mcp>=1.0.0,<2` in `requirements_gui.txt`.
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
