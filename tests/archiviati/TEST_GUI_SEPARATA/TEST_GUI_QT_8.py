#!/usr/bin/env python3
"""
BYTE-SWARMY Control Center — Log categorizzati + Code Explorer in Plancia
PyQt6, single-file
"""

import sys
import os
import random
import subprocess
import ast
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit, QTextEdit,
    QFrame, QTreeView, QGridLayout, QTabBar, QHeaderView, QMenu,
    QInputDialog, QMessageBox, QWidgetAction, QFileDialog, QSplitter,
    QGraphicsView, QGraphicsScene, QGraphicsTextItem, QGraphicsRectItem,
    QScrollArea
)
from PyQt6.QtGui import (
    QFont, QFileSystemModel, QCursor, QTextCursor, QAction,
    QColor, QPen, QBrush, QPainter
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QDir, QTimer, QRectF, QPoint


# ═══════════════════════════════════════════════════════════════
# DEVICE PANEL
# ═══════════════════════════════════════════════════════════════
class DevicePanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("device_panel")
        self.setFixedHeight(56)
        self.setStyleSheet(
            "QFrame#device_panel { background:#f8f9fa; border:1px solid #e0e0e0; "
            "border-radius:8px; }"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)

        devices_col = QVBoxLayout()
        devices_col.setSpacing(2)
        devices_col.setContentsMargins(0, 0, 0, 0)

        self.cpu_box = self._device_row("CPU", "#16a34a", "qwen2.5:1.5b")
        self.gpu_box = self._device_row("GPU", "#2563eb", "—")

        devices_col.addWidget(self.cpu_box)
        devices_col.addWidget(self.gpu_box)
        lay.addLayout(devices_col)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:#d0d0d0;")
        lay.addWidget(sep)

        self.git_btn = QPushButton("💾")
        self.git_btn.setFixedWidth(36)
        self.git_btn.setFixedHeight(46)
        self.git_btn.setObjectName("git_btn")
        self.git_btn.setToolTip("Salva su tutti i remote Git configurati")
        self.git_btn.setStyleSheet(
            "QPushButton#git_btn { background:#2563eb; color:white; "
            "font-size:16px; border-radius:6px; border:none; }"
            "QPushButton#git_btn:hover { background:#1d4ed8; }"
        )
        self.git_btn.clicked.connect(self._do_git_save)
        lay.addWidget(self.git_btn)

        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setFixedWidth(44)
        self.toggle_btn.setFixedHeight(46)
        self.toggle_btn.setObjectName("primary_btn")
        self.toggle_btn.setToolTip("Avvia/Ferma Orchestratore")
        self.toggle_btn.setStyleSheet(
            "QPushButton#primary_btn { background:#16a34a; color:white; "
            "font-weight:bold; font-size:16px; border-radius:6px; border:none; }"
            "QPushButton#primary_btn:hover { background:#15803d; }"
        )
        lay.addWidget(self.toggle_btn)

        self.git_remotes = self._detect_git_remotes()
        self._update_git_tooltip()

    def _detect_git_remotes(self):
        remotes = []
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                seen = set()
                for line in result.stdout.strip().split("\n"):
                    if line:
                        name = line.split()[0]
                        if name not in seen:
                            seen.add(name)
                            url = line.split()[1]
                            if "github" in url:
                                remotes.append(("GitHub", name))
                            elif "gitlab" in url:
                                remotes.append(("GitLab", name))
                            else:
                                remotes.append(("Git", name))
        except Exception:
            pass
        if not remotes:
            remotes = [("Git", "origin")]
        return remotes

    def _update_git_tooltip(self):
        names = [r[0] for r in self.git_remotes]
        if len(names) == 1:
            self.git_btn.setToolTip(f"Salva su {names[0]}")
        else:
            self.git_btn.setToolTip(f"Salva su {', '.join(names)}")

    def _do_git_save(self):
        names = [r[0] for r in self.git_remotes]
        print(f"[GIT] Salvataggio su: {', '.join(names)}")

    def _device_row(self, name, color, model_name):
        row = QFrame()
        row.setObjectName(f"{name.lower()}_row")
        row.setFixedHeight(24)
        row.setStyleSheet(
            f"QFrame#{name.lower()}_row {{ background:#ffffff; border:1px solid {color}44; "
            f"border-radius:4px; }}"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"color:{color}; font-size:12px; font-weight:bold;")
        lbl.setFixedWidth(32)
        lay.addWidget(lbl)

        model_lbl = QLabel(model_name)
        model_lbl.setStyleSheet("color:#555; font-size:10px;")
        model_lbl.setFixedWidth(72)
        lay.addWidget(model_lbl)

        temp_lbl = QLabel("45°C")
        tok_lbl = QLabel("12t/s")
        kv_lbl = QLabel("2.1G")
        mem_lbl = QLabel("65%")
        bus_lbl = QLabel("800M")

        for w in (temp_lbl, tok_lbl, kv_lbl, mem_lbl, bus_lbl):
            w.setStyleSheet("color:#333; font-size:11px; font-weight:500;")
            w.setFixedWidth(38)
            lay.addWidget(w)

        row._temp = temp_lbl
        row._tok = tok_lbl
        row._kv = kv_lbl
        row._mem = mem_lbl
        row._bus = bus_lbl
        row._model = model_lbl
        return row


# ═══════════════════════════════════════════════════════════════
# CLICKABLE CARD (COLLAPSIBLE)
# ═══════════════════════════════════════════════════════════════
class CollapsibleCard(QFrame):
    clicked = pyqtSignal()
    collapse_toggled = pyqtSignal(bool)

    def __init__(self, title, subtitle, badge=None, badge_color="#666", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(120)
        self._collapsed = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        # Header con titolo e badge
        head = QHBoxLayout()
        head.setSpacing(6)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size:14px; font-weight:bold; color:#1a1a1a;")
        head.addWidget(self.title_lbl, stretch=1)

        if badge:
            self.badge_lbl = QLabel(badge)
            self.badge_lbl.setStyleSheet(
                f"background:{badge_color}22; color:{badge_color}; "
                f"padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;"
            )
            head.addWidget(self.badge_lbl)

        # Pulsante collapse/expand
        self.toggle_btn = QPushButton("▾")
        self.toggle_btn.setFixedSize(24, 24)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background:#e8e8ec; border:none; border-radius:4px; font-size:11px; }"
            "QPushButton:hover { background:#d0d0d0; }"
        )
        self.toggle_btn.clicked.connect(self._on_toggle_collapse)
        head.addWidget(self.toggle_btn)

        lay.addLayout(head)

        # Sottotitolo
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("font-size:11px; color:#666;")
        lay.addWidget(self.sub_lbl)

        # Contenuto espandibile (nascosto di default)
        self.content_area = QWidget()
        content_lay = QVBoxLayout(self.content_area)
        content_lay.setContentsMargins(0, 8, 0, 0)
        content_lay.setSpacing(4)

        # Placeholder per contenuti dinamici
        self.content_text = QLabel("Contenuto dettagliato...")
        self.content_text.setStyleSheet("font-size:10px; color:#888; font-style:italic;")
        content_lay.addWidget(self.content_text)

        lay.addWidget(self.content_area)

        self._normal_style = (
            "QFrame#card { background:#ffffff; border:1px solid #e0e0e0; border-radius:10px; }"
        )
        self._hover_style = (
            "QFrame#card { background:#f0f9ff; border:1px solid #16a34a; border-radius:10px; }"
        )
        self.setStyleSheet(self._normal_style)

    def _on_toggle_collapse(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.content_area.hide()
            self.sub_lbl.hide()
            self.toggle_btn.setText("▸")
            self.setFixedHeight(50)
        else:
            self.content_area.show()
            self.sub_lbl.show()
            self.toggle_btn.setText("▾")
            self.setFixedHeight(120)
        self.collapse_toggled.emit(self._collapsed)

    def enterEvent(self, event):
        self.setStyleSheet(self._hover_style)

    def leaveEvent(self, event):
        self.setStyleSheet(self._normal_style)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.y() < 40:
            self.clicked.emit()


# ═══════════════════════════════════════════════════════════════
# LOG CATEGORIZZATO (solo Ollama + ByteSwarm)
# ══════════════════════════════════════════════════════════════
class CategorizedLogViewer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("log_viewer")
        self.setStyleSheet(
            "QFrame#log_viewer { background:#ffffff; border:1px solid #e0e0e0; "
            "border-radius:6px; }"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.setMovable(False)
        self.tab_bar.addTab("🦙 Ollama")
        self.tab_bar.addTab("🐝 ByteSwarm GUI")
        self.tab_bar.setStyleSheet(
            "QTabBar::tab { background:#f0f0f0; color:#555; border:1px solid #d0d0d0; "
            "border-bottom:none; border-top-left-radius:6px; border-top-right-radius:6px; "
            "padding:6px 12px; margin-right:2px; font-size:11px; }"
            "QTabBar::tab:selected { background:#ffffff; color:#16a34a; "
            "border-bottom:2px solid #16a34a; font-weight:bold; }"
            "QTabBar::tab:hover { background:#e8e8ec; }"
        )
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self.tab_bar)

        self.log_stack = QStackedWidget()
        self.logs = {}
        categories = ["ollama", "byteswarm"]
        colors = {
            "ollama": "#a6e3a1",
            "byteswarm": "#f9e2af"
        }

        for cat in categories:
            log_widget = QTextEdit()
            log_widget.setReadOnly(True)
            log_widget.setStyleSheet(
                f"QTextEdit {{ background:#fafafa; color:#1a1a1a; border:none; "
                f"font-family:'JetBrains Mono','Consolas',monospace; font-size:11px; "
                f"padding:8px; }}"
            )
            sample = self._get_sample_log(cat, colors[cat])
            log_widget.setPlainText(sample)
            self.logs[cat] = log_widget
            self.log_stack.addWidget(log_widget)

        lay.addWidget(self.log_stack, stretch=1)

    def _get_sample_log(self, category, color):
        samples = {
            "ollama": f"[{color}] 2026-11-01 11:43:15 [INFO]  Model loaded: qwen2.5-coder:1.5b\n"
                     f"[{color}] 2026-11-01 11:43:16 [DEBUG] GPU memory: 2.1G / 4G\n"
                     f"[{color}] 2026-11-01 11:43:17 [INFO]  Inference: 12.5 tok/s\n"
                     f"[{color}] 2026-11-01 11:43:18 [WARNING] KV cache at 65%\n",
            "byteswarm": f"[{color}] 2026-11-01 11:44:00 [INFO]  GUI initialized\n"
                        f"[{color}] 2026-11-01 11:44:01 [INFO]  Orchestrator started\n"
                        f"[{color}] 2026-11-01 11:44:02 [DEBUG] Task queue: 3 pending\n"
                        f"[{color}] 2026-11-01 11:44:15 [SUCCESS] Security audit passed\n"
        }
        return samples.get(category, "")

    def _on_tab_changed(self, index):
        self.log_stack.setCurrentIndex(index)


# ═══════════════════════════════════════════════════════════════
# BACKUP CODE LOGS (GitHub/GitLab/Git)
# ═══════════════════════════════════════════════════════════════
class BackupCodeLogs(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backup_logs")
        self.setStyleSheet(
            "QFrame#backup_logs { background:#ffffff; border:1px solid #e0e0e0; "
            "border-radius:6px; }"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QLabel("<b>💾 Backup Code — Git Logs</b>")
        header.setStyleSheet("background:#f0f0f0; padding:8px 12px; font-size:12px; border-bottom:1px solid #e0e0e0;")
        lay.addWidget(header)

        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.setMovable(False)
        self.tab_bar.addTab("🐙 GitHub")
        self.tab_bar.addTab("🦊 GitLab")
        self.tab_bar.addTab(" Git")
        self.tab_bar.setStyleSheet(
            "QTabBar::tab { background:#f0f0f0; color:#555; border:1px solid #d0d0d0; "
            "border-bottom:none; border-top-left-radius:6px; border-top-right-radius:6px; "
            "padding:6px 12px; margin:2px; font-size:11px; }"
            "QTabBar::tab:selected { background:#ffffff; color:#2563eb; "
            "border-bottom:2px solid #2563eb; font-weight:bold; }"
        )
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self.tab_bar)

        self.log_stack = QStackedWidget()
        self.logs = {}
        categories = ["github", "gitlab", "git"]
        colors = {
            "github": "#89b4fa",
            "gitlab": "#f38ba8",
            "git": "#fab387"
        }

        for cat in categories:
            log_widget = QTextEdit()
            log_widget.setReadOnly(True)
            log_widget.setStyleSheet(
                f"QTextEdit {{ background:#fafafa; color:#1a1a1a; border:none; "
                f"font-family:'JetBrains Mono','Consolas',monospace; font-size:11px; "
                f"padding:8px; }}"
            )
            sample = self._get_sample_log(cat, colors[cat])
            log_widget.setPlainText(sample)
            self.logs[cat] = log_widget
            self.log_stack.addWidget(log_widget)

        lay.addWidget(self.log_stack, stretch=1)

    def _get_sample_log(self, category, color):
        samples = {
            "github": f"[{color}] 2026-11-01 11:40:15 [INFO]  Push to main branch\n"
                     f"[{color}] 2026-11-01 11:40:16 [INFO]  CI pipeline triggered\n"
                     f"[{color}] 2026-11-01 11:40:18 [DEBUG] Running tests (3/15)\n"
                     f"[{color}] 2026-11-01 11:40:22 [SUCCESS] All tests passed\n",
            "gitlab": f"[{color}] 2026-11-01 11:38:10 [INFO]  MR !42 merged\n"
                     f"[{color}] 2026-11-01 11:38:12 [INFO]  Pipeline #1234 started\n"
                     f"[{color}] 2026-11-01 11:38:45 [WARNING] Coverage dropped to 82%\n"
                     f"[{color}] 2026-11-01 11:39:01 [SUCCESS] Deployment to staging\n",
            "git": f"[{color}] 2026-11-01 11:35:00 [INFO]  Commit: a1b2c3d - Fix bug in parser\n"
                  f"[{color}] 2026-11-01 11:35:01 [INFO]  Branch: feature/usb-reverse\n"
                  f"[{color}] 2026-11-01 11:35:02 [DEBUG] 3 files changed, +45 -12\n"
                  f"[{color}] 2026-11-01 11:42:00 [INFO]  Pull from origin/main successful\n"
        }
        return samples.get(category, "")

    def _on_tab_changed(self, index):
        self.log_stack.setCurrentIndex(index)


# ═══════════════════════════════════════════════════════════════
# CODE EXPLORER
# ═══════════════════════════════════════════════════════════════
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


class CodeExplorer(QFrame):
    node_clicked = pyqtSignal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("code_explorer")
        self.setStyleSheet(
            "QFrame#code_explorer { background:#ffffff; border:1px solid #e0e0e0; "
            "border-radius:6px; }"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(QLabel("<b>🎮 Code Explorer</b>"))
        head.addStretch()

        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(26, 26)
        zoom_in.setToolTip("Zoom in")
        head.addWidget(zoom_in)

        zoom_out = QPushButton("-")
        zoom_out.setFixedSize(26, 26)
        zoom_out.setToolTip("Zoom out")
        head.addWidget(zoom_out)

        lay.addLayout(head)

        self.file_label = QLabel("Nessun file caricato")
        self.file_label.setStyleSheet("color:#666; font-size:11px;")
        lay.addWidget(self.file_label)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setStyleSheet(
            "QGraphicsView { background:#fafafa; border:1px solid #d0d0d0; "
            "border-radius:6px; }"
        )
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
        text.setStyleSheet("font-size:10px; color:#666;")
        lay.addWidget(text)
        return widget

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


# ══════════════════════════════════════════════════════════════
# FILE EDITOR
# ═══════════════════════════════════════════════════════════════
class FileEditorWidget(QFrame):
    closed = pyqtSignal()
    dock_requested = pyqtSignal()
    undock_requested = pyqtSignal()

    def __init__(self, file_path, docked=False, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._docked = docked
        self.setObjectName("editor_widget")

        if docked:
            self.setStyleSheet("QFrame#editor_widget { background:#ffffff; border-left:1px solid #e0e0e0; }")
        else:
            self.setFixedSize(700, 500)
            self.setStyleSheet("QFrame#editor_widget { background:#ffffff; border:1px solid #e0e0e0; border-radius:12px; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(QLabel(f"<b>📝 {os.path.basename(file_path)}</b>"))
        head.addStretch()

        self.dock_btn = QPushButton("📌 Dock" if not docked else "📌 Undock")
        self.dock_btn.setFixedHeight(28)
        self.dock_btn.setObjectName("dock_btn")
        self.dock_btn.setStyleSheet(
            "QPushButton#dock_btn { background:#2563eb; color:white; border-radius:4px; font-size:11px; padding:0 10px; border:none; }"
            "QPushButton#dock_btn:hover { background:#1d4ed8; }"
        )
        self.dock_btn.clicked.connect(self._on_dock_toggle)
        head.addWidget(self.dock_btn)

        save_btn = QPushButton(" Salva")
        save_btn.setObjectName("primary_btn")
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(self._save)
        head.addWidget(save_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.closed.emit)
        head.addWidget(close_btn)
        lay.addLayout(head)

        path_lbl = QLabel(file_path)
        path_lbl.setStyleSheet("color:#888; font-size:10px; font-family:monospace;")
        lay.addWidget(path_lbl)

        self.editor = QTextEdit()
        self.editor.setStyleSheet(
            "QTextEdit { background:#fafafa; color:#1a1a1a; border:1px solid #e0e0e0; "
            "border-radius:6px; font-family:'JetBrains Mono','Consolas',monospace; font-size:12px; padding:8px; }"
        )
        lay.addWidget(self.editor)

        self.status = QLabel("Pronto")
        self.status.setStyleSheet("color:#666; font-size:11px;")
        lay.addWidget(self.status)

        self._load_file()

    def _on_dock_toggle(self):
        if self._docked:
            self.undock_requested.emit()
        else:
            self.dock_requested.emit()

    def _load_file(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                self.editor.setPlainText(f.read())
            self.status.setText(f"Caricato · {len(self.editor.toPlainText())} caratteri")
        except Exception as e:
            self.editor.setPlainText(f"[Errore lettura: {e}]")
            self.status.setText("Errore")

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.status.setText(f"✓ Salvato · {len(self.editor.toPlainText())} caratteri")
        except Exception as e:
            self.status.setText(f"✕ Errore: {e}")


# ═══════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════
class ControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BYTE-SWARMY · Control Center")
        self.resize(1450, 900)
        self.setStyleSheet(self._light_theme())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.drawer = FileTreeDrawer(self)
        self.center = CenterArea(self)

        root.addWidget(self._build_toolbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.drawer)
        body.addWidget(self.center, stretch=1)
        root.addLayout(body, stretch=1)

        root.addWidget(self._build_command_bar())

        self._cpu_temp = 45
        self._gpu_temp = 38
        self._tok_s = 12.5
        self._kv = "2.1G"
        self._mem = 65
        self._freq = 800
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_metrics)
        self._timer.start(1500)

        self._editor_overlay = None
        self._editor_docked = None

    def _build_toolbar(self):
        bar = QFrame()
        bar.setObjectName("toolbar")
        bar.setFixedHeight(64)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        menu_btn = QPushButton("☰")
        menu_btn.setFixedSize(32, 32)
        menu_btn.setObjectName("icon_btn")
        menu_btn.clicked.connect(self._show_context_menu)
        lay.addWidget(menu_btn)

        bee_btn = QPushButton("")
        bee_btn.setFixedSize(32, 32)
        bee_btn.setObjectName("icon_btn")
        bee_btn.clicked.connect(self.drawer.toggle)
        lay.addWidget(bee_btn)

        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setStyleSheet("background:#ddd;")
        lay.addWidget(sep1)

        self.project_tabs = ProjectTabBar()
        self.project_tabs.addTab("🔒 reverse-usb-engineering")
        self.project_tabs.addTab("📦 firmware-parser")
        self.project_tabs.addTab("🧪 test-sandbox")
        self.project_tabs.setCurrentIndex(0)
        lay.addWidget(self.project_tabs, stretch=1)

        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setStyleSheet("background:#ddd;")
        lay.addWidget(sep2)

        self.device_panel = DevicePanel()
        lay.addWidget(self.device_panel)

        return bar

    def _show_context_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; border:1px solid #e0e0e0; border-radius:8px; "
            "padding:8px; font-size:13px; }"
            "QMenu::item { padding:8px 24px; border-radius:4px; }"
            "QMenu::item:selected { background:#f0f9ff; color:#16a34a; }"
        )

        act_pause = QAction("⏸ Pausa orchestratore", self)
        act_pause.triggered.connect(self._toggle_orchestrator)
        menu.addAction(act_pause)

        menu.addSeparator()

        act_logs = QAction("📊 Log Ollama/GUI", self)
        act_logs.triggered.connect(lambda: self.center.main_tabs.setCurrentIndex(0))
        menu.addAction(act_logs)

        act_backup = QAction("💾 Backup Code Logs", self)
        act_backup.triggered.connect(lambda: self.center.main_tabs.setCurrentIndex(1))
        menu.addAction(act_backup)

        act_settings = QAction("⚙️ Impostazioni", self)
        act_settings.triggered.connect(lambda: self.center._open_panel("config"))
        menu.addAction(act_settings)

        menu.addSeparator()

        quit_action = QWidgetAction(self)
        quit_label = QLabel(" Esci")
        quit_label.setStyleSheet("color:#dc2626; font-weight:bold; padding:6px 20px;")
        quit_label.mousePressEvent = lambda e: self.close()
        quit_action.setDefaultWidget(quit_label)
        menu.addAction(quit_action)

        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))

    def _toggle_orchestrator(self):
        btn = self.device_panel.toggle_btn
        if btn.text() == "▶":
            btn.setText("⏸")
            btn.setStyleSheet("QPushButton#primary_btn { background:#f59e0b; color:white; font-weight:bold; font-size:14px; border-radius:6px; border:none; }")
        else:
            btn.setText("▶")
            btn.setStyleSheet("QPushButton#primary_btn { background:#16a34a; color:white; font-weight:bold; font-size:16px; border-radius:6px; border:none; }")

    def _tick_metrics(self):
        self._cpu_temp = max(35, min(75, self._cpu_temp + random.randint(-3, 4)))
        self._gpu_temp = max(30, min(65, self._gpu_temp + random.randint(-2, 3)))
        self._tok_s = round(max(0, self._tok_s + random.uniform(-2, 2)), 1)
        self._freq = random.choice([800, 1200, 1800, 2200, 2400])

        cpu = self.device_panel.cpu_box
        cpu._temp.setText(f"{self._cpu_temp}°C")
        cpu._tok.setText(f"{self._tok_s:.0f}t/s")
        cpu._kv.setText(self._kv)
        cpu._mem.setText(f"{self._mem}%")
        cpu._bus.setText(f"{self._freq}M")

        gpu = self.device_panel.gpu_box
        gpu._temp.setText(f"{self._gpu_temp}°C")
        gpu._tok.setText(f"{self._tok_s*0.3:.1f}t/s")
        gpu._kv.setText("0B")
        gpu._mem.setText("12%")
        gpu._bus.setText("—")

    def _build_command_bar(self):
        bar = QFrame()
        bar.setObjectName("command_bar")
        bar.setFixedHeight(52)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)

        cmd = QLineEdit()
        cmd.setPlaceholderText("Comando o prompt (premi Invia; validazione pre-flight automatica)")
        lay.addWidget(cmd)

        send = QPushButton("Invia")
        send.setObjectName("primary_btn")
        send.setFixedHeight(34)
        lay.addWidget(send)
        return bar

    def _show_file_editor(self, file_path):
        if self._editor_docked:
            self._editor_docked.file_path = file_path
            self._editor_docked._load_file()
            self.center.code_explorer.load_file(file_path)
            return

        if self._editor_overlay:
            self._editor_overlay.close()
            self._editor_overlay.deleteLater()

        self._editor_overlay = FileEditorWidget(file_path, docked=False, parent=self.centralWidget())
        self._editor_overlay.closed.connect(self._close_overlay)
        self._editor_overlay.dock_requested.connect(lambda: self._dock_editor(file_path))

        cw = self.centralWidget().size()
        self._editor_overlay.move(
            (cw.width() - self._editor_overlay.width()) // 2,
            (cw.height() - self._editor_overlay.height()) // 2,
        )
        self._editor_overlay.show()
        self._editor_overlay.raise_()

        self.center.code_explorer.load_file(file_path)

    def _close_overlay(self):
        if self._editor_overlay:
            self._editor_overlay.deleteLater()
            self._editor_overlay = None

    def _dock_editor(self, file_path):
        self._close_overlay()
        self._editor_docked = FileEditorWidget(file_path, docked=True)
        self._editor_docked.closed.connect(self._undock_editor)
        self._editor_docked.undock_requested.connect(lambda: self._undock_editor_to_float(file_path))
        self.center.attach_editor_column(self._editor_docked)

    def _undock_editor(self):
        if self._editor_docked:
            self.center.detach_editor_column()
            self._editor_docked.deleteLater()
            self._editor_docked = None

    def _undock_editor_to_float(self, file_path):
        self.center.detach_editor_column()
        self._editor_docked.deleteLater()
        self._editor_docked = None
        self._show_file_editor(file_path)

    def _light_theme(self):
        return """
        QMainWindow { background:#ffffff; color:#1a1a1a; }
        QFrame#toolbar   { background:#f5f5f7; border-bottom:1px solid #e0e0e0; }
        QFrame#command_bar { background:#f5f5f7; border-top:1px solid #e0e0e0; }
        QPushButton {
            background:#e8e8ec; color:#1a1a1a; border:none;
            padding:6px 12px; border-radius:6px; font-size:12px;
        }
        QPushButton:hover { background:#d8d8dc; }
        QPushButton#icon_btn { background:transparent; font-size:18px; }
        QPushButton#icon_btn:hover { background:#e8e8ec; }
        QPushButton#primary_btn { background:#16a34a; color:white; font-weight:bold; }
        QPushButton#primary_btn:hover { background:#15803d; }
        QLineEdit {
            background:#ffffff; color:#1a1a1a; border:1px solid #d0d0d0;
            padding:8px 12px; border-radius:6px; font-size:13px;
        }
        QLineEdit:focus { border-color:#16a34a; }
        QTextEdit, QPlainTextEdit {
            background:#fafafa; color:#1a1a1a; border:1px solid #e0e0e0;
            font-family:'JetBrains Mono','Consolas',monospace; font-size:11px;
        }
        QLabel { color:#1a1a1a; }
        QTreeView {
            background:#fafafa; color:#1a1a1a; border:none;
            font-size:12px; padding:4px;
        }
        QTreeView::item:hover { background:#f0f0f0; }
        QTreeView::item:selected { background:#e0f2fe; }
        QHeaderView::section { background:#f5f5f7; color:#666; border:none; padding:4px; }
        QTabBar::tab {
            background:#e8e8ec; color:#555; border:1px solid #d0d0d0;
            border-bottom:none; border-top-left-radius:6px; border-top-right-radius:6px;
            padding:6px 14px; margin-right:2px; font-size:12px;
        }
        QTabBar::tab:selected {
            background:#ffffff; color:#16a34a; border-bottom:2px solid #16a34a; font-weight:bold;
        }
        QTabBar::tab:hover { background:#f0f0f0; }
        """


class ProjectTabBar(QTabBar):
    def __init__(self):
        super().__init__()
        self.setDrawBase(False)
        self.setTabsClosable(False)
        self.setMovable(True)
        self.setExpanding(False)


class FileTreeDrawer(QFrame):
    def __init__(self, parent):
        super().__init__()
        self.setObjectName("drawer")
        self.setFixedWidth(280)
        self.setStyleSheet("QFrame#drawer { background:#fafafa; border-right:1px solid #e0e0e0; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(0)

        header = QLabel("<b>🐝 BYTE-SWARMY</b>")
        header.setStyleSheet("padding:8px 16px; color:#16a34a; font-size:13px;")
        lay.addWidget(header)

        self.tree = QTreeView()
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.model = QFileSystemModel()
        self.model.setRootPath("./")
        self.model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index("./"))
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.tree.clicked.connect(self._on_tree_click)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        lay.addWidget(self.tree)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#e0e0e0; margin:8px 12px;")
        lay.addWidget(sep)

        task_header = QLabel("<b> TASK</b>")
        task_header.setStyleSheet("padding:4px 16px; color:#2563eb; font-size:12px;")
        lay.addWidget(task_header)

        self.task_list = QWidget()
        task_lay = QVBoxLayout(self.task_list)
        task_lay.setContentsMargins(12, 4, 12, 4)
        task_lay.setSpacing(4)

        tasks = [
            ("✓", "refactoring.py", "ok", "#16a34a"),
            ("▶", "analyze_usb.py", "run", "#f59e0b"),
            ("○", "new_feature.py", "q", "#888"),
        ]
        for icon, name, status, color in tasks:
            row = QHBoxLayout()
            row.setContentsMargins(4, 2, 4, 2)
            ic = QLabel(icon)
            ic.setStyleSheet(f"color:{color}; font-weight:bold;")
            ic.setFixedWidth(20)
            row.addWidget(ic)
            nm = QLabel(name)
            nm.setStyleSheet("color:#333; font-size:11px;")
            row.addWidget(nm, stretch=1)
            st = QLabel(status)
            st.setStyleSheet(f"color:{color}; font-size:10px; background:#f0f0f0; padding:2px 6px; border-radius:4px;")
            row.addWidget(st)
            task_lay.addLayout(row)

        task_lay.addStretch()
        lay.addWidget(self.task_list, stretch=1)

        act = QHBoxLayout()
        act.setContentsMargins(12, 8, 12, 8)
        ref = QPushButton("🔄")
        ref.setFixedWidth(36)
        ref.clicked.connect(lambda: self.model.setRootPath("./"))
        act.addWidget(ref)
        close = QPushButton("✕ Chiudi")
        close.setStyleSheet("color:#dc2626;")
        close.clicked.connect(self.toggle)
        act.addWidget(close, stretch=1)
        lay.addLayout(act)

        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._open = True
        self.main_win = parent

    def _on_tree_click(self, index):
        path = self.model.filePath(index)
        if os.path.isfile(path):
            self.main_win._show_file_editor(path)

    def _on_tree_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        path = self.model.filePath(index)
        is_file = os.path.isfile(path)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; border:1px solid #e0e0e0; border-radius:8px; padding:6px; font-size:12px; }"
            "QMenu::item { padding:6px 20px; border-radius:4px; }"
            "QMenu::item:selected { background:#f0f9ff; }"
        )

        if is_file:
            act_edit = QAction("✏️ Modifica file", self)
            act_edit.triggered.connect(lambda: self.main_win._show_file_editor(path))
            menu.addAction(act_edit)
            menu.addSeparator()

        act_rename = QAction("📝 Rinomina", self)
        act_rename.triggered.connect(lambda: self._rename_item(path))
        menu.addAction(act_rename)

        act_delete = QAction("️ Cancella", self)
        act_delete.triggered.connect(lambda: self._delete_item(path))
        menu.addAction(act_delete)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _rename_item(self, path):
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(path), new_name)
            try:
                os.rename(path, new_path)
                self.model.setRootPath("./")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile rinominare:\n{e}")

    def _delete_item(self, path):
        name = os.path.basename(path)
        reply = QMessageBox.question(self, "Conferma cancellazione", f"Sei sicuro di voler eliminare '{name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    import shutil
                    shutil.rmtree(path)
                self.model.setRootPath("./")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile eliminare:\n{e}")

    def toggle(self):
        self._open = not self._open
        target = 0 if self._open else 280
        self._anim.setStartValue(280 if self._open else 0)
        self._anim.setEndValue(target)
        self._anim.start()


class CenterArea(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.main_win = parent
        self._editor_column = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.main_content = QWidget()
        main_lay = QVBoxLayout(self.main_content)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(12)

        # Tabs principali: Logs | Backup Code
        self.main_tabs = QTabBar()
        self.main_tabs.addTab(" Logs CI/CD")
        self.main_tabs.addTab("💾 Backup Code")
        self.main_tabs.setStyleSheet(
            "QTabBar::tab { background:#e8e8ec; color:#555; border:1px solid #d0d0d0; "
            "border-bottom:none; border-top-left-radius:6px; border-top-right-radius:6px; "
            "padding:8px 16px; margin-right:2px; font-size:12px; }"
            "QTabBar::tab:selected { background:#ffffff; color:#16a34a; border-bottom:2px solid #16a34a; font-weight:bold; }"
        )
        main_lay.addWidget(self.main_tabs)

        # Stack per i tab
        self.content_stack = QStackedWidget()

        # Tab 1: Logs (Ollama + ByteSwarm)
        self.log_viewer = CategorizedLogViewer()
        self.content_stack.addWidget(self.log_viewer)

        # Tab 2: Backup Code (GitHub/GitLab/Git)
        self.backup_logs = BackupCodeLogs()
        self.content_stack.addWidget(self.backup_logs)

        main_lay.addWidget(self.content_stack, stretch=1)
        self.main_tabs.currentChanged.connect(self.content_stack.setCurrentIndex)

        # PLANCIA con Code Explorer integrato
        plancia_widget = QWidget()
        plancia_lay = QVBoxLayout(plancia_widget)
        plancia_lay.setContentsMargins(0, 0, 0, 0)
        plancia_lay.setSpacing(12)

        # Header Plancia
        plancia_header = QLabel("✈️ Plancia di controllo")
        plancia_header.setStyleSheet("font-size:14px; font-weight:bold; color:#2563eb; padding:4px 0;")
        plancia_lay.addWidget(plancia_header)

        # Grid per le card (automatizzata, 3 colonne)
        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(12)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)

        # Card collapsibili
        self.cards = {}
        card_configs = [
            ("coda", "📋 Coda Task", "3 in coda", "3 tasks", "#f59e0b", 0, 0),
            ("modelli", "🤖 Modelli", "4 caricati", "4 loaded", "#2563eb", 0, 1),
            ("config", "⚙️ Config", "security: ON", "secure", "#16a34a", 0, 2),
        ]

        for key, title, subtitle, badge, badge_color, row, col in card_configs:
            card = CollapsibleCard(title, subtitle, badge=badge, badge_color=badge_color)
            card.clicked.connect(lambda k=key: self._open_panel(k))
            self.cards[key] = card
            self.cards_grid.addWidget(card, row, col)

        plancia_lay.addLayout(self.cards_grid)

        # Code Explorer integrato nella Plancia
        self.code_explorer = CodeExplorer()
        self.code_explorer.setFixedHeight(350)
        plancia_lay.addWidget(self.code_explorer)

        # Aggiungi plancia allo stack dei contenuti (nascosta di default)
        self.content_stack.addWidget(plancia_widget)

        root.addWidget(self.main_content, stretch=1)

        # Pagine funzionali (dettagli)
        self.stack = QStackedWidget()
        self.stack.hide()
        root.addWidget(self.stack)

        self.panel_pages = {}
        for key, title, content in [
            ("coda", "📋 Coda Task", "3 task in coda"),
            ("modelli", "🤖 Modelli", "qwen2.5-coder:1.5b active"),
            ("config", "⚙️ Config", "security: enabled"),
        ]:
            page = self._build_panel_page(title, content, key)
            self.panel_pages[key] = page
            self.stack.addWidget(page)

    def attach_editor_column(self, editor_widget):
        if self._editor_column:
            self._editor_column.deleteLater()
        self._editor_column = editor_widget
        self._editor_column.setFixedWidth(500)
        self.layout().addWidget(self._editor_column)

    def detach_editor_column(self):
        if self._editor_column:
            self.layout().removeWidget(self._editor_column)
            self._editor_column = None

    def _open_panel(self, key):
        if key in self.panel_pages:
            self.main_content.hide()
            self.stack.setCurrentWidget(self.panel_pages[key])
            self.stack.show()

    def _build_panel_page(self, title, content, key):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        head = QHBoxLayout()
        back = QPushButton("← Indietro")
        back.clicked.connect(self._back_to_plancia)
        head.addWidget(back)
        head.addStretch()
        head.addWidget(QLabel(f"<b style='font-size:18px;'>{title}</b>"))
        head.addStretch()
        lay.addLayout(head)

        body = QLabel(content)
        body.setStyleSheet("font-size:14px; color:#333; padding:20px; background:#f8f9fa; border-radius:8px; border:1px solid #e0e0e0;")
        body.setWordWrap(True)
        lay.addWidget(body, stretch=1)
        return page

    def _back_to_plancia(self):
        self.stack.hide()
        self.main_content.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ControlCenter()
    w.show()
    sys.exit(app.exec())
