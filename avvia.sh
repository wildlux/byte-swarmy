#!/usr/bin/env bash
#
# avvia.sh — Wrapper per byte-swarm.sh (backward compatibility)
#
# DEPRECATO: usa ./byte-swarm.sh direttamente.
# Questo wrapper mantiene la compatibilità con chi ha alias, script o
# abitudini che chiamano ./avvia.sh.
#
# Tutta la logica è stata spostata in byte-swarm.sh.
#
# Uso (invariato rispetto alla versione precedente):
#   ./avvia.sh              → ./byte-swarm.sh start
#   ./avvia.sh --gui        → ./byte-swarm.sh gui
#   ./avvia.sh --orch       → ./byte-swarm.sh orch
#   ./avvia.sh --status     → ./byte-swarm.sh status
#   ./avvia.sh --setup      → ./byte-swarm.sh setup
#
# Per fermare: ./ferma.sh  oppure  ./byte-swarm.sh stop
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Mappa argomenti vecchi → nuovi comandi
case "${1:-}" in
    --gui)        exec "$SCRIPT_DIR/byte-swarm.sh" gui ;;
    --orch)       exec "$SCRIPT_DIR/byte-swarm.sh" orch ;;
    --status)     exec "$SCRIPT_DIR/byte-swarm.sh" status ;;
    --setup)      exec "$SCRIPT_DIR/byte-swarm.sh" setup ;;
    --all|"")     exec "$SCRIPT_DIR/byte-swarm.sh" start ;;
    *)
        echo "❌ Argomento non riconosciuto: $1"
        echo "Usa: ./avvia.sh [--all|--gui|--orch|--status|--setup]"
        echo "Oppure (consigliato): ./byte-swarm.sh help"
        exit 1
        ;;
esac
