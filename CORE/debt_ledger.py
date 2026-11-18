"""CORE/debt_ledger.py — Registro del debito tecnico (SQLite).

La metà mancante rispetto a `CORE/code_map.py`: il codemap tiene traccia
di COSA ESISTE (AST → tabelle symbols/calls/imports), il ledger tiene
traccia di COSA VA RIFATTORIZZATO (item con stato, priorità, verifica
anti-stantio). Idea dell'utente: un DB + skill per far dialogare LLM e
SQL e tenere traccia di tutti i pezzi da rifattorizzare/ottimizzare.

Regole di design (le tre che ne decidono il successo):
1. L'LLM NON scrive SQL libero — dialoga con questa API/CLI. Le query
   sono deterministiche, gratuite, zero calore (pianificazione fredda,
   adatta al limite termico 60°C).
2. `file_hash` è la parte vitale: hash sha1 del file ALLA REGISTRAZIONE.
   Se il file cambia dopo, l'item diventa `stale` al primo `next()` —
   un ledger stantio è peggio di niente, quindi mai proposto alla cieca.
3. Un item per sessione, stadiale: `next()` sceglie dalla coda
   (priority ASC, created ASC), l'LLM esegue e chiude con `mark`.

DB: `state/debt_ledger.db` (stessa convenzione di memory_event_store.db
e sml_database.db). Stdlib only. Fail-open: mai crash per DB assente.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DB_NAME = "state/debt_ledger.db"

KINDS = ("refactor", "optimization", "test", "docs")
EFFORTS = ("xs", "s", "m", "l")
STATUSES = ("open", "in_progress", "verify", "done", "stale")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS debt_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    title TEXT NOT NULL,
    rationale TEXT DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 2,
    effort TEXT NOT NULL DEFAULT 's',
    status TEXT NOT NULL DEFAULT 'open',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
)
"""


def _root(project_root: Optional[str | Path] = None) -> Path:
    """Root del progetto: argomento > default repo."""
    return Path(project_root).resolve() if project_root else ROOT


def _conn(project_root: Optional[str | Path] = None) -> sqlite3.Connection:
    root = _root(project_root)
    db = root / DB_NAME
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    # Schema garantito a OGNI connessione (CREATE IF NOT EXISTS, idempotente):
    # nessun footgun "dimenticati l'init" per CLI/API. Costo ~zero.
    conn.executescript(_SCHEMA)
    return conn


def _sha1(path: Path) -> Optional[str]:
    """Hash del file, o None se assente/irraggiungibile (fail-open)."""
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()[:16]
    except Exception:
        return None


def _to_dict(row) -> dict:
    return dict(row) if row is not None else {}


def init(project_root: Optional[str | Path] = None) -> None:
    """Crea lo schema se assente (idempotente)."""
    with _conn(project_root) as conn:
        conn.executescript(_SCHEMA)


def add(project_root: Optional[str | Path], kind: str, file_path: str,
        title: str, rationale: str = "", priority: int = 2,
        effort: str = "s") -> dict:
    """Registra un item. Il file_hash è calcolato ORA (anti-stantio).

    Il file può anche non esistere ancora (es. nuovo file da creare):
    in quel caso file_hash resta None e viene registrato com'è.
    """
    if kind not in KINDS:
        raise ValueError(f"kind non valido: {kind} (scelti: {KINDS})")
    if effort not in EFFORTS:
        raise ValueError(f"effort non valido: {effort} (scelti: {EFFORTS})")
    if not (1 <= int(priority) <= 3):
        raise ValueError("priority deve essere 1 (alta), 2 (media) o 3 (bassa)")

    root = _root(project_root)
    p = root / file_path
    file_hash = _sha1(p)
    now = time.time()
    with _conn(root) as conn:
        cur = conn.execute(
            "INSERT INTO debt_items (kind, file_path, file_hash, title, "
            "rationale, priority, effort, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
            (kind, file_path, file_hash, title, rationale, int(priority),
             effort, now, now))
        item_id = cur.lastrowid
    return get(root, item_id)


def get(project_root: Optional[str | Path], item_id: int) -> dict:
    with _conn(project_root) as conn:
        row = conn.execute(
            "SELECT * FROM debt_items WHERE id = ?", (item_id,)).fetchone()
    return _to_dict(row)


def list_items(project_root: Optional[str | Path],
               status: Optional[str] = None,
               limit: int = 50) -> list[dict]:
    """Items in coda (priority ASC, created ASC), filtro opzionale per stato."""
    if status and status not in STATUSES:
        raise ValueError(f"status non valido: {status} (scelti: {STATUSES})")
    with _conn(project_root) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM debt_items WHERE status = ? "
                "ORDER BY priority ASC, created_at ASC LIMIT ?",
                (status, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM debt_items "
                "ORDER BY priority ASC, created_at ASC LIMIT ?",
                (limit,)).fetchall()
    return [_to_dict(r) for r in rows]


def _check_staleness(conn, item: dict, root: Path) -> bool:
    """Se il file è cambiato dalla registrazione → status='stale'.

    Ritorna True se l'item è ANCORA VALIDO (hash uguale, o None==None
    per file mai esistiti — la verifica resta compito della sessione).
    """
    recorded = item.get("file_hash")
    current = _sha1(root / item["file_path"])
    if recorded == current:
        return True
    conn.execute(
        "UPDATE debt_items SET status = 'stale', updated_at = ? WHERE id = ?",
        (time.time(), item["id"]))
    return False


def next(project_root: Optional[str | Path] = None,
         prefer_kind: Optional[str] = None) -> Optional[dict]:
    """Il prossimo item su cui lavorare: il più vecchio tra i più urgenti.

    Salta e marca `stale` gli item il cui file è cambiato dalla
    registrazione (regola 2). `prefer_kind` ripriorizza un tipo di
    lavoro (es. 'test') senza ignorare la priorità.
    """
    root = _root(project_root)
    with _conn(root) as conn:
        if prefer_kind:
            rows = conn.execute(
                "SELECT * FROM debt_items WHERE status = 'open' "
                "ORDER BY (kind = ?) DESC, priority ASC, created_at ASC",
                (prefer_kind,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM debt_items WHERE status = 'open' "
                "ORDER BY priority ASC, created_at ASC").fetchall()
        for row in rows:
            item = _to_dict(row)
            if _check_staleness(conn, item, root):
                return item
    return None


def mark(project_root: Optional[str | Path], item_id: int,
         status: str) -> dict:
    """Cambia lo stato di un item (open/in_progress/verify/done/stale)."""
    if status not in STATUSES:
        raise ValueError(f"status non valido: {status} (scelti: {STATUSES})")
    with _conn(project_root) as conn:
        conn.execute(
            "UPDATE debt_items SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), item_id))
    return get(project_root, item_id)


def stats(project_root: Optional[str | Path] = None) -> dict:
    """Conteggi per stato — vista d'insieme della coda."""
    with _conn(project_root) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM debt_items GROUP BY status"
        ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def context_for_file(project_root: Optional[str | Path],
                     file_path: str, cap: int = 30) -> list[dict]:
    """Simboli del file secondo il code_map (integrazione, fail-open).

    Riusa l'API di CORE.code_map: se il codemap non esiste o il file
    non è mappato, ritorna [] — la sessione lavora senza contesto, mai
    crash. Serve all'LLM per RIUSARE le API esistenti invece di
    allucinarle (stesso principio del PROJECT MAP nei prompt).
    """
    try:
        from CORE.code_map import symbols
        root = _root(project_root)
        target = str(file_path)
        return [s for s in symbols(root)
                if s.get("file") == target or
                str(Path(s.get("file", ""))) == str(Path(target))][:cap]
    except Exception:
        return []


def main(argv: Optional[list] = None) -> int:
    """CLI del ledger — l'interfaccia UFFICIALE per l'LLM (regola 1).

    Esempi:
      python -m CORE.debt_ledger add --kind refactor --file CORE/worker.py \
          --title "Estrarre _fast_lane_target" --priority 1 --effort s
      python -m CORE.debt_ledger next
      python -m CORE.debt_ledger list --status open
      python -m CORE.debt_ledger done 7
      python -m CORE.debt_ledger stats
      python -m CORE.debt_ledger context CORE/worker.py
    """
    ap = argparse.ArgumentParser(description="Registro del debito tecnico")
    # --root in un parent parser: valido su OGNI sottocomando
    # (es. `debt_ledger stats --root /percorso`)
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--root", default=None,
                        help="root progetto (default: repo)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="registra un item", parents=[parent])
    p_add.add_argument("--kind", required=True, choices=KINDS)
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--rationale", default="")
    p_add.add_argument("--priority", type=int, default=2, choices=(1, 2, 3))
    p_add.add_argument("--effort", default="s", choices=EFFORTS)

    p_next = sub.add_parser("next", parents=[parent], help="prossimo item (con check stale)")
    p_next.add_argument("--kind", choices=KINDS, default=None)

    p_list = sub.add_parser("list", parents=[parent], help="lista items")
    p_list.add_argument("--status", choices=STATUSES, default=None)
    p_list.add_argument("--limit", type=int, default=50)

    p_done = sub.add_parser("done", parents=[parent], help="marca un item come done")
    p_done.add_argument("id", type=int)
    p_prog = sub.add_parser("progress", parents=[parent], help="marca un item in_progress")
    p_prog.add_argument("id", type=int)
    sub.add_parser("stats", parents=[parent], help="conteggi per stato")
    p_ctx = sub.add_parser("context", parents=[parent], help="simboli del file dal code_map")
    p_ctx.add_argument("file")

    args = ap.parse_args(argv)
    root = args.root

    try:
        if args.cmd == "add":
            item = add(root, args.kind, args.file, args.title,
                       args.rationale, args.priority, args.effort)
            print(json.dumps(item, indent=2, ensure_ascii=False))
        elif args.cmd == "next":
            item = next(root, prefer_kind=args.kind) if args.kind \
                else next(root)
            print(json.dumps(item, indent=2, ensure_ascii=False)
                  if item else "coda vuota (nessun item valido)")
        elif args.cmd == "list":
            for it in list_items(root, args.status, args.limit):
                print(f"#{it['id']} [{it['status']}] p{it['priority']} "
                      f"{it['kind']}/{it['effort']} {it['file_path']} — "
                      f"{it['title']}")
        elif args.cmd == "done":
            print(json.dumps(mark(root, args.id, "done"),
                             indent=2, ensure_ascii=False))
        elif args.cmd == "progress":
            print(json.dumps(mark(root, args.id, "in_progress"),
                             indent=2, ensure_ascii=False))
        elif args.cmd == "stats":
            print(json.dumps(stats(root), indent=2))
        elif args.cmd == "context":
            print(json.dumps(context_for_file(root, args.file),
                             indent=2, ensure_ascii=False))
        return 0
    except ValueError as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
