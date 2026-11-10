"""
GUI/plancia_card.py — Card cliccabile per la plancia di controllo.

Estratto da GUI/control_center.py (classe PlanciaCard).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
)


class PlanciaCard(QFrame):
    """Card cliccabile per la plancia di controllo.

    Segnale:
        clicked() — emesso al click sinistro sulla card.
    """

    clicked = pyqtSignal()

    def __init__(self, title, subtitle, badge=None, badge_color="#666", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Altezza minima uniforme per tutte le card: 110px bastano per
        # titolo + 2 righe di descrizione (word-wrap tronca al bisogno).
        # Size policy orizzontale Expanding: la card RIEMPIE la cella della
        # grid, qualunque sia la lunghezza del titolo.
        # Altezza: lasciato al layout natural expansion (no fixed/minimum
        # imposti così la card cresce proporzionalmente con la finestra).
        # Nessun MinimumWidth (sennò invalidate il ColumnStretch e le
        # colonne diventano disuguali).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(120)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:13px; font-weight:bold; ")
        # Titolo troncato con elipsis (non va a capo) così non deforma la
        # card e non spinge il badge. Tooltip mostra il titolo completo.
        title_lbl.setToolTip(title)
        title_lbl.setWordWrap(False)
        title_lbl.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        head.addWidget(title_lbl, stretch=1)

        if badge:
            badge_lbl = QLabel(badge)
            # Badge: testo BIANCO su colore SOLIDO → contrasto sempre
            # leggibile anche allo zoom alto. Dimensione fissa per tutte
            # le card.
            badge_lbl.setStyleSheet(
                f"background:{badge_color}; color:#ffffff; "
                f"padding:3px 9px; border-radius:10px; font-size:10px; font-weight:bold;"
            )
            badge_lbl.setToolTip(badge)
            # Il badge non deve espandere né forzare la larghezza
            badge_lbl.setSizePolicy(
                QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
            )
            head.addWidget(badge_lbl)

        lay.addLayout(head)

        sub_lbl = QLabel(subtitle)
        # Descrizione: elipsis se troppo lunga, mai a capo (mantiene altezza fissa)
        sub_lbl.setToolTip(subtitle)
        sub_lbl.setWordWrap(False)
        sub_lbl.setStyleSheet("font-size:10px; color:#cbd5e1; ")
        sub_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        lay.addWidget(sub_lbl, stretch=1)

        lay.addStretch()

        # Tema: il QSS app-level stila QFrame#card; l'hover aggiunge solo
        # il bordo (il background resta quello del tema).
        self._normal_style = ""
        self._hover_style = (
            "QFrame#card { border:1px solid #16a34a; border-radius:8px; }"
        )

    def enterEvent(self, event):
        self.setStyleSheet(self._hover_style)

    def leaveEvent(self, event):
        self.setStyleSheet(self._normal_style)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
