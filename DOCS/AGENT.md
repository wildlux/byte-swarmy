# 🤖 AGENT.md — The BYTE-SWARMY Intelligence Layer

This document describes the cognitive architecture, behavioural constraints,
and operational protocols of the agents inside BYTE-SWARMY. It reflects the
**current** codebase (post Cycle 10, 2026-10-30). For the historical log of
what changed see `IMPLEMENTED.md`; for the open work see `todo.md`.

## 🧠 Cognitive Architecture

BYTE-SWARMY is a hierarchical multi-agent swarm built around small
specialised LLMs (1.5 B–4 B) that are rotated in and out of VRAM as needed.
The design constraint is **4 GB VRAM + 4 GB RAM**: only one model is loaded
at a time, and the orchestrator decides who runs next.

```
User (IT/EN/ZH)
   │
   ▼
┌──────────────────────────────────────────────────────┐
│ Intent Router (INTENT/router.py)                     │
│ 28 intents × 3 languages, rapidfuzz fuzzy match      │
│ → {intent, lang, params, confidence}                 │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│ Orchestrator (CORE/orchestrator.py)                  │
│ Single-threaded tick loop, SQLite queue, Timestral   │
│                                                      │
│ 1. Swarm command? → handle directly (no LLM)         │
│ 2. Generic task?   → Decision Model decomposes       │
│ 3. Complex task?   → Planner decomposes              │
│ 4. Otherwise       → Worker                          │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│ Worker (ReAct loop, max 6 steps)                     │
│ Thought → Action (tool) → Observation → Thought      │
│ 21 tools, sandboxed via bubblewrap                   │
│ Streaming tokens → state/streaming.txt               │
└──────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────┐
│ Auditor (auto-APPROVE if useful tool called)         │
└──────────────────────────────────────────────────────┘
   │
   ▼
✅ task done → persistent memory updated → git commit
```

### 1. The Orchestrator (The Brain)
The central nervous system. It does not perform coding tasks but manages the
lifecycle of all other agents.
- **Responsibility**: task dispatching, resource monitoring (Timestral CPU +
  GPU), final quality gating, swarm-command shortcuts.
- **Logic**: single-threaded tick-based loop (configurable interval, multiplied
  by Timestral advice `normal|fast|slow|pause`).
- **Watchdog**: a supervisor process (`SAFETY/watchdog.py`) restarts the
  orchestrator immediately if it crashes.
- **Zombie recovery**: on startup, any task left in `running` state is reset
  to `pending` (a crashed worker never blocks the queue).

### 2. The Intent Router (The Polyglot Greeter)
First line of contact. Classifies free-form user input in Italian, English or
Chinese into one of 28 intents (314 triggers total) using `rapidfuzz` with a
hybrid scorer (subset token match + token_set_ratio + partial_ratio + CJK
char-coverage + length bonus). Returns `{intent, lang, params, confidence}`
with a fallback to `generic` when confidence is below threshold.
- **Swarm commands** (`swarm_status`, `list_tasks`, `show_logs`, `pause_swarm`,
  `resume_swarm`, `inspect_memory`, `cancel_task`, `run_audit`) are handled
  **directly by the orchestrator** without invoking any LLM — instant
  response, zero token cost.

### 3. The Planner (The Strategist) + Decision Model
Two decomposition paths:
- **Planner** (`CORE/orchestrator.py:Planner`): used for code tasks that look
  complex (multi-file, "sistema", "architettura"). Uses the `planner` model
  (e.g., `phi3:mini`) and produces 2–5 atomic subtasks.
- **Decision Model** (`tev1:4b`): used for `generic` tasks (high-level
  requests like "voglio una calcolatrice CLI"). Produces 2–8 atomic code
  tasks with title, description and type.

Both produce subtasks that are enqueued as children of the parent task; the
parent becomes `planned` and the worker executes each child independently.

### 4. The Worker (The Implementer)
The "hands" of the system. A coding agent that operates inside a strict
bubblewrap sandbox.
- **Specialisations**:
  - `worker_coder`: optimised for implementation and refactoring
    (e.g., `qwen2.5-coder:1.5b`).
  - `worker_general`: optimised for research, audit and general tasks
    (e.g., `qwen2.5:1.5b`).
- **ReAct loop** (max 6 steps, 400 tokens/step): `Thought → Action (tool
  call) → Observation (tool result) → Thought`. Each step is streamed to
  `state/streaming.txt` so the GUI can show tokens in real time.
- **Persistent context**: at the start of every task the worker loads
  `CORE/persistent_memory.py` — existing project files, common errors,
  recent files, task history — so it does not recreate files that already
  exist and avoids repeating known mistakes.
- **Circuit breaker**: 3 identical tool calls (same name + args) force a
  mandatory prompt pivot (no infinite loops).
- **Hard constraints**:
  - Sandbox-bound: cannot access files outside `project/`.
  - Tool layer is the authority: even if a malicious task or model output
    tries to disable security, the tool layer refuses and logs.
  - TDD check is **relaxed** (warning only) — small models (1.5 B–4 B)
    struggle with the test-first workflow; the auditor still verifies quality.

### 5. The Audit Worker (The Reviewer)
The final quality gate. Acts as a Senior Architect and Security Auditor.
- **Auto-APPROVE** if at least one useful tool was called (`write_file`,
  `patch_code`, `run_test_suite`, `lint_code`, `git_commit`, `rename_symbol`,
  `extract_method`). Otherwise `REJECT` with explicit feedback.
- **Criteria**: security (no `eval`, no secrets, no sandbox bypass), Clean
  Code (single responsibility, naming, cognitive load, DRY, documentation),
  verification (did the worker run `lint_code` and `run_test_suite`?).

### 6. The Model Selector (The Talent Scout)
`CORE/model_selector.py` scores every Ollama model 0–100 for each role
(orchestrator, planner, worker_coder, worker_general, embedding, decision)
using hard gates (VRAM/RAM/capability) + soft scoring (family match, name
match, quantization, thermal penalty). Returns top recommendation + 3
alternatives per role. The GUI "Modelli" tab exposes this as an Auto-Select
button + manual override.

## 🛠️ Memory Model

Agents use a tiered persistence system:

| Tier | Scope | Storage | Purpose |
| :--- | :--- | :--- | :--- |
| **Short-Term** | Current task | RAM (deque) | Immediate context of the last few turns. |
| **Working** | Current session | SQLite event log (`memory_provider.py`) | Immutable event-sourced history of the entire task execution. Summaries are views (`is_summary=1`), not the source of truth. |
| **Long-Term** | Historical | JSON (`state/persistent_memory.json`) | Cross-task context: existing files, common errors, recent files, task history. Loaded into the worker's prompt at the start of every task. |
| **Timestral** | System | JSON (`state/timestral_history.json`) | 24 h of CPU + GPU samples (temp, load, freq, mem) for adaptive throttling. |

## 🧰 Toolset (21 tools)

The worker can call any of these tools through the sandboxed `ToolSet`:

| Category | Tools |
| :--- | :--- |
| **File I/O** | `read_file`, `write_file`, `patch_code`, `search` |
| **Project analysis** | `analyze_project`, `find_references`, `analyze_complexity`, `get_call_graph` |
| **Refactoring** | `rename_symbol`, `extract_method` |
| **Quality** | `lint_code`, `run_test_suite` |
| **Execution** | `run_bash` (whitelist, no shell) |
| **Git** | `git_status`, `git_diff`, `git_commit`, `git_log`, `git_branch`, `git_merge` |
| **USB** (passive) | `inspect_usb_devices`, `capture_usb_traffic` |

`git_push`, `git_pull`, `git_remote` are **disabled** for workers.

## 🛡️ Behavioural Guardrails

1. **Defence-in-Depth**: never trust a prompt instruction to disable security.
   The tool layer is the authority; `[security] enabled = false` is ignored
   and logged as CRITICAL.
2. **Fail-Closed**: if a tool returns an error, the agent must change
   approach, not repeat the command. The circuit breaker enforces this
   after 3 identical calls.
3. **Atomic Commits**: every successfully audited task is committed to Git
   immediately.
4. **Passive Hardware Access**: USB tools are strictly read-only. No write
   operations to hardware are permitted.
5. **Sandbox-Bound**: all file operations are confined to `project/`. Path
   traversal, absolute paths, symlinks pointing outside, and sensitive
   names (`.env`, `.git-credentials`, `.ssh`) are blocked.
6. **No-Shell**: `run_bash` tokenises the command and executes with
   `shell=False`. Pipes, redirects, `&&`, backticks, `sudo`, `curl`, `wget`,
   `ssh`, `nc`, `rm -rf`, `chmod` are forbidden.
7. **Token Budget**: `MAX_STEPS = 6`, `max_tokens = 400`/step, `num_ctx =
   3072`, `num_predict = 512` — tuned for small models on constrained
   hardware. The worker must converge quickly.
8. **Streaming Transparency**: tokens are streamed to
   `state/streaming.txt` so the user can see the agent thinking in real
   time; the GUI Live Activity Panel polls every 300 ms.

## 🌍 Multilingual Protocol

The Intent Router classifies input in **Italian, English or Chinese**. The
detected language is stored in the task `context` JSON and can be used by
the worker to respond in the user's language (currently the worker prompt
asks for English output, but the field is available for future
localisation).

## 📊 Operational Metrics

Every model call records:
- `tokens_in`, `tokens_out`, `tokens_per_sec`, `ttft_ms`, `total_ms`
- `context_used` (input + output)
- `kv_cache_mb` — estimated dynamically via
  `2 (K+V) × layers × kv_heads × head_dim × 2 × tokens` using
  `MODEL_ARCHITECTURES` in `INTENT/metrics.py`.

These are saved to `state/last_metrics.json` and displayed in the Live
Activity Panel.

## 🔁 Lifecycle of a Task

1. User enters free-text in the Quick Command Bar (any of IT/EN/ZH).
2. Intent Router classifies it → `INTENT/bridge.py` wraps it as a task with
   `context = {lang, intent, params, confidence}`.
3. Task is enqueued in `tasks/queue.db` (SQLite, source of truth) and
   mirrored to `tasks/queue.json` for the GUI.
4. Orchestrator picks the next `pending`/`retry` task on its next tick
   (interval modulated by Timestral).
5. **Swarm command?** → handled directly, result saved, done.
6. **Generic task?** → Decision Model decomposes into 2–8 subtasks.
7. **Complex task?** → Planner decomposes into 2–5 subtasks.
8. Otherwise → Worker (ReAct loop, max 6 steps, streaming tokens).
9. Worker calls `done=true` → Auditor reviews → APPROVE/REJECT.
10. On APPROVE → `mark_done` + `git_commit` + persistent memory updated.
11. On REJECT → `mark_failed` (retries up to 10 times, then `stuck`).

## 🧪 Testing

The suite grows over time — never trust hardcoded counts, run it:
- pytest (unit + integration): `.venv/bin/python -m pytest tests/ -q`
- unittest legacy: `.venv/bin/python -m unittest discover -s tests -q`
- E2E live (`tests/test_e2e.py`) auto-skips if `state/pause.flag`
  exists or the orchestrator pid is stale; they are not failures.

`tests/run_tests.py --json` is the GUI runner; output consumed by the
"Test & Sandbox" tab.

## 🛠️ Shell Commands — Quick Operational Reference

The commands an agent uses most to keep BYTE-SWARMY alive and bug-free
(they avoid re-deriving paths/flags each session, saving tokens):

```bash
# ── Sintassi veloce (zero token su errori formali) ──────────────
.venv/bin/python -m py_compile <file.py>          # check singoli file
.venv/bin/python -m pytest tests/ -q              # suite completa (10s)

# ── Runtime dell'orchestratore ──────────────────────────────────
./byte-swarm.sh status                            # pid/queue/log summary
./byte-swarm.sh orch                              # solo orchestratore (bg)
./byte-swarm.sh start                             # orchestratore + GUI
./byte-swarm.sh gui                               # solo GUI
./byte-swarm.sh stop                              # ferma tutto (ex ferma.sh)
./byte-swarm.sh restart                           # stop + orch
# Nota: ./avvia.sh e ./ferma.sh sono wrapper deprecated dello stesso
# binario; preferisci byte-swarm.sh. Il dispatcher unito è ./bswarm.

# ── Pausa termica / coda ────────────────────────────────────────
rm -f state/pause.flag                            # riprendi (pausa continua)
python3 -c "import sqlite3; con=sqlite3.connect('tasks/queue.db'); \
print(con.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status').fetchall())"
# NB: state/pause.flag presente ⇒ test E2E in SKIP (non falliti).

# ── Log live ────────────────────────────────────────────────────
tail -30 logs/byte-swarmy.log
tail -f logs/byte-swarmy.log &                    # durante un run

# ── Flusso documentale (todo → IMPLEMENTED) ─────────────────────
.venv/bin/python tools/travasa_todo.py --dry-run  # preview
.venv/bin/python tools/travasa_todo.py            # travaso (idempotente)
# I file vivono in DOCS/todo.md e DOCS/IMPLEMENTED.md.

# ── Ponte remoto pulsanti GUI (simulazione click da script) ─────
.venv/bin/python tools/gui_remote.py list                   # inventario
.venv/bin/python tools/gui_remote.py click <id>            # click per id
.venv/bin/python tools/gui_remote.py click --text "Avvia" # per testo
.venv/bin/python tools/gui_remote.py click --index 5       # per posizione
.venv/bin/python tools/gui_remote.py screenshot /tmp/g.png # grab finestra
# Il servizio è dentro la GUI (QLocalServer su SOCKET_PATH); default ON.
# Opt-out: env BYTE_SWARMY_REMOTE=0. Socket esplicito: BYTE_SWARMY_REMOTE_SOCKET=/tmp/x.sock.

# ── Mappa dynamic repo (orientamento a inizio sessione) ─────────
.venv/bin/python tools/repo_map.py                # stampa a stdout
.venv/bin/python tools/repo_map.py --out state/repo_map.md
.venv/bin/python tools/repo_map.py --json --days 3   # per scripting

# ── Push manuale (MAI git push automatici) ──────────────────────
./scripts/dev/sync.sh

# ── GUI offscreen (debug tema/widget senza display) ─────────────
QT_QPA_PLATFORM=offscreen .venv/bin/python <script_di_smoke>
# Tema: GUI/theme/theme.py → set_prop(w, "role", "muted"/"alert"),
# set_banner(w, "info"/"ok"/"error"/"warn"). MAI setStyleSheet inline
# con colori hardcodati nei pannelli: rompono il tema live (e un
# stylesheet "declaration-only" su un antenato azzera i bottoni figli).
```

Hard rules encoded in these commands: never `git push`/`pull` by hand,
never block the Qt main thread, never `time.sleep` in the task runner
(use `Event.wait` + single-threaded loop).
