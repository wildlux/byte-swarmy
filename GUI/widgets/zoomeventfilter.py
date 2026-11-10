"""
_ZoomEventFilter — estratto da GUI/control_center.py.
"""
import os

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabBar, QStackedWidget, QTextEdit,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QSizePolicy, QSpacerItem, QMessageBox,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QPalette, QPixmap, QFont, QBrush, QPen, QPainter, QCursor, QDesktopServices


class _ZoomEventFilter(QObject):
    """Event filter globale per catturare Ctrl++ / Ctrl+-- / Ctrl+0
    anche quando il focus è su un widget figlio (QLineEdit, QTextEdit, ecc.)."""

    def __init__(self, window):
        super().__init__()
        self.window = window

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier:
                if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                    self.window._zoom_in()
                    return True
                if key == Qt.Key.Key_Minus:
                    self.window._zoom_out()
                    return True
                if key == Qt.Key.Key_0:
                    self.window._zoom_reset()
                    return True
        return super().eventFilter(obj, event)
