#!/usr/bin/env bash
#
# ferma.sh — Ferma BYTE-SWARMY
#
# Ferma l'orchestratore (se attivo) in modo pulito (SIGTERM).
# La GUI viene chiusa manualmente dall'utente.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="state/orchestrator.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "○ Nessun orchestratore attivo"
    exit 0
fi

PID=$(cat "$PID_FILE")

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
echo
echo "Tutto fermato. Per riavviare: ./avvia.sh"
