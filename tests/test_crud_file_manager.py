"""Test di conformità CRUD per il File Manager e il Task Scheduler di byte-swarmy.

Verifica che:
- C (Create): si possano creare file e cartelle
- R (Read): si possano leggere/vedere nell'albero
- U (Update): si possano rinominare i file
- D (Delete): si possano eliminare file, cartelle e task
- Le checkbox di selezione funzionino (seleziona/deseleziona)

Eseguire con:
    .venv/bin/python -m pytest tests/test_crud_file_manager.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from PyQt6.QtWidgets import QMessageBox

# Aggiungi la root del progetto al path
sys.path.insert(0, os.getcwd())

from GUI.task_queue import (
    _tasks_file,
    add_task,
    delete_task,
    load_tasks,
    save_tasks,
)


# ════════════════════════════════════════════════════════════════
# Helper per creare una struttura di progetti temporanea
# ════════════════════════════════════════════════════════════════

def _make_project(tmp: str, name: str, files: dict[str, str] | None = None) -> str:
    """Crea una cartella progetto con eventuali file al suo interno."""
    proj = os.path.join(tmp, name)
    os.makedirs(os.path.join(proj, "tasks"), exist_ok=True)
    if files:
        for fname, content in files.items():
            with open(os.path.join(proj, fname), "w", encoding="utf-8") as f:
                f.write(content)
    return proj


# ════════════════════════════════════════════════════════════════
# TEST CRUD — Task (per-progetto)
# ════════════════════════════════════════════════════════════════


def test_task_crud_per_progetto():
    """Ogni sottoprogetto deve avere i propri task isolati."""
    tmp = tempfile.mkdtemp()
    try:
        proj_a = _make_project(tmp, "progettoA")
        proj_b = _make_project(tmp, "progettoB")

        # --- CREATE ---
        ta = add_task(title="Task A", description="Desc A", project_path=proj_a)
        tb = add_task(title="Task B", description="Desc B", project_path=proj_b)
        assert ta["id"] != tb["id"]

        # --- READ ---
        tasks_a = load_tasks(proj_a)
        tasks_b = load_tasks(proj_b)
        assert len(tasks_a) == 1
        assert tasks_a[0]["id"] == ta["id"]
        assert tasks_a[0]["title"] == "Task A"
        assert len(tasks_b) == 1
        assert tasks_b[0]["id"] == tb["id"]
        assert tasks_b[0]["title"] == "Task B"

        # Task del progetto A non devono apparire in B e viceversa
        ids_a = {t["id"] for t in tasks_a}
        ids_b = {t["id"] for t in tasks_b}
        assert ids_a.isdisjoint(ids_b)

        # --- UPDATE (modifica titolo e descrizione) ---
        tasks_a = load_tasks(proj_a)
        tasks_a[0]["title"] = "Task A modificato"
        tasks_a[0]["description"] = "Desc A modificata"
        save_tasks(tasks_a, proj_a)

        tasks_a2 = load_tasks(proj_a)
        assert tasks_a2[0]["title"] == "Task A modificato"
        assert tasks_a2[0]["description"] == "Desc A modificata"

        # --- DELETE ---
        delete_task(ta["id"], proj_a)
        tasks_a3 = load_tasks(proj_a)
        assert len(tasks_a3) == 0

        # Il progetto B non deve essere toccato
        tasks_b2 = load_tasks(proj_b)
        assert len(tasks_b2) == 1
        assert tasks_b2[0]["id"] == tb["id"]

    finally:
        shutil.rmtree(tmp)


def test_task_delete_nonexistent_is_safe():
    """Eliminare un task inesistente non deve crashare."""
    tmp = tempfile.mkdtemp()
    try:
        proj = _make_project(tmp, "progettoX")
        delete_task("task-inesistente", proj)  # non deve sollevare eccezione
    finally:
        shutil.rmtree(tmp)


# ════════════════════════════════════════════════════════════════
# TEST: _tasks_file risolve path per-progetto
# ════════════════════════════════════════════════════════════════


def test_tasks_file_path():
    """_tasks_file deve puntare a progetto/tasks/queue.json."""
    tmp = tempfile.mkdtemp()
    try:
        proj = _make_project(tmp, "progettoY")
        f = _tasks_file(proj)
        expected = Path(proj) / "tasks" / "queue.json"
        assert str(f) == str(expected)

        # project_path=None → file globale
        f_globale = _tasks_file(None)
        assert f_globale.name == "queue.json"
    finally:
        shutil.rmtree(tmp)


# ════════════════════════════════════════════════════════════════
# TEST: GUI — File Manager (selezionamento checkbox)
# ════════════════════════════════════════════════════════════════


def test_file_manager_checkbox_toggle():
    """Verifica che le checkbox del file manager si selezionino/deselezionino."""
    tmp = tempfile.mkdtemp()
    try:
        proj = _make_project(tmp, "progettoZ")
        open(os.path.join(proj, "main.py"), "w").write("print('ciao')")
        open(os.path.join(proj, "utils.py"), "w").write("def x(): pass")

        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt, QModelIndex

        app = QApplication.instance() or QApplication(sys.argv)

        from GUI.control_center import ControlCenter

        cc = ControlCenter()
        cc.show()
        app.processEvents()

        drawer = cc.drawer
        drawer.set_current_folder(proj)
        app.processEvents()

        root_idx = QModelIndex()

        # Trova l'index di main.py (colonna checkbox = 1)
        main_idx = None
        for r in range(drawer.model.rowCount(root_idx)):
            c1 = drawer.model.index(r, 1, root_idx)
            if drawer.model.filePath(c1).endswith("main.py"):
                main_idx = c1
                break

        assert main_idx is not None, "main.py non trovato nell'albero"
        target_path = os.path.join(proj, "main.py")

        # Stato iniziale: non selezionato
        assert target_path not in drawer.model.checked_paths()

        # Seleziona (setData Checked)
        drawer.model.setData(main_idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        app.processEvents()
        assert target_path in drawer.model.checked_paths(), "Selezione fallita"

        # Deseleziona (setData Unchecked)
        drawer.model.setData(main_idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        app.processEvents()
        assert target_path not in drawer.model.checked_paths(), "Deselezione fallita"

        # Riselena
        drawer.model.setData(main_idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        app.processEvents()
        assert target_path in drawer.model.checked_paths(), "Riselezione fallita"

        cc.close()
    finally:
        shutil.rmtree(tmp)


def test_file_manager_create_and_delete():
    """Verifica creazione e eliminazione file/cartelle nel file manager."""
    tmp = tempfile.mkdtemp()
    try:
        proj = _make_project(tmp, "progettoW")

        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt, QModelIndex
        from unittest.mock import patch

        app = QApplication.instance() or QApplication(sys.argv)

        from GUI.control_center import ControlCenter

        cc = ControlCenter()
        cc.show()
        app.processEvents()

        drawer = cc.drawer
        drawer.set_current_folder(proj)
        app.processEvents()

        root_idx = QModelIndex()

        # --- CREATE file ---
        with patch("PyQt6.QtWidgets.QInputDialog.getText",
                   return_value=("nuovo_file.txt", True)):
            drawer._add_text_file()
        app.processEvents()

        nuovo_file = os.path.join(proj, "nuovo_file.txt")
        assert os.path.exists(nuovo_file), "File non creato"

        # Verifica che appaia nell'albero
        trovato = False
        for r in range(drawer.model.rowCount(root_idx)):
            c1 = drawer.model.index(r, 1, root_idx)
            if drawer.model.filePath(c1) == nuovo_file:
                trovato = True
                break
        assert trovato, "Nuovo file non appare nell'albero"

        # --- CREATE cartella ---
        with patch("PyQt6.QtWidgets.QInputDialog.getText",
                   return_value=("nuova_cartella", True)):
            drawer._add_folder()
        app.processEvents()

        nuova_cartella = os.path.join(proj, "nuova_cartella")
        assert os.path.isdir(nuova_cartella), "Cartella non creata"

        # Verifica che appaia nell'albero
        trovato_cartella = False
        for r in range(drawer.model.rowCount(root_idx)):
            c1 = drawer.model.index(r, 1, root_idx)
            if drawer.model.filePath(c1) == nuova_cartella:
                trovato_cartella = True
                break
        assert trovato_cartella, "Nuova cartella non appare nell'albero"

        # --- DELETE file ---
        # Seleziona il file (colonna checkbox = 1)
        for r in range(drawer.model.rowCount(root_idx)):
            c1 = drawer.model.index(r, 1, root_idx)
            if drawer.model.filePath(c1) == nuovo_file:
                drawer.model.setData(c1, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
                break
        app.processEvents()
        assert nuovo_file in drawer.model.checked_paths(), "File non selezionato per eliminazione"

        # Elimina (mock della QMessageBox per saltare la conferma)
        with patch("PyQt6.QtWidgets.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            drawer._delete_selected_items()
        app.processEvents()

        assert not os.path.exists(nuovo_file), "File non eliminato"
        trovato_dopo = False
        for r in range(drawer.model.rowCount(root_idx)):
            c1 = drawer.model.index(r, 1, root_idx)
            if drawer.model.filePath(c1) == nuovo_file:
                trovato_dopo = True
                break
        assert not trovato_dopo, "File ancora presente nell'albero dopo eliminazione"

        cc.close()
    finally:
        shutil.rmtree(tmp)


# ════════════════════════════════════════════════════════════════
# TEST: GUI — File Editor (rinomina file)
# ════════════════════════════════════════════════════════════════


def test_file_editor_rename():
    """Verifica che il nome del file nell'editor sia modificabile e rinomini il file."""
    tmp = tempfile.mkdtemp()
    try:
        test_file = os.path.join(tmp, "prova.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("contenuto di prova")

        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)

        from GUI.control_center import FileEditorWidget

        editor = FileEditorWidget(test_file, docked=False)
        editor.show()
        app.processEvents()

        # Nome iniziale
        assert editor.file_name_edit.text() == "prova.txt"
        assert editor.file_path == test_file

        # Rinomina
        editor.file_name_edit.setText("rinominato.txt")
        editor._rename_file()
        app.processEvents()

        assert editor.file_path == os.path.join(tmp, "rinominato.txt")
        assert editor.file_name_edit.text() == "rinominato.txt"
        assert os.path.isfile(os.path.join(tmp, "rinominato.txt"))
        assert not os.path.exists(test_file), "File originale non dovrebbe esistere più"

        editor.close()
    finally:
        shutil.rmtree(tmp)


# ════════════════════════════════════════════════════════════════
# TEST: Task Scheduler — aggiornamento al cambio progetto
# ════════════════════════════════════════════════════════════════


def test_task_scheduler_refresh_on_project_change():
    """Il pannello Task Scheduler deve mostrare i task del progetto corrente."""
    tmp = tempfile.mkdtemp()
    try:
        proj1 = _make_project(tmp, "progetto1")
        proj2 = _make_project(tmp, "progetto2")

        from GUI.task_queue import save_tasks
        save_tasks([{"id": "p1-1", "title": "Task P1", "description": "", "status": "pending",
                     "attempts": 0, "subtasks": [], "parent": None, "created_at": 1,
                     "source": "gui", "type": "code"}], proj1)
        save_tasks([{"id": "p2-1", "title": "Task P2", "description": "", "status": "done",
                     "attempts": 0, "subtasks": [], "parent": None, "created_at": 2,
                     "source": "gui", "type": "code"}], proj2)

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)

        from GUI.control_center import ControlCenter

        cc = ControlCenter()
        cc.show()
        app.processEvents()

        drawer = cc.drawer
        scheduler = cc.center.panel_pages.get("coda")

        # Progetto 1
        cc._on_current_project_changed(proj1)
        app.processEvents()
        titoli1 = [scheduler.task_list_widget.item(i).text()
                   for i in range(scheduler.task_list_widget.count())]
        assert any("progetto1" in t or "P1" in t for t in titoli1), f"Atteso task P1, trovato: {titoli1}"

        # Progetto 2
        cc._on_current_project_changed(proj2)
        app.processEvents()
        titoli2 = [scheduler.task_list_widget.item(i).text()
                   for i in range(scheduler.task_list_widget.count())]
        assert any("progetto2" in t or "P2" in t for t in titoli2), f"Atteso task P2, trovato: {titoli2}"
        assert not any("P1" in t for t in titoli2), f"Non dovrebbe esserci task P1, trovato: {titoli2}"

        cc.close()
    finally:
        shutil.rmtree(tmp)
