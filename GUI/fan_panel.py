"""Pannello Plancia — controllo ventole (nbfc + pkexec).

REGOLA DI PARITÀ GUI (Cycle 70): il controllo ventole è parte del
software (Cycle 77), non uno strumento esterno: qui si riusa il widget
VENTOLA/ventola.py senza duplicare logica. Le azioni passano da pkexec
→ dialog password di KDE.
"""

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from VENTOLA.ventola import FanControl


class FanPanel(QWidget):
    """Wrapper leggero: il widget vero è FanControl (VENTOLA/ventola.py)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # 🆕 Cycle 85: regola di parità GUI — back_btn per tornare alla
        # Plancia (stesso pattern di hardware_panel/test_suite_panel).
        head = QHBoxLayout()
        head.addStretch()
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        lay.addLayout(head)

        self.fan = FanControl()
        lay.addWidget(self.fan)

    def _back_to_main(self):
        """Torna alla plancia di controllo (walk-up sul parent tree)."""
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()
