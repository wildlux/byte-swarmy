"""
TaskItemRow — estratto da GUI/control_center.py.
"""
import os

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabBar, QStackedWidget, QTextEdit,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QSizePolicy, QSpacerItem, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QPalette, QPixmap, QFont, QBrush, QPen, QPainter, QCursor, QDesktopServices


class TaskItemRow(QWidget):
    """Riga task personalizzata: icona a sinistra + titolo a riempimento."""

    def __init__(self, icon_text: str, icon_color: str, title: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.icon_lbl = QLabel(icon_text)
        self.icon_lbl.setStyleSheet(f"color: {icon_color}; font-weight: bold;")
        self.icon_lbl.setFixedSize(22, 22)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: inherit;")
        self.title_lbl.setWordWrap(True)
        lay.addWidget(self.title_lbl, stretch=1)
