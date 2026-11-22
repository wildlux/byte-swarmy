"""
GUI/label_actions.py — azioni condivise sulle etichette.

Tiene coerenti registro (`CORE/labels.py`) e task (`tasks/queue.db`) quando
si rinomina un'etichetta, senza duplicare la logica nei vari pannelli.
"""
from __future__ import annotations

import json


def _as_list(value) -> list:
    """Etichette di un task: lista, JSON stringa o vuoto."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return list(parsed) if isinstance(parsed, list) else []
        except Exception:
            return []
    return list(value or [])


def rename_label_everywhere(old: str, new: str,
                            project_path: str | None = None) -> bool:
    """Rinomina etichetta nel registro e in tutti i task che la usano.

    Ritorna False se il nome è vuoto, identico al vecchio o già presente.
    Il colore viene preservato da ``CORE.labels.rename_label``.
    """
    from CORE import labels as L

    old = (old or "").strip()
    new = (new or "").strip()
    if not old or not new or old == new:
        return False
    if new in {entry["name"] for entry in L.list_labels()}:
        return False
    if not L.rename_label(old, new):
        return False

    try:
        from GUI.task_queue import load_tasks, update_task_labels
        for task in load_tasks(project_path):
            current = _as_list(task.get("labels"))
            if old in current:
                updated = [new if item == old else item for item in current]
                update_task_labels(task.get("id"), updated, project_path)
    except Exception as exc:
        print(f"WARNING: aggiornamento task dopo rinomina etichetta: {exc}")
    return True


def delete_label_everywhere(name: str,
                            project_path: str | None = None) -> bool:
    """Elimina l'etichetta dal registro e da tutti i task che la usano.

    Unifica le quattro implementazioni duplicate nei pannelli (Impostazioni,
    Archivio, Pianificatore, completamento etichette). Ritorna False se il
    nome non era registrato. Le etichette di default vengono testamentate da
    ``CORE.labels.remove_label`` per evitare che ricompaiano.
    """
    from CORE import labels as L

    name = (name or "").strip()
    if not name or not L.remove_label(name):
        return False

    try:
        from GUI.task_queue import load_tasks, update_task_labels
        for task in load_tasks(project_path):
            current = _as_list(task.get("labels"))
            if name in current:
                updated = [item for item in current if item != name]
                update_task_labels(task.get("id"), updated, project_path)
    except Exception as exc:
        print(f"WARNING: aggiornamento task dopo eliminazione etichetta: {exc}")
    return True
