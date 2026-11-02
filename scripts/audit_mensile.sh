#!/usr/bin/env bash
#
# scripts/audit_mensile.sh — Lancia l'audit mensile di BYTE-SWARMY
#
# Genera:
#   - logs/audit/YYYY-MM-DD_audit.html  (report HTML leggibile)
#   - logs/audit/YYYY-MM-DD_audit.json  (report JSON machine-readable)
#   - logs/audit/latest.html            (symlink all'ultimo report)
#
# Uso:
#   ./scripts/audit_mensile.sh                 Genera report HTML + JSON
#   ./scripts/audit_mensile.sh --json          Solo JSON su stdout
#   ./scripts/audit_mensile.sh --quiet         Nessun output (per cron/scheduler)
#
# NOTA: byte-swarmy NON usa cron di sistema (è bandito da SAFETY/security.py:132).
# Questo script va lanciato dallo scheduler interno di byte-swarmy (task di tipo
# "monthly" con day=1, time="03:00") oppure manualmente con:
#   ./byte-swarm.sh audit
#
# Exit code: 0 se audit PASS (0 critical), 1 se FAIL (critical presenti).
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# Attiva venv se presente
if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || true
fi

# Directory dei report
AUDIT_DIR="logs/audit"
mkdir -p "$AUDIT_DIR"

# Timestamp ISO per il nome file
TIMESTAMP=$(date -u +"%Y-%m-%d")
DATE_TIME=$(date -u +"%Y-%m-%dT%H-%M-%S")

HTML_REPORT="$AUDIT_DIR/${TIMESTAMP}_audit.html"
JSON_REPORT="$AUDIT_DIR/${TIMESTAMP}_audit.json"
LATEST_HTML="$AUDIT_DIR/latest.html"
LATEST_JSON="$AUDIT_DIR/latest.json"

QUIET=false
JSON_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --quiet)  QUIET=true ;;
        --json)   JSON_ONLY=true ;;
    esac
done

if [ "$JSON_ONLY" = true ]; then
    exec python tests/test_monthly_audit.py --json
fi

if [ "$QUIET" = false ]; then
    echo "🔍 Avvio audit mensile BYTE-SWARMY..."
    echo "   Timestamp: $DATE_TIME (UTC)"
    echo "   Output:    $HTML_REPORT"
    echo
fi

# Esegui audit e salva i report
# --json va su stdout → lo catturiamo nel file JSON
# --html salva direttamente il file HTML
# --no-text evita output testuale extra su stdout (che finirebbe nel JSON)
python tests/test_monthly_audit.py --json --html "$HTML_REPORT" > "$JSON_REPORT" 2>"$AUDIT_DIR/.last_stderr.log"
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ] && [ "$QUIET" = false ]; then
    echo "⚠️  Audit completato con errori (exit $EXIT_CODE)"
    [ -s "$AUDIT_DIR/.last_stderr.log" ] && tail -5 "$AUDIT_DIR/.last_stderr.log"
fi
rm -f "$AUDIT_DIR/.last_stderr.log"

# Aggiorna symlink latest
ln -sf "$(basename "$HTML_REPORT")" "$LATEST_HTML"
ln -sf "$(basename "$JSON_REPORT")" "$LATEST_JSON"

# Estrai summary dal JSON
if command -v python3 &>/dev/null; then
    SUMMARY=$(python3 -c "
import json
try:
    with open('$JSON_REPORT') as f:
        data = json.load(f)
    s = data['summary']
    print(f\"{s['total']} {s['critical']} {s['warning']} {s['info']} {s['passed']}\")
except Exception:
    print('0 0 0 0 false')
" 2>/dev/null)
    if [ "$QUIET" = false ] && [ -n "$SUMMARY" ]; then
        TOTAL=$(echo "$SUMMARY" | awk '{print $1}')
        CRITICAL=$(echo "$SUMMARY" | awk '{print $2}')
        WARNING=$(echo "$SUMMARY" | awk '{print $3}')
        PASSED=$(echo "$SUMMARY" | awk '{print $5}')
        echo "═══════════════════════════════════════════════════════════"
        if [ "$PASSED" = "True" ]; then
            echo "  ✓ AUDIT PASS — 0 problemi critical"
        else
            echo "  ✗ AUDIT FAIL — $CRITICAL problemi critical"
        fi
        echo "  Totale finding: $TOTAL (critical: $CRITICAL, warning: $WARNING)"
        echo "  Report HTML: $HTML_REPORT"
        echo "  Report JSON: $JSON_REPORT"
        echo "═══════════════════════════════════════════════════════════"
    fi
fi

# Exit code: 0 se PASS, 1 se FAIL
if [ "$PASSED" = "True" ]; then
    exit 0
else
    exit 1
fi
