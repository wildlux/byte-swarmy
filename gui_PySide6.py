"""
gui.py — AI-CIV Control Center (PySide6)

GUI Qt per controllare l'orchestratore AI-CIV:
- Tab 1: Coda Task (visualizza, aggiungi, elimina)
- Tab 2: MCP Servers (configura connessioni esterne)
- Tab 3: Logs (tail del file di log in tempo reale)
- Tab 4: Config (editor del config.toml)

Avvio:
    python gui.py

Requisiti:
    pip install PySide6 mcp httpx httpx-sse
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QFileSystemWatcher, QObject
)
from PySide6.QtGui import (
    QAction, QFont, QColor, QTextCursor, QIcon
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFormLayout, QSpinBox, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QMessageBox, QFileDialog, QSplitter, QGroupBox,
    QPlainTextEdit, QToolBar, QStatusBar, QListWidget, QListWidgetItem,
)

# Import moduli del progetto
try:
    from mcp_client import MCPClient, McpServerConfig, MCP_AVAILABLE
except ImportError as e:
    print(f"WARNING: cannot import mcp_client: {e}")
    MCPClient = None
    McpServerConfig = None
    MCP_AVAILABLE = False


# ====================================================================
# PATH CONSTANTS
# ====================================================================

BASE_DIR = Path(__file__).parent.resolve()
TASKS_FILE = BASE_DIR / "tasks" / "queue.json"
LOG_FILE = BASE_DIR / "logs" / "ai-civ.log"
CONFIG_FILE = BASE_DIR / "config.toml"
MCP_CONFIG_FILE = BASE_DIR / "mcp_servers.json"
PID_FILE = BASE_DIR / "state" / "orchestrator.pid"


# ====================================================================
# TASK QUEUE I/O (shared with orchestrator)
# ====================================================================

def load_tasks() -> list:
    if not TASKS_FILE.exists():
        return []
    try:
        return json.loads(TASKS_FILE.read_text())
    except Exception:
        return []


def save_tasks(tasks: list) -> None:
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TASKS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    tmp.replace(TASKS_FILE)


def add_task(title: str, description: str, context: str = "") -> dict:
    tasks = load_tasks()
    task = {
        "id": f"task-{int(time.time()*1000)}-{len(tasks)}",
        "title": title,
        "description": description,
        "context": context,
        "status": "pending",
        "attempts": 0,
        "subtasks": [],
        "parent": None,
        "created_at": time.time(),
        "source": "gui",
    }
    tasks.append(task)
    save_tasks(tasks)
    return task


def delete_task(task_id: str) -> None:
    tasks = load_tasks()
    tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(tasks)


def reset_task(task_id: str) -> None:
    """Resetta un task stuck/retry a pending."""
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "pending"
            t["attempts"] = 0
            t.pop("last_error", None)
            t.pop("failure_reason", None)
    save_tasks(tasks)


# ====================================================================
# MCP SERVERS CONFIG (persistente)
# ====================================================================

def load_mcp_servers() -> list:
    if not MCP_CONFIG_FILE.exists():
        return []
    try:
        return json.loads(MCP_CONFIG_FILE.read_text())
    except Exception:
        return []


def save_mcp_servers(servers: list) -> None:
    MCP_CONFIG_FILE.write_text(json.dumps(servers, indent=2))


# ====================================================================
# ORCHESTRATOR PROCESS MANAGER
# ====================================================================

class OrchestratorProcess:
    """Gestisce il subprocess dell'orchestratore."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        if self.is_running():
            return False
        try:
            # Assicura che le dir esistano
            for d in ("tasks", "state", "logs", "project", "backups"):
                (BASE_DIR / d).mkdir(parents=True, exist_ok=True)

            self.process = subprocess.Popen(
                [sys.executable, "orchestrator.py"],
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # nuovo process group per SIGTERM pulito
            )
            PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(self.process.pid))
            return True
        except Exception as e:
            print(f"Failed to start orchestrator: {e}")
            return False

    def stop(self) -> bool:
        if not self.is_running():
            return False
        try:
            # SIGTERM al process group (kill anche figli)
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            # Aspetta max 5s
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            self.process = None
            if PID_FILE.exists():
                PID_FILE.unlink()
            return True
        except Exception as e:
            print(f"Failed to stop orchestrator: {e}")
            return False

    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def pid(self) -> Optional[int]:
        if self.process and self.is_running():
            return self.process.pid
        return None


# ====================================================================
# LOG WATCHER (tail del file di log)
# ====================================================================

class LogWatcher(QObject):
    """Tail del file di log via QFileSystemWatcher."""
    new_lines = Signal(str)
    status = Signal(str)

    def __init__(self, log_path: Path):
        super().__init__()
        self.log_path = log_path
        self.watcher = QFileSystemWatcher()
        self.last_pos = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._read_new)

    def start(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()
        # Watch directory (più robusto che watch file, gestisce rotation)
        self.watcher.addPath(str(self.log_path.parent))
        self.watcher.directoryChanged.connect(self._on_dir_changed)
        # Poll ogni 500ms come fallback
        self.timer.start(500)
        self._read_new(initial=True)
        self.status.emit(f"Watching {self.log_path}")

    def _on_dir_changed(self, _path: str) -> None:
        self._read_new()

    def _read_new(self, initial: bool = False) -> None:
        if not self.log_path.exists():
            return
        try:
            size = self.log_path.stat().st_size
            if size < self.last_pos:
                # File ruotato, ricomincia
                self.last_pos = 0
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.last_pos)
                new_data = f.read()
                self.last_pos = f.tell()
            if new_data:
                self.new_lines.emit(new_data)
            if initial:
                # Limita a ultime 500 righe all'avvio
                pass
        except Exception:
            pass


# ====================================================================
# TASK TABLE TAB
# ====================================================================

class TaskQueueTab(QWidget):
    """Tab 1: visualizzazione e gestione della coda task."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh()

        # Auto-refresh ogni 2s
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(2000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ Aggiungi Task")
        btn_add.clicked.connect(self._on_add_task)
        btn_refresh = QPushButton("↻ Aggiorna")
        btn_refresh.clicked.connect(self._refresh)
        btn_delete = QPushButton("🗑 Elimina")
        btn_delete.clicked.connect(self._on_delete_selected)
        btn_reset = QPushButton("↻ Reset (retry→pending)")
        btn_reset.clicked.connect(self._on_reset_selected)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_reset)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Statistiche
        self.stats_label = QLabel("Caricamento...")
        self.stats_label.setStyleSheet("padding: 4px; background: #f0f0f0;")
        layout.addWidget(self.stats_label)

        # Tabella
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Stato", "Titolo", "Tentativi", "Sorgente"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Dettagli task selezionato
        details_group = QGroupBox("Dettagli task selezionato")
        details_layout = QVBoxLayout(details_group)
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        layout.addWidget(details_group)

        # Connessione selezione
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def _refresh(self) -> None:
        tasks = load_tasks()
        from collections import Counter
        stats = Counter(t["status"] for t in tasks)
        stats_str = " | ".join(f"{k}: {v}" for k, v in sorted(stats.items()))
        self.stats_label.setText(f"Totale: {len(tasks)}   |   {stats_str}")

        # Mantieni selezione
        selected_id = None
        for item in self.table.selectedItems():
            row = item.row()
            selected_id = self.table.item(row, 0).data(Qt.UserRole)
            break

        self.table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            id_item = QTableWidgetItem(t["id"])
            id_item.setData(Qt.UserRole, t["id"])
            status_item = QTableWidgetItem(t["status"])
            self._color_status(status_item, t["status"])
            title_item = QTableWidgetItem(t.get("title", "")[:80])
            attempts_item = QTableWidgetItem(str(t.get("attempts", 0)))
            source_item = QTableWidgetItem(t.get("source", "manual"))
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, title_item)
            self.table.setItem(i, 3, attempts_item)
            self.table.setItem(i, 4, source_item)

            if t["id"] == selected_id:
                self.table.selectRow(i)

    def _color_status(self, item: QTableWidgetItem, status: str) -> None:
        colors = {
            "pending":      QColor("#909090"),
            "running":      QColor("#0066cc"),
            "planned":      QColor("#9966cc"),
            "done":         QColor("#008800"),
            "retry":        QColor("#cc6600"),
            "stuck":        QColor("#cc0000"),
            "needs_human":  QColor("#cc0000"),
        }
        c = colors.get(status, QColor("#000000"))
        item.setForeground(c)
        font = item.font()
        font.setBold(True)
        item.setFont(font)

    def _on_selection_changed(self) -> None:
        items = self.table.selectedItems()
        if not items:
            self.details_text.clear()
            return
        row = items[0].row()
        task_id = self.table.item(row, 0).data(Qt.UserRole)
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                self.details_text.setPlainText(json.dumps(t, indent=2, ensure_ascii=False))
                return

    def _on_add_task(self) -> None:
        dialog = AddTaskDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if data["title"]:
                add_task(data["title"], data["description"], data.get("context", ""))
                self._refresh()

    def _on_delete_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        task_id = self.table.item(row, 0).data(Qt.UserRole)
        title = self.table.item(row, 2).text()
        if QMessageBox.question(
            self, "Conferma eliminazione",
            f"Eliminare il task '{title}'?\n(ID: {task_id})"
        ) == QMessageBox.Yes:
            delete_task(task_id)
            self._refresh()

    def _on_reset_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        task_id = self.table.item(row, 0).data(Qt.UserRole)
        reset_task(task_id)
        self._refresh()


# ====================================================================
# ADD TASK DIALOG
# ====================================================================

class AddTaskDialog(QDialog):
    """Dialog per aggiungere un nuovo task."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuovo Task")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("es. Implementa echo server TCP")
        form.addRow("Titolo:", self.title_edit)

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText(
            "Descrizione dettagliata: requisiti, file di output, criteri di test, "
            "vincoli (es. max 200 righe, usa stdlib Python)."
        )
        self.desc_edit.setMinimumHeight(120)
        form.addRow("Descrizione:", self.desc_edit)

        self.context_edit = QLineEdit()
        self.context_edit.setPlaceholderText("es. progetto nuovo, file esistenti: main.py")
        form.addRow("Contesto:", self.context_edit)

        layout.addLayout(form)

        # Hint
        hint = QLabel(
            "<i>Suggerimento: includi sempre file di output, linguaggio e criteri di test. "
            "Task semplici (con keyword 'scrivi', 'crea', 'implementa') bypassano il planner.</i>"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(hint)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
            "context": self.context_edit.text().strip(),
        }


# ====================================================================
# MCP SERVERS TAB
# ====================================================================

class McpServersTab(QWidget):
    """Tab 2: configurazione e gestione server MCP."""

    def __init__(self, mcp_client: Optional[MCPClient], parent=None):
        super().__init__(parent)
        self.client = mcp_client
        self._build_ui()
        self._load_servers()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Banner se MCP non disponibile
        if not MCP_AVAILABLE:
            banner = QLabel(
                f"⚠️ Modulo `mcp` non installato. Solo task locali disponibili.\n"
                f"Installa con: pip install mcp httpx httpx-sse\n"
                f"Errore: {(__import__('mcp_client').MCP_IMPORT_ERROR if MCP_AVAILABLE else 'module not loaded')}"
            )
            banner.setStyleSheet("padding: 12px; background: #fff3cd; color: #856404;")
            banner.setWordWrap(True)
            layout.addWidget(banner)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ Aggiungi Server")
        btn_add.clicked.connect(self._on_add_server)
        btn_edit = QPushButton("✎ Modifica")
        btn_edit.clicked.connect(self._on_edit_server)
        btn_delete = QPushButton("🗑 Elimina")
        btn_delete.clicked.connect(self._on_delete_server)
        btn_discover = QPushButton("🔍 Discover Tools")
        btn_discover.clicked.connect(self._on_discover)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_discover)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tabella server
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Nome", "URL", "Poll (s)", "Stato", "Tool"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Info box
        info = QLabel(
            "<b>Come funziona MCP qui:</b><br>"
            "1. Aggiungi un server MCP con il suo URL (deve esporre SSE, es. <code>http://host:port/sse</code>)<br>"
            "2. Il client si connette e chiama periodicamente il tool <code>get_pending_tasks</code><br>"
            "3. I task ricevuti vengono aggiunti alla coda locale con <code>source=mcp:&lt;nome&gt;</code><br>"
            "4. L'orchestratore li elabora come qualsiasi altro task"
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding: 8px; background: #e8f4fd;")
        layout.addWidget(info)

        # Auto-refresh stato
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(2000)

    def _load_servers(self) -> None:
        servers = load_mcp_servers()
        self.table.setRowCount(len(servers))
        for i, s in enumerate(servers):
            self._set_row(i, s)

    def _set_row(self, row: int, s: dict) -> None:
        self.table.setItem(row, 0, QTableWidgetItem(s.get("name", "")))
        self.table.setItem(row, 1, QTableWidgetItem(s.get("url", "")))
        self.table.setItem(row, 2, QTableWidgetItem(str(s.get("poll_interval", 30))))
        self.table.setItem(row, 3, QTableWidgetItem("disconnected"))
        self.table.setItem(row, 4, QTableWidgetItem(s.get("tool_name", "get_pending_tasks")))

    def _refresh_status(self) -> None:
        """Aggiorna solo la colonna stato."""
        if not self.client:
            return
        servers = self.client.list_servers()
        for srv in servers:
            # Trova la riga corrispondente
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).text() == srv.name:
                    item = self.table.item(row, 3) or QTableWidgetItem("")
                    item.setText(f"{srv.last_status}" + (
                        f" (err: {srv.last_error[:30]})" if srv.last_error else ""))
                    colors = {
                        "connected": QColor("#008800"),
                        "connecting": QColor("#cc6600"),
                        "error": QColor("#cc0000"),
                        "disconnected": QColor("#909090"),
                    }
                    item.setForeground(colors.get(srv.last_status, QColor("#000000")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    self.table.setItem(row, 3, item)
                    break

    def _on_add_server(self) -> None:
        dialog = McpServerDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"] and data["url"]:
                servers = load_mcp_servers()
                servers.append(data)
                save_mcp_servers(servers)
                self._load_servers()
                self._register_with_client(data)

    def _on_edit_server(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        servers = load_mcp_servers()
        if row >= len(servers):
            return
        dialog = McpServerDialog(self, servers[row])
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            servers[row] = data
            save_mcp_servers(servers)
            self._load_servers()
            self._update_client(data)

    def _on_delete_server(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        name = self.table.item(row, 0).text()
        if QMessageBox.question(
            self, "Conferma", f"Eliminare il server MCP '{name}'?"
        ) == QMessageBox.Yes:
            servers = load_mcp_servers()
            servers = [s for s in servers if s.get("name") != name]
            save_mcp_servers(servers)
            if self.client:
                self.client.remove_server(name)
            self._load_servers()

    def _on_discover(self) -> None:
        items = self.table.selectedItems()
        if not items or not self.client:
            return
        row = items[0].row()
        name = self.table.item(row, 0).text()
        tools = self.client.discover_tools(name)
        QMessageBox.information(
            self, "Tool Discovery",
            f"Server '{name}' espone {len(tools)} tool:\n\n" + "\n".join(tools)
            if tools else f"Nessun tool trovato o connessione fallita."
        )

    def _register_with_client(self, server_data: dict) -> None:
        if not self.client:
            return
        config = McpServerConfig(
            name=server_data["name"],
            url=server_data["url"],
            enabled=server_data.get("enabled", True),
            poll_interval=server_data.get("poll_interval", 30),
            tool_name=server_data.get("tool_name", "get_pending_tasks"),
        )
        self.client.add_server(config)

    def _update_client(self, server_data: dict) -> None:
        if not self.client:
            return
        # Rimuovi e riaggiungi
        self.client.remove_server(server_data["name"])
        self._register_with_client(server_data)


# ====================================================================
# MCP SERVER DIALOG
# ====================================================================

class McpServerDialog(QDialog):
    """Dialog per aggiungere/modificare un server MCP."""

    def __init__(self, parent=None, initial: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Server MCP")
        self.setMinimumWidth(450)
        self._build_ui()
        if initial:
            self._fill(initial)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("es. local-server, work-tasks")
        form.addRow("Nome:", self.name_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://localhost:8080/sse")
        form.addRow("URL SSE:", self.url_edit)

        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(5, 3600)
        self.poll_spin.setValue(30)
        self.poll_spin.setSuffix(" s")
        form.addRow("Intervallo poll:", self.poll_spin)

        self.tool_edit = QLineEdit()
        self.tool_edit.setText("get_pending_tasks")
        self.tool_edit.setToolTip(
            "Nome del tool MCP da chiamare per ottenere i task. "
            "Convenzione: get_pending_tasks"
        )
        form.addRow("Tool name:", self.tool_edit)

        self.enabled_check = QCheckBox("Abilitato")
        self.enabled_check.setChecked(True)
        form.addRow("", self.enabled_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill(self, data: dict) -> None:
        self.name_edit.setText(data.get("name", ""))
        self.url_edit.setText(data.get("url", ""))
        self.poll_spin.setValue(data.get("poll_interval", 30))
        self.tool_edit.setText(data.get("tool_name", "get_pending_tasks"))
        self.enabled_check.setChecked(data.get("enabled", True))

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "url": self.url_edit.text().strip(),
            "poll_interval": self.poll_spin.value(),
            "tool_name": self.tool_edit.text().strip() or "get_pending_tasks",
            "enabled": self.enabled_check.isChecked(),
        }


# ====================================================================
# LOGS TAB
# ====================================================================

class LogsTab(QWidget):
    """Tab 3: tail del file di log."""

    def __init__(self, log_watcher: LogWatcher, parent=None):
        super().__init__(parent)
        self.watcher = log_watcher
        self._build_ui()
        self.watcher.new_lines.connect(self._append)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_clear = QPushButton("🗑 Pulisci view")
        btn_clear.clicked.connect(self._clear)
        btn_export = QPushButton("💾 Esporta")
        btn_export.clicked.connect(self._export)
        self.autoscroll_check = QCheckBox("Auto-scroll")
        self.autoscroll_check.setChecked(True)
        toolbar.addWidget(btn_clear)
        toolbar.addWidget(btn_export)
        toolbar.addStretch()
        toolbar.addWidget(self.autoscroll_check)
        layout.addLayout(toolbar)

        # Log viewer
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        font = QFont("Monospace")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        self.text.setFont(font)
        layout.addWidget(self.text)

    def _append(self, text: str) -> None:
        self.text.appendPlainText(text.rstrip())
        if self.autoscroll_check.isChecked():
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.text.setTextCursor(cursor)

        # Limita a 50k caratteri per non saturare RAM
        if self.text.document().characterCount() > 50000:
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 1500)
            cursor.removeSelectedText()

    def _clear(self) -> None:
        self.text.clear()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta log", str(BASE_DIR / "logs" / "export.txt"), "Text (*.txt)"
        )
        if path:
            Path(path).write_text(self.text.toPlainText())


# ====================================================================
# CONFIG TAB
# ====================================================================

class ConfigTab(QWidget):
    """Tab 4: editor del config.toml."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_save = QPushButton("💾 Salva")
        btn_save.clicked.connect(self._save)
        btn_reload = QPushButton("↻ Ricarica")
        btn_reload.clicked.connect(self._load)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_reload)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Avviso
        warn = QLabel(
            "⚠️ Salvare il config richiede il riavvio dell'orchestratore per applicare le modifiche."
        )
        warn.setStyleSheet("padding: 8px; background: #fff3cd; color: #856404;")
        layout.addWidget(warn)

        # Editor
        self.editor = QPlainTextEdit()
        font = QFont("Monospace")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.editor.setFont(font)
        layout.addWidget(self.editor)

    def _load(self) -> None:
        if CONFIG_FILE.exists():
            self.editor.setPlainText(CONFIG_FILE.read_text())

    def _save(self) -> None:
        if QMessageBox.question(
            self, "Conferma", "Sovrascrivere config.toml?"
        ) == QMessageBox.Yes:
            CONFIG_FILE.write_text(self.editor.toPlainText())
            QMessageBox.information(self, "OK", "Config salvato.")


# ====================================================================
# MAIN WINDOW
# ====================================================================

class MainWindow(QMainWindow):
    """Finestra principale."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-CIV Control Center")
        self.setMinimumSize(900, 650)

        # Componenti
        self.orchestrator = OrchestratorProcess()
        self.log_watcher = LogWatcher(LOG_FILE)
        self.log_watcher.start()

        # MCP client (opzionale)
        self.mcp_client = None
        if MCP_AVAILABLE and MCPClient:
            self.mcp_client = MCPClient(
                on_task_received=self._on_mcp_task,
                on_status_changed=self._on_mcp_status,
            )
            # Carica server salvati
            for srv_data in load_mcp_servers():
                if srv_data.get("enabled", True):
                    config = McpServerConfig(
                        name=srv_data["name"],
                        url=srv_data["url"],
                        enabled=srv_data.get("enabled", True),
                        poll_interval=srv_data.get("poll_interval", 30),
                        tool_name=srv_data.get("tool_name", "get_pending_tasks"),
                    )
                    self.mcp_client.add_server(config)
            self.mcp_client.start()

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(TaskQueueTab(), "📋 Coda Task")
        self.tabs.addTab(McpServersTab(self.mcp_client), "🔌 MCP Servers")
        self.tabs.addTab(LogsTab(self.log_watcher), "📜 Logs")
        self.tabs.addTab(ConfigTab(), "⚙️ Config")
        self.setCentralWidget(self.tabs)

        # Toolbar
        self._build_toolbar()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

        # Timer per status bar
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_status_bar)
        self.status_timer.start(2000)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.act_start = QAction("▶ Avvia Orchestratore", self)
        self.act_start.triggered.connect(self._on_start)
        toolbar.addAction(self.act_start)

        self.act_stop = QAction("■ Ferma", self)
        self.act_stop.triggered.connect(self._on_stop)
        toolbar.addAction(self.act_stop)

        toolbar.addSeparator()

        self.act_quit = QAction("Esci", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)
        toolbar.addAction(self.act_quit)

    def _on_start(self) -> None:
        if self.orchestrator.start():
            self.status_bar.showMessage("Orchestratore avviato", 3000)
        else:
            self.status_bar.showMessage("Avvio fallito (già in esecuzione?)", 3000)
        self._update_status_bar()

    def _on_stop(self) -> None:
        if self.orchestrator.stop():
            self.status_bar.showMessage("Orchestratore fermato", 3000)
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        if self.orchestrator.is_running():
            pid = self.orchestrator.pid()
            self.status_bar.showMessage(f"● Orchestratore ATTIVO (PID {pid})")
            self.act_start.setEnabled(False)
            self.act_stop.setEnabled(True)
        else:
            self.status_bar.showMessage("○ Orchestratore fermato")
            self.act_start.setEnabled(True)
            self.act_stop.setEnabled(False)

    def _on_mcp_task(self, server_name: str, task: dict) -> None:
        """Callback chiamata quando un server MCP invia un task."""
        # Aggiungi alla coda locale
        tasks = load_tasks()
        task.setdefault("id", f"task-mcp-{int(time.time()*1000)}-{len(tasks)}")
        task.setdefault("status", "pending")
        task.setdefault("attempts", 0)
        task.setdefault("subtasks", [])
        task.setdefault("parent", None)
        task.setdefault("created_at", time.time())
        task["source"] = f"mcp:{server_name}"
        tasks.append(task)
        save_tasks(tasks)
        self.status_bar.showMessage(
            f"Task ricevuto da MCP '{server_name}': {task.get('title', '')[:50]}",
            5000
        )

    def _on_mcp_status(self, server_name: str, status: str) -> None:
        self.status_bar.showMessage(
            f"MCP '{server_name}': {status}", 2000
        )

    def closeEvent(self, event) -> None:
        """Cleanup alla chiusura."""
        if self.orchestrator.is_running():
            reply = QMessageBox.question(
                self, "Conferma uscita",
                "L'orchestratore è ancora attivo. Fermarlo?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Yes:
                self.orchestrator.stop()
        if self.mcp_client:
            self.mcp_client.stop()
        event.accept()


# ====================================================================
# ENTRY POINT
# ====================================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI-CIV Control Center")
    app.setOrganizationName("AI-CIV")

    # Assicura che le dir base esistano
    for d in ("tasks", "state", "logs", "project", "backups"):
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)

    # Crea queue.json se non esiste
    if not TASKS_FILE.exists():
        save_tasks([])

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
