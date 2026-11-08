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

from GUI.theme.theme import set_prop as _theme_prop
from GUI.theme.theme import set_banner as _theme_banner

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULED_FILE = os.path.join(_BASE, "CONFIG", "scheduled_tasks.json")

DEFAULTS = {"tasks": []}


def _scheduled_file(project_path: str | None = None) -> str:
    """Path del file scheduled tasks: per-progetto se project_path è dato,
    altrimenti globale (backward compat)."""
    if project_path:
        return os.path.join(project_path, "tasks", "scheduled_tasks.json")
    return SCHEDULED_FILE


def load_scheduled(project_path: str | None = None) -> List[Dict]:
    f = _scheduled_file(project_path)
    if not os.path.exists(f):
        return []
    try:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("tasks", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_scheduled(tasks: List[Dict], project_path: str | None = None) -> bool:
    f = _scheduled_file(project_path)
    try:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump({"tasks": tasks}, fh, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f"Errore salvataggio scheduled tasks: {e}")
        return False


def add_scheduled_task(task: Dict, project_path: str | None = None) -> bool:
    tasks = load_scheduled(project_path)
    tasks.append(task)
    return save_scheduled(tasks, project_path)


def update_scheduled_task(idx: int, task: Dict,
                          project_path: str | None = None) -> bool:
    """Sostituisce il task alla posizione idx (modifica da GUI)."""
    tasks = load_scheduled(project_path)
    if 0 <= idx < len(tasks):
        tasks[idx] = task
        return save_scheduled(tasks, project_path)
    return False


def remove_scheduled_task(idx: int,
                          project_path: str | None = None) -> bool:
    tasks = load_scheduled(project_path)
    if 0 <= idx < len(tasks):
        tasks.pop(idx)
        return save_scheduled(tasks, project_path)
    return False


from GUI.actors_panel import fill_model_combo, combo_current_model  # noqa: E402


class TaskSchedulerPanel(QWidget):
    """Pannello per schedulare task (Code Task) a orari specifici."""

    def __init__(self, parent=None, get_project_path=None):
        super().__init__(parent)
        self.setObjectName("task_scheduler_panel")
        self.get_project_path = get_project_path
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")   # stile dal tema app-level
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
        content.setObjectName("panelScrollContent")
        # NB: stylesheet con SELETTORE (non declaration-only), altrimenti
        # il "background: transparent" trasuda su tutti i figli e azzera
        # i bottoni role="start"/"danger" del tema app-level.
        content.setStyleSheet("QWidget#panelScrollContent { background: transparent; }")
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
        _theme_banner(expl, "warn")
        lay.addWidget(expl)

        # Form per aggiungere un task
        form_box = QGroupBox("➕ Nuovo task schedulato")
        form = QFormLayout(form_box)
        form.setSpacing(8)
        form.setContentsMargins(14, 14, 14, 14)

        self.task_title = QLineEdit()
        self.task_title.setPlaceholderText("Es. Analisi sicurezza settimanale")
        form.addRow("Titolo:", self.task_title)

        self.task_prompt = QLineEdit()
        self.task_prompt.setPlaceholderText("Prompt del compito da eseguire")
        form.addRow("Prompt:", self.task_prompt)

        self.task_type = QComboBox()
        self.task_type.addItem("🕐 Uno-shot (una volta)", "oneshot")
        self.task_type.addItem("🔁 Ricorrente (ogni N secondi)", "interval")
        self.task_type.addItem("📅 Giornaliero (alle HH:MM)", "daily")
        self.task_type.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Tipo:", self.task_type)

        # Per oneshot: data/ora divisa in campi separati (user-friendly)
        oneshot_box = QFrame()
        oneshot_lay = QHBoxLayout(oneshot_box)
        oneshot_lay.setContentsMargins(0, 0, 0, 0)
        oneshot_lay.setSpacing(6)

        now = QDateTime.currentDateTime().addSecs(3600)
        self.task_year = QSpinBox()
        self.task_year.setRange(2024, 2100)
        self.task_year.setValue(now.date().year())
        self.task_year.setPrefix("Anno ")
        oneshot_lay.addWidget(self.task_year)

        self.task_month = QSpinBox()
        self.task_month.setRange(1, 12)
        self.task_month.setValue(now.date().month())
        self.task_month.setPrefix("mese ")
        oneshot_lay.addWidget(self.task_month)

        self.task_day = QSpinBox()
        self.task_day.setRange(1, 31)
        self.task_day.setValue(now.date().day())
        self.task_day.setPrefix("giorno ")
        oneshot_lay.addWidget(self.task_day)

        self.task_hour = QSpinBox()
        self.task_hour.setRange(0, 23)
        self.task_hour.setValue(now.time().hour())
        self.task_hour.setPrefix("ore ")
        oneshot_lay.addWidget(self.task_hour)

        self.task_minute = QSpinBox()
        self.task_minute.setRange(0, 59)
        self.task_minute.setValue(now.time().minute())
        self.task_minute.setPrefix("min ")
        oneshot_lay.addWidget(self.task_minute)

        form.addRow("Data/Ora (uno-shot):", oneshot_box)
        self.task_datetime_box = oneshot_box

        # Per interval: ogni quanti secondi
        self.task_interval = QSpinBox()
        self.task_interval.setRange(60, 86400)
        self.task_interval.setSuffix(" s")
        self.task_interval.setValue(3600)
        form.addRow("Intervallo (ricorrente):", self.task_interval)

        # Per daily: a che ora
        self.task_time = QLineEdit("09:00")
        self.task_time.setInputMask("00:00")
        form.addRow("Orario (giornaliero):", self.task_time)

        # Modello da usare (opzionale)
        self.task_model = QComboBox()
        try:
            from GUI.actors_panel import OLLAMA_MODELS as _fallback
            fill_model_combo(self.task_model,
                             _ollama_installed() or _fallback,
                             with_default=True)
        except Exception:
            self.task_model.addItem("(default)", "(default)")
        form.addRow("Modello LLM:", self.task_model)

        # Pulsante aggiungi (primario dal tema)
        self.add_btn = QPushButton("➕ Aggiungi task")
        _theme_prop(self.add_btn, "role", "start")
        self.add_btn.clicked.connect(self._on_add_task)
        form.addRow("", self.add_btn)
        self._editing_task_id = None   # None = nuova voce; str = ID del task in modifica

        lay.addWidget(form_box)

        # Lista task schedulati
        list_box = QGroupBox("📋 Lavori e compiti (coda principale)")
        list_lay = QVBoxLayout(list_box)
        list_lay.setContentsMargins(14, 14, 14, 14)
        list_lay.setSpacing(6)

        self.task_list_widget = QListWidget()
        self.task_list_widget.setObjectName("schedlist")   # stile dal tema QSS
        self.task_list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list_widget.customContextMenuRequested.connect(
            self._on_task_context_menu)
        list_lay.addWidget(self.task_list_widget, stretch=1)

        # Pulsante elimina (danger dal tema)
        del_row = QHBoxLayout()
        del_btn = QPushButton("🗑️ Elimina selezionato")
        _theme_prop(del_btn, "role", "danger")
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
        self.task_datetime_box.setVisible(t == "oneshot")
        self.task_interval.setVisible(t == "interval")
        self.task_time.setVisible(t == "daily")

    def _on_add_task(self):
        title = self.task_title.text().strip()
        prompt = self.task_prompt.text().strip()
        if not title or not prompt:
            QMessageBox.warning(self, "Dati mancanti",
                                "Inserisci almeno titolo e prompt del task.")
            return
        project_path = self.get_project_path() if self.get_project_path else None
        # Costruisce il contesto di schedulazione (stesso per add e update)
        t = self.task_type.currentData()
        context = f"schedulato: tipo={t}"
        if t == "oneshot":
            context += f" data={self.task_year.value():04d}-{self.task_month.value():02d}-{self.task_day.value():02d} {self.task_hour.value():02d}:{self.task_minute.value():02d}"
        elif t == "interval":
            context += f" ogni {self.task_interval.value()}s"
        elif t == "daily":
            context += f" giornaliero alle {self.task_time.text().strip()}"
        model = combo_current_model(self.task_model)
        if model and model != "(default)":
            context += f" modello={model}"

        # Se siamo in modalità modifica, aggiorna il task esistente per ID
        if getattr(self, "_editing_task_id", None):
            try:
                from GUI.main_window import load_tasks, save_tasks
                tasks = load_tasks(project_path)
                aggiornato = False
                for task in tasks:
                    if task.get("id") == self._editing_task_id:
                        task["title"] = title
                        task["description"] = prompt
                        task["context"] = context
                        task["type"] = "code"
                        aggiornato = True
                        break
                if not aggiornato:
                    QMessageBox.warning(self, "Errore",
                                        "Task da modificare non trovato.")
                    return
                save_tasks(tasks, project_path)
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile modificare il task:\n{e}")
                return
            self.task_title.clear()
            self.task_prompt.clear()
            self._editing_task_id = None
            self.add_btn.setText("➕ Aggiungi task")
            self._refresh_list()
            QMessageBox.information(
                self, "Task modificato",
                f"Task '{title}' aggiornato nella coda principale."
            )
            return

        # Altrimenti aggiunge un nuovo task alla coda principale
        try:
            from GUI.main_window import add_task
            ok = add_task(
                title=title,
                description=prompt,
                context=context,
                task_type="code",
                project_path=project_path,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiungere il task:\n{e}")
            return
        if ok:
            self.task_title.clear()
            self.task_prompt.clear()
            self._editing_task_id = None
            self.add_btn.setText("➕ Aggiungi task")
            self._refresh_list()
            QMessageBox.information(
                self, "Task aggiunto",
                f"Task '{title}' aggiunto alla coda principale (Lavori e compiti).\n\n"
                f"L'orchestratore lo preleverà automaticamente."
            )

    def _on_task_context_menu(self, pos):
        """Tasto destro sulla lista: Modifica / Elimina il task selezionato."""
        row = self.task_list_widget.indexAt(pos).row()
        if row < 0:
            return
        item = self.task_list_widget.item(row)
        if not item:
            return
        project_path = self.get_project_path() if self.get_project_path else None
        # Recupera l'ID del task da UserRole (salvato in _refresh_list)
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if not task_id:
            return
        # Cerca il task per ID nella coda principale (stessa fonte di _refresh_list)
        try:
            from GUI.main_window import load_tasks
            tasks = load_tasks(project_path)
            task = next((t for t in tasks if task.get("id") == task_id), None)
        except Exception:
            task = None
        if not task:
            return
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        act_edit = menu.addAction("✏️ Modifica")
        act_del = menu.addAction("🗑️ Elimina")
        chosen = menu.exec(self.task_list_widget.mapToGlobal(pos))
        if chosen is act_edit:
            self._start_edit_task(task)
        elif chosen is act_del:
            self.task_list_widget.setCurrentRow(row)
            self._on_del_task()
        if row >= len(tasks):
            return
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        act_edit = menu.addAction("✏️ Modifica")
        act_del = menu.addAction("🗑️ Elimina")
        chosen = menu.exec(self.task_list_widget.mapToGlobal(pos))
        if chosen is act_edit:
            self._start_edit_task(row)
        elif chosen is act_del:
            self.task_list_widget.setCurrentRow(row)
            self._on_del_task()

    def _start_edit_task(self, task: dict = None):
        """Carica il task nel form di sopra per modificarlo e risalvarlo."""
        if task is None:
            return
        self._editing_task_id = task.get("id", "")
        self.task_title.setText(task.get("title", ""))
        self.task_prompt.setText(task.get("description", ""))
        ttype = task.get("type", "oneshot")
        pos = self.task_type.findData(ttype)
        self.task_type.setCurrentIndex(pos if pos >= 0 else 0)
        self._on_type_changed(0)
        if ttype == "oneshot":
            dt = task.get("datetime", "")
            parts = dt.replace("-", " ").replace(":", " ").split()
            if len(parts) == 5:
                y, mo, d, h, mi = (int(x) for x in parts)
                self.task_year.setValue(y)
                self.task_month.setValue(mo)
                self.task_day.setValue(d)
                self.task_hour.setValue(h)
                self.task_minute.setValue(mi)
        elif ttype == "interval":
            self.task_interval.setValue(int(task.get("interval_sec", 3600)))
        elif ttype == "daily":
            self.task_time.setText(task.get("time", "09:00"))
        idx = self.task_model.findData(task.get("model", "(default)"))
        self.task_model.setCurrentIndex(idx if idx >= 0 else 0)
        self.add_btn.setText("💾 Salva modifiche")
        self.task_title.setFocus()

    def _on_del_task(self):
        row = self.task_list_widget.currentRow()
        if row < 0:
            QMessageBox.information(self, "Nessuna selezione",
                                    "Seleziona un task dalla lista prima di eliminarlo.")
            return
        item = self.task_list_widget.item(row)
        if not item:
            return
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if not task_id:
            return
        title = item.text().split(" — ")[1] if " — " in item.text() else "?"
        reply = QMessageBox.question(self, "Conferma",
            f"Eliminare il task '{title}' ({task_id}) dalla coda principale?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            project_path = self.get_project_path() if self.get_project_path else None
            try:
                from GUI.main_window import delete_task
                delete_task(task_id, project_path)
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile eliminare:\n{e}")
                return
            self._refresh_list()

    def _refresh_list(self):
        self.task_list_widget.clear()
        # Stessa lista di "Lavori e compiti" del progetto attivo
        project_path = self.get_project_path() if self.get_project_path else None
        try:
            from GUI.main_window import load_tasks
            tasks = load_tasks(project_path)
        except Exception:
            tasks = []
        if not tasks:
            item = QListWidgetItem("📭 Nessun task in coda. Aggiungine uno sopra. ↑")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.task_list_widget.addItem(item)
            return
        status_icon = {
            "pending": "⏳", "running": "▶️", "done": "✅",
            "failed": "❌", "retry": "🔄", "stuck": "⚠️",
            "needs_human": "🙋", "thermal_paused": "🌡️",
        }
        for i, t in enumerate(tasks):
            icon = status_icon.get(t.get("status", ""), "•")
            text = (
                f"{icon} [{i+1}] {str(t.get('id',''))[:12]} — "
                f"{t.get('title', '?')} — {t.get('status', '?')} "
                f"— tipo: {t.get('type', '?')}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, t.get("id", ""))
            self.task_list_widget.addItem(item)

    def _back_to_main(self):
        parent = self.parent()
        while parent and not hasattr(parent, "back_to_main"):
            parent = parent.parent()
        if parent and hasattr(parent, "back_to_main"):
            parent.back_to_main()

    def showEvent(self, event):
        """Refresh forzato della lista quando si entra nella scheda."""
        super().showEvent(event)
        self._refresh_list()

    # ──────────────────────────────────────────────────────────────────
    # Stili
    # ──────────────────────────────────────────────────────────────────
    # NB: gli stili inline (group/combo/input) sono rimossi: QGroupBox,
    # QComboBox, QLineEdit, QDateTimeEdit, QSpinBox prendono lo stile dal
    # tema app-level (GUI/theme/*.qss) e seguono il tema live.
