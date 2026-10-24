# BYTE-SWARMY

```
██████╗ ██╗   ██╗████████╗███████╗    ███████╗██╗    ██╗ █████╗ ██████╗ ███╗   ███╗██╗   ██╗
██╔══██╗╚██╗ ██╔╝╚══██╔══╝██╔════╝    ██╔════╝██║    ██║██╔══██╗██╔══██╗████╗ ████║╚██╗ ██╔╝
██████╔╝ ╚████╔╝    ██║   ███████╗    ███████╗██║ █╗ ██║███████║██████╔╝██╔████╔██║ ╚████╔╝
██╔══██╗  ╚██╔╝     ██║   ╚════██║    ╚════██║██║███╗██║██╔══██║██╔══██║██║╚██╔╝██║  ╚██╔╝
██████╔╝   ██║      ██║   ███████║    ███████║╚███╔███╔╝██║  ██║██║  ██║██║ ╚═╝ ██║   ██║
╚═════╝    ╚═╝      ╚═╝   ╚══════╝    ╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝
```

**Sistema di agenti autonomi locali per macchine con 4 GB di RAM.**
Nessun cloud, nessuna GPU, nessuna dipendenza da servizi esterni. Solo Ollama, Python e file JSON.

> *"The swarm works. You think elsewhere."*

---

## Cos'è BYTE-SWARMY

BYTE-SWARMY è un sistema multi-agente autonomo che gira interamente in locale su hardware modesto (4 GB di RAM, CPU only). È progettato per lavorare senza supervisione: riceve un task, lo scompone, lo esegue con worker specializzati, gestisce errori, salva stato su disco e ti permette di riprendere da dove aveva lasciato.

### Identità del nome

Il nome ha tre livelli di lettura simultanei:

| Lettura | Significato |
|---|---|
| **Byte** | Unità di memoria — il codice prodotto è fatto di byte |
| **Bite** | Morso (in inglese si pronuncia come "byte") — le api "mordono" i task, li scompongono |
| **Bee** | Ape (la lettera B in inglese) — lo sciame di agenti |

**Acronimo**: **B**yte-**S**warm **W**ith **A**utonomous **R**esource **M**anagement & **Y**ield

### Filosofia del progetto

- **Routing deterministico prima dell'LLM** — se una keyword matcha un worker, il planner viene bypassato. Risparmio token, latenza zero.
- **Stato = file JSON** — coda, memorie, heartbeat. Tutto ispezionabile con `cat`, tutto ripristinabile.
- **Write transazionale** — ogni scrittura passa per `tmp/` e poi `rename()` atomico. Nessuno stato inconsistente se l'agente crasha.
- **Memory compaction** — dopo 50 eventi l'orchestratore riassume in 300 token verso `long_term`. Il contesto non esplode mai.
- **Loop sequenziale** — niente thread, niente asyncio. Un tick ogni 30s: `safety → maintenance → dispatch → sleep`. Prevedibile.
- **Safety valves** — RAM > 80% → pausa. Disco < 1 GB → pausa. 10 fallimenti consecutivi → stuck. SIGTERM → shutdown pulito con unload dei modelli.

---

## Componenti del sistema

| Componente | Ruolo | Stack |
|---|---|---|
| Orchestratore | Loop principale, dispatch task, safety check, compaction | Python |
| Planner | Scompone task complessi in sotto-task (solo se il routing deterministico non basta) | Ollama (LLM) |
| Worker | Esegue il task atomico: code, file, shell, git | Ollama (LLM) |
| Decision Models | d3, tev1, nimble, clef, clef-flash, nimble-v3, pplx-decider, kev, laya, strands-decider | Ollama (LLM) |
| Generic Task Planner | Scompone task vaghi in Code task atomici usando il decision model attivo | Ollama (LLM) |
| Timestral | Monitor termico + dynamic tuning dei parametri (tick multiplier, max tasks/hour) | Python |
| MCP Client | Riceve task da server MCP esterni via SSE | Python |
| GUI PyQt6 | Control Center con 5 tab (Coda, MCP, Logs, Timestral, Config) | PyQt6 |
| CLI Launcher | `byte-swarmy` e alias `bswarm` | Bash |
| Backup | Snapshot git ogni 15 min + sync GitHub on-demand | git |

---

## Requisiti

- Linux (testato su Kubuntu/Ubuntu; dovrebbe girare su qualsiasi distro con Python 3.11+)
- Python 3.11+ (per `tomllib` in stdlib)
- Ollama installato e funzionante
- 4 GB RAM minimo (2 GB occupati dal modello, il resto per il sistema)
- PyQt6 (opzionale, solo per la GUI)
- git (per backup e sync)

### Modelli Ollama richiesti

```bash
# Orchestratore (700 MB)
ollama pull qwen2.5:0.5b

# Planner (2.2 GB)
ollama pull phi3:mini

# Worker coding (1 GB)
ollama pull qwen2.5-coder:1.5b

# Worker general (1 GB)
ollama pull qwen2.5:1.5b

# Embedding (274 MB)
ollama pull nomic-embed-text

# Decision model attivo (2.5 GB) — opzionale ma raccomandato
ollama pull tev1:4b
```

Altri decision models opzionali (vedi sezione `[decision_models]` in `config.toml`): `d3:2b`, `nimble:9b`, `clef-flash:9b`, `nimble-v3:9b`, `pplx-decider:27b`, `kev`, `laya`, `strands-decider:2b`.

---

## Installazione

```bash
# Clona o copia la directory
cd ~/Desktop/byte-swarmy

# Setup completo: verifica dipendenze, installa pacchetti, scarica modelli
./setup.sh
```

Lo script `setup.sh` verifica e installa in automatico:

- Presenza di Python, pip, git, Ollama (con installazione guidata se mancante)
- Pacchetti sistema (`python3-venv`, `python3-full`, `git`) — chiede conferma sudo
- Virtualenv `.venv/` con pip interno funzionante
- Pacchetti Python (`PyQt6`, `tomli-w`, `mcp`, `httpx`, `httpx-sse`, `uvicorn`, `starlette`)
- Modelli Ollama necessari (chiede prima di scaricare)
- Directory di lavoro: `state/`, `logs/`, `tasks/`, `project/`, `backups/`

---

## Avvio rapido

### 1. Avvia tutto il sistema

```bash
./avvia.sh
```

Attiva il virtualenv, avvia l'orchestratore in background e apre la GUI. Quando chiudi la GUI, l'orchestratore continua a girare in background.

Modalità alternative:

```bash
./avvia.sh --gui      # Solo GUI (orchestratore già attivo o manuale)
./avvia.sh --orch     # Solo orchestratore in background
./avvia.sh --status   # Solo stato, non avvia nulla
./avvia.sh --setup    # Forza setup.sh (check + install)
```

### 2. Verifica lo stato

```bash
./byte-swarmy status
# oppure
bswarm status
```

### 3. Ferma tutto (shutdown pulito)

```bash
./ferma.sh
```

Il segnale SIGTERM fa sì che l'orchestratore scarichi i modelli Ollama dalla RAM prima di uscire.

### 4. Sync su GitHub

```bash
./sync.sh "messaggio di commit"
```

Fa commit degli snapshot correnti e push (se il remote è configurato). Il backup locale automatico è già attivo ogni 15 minuti via timer interno.

---

## Struttura del progetto

```
byte-swarmy/
├── orchestrator.py          # Orchestratore + Planner + Worker + TaskQueue + GenericTaskPlanner
├── tools.py                 # ToolSet con 13 tool (6 base + 7 Git avanzati)
├── memory.py                # AgentMemory: 3 buffer (short/working/long_term) + compaction
├── ollama_client.py         # ModelClient con rotation automatica modelli
├── mcp_client.py            # MCPClient — connessione SSE a server MCP esterni
├── thermal_manager.py       # TimestralManager — monitor termico + dynamic tuning
├── example_mcp_server.py    # Server MCP di esempio (per test)
├── add_task.py              # Helper CLI per aggiungere task
├── gui.py                   # GUI PyQt6 con 5 tab (Control Center)
├── config.toml              # Tutti i parametri (modelli, timing, safety, routing, decision_models, thermal)
├── byte-swarmy              # CLI launcher (bash) — alias bswarm
├── avvia.sh                 # Launcher unico: venv + orchestratore + GUI
├── ferma.sh                 # Ferma orchestratore (SIGTERM, fallback SIGKILL)
├── setup.sh                 # Check + installazione automatica dipendenze
├── sync.sh                  # Helper commit + push GitHub
├── BYTE-SWARMY.desktop      # Voce di menu per Kubuntu/KDE
├── requirements_gui.txt     # Dipendenze Python
├── README.md
├── LICENSE                  # MIT
├── state/                   # Stato persistente (JSON)
│   ├── agents/              # Memorie agenti per worker
│   ├── timestral_history.json  # Storico termico 24h
│   └── orchestrator.pid
├── tasks/                   # Coda task (queue.json)
├── logs/                    # Log rotativo + stdout
├── project/                 # Codice prodotto dagli agenti (honey)
└── backups/                 # Backup giornalieri tar.gz (ultimi 7)
```

---

## Come funziona un tick

```
┌─────────────────────────────────────────────────────────────┐
│  ogni 30 secondi                                            │
│                                                             │
│  1. SAFETY CHECK    → RAM > 80%? Disco < 1 GB? → pausa      │
│  2. TIMESTRAL       → temperatura critica? → pausa termica  │
│  3. MAINTENANCE     → backup git ogni 15 min, compaction 1h │
│  4. DISPATCH        → leggi coda → routing → worker/planner │
│  5. EXECUTE         → worker.run(task) → risultato          │
│  6. PERSIST         → scrivi memory, eventi, stato          │
│  7. SLEEP 30s                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Routing deterministico (prima dell'LLM)

| Keyword nel task | Worker di destinazione |
|---|---|
| `scrivi`, `crea`, `implementa`, `fix`, `bug`, `hello world`, `semplice` | `worker_coder` (qwen2.5-coder) |
| `documenta`, `commenta`, `readme`, `spiega` | `worker_general` (qwen2.5:1.5b) |
| `type=generic` o `source=generic:*` | `GenericTaskPlanner` (decision model) |
| nessuna corrispondenza | `Planner` (phi3:mini) → scomposizione LLM |

Questo è il cuore dell'efficienza: l'LLM non viene chiamato per task che possono essere smistati con una regex.

### Timestral — Dynamic tuning

Il thermal manager campiona ogni 30 secondi temperatura, CPU load, frequenza, RAM e swap. In base alle soglie (configurabili in `config.toml`):

| Stato | Condizione | Effetto |
|---|---|---|
| `FAST` | temp < 50°C e load < 60% | `tick × 0.6`, raddoppia max_tasks/hour |
| `NORMAL` | temp tra 50-65°C | `tick × 1.0`, default |
| `SLOW` | temp 65-80°C | `tick × 1.7-2.5`, dimezza max_tasks/hour |
| `PAUSE` | temp > 90°C o CPU > 95% per 60s | Nessun dispatch, attesa raffreddamento |

Storico salvato in `state/timestral_history.json` (24h di campioni).

---

## GUI Control Center (PyQt6)

```bash
python gui.py
# oppure
./avvia.sh --gui
```

Cinque tab:

1. **Coda Task** — task in coda, in esecuzione, completati. 7 azioni: add, refresh, delete, reset, force re-run, delete subtasks, cleanup done. Code task in nero, Generic task in viola.
2. **MCP Servers** — configura server MCP esterni (URL SSE), polling automatico, discover tools
3. **Logs** — tail del log in tempo reale, auto-scroll, export
4. **Timestral** — 4 metric card live (temp/load/freq/mem), advice con icona, statistiche 24h, storico testuale
5. **Config** — editor bidirezionale form↔testo con validazione TOML live, pulsante "Copia errore", revert automatico su parametri invalidi

---

## MCP Client

BYTE-SWARMY può ricevere task da server esterni compatibili MCP. Il client è in `mcp_client.py`, configurabile dal tab MCP Servers della GUI.

### Server MCP di esempio

```bash
# In un altro terminale
./byte-swarmy mcp start
```

Espone `http://localhost:8080/sse` con 3 tool: `get_pending_tasks`, `add_task`, `clear_outbox`.

I task ricevuti vengono accodati come qualsiasi altro task, con `source=mcp:<server_name>`. Utile per integrare con IDE, editor o altri agenti.

---

## Decision Models

Sezione `[decision_models]` in `config.toml` configura i modelli decisionali disponibili (referenziati da https://ollama.com/search?c=decision):

| Modello | Tag | Dimensione | Note |
|---|---|---|---|
| **tev1** | `tev1:4b` | 2.5 GB | Together AI, fast classification (default attivo) |
| **d3** | `d3:2b` | 1.3 GB | Scored choices, yes/no, ratings |
| **nimble** | `nimble:9b` | 5.5 GB | Bespoke Labs, typed classification |
| **clef** | `clef:27b` | 16 GB | Cloudflare, multimodal (cloud o locale) |
| **clef-flash** | `clef-flash:9b` | 5.5 GB | Versione flash di clef |
| **nimble-v3** | `nimble-v3:9b` | 5.5 GB | Bespoke Labs v3: classification, routing, scoring |
| **pplx-decider** | `pplx-decider:27b` | 16 GB | Perplexity, fine-tuned da Qwen3.8-27B |
| **kev** | `kev` | — | Scores answers in one forward pass |
| **laya** | `laya` | 421 MB | Convai, ultra light (ModernBERT-large) |
| **strands-decider** | `strands-decider:2b` | 1.3 GB | Strands Agents, classification/routing/scoring |

Il modello attivo si sceglie con `active = "tev1"` (o un altro). Il `GenericTaskPlanner` lo usa per scomporre i Generic Task in Code task atomici.

---

## Safety valves in dettaglio

| Condizione | Azione |
|---|---|
| RAM > 80% | Pausa dispatch, log warning, riprende quando scende |
| Disco libero < 1 GB | Pausa, blocca nuove scritture |
| Temperatura CPU > 90°C | Pausa termica, attesa raffreddamento |
| CPU load > 95% per 60s | Pausa, evita thrashing |
| 10 fallimenti consecutivi | Stato → stuck, richiede intervento manuale (`bswarm queue reset <id>`) |
| SIGTERM | Shutdown pulito: salva stato, scarica modelli, esce con codice 0 |
| Task > 8 step senza `done` | Marcato fallito, va in retry (max 10 volte) |

---

## Comandi CLI

```bash
# Avvio / arresto
byte-swarmy start              # Avvia orchestratore in background
byte-swarmy stop               # Ferma orchestratore (SIGTERM)
byte-swarmy gui                # Avvia GUI
byte-swarmy status             # Stato: PID, coda, ultimo campione termico

# Coda task
byte-swarmy queue list
byte-swarmy queue add <title> [desc]
byte-swarmy queue add-generic <title> [desc]   # Scomposto dal decision model
byte-swarmy queue reset <id>                   # Reset a pending
byte-swarmy queue cleanup                      # Elimina tutti i task done

# Timestral
byte-swarmy thermal            # Ultimo campione
byte-swarmy thermal history    # Ultimi 30 campioni

# Codice prodotto (honey)
byte-swarmy honey              # ls project/
byte-swarmy honey log          # git log del project/

# Log
byte-swarmy logs               # Tail del file di log (Ctrl+C per uscire)

# MCP
byte-swarmy mcp start          # Avvia server MCP di esempio
byte-swarmy mcp list           # Lista server MCP configurati

# Config
byte-swarmy config edit        # Apri config.toml in $EDITOR

# Varie
byte-swarmy version
byte-swarmy help
```

Alias: `bswarm` (symlink a `byte-swarmy`)

---

## Sincronizzazione con GitHub

### Setup iniziale (una volta sola)

```bash
# 1. Crea repo su https://github.com/new (nome: byte-swarmy)
# 2. Crea PAT su https://github.com/settings/tokens (scope: repo)
# 3. Configura git locale
git config --global user.name "Il Tuo Nome"
git config --global user.email "tua.email@example.com"
git config --global init.defaultBranch main
git config --global credential.helper store

# 4. Collega il remote (SOSTITUISCI ghp_xxx con il tuo PAT)
cd ~/Desktop/byte-swarmy
git remote add origin https://USERNAME:ghp_TUO_TOKEN@github.com/USERNAME/byte-swarmy.git
git push -u origin main --force
```

### Workflow quotidiano

```bash
# Sync con un comando
./sync.sh "descrizione delle modifiche"

# Solo pull (se hai lavorato da altro PC)
./sync.sh --pull

# Vedi stato
./sync.sh --status

# Vedi ultimi 20 commit
./sync.sh --log
```

---

## Primo task: validare il loop end-to-end

Prima di lanciare task seri, usa un task minuscolo per verificare che tutto funzioni:

```bash
./byte-swarmy queue add "Hello world in C" \
  "Crea il file project/hello.c con un programma C che stampa 'Hello from BYTE-SWARMY!' seguito da newline. Compila con gcc project/hello.c -o project/hello e verifica che project/hello produca l'output atteso. Massimo 30 righe di codice."

./avvia.sh
```

Se in `project/hello.c` trovi il sorgente e in `logs/byte-swarmy.log` vedi i tick di esecuzione → il loop funziona.

### Esempio di Generic Task

```bash
./byte-swarmy queue add-generic "Sistema di note CLI" \
  "Voglio un sistema per prendere appunti da terminale. Comandi: add <text>, list, search <text>, delete <id>. Storage su file JSON. Massimo 250 righe totali."
```

Il decision model analizzerà la descrizione e genererà 2-8 Code task atomici, che verranno accodati automaticamente.

---

## Punti chiave del design

1. **Loop sequenziale**: niente thread, niente asyncio. `tick → safety → maintenance → dispatch → sleep 30s`.
2. **Routing deterministico prima dell'LLM**: keyword match → worker diretto, bypassa il planner e risparmia token.
3. **Stato = file JSON**: coda, memorie, heartbeat. Tutto ispezionabile, tutto ripristinabile.
4. **Write transazionale**: `write_file` passa per `tmp/` poi `rename()` atomico — nessuno stato inconsistente se l'agente crasha a metà.
5. **Memory compaction**: dopo 50 eventi, l'orchestratore stesso riassume in 300 token → `long_term`. Evita contesti che esplodono.
6. **Safety valves**: RAM > 80% → pausa; disco < 1 GB → pausa; temp > 90°C → pausa; 10 fallimenti → stuck; SIGTERM → shutdown pulito con unload modelli.
7. **Rotation modelli**: un solo LLM caricato in RAM alla volta. Caricamento/scaricamento esplicito via `keep_alive=0`.
8. **Backup automatici**: snapshot git ogni 15 min, tar.gz ogni 24h (ultimi 7 conservati).

---

## Limiti noti (con 4 GB RAM)

- **Un solo modello caricato alla volta**: rotation esplicita (carica/scarica)
- **Worker sequenziali**: niente parallelismo. Un task alla volta
- **Contesto 4096 token max**: se il task è più grande, il planner lo spezza
- **Output LLM max 2048 token**: il worker non può generare file enormi in un colpo
- **Modelli 1B-4B**: bravi su task discreti, falliscono su architetture complesse

---

## Troubleshooting

| Sintomo | Causa | Fix |
|---|---|---|
| `ModuleNotFoundError: PyQt6` | Dipendenze non installate | `./setup.sh` o `pip install -r requirements_gui.txt` |
| `ModuleNotFoundError: mcp` | Solo task locali disponibili | `pip install mcp httpx httpx-sse` (la GUI offre auto-install) |
| GUI parte ma tab MCP vuoto | Modulo mcp non caricato | Guarda il banner giallo nel tab MCP |
| MCP server "connection refused" | Server non avviato | `./byte-swarmy mcp start` in altro terminale |
| Orchestratore non parte | Venv non attivo | `source .venv/bin/activate` prima di avviare |
| Status "fermato" anche dopo Avvia | Subprocess crashato | Guarda `logs/byte-swarmy.log` per errori |
| RAM saturata | Modelli non si scaricano | Verifica `keep_alive=0` nel log |
| Task sempre `stuck` | Prompt troppo difficile | Spezza in sottotask più piccoli o usa Generic task |
| `tomli_w non installato` | Dipendenza writer mancante | `pip install tomli-w` (la GUI offre auto-install) |
| Push GitHub fallisce con `Authentication failed` | Token errato/scaduto | Crea nuovo PAT su https://github.com/settings/tokens |
| Push fallisce con `repository not found` | URL remoto sbagliato | `git remote set-url origin https://USERNAME:ghp_TOKEN@github.com/USERNAME/byte-swarmy.git` |
| Push fallisce con `Updates were rejected` | Remote ha commit non locali | `./sync.sh --pull` poi `./sync.sh` |

---

## Compatibilità

- **OS**: Linux (testato su Kubuntu/Ubuntu). Su Windows/Mac disabilitare Timestral nel config.
- **Python**: 3.11+ (per `tomllib` in stdlib). Su 3.10 installa `tomli`.
- **RAM**: 4 GB minimo, 8 GB consigliato.
- **Ollama**: qualsiasi versione recente.

---

## Roadmap

- [ ] Worker paralleli via subprocess (solo se RAM > 8 GB)
- [ ] Embedding per memoria semantica (cercare task simili già risolti)
- [ ] Test runner automatico come hook post-commit
- [ ] Modello grande on-demand per task `needs_human`
- [ ] Dashboard grafici Timestral (matplotlib nella GUI)
- [ ] Integrazione HuggingFace per download automatico nuovi modelli
- [ ] TUI curses per monitorare la coda in tempo reale da terminale

---

## Contribuire

Il progetto è pensato per essere modificato. Le aree più aperte:

- Nuovi decision models (configurabili in `config.toml`)
- Nuovi worker specializzati (test runner, database, refactoring)
- Nuovi hook post-commit (lint, format, test)
- Nuovi adapter MCP per integrazioni esterne
- Dashboard Timestral con matplotlib

Prima di aggiungere qualcosa, chiediti: *"Lo farebbe girare su 4 GB di RAM senza cloud?"* Se la risposta è sì, è benvenuto.

---

## Licenza

MIT License — vedi file [LICENSE](LICENSE).

---

## Ringraziamenti

- [Ollama](https://ollama.com) per i modelli locali
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) per la GUI
- [MCP](https://modelcontextprotocol.io) per il protocollo di task distribution
- I modelli decisionali di [Together AI](https://www.together.ai/), [Bespoke Labs](https://www.bespoke.co/), [Cloudflare](https://www.cloudflare.com/), [Perplexity](https://www.perplexity.ai/), [Strands Agents](https://strandsagents.com/) e [Convai](https://convai.com/)

---

## Versione

**BYTE-SWARMY v0.1.0**

```
/ˈbaɪt ˈswɔːrmi/  ·  "BYTE SWOR-mee"
```

> *"The swarm works. You think elsewhere."*
