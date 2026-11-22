# -*- coding: utf-8 -*-
"""Regression test — eliminazione etichette e click sull'ordinamento (2026-11-22).

Bug 1: ``remove_label`` cancellava il JSON ma ``list_labels`` richiamava
``ensure_default_labels``, che ricreava "Test" (etichetta di default).
Bug 2: ``sectionClicked`` era collegato ma l'header non era ``sectionsClickable``:
i click dell'utente non emettevano mai il segnale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QMessageBox  # noqa: E402

from CORE import labels as L  # noqa: E402
from GUI import label_actions  # noqa: E402
from GUI import task_queue  # noqa: E402
from GUI.file_tree_drawer import FileTreeDrawer  # noqa: E402
from GUI.settings_panel import SettingsPanel  # noqa: E402


@pytest.fixture
def labels_files(monkeypatch, tmp_path):
    """Registry e tombstone isolati: non tocca state/labels.json reale."""
    monkeypatch.setattr(L, "LABELS_FILE", tmp_path / "labels.json")
    monkeypatch.setattr(L, "DELETED_FILE", tmp_path / "labels_deleted.json")
    L.ensure_default_labels()
    return tmp_path


def _names() -> list[str]:
    return [entry["name"] for entry in L.list_labels()]


def test_default_label_stays_deleted(labels_files):
    """Una default eliminata non deve ricomparire al prossimo list_labels."""
    assert "Test" in _names()
    assert L.remove_label("Test") is True
    assert "Test" not in _names()
    assert "Test" not in json.loads(labels_files.joinpath("labels.json").read_text())
    assert "Test" in json.loads(
        labels_files.joinpath("labels_deleted.json").read_text())
    # Simula un secondo accesso in un'altra sessione
    assert "Test" not in _names()
    assert L.remove_label("Test") is False


def test_recreating_label_clears_tombstone(labels_files):
    """Se l'utente riaggiunge il nome, torna un'etichetta normale."""
    L.remove_label("Test")
    L.get_or_create_label("Test")
    assert "Test" in _names()
    assert "Test" not in json.loads(
        labels_files.joinpath("labels_deleted.json").read_text())


def test_delete_label_everywhere_updates_tasks(labels_files, monkeypatch):
    """L'etichetta viene tolta anche dai task (labels come stringa JSON)."""
    updates = []
    tasks = [
        {"id": "t1", "labels": '["Test", "Altro"]'},
        {"id": "t2", "labels": ["Bug"]},
    ]
    monkeypatch.setattr(task_queue, "load_tasks", lambda project_path=None: tasks)
    monkeypatch.setattr(
        task_queue, "update_task_labels",
        lambda task_id, labels, project_path=None: updates.append(
            (task_id, labels)),
    )

    assert label_actions.delete_label_everywhere("Test", None) is True
    assert updates == [("t1", ["Altro"])]
    assert "Test" not in _names()


def test_settings_confirm_deletes_label(labels_files, monkeypatch):
    """Il dialog di conferma con 'Sì' elimina davvero l'etichetta."""
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    fake = SimpleNamespace(_refresh_labels_list=lambda: None)
    SettingsPanel._on_delete_label(fake, "Test")
    assert "Test" not in _names()


def _tree_with_files(tmp_path, qapp):
    """Drawer con una cartella di esempio (file + cartelle) già popolata."""
    for name in ("zeta.txt", "Alpha.py", "beta.md"):
        (tmp_path / name).write_text("x")
    (tmp_path / "Cartella_Z").mkdir()
    (tmp_path / "Cartella_A").mkdir()
    drawer = FileTreeDrawer()
    drawer.resize(360, 600)
    drawer.show()
    drawer.model.set_root_path(str(tmp_path))
    qapp.processEvents()
    return drawer


def _click_header(drawer, section, qapp):
    """Click REALE sul viewport dell'header (non emissione manuale)."""
    header = drawer.tree.header()
    x = header.sectionViewportPosition(section) + header.sectionSize(section) // 2
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton,
                     pos=QPoint(x, 10))
    qapp.processEvents()


def _names_tree(drawer):
    root = drawer.model.invisibleRootItem()
    return [root.child(row, 3).text() for row in range(root.rowCount())]


def test_header_clicks_are_connected(tmp_path, qapp):
    """I click su Name e 📄 devono ordinare: prima A→Z, poi Z→A, poi tipologia."""
    drawer = _tree_with_files(tmp_path, qapp)
    assert drawer.tree.header().sectionsClickable() is True

    _click_header(drawer, 3, qapp)
    assert drawer.model._sort_mode == "name"
    assert drawer.model._sort_desc is False
    assert drawer.tree.header().sortIndicatorSection() == 3

    _click_header(drawer, 3, qapp)
    assert drawer.model._sort_desc is True
    assert _names_tree(drawer)[0] == "zeta.txt"

    _click_header(drawer, 2, qapp)
    assert drawer.model._sort_mode == "type"
    assert drawer.model._folders_first is True
    assert _names_tree(drawer)[:2] == ["Cartella_A", "Cartella_Z"]

    _click_header(drawer, 2, qapp)
    assert drawer.model._folders_first is False
    assert _names_tree(drawer)[-2:] == ["Cartella_A", "Cartella_Z"]
