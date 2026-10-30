# BYTE-SWARMY

<p align="center">
  <img src="IMG/documentazione.jpeg" alt="BYTE-SWARMY — Swarm autonomo locale" width="720">
</p>

<p align="center">
  <strong>Sistema multi-agente autonomo, interamente locale, per macchine con 4 GB di RAM.</strong>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-0.3.0-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-yellow">
  <img alt="Ollama" src="https://img.shields.io/badge/Ollama-required-orange">
  <img alt="RAM" src="https://img.shields.io/badge/RAM-4%20GB%20min-red">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Linux-lightgrey">
  <img alt="Cloud" src="https://img.shields.io/badge/cloud-NOT%20needed-success">
  <img alt="Tests" src="https://img.shields.io/badge/tests-58%20pass-brightgreen">
</p>

<p align="center">
  <em>"The swarm works. You think elsewhere."</em>
</p>

---

> **Nessun cloud, nessuna dipendenza da servizi esterni:**
> solo Ollama, Python e SQLite/JSON. I worker eseguono task di programmazione,
> test e documentazione sotto il controllo di un orchestratore deterministico,
> con streaming token in tempo reale, selezione intelligente dei modelli e
> ottimizzazione termica adattiva (Timestral LLM Tuner).

**Versione:** 0.3.0 · **Licenza:** MIT · **Piattaforma:** Linux

---

## Indice

- [Sicurezza](#sicurezza)
- [Panoramica](#panoramica)
- [Perché BYTE-SWARMY?](#perché-byte-swarmy)
- [Demo](#demo)
- [Architettura](#architettura)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio rapido](#avvio-rapido)
- [Utilizzo](#utilizzo)
- [Come funziona](#come-funziona)
- [Sicurezza in profondità](#sicurezza-in-profondità)
- [Struttura del progetto](#struttura-del-progetto)
- [Sviluppo e test](#sviluppo-e-test)
- [Limiti noti](#limiti-noti)
- [Troubleshooting](#troubleshooting)
- [Compatibilità](#compatibilità)
- [Contribuire](#contribuire)
- [Licenza](#licenza)
- [Ringraziamenti](#ringraziamenti)

---

## Sicurezza

> **Regola 0 — la difesa è sempre attiva.**
> Ogni task è trattato come potenzialmente ostile (prompt injection). La policy
> di sicurezza è applicata nel codice a ogni chiamata di tool e **non può essere
> disattivata** da configurazione, prompt, task MCP o output del modello.

BYTE-SWARMY esegue codice generato da LLM piccoli con i permessi dell'utente che
avvia l'orchestratore. Le protezioni incluse bloccano i comandi più pericolosi,
ma **non sostituiscono un isolamento di sistema**:

- `run_bash` non usa una shell: allowlist, blacklist e path confinati in `project/`;
- sandbox bubblewrap: filesystem isolato, rete bloccata, PID/user namespace separati;
- escape `/etc` bloccato (`--tmpfs /etc` + `--remount-ro`);
- `git push` / `pull` / `remote add|remove` sono disabilitati per i worker;
- ambiente sanificato (niente token, `SSH_AUTH_SOCK`, `HOME` reale);
- limiti di CPU, memoria, dimensione file e timeout sul process group;
- quota disco su `project/` (500 MB default);
- task MCP ricostruiti da zero e URL limitati a `http`/`https`;
- audit log con rotazione in `logs/security.log`;
- AST scanner: blocca `eval`, `exec`, `pickle` prima del sandbox;
- anti-escape guardrail: blocca artefatti `\"`, `//` e righe duplicate nei file generati.

`[security] enabled = false` in `config.toml` viene **ignorato** e registrato
come `CRITICAL`: il flag esiste solo per retrocompatibilità.

Per dati reali è necessario aggiungere l'isolamento di sistema (utente dedicato,
cgroup, firewall):

```bash
./setup-hardening.sh                  # diagnostica, nessuna modifica
sudo ./setup-hardening.sh --all       # utente byteswarmy + cgroup + firewall
```

Dettagli, modello di minaccia, rischi residui e rollback:
**[SECURITY.md](SECURITY.md)**.

Verifica della policy:

```bash
python -m pytest tests/ -v            # 58 test: 27 security + 22 sandbox + 3 escape-gate + 6 intent
tail -f logs/security.log
```

---

## Panoramica

BYTE-SWARMY è un sistema multi-agente che gira interamente in locale su hardware
modesto (4 GB di RAM, GPU opzionale). Riceve un task in linguaggio naturale
(IT/EN/ZH), lo classifica, lo scompone se necessario e lo esegue con worker
specializzati. Lo stato è persistito su SQLite, quindi il lavoro può riprendere
dopo un riavvio.

### Enterprise Grade Quality Assurance

| Feature | Descrizione | Vantaggio |
|---|---|---|
| **Audit Worker** | Secondo agente (Reviewer) che controlla ogni modifica prima dell'approvazione. | Blocca bug e vulnerabilità prima che entrino nel progetto. |
| **Refactor-Loop** | Protocollo: Mappatura → Analisi → Intervento → Validazione. | Riduce le regressioni e mantiene il codice modulare. |
| **JSONL Logging** | Log strutturati e immutabili per ogni azione del sistema. | Audit completo e tracciabilità enterprise. |
| **Sandbox Bwrap** | Isolamento completo dei processi worker via bubblewrap (no rete, no home, escape `/etc` bloccato). | Previene l'esecuzione di codice malevolo sul sistema host. |
| **AST Scanner** | Gate deterministico che blocca codice Python pericoloso in `write_file`. | Ferma `eval`, `exec`, `pickle` prima del sandbox. |
| **Anti-escape Guardrail** | Rileva artefatti di escape (`\"`, `//`, righe duplicate) nei file generati. | Previene il bug più costoso del progetto alla radice. |
| **Event Sourcing** | Memoria worker come log immutabile su SQLite. | Crash recovery e audit completo delle decisioni. |
| **State Recovery** | Ripristino contesto worker dall'event store al riavvio. | Minimizza la perdita di contesto tra crash e restart. |
| **Exception Hardening** | Policy centralizzata per classificazione errori LLM/tool. | Retry intelligente con backoff, analisi degli errori. |
| **Persistent Memory** | Memoria cross-task: file esistenti, errori comuni, task recenti, preferenze utente. | Il worker non ricrea file già esistenti, evita errori noti. |
| **USB Analysis** | Tool di ispezione passiva del traffico USB via `usbmon`. | Reverse engineering hardware in modo sicuro e read-only. |
| **Disk Quota** | Limite 500 MB su `project/` per prevenire saturazione disco. | Protezione contro attacchi di tipo `dd` o loop di scritture. |

### Principi di progettazione

| Principio | Implementazione |
|---|---|
| **Routing deterministico prima dell'LLM** | Intent Router multilingue classifica l'input; swarm commands ed execute tasks gestiti senza LLM. |
| **Stato = SQLite + JSON** | Coda su SQLite (ACID), stato su JSON ispezionabile con `cat`. |
| **Scritture transazionali** | `write_file` scrive un file temporaneo e poi esegue `rename()` atomico. |
| **Memoria compattata** | Dopo 50 eventi il contesto viene riassunto in `long_term`. |
| **Loop sequenziale** | Un tick ogni 30 secondi (modulato da Timestral), prevedibile e monitorabile. |
| **Safety valve** | Pausa automatica per RAM, disco, temperatura CPU/GPU; shutdown pulito su SIGTERM. |
| **Streaming token** | I token del modello appaiono in tempo reale nel Live Activity Panel (300 ms). |
| **Model rotation** | Un solo modello in VRAM alla volta; caricamento/scaricamento esplicito. |
| **Thermal optimization** | Timestral LLM Tuner adatta parametri LLM (temp, top_p, ctx, max_steps) allo stato termico. |
| **Predictive throttling** | EMA + regressione lineare stimano "minuti alla soglia termica". |

### Identità del nome

| Lettura | Significato |
|---|---|
| **Byte** | Unità di memoria: il codice prodotto è fatto di byte. |
| **Bite** | Morso: le api "mordono" i task e li scompongono. |
| **Bee** | Ape: lo sciame di agenti. |

**Acronimo:** **B**yte-**S**warm **W**ith **A**utonomous **R**esource
**M**anagement & **Y**ield.

---

## Perché BYTE-SWARMY?

| Senza BYTE-SWARMY | Con BYTE-SWARMY |
|---|---|
| Compri una GPU da €2000 | Usa il tuo laptop del 2015 (GPU opzionale) |
| Dipendi da API cloud a consumo | Tutto in locale, gratis per sempre |
| 8 GB di RAM come minimo | 4 GB di RAM bastano |
| Codice nel cloud di terze parti | Codice tuo, sempre, ovunque |
| Coda task persa se chiudi il terminale | Stato persistito in SQLite |
| L'LLM decide cosa eseguire | Orchestratore deterministico + Intent Router |
| Fidi del prompt di sistema | Policy di sicurezza nel codice (Rule 0) |
| Modelli hardcoded nel config | Auto-selezione intelligente basata su hardware |
| Parametri LLM fissi | Timestral LLM Tuner adatta i parametri al calore |

---

## Demo

<p align="center">
  <em>Control Center: 7 tab, toggle button, temperature CPU/GPU colorate, Live Activity Panel con streaming token e LLM Tuner indicator.</em>
</p>

Cosa puoi vedere:

- il worker `worker_coder` che esegue un task con token streaming in tempo reale;
- Timestral che mostra temperatura CPU e GPU in tempo reale + predizione EMA;
- il LLM Tuner che adatta parametri in base allo stato termico (🎚️ LLM Tuned: SLOW);
- il tab Modelli con Auto-Select che sceglie il modello migliore per ogni ruolo;
- il benchmark modelli con score 100/100;
- l'audit log che registra ogni comando eseguito o bloccato dalla policy;
- la coda con task pending, in esecuzione e completati.

---

## Architettura

| Componente | Ruolo | Stack |
|---|---|---|
| **Intent Router** | Classifica input libero multilingue (IT/EN/ZH) in task strutturati | Python (rapidfuzz) |
| **Orchestratore** | Loop principale, dispatch, safety check, swarm commands, execute handler | Python |
| **Planner** | Scompone i task complessi | Ollama |
| **Decision Model** | Scompone i task generici in 2–8 sottotask atomici | Ollama (`tev1:4b`) |
| **Worker** | Esegue il task atomico: 21 tool, ReAct loop, streaming token | Ollama |
| **Audit Worker** | Reviewer: approva/rifiuta il lavoro del worker | Ollama |
| **Execute Handler** | Esegue task `type=execute` (gcc/python/make) deterministicamente senza LLM | Python |
| **Model Selector** | Algoritmo 0–100 per scegliere il modello migliore per ruolo | Python |
| **Benchmark Suite** | 3-test suite (code/summary/classify) con tok/s, TTFT, score | Python |
| **Persistent Memory** | Memoria cross-task: file, errori, preferenze utente | Python (JSON) |
| **Exception Handler** | Classificazione errori centralizzata con retry policy | Python |
| **State Recovery** | Ripristino contesto worker da event store SQLite al riavvio | Python |
| **LLM Tuner** | Adatta parametri LLM (temp, top_p, ctx, steps) allo stato termico | Python |
| **Thermal Predictor** | EMA + regressione lineare per stimare minuti alla soglia termica | Python |
| **Watchdog** | Supervisore: riavvia l'orchestratore dopo un crash | Python |
| **AST Scanner** | Gate deterministico su `write_file` + anti-escape guardrail | Python |
| **Event Store** | Memoria worker come log immutabile su SQLite | Python |
| **Timestral** | Monitor termico CPU + GPU e tuning dinamico | Python |
| **MCP Client** | Riceve task da server MCP esterni via SSE | Python |
| **GUI PyQt6** | Control Center con 7 tab + QSS theme system (light/dark) | PyQt6 |
| **CLI Launcher** | `byte-swarmy` e alias `bswarm` | Bash |
| **Backup** | Snapshot git periodici, tar verificati e sync GitHub on-demand | git |

### Ciclo di un tick

```
┌──────────────────────────────────────────────────────────────┐
│  ogni 30 secondi (modulato da Timestral + LLM Tuner)         │
│                                                              │
│  1. SAFETY CHECK   → RAM > 95%? Disco < 1 GB? → pausa        │
│  2. TIMESTRAL      → temperatura CPU/GPU critiche? → pausa   │
│  3. MAINTENANCE    → backup git, memory compaction           │
│  4. DISPATCH       → leggi coda SQLite                       │
│  5. SWARM CMD?     → handle diretto (no LLM, instantaneo)    │
│  6. EXECUTE?       → handler deterministico (gcc/python)     │
│  7. GENERIC?       → Decision Model scompone                 │
│  8. COMPLEX?       → Planner scompone                        │
│  9. EXECUTE        → Worker ReAct (6 step, streaming)        │
│ 10. AUDIT          → auto-APPROVE se tool utile chiamato     │
│ 11. PERSIST        → memoria, eventi, stato su disco         │
│ 12. SLEEP          → prossimo tick                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Requisiti

- Linux (testato su Kubuntu/Ubuntu; qualsiasi distro con Python 3.11+)
- Python 3.11+ (per `tomllib` nella standard library)
- Ollama installato e funzionante
- 4 GB di RAM minimo (8 GB consigliati)
- GPU NVIDIA opzionale (per accelerazione LLM, es. GTX 1050 4 GB)
- PyQt6 (opzionale, solo per la GUI)
- bubblewrap ≥ 0.11 (per il sandbox)
- git (backup e sincronizzazione)

### Modelli Ollama

```bash
# Orchestratore (circa 400 MB)
ollama pull qwen2.5:0.5b

# Planner (circa 2.2 GB)
ollama pull phi3:mini

# Worker coding (circa 1 GB)
ollama pull qwen2.5-coder:1.5b

# Worker general (circa 1 GB)
ollama pull qwen2.5:1.5b

# Embedding (circa 274 MB)
ollama pull nomic-embed-text

# Decision model (circa 4.5 GB) — per task generici
ollama pull tev1:4b
```

> Il tab **Modelli** nella GUI può auto-selezionare i modelli migliori per il
> tuo hardware con un clic (pulsante "Auto-Select"). Puoi anche eseguire un
> benchmark completo con `python -m CORE.benchmark`.

---

## Installazione

```bash
git clone https://github.com/wildlux/byte-swarmy.git
cd byte-swarmy
./setup.sh
```

`setup.sh` verifica e, con conferma esplicita, installa:

- Python, pip, git, Ollama e bubblewrap;
- virtualenv `.venv/` con pip funzionante;
- dipendenze Python: `PyQt6`, `tomli-w`, `rapidfuzz`, `mcp`, `httpx`,
  `httpx-sse`, `uvicorn`, `starlette`;
- modelli Ollama necessari (chiede prima di scaricarli);
- directory di lavoro: `state/`, `logs/`, `tasks/`, `project/`, `backups/`.

---

## Avvio rapido

### Avvio completo

```bash
./avvia.sh
```

Lo script attiva il virtualenv, avvia l'orchestratore **sotto supervisore
Watchdog** in background e apre la GUI. Chiudendo la GUI l'orchestratore
continua a girare; se il processo crasha viene riavviato automaticamente.

Modalità alternative:

```bash
./avvia.sh --gui      # Solo GUI
./avvia.sh --orch     # Solo orchestratore in background
./avvia.sh --status   # Mostra lo stato ed esce
./avvia.sh --setup    # Forza setup.sh (check + install)
```

### Stato e arresto

```bash
./byte-swarmy status
./ferma.sh
```

### Primo task di verifica

Avvia la GUI e scrivi nella **Quick Command Bar** in cima al tab "Coda Task":

```
crea funzione fattoriale in python
```

L'Intent Router classifica la richiesta (IT), crea il task e l'orchestratore lo
esegue. Guarda il **Live Activity Panel** a destra: vedrai i token apparire in
tempo reale mentre il worker genera il codice, più l'indicatore `🎚️ LLM Tuned`
che mostra il profilo termico attivo.

---

## Utilizzo

### CLI

```bash
# Avvio e arresto
byte-swarmy start              # Orchestratore in background
byte-swarmy stop               # Arresto con SIGTERM
byte-swarmy gui                # Avvia la GUI
byte-swarmy status             # PID, coda, ultimo campione termico

# Coda task
byte-swarmy queue list
byte-swarmy queue add <title> [desc]
byte-swarmy queue add-generic <title> [desc]   # Scomposto dal decision model
byte-swarmy queue reset <id>                   # Riporta il task a pending
byte-swarmy queue cleanup                      # Elimina i task completati

# Timestral
byte-swarmy thermal            # Ultimo campione (CPU + GPU)
byte-swarmy thermal history    # Storico recente

# Model selector e benchmark
python -m CORE.model_selector           # Mostra raccomandazioni
python -m CORE.model_selector --apply   # Applica al config.toml
python -m CORE.benchmark                # Benchmark tutti i modelli
python -m CORE.benchmark --model qwen2.5-coder:1.5b  # Solo uno

# Codice prodotto
byte-swarmy honey              # Elenca project/
byte-swarmy honey log          # git log di project/

# Log e configurazione
byte-swarmy logs               # Tail del log (Ctrl+C per uscire)
byte-swarmy config edit        # Apre CONFIG/config.toml in $EDITOR

# MCP
byte-swarmy mcp start          # Avvia il server MCP di esempio
byte-swarmy mcp list           # Elenca i server MCP configurati

# Varie
byte-swarmy version
byte-swarmy help
```

Alias disponibile: `bswarm`.

### GUI Control Center

```bash
./avvia.sh --gui
```

**7 tab** + Quick Command Bar in cima alla coda:

0. **Quick Command Bar** — scrivi in linguaggio naturale (IT/EN/ZH); l'Intent
   Router classifica la richiesta e crea il task strutturato in coda.
1. **Coda Task** — task pending, in esecuzione e completati. Accanto alla
   tabella un **Live Activity Panel** mostra streaming token, step, thought,
   tool call, metriche (tok/s, KV cache, VRAM) e `🎚️ LLM Tuned` in tempo reale
   (300 ms).
2. **Modelli** — selettore modelli LLM con Auto-Select intelligente, ComboBox
   per ogni ruolo, Test button (misura tok/s), Save & Restart.
3. **MCP Servers** — configura server MCP esterni, polling automatico e
   discovery dei tool.
4. **Logs** — tail in tempo reale, auto-scroll ed export.
5. **Timestral (Termico)** — metriche live (temperatura CPU e GPU, carico,
   frequenza, memoria), consigli operativi, predizione EMA e storico. Gli
   indicatori CPU/GPU colorati (verde/arancio/rosso) sono anche nella toolbar.
6. **Config** — editor bidirezionale form↔TOML con validazione live, copia
   errore e revert automatico. Si ricarica da disco quando torni al tab.
7. **Test & Sandbox** — esecuzione della suite (58 test), self-test del
   sandbox e verifica dello stato di isolamento.

**Toolbar**: toggle button unico Avvia/Ferma (verde/rosso), indicatori
temperatura CPU/GPU colorati, pulsante tema (◐), pulsante Esci.

**Theme**: QSS theme system con light e dark. Toggle con `Ctrl+Shift+T`.

### Swarm commands (istantanei, no LLM)

| Comando | Effetto |
|---------|---------|
| `swarm status` | Stato completo dello swarm (coda, modelli, timestral) |
| `lista task` | Lista di tutti i task in coda |
| `mostra log` | Ultimi 30 log (esclusi timestral) |
| `pause swarm` | Mette in pausa lo swarm |
| `riprendi swarm` | Riprende lo swarm |
| `ispeziona memoria` | Mostra memoria agenti |
| `cancella task` | Cancella task pending |
| `run audit` | Audit del progetto (file, linee) |

### Execute tasks (deterministici, no LLM)

I task con `type=execute` (es. "Compila ed esegui l'applicazione") vengono
gestiti deterministicamente dall'Execute Handler senza invocare alcun LLM.
Il parser estrae comandi `gcc`, `python`, `make` dalla descrizione e li esegue
via `run_bash` nel sandbox.

### GitHub sync

Push è **manuale solo**. I worker non possono modificare remote o push.

```bash
./sync.sh "descrizione delle modifiche"
./sync.sh --pull
./sync.sh --status
./sync.sh --log
```

---

## Come funziona

### Intent Router (multilingue)

Free-form input (Quick Command Bar) passes through `INTENT/router.py` before
entering the queue: the text is classified with fuzzy matching (`rapidfuzz`)
against 28 intents in `INTENT/intents.json` (314 triggers total), the language
is detected (Italian, English, Chinese) and extracted parameters end up in the
task metadata. If the intent is not recognised with sufficient confidence, the
task degrades to `generic` and goes through the Decision Model.

### Swarm commands (zero LLM)

8 commands are intercepted by the orchestrator before dispatch and handled
directly with Python handlers. Instant response, zero tokens.

### Execute handler (zero LLM)

Tasks with `type=execute` are parsed by `CORE/execute_handler.py` which
extracts shell commands (gcc, python, make) from the description and executes
them via `tools.run_bash` in the sandbox. No LLM invoked.

### Routing deterministico

| Tipo di task | Destinazione |
|---|---|
| Swarm command | Handler diretto (no LLM) |
| `type=execute` | Execute Handler (gcc/python/make, no LLM) |
| `type=generic` | Decision Model (`tev1:4b`) → 2–8 subtask |
| Keyword complesse ("sistema", "multi") | Planner (`phi3:mini`) → 2–5 subtask |
| Altrimenti | Worker diretto |

### Timestral — tuning dinamico + LLM Tuner

Timestral samples CPU + GPU temperature every 30 seconds. Based on the thermal
state, two things happen:

1. **Tick modulation**: `fast` (×0.6) / `normal` (×1.0) / `slow` (×1.7–2.5) /
   `pause` (no dispatch).
2. **LLM Tuner**: adjusts LLM parameters for the current thermal profile:

| Profile | temp | top_p | num_predict | num_ctx | max_steps |
|---------|------|-------|-------------|---------|-----------|
| **FAST** (< 50°C) | 0.25 | 0.92 | 600 | 3072 | 8 |
| **NORMAL** (50–65°C) | 0.15 | 0.85 | 450 | 3072 | 6 |
| **SLOW** (65–85°C) | 0.08 | 0.78 | 300 | 2048 | 5 |
| **PAUSE** (> 85°C) | 0.05 | 0.70 | 200 | 1536 | 4 |

### Timestral predittivo (EMA)

`MONITORING/predictive.py` uses Exponential Moving Average + linear regression
to estimate "minutes to thermal threshold". Pure stdlib, no numpy.

### Intelligent Model Selector

`CORE/model_selector.py` scores every Ollama model 0–100 for each role. Hard
gates (VRAM/RAM/capability) + soft scoring (family, name, quantization,
thermal). Returns top 1 + 3 alternatives per role.

### Dynamic KV cache

`INTENT/metrics.py` estimates KV cache with the real formula
`2 (K+V) × layers × kv_heads × head_dim × 2 × tokens`, using a
`MODEL_ARCHITECTURES` table for known models.

### Model Benchmark Suite

`CORE/benchmark.py` runs a 3-test suite (code generation, summarization,
classification) on each model. Results saved to `state/model_benchmarks.json`.
qwen2.5-coder:1.5b scored 100/100, avg 31.8 tok/s.

### Exception Hardening

`CORE/exception_handler.py` classifies errors (model_unavailable, model_timeout,
tool_error, sandbox_violation, parse_error) and recommends actions (retry,
abort, simplify, pivot) with exponential backoff.

### State Recovery

`CORE/state_recovery.py` reconstructs worker context from the immutable SQLite
event store on restart, minimizing context loss after crashes.

### Persistent Memory

4 tiers:

- **short_term** — current task events (RAM);
- **working** — compact context used in the prompt;
- **long_term** — persistent summary after compaction (SQLite event store);
- **persistent** — cross-task memory: existing files, common errors, recent
  tasks, **user preferences** (preferred language, type hints, frameworks,
  styles extracted via pattern matching). Injected into the worker's prompt.

### Safety valve

| Condizione | Azione |
|---|---|
| RAM > 95% | Pause dispatch, auto-resume |
| Free disk < 1 GB | Pause and block new writes |
| CPU temp > 90 °C | Thermal pause |
| GPU temp > 95 °C | Thermal pause |
| CPU load > 95% for 60 s | Pause to avoid thrashing |
| 10 consecutive failures | Task in `stuck` state |
| Crash dell'orchestratore | Watchdog riavvia il processo |
| 3 tool call identiche | Circuit breaker: pivot obbligato |
| Project/ > 500 MB | Disk quota: write_file rifiutato |
| SIGTERM | Save state, unload models, clean exit |

---

## Sicurezza in profondità

| Livello | Comportamento |
|---|---|
| **Comandi** | `run_bash` tokenizza, rifiuta metacaratteri shell, allowlist + blacklist, `shell=False`. |
| **Path** | Solo path relativi a `project/`; blocco path assoluti, `..`, `~`, symlink escape, file sensibili. |
| **Sandbox** | bubblewrap: isolated filesystem, blocked network, separate PID/user namespaces, `--cap-drop ALL`, `--disable-userns`, `--remount-ro /etc` (escape blocked). |
| **AST** | `write_file` passa per `ast_scanner.py` che blocca `eval`, `exec`, `pickle`, ecc. |
| **Anti-escape** | `detect_artifacts` blocca `\"`, `//` C-style, righe duplicate, syntax error. |
| **Git** | local `status`, `log`, `diff`, `branch`, `merge`, `commit`; push/pull/remote disabled. |
| **Ambiente** | sandbox `HOME`; token, SSH sockets, cloud vars removed. |
| **Risorse** | CPU, memory, open files, file size, core dump limits; process group timeout. |
| **Disco** | Quota 500 MB su `project/` verificata prima di ogni `write_file`. |
| **External input** | MCP tasks rebuilt from scratch, fields with max length, URLs `http`/`https` only. |
| **Audit** | Every allowed/blocked/timed-out command logged in `logs/security.log`. |
| **Exception** | `CORE/exception_handler.py` classifica errori con retry policy e backoff. |

---

## Struttura del progetto

```
byte-swarmy/
├── CORE/                    # Motori: orchestrator, tools, sandbox, memory,
│   │                          ollama_client, model_selector, mcp_client,
│   │                          persistent_memory, ast_scanner, constants,
│   │                          execute_handler, llm_tuner, benchmark,
│   │                          exception_handler, state_recovery
│   ├── orchestrator.py      # Orchestratore, Planner, Worker, Auditor
│   ├── tools.py             # ToolSet: 21 tools, sandboxed execution
│   ├── sandbox.py           # bubblewrap builder
│   ├── memory.py            # AgentMemory: short/working/long_term
│   ├── memory_provider.py   # SQLite event sourcing
│   ├── ollama_client.py     # ModelClient + call_streaming()
│   ├── model_selector.py    # Algoritmo 0–100 per ruolo
│   ├── persistent_memory.py # Memoria cross-task + extract_preferences()
│   ├── ast_scanner.py       # AST gate + anti-escape guardrail
│   ├── execute_handler.py   # Handler deterministico per type=execute
│   ├── llm_tuner.py         # 4 profili termici per parametri LLM
│   ├── benchmark.py         # Suite benchmark modelli (3 test)
│   ├── exception_handler.py # Policy centralizzata gestione errori
│   ├── state_recovery.py    # Ripristino stato worker da event store
│   ├── mcp_client.py        # MCP client over SSE
│   └── constants.py
├── INTENT/                  # Router multilingue + metrics
│   ├── router.py            # IT/EN/ZH classification (rapidfuzz)
│   ├── intents.json         # 28 intent, 314 trigger
│   ├── bridge.py            # Bridge router ↔ GUI/orchestratore
│   └── metrics.py           # Metriche Ollama + KV cache dinamica
├── SAFETY/                  # security.py + watchdog
│   ├── security.py          # Policy centrale (audit, allowlist, ./binari)
│   ├── security_checks.py   # Check isolamento + safe mode
│   └── watchdog.py          # Supervisore crash-recovery
├── MONITORING/              # Timestral + predittivo
│   ├── thermal_manager.py   # CPU + GPU monitoring + advice.json
│   ├── predictive.py        # EMA + regressione lineare
│   ├── system_monitor.py
│   └── lifecycle_manager.py
├── GUI/                     # PyQt6 Control Center
│   ├── main_window.py       # 7 tab + toolbar + live activity
│   └── theme/               # QSS theme system (light.qss, dark.qss, theme.py)
├── CONFIG/                  # config.toml
├── tests/                   # 58 test: security, sandbox, escape-gate, intent
│   ├── test_security.py     # 27 test
│   ├── test_sandbox.py      # 22 test (11 subtest)
│   ├── test_escape_gate.py  # 3 test (anti-escape)
│   ├── test_intent_integration.py  # 6 test
│   └── run_tests.py         # Runner JSON per GUI
├── state/                   # Stato persistente
│   ├── timestral_history.json       # 24h campioni CPU/GPU
│   ├── timestral_advice.json        # Ultimo advice (per GUI)
│   ├── persistent_memory.json       # Memoria cross-task + preferenze
│   ├── last_metrics.json            # Metriche ultima call
│   ├── model_benchmarks.json        # Risultati benchmark
│   ├── streaming.txt                # Token streaming live
│   └── orchestrator.pid
├── tasks/                   # Coda task
│   ├── queue.db             # SQLite (fonte di verità orchestratore)
│   └── queue.json           # Mirror per GUI
├── logs/                    # Log applicativo, JSONL, audit, watchdog
├── project/                 # Codice prodotto dai worker (sandboxed)
├── backups/                 # tar.gz snapshots (ultimi 7)
├── main.py                  # CLI entry point
├── byte-swarmy              # CLI launcher (alias: bswarm)
├── avvia.sh / ferma.sh / sync.sh / setup.sh / setup-hardening.sh
├── SECURITY.md / IMPLEMENTED.md / SPECIFICATIONS.md / AGENT.md / todo.md
├── BYTE-SWARMY.desktop      # KDE menu entry
└── requirements_gui.txt
```

---

## Sviluppo e test

### Test suite (58 test)

```bash
source .venv/bin/activate
python -m pytest tests/ -v
deactivate
```

Covers:

- **27 security** — comandi distruttivi, pipe, redirect, path traversal,
  symlink escapes, git push/pull/remote, sanitised environment, prompt injection;
- **22 sandbox** — bubblewrap isolation, `/etc` escape blocked, network blocked,
  write-outside-project blocked, 11 self-test subtests;
- **3 escape-gate** — anti-escape guardrail: syntax error, C-style comment,
  duplicated lines, JSON error;
- **6 intent** — multilingual routing IT/EN/ZH, swarm command detection,
  localisation.

### Static checks

```bash
python -m py_compile CORE/*.py INTENT/*.py SAFETY/*.py MONITORING/*.py GUI/*.py
bash -n avvia.sh ferma.sh sync.sh setup.sh setup-hardening.sh
git diff --check
```

### Model selector e benchmark

```bash
python -m CORE.model_selector           # raccomandazioni
python -m CORE.model_selector --apply   # applica al config
python -m CORE.benchmark                # benchmark tutti i modelli
python -m CORE.benchmark --model qwen2.5-coder:1.5b  # solo uno
```

---

## Limiti noti

- **Un solo modello caricato alla volta**: rotation è esplicita (vincolo 4 GB VRAM).
- **Worker sequenziali**: nessun parallelismo, un task alla volta.
- **Contesto limitato** (3072 token, ridotto a 1536 quando caldo): i task grandi vengono scomposti.
- **Output LLM limitato** (512 token/step, 6 step max, ridotti quando caldo): file grandi richiedono più task.
- **Modelli 1.5 B–4 B**: efficaci su task discreti, poco affidabili su architetture complesse.
- **TDD relaxed**: il check TDD è warning-only (i modelli piccoli struggle col test-first).
- **Nessun sandbox di kernel**: l'isolamento completo richiede system hardening.

---

## Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| `ModuleNotFoundError: PyQt6` | Dipendenze GUI assenti | `./setup.sh` o `pip install -r requirements_gui.txt` |
| `ModuleNotFoundError: rapidfuzz` | Router intenti non installato | `pip install rapidfuzz` |
| `ModuleNotFoundError: mcp` | Dipendenze MCP assenti | `pip install mcp httpx httpx-sse` |
| Orchestratore non parte | Virtualenv non attivo | `source .venv/bin/activate` |
| Status "fermato" dopo l'avvio | Subprocess terminato | Controlla `logs/byte-swarmy.log` |
| `RAM pressure: 94%` | Troppa RAM usata | Chiudi app pesanti, o alza `swap_threshold` a 0.95 |
| Task sempre `stuck` | Prompt troppo complesso | Spezza il task o usa un Generic task |
| KV cache enorme | Modello con tanti layer (es. phi3) | Usa modello più piccolo (qwen2.5-coder:1.5b) |
| GPU troppo calda (> 90°C) | Timestral pausa | LLM Tuner riduce parametri automaticamente |
| `./hello_world` bloccato | Allowlist non aggiornata | Verifica `security.py` ha il check `./` |
| `tomli_w non installato` | Writer TOML mancante | `pip install tomli-w` |
| Push: `Authentication failed` | Token errato o scaduto | Crea un nuovo PAT su GitHub |
| Comando bloccato da `run_bash` | Policy di sicurezza attiva | Leggi il messaggio: indica il motivo e l'alternativa |

---

## Compatibilità

- **OS:** Linux (testato su Kubuntu/Ubuntu). Su Windows/macOS disattiva Timestral.
- **Python:** 3.11+ per `tomllib`; su 3.10 installa `tomli`.
- **RAM:** 4 GB minimo, 8 GB consigliati.
- **GPU:** NVIDIA opzionale (per LLM acceleration, es. GTX 1050 4 GB).
- **Ollama:** qualsiasi versione recente.
- **bubblewrap:** ≥ 0.11 (per `--disable-userns`).
- **GUI:** PyQt6 con wheel disponibili per Python 3.14.

---

## Contribuire

Il progetto è pensato per essere esteso. Le aree più aperte (vedi `todo.md`):

- UI redesign (menu hamburger, Live Activity in alto);
- MCP E2E testing;
- USB protocol parser e differential analysis;
- unificazione coda GUI→SQLite (FM14).

Prima di proporre una modifica, verifica che rispetti il vincolo del progetto:
*"gira su 4 GB di RAM senza cloud?"*

Per modifiche che toccano la sicurezza, aggiorna anche `SECURITY.md` e la suite
`tests/test_security.py`.

---

## Licenza

Rilasciato sotto licenza MIT. Vedi [LICENSE](LICENSE).

---

## Ringraziamenti

- [Ollama](https://ollama.com) per l'esecuzione locale dei modelli
- [PyQt6](https://www.riverbankcomputing.com/software/pyq/) per la GUI
- [MCP](https://modelcontextprotocol.io) per il protocollo di distribuzione task
- [bubblewrap](https://github.com/containers/bubblewrap) per il sandbox
- [rapidfuzz](https://github.com/maxbachmann/RapidFuzz) per il fuzzy matching
- I modelli decisionali di [Together AI](https://www.together.ai/),
  [Bespoke Labs](https://www.bespoke.co/), [Cloudflare](https://www.cloudflare.com/),
  [Perplexity](https://www.perplexity.ai/), [Strands Agents](https://strandsagents.com/)
  e [Convai](https://convai.com/)

---

**BYTE-SWARMY v0.3.0**

```
/ˈbaɪt ˈswɔːrmi/  ·  "BYTE SWOR-mee"
```

> *"The swarm works. You think elsewhere."*
