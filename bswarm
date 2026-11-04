#!/usr/bin/env bash
# bswarm — Unified dispatcher for byte-swarmy
# Internamente usa avvia.sh/ferma.sh (sistema corretto: CORE.orchestrator + Watchdog + SQLite)
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

# Python nel venv locale
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

PID_FILE="state/orchestrator.pid"
LOG_FILE="logs/byte-swarmy.log"
DB_FILE="tasks/queue.db"
THERMAL_HISTORY="state/timestral_history.json"

usage() {
    cat <<EOF
🐝 byte-swarmy — Autonomous Programming Intelligence Swarm

Usage: ./bswarm <command> [args]

Comandi principali:
  start [--orch]      Avvia orchestratore (+ GUI se senza --orch)
  stop                Ferma orchestratore + watchdog
  status              Mostra stato (PID, task, modelli ollama, thermals)
  restart             Stop + start --orch
  logs [-f] [N]       Ultimi N log (default 30, -f per follow)

Gestione task (SQLite):
  queue list          Lista task nella coda
  queue add <title> [desc]  Aggiungi Code task
  queue cleanup       Elimina task done/failed
  tasks               Alias di 'queue list'

Monitoring:
  thermal             Ultimo campione termico
  thermal history     Storico (ultimi 30 campioni)
  honey               Codice prodotto (ls project/)
  honey log           Git log di project/

Dev / Setup:
  sync                Git push (was scripts/dev/sync.sh)
  setup <target>      all | gpu | hardening | usbmon
  config edit         Apri config in \$EDITOR

Alias legacy:
  avvia -> start      ferma -> stop

Esempi:
  ./bswarm start --orch
  ./bswarm queue add "Crea hello.c" "Stampa Hello BYTE-SWARMY"
  ./bswarm status
EOF
}

cmd_status() {
    # 1. Check PID file
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
        echo "● Orchestratore ATTIVO (PID $(cat "$PID_FILE"))"
    else
        # 2. Fallback: cerca processi attivi anche se PID file mancante
        RUNNING=$(pgrep -f "CORE.orchestrator" 2>/dev/null | head -1)
        if [ -n "$RUNNING" ]; then
            echo "● Orchestratore ATTIVO (rilevato via pgrep, PID $RUNNING)"
            echo "  ⚠ PID file mancante o stale — considera ./bswarm stop + start"
        else
            echo "○ Orchestratore fermato"
        fi
    fi
    echo ""
    echo "=== Processi ==="
    ps aux | grep -E "CORE.orchestrator|SAFETY.watchdog" | grep -v grep || echo "  (nessuno)"
    echo ""
    echo "=== Task (SQLite) ==="
    if [ -f "$DB_FILE" ]; then
        $PYTHON -c "
import sqlite3
con = sqlite3.connect('$DB_FILE')
cur = con.cursor()
cur.execute('SELECT status, COUNT(*) FROM tasks GROUP BY status')
rows = cur.fetchall()
if not rows:
    print('  Coda vuota')
else:
    total = sum(r[1] for r in rows)
    print(f'  Totale: {total}')
    for r in sorted(rows):
        print(f'    {r[0]}: {r[1]}')
"
    else
        echo "  DB non trovato: $DB_FILE"
    fi
    echo ""
    echo "=== Ollama modelli caricati ==="
    ollama ps 2>/dev/null || echo "  (ollama non raggiungibile)"
    echo ""
    if [ -f "$THERMAL_HISTORY" ]; then
        echo "=== Ultimo campione termico ==="
        $PYTHON -c "
import json, time
with open('$THERMAL_HISTORY') as f:
    data = json.load(f)
samples = data.get('samples', [])
if samples:
    s = samples[-1]
    ts = time.strftime('%H:%M:%S', time.localtime(s['timestamp']))
    print(f'  {ts} | temp={s[\"cpu_temp_max\"]:.1f}C | load={s[\"cpu_load\"]*100:.0f}% | mem={s[\"mem_used_ratio\"]*100:.0f}%')
else:
    print('  (nessun campione)')
" 2>/dev/null || echo "  (errore lettura)"
    fi
}

cmd_queue_list() {
    if [ ! -f "$DB_FILE" ]; then
        echo "DB non trovato: $DB_FILE"
        exit 0
    fi
    $PYTHON -c "
import sqlite3
con = sqlite3.connect('$DB_FILE')
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute('SELECT id, status, title FROM tasks ORDER BY created_at DESC LIMIT 20')
rows = cur.fetchall()
if not rows:
    print('Coda vuota')
else:
    print(f'{\"ID\":<35} {\"Status\":<10} {\"Titolo\":<40}')
    print('-' * 90)
    for r in rows:
        print(f'{r[\"id\"]:<35} {r[\"status\"]:<10} {r[\"title\"][:40]:<40}')
"
}

cmd_queue_add() {
    if [ -z "$1" ]; then
        echo "Uso: bswarm queue add <title> [description]"
        exit 1
    fi
    TITLE="$1"
    DESC="${2:-}"
    $PYTHON -c "
import sqlite3, time, sys
con = sqlite3.connect('tasks/queue.db')
tid = f'task-cli-{int(time.time()*1000)}'
con.execute('''INSERT INTO tasks (id, title, description, status, attempts, created_at, type, source)
               VALUES (?,?,?,?,?,?,?,?)''',
            (tid, sys.argv[1], sys.argv[2] or '', 'pending', 0, time.time(), 'code', 'cli'))
con.commit()
con.close()
print(f'Aggiunto: {tid}')
print(f'  Titolo: {sys.argv[1]}')
" "$TITLE" "$DESC"
}

cmd_queue_cleanup() {
    $PYTHON -c "
import sqlite3
con = sqlite3.connect('tasks/queue.db')
cur = con.cursor()
cur.execute(\"DELETE FROM tasks WHERE status IN ('done','failed')\")
deleted = cur.rowcount
con.commit()
con.close()
print(f'Eliminati {deleted} task done/failed')
"
}

cmd_thermal() {
    if [ ! -f "$THERMAL_HISTORY" ]; then
        echo "Nessuno storico termico. Avvia l'orchestratore prima."
        exit 0
    fi
    $PYTHON -c "
import json, time
with open('$THERMAL_HISTORY') as f:
    data = json.load(f)
samples = data.get('samples', [])
if not samples:
    print('Nessun campione ancora')
    exit()
s = samples[-1]
ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(s['timestamp']))
print(f'Ultimo campione: {ts}')
print(f'  Temperatura CPU: {s[\"cpu_temp_max\"]:.1f} °C')
print(f'  CPU load:        {s[\"cpu_load\"]*100:.0f} %')
print(f'  CPU freq:        {s[\"cpu_freq_avg\"]//1000} MHz')
print(f'  RAM usata:       {s[\"mem_used_ratio\"]*100:.0f} %')
"
}

case "${1:-help}" in
    start|avvia)
        shift
        exec "$ROOT/avvia.sh" "$@"
        ;;
    stop|ferma)
        # 1. Ferma watchdog + orchestrator via ferma.sh (canonico)
        "$ROOT/ferma.sh" || true
        # 2. Cleanup orchestrator orfani: il watchdog potrebbe essere morto
        #    lasciando figli CORE.orchestrator senza parent.
        sleep 1
        ORPHANS=$(pgrep -f "CORE.orchestrator" 2>/dev/null || true)
        if [ -n "$ORPHANS" ]; then
            echo "Cleanup orchestrator orfani: $ORPHANS"
            for pid in $ORPHANS; do
                kill -TERM "$pid" 2>/dev/null || true
            done
            sleep 1
            # SIGKILL ai resilienti
            pkill -9 -f "CORE.orchestrator" 2>/dev/null || true
            echo "✓ Orfani fermati"
        fi
        ;;
    restart)
        "$ROOT/ferma.sh" || true
        sleep 2
        "$ROOT/avvia.sh" --orch
        ;;
    status)     cmd_status ;;
    queue)
        case "${2:-list}" in
            list)     cmd_queue_list ;;
            add)      shift 2; cmd_queue_add "$@" ;;
            cleanup)  cmd_queue_cleanup ;;
            *)        echo "Uso: bswarm queue {list|add|cleanup}"; exit 1 ;;
        esac
        ;;
    tasks)      cmd_queue_list ;;
    thermal)
        case "${2:-show}" in
            show)    cmd_thermal ;;
            history) echo "TODO: thermal history";;
            *)       echo "Uso: bswarm thermal {show|history}"; exit 1 ;;
        esac
        ;;
    honey)
        case "${2:-show}" in
            show) ls -la project/ 2>/dev/null | grep -v "^total" ;;
            log)  cd project && git log --oneline -20 2>/dev/null || echo "Nessun git in project/" ;;
            *)    echo "Uso: bswarm honey {show|log}"; exit 1 ;;
        esac
        ;;
    logs)
        shift
        if [[ "${1:-}" == "-f" ]]; then
            tail -f "$LOG_FILE"
        else
            tail -n "${1:-30}" "$LOG_FILE"
        fi
        ;;
    sync)       exec "$ROOT/scripts/dev/sync.sh" ;;
    setup)
        target="${2:-all}"
        case "$target" in
            all)       "$ROOT/scripts/setup/setup.sh" ;;
            gpu)       "$ROOT/scripts/setup/dual-gpu.sh" ;;
            hardening) "$ROOT/scripts/setup/hardening.sh" ;;
            usbmon)    "$ROOT/scripts/setup/usbmon.sh" ;;
            *)         echo "Target sconosciuto: $target"; exit 1 ;;
        esac
        ;;
    config)     EDITOR="${EDITOR:-nano}"; exec $EDITOR config.toml ;;
    version|-v) echo "BYTE-SWARMY v0.2.0 (post-SQLite refactor)" ;;
    help|--help|-h|"") usage ;;
    *)          echo "Comando sconosciuto: $1"; echo; usage; exit 1 ;;
esac
