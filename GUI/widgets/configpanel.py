"""
ConfigPanel — estratto da GUI/control_center.py.
"""

from GUI import settings_store
from CORE.constants import BTN_TRANSPARENT_STYLE
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabBar, QStackedWidget, QTextEdit,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QSizePolicy, QSpacerItem, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QPalette, QPixmap, QFont, QBrush, QPen, QPainter, QCursor, QDesktopServices


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
        title.setStyleSheet("font-size:18px; font-weight:bold; ")
        lay.addWidget(title)

        sub = QLabel("Modifica i parametri e premi 'Salva' per applicare. "
                     "Backup automatico in config.toml.bak")
        sub.setStyleSheet("font-size:11px; ")
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
                    ("num_predict", "Max tokens", "spin_int", (64, DEFAULT_NUM_CTX, 64)),
                ]),
                ("Planner", "planner", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, DEFAULT_NUM_CTX, 64)),
                ]),
                ("Worker Coder", "worker_coder", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, DEFAULT_NUM_CTX, 64)),
                ]),
                ("Worker General", "worker_general", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, DEFAULT_NUM_CTX, 64)),
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
            with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2) as r:
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
        self.reset_btn.setStyleSheet(
            "QPushButton { padding:8px 20px; }"
        )
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



