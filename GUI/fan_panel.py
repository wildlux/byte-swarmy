"""Pannello Plancia — controllo ventole (nbfc + pkexec).

REGOLA DI PARITÀ GUI (Cycle 70): il controllo ventole è parte del
software (Cycle 77), non uno strumento esterno: qui si riusa il widget
VENTOLA/ventola.py senza duplicare logica. Le azioni passano da pkexec
→ dialog password di KDE.
"""

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from VENTOLA.ventola import FanControl


class FanPanel(QWidget):
    """Wrapper leggero: il widget vero è FanControl (VENTOLA/ventola.py)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.fan = FanControl()
        lay.addWidget(self.fan)
