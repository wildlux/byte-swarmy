"""
CodeNode — estratto da GUI/control_center.py.
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


class CodeNode:
    def __init__(self, name, node_type, line_start, line_end, children=None):
        self.name = name
        self.node_type = node_type
        self.line_start = line_start
        self.line_end = line_end
        self.children = children or []
        self.expanded = True
        self.x = 0
        self.y = 0


