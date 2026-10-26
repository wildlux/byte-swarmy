"""
gui.py — BYTE-SWARMY Control Center (PyQt6)

GUI Qt per controllare l'orchestratore BYTE-SWARMY:
- Tab 1: Coda Task (visualizza, aggiungi, elimina)
- Tab 2: MCP Servers (configura connessioni esterne)
- Tab 3: Logs (tail del file di log in tempo reale)
- Tab 4: Config (editor del config.toml)

Avvio:
    python gui.py

Requisiti:
    pip install PyQt6 mcp httpx httpx-sse
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

# TOML parser (stdlib in 3.11+, fallback to tomli)
try:
    import tomllib
except ImportError:
    import tomli as tomllib

# TOML writer (opzionale, per sync form↔testo)
try:
    import tomli_w
    TOML_WRITER_AVAILABLE = True
except ImportError:
    TOML_WRITER_AVAILABLE = False

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QFileSystemWatcher, QObject
)
from PyQt6.QtGui import (
    QAction, QFont, QColor, QTextCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QMessageBox, QFileDialog, QSplitter, QGroupBox,
    QPlainTextEdit, QToolBar, QStatusBar, QListWidget, QListWidgetItem,
    QScrollArea, QFrame, QTextBrowser, QProgressBar,
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
# ERROR DIALOG (con testo copiabile)
# ====================================================================

class CopyableErrorDialog(QDialog):
    """Dialog di errore con testo selezionabile e copiabile.
    Uso:
        dialog = CopyableErrorDialog("Titolo", "Messaggio lungo...", parent)
        dialog.exec()
    """

    def __init__(self, title: str, message: str, parent=None,
                 is_error: bool = True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self._build_ui(message, is_error)

    def _build_ui(self, message: str, is_error: bool) -> None:
        layout = QVBoxLayout(self)

        # Icona + titolo
        icon = "❌" if is_error else "ℹ️"
        header = QLabel(f"<h3>{icon} {self.windowTitle()}</h3>")
        layout.addWidget(header)

        # Testo selezionabile e copiabile
        text_edit = QPlainTextEdit()
        text_edit.setPlainText(message)
        text_edit.setReadOnly(True)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        text_edit.setFont(font)
        text_edit.setMinimumHeight(150)
        layout.addWidget(text_edit)

        # Pulsanti
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("📋 Copia tutto")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(message))
        btn_close = QPushButton("Chiudi")
        btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        # Seleziona tutto all'apertura
        text_edit.selectAll()


def show_error_dialog(parent, title: str, message: str) -> None:
    """Mostra un dialog di errore con testo copiabile."""
    dialog = CopyableErrorDialog(title, message, parent, is_error=True)
    dialog.exec()


# ====================================================================
# PATH CONSTANTS
# ====================================================================

BASE_DIR = Path(__file__).parent.resolve()
TASKS_FILE = BASE_DIR / "tasks" / "queue.json"
LOG_FILE = BASE_DIR / "logs" / "byte-swarmy.log"
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


def add_task(title: str, description: str, context: str = "",
             task_type: str = "code") -> dict:
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
        "type": task_type,
    }
    tasks.append(task)
    save_tasks(tasks)
    return task


def delete_task(task_id: str) -> None:
    tasks = load_tasks()
    tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(tasks)


def reset_task(task_id: str) -> None:
    """Resetta un task a pending, qualunque sia lo stato attuale.
    Pulisce tentativi, errori, risultato. Funziona anche su 'done' e 'planned'."""
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "pending"
            t["attempts"] = 0
            for k in ("last_error", "failure_reason", "result",
                      "completed_at", "started_at", "reason"):
                t.pop(k, None)
    save_tasks(tasks)


def force_rerun_task(task_id: str) -> None:
    """Forza re-run: resetta il task E elimina i suoi sottotask (se presenti).
    Utile per ripartire da capo con un task già 'planned' o 'done'."""
    tasks = load_tasks()
    # Trova il task
    target = next((t for t in tasks if t["id"] == task_id), None)
    if not target:
        return
    # Elimina i sottotask associati
    subtask_ids = target.get("subtask_ids", [])
    if subtask_ids:
        tasks = [t for t in tasks if t["id"] not in subtask_ids]
    # Resetta il task
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "pending"
            t["attempts"] = 0
            t["subtasks"] = []
            t.pop("subtask_ids", None)
            for k in ("last_error", "failure_reason", "result",
                      "completed_at", "started_at", "reason"):
                t.pop(k, None)
    save_tasks(tasks)


def cleanup_done_tasks() -> int:
    """Elimina tutti i task in stato 'done'. Ritorna il numero eliminati."""
    tasks = load_tasks()
    before = len(tasks)
    tasks = [t for t in tasks if t["status"] != "done"]
    after = len(tasks)
    save_tasks(tasks)
    return before - after


def delete_subtasks(task_id: str) -> int:
    """Elimina i sottotask di un task. Ritorna il numero eliminati."""
    tasks = load_tasks()
    target = next((t for t in tasks if t["id"] == task_id), None)
    if not target:
        return 0
    subtask_ids = target.get("subtask_ids", [])
    if not subtask_ids:
        # Fallback: cerca task con parent == task_id
        subtask_ids = [t["id"] for t in tasks if t.get("parent") == task_id]
    before = len(tasks)
    tasks = [t for t in tasks if t["id"] not in subtask_ids]
    # Pulisce il riferimento nel parent
    for t in tasks:
        if t["id"] == task_id:
            t["subtasks"] = []
            t.pop("subtask_ids", None)
    save_tasks(tasks)
    return before - len(tasks)


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
    new_lines = pyqtSignal(str)
    status = pyqtSignal(str)

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
        btn_refresh = QPushButton("Aggiorna")
        btn_refresh.clicked.connect(self._refresh)
        btn_delete = QPushButton("Elimina")
        btn_delete.clicked.connect(self._on_delete_selected)
        btn_reset = QPushButton("Reset -> pending")
        btn_reset.clicked.connect(self._on_reset_selected)
        btn_rerun = QPushButton("Forza re-run")
        btn_rerun.clicked.connect(self._on_rerun_selected)
        btn_del_subs = QPushButton("Elimina sottotask")
        btn_del_subs.clicked.connect(self._on_delete_subtasks)
        btn_cleanup = QPushButton("Pulisci completati")
        btn_cleanup.clicked.connect(self._on_cleanup_done)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_reset)
        toolbar.addWidget(btn_rerun)
        toolbar.addWidget(btn_del_subs)
        toolbar.addWidget(btn_cleanup)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Statistiche
        self.stats_label = QLabel("Caricamento...")
        self.stats_label.setStyleSheet("padding: 4px; background: #f0f0f0;")
        layout.addWidget(self.stats_label)

        # Tabella
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Stato", "Titolo", "Tipo", "Tentativi", "Sorgente"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
            selected_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            break

        self.table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            id_item = QTableWidgetItem(t["id"])
            id_item.setData(Qt.ItemDataRole.UserRole, t["id"])
            status_item = QTableWidgetItem(t["status"])
            self._color_status(status_item, t["status"])
            title_item = QTableWidgetItem(t.get("title", "")[:80])
            type_item = QTableWidgetItem(t.get("type", "code"))
            # Colore tipo: generic=viola, code=nero
            if t.get("type") == "generic":
                type_item.setForeground(QColor("#9933cc"))
                font = type_item.font()
                font.setBold(True)
                type_item.setFont(font)
            attempts_item = QTableWidgetItem(str(t.get("attempts", 0)))
            source_item = QTableWidgetItem(t.get("source", "manual"))
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, title_item)
            self.table.setItem(i, 3, type_item)
            self.table.setItem(i, 4, attempts_item)
            self.table.setItem(i, 5, source_item)

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
        task_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                self.details_text.setPlainText(json.dumps(t, indent=2, ensure_ascii=False))
                return

    def _on_add_task(self) -> None:
        dialog = AddTaskDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["title"]:
                add_task(
                    title=data["title"],
                    description=data["description"],
                    context=data.get("context", ""),
                    task_type=data.get("type", "code"),
                )
                self._refresh()

    def _on_delete_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        task_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        title = self.table.item(row, 2).text()
        if QMessageBox.question(
            self, "Conferma eliminazione",
            f"Eliminare il task '{title}'?\n(ID: {task_id})"
        ) == QMessageBox.StandardButton.Yes:
            delete_task(task_id)
            self._refresh()

    def _on_reset_selected(self) -> None:
        """Reset a pending: funziona su qualsiasi stato."""
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Reset", "Seleziona un task dalla tabella.")
            return
        row = items[0].row()
        task_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        title = self.table.item(row, 2).text()
        current_status = self.table.item(row, 1).text()

        msg = f"Resettare il task '{title}' a 'pending'?\nStato attuale: {current_status}\n\n"
        msg += "Verranno azzerati: tentativi, errori, risultato."
        if QMessageBox.question(self, "Conferma reset", msg) == QMessageBox.StandardButton.Yes:
            reset_task(task_id)
            self._refresh()

    def _on_rerun_selected(self) -> None:
        """Forza re-run: resetta il task e cancella i sottotask precedenti."""
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Re-run", "Seleziona un task dalla tabella.")
            return
        row = items[0].row()
        task_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        title = self.table.item(row, 2).text()

        msg = (f"Forzare re-run del task '{title}'?\n\n"
               "Verranno eliminati i sottotask precedenti e il task torna a 'pending'. "
               "Il planner lo ri-decomporrà da capo.")
        if QMessageBox.question(self, "Conferma re-run", msg) == QMessageBox.StandardButton.Yes:
            force_rerun_task(task_id)
            self._refresh()

    def _on_delete_subtasks(self) -> None:
        """Elimina i sottotask del task selezionato."""
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Elimina sottotask", "Seleziona un task dalla tabella.")
            return
        row = items[0].row()
        task_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        title = self.table.item(row, 2).text()

        n = delete_subtasks(task_id)
        if n > 0:
            QMessageBox.information(self, "OK", f"Eliminati {n} sottotask del task '{title}'.")
        else:
            QMessageBox.information(self, "Nessun sottotask",
                                    f"Il task '{title}' non ha sottotask.")
        self._refresh()

    def _on_cleanup_done(self) -> None:
        """Elimina tutti i task 'done' dalla coda."""
        tasks = load_tasks()
        done_count = sum(1 for t in tasks if t["status"] == "done")
        if done_count == 0:
            QMessageBox.information(self, "Pulizia", "Nessun task 'done' da eliminare.")
            return
        msg = f"Eliminare {done_count} task completati (stato 'done')?\n"
        msg += "Il codice prodotto resta in project/, viene solo pulita la coda."
        if QMessageBox.question(self, "Conferma pulizia", msg) == QMessageBox.StandardButton.Yes:
            n = cleanup_done_tasks()
            QMessageBox.information(self, "OK", f"Eliminati {n} task completati.")
            self._refresh()


# ====================================================================
# ADD TASK DIALOG
# ====================================================================

class AddTaskDialog(QDialog):
    """Dialog per aggiungere un nuovo task (Code o Generic)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuovo Task")
        self.setMinimumWidth(550)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Tipo di task
        type_group = QGroupBox("Tipo di task")
        type_layout = QVBoxLayout(type_group)
        type_hint = QLabel(
            "<b>Code task</b>: task atomico di programmazione (es. 'scrivi funzione X'). "
            "L'orchestratore lo esegue direttamente o tramite planner classico.<br><br>"
            "<b>Generic task</b>: descrizione ad alto livello (es. 'voglio un editor CLI'). "
            "Il <b>decision model</b> attivo (d3/tev1/nimble/clef/etc.) lo scompone "
            "in 2-8 Code task atomici, che vengono accodati automaticamente."
        )
        type_hint.setWordWrap(True)
        type_hint.setStyleSheet("color: #555; padding: 4px;")
        type_layout.addWidget(type_hint)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Tipo:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Code task (eseguito dal worker)", "code")
        self.type_combo.addItem("Generic task (scomposto dal decision model)", "generic")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo, stretch=1)
        type_layout.addLayout(type_row)
        layout.addWidget(type_group)

        # Form
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("es. Implementa echo server TCP (code) / Voglio un sistema di note in CLI (generic)")
        form.addRow("Titolo:", self.title_edit)

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText(
            "CODE: requisiti, file di output, criteri di test, vincoli (es. max 200 righe).\n"
            "GENERIC: descrivi cosa vuoi. Il decision model pensa a scomporlo."
        )
        self.desc_edit.setMinimumHeight(120)
        form.addRow("Descrizione:", self.desc_edit)

        self.context_edit = QLineEdit()
        self.context_edit.setPlaceholderText("es. progetto nuovo, file esistenti: main.py")
        form.addRow("Contesto:", self.context_edit)
        layout.addLayout(form)

        # Hint
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(self.hint_label)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_type_changed(0)

    def _on_type_changed(self, idx: int) -> None:
        is_generic = self.type_combo.currentData() == "generic"
        if is_generic:
            self.hint_label.setText(
                "💡 Il decision model analizzerà la descrizione e genererà "
                "2-8 Code task atomici. Verifica che un decision model sia "
                "abilitato nel config (sezione [decision_models])."
            )
        else:
            self.hint_label.setText(
                "💡 Suggerimento: includi sempre file di output, linguaggio e criteri di test. "
                "Task semplici (con keyword 'scrivi', 'crea', 'implementa') bypassano il planner."
            )

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
            "context": self.context_edit.text().strip(),
            "type": self.type_combo.currentData(),
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
            import mcp_client as _mc
            banner = QLabel(
                f"Modulo `mcp` non installato. Solo task locali disponibili.\n"
                f"Installa con: pip install mcp httpx httpx-sse\n"
                f"Errore: {_mc.MCP_IMPORT_ERROR}"
            )
            banner.setStyleSheet("padding: 12px; background: #fff3cd; color: #856404;")
            banner.setWordWrap(True)
            layout.addWidget(banner)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ Aggiungi Server")
        btn_add.clicked.connect(self._on_add_server)
        btn_edit = QPushButton("Modifica")
        btn_edit.clicked.connect(self._on_edit_server)
        btn_delete = QPushButton("Elimina")
        btn_delete.clicked.connect(self._on_delete_server)
        btn_discover = QPushButton("Discover Tools")
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
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
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
        ) == QMessageBox.StandardButton.Yes:
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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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
        btn_clear = QPushButton("Pulisci view")
        btn_clear.clicked.connect(self._clear)
        btn_export = QPushButton("Esporta")
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
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self.text.setFont(font)
        layout.addWidget(self.text)

    def _append(self, text: str) -> None:
        self.text.appendPlainText(text.rstrip())
        if self.autoscroll_check.isChecked():
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.text.setTextCursor(cursor)

        # Limita a 50k caratteri per non saturare RAM
        if self.text.document().characterCount() > 50000:
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor, 1500)
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
# CONFIG TAB (con sync bidirezionale form <-> testo)
# ====================================================================

class ConfigTab(QWidget):
    """Tab 4: editor del config.toml con sync bidirezionale.

    - Form a sinistra (con spinbox/lineedit che validano i range)
    - Editor di testo a destra (TOML grezzo)
    - Modifiche al form -> testo aggiornato in tempo reale
    - Modifiche al testo -> form aggiornato se TOML valido, altrimenti errore mostrato
    - "Applica e Salva" -> syntax check + conferma + scrittura su disco
    - Su errore di sintassi: testo mantenuto, form resta all'ultimo valido
    """

    # Definizione dei campi: (label, path, tipo, constraint)
    # path = "sezione.sottochiave" (es. "models.orchestrator.temperature")
    # tipo = "str" | "int" | "float" | "choice" | "list"
    FIELDS = [
        # Ollama
        ("Ollama", [
            ("Host", "ollama.host", "str", None),
            ("Request timeout (s)", "ollama.request_timeout", "int", (5, 600)),
        ]),
        # Modelli
        ("Modello: Orchestrator", [
            ("Nome", "models.orchestrator.name", "str", None),
            ("Temperature", "models.orchestrator.temperature", "float", (0.0, 2.0)),
            ("Top P", "models.orchestrator.top_p", "float", (0.0, 1.0)),
            ("Top K", "models.orchestrator.top_k", "int", (0, 1000)),
            ("Repeat penalty", "models.orchestrator.repeat_penalty", "float", (0.5, 2.0)),
            ("Repeat last N", "models.orchestrator.repeat_last_n", "int", (0, 8192)),
            ("Context", "models.orchestrator.num_ctx", "int", (256, 32768)),
            ("Predict", "models.orchestrator.num_predict", "int", (1, 8192)),
            ("Seed", "models.orchestrator.seed", "int", (0, 2_147_483_647)),
        ]),
        ("Modello: Planner", [
            ("Nome", "models.planner.name", "str", None),
            ("Temperature", "models.planner.temperature", "float", (0.0, 2.0)),
            ("Top P", "models.planner.top_p", "float", (0.0, 1.0)),
            ("Top K", "models.planner.top_k", "int", (0, 1000)),
            ("Repeat penalty", "models.planner.repeat_penalty", "float", (0.5, 2.0)),
            ("Repeat last N", "models.planner.repeat_last_n", "int", (0, 8192)),
            ("Context", "models.planner.num_ctx", "int", (256, 32768)),
            ("Predict", "models.planner.num_predict", "int", (1, 8192)),
        ]),
        ("Modello: Worker Coder", [
            ("Nome", "models.worker_coder.name", "str", None),
            ("Temperature", "models.worker_coder.temperature", "float", (0.0, 2.0)),
            ("Top P", "models.worker_coder.top_p", "float", (0.0, 1.0)),
            ("Top K", "models.worker_coder.top_k", "int", (0, 1000)),
            ("Repeat penalty", "models.worker_coder.repeat_penalty", "float", (0.5, 2.0)),
            ("Repeat last N", "models.worker_coder.repeat_last_n", "int", (0, 8192)),
            ("Context", "models.worker_coder.num_ctx", "int", (256, 32768)),
            ("Predict", "models.worker_coder.num_predict", "int", (1, 8192)),
        ]),
        ("Modello: Worker General", [
            ("Nome", "models.worker_general.name", "str", None),
            ("Temperature", "models.worker_general.temperature", "float", (0.0, 2.0)),
            ("Top P", "models.worker_general.top_p", "float", (0.0, 1.0)),
            ("Top K", "models.worker_general.top_k", "int", (0, 1000)),
            ("Repeat penalty", "models.worker_general.repeat_penalty", "float", (0.5, 2.0)),
            ("Repeat last N", "models.worker_general.repeat_last_n", "int", (0, 8192)),
            ("Context", "models.worker_general.num_ctx", "int", (256, 32768)),
            ("Predict", "models.worker_general.num_predict", "int", (1, 8192)),
        ]),
        ("Modello: Embedding", [
            ("Nome", "models.embedding.name", "str", None),
        ]),
        # Timing
        ("Timing (secondi)", [
            ("Orchestrator tick", "timing.orchestrator_tick", "int", (5, 3600)),
            ("Worker tick", "timing.worker_tick", "int", (5, 3600)),
            ("Health check", "timing.health_check", "int", (30, 7200)),
            ("Git snapshot", "timing.git_snapshot", "int", (60, 86400)),
            ("Memory compaction", "timing.memory_compaction", "int", (300, 86400)),
            ("Backup completo", "timing.backup_complete", "int", (3600, 7 * 86400)),
            ("Model unload idle", "timing.model_unload_idle", "int", (10, 3600)),
        ]),
        # Safety
        ("Safety", [
            ("Max attempts", "safety.max_attempts", "int", (1, 100)),
            ("Max consecutive failures", "safety.max_consecutive_failures", "int", (1, 100)),
            ("Cooldown after failure (s)", "safety.cooldown_after_failure", "int", (0, 3600)),
            ("Swap threshold (0-1)", "safety.swap_threshold", "float", (0.0, 1.0)),
            ("Disk free threshold (MB)", "safety.disk_free_threshold", "disk_mb", None),
            ("Max log size (MB)", "safety.max_log_size", "log_mb", None),
            ("Heartbeat timeout (s)", "safety.heartbeat_timeout", "int", (10, 7200)),
            ("Max tasks per agent per hour", "safety.max_tasks_per_agent_per_hour", "int", (1, 1000)),
            ("Memory compaction threshold", "safety.memory_compaction_threshold", "int", (5, 1000)),
        ]),
        # Routing
        ("Routing", [
            ("Confidence threshold", "routing.confidence_threshold", "float", (0.0, 1.0)),
            ("Max files per task", "routing.max_files_per_task", "int", (1, 100)),
            ("Max file size readable (KB)", "routing.max_file_size_readable", "filesize_kb", None),
            ("Timeout bash (s)", "routing.timeout_bash", "int", (1, 600)),
        ]),
        # Routing: direct keywords (list, gestite separatamente)
        # Logging
        ("Logging", [
            ("Level", "logging.level", "choice", ["DEBUG", "INFO", "WARNING", "ERROR"]),
            ("File", "logging.file", "str", None),
        ]),
        # Decision Models — selettore modello attivo
        ("Decision Models (router/generic planner)", [
            ("Modello attivo", "decision_models.active", "choice",
             ["tev1", "d3", "nimble", "clef", "clef_flash", "nimble_v3",
              "pplx_decider", "kev", "laya", "strands_decider"]),
        ]),
        # Generic Task Planner
        ("Generic Task Planner", [
            ("Abilitato (1=si, 0=no)", "generic_task_planner.enabled", "int", (0, 1)),
            ("Max subtasks", "generic_task_planner.max_subtasks", "int", (2, 20)),
            ("Max tokens risposta", "generic_task_planner.max_tokens", "int", (500, 4000)),
        ]),
        # Thermal (Timestral)
        ("Thermal / Timestral", [
            ("Abilitato (1=si, 0=no)", "thermal.enabled", "int", (0, 1)),
            ("Sample interval (s)", "thermal.sample_interval", "int", (10, 600)),
            ("Temp cold (°C)", "thermal.thresholds.temp_cold", "float", (20.0, 60.0)),
            ("Temp warm (°C)", "thermal.thresholds.temp_warm", "float", (40.0, 80.0)),
            ("Temp hot (°C)", "thermal.thresholds.temp_hot", "float", (60.0, 90.0)),
            ("Temp critical (°C)", "thermal.thresholds.temp_critical", "float", (70.0, 100.0)),
            ("CPU pause threshold (0-1)", "thermal.thresholds.cpu_pause_threshold", "float", (0.5, 1.0)),
        ]),
    ]

    # Campi lista (keywords), gestiti con QPlainTextEdit (uno per riga)
    LIST_FIELDS = [
        ("Routing: Worker Coder keywords (uno per riga)",
         "routing.direct_keywords.worker_coder"),
        ("Routing: Worker General keywords (uno per riga)",
         "routing.direct_keywords.worker_general"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        # Stato interno
        self._syncing = False         # True durante sync programmatico (evita loop)
        self.last_valid_text = ""     # ultimo TOML validato con successo
        self.saved_text = ""          # ultimo TOML salvato su disco
        self._last_error_msg = ""     # ultimo messaggio di errore (per copia)

        # Riferimento ai widget del form: path -> (kind, widget)
        self.form_widgets: dict = {}
        # Riferimento ai widget lista: path -> QPlainTextEdit
        self.list_widgets: dict = {}

        self._build_ui()
        self._load_from_disk()

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar superiore
        toolbar = QHBoxLayout()
        btn_apply = QPushButton("Applica e Salva")
        btn_apply.clicked.connect(self._on_apply)
        btn_reload = QPushButton("Ricarica da disco")
        btn_reload.clicked.connect(self._on_reload)
        btn_revert = QPushButton("Reverti all'ultimo salvato")
        btn_revert.clicked.connect(self._on_revert)
        toolbar.addWidget(btn_apply)
        toolbar.addWidget(btn_reload)
        toolbar.addWidget(btn_revert)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Status label (valid/invalid) + pulsante Copia errore
        status_row = QHBoxLayout()
        self.status_label = QLabel("Caricamento...")
        self.status_label.setStyleSheet("padding: 4px; background: #f0f0f0; font-weight: bold;")
        self.status_label.setMinimumWidth(400)
        # Click sulla label copia il messaggio
        self.status_label.setCursor(Qt.CursorShape.IBeamCursor)
        self.status_label.setToolTip("Click per copiare il messaggio negli appunti")
        self.status_label.mousePressEvent = self._on_status_clicked

        self.btn_copy_error = QPushButton("Copia errore")
        self.btn_copy_error.setToolTip("Copia il messaggio di stato/errore negli appunti")
        self.btn_copy_error.clicked.connect(self._copy_status_to_clipboard)
        self.btn_copy_error.setMaximumWidth(120)

        status_row.addWidget(self.status_label, stretch=1)
        status_row.addWidget(self.btn_copy_error)
        layout.addLayout(status_row)

        # Avviso
        warn = QLabel(
            "Modifica i parametri dal form (sinistra) o dal testo (destra). "
            "Le due viste sono sincronizzate in tempo reale. "
            "Clicca 'Applica e Salva' per scrivere su disco (richiede riavvio orchestratore)."
        )
        warn.setStyleSheet("padding: 8px; background: #fff3cd; color: #856404;")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        # Splitter: form | text editor
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Pannello sinistro: form in scroll area
        form_widget = self._build_form_panel()
        scroll = QScrollArea()
        scroll.setWidget(form_widget)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(450)
        splitter.addWidget(scroll)

        # Pannello destro: editor di testo
        self.editor = QPlainTextEdit()
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.editor.setFont(font)
        splitter.addWidget(self.editor)

        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

        # Connect text editor -> form
        self.editor.textChanged.connect(self._on_text_changed)

        # Banner se tomli_w non disponibile
        if not TOML_WRITER_AVAILABLE:
            banner = QLabel(
                "⚠️ Modulo `tomli_w` non installato. Le modifiche dal FORM non aggiorneranno il testo. "
                "Installa con: pip install tomli-w"
            )
            banner.setStyleSheet("padding: 8px; background: #f8d7da; color: #721c24;")
            layout.addWidget(banner)

    def _build_form_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        # Sezioni definite in FIELDS
        for section_title, fields in self.FIELDS:
            group = QGroupBox(section_title)
            form = QFormLayout(group)
            for label, path, kind, constraint in fields:
                widget = self._create_widget(kind, constraint)
                self.form_widgets[path] = (kind, widget)
                self._connect_widget(path, widget, kind)
                form.addRow(label + ":", widget)
            layout.addWidget(group)

        # Sezione liste (keywords)
        list_group = QGroupBox("Routing: Direct Keywords")
        list_layout = QVBoxLayout(list_group)
        for label, path in self.LIST_FIELDS:
            list_layout.addWidget(QLabel(label))
            edit = QPlainTextEdit()
            edit.setMaximumHeight(80)
            self.list_widgets[path] = edit
            # path catturato per riferimento nel lambda
            edit.textChanged.connect(
                lambda p=path, e=edit: self._on_list_changed(p, e)
            )
            list_layout.addWidget(edit)
        layout.addWidget(list_group)

        layout.addStretch()
        return container

    def _create_widget(self, kind: str, constraint):
        if kind == "str":
            w = QLineEdit()
            return w
        elif kind == "int":
            w = QSpinBox()
            w.setRange(*constraint)
            w.setMaximumWidth(250)
            return w
        elif kind == "float":
            w = QDoubleSpinBox()
            w.setRange(*constraint)
            w.setDecimals(3)
            w.setSingleStep(0.05)
            w.setMaximumWidth(250)
            return w
        elif kind == "choice":
            w = QComboBox()
            for opt in constraint:
                w.addItem(opt)
            return w
        elif kind == "disk_mb":
            # Disk free threshold in MB (range: 1 MB - 1 TB = 1048576 MB)
            # QSpinBox con int32 max ~2.1 miliardi, 1 TB = 1M MB OK
            w = QSpinBox()
            w.setRange(1, 1_048_576)  # 1 MB - 1 TB
            w.setSuffix(" MB")
            w.setSingleStep(100)
            w.setMaximumWidth(250)
            return w
        elif kind == "log_mb":
            # Log size in MB (range: 1 MB - 10 GB)
            w = QSpinBox()
            w.setRange(1, 10_240)  # 1 MB - 10 GB
            w.setSuffix(" MB")
            w.setSingleStep(1)
            w.setMaximumWidth(250)
            return w
        elif kind == "filesize_mb":
            # Max file size readable in MB (range: 1 MB - 10 GB)
            w = QSpinBox()
            w.setRange(1, 10_240)  # 1 MB - 10 GB
            w.setSuffix(" MB")
            w.setSingleStep(1)
            w.setMaximumWidth(250)
            return w
        elif kind == "filesize_kb":
            # Max file size readable in KB (range: 1 KB - 1 GB = 1048576 KB)
            # Usato per valori piccoli come 50000 bytes (~50 KB)
            w = QSpinBox()
            w.setRange(1, 1_048_576)  # 1 KB - 1 GB
            w.setSuffix(" KB")
            w.setSingleStep(10)
            w.setMaximumWidth(250)
            return w
        return QLineEdit()

    def _connect_widget(self, path: str, widget, kind: str) -> None:
        if kind == "str":
            widget.textChanged.connect(lambda v, p=path: self._on_form_changed(p, v, "str"))
        elif kind in ("int", "float"):
            widget.valueChanged.connect(lambda v, p=path: self._on_form_changed(p, v, kind))
        elif kind == "choice":
            widget.currentTextChanged.connect(lambda v, p=path: self._on_form_changed(p, v, "str"))
        elif kind in ("disk_mb", "log_mb", "filesize_mb", "filesize_kb"):
            widget.valueChanged.connect(lambda v, p=path: self._on_form_changed(p, v, kind))

    # ------------------------------------------------------------------
    # Caricamento da disco
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        """Carica config.toml dal disco e popola form + text editor."""
        if not CONFIG_FILE.exists():
            self.status_label.setText("⚠️ config.toml non trovato")
            return
        text = CONFIG_FILE.read_text()
        self.saved_text = text
        self.last_valid_text = text
        self._syncing = True
        self.editor.setPlainText(text)
        self._syncing = False
        # Popola il form
        self._populate_form_from_text(text)
        self._update_status_ok()

    def _populate_form_from_text(self, text: str) -> bool:
        """Parse del testo e aggiorna i widget del form. Ritorna True se OK."""
        try:
            data = tomllib.loads(text)
        except Exception as e:
            self._update_status_error(f"TOML non valido: {e}")
            return False

        self._syncing = True
        # Campi regolari
        for path, (kind, widget) in self.form_widgets.items():
            value = self._get_nested(data, path)
            if value is None:
                continue
            try:
                if kind == "str":
                    widget.setText(str(value))
                elif kind == "int":
                    widget.setValue(int(value))
                elif kind == "float":
                    widget.setValue(float(value))
                elif kind == "choice":
                    widget.setCurrentText(str(value))
                elif kind == "disk_mb":
                    # value in bytes -> MB
                    mb = int(value) // (1024 * 1024)
                    mb = max(widget.minimum(), min(widget.maximum(), mb))
                    widget.setValue(mb)
                elif kind == "log_mb":
                    mb = int(value) // (1024 * 1024)
                    mb = max(widget.minimum(), min(widget.maximum(), mb))
                    widget.setValue(mb)
                elif kind == "filesize_mb":
                    mb = int(value) // (1024 * 1024)
                    mb = max(widget.minimum(), min(widget.maximum(), mb))
                    widget.setValue(mb)
                elif kind == "filesize_kb":
                    kb = int(value) // 1024
                    kb = max(widget.minimum(), min(widget.maximum(), kb))
                    widget.setValue(kb)
            except Exception:
                pass  # ignora tipi non compatibili

        # Liste
        for path, edit in self.list_widgets.items():
            value = self._get_nested(data, path)
            if isinstance(value, list):
                edit.setPlainText("\n".join(value))

        self._syncing = False
        return True

    # ------------------------------------------------------------------
    # Handler: modifiche dal form
    # ------------------------------------------------------------------

    def _on_form_changed(self, path: str, value, kind: str) -> None:
        """Cambiamento in un widget del form. Aggiorna il testo TOML."""
        if self._syncing:
            return

        # Import dinamico di tomli_w (così funziona anche se installato dopo l'avvio)
        try:
            import tomli_w
        except ImportError:
            self._update_status_error(
                "tomli_w non installato. Installalo con: pip install tomli-w"
            )
            return

        # Converti valore al tipo corretto
        if kind == "int":
            value = int(value)
        elif kind == "float":
            value = float(value)
        elif kind in ("disk_mb", "log_mb", "filesize_mb"):
            # MB -> bytes
            value = int(value) * 1024 * 1024
        elif kind == "filesize_kb":
            # KB -> bytes
            value = int(value) * 1024
        else:  # str, choice
            value = str(value)

        # Parse del testo corrente (usa last_valid come base)
        try:
            data = tomllib.loads(self.last_valid_text)
        except Exception:
            data = {}

        # Aggiorna il campo
        self._set_nested(data, path, value)

        # Serializza di nuovo
        try:
            new_text = tomli_w.dumps(data)
        except Exception as e:
            self._update_status_error(f"Errore serializzazione: {e}")
            return

        # Aggiorna editor senza riattivare il signal
        self._syncing = True
        self.editor.setPlainText(new_text)
        self._syncing = False
        self.last_valid_text = new_text
        self._update_status_ok()

    def _on_list_changed(self, path: str, edit: QPlainTextEdit) -> None:
        """Cambiamento in una lista di keyword. Aggiorna il testo TOML."""
        if self._syncing:
            return

        # Import dinamico di tomli_w
        try:
            import tomli_w
        except ImportError:
            self._update_status_error(
                "tomli_w non installato. Installalo con: pip install tomli-w"
            )
            return

        # Estrai le righe non vuote
        items = [line.strip() for line in edit.toPlainText().splitlines() if line.strip()]

        try:
            data = tomllib.loads(self.last_valid_text)
        except Exception:
            data = {}

        self._set_nested(data, path, items)

        try:
            new_text = tomli_w.dumps(data)
        except Exception as e:
            self._update_status_error(f"Errore serializzazione: {e}")
            return

        self._syncing = True
        self.editor.setPlainText(new_text)
        self._syncing = False
        self.last_valid_text = new_text
        self._update_status_ok()

    # ------------------------------------------------------------------
    # Handler: modifiche dal testo
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        """Cambiamento nel text editor. Aggiorna il form se TOML valido."""
        if self._syncing:
            return
        text = self.editor.toPlainText()
        try:
            data = tomllib.loads(text)
        except Exception as e:
            # Testo invalido: mantieni testo (l'utente sta ancora scrivendo),
            # ma mostra errore. NON toccare il form (resta all'ultimo valido).
            self._update_status_error(f"TOML non valido: {e}")
            return

        # Testo valido: aggiorna form + last_valid
        self.last_valid_text = text
        self._populate_form_from_text(text)
        self._update_status_ok()

    # ------------------------------------------------------------------
    # Handler: pulsanti toolbar
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        """Applica: syntax check + conferma + scrittura su disco."""
        text = self.editor.toPlainText()

        # Syntax check rigoroso
        try:
            tomllib.loads(text)
        except Exception as e:
            error_msg = (
                f"Impossibile salvare: il TOML ha errori di sintassi.\n\n"
                f"Errore: {e}\n\n"
                f"--- Contenuto attuale (primi 500 char) ---\n"
                f"{text[:500]}\n\n"
                f"Il file su disco NON e' stato modificato.\n"
                f"Correggi e riprova."
            )
            show_error_dialog(self, "Sintassi non valida", error_msg)
            return

        # Verifica anche che i campi obbligatori ci siano
        missing = self._check_required_fields(text)
        if missing:
            reply = QMessageBox.warning(
                self, "Campi mancanti",
                "Attenzione: i seguenti campi risultano mancanti o vuoti:\n\n"
                + "\n".join(f"  - {m}" for m in missing) +
                "\n\nSalvare comunque?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Conferma finale
        if QMessageBox.question(
            self, "Conferma salvataggio",
            f"Sovrascrivere {CONFIG_FILE.name}?\n"
            "Le modifiche avranno effetto al prossimo riavvio dell'orchestratore.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        ) != QMessageBox.StandardButton.Yes:
            return

        # Scrivi su disco in modo atomico
        try:
            tmp = CONFIG_FILE.with_suffix(".toml.tmp")
            tmp.write_text(text)
            tmp.replace(CONFIG_FILE)
            self.saved_text = text
            self.last_valid_text = text
            self._update_status_ok()
            QMessageBox.information(self, "OK", "Config salvato correttamente.")
        except Exception as e:
            show_error_dialog(
                self, "Errore scrittura",
                f"Impossibile scrivere il file:\n{e}\n\n"
                f"Percorso: {CONFIG_FILE}\n"
                f"Verifica permessi e spazio su disco."
            )

    def _on_reload(self) -> None:
        """Ricarica config.toml dal disco (scarta modifiche)."""
        if QMessageBox.question(
            self, "Ricarica",
            "Scartare tutte le modifiche e ricaricare config.toml dal disco?"
        ) == QMessageBox.StandardButton.Yes:
            self._load_from_disk()

    def _on_revert(self) -> None:
        """Reverti all'ultimo salvato (su disco)."""
        if not self.saved_text:
            QMessageBox.information(self, "Revert", "Nessun salvataggio precedente.")
            return
        if QMessageBox.question(
            self, "Revert",
            "Revertire tutte le modifiche all'ultimo stato salvato su disco?"
        ) == QMessageBox.StandardButton.Yes:
            self._syncing = True
            self.editor.setPlainText(self.saved_text)
            self._syncing = False
            self.last_valid_text = self.saved_text
            self._populate_form_from_text(self.saved_text)
            self._update_status_ok()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _check_required_fields(self, text: str) -> list:
        """Verifica che i campi critici ci siano. Ritorna lista di mancanti."""
        try:
            data = tomllib.loads(text)
        except Exception:
            return ["(TOML non valido)"]

        missing = []
        # Verifica nomi modelli (sono essenziali)
        for model_key in ("orchestrator", "planner", "worker_coder", "worker_general"):
            name = self._get_nested(data, f"models.{model_key}.name")
            if not name:
                missing.append(f"models.{model_key}.name")
        # Verifica sezione timing
        if not self._get_nested(data, "timing.orchestrator_tick"):
            missing.append("timing.orchestrator_tick")
        return missing

    def _get_nested(self, data: dict, path: str):
        """Ottiene un valore annidato. path = "a.b.c" """
        keys = path.split(".")
        cur = data
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def _set_nested(self, data: dict, path: str, value) -> None:
        """Imposta un valore annidato, creando i dict intermedi. path = "a.b.c" """
        keys = path.split(".")
        cur = data
        for k in keys[:-1]:
            if k not in cur or not isinstance(cur[k], dict):
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = value

    def _update_status_ok(self) -> None:
        self.status_label.setText("✓ TOML valido - modifiche non salvate")
        self.status_label.setStyleSheet(
            "padding: 4px; background: #d4edda; color: #155724; font-weight: bold;"
        )

    def _update_status_error(self, msg: str) -> None:
        self.status_label.setText(f"✗ {msg}")
        self.status_label.setStyleSheet(
            "padding: 4px; background: #f8d7da; color: #721c24; font-weight: bold;"
        )
        # Salva il messaggio per copia facile
        self._last_error_msg = msg

    def _on_status_clicked(self, event) -> None:
        """Click sulla label di stato -> copia negli appunti."""
        self._copy_status_to_clipboard()

    def _copy_status_to_clipboard(self) -> None:
        """Copia il messaggio di stato/errore negli appunti."""
        text = self.status_label.text()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        # Feedback visivo breve
        original = self.status_label.text()
        self.status_label.setText("📋 Copiato negli appunti")
        QTimer.singleShot(1500, lambda: self.status_label.setText(original))


# ====================================================================
# THERMAL TAB (Timestral — monitor CPU/temperatura + advice)
# ====================================================================

class ThermalTab(QWidget):
    """Tab 5: Timestral — monitor termico in tempo reale.

    Mostra:
    - Ultimo campione (temp, load, freq, mem, swap, n_proc)
    - Advice corrente (normal/slow/fast/pause) con motivo
    - Statistiche ultime 24h (min/max/avg)
    - Storico testuale (ultimi N campioni)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timestral = None
        self._build_ui()

        # Auto-refresh ogni 5s
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(5000)

        # Refresh iniziale dopo 1s (per dare tempo all'orchestratore di partire)
        QTimer.singleShot(1000, self._refresh)

    def set_timestral(self, timestral) -> None:
        """Inietta il TimestralManager (creato dall'orchestratore)."""
        self.timestral = timestral

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Banner informativo
        info = QLabel(
            "<b>Timestral — Monitoraggio termico + dynamic tuning</b><br>"
            "L'orchestratore consulta Timestral a ogni tick. Se la CPU è troppo calda, "
            "rallenta o mette in pausa il dispatch dei task per proteggere l'hardware.<br>"
            "Storico salvato in <code>state/timestral_history.json</code> (24h di campioni)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding: 8px; background: #e8f4fd;")
        layout.addWidget(info)

        # Status corrente
        status_group = QGroupBox("Stato corrente")
        status_layout = QFormLayout(status_group)
        self.advice_label = QLabel("...")
        self.advice_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.reason_label = QLabel("...")
        self.reason_label.setWordWrap(True)
        self.sample_label = QLabel("...")
        self.sample_label.setStyleSheet("font-family: monospace;")
        status_layout.addRow("Advice:", self.advice_label)
        status_layout.addRow("Motivo:", self.reason_label)
        status_layout.addRow("Ultimo campione:", self.sample_label)
        layout.addWidget(status_group)

        # Metriche live (4 cards)
        metrics_row = QHBoxLayout()
        self.metric_temp = self._make_metric_card("Temperatura", "°C", "#dc3545")
        self.metric_load = self._make_metric_card("CPU Load", "%", "#fd7e14")
        self.metric_freq = self._make_metric_card("CPU Freq", "MHz", "#007bff")
        self.metric_mem = self._make_metric_card("RAM usata", "%", "#28a745")
        metrics_row.addWidget(self.metric_temp)
        metrics_row.addWidget(self.metric_load)
        metrics_row.addWidget(self.metric_freq)
        metrics_row.addWidget(self.metric_mem)
        layout.addLayout(metrics_row)

        # Soglie
        thresholds_group = QGroupBox("Soglie (da config.toml)")
        thresholds_layout = QFormLayout(thresholds_group)
        self.thresholds_label = QLabel("...")
        self.thresholds_label.setStyleSheet("font-family: monospace;")
        thresholds_layout.addRow("", self.thresholds_label)
        layout.addWidget(thresholds_group)

        # Statistiche 24h
        stats_group = QGroupBox("Statistiche ultime 24h")
        stats_layout = QFormLayout(stats_group)
        self.stats_label = QLabel("...")
        self.stats_label.setStyleSheet("font-family: monospace;")
        stats_layout.addRow("", self.stats_label)
        layout.addWidget(stats_group)

        # Storico testuale
        history_group = QGroupBox("Storico recente (ultimi 20 campioni)")
        history_layout = QVBoxLayout(history_group)
        self.history_text = QPlainTextEdit()
        self.history_text.setReadOnly(True)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self.history_text.setFont(font)
        self.history_text.setMaximumHeight(150)
        history_layout.addWidget(self.history_text)
        layout.addWidget(history_group)

        layout.addStretch()

    def _make_metric_card(self, title: str, unit: str, color: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setStyleSheet(f"QGroupBox::title {{ color: {color}; font-weight: bold; }}")
        layout = QVBoxLayout(card)
        value_label = QLabel("--")
        value_label.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        card._value_label = value_label
        card._unit = unit
        return card

    def _refresh(self) -> None:
        # Prova a ottenere il timestral dall'orchestratore in esecuzione
        if not self.timestral:
            self.advice_label.setText("○ Timestral non attivo")
            self.advice_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #909090;")
            self.reason_label.setText("L'orchestratore non sta girando o Timestral è disabilitato nel config.")
            return

        advice = self.timestral.get_advice()
        s = advice.sample

        # Advice label
        colors = {
            "normal": "#28a745",
            "slow": "#fd7e14",
            "fast": "#17a2b8",
            "pause": "#dc3545",
        }
        icons = {
            "normal": "🟢",
            "slow": "🟠",
            "fast": "🔵",
            "pause": "🔴",
        }
        c = colors.get(advice.action, "#000000")
        i = icons.get(advice.action, "❓")
        self.advice_label.setText(f"{i} {advice.action.upper()}")
        self.advice_label.setStyleSheet(
            f"font-weight: bold; font-size: 14pt; color: {c};"
        )
        self.reason_label.setText(advice.reason)

        # Sample details
        if s:
            self.sample_label.setText(
                f"ts={time.strftime('%H:%M:%S', time.localtime(s.timestamp))} | "
                f"temp={s.cpu_temp_max:.1f}°C | "
                f"load={s.cpu_load*100:.0f}% | "
                f"freq={s.cpu_freq_avg//1000}MHz | "
                f"mem={s.mem_used_ratio*100:.0f}% | "
                f"swap={s.swap_used_ratio*100:.0f}% | "
                f"proc={s.n_processes}"
            )
            # Aggiorna metric cards
            self.metric_temp._value_label.setText(f"{s.cpu_temp_max:.1f}")
            self.metric_load._value_label.setText(f"{s.cpu_load*100:.0f}")
            self.metric_freq._value_label.setText(f"{s.cpu_freq_avg//1000}")
            self.metric_mem._value_label.setText(f"{s.mem_used_ratio*100:.0f}")

        # Soglie
        th = self.timestral.thresholds
        self.thresholds_label.setText(
            f"temp_cold  = {th['temp_cold']:.1f}°C  (ottimizza)\n"
            f"temp_warm  = {th['temp_warm']:.1f}°C  (rallenta x1.7)\n"
            f"temp_hot   = {th['temp_hot']:.1f}°C   (rallenta x2.5)\n"
            f"temp_crit  = {th['temp_critical']:.1f}°C (PAUSA)\n"
            f"cpu_pause  = {th['cpu_pause_threshold']*100:.0f}%  per 60s (PAUSA)"
        )

        # Statistiche 24h
        stats = self.timestral.get_stats()
        if stats.get("samples", 0) > 0:
            self.stats_label.setText(
                f"Campioni: {stats['samples']}  |  "
                f"Periodo: {time.strftime('%H:%M', time.localtime(stats['first_ts']))} - "
                f"{time.strftime('%H:%M', time.localtime(stats['last_ts']))}\n"
                f"Temp:  min {stats['temp_min']:.1f}°C  max {stats['temp_max']:.1f}°C  "
                f"avg {stats['temp_avg']:.1f}°C\n"
                f"Load:  min {stats['load_min']*100:.0f}%  max {stats['load_max']*100:.0f}%  "
                f"avg {stats['load_avg']*100:.0f}%"
            )
        else:
            self.stats_label.setText("(nessun campione ancora)")

        # Storico recente
        history = self.timestral.get_history(last_n=20)
        if history:
            lines = []
            for s in reversed(history):  # più recenti in alto
                lines.append(
                    f"{time.strftime('%H:%M:%S', time.localtime(s['timestamp']))} | "
                    f"temp={s['cpu_temp_max']:5.1f}°C | "
                    f"load={s['cpu_load']*100:3.0f}% | "
                    f"freq={s['cpu_freq_avg']//1000:4d}MHz | "
                    f"mem={s['mem_used_ratio']*100:3.0f}% | "
                    f"swap={s['swap_used_ratio']*100:3.0f}%"
                )
            self.history_text.setPlainText("\n".join(lines))


# ====================================================================
# MAIN WINDOW
# ====================================================================

class MainWindow(QMainWindow):
    """Finestra principale."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BYTE-SWARMY · Control Center")
        self.setMinimumSize(900, 650)

        # Componenti
        self.orchestrator = OrchestratorProcess()
        self.log_watcher = LogWatcher(LOG_FILE)
        self.log_watcher.start()

        # Timestral locale (la GUI monitora anche se l'orchestratore è fermo)
        self.timestral = None
        try:
            import sys as _sys
            _sys.path.insert(0, str(BASE_DIR))
            from thermal_manager import TimestralManager
            import logging as _logging
            _log = _logging.getLogger("byte-swarmy-gui")
            _log.addHandler(_logging.NullHandler())
            # Carica config per soglie
            try:
                with open(CONFIG_FILE, "rb") as f:
                    _cfg = tomllib.load(f)
            except Exception:
                _cfg = {"thermal": {"enabled": True}}
            self.timestral = TimestralManager(_cfg, _log, base_dir=BASE_DIR)
            self.timestral.start()
        except Exception as e:
            print(f"WARNING: cannot start local Timestral: {e}")
            self.timestral = None

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
        self.task_tab = TaskQueueTab()
        self.mcp_tab = McpServersTab(self.mcp_client)
        self.logs_tab = LogsTab(self.log_watcher)
        self.thermal_tab = ThermalTab()
        self.config_tab = ConfigTab()
        self.tabs.addTab(self.task_tab, "Coda Task")
        self.tabs.addTab(self.mcp_tab, "MCP Servers")
        self.tabs.addTab(self.logs_tab, "Logs")
        self.tabs.addTab(self.thermal_tab, "Timestral (Termico)")
        self.tabs.addTab(self.config_tab, "Config")
        self.setCentralWidget(self.tabs)

        # Collega il Timestral locale al tab Thermal
        if self.timestral:
            self.thermal_tab.set_timestral(self.timestral)

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

        self.act_start = QAction("Avvia Orchestratore", self)
        self.act_start.triggered.connect(self._on_start)
        toolbar.addAction(self.act_start)

        self.act_stop = QAction("Ferma", self)
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
        """Callback chiamata quando un server MCP invia un task.

        I task MCP sono dati NON fidati: si tengono solo i campi utili,
        con limiti di lunghezza. `id`, `status`, `parent` e `subtasks`
        non possono essere imposti dall'esterno.
        """
        if not isinstance(task, dict):
            return

        def _clean(value, limit: int) -> str:
            if not isinstance(value, str):
                return ""
            return value.replace("\x00", "").strip()[:limit]

        title = _clean(task.get("title"), 160) or "task-from-mcp"
        description = _clean(task.get("description"), 4000)
        context = _clean(task.get("context"), 2000)
        task_type = task.get("type", "code")
        if task_type not in ("generic", "code", "implement", "test", "fix", "document"):
            task_type = "code"

        # Aggiungi alla coda locale con campi controllati da noi.
        tasks = load_tasks()
        new_task = {
            "id": f"task-mcp-{int(time.time()*1000)}-{len(tasks)}",
            "title": title,
            "description": description,
            "context": context,
            "type": task_type,
            "status": "pending",
            "attempts": 0,
            "subtasks": [],
            "parent": None,
            "created_at": time.time(),
            "source": f"mcp:{server_name}",
        }
        tasks.append(new_task)
        save_tasks(tasks)
        self.status_bar.showMessage(
            f"Task ricevuto da MCP '{server_name}': {title[:50]}",
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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.orchestrator.stop()
        if self.mcp_client:
            self.mcp_client.stop()
        if self.timestral:
            self.timestral.stop()
        event.accept()


# ====================================================================
# ENTRY POINT
# ====================================================================

def check_dependencies() -> bool:
    """Verifica tutte le dipendenze prima di avviare la GUI.
    Ritorna True se tutto OK, False se manca qualcosa di critico.
    Prova ad auto-installare le dipendenze opzionali (tomli-w, mcp)."""

    # 1. PyQt6 — CRITICA, non si può auto-installare (richiede compilazione)
    try:
        import PyQt6  # noqa
    except ImportError:
        # Messaggio a console (non possiamo usare QMessageBox senza PyQt6)
        print("=" * 60, file=sys.stderr)
        print("ERRORE: PyQt6 non installato", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(file=sys.stderr)
        print("Installa con:", file=sys.stderr)
        print("  pip install PyQt6", file=sys.stderr)
        print(file=sys.stderr)
        print("Se fallisce su Python 3.14, installa Python 3.12:", file=sys.stderr)
        print("  sudo apt install python3.12 python3.12-venv", file=sys.stderr)
        print("  python3.12 -m venv .venv-gui", file=sys.stderr)
        print("  source .venv-gui/bin/activate", file=sys.stderr)
        print("  pip install PyQt6", file=sys.stderr)
        # Prova installazione automatica (su alcune distro funziona)
        print(file=sys.stderr)
        print("Tentativo di installazione automatica...", file=sys.stderr)
        if _try_install("PyQt6"):
            try:
                import PyQt6  # noqa
                print("OK: PyQt6 installato.", file=sys.stderr)
            except ImportError:
                print("ERRORE: installazione fallita. Installa manualmente.", file=sys.stderr)
                return False
        else:
            return False

    # A questo punto PyQt6 e' disponibile: possiamo usare QMessageBox per i dialog
    from PyQt6.QtWidgets import QMessageBox
    app = QApplication.instance()  # None se non ancora creata
    # Crea QApplication temporanea se serve solo per il check (la main() ne creera' un'altra)
    temp_app = None
    if app is None:
        temp_app = QApplication(sys.argv)

    # 2. tomli (parser TOML) — CRITICA, in stdlib da 3.11
    try:
        import tomllib  # noqa
    except ImportError:
        try:
            import tomli  # noqa
        except ImportError:
            QMessageBox.critical(
                None, "Dipendenza mancante",
                "Modulo 'tomli' non disponibile (necessario per parsare config.toml).\n\n"
                "Usa Python 3.11+ oppure installa:\n  pip install tomli"
            )
            return False

    # 3. tomli-w (writer TOML) — OPZIONALE ma raccomandata, auto-installabile
    global TOML_WRITER_AVAILABLE
    try:
        import tomli_w  # noqa
        TOML_WRITER_AVAILABLE = True
    except ImportError:
        reply = QMessageBox.question(
            None, "Modulo opzionale mancante",
            "Il modulo 'tomli-w' non e' installato.\n\n"
            "Serve per sincronizzare le modifiche dal FORM al testo del config.\n"
            "Senza di esso, puoi modificare solo dal testo.\n\n"
            "Vuoi installarlo automaticamente ora? (richiede ~5 secondi)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            if _try_install("tomli-w"):
                try:
                    import tomli_w  # noqa
                    TOML_WRITER_AVAILABLE = True
                    QMessageBox.information(None, "OK", "tomli-w installato con successo.")
                except ImportError:
                    QMessageBox.warning(
                        None, "Avviso",
                        "Installazione apparentemente riuscita ma import fallito.\n"
                        "Riavvia la GUI. Se persiste, installa manualmente:\n  pip install tomli-w"
                    )
            else:
                QMessageBox.warning(
                    None, "Installazione fallita",
                    "Impossibile installare tomli-w automaticamente.\n\n"
                    "Il form funzionera' in sola lettura dal testo.\n"
                    "Installa manualmente:\n  pip install tomli-w"
                )

    # 4. mcp — OPZIONALE (per task via MCP), auto-installabile
    global MCP_AVAILABLE
    try:
        import mcp  # noqa
        MCP_AVAILABLE = True
    except ImportError:
        reply = QMessageBox.question(
            None, "Modulo opzionale mancante",
            "Il modulo 'mcp' non e' installato.\n\n"
            "Serve per ricevere task da server MCP esterni.\n"
            "Senza di esso, puoi usare solo task locali.\n\n"
            "Vuoi installarlo automaticamente ora? (richiede ~30 secondi, "
            "installa anche httpx e httpx-sse)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Installa mcp + dipendenze
            ok = _try_install("mcp") and _try_install("httpx-sse")
            if ok:
                try:
                    import mcp  # noqa
                    MCP_AVAILABLE = True
                    QMessageBox.information(None, "OK", "mcp installato con successo.")
                except ImportError:
                    QMessageBox.warning(
                        None, "Avviso",
                        "Installazione riuscita ma import fallito.\n"
                        "Riavvia la GUI."
                    )
            else:
                QMessageBox.warning(
                    None, "Installazione fallita",
                    "Impossibile installare mcp automaticamente.\n\n"
                    "Il tab MCP sara' disabilitato (solo task locali).\n"
                    "Installa manualmente:\n  pip install mcp httpx httpx-sse"
                )

    return True


def _try_install(package: str) -> bool:
    """Tenta di installare un pacchetto pip. Ritorna True se OK.
    Usa sys.executable per rispettare il venv attivo.

    Solo i pacchetti previsti dalla GUI: un nome arbitrario non deve mai
    arrivare a pip (difesa contro input non fidato).
    """
    allowed = {"PyQt6", "tomli-w", "mcp", "httpx", "httpx-sse"}
    if package not in allowed:
        return False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Errore installazione {package}: {e}", file=sys.stderr)
        return False


def main():
    # 1. Check dipendenze PRIMA di creare QApplication definitiva
    # check_dependencies() puo' creare una QApplication temporanea per i dialog
    if not check_dependencies():
        sys.exit(1)

    # 2. Usa la QApplication esistente (creata dentro check_dependencies) o creane una nuova
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("BYTE-SWARMY Control Center")
    app.setOrganizationName("BYTE-SWARMY")

    # 3. Assicura che le dir base esistano
    for d in ("tasks", "state", "logs", "project", "backups"):
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)

    # 4. Crea queue.json se non esiste
    if not TASKS_FILE.exists():
        save_tasks([])

    # 5. Mostra la finestra
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
