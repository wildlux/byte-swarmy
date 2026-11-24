# Modulo: CORE.task_queue
# Task Queue API — cheat sheet (byte-swarmy)

Modulo: CORE.task_queue. Coda persistente SQLite usata dall'orchestratore.

## Classe `TaskQueue`
- `TaskQueue(tasks_dir, logger)` — costruttore
- `add(task: dict) -> str` — accoda un task e restituisce l'id
- `claim_by_id(task_id) -> dict | None` — prende un task per id
- `mark_done(task_id, result, first_try=True)` — chiude il task
- `TaskQueue.tasks_count()` — numero di task presenti

## Esempio minimo
```python
from pathlib import Path
from CORE.task_queue import TaskQueue

q = TaskQueue(Path("tasks"), logger)
q.add({"title": "esempio", "description": "task di prova"})
```

## Regola d'oro
Il worker NON istanzia l'orchestratore: usa la coda solo per scrivere task,
mai per alterare lo stato del processo padre.
