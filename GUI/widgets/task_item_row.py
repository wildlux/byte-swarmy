"""
TaskItemRow — riga task personalizzata per la sezione "Lavori e Compiti".

Estratto da GUI/control_center.py (riga ~3888).
Mostra un'icona colorata a sinistra + titolo a riempimento.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt


class TaskItemRow(QWidget):
    """Riga task personalizzata: icona a sinistra + titolo a riempimento."""

    def __init__(self, icon_text: str, icon_color: str, title: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        self.icon_lbl = QLabel(icon_text)
        self.icon_lbl.setStyleSheet(f"color: {icon_color}; font-weight: bold;")
        self.icon_lbl.setFixedWidth(22)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: inherit;")
        self.title_lbl.setWordWrap(True)
        lay.addWidget(self.title_lbl, stretch=1)
