"""
control_center.py — Layout 3-pannelli (niente tab).

Layout:
  +------------------------------------------+
  | Toolbar: [Avvia/Ferma] [CPU] [GPU] [Tema]|
  +-------------------+----------------------+
  |                   |                      |
  |   Coda Task       |   Live Activity      |
  |   + Quick Cmd     |   (streaming,        |
  |   + Tabella       |    metriche,         |
  |                   |    LLM Tuner)        |
  |                   |                      |
  +-------------------+----------------------+
  |  Log tail (ultime 10 righe, collapsible) |
  +------------------------------------------+

Usage: python -m GUI.control_center
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QFileSystemWatcher, QObject, QSize
from PyQt6.QtGui import QAction, QFont, QColor, QTextCursor, QPixmap, QIcon, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QMessageBox, QFileDialog, QSplitter, QGroupBox,
    QPlainTextEdit, QToolBar, QStatusBar, QListWidget, QListWidgetItem,
    QScrollArea, QFrame, QTextBrowser, QProgressBar,
)

# Import moduli progetto
from INTENT.bridge import parse_input, localize
try:
    from INTENT.bridge import parse_input
    INTENT_ROUTER_AVAILABLE = True
except ImportError:
    INTENT_ROUTER_AVAILABLE = False
from INTENT.metrics import format_metrics_line, format_vram_line


# ====================================================================
# Constants
# ====================================================================

BASE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_FILE = BASE_DIR / "CONFIG" / "config.toml"
LOG_FILE = BASE_DIR / "logs" / "byte-swarmy.log"
TASKS_DB = BASE_DIR / "tasks" / "queue.db"


# ====================================================================
# Helper functions
# ====================================================================

def load_tasks_from_db():
    """Carica task dal DB SQLite."""
    import sqlite3
    if not TASKS_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(TASKS_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def tail_log(n=10):
    """Ultime N righe del log (senza timestral)."""
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        filtered = [l for l in lines if "timestral" not in l.lower()]
        return "\n".join(filtered[-n:])
    except Exception:
        return "(no log)"


def read_streaming():
    """Legge streaming.txt per i token live."""
    try:
        f = BASE_DIR / "state" / "streaming.txt"
        if f.exists():
            return f.read_text(encoding="utf-8", errors="replace")[-400:]
        return ""
    except Exception:
        return ""


def read_advice():
    """Legge advice termico."""
    try:
        f = BASE_DIR / "state" / "timestral_advice.json"
        if f.exists():
            return json.loads(f.read_text())
    except Exception:
        pass
    return {}


def read_metrics():
    """Legge metriche ultima chiamata."""
    try:
        f = BASE_DIR / "state" / "last_metrics.json"
        if f.exists():
            return json.loads(f.read_text())
    except Exception:
        pass
    return {}


# ====================================================================
# Orchestrator process manager (riuso da main_window)
# ====================================================================

class OrchestratorProcess:
    def __init__(self):
        self.process = None
    
    def start(self):
        if self.is_running():
            return False
        try:
            for d in ("tasks", "state", "logs", "project", "backups"):
                (BASE_DIR / d).mkdir(parents=True, exist_ok=True)
            self.process = subprocess.Popen(
                [sys.executable, "-m", "SAFETY.watchdog"],
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            (BASE_DIR / "state" / "orchestrator.pid").write_text(str(self.process.pid))
            return True
        except Exception:
            return False
    
    def stop(self):
        if not self.is_running():
            return False
        try:
            import os as _os
            import signal as _sig
            _os.killpg(_os.getpgid(self.process.pid), _sig.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _os.killpg(_os.getpgid(self.process.pid), _sig.SIGKILL)
            self.process = None
            pid_file = BASE_DIR / "state" / "orchestrator.pid"
            if pid_file.exists():
                pid_file.unlink()
            return True
        except Exception:
            return False
    
    def is_running(self):
        if self.process is None:
            return False
        return self.process.poll() is None


# ====================================================================
# Live Activity Panel (pannello destro)
# ====================================================================

class LiveActivityPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(500)
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Titolo
        title = QLabel("Live Activity")
        title.setStyleSheet("font-weight: bold; font-size: 12pt; padding: 4px;")
        layout.addWidget(title)
        
        # Status + spinner
        row1 = QHBoxLayout()
        self.status_label = QLabel("In attesa")
        self.status_label.setStyleSheet("font-weight: bold; color: #999;")
        row1.addWidget(self.status_label)
        row1.addStretch()
        self.spinner_label = QLabel("")
        self.spinner_label.setStyleSheet("font-size: 14pt; color: #007acc;")
        row1.addWidget(self.spinner_label)
        layout.addLayout(row1)
        
        # Dettagli task
        self.details_label = QLabel("Nessun task in esecuzione")
        self.details_label.setStyleSheet("color: #999; font-family: monospace; font-size: 9pt;")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        
        # Streaming token
        self.stream_label = QLabel("")
        self.stream_label.setStyleSheet(
            "color: #50fa7b; font-family: monospace; font-size: 9pt; "
            "padding: 2px; background: #1a1a1a; border-radius: 3px;"
        )
        self.stream_label.setWordWrap(True)
        layout.addWidget(self.stream_label)
        
        # LLM Tuner
        self.tuner_label = QLabel("")
        self.tuner_label.setStyleSheet("color: #ff79c6; font-family: monospace; font-size: 9pt;")
        self.tuner_label.setWordWrap(True)
        layout.addWidget(self.tuner_label)
        
        # Metriche
        self.metrics_label = QLabel("")
        self.metrics_label.setStyleSheet("color: #ffb86c; font-family: monospace; font-size: 9pt;")
        self.metrics_label.setWordWrap(True)
        layout.addWidget(self.metrics_label)
        
        # VRAM
        self.vram_label = QLabel("")
        self.vram_label.setStyleSheet("color: #50fa7b; font-family: monospace; font-size: 9pt;")
        self.vram_label.setWordWrap(True)
        layout.addWidget(self.vram_label)
        
        # Log tail
        layout.addStretch()
        log_title = QLabel("Log tail:")
        log_title.setStyleSheet("font-weight: bold; color: #999; font-size: 9pt;")
        layout.addWidget(log_title)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(8)
        self.log_text.setFont(font)
        layout.addWidget(self.log_text)
    
    def _refresh(self):
        import sqlite3
        # Task running
        running = []
        if TASKS_DB.exists():
            try:
                conn = sqlite3.connect(str(TASKS_DB))
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = 'running' ORDER BY created_at"
                ).fetchall()
                conn.close()
                running = [dict(r) for r in rows]
            except Exception:
                pass
        
        if running:
            task = running[0]
            self.status_label.setText("In esecuzione")
            self.status_label.setStyleSheet("font-weight: bold; color: #007acc;")
            self.details_label.setText(
                f"Task: {task.get('id', '?')[:30]}\n"
                f"Title: {task.get('title', '?')[:60]}"
            )
            self.spinner_label.setText("...")
        else:
            self.status_label.setText("In attesa")
            self.status_label.setStyleSheet("font-weight: bold; color: #999;")
            self.details_label.setText("Nessun task in esecuzione")
            self.spinner_label.setText("")
        
        # Streaming
        stream = read_streaming()
        if stream:
            display = stream[-300:].replace("\n", " ")
            self.stream_label.setText(f"Streaming: {display}")
        else:
            self.stream_label.setText("")
        
        # Advice / Tuner
        advice = read_advice()
        if advice:
            action = advice.get("action", "normal")
            cpu = advice.get("cpu_temp", 0)
            gpu = advice.get("gpu_temp", 0)
            self.tuner_label.setText(
                f"Timestral: {action.upper()} (CPU {cpu:.0f}C, GPU {gpu:.0f}C)"
            )
        
        # Metriche
        m = read_metrics()
        if m:
            self.metrics_label.setText(format_metrics_line())
        
        # VRAM
        self.vram_label.setText(format_vram_line())
        
        # Log tail
        self.log_text.setPlainText(tail_log(8))


# ====================================================================
# Task Queue Panel (pannello sinistro)
# ====================================================================

class TaskQueuePanel(QWidget):
    def __init__(self, orchestrator_proc):
        super().__init__()
        self.orch = orchestrator_proc
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(2000)
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Quick Command Bar
        cmd_layout = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setObjectName("quickCommand")
        self.cmd_input.setPlaceholderText(
            "Scrivi in qualsiasi lingua (IT/EN/ZH) e premi Invio..."
        )
        self.cmd_input.returnPressed.connect(self._on_quick_command)
        cmd_layout.addWidget(self.cmd_input, stretch=1)
        btn_add = QPushButton("Aggiungi")
        btn_add.clicked.connect(self._on_quick_command)
        cmd_layout.addWidget(btn_add)
        layout.addLayout(cmd_layout)
        
        # Status feedback
        self.feedback_label = QLabel("")
        self.feedback_label.setStyleSheet("color: #999; font-size: 9pt; padding: 2px;")
        layout.addWidget(self.feedback_label)
        
        # Tabella task
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Stato", "Titolo", "Tipo", "Tent."])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)
        
        # Bottoni azione
        btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("Aggiorna")
        btn_refresh.clicked.connect(self._refresh)
        btn_layout.addWidget(btn_refresh)
        btn_cleanup = QPushButton("Pulisci completati")
        btn_cleanup.clicked.connect(self._cleanup)
        btn_layout.addWidget(btn_cleanup)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def _on_quick_command(self):
        raw = self.cmd_input.text().strip()
        if not raw:
            return
        try:
            import sqlite3
            import time
            
            # Intent router
            if INTENT_ROUTER_AVAILABLE:
                result = parse_input(raw)
                task_type = result.get("task_type", "generic")
                context = result.get("context", "{}")
            else:
                task_type = "code"
                context = "{}"
            
            # Scrivi nel DB SQLite
            task_id = f"task-{int(time.time()*1000)}"
            conn = sqlite3.connect(str(TASKS_DB))
            conn.execute(
                "INSERT INTO tasks (id, title, description, context, status, "
                "attempts, created_at, parent, type, source) "
                "VALUES (?,?,?,?,?,?,?, ?,?,?)",
                (task_id, raw[:120], raw, context, "pending", 0,
                 time.time(), None, task_type, "gui")
            )
            # Mirror su JSON per retrocompat
            tasks = []
            json_file = BASE_DIR / "tasks" / "queue.json"
            if json_file.exists():
                try:
                    tasks = json.loads(json_file.read_text())
                except Exception:
                    pass
            tasks.append({
                "id": task_id, "title": raw[:120], "description": raw,
                "context": context, "status": "pending", "attempts": 0,
                "subtasks": [], "parent": None, "created_at": time.time(),
                "source": "gui", "type": task_type,
            })
            json_file.write_text(json.dumps(tasks, indent=2))
            conn.commit()
            conn.close()
            
            self.feedback_label.setText(f"Task aggiunto: {task_id}")
            self.feedback_label.setStyleSheet("color: #28a745; font-size: 9pt;")
            self.cmd_input.clear()
            self._refresh()
        except Exception as e:
            self.feedback_label.setText(f"Errore: {e}")
            self.feedback_label.setStyleSheet("color: #dc3545; font-size: 9pt;")
    
    def _refresh(self):
        tasks = load_tasks_from_db()
        self.table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            self.table.setItem(i, 0, QTableWidgetItem(t.get("id", "")[:25]))
            status_item = QTableWidgetItem(t.get("status", ""))
            colors = {
                "pending": QColor("#909090"), "running": QColor("#0066cc"),
                "done": QColor("#008800"), "retry": QColor("#cc6600"),
                "stuck": QColor("#cc0000"), "planned": QColor("#9966cc"),
            }
            c = colors.get(t.get("status", ""), QColor("#000000"))
            status_item.setForeground(c)
            font = status_item.font()
            font.setBold(True)
            status_item.setFont(font)
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, QTableWidgetItem(t.get("title", "")[:80]))
            self.table.setItem(i, 3, QTableWidgetItem(t.get("type", "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(t.get("attempts", 0))))
    
    def _cleanup(self):
        import sqlite3
        try:
            conn = sqlite3.connect(str(TASKS_DB))
            conn.execute("DELETE FROM tasks WHERE status = 'done'")
            conn.commit()
            conn.close()
            self._refresh()
        except Exception:
            pass


# ====================================================================
# MainWindow (3-pannelli, niente tab)
# ====================================================================

class ControlCenter(QMainWindow):
    """Layout 3-pannelli: Task Queue | Live Activity | Log tail."""
    
    SPINNER_FRAMES = ["-", "\\", "|", "/"]
    
    def __init__(self):
        super().__init__()
        self.orch = OrchestratorProcess()
        self._spinner_idx = 0
        self._build_ui()
        
        # Auto-start orchestrator
        QTimer.singleShot(500, self._auto_start)
        
        # Status timer
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(2000)
    
    def _build_ui(self):
        self.setWindowTitle("BYTE-SWARMY Control Center")
        self.setMinimumSize(1000, 600)
        
        # Icona
        icon_path = str(BASE_DIR / "IMG" / "icona.png")
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))
        
        # Toolbar
        self._build_toolbar()
        
        # Splitter principale: sinistra (task) | destra (activity)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Pannello sinistro: Coda Task + Quick Command
        self.task_panel = TaskQueuePanel(self.orch)
        splitter.addWidget(self.task_panel)
        
        # Pannello destro: Live Activity
        self.activity_panel = LiveActivityPanel()
        splitter.addWidget(self.activity_panel)
        
        # Proporzioni: 60% task, 40% activity
        splitter.setSizes([600, 400])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        
        # Widget centrale
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(splitter, stretch=1)
        
        # Log tail in basso (collapsible)
        self.log_toggle = QPushButton("Log tail (mostra/nascondi)")
        self.log_toggle.setMaximumHeight(24)
        self.log_toggle.clicked.connect(self._toggle_log)
        central_layout.addWidget(self.log_toggle)
        
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(120)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(8)
        self.log_view.setFont(font)
        central_layout.addWidget(self.log_view)
        
        # Log auto-refresh
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_log)
        self.log_timer.start(2000)
        
        self.setCentralWidget(central)
        
        # Scorciatoie
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, activated=self._toggle_theme)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)
    
    def _build_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Toggle orchestratore
        self.btn_toggle = QPushButton("Avvia Orchestratore")
        self.btn_toggle.setObjectName("toggleOrch")
        self.btn_toggle.clicked.connect(self._toggle_orch)
        toolbar.addWidget(self.btn_toggle)
        
        toolbar.addSeparator()
        
        # Temperature
        self.temp_cpu = QLabel("CPU: --C")
        self.temp_cpu.setObjectName("tempIndicator")
        toolbar.addWidget(self.temp_cpu)
        
        self.temp_gpu = QLabel("GPU: --C")
        self.temp_gpu.setObjectName("tempIndicator")
        toolbar.addWidget(self.temp_gpu)
        
        spacer = QWidget()
        from PyQt6.QtWidgets import QSizePolicy; spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        
        # Tema
        self.btn_theme = QPushButton("Tema")
        self.btn_theme.setMaximumWidth(60)
        self.btn_theme.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self.btn_theme)
        
        toolbar.addSeparator()
        
        # Esci
        act_quit = QAction("Esci", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        toolbar.addAction(act_quit)
    
    def _toggle_orch(self):
        if self.orch.is_running():
            self.orch.stop()
        else:
            self.orch.start()
        self._update_status()
    
    def _auto_start(self):
        self.orch.start()
        self._update_status()
    
    def _update_status(self):
        running = self.orch.is_running()
        if running:
            self.btn_toggle.setText("Ferma Orchestratore")
            self.btn_toggle.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px 14px;")
        else:
            self.btn_toggle.setText("Avvia Orchestratore")
            self.btn_toggle.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 6px 14px;")
        
        # Temperature
        try:
            import subprocess
            # CPU
            cpu_file = Path("/sys/class/thermal/thermal_zone0/temp")
            if cpu_file.exists():
                cpu_temp = int(cpu_file.read_text().strip()) / 1000
                self.temp_cpu.setText(f"CPU: {cpu_temp:.0f}C")
                if cpu_temp >= 90:
                    self.temp_cpu.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 2px 8px;")
                elif cpu_temp >= 75:
                    self.temp_cpu.setStyleSheet("background-color: #fd7e14; color: white; font-weight: bold; padding: 2px 8px;")
                elif cpu_temp >= 60:
                    self.temp_cpu.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 2px 8px;")
                else:
                    self.temp_cpu.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 2px 8px;")
            # GPU
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0 and r.stdout.strip():
                gpu_temp = float(r.stdout.strip())
                self.temp_gpu.setText(f"GPU: {gpu_temp:.0f}C")
                if gpu_temp >= 90:
                    self.temp_gpu.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 2px 8px;")
                elif gpu_temp >= 80:
                    self.temp_gpu.setStyleSheet("background-color: #fd7e14; color: white; font-weight: bold; padding: 2px 8px;")
                elif gpu_temp >= 70:
                    self.temp_gpu.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 2px 8px;")
                else:
                    self.temp_gpu.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 2px 8px;")
        except Exception:
            pass
    
    def _toggle_theme(self):
        try:
            from GUI.theme.theme import toggle_theme
            app = QApplication.instance()
            theme = toggle_theme(app)
            self.btn_theme.setText(theme)
        except Exception as e:
            print(f"Theme: {e}")
    
    def _toggle_log(self):
        self.log_view.setVisible(not self.log_view.isVisible())
    
    def _refresh_log(self):
        self.log_view.setPlainText(tail_log(15))
    
    def closeEvent(self, event):
        if self.orch.is_running():
            reply = QMessageBox.question(
                self, "Conferma uscita",
                "L'orchestratore e attivo. Fermarlo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.orch.stop()
        event.accept()


# ====================================================================
# Entry point
# ====================================================================

def main():
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("BYTE-SWARMY Control Center")
    
    # Theme
    try:
        from GUI.theme.theme import apply_theme
        apply_theme(app)
    except Exception as e:
        print(f"Theme: {e}")
    
    window = ControlCenter()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
