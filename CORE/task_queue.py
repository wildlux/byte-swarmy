"""
CORE/task_queue.py — Coda task persistente basata su SQLite.

Estratto da CORE/orchestrator.py per ridurre il monolite.
Supporta transazioni ACID e claim atomico delle task in coda.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from CORE.constants import TaskStatus

log = logging.getLogger("byte-swarmy")


class TaskQueue:
    """Coda task persistente basata su SQLite. Supporta transazioni ACID."""

    def __init__(self, tasks_dir: Path, logger):
        self.dir = tasks_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.dir / "queue.db"
        self.log = logger
        self._init_db()

    def _init_db(self) -> None:
        """Inizializza lo schema del database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    context TEXT,
                    status TEXT,
                    attempts INTEGER DEFAULT 0,
                    created_at REAL,
                    parent TEXT,
                    type TEXT,
                    source TEXT,
                    result TEXT,
                    last_error TEXT,
                    failure_reason TEXT,
                    completed_at REAL,
                    started_at REAL,
                    reason TEXT,
                    project_path TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
            self._migrate(conn)
            conn.commit()

    @staticmethod
    def _migrate(conn) -> None:
        """Migrazioni additive (idempotenti) per DB esistenti."""
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "tasks" not in tables:
            return
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "retry_after" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN retry_after REAL")
        if "project_path" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN project_path TEXT")

    def _get_conn(self):
        # timeout=30: busy-wait su lock concorrenti (threads/GUI) invece di
        # 'database is locked' immediato.
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def add(self, task: dict) -> str:
        task_id = f"task-{int(time.time()*1000)}-{self.tasks_count()}"
        task.setdefault("id", task_id)
        task.setdefault("status", "pending")
        task.setdefault("attempts", 0)
        task.setdefault("created_at", time.time())
        task.setdefault("parent", None)

        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO tasks (id, title, description, context, status, attempts, created_at, parent, type, source, project_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    task["id"], task.get("title", ""), task.get("description", ""),
                    task.get("context", ""), task["status"], task["attempts"],
                    task["created_at"], task["parent"], task.get("type", "code"),
                    task.get("source", "manual"), task.get("project_path") or task.get("project")
                )
            )
            conn.commit()
        self.log.info(f"queue: added {task_id}")
        return task_id

    def next_pending(self) -> Optional[dict]:
        now = time.time()
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            # retry_after: cooldown tra i tentativi — il task "aspetta"
            # prima di essere ripescato invece di bloccarsi in definitivo.
            #
            # CLAIM ATOMICO: SELECT+UPDATE in un solo statement con
            # UPDATE...RETURNING. Due connessioni concorrenti non possono
            # più pendenzare lo stesso task: la seconda trova status='running'
            # nella re-check WHERE e rientra nel loop (o ritorna None).
            for _ in range(5):
                cur = conn.execute(
                    "UPDATE tasks SET status = 'running', started_at = ? "
                    "WHERE id = ("
                    "  SELECT id FROM tasks WHERE status IN ('pending', 'retry') "
                    "  AND (retry_after IS NULL OR retry_after <= ?) "
                    "  ORDER BY created_at ASC LIMIT 1"
                    ") AND status IN ('pending', 'retry') "
                    "RETURNING id",
                    (time.time(), now),
                )
                row = cur.fetchone()
                if row is not None:
                    task_id = row["id"]
                    res = conn.execute(
                        "SELECT * FROM tasks WHERE id = ?", (task_id,)
                    ).fetchone()
                    conn.commit()
                    return dict(res) if res else None
                # Nessun claim: verifico SE davvero la coda è vuota,
                # altrimenti è avvenuta una contesa → riprovo brevemente.
                still = conn.execute(
                    "SELECT 1 FROM tasks WHERE status IN ('pending', 'retry') "
                    "AND (retry_after IS NULL OR retry_after <= ?) LIMIT 1",
                    (now,),
                ).fetchone()
                if still is None:
                    conn.commit()
                    return None
                time.sleep(0.01)
            return None

    def mark_done(self, task_id: str, result: str) -> None:
        with self._get_conn() as conn:
            # Non sovrascrivere un task fermato dall'utente (status='failed')
            cur = conn.execute(
                "UPDATE tasks SET status = 'done', result = ?, completed_at = ? "
                "WHERE id = ? AND status NOT IN ('failed', 'stuck')",
                (result[:500], time.time(), task_id)
            )
            conn.commit()

            # Se il task appena completato ha un parent, controlla se TUTTI i
            # subtask del parent sono done: in tal caso marca anche il parent
            # come done (chiusura automatica del task padre).
            row = conn.execute(
                "SELECT parent FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row and row[0]:
                parent_id = row[0]
                subtasks = conn.execute(
                    "SELECT status FROM tasks WHERE parent = ?", (parent_id,)
                ).fetchall()
                if subtasks and all(s[0] == "done" for s in subtasks):
                    conn.execute(
                        "UPDATE tasks SET status = 'done', completed_at = ? "
                        "WHERE id = ? AND status NOT IN ('failed', 'stuck')",
                        (time.time(), parent_id)
                    )
                    conn.commit()
                    self.log.info(
                        f"task {parent_id} DONE (tutti i subtask completati)"
                    )

    def mark_failed(self, task_id: str, reason: str) -> None:
        with self._get_conn() as conn:
            # Increment attempts
            curr = conn.execute("SELECT attempts FROM tasks WHERE id = ?", (task_id,)).fetchone()
            attempts = (curr[0] if curr else 0) + 1

            status = "stuck" if attempts >= 10 else "retry"
            fail_col = "failure_reason" if status == "stuck" else "last_error"

            conn.execute(
                f"UPDATE tasks SET attempts = ?, status = ?, {fail_col} = ? WHERE id = ?",  # nosec: colonna dinamica validata (fail_col ∈ {failure_reason,last_error})
                (attempts, status, reason[:300], task_id)
            )
            conn.commit()

    def needs_human(self, task_id: str, reason: str) -> None:
        with self._get_conn() as conn:
            conn.execute("UPDATE tasks SET status = 'needs_human', reason = ? WHERE id = ?", (reason, task_id))
            conn.commit()

    # ---------------------------------------------------------------
    # Feedback loop (work order T2): retry con prompt sovrascritto
    # ---------------------------------------------------------------
    RETRY_LIMIT = 3            # fallimenti tollerati; il 4° e' definitivo
                               # (sovrascrivibile da [orchestrator]
                               #  max_task_retries in CONFIG/config.toml)
    STATUS_FINAL = "failed_definitively"

    def update_prompt(self, task_id: str, prompt: str) -> None:
        """Sovrascrive la description del task (prompt corretto)."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET description = ? WHERE id = ?",
                (str(prompt)[:4000], task_id),
            )
            conn.commit()

    def set_status(self, task_id: str, status: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
            conn.commit()

    def mark_pending(self, task_id: str) -> None:
        """Rimette un task in pending (usato per il fallback modello)."""
        self.set_status(task_id, "pending")

        # non ripesca piu' nulla di definitivo: loop terminato

    def pause_thermal(self) -> int:
        """Mette in 'thermal_paused' i task ancora in attesa (T3). Idempotente."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = 'thermal_paused' "
                "WHERE status IN ('pending', 'retry')"
            )
            conn.commit()
            return cur.rowcount

    def resume_thermal(self) -> int:
        """Riaccoda i task 'thermal_paused' quando la temperatura rientra."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = 'pending' WHERE status = 'thermal_paused'"
            )
            conn.commit()
            return cur.rowcount

    def fail_with_correction(self, task_id: str, reason: str,
                             correction_prompt: str,
                             retry_limit: Optional[int] = None,
                             cooldown_sec: int = 0) -> str:
        """Feedback-loop atomico.

        attempt 1..N  -> status 'pending' + description sovrascritta col
                         prompt di correzione (il loop lo ripesca). Con
                         cooldown_sec > 0 il task non viene ripescato
                         prima che sia passato l'intervallo (retry_after).
        attempt N+1   -> status 'failed_definitively' + last_error.

        N = retry_limit (default RETRY_LIMIT della classe, sovrascrivibile
        da [orchestrator] max_task_retries in CONFIG/config.toml).

        Returns:
            nuovo status ('pending' | 'failed_definitively').
        """
        limit = self.RETRY_LIMIT if retry_limit is None else max(1, retry_limit)
        with self._get_conn() as conn:
            curr = conn.execute(
                "SELECT attempts FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            attempts = (curr[0] if curr else 0) + 1
            if attempts <= limit:
                status = "pending"
                retry_after = (time.time() + cooldown_sec) if cooldown_sec > 0 else None
                conn.execute(
                    "UPDATE tasks SET attempts = ?, status = ?, "
                    "description = ?, last_error = ?, retry_after = ? WHERE id = ?",
                    (attempts, status, str(correction_prompt)[:4000],
                     reason[:300], retry_after, task_id),
                )
            else:
                status = self.STATUS_FINAL
                conn.execute(
                    "UPDATE tasks SET attempts = ?, status = ?, "
                    "last_error = ?, completed_at = ? WHERE id = ?",
                    (attempts, status, reason[:300], time.time(), task_id),
                )
            conn.commit()
            return status

    def _save(self):
        """No-op: SQLite auto-commit. Mantenuto per compatibilità vecchia API."""
        pass

    def update_task(self, task_id: str, **fields):
        """Aggiorna campi di un task nel DB SQLite (UPDATE diretto).

        Esempio: queue.update_task("task-123", status="planned", result="ok")
        Campi non esistenti nello schema vengono ignorati con warning.
        Liste/dict vengono serializzati come JSON.
        """
        if not fields:
            return
        _log = logging.getLogger("byte-swarmy")
        conn = self._get_conn()
        try:
            cur = conn.execute("PRAGMA table_info(tasks)")
            valid_cols = {row[1] for row in cur.fetchall()}
            updates, vals = [], []
            for k, v in fields.items():
                if k in valid_cols:
                    if isinstance(v, (list, dict)):
                        v = json.dumps(v)
                    updates.append(f"{k} = ?")
                    vals.append(v)
                else:
                    _log.warning(f"update_task: colonna '{k}' non in schema, ignorata")
            if not updates:
                return
            vals.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",  # nosec: chiavi validate contro schema (solo colonne note)
                vals,
            )
            conn.commit()
        finally:
            conn.close()

    def list_tasks(self) -> list:
        """Ritorna tutti i task (compatibilità vecchia API .tasks)."""
        conn = self._get_conn()
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute('SELECT * FROM tasks')
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def stats(self) -> dict:
        with self._get_conn() as conn:
            res = conn.execute("SELECT status, count(*) FROM tasks GROUP BY status").fetchall()
            return {row[0]: row[1] for row in res}

    def tasks_count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT count(*) FROM tasks").fetchone()[0]

    def get_all_tasks(self) -> list:
        """Compatibility method for GUI."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM tasks ORDER BY created_at ASC").fetchall()]

    # ---------------------------------------------------------------
    # API scoped condivisa con la GUI (FM14 — coda unica GUI→SQLite)
    # ---------------------------------------------------------------
    # Convenzione scope: project_path=None/'' → coda GLOBALE (righe con
    # project_path NULL o ''); altrimenti coda del singolo progetto.
    # Gli id sono univoci a livello globale, quindi le operazioni by-id
    # non hanno bisogno di scope.

    _TASK_COLUMNS = (
        "id", "title", "description", "context", "status", "attempts",
        "created_at", "parent", "type", "source", "result", "last_error",
        "failure_reason", "completed_at", "started_at", "reason",
        "project_path",
    )

    def list_scoped(self, project_path: Optional[str] = None,
                    limit: Optional[int] = None) -> List[dict]:
        """Task nello scope indicato, in ordine di creazione.

        project_path None/'' → coda globale (project_path NULL o vuoto);
        altrimenti solo le righe di quel progetto. `limit` opzionale.
        """
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            if project_path:
                sql = ("SELECT * FROM tasks WHERE project_path = ? "
                       "ORDER BY created_at ASC")
                args: list = [project_path]
            else:
                sql = ("SELECT * FROM tasks WHERE project_path IS NULL "
                       "OR project_path = '' ORDER BY created_at ASC")
                args = []
            if limit:
                sql += " LIMIT ?"
                args.append(limit)
            return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def get_by_id(self, task_id: str) -> Optional[dict]:
        """Ritorna il task per id (o None). Gli id sono univoci globali."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def upsert_task(self, task: dict) -> None:
        """INSERT OR REPLACE di un task (import/mirror/update-by-id).

        Solo le colonne dello schema vengono scritte: i campi extra del
        vecchio formato JSON (subtasks, subtask_ids, …) vengono ignorati —
        nel modello a coda unica i figli sono righe con parent=<id>.
        """
        row = {k: task.get(k) for k in self._TASK_COLUMNS}
        if row.get("project_path") is None and task.get("project"):
            row["project_path"] = task["project"]
        if not row.get("id"):
            raise ValueError("upsert_task: task senza 'id'")
        row["status"] = row.get("status") or "pending"
        row["attempts"] = int(row.get("attempts") or 0)
        row["created_at"] = row.get("created_at") or time.time()
        with self._get_conn() as conn:
            cols = ", ".join(self._TASK_COLUMNS)
            qs = ", ".join("?" for _ in self._TASK_COLUMNS)
            conn.execute(
                f"INSERT OR REPLACE INTO tasks ({cols}) VALUES ({qs})",  # nosec: colonne validate contro _TASK_COLUMNS
                tuple(row[k] for k in self._TASK_COLUMNS),
            )
            conn.commit()

    def delete_by_id(self, task_id: str) -> int:
        """Elimina il task per id. Ritorna il numero di righe eliminate."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount

    def delete_children(self, parent_id: str) -> int:
        """Elimina le righe figlie (parent=<id>). Ritorna il numero."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM tasks WHERE parent = ?", (parent_id,)
            )
            conn.commit()
            return cur.rowcount

    def reset_task(self, task_id: str) -> bool:
        """Riporta il task a pending (tentativi/errori puliti), qualunque
        sia lo stato attuale. True se il task esisteva."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = 'pending', attempts = 0, "
                "last_error = NULL, failure_reason = NULL, result = NULL, "
                "completed_at = NULL, started_at = NULL, reason = NULL, "
                "retry_after = NULL WHERE id = ?",
                (task_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def cleanup_done(self, project_path: Optional[str] = None) -> int:
        """Elimina i task 'done' nello scope indicato. Ritorna il numero."""
        with self._get_conn() as conn:
            if project_path:
                cur = conn.execute(
                    "DELETE FROM tasks WHERE status = 'done' AND project_path = ?",
                    (project_path,),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM tasks WHERE status = 'done' AND "
                    "(project_path IS NULL OR project_path = '')"
                )
            conn.commit()
            return cur.rowcount
