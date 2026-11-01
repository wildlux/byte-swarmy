#!/usr/bin/env python3
"""
BYTE-SWARMY Control Center — Fix: DevicePanel compatto + card menu renderizzate
PyQt6, single-file
"""

import sys
import random
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit, QTextEdit,
    QFrame, QTreeView, QGridLayout, QTabBar, QHeaderView
)
from PyQt6.QtGui import QFont, QFileSystemModel, QCursor
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QDir, QTimer


# ═══════════════════════════════════════════════════════════════
# DEVICE PANEL: CPU + GPU + Orchestratore (COMPATTO)
# ═══════════════════════════════════════════════════════════════
class DevicePanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("device_panel")
        self.setStyleSheet(
            "QFrame#device_panel { background:#f8f9fa; border:1px solid #e0e0e0; "
            "border-radius:8px; padding:3px; }"
        )
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(6)
        
        # Colonna CPU + GPU
        devices_col = QVBoxLayout()
        devices_col.setSpacing(3)
        devices_col.setContentsMargins(0, 0, 0, 0)
        
        self.cpu_box = self._device_row("CPU", "#16a34a", "qwen2.5:1.5b")
        self.gpu_box = self._device_row("GPU", "#2563eb", "—")
        
        devices_col.addWidget(self.cpu_box)
        devices_col.addWidget(self.gpu_box)
        lay.addLayout(devices_col)
        
        # Separatore
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:#d0d0d0;")
        lay.addWidget(sep)
        
        # Pulsante Orchestratore
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setFixedWidth(40)
        self.toggle_btn.setMinimumHeight(50)
        self.toggle_btn.setObjectName("primary_btn")
        self.toggle_btn.setToolTip("Avvia/Ferma Orchestratore")
        lay.addWidget(self.toggle_btn)
    
    def _device_row(self, name, color, model_name):
        row = QFrame()
        row.setObjectName(f"{name.lower()}_row")
        row.setStyleSheet(
            f"QFrame#{name.lower()}_row {{ background:#ffffff; border:1px solid {color}33; "
            f"border-radius:4px; padding:2px 4px; }}"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)
        
        lbl = QLabel(f"<b>{name}</b>")
        lbl.setStyleSheet(f"color:{color}; font-size:10px; font-weight:bold;")
        lbl.setFixedWidth(28)
        lay.addWidget(lbl)
        
        # Modello compatto (troncato se troppo lungo)
        model_lbl = QLabel(model_name)
        model_lbl.setStyleSheet("color:#555; font-size:9px;")
        model_lbl.setFixedWidth(70)
        lay.addWidget(model_lbl)
        
        # Metrici compatti (senza emoji per risparmiare spazio)
        temp_lbl = QLabel("45°C")
        tok_lbl = QLabel("12t/s")
        kv_lbl = QLabel("2.1G")
        mem_lbl = QLabel("65%")
        bus_lbl = QLabel("800M")
        
        for w in (temp_lbl, tok_lbl, kv_lbl, mem_lbl, bus_lbl):
            w.setStyleSheet("color:#444; font-size:9px;")
            w.setFixedWidth(32)
            lay.addWidget(w)
        
        row._temp = temp_lbl
        row._tok = tok_lbl
        row._kv = kv_lbl
        row._mem = mem_lbl
        row._bus = bus_lbl
        row._model = model_lbl
        return row


# ═══════════════════════════════════════════════════════════════
# CLICKABLE CARD (sostituisce QPushButton con HTML)
# ═══════════════════════════════════════════════════════════════
class ClickableCard(QFrame):
    """Card cliccabile con titolo e sottotitolo renderizzati correttamente."""
    clicked = pyqtSignal()
    
    def __init__(self, title, subtitle, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size:15px; font-weight:bold; color:#1a1a1a;")
        lay.addWidget(self.title_lbl)
        
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("font-size:11px; color:#666;")
        lay.addWidget(self.sub_lbl)
        
        lay.addStretch()
        
        self._apply_style(normal=True)
    
    def _apply_style(self, normal):
        if normal:
            self.setStyleSheet(
                "QFrame#card { background:#ffffff; border:1px solid #e0e0e0; "
                "border-radius:10px; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#card { background:#f0f9ff; border:1px solid #16a34a; "
                "border-radius:10px; }"
            )
    
    def enterEvent(self, event):
        self._apply_style(normal=False)
    
    def leaveEvent(self, event):
        self._apply_style(normal=True)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ═══════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════
class ControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BYTE-SWARMY · Control Center")
        self.resize(1320, 800)
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

    def _build_toolbar(self):
        bar = QFrame()
        bar.setObjectName("toolbar")
        bar.setFixedHeight(60)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        menu_btn = QPushButton("☰")
        menu_btn.setFixedSize(30, 30)
        menu_btn.setObjectName("icon_btn")
        menu_btn.clicked.connect(self.drawer.toggle)
        lay.addWidget(menu_btn)

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
        QPushButton#icon_btn { background:transparent; font-size:16px; }
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
            background:#ffffff; color:#1a1a1a; border-bottom:2px solid #16a34a;
            font-weight:bold;
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
        self.setStyleSheet(
            "QFrame#drawer { background:#fafafa; border-right:1px solid #e0e0e0; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(0)

        header = QLabel("<b>📁 BYTE-SWARMY</b>")
        header.setStyleSheet("padding:8px 16px; color:#16a34a; font-size:13px;")
        lay.addWidget(header)

        self.tree = QTreeView()
        self.tree.setAlternatingRowColors(True)
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
        lay.addWidget(self.tree)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#e0e0e0; margin:8px 12px;")
        lay.addWidget(sep)

        task_header = QLabel("<b>📋 TASK</b>")
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
            ("○", "test_sandbox.py", "q", "#888"),
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
            st.setStyleSheet(f"color:{color}; font-size:10px; background:#f0f0f0; "
                             "padding:2px 6px; border-radius:4px;")
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

    def toggle(self):
        self._open = not self._open
        target = 0 if self._open else 280
        self._anim.setStartValue(280 if self._open else 0)
        self._anim.setEndValue(target)
        self._anim.start()


class CenterArea(QStackedWidget):
    def __init__(self, parent):
        super().__init__()
        self.main_win = parent

        self.main_page = QWidget()
        main_lay = QVBoxLayout(self.main_page)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(12)

        self.log_toggle = QPushButton("📜 Logs  [▾ collassa]")
        self.log_toggle.setStyleSheet(
            "background:#f0f0f0; border:1px solid #d0d0d0; border-radius:6px; "
            "padding:8px 14px; text-align:left; font-size:13px; color:#1a1a1a;"
        )
        self.log_toggle.clicked.connect(self._toggle_logs)
        main_lay.addWidget(self.log_toggle)

        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        sample = (
            "2026-11-01 11:43:15 [INFO]  FAST: CPU cool (45.0C) and idle (5%)\n"
            "2026-11-01 11:43:17 [DEBUG] sample: temp=45.0C load=2% freq=800MHz mem=54%\n"
            "2026-11-01 11:43:18 [INFO]  FAST: CPU cool (45.0C) and idle (5%)\n"
            "2026-11-01 11:43:47 [DEBUG] sample: temp=59.0C load=8% freq=2224MHz mem=65%\n"
            "2026-11-01 11:43:48 [INFO]  FAST: CPU cool (45.0C) and idle (2%)\n"
            "2026-11-01 11:43:49 [DEBUG] sample: temp=52.0C load=8% freq=805MHz mem=65%\n"
            "2026-11-01 11:44:17 [DEBUG] sample: temp=49.0C load=8% freq=837MHz mem=64%\n"
            "2026-11-01 11:44:19 [DEBUG] sample: temp=49.0C load=8% freq=2220MHz mem=64%\n"
        )
        self.log_panel.setPlainText(sample)
        main_lay.addWidget(self.log_panel, stretch=1)

        self.menu_grid = self._build_menu_grid()
        self.menu_grid.hide()
        main_lay.addWidget(self.menu_grid, stretch=1)

        self.addWidget(self.main_page)

        self.panel_pages = {}
        for key, title, content in [
            ("coda", "📋 Coda Task", "3 task in coda · 1 in esecuzione · 1 completato"),
            ("modelli", "🤖 Modelli", "qwen2.5-coder:1.5b (active) · llama3:8b · mistral:7b · phi3:mini"),
            ("mcp", "🔌 MCP Servers", "Nessun server MCP configurato. Aggiungi un server in config.toml"),
            ("timestral", "🌡️ Timestral", "Storico termico 24h · 2880 campioni · CPU 45°C · GPU 38°C"),
            ("config", "⚙️ Config", "config.toml · security: enabled · MAX_STEPS: 6 · num_ctx: 3072"),
            ("sandbox", "🧪 Test & Sandbox", "55 test passano · 27 security · 22 sandbox · 6 intent"),
        ]:
            page = self._build_panel_page(title, content, key)
            self.panel_pages[key] = page
            self.addWidget(page)

        self._logs_visible = True

    def _toggle_logs(self):
        self._logs_visible = not self._logs_visible
        if self._logs_visible:
            self.log_panel.show()
            self.menu_grid.hide()
            self.log_toggle.setText("📜 Logs  [▾ collassa]")
        else:
            self.log_panel.hide()
            self.menu_grid.show()
            self.log_toggle.setText("📜 Logs  [▴ espandi]")

    def _build_menu_grid(self):
        grid = QWidget()
        lay = QGridLayout(grid)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        cards = [
            ("coda", "📋 Coda Task", "3 in coda"),
            ("modelli", "🤖 Modelli", "4 caricati"),
            ("mcp", "🔌 MCP", "0 server"),
            ("timestral", "🌡️ Timestral", "45°C cool"),
            ("config", "⚙️ Config", "config.toml"),
            ("sandbox", "🧪 Sandbox", "55 test OK"),
        ]
        for i, (key, title, sub) in enumerate(cards):
            card = ClickableCard(title, sub)
            card.clicked.connect(lambda k=key: self._open_panel(k))
            lay.addWidget(card, i // 3, i % 3)

        lay.setRowStretch(1, 1)
        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)
        lay.setColumnStretch(2, 1)
        return grid

    def _open_panel(self, key):
        if key in self.panel_pages:
            self.setCurrentWidget(self.panel_pages[key])

    def _build_panel_page(self, title, content, key):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        head = QHBoxLayout()
        back = QPushButton("← Indietro")
        back.clicked.connect(lambda: self.setCurrentWidget(self.main_page))
        head.addWidget(back)
        head.addStretch()
        head.addWidget(QLabel(f"<b style='font-size:18px;'>{title}</b>"))
        head.addStretch()
        lay.addLayout(head)

        body = QLabel(content)
        body.setStyleSheet("font-size:14px; color:#333; padding:20px; "
                           "background:#f8f9fa; border-radius:8px; border:1px solid #e0e0e0;")
        body.setWordWrap(True)
        lay.addWidget(body, stretch=1)
        return page


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ControlCenter()
    w.show()
    sys.exit(app.exec())