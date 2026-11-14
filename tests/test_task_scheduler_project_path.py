"""Test per il Task Scheduler: verifica che modifiche/eliminazioni
usino sempre il project_path corretto (per-progetto, non globale).

FM14: la coda vive SOLO in SQLite (tasks/queue.db condivisa con
l'orchestratore); gli scope (progetto vs globale) sono righe con
project_path impostato o NULL. I test girano su un DB temporaneo."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helper: import delle funzioni da testare + isolamento DB temporaneo
# ──────────────────────────────────────────────────────────────────────


def _import_task_queue_functions():
    import sys

    sys.path.insert(0, os.getcwd())
    import GUI.task_queue as tq
    from GUI.task_queue import (
        add_task,
        delete_task,
        load_tasks,
        save_tasks,
    )
    return add_task, delete_task, load_tasks, save_tasks, tq


@pytest.fixture(autouse=True)
def _isolated_queue(tmp_path, monkeypatch):
    import GUI.task_queue as tq

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tq, "_TASKS_DIR", tasks_dir)
    monkeypatch.setattr(tq, "_QUEUE", None)
    yield
    monkeypatch.setattr(tq, "_TASKS_DIR", None)
    monkeypatch.setattr(tq, "_QUEUE", None)


# ──────────────────────────────────────────────────────────────────────
# Test 1: load_tasks/save_tasks usano lo scope per-progetto, non globale
# ──────────────────────────────────────────────────────────────────────


def test_save_and_load_per_progetto():
    add_task, delete_task, load_tasks, save_tasks, tq = (
        _import_task_queue_functions()
    )

    tmp = tempfile.mkdtemp()
    try:
        proj_a = os.path.join(tmp, "progettoA")
        proj_b = os.path.join(tmp, "progettoB")
        os.makedirs(proj_a)
        os.makedirs(proj_b)

        # Salvo due task diversi per i due progetti
        save_tasks(
            [{"id": "t1", "title": "Task A", "description": "desc A"}],
            proj_a,
        )
        save_tasks(
            [{"id": "t2", "title": "Task B", "description": "desc B"}],
            proj_b,
        )

        # Caricamento per-progetto deve restituire i task corretti
        ta = load_tasks(proj_a)
        tb = load_tasks(proj_b)

        assert len(ta) == 1
        assert ta[0]["id"] == "t1"
        assert ta[0]["title"] == "Task A"

        assert len(tb) == 1
        assert tb[0]["id"] == "t2"
        assert tb[0]["title"] == "Task B"

        # I task di progetto non compaiono nella vista globale (scope)
        ids_globale = {t["id"] for t in load_tasks(None)}
        assert "t1" not in ids_globale and "t2" not in ids_globale
    finally:
        shutil.rmtree(tmp)


def test_load_tasks_none_usa_globale():
    _, _, load_tasks, _, _ = _import_task_queue_functions()

    # project_path=None → scope globale (righe con project_path NULL)
    result = load_tasks(None)
    assert isinstance(result, list)


# ──────────────────────────────────────────────────────────────────────
# Test 2: delete_task elimina dal file per-progetto, non globale
# ──────────────────────────────────────────────────────────────────────


def test_delete_task_per_progetto():
    add_task, delete_task, load_tasks, save_tasks, tq = (
        _import_task_queue_functions()
    )

    tmp = tempfile.mkdtemp()
    try:
        proj = os.path.join(tmp, "progettoX")
        os.makedirs(os.path.join(proj, "tasks"))

        save_tasks(
            [
                {"id": "keep-1", "title": "Tieni questo"},
                {"id": "del-1", "title": "Elimina questo"},
            ],
            proj,
        )

        delete_task("del-1", proj)

        remaining = load_tasks(proj)
        assert len(remaining) == 1
        assert remaining[0]["id"] == "keep-1"
    finally:
        shutil.rmtree(tmp)


# ──────────────────────────────────────────────────────────────────────
# Test 3: FM14 — nessun nuovo queue.json: il DB è l'unica fonte
# ──────────────────────────────────────────────────────────────────────


def test_nessun_nuovo_queue_json():
    add_task, delete_task, load_tasks, save_tasks, tq = (
        _import_task_queue_functions()
    )

    tmp = tempfile.mkdtemp()
    try:
        proj = os.path.join(tmp, "progettoY")
        os.makedirs(proj)

        add_task(title="Task", description="desc", project_path=proj)

        # Nei dir di test non esiste alcun queue.json (solo queue.db)
        assert not os.path.exists(os.path.join(proj, "tasks", "queue.json"))
        assert not (tq._TASKS_DIR / "queue.json").exists()
        assert (tq._TASKS_DIR / "queue.db").exists()
    finally:
        shutil.rmtree(tmp)


# ──────────────────────────────────────────────────────────────────────
# Test 4: modifica task nel scheduler usa project_path (simulazione logica)
# ──────────────────────────────────────────────────────────────────────


def test_modifica_task_usa_project_path():
    """Simula il flusso di modifica del TaskSchedulerPanel:
    carica task per progetto, modifica, salva nello stesso progetto."""
    add_task, delete_task, load_tasks, save_tasks, tq = (
        _import_task_queue_functions()
    )

    tmp = tempfile.mkdtemp()
    try:
        proj = os.path.join(tmp, "progettoZ")
        os.makedirs(os.path.join(proj, "tasks"))

        # Task iniziale nel progetto
        save_tasks(
            [
                {
                    "id": "task-mod-1",
                    "title": "Titolo originale",
                    "description": "Prompt originale",
                    "status": "pending",
                }
            ],
            proj,
        )

        # --- Simula _start_edit_task: carica task per ID con project_path ---
        tasks = load_tasks(proj)
        task_da_modificare = next(
            t for t in tasks if t.get("id") == "task-mod-1"
        )
        assert task_da_modificare["title"] == "Titolo originale"

        # --- Simula _on_add_task in modalità modifica: aggiorna per ID ---
        for t in tasks:
            if t.get("id") == "task-mod-1":
                t["title"] = "Titolo modificato"
                t["description"] = "Prompt modificato"
                break
        save_tasks(tasks, proj)

        # --- Verifica: il task è stato aggiornato nel file per-progetto ---
        dopo = load_tasks(proj)
        assert len(dopo) == 1
        assert dopo[0]["id"] == "task-mod-1"
        assert dopo[0]["title"] == "Titolo modificato"
        assert dopo[0]["description"] == "Prompt modificato"

        # --- Verifica: non è stato creato un duplicato ---
        assert len(dopo) == 1
    finally:
        shutil.rmtree(tmp)
