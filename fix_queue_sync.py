#!/usr/bin/env python3
"""
fix_queue_sync.py — Risolve il mismatch GUI↔Orchestrator.

Problema: la GUI scrive in tasks/queue.json, l'orchestrator legge da
tasks/queue.db (SQLite). I task aggiunti dalla GUI non vengono mai eseguiti.

Fix: patcha add_task() in gui.py per scrivere ANCHE nel DB SQLite.
Mantiene la compatibilità con il JSON (per la visualizzazione GUI).
"""
import re
import shutil
from pathlib import Path

GUI_FILE = Path("gui.py")
BACKUP = Path("gui.py.bak.queuesync")


# Nuova versione di add_task che scrive in entrambi i backend
NEW_ADD_TASK = '''def add_task(title: str, description: str, context: str = "",
             task_type: str = "code") -> dict:
    """Aggiunge un task sia al JSON (per la GUI) che al DB SQLite (per l'orchestrator)."""
    import sqlite3 as _sqlite3
    import time as _time

    tasks = load_tasks()
    task = {
        "id": f"task-{int(_time.time()*1000)}-{len(tasks)}",
        "title": title,
        "description": description,
        "context": context,
        "status": "pending",
        "attempts": 0,
        "subtasks": [],
        "parent": None,
        "created_at": _time.time(),
        "source": "gui",
        "type": task_type,
    }
    tasks.append(task)
    save_tasks(tasks)

    # 🆕 Scrivi anche nel DB SQLite che l'orchestrator legge
    try:
        db_path = BASE_DIR / "tasks" / "queue.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with _sqlite3.connect(str(db_path)) as conn:
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
                "created_at, parent, type, source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (task["id"], title, description, context, "pending", 0,
                 task["created_at"], None, task_type, "gui")
            )
            conn.commit()
    except Exception as e:
        print(f"WARNING: SQLite insert failed: {e}")

    return task'''


# Vecchia versione da sostituire
OLD_ADD_TASK = '''def add_task(title: str, description: str, context: str = "",
             task_type: str = "code") -> dict:
    tasks = load_tasks()
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
    }
    tasks.append(task)
    save_tasks(tasks)
    return task'''


def main():
    if not GUI_FILE.exists():
        print(f"❌ {GUI_FILE} non trovato")
        return 1

    content = GUI_FILE.read_text()

    # Verifica se la patch è già applicata
    if "Scrivi anche nel DB SQLite" in content:
        print("✓ Patch già applicata")
        return 0

    # Backup
    shutil.copy2(GUI_FILE, BACKUP)
    print(f"✓ Backup: {BACKUP}")

    # Verifica che il pattern esista
    if OLD_ADD_TASK not in content:
        print("❌ Pattern add_task non trovato. Verifica che gui.py non sia stato modificato.")
        print("\nPattern cercato (primi 200 char):")
        print(OLD_ADD_TASK[:200])
        return 1

    # Applica la patch
    content = content.replace(OLD_ADD_TASK, NEW_ADD_TASK, 1)
    GUI_FILE.write_text(content)
    print("✓ add_task() patchata: ora scrive anche in tasks/queue.db")

    # Verifica sintassi
    try:
        compile(content, "gui.py", "exec")
        print("✓ Verifica sintassi OK")
    except SyntaxError as e:
        print(f"❌ Errore sintassi: {e}")
        shutil.copy2(BACKUP, GUI_FILE)
        return 1

    print("\n" + "=" * 60)
    print("✓ FIX APPLICATO")
    print("=" * 60)
    print("\nOra i task aggiunti dalla GUI verranno visti dall'orchestrator.")
    print("\nPer testare:")
    print("  1. python -c \"import gui; print('OK')\"")
    print("  2. ./avvia.sh")
    print("  3. Aggiungi un task dalla Quick Command bar")
    print("  4. Guarda il tab Logs: dovresti vedere 'dispatching task...'")
    print("\nPer ripristinare:")
    print(f"  cp {BACKUP} {GUI_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
