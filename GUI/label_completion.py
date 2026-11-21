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
        # Menu contestuale (tasto destro) sul popup per cambiare colore.
        popup = self.popup()
        popup.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        popup.customContextMenuRequested.connect(self._on_context_menu)

    def _on_context_menu(self, pos) -> None:
        """Menu tasto destro: cambia colore dell'etichetta selezionata."""
        from PyQt6.QtWidgets import QMenu, QColorDialog
        from CORE import labels as L
        popup = self.popup()
        index = popup.indexAt(pos)
        if not index.isValid():
            return
        name = str(index.data(Qt.ItemDataRole.UserRole) or "")
        if not name:
            return
        menu = QMenu(popup)
        act_color = menu.addAction("🎨 Cambia colore (dialog)")
        # Sottomenu colori rapidi
        color_menu = menu.addMenu("🎨 Colori rapidi")
        quick_colors = [
            ("#2563eb", "Blu"),
            ("#16a34a", "Verde"),
            ("#f59e0b", "Arancione"),
            ("#9333ea", "Viola"),
            ("#dc2626", "Rosso"),
            ("#0891b2", "Ciano"),
            ("#ec4899", "Rosa"),
            ("#64748b", "Grigio"),
        ]
        for hex_color, color_name in quick_colors:
            from GUI.label_swatch import make_swatch
            act = color_menu.addAction(
                make_swatch(hex_color), f"● {color_name}  {hex_color}")
            act.setData(hex_color)
        act_remove = menu.addAction("🗑️ Rimuovi etichetta")
        chosen = menu.exec(popup.mapToGlobal(pos))
        if chosen == act_color:
            picked = QColorDialog.getColor()
            if picked.isValid():
                L.set_color(name, picked.name())
                self._refresh_model()
        elif chosen == act_remove:
            L.remove_label(name)
            self._refresh_model()
        else:
            # Controlla se è un colore rapido
            chosen_color = chosen.data() if chosen is not None else None
            if chosen_color and isinstance(chosen_color, str) and chosen_color.startswith("#"):
                L.set_color(name, chosen_color)
                self._refresh_model()

    def _refresh_model(self) -> None:
        """Ricarica il modello con le etichette correnti."""
        self._model.clear()
        from GUI.label_swatch import make_swatch
        for lab in L.list_labels():
            item = QStandardItem(lab["name"])
            item.setData(lab["name"], Qt.ItemDataRole.UserRole)
            item.setData(lab["name"], Qt.ItemDataRole.EditRole)
            item.setToolTip(f"Colore: {lab['color']}")
            item.setForeground(QColor(lab["color"]))
            item.setIcon(make_swatch(lab["color"]))
            self._model.appendRow(item)

    def refresh(self) -> None:
        """Alias pubblico per ricaricare il modello."""
        self._refresh_model()

    def selected_label_name(self, index: QModelIndex) -> str:
        """Restituisce il nome dell'etichetta dall'indice selezionato."""
        if not index.isValid():
            return ""
        return str(index.data(Qt.ItemDataRole.UserRole) or "")
