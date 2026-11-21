"""
GUI/label_completion.py — Autocompletamento etichette con trigger "#".

Mostra un popup con tutte le etichette registrate (CORE/labels.py) quando
l'utente digita "#" nel campo comando, con il colore di ogni etichetta.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QStandardItem, QStandardItemModel, QColor
from PyQt6.QtWidgets import QCompleter

from CORE import labels as L


class LabelMentionCompleter(QCompleter):
    """Completer che mostra le etichette (tag) con trigger '#'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self._refresh_model()

    def _refresh_model(self) -> None:
        """Ricarica il modello con le etichette correnti."""
        self._model.clear()
        for lab in L.list_labels():
            item = QStandardItem(lab["name"])
            item.setData(lab["name"], Qt.ItemDataRole.UserRole)
            item.setData(lab["name"], Qt.ItemDataRole.EditRole)
            item.setToolTip(f"Colore: {lab['color']}")
            item.setForeground(QColor(lab["color"]))
            self._model.appendRow(item)

    def refresh(self) -> None:
        """Alias pubblico per ricaricare il modello."""
        self._refresh_model()

    def selected_label_name(self, index: QModelIndex) -> str:
        """Restituisce il nome dell'etichetta dall'indice selezionato."""
        if not index.isValid():
            return ""
        return str(index.data(Qt.ItemDataRole.UserRole) or "")
