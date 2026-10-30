# BYTE-SWARMY

<p align="center">
  <img src="IMG/documentazione.jpeg" alt="BYTE-SWARMY — Swarm autonomo locale" width="720">
</p>

<p align="center">
  <strong>Sistema multi-agente autonomo, interamente locale, per macchine con 4 GB di RAM.</strong>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-0.2.0-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-yellow">
  <img alt="Ollama" src="https://img.shields.io/badge/Ollama-required-orange">
  <img alt="RAM" src="https://img.shields.io/badge/RAM-4%20GB%20min-red">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Linux-lightgrey">
  <img alt="Cloud" src="https://img.shields.io/badge/cloud-NOT%20needed-success">
  <img alt="Tests" src="https://img.shields.io/badge/tests-55%20pass-brightgreen">
</p>

<p align="center">
  <em>"The swarm works. You think elsewhere."</em>
</p>

---

> **Nessun cloud, nessuna dipendenza da servizi esterni:**
> solo Ollama, Python e SQLite/JSON. I worker eseguono task di programmazione,
> test e documentazione sotto il controllo di un orchestratore deterministico,
> con streaming token in tempo reale e selezione intelligente dei modelli.

**Versione:** 0.2.0 · **Licenza:** MIT · **Piattaforma:** Linux

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
- `git push` / `pull` / `remote add|remove` sono disabilitati per i worker;
- ambiente sanificato (niente token, `SSH_AUTH_SOCK`, `HOME` reale);
- limiti di CPU, memoria, dimensione file e timeout sul process group;
- task MCP ricostruiti da zero e URL limitati a `http`/`https`;
- audit log con rotazione in `logs/security.log`;
- escape `/etc` bloccato (`--tmpfs /etc` + `--remount-ro`).

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
python -m pytest tests/ -v            # 55 test: 27 security + 22 sandbox + 6 intent
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
| **Event Sourcing** | Memoria worker come log immutabile su SQLite. | Crash recovery e audit completo delle decisioni. |
| **Persistent Memory** | Memoria cross-task: file esistenti, errori comuni, task recenti. | Il worker non ricrea file già esistenti, evita errori noti. |
| **USB Analysis** | Tool di ispezione passiva del traffico USB via `usbmon`. | Reverse engineering hardware in modo sicuro e read-only. |

### Principi di progettazione

| Principio | Implementazione |
|---|---|
| **Routing deterministico prima dell'LLM** | Intent Router multilingue classifica l'input; swarm commands gestiti senza LLM. |
| **Stato = SQLite + JSON** | Coda su SQLite (ACID), stato su JSON ispezionabile con `cat`. |
| **Scritture transazionali** | `write_file` scrive un file temporaneo e poi esegue `rename()` atomico. |
| **Memoria compattata** | Dopo 50 eventi il contesto viene riassunto in `long_term`. |
| **Loop sequenziale** | Un tick ogni 30 secondi (modulato da Timestral), prevedibile e monitorabile. |
| **Safety valve** | Pausa automatica per RAM, disco, temperatura CPU/GPU; shutdown pulito su SIGTERM. |
| **Streaming token** | I token del modello appaiono in tempo reale nel Live Activity Panel (300 ms). |
| **Model rotation** | Un solo modello in VRAM alla volta; caricamento/scaricamento esplicito. |

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

---

## Demo

<p align="center">
  <em>Control Center: 7 tab, toggle button, temperature CPU/GPU colorate, Live Activity Panel con streaming token.</em>
</p>

Cosa puoi vedere:

- il worker `worker_coder` che esegue un task con token streaming in tempo reale;
- Timestral che mostra temperatura CPU e GPU in tempo reale;
- il tab Modelli con Auto-Select che sceglie il modello migliore per ogni ruolo;
- l'audit log che registra ogni comando eseguito o bloccato dalla policy;
- la coda con task pending, in esecuzione e completati.

---

## Architettura

| Componente | Ruolo | Stack |
|---|---|---|
| **Intent Router** | Classifica input libero multilingue (IT/EN/ZH) in task strutturati | Python (rapidfuzz) |
| **Orchestratore** | Loop principale, dispatch, safety check, swarm commands | Python |
| **Planner** | Scompone i task complessi | Ollama |
| **Decision Model** | Scompone i task generici in 2–8 sottotask atomici | Ollama (`tev1:4b`) |
| **Worker** | Esegue il task atomico: 21 tool, ReAct loop, streaming token | Ollama |
| **Audit Worker** | Reviewer: approva/rifiuta il lavoro del worker | Ollama |
| **Model Selector** | Algoritmo 0–100 per scegliere il modello migliore per ruolo | Python |
| **Persistent Memory** | Memoria cross-task: file, errori, preferenze | Python (JSON) |
| **Watchdog** | Supervisore: riavvia l'orchestratore dopo un crash | Python |
| **AST Scanner** | Gate deterministico su `write_file` | Python |
| **Event Store** | Memoria worker come log immutabile su SQLite | Python |
| **Timestral** | Monitor termico CPU + GPU e tuning dinamico | Python |
| **MCP Client** | Riceve task da server MCP esterni via SSE | Python |
| **GUI PyQt6** | Control Center con 7 tab | PyQt6 |
| **CLI Launcher** | `byte-swarmy` e alias `bswarm` | Bash |
| **Backup** | Snapshot git periodici, tar verificati e sync GitHub on-demand | git |

### Ciclo di un tick

```
┌──────────────────────────────────────────────────────────────┐
│  ogni 30 secondi (modulato da Timestral)                     │
│                                                              │
│  1. SAFETY CHECK   → RAM > 80%? Disco < 1 GB? → pausa        │
│  2. TIMESTRAL      → temperatura CPU/GPU critiche? → pausa   │
│  3. MAINTENANCE    → backup git, memory compaction           │
│  4. DISPATCH       → leggi coda SQLite                       │
│  5. SWARM CMD?     → handle diretto (no LLM, instantaneo)    │
│  6. GENERIC?       → Decision Model scompone                 │
│  7. COMPLEX?       → Planner scompone                        │
│  8. EXECUTE        → Worker ReAct (6 step, streaming)        │
│  9. AUDIT          → auto-APPROVE se tool utile chiamato     │
│ 10. PERSIST        → memoria, eventi, stato su disco         │
│ 11. SLEEP          → prossimo tick                           │
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
> tuo hardware con un clic (pulsante "Auto-Select").

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
tempo reale mentre il worker genera il codice.

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

# Model selector
python -m CORE.model_selector           # Mostra raccomandazioni
python -m CORE.model_selector --apply   # Applica al config.toml

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
   tool call e metriche (tok/s, KV cache, VRAM) in tempo reale (300 ms).
2. **Modelli** — selettore modelli LLM con Auto-Select intelligente, ComboBox
   per ogni ruolo, Test button (misura tok/s), Save & Restart.
3. **MCP Servers** — configura server MCP esterni, polling automatico e
   discovery dei tool.
4. **Logs** — tail in tempo reale, auto-scroll ed export.
5. **Timestral (Termico)** — metriche live (temperatura CPU e GPU, carico,
   frequenza, memoria), consigli operativi e storico. Gli indicatori CPU/GPU
   colorati (verde/arancio/rosso) sono anche nella toolbar.
6. **Config** — editor bidirezionale form↔TOML con validazione live, copia
   errore e revert automatico. Si ricarica da disco quando torni al tab.
7. **Test & Sandbox** — esecuzione della suite (55 test), self-test del
   sandbox e verifica dello stato di isolamento.

**Toolbar**: toggle button unico Avvia/Ferma (verde/rosso), indicatori
temperatura CPU/GPU colorati, pulsante Esci.

### Task generici

Scrivi nella Quick Command Bar:

```
voglio una calcolatrice CLI in Python
```

Il decision model (`tev1:4b`) analizza la descrizione e genera da 2 a 8 task
atomici, che vengono accodati automaticamente come sottotask.

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

Questi comandi vengono gestiti direttamente dall'orchestratore senza invocare
nessun LLM: risposta istantanea, zero token consumati.

### Sincronizzazione GitHub

Il push è **solo manuale**. I worker non possono modificare remote né fare push.

```bash
./sync.sh "descrizione delle modifiche"
./sync.sh --pull
./sync.sh --status
./sync.sh --log
```

---

## Come funziona

### Intent Router (multilingue)

L'input libero (Quick Command Bar) passa da `INTENT/router.py` prima di entrare
in coda: il testo viene classificato con matching fuzzy (`rapidfuzz`) su 28
intent in `INTENT/intents.json` (314 trigger totali), la lingua viene rilevata
(italiano, inglese, cinese) e i parametri estratti finiscono nei metadati del
task. Se l'intent non è riconosciuto con sufficiente confidenza, il task
degrada a `generic` e passa dal Decision Model.

### Swarm commands (zero LLM)

8 comandi (`swarm_status`, `list_tasks`, `show_logs`, `pause_swarm`,
`resume_swarm`, `inspect_memory`, `cancel_task`, `run_audit`) vengono
intercettati dall'orchestratore prima del dispatch e gestiti direttamente con
handler Python. Risposta istantanea, zero token.

### Routing deterministico

| Tipo di task | Destinazione |
|---|---|
| Swarm command | Handler diretto (no LLM) |
| `type=generic` | Decision Model (`tev1:4b`) → 2–8 sottotask |
| Keyword complesse ("sistema", "multi") | Planner (`phi3:mini`) → 2–5 sottotask |
| Altrimenti | Worker diretto |

### Timestral — tuning dinamico

Timestral campiona ogni 30 secondi temperatura CPU, temperatura GPU (via
`nvidia-smi`), carico CPU, frequenza, RAM e swap. Le soglie sono configurabili
in `config.toml`.

| Stato | Condizione | Effetto |
|---|---|---|
| `FAST` | temperatura < 50 °C e carico < 60% | tick × 0.6, raddoppia i task/ora |
| `NORMAL` | temperatura 50–65 °C | tick × 1.0 |
| `SLOW` | temperatura 65–80 °C | tick × 1.7–2.5, dimezza i task/ora |
| `PAUSE` | temperatura > 90 °C o GPU > 95 °C | Nessun dispatch fino al raffreddamento |

Lo storico è salvato in `state/timestral_history.json` (24 ore di campioni).

### Model Selector intelligente

`CORE/model_selector.py` assegna un punteggio 0–100 a ogni modello Ollama per
ogni ruolo (orchestrator, planner, worker_coder, worker_general, embedding,
decision). Hard gates (VRAM/RAM/capability) + soft scoring (family match, name
match, quantization, thermal penalty). Ritorna top 1 + 3 alternative per ruolo.

```bash
python -m CORE.model_selector           # solo raccomandazioni
python -m CORE.model_selector --apply   # scrive nel config.toml
```

### KV cache dinamica

`INTENT/metrics.py` stima la KV cache con la formula reale
`2 (K+V) × layers × kv_heads × head_dim × 2 × tokens`, usando una tabella
`MODEL_ARCHITECTURES` per i modelli noti. Sostituisce la vecchia stima
hardcoded per famiglia (era fino a 15× sbagliata per `phi3:mini`).

### Safety valve

| Condizione | Azione |
|---|---|
| RAM > 80% | Pausa del dispatch, ripresa automatica |
| Disco libero < 1 GB | Pausa e blocco delle nuove scritture |
| Temperatura CPU > 90 °C | Pausa termica |
| Temperatura GPU > 95 °C | Pausa termica |
| CPU load > 95% per 60 s | Pausa per evitare thrashing |
| 10 fallimenti consecutivi | Task in stato `stuck` |
| Crash dell'orchestratore | Watchdog riavvia il processo |
| 3 tool call identiche | Circuit breaker: pivot obbligato |
| SIGTERM | Salvataggio stato, unload modelli, uscita pulita |

### Memoria

Ogni worker ha 4 tier:

- **short_term** — eventi del task corrente (RAM);
- **working** — contesto compatto usato nel prompt;
- **long_term** — riassunto persistente dopo la compaction (SQLite event store);
- **persistent** — memoria cross-task: file esistenti, errori comuni, task
  recenti (`state/persistent_memory.json`). Iniettata nel prompt iniziale del
  worker così non ricrea file già esistenti.

---

## Sicurezza in profondità

| Livello | Comportamento |
|---|---|
| **Comandi** | `run_bash` tokenizza, rifiuta metacaratteri shell, allowlist + blacklist, `shell=False`. |
| **Path** | Solo path relativi a `project/`; blocco path assoluti, `..`, `~`, symlink escape, file sensibili. |
| **Sandbox** | bubblewrap: filesystem isolato, rete bloccata, PID/user namespace separati, `--cap-drop ALL`, `--disable-userns`, `--remount-ro /etc` (escape bloccato). |
| **AST** | `write_file` passa per `ast_scanner.py` che blocca `eval`, `exec`, `pickle`, ecc. |
| **Git** | `status`, `log`, `diff`, `branch`, `merge`, `commit` locali; push/pull/remote disabilitati. |
| **Ambiente** | `HOME` sandbox; token, socket SSH, variabili cloud rimossi. |
| **Risorse** | Limiti CPU, memoria, file aperti, dimensione file, core dump; timeout process group. |
| **Input esterni** | Task MCP ricostruiti da zero, campi con lunghezza max, URL solo `http`/`https`. |
| **Audit** | Ogni comando permesso/bloccato/timeout registrato in `logs/security.log`. |

La difesa **non dipende dal prompt**: anche se un task contiene "ignora le
regole", il tool layer applica comunque la policy.

### Isolamento di sistema (opzionale, richiede root)

```bash
./setup-hardening.sh                  # Diagnostica
sudo ./setup-hardening.sh --all       # Utente byteswarmy + cgroup + firewall
sudo ./setup-hardening.sh --undo      # Rimuove slice e regole firewall
```

### Rischi residui

1. Il codice del progetto viene eseguito con i permessi dell'utente.
2. `Makefile`/`CMakeLists.txt`/test possono eseguire comandi shell propri.
3. Non sono inclusi seccomp, AppArmor o container.

Per dati sensibili usa **utente dedicato + firewall**.

---

## Struttura del progetto

```
byte-swarmy/
├── CORE/                    # Motori: orchestrator, tools, sandbox, memory,
│   │                          ollama_client, model_selector, mcp_client,
│   │                          persistent_memory, ast_scanner, constants
│   ├── orchestrator.py      # Orchestratore, Planner, Worker, Auditor
│   ├── tools.py             # ToolSet: 21 tool, esecuzione sandboxed
│   ├── sandbox.py           # bubblewrap builder
│   ├── memory.py            # AgentMemory: short/working/long_term
│   ├── memory_provider.py   # Event sourcing SQLite
│   ├── ollama_client.py     # ModelClient + call_streaming()
│   ├── model_selector.py    # Algoritmo 0–100 per ruolo
│   ├── persistent_memory.py # Memoria cross-task
│   ├── ast_scanner.py       # Gate AST su write_file
│   ├── mcp_client.py        # Client MCP su SSE
│   └── constants.py
├── INTENT/                  # Router multilingue + metrics
│   ├── router.py            # Classificazione IT/EN/ZH (rapidfuzz)
│   ├── intents.json         # 28 intent, 314 trigger
│   ├── bridge.py            # Bridge router ↔ GUI/orchestratore
│   └── metrics.py           # Metriche Ollama + KV cache dinamica
├── SAFETY/                  # security.py + watchdog
│   ├── security.py          # Policy centrale (audit, allowlist)
│   ├── security_checks.py   # Check isolamento + safe mode
│   └── watchdog.py          # Supervisore crash-recovery
├── MONITORING/              # Timestral
│   ├── thermal_manager.py   # CPU + GPU monitoring
│   ├── system_monitor.py
│   └── lifecycle_manager.py
├── GUI/                     # GUI PyQt6 Control Center
│   └── main_window.py       # 7 tab + toolbar + live activity
├── CONFIG/                  # config.toml
├── tests/                   # 55 test: security, sandbox, intent
│   ├── test_security.py     # 27 test
│   ├── test_sandbox.py      # 22 test (11 subtest)
│   ├── test_intent_integration.py  # 6 test
│   └── run_tests.py         # Runner JSON per GUI
├── state/                   # Stato persistente
│   ├── timestral_history.json       # 24h campioni CPU/GPU
│   ├── persistent_memory.json       # Memoria cross-task
│   ├── last_metrics.json            # Metriche ultima call
│   ├── streaming.txt                # Token streaming live
│   └── orchestrator.pid
├── tasks/                   # Coda task
│   ├── queue.db             # SQLite (fonte di verità orchestratore)
│   └── queue.json           # Mirror per GUI
├── logs/                    # Log applicativo, JSONL, audit, watchdog
├── project/                 # Codice prodotto dai worker (sandboxed)
├── backups/                 # Snapshot tar.gz (ultimi 7)
├── main.py                  # Entry point CLI
├── byte-swarmy              # CLI launcher (alias: bswarm)
├── avvia.sh / ferma.sh / sync.sh / setup.sh / setup-hardening.sh
├── SECURITY.md / IMPLEMENTED.md / SPECIFICATIONS.md / AGENT.md / todo.md
├── BYTE-SWARMY.desktop      # Voce di menu KDE
└── requirements_gui.txt
```

---

## Sviluppo e test

### Suite di test (55 test)

```bash
source .venv/bin/activate
python -m pytest tests/ -v
deactivate
```

Copre:

- **27 security** — comandi distruttivi, pipe, redirect, path traversal, symlink
  escape, git push/pull/remote, ambiente sanificato, prompt injection;
- **22 sandbox** — bubblewrap isolation, escape `/etc` bloccato, rete bloccata,
  scrittura fuori progetto bloccata, 11 subtest self-test;
- **6 intent** — routing multilingue IT/EN/ZH, swarm command detection,
  localizzazione.

### Controlli statici

```bash
python -m py_compile CORE/*.py INTENT/*.py SAFETY/*.py MONITORING/*.py GUI/*.py
bash -n avvia.sh ferma.sh sync.sh setup.sh setup-hardening.sh
git diff --check
```

### Model selector

```bash
python -m CORE.model_selector           # raccomandazioni
python -m CORE.model_selector --apply   # applica al config
```

---

## Limiti noti

- **Un solo modello caricato alla volta**: la rotation è esplicita (vincolo 4 GB VRAM).
- **Worker sequenziali**: nessun parallelismo, un task alla volta.
- **Contesto limitato** (3072 token): i task grandi vengono scomposti.
- **Output LLM limitato** (512 token/step, 6 step max): file grandi richiedono più task.
- **Modelli 1.5 B–4 B**: efficaci su task discreti, poco affidabili su architetture complesse.
- **TDD relaxed**: il check TDD è warning-only (i modelli piccoli struggle col test-first).
- **Nessun sandbox di kernel**: l'isolamento completo richiede l'hardening di sistema.

---

## Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| `ModuleNotFoundError: PyQt6` | Dipendenze GUI assenti | `./setup.sh` oppure `pip install -r requirements_gui.txt` |
| `ModuleNotFoundError: rapidfuzz` | Router intenti non installato | `pip install rapidfuzz` |
| `ModuleNotFoundError: mcp` | Dipendenze MCP assenti | `pip install mcp httpx httpx-sse` |
| Orchestratore non parte | Virtualenv non attivo | `source .venv/bin/activate` |
| Status "fermato" dopo l'avvio | Subprocess terminato | Controlla `logs/byte-swarmy.log` |
| Toggle button desincronizzato | Bug vecchio | Riavvia GUI (`./avvia.sh --gui`) |
| RAM saturata | Modelli non scaricati | Verifica `keep_alive=0` nel log |
| Task sempre `stuck` | Prompt troppo complesso | Spezza il task o usa un Generic task |
| KV cache enorme | Modello con tanti layer (es. phi3) | Usa modello più piccolo (qwen2.5-coder:1.5b) |
| GPU troppo calda (> 90°C) | Timestral pausa | Migliora ventilazione o usa modello più piccolo |
| `tomli_w non installato` | Writer TOML mancante | `pip install tomli-w` |
| Push: `Authentication failed` | Token errato o scaduto | Crea un nuovo PAT su GitHub |
| Comando bloccato da `run_bash` | Policy di sicurezza attiva | Leggi il messaggio: indica il motivo e l'alternativa |

---

## Compatibilità

- **OS:** Linux (testato su Kubuntu/Ubuntu). Su Windows/macOS disattiva Timestral.
- **Python:** 3.11+ per `tomllib`; su 3.10 installa `tomli`.
- **RAM:** 4 GB minimo, 8 GB consigliati.
- **GPU:** NVIDIA opzionale (per accelerazione LLM, es. GTX 1050 4 GB).
- **Ollama:** qualsiasi versione recente.
- **bubblewrap:** ≥ 0.11 (per `--disable-userns`).
- **GUI:** PyQt6 con wheel disponibili per Python 3.14.

---

## Contribuire

Il progetto è pensato per essere esteso. Le aree più aperte (vedi `todo.md`):

- guardrail anti-escape in `write_file`/`patch_code` (M1);
- handler deterministico per `type=execute` (gcc + run, no LLM);
- Timestral predittivo (EMA/regressione);
- memoria persistente avanzata (preferenze utente);
- benchmark automatico dei modelli;
- USB protocol parser e differential analysis.

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

**BYTE-SWARMY v0.2.0**

```
/ˈbaɪt ˈswɔːrmi/  ·  "BYTE SWOR-mee"
```

> *"The swarm works. You think elsewhere."*
