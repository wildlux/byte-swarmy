"""
GUI/label_swatch.py — Pallino colorato per le voci di menu delle etichette.

Piccolo helper condiviso: genera una QIcon circolare del colore dell'etichetta
da mostrare accanto al nome nel menu contestuale (tasto destro → Etichetta).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap


def make_swatch(color: str, size: int = 12) -> QIcon:
    """Restituisce un'icona circolare piena del colore indicato."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return QIcon(pix)
