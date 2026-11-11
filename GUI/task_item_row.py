"""task_item_row.py — Riga task personalizzata per il Control Center.

Estratto da GUI/control_center.py per ridurre il monolite.

Riga usata con QListWidget.setItemWidget(): checkbox di selezione (colonna
✓) + pallino di stato colorato + titolo neutro. La checkbox è il primo
elemento con margine sinistro calibrato perché il suo indicatore risulti
allineato verticalmente col glifo ☑ del pulsante "seleziona tutto" che
sta nella barra sopra la lista (stesso asse x ≈ 14px).
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal


class TaskItemRow(QWidget):
    """Riga task personalizzata: checkbox + pallino di stato colorato + titolo.

    Segnali (per replicare i comportamenti nativi della QListWidget, che con
    setItemWidget riceverebbero solo gli eventi dei widget figli):
    - ``clicked``          → click sulla riga
    - ``double_clicked``   → doppio click sulla riga
    - ``context_requested``→ tasto destro (emette la pos GLOBAL)
    """

    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    context_requested = pyqtSignal(object)  # QPoint globale

    def __init__(self, icon_text: str, icon_color: str, title: str,
                 checked: bool = False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        # Margine sinistro 7px: l'indicatore checkbox (14px) resta centrato
        # a 7+7=14px, come il centro del glifo ☑ nel pulsante da 28px sopra.
        lay.setContentsMargins(7, 2, 4, 2)
        lay.setSpacing(6)

        self.check = QCheckBox()
        self.check.setToolTip("Seleziona il task")
        self.check.setStyleSheet(
            "QCheckBox::indicator { width: 14px; height: 14px; "
            "border: 1px solid #94a3b8; border-radius: 3px; background: #ffffff; }"
            "QCheckBox::indicator:hover { border-color: #2563eb; }"
            "QCheckBox::indicator:checked { background: #2563eb; "
            "border-color: #2563eb; }"
        )
        lay.addWidget(self.check)

        self.icon_lbl = QLabel(icon_text)
        self.icon_lbl.setStyleSheet(f"color: {icon_color}; font-weight: bold;")
        self.icon_lbl.setFixedWidth(22)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Trasparente al mouse: i click raggiungono la riga (segnali sopra)
        self.icon_lbl.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: inherit;")
        # Niente wordWrap: con righe da 30px il testo andata a capo sarebbe
        # tagliato (era la causa della "scritta male" nello screenshot).
        self.title_lbl.setWordWrap(False)
        self.title_lbl.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.title_lbl, stretch=1)

        self.set_checked(checked)

    # ------------------------------------------------------------------
    # API per il drawer
    # ------------------------------------------------------------------

    def set_checked(self, checked: bool):
        """Imposta lo stato della checkbox senza emettere segnali (no loop)."""
        self.check.blockSignals(True)
        self.check.setChecked(checked)
        self.check.blockSignals(False)

    def set_display(self, icon_text: str, icon_color: str, title: str):
        """Aggiorna pallino di stato (testo+colore) e titolo della riga."""
        self.icon_lbl.setText(icon_text)
        self.icon_lbl.setStyleSheet(f"color: {icon_color}; font-weight: bold;")
        self.title_lbl.setText(title)

    # ------------------------------------------------------------------
    # Eventi mouse: instradati come segnali per il QListWidget
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        event.accept()

    def contextMenuEvent(self, event):
        self.context_requested.emit(event.globalPos())
        event.accept()
