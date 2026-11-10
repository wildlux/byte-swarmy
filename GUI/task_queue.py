"""
GUI/task_queue.py — Funzioni di I/O per la coda task e configurazione MCP.

Modulo condiviso tra i moduli GUI (control_center, task_scheduler_panel)
per le operazioni sulla coda task e la configurazione MCP.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent.parent.resolve()

TASKS_FILE = BASE_DIR / "tasks" / "queue.json"
LOG_FILE = BASE_DIR / "logs" / "byte-swarmy.log"
CONFIG_FILE = BASE_DIR / "CONFIG" / "config.toml"
MCP_CONFIG_FILE = BASE_DIR / "mcp_servers.json"
PID_FILE = BASE_DIR / "state" / "orchestrator.pid"


# ====================================================================
# TASK QUEUE I/O (shared with orchestrator)
# ====================================================================

def _tasks_file(project_path: Optional[str] = None) -> Path:
    """Ritorna il path del file queue.json per il progetto indicato.
    Se project_path è None usa la coda globale (backward compat)."""
    if project_path:
        p = Path(project_path) / "tasks" / "queue.json"
    else:
        p = TASKS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_tasks(project_path: Optional[str] = None) -> list:
    f = _tasks_file(project_path)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text())
    except Exception:
        return []


def save_tasks(tasks: list, project_path: Optional[str] = None) -> None:
    f = _tasks_file(project_path)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    tmp.replace(f)


def add_task(title: str, description: str, context: str = "",
             task_type: str = "code",
             project_path: Optional[str] = None) -> dict:
    """Aggiunge un task sia al JSON (per la GUI) che al DB SQLite (per l'orchestrator)."""
    tasks = load_tasks(project_path)
    task = {
        "id": f"task-{int(time.time()*1000)}-{len(tasks)}",
        "title": title,
        "description": description,
        "context": context,
        "status": "pending",
        "attempts": 0,
        "subtasks": [],
        "parent": None,
        "created_at": time.time(),
        "source": "gui",
        "type": task_type,
        "project_path": project_path,
    }
    tasks.append(task)
    save_tasks(tasks, project_path)

    # Scrivi anche nel DB SQLite che l'orchestrator legge (globale)
    try:
        db_path = BASE_DIR / "tasks" / "queue.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
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
                    reason TEXT
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO tasks "
                "(id, title, description, context, status, attempts, "
                "created_at, parent, type, source, project_path) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (task["id"], title, description, context, "pending", 0,
                 task["created_at"], None, task_type, "gui", project_path)
            )
            conn.commit()
    except Exception as e:
        print(f"WARNING: SQLite insert failed: {e}")

    return task


def delete_task(task_id: str, project_path: Optional[str] = None) -> None:
    # Prima prova nel progetto specificato
    if project_path:
        tasks = load_tasks(project_path)
        before = len(tasks)
        tasks = [t for t in tasks if t["id"] != task_id]
        if len(tasks) < before:
            save_tasks(tasks, project_path)
            return
    # Fallback: coda globale
    tasks = load_tasks(None)
    tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(tasks, None)


def reset_task(task_id: str, project_path: Optional[str] = None) -> None:
    """Resetta un task a pending, qualunque sia lo stato attuale.
    Pulisce tentativi, errori, risultato. Funziona anche su 'done' e 'planned'."""
    # Prima prova nel progetto specificato
    if project_path:
        tasks = load_tasks(project_path)
        found = False
        for t in tasks:
            if t["id"] == task_id:
                found = True
                t["status"] = "pending"
                t["attempts"] = 0
                for k in ("last_error", "failure_reason", "result",
                          "completed_at", "started_at", "reason"):
                    t.pop(k, None)
        if found:
            save_tasks(tasks, project_path)
            return
    # Fallback: coda globale
    tasks = load_tasks(None)
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "pending"
            t["attempts"] = 0
            for k in ("last_error", "failure_reason", "result",
                      "completed_at", "started_at", "reason"):
                t.pop(k, None)
    save_tasks(tasks, None)


def force_rerun_task(task_id: str, project_path: Optional[str] = None) -> None:
    """Forza re-run: resetta il task E elimina i suoi sottotask (se presenti).
    Utile per ripartire da capo con un task già 'planned' o 'done'."""
    # Prima prova nel progetto specificato
    if project_path:
        tasks = load_tasks(project_path)
        target = next((t for t in tasks if t["id"] == task_id), None)
        if target:
            # Elimina i sottotask associati
            subtask_ids = target.get("subtask_ids", [])
            if subtask_ids:
                tasks = [t for t in tasks if t["id"] not in subtask_ids]
            # Resetta il task
            for t in tasks:
                if t["id"] == task_id:
                    t["status"] = "pending"
                    t["attempts"] = 0
                    t["subtasks"] = []
                    t.pop("subtask_ids", None)
                    for k in ("last_error", "failure_reason", "result",
                              "completed_at", "started_at", "reason"):
                        t.pop(k, None)
            save_tasks(tasks, project_path)
            return
    # Fallback: coda globale
    tasks = load_tasks(None)
    target = next((t for t in tasks if t["id"] == task_id), None)
    if not target:
        return
    subtask_ids = target.get("subtask_ids", [])
    if subtask_ids:
        tasks = [t for t in tasks if t["id"] not in subtask_ids]
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "pending"
            t["attempts"] = 0
            t["subtasks"] = []
            t.pop("subtask_ids", None)
            for k in ("last_error", "failure_reason", "result",
                      "completed_at", "started_at", "reason"):
                t.pop(k, None)
    save_tasks(tasks, None)


def cleanup_done_tasks(project_path: Optional[str] = None) -> int:
    """Elimina tutti i task in stato 'done'. Ritorna il numero eliminati."""
    total_removed = 0
    # Prima prova nel progetto specificato
    if project_path:
        tasks = load_tasks(project_path)
        before = len(tasks)
        tasks = [t for t in tasks if t["status"] != "done"]
        after = len(tasks)
        save_tasks(tasks, project_path)
        total_removed += before - after
    # Fallback: coda globale
    tasks = load_tasks(None)
    before = len(tasks)
    tasks = [t for t in tasks if t["status"] != "done"]
    after = len(tasks)
    save_tasks(tasks, None)
    total_removed += before - after
    return total_removed


def delete_subtasks(task_id: str, project_path: Optional[str] = None) -> int:
    """Elimina i sottotask di un task. Ritorna il numero eliminati."""
    # Prima prova nel progetto specificato
    if project_path:
        tasks = load_tasks(project_path)
        target = next((t for t in tasks if t["id"] == task_id), None)
        if target:
            subtask_ids = target.get("subtask_ids", [])
            if not subtask_ids:
                # Fallback: cerca task con parent == task_id
                subtask_ids = [t["id"] for t in tasks if t.get("parent") == task_id]
            before = len(tasks)
            tasks = [t for t in tasks if t["id"] not in subtask_ids]
            for t in tasks:
                if t["id"] == task_id:
                    t["subtasks"] = []
                    t.pop("subtask_ids", None)
            save_tasks(tasks, project_path)
            return before - len(tasks)
    # Fallback: coda globale
    tasks = load_tasks(None)
    target = next((t for t in tasks if t["id"] == task_id), None)
    if not target:
        return 0
    subtask_ids = target.get("subtask_ids", [])
    if not subtask_ids:
        subtask_ids = [t["id"] for t in tasks if t.get("parent") == task_id]
    before = len(tasks)
    tasks = [t for t in tasks if t["id"] not in subtask_ids]
    for t in tasks:
        if t["id"] == task_id:
            t["subtasks"] = []
            t.pop("subtask_ids", None)
    save_tasks(tasks, None)
    return before - len(tasks)


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
