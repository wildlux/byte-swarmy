"""
add_task.py — Helper per aggiungere task alla coda.
Uso:
  python add_task.py "Titolo del task" "Descrizione dettagliata"
  python add_task.py --from-file task.json
"""

import json
import sys
import time
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Uso: python add_task.py \"Titolo\" \"Descrizione\"")
        print("     python add_task.py --from-file task.json")
        sys.exit(1)

    queue_path = Path("tasks/queue.json")
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    if queue_path.exists():
        queue = json.loads(queue_path.read_text())
    else:
        queue = []

    if sys.argv[1] == "--from-file":
        task_data = json.loads(Path(sys.argv[2]).read_text())
    else:
        title = sys.argv[1]
        description = sys.argv[2] if len(sys.argv) > 2 else ""
        task_data = {"title": title, "description": description}

    task_id = f"task-{int(time.time()*1000)}-{len(queue)}"
    task = {
        "id": task_id,
        "title": task_data.get("title", ""),
        "description": task_data.get("description", ""),
        "context": task_data.get("context", ""),
        "status": "pending",
        "attempts": 0,
        "subtasks": [],
        "parent": None,
        "created_at": time.time(),
    }
    queue.append(task)
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2))
    print(f"Aggiunto: {task_id}")
    print(f"  Titolo: {task['title']}")
    print(f"  Descrizione: {task['description'][:80]}...")
    print(f"  Totale task in coda: {len(queue)}")


if __name__ == "__main__":
    main()
