#!/usr/bin/env python3
"""
fix_worker_parsing.py — Fix completo per worker:

1. orchestrator.py: parser tollerante per action con args inlineati
   (es. "patch_code('a','b','c')" → action="patch_code", args=["a","b","c"])
2. config.toml: phi3:mini per worker_coder e worker_general (più bravo con JSON)
3. Pulisci task "test sync" dal DB
"""
import re
import shutil
import sqlite3
from pathlib import Path

ORCH_FILE = Path("orchestrator.py")
ORCH_BACKUP = Path("orchestrator.py.bak.parsing")
CONFIG_FILE = Path("config.toml")
CONFIG_BACKUP = Path("config.toml.bak.parsing")


# ====================================================================
# Fix 1: parser tollerante in _parse_action
# ====================================================================

OLD_PARSE = '''    def _parse_action(self, raw: str) -> Optional[dict]:
        m = re.search(r"\\{[\\s\\S]*\\}", raw)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None'''

NEW_PARSE = '''    def _parse_action(self, raw: str) -> Optional[dict]:
        m = re.search(r"\\{[\\s\\S]*\\}", raw)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        # 🆕 Fix: se il modello ha messo args inlineati in "action",
        # estrai nome tool + args dalla stringa.
        # Esempi che gestisce:
        #   "patch_code('a','b','c')" → action="patch_code", args=["a","b","c"]
        #   "read_file('main.py')" → action="read_file", args=["main.py"]
        #   "tool(['analyze_project'])" → action="analyze_project", args=[]
        action = data.get("action", "")
        args = data.get("args", [])
        if isinstance(action, str) and "(" in action and not args:
            # Estrai nome funzione e argomenti
            m2 = re.match(r"^(\\w+)\\s*\\((.*)\\)\\s*$", action)
            if m2:
                func_name = m2.group(1)
                args_str = m2.group(2).strip()
                # Se è una lista come argomento: tool(['analyze_project'])
                if args_str.startswith("[") and args_str.endswith("]"):
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = []
                elif args_str:
                    # Split by comma, pulisci quotes
                    parts = [p.strip().strip("'\\\"") for p in args_str.split(",")]
                    args = [p for p in parts if p]
                else:
                    args = []
                # Se il func_name è "tool" e args è una lista, usa il primo elemento
                if func_name == "tool" and args and isinstance(args[0], str):
                    data["action"] = args[0]
                    data["args"] = []
                else:
                    data["action"] = func_name
                    data["args"] = args
        return data'''


# ====================================================================
# Fix 2: config.toml — usa phi3:mini (più bravo con JSON di qwen-coder:3b)
# ====================================================================

def fix_config():
    if not CONFIG_FILE.exists():
        return False
    content = CONFIG_FILE.read_text()
    modified = False

    shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)

    # worker_coder: phi3:mini (2.2GB, 3.8B, eccellente con JSON)
    if 'name = "qwen2.5-coder:3b"' in content:
        content = content.replace(
            '[models.worker_coder]\nname = "qwen2.5-coder:3b"',
            '[models.worker_coder]\nname = "phi3:mini"',
        )
        modified = True
        print("✓ worker_coder: qwen2.5-coder:3b → phi3:mini")

    # worker_general: phi3:mini (anche per auditor)
    if 'name = "qwen2.5:1.5b"' in content:
        content = content.replace(
            '[models.worker_general]\nname = "qwen2.5:1.5b"',
            '[models.worker_general]\nname = "phi3:mini"',
        )
        modified = True
        print("✓ worker_general: qwen2.5:1.5b → phi3:mini")

    if modified:
        CONFIG_FILE.write_text(content)
    else:
        print("ℹ  config.toml già configurato (o pattern non trovato)")

    return True


# ====================================================================
# Fix 3: pulisci task "test sync" dal DB
# ====================================================================

def cleanup_test_tasks():
    db = Path("tasks/queue.db")
    if not db.exists():
        return
    try:
        with sqlite3.connect(str(db)) as conn:
            # Elimina i task "test sync"
            cur = conn.execute("DELETE FROM tasks WHERE title LIKE '%test sync%'")
            deleted = cur.rowcount
            # Resetta i task zombie rimanenti a pending
            cur2 = conn.execute(
                "UPDATE tasks SET status = 'pending', attempts = 0, "
                "last_error = NULL, failure_reason = NULL, started_at = NULL "
                "WHERE status IN ('running', 'retry', 'stuck')"
            )
            reset = cur2.rowcount
            conn.commit()
            if deleted > 0:
                print(f"✓ Eliminati {deleted} task 'test sync'")
            if reset > 0:
                print(f"✓ Reset {reset} task zombie a pending")
    except Exception as e:
        print(f"⚠  Cleanup DB fallito: {e}")


def main():
    print("=" * 60)
    print("FIX WORKER PARSING + CONFIG + CLEANUP")
    print("=" * 60)
    print()

    # Fix 1
    print("→ Fix 1: parser tollerante in orchestrator.py")
    if not ORCH_FILE.exists():
        print("❌ orchestrator.py non trovato")
    else:
        content = ORCH_FILE.read_text()
        if "args inlineati" in content:
            print("ℹ  Fix 1 già applicato, skip")
        elif OLD_PARSE in content:
            shutil.copy2(ORCH_FILE, ORCH_BACKUP)
            content = content.replace(OLD_PARSE, NEW_PARSE, 1)
            ORCH_FILE.write_text(content)
            print("✓ Parser tollerante aggiunto a _parse_action")
        else:
            print("⚠  Pattern _parse_action non trovato esattamente")

    print()

    # Fix 2
    print("→ Fix 2: config.toml modelli più capaci")
    fix_config()

    print()

    # Fix 3
    print("→ Fix 3: cleanup task DB")
    cleanup_test_tasks()

    print()
    print("=" * 60)
    print("✓ FIX COMPLETATI")
    print("=" * 60)
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2 && ./avvia.sh")
    print()
    print("Poi aggiungi un task pulito dalla Quick Command bar:")
    print("  crea funzione fattoriale in python")


if __name__ == "__main__":
    main()
