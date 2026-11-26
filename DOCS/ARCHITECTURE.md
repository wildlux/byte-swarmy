# 🧠 BYTE-SWARMY — Architettura

> Documento esteso per umani e manutentori. Le **regole operative** che i
> modelli piccoli (1.5B–4B) devono vedere restano in [`AGENT.md`](../AGENT.md);
> qui vivono architettura, memoria, tool, threat model, metriche, lifecycle e
> prompt engineering. Comandi e protocolli operativi: [`OPERATIONS.md`](OPERATIONS.md).

---

## 1. Cognitive Architecture

BYTE-SWARMY is a hierarchical multi-agent swarm built around small specialised
LLMs (1.5B–4B) that are rotated in and out of VRAM as needed. The design
constraint is **4 GB VRAM + 4 GB RAM**: only one model is loaded at a time, and
the orchestrator decides who runs next.

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
│ Worker (ReAct loop, MAX_STEPS = 10)                  │
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

### 1.1 The Orchestrator (The Brain)

The central nervous system. It does not perform coding tasks but manages the
lifecycle of all other agents.

- **Responsibility**: task dispatching, resource monitoring (Timestral CPU +
  GPU), final quality gating, swarm-command shortcuts.
- **Logic**: single-threaded tick-based loop (configurable interval, multiplied
  by Timestral advice `normal|fast|slow|pause`).
- **Watchdog**: a supervisor process (`SAFETY/watchdog.py`) restarts the
  orchestrator immediately if it crashes.
- **Zombie recovery**: on startup, any task left in `running` state is reset to
  `pending` (a crashed worker never blocks the queue).

### 1.2 The Intent Router (The Polyglot Greeter)

First line of contact. Classifies free-form user input in Italian, English or
Chinese into one of 28 intents (314 triggers total) using `rapidfuzz` with a
hybrid scorer (subset token match + token_set_ratio + partial_ratio + CJK
char-coverage + length bonus). Returns `{intent, lang, params, confidence}` with
a fallback to `generic` when confidence is below threshold.

- **Swarm commands** (`swarm_status`, `list_tasks`, `show_logs`, `pause_swarm`,
  `resume_swarm`, `inspect_memory`, `cancel_task`, `run_audit`) are handled
  **directly by the orchestrator** without invoking any LLM — instant response,
  zero token cost.

### 1.3 The Planner (The Strategist) + Decision Model

Two decomposition paths:

- **Planner** (`CORE/orchestrator.py:Planner`): used for code tasks that look
  complex (multi-file, "sistema", "architettura"). Uses the `planner` model
  (e.g., `phi3:mini`) and produces 2–5 atomic subtasks.
- **Decision Model** (`tev1:4b`): used for `generic` tasks (high-level requests
  like "voglio una calcolatrice CLI"). Produces 2–8 atomic code tasks with
  title, description and type.

Both produce subtasks that are enqueued as children of the parent task; the
parent becomes `planned` and the worker executes each child independently.

### 1.4 The Worker (The Implementer)

The "hands" of the system. A coding agent that operates inside a strict
bubblewrap sandbox.

- **Specialisations**:
  - `worker_coder`: optimised for implementation and refactoring
    (e.g., `qwen2.5-coder:3b` — 10/10 on the T1–T10 suite).
  - `worker_granite`: complexity-routing heavy for high-impact tasks
    (e.g., `granite4:7b-a1b-h`, MoE ~1B active params — verified first attempt
    on the heavy spot-check).
  - `worker_general`: optimised for research, audit and general tasks
    (e.g., `qwen2.5:1.5b`).
- **ReAct loop** (`MAX_STEPS = 10`, 400–1024 tokens/step): `Thought → Action
  (tool call) → Observation (tool result) → Thought`. Each step is streamed to
  `state/streaming.txt` so the GUI can show tokens in real time.
- **Persistent context**: at the start of every task the worker loads
  `CORE/persistent_memory.py` — existing project files, common errors, recent
  files, task history — so it does not recreate files that already exist and
  avoids repeating known mistakes.
- **Circuit breaker**: 3 identical tool calls (same name + args) force a
  mandatory prompt pivot (no infinite loops).
- **Hard constraints**:
  - Sandbox-bound: cannot access files outside `project/`.
  - Tool layer is the authority: even if a malicious task or model output tries
    to disable security, the tool layer refuses and logs.
  - TDD check is **relaxed** (warning only) — small models (1.5B–4B) struggle
    with the test-first workflow; the auditor still verifies quality.

### 1.5 The Audit Worker (The Reviewer)

The final quality gate. Acts as a Senior Architect and Security Auditor.

- **Auto-APPROVE** if at least one useful tool was called (`write_file`,
  `patch_code`, `run_test_suite`, `lint_code`, `git_commit`, `rename_symbol`,
  `extract_method`). Otherwise `REJECT` with explicit feedback.
- **Criteria**: security (no `eval`, no secrets, no sandbox bypass), Clean Code
  (single responsibility, naming, cognitive load, DRY, documentation),
  verification (did the worker run `lint_code` and `run_test_suite`?).

### 1.6 The Model Selector (The Talent Scout)

`CORE/model_selector.py` scores every Ollama model 0–100 for each role
(orchestrator, planner, worker_coder, worker_general, embedding, decision)
using hard gates (VRAM/RAM/capability) + soft scoring (family match, name
match, quantization, thermal penalty). Returns top recommendation + 3
alternatives per role. The GUI "Modelli" tab exposes this as an Auto-Select
button + manual override.

---

## 2. Memory Model

Agents use a tiered persistence system:

| Tier | Scope | Storage | Purpose |
| :--- | :--- | :--- | :--- |
| **Short-Term** | Current task | RAM (deque) | Immediate context of the last few turns. |
| **Working** | Current session | SQLite event log (`memory_provider.py`) | Immutable event-sourced history of the entire task execution. Summaries are views (`is_summary=1`), not the source of truth. |
| **Long-Term** | Historical | JSON (`state/persistent_memory.json`) | Cross-task context: existing files, common errors, recent files, task history. Loaded into the worker's prompt at the start of every task. |
| **Timestral** | System | JSON (`state/timestral_history.json`) | 24 h of CPU + GPU samples (temp, load, freq, mem) for adaptive throttling. |

---

## 3. Toolset (21 tools)

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

---

## 4. Sicurezza — Threat Model e Procedure

### 4.1 Modello delle minacce

| Minaccia | Vettore | Mitigazione nel progetto |
|---|---|---|
| Prompt injection | Input utente al LLM | Intent Router classifica, non esegue direttamente; tool layer è authority |
| Codice maligno generato | Output LLM → ToolSet | `detect_artifacts()` blocca prima dell'esecuzione; bubblewrap sandbox |
| Escape dalla sandbox | Bubblewrap fallisce | `safe_project_path` confina path; `for_write` blocca symlink; watchdog riavvia |
| Esfiltrazione dati | Worker di rete | `run_bash` blocca curl/wget/ssh/nc; nessuna rete in sandbox |
| Compromissione modello Ollama | Model file manomessi | Verifica header GGUF; `hf_weights` importa solo GGUF da HF |
| Segreti esposti | Token in config/log | `security.py` maschera i segreti; nessun segreto in chiaro nei log |
| Supply chain | Dipendenze esterne | `requirements*.txt` pinned; `security_scan.py` pattern pericolosi |
| Loop infinito LLM | Codice generato ripetitivo | `repeat_penalty`, `MAX_STEPS = 10`, circuit breaker (3 chiamate identiche) |

### 4.2 Principi di sicurezza (hard rules)

1. **Fail-Closed**: se un tool fallisce o bubblewrap non è disponibile, il
   comando NON viene eseguito.
2. **Defense-in-Depth**: nessun singolo livello è sufficiente; input
   validation + sandbox + audit sono indipendenti.
3. **Least Privilege**: worker gira con PID/namespace separati, filesystem
   minimo, home volatile.
4. **No-Shell**: `run_bash` tokenizza e usa `shell=False`; pipe, redirect,
   `&&`, `sudo`, `curl`, `wget`, `ssh`, `nc`, `rm -rf`, `chmod` sono vietati.
5. **Never Trust Prompt**: le istruzioni nell'input utente non possono
   disabilitare la sicurezza (`[security] enabled = false` è ignorato e
   loggato come CRITICAL).
6. **Atomic Commits**: nessun task è considerato fatto senza git commit dopo
   audit APPROVE.

### 4.3 Procedure di emergenza

| Scenario | Azione |
|---|---|
| Orchestratore crashato | Watchdog (`SAFETY/watchdog.py`) riavvia subito; task in `running` tornano `pending` |
| Bubblewrap non disponibile | `run_bash` fail closed (non esegue); log evento sicurezza |
| LLM genera loop | Circuit breaker dopo 3 chiamate identiche; `repeat_penalty` aggressivo |
| Task bloccato (`stuck`) | Max 10 retry, poi `stuck`; richiede intervento umano |
| Sospetto compromissione | Fermare swarm (`./byte-swarm.sh stop`), ispezionare `logs/security.log`, rimuovere task sospetti |

### 4.4 Gestione segreti

- Nessun token o password in chiaro nei log (`logs/security.log` maschera i
  segreti).
- `HF_TOKEN` per modelli gated su Hugging Face: passare via variabile
  d'ambiente, mai hardcodato.
- `CONFIG/settings.json` non deve contenere token in chiaro; usare `git_remotes`
  con token solo se necessario e ruotarli.

### 4.5 Audit di sicurezza ricorrente

- **Ogni sessione**: controllare `logs/security.log` per eventi critici.
- **Ogni rilascio**: eseguire `tools/security_scan.py`, `tools/lint_style.py`,
  `tools/git_hygiene.py`.
- **Mensile**: `tests/test_monthly_audit.py` + `AuditGate` per porte esposte,
  codice morto, import banditi, reverse proxy (ngrok, cloudflared, ssh -R,
  docker -p).

### 4.6 Checklist pre-commit / pre-release

- [x] `py_compile` su tutti i file modificati
- [ ] `pytest tests/ -q` passa (la suite cresce: non fidarsi di conteggi
      hardcoded, eseguirla)
- [ ] Nessun segreto in chiaro in `CONFIG/` o `logs/`
- [ ] `safe_project_path` usato per ogni path da input utente
- [ ] Nessuna chiamata `curl`/`wget`/`ssh`/`sudo` in `run_bash` allowlist
- [ ] Nuovi tool registrati in `TOOL_REGISTRY` hanno validazione path

### 4.7 Relazione con i moduli di sicurezza esistenti

- `SAFETY/security.py` — `safe_project_path`, `is_sensitive_path`,
  `validate_bash_command`, `log_security_event`
- `SAFETY/security_checks.py` — check automatizzati
- `SAFETY/watchdog.py` — monitoraggio e riavvio orchestrator
- `CORE/sandbox.py` / `CORE/sandbox_selftest.py` — isolamento esecuzione
- `CORE/audit_gate.py` — quality gate prima del commit

---

## 5. Multilingual Protocol

The Intent Router classifies input in **Italian, English or Chinese**. The
detected language is stored in the task `context` JSON and can be used by the
worker to respond in the user's language (currently the worker prompt asks for
English output, but the field is available for future localisation).

---

## 6. Operational Metrics

Every model call records:

- `tokens_in`, `tokens_out`, `tokens_per_sec`, `ttft_ms`, `total_ms`
- `context_used` (input + output)
- `kv_cache_mb` — estimated dynamically via
  `2 (K+V) × layers × kv_heads × head_dim × 2 × tokens` using
  `MODEL_ARCHITECTURES` in `INTENT/metrics.py`.

These are saved to `state/last_metrics.json` and displayed in the Live Activity
Panel.

---

## 7. Lifecycle of a Task

1. User enters free-text in the Quick Command Bar (any of IT/EN/ZH).
2. Intent Router classifies it → `INTENT/bridge.py` wraps it as a task with
   `context = {lang, intent, params, confidence}`.
3. Task is enqueued in `tasks/queue.db` (SQLite, source of truth) and mirrored
   to `tasks/queue.json` for the GUI.
4. Orchestrator picks the next `pending`/`retry` task on its next tick
   (interval modulated by Timestral).
5. **Swarm command?** → handled directly, result saved, done.
6. **Generic task?** → Decision Model decomposes into 2–8 subtasks.
7. **Complex task?** → Planner decomposes into 2–5 subtasks.
8. Otherwise → Worker (ReAct loop, `MAX_STEPS = 10`, streaming tokens).
9. Worker calls `done=true` → Auditor reviews → APPROVE/REJECT.
10. On APPROVE → `mark_done` + `git_commit` + persistent memory updated.
11. On REJECT → `mark_failed` (retries up to 10 times, then `stuck`).
12. **Routing per complessità (live only):** prima dell'esecuzione diretta il
    sistema stima keyword + IMPATTO reale (`CORE/routing.py`, grafo del
    code_map: simboli citati → file toccati, BFS a valle). Livello `alta` →
    `worker_granite` (granite4:7b-a1b-h) se installato, con isteresi sticky
    (`media` resta heavy, `bassa` torna al base); fail-open.
13. **Fallback modello:** se `worker_coder` (qwen2.5-coder:3b, GPU) fallisce
    definitivamente, il task viene rimesso in `pending` e rieseguito con
    `worker_general` (qwen2.5:1.5b, RAM) come secondo tentativo.

---

## 8. Schema consigliato (4 GB RAM / 4 GB VRAM)

```
Router (qwen2.5:0.5b, RAM)  →  Routing per complessità  →  Verifica (gate statici + runtime)
                                ├─ semplice/media → Coder 3B Q4_K_M (GPU) · 10/10 suite T1–T10
                                └─ alta (keyword o impatto ≥2 file) → granite4:7b-a1b-h (heavy)
                                        ↓ heavy non installato: fallback automatico sul 3B
        task comunque fallito → worker_general (RAM) come secondo tentativo
```

I due coder sono della stessa famiglia e sbagliano in modo simile; per la
diversità si può aggiungere un modello di un'altra famiglia (es.
`deepseek-coder:1.3b`).

---

## 9. Testing

The suite grows over time — never trust hardcoded counts, run it:

- pytest (unit + integration):
  `.venv/bin/python -m pytest tests/ -q --durations=15`
  (regola operativa: ogni run completo registra i 15 test più lenti con i loro
  tempi; il report `--durations` è obbligatorio per le sessioni di benchmark)
- unittest legacy:
  `.venv/bin/python -m unittest discover -s tests -q`
- E2E live (`tests/test_e2e.py`) auto-skips if `state/pause.flag` exists or the
  orchestrator pid is stale; they are not failures.

`tests/run_tests.py --json` is the GUI runner; output consumed by the
"Test & Sandbox" tab.

---

## 10. Prompt Engineering per modelli piccoli (1.5B–4B)

I modelli piccoli (Qwen2.5 1.5B, phi3:mini, ecc.) hanno meno capacità di
ragionamento, contesto ridotto e tendenza a ignorare istruzioni complesse.
Queste regole valgono per ogni prompt inviato a Ollama:

### 10.1 Istruzioni brevi e vincolanti

- Una sola istruzione per frase.
- Usa maiuscole per le regole critiche (es. "RISPONDI SOLO CON...").
- Non chiedere "spiega passo dopo passo" se non serve: i modelli piccoli si
  perdono nei ragionamenti lunghi. Preferisci output diretto.

### 10.2 Formato di output rigido

- Specifica esattamente cosa vuoi: JSON, elenco puntato, singola parola,
  blocco di codice Python.
- Esempio: "RISPONDI SOLO con: {\"subtasks\": [...]}"
- Se serve JSON, non aggiungere testo prima o dopo. Il sistema usa
  `CORE/regex_controller.py:json_block()` per estrarre il primo blocco `{...}`
  o `[...]` da output misto.

### 10.3 Few-shot (esempi concreti)

- Fornisci 1-2 esempi input/output direttamente nel prompt.
- I modelli piccoli imparano meglio dagli esempi che dalle istruzioni astratte.

### 10.4 Separazione istruzioni/dati

- Usa delimitatori chiari: `### INPUT`, `### OUTPUT`, `---`.
- Non mescolare le regole con il codice da analizzare.

### 10.5 Parametri Ollama consigliati

| Parametro | Valore | Motivo |
|-----------|--------|--------|
| `temperature` | 0.1–0.2 | Determinismo per task di codice |
| `num_predict` | 256–512 | Evita output infiniti su modelli piccoli |
| `num_ctx` | 2048–3072 | Contesto ridotto, più veloce |
| `repeat_penalty` | 1.1–1.15 | Evita loop di ripetizione |
| `seed` | fisso (es. 42) | Riproducibilità |

### 10.6 Gestione errori e retry

- Se il modello non rispetta il formato, non ripetere lo stesso prompt:
  aggiungi un'istruzione di correzione (es. "Il formato precedente era
  sbagliato. RISPONDI SOLO con JSON valido.").
- L'orchestratore già gestisce retry fino a `max_task_retries` con prompt di
  correzione automatico.

### 10.7 Think tags (Qwen3)

Se usi modelli Qwen3, racchiudi il ragionamento in `<thinking>...</thinking>` e
l'output finale fuori dai tag. Il sistema estrae solo il contenuto fuori dai
tag per l'esecuzione.

---

## 11. Strumenti per migliorare l'output prodotto

Questi moduli e pratiche esistono già nel progetto per validare, correggere e
migliorare ciò che i modelli generano:

### 11.1 Parsing robusto (`CORE/regex_controller.py`)

- `json_block(testo)` → estrae il primo blocco JSON `{...}` o `[...]` da output
  LLM misto (usato dall'orchestratore in 4 punti).
- `number_after_label(testo, "RISULTATO")` → estrae numeri etichettati.
- `RegexController` → registro di pattern precompilati per nome (py_def,
  json_object, code_fenced, …).

### 11.2 Selezione modello (`CORE/model_selector.py`)

- Punteggia ogni modello 0–100 per ruolo (orchestrator, planner, worker_coder,
  worker_general, decision) usando hard gates (VRAM/RAM/capabilità) e soft
  scoring.
- Usa `get_recommendations()` per scegliere il modello giusto prima di inviare
  il prompt.

### 11.3 Tuning termico (`CORE/llm_tuner.py`, Timestral)

- Aggiusta temperatura/num_predict in base alla temperatura CPU/GPU.
- Sistema caldo → output più breve e deterministico (meno KV cache, meno spill
  su CPU).

### 11.4 Qualità del codice (`SAFETY/security.py`, `CORE/ast_scanner.py`)

- `detect_artifacts()` blocca codice sospetto prima dell'esecuzione.
- `lint_code` e `run_test_suite` sono gate di qualità obbligatori prima
  dell'approvazione del task.

### 11.5 Audit finale (`CORE/orchestrator.py` Auditor)

- APPROVE solo se almeno un tool utile è stato chiamato.
- Altrimenti REJECT con feedback esplicito.

### 11.6 Streaming e feedback

- I token vengono scritti in `state/streaming.txt` e mostrati nella GUI Live
  Activity Panel ogni 300 ms, così l'utente vede il progresso in tempo reale.

---

## 12. GUI Control Center — note

- **Barra "Lavori e compiti"**: pulsante toggle ☑ "Seleziona/deseleziona tutti"
  a destra (accanto a 🔄 ➕ 🗑️ 🧹), agisce sulle checkbox dei task
  (`FileTreeDrawer._toggle_select_all_tasks`).
- **Plancia di controllo**: triangolo "arrotola" (▾/▸) allineato in alto a
  destra (`CollapsibleSection.toggle_btn` con `Qt.AlignmentFlag.AlignTop`);
  header più compatto (minHeight 40px, margini 6px) e rimosso lo spazio vuoto
  sopra il contenuto (`content_lay` margine-top 6px) → più spazio per i menù
  rettangoli (card) sottostanti.
- **Zoom reale**: `_apply_zoom` riscala i font-size hard-coded (px e pt) negli
  stylesheet inline per-widget e nel QSS della finestra a partire da base 100%
  (fattore assoluto `level/100`, zero drift composto). Catch-up periodico
  (1,5s) scala i widget creati dopo lo zoom (pannelli aperti dai menu, sezioni
  CPU/GPU ricreate). Barra zoom `[-][%][+]` con etichetta percentuale live.
  Scorciatoie: `Ctrl++` / `Ctrl+−` / `Ctrl+0` (`_ZoomEventFilter` globale +
  `keyPressEvent`, funzionano anche con focus su `QLineEdit`). Zoom persistito
  in `CONFIG/settings.json` (`settings_store.get_zoom_level`/
  `set_zoom_level`).
- **QSplitter verticale** tra file tree e lista task (metà/metà di default,
  ridimensionabile dall'utente, dimensioni persistenti in
  `state/splitter_vertical_state.json`).
- **Usabilità plancia**: badge testo bianco su colore solido (contrasto sempre
  leggibile), badge dimensione fissa, titoli troncati con elipsis + tooltip,
  tooltip sui valori CPU/GPU (2.1G, 65%, 800M…), filtro categorie "Tutte le
  categorie" accanto alla ricerca, barra avanzamento "Pronto" a riposo,
  larghezza minima pannello sinistro adeguata allo zoom, scrollbar visibile
  sull'area card.
- **Bug CPU/GPU valori identici**: `kv`/`mem`/`bus` erano segnaposto hardcoded
  (2.1G, 65%, 800M) uguali per entrambi i box. Ora leggono valori reali: RAM %
  da `/proc/meminfo`, GPU mem % e frequenza da `nvidia-smi`, KV cache stimata
  da `context_used` + architettura modello
  (`INTENT.metrics.estimate_kv_cache_mb`). Mostrano `-` quando il dato non è
  disponibile.
- **Rimossi ultimi valori hardcoded**: inizializzazioni `self._cpu_temp`,
  `self._gpu_temp`, `self._tok_s`, `self._kv`, `self._mem`, `self._freq` e le
  label iniziali di `_device_row` usano valori neutri (`0`, `0.0`, `-`) invece
  di segnaposto fittizi (45°C, 12t/s, 2.1G, 65%, 800M).
