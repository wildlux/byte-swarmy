"""Template PyQt6 — layout annidato (E3 / py-gui-scaffold).

Copiare e sostituire i valori marcati `# SLOT:`. Struttura: QVBoxLayout
radice, QFormLayout per i campi, QHBoxLayout per i pulsanti.
"""
from PyQt6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

# SLOT: etichetta del campo
FIELD_LABEL = "Nome"
# SLOT: testi dei pulsanti
OK_TEXT, CANCEL_TEXT = "OK", "Annulla"


def build_layout():
    """Restituisce un QWidget con la gerarchia di layout completa."""
    root = QWidget()
    main = QVBoxLayout(root)

    # QFormLayout crea la QLabel di FIELD_LABEL: non duplicarla.
    form = QFormLayout()
    form.addRow(FIELD_LABEL, QLineEdit())
    main.addLayout(form)

    buttons = QHBoxLayout()
    buttons.addWidget(QPushButton(OK_TEXT))
    buttons.addWidget(QPushButton(CANCEL_TEXT))
    main.addLayout(buttons)
    return root
