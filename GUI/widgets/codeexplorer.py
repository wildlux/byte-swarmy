"""
CodeExplorer — estratto da GUI/control_center.py.
"""

import os
import ast
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabBar, QStackedWidget, QTextEdit,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QSizePolicy, QSpacerItem, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QPalette, QPixmap, QFont, QBrush, QPen, QPainter, QCursor, QDesktopServices


class CodeExplorer(QFrame):
    node_clicked = pyqtSignal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("code_explorer")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(QLabel("<b>🎮 Navigatore di codice Interattivo</b>"))
        head.addStretch()

        # Pulsanti zoom in/out e reset pan — prima esistevano ma non erano
        # collegati a nessuna funzione (artefatti visivi). Ora funzionano.
        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(26, 26)
        zoom_in.setObjectName("code_zoom_in")
        zoom_in.setToolTip("Zoom in (ingrandisci grafo)")
        zoom_in.setStyleSheet(
            "QPushButton#code_zoom_in { font-size:14px; font-weight:bold; "
            "background:#e8e8ec; border:1px solid #d0d0d0; border-radius:4px; }"
            "QPushButton#code_zoom_in:hover { background:#d0d0d0; }"
        )
        zoom_in.clicked.connect(self._zoom_in)
        head.addWidget(zoom_in)

        zoom_out = QPushButton("-")
        zoom_out.setFixedSize(26, 26)
        zoom_out.setObjectName("code_zoom_out")
        zoom_out.setToolTip("Zoom out (riduci grafo)")
        zoom_out.setStyleSheet(
            "QPushButton#code_zoom_out { font-size:14px; font-weight:bold; "
            "background:#e8e8ec; border:1px solid #d0d0d0; border-radius:4px; }"
            "QPushButton#code_zoom_out:hover { background:#d0d0d0; }"
        )
        zoom_out.clicked.connect(self._zoom_out)
        head.addWidget(zoom_out)

        # Pulsante reset zoom (pan/fit) — resetta la vista al grafo intero
        reset_btn = QPushButton("⟳")
        reset_btn.setFixedSize(26, 26)
        reset_btn.setObjectName("code_zoom_reset")
        reset_btn.setToolTip("Reset vista (fit grafo)")
        reset_btn.setStyleSheet(
            "QPushButton#code_zoom_reset { font-size:13px; "
            "background:#e8e8ec; border:1px solid #d0d0d0; border-radius:4px; }"
            "QPushButton#code_zoom_reset:hover { background:#d0d0d0; }"
        )
        reset_btn.clicked.connect(self._reset_view)
        head.addWidget(reset_btn)

        lay.addLayout(head)

        self.file_label = QLabel("Nessun file caricato")
        self.file_label.setStyleSheet("font-size:11px;")
        lay.addWidget(self.file_label)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        lay.addWidget(self.view)

        legend = QHBoxLayout()
        legend.addWidget(self._legend_item("Classe", "#89b4fa"))
        legend.addWidget(self._legend_item("Funzione", "#a6e3a1"))
        legend.addWidget(self._legend_item("Variabile", "#fab387"))
        lay.addLayout(legend)

        self.nodes = []

    def _legend_item(self, label, color):
        widget = QWidget()
        lay = QHBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        indicator = QLabel("●")
        indicator.setStyleSheet(f"color:{color}; font-size:14px;")
        lay.addWidget(indicator)
        text = QLabel(label)
        text.setStyleSheet("font-size:10px; ")
        lay.addWidget(text)
        return widget

    # ── Zoom / pan handlers ────────────────────────────────────────────
    def _zoom_in(self):
        """Ingrandisce il grafo del 20% (zoom in)."""
        self.view.scale(1.2, 1.2)

    def _zoom_out(self):
        """Riduce il grafo del 20% (zoom out)."""
        self.view.scale(1 / 1.2, 1 / 1.2)

    def _reset_view(self):
        """Reset zoom/pan: fit del grafo nell'area visibile."""
        self.view.resetTransform()
        if self.scene.items():
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def load_file(self, file_path):
        self.file_label.setText(os.path.basename(file_path))
        self.nodes = []
        self.scene.clear()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            self._parse_ast(tree, file_path)
            self._layout_nodes()
            self._render_nodes()
        except Exception as e:
            self.scene.addText(f"Errore parsing: {e}")

    def _parse_ast(self, tree, file_path):
        module_node = CodeNode(os.path.basename(file_path), "module", 1, len(tree.body), [])
        self.nodes.append(module_node)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_node = CodeNode(node.name, "class", node.lineno, node.end_lineno or node.lineno + 10, [])
                module_node.children.append(class_node)
                self.nodes.append(class_node)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        func_node = CodeNode(item.name, "function", item.lineno, item.end_lineno or item.lineno + 5, [])
                        class_node.children.append(func_node)
                        self.nodes.append(func_node)
            elif isinstance(node, ast.FunctionDef):
                if not any(n.children and node in n.children for n in self.nodes):
                    func_node = CodeNode(node.name, "function", node.lineno, node.end_lineno or node.lineno + 5, [])
                    module_node.children.append(func_node)
                    self.nodes.append(func_node)

    def _layout_nodes(self):
        y_spacing = 80
        x_spacing = 200
        if self.nodes:
            self.nodes[0].x = 200
            self.nodes[0].y = 50
            child_y = 150
            for child in self.nodes[0].children:
                child.x = 200
                child.y = child_y
                child_y += y_spacing
                if child.children:
                    grandchild_x = 450
                    for gc in child.children:
                        gc.x = grandchild_x
                        gc.y = child.y
                        grandchild_x += x_spacing

    def _render_nodes(self):
        colors = {"module": "#cdd6f4", "class": "#89b4fa", "function": "#a6e3a1", "variable": "#fab387"}
        for node in self.nodes:
            if node.children:
                for child in node.children:
                    line = self.scene.addLine(node.x + 60, node.y + 20, child.x + 60, child.y + 20, QPen(QColor("#6c7086"), 1.5))
                    line.setZValue(-1)

        for node in self.nodes:
            color = colors.get(node.node_type, "#cdd6f4")
            rect = QGraphicsRectItem(node.x, node.y, 140, 40)
            rect.setBrush(QBrush(QColor(color)))
            rect.setPen(QPen(QColor("#1e1e2e"), 2))
            rect.setZValue(0)
            self.scene.addItem(rect)

            text = self.scene.addText(f"{node.name}")
            text.setDefaultTextColor(QColor("#1e1e2e"))
            text.setPos(node.x + 10, node.y + 8)
            text.setZValue(1)

            line_info = self.scene.addText(f"L{node.line_start}-{node.line_end}")
            line_info.setDefaultTextColor(QColor("#6c7086"))
            line_info.setPos(node.x + 10, node.y + 24)
            line_info.setScale(0.7)
            line_info.setZValue(1)

            rect.setAcceptHoverEvents(True)
            rect.mousePressEvent = lambda e, n=node: self._on_node_click(n)

    def _on_node_click(self, node):
        node.expanded = not node.expanded
        self.scene.clear()
        self._render_nodes()
        self.node_clicked.emit(node.name, node.line_start, node.line_end)


# ═══════════════════════════════════════════════════════════════
# FILE EDITOR
# ═══════════════════════════════════════════════════════════════
