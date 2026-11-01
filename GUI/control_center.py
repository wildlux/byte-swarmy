#!/usr/bin/env python3
"""
BYTE-SWARMY Control Center — Sezioni collassabili + Credits overlay
PyQt6, single-file
"""

import sys
import os
import random
import subprocess
import ast
import re
import json
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGridLayout, QStackedWidget, QPushButton, QLabel,
    QLineEdit, QTextEdit, QPlainTextEdit, QFrame, QToolBar, QStatusBar,
    QMenuBar, QDockWidget, QTabWidget, QTabBar, QScrollArea, QSplitter,
    QCheckBox, QComboBox, QSpinBox, QSlider, QProgressBar, QGroupBox,
    QRadioButton, QButtonGroup, QFileDialog, QMessageBox, QInputDialog,
    QMenu, QToolButton, QStyle, QStyleFactory, QSpacerItem,
    QSizePolicy, QAbstractItemView, QHeaderView, QListWidget,
    QListWidgetItem, QTreeView, QWidgetAction, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem
)
from PyQt6.QtGui import (
    QColor, QCursor, QFont, QIcon, QPixmap, QPalette, QAction,
    QBrush, QPainter, QPen
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QDir, QTimer, 
)

from GUI.gui_backend import (
    get_cpu_temp, get_gpu_temp, get_metrics, get_tasks, get_logs,
    add_task_to_db
)

# QFileSystemModel fallback (posizione varia tra versioni PyQt6)
try:
    from PyQt6.QtWidgets import QFileSystemModel
except ImportError:
    try:
        from PyQt6.QtCore import QFileSystemModel
    except ImportError:
        try:
            from PyQt6.QtGui import QFileSystemModel
        except ImportError:
            from PyQt6.QtGui import QStandardItemModel
            from PyQt6.QtCore import QModelIndex
            class QFileSystemModel(QStandardItemModel):
                """Fallback QFileSystemModel per PyQt6 senza il vero modulo."""
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._root_path = ""
                def setRootPath(self, path):
                    self._root_path = path
                def rootPath(self):
                    return self._root_path
                def filePath(self, index):
                    return self._root_path


# ═══════════════════════════════════════════════════════════════
# CREDITS OVERLAY (schermata ringraziamenti)
# ═══════════════════════════════════════════════════════════════
class CreditsOverlay(QFrame):
    """Overlay modale con i ringraziamenti del progetto."""
    closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("credits_overlay")
        self.setFixedSize(620, 520)
        self.setStyleSheet(
            "QFrame#credits_overlay { "
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "    stop:0 #1e1e2e, stop:0.5 #2a2a3c, stop:1 #1e1e2e); "
            "  border: 2px solid #4ade80; "
            "  border-radius: 16px; "
            "}"
        )
        
        lay = QVBoxLayout(self)
        # Immagine ringraziamenti
        try:
            import os
            from PyQt6.QtGui import QPixmap
            img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'IMG', 'documentazione.jpeg')
            if os.path.exists(img_path):
                img_label = QLabel()
                pix = QPixmap(img_path)
                # Ridimensiona mantenendo aspect ratio
                pix = pix.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
                img_label.setPixmap(pix)
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lay.addWidget(img_label)
        except Exception as e:
            print(f"Errore caricamento immagine credits: {e}")
        lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(16)
        
        # Header con ape grande
        bee_header = QLabel("🐝")
        bee_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bee_header.setStyleSheet("font-size: 64px;")
        lay.addWidget(bee_header)
        
        # Titolo
        title = QLabel("<b>BYTE-SWARMY</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 28px; color: #4ade80; font-weight: bold;"
        )
        lay.addWidget(title)
        
        subtitle = QLabel("Autonomous Multi-Agent System")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #a0a0b0; font-style: italic;")
        lay.addWidget(subtitle)
        
        # Separatore
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #4ade80;")
        lay.addWidget(sep)
        
        # Sezione credits
        credits_title = QLabel("✨ Ringraziamenti ✨")
        credits_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_title.setStyleSheet("font-size: 16px; color: #f9e2af; font-weight: bold;")
        lay.addWidget(credits_title)
        
        # Lista contributori
        contributors = [
            ("👤", "Paolo Lo Bello", "Ideatore del progetto", "#4ade80"),
            ("🤖", "GLM 5.2", "Codice iniziale", "#89b4fa"),
            ("🦙", "Qwen", "Miglioramento e ottimizzazione interfaccia grafica", "#f9e2af"),
            ("🔍", "DeepSeek", "Analisi della sicurezza", "#f38ba8"),
        ]
        
        for icon, name, role, color in contributors:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: #0f0f19; border-left: 3px solid {color}; "
                f"border-radius: 6px; padding: 8px 12px; }}"
            )
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(10, 8, 10, 8)
            card_lay.setSpacing(12)
            
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size: 22px;")
            icon_lbl.setFixedWidth(32)
            card_lay.addWidget(icon_lbl)
            
            info = QWidget()
            info_lay = QVBoxLayout(info)
            info_lay.setContentsMargins(0, 0, 0, 0)
            info_lay.setSpacing(2)
            
            name_lbl = QLabel(f"<b>{name}</b>")
            name_lbl.setStyleSheet(f"font-size: 14px; color: {color};")
            info_lay.addWidget(name_lbl)
            
            role_lbl = QLabel(role)
            role_lbl.setStyleSheet("font-size: 11px; color: #c0c0d0;")
            info_lay.addWidget(role_lbl)
            
            card_lay.addWidget(info, stretch=1)
            lay.addWidget(card)
        
        # Messaggio finale
        final_msg = QLabel("Grazie a tutti per aver contribuito a questo progetto 🐝")
        final_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        final_msg.setStyleSheet("font-size: 12px; color: #8888a0; font-style: italic; margin-top: 8px;")
        lay.addWidget(final_msg)
        
        lay.addStretch()
        
        # Pulsante chiudi
        close_btn = QPushButton("✕ Chiudi")
        close_btn.setObjectName("credits_close_btn")
        close_btn.setStyleSheet(
            "QPushButton#credits_close_btn { "
            "  background: #4ade80; color: #0f0f19; "
            "  border: none; border-radius: 8px; "
            "  padding: 10px 24px; font-size: 13px; font-weight: bold; "
            "}"
            "QPushButton#credits_close_btn:hover { background: #6ee7a0; }"
        )
        close_btn.clicked.connect(self.closed.emit)
        lay.addWidget(close_btn)
    
    def showEvent(self, event):
        """Animazione fade-in all'apertura."""
        super().showEvent(event)
        self.setWindowOpacity(0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(250)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()


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
# SEZIONE COLLABILE
# ═══════════════════════════════════════════════════════════════
class CollapsibleSection(QFrame):
    def __init__(self, title, icon="📁", parent=None):
        super().__init__(parent)
        self.setObjectName("collapsible_section")
        self.setStyleSheet(
            "QFrame#collapsible_section { background:#ffffff; border:1px solid #e0e0e0; "
            "border-radius:8px; }"
        )
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        
        self.header = QFrame()
        self.header.setObjectName("section_header")
        self.header.setStyleSheet(
            "QFrame#section_header { background:#f5f5f7; border-bottom:1px solid #e0e0e0; "
            "border-top-left-radius:8px; border-top-right-radius:8px; }"
        )
        header_lay = QHBoxLayout(self.header)
        header_lay.setContentsMargins(14, 10, 14, 10)
        header_lay.setSpacing(8)
        
        self.title_lbl = QLabel(f"{icon} {title}")
        self.title_lbl.setStyleSheet("font-size:13px; font-weight:bold; color:#1a1a1a;")
        header_lay.addWidget(self.title_lbl, stretch=1)
        
        self.toggle_btn = QPushButton("▾")
        self.toggle_btn.setFixedSize(28, 28)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background:#e8e8ec; border:none; border-radius:4px; "
            "font-size:12px; font-weight:bold; }"
            "QPushButton:hover { background:#d0d0d0; }"
        )
        self.toggle_btn.clicked.connect(self._on_toggle)
        header_lay.addWidget(self.toggle_btn)
        
        lay.addWidget(self.header)
        
        self.content = QWidget()
        self.content.setStyleSheet("background:#ffffff; border-bottom-left-radius:8px; border-bottom-right-radius:8px;")
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(12, 12, 12, 12)
        self.content_lay.setSpacing(8)
        
        lay.addWidget(self.content)
        
        self._expanded = True
    
    def _on_toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.content.show()
            self.toggle_btn.setText("▾")
        else:
            self.content.hide()
            self.toggle_btn.setText("▸")
    
    def add_widget(self, widget):
        self.content_lay.addWidget(widget)


# ═══════════════════════════════════════════════════════════════
# CARD PLANCIA
# ═══════════════════════════════════════════════════════════════
class PlanciaCard(QFrame):
    clicked = pyqtSignal()
    
    def __init__(self, title, subtitle, badge=None, badge_color="#666", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(90)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        
        head = QHBoxLayout()
        head.setSpacing(6)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:14px; font-weight:bold; color:#1a1a1a;")
        head.addWidget(title_lbl, stretch=1)
        
        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setStyleSheet(
                f"background:{badge_color}22; color:{badge_color}; "
                f"padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;"
            )
            head.addWidget(badge_lbl)
        
        lay.addLayout(head)
        
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("font-size:11px; color:#666;")
        lay.addWidget(sub_lbl)
        
        lay.addStretch()
        
        self._normal_style = (
            "QFrame#card { background:#ffffff; border:1px solid #e0e0e0; border-radius:10px; }"
        )
        self._hover_style = (
            "QFrame#card { background:#f0f9ff; border:1px solid #16a34a; border-radius:10px; }"
        )
        self.setStyleSheet(self._normal_style)
    
    def enterEvent(self, event):
        self.setStyleSheet(self._hover_style)
    
    def leaveEvent(self, event):
        self.setStyleSheet(self._normal_style)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ═══════════════════════════════════════════════════════════════
# LOG CATEGORIZZATO
# ═══════════════════════════════════════════════════════════════
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
        colors = {"ollama": "#a6e3a1", "byteswarm": "#f9e2af"}
        
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
        # SOSTITUISCI i log finti con log reali
        if category == "byteswarm":
            return get_logs(50)
        return ""

    def _on_tab_changed(self, index):
        self.log_stack.setCurrentIndex(index)


# ═══════════════════════════════════════════════════════════════
# BACKUP CODE LOGS
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
        self.tab_bar.addTab("📂 Git")
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
        colors = {"github": "#89b4fa", "gitlab": "#f38ba8", "git": "#fab387"}
        
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


# ═══════════════════════════════════════════════════════════════
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
        
        save_btn = QPushButton("💾 Salva")
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
class ConfigPanel(QFrame):
    """Pannello configurazione con tutti i parametri modificabili."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("config_panel")
        self._widgets = {}  # path -> widget
        self._build_ui()
    
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        
        # Header
        title = QLabel("⚙ Configurazione BYTE-SWARMY")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#1a1a1a;")
        lay.addWidget(title)
        
        sub = QLabel("Modifica i parametri e premi 'Salva' per applicare. "
                     "Backup automatico in config.toml.bak")
        sub.setStyleSheet("font-size:11px; color:#666;")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        
        # Scroll area con i parametri
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        container = QWidget()
        container_lay = QVBoxLayout(container)
        container_lay.setSpacing(12)
        
        # Carica config
        try:
            from GUI.gui_backend import load_config
            self._config = load_config()
        except Exception as e:
            self._config = {}
            container_lay.addWidget(QLabel(f"Errore lettura config: {e}"))
        
        # Definizione sezioni da mostrare (con campi)
        sections = [
            ("🧠 Modelli LLM", "models", [
                ("Orchestratore", "orchestrator", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("top_p", "Top P", "spin_float", (0.0, 1.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
                ]),
                ("Planner", "planner", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
                ]),
                ("Worker Coder", "worker_coder", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
                ]),
                ("Worker General", "worker_general", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
                ]),
                ("Embedding", "embedding", [
                    ("name", "Modello embedding", "combo", []),
                ]),
            ]),
            ("🌡️ Thermal (Timestral)", "thermal", [
                ("enabled", "Abilitato", "check", None),
                ("sample_interval", "Intervallo campionamento (s)", "spin_int", (1, 3600, 1)),
            ]),
            ("🌡️ Soglie termiche", "thermal.thresholds", [
                ("temp_cold", "Temp fredda (°C)", "spin_float", (0, 100, 1)),
                ("temp_warm", "Temp calda (°C)", "spin_float", (0, 100, 1)),
                ("temp_hot", "Temp molto calda (°C)", "spin_float", (0, 100, 1)),
                ("temp_critical", "Temp critica (°C)", "spin_float", (0, 110, 1)),
                ("gpu_temp_critical", "GPU critica (°C)", "spin_float", (0, 110, 1)),
                ("cpu_pause_threshold", "CPU pause %", "spin_float", (0.5, 1.0, 0.05)),
            ]),
            ("⏱️ Timing", "timing", [
                ("orchestrator_tick", "Tick orchestratore (s)", "spin_int", (5, 3600, 5)),
                ("worker_tick", "Tick worker (s)", "spin_int", (5, 3600, 5)),
                ("health_check", "Health check (s)", "spin_int", (30, 7200, 30)),
                ("memory_compaction", "Compaction memory (s)", "spin_int", (60, 86400, 60)),
            ]),
            ("🛡️ Safety", "safety", [
                ("sandbox_enabled", "Sandbox bubblewrap", "check", None),
                ("max_attempts", "Max tentativi task", "spin_int", (1, 50, 1)),
                ("max_consecutive_failures", "Max fallimenti consecutivi", "spin_int", (1, 20, 1)),
                ("cooldown_after_failure", "Cooldown dopo fallimento (s)", "spin_int", (10, 3600, 10)),
                ("max_log_size", "Max size log (bytes)", "spin_int", (100000, 100000000, 100000)),
            ]),
            ("🔒 Security", "security", [
                ("enabled", "Security abilitata (ALWAYS-ON)", "check", None),
                ("max_output_chars", "Max caratteri output", "spin_int", (1000, 1000000, 1000)),
                ("max_file_size_write", "Max size file scritto (bytes)", "spin_int", (10000, 100000000, 10000)),
                ("max_memory_mb", "Max memoria MB", "spin_int", (256, 8192, 128)),
            ]),
            ("🎯 Decision Models", "decision_models", [
                ("active", "Modello decisionale attivo", "combo_decision", []),
            ]),
            ("📚 LLM Tuner (profili termici)", "llm_tuner", [
                # Solo informativo — i valori sono commentati nel file
            ]),
        ]
        
        # Lista modelli Ollama disponibili
        try:
            import urllib.request, json
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
                data = json.loads(r.read())
                self._available_models = [m['name'] for m in data.get('models', [])]
        except Exception:
            self._available_models = ["qwen2.5:1.5b", "qwen2.5-coder:1.5b",
                                      "tev1:4b", "nomic-embed-text"]
        
        # Costruisci le sezioni
        for section_title, section_path, fields in sections:
            section_widget = self._build_section(section_title, section_path, fields)
            container_lay.addWidget(section_widget)
        
        container_lay.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, stretch=1)
        
        # Bottoni Salva / Ripristina / Applica
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        self.save_btn = QPushButton("💾 Salva")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background:#16a34a; color:white; border:none;
                padding:8px 20px; border-radius:6px; font-weight:bold;
            }
            QPushButton:hover { background:#15803d; }
        """)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)
        
        self.reset_btn = QPushButton("↩ Ripristina")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background:#f5f5f5; color:#333; border:1px solid #ccc;
                padding:8px 20px; border-radius:6px;
            }
            QPushButton:hover { background:#e5e5e5; }
        """)
        self.reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self.reset_btn)
        
        self.apply_btn = QPushButton("🔄 Applica & Riavvia")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background:#f59e0b; color:white; border:none;
                padding:8px 20px; border-radius:6px; font-weight:bold;
            }
            QPushButton:hover { background:#d97706; }
        """)
        self.apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self.apply_btn)
        
        btn_row.addStretch()
        lay.addLayout(btn_row)
    
    def _build_section(self, title, path, fields):
        """Costruisce una sezione collassabile con i campi."""
        section = CollapsibleSection(title, icon="⚙")
        try:
            data = self._get_nested(self._config, path)
        except Exception:
            data = {}
        
        if not data and not fields:
            section.add_widget(QLabel(f"<i>Sezione {path} non presente nel config</i>"))
            return section
        
        form = QFormLayout()
        form.setSpacing(6)
        form.setContentsMargins(8, 8, 8, 8)
        
        for field in fields:
            key, label, widget_type, params = field
            full_path = f"{path}.{key}"
            current_val = data.get(key) if data else None
            
            widget = self._make_widget(widget_type, current_val, params)
            if widget:
                self._widgets[full_path] = widget
                form.addRow(label + ":", widget)
        
        section.add_widget(QWidget() if not fields else self._wrap_form(form))
        return section
    
    def _wrap_form(self, form_layout):
        w = QWidget()
        w.setLayout(form_layout)
        return w
    
    def _make_widget(self, wtype, value, params):
        try:
            if wtype == "check":
                w = QCheckBox()
                w.setChecked(bool(value))
                return w
            elif wtype == "spin_int":
                lo, hi, step = params
                w = QSpinBox()
                w.setRange(lo, hi)
                w.setSingleStep(step)
                w.setValue(int(value) if value is not None else lo)
                return w
            elif wtype == "spin_float":
                lo, hi, step = params
                w = QDoubleSpinBox()
                w.setRange(lo, hi)
                w.setSingleStep(step)
                w.setDecimals(2)
                w.setValue(float(value) if value is not None else lo)
                return w
            elif wtype == "combo":
                w = QComboBox()
                w.addItems(self._available_models)
                if value and value in self._available_models:
                    w.setCurrentText(value)
                elif value:
                    w.addItem(value)
                    w.setCurrentText(value)
                return w
            elif wtype == "combo_decision":
                w = QComboBox()
                options = ["qwen2_5", "tev1", "d3", "nimble"]
                w.addItems(options)
                if value and value in options:
                    w.setCurrentText(value)
                return w
            elif wtype == "line":
                w = QLineEdit()
                w.setText(str(value) if value is not None else "")
                return w
        except Exception as e:
            print(f"Errore make_widget {wtype}: {e}")
        return None
    
    def _get_nested(self, d, path):
        for part in path.split('.'):
            d = d[part]
        return d
    
    def _set_nested(self, d, path, value):
        parts = path.split('.')
        for part in parts[:-1]:
            if part not in d or not isinstance(d[part], dict):
                d[part] = {}
            d = d[part]
        d[parts[-1]] = value
    
    def _collect_values(self):
        """Raccoglie i valori dai widget e aggiorna self._config."""
        for path, widget in self._widgets.items():
            try:
                if isinstance(widget, QCheckBox):
                    val = widget.isChecked()
                elif isinstance(widget, QSpinBox):
                    val = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    val = widget.value()
                elif isinstance(widget, QComboBox):
                    val = widget.currentText()
                elif isinstance(widget, QLineEdit):
                    val = widget.text()
                else:
                    continue
                self._set_nested(self._config, path, val)
            except Exception as e:
                print(f"Errore collect {path}: {e}")
    
    def _save(self):
        self._collect_values()
        try:
            from GUI.gui_backend import save_config
            ok, msg = save_config(self._config)
            if ok:
                self.save_btn.setText("✓ Salvato!")
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1500, lambda: self.save_btn.setText("💾 Salva"))
            else:
                QMessageBox.warning(self, "Errore", msg)
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Salvataggio fallito: {e}")
    
    def _reset(self):
        """Ricarica il config dal file."""
        try:
            from GUI.gui_backend import load_config
            self._config = load_config()
            self._widgets = {}
            # Ricrea la UI
            lay = self.layout()
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._build_ui()
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Reset fallito: {e}")
    
    def _apply(self):
        """Salva e riavvia l'orchestratore."""
        self._save()
        reply = QMessageBox.question(
            self, "Applica & Riavvia",
            "Riavviare l'orchestratore per applicare le modifiche?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import subprocess, os
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                # Ferma e riavvia
                subprocess.Popen([os.path.join(base, 'ferma.sh')])
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: subprocess.Popen([os.path.join(base, 'avvia.sh')]))
                QMessageBox.information(self, "Riavvio", "Orchestratore riavviato!")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Riavvio fallito: {e}")





def _pause_task(task_id):
    """Mette in pausa un singolo task (status='paused')."""
    import sqlite3, os, time
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base, 'tasks', 'queue.db')
    try:
        con = sqlite3.connect(db_path, timeout=10.0)
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='paused' WHERE id=? AND status IN ('pending', 'running')",
            (task_id,)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} in pausa"
    except Exception as e:
        return False, f"Errore: {e}"


def _resume_single_task(task_id):
    """Riprende un singolo task (status='pending')."""
    import sqlite3, os, time
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base, 'tasks', 'queue.db')
    try:
        con = sqlite3.connect(db_path, timeout=10.0)
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='pending' WHERE id=? AND status='paused'",
            (task_id,)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} ripreso"
    except Exception as e:
        return False, f"Errore: {e}"


def _stop_task(task_id):
    """Ferma un singolo task (marca come failed con last_error='Stopped by user')."""
    import sqlite3, os, time
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base, 'tasks', 'queue.db')
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='failed', "
            "last_error='Stopped by user (GUI)', "
            "completed_at=? WHERE id=?",
            (time.time(), task_id)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} fermato"
    except Exception as e:
        return False, f"Errore: {e}"


def _restart_task(task_id):
    """Riavvia un task esistente (cambia status da done/failed a pending)."""
    import sqlite3, time, os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base, 'tasks', 'queue.db')
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute(
            "UPDATE tasks SET status='pending', attempts=0, last_error=NULL, "
            "started_at=NULL, completed_at=NULL WHERE id=?",
            (task_id,)
        )
        con.commit()
        con.close()
        return True, f"Task {task_id[:12]} rimesso in coda"
    except Exception as e:
        return False, f"Errore: {e}"




def _log_user_action(component, action, task_id=None, details=""):
    """Logga le azioni utente in logs/user_actions.log."""
    import os, time, json
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_path = os.path.join(base, 'logs', 'user_actions.log')
    entry = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "epoch": time.time(),
        "component": component,  # "Pulsante-in-Alto_DX" o "Task-Action"
        "action": action,        # "avviato", "fermato", "pausa", "riprendi", "stop"
        "task_id": task_id,
        "details": details,
        "message": ""  # riempito sotto
    }
    # Costruisci messaggio leggibile
    if component == "Pulsante-in-Alto_DX":
        entry["message"] = f"{component} : stato attuale = {action} premuto adesso"
    elif component == "Task-Action":
        tid_short = (task_id or "?")[:15] if task_id else "?"
        entry["message"] = f"Task #{tid_short} ha premuto lo stato di {action}"
    else:
        entry["message"] = f"{component}: {action}"
    try:
        with open(log_path, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # Stampa anche in console
        print(f"[USER_ACTION] {entry['message']}")
    except Exception as e:
        print(f"Errore log user action: {e}")
    return entry["message"]



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
        self._credits_overlay = None
    def _pause_orchestrator(self):
        """Mette in pausa l'orchestratore (crea file state/pause.flag)."""
        try:
            _log_user_action("Sidebar-Orchestratore", "pausa", details="Pausa orchestratore da sidebar")
            import os, time
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pause_file = os.path.join(base, 'state', 'pause.flag')
            with open(pause_file, 'w') as f:
                f.write(str(time.time()))
            if hasattr(self, '_pause_btn'):
                self._pause_btn.setText("▶ Riprendi")
                self._pause_btn.setStyleSheet("QPushButton { background:#16a34a; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; }")
                try: self._pause_btn.clicked.disconnect()
                except Exception: pass
                self._pause_btn.clicked.connect(self._resume_orchestrator)
            self.statusBar().showMessage("⏸ Orchestratore in pausa", 3000)
        except Exception as e:
            print(f"Errore pausa: {e}")

    def _resume_orchestrator(self):
        """Riprende l'orchestratore."""
        try:
            import os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pause_file = os.path.join(base, 'state', 'pause.flag')
            if os.path.exists(pause_file):
                os.remove(pause_file)
            if hasattr(self, '_pause_btn'):
                self._pause_btn.setText("⏸ Pausa")
                self._pause_btn.setStyleSheet("QPushButton { background:#f59e0b; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; }")
                try: self._pause_btn.clicked.disconnect()
                except Exception: pass
                self._pause_btn.clicked.connect(self._pause_orchestrator)
            self.statusBar().showMessage("▶ Orchestratore ripreso", 3000)
        except Exception as e:
            print(f"Errore resume: {e}")

    def _stop_orchestrator(self):
        """Ferma l'orchestratore."""
        try:
            _log_user_action("Sidebar-Orchestratore", "fermato", details="Stop orchestratore da sidebar")
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, "Stop orchestratore",
                "Fermare definitivamente l'orchestratore?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            import os, signal
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pid_file = os.path.join(base, 'state', 'orchestrator.pid')
            if os.path.exists(pid_file):
                pid = int(open(pid_file).read().strip())
                try:
                    os.kill(pid, signal.SIGTERM)
                    self.statusBar().showMessage(f"⏹ Orchestratore fermato", 5000)
                    if hasattr(self, '_pause_btn'): self._pause_btn.setEnabled(False)
                    if hasattr(self, '_stop_btn'): self._stop_btn.setEnabled(False)
                except ProcessLookupError:
                    self.statusBar().showMessage("Processo già terminato", 3000)
        except Exception as e:
            print(f"Errore stop: {e}")


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

        # 🐝 Ape → apre i credits (NON più il drawer)
        bee_btn = QPushButton("🐝")
        bee_btn.setFixedSize(32, 32)
        bee_btn.setObjectName("icon_btn")
        bee_btn.setToolTip("Credits & Ringraziamenti")
        bee_btn.clicked.connect(self._show_credits)
        lay.addWidget(bee_btn)
        
        # Aggiungo un nuovo bottone per il drawer (file tree)
        files_btn = QPushButton("📁")
        files_btn.setFixedSize(32, 32)
        files_btn.setObjectName("icon_btn")
        files_btn.setToolTip("File & Task")
        files_btn.clicked.connect(self.drawer.toggle)
        lay.addWidget(files_btn)

        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setStyleSheet("background:#ddd;")
        lay.addWidget(sep1)

        self.project_tabs = ProjectTabBar()
        self.project_tabs.setCurrentIndex(0)
        lay.addWidget(self.project_tabs, stretch=1)

        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setStyleSheet("background:#ddd;")
        lay.addWidget(sep2)

        self.device_panel = DevicePanel()
        lay.addWidget(self.device_panel)

        return bar
    
        # Pulsanti Pausa/Stop orchestratore
        _spacer = QWidget()
        _spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(_spacer)
        self._pause_btn = QPushButton("⏸ Pausa")
        self._pause_btn.setStyleSheet("QPushButton { background:#f59e0b; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; } QPushButton:hover { background:#d97706; }")
        self._pause_btn.clicked.connect(self._pause_orchestrator)
        lay.addWidget(self._pause_btn)
        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setStyleSheet("QPushButton { background:#dc2626; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; } QPushButton:hover { background:#b91c1c; }")
        self._stop_btn.clicked.connect(self._stop_orchestrator)
        lay.addWidget(self._stop_btn)


    def _show_credits(self):
        """Mostra l'overlay dei ringraziamenti."""
        if self._credits_overlay:
            self._credits_overlay.deleteLater()
        
        self._credits_overlay = CreditsOverlay(self.centralWidget())
        self._credits_overlay.closed.connect(self._close_credits)
        
        # Centra l'overlay
        cw = self.centralWidget().size()
        self._credits_overlay.move(
            (cw.width() - self._credits_overlay.width()) // 2,
            (cw.height() - self._credits_overlay.height()) // 2,
        )
        self._credits_overlay.show()
        self._credits_overlay.raise_()
    
    def _close_credits(self):
        if self._credits_overlay:
            self._credits_overlay.deleteLater()
            self._credits_overlay = None

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

        act_settings = QAction("⚙️ Impostazioni", self)
        act_settings.triggered.connect(lambda: self.center.open_panel("config"))
        menu.addAction(act_settings)

        menu.addSeparator()
        
        act_credits = QAction("🐝 Credits", self)
        act_credits.triggered.connect(self._show_credits)
        menu.addAction(act_credits)

        menu.addSeparator()

        quit_action = QWidgetAction(self)
        quit_label = QLabel("✕ Esci")
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
        self._cpu_temp = get_cpu_temp()
        self._gpu_temp = get_gpu_temp()
        
        metrics = get_metrics()
        self._tok_s = metrics.get("tokens_per_sec", 0) if metrics else 0

        cpu = self.device_panel.cpu_box
        cpu._temp.setText(f"{self._cpu_temp:.0f}°C")
        cpu._tok.setText(f"{self._tok_s:.0f}t/s")
        cpu._kv.setText(self._kv)
        cpu._mem.setText(f"{self._mem}%")
        cpu._bus.setText(f"{self._freq}M")

        gpu = self.device_panel.gpu_box
        gpu._temp.setText(f"{self._gpu_temp:.0f}°C")

    def _build_command_bar(self):
        bar = QFrame()
        bar.setObjectName("command_bar")
        bar.setFixedHeight(52)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Comando o prompt (premi Invia; validazione pre-flight automatica)")
        lay.addWidget(self.cmd_input)

        send = QPushButton("Invia")
        send.setObjectName("primary_btn")
        send.setFixedHeight(34)
        # COLLEGA IL BOTTONE
        send.clicked.connect(self._send_command)
        # PERMETTI DI PREMERE INVIO
        self.cmd_input.returnPressed.connect(self._send_command)
        lay.addWidget(send)
        return bar

    def _send_command(self):
        text = self.cmd_input.text().strip()
        if text:
            add_task_to_db(text)
            self.cmd_input.clear()
            print("Task aggiunto al database!")
            # Qui potresti aggiungere un aggiornamento della lista task nel drawer
            # self.drawer.refresh_tasks() 
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

        task_header = QLabel("<b>📋 TASK</b>")
        task_header.setStyleSheet("padding:4px 16px; color:#2563eb; font-size:12px;")
        lay.addWidget(task_header)

        self.task_list = QListWidget()
        self.task_list.setObjectName("task_list")
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.itemDoubleClicked.connect(self._on_task_double_clicked)
        self.task_list.customContextMenuRequested.connect(self._on_task_context_menu)
        # Popola con task reali dal DB
        try:
            from GUI import gui_backend as gb
            tasks = gb.get_tasks()
            for t in tasks:
                title = t.get("title", t.get("description", "?"))[:50]
                st = t.get("status", "?")
                icon = {"done": "✓", "running": "▶", "pending": "○",
                        "failed": "✗", "queued": "○",
                        "paused": "⏸", "thermal_paused": "🌡"}.get(st, "?")
                item = QListWidgetItem(f"{icon} {title}")
                item.setData(Qt.ItemDataRole.UserRole, t.get("id", ""))
                color = {"done": "#16a34a", "running": "#f59e0b",
                         "pending": "#888", "failed": "#dc2626",
                         "paused": "#6b7280", "thermal_paused": "#f97316"}.get(st, "#888")
                item.setForeground(QColor(color))
                self.task_list.addItem(item)
        except Exception as e:
            print(f"Errore popolamento task_list: {e}")
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
        
        act_delete = QAction("🗑️ Cancella", self)
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


    def _pause_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_pause_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._pause_orchestrator()

    def _resume_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_resume_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._resume_orchestrator()

    def _stop_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_stop_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._stop_orchestrator()

    def _on_task_double_clicked(self, item):
        """Doppio click su task nella sidebar -> riavvia."""
        try:
            task_id = item.data(Qt.ItemDataRole.UserRole) if hasattr(item, 'data') else None
            if task_id:
                _log_user_action("Task-Action", "avvio", task_id=task_id, details="Doppio click - riavvio veloce")
            if not task_id:
                # Fallback: estrai dal testo
                m = re.search(r'task-\d+', item.text() if hasattr(item, 'text') else str(item))
                if m:
                    task_id = m.group(0)
                else:
                    return
            ok, msg = _restart_task(task_id)
            if ok:
                # Estrai il testo originale rimuovendo eventuali ↻ ... [restart] precedenti
                if hasattr(item, 'text'):
                    txt = item.text()
                    # Rimuovi prefisso ↻ e suffisso [restart] se presenti
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"↻ {txt} [restart]")
                if hasattr(item, 'setStyleSheet'):
                    item.setStyleSheet("color: #16a34a;")
                # Refresh via ControlCenter
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore double-click task: {e}")

    def _get_task_status(self, task_id):
        """Ritorna lo status corrente di un task."""
        try:
            import sqlite3, os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path, timeout=5.0)
            cur = con.cursor()
            cur.execute("SELECT status FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def _pause_task_with_refresh(self, task_id, item):
        """Mette in pausa un singolo task."""
        try:
            _log_user_action("Task-Action", "pausa", task_id=task_id, details="Task messo in pausa dall'utente")
            ok, msg = _pause_task(task_id)
            if ok and item:
                txt = item.text() if hasattr(item, 'text') else ""
                for prefix in ["⏸ ", "▶ ", "🛑 ", "↻ "]:
                    if txt.startswith(prefix):
                        txt = txt[len(prefix):]
                if " [paused]" in txt: txt = txt.replace(" [paused]", "")
                if " [restart]" in txt: txt = txt.replace(" [restart]", "")
                if " [stopped]" in txt: txt = txt.replace(" [stopped]", "")
                item.setText(f"⏸ {txt} [paused]")
                item.setStyleSheet("color: #6b7280;")
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore pause task: {e}")

    def _resume_task_with_refresh(self, task_id, item):
        """Riprende un singolo task dalla pausa."""
        try:
            _log_user_action("Task-Action", "avvio", task_id=task_id, details="Task riavviato dall'utente")
            ok, msg = _resume_single_task(task_id)
            if ok and item:
                txt = item.text() if hasattr(item, 'text') else ""
                for prefix in ["⏸ ", "▶ ", "🛑 ", "↻ "]:
                    if txt.startswith(prefix):
                        txt = txt[len(prefix):]
                if " [paused]" in txt: txt = txt.replace(" [paused]", "")
                if " [restart]" in txt: txt = txt.replace(" [restart]", "")
                if " [stopped]" in txt: txt = txt.replace(" [stopped]", "")
                item.setText(f"▶ {txt}")
                item.setStyleSheet("color: #f59e0b;")
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore resume task: {e}")

    def _on_task_context_menu(self, pos):
        """Menu contestuale tasto destro su un task."""
        try:
            item = self.task_list.itemAt(pos)
            if not item:
                return
            task_id = item.data(Qt.ItemDataRole.UserRole)
            if not task_id:
                return
            
            from PyQt6.QtGui import QAction
            menu = QMenu(self)
            
            act_details = QAction("📋 Dettagli task", self)
            act_details.triggered.connect(lambda: self._show_task_details(task_id))
            menu.addAction(act_details)
            
            menu.addSeparator()
            
            act_restart = QAction("🔄 Riavvia task", self)
            act_restart.triggered.connect(lambda: self._restart_task_with_refresh(task_id, item))
            menu.addAction(act_restart)
            
            # Pausa/Riprendi task (singolo)
            cur_status = self._get_task_status(task_id)
            if cur_status == 'paused':
                act_resume = QAction("▶ Riprendi task", self)
                act_resume.triggered.connect(lambda: self._resume_task_with_refresh(task_id, item))
                menu.addAction(act_resume)
            elif cur_status in ('pending', 'running'):
                act_pause = QAction("⏸ Pausa task", self)
                act_pause.triggered.connect(lambda: self._pause_task_with_refresh(task_id, item))
                menu.addAction(act_pause)
            
            # Ferma task definitivamente
            act_stop = QAction("🛑 Ferma task", self)
            act_stop.triggered.connect(lambda: self._stop_task_with_refresh(task_id, item))
            menu.addAction(act_stop)
            
            act_copy = QAction("📋 Copia ID task", self)
            act_copy.triggered.connect(lambda: self._copy_task_id(task_id))
            menu.addAction(act_copy)
            
            menu.addSeparator()
            
            act_delete = QAction("🗑 Elimina task", self)
            act_delete.triggered.connect(lambda: self._delete_task_with_refresh(task_id, item))
            menu.addAction(act_delete)
            
            menu.addSeparator()
            
            act_open = QAction("📂 Apri risultato", self)
            act_open.triggered.connect(lambda: self._open_task_result(task_id))
            menu.addAction(act_open)
            
            menu.exec(self.task_list.mapToGlobal(pos))
        except Exception as e:
            print(f"Errore context menu: {e}")

    def _stop_task_with_refresh(self, task_id, item):
        """Ferma un singolo task e aggiorna la lista."""
        try:
            _log_user_action("Task-Action", "stop", task_id=task_id, details="Task fermato dall'utente")
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Ferma task",
                f"Fermare il task {task_id[:12]}?\n\n"
                f"L'orchestratore continuerà a girare, ma questo task verrà marcato come fallito.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ok, msg = _stop_task(task_id)
            if ok:
                if item:
                    txt = item.text() if hasattr(item, 'text') else ""
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"🛑 {txt} [stopped]")
                    item.setStyleSheet("color: #dc2626;")
                # Refresh via ControlCenter
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore stop task: {e}")

    def _show_task_details(self, task_id):
        """Mostra un dialog con i dettagli completi del task."""
        try:
            from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                                         QLabel, QPushButton, QHBoxLayout, QTextEdit)
            import sqlite3, os, time
            
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            con.close()
            
            if not row:
                return
            
            task = dict(zip(cols, row))
            
            dlg = QDialog(self)
            dlg.setWindowTitle(f"📋 Dettagli Task {task_id[:12]}")
            dlg.resize(600, 500)
            lay = QVBoxLayout(dlg)
            
            title = QLabel(f"<b>{task.get('title', '(senza titolo)')[:80]}</b>")
            title.setStyleSheet("font-size:14px; padding:8px; background:#f0f9ff; border-radius:6px;")
            title.setWordWrap(True)
            lay.addWidget(title)
            
            form = QFormLayout()
            form.setSpacing(6)
            
            def fmt_time(ts):
                if not ts:
                    return "—"
                try:
                    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(ts)))
                except Exception:
                    return str(ts)
            
            st_color = {'done': 'green', 'running': 'orange', 'failed': 'red',
                        'pending': 'gray'}.get(task.get('status'), 'gray')
            form.addRow("ID:", QLabel(task.get('id', '—')))
            form.addRow("Status:", QLabel(f"<b style='color:{st_color}'>{task.get('status', '—')}</b>"))
            form.addRow("Type:", QLabel(task.get('type', '—')))
            form.addRow("Source:", QLabel(task.get('source', '—')))
            form.addRow("Attempts:", QLabel(str(task.get('attempts', 0))))
            form.addRow("Parent:", QLabel(task.get('parent') or '—'))
            form.addRow("Created:", QLabel(fmt_time(task.get('created_at'))))
            form.addRow("Started:", QLabel(fmt_time(task.get('started_at'))))
            form.addRow("Completed:", QLabel(fmt_time(task.get('completed_at'))))
            
            if task.get('reason'):
                form.addRow("Reason:", QLabel(str(task.get('reason'))))
            
            lay.addLayout(form)
            
            for label, field in [("Description", 'description'), ("Result", 'result'), ("Last error", 'last_error')]:
                val = task.get(field, '')
                if val:
                    color_style = ' style="color:red"' if 'error' in label.lower() else ''
                    lay.addWidget(QLabel(f"<b{color_style}>{label}:</b>"))
                    te = QTextEdit()
                    te.setReadOnly(True)
                    te.setPlainText(str(val)[:2000])
                    if 'error' in label.lower():
                        te.setStyleSheet("background:#fef2f2; border:1px solid #fecaca;")
                    te.setMaximumHeight(100)
                    lay.addWidget(te)
            
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            close_btn = QPushButton("Chiudi")
            close_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(close_btn)
            lay.addLayout(btn_row)
            
            dlg.exec()
        except Exception as e:
            print(f"Errore show details: {e}")

    def _restart_task_with_refresh(self, task_id, item):
        """Riavvia un task e aggiorna la lista."""
        try:
            _log_user_action("Task-Action", "avvio", task_id=task_id, details="Task riavviato dall'utente")
            ok, msg = _restart_task(task_id)
            if ok:
                if item:
                    txt = item.text() if hasattr(item, 'text') else ""
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"↻ {txt} [restart]")
                    item.setStyleSheet("color: #16a34a;")
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore restart: {e}")

    def _delete_task_with_refresh(self, task_id, item):
        """Elimina un task dal DB."""
        try:
            reply = QMessageBox.question(
                self, "Elimina task",
                f"Eliminare definitivamente il task {task_id[:12]}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            import sqlite3, os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            con.commit()
            con.close()
            parent = self.parent()
            while parent and not hasattr(parent, '_refresh_coda_card'):
                parent = parent.parent()
            if parent:
                parent._refresh_coda_card()
                if hasattr(parent, '_refresh_task_list'):
                    parent._refresh_task_list()
        except Exception as e:
            print(f"Errore delete: {e}")

    def _copy_task_id(self, task_id):
        """Copia l'ID del task negli appunti."""
        try:
            cb = QApplication.clipboard()
            cb.setText(task_id)
        except Exception as e:
            print(f"Errore copy: {e}")

    def _open_task_result(self, task_id):
        """Apre il file risultato del task se esiste."""
        try:
            import sqlite3, os, subprocess
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT result, title FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            con.close()
            
            if not row:
                return
            result_text, title = row
            
            file_patterns = []
            if result_text:
                file_patterns = re.findall(r'[\w/\\]+\.\w+', str(result_text))
            
            candidates = ['project/main.py']
            if title:
                try:
                    candidates.append('project/' + title.split()[0] + '.py')
                except Exception:
                    pass
            candidates.extend(file_patterns[:3])
            
            opened = False
            for f in candidates:
                full = os.path.join(base, f) if not os.path.isabs(f) else f
                if os.path.exists(full):
                    subprocess.Popen(['xdg-open', full])
                    opened = True
                    break
            
            if not opened:
                QMessageBox.information(self, "Risultato",
                    f"Nessun file trovato per il task.\n\nResult: {result_text}")
        except Exception as e:
            print(f"Errore open result: {e}")


class CenterArea(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.main_win = parent
        self._editor_column = None
        
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        self.main_stack = QStackedWidget()
        
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setStyleSheet("QScrollArea { border:none; background:#ffffff; }")
        
        main_widget = QWidget()
        main_lay = QVBoxLayout(main_widget)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(12)
        
        self.logs_section = CollapsibleSection("Logs CI/CD", icon="📜")
        self.log_viewer = CategorizedLogViewer()
        self.logs_section.add_widget(self.log_viewer)
        main_lay.addWidget(self.logs_section)
        
        self.plancia_section = CollapsibleSection("Plancia di controllo", icon="✈️")
        
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)
        cards_grid.setContentsMargins(0, 0, 0, 0)
        
        self.cards = {}
        card_configs = [
            ("coda", "📋 Coda Task", "3 in coda", "3 tasks", "#f59e0b", 0, 0),
            ("modelli", "🤖 Modelli", "4 caricati", "4 loaded", "#2563eb", 0, 1),
            ("config", "⚙️ Config", "security: ON", "secure", "#16a34a", 0, 2),
        ]
        
        for key, title, subtitle, badge, badge_color, row, col in card_configs:
            card = PlanciaCard(title, subtitle, badge=badge, badge_color=badge_color)
            card.clicked.connect(lambda k=key: self.open_panel(k))
            self.cards[key] = card
            cards_grid.addWidget(card, row, col)
        
        cards_container = QWidget()
        cards_container.setLayout(cards_grid)
        self.plancia_section.add_widget(cards_container)
        
        self.code_explorer = CodeExplorer()
        self.code_explorer.setFixedHeight(350)
        self.plancia_section.add_widget(self.code_explorer)
        
        self.backup_logs = BackupCodeLogs()
        self.backup_logs.setFixedHeight(250)
        self.plancia_section.add_widget(self.backup_logs)
        
        main_lay.addWidget(self.plancia_section)
        
        main_scroll.setWidget(main_widget)
        self.main_stack.addWidget(main_scroll)
        
        self.detail_stack = QStackedWidget()
        self.panel_pages = {}
        for key, title, content in [
            ("coda", "📋 Coda Task", "3 task in coda · 1 in esecuzione · 1 completato\n\n• refactoring.py [ok]\n• analyze_usb.py [run]\n• new_feature.py [queued]"),
            ("modelli", "🤖 Modelli", "Modelli Ollama caricati:\n\n• qwen2.5-coder:1.5b (active)\n• llama3:8b\n• mistral:7b\n• phi3:mini\n\nVRAM usata: 2.1G / 4G"),
            ("config", "⚙️ Impostazioni", "Configurazione BYTE-SWARMY:\n\n• security: enabled (ALWAYS-ON)\n• MAX_STEPS: 6\n• num_ctx: 3072\n• num_predict: 512\n• tick_interval: 30s\n\nFile: CONFIG/config.toml"),
        ]:
            page = self._build_panel_page(title, content, key)
            self.panel_pages[key] = page
            self.detail_stack.addWidget(page)
        
        self.main_stack.addWidget(self.detail_stack)
        
        root.addWidget(self.main_stack, stretch=1)
    
    def open_panel(self, key):
        if key in self.panel_pages:
            self.main_stack.setCurrentIndex(1)
            self.detail_stack.setCurrentWidget(self.panel_pages[key])
    
    def back_to_main(self):
        self.main_stack.setCurrentIndex(0)
    
    def _build_panel_page(self, title, content, key):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)
        
        head = QHBoxLayout()
        back = QPushButton("← Indietro alla Plancia")
        back.setObjectName("back_btn")
        back.setStyleSheet(
            "QPushButton#back_btn { background:#e8e8ec; color:#1a1a1a; border:none; "
            "padding:8px 16px; border-radius:6px; font-size:12px; }"
            "QPushButton#back_btn:hover { background:#d0d0d0; }"
        )
        back.clicked.connect(self.back_to_main)
        head.addWidget(back)
        head.addStretch()
        head.addWidget(QLabel(f"<b style='font-size:18px;'>{title}</b>"))
        head.addStretch()
        lay.addLayout(head)
        
        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(content)
        body.setStyleSheet(
            "QTextEdit { font-size:13px; color:#333; padding:20px; "
            "background:#f8f9fa; border-radius:8px; border:1px solid #e0e0e0; "
            "font-family:'JetBrains Mono','Consolas',monospace; }"
        )
        lay.addWidget(body, stretch=1)
        return page
    
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ControlCenter()
    # Imposta icona finestra
    import os
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'IMG', 'icona.ico')
    if os.path.exists(icon_path):
        from PyQt6.QtGui import QIcon
        w.setWindowIcon(QIcon(icon_path))
        app.setWindowIcon(QIcon(icon_path))
        fixes_log = "Icona finestra impostata"
    else:
        fixes_log = "Icona non trovata"

    w.show()
    sys.exit(app.exec())
