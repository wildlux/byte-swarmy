#!/bin/bash
# 🌀 Avvio di Ventola (controllo ventole HP via nbfc + pkexec)
cd "$(dirname "$0")/.."
exec .venv/bin/python VENTOLA/ventola.py "$@"
