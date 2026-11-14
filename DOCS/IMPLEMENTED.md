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
