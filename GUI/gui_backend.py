"""
gui_backend.py — Funzioni di collegamento tra la GUI e il backend reale.
"""
import json
import sqlite3
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
DB_PATH = BASE_DIR / "tasks" / "queue.db"
METRICS_FILE = BASE_DIR / "state" / "last_metrics.json"
LOG_FILE = BASE_DIR / "logs" / "byte-swarmy.log"

def get_cpu_temp():
    try:
        temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
        if temp_file.exists():
            return int(temp_file.read_text().strip()) / 1000.0
    except Exception:
        pass
    return 0.0

def get_gpu_temp():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except Exception:
        pass
    return 0.0

def get_metrics():
    try:
        if METRICS_FILE.exists():
            return json.loads(METRICS_FILE.read_text())
    except Exception:
        pass
    return {}

def get_tasks():
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_logs(n=50):
    try:
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
            filtered = [l for l in lines if "timestral" not in l.lower()]
            return "\n".join(filtered[-n:])
    except Exception:
        pass
    return "(no log)"

def add_task_to_db(title, description="", task_type="code", project_path=None):
    """Aggiunge un task al database SQLite e al mirror JSON."""
    task_id = f"task-{int(time.time()*1000)}"

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO tasks (id, title, description, context, status, "
        "attempts, created_at, parent, type, source, project_path) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (task_id, title[:120], description, "", "pending", 0,
         time.time(), None, task_type, "gui", project_path)
    )
    conn.commit()
    conn.close()

    json_file = BASE_DIR / "tasks" / "queue.json"
    tasks = []
    if json_file.exists():
        try:
            tasks = json.loads(json_file.read_text())
        except Exception:
            pass
    tasks.append({
        "id": task_id, "title": title[:120], "description": description,
        "context": "", "status": "pending", "attempts": 0,
        "subtasks": [], "parent": None, "created_at": time.time(),
        "source": "gui", "type": task_type,
    })
    json_file.write_text(json.dumps(tasks, indent=2))

    return task_id


# ====================================================================
# CONFIG — lettura/scrittura CONFIG/config.toml
# ====================================================================
def load_config():
    """Legge CONFIG/config.toml e ritorna un dict."""
    import tomllib
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'CONFIG', 'config.toml')
    try:
        with open(config_path, 'rb') as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Errore load_config: {e}")
        return {}


def save_config(config_dict):
    """Scrive un dict in CONFIG/config.toml (formato TOML)."""
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'CONFIG', 'config.toml')
    try:
        backup_path = config_path + '.bak'
        if os.path.exists(config_path):
            import shutil
            shutil.copy2(config_path, backup_path)
        with open(config_path, 'w') as f:
            _write_toml(f, config_dict)
        return True, f"Config salvato in {config_path}"
    except Exception as e:
        return False, f"Errore save_config: {e}"


def _write_toml(f, data, parent_key=''):
    """Scrive un dict in formato TOML (supporta sezioni annidate)."""
    # Prima scrivi i valori semplici della sezione corrente
    for k, v in data.items():
        if isinstance(v, dict):
            continue
        if isinstance(v, str):
            f.write(f'{k} = "{v}"\n')
        elif isinstance(v, bool):
            f.write(f'{k} = {"true" if v else "false"}\n')
        elif isinstance(v, (int, float)):
            f.write(f'{k} = {v}\n')
        elif isinstance(v, list):
            f.write(f'{k} = [\n')
            for item in v:
                if isinstance(item, str):
                    f.write(f'    "{item}",\n')
                else:
                    f.write(f'    {item},\n')
            f.write(']\n')
    # Poi scrivi le sottosezioni
    for k, v in data.items():
        if isinstance(v, dict):
            section_name = f"{parent_key}.{k}" if parent_key else k
            f.write(f'\n[{section_name}]\n')
            _write_toml(f, v, section_name)
