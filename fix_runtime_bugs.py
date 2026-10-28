#!/usr/bin/env python3
"""
fix_runtime_bugs.py — Risolve 3 bug runtime:
1. ollama_client.py: aggiunge import Path mancante (metrics save failed)
2. orchestrator.py: resetta task "running" all'avvio (task zombie)
3. config.toml: usa qwen2.5-coder:3b invece di 1.5b (modello troppo piccolo)
"""
import shutil
from pathlib import Path

OLLAMA_FILE = Path("ollama_client.py")
OLLAMA_BACKUP = Path("ollama_client.py.bak.runtime")
ORCH_FILE = Path("orchestrator.py")
ORCH_BACKUP = Path("orchestrator.py.bak.runtime")
CONFIG_FILE = Path("config.toml")
CONFIG_BACKUP = Path("config.toml.bak.runtime")


# ====================================================================
# Fix 1: import Path in ollama_client.py
# ====================================================================

OLLAMA_OLD = '''import json
import time
import urllib.request
import urllib.error
from typing import Optional'''

OLLAMA_NEW = '''import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional'''


# ====================================================================
# Fix 2: reset task "running" all'avvio in orchestrator.py
# ====================================================================

ORCH_OLD = '''        self.queue = TaskQueue(Path(self.config["paths"]["tasks_dir"]), self.log)
        self.planner = Planner(self.models, self.log)'''

ORCH_NEW = '''        self.queue = TaskQueue(Path(self.config["paths"]["tasks_dir"]), self.log)
        # 🆕 Fix: resetta task "running" a "pending" all'avvio (erano crashati)
        try:
            with self.queue._get_conn() as conn:
                cur = conn.execute(
                    "UPDATE tasks SET status = 'pending', started_at = NULL "
                    "WHERE status = 'running'"
                )
                if cur.rowcount > 0:
                    self.log.info(f"reset {cur.rowcount} zombie running task(s) to pending")
                conn.commit()
        except Exception as e:
            self.log.warning(f"reset running tasks failed: {e}")
        self.planner = Planner(self.models, self.log)'''


def fix_ollama() -> bool:
    if not OLLAMA_FILE.exists():
        return False
    content = OLLAMA_FILE.read_text()
    if "from pathlib import Path" in content:
        print("ℹ  Fix 1 già applicato (Path importato), skip")
        return True
    if OLLAMA_OLD not in content:
        print("⚠  Pattern Fix 1 non trovato, skip")
        return False
    shutil.copy2(OLLAMA_FILE, OLLAMA_BACKUP)
    content = content.replace(OLLAMA_OLD, OLLAMA_NEW, 1)
    OLLAMA_FILE.write_text(content)
    print("✓ Fix 1: import Path aggiunto a ollama_client.py")
    return True


def fix_orchestrator() -> bool:
    if not ORCH_FILE.exists():
        return False
    content = ORCH_FILE.read_text()
    if "zombie running task" in content:
        print("ℹ  Fix 2 già applicato (reset zombie), skip")
        return True
    if ORCH_OLD not in content:
        print("⚠  Pattern Fix 2 non trovato, skip")
        return False
    shutil.copy2(ORCH_FILE, ORCH_BACKUP)
    content = content.replace(ORCH_OLD, ORCH_NEW, 1)
    ORCH_FILE.write_text(content)
    print("✓ Fix 2: reset task zombie all'avvio in orchestrator.py")
    return True


def fix_config() -> bool:
    if not CONFIG_FILE.exists():
        return False
    content = CONFIG_FILE.read_text()
    if "qwen2.5-coder:3b" in content:
        print("ℹ  Fix 3 già applicato (3b), skip")
        return True
    shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)
    # Sostituisci 1.5b con 3b SOLO nella sezione worker_coder
    new_content = content.replace(
        '[models.worker_coder]\nname = "qwen2.5-coder:1.5b"',
        '[models.worker_coder]\nname = "qwen2.5-coder:3b"',
    )
    if new_content == content:
        print("⚠  Pattern Fix 3 non trovato (verifica config manualmente)")
        return False
    CONFIG_FILE.write_text(new_content)
    print("✓ Fix 3: worker_coder cambiato da 1.5b a 3b in config.toml")
    return True


def reset_zombie_tasks() -> None:
    """Reset immediato dei task zombie nel DB (senza aspettare riavvio)."""
    import sqlite3
    db = Path("tasks/queue.db")
    if not db.exists():
        return
    try:
        with sqlite3.connect(str(db)) as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = 'pending', started_at = NULL, "
                "attempts = 0, last_error = NULL "
                "WHERE status IN ('running', 'retry', 'stuck')"
            )
            if cur.rowcount > 0:
                print(f"✓ Reset {cur.rowcount} task zombie a pending nel DB")
            conn.commit()
    except Exception as e:
        print(f"⚠  Reset DB fallito: {e}")


def main():
    print("=" * 60)
    print("FIX RUNTIME BUGS")
    print("=" * 60)
    print()

    fix_ollama()
    print()
    fix_orchestrator()
    print()
    fix_config()
    print()
    reset_zombie_tasks()

    print()
    print("=" * 60)
    print("✓ FIX COMPLETATI")
    print("=" * 60)
    print()
    print("⚠  MANCA ANCORA: verifica allowed_tools in tools.py")
    print("   Il worker prova a chiamare patch_code/analyze_project ma")
    print("   riceve 'unknown tool'. Esegui:")
    print("     grep -n 'def allowed_tools\\|patch_code\\|analyze_project' tools.py")
    print("   e mandami l'output.")
    print()
    print("Per testare ora:")
    print("  1. ferma l'orchestrator: ./ferma.sh")
    print("  2. riavvia: ./avvia.sh")
    print("  3. aggiungi un task dalla Quick Command bar")


if __name__ == "__main__":
    main()
