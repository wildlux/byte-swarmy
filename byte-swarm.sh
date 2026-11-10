#!/usr/bin/env bash
#
# byte-swarm.sh — Launcher unico per BYTE-SWARM
#
# Sostituisce i vecchi avvia.sh + ferma.sh con un solo script
# che gestisce avvio, arresto, stato e modalità GUI/orchestratore.
#
# Uso:
#   ./byte-swarm.sh                 Avvia orchestratore + GUI (default)
#   ./byte-swarm.sh start           Avvia orchestratore + GUI
#   ./byte-swarm.sh stop            Ferma l'orchestratore
#   ./byte-swarm.sh restart         Stop + start (solo orchestratore)
#   ./byte-swarm.sh status          Mostra stato ed esci
#   ./byte-swarm.sh gui             Solo GUI (orchestratore già attivo o no)
#   ./byte-swarm.sh orch            Solo orchestratore in background
#   ./byte-swarm.sh setup           Forza esecuzione setup.sh
#   ./byte-swarm.sh help            Mostra questo aiuto
#
# Comandi alias (backward compat con avvia.sh/ferma.sh):
#   ./byte-swarm.sh --all | --gui | --orch | --status | --setup
#

set -e

# Risolve la directory dello script (funziona anche se chiamato via symlink)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# === HARDENING DI BASE ===
# I worker LLM ereditano l'ambiente di questo processo: qui togliamo i
# segreti più comuni e limitiamo i danni collaterali.
umask 077
unset GITHUB_TOKEN GH_TOKEN GIT_TOKEN GIT_ASKPASS OLLAMA_API_KEY 2>/dev/null || true
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN 2>/dev/null || true
unset OPENAI_API_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY 2>/dev/null || true
unset DATABASE_URL DB_PASSWORD REDIS_URL HF_TOKEN 2>/dev/null || true
# I tool git dei worker non devono poter chiedere credenziali.
unset SSH_AUTH_SOCK SSH_AGENT_PID 2>/dev/null || true
export GIT_TERMINAL_PROMPT=0
export PYTHONDONTWRITEBYTECODE=1
# Niente core dump; file singolo max 1 GB (i limiti per-comando sono in tools.py).
ulimit -c 0 2>/dev/null || true
ulimit -f 1048576 2>/dev/null || true
ulimit -n 512 2>/dev/null || true

# === COSTANTI ===
PID_FILE="state/orchestrator.pid"
mkdir -p state logs tasks project backups

# === VARIABILI D'AMBIENTE OLLAMA ===
# Un solo modello caricato in RAM/VRAM alla volta (vincolo 4 GB):
# - OLLAMA_MAX_LOADED_MODELS=1 impedisce che due modelli restino in memoria
# - OLLAMA_KEEP_ALIVE=300 scarica il modello dopo 5 min di inattività
# Questo è fondamentale per far convivere il modello leggero (RAM) e il
# modello pesante (GPU) senza saturare la memoria.
export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-1}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-300}"

# === BANNER ASCII ART (font "standard" di figlet) ===
# Testo corretto: BYTE SWARM (non "byte-swarmy").
show_banner() {
    cat <<'EOF'
 ______   _______ _____   ______        ___    ____  __  __
| __ ) \ / /_   _| ____| / ___\ \      / / \  |  _ \|  \/  |
|  _ \\ V /  | | |  _|   \___ \\ \ /\ / / _ \ | |_) | |\/| |
| |_) || |   | | | |___   ___) |\ V  V / ___ \|  _ <| |  | |
|____/ |_|   |_| |_____| |____/  \_/\_/_/   \_\_| \_\_|  |_|
        Autonomous Programming Intelligence Swarm
EOF
}

show_help() {
    cat <<'EOF'
Uso: ./byte-swarm.sh <comando>

Comandi:
  (nessuno)         Avvia orchestratore + GUI (default)
  start             Avvia orchestratore + GUI
  stop              Ferma l'orchestratore (SIGTERM, poi SIGKILL)
  restart           Stop + start (solo orchestratore in background)
  status            Mostra stato ed esci
  gui               Solo GUI (orchestratore già attivo o no)
  orch              Solo orchestratore in background
  audit             Esegue l'audit mensile del software (report HTML+JSON in logs/audit/)
  lint              Lint: stile (lint_style) + sicurezza (security_scan) + igiene (git_hygiene)
  map               Mappa dinamica del repo (tools/repo_map.py; vedi DOCS/AGENT.md)
  setup             Forza esecuzione setup.sh (check + install dipendenze)
  help              Mostra questo aiuto

Alias (backward compat):
  --all | --gui | --orch | --status | --setup

Esempi:
  ./byte-swarm.sh                   # avvia tutto
  ./byte-swarm.sh stop              # ferma orchestratore
  ./byte-swarm.sh restart           # riavvia orchestratore
  ./byte-swarm.sh gui               # solo GUI (no orchestratore in background)
  ./byte-swarm.sh audit             # audit mensile (variabili, codice morto, porte, tunnel)
  ./byte-swarm.sh audit --json      # solo JSON su stdout
EOF
}

# === CHECK PRELIMINARE DIPENDENZE ===

check_quick() {
    # Check rapido: venv esiste e PyQt6 importabile?
    [ -d ".venv" ] || return 1
    source .venv/bin/activate 2>/dev/null || return 1
    python -c "import PyQt6, tomli_w" 2>/dev/null || return 1
    return 0
}

ensure_env() {
    # Se richiesto setup esplicito, o check fallisce, lancia setup.sh
    if [ "${SETUP_FORCE:-0}" = "1" ]; then
        if [ -f "./setup.sh" ]; then
            exec ./setup.sh
        else
            echo "❌ setup.sh non trovato in $SCRIPT_DIR"
            exit 1
        fi
    fi

    if ! check_quick; then
        show_banner
        echo
        echo "⚠️  Dipendenze non verificate o mancanti."
        echo "   Eseguo setup.sh per verificare e installare..."
        echo
        if [ -f "./setup.sh" ]; then
            chmod +x ./setup.sh
            ./setup.sh
            # Dopo setup, riattiva venv
            source .venv/bin/activate
        else
            echo "❌ setup.sh non trovato. Installa manualmente:"
            echo "   python3 -m venv .venv"
            echo "   source .venv/bin/activate"
            echo "   pip install -r requirements_gui.txt"
            exit 1
        fi
    fi

    # A questo punto il venv è attivo e PyQt6 è disponibile
    source .venv/bin/activate

    # Verifica anche modelli Ollama minimi (check veloce senza installare)
    if ! curl -s http://localhost:11434/api/tags | grep -q "qwen2.5:0.5b" 2>/dev/null; then
        echo "⚠️  Modello 'qwen2.5:0.5b' non trovato in Ollama."
        echo "    L'orchestratore potrebbe fallire."
        echo "    Per installare tutti i modelli: ./byte-swarm.sh setup"
        echo
        read -p "Continuare comunque? (S/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Nn]$ ]] || exit 1
    fi

    # Verifica modello pesante per worker_coder (GPU)
    if ! curl -s http://localhost:11434/api/tags | grep -q "qwen2.5-coder:3b" 2>/dev/null; then
        echo "ℹ️  Modello 'qwen2.5-coder:3b' non trovato in Ollama."
        echo "    Il worker_coder userà qwen2.5-coder:1.5b come fallback."
        echo "    Per installarlo: ollama pull qwen2.5-coder:3b"
        echo
    fi
}

# === FUNZIONI STATO ORCHESTRATORE ===

is_orchestrator_running() {
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null || true)
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    # Evita di considerare "orchestratore" un PID riutilizzato da altro.
    if [ -r "/proc/$pid/cmdline" ] && ! tr '\0' ' ' < "/proc/$pid/cmdline" | grep -qE "orchestrator|watchdog"; then
        return 1
    fi
    return 0
}

# === FUNZIONI AVVIO ===

start_orchestrator() {
    if is_orchestrator_running; then
        echo "✓ Orchestratore già attivo (PID $(cat "$PID_FILE" 2>/dev/null))"
        return 0
    fi
    echo "🐝 Avvio orchestratore via Watchdog..."
    nohup python -m SAFETY.watchdog > logs/watchdog.log 2>&1 &
    echo $! > "$PID_FILE"
    sleep 3
    if is_orchestrator_running; then
        echo "✓ Sistema avviato sotto protezione del Watchdog (PID $(cat "$PID_FILE" 2>/dev/null))"
        # Verifica che non sia crashato subito
        if ! tail -10 logs/byte-swarmy.log 2>/dev/null | grep -q "swarm started"; then
            echo "⚠️  Possibile problema — ultimi log:"
            tail -5 logs/byte-swarmy.log 2>/dev/null || echo "(log vuoto)"
        fi
    else
        echo "❌ Avvio fallito — vedi logs/watchdog.log e logs/byte-swarmy.log"
        echo
        echo "Ultimi log orchestratore:"
        tail -20 logs/byte-swarmy.log 2>/dev/null || echo "(log vuoto)"
        echo
        echo "stdout/stderr watchdog:"
        tail -20 logs/watchdog.log 2>/dev/null || echo "(vuoto)"
        rm -f "$PID_FILE"
        read -p "Vuoi continuare ad avviare la GUI comunque? (s/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Ss]$ ]] || exit 1
    fi
}

start_gui() {
    echo "🎨 Avvio GUI in foreground..."
    echo "   (chiudi la GUI con X — l'orchestratore continua in background)"
    echo
    # Avvia GUI in foreground (nuova interfaccia modulare: control_center + panels)
    python -m GUI.control_center
    # Quando la GUI chiude
    echo
    echo "GUI chiusa. Orchestratore ancora attivo in background."
    echo "Per fermare tutto: ./byte-swarm.sh stop"
}

# === FUNZIONI STOP ===

stop_orchestrator() {
    if [ ! -f "$PID_FILE" ]; then
        echo "○ Nessun orchestratore attivo"
        return 0
    fi

    local PID
    PID=$(cat "$PID_FILE" 2>/dev/null || true)

    # Non fidarsi del pid file: potrebbe essere vecchio o manomesso.
    if ! [[ "$PID" =~ ^[0-9]+$ ]]; then
        echo "❌ PID non valido in $PID_FILE: non tocco nessun processo."
        rm -f "$PID_FILE"
        return 1
    fi
    if [ -r "/proc/$PID/cmdline" ] && ! tr '\0' ' ' < "/proc/$PID/cmdline" | grep -qE "orchestrator|watchdog"; then
        echo "❌ Il PID $PID non è l'orchestratore: non lo termino."
        return 1
    fi

    if kill -0 "$PID" 2>/dev/null; then
        echo "🐝 Ferma orchestratore (PID $PID)..."
        kill -TERM "$PID"
        sleep 3
        if kill -0 "$PID" 2>/dev/null; then
            echo "⚠️  Non risponde a SIGTERM, invio SIGKILL"
            kill -9 "$PID" 2>/dev/null || true
        fi
        echo "✓ Orchestratore fermato"
    else
        echo "○ Processo $PID non trovato (già fermato)"
    fi

    rm -f "$PID_FILE"
}

# === FUNZIONI STATO ===

show_status() {
    # Status compatto su 1 riga: stato + PID + conteggio task
    local pid="" status_str="fermato" task_str=""
    if is_orchestrator_running; then
        pid=$(cat "$PID_FILE" 2>/dev/null)
        status_str="attivo (PID $pid)"
    fi
    if [ -f "tasks/queue.json" ]; then
        task_str=$(python3 -c "
import json
from collections import Counter
try:
    with open('tasks/queue.json') as f:
        tasks = json.load(f)
    stats = Counter(t['status'] for t in tasks)
    parts = [f'{k}:{v}' for k, v in sorted(stats.items())]
    print(f' — {len(tasks)} task (' + ', '.join(parts) + ')')
except Exception:
    pass
" 2>/dev/null)
    fi
    echo "● Orchestratore $status_str$task_str"
}

# === MAIN ===

# Normalizza l'argomento: accetta sia "start" che "--all"
cmd="${1:-start}"
case "$cmd" in
    --all|"")     cmd="start" ;;
    --gui)        cmd="gui" ;;
    --orch)       cmd="orch" ;;
    --status)     cmd="status" ;;
    --setup)      cmd="setup" ;;
    --help|-h)    cmd="help" ;;
esac

case "$cmd" in
    start)
        show_banner
        echo
        ensure_env
        start_orchestrator
        show_status
        echo
        start_gui
        ;;
    stop)
        show_banner
        echo
        stop_orchestrator
        echo
        echo "Tutto fermato. Per riavviare: ./byte-swarm.sh start"
        ;;
    restart)
        show_banner
        echo
        stop_orchestrator
        echo
        ensure_env
        start_orchestrator
        show_status
        echo
        echo "Per fermare: ./byte-swarm.sh stop"
        ;;
    status)
        show_banner
        show_status
        ;;
    gui)
        show_banner
        echo
        ensure_env
        echo "🎨 Avvio solo GUI..."
        exec python -m GUI.control_center
        ;;
    orch)
        show_banner
        echo
        ensure_env
        start_orchestrator
        show_status
        echo
        echo "Per fermare: ./byte-swarm.sh stop"
        ;;
    setup)
        SETUP_FORCE=1 ensure_env
        ;;
    audit)
        show_banner
        echo
        echo "🔍 Audit mensile del software..."
        echo
        exec "$SCRIPT_DIR/scripts/audit_mensile.sh" "$@"
        ;;
    lint)
        show_banner
        echo
        echo "🧹 Lint: stile + sicurezza + igiene git"
        echo
        "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/tools/lint_style.py" "$@" || true
        "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/tools/security_scan.py" "$@" || true
        "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/tools/git_hygiene.py" "$@" || true
        ;;
    map)
        show_banner
        echo
        exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/tools/repo_map.py" "$@"
        ;;
    help)
        show_banner
        echo
        show_help
        ;;
    *)
        echo "❌ Comando non riconosciuto: $cmd"
        echo
        show_help
        exit 1
        ;;
esac
