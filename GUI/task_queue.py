"""
GUI/task_queue.py — Funzioni di I/O per la coda task e configurazione MCP.

FM14 — Coda unica GUI→SQLite: la coda task vive SOLO in SQLite
(`tasks/queue.db`, schema e implementazione condivisi con l'orchestratore
via `CORE/task_queue.py:TaskQueue`). Nessuna coda in memoria, nessun
mirror queue.json da tenere in sync: un task = una riga del DB.

I vecchi `queue.json` (globale + per-progetto) vengono importati una-tantum
nel DB e rinominati `.json.migrated` (dati mai cancellati).

Modulo condiviso tra i moduli GUI (control_center, task_scheduler_panel,
file_tree_drawer) per le operazioni sulla coda task e la configurazione MCP.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

from CORE.task_queue import TaskQueue

BASE_DIR = Path(__file__).parent.parent.resolve()

LOG_FILE = BASE_DIR / "logs" / "byte-swarmy.log"
CONFIG_FILE = BASE_DIR / "CONFIG" / "config.toml"
MCP_CONFIG_FILE = BASE_DIR / "mcp_servers.json"
PID_FILE = BASE_DIR / "state" / "orchestrator.pid"

_QUEUE: Optional[TaskQueue] = None

# Hook per i test: se impostata, la coda vive in questa cartella (DB
# temporaneo) invece che in tasks/. Nessun uso in produzione.
_TASKS_DIR: Optional[Path] = None


# ====================================================================
# TASK QUEUE I/O — unica fonte di verità: tasks/queue.db
# ====================================================================

def _queue() -> TaskQueue:
    """TaskQueue condivisa (stessa istanza/DB dell'orchestratore).

    Al primo accesso esegue la migrazione una-tantum dei vecchi queue.json.
    """
    global _QUEUE
    if _QUEUE is None:
        tasks_dir = _TASKS_DIR if _TASKS_DIR is not None else (BASE_DIR / "tasks")
        _QUEUE = TaskQueue(tasks_dir, logging.getLogger("byte-swarmy.gui"))
        _migrate_json_queues(_QUEUE)
    return _QUEUE


def _migrate_json_queues(q: TaskQueue) -> None:
    """Importa i vecchi queue.json nel DB (una-tantum, idempotente).

    - coda `<tasks_dir>/queue.json` → righe con project_path NULL
    - code per-progetto `<tasks_dir>/../project/*/tasks/queue.json` →
      righe con project_path = cartella del progetto
    I file originali vengono RINOMINATI `.json.migrated` (backup, mai
    cancellati); il marker `.fm14_migrated` evita re-import.
    """
    tasks_dir = q.dir
    marker = tasks_dir / ".fm14_migrated"
    projects_dir = tasks_dir.parent / "project"
    if marker.exists():
        return
    imported = 0
    try:
        legacy_file = tasks_dir / "queue.json"
        if legacy_file.exists():
            try:
                legacy = json.loads(legacy_file.read_text(encoding="utf-8"))
            except Exception:
                legacy = []
            if isinstance(legacy, list):
                for t in legacy:
                    if not isinstance(t, dict) or not t.get("id"):
                        continue
                    row = dict(t)
                    row.pop("subtasks", None)
                    row.pop("subtask_ids", None)
                    row["project_path"] = None
                    q.upsert_task(row)
                    imported += 1
            legacy_file.rename(legacy_file.with_suffix(".json.migrated"))

        if projects_dir.is_dir():
            for jf in sorted(projects_dir.glob("*/tasks/queue.json")):
                project_dir = str(jf.parent.parent.resolve())
                try:
                    legacy = json.loads(jf.read_text(encoding="utf-8"))
                except Exception:
                    legacy = []
                if isinstance(legacy, list):
                    for t in legacy:
                        if not isinstance(t, dict) or not t.get("id"):
                            continue
                        row = dict(t)
                        row.pop("subtasks", None)
                        row.pop("subtask_ids", None)
                        row["project_path"] = project_dir
                        q.upsert_task(row)
                        imported += 1
                jf.rename(jf.with_suffix(".json.migrated"))

        marker.write_text(
            f"fm14 migration ok ({imported} tasks) — {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            encoding="utf-8",
        )
        if imported:
            print(f"[fm14] migrati {imported} task da queue.json → queue.db")
    except Exception as e:
        # Fail-open: se la migrazione fallisce la coda continua a funzionare
        # (i JSON restano al loro posto e si riprova al prossimo avvio).
        print(f"[fm14] migrazione queue.json saltata: {e}")


def _display_row(row: dict) -> dict:
    """Normalizza una riga DB al vecchio formato dict usato dalla GUI
    (campi 'subtasks'/'subtask_ids' sempre presenti e vuoti: nel modello
    a coda unica i figli sono righe con parent=<id>)."""
    row.setdefault("subtasks", [])
    row.setdefault("subtask_ids", [])
    return row


def load_tasks(project_path: Optional[str] = None) -> list:
    """Task nello scope indicato (None = globale), in ordine di creazione."""
    try:
        rows = _queue().list_scoped(project_path)
    except Exception as e:
        print(f"WARNING: lettura coda fallita: {e}")
        return []
    return [_display_row(r) for r in rows]


def save_tasks(tasks: list, project_path: Optional[str] = None) -> None:
    """Scrive la lista task nel DB (upsert per id, usato dal flusso 'modifica')."""
    q = _queue()
    for task in tasks:
        if not isinstance(task, dict) or not task.get("id"):
            continue
        row = dict(task)
        row.pop("subtasks", None)
        row.pop("subtask_ids", None)
        if project_path and not row.get("project_path"):
            row["project_path"] = project_path
        q.upsert_task(row)


def add_task(title: str, description: str = "", context: str = "",
             task_type: str = "code",
             project_path: Optional[str] = None) -> dict:
    """Aggiunge un task alla coda SQLite (condivisa con l'orchestrator)."""
    task = {
        "id": f"task-{int(time.time()*1000)}-{_queue().tasks_count()}",
        "title": title,
        "description": description,
        "context": context,
        "status": "pending",
        "attempts": 0,
        "parent": None,
        "created_at": time.time(),
        "source": "gui",
        "type": task_type,
        "project_path": project_path,
    }
    try:
        _queue().add(task)
    except Exception as e:
        print(f"WARNING: SQLite insert failed: {e}")
    return task


def delete_task(task_id: str, project_path: Optional[str] = None) -> None:
    """Elimina il task per id (id univoci globali: lo scope è ignorato)."""
    try:
        _queue().delete_by_id(task_id)
    except Exception as e:
        print(f"WARNING: SQLite delete failed: {e}")


def reset_task(task_id: str, project_path: Optional[str] = None) -> None:
    """Resetta un task a pending, qualunque sia lo stato attuale.
    Pulisce tentativi, errori, risultato. Funziona anche su 'done' e 'planned'."""
    try:
        _queue().reset_task(task_id)
    except Exception as e:
        print(f"WARNING: SQLite reset failed: {e}")


def force_rerun_task(task_id: str, project_path: Optional[str] = None) -> None:
    """Forza re-run: resetta il task E elimina i suoi sottotask (se presenti).
    Utile per ripartire da capo con un task già 'planned' o 'done'."""
    q = _queue()
    try:
        q.delete_children(task_id)
        q.reset_task(task_id)
    except Exception as e:
        print(f"WARNING: SQLite force rerun failed: {e}")


def cleanup_done_tasks(project_path: Optional[str] = None) -> int:
    """Elimina tutti i task in stato 'done' nello scope indicato.
    Ritorna il numero eliminato."""
    try:
        return _queue().cleanup_done(project_path)
    except Exception as e:
        print(f"WARNING: SQLite cleanup failed: {e}")
        return 0


def delete_subtasks(task_id: str, project_path: Optional[str] = None) -> int:
    """Elimina i sottotask di un task. Ritorna il numero eliminato."""
    try:
        return _queue().delete_children(task_id)
    except Exception as e:
        print(f"WARNING: SQLite delete subtasks failed: {e}")
        return 0


# ====================================================================
# MCP SERVERS CONFIG (persistente)
# ====================================================================

def load_mcp_servers() -> list:
    if not MCP_CONFIG_FILE.exists():
        return []
    try:
        return json.loads(MCP_CONFIG_FILE.read_text())
    except Exception:
        return []


def save_mcp_servers(servers: list) -> None:
    MCP_CONFIG_FILE.write_text(json.dumps(servers, indent=2))


# ====================================================================
# SINGLE-TASK STATE TRANSITIONS (sqlite queue.db)
# ====================================================================
# Queste funzioni erano originariamente in control_center.py / main_window.py
# e sono state persa durante la rifattorizzazione modulare (commit 3312ad4).
# Vengono ripristinate qui perche' sono l'interfaccia naturale per la GUI
# (file_tree_drawer.py e control_center.py le usano per pause/resume/stop/restart).

def _queue_db_path() -> Path:
    """Path del database SQLite della coda task (tasks/queue.db)."""
    return BASE_DIR / "tasks" / "queue.db"


def pause_task(task_id: str) -> tuple[bool, str]:
    """Mette in pausa un singolo task (status='paused').

    Ritorna (ok, message). Compatible con la vecchia _pause_task(task_id).
    """
    db_path = _queue_db_path()
    if not db_path.exists():
        return False, "Database coda non trovato"
    try:
        con = sqlite3.connect(str(db_path), timeout=10.0)
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='paused' "
            "WHERE id=? AND status IN ('pending', 'running')",
            (task_id,)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} in pausa"
    except Exception as e:
        return False, f"Errore: {e}"


def resume_single_task(task_id: str) -> tuple[bool, str]:
    """Riprende un singolo task (status='pending')."""
    db_path = _queue_db_path()
    if not db_path.exists():
        return False, "Database coda non trovato"
    try:
        con = sqlite3.connect(str(db_path), timeout=10.0)
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='pending' WHERE id=? AND status='paused'",
            (task_id,)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} ripreso"
    except Exception as e:
        return False, f"Errore: {e}"


def stop_task(task_id: str) -> tuple[bool, str]:
    """Ferma un singolo task (marca come failed con last_error='Stopped by user')."""
    db_path = _queue_db_path()
    if not db_path.exists():
        return False, "Database coda non trovato"
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='failed', "
            "last_error='Stopped by user (GUI)', "
            "completed_at=? WHERE id=?",
            (time.time(), task_id)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} fermato"
    except Exception as e:
        return False, f"Errore: {e}"


def restart_task(task_id: str) -> tuple[bool, str]:
    """Riavvia un task esistente (cambia status da done/failed a pending)."""
    db_path = _queue_db_path()
    if not db_path.exists():
        return False, "Database coda non trovato"
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='pending', attempts=0, last_error=NULL, "
            "started_at=NULL, completed_at=NULL WHERE id=?",
            (task_id,)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} rimesso in coda"
    except Exception as e:
        return False, f"Errore: {e}"


# ====================================================================
# USER ACTION LOGGING (logs/user_actions.log)
# ====================================================================

def log_user_action(component: str, action: str,
                    task_id: Optional[str] = None,
                    details: str = "") -> str:
    """Logga le azioni utente in logs/user_actions.log (JSONL).

    Originariamente ``_log_user_action`` in control_center.py / main_window.py,
    persa durante la rifattorizzazione. Ripristinata come funzione pubblica
    di task_queue perche' usata da control_center.py e file_tree_drawer.py.
    """
    log_path = BASE_DIR / "logs" / "user_actions.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    entry = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "epoch": time.time(),
        "component": component,   # "Pulsante-in-Alto_DX" o "Task-Action"
        "action": action,         # "avviato", "fermato", "pausa", "riprendi", "stop"
        "task_id": task_id,
        "details": details,
        "message": ""
    }
    # Costruisci messaggio leggibile
    if component == "Pulsante-in-Alto_DX":
        entry["message"] = (
            f"{component} : stato attuale = {action} premuto adesso"
        )
    elif component == "Task-Action":
        tid_short = (task_id or "?")[:15] if task_id else "?"
        entry["message"] = (
            f"Task #{tid_short} ha premuto lo stato di {action}"
        )
    else:
        entry["message"] = f"{component}: {action}"
    try:
        with open(log_path, 'a', encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"[USER_ACTION] {entry['message']}")
    except Exception as e:
        print(f"Errore log user action: {e}")
    return entry["message"]
