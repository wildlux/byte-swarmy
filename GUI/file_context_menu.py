"""
GUI/file_context_menu.py — Context menu per file tree e task list.

Estratto da GUI/file_tree_drawer.py per ridurre il monolite.

Fornisce:
- Costruzione e visualizzazione di menu contestuali (tasto destro) su file tree e task.
- Azioni: Modifica, Rinomina, Elimina, Dettagli, Copia ID, Apri risultato, Pausa/Ferma task.
- Callback delegate al genitore (FileTreeDrawer) per mantenere la logica.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt as _Qt, QPoint, QModelIndex
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QMenu


class FileContextMenu(QMenu):
    """Menu contestuale per elementi del file tree o task list.

    Usa callback passati al costruttore per evitare accoppiamento forte.
    Il genitore (FileTreeDrawer) collega i callback ai segnali delle azioni.
    """

    def __init__(
        self,
        *,
        on_edit: Optional[Callable[[str], None]] = None,
        on_rename: Optional[Callable[[str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
        on_details: Optional[Callable[[str], None]] = None,
        on_copy_id: Optional[Callable[[str], None]] = None,
        on_open_result: Optional[Callable[[str], None]] = None,
        on_pause: Optional[Callable[[str], None]] = None,
        on_resume: Optional[Callable[[str], None]] = None,
        on_stop: Optional[Callable[[str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setIconSize(_Qt.QSize(16, 16))

        # Azioni file
        self.act_edit = QAction("✏️ Modifica", self)
        self.act_edit.triggered.connect(self._on_action_edit)
        self.addAction(self.act_edit)

        self.act_rename = QAction("📝 Rinomina", self)
        self.act_rename.triggered.connect(self._on_action_rename)
        self.addAction(self.act_rename)

        self.addSeparator()

        self.act_delete = QAction("🗑️ Elimina", self)
        self.act_delete.triggered.connect(self._on_action_delete)
        self.addAction(self.act_delete)

        self.addSeparator()

        # Azioni task-specific (condizionali)
        self.act_details = QAction("📋 Dettagli", self)
        self.act_details.triggered.connect(self._on_action_details)
        self.addAction(self.act_details)

        self.act_copy_id = QAction("📋 Copia ID", self)
        self.act_copy_id.triggered.connect(self._on_action_copy_id)
        self.addAction(self.act_copy_id)

        self.act_open_result = QAction("📂 Apri risultato", self)
        self.act_open_result.triggered.connect(self._on_action_open_result)
        self.addAction(self.act_open_result)

        self.addSeparator()

        # Azioni task (pause/resume/stop) — visibili solo per task
        self.act_pause = QAction("▶ Pausa", self)
        self.act_pause.triggered.connect(self._on_action_pause)
        self.addAction(self.act_pause)

        self.act_resume = QAction("⏸ Riprendi", self)
        self.act_resume.triggered.connect(self._on_action_resume)
        self.addAction(self.act_resume)

        self.act_stop = QAction("🛑 Ferma", self)
        self.act_stop.triggered.connect(self._on_action_stop)
        self.addAction(self.act_stop)

        # Inizialmente nascondiamo le azioni task finché non sappiamo se siamo su task o file
        self.act_pause.setVisible(False)
        self.act_resume.setVisible(False)
        self.act_stop.setVisible(False)

    # ── Handler azioni (delegano ai callback esterni) ──

    def _on_action_edit(self):
        if self._on_edit:
            self._on_edit()

    def _on_action_rename(self):
        if self._on_rename:
            self._on_rename()

    def _on_action_delete(self):
        if self._on_delete:
            self._on_delete()

    def _on_action_details(self):
        if self._on_details:
            self._on_details()

    def _on_action_copy_id(self):
        if self._on_copy_id:
            self._on_copy_id()

    def _on_action_open_result(self):
        if self._on_open_result:
            self._on_open_result()

    def _on_action_pause(self):
        if self._on_pause:
            self._on_pause()

    def _on_action_resume(self):
        if self._on_resume:
            self._on_resume()

    def _on_action_stop(self):
        if self._on_stop:
            self._on_stop()

    # ── Metodi di comodità per mostrare/nascondere azioni task ──

    def show_task_actions(self, show: bool = True):
        """Mostra/nascondi le azioni pause/resume/stop (visibili solo per task)."""
        self.act_pause.setVisible(show)
        self.act_resume.setVisible(show)
        self.act_stop.setVisible(show)

    def set_edit_enabled(self, enabled: bool):
        """Abilita/disabilita l'azione Modifica."""
        self.act_edit.setEnabled(enabled)

    def set_delete_enabled(self, enabled: bool):
        """Abilita/disabilina l'azione Elimina."""
        self.act_delete.setEnabled(enabled)

    # ── Posizionamento del menu ──

    def exec_at(self, pos: QPoint):
        """Esegui il menu nella posizione specificata."""
        self.exec(pos)

    # ── Reset stato interno (chiamare dopo chiusura menu) ──

    def reset(self):
        """Resetta stato interno del menu."""
        pass
