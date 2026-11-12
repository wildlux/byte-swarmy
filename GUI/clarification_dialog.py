"""GUI/clarification_dialog.py — Q2: dialog per domande interattive.

Widget PyQt6 che mostra domande con opzioni numerate e un campo per
risposta libera. L'utente seleziona → la risposta viene restituita
come stringa "1,3,1" compatibile con parse_answer().

Fail-open: se PyQt6 non è disponibile, il modulo si importa senza errori
e fornisce una fallback CLI.
"""
from __future__ import annotations

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QLabel, QRadioButton, QButtonGroup,
        QPushButton, QLineEdit, QHBoxLayout, QScrollArea, QWidget,
    )
    from PyQt6.QtCore import Qt
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

from typing import Optional


class ClarificationDialog:
    """Dialog per domande interattive (Q2).

    Uso:
        dlg = ClarificationDialog(questions, parent=window)
        answer = dlg.exec_and_get_answer()  # "1,3,1" o None se annullato
    """

    def __init__(self, questions, parent=None):
        self.questions = questions
        self._parent = parent
        self._answer: Optional[str] = None

        if not _QT_AVAILABLE:
            return

        self._dialog = QDialog(parent)
        self._dialog.setWindowTitle("Chiarimento task")
        self._dialog.setMinimumWidth(500)
        layout = QVBoxLayout(self._dialog)

        # Titolo
        title = QLabel("Ho bisogno di chiarire alcuni punti prima di iniziare:")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Gruppi di radio button per ogni domanda
        self._groups: list = []
        for q in questions:
            # Testo domanda
            q_label = QLabel(f"{q.id}. {q.text}")
            q_label.setWordWrap(True)
            layout.addWidget(q_label)

            group = QButtonGroup(self._dialog)
            group.setExclusive(True)
            radios = []
            for i, opt in enumerate(q.options, 1):
                radio = QRadioButton(f"{i}) {opt}")
                group.addButton(radio, i)
                radios.append(radio)
                layout.addWidget(radio)
            # Opzione "Altro (libero)"
            free_radio = QRadioButton("0) Altro (specifica)")
            group.addButton(free_radio, 0)
            radios.append(free_radio)
            layout.addWidget(free_radio)

            # Campo libero (visibile solo se "Altro" selezionato)
            free_edit = QLineEdit()
            free_edit.setPlaceholderText("Specifica...")
            free_edit.setVisible(False)
            layout.addWidget(free_edit)
            free_radio.toggled.connect(
                lambda checked, e=free_edit: e.setVisible(checked))

            self._groups.append((group, radios, free_edit))

        # Pulsanti
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Conferma")
        cancel_btn = QPushButton("Annulla")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_ok(self):
        answers = []
        for group, radios, free_edit in self._groups:
            checked = group.checkedId()
            if checked == 0:
                answers.append(free_edit.text() or "0")
            else:
                answers.append(str(checked))
        self._answer = ",".join(answers)
        self._dialog.accept()

    def _on_cancel(self):
        self._answer = None
        self._dialog.reject()

    def exec_and_get_answer(self) -> Optional[str]:
        """Mostra il dialog e restituisce la risposta o None."""
        if not _QT_AVAILABLE:
            return None
        self._dialog.exec()
        return self._answer


def show_clarification(questions, parent=None) -> Optional[str]:
    """Funzione helper per mostrare il dialog di chiarimento."""
    dlg = ClarificationDialog(questions, parent=parent)
    return dlg.exec_and_get_answer()
