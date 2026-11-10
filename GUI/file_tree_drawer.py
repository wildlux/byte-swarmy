# -*- coding: utf-8 -*-
"""file_tree_drawer.py — File tree drawer e lista task "Lavori e compiti".

Estratto da GUI/control_center.py per ridurre il monolite.
Fornisce l'interfaccia per la gestione di file e task nella sidebar.
"""

from __future__ import annotations

import os
import json
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QAbstractItemView, QTreeView, QListWidget, QListWidgetItem,
    QHeaderView, QFileIconProvider, QMessageBox, QInputDialog, QMenu,
)
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon, QPixmap, QPalette, QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize as _QSize, QPropertyAnimation, QEasingCurve, QModelIndex

BASE_DIR = Path(__file__).parent.parent.resolve()

from CORE.constants import (
    BTN_TRANSPARENT_STYLE,
    BTN_TRANSPARENT_DANGER_STYLE,
    BTN_TRANSPARENT_MEDIUM_STYLE,
    BTN_TRANSPARENT_SMALL_STYLE,
)
from GUI.file_manager import FileSystemModel, CheckableTreeView
from GUI.task_item_row import TaskItemRow
from GUI.task_list_widget import TaskListWidget
from GUI import settings_store

# _click_log è definito in control_center.py; lo importiamo in modo sicuro
# per evitare dipendenze circolari (control_center importa da questo modulo).
try:
    from GUI.control_center import _click_log  # type: ignore
except Exception:  # pragma: no cover
    def _click_log(*args, **kwargs):  # type: ignore
        pass


class FileTreeDrawer(QFrame):
    """File tree drawer e lista task "Lavori e compiti"."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("file_tree_drawer")
        self.model = FileSystemModel()

        # === Layout principale ===
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # === Splitter verticale: file tree in alto ===
        self.splitter_vertical = QSplitter(Qt.Orientation.Vertical)
        lay.addWidget(self.splitter_vertical)

        # File tree
        self.tree = CheckableTreeView()
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.clicked.connect(self._on_tree_click)
        self.tree.doubleClicked.connect(self._on_tree_double_click)
        self.tree.expanded.connect(self._on_folder_expanded)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(0, 0))
        self.tree.setAnimated(False)
        self.tree.setIndentation(10)
        self.tree.setSortingEnabled(True)
        self.tree.header().sectionClicked.connect(self._on_header_section_clicked)
        self.splitter_vertical.addWidget(self.tree)

        # === Task list widget (G1: estrapolato in task_list_widget.py) ===
        # Aggiunto sotto lo splitter (in basso)
        self.task_list_widget = TaskListWidget(
            on_select_all_toggled=self._toggle_select_all_tasks,
            on_refresh_requested=self._force_refresh_tasks,
            on_add_requested=lambda: None,
            on_delete_checked_requested=self._delete_checked_tasks,
            on_clean_queue_requested=self._clean_queue,
            on_task_activated=self._on_task_double_clicked,
            on_context_menu=self._on_task_context_menu,
        )
        lay.addWidget(self.task_list_widget)

    # Context menu per il file tree
    def _on_tree_context_menu(self, pos):
        """Show context menu for file tree."""
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        path = self.model.filePath(index)
        if not path:
            return
        is_file = os.path.isfile(path)

        menu = QMenu(self)

        if is_file:
            act_edit = QAction("Modifica file", self)
            act_edit.triggered.connect(lambda: self.parent._show_file_editor(path))
            menu.addAction(act_edit)
            menu.addSeparator()

        act_rename = QAction("Rinomina", self)
        act_rename.triggered.connect(lambda: self._rename_item(path))
        menu.addAction(act_rename)

        act_delete = QAction("Cancella", self)
        act_delete.triggered.connect(lambda: self._delete_item(path))
        menu.addAction(act_delete)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _on_tree_click(self, index):
        """Gestisce il click sull'albero dei file."""
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt as _Qt
            if QApplication.keyboardModifiers() & _Qt.KeyboardModifier.ShiftModifier:
                path = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else ""
                info = self._debug_call_info("albero-click", path)
                QApplication.clipboard().setText(info)
                if self._GUI_DEBUG:
                    print("[DEBUG] Shift+click copiato negli appunti:", info)
                return
            if not index.isValid():
                return
            if index.column() == 0:
                # Toggle manuale della checkbox su colonna 0
                fp = index.data(Qt.ItemDataRole.UserRole)
                if fp in self.model.checked_paths():
                    self.model.setData(index, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
                    _click_log("filemanager", "deseleziona",
                                self.parent().get_current_project_path() if self.parent() else "",
                                fp)
                else:
                    self.model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
                    _click_log("filemanager", "seleziona",
                                self.parent().get_current_project_path() if self.parent() else "",
                                fp)
                return
            path = index.data(Qt.ItemDataRole.UserRole)
            if not path or not os.path.exists(path):
                return
            if os.path.isdir(path):
                return
            if getattr(self, "_editor_open_timer", None) is not None:
                self._editor_open_timer.stop()
            self._pending_editor_path = None
            self._rename_item(path)
        except Exception as e:
            print("Errore click albero:", e)

    def _on_tree_double_click(self, index):
        """Gestisce il doppio click sull'albero."""
        try:
            if not index.isValid():
                return
            path = index.data(Qt.ItemDataRole.UserRole)
            if not path or not os.path.exists(path):
                return
            if os.path.isdir(path):
                return
            if getattr(self, "_editor_open_timer", None) is not None:
                self._editor_open_timer.stop()
            self._pending_editor_path = None
            self._rename_item(path)
        except Exception as e:
            print("Errore doppio click albero:", e)

    def _on_folder_expanded(self, index):
        """Evento di espansione nodo albero (placeholder)."""
        pass

    def _toggle_sort_order(self):
        self.model._folders_first = not self.model._folders_first
        self.parent.parent.sort_btn.setText("📁📄" if self.model._folders_first else "📄📁")
        self._refresh_file_tree()

    def _sort_by_name(self):
        parent = self.parent.parent.invisibleRootItem()
        self._sort_children_recursive(parent)

    def _sort_children_recursive(self, parent_item):
        rows = parent_item.rowCount()
        if rows <= 1:
            return
        row_items = []
        for _ in range(rows):
            row_items.append(parent_item.takeRow(0))
        row_items.sort(key=lambda row: (
            not row[0].data(Qt.ItemDataRole.UserRole + 1),
            str(row[3].data(Qt.ItemDataRole.UserRole) or "").lower(),
        ))
        for row in row_items:
            parent_item.appendRow(row)
        for row in row_items:
            col0 = row[0]
            if col0.data(Qt.ItemDataRole.UserRole + 1):
                first = col0.child(0, 0)
                if col0.rowCount() > 0 and first is not None and first.data(Qt.ItemDataRole.UserRole) is not None:
                    self._sort_children_recursive(col0)

    def _add_text_file(self):
        """Aggiunge un nuovo file di testo."""
        from PyQt6.QtWidgets import QInputDialog
        import os
        sel = self.tree.selectionModel().currentIndex()
        idx0 = sel.siblingAtColumn(0) if sel.isValid() else sel
        target_dir = ""
        if idx0.isValid():
            item = self.model.itemFromIndex(idx0)
            if item is not None:
                fp = item.data(Qt.ItemDataRole.UserRole)
                if fp and os.path.isdir(fp):
                    target_dir = fp
                elif fp:
                    target_dir = os.path.dirname(fp)
        if not target_dir:
            target_dir = self.model._root_path if hasattr(self.model, '_root_path') and self.model._root_path else str(BASE_DIR.resolve())
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = str(BASE_DIR.resolve())
        dlg = QInputDialog(self)
        dlg.setInputMode(QInputDialog.InputMode.TextInput)
        dlg.setTextValue("nuovo_file.txt")
        if dlg.exec():
            name = dlg.textValue()
        else:
            return
        if not any(name.endswith(ext) for ext in (".txt", ".md", ".py", ".sh", ".log", ".json", ".csv")):
            name += ".txt"
        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            base, ext = os.path.splitext(name)
            i = 1
            while os.path.exists(os.path.join(target_dir, "{base} ({i}){ext}".format(base=base, i=i, ext=ext))):
                i += 1
            suggested = "{base} ({i}){ext}".format(base=base, i=i, ext=ext)
            msg = "Il file '" + name + "' esiste già.\nVuoi usare " + suggested + "?"
            ans = QMessageBox.question(self, "Esiste già", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
            name = suggested
            new_path = os.path.join(target_dir, name)
        try:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write("")
            _click_log("filemanager", "crea file",
                        self.parent().get_current_project_path() if self.parent() else "",
                        new_path)
            self._refresh_file_tree()
            if self.parent_win:
                self.parent_win._show_file_editor(new_path)
        except Exception as e:
            QMessageBox.warning(self, "Errore", "Impossibile creare il file:\n" + str(e))

    def _add_folder(self):
        """Aggiunge una nuova cartella."""
        from PyQt6.QtWidgets import QInputDialog
        import os
        sel = self.tree.selectionModel().currentIndex()
        idx0 = sel.siblingAtColumn(0) if sel.isValid() else sel
        target_dir = ""
        if idx0.isValid():
            item = self.model.itemFromIndex(idx0)
            if item is not None:
                fp = item.data(Qt.ItemDataRole.UserRole)
                if fp and os.path.isdir(fp):
                    target_dir = fp
                elif fp:
                    target_dir = os.path.dirname(fp)
        if not target_dir:
            target_dir = self.model._root_path if hasattr(self.model, '_root_path') and self.model._root_path else str(BASE_DIR.resolve())
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = str(BASE_DIR.resolve())
        dlg = QInputDialog(self)
        dlg.setInputMode(QInputDialog.InputMode.TextInput)
        dlg.setTextValue("nuova_cartella")
        if dlg.exec():
            name = dlg.textValue()
        else:
            return
        name = name.strip()
        name = name.replace("/", os.sep).replace("\\", os.sep)
        name = os.path.basename(name)
        if not name or name in (".", ".."):
            QMessageBox.warning(self, "Nome non valido", "Inserisci un nome di cartella valido.")
            return
        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            base = name
            i = 1
            while os.path.exists(os.path.join(target_dir, "{base} ({i})".format(base=base, i=i))):
                i += 1
            suggested = "{base} ({i})".format(base=base, i=i)
            msg2 = "La cartella '" + name + "' esiste gi".format(name) + "\nVuoi usare " + suggested + "?"
            ans = QMessageBox.question(self, "Esiste già", msg2,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
            name = suggested
            new_path = os.path.join(target_dir, name)
        try:
            os.makedirs(new_path, exist_ok=True)
            _click_log("filemanager", "crea cartella",
                        self.parent().get_current_project_path() if self.parent() else "",
                        new_path)
            self._refresh_file_tree()
        except Exception as e:
            QMessageBox.warning(self, "Errore", "Impossibile creare la cartella: " + "\n" + str(e))

    def _refresh_file_tree(self):
        """Ricarica l'albero file."""
        try:
            target_dir = self.parent.parent.model._root_path
            if not target_dir or not os.path.isdir(target_dir):
                target_dir = str(BASE_DIR.resolve())
            self.parent.parent.model.set_root_path(target_dir)
            self.parent.parent.tree.setRootIndex(QModelIndex())
            self.parent.parent.tree.scrollToTop()
            self._sort_by_name()
            _click_log("filemanager", "refresh",
                        self.parent.parent.parent.get_current_project_path() if self.parent.parent.parent else "",
                        target_dir)
        except Exception as e:
            print("Errore refresh file tree:", e)

    def _on_header_section_clicked(self, logicalIndex: int):
        """Gestisce il click sulla header della colonna."""
        if logicalIndex == 3:
            self._sort_by_name()

    def set_current_folder(self, path: str):
        """Imposta la cartella corrente nell'albero file."""
        if not path or not os.path.isdir(path):
            path = str(BASE_DIR.resolve())
        self.model.set_root_path(path)
        self.tree.setRootIndex(self.model.index(0, 0))

    def _on_task_double_clicked(self, task_id: str):
        """Gestisce il doppio click su una task."""
        self._debug_call_info("_on_task_double_clicked", task_id)

    def _on_task_context_menu(self, pos):
        """Show context menu for task list widget."""
        from PyQt6.QtWidgets import QApplication
        menu = QMenu(self)
        act_delete = QAction("Elimina", self)
        act_delete.triggered.connect(self._delete_checked_tasks)
        menu.addAction(act_delete)
        menu.exec(QApplication.mouseGlobalPos(pos))

    def _debug_call_info(self, handler_name, extra=""):
        """Registra informazioni di debug per segnalazioni al sviluppatore."""
        if self._GUI_DEBUG:
            print("[DEBUG] " + handler_name + ": " + extra)
