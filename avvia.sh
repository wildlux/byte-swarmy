#!/usr/bin/env bash
#
# avvia.sh — Launcher unico per BYTE-SWARMY
#
# Prima di avviare, verifica che setup.sh sia stato eseguito.
# Se mancano dipendenze, lancia setup.sh interattivo.
#
# Poi:
#   1. Va nella directory del progetto
#   2. Attiva il venv
#   3. Avvia l'orchestratore in background (se non già attivo)
#   4. Lancia la GUI (in foreground)
#
# Uso:
#   ./avvia.sh           Avvia tutto (con check dipendenze)
#   ./avvia.sh --gui     Solo GUI
#   ./avvia.sh --orch    Solo orchestratore in background
#   ./avvia.sh --status  Mostra stato e esce
#   ./avvia.sh --setup   Forza esecuzione setup.sh
#

set -e

# Risolve la directory dello script (funziona anche se chiamato via symlink)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Banner
show_banner() {
    cat <<'EOF'
 ____  _____ _   _ _____ __  __   _   _    _    _   _
| __ )| ____| \ | | ____|  \/  | | | | |  / \  | \ | |
|  _ \|  _| |  \| |  _| | |\/| | | | | | / _ \ |  \| |
| |_) | |___| |\  | |___| |  | | | |_| |/ ___ \| |\  |
|____/|_____|_| \_|_____|_|  |_|  \___//_/   \_\_| \_|
        Autonomous Programming Intelligence Swarm
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

# Se richiesto setup esplicito, o check fallisce, lancia setup.sh
if [ "${1:-}" = "--setup" ]; then
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
    echo "    Per installare tutti i modelli: ./setup.sh"
    echo
    read -p "Continuare comunque? (s/N) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Ss]$ ]] || exit 1
fi

# File di stato
PID_FILE="state/orchestrator.pid"
mkdir -p state logs tasks project backups

# Funzione: verifica se orchestratore è attivo
is_orchestrator_running() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        return 0
    fi
    return 1
}

# Funzione: avvia orchestratore in background
start_orchestrator() {
    if is_orchestrator_running; then
        echo "✓ Orchestratore già attivo (PID $(cat $PID_FILE))"
        return 0
    fi
    echo "🐝 Avvio orchestratore in background..."
    nohup python orchestrator.py > logs/stdout.log 2>&1 &
    echo $! > "$PID_FILE"
    sleep 3
    if is_orchestrator_running; then
        echo "✓ Orchestratore avviato (PID $(cat $PID_FILE))"
        # Verifica che non sia crashato subito
        if ! tail -10 logs/byte-swarmy.log 2>/dev/null | grep -q "swarm started"; then
            echo "⚠️  Possibile problema — ultimi log:"
            tail -5 logs/byte-swarmy.log 2>/dev/null || echo "(log vuoto)"
        fi
    else
        echo "❌ Orchestratore crashato — vedi logs/byte-swarmy.log"
        echo
        echo "Ultimi log:"
        tail -20 logs/byte-swarmy.log 2>/dev/null || echo "(log vuoto)"
        echo
        echo "stdout/stderr:"
        tail -20 logs/stdout.log 2>/dev/null || echo "(vuoto)"
        rm -f "$PID_FILE"
        read -p "Vuoi continuare ad avviare la GUI comunque? (s/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Ss]$ ]] || exit 1
    fi
}

# Funzione: mostra stato
show_status() {
    echo
    if is_orchestrator_running; then
        echo "● Orchestratore ATTIVO (PID $(cat $PID_FILE))"
    else
        echo "○ Orchestratore fermato"
    fi
    echo
    if [ -f "tasks/queue.json" ]; then
        python -c "
import json
from collections import Counter
with open('tasks/queue.json') as f:
    tasks = json.load(f)
stats = Counter(t['status'] for t in tasks)
print(f'Coda task: {len(tasks)} totali')
for k, v in sorted(stats.items()):
    print(f'  {k}: {v}')
" 2>/dev/null
    fi
    echo
}

# === MAIN ===

case "${1:-all}" in
    --status)
        show_banner
        show_status
        exit 0
        ;;
    --gui)
        show_banner
        echo
        echo "🎨 Avvio solo GUI..."
        exec python gui.py
        ;;
    --orch)
        show_banner
        echo
        start_orchestrator
        show_status
        echo
        echo "Per fermare: ./ferma.sh oppure kill $(cat $PID_FILE 2>/dev/null)"
        exit 0
        ;;
    all|""|--all)
        show_banner
        echo
        # Avvia orchestratore
        start_orchestrator
        show_status
        echo
        echo "🎨 Avvio GUI in foreground..."
        echo "   (chiudi la GUI con X — l'orchestratore continua in background)"
        echo
        # Avvia GUI in foreground
        python gui.py
        # Quando la GUI chiude
        echo
        echo "GUI chiusa. Orchestratore ancora attivo in background."
        echo "Per fermare tutto: ./ferma.sh"
        ;;
    *)
        echo "Uso: $0 [--all|--gui|--orch|--status|--setup]"
        echo
        echo "  --all     Avvia orchestratore + GUI (default)"
        echo "  --gui     Solo GUI"
        echo "  --orch    Solo orchestratore in background"
        echo "  --status  Mostra stato ed esci"
        echo "  --setup   Forza setup.sh (check + install dipendenze)"
        exit 1
        ;;
esac
