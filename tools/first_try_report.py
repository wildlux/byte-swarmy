"""tools/first_try_report.py — metrica "primo colpo %" (P1-1, zero LLM).

Legge tasks/queue.db (TaskQueue) e conta i task chiusi al primo colpo:

    status='done' AND first_try IS NOT NULL
    primo_colpo = SUM(first_try)   (1 = primo colpo, 0 = correction)

I task deterministici (swarm/execute) hanno first_try NULL e NON entrano
nel conteggio: misuriamo solo dove un LLM ha lavorato.

Uso:
  .venv/bin/python tools/first_try_report.py            # riga sintetica
  .venv/bin/python tools/first_try_report.py --json     # dettaglio

Fail-open: DB assente/illeggibile → riga "n/d", exit 0 (non rompe
verify_cycle.sh).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Il DB della coda può stare in più punti (dipende dalla cwd con cui è
# stato avviato l'orchestratore: repo root o data/). Si sceglie il più
# recente esistente; BW_TASKS_DB forza un path esplicito.
_DB_CANDIDATES = (
    ROOT / "data" / "tasks" / "queue.db",
    ROOT / "tasks" / "queue.db",
)


def resolve_db(path: str | Path | None = None) -> Path | None:
    """Path del queue.db da leggere, o None se nessun candidato esiste."""
    if path is not None:
        p = Path(path)
        return p if p.exists() else None
    env = os.environ.get("BW_TASKS_DB")
    candidates = ([Path(env)] if env else []) + list(_DB_CANDIDATES)
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def build_report(db_path: str | Path | None = None) -> dict | None:
    """Ritorna {done, first_try, pct, legacy} o None se il DB non è leggibile.

    legacy=True: la colonna first_try non esiste ancora (schema vecchio,
    migrato automaticamente al prossimo avvio dell'orchestratore).
    """
    p = resolve_db(db_path)
    if p is None:
        return None
    try:
        with sqlite3.connect(str(p)) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
            if "first_try" not in cols:
                return {"done": 0, "first_try": 0, "pct": 0.0, "legacy": True}
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(first_try), 0) FROM tasks "
                "WHERE status = 'done' AND first_try IS NOT NULL"
            ).fetchone()
    except sqlite3.Error:
        # File corrotto/illeggibile: fail-open.
        return None
    done = int((row[0] if row else 0) or 0)
    first_try = int((row[1] if row else 0) or 0)
    pct = (100.0 * first_try / done) if done else 0.0
    return {"done": done, "first_try": first_try, "pct": round(pct, 1),
            "legacy": False}


def format_line(report: dict | None) -> str:
    if report is None:
        return "primo_colpo: n/d (queue.db assente o illeggibile)"
    if report.get("legacy"):
        return ("primo_colpo: n/d (schema non ancora migrato — "
                "avviene al prossimo avvio dell'orchestratore)")
    return (f"primo_colpo: {report['first_try']}/{report['done']} "
            f"({report['pct']}%)")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    report = build_report()
    if "--json" in argv:
        payload = {"available": report is not None}
        payload.update(report or {"done": 0, "first_try": 0, "pct": 0.0,
                                  "legacy": False})
        print(json.dumps(payload, indent=1))
    else:
        print(format_line(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
