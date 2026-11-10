"""
GUI/task_list_widget.py — TaskListWidget e pulsanti correlati.

Estratto da GUI/file_tree_drawer.py per ridurre il monolite.

Fornisce:
- TaskListWidget(QFrame): lista task + header + pulsanti (☑/🔄/➕/🗑️/🧹)
- Gestisce UI task list in modo autonomo.

Nota: i callback sono chiamati direttamente dal widget, non tramite segnali
pyqtSignal. Questo evita problemi di None e mantiene la coerenza con il
pattern usato in altri moduli estratti.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt as _Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtGui import QColor


class TaskListWidget(QFrame):
    """Widget autonomo che contiene:
    - Header "📋 Lavori e Compiti"
    - Pulsanti: seleziona tutto / aggiorna / aggiungi / elimina scelti / svuota coda
    - QListWidget con i task (checkbox user checkable)

    I callback sono chiamati direttamente dal widget quando l'utente interagisce.
    Il genitore (FileTreeDrawer) può sovrascrivere il comportamento passando
    i callback al costruttore, oppure i metodi interni del widget sono sufficienti.
    """

    def __init__(
        self,
        *,
        on_select_all_toggled: Optional[Callable] = None,
        on_refresh_requested: Optional[Callable] = None,
        on_add_requested: Optional[Callable] = None,
        on_delete_checked_requested: Optional[Callable] = None,
        on_clean_queue_requested: Optional[Callable] = None,
        on_task_activated: Optional[Callable[[str], None]] = None,
        on_context_menu: Optional[Callable[[_Qt.QPoint], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        layout = self.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Header + Titolo ──
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)
        self.title_lbl = QLabel("📋 Lavori e Compiti")
        self.title_lbl.setToolTip("Lavori e compiti — lista dei task del progetto attivo")
        self.title_lbl.setStyleSheet("font-size:11px; font-weight:bold; padding:0; margin:0;")
        header.addWidget(self.title_lbl, stretch=0)
        layout.addLayout(header)

        # ── Pulsanti ──
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(4)

        # ☑ Toggle select all
        self.btn_select_all = QPushButton("☑")
        self.btn_select_all.setFixedSize(20, 20)
        self.btn_select_all.setToolTip("Seleziona/deseleziona tutti i task")
        self.btn_select_all.setStyleSheet("QPushButton { border: none; } QPushButton::hover { background: transparent; }")
        self.btn_select_all.clicked.connect(self._on_select_all_clicked)
        btn_row.addWidget(self.btn_select_all)

        # 🔄 Refresh
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setToolTip("Aggiorna lista task")
        self.btn_refresh.setStyleSheet("QPushButton { border: none; } QPushButton::hover { background: transparent; }")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        btn_row.addWidget(self.btn_refresh)

        # ➕ Aggiungi
        self.btn_add = QPushButton("➕")
        self.btn_add.setFixedSize(28, 28)
        self.btn_add.setToolTip("Aggiungi un nuovo task")
        self.btn_add.setStyleSheet("QPushButton { border: none; } QPushButton::hover { background: transparent; }")
        self.btn_add.clicked.connect(self._on_add_clicked)
        btn_row.addWidget(self.btn_add)

        # 🗑 Elimina selezionati
        self.btn_delete = QPushButton("🗑️")
        self.btn_delete.setFixedSize(28, 28)
        self.btn_delete.setToolTip("Elimina task selezionati con la colonna ✓")
        self.btn_delete.setStyleSheet("QPushButton { border: none; } QPushButton::hover { background: transparent; }")
        self.btn_delete.clicked.connect(self._on_delete_checked_clicked)
        btn_row.addWidget(self.btn_delete)

        # 🧹 Svuota coda
        self.btn_clean = QPushButton("🧹 Svuota coda")
        self.btn_clean.setFixedHeight(28)
        self.btn_clean.setStyleSheet(
            "QPushButton { background:#9ca3af; color:white; border:none; "
            "border-radius:4px; padding:2px 8px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#788087; }"
        )
        self.btn_clean.clicked.connect(self._on_clean_clicked)
        btn_row.addWidget(self.btn_clean)

        btn_row.addStretch()  # spinge i pulsanti a sinistra
        layout.addLayout(btn_row)

        # ── Lista task ──
        self.task_list = QListWidget()
        self.task_list.setObjectName("task_list")
        self.task_list.setContextMenuPolicy(_Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.task_list.itemClicked.connect(self._on_item_clicked)
        self.task_list.customContextMenuRequested.connect(self._on_custom_context_menu)
        self.task_list.itemChanged.connect(self._on_item_changed)

        # Memorizza i callback per richiamarli negli handler
        self._on_select_all_toggled = on_select_all_toggled
        self._on_refresh_requested = on_refresh_requested
        self._on_add_requested = on_add_requested
        self._on_delete_checked_requested = on_delete_checked_requested
        self._on_clean_queue_requested = on_clean_queue_requested
        self._on_task_activated = on_task_activated
        self._on_context_menu = on_context_menu

    # ── Handler pulsanti (chiamano i callback opzionali) ──

    def _on_select_all_clicked(self):
        self._toggle_select_all()
        if self._on_select_all_toggled:
            self._on_select_all_toggled(self._is_select_all_checked())

    def _on_refresh_clicked(self):
        if self._on_refresh_requested:
            self._on_refresh_requested()

    def _on_add_clicked(self):
        if self._on_add_requested:
            self._on_add_requested()

    def _on_delete_checked_clicked(self):
        if self._on_delete_checked_requested:
            self._on_delete_checked_requested()

    def _on_clean_clicked(self):
        if self._on_clean_queue_requested:
            self._on_clean_queue_requested()

    # ── Handler selezione task ──

    def _on_item_double_clicked(self, item):
        tid = item.data(_Qt.ItemDataRole.UserRole) if item else ""
        if self._on_task_activated:
            self._on_task_activated(tid)

    def _on_custom_context_menu(self, pos):
        if self._on_context_menu:
            self._on_context_menu(pos)

    def _on_item_clicked(self, item):
        pass  # Handler opzionale

    def _on_item_changed(self, item):
        pass  # Handler opzionale checkbox state

    # ── Logica helper interni ──

    def _toggle_select_all(self):
        """Inverte lo stato della select-all e aggiorna pulsante."""
        checked_count = 0
        unchecked_count = 0
        for i in range(self.task_list.count()):
            it = self.task_list.item(i)
            if it.checkState() == _Qt.CheckState.Checked:
                checked_count += 1
            else:
                unchecked_count += 1
        if checked_count > 0 and unchecked_count > 0:
            new_state = _Qt.CheckState.Checked
        elif checked_count > 0:
            new_state = _Qt.CheckState.Unchecked
        else:
            new_state = _Qt.CheckState.Checked
        for i in range(self.task_list.count()):
            it = self.task_list.item(i)
            it.setCheckState(new_state)
        self.btn_select_all.setText("☐" if new_state == _Qt.CheckState.Checked else "☑")

    def _is_select_all_checked(self) -> bool:
        """Verifica se tutti i task sono spuntati."""
        for i in range(self.task_list.count()):
            it = self.task_list.item(i)
            if it.checkState() != _Qt.CheckState.Checked:
                return False
        return True

    # ── Esportatore stato lista (per FileTreeDrawer) ──

    def set_tasks(self, tasks: list[dict]):
        """Sovrascrive la lista task visualizzate.

        `tasks`: lista di dict {"id": str, "title": str, "status": str}.
        Lo stato "status" è uno di: pending, running, failed, done, queued, paused, thermal_paused.
        """
        self.task_list.clear()
        for t in tasks:
            tid = t.get("id", "")
            title = t.get("title", "?")
            st = t.get("status", "pending")
            icon_map = {
                "done": "✓", "running": "▶", "pending": "○",
                "failed": "✗", "queued": "○",
                "paused": "⏸", "thermal_paused": "🌡",
            }
            color_map = {
                "done": "#16a34a", "running": "#f59e0b",
                "pending": "#dc2626", "failed": "#dc2626",
                "paused": "#6b7280", "thermal_paused": "#f97316",
            }
            icon = icon_map.get(st, "○")
            color = color_map.get(st, "#888")
            item = QListWidgetItem(f"{icon} {title}")
            item.setData(_Qt.ItemDataRole.UserRole, tid)
            item.setFlags(item.flags() | _Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(_Qt.CheckState.Unchecked)
            item.setForeground(QColor(color))
            self.task_list.addItem(item)

    def toggle_select_all(self):
        """Pubblica il toggle (chiamato da FileTreeDrawer)."""
        self._toggle_select_all()

    def refresh_tasks(self):
        """Pubblica il refresh (chiamato da FileTreeDrawer)."""
        self._refresh_internal()

    def _refresh_internal(self):
        """Refresh interno: ricarica task dal progetto."""
        raise NotImplementedError("TaskListWidget.refresh() richiede project_path")

    def add_task(self, task_id: str, title: str, status: str = "pending"):
        """Aggiunge un task alla lista."""
        icon_map = {
            "done": "✓", "running": "▶", "pending": "○",
            "failed": "✗", "queued": "○",
            "paused": "⏸", "thermal_paused": "🌡",
        }
        color_map = {
            "done": "#16a34a", "running": "#f59e0b",
            "pending": "#dc2626", "failed": "#dc2626",
            "paused": "#6b7280", "thermal_paused": "#f97316",
        }
        icon = icon_map.get(status, "○")
        color = color_map.get(status, "#888")
        item = QListWidgetItem(f"{icon} {title}")
        item.setData(_Qt.ItemDataRole.UserRole, task_id)
        item.setFlags(item.flags() | _Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(_Qt.CheckState.Unchecked)
        item.setForeground(QColor(color))
        self.task_list.addItem(item)

    def delete_checked_tasks(self):
        """Rimuove dalla lista i task con checkbox spuntata."""
        checked_ids = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.checkState() == _Qt.CheckState.Checked:
                tid = item.data(_Qt.ItemDataRole.UserRole)
                if tid:
                    checked_ids.append(str(tid))
        for tid in reversed(checked_ids):
            for i in range(self.task_list.count()):
                item = self.task_list.item(i)
                if str(item.data(_Qt.ItemDataRole.UserRole)) == tid:
                    self.task_list.takeItem(i)
                    break

    def clean_queue(self):
        """Resetta in pending i task bloccati (fallito/stuck/failed_definitively)."""
        # Placeholder: la logica vera è in FileTreeDrawer/_clean_queue
        pass
