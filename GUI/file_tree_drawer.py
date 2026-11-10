# -*- coding: utf-8 -*-
"""file_tree_drawer.py — Sidebar "Archivio progetto" + "Lavori e Compiti".

Estratto originariamente da ``GUI/control_center.py`` durante la
rifattorizzazione modulare (commit ``ff73e40``), ma lo stub estratto
conteneva solo il 30% del codice originale: i metodi per rename, delete,
toggle-select-all, refresh task, context menu, sort, column widths, ecc.
erano stati omessi, causando ``AttributeError`` gia' in fase di
costruzione (il costruttore passa ``self._toggle_select_all_tasks`` e
altri come callback a ``TaskListWidget(...)``).

Questo file ripristina la classe completa adattando gli import al nuovo
layout modulare:
- ``load_tasks`` / ``delete_task`` ora da ``GUI.task_queue`` (non piu'
  da ``GUI.main_window``, che e' stato rimosso)
- ``_is_junk_project_path`` / ``build_run_command`` da ``GUI.project_tab_bar``
- ``_pause_task`` / ``_resume_single_task`` / ``_stop_task`` /
  ``_restart_task`` / ``_log_user_action`` ripristinate in
  ``GUI.task_queue`` come funzioni pubbliche
"""

from __future__ import annotations

import os
import json
import re
import time
import shutil
import sqlite3
import inspect
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QAbstractItemView, QTreeView, QListWidget, QListWidgetItem,
    QHeaderView, QFileIconProvider, QMessageBox, QInputDialog, QMenu,
    QApplication,
)
from PyQt6.QtGui import (
    QColor, QBrush, QFont, QIcon, QPixmap, QPalette,
    QStandardItemModel, QStandardItem, QAction, QDesktopServices,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QSize as _QSize, QPropertyAnimation,
    QEasingCurve, QModelIndex, QUrl, QProcess,
    QItemSelectionModel,
)

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
from GUI.task_queue import (
    load_tasks, delete_task,
    pause_task as _pause_task,
    resume_single_task as _resume_single_task,
    stop_task as _stop_task,
    restart_task as _restart_task,
    log_user_action as _log_user_action,
)
from GUI.project_tab_bar import _is_junk_project_path, build_run_command

# Pallino di stato per riga task (TaskItemRow):
# verde=fatto, giallo=in lavorazione, rosso=in attesa.
TASK_STATUS_STYLE = {
    "done":           ("✓", "#16a34a"),   # verde: completato
    "running":        ("▶", "#eab308"),   # giallo: in lavorazione
    "retry":          ("▶", "#eab308"),
    "pending":        ("○", "#dc2626"),   # rosso: in attesa
    "queued":         ("○", "#dc2626"),
    "planned":        ("○", "#dc2626"),
    "failed":         ("✗", "#991b1b"),
    "stuck":          ("✗", "#991b1b"),
    "stopped":        ("🛑", "#991b1b"),
    "paused":         ("⏸", "#6b7280"),
    "thermal_paused": ("🌡", "#f97316"),
}

# ``_click_log`` e' definito in ``GUI.control_center``; lo importiamo in modo
# sicuro per evitare dipendenze circolari (control_center importa da questo
# modulo). Se l'import fallisce, usiamo un no-op.
try:
    from GUI.control_center import _click_log  # type: ignore
except Exception:  # pragma: no cover
    def _click_log(*args, **kwargs):  # type: ignore
        pass


# QSize: PyQt6 ha QSize in QtCore ma alcuni import legacy lo aliasano
QSize = _QSize


class FileTreeDrawer(QFrame):
    """Sidebar sinistra del Control Center.

    Contiene:
    - Header ``📁 Archivio progetto`` con pulsanti (➕ 📁 🔄 🗑️)
    - Path della cartella corrente
    - File tree (QTreeView con checkbox multipla, lazy-loading, ordinamento)
    - Splitter verticale
    - Header ``📋 Lavori e Compiti`` con pulsanti (☑ 🔄 ➕ 🗑️ 🧹)
    - Lista task del progetto attivo

    Costruttore:
        FileTreeDrawer(parent=ControlCenter)

    Il ``parent`` viene conservato come ``self.main_win`` per accedere a
    ``main_win.get_current_project_path()`` e ``main_win._show_file_editor()``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("file_tree_drawer")
        # Larghezza tra 1/4 (minimo) e 1/3 (massimo) della finestra per
        # rendere il testo dei file leggibile e allineato.
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)

        # === Riferimento al ControlCenter genitore ===
        # ``parent`` e' il ControlCenter: serve per chiamare
        # get_current_project_path(), _show_file_editor(), _refresh_coda_card()
        # e _refresh_task_list().
        self.main_win = parent
        # Flag debug sincronizzato con Impostazioni: evita AttributeError
        # in _force_refresh_tasks / _on_task_item_changed / _on_tree_click.
        self._GUI_DEBUG = settings_store.get_gui_debug()
        # Timer per aprire l'editor dopo click singolo (annullato dal doppio)
        self._pending_editor_path = None
        self._editor_open_timer = None
        # Flag anti-loop durante refresh programmato della lista task
        self._refreshing_tasks = False

        # === Layout principale ===
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(0)

        # === Riga sopra: titolo "Archivio progetto" ===
        header_title_row = QHBoxLayout()
        header_title_row.setContentsMargins(0, 0, 0, 0)
        header_title_row.setSpacing(0)
        self.header = QLabel("<b>📁 Archivio progetto</b>")
        self.header.setObjectName("sidebar_header")
        self.header.setStyleSheet(  # nolint: header verde accordion Archivio
            "padding:0; color:#16a34a; font-size:11px; font-weight:bold;"
        )
        self.header.setWordWrap(True)
        self.header.setMinimumHeight(30)
        header_title_row.addWidget(self.header, stretch=0)
        lay.addLayout(header_title_row)

        # === Riga sotto: pulsanti allineati a sinistra ===
        header_btn_row = QHBoxLayout()
        header_btn_row.setContentsMargins(0, 0, 0, 0)
        header_btn_row.setSpacing(4)

        # ➕ Crea nuovo file di testo
        self.add_file_btn = QPushButton("➕")
        self.add_file_btn.setFixedSize(28, 28)
        self.add_file_btn.setToolTip("Crea un nuovo file di testo nella cartella corrente")
        self.add_file_btn.setStyleSheet(BTN_TRANSPARENT_STYLE)
        self.add_file_btn.clicked.connect(self._add_text_file)
        header_btn_row.addWidget(self.add_file_btn)

        # 📁 Crea nuova cartella
        self.add_folder_btn = QPushButton("📁")
        self.add_folder_btn.setFixedSize(28, 28)
        self.add_folder_btn.setToolTip("Crea una nuova cartella nella cartella corrente")
        self.add_folder_btn.setStyleSheet(BTN_TRANSPARENT_STYLE)
        self.add_folder_btn.clicked.connect(self._add_folder)
        header_btn_row.addWidget(self.add_folder_btn)

        # 🔄 Refresh file tree
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setToolTip("Aggiorna file tree (cartelle e file della cartella corrente)")
        self.refresh_btn.setStyleSheet(BTN_TRANSPARENT_STYLE)
        self.refresh_btn.clicked.connect(self._refresh_file_tree)
        header_btn_row.addWidget(self.refresh_btn)

        # 🗑️ Elimina selezionati (colonna ✓)
        self.del_btn = QPushButton("🗑️")
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setToolTip("Elimina file/cartelle selezionate con la colonna ✓")
        self.del_btn.setStyleSheet(BTN_TRANSPARENT_DANGER_STYLE)
        self.del_btn.clicked.connect(self._delete_selected_items)
        header_btn_row.addWidget(self.del_btn)

        header_btn_row.addStretch()
        lay.addLayout(header_btn_row)

        # Pulsante ordina (mantenuto per compatibilita', nascosto)
        self.sort_btn = QPushButton("📁📄")
        self.sort_btn.setFixedSize(28, 28)
        self.sort_btn.setToolTip("Ordina elementi: cartelle prima / file prima")
        self.sort_btn.setStyleSheet(BTN_TRANSPARENT_MEDIUM_STYLE)
        self.sort_btn.clicked.connect(self._toggle_sort_order)
        self.sort_btn.hide()

        # Sotto-titolo: path della cartella corrente (si aggiorna col tab)
        self.path_label = QLabel("byte-swarmy/")
        self.path_label.setObjectName("sidebar_path")
        self.path_label.setStyleSheet(
            "padding:0 16px 4px 16px; font-size:10px; "
            "font-family:'JetBrains Mono','Consolas',monospace;"
        )
        self.path_label.setWordWrap(True)
        lay.addWidget(self.path_label)

        # === File tree ===
        self.tree = CheckableTreeView()
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.model = FileSystemModel()
        self.tree.setModel(self.model)
        self.tree.set_drawer(self)
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.header().setStretchLastSection(False)
        self._apply_header_layout()
        self.tree.setIndentation(16)
        # Elimina padding/margini interni delle celle: checkbox piccole (13px)
        # e righe basse (22px) per un aspetto compatto.
        self.tree.setStyleSheet(
            "QTreeView { outline: 0px; font-size: 11px; }"
            "QTreeView::item { padding: 0px; border: none; height: 22px; }"
            "QTreeView::branch { padding: 0px; margin: 0px; }"
            "QTreeView::indicator { width: 13px; height: 13px; }"
            "QHeaderView::section { padding: 0px 2px; border: none; font-size: 10px; }"
        )
        # Ogni reset del model riporta le sezioni header a 100px di default:
        # riapplica il layout compatto dopo ogni reset/inserimento colonne.
        self.model.modelReset.connect(self._apply_header_layout)
        self.model.columnsInserted.connect(self._apply_header_layout)

        # Persistenza larghezze colonne
        self.tree.header().sectionResized.connect(self._save_column_widths)
        self._load_column_widths()

        # Ordinamento automatico per colonna Name
        self.tree.header().sectionClicked.connect(self._on_header_section_clicked)

        # Aggiorna l'icona del pulsante ordina secondo lo stato attuale
        self.sort_btn.setText("📁📄" if self.model._folders_first else "📄📁")

        # Signal wiring per il file tree
        self.tree.clicked.connect(self._on_tree_click)
        self.tree.doubleClicked.connect(self._on_tree_double_click)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.tree.expanded.connect(self._on_folder_expanded)
        self.model.dataChanged.connect(self._on_model_data_changed)

        # === Splitter verticale: file tree in alto, task list in basso ===
        self.splitter_vertical = QSplitter(Qt.Orientation.Vertical)
        self.splitter_vertical.addWidget(self.tree)

        # === Task list widget (delegato a TaskListWidget, nuovo design modulare) ===
        self.task_list_widget = TaskListWidget(
            on_select_all_toggled=self._toggle_select_all_tasks,
            on_refresh_requested=self._force_refresh_tasks,
            on_add_requested=lambda: self._on_task_add_requested(),
            on_delete_checked_requested=self._delete_checked_tasks,
            on_clean_queue_requested=self._clean_queue,
            on_task_activated=self._on_task_double_clicked,
            on_context_menu=self._on_task_context_menu,
        )
        # Esponi ``task_list`` come attributo diretto per retro-compatibilita'
        # con il codice originale (self.task_list.item(i), ecc.).
        self.task_list = self.task_list_widget.task_list
        # Connessioni aggiuntive non coperte dai callback di TaskListWidget:
        # shift+click debug + sync selezione visiva con stato checkbox.
        self.task_list.itemClicked.connect(self._on_task_item_clicked)
        self.task_list.itemChanged.connect(self._on_task_item_changed)

        self.splitter_vertical.addWidget(self.task_list_widget)
        lay.addWidget(self.splitter_vertical)

        # Carica dimensioni salvate dello splitter verticale
        state_file = BASE_DIR / "state" / "splitter_vertical_state.json"
        saved_sizes = None
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) == 2:
                    saved_sizes = [int(data[0]), int(data[1])]
            except Exception:
                pass
        if saved_sizes:
            self.splitter_vertical.setSizes(saved_sizes)
        else:
            # Divide a metà per default
            self.splitter_vertical.setSizes([300, 300])
        self.splitter_vertical.splitterMoved.connect(self._save_splitter_vertical_state)

        # Animazione (mantenuta per compatibilita', usata da toggle())
        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._open = True

        # Popola la lista task con i task reali del progetto attivo
        self._force_refresh_tasks()

    # ==================================================================
    # Persistenza splitter verticale
    # ==================================================================

    def _save_splitter_vertical_state(self):
        """Salva le larghezze dello splitter verticale (file tree <-> task list)
        in ``state/splitter_vertical_state.json`` per ripristinarle all'avvio.
        """
        try:
            state_file = BASE_DIR / "state" / "splitter_vertical_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            sizes = self.splitter_vertical.sizes()
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(sizes, f)
        except Exception as e:
            print(f"Errore salvataggio splitter verticale: {e}")

    # ==================================================================
    # Task list: toggle select-all
    # ==================================================================

    def _toggle_select_all_tasks(self, *args):
        """Seleziona/deseleziona tutte le checkbox dei task nella lista.

        Firma variadica per compatibilita' con TaskListWidget.on_select_all_toggled
        (chiama con bool) e con il vecchio codice inline (chiama senza arg).
        """
        try:
            if not hasattr(self, "task_list"):
                return
            items = [self.task_list.item(i) for i in range(self.task_list.count())]
            if not items:
                return
            tutte_selezionate = all(
                it.checkState() == Qt.CheckState.Checked for it in items
            )
            stato = Qt.CheckState.Unchecked if tutte_selezionate else Qt.CheckState.Checked
            for it in items:
                it.setCheckState(stato)
                # Sync riga visiva (TaskItemRow): checkbox della riga deve
                # riflettere il nuovo stato senza ri-emettere il segnale.
                row = self._task_row(it)
                if row is not None:
                    row.set_checked(stato == Qt.CheckState.Checked)
        except Exception as e:
            print(f"Errore toggle seleziona tutti i task: {e}")

    def _on_task_add_requested(self):
        """Apre il pannello coda (task scheduler) per aggiungere un task."""
        try:
            if self.main_win and hasattr(self.main_win, "center"):
                self.main_win.center.open_panel("coda")
        except Exception as e:
            print(f"Errore apertura pannello coda: {e}")

    # ==================================================================
    # set_current_folder — chiamato da ControlCenter al cambio tab progetto
    # ==================================================================

    def set_current_folder(self, folder_path: str):
        """Aggiorna il file tree per puntare alla cartella del progetto aperto.

        Chiamato quando l'utente cambia tab in ProjectTabBar: la sidebar
        'Archivio progetto' deve riflettere la cartella su cui si sta
        lavorando (es. project/sourceCode/ quando si seleziona il tab
        'sourceCode', o la root del repo quando si seleziona byte-swarmy).

        Aggiorna anche _current_project_path su ControlCenter e ricarica
        i task della sidebar: ogni sottoprogetto ha i propri task.
        """
        if not folder_path:
            return
        # Risolvi path relativo in assoluto
        if not os.path.isabs(folder_path):
            abs_candidate = os.path.join(str(BASE_DIR), folder_path)
            if os.path.isdir(abs_candidate):
                folder_path = abs_candidate
            else:
                if os.path.isdir(folder_path):
                    pass  # gia' valido
                else:
                    return
        if not os.path.isdir(folder_path):
            return
        # Aggiorna il percorso progetto corrente su ControlCenter
        if hasattr(self, 'main_win') and self.main_win is not None:
            self.main_win._current_project_path = folder_path
        # Aggiorna root del modello + rootIndex del QTreeView
        self.model.set_root_path(folder_path)
        self.tree.setRootIndex(QModelIndex())
        # Aggiorna il sottotitolo con il path
        try:
            rel = os.path.relpath(folder_path, str(BASE_DIR))
        except ValueError:
            rel = folder_path
        # Mostra solo il nome della cartella senza prefisso PR_
        base_name = os.path.basename(rel)
        if base_name.startswith("PR_"):
            base_name = base_name[3:]
        self.path_label.setText(base_name)
        # Scrolla in cima
        self.tree.scrollToTop()
        # Ricarica i task della sidebar per questo progetto
        self._force_refresh_tasks()

    # ==================================================================
    # Debug helper
    # ==================================================================

    def _debug_call_info(self, handler_name, extra=""):
        """Registra informazioni di debug per segnalazioni al sviluppatore."""
        frames = inspect.stack()
        caller = frames[1] if len(frames) > 1 else None
        if caller:
            fn = caller.function
            mod = inspect.getmodule(caller.frame)
            modname = mod.__name__ if mod else "?"
            fname = os.path.basename(caller.filename)
            line = caller.lineno
            cls = None
            selfobj = caller.frame.f_locals.get("self")
            if selfobj is not None:
                cls = type(selfobj).__name__
            parts = [f"{cls or '?'}", f"{fn}", f"({fname}:{line})"]
            if extra:
                parts.append(str(extra))
            return " | ".join(parts)
        return f"{handler_name} | {extra}"

    # ==================================================================
    # File tree: click / double click / context menu
    # ==================================================================

    def _on_tree_click(self, index):
        """Click sull'albero file: toggle checkbox su colonna 0, apre editor su file.

        Con Shift premuto: copia negli appunti la classe/riga di chiamata.
        """
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt as _Qt
            if QApplication.keyboardModifiers() & _Qt.KeyboardModifier.ShiftModifier:
                path = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else ""
                info = self._debug_call_info("FileTreeDrawer._on_tree_click", path)
                QApplication.clipboard().setText(info)
                if self._GUI_DEBUG:
                    print(f"[DEBUG] Shift+click copiato negli appunti: {info}")
                return
            if not index.isValid():
                return
            if index.column() == 0:
                # Toggle manuale della checkbox su colonna 0
                fp = index.data(Qt.ItemDataRole.UserRole)
                if fp in self.model.checked_paths():
                    self.model.setData(index, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
                    _click_log("filemanager", "deseleziona",
                                self.main_win.get_current_project_path() if self.main_win else "", fp)
                else:
                    self.model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
                    _click_log("filemanager", "seleziona",
                                self.main_win.get_current_project_path() if self.main_win else "", fp)
                return
            path = index.data(Qt.ItemDataRole.UserRole)
            if not path or not os.path.exists(path):
                return
            if os.path.isfile(path):
                # Ritarda l'apertura dell'editor: se arriva un doppio click
                # (rinomina) annulla l'apertura per non aprire l'editor inutilmente.
                self._pending_editor_path = path
                if self._editor_open_timer is None:
                    from PyQt6.QtCore import QTimer
                    self._editor_open_timer = QTimer(self)
                    self._editor_open_timer.setSingleShot(True)
                    self._editor_open_timer.timeout.connect(self._open_pending_editor)
                self._editor_open_timer.start(250)
        except Exception as e:
            print(f"Errore click albero: {e}")

    def _open_pending_editor(self):
        """Apre il file pending nell'editor (chiamato dal timer di _on_tree_click)."""
        path = getattr(self, "_pending_editor_path", None)
        if path and os.path.isfile(path):
            _click_log("filemanager", "apri file",
                        self.main_win.get_current_project_path() if self.main_win else "", path)
            if self.main_win and hasattr(self.main_win, "_show_file_editor"):
                self.main_win._show_file_editor(path)
        self._pending_editor_path = None

    def _on_tree_double_click(self, index):
        """Doppio click su un file: apre il campo di rinomina con il nome
        attuale gia' inserito, cosi' l'utente puo' cambiarlo direttamente."""
        try:
            if not index.isValid():
                return
            path = index.data(Qt.ItemDataRole.UserRole)
            if not path or not os.path.exists(path):
                return
            if os.path.isdir(path):
                return
            # Annulla l'apertura dell'editor in attesa (era un doppio click)
            if getattr(self, "_editor_open_timer", None) is not None:
                self._editor_open_timer.stop()
            self._pending_editor_path = None
            self._rename_item(path)
        except Exception as e:
            print(f"Errore doppio click albero: {e}")

    def _on_tree_context_menu(self, pos):
        """Menu contestuale tasto destro su un elemento del file tree."""
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        path = index.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        is_file = os.path.isfile(path)

        menu = QMenu(self)
        if is_file:
            act_edit = QAction("✏️ Modifica file", self)
            act_edit.triggered.connect(
                lambda: self.main_win._show_file_editor(path)
                if self.main_win and hasattr(self.main_win, "_show_file_editor")
                else None
            )
            menu.addAction(act_edit)
            menu.addSeparator()

        act_rename = QAction("📝 Rinomina", self)
        act_rename.triggered.connect(lambda: self._rename_item(path))
        menu.addAction(act_rename)

        act_delete = QAction("🗑️ Cancella", self)
        act_delete.triggered.connect(lambda: self._delete_item(path))
        menu.addAction(act_delete)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ==================================================================
    # File tree: rename / delete
    # ==================================================================

    def _rename_item(self, path):
        """Rinomina un file o cartella via QInputDialog."""
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(path), new_name)
            try:
                os.rename(path, new_path)
                # Ricarica l'albero per riflettere il nuovo nome
                self.model.set_root_path(
                    self.model._root_path
                    if hasattr(self.model, '_root_path') and self.model._root_path
                    else str(BASE_DIR.resolve())
                )
                self.tree.setRootIndex(QModelIndex())
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile rinominare:\n{e}")

    def _delete_item(self, path):
        """Elimina un singolo file o cartella (con conferma)."""
        name = os.path.basename(path)
        reply = QMessageBox.question(
            self, "Conferma cancellazione",
            f"Sei sicuro di voler eliminare '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
                # Ricarica l'albero
                self.model.set_root_path(
                    self.model._root_path
                    if hasattr(self.model, '_root_path') and self.model._root_path
                    else str(BASE_DIR.resolve())
                )
                self.tree.setRootIndex(QModelIndex())
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile eliminare:\n{e}")

    # ==================================================================
    # File tree: refresh, expand, model data changed
    # ==================================================================

    def _refresh_file_tree(self):
        """Forza il refresh del file tree (cartelle e file della cartella corrente).

        Utile dopo creazione/eliminazione di elementi o per allineare il model
        con lo stato reale del disco.
        """
        try:
            target_dir = (
                self.model._root_path
                if hasattr(self.model, '_root_path') and self.model._root_path
                else str(BASE_DIR.resolve())
            )
            if not target_dir or not os.path.isdir(target_dir):
                target_dir = str(BASE_DIR.resolve())
            self.model.set_root_path(target_dir)
            self.tree.setRootIndex(QModelIndex())
            self.tree.scrollToTop()
            # Ordina automaticamente: cartelle prima, poi file, alfabeticamente
            self._sort_by_name()
            _click_log("filemanager", "refresh",
                        self.main_win.get_current_project_path() if self.main_win else "",
                        target_dir)
        except Exception as e:
            QMessageBox.warning(self, "Errore",
                                f"Impossibile aggiornare il file tree:\n{e}")

    def _on_folder_expanded(self, index):
        """Quando una cartella viene espansa, popola i suoi figli (lazy loading)."""
        if not index.isValid() or index.column() != 0:
            return
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        # Verifica se c'e' un placeholder da sostituire
        if item.rowCount() > 0:
            child = item.child(0, 0)
            if child is not None and not child.isEnabled():
                # E' un placeholder, popola i figli reali
                self.model.populate_on_expand(item)

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        """Sincronizza selezione visiva QTreeView con stato checkbox del model."""
        if Qt.ItemDataRole.CheckStateRole not in roles:
            return
        if top_left.column() != 1:
            return
        fp = top_left.data(Qt.ItemDataRole.UserRole)
        stato = "selezionato" if fp in self.model.checked_paths() else "deselezionato"
        _click_log("filemanager", stato,
                    self.main_win.get_current_project_path() if self.main_win else "", fp)
        # setCurrentIndex garantisce il feedback visivo (highlight della riga)
        if fp in self.model.checked_paths():
            self.tree.setCurrentIndex(top_left)
            self.tree.selectionModel().select(
                top_left,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
        else:
            self.tree.selectionModel().select(
                top_left,
                QItemSelectionModel.SelectionFlag.Deselect
                | QItemSelectionModel.SelectionFlag.Rows,
            )

    def _delete_selected_items(self):
        """Elimina file/cartelle selezionate (colonna ✓ o selezione visiva)."""
        paths = self.model.checked_paths()
        if not paths:
            selection = self.tree.selectionModel().selectedRows()
            paths = {self.model.filePath(idx) for idx in selection if idx.column() == 1}
        if not paths:
            QMessageBox.information(self, "Nessuna selezione",
                                    "Seleziona almeno un elemento con la colonna ✓.")
            return
        n = len(paths)
        # Protezione: non cancellare MAI la radice del progetto byte-swarmy
        # ne' la radice del progetto attivo (corromperebbe il progetto).
        base_dir = str(BASE_DIR.resolve())
        protected = {base_dir}
        cur = self.main_win.get_current_project_path() if getattr(self, 'main_win', None) else None
        if cur:
            protected.add(str(Path(cur).resolve()))
        to_delete = set()
        for fp in paths:
            rfp = str(Path(fp).resolve())
            if rfp in protected:
                continue
            to_delete.add(fp)
        skipped = n - len(to_delete)
        if skipped:
            QMessageBox.information(
                self, "Protetto",
                f"{skipped} elemento(i) protetto(i) non cancellato(i)\n"
                "(la radice del progetto non puo' essere eliminata).")
        if not to_delete:
            self.model.clear_checks()
            self.tree.selectionModel().clearSelection()
            return
        reply = QMessageBox.question(
            self, "Conferma cancellazione",
            f"Sei sicuro di voler eliminare {len(to_delete)} elemento(i)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for fp in sorted(to_delete, reverse=True):
            _click_log("filemanager", "elimina",
                        self.main_win.get_current_project_path() if self.main_win else "", fp)
            try:
                if os.path.isdir(fp):
                    shutil.rmtree(fp)
                else:
                    os.remove(fp)
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile eliminare {fp}:\n{e}")
        # Refresh dell'albero per riflettere le eliminazioni
        self._refresh_file_tree()
        self.model.clear_checks()
        self.tree.selectionModel().clearSelection()

    # ==================================================================
    # File tree: sort
    # ==================================================================

    def _toggle_sort_order(self):
        """Alterna l'ordinamento: cartelle prima / file prima."""
        self.model._folders_first = not self.model._folders_first
        self.sort_btn.setText("📁📄" if self.model._folders_first else "📄📁")
        self._refresh_file_tree()

    def _on_header_section_clicked(self, logicalIndex: int):
        """Click sull'header di una colonna.

        Se si clicca sulla colonna Name (3): ordina i figli di ogni cartella
        gia' espansa (e della radice) mettendo cartelle prima, poi file,
        in ordine alfabetico.
        """
        if logicalIndex == 3:
            self._sort_by_name()

    def _sort_by_name(self):
        """Ordina i figli di ogni cartella visibile: cartelle prima, poi file, alfabeticamente."""
        root = self.model.invisibleRootItem()
        self._sort_children_recursive(root)

    def _sort_children_recursive(self, parent_item):
        """Riordina i figli di parent_item: is_dir=True prima, poi nome alfabeticamente."""
        rows = parent_item.rowCount()
        if rows <= 1:
            return
        # Raccogli tutte le righe con takeRow (trasferisce la ownership a Python)
        row_items = []
        for _ in range(rows):
            row_items.append(parent_item.takeRow(0))
        # Ordina: colonna 0 ha is_dir in UserRole+1 (True=cartella),
        # colonna 3 ha il nome in UserRole
        row_items.sort(key=lambda row: (
            not row[0].data(Qt.ItemDataRole.UserRole + 1),  # cartelle prima
            str(row[3].data(Qt.ItemDataRole.UserRole) or "").lower(),  # nome alfabetico
        ))
        # Reinserisci in ordine
        for row in row_items:
            parent_item.appendRow(row)
        # Ordina ricorsivamente le sottocartelle che hanno gia' figli caricati
        for row in row_items:
            col0 = row[0]
            if col0.data(Qt.ItemDataRole.UserRole + 1):  # e' una cartella
                first = col0.child(0, 0)
                if col0.rowCount() > 0 and first is not None and first.data(Qt.ItemDataRole.UserRole) is not None:
                    self._sort_children_recursive(col0)

    # ==================================================================
    # File tree: header layout / column widths persistence
    # ==================================================================

    def _column_width_file(self) -> Path:
        """Path del file che memorizza le larghezze colonne del file manager."""
        return BASE_DIR / "state" / "file_manager_columns.json"

    def _apply_header_layout(self):
        """Layout colonne del file manager.

        Va richiamata dopo ogni reset del model: clear() + setColumnCount()
        (dentro set_root_path) ricreano le sezioni dell'header.
        """
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(8)
        # Colonne 0-2: fisse con dimensione minima (triangolo, checkbox, icona)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(0, 100)  # triangolino espansione
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(1, 100)  # checkbox selezione
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(2, 100)  # icona file
        # Colonna 3: si allarga per riempire lo spazio rimanente
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        # Ripristina l'eventuale larghezza salvata della sola colonna Name
        self._load_column_widths()

    def _load_column_widths(self):
        """Ripristina la larghezza salvata SOLO per la colonna Name (3)."""
        f = self._column_width_file()
        if not f.exists():
            return
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            widths = data.get("widths", {})
            key = "3"
            if key in widths:
                self.tree.header().resizeSection(3, int(widths[key]))
        except Exception as e:
            print(f"Errore caricamento larghezze colonne: {e}")

    def _save_column_widths(self, logicalIndex: int, oldSize: int, newSize: int):
        """Salva le larghezze colonne ogni volta che l'utente le sposta."""
        try:
            f = self._column_width_file()
            f.parent.mkdir(parents=True, exist_ok=True)
            widths = {}
            if f.exists():
                try:
                    widths = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    widths = {}
            widths.setdefault("widths", {})
            # Salva solo la colonna Name (3): le altre sono a larghezza fissa
            widths["widths"] = {"3": self.tree.header().sectionSize(3)}
            f.write_text(json.dumps(widths, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Errore salvataggio larghezze colonne: {e}")

    # ==================================================================
    # File tree: add file / add folder
    # ==================================================================

    def _add_text_file(self):
        """Crea un nuovo file di testo nella cartella corrente del progetto."""
        from PyQt6.QtWidgets import QInputDialog

        # Determina cartella di destinazione dalla selezione corrente
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
            target_dir = (
                self.model._root_path
                if hasattr(self.model, '_root_path') and self.model._root_path
                else str(BASE_DIR.resolve())
            )
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = str(BASE_DIR.resolve())

        # Chiedi nome file
        name, ok = QInputDialog.getText(
            self, "Nuovo file di testo",
            "Nome del file (es. note.txt):",
            text="nuovo_file.txt",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if not any(name.endswith(ext) for ext in (".txt", ".md", ".py", ".sh",
                                                   ".log", ".json", ".csv")):
            name += ".txt"

        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            base, ext = os.path.splitext(name)
            i = 1
            while os.path.exists(os.path.join(target_dir, f"{base} ({i}){ext}")):
                i += 1
            suggested = f"{base} ({i}){ext}"
            msg = f"Il file '{name}' esiste gia'.\nVuoi usare '{suggested}'?"
            ans = QMessageBox.question(
                self, "Esiste gia'", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            name = suggested
            new_path = os.path.join(target_dir, name)

        try:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write("")
            _click_log("filemanager", "crea file",
                        self.main_win.get_current_project_path() if self.main_win else "",
                        new_path)
            # Refresh del file tree per far apparire il nuovo file
            self._refresh_file_tree()
            # Apri il nuovo file nell'editor
            if self.main_win and hasattr(self.main_win, "_show_file_editor"):
                self.main_win._show_file_editor(new_path)
        except Exception as e:
            QMessageBox.warning(self, "Errore",
                                "Impossibile creare il file:\n" + str(e))

    def _add_folder(self):
        """Crea una nuova cartella nella cartella corrente del progetto."""
        from PyQt6.QtWidgets import QInputDialog

        # Determina cartella di destinazione (come per _add_text_file)
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
            target_dir = (
                self.model._root_path
                if hasattr(self.model, '_root_path') and self.model._root_path
                else str(BASE_DIR.resolve())
            )
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = str(BASE_DIR.resolve())

        # Chiedi nome cartella
        name, ok = QInputDialog.getText(
            self, "Nuova cartella",
            "Nome della cartella (es. sourceCode):",
            text="nuova_cartella",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        # Sanitizza: niente caratteri proibiti per nome cartella
        name = name.replace("/", os.sep).replace("\\", os.sep)
        name = os.path.basename(name)  # evita path traversal
        if not name or name in (".", ".."):
            QMessageBox.warning(self, "Nome non valido",
                                "Inserisci un nome di cartella valido.")
            return

        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            base = name
            i = 1
            while os.path.exists(os.path.join(target_dir, f"{base} ({i})")):
                i += 1
            suggested = f"{base} ({i})"
            msg2 = f"La cartella '{name}' esiste gia'.\nVuoi usare '{suggested}'?"
            ans = QMessageBox.question(
                self, "Esiste gia'", msg2,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            name = suggested
            new_path = os.path.join(target_dir, name)

        try:
            os.makedirs(new_path, exist_ok=True)
            _click_log("filemanager", "crea cartella",
                        self.main_win.get_current_project_path() if self.main_win else "",
                        new_path)
            # Refresh del file tree per far apparire la nuova cartella
            self._refresh_file_tree()
        except Exception as e:
            QMessageBox.warning(self, "Errore",
                                "Impossibile creare la cartella:\n" + str(e))

    # ==================================================================
    # Animazione toggle sidebar
    # ==================================================================

    def toggle(self):
        """Toggle visibilita' sidebar con animazione."""
        self._open = not self._open
        target = 0 if self._open else 280
        self._anim.setStartValue(280 if self._open else 0)
        self._anim.setEndValue(target)
        self._anim.start()

    # ==================================================================
    # Orchestrator control wrappers (delegano al ControlCenter genitore)
    # ==================================================================

    def _pause_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_pause_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._pause_orchestrator()

    def _resume_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_resume_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._resume_orchestrator()

    def _stop_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_stop_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._stop_orchestrator()

    # ==================================================================
    # Task list: item clicked / changed / double-click / context menu
    # ==================================================================

    def _on_task_item_clicked(self, item: QListWidgetItem):
        """Shift+click: copia info debug negli appunti. Click normale: noop."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt as _Qt
        if QApplication.keyboardModifiers() & _Qt.KeyboardModifier.ShiftModifier:
            tid = item.data(Qt.ItemDataRole.UserRole) if item else ""
            info = self._debug_call_info("task_list itemClicked", tid)
            QApplication.clipboard().setText(info)
            if self._GUI_DEBUG:
                print(f"[DEBUG] Shift+click copiato negli appunti: {info}")
            return
        # Checkbox: toggle gestito nativamente da QListWidgetItem.
        # Il log viene scritto da _on_task_item_changed su itemChanged.
        if item is None:
            return

    def _on_task_item_changed(self, item: QListWidgetItem):
        """Sincronizza selezione visiva QListWidget con stato checkbox."""
        if not item:
            return
        if getattr(self, "_refreshing_tasks", False):
            return
        checked = item.checkState() == Qt.CheckState.Checked
        mark = "✓" if checked else "✗"
        stato = "selezionato" if checked else "deselezionato"
        tid = item.data(Qt.ItemDataRole.UserRole)
        if self._GUI_DEBUG:
            print(f"[DEBUG] Lavori e compiti (colonna ✓): {mark} {stato} elemento='{tid} - {item.text()}'")
        _click_log("task", stato,
                    self.main_win.get_current_project_path() if self.main_win else "",
                    f"{tid} - {item.text()}")
        if checked:
            item.setSelected(True)
        else:
            item.setSelected(False)

    def _delete_checked_tasks(self):
        """Elimina i task selezionati con checkbox dalla lista Lavori e compiti."""
        checked_ids = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                tid = item.data(Qt.ItemDataRole.UserRole)
                if tid:
                    checked_ids.append(tid)
        if not checked_ids:
            QMessageBox.information(self, "Nessuna selezione",
                                    "Seleziona almeno un task con la colonna ✓.")
            return
        n = len(checked_ids)
        reply = QMessageBox.question(
            self, "Conferma cancellazione",
            f"Sei sicuro di voler eliminare {n} task selezionato(i)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        project_path = (
            self.main_win.get_current_project_path()
            if hasattr(self, 'main_win') and self.main_win else None
        )
        for tid in checked_ids:
            # Recupera il titolo del task per il log
            titolo = ""
            for i in range(self.task_list.count()):
                it = self.task_list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == tid:
                    titolo = it.text()
                    break
            _click_log("task", "elimina",
                        self.main_win.get_current_project_path() if self.main_win else "",
                        f"{tid} - {titolo}")
            try:
                delete_task(tid, project_path)
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile eliminare task {tid}:\n{e}")
        # Ricarica lista
        self._force_refresh_tasks()

    def _on_task_double_clicked(self, task_id):
        """Doppio click su task nella sidebar -> riavvia.

        Firma compatibile con TaskListWidget.on_task_activated (str).
        """
        try:
            # Recupera l'item corrispondente per aggiornare testo/colore
            item = None
            for i in range(self.task_list.count()):
                it = self.task_list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == task_id:
                    item = it
                    break
            if task_id:
                _log_user_action("Task-Action", "avvio", task_id=task_id,
                                 details="Doppio click - riavvio veloce")
            if not task_id:
                return
            ok, msg = _restart_task(task_id)
            if ok:
                if item is not None:
                    txt = item.text()
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"↻ {txt} [restart]")
                    item.setForeground(QColor("#16a34a"))
                # Refresh via ControlCenter
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore double-click task: {e}")

    # ==================================================================
    # Clean queue + force refresh tasks
    # ==================================================================

    def _clean_queue(self):
        """Rimette in pending tutti i task bloccati (failed, stuck, failed_definitively)."""
        db_path = BASE_DIR / 'tasks' / 'queue.db'
        try:
            if not db_path.exists():
                if self.main_win and hasattr(self.main_win, "statusBar"):
                    self.main_win.statusBar().showMessage(
                        "🧹 Database coda non trovato", 4000)
                return
            con = sqlite3.connect(str(db_path), timeout=10.0)
            cur = con.cursor()
            before = con.execute(
                "SELECT COUNT(*) FROM tasks WHERE status IN ('failed', 'stuck', 'failed_definitively')"
            ).fetchone()[0]
            cur.execute(
                "UPDATE tasks SET status='pending', attempts=0, last_error=NULL, "
                "failure_reason=NULL, started_at=NULL, completed_at=NULL "
                "WHERE status IN ('failed', 'stuck', 'failed_definitively')"
            )
            con.commit()
            after = con.execute(
                "SELECT COUNT(*) FROM tasks WHERE status IN ('failed', 'stuck', 'failed_definitively')"
            ).fetchone()[0]
            con.close()
            n_reset = before - after
            if n_reset > 0:
                if self.main_win and hasattr(self.main_win, "statusBar"):
                    self.main_win.statusBar().showMessage(
                        f"🧹 Coda pulita: {n_reset} task rimesso/i in pending", 5000)
                _log_user_action("Task-Action", "pulisci_coda",
                                 details=f"{n_reset} task reset a pending")
                # Refresh lista
                self._force_refresh_tasks()
                # Refresh scheduler coda
                try:
                    scheduler = (
                        self.main_win.center.panel_pages.get("coda")
                        if self.main_win and hasattr(self.main_win, "center") else None
                    )
                    if scheduler is not None and hasattr(scheduler, "refresh"):
                        scheduler.refresh()
                except Exception:
                    pass
            else:
                if self.main_win and hasattr(self.main_win, "statusBar"):
                    self.main_win.statusBar().showMessage(
                        "🧹 Nessun task bloccato da pulire", 4000)
        except Exception as e:
            if self.main_win and hasattr(self.main_win, "statusBar"):
                self.main_win.statusBar().showMessage(
                    f"❌ Errore pulizia coda: {e}", 5000)
            print(f"Errore pulizia coda: {e}")

    def _force_refresh_tasks(self, *args):
        """Forza il refresh della lista task dal progetto attivo.

        Firma variadica per compatibilita' con TaskListWidget.on_refresh_requested
        (chiama senza argomenti).

        Le righe usano TaskItemRow via setItemWidget: checkbox allineata col
        pulsante ☑ e pallino di stato colorato
        (verde=fatto, giallo=in lavorazione, rosso=in attesa).
        """
        try:
            self._refreshing_tasks = True
            if self._GUI_DEBUG:
                print("[DEBUG] Sidebar-Refresh: refresh (aggiorna lista task)")
            _log_user_action("Sidebar-Refresh", "refresh",
                             details="Refresh manuale lista task")
            if hasattr(self, 'task_list'):
                self.task_list.clear()
                try:
                    project_path = (
                        self.main_win.get_current_project_path()
                        if hasattr(self, 'main_win') and self.main_win else None
                    )
                    tasks = load_tasks(project_path)
                    for t in tasks:
                        self._append_task_row(t)
                except Exception as e:
                    print(f"Errore refresh task: {e}")
            # Refresh card coda nel ControlCenter
            parent = self.parent()
            while parent and not hasattr(parent, '_refresh_coda_card'):
                parent = parent.parent()
            if parent:
                parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore force refresh: {e}")
        finally:
            self._refreshing_tasks = False

    # ==================================================================
    # Righe task: creazione e helper (TaskItemRow + setItemWidget)
    # ==================================================================

    def _append_task_row(self, t: dict):
        """Aggiunge una riga task: item (checkbox + dati) + TaskItemRow visuale.

        Il titolo "vero" viene conservato in UserRole+1 (il testo dell'item
        resta vuoto: la riga visiva lo copre interamente).
        """
        task_id = str(t.get("id", ""))
        base_title = str(t.get("title", t.get("description", "?")))[:80]
        st = str(t.get("status", "?"))
        icon, color = TASK_STATUS_STYLE.get(st, ("○", "#dc2626"))

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, task_id)
        item.setData(Qt.ItemDataRole.UserRole + 1, base_title)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setToolTip(f"{base_title}\nStato: {st}")
        item.setSizeHint(_QSize(0, 26))
        self.task_list.addItem(item)

        row = TaskItemRow(icon, color, base_title)
        row.setToolTip(item.toolTip())
        self.task_list.setItemWidget(item, row)
        # Checkbox della riga -> stato dell'item (log in _on_task_item_changed)
        row.check.toggled.connect(
            lambda checked, it=item: self._on_row_check_toggled(it, checked))
        # Click singolo (shift+click debug) e doppio click (riavvio veloce)
        row.clicked.connect(lambda it=item: self._on_task_item_clicked(it))
        row.double_clicked.connect(
            lambda it=item: self._on_task_double_clicked(
                str(it.data(Qt.ItemDataRole.UserRole))))
        # Menu contestuale: stessa firma di TaskListWidget.on_context_menu
        row.context_requested.connect(
            lambda gpos, it=item: self._on_task_context_menu(
                self.task_list.mapFromGlobal(gpos)))

    def _task_row(self, item):
        """Widget TaskItemRow associato a item (o None)."""
        w = self.task_list.itemWidget(item)
        return w if isinstance(w, TaskItemRow) else None

    def _task_base_title(self, item) -> str:
        """Titolo base del task (senza icone/prefissi di stato)."""
        t = item.data(Qt.ItemDataRole.UserRole + 1)
        if not t:
            t = item.text()
        return str(t)

    def _update_task_display(self, item, icon: str, color: str, title: str):
        """Aggiorna la riga visiva (pallino + titolo) e il titolo base."""
        item.setData(Qt.ItemDataRole.UserRole + 1, title)
        row = self._task_row(item)
        if row is not None:
            row.set_display(icon, color, title)
        else:
            item.setText(f"{icon} {title}")

    def _on_row_check_toggled(self, item, checked: bool):
        """Sync checkbox della riga -> stato dell'item (log via itemChanged)."""
        stato = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        if item.checkState() != stato:
            item.setCheckState(stato)

    # ==================================================================
    # Task list: status + pause/resume/stop/restart/delete
    # ==================================================================

    def _get_task_status(self, task_id):
        """Ritorna lo status corrente di un task."""
        try:
            db_path = BASE_DIR / 'tasks' / 'queue.db'
            if not db_path.exists():
                return None
            con = sqlite3.connect(str(db_path), timeout=5.0)
            cur = con.cursor()
            cur.execute("SELECT status FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def _pause_task_with_refresh(self, task_id, item):
        """Mette in pausa un singolo task."""
        try:
            _log_user_action("Task-Action", "pausa", task_id=task_id,
                             details="Task messo in pausa dall'utente")
            ok, msg = _pause_task(task_id)
            if ok and item:
                txt = item.text() if hasattr(item, 'text') else ""
                for prefix in ["⏸ ", "▶ ", "🛑 ", "↻ "]:
                    if txt.startswith(prefix):
                        txt = txt[len(prefix):]
                if " [paused]" in txt: txt = txt.replace(" [paused]", "")
                if " [restart]" in txt: txt = txt.replace(" [restart]", "")
                if " [stopped]" in txt: txt = txt.replace(" [stopped]", "")
                item.setText(f"⏸ {txt} [paused]")
                item.setForeground(QColor("#6b7280"))
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore pause task: {e}")

    def _resume_task_with_refresh(self, task_id, item):
        """Riprende un singolo task dalla pausa."""
        try:
            _log_user_action("Task-Action", "avvio", task_id=task_id,
                             details="Task riavviato dall'utente")
            ok, msg = _resume_single_task(task_id)
            if ok and item:
                txt = item.text() if hasattr(item, 'text') else ""
                for prefix in ["⏸ ", "▶ ", "🛑 ", "↻ "]:
                    if txt.startswith(prefix):
                        txt = txt[len(prefix):]
                if " [paused]" in txt: txt = txt.replace(" [paused]", "")
                if " [restart]" in txt: txt = txt.replace(" [restart]", "")
                if " [stopped]" in txt: txt = txt.replace(" [stopped]", "")
                item.setText(f"▶ {txt}")
                item.setForeground(QColor("#f59e0b"))
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore resume task: {e}")

    def _on_task_context_menu(self, pos):
        """Menu contestuale tasto destro su un task."""
        try:
            item = self.task_list.itemAt(pos)
            if not item:
                return
            task_id = item.data(Qt.ItemDataRole.UserRole)
            if not task_id:
                return

            menu = QMenu(self)

            act_details = QAction("📋 Dettagli task", self)
            act_details.triggered.connect(lambda: self._show_task_details(task_id))
            menu.addAction(act_details)

            menu.addSeparator()

            act_restart = QAction("🔄 Riavvia task", self)
            act_restart.triggered.connect(
                lambda: self._restart_task_with_refresh(task_id, item))
            menu.addAction(act_restart)

            # Pausa/Riprendi task (singolo)
            cur_status = self._get_task_status(task_id)
            if cur_status == 'paused':
                act_resume = QAction("▶ Riprendi task", self)
                act_resume.triggered.connect(
                    lambda: self._resume_task_with_refresh(task_id, item))
                menu.addAction(act_resume)
            elif cur_status in ('pending', 'running'):
                act_pause = QAction("⏸ Pausa task", self)
                act_pause.triggered.connect(
                    lambda: self._pause_task_with_refresh(task_id, item))
                menu.addAction(act_pause)

            # Ferma task definitivamente
            act_stop = QAction("🛑 Ferma task", self)
            act_stop.triggered.connect(
                lambda: self._stop_task_with_refresh(task_id, item))
            menu.addAction(act_stop)

            act_copy = QAction("📋 Copia ID task", self)
            act_copy.triggered.connect(lambda: self._copy_task_id(task_id))
            menu.addAction(act_copy)

            menu.addSeparator()

            act_delete = QAction("🗑 Elimina task", self)
            act_delete.triggered.connect(
                lambda: self._delete_task_with_refresh(task_id, item))
            menu.addAction(act_delete)

            menu.addSeparator()

            act_open = QAction("📂 Apri risultato", self)
            act_open.triggered.connect(lambda: self._open_task_result(task_id))
            menu.addAction(act_open)

            menu.exec(self.task_list.mapToGlobal(pos))
        except Exception as e:
            print(f"Errore context menu: {e}")

    def _stop_task_with_refresh(self, task_id, item):
        """Ferma un singolo task e aggiorna la lista."""
        try:
            _log_user_action("Task-Action", "stop", task_id=task_id,
                             details="Task fermato dall'utente")
            reply = QMessageBox.question(
                self, "Ferma task",
                f"Fermare il task {task_id[:12]}?\n\n"
                f"L'orchestratore continuera' a girare, ma questo task verra' marcato come fallito.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ok, msg = _stop_task(task_id)
            try:
                if hasattr(self, "main_win") and self.main_win:
                    self.main_win.statusBar().showMessage(f"🛑 {msg}", 4000)
            except Exception:
                pass
            if ok:
                if item:
                    txt = item.text() if hasattr(item, 'text') else ""
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"🛑 {txt} [stopped]")
                    item.setForeground(QColor("#dc2626"))
                # Refresh via ControlCenter
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore stop task: {e}")

    @staticmethod
    def _collect_task_files(task: dict, base_dir: str) -> list:
        """File di progetto prodotti da un task.

        1) via git: il worker committa con messaggio 'task <id>: ...' ->
           file toccati da quei commit;
        2) fallback: file in project/ modificati nell'intervallo di vita
           del task (started_at..completed_at, ±120s di margine).
        Ritorna path RELATIVI a project/, ordinati.
        """
        proj = Path(base_dir) / "project"
        if not proj.exists():
            return []
        files: list = []

        tid = str(task.get("id") or "")
        if tid:
            try:
                out = subprocess.run(
                    ["git", "-C", str(base_dir), "log", "--all",
                     "--format=", "--name-only", "--grep", f"task {tid}"],
                    capture_output=True, text=True, timeout=5,
                )
                seen = set()
                for line in out.stdout.splitlines():
                    rel = line.strip()
                    if (rel and ".." not in rel
                            and not _is_junk_project_path(rel)
                            and (proj / rel).exists()
                            and rel not in seen):
                        seen.add(rel)
                        files.append(rel)
            except Exception:
                pass

        if not files:
            try:
                start = float(task.get("started_at") or 0)
                end = float(task.get("completed_at") or 0) or time.time()
                if start > 0:
                    margin = 120
                    count = 0
                    for pth in proj.rglob("*"):
                        if not pth.is_file():
                            continue
                        rel = str(pth.relative_to(proj))
                        if _is_junk_project_path(rel):
                            continue
                        try:
                            if start - margin <= pth.stat().st_mtime <= end + margin:
                                files.append(rel)
                        except OSError:
                            pass
                        count += 1
                        if count > 2000:
                            break
            except Exception:
                pass
        # Ordine: prima i file "di ingresso" (main, avvio, requirements)
        prio = {"main.py": 0, "app.py": 1, "avvia.sh": 2, "requirements.txt": 3}
        return sorted(set(files),
                      key=lambda f: (prio.get(Path(f).name, 10), f))

    def _show_task_details(self, task_id):
        """Mostra un dialog con i dettagli completi del task."""
        try:
            from PyQt6.QtWidgets import (
                QDialog, QFormLayout, QTextEdit, QPlainTextEdit,
            )

            db_path = BASE_DIR / 'tasks' / 'queue.db'
            if not db_path.exists():
                QMessageBox.warning(self, "Database",
                                    "Database coda non trovato.")
                return
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            con.close()

            if not row:
                return

            task = dict(zip(cols, row))

            dlg = QDialog(self)
            dlg.setWindowTitle(f"📋 Dettagli task {task_id[:12]}")
            dlg.resize(600, 500)
            lay = QVBoxLayout(dlg)

            title = QLabel(f"<b>{task.get('title', '(senza titolo)')[:80]}</b>")
            title.setStyleSheet("font-size:14px; padding:8px; border-radius:6px;")
            title.setWordWrap(True)
            lay.addWidget(title)

            form = QFormLayout()
            form.setSpacing(6)

            def fmt_time(ts):
                if not ts:
                    return "—"
                try:
                    return time.strftime('%Y-%m-%d %H:%M:%S',
                                          time.localtime(float(ts)))
                except Exception:
                    return str(ts)

            st_map = {
                'done': ('Completato', 'green'),
                'running': ('In esecuzione', 'orange'),
                'failed': ('Fallito', 'red'),
                'pending': ('In attesa', 'gray'),
                'planned': ('Pianificato', 'gray'),
                'retry': ('Nuovo tentativo', 'orange'),
                'stuck': ('Bloccato', 'red'),
                'paused': ('In pausa', 'gray'),
                'thermal_paused': ('Pausa termica', 'orange'),
            }
            st_label, st_color = st_map.get(
                task.get('status'),
                (task.get('status', '—'), 'gray'),
            )
            form.addRow("ID:", QLabel(task.get('id', '—')))
            form.addRow("Stato:", QLabel(f"<b style='color:{st_color}'>{st_label}</b>"))
            form.addRow("Tipo:", QLabel(task.get('type', '—')))
            form.addRow("Origine:", QLabel(task.get('source', '—')))
            form.addRow("Tentativi:", QLabel(str(task.get('attempts', 0))))
            form.addRow("Genitore:", QLabel(task.get('parent') or '—'))
            form.addRow("Creato il:", QLabel(fmt_time(task.get('created_at'))))
            form.addRow("Avviato il:", QLabel(fmt_time(task.get('started_at'))))
            form.addRow("Completato il:", QLabel(fmt_time(task.get('completed_at'))))

            if task.get('reason'):
                form.addRow("Motivo:", QLabel(str(task.get('reason'))))

            lay.addLayout(form)

            for label, field in [("Descrizione", 'description'),
                                  ("Risultato", 'result'),
                                  ("Ultimo errore", 'last_error')]:
                val = task.get(field, '')
                if val:
                    color_style = ' style="color:red"' if 'error' in field.lower() else ''
                    lay.addWidget(QLabel(f"<b{color_style}>{label}:</b>"))
                    te = QTextEdit()
                    te.setReadOnly(True)
                    te.setPlainText(str(val)[:2000])
                    if 'error' in field.lower():
                        te.setStyleSheet(
                            "border:1px solid rgba(128,128,128,0.35); border-radius:4px;")
                    te.setMaximumHeight(100)
                    lay.addWidget(te)

            # Codice prodotto dal task (navigabile se multi-file)
            try:
                task_files = self._collect_task_files(task, str(BASE_DIR))
            except Exception as _e:
                print(f"raccolta file task: {_e}")
                task_files = []
            if task_files:
                lay.addWidget(QLabel("<b>📄 Codice prodotto:</b>"))
                from PyQt6.QtWidgets import QSplitter

                code_split = QSplitter(Qt.Orientation.Horizontal)
                file_list = QListWidget()
                file_list.addItems(task_files)
                file_list.setMaximumWidth(260)
                viewer = QPlainTextEdit()
                viewer.setReadOnly(True)
                viewer.setStyleSheet(
                    "font-family:'JetBrains Mono','Consolas',monospace; "
                    "font-size:11px;")
                code_split.addWidget(file_list)
                code_split.addWidget(viewer)
                code_split.setStretchFactor(0, 0)
                code_split.setStretchFactor(1, 1)
                lay.addWidget(code_split, stretch=1)

                def _load_file(item):
                    rel = item.text()
                    try:
                        full = Path(BASE_DIR) / "project" / rel
                        content = full.read_text(encoding="utf-8",
                                                 errors="replace")
                        if len(content) > 30000:
                            content = (content[:30000]
                                       + "\n...[troncato — apri il file "
                                         "dall'Archivio per tutto]...")
                        viewer.setPlainText(content)
                    except Exception as e:
                        viewer.setPlainText(f"ERRORE lettura {rel}: {e}")

                file_list.currentItemChanged.connect(_load_file)
                file_list.setCurrentRow(0)

                # Flusso utente 3: ESEGUIRE il codice generato
                run_row = QHBoxLayout()
                run_btn = QPushButton("▶ Esegui")
                run_hint = QLabel("")
                run_hint.setStyleSheet("font-size:10px;")
                run_row.addWidget(run_btn)
                run_row.addWidget(run_hint, stretch=1)
                lay.addLayout(run_row)

                proc_holder = []

                def _refresh_run_btn(item):
                    rel = item.text() if item else ""
                    full = Path(BASE_DIR) / "project" / rel
                    ext = full.suffix.lower()
                    if ext == ".html":
                        run_btn.setEnabled(True)
                        run_btn.setText("🌐 Apri nel browser")
                        run_hint.setText("configurazione web")
                        return
                    cmd = build_run_command(full)
                    run_btn.setEnabled(cmd is not None)
                    run_btn.setText(f"▶ Esegui {rel}" if cmd else "▶ Esegui")
                    run_hint.setText("" if cmd
                                     else "estensione non eseguibile direttamente")

                def _start_run():
                    item = file_list.currentItem()
                    if not item or proc_holder:
                        return
                    rel = item.text()
                    full = Path(BASE_DIR) / "project" / rel
                    if full.suffix.lower() == ".html":
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(full)))
                        return
                    cmd = build_run_command(full)
                    if not cmd:
                        return
                    viewer.appendPlainText(f"$ {' '.join(cmd)}")
                    proc = QProcess(dlg)
                    proc.setWorkingDirectory(str(full.parent))
                    proc.readyReadStandardOutput.connect(
                        lambda: viewer.appendPlainText(bytes(
                            proc.readAllStandardOutput()).decode(
                            "utf-8", errors="replace").rstrip()))
                    proc.readyReadStandardError.connect(
                        lambda: viewer.appendPlainText(bytes(
                            proc.readAllStandardError()).decode(
                            "utf-8", errors="replace").rstrip()))
                    proc.finished.connect(
                        lambda code, _st: (viewer.appendPlainText(
                            f"[uscita: {code}]"), _rearm()))
                    proc.start(cmd[0], cmd[1:])
                    proc_holder.append(proc)
                    run_btn.setEnabled(False)

                def _rearm(*_a):
                    if proc_holder:
                        proc_holder.clear()
                        _refresh_run_btn(file_list.currentItem())

                run_btn.clicked.connect(_start_run)
                file_list.currentItemChanged.connect(_refresh_run_btn)
                _refresh_run_btn(file_list.currentItem())

                if len(task_files) > 1:
                    dlg.resize(980, 680)
            elif task.get("status") == "done":
                lay.addWidget(QLabel("<span style='color:gray'>"
                                     "Nessun file di progetto associato.</span>"))

            # Ragionamento / Log del task (per debug e stima tempo)
            try:
                log_path = BASE_DIR / "logs" / "byte-swarmy.log"
                related_ids = [task_id]
                # Includi anche i sotto-task
                try:
                    con2 = sqlite3.connect(str(db_path))
                    subs = con2.execute(
                        "SELECT id FROM tasks WHERE parent=?", (task_id,)
                    ).fetchall()
                    con2.close()
                    related_ids += [s[0] for s in subs]
                except Exception:
                    pass
                lines_out = []
                if log_path.exists():
                    try:
                        size = log_path.stat().st_size
                        read_size = min(size, 200_000)
                        with open(log_path, "rb") as f:
                            if size > read_size:
                                f.seek(size - read_size)
                            chunk = f.read().decode("utf-8", errors="replace")
                        for ln in chunk.splitlines():
                            if any(rid in ln for rid in related_ids):
                                lines_out.append(ln)
                    except Exception:
                        pass
                if len(lines_out) > 40:
                    lines_out = lines_out[-40:]
                lay.addWidget(QLabel("<b>🧠 Ragionamento / Log (debug):</b>"))
                log_te = QTextEdit()
                log_te.setReadOnly(True)
                log_te.setStyleSheet(
                    "font-family:'JetBrains Mono','Consolas',monospace; "
                    "font-size:10px;")
                log_te.setPlainText(
                    "\n".join(lines_out) if lines_out
                    else "(nessun log trovato per questo task)"
                )
                log_te.setMaximumHeight(160)
                lay.addWidget(log_te)
            except Exception as e:
                print(f"log ragionamento: {e}")

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            close_btn = QPushButton("Chiudi")
            close_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(close_btn)
            lay.addLayout(btn_row)

            dlg.exec()
        except Exception as e:
            print(f"Errore show details: {e}")

    def _restart_task_with_refresh(self, task_id, item):
        """Riavvia un task e aggiorna la lista."""
        try:
            _log_user_action("Task-Action", "avvio", task_id=task_id,
                             details="Task riavviato dall'utente")
            ok, msg = _restart_task(task_id)
            try:
                if hasattr(self, "main_win") and self.main_win:
                    self.main_win.statusBar().showMessage(f"🔄 {msg}", 4000)
            except Exception:
                pass
            if ok:
                if item:
                    txt = item.text() if hasattr(item, 'text') else ""
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"↻ {txt} [restart]")
                    item.setForeground(QColor("#16a34a"))
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore restart: {e}")

    def _delete_task_with_refresh(self, task_id, item):
        """Elimina un task dal DB."""
        try:
            reply = QMessageBox.question(
                self, "Elimina task",
                f"Eliminare definitivamente il task {task_id[:12]}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            db_path = BASE_DIR / 'tasks' / 'queue.db'
            if not db_path.exists():
                return
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            con.commit()
            con.close()
            parent = self.parent()
            while parent and not hasattr(parent, '_refresh_coda_card'):
                parent = parent.parent()
            if parent:
                parent._refresh_coda_card()
                if hasattr(parent, '_refresh_task_list'):
                    parent._refresh_task_list()
        except Exception as e:
            print(f"Errore delete: {e}")

    def _copy_task_id(self, task_id):
        """Copia l'ID del task negli appunti."""
        try:
            cb = QApplication.clipboard()
            cb.setText(task_id)
        except Exception as e:
            print(f"Errore copy: {e}")

    def _open_task_result(self, task_id):
        """Apre la CARTELLA dei file prodotti dal task nel file manager.

        Flusso utente 3: l'utente deve vedere dove sta il codice generato
        (e lanciare avvia.sh), non un singolo file indovinato.
        """
        try:
            db_path = BASE_DIR / 'tasks' / 'queue.db'
            if not db_path.exists():
                return
            con = sqlite3.connect(str(db_path))
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            con.close()
            if not row:
                return

            proj = str(BASE_DIR / 'project')
            files = self._collect_task_files(dict(row), str(BASE_DIR))
            if files:
                first_dir = os.path.dirname(os.path.join(proj, files[0]))
            else:
                first_dir = proj
            os.makedirs(first_dir, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(first_dir))
        except Exception as e:
            print(f"Errore open result: {e}")


__all__ = ["FileTreeDrawer"]
