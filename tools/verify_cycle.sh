#!/usr/bin/env bash
# tools/verify_cycle.sh — Ciclo di verifica standard (🆕 Cycle 66)
#
# Un solo comando che incapsula la sequenza ripetuta a ogni ciclo:
#   1) py_compile dei file toccati
#   2) test mirati (via CORE.test_runner, con timeout per file)
#   3) boot smoke (orchestrator in pausa: exit 124 = OK atteso)
#
# Automazione deterministica, NON un LLM che genera comandi:
# zero LLM, zero calore, stessa disciplina rigorosa.
#
# Uso:
#   ./tools/verify_cycle.sh CORE/worker.py GUI/cc_shell.py   # ciclo tipico
#   ./tools/verify_cycle.sh                                  # default: CORE/
#   TEST_CATEGORY=fuzz ./tools/verify_cycle.sh               # categoria diversa
#
# Variabili d'ambiente:
#   TEST_CATEGORY  categoria test_runner (default: tutti)
#   TEST_TIMEOUT   timeout per file in secondi (default: 120)
#   PY             interprete python (default: .venv/bin/python)

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
CATEGORY="${TEST_CATEGORY:-tutti}"
TTIMEOUT="${TEST_TIMEOUT:-120}"

fail=0

files=("$@")
if [ ${#files[@]} -eq 0 ]; then
    files=(CORE/*.py)
fi

echo "== 1/3 py_compile (${#files[@]} file) =="
if ! "$PY" -m py_compile "${files[@]}"; then
    echo "✗ py_compile FALLITO"
    fail=1
fi

echo "== 2/3 test mirati (categoria: $CATEGORY, timeout: ${TTIMEOUT}s/file) =="
if ! "$PY" -m CORE.test_runner --categoria "$CATEGORY" --timeout "$TTIMEOUT"; then
    echo "✗ test FALLITI"
    fail=1
fi

echo "== 3/3 boot smoke =="
touch state/pause.flag
timeout 15 "$PY" -m CORE.orchestrator CONFIG/config.toml >/dev/null 2>&1
smoke_rc=$?
rm -f state/pause.flag
if [ "$smoke_rc" -eq 124 ] || [ "$smoke_rc" -eq 0 ]; then
    echo "✓ boot smoke OK (rc=$smoke_rc: avvio in pausa o shutdown pulito)"
else
    echo "✗ boot smoke FALLITO (rc=$smoke_rc)"
    fail=1
fi

if [ "$fail" -eq 0 ]; then
    echo "✅ VERIFICA CICLO: PASS"
else
    echo "❌ VERIFICA CICLO: FAIL"
fi
exit "$fail"
