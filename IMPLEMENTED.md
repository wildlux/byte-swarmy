# 🛠️ Implementation Log — BYTE-SWARMY

This file tracks every significant feature, fix, and architectural change implemented in the system. It serves as a historical record to keep the main READMEs clean and focused on usage.

## 🛡️ Core Security & Sandbox
- [x] **Rule 0 Implementation**: Security policy moved to the tool layer; cannot be disabled via config or prompts.
- [x] **Unprivileged Sandbox**: Integrated `bubblewrap` to isolate filesystem, network, and PID namespaces.
- [x] **Command Validation**: Implemented structural tokenization and whitelist/blacklist for `run_bash` (no shell).
- [x] **Path Confinement**: Strict restriction of all file operations to the `project/` directory.
- [x] **Environment Sanitization**: `avvia.sh` now clears sensitive env vars and sets strict `ulimit`.
- [x] **Hardening Scripts**: Created `setup-hardening.sh` for root-level isolation (cgroups, dedicated user).

## 🧠 Intelligence & Orchestration
- [x] **Multi-Agent Hierarchy**: Implemented Orchestrator $\rightarrow$ Planner $\rightarrow$ Worker $\rightarrow$ Auditor flow.
- [x] **Audit Worker (The Reviewer)**: Dedicated agent for senior-level code review and security gating.
- [x] **TDD Enforcement**: Orchestrator now rejects `done` status if a failing test wasn't run first.
- [x] **Tiered Memory**: Implemented Short-Term (RAM), Working (JSON), and Long-Term memory buffers.
- [x] **Professional Refactor-Loop**: Workers now follow Map $\rightarrow$ Analyze $\rightarrow$ Modify $\rightarrow$ Verify.
- [x] **Generic Task Planner**: Integration of decision models for high-level task decomposition.

## 💻 Development Toolset
- [x] **Precision Patching**: `patch_code` for targeted find-and-replace modifications.
- [x] **Refactoring Suite**: `rename_symbol`, `extract_method`, `analyze_complexity`, `get_call_graph`.
- [x] **Static Analysis**: Integration of `lint_code` and `Bandit` (SAST) for security scanning.
- [x] **Automated Testing**: `run_test_suite` for self-healing and verification.

## 🔌 Hardware & USB Analysis
- [x] **Passive Capture**: `inspect_usb_devices` and `capture_usb_traffic` (Read-Only).
- [x] **USB Monitoring**: Integration with `usbmon` kernel module and `tshark`.
- [x] **Safe Hardware Access**: Tool-layer block on any write operations to the USB bus.

## ⚙️ Infrastructure & GUI
- [x] **ACID Task Queue**: Migrated from JSON to SQLite for data integrity.
- [x] **Enterprise GUI**: Professional dark theme with a dedicated "Test & Sandbox" monitoring tab.
- [x] **Thermal Management**: `TimestralManager` for CPU temperature monitoring and tick-rate adjustment.
- [x] **Automatic Backups**: Lifecycle manager handles periodic project snapshots.

## 🏗️ Cycle 7 — Foundations & Robustness (2026-10-28)
- [x] **System Watchdog** (`watchdog.py`): supervisor process restarts the orchestrator after a crash; `avvia.sh` now launches the orchestrator through it.
- [x] **Circuit Breaker** in `Worker.execute`: 3 identical tool calls force a mandatory prompt pivot (no more infinite tool-call loops).
- [x] **AST Security Scanner** (`ast_scanner.py`): deterministic gate on `write_file`; blocks banned functions/modules regardless of obfuscation.
- [x] **Event Sourcing Memory** (`memory_provider.py`): immutable SQLite event log per worker; summaries become views (`is_summary=1`), not the source of truth.
- [x] **Mandatory Isolation Check** (`security_checks.py`): boot-time verification of user/cgroups; without isolation the orchestrator starts in **Safe Mode** with extreme restrictions.
- [x] **Escape-artifacts cleanup**: clean rewrite of `watchdog.py`, `memory.py`, `ast_scanner.py` and the Worker region of `orchestrator.py`; suite 47/47 PASS, `py_compile` clean on all modules.
- [x] **Orchestrator modularization**: `constants.py`, `lifecycle_manager.py`, `system_monitor.py`, `task_dispatcher.py`; removed dead duplicated `run`/`_tick` and duplicated QC block.
- [x] **Verified backups**: `perform_backup()` now extracts and re-counts archives after creation ("an unverified backup is no backup").

## 🌊 Cycle 8 — Intent Router & GUI Control Center (2026-10-28/29)
- [x] **Intent Router** (`intent_router.py` + `intents.json`): multilingual (IT/EN/ZH) fuzzy classification of free-form input via `rapidfuzz`; confidence-based fallback to `generic`.
- [x] **Intent Bridge** (`intent_bridge.py`): router↔GUI/orchestrator adapter; integrated in the GUI Quick Command Bar (`integrazione_add_task.py` documents the CLI path).
- [x] **GUI redesign**: unified Start/Stop toggle, colored CPU/GPU temperature indicators in the toolbar, **Live Activity Panel** beside the task table, simplified status bar.
- [x] **Test & Sandbox tab**: run the suite, sandbox self-test and isolation status from the GUI (Control Center now has 6 tabs).
- [x] **GPU thermal sensing**: `nvidia-smi` GPU temperature in `thermal_manager.py` + direct `/sys/class/thermal` reads in the GUI indicators.
- [x] **Ollama metrics** (`ollama_metrics.py`): last-call metrics and loaded VRAM models exposed to the GUI.
- [x] **Dependency fix**: `rapidfuzz` added to `requirements_gui.txt` and `setup.sh` (was required but never declared).
- [x] **Toolbar temperature fix**: `_set_temp_label` was referenced but never defined (silent `AttributeError` swallowed by try/except) and there was no refresh timer — indicators stayed at `--°C` unless the orchestrator started. Added `_update_temp_indicators()` with a 3 s timer; CPU reads `/sys/class/thermal`, GPU via `nvidia-smi`. Works also with the orchestrator stopped.
- [x] **Stylesheet actually applied**: `STYLESHEET` was defined inside the `except ImportError` block of the `intent_bridge` import (never executed when the module is present) and was never applied via `app.setStyleSheet`. Moved to module level, rewritten as a flat minimal dark theme, applied in `main()`.
- [x] **Minimalist UI pass**: removed emoji chrome from buttons, table headers, quick bar, live panel, MCP/thermal/tests headings; semantic state dots (green/orange/red) kept; UI-only.
- [x] **Themeable UI**: `STYLESHEET` replaced by `build_stylesheet(theme)` with two palettes (dark default, new light); choice persisted in `state/gui_theme.json`; toolbar toggle "◐ Tema" applies the new theme live. Token collision fixed (longest-token-first substitution).
- [x] **Simplified task insertion**: single entry row — Quick Command Bar hosts both "Aggiungi" (natural language, Enter works too) and "Nuovo Task…" (full form); "Aggiungi Task" deduplicated from the selection buttons row. Fallback keeps "Nuovo Task…" visible when the Intent Router is unavailable.
- [ ] **Open follow-ups from the Brutal Honesty audit** (`todo.md`, 2026-10-28): anti-escape guardrail in `write_file`/`patch_code` (M1), centralized exception policy (M2), Bandit/Mypy static gates (M3), full state recovery from the event store (M4), selective `/etc` masking (M6), disk quota on `project/` (M7), USB protocol parser and differential capture analysis (M10/M11).
