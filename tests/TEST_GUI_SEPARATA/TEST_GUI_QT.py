#!/usr/bin/env python3
"""
BYTE-SWARMY Control Center — Test GUI minimale
PyQt6, single-file, dark theme, drawer + overlay + collapsible logs
"""

import sys
import random
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit, QTextEdit,
    QFrame, QTreeView, QScrollArea, QGridLayout,
    QSizePolicy, QAbstractItemView, QSplitter, QHeaderView
)
from PyQt6.QtGui import QFont, QFileSystemModel 
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QDir, QTimer


# ═══════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════
class ControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BYTE-SWARMY · Control Center")
        self.resize(1280, 780)
        self.setStyleSheet(self._dark_theme())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Creo prima gli oggetti che servono alla toolbar
        self.drawer = FileTreeDrawer(self)
        self.center = CenterArea(self)

        # 2. Poi creo la toolbar (che ora può usare self.drawer)
        root.addWidget(self._build_toolbar())

        # 3. Corpo: drawer + centro
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.drawer)
        body.addWidget(self.center, stretch=1)
        root.addLayout(body, stretch=1)

        # 4. Command Bar
        root.addWidget(self._build_command_bar())

        # ── Simulazione metrici ──
        self._cpu_temp = 45
        self._gpu_temp = 38
        self._tok_s = 12.5
        self._kv = "2.1G"
        self._mem = 65
        self._freq = 800
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_metrics)
        self._timer.start(1500)

    # ── Toolbar ──
    def _build_toolbar(self):
        bar = QFrame()
        bar.setObjectName("toolbar")
        bar.setFixedHeight(72)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(4)

        # Riga 1
        row1 = QHBoxLayout()
        menu_btn = QPushButton("☰")
        menu_btn.setFixedSize(34, 34)
        menu_btn.clicked.connect(self.drawer.toggle)  # Ora self.drawer esiste!
        row1.addWidget(menu_btn)

        row1.addWidget(QLabel("modello: <b>qwen2.5-coder:1.5b</b>"))
        row1.addStretch()

        self.cpu_box = self._device_box("CPU", "#4ade80")
        row1.addWidget(self.cpu_box)
        lay.addLayout(row1)

        # Riga 2
        row2 = QHBoxLayout()
        row2.addSpacing(46)
        row2.addWidget(QLabel("progetto: <b>reverse-usb-engineering</b>"))
        row2.addStretch()

        self.gpu_box = self._device_box("GPU", "#60a5fa")
        row2.addWidget(self.gpu_box)

        row2.addSpacing(12)
        self.toggle_btn = QPushButton("▶ Orchestratore")
        self.toggle_btn.setObjectName("primary_btn")
        row2.addWidget(self.toggle_btn)

        theme_btn = QPushButton("◐")
        theme_btn.setFixedSize(34, 34)
        row2.addWidget(theme_btn)
        lay.addLayout(row2)
        return bar

    def _device_box(self, name, color):
        box = QFrame()
        box.setObjectName(f"{name.lower()}_box")
        box.setStyleSheet(
            f"QFrame#{name.lower()}_box {{ background:#0f0f19; border-radius:6px; "
            f"border:1px solid {color}33; padding:4px 10px; }}"
        )
        lay = QHBoxLayout(box)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(10)

        lbl = QLabel(f"<b>{name}</b>")
        lbl.setStyleSheet(f"color:{color}; font-size:11px;")
        lay.addWidget(lbl)

        temp_lbl = QLabel("🌡️ —°C")
        tok_lbl = QLabel("⚡ — t/s")
        kv_lbl = QLabel("📦 KV: —")
        mem_lbl = QLabel("💾 —%")
        bus_lbl = QLabel("🔌 —MHz")
        
        for w in (temp_lbl, tok_lbl, kv_lbl, mem_lbl, bus_lbl):
            w.setStyleSheet("color:#c8c8d8; font-size:10px;")
            lay.addWidget(w)

        box._temp = temp_lbl
        box._tok = tok_lbl
        box._kv = kv_lbl
        box._mem = mem_lbl
        box._bus = bus_lbl
        return box

    def _tick_metrics(self):
        self._cpu_temp = max(35, min(75, self._cpu_temp + random.randint(-3, 4)))
        self._gpu_temp = max(30, min(65, self._gpu_temp + random.randint(-2, 3)))
        self._tok_s = round(max(0, self._tok_s + random.uniform(-2, 2)), 1)
        self._freq = random.choice([800, 1200, 1800, 2200, 2400])

        self.cpu_box._temp.setText(f"🌡️ {self._cpu_temp}°C")
        self.cpu_box._tok.setText(f"⚡ {self._tok_s} t/s")
        self.cpu_box._kv.setText(f"📦 KV: {self._kv}")
        self.cpu_box._mem.setText(f"💾 {self._mem}%")
        self.cpu_box._bus.setText(f"🔌 {self._freq}MHz")

        self.gpu_box._temp.setText(f"🌡️ {self._gpu_temp}°C")
        self.gpu_box._tok.setText(f"⚡ {self._tok_s * 0.3:.1f} t/s")
        self.gpu_box._kv.setText("📦 KV: 0B")
        self.gpu_box._mem.setText("💾 12%")
        self.gpu_box._bus.setText("🔌 —")

    # ── Command Bar ──
    def _build_command_bar(self):
        bar = QFrame()
        bar.setObjectName("command_bar")
        bar.setFixedHeight(56)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 8, 12, 8)

        cmd = QLineEdit()
        cmd.setPlaceholderText("Comando o prompt (premi Invia; validazione pre-flight automatica)")
        lay.addWidget(cmd)

        send = QPushButton("Invia")
        send.setObjectName("primary_btn")
        lay.addWidget(send)
        return bar

    # ── Tema ──
    def _dark_theme(self):
        return """
        QMainWindow { background:#12121c; color:#e0e0e8; }
        QFrame#toolbar   { background:#1c1c2e; border-bottom:1px solid #2a2a3c; }
        QFrame#command_bar { background:#1c1c2e; border-top:1px solid #2a2a3c; }
        QPushButton {
            background:#2a2a3c; color:#e0e0e8; border:none;
            padding:6px 12px; border-radius:6px; font-size:12px;
        }
        QPushButton:hover { background:#3a3a52; }
        QPushButton#primary_btn { background:#4ade80; color:#0f0f19; font-weight:bold; }
        QPushButton#primary_btn:hover { background:#6ee7a0; }
        QPushButton#card_btn {
            background:#1e1e32; border:1px solid #2a2a3c; border-radius:10px;
            padding:20px; text-align:left;
        }
        QPushButton#card_btn:hover { background:#2a2a4a; border-color:#4ade80; }
        QLineEdit {
            background:#0f0f19; color:#e0e0e8; border:1px solid #2a2a3c;
            padding:8px 12px; border-radius:6px; font-size:13px;
        }
        QTextEdit, QPlainTextEdit {
            background:#0a0a12; color:#c8c8d8; border:1px solid #2a2a3c;
            font-family:'JetBrains Mono','Consolas',monospace; font-size:11px;
        }
        QLabel { color:#c8c8d8; }
        QTreeView {
            background:#16162a; color:#c8c8d8; border:none;
            font-size:12px; padding:4px;
        }
        QTreeView::item:hover { background:#22223a; }
        QTreeView::item:selected { background:#2a2a4a; }
        QHeaderView::section { background:#16162a; color:#8888a0; border:none; padding:4px; }
        """


# ═══════════════════════════════════════════════════════════════
# DRAWER: file tree + task list
# ═══════════════════════════════════════════════════════════════
class FileTreeDrawer(QFrame):
    def __init__(self, parent):
        super().__init__()
        self.setObjectName("drawer")
        self.setFixedWidth(280)
        self.setStyleSheet(
            "QFrame#drawer { background:#16162a; border-right:1px solid #2a2a3c; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(0)

        # Header
        header = QLabel("<b>📁 BYTE-SWARMY</b>")
        header.setStyleSheet("padding:8px 16px; color:#4ade80; font-size:13px;")
        lay.addWidget(header)

        # File tree
        self.tree = QTreeView()
        self.tree.setAlternatingRowColors(True)
        self.model = QFileSystemModel()
        self.model.setRootPath("./")
        self.model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index("./"))
        self.tree.hideColumn(1) # Size
        self.tree.hideColumn(2) # Type
        self.tree.hideColumn(3) # Date
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tree)

        # Separator + Task section
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#2a2a3c; margin:8px 12px;")
        lay.addWidget(sep)

        task_header = QLabel("<b>📋 TASK</b>")
        task_header.setStyleSheet("padding:4px 16px; color:#60a5fa; font-size:12px;")
        lay.addWidget(task_header)

        self.task_list = QWidget()
        task_lay = QVBoxLayout(self.task_list)
        task_lay.setContentsMargins(12, 4, 12, 4)
        task_lay.setSpacing(4)

        tasks = [
            ("✓", "refactoring.py", "ok", "#4ade80"),
            ("▶", "analyze_usb.py", "run", "#fbbf24"),
            ("○", "new_feature.py", "q", "#8888a0"),
            ("○", "test_sandbox.py", "q", "#8888a0"),
        ]
        for icon, name, status, color in tasks:
            row = QHBoxLayout()
            row.setContentsMargins(4, 2, 4, 2)
            ic = QLabel(icon)
            ic.setStyleSheet(f"color:{color}; font-weight:bold;")
            ic.setFixedWidth(20)
            row.addWidget(ic)
            nm = QLabel(name)
            nm.setStyleSheet("color:#c8c8d8; font-size:11px;")
            row.addWidget(nm, stretch=1)
            st = QLabel(status)
            st.setStyleSheet(f"color:{color}; font-size:10px; background:#0f0f19; "
                             "padding:2px 6px; border-radius:4px;")
            row.addWidget(st)
            task_lay.addLayout(row)

        task_lay.addStretch()
        lay.addWidget(self.task_list, stretch=1)

        # Azioni
        act = QHBoxLayout()
        act.setContentsMargins(12, 8, 12, 8)
        ref = QPushButton("🔄")
        ref.setFixedWidth(36)
        ref.clicked.connect(lambda: self.model.setRootPath("./"))
        act.addWidget(ref)
        close = QPushButton("✕ Chiudi Drawer")
        close.setStyleSheet("color:#ef4444;")
        close.clicked.connect(self.toggle)
        act.addWidget(close, stretch=1)
        lay.addLayout(act)

        # Animazione
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


# ═══════════════════════════════════════════════════════════════
# CENTER AREA: logs collapsible + menu grid + functional panels
# ═══════════════════════════════════════════════════════════════
class CenterArea(QStackedWidget):
    def __init__(self, parent):
        super().__init__()
        self.main_win = parent

        # Pagina 0: logs + menu grid (toggle)
        self.main_page = QWidget()
        main_lay = QVBoxLayout(self.main_page)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(12)

        # Header collassabile
        self.log_toggle = QPushButton("📜 Logs  [▾ collassa]")
        self.log_toggle.setStyleSheet(
            "background:#1e1e32; border:1px solid #2a2a3c; border-radius:6px; "
            "padding:8px 14px; text-align:left; font-size:13px; color:#e0e0e8;"
        )
        self.log_toggle.clicked.connect(self._toggle_logs)
        main_lay.addWidget(self.log_toggle)

        # Pannello log
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

        # Griglia menu (nascosta di default)
        self.menu_grid = self._build_menu_grid()
        self.menu_grid.hide()
        main_lay.addWidget(self.menu_grid, stretch=1)

        self.addWidget(self.main_page)

        # Pagine funzionali (una per card)
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
            btn = QPushButton()
            btn.setObjectName("card_btn")
            btn.setStyleSheet(
                "QPushButton#card_btn { background:#1e1e32; border:1px solid #2a2a3c; "
                "border-radius:10px; padding:20px; text-align:left; }"
                "QPushButton#card_btn:hover { background:#2a2a4a; border-color:#4ade80; }"
            )
            btn.setText(f"<b style='font-size:16px;'>{title}</b><br>"
                        f"<span style='color:#8888a0; font-size:11px;'>{sub}</span>")
            btn.clicked.connect(lambda _, k=key: self._open_panel(k))
            lay.addWidget(btn, i // 3, i % 3)

        lay.setRowStretch(1, 1)
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
        body.setStyleSheet("font-size:14px; color:#c8c8d8; padding:20px; "
                           "background:#0f0f19; border-radius:8px;")
        body.setWordWrap(True)
        lay.addWidget(body, stretch=1)
        return page


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ControlCenter()
    w.show()
    sys.exit(app.exec())