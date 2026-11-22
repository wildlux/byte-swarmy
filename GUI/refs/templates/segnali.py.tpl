"""Template PyQt6 — segnali e slot (E3 / py-gui-scaffold).

Copiare e sostituire i valori marcati `# SLOT:`. Pattern: pyqtSignal
dichiarato sulla classe, connect in __init__, nessuna logica bloccante nel costruttore
che blocchi la GUI. Il segnale è verificabile offscreen senza event loop.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget


class LiveLabel(QWidget):
    """Mostra in tempo reale il testo digitato (segnali collegati)."""

    # SLOT: tipo del segnale (str, int, ...)
    changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # SLOT: placeholder del campo di testo
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Scrivi qui")
        self.label = QLabel("")
        layout = QVBoxLayout(self)
        layout.addWidget(self.edit)
        layout.addWidget(self.label)
        self.edit.textChanged.connect(self.changed.emit)
        self.changed.connect(self.label.setText)
