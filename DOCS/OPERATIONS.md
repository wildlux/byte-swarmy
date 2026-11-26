# 🛠️ BYTE-SWARMY — Operations

> Comandi operativi e protocolli di sessione. Le regole vincolanti per i
> modelli piccoli restano in [`AGENT.md`](../AGENT.md); l'architettura estesa è
> in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Shell commands — quick operational reference

The commands an agent uses most to keep BYTE-SWARMY alive and bug-free (they
avoid re-deriving paths/flags each session, saving tokens):

```bash
# ── Sintassi veloce (zero token su errori formali) ──────────────
.venv/bin/python -m py_compile <file.py>          # check singoli file
.venv/bin/python -m pytest tests/ -q              # suite completa

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
# todo.md vive in root, IMPLEMENTED.md vive in DOCS/ (risoluzione
# indipendente; backward-compat con entrambi i file in DOCS/ o in root).

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

# ── Audit statico (stile, sicurezza, igiene git) ────────────────
.venv/bin/python tools/lint_style.py        # stile/leggibilità + guardia tema
.venv/bin/python tools/lint_style.py --fix  # auto-fix trailing ws + newline
.venv/bin/python tools/security_scan.py     # pattern pericolosi (exit 2 = blocca)
.venv/bin/python tools/git_hygiene.py      # igiene repo (bak, grandi, ws)
# Orchestrazione: ./byte-swarm.sh lint (esegue i tre in sequenza)

# ── Push manuale (MAI git push automatici) ──────────────────────
./scripts/dev/sync.sh

# ── GUI offscreen (debug tema/widget senza display) ─────────────
QT_QPA_PLATFORM=offscreen .venv/bin/python <script_di_smoke>
# Tema: GUI/theme/theme.py → set_prop(w, "role", "muted"/"alert"),
# set_banner(w, "info"/"ok"/"error"/"warn"). MAI setStyleSheet inline
# con colori hardcodati nei pannelli: rompono il tema live (e un
# stylesheet "declaration-only" su un antenato azzera i bottoni figli).
```

### Scorciatoie tastiera (globali, in GUI)

- `Backspace` → "Indietro alla Plancia" (fuori dagli editor di testo)
- `/` → focus sul campo comando in basso + inserisce `/`
- I pulsanti "Indietro" mostrano `(Backspace)` nel label.

Hard rules encoded in these commands: never `git push`/`pull` by hand, never
block the Qt main thread, never `time.sleep` in the task runner (use
`Event.wait` + single-threaded loop).

---

## 2. Comandi di esplorazione e refactoring

Permettono a un agente locale (Ollama) di mappare, modificare e verificare il
codice senza dover re-derivare path/flag ogni volta.

```bash
# 1. Cerca un pattern in tutto il progetto (file Python)
grep -rn "PATTERN" --include="*.py" . | grep -v __pycache__ | grep -v .venv

# 2. Conta righe per file (trova i file troppo grandi da spezzare)
find . -name "*.py" -not -path "./.venv/*" -not -path "./.git/*" \
  -not -path "./__pycache__/*" -exec wc -l {} + 2>/dev/null | sort -rn | head -20

# 3. Verifica che un file modificato compili (syntax check, nessun import)
.venv/bin/python -m py_compile <percorso/file.py>

# 4. Lancia la suite di test unitari
.venv/bin/python -m pytest tests/ -q

# 5. Lancia solo un file di test specifico
.venv/bin/python -m pytest tests/test_reuse.py tests/test_weight_space.py -q

# 6. Test GUI senza display (offscreen, per smoke test widget/tema)
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "import sys; sys.path.insert(0, '.'); from GUI.<modulo> import <Classe>; ..."

# 7. Script inline rapido (esplorazione, non salva file)
.venv/bin/python -c "import sys; sys.path.insert(0, '.'); from CORE.<modulo> import <funzione>; print(...)"

# 8. Leggi una sezione precisa di un file (evita output enorme)
sed -n 'X,Yp' <percorso/file.py>

# 9. Ultimi commit (cosa è stato toccato di recente)
git log --oneline -10
git status --short

# 10. Controlla se un simbolo/stringa è hardcodato ovunque
grep -rn "http://localhost:11434" --include="*.py" . | grep -v __pycache__ | grep -v .venv
grep -rn "4096" --include="*.py" CORE GUI | grep -v __pycache__ | grep -v .venv
```

---

## 3. OLLAMA_SML_AGENT — isolamento e test di un modello piccolo (SML)

Questa sezione definisce un protocollo per testare in isolamento un modello
locale piccolo (es. `qwen2.5:1.5b`, `phi3:mini`) sui task di BYTE-SWARMY.
Obiettivo: verificare se il modello SML riesce a seguire prompt rigidi,
parsificare output JSON, rispettare i path di sicurezza e non andare in loop.

### 3.1 Verifica che Ollama sia attivo e il modello SML caricato

```bash
curl -s http://localhost:11434/api/tags | python3 -m json.tool | head -40
# Oppure: .venv/bin/python -c "from CORE.model_selector import get_ollama_models; print(get_ollama_models())"
```

### 3.2 System prompt per il modello SML

Salva questo testo in `state/sml_agent/system_prompt.txt` e usalo come system
prompt.

````text
Sei un agente di sviluppo per BYTE-SWARMY. Rispondi SOLO in italiano.
Regole assolute:
1. Non aggiungere testo prima o dopo il JSON richiesto.
2. Non usare markdown ```json ... ``` intorno alla risposta.
3. Se non sai la risposta, rispondi con {"errore": "non so", "dettaglio": "..."}.
4. Non eseguire comandi shell, non inventare percorsi fuori da project/.
5. Output finale: solo JSON valido, niente spiegazioni.

Task di esempio: dato un percorso di file, rispondi se è sicuro scriverlo
dentro project/. Usa solo caratteri alfanumerici, punto, barra, underscore.
````

```bash
mkdir -p state/sml_agent
```

### 3.3 Test atomico livello 1 — Parsing JSON

Il modello deve rispondere solo JSON.

```bash
curl -s http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5:1.5b","prompt":"RISPONDI SOLO CON: {\"nome\":\"prova\",\"valore\":42}","stream":false,"options":{"temperature":0,"num_predict":64}}'
```

Il modello dovrebbe rispondere esattamente con quel JSON, niente altro.

### 3.4 Test atomico livello 2 — Safe project path

Prompt: "Il percorso 'sub/file.txt' è sicuro dentro project/? Rispondi SOLO con
JSON `{\"sicuro\": true/false, \"motivo\": \"...\"}`".

### 3.5 Test atomico livello 3 — Refactoring minuscolo

Prompt: "Dividi questa funzione Python in due: una che legge e una che scrive.
Rispondi SOLO con JSON `{\"funzione_lettura\": \"...\", \"funzione_scrittura\":
\"...\"}`".

### 3.6 Test rapido via Python (alternativa a curl)

```bash
.venv/bin/python -c "
import sys, json, urllib.request
sys.path.insert(0, '.')
payload = json.dumps({'model':'qwen2.5:1.5b','prompt':'RISPONDI SOLO CON: {\"test\":\"ok\"}','stream':False,'options':{'temperature':0,'num_predict':32}}).encode()
req = urllib.request.Request('http://localhost:11434/api/generate', data=payload, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read())
    print(data.get('response',''))
"
```

### 3.7 Dove salvare i risultati

Tutti i log di test vanno in `state/sml_agent/` (mai in `CONFIG/` o `logs/` di
sicurezza). Esempio: `state/sml_agent/test_20261109_parse_json.json`.

### 3.8 Criteri di successo

Il modello SML è promosso se supera tutti e 3 i test atomici:

- **Livello 1**: output è JSON valido, niente testo extra.
- **Livello 2**: campo `"sicuro"` booleano corretto, motivo presente.
- **Livello 3**: entrambe le chiavi presenti, codice Python sintatticamente
  valido.
- **Fallimento**: output contiene markdown con tre backtick, testo prima del
  JSON, o JSON non parsabile.

Nota: se il modello fallisce il livello 1, non procedere con i livelli 2 e 3.
Se supera tutti, è candidato per task di orchestrator semplici (swarm command
diretti, non task di coding complessi).
