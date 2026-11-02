"""Pannello Code Task Scheduler per BYTE-SWARMY.

Permette di schedulare task (compiti) a orari specifici: uno-shot a
una certa data/ora, oppure ricorrenti (ogni N secondi, ogni giorno alle HH:MM).

La schedulazione è salvata in CONFIG/scheduled_tasks.json ed eseguita
dall'orchestratore tramite un timer (in futuro). Per ora il pannello
permette di creare/eliminare/visualizzare task schedulati.
"""
import json
import os
from typing import Dict, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QLineEdit, QDateTimeEdit, QSpinBox, QGroupBox,
    QFormLayout, QScrollArea, QListWidget, QListWidgetItem, QMessageBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QDateTime, pyqtSignal

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULED_FILE = os.path.join(_BASE, "CONFIG", "scheduled_tasks.json")

DEFAULTS = {"tasks": []}


def load_scheduled() -> List[Dict]:
    if not os.path.exists(SCHEDULED_FILE):
        return []
    try:
        with open(SCHEDULED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tasks", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_scheduled(tasks: List[Dict]) -> bool:
    try:
        os.makedirs(os.path.dirname(SCHEDULED_FILE), exist_ok=True)
        with open(SCHEDULED_FILE, "w", encoding="utf-8") as f:
            json.dump({"tasks": tasks}, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f"Errore salvataggio scheduled tasks: {e}")
        return False


def add_scheduled_task(task: Dict) -> bool:
    tasks = load_scheduled()
    tasks.append(task)
    return save_scheduled(tasks)


def remove_scheduled_task(idx: int) -> bool:
    tasks = load_scheduled()
    if 0 <= idx < len(tasks):
        tasks.pop(idx)
        return save_scheduled(tasks)
    return False


class TaskSchedulerPanel(QWidget):
    """Pannello per schedulare task (Code Task) a orari specifici."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("task_scheduler_panel")
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia")
        back.setObjectName("back_btn")
        back.setStyleSheet(
            "QPushButton#back_btn { background:#e8e8ec; color:#1a1a1a; "
            "border:none; padding:8px 16px; border-radius:6px; font-size:12px; }"
            "QPushButton#back_btn:hover { background:#d0d0d0; }"
        )
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>⏰ Code Task Scheduler</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 0, 0, 0)

        # Spiegazione
        expl = QLabel(
            "Schedula qui i compiti (Code Task) a orari previsti. "
            "Un task può essere <b>uno-shot</b> (una volta sola a una certa "
            "data/ora) oppure <b>ricorrente</b> (ogni N secondi, oppure "
            "ogni giorno alle HH:MM)."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet(
            "background:#fffbeb; border:1px solid #fde68a; border-radius:8px; "
            "padding:10px; font-size:11px; color:#92400e;"
        )
        lay.addWidget(expl)

        # Form per aggiungere un task
        form_box = QGroupBox("➕ Nuovo task schedulato")
        form_box.setStyleSheet(self._group_style())
        form = QFormLayout(form_box)
        form.setSpacing(8)
        form.setContentsMargins(14, 14, 14, 14)

        self.task_title = QLineEdit()
        self.task_title.setPlaceholderText("Es. Analisi sicurezza settimanale")
        self.task_title.setStyleSheet(self._input_style())
        form.addRow("Titolo:", self.task_title)

        self.task_prompt = QLineEdit()
        self.task_prompt.setPlaceholderText("Prompt del compito da eseguire")
        self.task_prompt.setStyleSheet(self._input_style())
        form.addRow("Prompt:", self.task_prompt)

        self.task_type = QComboBox()
        self.task_type.addItem("🕐 Uno-shot (una volta)", "oneshot")
        self.task_type.addItem("🔁 Ricorrente (ogni N secondi)", "interval")
        self.task_type.addItem("📅 Giornaliero (alle HH:MM)", "daily")
        self.task_type.currentIndexChanged.connect(self._on_type_changed)
        self.task_type.setStyleSheet(self._combo_style())
        form.addRow("Tipo:", self.task_type)

        # Per oneshot: data/ora
        self.task_datetime = QDateTimeEdit()
        self.task_datetime.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.task_datetime.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.task_datetime.setStyleSheet(self._input_style())
        form.addRow("Data/Ora (uno-shot):", self.task_datetime)

        # Per interval: ogni quanti secondi
        self.task_interval = QSpinBox()
        self.task_interval.setRange(60, 86400)
        self.task_interval.setSuffix(" s")
        self.task_interval.setValue(3600)
        self.task_interval.setStyleSheet(self._input_style())
        form.addRow("Intervallo (ricorrente):", self.task_interval)

        # Per daily: a che ora
        self.task_time = QLineEdit("09:00")
        self.task_time.setInputMask("00:00")
        self.task_time.setStyleSheet(self._input_style())
        form.addRow("Orario (giornaliero):", self.task_time)

        # Modello da usare (opzionale)
        self.task_model = QComboBox()
        self.task_model.setEditable(True)
        self.task_model.addItems([
            "(default)", "qwen2.5:1.5b", "qwen2.5-coder:1.5b",
            "llama3:8b", "mistral:7b", "phi3:mini",
        ])
        self.task_model.setStyleSheet(self._combo_style())
        form.addRow("Modello LLM:", self.task_model)

        # Pulsante aggiungi
        add_btn = QPushButton("➕ Aggiungi task")
        add_btn.setStyleSheet(
            "QPushButton { background:#16a34a; color:#ffffff; border:none; "
            "padding:8px 16px; border-radius:6px; font-weight:bold; font-size:12px; }"
            "QPushButton:hover { background:#15803d; }"
        )
        add_btn.clicked.connect(self._on_add_task)
        form.addRow("", add_btn)

        lay.addWidget(form_box)

        # Lista task schedulati
        list_box = QGroupBox("📋 Task schedulati")
        list_box.setStyleSheet(self._group_style())
        list_lay = QVBoxLayout(list_box)
        list_lay.setContentsMargins(14, 14, 14, 14)
        list_lay.setSpacing(6)

        self.task_list_widget = QListWidget()
        self.task_list_widget.setStyleSheet(
            "QListWidget { background:#fafafa; border:1px solid #e0e0e0; "
            "border-radius:6px; padding:4px; font-size:12px; }"
            "QListWidget::item { padding:8px; border-bottom:1px solid #f0f0f0; }"
            "QListWidget::item:selected { background:#f0f9ff; color:#16a34a; }"
        )
        list_lay.addWidget(self.task_list_widget)

        # Pulsante elimina
        del_row = QHBoxLayout()
        del_btn = QPushButton("🗑️ Elimina selezionato")
        del_btn.setStyleSheet(
            "QPushButton { background:#dc2626; color:#ffffff; border:none; "
            "padding:8px 16px; border-radius:6px; font-weight:bold; font-size:12px; }"
            "QPushButton:hover { background:#b91c1c; }"
        )
        del_btn.clicked.connect(self._on_del_task)
        del_row.addWidget(del_btn)
        del_row.addStretch()
        list_lay.addLayout(del_row)

        lay.addWidget(list_box)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # Inizializza la visibilità dei campi in base al tipo
        self._on_type_changed(0)

    def _on_type_changed(self, _idx: int):
        t = self.task_type.currentData()
        # Mostra solo i campi rilevanti
        self.task_datetime.setVisible(t == "oneshot")
        self.task_interval.setVisible(t == "interval")
        self.task_time.setVisible(t == "daily")

    def _on_add_task(self):
        title = self.task_title.text().strip()
        prompt = self.task_prompt.text().strip()
        if not title or not prompt:
            QMessageBox.warning(self, "Dati mancanti",
                                "Inserisci almeno titolo e prompt del task.")
            return
        t = self.task_type.currentData()
        task = {
            "title": title,
            "prompt": prompt,
            "type": t,
            "model": self.task_model.currentText(),
        }
        if t == "oneshot":
            task["datetime"] = self.task_datetime.dateTime().toString("yyyy-MM-dd HH:mm")
        elif t == "interval":
            task["interval_sec"] = self.task_interval.value()
        elif t == "daily":
            task["time"] = self.task_time.text().strip()
        ok = add_scheduled_task(task)
        if ok:
            self.task_title.clear()
            self.task_prompt.clear()
            self._refresh_list()
            QMessageBox.information(self, "Task aggiunto",
                f"Task '{title}' schedulato ({t}).\n\n"
                f"Salvato in CONFIG/scheduled_tasks.json.\n"
                f"L'orchestratore lo eseguirà automaticamente.")

    def _on_del_task(self):
        row = self.task_list_widget.currentRow()
        if row < 0:
            QMessageBox.information(self, "Nessuna selezione",
                                    "Seleziona un task dalla lista prima di eliminarlo.")
            return
        item = self.task_list_widget.item(row)
        if not item:
            return
        title = item.data(Qt.ItemDataRole.UserRole) or {}
        title_str = title.get("title", "?") if isinstance(title, dict) else "?"
        reply = QMessageBox.question(self, "Conferma",
            f"Eliminare il task '{title_str}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            remove_scheduled_task(row)
            self._refresh_list()

    def _refresh_list(self):
        self.task_list_widget.clear()
        tasks = load_scheduled()
        if not tasks:
            item = QListWidgetItem("📭 Nessun task schedulato. Aggiungine uno sopra. ↑")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.task_list_widget.addItem(item)
            return
        for i, t in enumerate(tasks):
            type_icon = {"oneshot": "🕐", "interval": "🔁", "daily": "📅"}.get(
                t.get("type", ""), "•"
            )
            when = ""
            if t.get("type") == "oneshot":
                when = t.get("datetime", "")
            elif t.get("type") == "interval":
                when = f"ogni {t.get('interval_sec', '?')}s"
            elif t.get("type") == "daily":
                when = f"ogni giorno alle {t.get('time', '?')}"
            model = t.get("model", "(default)")
            text = f"{type_icon} [{i+1}] {t.get('title', '?')} — {when} — modello: {model}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.task_list_widget.addItem(item)

    def _back_to_main(self):
        parent = self.parent()
        while parent and not hasattr(parent, "back_to_main"):
            parent = parent.parent()
        if parent and hasattr(parent, "back_to_main"):
            parent.back_to_main()

    # ──────────────────────────────────────────────────────────────────
    # Stili
    # ──────────────────────────────────────────────────────────────────
    def _group_style(self) -> str:
        return (
            "QGroupBox {"
            "  background:#ffffff; border:1px solid #e0e0e0; border-radius:8px;"
            "  margin-top:14px; padding-top:8px;"
            "  font-weight:bold; color:#1a1a1a;"
            "}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin; left:14px; padding:0 6px;"
            "  background:#ffffff;"
            "}"
        )

    def _combo_style(self) -> str:
        return (
            "QComboBox { background:#ffffff; color:#1a1a1a; "
            "border:1px solid #d0d0d0; padding:6px 10px; border-radius:6px; "
            "font-size:12px; min-width:200px; }"
            "QComboBox:hover { border-color:#16a34a; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#1a1a1a; "
            "selection-background-color:#f0f9ff; }"
        )

    def _input_style(self) -> str:
        return (
            "QLineEdit, QDateTimeEdit, QSpinBox { background:#ffffff; color:#1a1a1a; "
            "border:1px solid #d0d0d0; padding:6px 10px; border-radius:6px; "
            "font-size:12px; }"
            "QLineEdit:focus, QDateTimeEdit:focus, QSpinBox:focus { border-color:#16a34a; }"
        )
