#!/usr/bin/env bash
set -uo pipefail

###############################################################################
# compile_sml.sh — Compilazione moduli OLLAMA_SML_AGENT
#
# Esegue py_compile su tutti i file Python del package OLLAMA_SML_AGENT
# per verificare la sintassi senza importare (nessuna dipendenza esterna
# necessaria oltre a Python).
#
# Uso:
#   ./compile_sml.sh              # compila tutti i file
#   ./compile_sml.sh --file X     # compila solo un file specifico
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Lo script si trova nella root del progetto, quindi PROJECT_ROOT è SCRIPT_DIR stesso
PROJECT_ROOT="$SCRIPT_DIR"

# Trova l'interprete Python: prima .venv, poi python3 di sistema
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
PYTHON_CMD=""
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON_CMD="$VENV_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "ERRORE: nessun interprete Python trovato (.venv/bin/python, python3 o python)." >&2
    exit 1
fi

# Lista file da compilare (aggiungi qui nuovi file quando li crei)
FILE_LIST=(
    "OLLAMA_SML_AGENT/config.py"
    "OLLAMA_SML_AGENT/model_discovery.py"
    "OLLAMA_SML_AGENT/prompt_manager.py"
    "OLLAMA_SML_AGENT/evaluator.py"
    "OLLAMA_SML_AGENT/auto_optimizer.py"
    "OLLAMA_SML_AGENT/ensemble_runner.py"
    "OLLAMA_SML_AGENT/cli.py"
    "OLLAMA_SML_AGENT/run_optimization_loop.py"
    "OLLAMA_SML_AGENT/sml_tester_senior.py"
    "OLLAMA_SML_AGENT/sml_tester.py"
    "OLLAMA_SML_AGENT/logbook.py"
)

cd "$PROJECT_ROOT"

if [[ "${1:-}" == "--file" && -n "${2:-}" ]]; then
    FILE_LIST=("$2")
fi

echo "Compilazione moduli OLLAMA_SML_AGENT (interprete: $PYTHON_CMD)..."
errori=0
for f in "${FILE_LIST[@]}"; do
    if [[ -f "$f" ]]; then
        echo "  [compile] $f"
        if ! "$PYTHON_CMD" -m py_compile "$f"; then
            echo "  ERRORE: $f" >&2
            errori=$((errori + 1))
        fi
    else
        echo "  AVVISO: file non trovato: $f" >&2
        errori=$((errori + 1))
    fi
done

echo ""
if [[ $errori -eq 0 ]]; then
    echo "Compilazione completata con successo (${#FILE_LIST[@]} file)."
    exit 0
else
    echo "Compilazione terminata con $errori errore/i." >&2
    exit 1
fi
