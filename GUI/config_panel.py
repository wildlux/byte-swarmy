"""config_panel.py — Pannello configurazione con tutti i parametri modificabili.

Estratto da GUI/control_center.py per ridurre il monolite.
"""

from __future__ import annotations

import json
import urllib.request

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QFormLayout, QCheckBox, QLineEdit, QTextEdit, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt

from CORE.constants import DEFAULT_NUM_CTX, OLLAMA_HOST
from GUI.collapsible_section import CollapsibleSection
from GUI.gui_backend import load_config


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
                    ("top_p", "Top P", "spin_float", (0.0, 1.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, DEFAULT_NUM_CTX, 64)),
                    ("no_tools", "Modalità diretta (senza tool)", "check", None),
                ]),
                ("Worker General", "worker_general", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, DEFAULT_NUM_CTX, 64)),
                    ("no_tools", "Modalità diretta (senza tool)", "check", None),
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
        """Costruisce una sezione collassabile con i campi.

        Supporta due formati (fix: la sezione "🧠 Modelli LLM" è annidata):
          - fields = [(nome, label, tipo, params), ...] → campi piatti
            (i widget si registrano come "{path}.{nome}" in _widgets)
          - fields = [(sub_titolo, sub_path, sub_fields), ...] →
            sotto-sezioni annidate (es. Orchestratore/Planner/Worker…)
        """
        section = CollapsibleSection(title, icon="⚙")
        try:
            data = self._get_nested(self._config, path)
        except Exception:
            data = {}

        if not data and not fields:
            section.add_widget(QLabel(f"<i>Sezione {path} non presente nel config</i>"))
            return section

        # Sotto-sezioni annidate: ogni campo è (titolo, sub_path, campi)
        if fields and all(
                isinstance(f, (tuple, list)) and len(f) == 3
                and isinstance(f[2], (list, tuple))
                for f in fields):
            for sub_title, sub_path, sub_fields in fields:
                section.add_widget(self._build_section(
                    sub_title, f"{path}.{sub_path}", sub_fields))
            return section

        form = QFormLayout()
        form.setSpacing(6)
        form.setContentsMargins(10, 8, 10, 8)

        for field_name, label, wtype, params in fields:
            widget = self._make_widget(wtype, value=self._get_nested(data, field_name) if data else None, params=params)
            if widget is not None:
                form.addRow(label, widget)
                self._widgets[f"{path}.{field_name}"] = widget

        # NB: CollapsibleSection NON ha add_layout (solo add_widget):
        # il QFormLayout va incartato in un QWidget (helper _wrap_form).
        section.add_widget(self._wrap_form(form))
        return section

    def _wrap_form(self, form_layout):
        wrap = QWidget()
        wrap.setLayout(form_layout)
        return wrap

    def _make_widget(self, wtype, value, params):
        if wtype == "combo":
            cb = QComboBox()
            cb.addItems(self._available_models)
            if value:
                cb.setCurrentText(str(value))
            return cb
        if wtype == "combo_decision":
            cb = QComboBox()
            cb.addItems(["qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b", "tev1:4b"])
            if value:
                cb.setCurrentText(str(value))
            return cb
        if wtype == "spin_int":
            lo, hi, step = params
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(step)
            if value is not None:
                try:
                    sb.setValue(int(value))
                except Exception:
                    pass
            return sb
        if wtype == "spin_float":
            lo, hi, step = params
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(step)
            sb.setDecimals(3)
            if value is not None:
                try:
                    sb.setValue(float(value))
                except Exception:
                    pass
            return sb
        if wtype == "check":
            cb = QCheckBox()
            if value is not None:
                cb.setChecked(bool(value))
            return cb
        return None

    def _get_nested(self, d, path):
        cur = d
        for part in str(path).split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    def _set_nested(self, d, path, value):
        keys = str(path).split(".")
        cur = d
        for k in keys[:-1]:
            if k not in cur:
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = value

    def _collect_values(self):
        result = {}
        for path_key, widget in self._widgets.items():
            if isinstance(widget, QComboBox):
                result[path_key] = widget.currentText()
            elif isinstance(widget, QSpinBox):
                result[path_key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                result[path_key] = widget.value()
            elif isinstance(widget, QCheckBox):
                result[path_key] = widget.isChecked()
        return result

    def _save(self):
        try:
            import tomli_w
        except Exception:
            QMessageBox.warning(self, "Errore", "tomli_w non installato: impossibile salvare config.toml")
            return
        new_values = self._collect_values()
        for path_key, value in new_values.items():
            self._set_nested(self._config, path_key, value)
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        path = "CONFIG/config.toml"
        backup = path + ".bak"
        try:
            import shutil
            shutil.copy2(path, backup)
        except Exception:
            pass
        with open(path, "wb") as f:
            tomli_w.dump(self._config, f)
        QMessageBox.information(self, "Salvato", f"Configurazione salvata in {path}\nBackup: {backup}")

    def _reset(self):
        self._widgets.clear()
        self._build_ui()

    def _apply(self):
        self._save()
        QMessageBox.information(self, "Riavvio", "Applica le modifiche e riavvia l'orchestratore.")
