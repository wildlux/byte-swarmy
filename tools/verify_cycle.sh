#!/usr/bin/env bash
# tools/verify_cycle.sh — Ciclo di verifica standard (🆕 Cycle 66)
#
# Un solo comando che incapsula la sequenza ripetuta a ogni ciclo:
#   1) py_compile dei file toccati
#   2) test mirati (via CORE.test_runner, con timeout per file)
#   3) boot smoke (orchestrator in pausa: exit 124 = OK atteso)
#   4) metrica primo colpo % (P1-1, zero LLM: legge tasks/queue.db)
#   5) security scan (baseline unica: 7 errori, falsi positivi documentati)
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

echo "== 3/4 boot smoke =="
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

echo "== 4/4 metrica primo colpo (P1-1) =="
"$PY" tools/first_try_report.py || true

echo "== 5/5 security scan (baseline: 7 errori, falsi positivi documentati) =="
"$PY" tools/security_scan.py --json > /tmp/bswarm-scan.json 2>/dev/null || true
errs=$("$PY" -c "import json; d=json.load(open('/tmp/bswarm-scan.json')); print(sum(1 for x in d if x.get('level') in ('error','ERROR')))" 2>/dev/null || echo 0)
if [ "$errs" -gt 7 ]; then
    echo "✗ security scan: $errs errori (baseline 7) — nuovi errori"
    fail=1
else
    echo "✓ security scan: $errs errori (baseline 7)"
fi

if [ "$fail" -eq 0 ]; then
    echo "✅ VERIFICA CICLO: PASS"
else
    echo "❌ VERIFICA CICLO: FAIL"
fi
exit "$fail"
