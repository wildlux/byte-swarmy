# 📜 SPECIFICATIONS.md — System Technical Specifications

This document provides the comprehensive technical specifications for BYTE-SWARMY, detailing the architectural requirements, security boundaries, and functional capabilities.

## 1. System Overview
BYTE-SWARMY is an autonomous multi-agent system designed for enterprise-grade software development and passive USB reverse engineering, optimized for execution on resource-constrained Linux environments (e.g., 4 GB RAM, 4 GB VRAM GPU). It is organised as a swarm of small specialised LLMs (orchestrator, planner, worker_coder, worker_general, embedding, decision) that are rotated in and out of VRAM as needed.

## 2. Technical Stack
- **Language**: Python 3.11+ (tested on 3.14)
- **Interface**: PyQt6 (GUI), CLI (`main.py`, `avvia.sh`, `ferma.sh`, `sync.sh`)
- **Inference**: Ollama (local LLMs: qwen2.5, qwen2.5-coder, phi3, tev1, nomic-embed-text, …)
- **Persistence**: SQLite (task queue + event sourcing memory), JSON (Timestral history, persistent memory, metrics)
- **Isolation**: Bubblewrap 0.11+ (unprivileged sandbox)
- **Monitoring**: Custom thermal/resource manager (`TimestralManager`) — CPU + NVIDIA GPU
- **Routing**: `rapidfuzz` fuzzy multilingual intent classification (IT/EN/ZH)
- **TOML**: `tomllib` (read) + `tomli_w` (write)

## 3. Package Structure
The project is organised into uppercase Python packages, each with `__init__.py`:

```
byte-swarmy/
├── CORE/           orchestrator, worker, planner, auditor, tools, sandbox,
│                   memory, memory_provider, ollama_client, task_dispatcher,
│                   constants, ast_scanner, mcp_client, persistent_memory,
│                   model_selector
├── INTENT/         router, bridge, metrics, intents.json
├── SAFETY/         security, security_checks, watchdog
├── MONITORING/     thermal_manager, system_monitor, lifecycle_manager
├── GUI/            main_window (PyQt6)
├── CONFIG/         config.toml
├── tests/          test_security, test_sandbox, test_intent_integration, run_tests
├── state/          timestral_history.json, persistent_memory.json, last_metrics.json,
│                   streaming.txt, orchestrator.pid
├── tasks/          queue.db (SQLite, source of truth), queue.json (GUI dual-write)
├── logs/           byte-swarmy.log, byte-swarmy.jsonl, watchdog.log, security.log
├── project/        worker output (sandboxed)
├── backups/        auto-snapshot tar.gz
├── avvia.sh / ferma.sh / sync.sh / setup.sh / setup-hardening.sh
└── main.py         CLI entry point
```

All cross-module imports use package paths (`from CORE.tools import ToolSet`, `from SAFETY.security import log_security_event`, etc.). Entry points use `python -m CORE.orchestrator`, `python -m GUI.main_window`, `python -m SAFETY.watchdog`.

## 4. Architectural Requirements

### 4.1 Execution Model
- **Sequential Loop**: The system operates on a single-threaded tick-based orchestrator to avoid race conditions and ensure stability.
- **Stateless Workers**: Workers are instantiated on-demand and their state is persisted to disk (event-sourced SQLite), allowing for crash recovery.
- **ACID Compliance**: The task queue uses SQLite (`tasks/queue.db`) to ensure no tasks are lost during power failure or crashes.
- **Watchdog**: A supervisor process (`SAFETY/watchdog.py`) restarts the orchestrator immediately if it crashes.
- **Model Rotation**: Only one Ollama model is loaded in VRAM at a time (`ModelClient` unloads the previous model before loading a new one). Hard constraint to fit in 4 GB VRAM.

### 4.2 Sandbox Specification
Every worker subprocess must be encapsulated in a `bubblewrap` container with the following properties:
- **Filesystem**: Only `/usr`, selected `/etc` files (ld.so.cache, nsswitch.conf, passwd, group, hosts, localtime, gai.conf, ld.so.conf.d, ssl), the venv and `project/` are mounted. `/etc` and `/opt` are mounted as tmpfs and then `--remount-ro` so no file can be created outside `project/`.
- **Network**: Fully isolated network namespace (no internet/LAN access).
- **Namespaces**: Isolated PID, IPC, UTS, and User namespaces.
- **Privileges**: `--cap-drop ALL`, `no_new_privs`, and `--disable-userns` (blocks nested user namespaces).
- **Environment**: `--clearenv` + only safe variables (`PATH`, `HOME=/home/sandbox`, `TMPDIR=/tmp`, `LANG=C.UTF-8`, git safety vars, …); no tokens, no SSH socket.
- **Fail-closed**: if `bwrap` is not available, `run_bash`/git/search refuse to execute and log CRITICAL.

### 4.3 Timestral (Thermal) Specification
- **Sampling**: CPU temp (`/sys/class/thermal/thermal_zone*/temp`), CPU load (`/proc/stat`), CPU freq, mem/swap ratio, process count, GPU temp (`nvidia-smi`) every 30 s.
- **Adaptive advice**: `normal | fast | slow | pause` based on temperature thresholds (configurable). When advice is `pause` the orchestrator skips the tick; when `slow` the tick multiplier increases (less work per minute).
- **History**: 24 h of samples persisted in `state/timestral_history.json` (max 2880 samples).

## 5. Security Specifications (The "Rule 0")
Security is enforced at the **Tool Layer**, not the Prompt Layer.

### 5.1 Command Validation
- **No-Shell Policy**: All bash commands are tokenized and executed with `shell=False`.
- **Whitelist/Blacklist**: Commands are validated against a strict set of allowed patterns (e.g., `gcc`, `python`, `git status`). Forbidden: `sudo`, `curl`, `wget`, `ssh`, `nc`, `rm -rf`, `chmod`, pipes, redirects, `&&`, backticks.
- **Path Confinement**: All file operations are restricted to the `project/` directory. Path traversal (`..`), absolute paths, symlinks pointing outside, and sensitive names (`.env`, `.git-credentials`, `.ssh`) are blocked.
- **Always-on**: `[security] enabled = false` in `config.toml` is ignored and logged as CRITICAL.

### 5.2 Hardware Access (USB)
- **Passive Only**: Tools must only use read-only interfaces (`lsusb`, `tshark` via `usbmon`).
- **No Write**: Any attempt to send packets to the USB bus must be blocked at the tool level.

### 5.3 Prompt-Injection Resistance
- The worker's tool layer is the authority: even if a malicious task or model output tries to disable security, the tool layer refuses and logs.
- The `tests/test_security.py::TestAlwaysOnSecurity` suite verifies this with a mock model that obeys injection: the sentinel file survives, the policy stays active.

## 6. Functional Capabilities

### 6.1 Refactoring Suite
- **Symbol Renaming**: Global consistency across the project (`rename_symbol`).
- **Method Extraction**: Automatic decomposition of complex functions (`extract_method`).
- **Call Graph Analysis**: Impact analysis of changes (`get_call_graph`).
- **Complexity Metrics**: Identification of technical debt via cyclomatic complexity (`analyze_complexity`).
- **Precision Patching**: `patch_code` for targeted find-and-replace modifications.
- **Project Map**: `analyze_project`, `find_references`, `lint_code`, `run_test_suite`.

### 6.2 Quality Assurance (QA)
- **Audit Cycle**: Every piece of code is reviewed by a separate `AuditWorker` before being committed. Auto-APPROVE only if at least one useful tool (`write_file`, `patch_code`, `run_test_suite`, `lint_code`, `git_commit`, `rename_symbol`, `extract_method`) was called.
- **Static Analysis**: AST scanner on `write_file`; `Bandit` integration for SAST.
- **Circuit Breaker**: 3 identical tool calls (same name + args) force a mandatory prompt pivot.

### 6.3 Multilingual Intent Routing
- 28 intents × 3 languages (IT/EN/ZH), 314 triggers in `INTENT/intents.json`.
- Hybrid scoring: subset token match + token_set_ratio + partial_ratio + length bonus; CJK char-coverage fallback.
- Swarm commands (`swarm_status`, `list_tasks`, `show_logs`, `pause_swarm`, `resume_swarm`, `inspect_memory`, `cancel_task`, `run_audit`) are handled directly by the orchestrator without invoking any LLM.

### 6.4 Persistent Memory
- `CORE/persistent_memory.py` keeps: user profile, project context (existing files, main modules, dependencies), common errors (with recurrence count), recent files (last 10), task history (last 20).
- The worker loads this context at the start of every task and updates it on completion, so it does not recreate files that already exist and avoids repeating known errors.

### 6.5 Intelligent Model Selection
- `CORE/model_selector.py` scores every Ollama model 0–100 for each role (orchestrator, planner, worker_coder, worker_general, embedding, decision).
- Hard gates: reject if `model_size > VRAM × 0.75` or `model_size > RAM × 0.5` or wrong capability.
- Soft scoring: family match, preferred-name match, preferred capability (decision), quantization (Q4_K_M bonus, BF16 penalty), thermal penalty when GPU is hot.
- Returns top recommendation + 3 alternatives per role. CLI `--apply` writes to `CONFIG/config.toml` with backup.

### 6.6 Dynamic KV Cache Estimation
- `INTENT/metrics.py` estimates KV cache from the real formula `2 (K+V) × num_layers × num_kv_heads × head_dim × 2 (fp16) × tokens`, using a `MODEL_ARCHITECTURES` table for known models (qwen2.5, qwen3, phi3, llama3.2, deepseek-coder, mistral, codellama, tev1, …) and size-based heuristics for unknown ones.
- Replaces the old hardcoded `bytes_per_token` per family (was up to 15× wrong for phi3:mini).

### 6.7 Real-Time Streaming & Metrics
- `ollama_client.call_streaming()` yields tokens; the worker writes them to `state/streaming.txt`.
- The Live Activity Panel polls every 300 ms and shows: step counter, last tool call, LLM thought, streaming token preview, and metrics (tok/s, tokens in/out, TTFT, KV cache, VRAM of loaded models).
- Metrics are saved to `state/last_metrics.json` after every call.

## 7. Performance Constraints
- **Memory Ceiling**: Total system footprint must not exceed 4 GB RAM. Models are rotated to fit in 4 GB VRAM.
- **Thermal Throttling**: The system monitors CPU + GPU temperature and adjusts the orchestrator tick rate or pauses execution to prevent overheating.
- **Token Budget**: `MAX_STEPS = 6` per task, `max_tokens = 400` per step, `num_ctx = 3072`, `num_predict = 512` — tuned for small models on CPU/GPU-constrained hardware.
- **Disk Quota**: The project directory should be limited to prevent disk saturation attacks (planned, not yet enforced).

## 8. Error Handling
- **Fail-Closed**: Any security violation or sandbox failure must result in immediate task termination.
- **Instructive Errors**: Tool errors must be explicit, explaining the reason for the failure and suggesting the safe alternative.
- **Centralized Exception Policy**: planned (M2) — currently each call site handles its own exceptions.

## 9. Testing
- 55 tests pass: 27 security + 22 sandbox (11 subtests each) + 6 intent integration.
- `tests/run_tests.py --json` is the GUI runner; outputs a JSON report consumed by the "Test & Sandbox" tab.
- TDD enforcement in the worker is currently relaxed (warning only) because small models (1.5 B–4 B) struggle with the test-first workflow.

## 10. GUI Specification
- 7 tabs: Coda Task, Modelli, MCP Servers, Logs, Timestral (Termico), Config, Test & Sandbox.
- Toolbar: single Start/Stop toggle button (green when stopped, red when running), CPU/GPU temperature chips (green/orange/red), Exit.
- Status bar: orchestrator state + PID.
- Quick Command Bar: multilingual free-text input routed through the Intent Router; fallback to "Nuovo Task…" form when the router is unavailable.
- Live Activity Panel: 2-column layout beside the task table with streaming tokens, step, thought, tool call, metrics.
- ModelsTab: ComboBox per role populated from `ollama list`, Auto-Select button (applies `model_selector`), per-model Test button (measures tok/s), Save & Restart (writes config + restarts orchestrator). Config tab auto-reloads from disk when revisited.
- Themeable: dark (default) and light themes, persisted in `state/gui_theme.json`, toggle in toolbar.
