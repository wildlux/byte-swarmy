#!/usr/bin/env bash
#
# ferma.sh — Wrapper per byte-swarm.sh stop (backward compatibility)
#
# DEPRECATO: usa ./byte-swarm.sh stop direttamente.
# Questo wrapper mantiene la compatibilità con chi ha alias, script o
# abitudini che chiamano ./ferma.sh.
#
# Tutta la logica è stata spostata in byte-swarm.sh.
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/byte-swarm.sh" stop
