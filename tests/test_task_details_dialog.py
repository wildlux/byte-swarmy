# -*- coding: utf-8 -*-
"""Regression test — il dialog "📋 Dettagli task" deve aprirsi (2026-11-22).

Bug: ``_show_task_details`` usava ``QWidget`` senza importarlo; il ``NameError``
veniva inghiottito da un ``except`` che faceva solo ``print``, quindi la
finestra non si apriva e l'utente non vedeva alcun errore.

I test girano offscreen e non aprono dialog modali: ``QDialog.exec`` viene
sostituito da una lambda che registra il titolo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QDialog, QListWidget, QListWidgetItem, QMenu, QMessageBox,
)

from GUI import file_tree_drawer as ftd  # noqa: E402

_TASK = {
    "id": "task-test-123",
    "title": "Task di prova",
    "status": "done",
    "type": "generic",
    "source": "test",
    "attempts": 1,
    "created_at": 1700000000,
    "result": "OK",
    "description": "descrizione",
}


def _drawer(monkeypatch):
    """Drawer con task fake, senza file di progetto e senza dialog reali."""
    opened, warnings = [], []

    monkeypatch.setattr(ftd, "load_tasks", lambda project_path=None: [_TASK])
    monkeypatch.setattr(
        ftd.FileTreeDrawer, "_collect_task_files",
        lambda self, task, base: [],
    )
    monkeypatch.setattr(QDialog, "exec", lambda self: opened.append(
        self.windowTitle()) or 0)
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *a, **k: warnings.append(a[2] if len(a) > 2 else k),
    )
    return ftd.FileTreeDrawer(), opened, warnings


def test_details_dialog_opens(monkeypatch):
    """Il click su Dettagli apre esattamente un dialog, senza warning."""
    drawer, opened, warnings = _drawer(monkeypatch)
    drawer._show_task_details(_TASK["id"])
    assert len(opened) == 1, f"Dialog non aperto: {warnings}"
    assert _TASK["id"][:12] in opened[0]
    assert warnings == []


def test_details_dialog_with_files(monkeypatch):
    """La colonna destra con visualizzatore codice non deve rompere il dialog."""
    drawer, opened, warnings = _drawer(monkeypatch)
    monkeypatch.setattr(
        ftd.FileTreeDrawer, "_collect_task_files",
        lambda self, task, base: [str(ROOT / "README.md")],
    )
    drawer._show_task_details(_TASK["id"])
    assert len(opened) == 1, f"Dialog non aperto: {warnings}"
    assert warnings == []


def test_missing_task_shows_warning(monkeypatch):
    """Un task inesistente avvisa l'utente invece di non fare nulla."""
    drawer, opened, warnings = _drawer(monkeypatch)
    drawer._show_task_details("inesistente")
    assert opened == []
    assert any("non trovato" in str(w) for w in warnings), warnings


def test_context_menu_action_opens_dialog(monkeypatch):
    """Percorso reale: tasto destro -> 📋 Dettagli task -> dialog."""
    drawer, opened, warnings = _drawer(monkeypatch)
    menu_holder = []
    monkeypatch.setattr(
        QMenu, "exec", lambda self, pos=None: menu_holder.append(self))
    task_list = QListWidget()
    item = QListWidgetItem(_TASK["title"])
    item.setData(Qt.ItemDataRole.UserRole, _TASK["id"])
    task_list.addItem(item)
    drawer.task_list = task_list

    drawer._on_task_context_menu(QPoint(5, 5))

    assert menu_holder, "Menu contestuale non creato"
    actions = [a for a in menu_holder[0].actions()
               if "Dettagli" in a.text()]
    assert len(actions) == 1, [a.text() for a in menu_holder[0].actions()]
    actions[0].trigger()
    assert len(opened) == 1, f"Dialog non aperto: {warnings}"
