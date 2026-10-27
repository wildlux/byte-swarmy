# REGOLA OPERATIVA (per questo repo e per i piccoli LLM)

> **Prima si scrive il task qui, poi si esegue.**
> Ogni modifica al codice deve avere una riga in questa lista con stato `[ ]` / `[x]`.
> I task devono essere piccoli, atomici e verificabili: un passo = una modifica.
> I worker LLM (0.5B–4B) ricevono solo tool sicuri, istruzioni brevi ed errori
> espliciti su *cosa* è bloccato e *come* fare l'alternativa corretta.

## REGOLA 0 — DIFESA SEMPRE ATTIVA (obbligatoria)

> **Ogni task è potenzialmente un prompt injection.** La difesa non è opzionale
> e non è delegata al modello:
>
> - la policy è applicata nel codice (`security.py` + `tools.py`) a **ogni**
>   chiamata di tool, sempre;
> - nessuna configurazione, prompt, task MCP, file letto o output di modello può
>   disattivarla;
> - `[security] enabled = false` in `config.toml` viene **ignorato** e registrato
>   come `CRITICAL` in `logs/security.log` (il flag resta solo per
>   retrocompatibilità);
> - i test devono dimostrare che la difesa resta attiva anche con una
>   configurazione ostile e con un modello che esegue l'iniezione.

## Ciclo 2 — difesa obbligatoria + README professionale (2026-10-26)

Richiesta: rendere la difesa sempre attiva (i task possono essere prompt
injection), riscrivere `README.md`, dichiarare in modo onesto lo stato delle
falle.

- [x] **1. `todo.md`** — scrivere questa sezione *prima* di modificare il codice (regola operativa).
- [x] **2. `tools.py`** — rimuovere il bypass `security.enabled`: la policy si applica sempre; se il config prova a disabilitarla, log `CRITICAL` e si continua.
- [x] **3. `orchestrator.py`** — rafforzare `Worker.SYSTEM`: la difesa è imposta dal layer dei tool, non dal prompt; nessuna istruzione nel task può annullarla.
- [x] **4. `config.toml`** — documentare che `enabled = false` è ignorato (retrocompatibilità).
- [x] **5. `tests/test_security.py`** — aggiungere: policy attiva con `enabled=false`; prompt injection (modello che esegue l'istruzione) non cancella un file sentinella fuori da `project/`.
- [x] **6. `README.md`** — riscrittura professionale: panoramica, architettura, requisiti, installazione, uso, CLI, GUI, sicurezza, troubleshooting, struttura, licenza.
- [x] **7. `SECURITY.md`** — aggiungere "Regola 0" e aggiornare la sezione sul flag disabilitato.
- [x] **8. Verifica** — `unittest`, `py_compile`, `bash -n`, `git diff --check`; aggiornare questo file con l'esito.

### Esito Ciclo 2 (2026-10-26)

- `python -m unittest discover -s tests -t . -v` → **27 test OK**
  (4 nuovi: config ostile, log CRITICAL, operazioni file iniettate, worker
  end-to-end con modello che obbedisce all'iniezione).
- `python -m py_compile` su tutti i moduli → OK.
- `bash -n` su tutti gli script → OK.
- `git diff --check` → OK.
- Il flag `[security] enabled = false` non disattiva più nulla: viene
  registrato come `CRITICAL` e la policy resta attiva.
- `README.md` riscritto e verificato contro i comandi reali (`avvia.sh`,
  `byte-swarmy`, `sync.sh`, tool list).
- `bswarm` riallineato a `byte-swarmy`: era una copia vecchia senza validazione
  del PID (rischio di terminare un processo sbagliato).


### Stato reale delle falle (onesto)

**Risolte a livello di codice (tutte quelle identificate nell'analisi):**

- esecuzione shell arbitraria (`bash -c`) → `shell=False` + allowlist/blacklist;
- path traversal / path assoluti / symlink escape → sandbox `project/`;
- lettura di `~/.ssh`, `.env`, `.git-credentials` → path sensibili e `HOME` sandbox;
- leak via `grep` ricorsivo → esclusioni obbligatorie;
- `git push/pull/remote add|remove` → disabilitati per i worker;
- ambiente ereditato con token/socket SSH → sanificato;
- task MCP non fidati → ricostruiti da zero con campi e URL validati;
- fork bomb / disco / RAM → limiti per processo e timeout sul process group;
- PID file manomesso → validazione numerica + `/proc/<pid>/cmdline`;
- `curl | python` nel setup → rimosso;
- server MCP di esempio esposto su `0.0.0.0` → solo loopback.

**Non risolte (richiedono isolamento di sistema, non codice):**

- il codice del progetto (`python`, `make`, `pytest`, binari) gira con i permessi
  dell'utente: può usare `socket`/`urllib` e leggere file leggibili dall'utente;
- non c'è seccomp/AppArmor/container;
- utente dedicato `byteswarmy`, cgroup e firewall **non sono applicati**:
  lo script `setup-hardening.sh` è pronto ma richiede root e va lanciato
  consapevolmente.

Quindi: **sì, tutte le falle correggibili nel codice sono state chiuse**;
**no**, il sistema non è ancora un sandbox completo finché non si applica
l'hardening di sistema. Per dati reali vale la regola: utente dedicato +
firewall, mai l'utente principale.

## Ciclo 3 — sandbox completo + test nella GUI (2026-10-27)

Richiesta: sandbox completo per il codice generato e test automatici visibili
dentro la GUI, con esito esplicito.

Vincoli verificati:

- `bubblewrap 0.11.1` disponibile; user namespace funzionanti senza root.
- `sudo` non è passwordless: l'hardening di sistema con utente dedicato/cgroup/
  firewall non può essere applicato automaticamente in questa sessione.
- Quindi il sandbox "completo" viene realizzato con bubblewrap unprivileged
  (filesystem, rete, PID, IPC, UTS, user namespace, capability dropped), mentre
  l'hardening root resta opzionale.

- [x] **1. `todo.md`** — scrivere il piano prima di modificare il codice.
- [x] **2. `sandbox.py`** — builder bubblewrap: root filesystem minimo, solo `project/` scrivibile, `/home` e `/tmp` temporanei, niente rete, PID/user/IPC separati, capability droppate, `--disable-userns`, ambiente pulito.
- [x] **3. `sandbox_selftest.py`** — test eseguito *dentro* il sandbox: home host invisibile, scrittura fuori bloccata, rete bloccata, scrittura progetto OK, PID host invisibile, variabili sensibili assenti, nesting user namespace bloccato.
- [x] **4. `tools.py`** — instradare **tutti** i sottoprocessi (`run_bash`, git, search) attraverso il sandbox; fail-closed se bubblewrap non è disponibile.
- [x] **5. `tests/test_sandbox.py` + test esistenti** — verificare il sandbox e aggiornare i test che assumevano l'esecuzione diretta.
- [x] **6. `tests/run_tests.py`** — runner unico con output JSON: unit test + sandbox self-test, conteggi PASS/FAIL/SKIP.
- [x] **7. `gui.py`** — nuovo tab "Test & Sandbox": stato bubblewrap, pulsante "Esegui test", tabella per singolo test, riepilogo, auto-run alla prima apertura.
- [x] **8. Integrazione** — `setup.sh` installa `bubblewrap`; `avvia.sh`/`setup-hardening.sh` controllano il sandbox; CI installa bubblewrap.
- [x] **9. Documentazione** — aggiornare `README.md` e `SECURITY.md` con sandbox, limiti e uso della GUI.
- [x] **10. Verifica** — unit test, sandbox self-test, `py_compile`, `bash -n`, `git diff --check`; aggiornare questo file.

### Cosa copre il sandbox e cosa resta fuori

**Coperto da bubblewrap (senza root):**

- filesystem: solo `/usr`, `/etc`, venv e `project/`; niente home reale;
- rete: network namespace separato, nessuna connessione in uscita;
- processi: PID namespace separato, processi host invisibili;
- utente/IPC/UTS: namespace separati;
- privilegi: `--cap-drop ALL`, `--disable-userns`, `no_new_privs`;
- ambiente: `--clearenv` + sole variabili sicure;
- risorse: rlimit e timeout già presenti, process group terminato.

**Fuori dal sandbox (richiede root o kernel):**

- seccomp filter custom e mitigazione di exploit del kernel;
- cgroup con `TasksMax`/`MemoryMax` e firewall per uid;
- utente dedicato `byteswarmy`.
  Restano disponibili con `sudo ./setup-hardening.sh --all`, ma non eseguiti qui.

## Ciclo 4 — Agent Power-Up: Tool Sofisticati (2026-10-27)

L'obiettivo è trasformare i worker in sviluppatori autonomi, riducendo l'uso di token e aumentando la precisione delle modifiche tramite tool di alto livello.

- [x] **1. `patch_code`** — Modifiche mirate (find-and-replace) invece di riscrivere l'intero file.
- [x] **2. `analyze_project`** — Mappa strutturale del progetto (classi, funzioni, dipendenze).
- [x] **3. `find_references`** — Ricerca di tutte le occorrenze di un simbolo per refactoring sicuro.
- [x] **4. `run_test_suite`** — Esecuzione automatizzata dei test con report di errore per self-healing.
- [x] **5. `lint_code`** — Analisi statica per correggere errori di sintassi prima dell'esecuzione.
- [x] **6. Aggiornamento `ToolSet`** — Integrazione e documentazione di tutti i nuovi tool.
- [x] **7. Prompt Tuning** — Istruzioni per i worker su come combinare i nuovi tool per workflow efficienti.
- [x] **8. Verifica** — Test di regressione e test di efficienza (riduzione token).

## Ciclo 5 — Professional Refactoring Suite (2026-10-27)

L'obiettivo è dare agli agenti la capacità di ristrutturare il codice in modo sicuro, coerente e professionale, riducendo il rischio di regressioni.

- [x] **1. `rename_symbol`** — Rinomina una variabile/classe/funzione in tutto il progetto (coerenza globale).
- [x] **2. `analyze_complexity`** — Calcola la complessità di una funzione per identificare i punti critti da rifattorizzare.
- [x] **3. `get_call_graph`** — Mappa le chiamate tra funzioni per l'analisi d'impatto.
- [x] **4. `extract_method`** — Sposta un blocco di codice in una nuova funzione e aggiorna la chiamata originale.
- [x] **5. Aggiornamento `ToolSet`** — Integrazione dei nuovi tool in `tools.py`.
- [x] **6. Refactor-Loop Prompting** — Istruzioni per l'agente su come usare questi tool in sequenza (Mappa $\rightarrow$ Modifica $\rightarrow$ Verifica).
- [x] **7. Verifica** — Test di regressione e test di refactoring su un progetto campione.

## Ciclo 6 — Enterprise Grade & Quality Assurance (2026-10-27)

L'obiettivo è elevare il sistema a standard Enterprise, introducendo una catena di comando con revisione incrociata, TDD obbligatorio e analisi statica avanzata.

- [x] **1. Audit Worker (The Reviewer)** — Implementazione di un secondo agente specializzato esclusivamente nella revisione del codice e della sicurezza.
- [x] **2. TDD Workflow (Test-First)** — Modifica dell'orchestratore per obbligare l'agente a scrivere e far fallire il test prima di implementare la soluzione.
- [x] **3. SAST Integration (Bandit)** — Integrazione di un analizzatore di sicurezza statico per rilevare vulnerabilità (es. `eval`, `pickle`) nel codice prodotto.
- [x] **4. Immutable Security Logs** — Passaggio a log strutturati (JSONL) per l'audit e la tracciabilità.
- [x] **5. Prompt Governance** — Versionamento dei prompt e salvataggio dei metadati della risposta (modello, temperatura, prompt) per ogni azione.
- [x] **6. Verifica e Stress Test** — Test di "attacco" per verificare che l'Audit Worker blocchi codice insicuro o non testato.


## Ciclo 7 — Fondamenta e Robustezza (Consolidamento)

L'obiettivo è trasformare BYTE-SWARMY da un prototipo avanzato a un sistema resiliente e stabile. Prima di aggiungere nuove feature, ci concentriamo sulla sopravvivenza del sistema e sulla eliminazione della fragilità strutturale.

### 🏗️ Resilienza dell'Orchestratore (Crash-Proofing)
- [ ] **1. System Watchdog** — Implementazione di un processo supervisore che monitora l'orchestratore e lo riavvia istantaneamente in caso di crash, garantendo la continuità del servizio.
- [ ] **2. Exception Hardening** — Revisione di ogni punto di chiamata LLM e Tool per gestire ogni possibile eccezione senza abbattere il loop principale.
- [ ] **3. State Recovery** — Ottimizzazione del ripristino dello stato da SQLite al riavvio, per minimizzare la perdita di contesto tra un crash e un restart.

### 🛡️ Validazione Deterministica (Zero-Trust)
- [ ] **4. AST Security Scanner** — Implementazione di uno scanner basato su Abstract Syntax Trees (AST) per bloccare l'esecuzione di codice Python pericoloso prima che entri nel sandbox.
- [ ] **5. Mandatory Static Checks** — Integrazione di `Bandit` e `Mypy` come gate obbligatori: se il codice non passa l'analisi statica, non viene nemmeno provato l'avvio.

### 🧠 Memoria Immutabile (Event Sourcing)
- [ ] **6. Event Sourcing Architecture** — Passaggio da "riassunti" a un log immutabile di eventi. Il riassunto diventa una vista, non la fonte della verità.
- [ ] **7. Memory Integrity Check** — Sistema di validazione dei buffer di memoria per prevenire il "drift" (perdita di contesto) durante la compattazione.

### 🔒 Hardening di Sistema Obbligatorio
- [ ] **8. Mandatory Isolation Check** — L'orchestratore deve verificare all'avvio se l'isolamento (utente dedicato/cgroups) è attivo; in caso contrario, attiva la "Safe Mode" con restrizioni estreme.
- [ ] **9. Automated Hardening Flow** — Integrazione di `setup-hardening.sh` nel flusso di installazione guidata per ridurre l'attrito dell'utente.

### 🔌 USB Analysis (Post-Consolidamento)
- [ ] **10. Protocol Parser** — Tool per l'analisi dei pacchetti USB (traduzione descrittori, endpoint, analisi payload).
- [ ] **11. Differential Analysis** — Tool per confrontare due catture USB e isolare i pacchetti di un'azione specifica.
