#!/usr/bin/env python3
"""
BYTE-SWARMY Control Center — Sezioni collassabili + Credits overlay
PyQt6, single-file
"""

import sys
import os
from pathlib import Path
import random
import subprocess
import ast
import re
import json
import time

BASE_DIR = Path(__file__).parent.parent.resolve()

from CORE.constants import OLLAMA_HOST, DEFAULT_NUM_CTX, BTN_TRANSPARENT_STYLE, BTN_TRANSPARENT_DANGER_STYLE, BTN_TRANSPARENT_MEDIUM_STYLE, BTN_TRANSPARENT_SMALL_STYLE

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
    QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QFileIconProvider,
)
from PyQt6 import QtWidgets
from PyQt6.QtGui import (
    QColor, QCursor, QFont, QIcon, QPixmap, QPalette, QAction,
    QBrush, QPainter, QPen, QDesktopServices,
    QStandardItem, QStandardItemModel,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QDir, QTimer,
    QUrl, QEvent, QItemSelectionModel, QModelIndex, QSize, QObject
)

from GUI.gui_backend import (
    get_cpu_temp, get_gpu_temp, get_metrics, get_tasks, get_logs,
    add_task_to_db, get_ram_pct, get_gpu_mem_pct, get_gpu_freq_mhz
)
from INTENT.metrics import estimate_kv_cache_mb
from GUI.file_manager import FileSystemModel, CheckableTreeView
from GUI.panels import (
    wrap_in_panel_page,
    build_actors_page,
    build_cicd_page,
    build_clean_code_page,
    build_config_page,
    build_scheduler_page,
    build_plancia_cards,
    build_tools_cards,
)
from GUI import settings_store
from GUI.settings_panel import SettingsPanel
from GUI.actors_panel import ActorsPanel
from GUI.task_scheduler_panel import TaskSchedulerPanel
from GUI.task_item_row import TaskItemRow
from GUI.credits_overlay import CreditsOverlay
from GUI.device_panel import DevicePanel
from GUI.collapsible_section import CollapsibleSection
from GUI.plancia_card import PlanciaCard
from GUI.categorized_log_viewer import CategorizedLogViewer
from GUI.backup_code_logs import BackupCodeLogs
from GUI.code_explorer import CodeExplorer, CodeNode
from GUI.file_editor_widget import FileEditorWidget
from GUI.config_panel import ConfigPanel
from GUI.integrity_tests_panel import IntegrityTestsPanel
from GUI.software_security_panel import SoftwareSecurityPanel
from GUI.cicd_pipeline_panel import CICDPipelinePanel
from GUI.clean_code_panel import CleanCodePanel
from GUI.project_tab_bar import ProjectTabBar, _is_junk_project_path, build_run_command
from GUI.file_tree_drawer import FileTreeDrawer
from GUI.center_area import CenterArea

# ════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════
# TRACCIAMENTO CLICK GUI (file manager + task) — sempre attivo
# ════════════════════════════════════════════════════════════════
_CLICK_COUNT = 0

# ════════════════════════════════════════════════════════════════
# ZOOM: riscalatura dei font-size hard-coded nei CSS
# ════════════════════════════════════════════════════════════════
_ZOOM_FS_RE = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)\s*(px|pt)")


def _zoom_scale_css(css: str, factor: float) -> str:
    """Riscala i font-size (px e pt) di un CSS con il fattore indicato."""
    def _scale(m):
        try:
            n = float(m.group(2)) * factor
        except Exception:
            n = float(m.group(2))
        n = max(6.0, n)
        return f"{m.group(1)}{n:.2f}{m.group(3)}"
    return _ZOOM_FS_RE.sub(_scale, css)


def _click_log(area: str, pulsante: str, progetto: str = "",
               elemento: str = "") -> None:
    """Traccia ogni click con formato:
    [Nome-Cartella-progetto]- [area] [pulsante premuto]
    aree: plancia, filemanager, task, logo, amburghermenù
    Scritto sempre su logs/gui_clicks.log (indipendente da BSWARM_GUI_DEBUG)."""
    global _CLICK_COUNT
    _CLICK_COUNT += 1
    ts = time.strftime("%H:%M:%S")
    nome_progetto = ""
    if progetto:
        try:
            nome_progetto = Path(progetto).name
        except Exception:
            nome_progetto = progetto
    riga = (
        f"[{ts}] click#{_CLICK_COUNT} | [{nome_progetto or 'root'}]- "
        f"[{area}] [{pulsante}] {elemento}\n"
    )
    try:
        log_path = Path("logs/gui_clicks.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(riga)
    except Exception:
        pass


class _ZoomEventFilter(QObject):
    """Event filter globale per catturare Ctrl++ / Ctrl+-- / Ctrl+0
    anche quando il focus è su un widget figlio (QLineEdit, QTextEdit, ecc.)."""

    def __init__(self, window: ControlCenter):
        super().__init__()
        self.window = window

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier:
                if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                    self.window._zoom_in()
                    return True
                if key == Qt.Key.Key_Minus:
                    self.window._zoom_out()
                    return True
                if key == Qt.Key.Key_0:
                    self.window._zoom_reset()
                    return True
        return super().eventFilter(obj, event)


class ControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BYTE-SWARMY · Control Center")
        self.resize(1450, 900)
        # Tema: legge da CONFIG/settings.json e carica il QSS completo.
        # I temi sono 10+ (nord, dracula, hacker, ...): non più binario
        # dark/light. Il QSS si applica live anche senza riavvio.
        # _window_chrome() aggiunge le regole di LAYOUT (tab a ×, senza
        # colori) che i temi non contengono.
        from GUI.theme import theme as _theme_mod
        self.setStyleSheet(_theme_mod.load_stylesheet(settings_store.get_theme())
                           + "\n" + self._window_chrome())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.drawer = FileTreeDrawer(self)
        self.drawer.setMinimumWidth(300)
        self._current_project_path = None
        self.center = CenterArea(self)

        # Preferenze GUI (tema, zoom, font, posizione testo icone)
        from CORE.config_model import load_typed_config
        self.gui_settings = load_typed_config().gui
        # Zoom persistito in CONFIG/settings.json vince sul config.toml:
        # all'avvio l'interfaccia parte gia' scalata come nell'ultima sessione.
        try:
            from GUI import settings_store as _settings_store_mod
            self.gui_settings.zoom_level = _settings_store_mod.get_zoom_level()
        except Exception:
            pass
        # Applica lo zoom iniziale
        self._apply_zoom(self.gui_settings.zoom_level)

        # Event filter globale per catturare Ctrl++ / Ctrl+-- / Ctrl+0
        # anche quando il focus è su un widget figlio (QLineEdit, ecc.)
        self.app_event_filter = _ZoomEventFilter(self)
        QApplication.instance().installEventFilter(self.app_event_filter)

        root.addWidget(self._build_toolbar())

        # Splitter orizzontale tra Archivio progetto e area centrale:
        # l'utente può trascinare il bordo per ridimensionare.
        # Le dimensioni vengono salvate in state/splitter_state.json e
        # ripristinate all'avvio.
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.drawer)
        self.splitter.addWidget(self.center)

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        state_file = os.path.join(base, "state", "splitter_state.json")
        saved_sizes = None
        if os.path.exists(state_file):
            try:
                data = json.loads(open(state_file, encoding="utf-8").read())
                if isinstance(data, list) and len(data) == 2:
                    saved_sizes = [int(data[0]), int(data[1])]
            except Exception:
                pass

        if saved_sizes:
            self.splitter.setSizes(saved_sizes)
        else:
            self.splitter.setSizes([350, 700])

        self.splitter.splitterMoved.connect(
            lambda *args: self._save_splitter_state()
        )
        root.addWidget(self.splitter, stretch=1)

        root.addWidget(self._build_command_bar())

        # Scorciatoie globali: Backspace → "Indietro alla Plancia",
        # "/" (con campo vuoto e focus non su un editor) → scrivi nel
        # campo comando in basso. Installate a livello app per catturare
        # i tasti anche quando il focus è su widget figli.
        try:
            QApplication.instance().installEventFilter(self.center)
            self._global_keys_installed = True
        except Exception:
            self._global_keys_installed = False

        self._cpu_temp = 0
        self._gpu_temp = 0
        self._tok_s = 0.0
        self._kv = "-"
        self._mem = "-"
        self._freq = "-"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_metrics)
        self._timer.start(1500)

        self._editor_overlay = None
        self._editor_docked = None
        self._credits_overlay = None
        # Debug GUI: barra info-widget sotto il mouse (attivabile da Impostazioni)
        self._gui_debug = settings_store.get_gui_debug()
        self._debug_label = None
        if self._gui_debug:
            self._install_debug_bar()

        # Ri-applica lo zoom ORA che tutta l'UI e' costruita (toolbar, status
        # bar, barre pulsanti): il primo _apply_zoom avveniva prima e quindi
        # quei widget restavano al font-base anche con zoom salvato != 100.
        self._apply_zoom(self.gui_settings.zoom_level)

        # Catch-up periodico: i widget creati DOPO lo zoom (pannelli aperti
        # dai menu, sezioni CPU/GPU ricreate, dialog) vengono scalati entro
        # ~1.5s invece di restare al font base fino al prossimo re-zoom.
        self._zoom_catchup_timer = QTimer(self)
        self._zoom_catchup_timer.timeout.connect(self._rescale_missing_widgets)
        self._zoom_catchup_timer.start(1500)

    def _save_splitter_state(self):
        """Salva le larghezze attuali dello splitter (sidebar <-> centro)
        in state/splitter_state.json per ripristinarle all'avvio."""
        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            state_file = os.path.join(base, "state", "splitter_state.json")
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            sizes = self.splitter.sizes()
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(sizes, f)
        except Exception as e:
            print(f"Errore salvataggio splitter: {e}")

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
            try:
                self._sync_toggle_icon()
            except Exception:
                pass
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
            try:
                self._sync_toggle_icon()
            except Exception:
                pass
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
        bar.setMinimumHeight(64)
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        menu_btn = QPushButton("☰")
        menu_btn.setFixedSize(32, 32)
        menu_btn.setObjectName("icon_btn")
        menu_btn.clicked.connect(self._show_context_menu)
        lay.addWidget(menu_btn)

        # 🐝 Ape → apre i credits (NON più il drawer)
        # Più grande (40x40) e con font-size adeguato per evitare che
        # l'emoji venga schiacciata/compressa verticalmente (bug segnalato).
        bee_btn = QPushButton("🐝")
        bee_btn.setFixedSize(40, 40)
        bee_btn.setObjectName("icon_btn")
        # Emoji rendering: usiamo un font grande e centrato, niente padding
        bee_btn.setStyleSheet(
            "QPushButton#icon_btn {"
            "  font-size: 22px;"
            "  padding: 0;"
            "  border: 2px solid #16a34a;"
            "  border-radius: 8px;"
            "}"
        )
        bee_btn.setToolTip("Credits & Ringraziamenti")
        bee_btn.clicked.connect(self._show_credits)
        lay.addWidget(bee_btn)

        # Nome del progetto accanto al logo ape (richiesto dall'utente)
        brand_lbl = QLabel("<b>Byte SwarmY</b>")
        brand_lbl.setObjectName("brand_label")
        brand_lbl.setStyleSheet(  # nolint: brand verde accanto al logo ape
            "QLabel#brand_label {"
            "  color:#16a34a; font-size:14px; font-weight:bold;"
            "  padding:0 6px 0 4px;"
            "}"
        )
        lay.addWidget(brand_lbl)

        # NOTA: il pulsante cartella gialla 📁 qui è stato rimosso su
        # richiesta dell'utente — era ridondante (la sidebar con "Archivio
        # progetto" e i tab in alto coprono già la navigazione file).
        # Per aprire/chiudere il drawer resta il menu ☰ in alto a sinistra.

        sep1 = QFrame()
        sep1.setFixedWidth(1)
        lay.addWidget(sep1)

        self.project_tabs = ProjectTabBar()
        self.project_tabs.setCurrentIndex(0)
        # Quando si cambia tab, la sidebar 'Archivio progetto' si aggiorna
        # alla cartella del progetto appena selezionato.
        self.project_tabs.current_project_changed.connect(
            self._on_current_project_changed
        )
        # Forza emissione iniziale per il tab corrente (all'avvio il
        # currentChanged non scatta se setCurrentIndex(0) non cambia indice)
        initial_path = self.project_tabs._path_for_tab(0) if self.project_tabs.count() > 0 else None
        if initial_path:
            self.drawer.set_current_folder(initial_path)
        else:
            # Nessun progetto PR_ selezionato: mostra la root project/ nel
            # file manager così le cartelle senza prefisso PR_ sono visibili
            # e navigabili lì (non nelle schede in alto).
            self.drawer.set_current_folder(str(BASE_DIR / "project"))
        lay.addWidget(self.project_tabs, stretch=1)

        sep2 = QFrame()
        sep2.setFixedWidth(1)
        lay.addWidget(sep2)

        self.device_panel = DevicePanel(control_center=self)
        lay.addWidget(self.device_panel)

        # Il pulsante ▶/⏸ è già dentro DevicePanel (pause_btn) e si collega
        # internamente a control_center._toggle_orchestrator; non serve
        # ricollegarlo da qui (eviterebbe un doppio toggle).
        self._sync_toggle_icon()
        # Stato iniziale in status bar
        try:
            self.statusBar().showMessage(
                f"Orchestratore: {'▶ attivo' if self._is_orchestrator_running() else '⛔ fermo'}  |  "
                f"Progetto: {os.path.basename((self.get_current_project_path() or '').rstrip('/')) or '(nessuno)'}",
                6000,
            )
        except Exception:
            pass

        # Barra di avanzamento completamento task (in basso a destra)
        try:
            from PyQt6.QtWidgets import QProgressBar
            self._completion_bar = QProgressBar()
            self._completion_bar.setRange(0, 100)
            self._completion_bar.setValue(0)
            self._completion_bar.setFixedWidth(220)
            self._completion_bar.setFixedHeight(18)
            # Barra trasparente/bianca a riposo: nessun verde fisso.
            # Il colore del chunk (progresso) appare solo durante l'esecuzione.
            self._completion_bar.setStyleSheet(
                "QProgressBar { border: none; background: #f1f5f9; "
                "text-align: center; color: #64748b; font-size: 10px; }"
                "QProgressBar::chunk { background: #cbd5e1; width: 1px; }"
            )
            self._completion_bar.setFormat("Pronto")
            self._completion_bar.setToolTip("Percentuale di task completati nella coda globale")
            self.statusBar().addPermanentWidget(self._completion_bar)
            # Timer di aggiornamento ogni 3s
            from PyQt6.QtCore import QTimer
            self._completion_timer = QTimer(self)
            self._completion_timer.timeout.connect(self._update_completion_bar)
            self._completion_timer.start(3000)
            self._update_completion_bar()

            # Pulsanti fisici zoom (in basso a destra, dopo la completion bar)
            # Ordine richiesto: [−] [%] [+] [↻]
            # (QLabel/QHBoxLayout/QSizePolicy già importati a livello modulo)
            _zoom_container = QHBoxLayout()
            _zoom_container.setContentsMargins(0, 0, 0, 0)
            _zoom_container.setSpacing(4)

            self._zoom_out_btn = QPushButton("−")
            self._zoom_out_btn.setFixedSize(24, 24)
            self._zoom_out_btn.setToolTip("Zoom riduci (Ctrl + −)")
            self._zoom_out_btn.setStyleSheet(
                "QPushButton { background:#6b7280; color:white; border:none; "
                "border-radius:12px; font-weight:bold; padding:0; }"
                "QPushButton:hover { background:#4b5563; }"
            )
            self._zoom_out_btn.clicked.connect(lambda: (print("DEBUG zoom out click"), self._zoom_out()))
            _zoom_container.addWidget(self._zoom_out_btn)

            # Etichetta percentuale zoom (es. "100%")
            self._zoom_level_lbl = QLabel(f"{getattr(self.gui_settings, 'zoom_level', 100)}%")
            self._zoom_level_lbl.setToolTip("Livello zoom corrente (Ctrl++ / Ctrl+− / Ctrl+0)")
            self._zoom_level_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._zoom_level_lbl.setFixedWidth(40)
            self._zoom_level_lbl.setStyleSheet(
                "QLabel { color:#9ca3af; font-size:10px; font-weight:bold; padding:0; }"
            )
            _zoom_container.addWidget(self._zoom_level_lbl)

            self._zoom_in_btn = QPushButton("+")
            self._zoom_in_btn.setFixedSize(24, 24)
            self._zoom_in_btn.setToolTip("Zoom aumenta (Ctrl + +)")
            self._zoom_in_btn.setStyleSheet(
                "QPushButton { background:#6b7280; color:white; border:none; "
                "border-radius:12px; font-weight:bold; padding:0; }"
                "QPushButton:hover { background:#4b5563; }"
            )
            self._zoom_in_btn.clicked.connect(lambda: (print("DEBUG zoom in click"), self._zoom_in()))
            _zoom_container.addWidget(self._zoom_in_btn)

            self._zoom_reset_btn = QPushButton("↻")
            self._zoom_reset_btn.setFixedSize(24, 24)
            self._zoom_reset_btn.setToolTip("Reset vista (Ctrl + 0)")
            self._zoom_reset_btn.setStyleSheet(
                "QPushButton { background:#6b7280; color:white; border:none; "
                "border-radius:12px; font-weight:bold; padding:0; }"
                "QPushButton:hover { background:#4b5563; }"
            )
            self._zoom_reset_btn.clicked.connect(lambda: (print("DEBUG zoom reset click"), self._zoom_reset()))
            _zoom_container.addWidget(self._zoom_reset_btn)

            _zoom_widget = QWidget()
            _zoom_widget.setLayout(_zoom_container)
            self.statusBar().addPermanentWidget(_zoom_widget)

            # I shortcut da tastiera sono gestiti da _ZoomEventFilter (globale)
            # e da keyPressEvent (sulla finestra principale).
        except Exception as e:
            print(f"completion bar init fallito: {e}")

        return bar

    def keyPressEvent(self, event):
        """Intercetta scorciatoie da tastiera per zoom e altre azioni."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeySequence
        key = event.key()
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._zoom_in()
                event.accept()
                return
            if key == Qt.Key.Key_Minus:
                self._zoom_out()
                event.accept()
                return
            if key == Qt.Key.Key_0:
                self._zoom_reset()
                event.accept()
                return
        super().keyPressEvent(event)


    def _show_credits(self):
        """Mostra l'overlay dei ringraziamenti."""
        if self._credits_overlay:
            self._credits_overlay.deleteLater()

        self._credits_overlay = CreditsOverlay(self.centralWidget())
        self._credits_overlay.closed.connect(self._close_credits)

        # Centra l'overlay, clamped alla finestra: se non siamo a tutto
        # schermo e la finestra è più piccola dell'overlay (1180x600),
        # l'overlay si ridimensiona invece di venire tagliato.
        cw = self.centralWidget().size()
        self._credits_overlay.scale_to(cw.width() - 24, cw.height() - 24)
        self._credits_overlay.move(
            max(12, (cw.width() - self._credits_overlay.width()) // 2),
            max(12, (cw.height() - self._credits_overlay.height()) // 2),
        )
        self._credits_overlay.show()
        self._credits_overlay.raise_()

    def _close_credits(self):
        if self._credits_overlay:
            self._credits_overlay.deleteLater()
            self._credits_overlay = None

    def _show_context_menu(self):
        menu = QMenu(self)

        act_pause = QAction("⏸/▶ Pausa / Riprendi orchestratore", self)
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
        quit_label.setStyleSheet("color:#dc2626; font-weight:bold; padding:6px 20px;")  # nolint: Azione Esci = rosso di pericolo
        quit_label.mousePressEvent = lambda e: self.close()
        quit_action.setDefaultWidget(quit_label)
        menu.addAction(quit_action)

        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))

    def _toggle_orchestrator(self):
        """Pausa/Riprendi l'orchestratore (state/pause.flag).

        Pulsante ▶/⏸ della toolbar e voce menu condividono questa logica:
        ▶ (verde) = attivo, click → pausa (⏸ ambra); ⏸ = in pausa,
        click → riprendi (▶ verde).
        """
        import os, time
        btn = self.device_panel.pause_btn
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pause_file = os.path.join(base, 'state', 'pause.flag')
        pid_file = os.path.join(base, 'state', 'orchestrator.pid')
        running_style = ("QPushButton#primary_btn { background:#16a34a; color:white; "
                         "font-weight:bold; font-size:16px; border-radius:6px; "
                         "border:none; }")
        paused_style = ("QPushButton#primary_btn { background:#f59e0b; color:white; "
                        "font-weight:bold; font-size:14px; border-radius:6px; "
                        "border:none; }")
        # Verifica che l'orchestratore sia effettivamente in esecuzione
        orch_running = False
        try:
            if os.path.exists(pid_file):
                with open(pid_file) as _f:
                    _pid = int(_f.read().strip())
                with open(f"/proc/{_pid}/cmdline", "rb") as _f:
                    _cmd = _f.read().replace(b"\\x00", b" ").decode("utf-8", "replace")
                orch_running = ("orchestrator" in _cmd or "watchdog" in _cmd)
        except Exception:
            orch_running = False
        if not orch_running:
            # Avvia l'orchestratore in background
            try:
                import subprocess as _sp
                python = os.path.join(base, ".venv", "bin", "python")
                if not os.path.exists(python):
                    python = "python3"
                log_path = os.path.join(base, "logs", "byte-swarmy.log")
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                logf = open(log_path, "a")
                proc = _sp.Popen(
                    [python, "-m", "CORE.orchestrator"],
                    cwd=base,
                    stdout=logf,
                    stderr=logf,
                    start_new_session=True,
                )
                # Scrivi pid file
                with open(pid_file, "w") as _f:
                    _f.write(str(proc.pid))
                # Attendi avvio
                import time as _t
                for _ in range(10):
                    _t.sleep(0.5)
                    if self._is_orchestrator_running():
                        break
                if self._is_orchestrator_running():
                    btn.setText("▶")
                    btn.setStyleSheet(running_style)
                    self.statusBar().showMessage("▶ Orchestratore avviato", 4000)
                else:
                    self.statusBar().showMessage("⚠ Avvio orchestratore fallito: controlla i log", 5000)
            except Exception as e:
                self.statusBar().showMessage(f"⚠ Errore avvio: {e}", 5000)
            return
        try:
            # Stato reale basato sul flag, non sul testo del pulsante
            # (il testo può andare fuori sync dopo pause/resume esterni).
            paused = os.path.exists(pause_file)
            if not paused:
                _log_user_action("Toolbar-Orchestratore", "pausa",
                                 details="Pausa da pulsante ▶ toolbar")
                with open(pause_file, 'w') as f:
                    f.write(str(time.time()))
                btn.setText("⏸")
                btn.setStyleSheet(paused_style)
                self.statusBar().showMessage("⏸ Orchestratore in pausa", 3000)
            else:
                _log_user_action("Toolbar-Orchestratore", "ripreso",
                                 details="Ripresa da pulsante ⏸ toolbar")
                if os.path.exists(pause_file):
                    os.remove(pause_file)
                btn.setText("▶")
                btn.setStyleSheet(running_style)
                self.statusBar().showMessage("▶ Orchestratore ripreso", 3000)
        except Exception as e:
            print(f"Errore toggle orchestratore: {e}")

    def _stop_orchestrator(self):
        """Ferma l'orchestratore (kill del processo)."""
        import os, signal
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pid_file = os.path.join(base, 'state', 'orchestrator.pid')
        try:
            if os.path.exists(pid_file):
                with open(pid_file) as _f:
                    _pid = int(_f.read().strip())
                os.kill(_pid, signal.SIGTERM)
                self.statusBar().showMessage("⏹ Orchestratore fermato", 4000)
                # Rimuovi pause.flag se presente
                pause_file = os.path.join(base, 'state', 'pause.flag')
                if os.path.exists(pause_file):
                    os.remove(pause_file)
                # Reset icona pulsante pausa/riprendi
                btn = self.device_panel.pause_btn
                btn.setText("▶")
                btn.setStyleSheet(
                    "QPushButton#primary_btn { background:#16a34a; color:white; "
                    "font-weight:bold; font-size:16px; border-radius:6px; border:none; }"
                )
            else:
                self.statusBar().showMessage("⚠ Nessun orchestratore in esecuzione", 4000)
        except Exception as e:
            self.statusBar().showMessage(f"⚠ Errore stop: {e}", 5000)

    def _stop_orchestrator(self):
        """Ferma l'orchestratore (kill del processo)."""
        import os, signal
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pid_file = os.path.join(base, 'state', 'orchestrator.pid')
        try:
            if os.path.exists(pid_file):
                with open(pid_file) as _f:
                    _pid = int(_f.read().strip())
                os.kill(_pid, signal.SIGTERM)
                self.statusBar().showMessage("⏹ Orchestratore fermato", 4000)
                # Rimuovi pause.flag se presente
                pause_file = os.path.join(base, 'state', 'pause.flag')
                if os.path.exists(pause_file):
                    os.remove(pause_file)
                # Reset icona pulsante pausa/riprendi
                btn = self.device_panel.pause_btn
                btn.setText("▶")
                btn.setStyleSheet(
                    "QPushButton#primary_btn { background:#16a34a; color:white; "
                    "font-weight:bold; font-size:16px; border-radius:6px; border:none; }"
                )
            else:
                self.statusBar().showMessage("⚠ Nessun orchestratore in esecuzione", 4000)
        except Exception as e:
            self.statusBar().showMessage(f"⚠ Errore stop: {e}", 5000)

    def _sync_toggle_icon(self):
        """Allinea l'icona del pulsante ▶/⏸ allo stato reale (pause.flag)."""
        import os
        btn = self.device_panel.pause_btn
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paused = os.path.exists(os.path.join(base, 'state', 'pause.flag'))
        if paused:
            btn.setText("⏸")
            btn.setStyleSheet(
                "QPushButton#primary_btn { background:#f59e0b; color:white; "
                "font-weight:bold; font-size:14px; border-radius:6px; border:none; }")
        else:
            btn.setText("▶")
            btn.setStyleSheet(
                "QPushButton#primary_btn { background:#16a34a; color:white; "
                "font-weight:bold; font-size:16px; border-radius:6px; border:none; }")

    def _on_current_project_changed(self, path: str):
        """Salva il percorso del progetto attivo (per task per-progetto)
        e ricarica la lista task della sidebar per quel progetto."""
        # set_current_folder si occupa di: aggiornare _current_project_path,
        # aggiornare il file tree e ricaricare i task del progetto.
        self.drawer.set_current_folder(path)
        # Feedback visivo del progetto attivo
        import os
        name = os.path.basename(path.rstrip("/")) if path else "(nessuno)"
        orch = "▶ attivo" if self._is_orchestrator_running() else "⛔ fermo"
        self.statusBar().showMessage(f"📁 Progetto attivo: {name}   |   Orchestratore: {orch}", 4000)
        # Ricarica il pannello Coda Task se esiste, così mostra i task
        # del progetto appena selezionato
        scheduler = self.center.panel_pages.get("coda")
        if scheduler is not None:
            scheduler.refresh()

    def get_current_project_path(self) -> str | None:
        """Ritorna il percorso assoluto del progetto attivo, o None."""
        return getattr(self, "_current_project_path", None)

    def _refresh_task_list(self):
        """Ricarica la lista task del drawer (chiamato dai menu azione)."""
        try:
            if hasattr(self, "drawer") and self.drawer is not None:
                self.drawer._force_refresh_tasks()
        except Exception as e:
            print(f"_refresh_task_list fallito: {e}")

    def _refresh_coda_card(self):
        """Ricarica il pannello Coda Task del centro."""
        try:
            scheduler = self.center.panel_pages.get("coda") if hasattr(self, "center") else None
            if scheduler is not None and hasattr(scheduler, "refresh"):
                scheduler.refresh()
        except Exception as e:
            print(f"_refresh_coda_card fallito: {e}")

    def _tick_metrics(self):
        self._cpu_temp = get_cpu_temp()
        self._gpu_temp = get_gpu_temp()

        metrics = get_metrics()
        self._tok_s = metrics.get("tokens_per_sec", 0) if metrics else 0

        # ── Posizione REALE dei modelli (da `ollama ps`) ─────────────
        # Non mostriamo più l'etichetta dell'attore (LLM/Decision) ma
        # DOVE sta effettivamente girando il modello in questo momento:
        #   - 100% GPU  → modello su GPU
        #   - 100% CPU  → modello su CPU
        #   - 80%/20%   → offload parziale
        # Se nessun modello è caricato, mostriamo "(idle)".
        running = self._get_ollama_running_models()
        # running: dict {model_name: {"cpu": int, "gpu": int}}
        # Cerca il modello con uso percentuale più alto per riga
        cpu_model_str = "(idle)"
        gpu_model_str = "(idle)"
        for name, info in running.items():
            cpu_pct = info.get("cpu", 0)
            gpu_pct = info.get("gpu", 0)
            if gpu_pct >= 90:
                # Modello principalmente su GPU
                gpu_model_str = f"{name} ({gpu_pct}%GPU)"
            elif cpu_pct >= 90:
                # Modello principalmente su CPU
                cpu_model_str = f"{name} ({cpu_pct}%CPU)"
            elif cpu_pct > 0 and gpu_pct > 0:
                # Offload parziale: mostra su entrambe le righe
                cpu_model_str = f"{name} ({cpu_pct}%CPU)"
                gpu_model_str = f"{name} ({gpu_pct}%GPU)"
            # Se solo un modello è attivo e sta su GPU, la riga CPU resta (idle)

        cpu = self.device_panel.cpu_box
        cpu._model.setText(cpu_model_str)
        cpu._temp.setText(f"{self._cpu_temp:.0f}°C")
        cpu._tok.setText(f"{self._tok_s:.0f}t/s")

        # Valori reali (non segnaposto hardcoded):
        #   KV cache → stima da context_used + architettura modello
        #   RAM %    → /proc/meminfo
        #   GPU mem %→ nvidia-smi memory.used/memory.total
        #   GPU freq → nvidia-smi clocks.current.graphics
        ram_pct = get_ram_pct()
        gpu_mem_pct = get_gpu_mem_pct()
        gpu_freq = get_gpu_freq_mhz()
        model_name = metrics.get("model", "") if metrics else ""
        ctx = metrics.get("context_used", 0) if metrics else 0
        kv_mb = estimate_kv_cache_mb(ctx, model_name) if ctx > 0 else 0.0

        cpu._kv.setText(f"{kv_mb:.0f}MB" if kv_mb > 0 else "-")
        cpu._mem.setText(f"{ram_pct}%" if ram_pct is not None else "-")
        cpu._bus.setText("-")  # bus CPU non disponibile su questa piattaforma

        gpu = self.device_panel.gpu_box
        gpu._model.setText(gpu_model_str)
        gpu._temp.setText(f"{self._gpu_temp:.0f}°C")
        gpu._kv.setText(f"{kv_mb:.0f}MB" if kv_mb > 0 else "-")
        gpu._mem.setText(f"{gpu_mem_pct}%" if gpu_mem_pct is not None else "-")
        gpu._bus.setText(f"{gpu_freq}M" if gpu_freq is not None else "-")

    def _get_ollama_running_models(self) -> dict:
        """Esegue `ollama ps` e ritorna un dict {model_name: {"cpu": pct, "gpu": pct}}.

        Esempio output ollama ps:
            NAME              SIZE    PROCESSOR           ...
            qwen2.5:1.5b      986 MB  100% GPU            ...
            qwen2.5:7b        4.7 GB  80% CPU / 20% GPU   ...

        Ritorno:
            {"qwen2.5:1.5b": {"cpu": 0, "gpu": 100},
             "qwen2.5:7b":   {"cpu": 80, "gpu": 20}}

        Se ollama non è disponibile o nessun modello è caricato, ritorna {}.
        """
        try:
            import subprocess as _sp
            result = _sp.run(
                ["ollama", "ps"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {}
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return {}  # solo header, nessun modello
            # Trova l'indice della colonna PROCESSOR dall'header
            header = lines[0].upper()
            proc_idx = header.find("PROCESSOR")
            name_idx = 0  # NAME è sempre la prima colonna
            if proc_idx < 0:
                return {}  # formato inatteso
            running = {}
            for line in lines[1:]:
                if not line.strip():
                    continue
                # Estrai nome modello (primi caratteri fino al primo spazio multiplo)
                parts = line.split(None, 1)
                if not parts:
                    continue
                name = parts[0]
                # Estrai la colonna PROCESSOR
                if len(line) > proc_idx:
                    proc_str = line[proc_idx:].strip()
                else:
                    proc_str = ""
                # Parsifica "100% GPU" o "80% CPU / 20% GPU"
                cpu_pct = 0
                gpu_pct = 0
                import re
                for match in re.finditer(r'(\d+)%\s*(CPU|GPU)', proc_str, re.IGNORECASE):
                    pct = int(match.group(1))
                    kind = match.group(2).upper()
                    if kind == "CPU":
                        cpu_pct = pct
                    elif kind == "GPU":
                        gpu_pct = pct
                if cpu_pct > 0 or gpu_pct > 0:
                    running[name] = {"cpu": cpu_pct, "gpu": gpu_pct}
            return running
        except FileNotFoundError:
            return {}  # ollama non installato
        except Exception:
            return {}  # timeout, parse error, ecc.

    def _build_command_bar(self):
        bar = QFrame()
        bar.setObjectName("command_bar")
        bar.setMinimumHeight(52)
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Comando o prompt (premi Invia; validazione pre-flight automatica)")
        lay.addWidget(self.cmd_input)

        send = QPushButton("Invia")
        send.setObjectName("primary_btn")
        send.setMinimumHeight(34)
        # COLLEGA IL BOTTONE
        send.clicked.connect(self._send_command)
        # PERMETTI DI PREMERE INVIO
        self.cmd_input.returnPressed.connect(self._send_command)
        lay.addWidget(send)
        return bar

    def _is_orchestrator_running(self) -> bool:
        """True se il processo orchestratore è attivo (via pid file)."""
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pid_file = os.path.join(base, "state", "orchestrator.pid")
        try:
            if not os.path.exists(pid_file):
                return False
            with open(pid_file) as _f:
                _pid = int(_f.read().strip())
            with open(f"/proc/{_pid}/cmdline", "rb") as _f:
                _cmd = _f.read().replace(b"\\x00", b" ").decode("utf-8", "replace")
            return ("orchestrator" in _cmd or "watchdog" in _cmd)
        except Exception:
            return False

    def _update_completion_bar(self):
        '''Aggiorna la barra di avanzamento con % task done/total.'''
        try:
            import sqlite3, os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, "tasks", "queue.db")
            if not os.path.exists(db_path):
                return
            conn = sqlite3.connect(db_path, timeout=3.0)
            project_path = self.get_current_project_path() if hasattr(self, "get_current_project_path") else None
            # Filtro per progetto attivo (se disponibile)
            if project_path:
                proj_filter = " AND project_path = ?"
                proj_params = (project_path,)
            else:
                proj_filter = " AND project_path IS NULL"
                proj_params = ()

            # 1) Task attualmente in esecuzione (in assoluto, per l'animazione)
            running_any = conn.execute(
                "SELECT id, title FROM tasks WHERE status='running' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            # Task in esecuzione per il progetto attivo (per il tooltip/dettaglio)
            running = conn.execute(
                "SELECT id, title FROM tasks WHERE status='running'" + proj_filter + " ORDER BY started_at DESC LIMIT 1",
                proj_params,
            ).fetchone()
            target_id = None
            target_title = None
            if running:
                target_id = running[0]
                target_title = running[1]
            elif running_any:
                # C'è un task running ma non del progetto attivo: usa quello per il titolo
                target_id = running_any[0]
                target_title = running_any[1]
            else:
                # 2) Ultimo task top-level con sotto-task
                parents = conn.execute(
                    "SELECT t.id, t.title FROM tasks t "
                    "WHERE t.parent IS NULL AND EXISTS (SELECT 1 FROM tasks c WHERE c.parent=t.id) "
                    + proj_filter.replace(" AND ", " AND t.") + " ORDER BY t.created_at DESC LIMIT 1",
                    proj_params,
                ).fetchone()
                if parents:
                    target_id = parents[0]
                    target_title = parents[1]
                else:
                    # 3) Ultimo task top-level (anche senza sotto-task)
                    last = conn.execute(
                        "SELECT id, title FROM tasks WHERE parent IS NULL" + proj_filter + " ORDER BY created_at DESC LIMIT 1",
                        proj_params,
                    ).fetchone()
                    if last:
                        target_id = last[0]
                        target_title = last[1]

            # Progresso complessivo del progetto attivo (tutti i task)
            proj_total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE 1=1" + proj_filter, proj_params
            ).fetchone()[0]
            proj_done = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status='done'" + proj_filter, proj_params
            ).fetchone()[0]

            total = proj_total
            done = proj_done

            tot_all = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            done_all = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]

            # Info sotto-task del task attivo (per tooltip)
            sub_total = 0
            sub_done = 0
            if target_id:
                children = conn.execute(
                    "SELECT status FROM tasks WHERE parent=?", (target_id,)
                ).fetchall()
                if children:
                    sub_total = len(children)
                    sub_done = sum(1 for (s,) in children if s == "done")
                else:
                    st = conn.execute(
                        "SELECT status FROM tasks WHERE id=?", (target_id,)
                    ).fetchone()
                    sub_total = 1
                    sub_done = 1 if (st and st[0] == "done") else 0

            conn.close()

            if hasattr(self, "_completion_bar"):
                # Se c'è un task in esecuzione (qualsiasi progetto) → animazione indeterminata
                # (la barra "carica" per far capire che qualcosa sta succedendo)
                if running_any:
                    self._completion_bar.setRange(0, 0)  # modalità indeterminata
                    self._completion_bar.setFormat("In elaborazione…")
                    self._completion_bar.setToolTip(
                        f"Progetto: {proj_name}\n"
                        f"Task in esecuzione: {target_title or '-'}\n"
                        f"Sotto-task attivi: {sub_done}/{sub_total}\n"
                        f"Totale storico: {done_all}/{tot_all}"
                    )
                else:
                    # Torna a modalità percentuale normale
                    self._completion_bar.setRange(0, 100)
                    pct = int(done * 100 / total) if total > 0 else 0
                    self._completion_bar.setValue(pct)
                    proj_name = os.path.basename((project_path or '').rstrip('/')) or "tutti"
                    # A riposo (nessun task o 0%): mostra "Pronto" e barra vuota
                    if total == 0 or pct == 0:
                        self._completion_bar.setFormat("Pronto")
                        self._completion_bar.setToolTip(
                            f"Progetto: {proj_name}\n"
                            f"Nessun task in coda o tutti completati.\n"
                            f"Totale storico: {done_all}/{tot_all}"
                        )
                    else:
                        self._completion_bar.setFormat(f"{proj_name}: {done}/{total} (%p%)")
                        self._completion_bar.setToolTip(
                            f"Progetto: {proj_name}\n"
                            f"Task completati: {done}/{total} ({pct}%)\n"
                            f"Task attivo: {target_title or '-'}\n"
                            f"Sotto-task attivi: {sub_done}/{sub_total}\n"
                            f"Totale storico: {done_all}/{tot_all}"
                        )
        except Exception:
            pass

    def _persist_zoom(self, level: int):
        """Salva il livello zoom in CONFIG/settings.json (best effort)."""
        try:
            from GUI import settings_store as _settings_store_mod
            _settings_store_mod.set_zoom_level(level)
        except Exception:
            pass

    def _zoom_in(self):
        """Aumenta lo zoom dell'interfaccia."""
        try:
            print(f"DEBUG _zoom_in chiamato, livello attuale: {self.gui_settings.zoom_level}")
            new_level = min(200, self.gui_settings.zoom_level + 10)
            self.gui_settings.zoom_level = new_level
            self._persist_zoom(new_level)
            self._apply_zoom(new_level)
            print(f"DEBUG zoom applicato: {new_level}%")
        except Exception as e:
            print(f"Errore zoom in: {e}")

    def _zoom_out(self):
        """Riduce lo zoom dell'interfaccia."""
        try:
            new_level = max(50, self.gui_settings.zoom_level - 10)
            self.gui_settings.zoom_level = new_level
            print(f"DEBUG _zoom_out → {new_level}%")
            self._persist_zoom(new_level)
            self._apply_zoom(new_level)
            print(f"DEBUG zoom applicato: {new_level}%")
        except Exception as e:
            print(f"Errore zoom out: {e}")

    def _zoom_reset(self):
        """Reset zoom al valore default."""
        try:
            self.gui_settings.zoom_level = 100
            print("DEBUG _zoom_reset → 100%")
            self._persist_zoom(100)
            self._apply_zoom(100)
            print("DEBUG zoom applicato: 100%")
        except Exception as e:
            print(f"Errore zoom reset: {e}")

    def _apply_zoom(self, level: int):
        """Applica il livello zoom a tutta l'interfaccia.

        Il font-size e' hard-coded in decine di stylesheet inline per-widget
        (px) e nel tema QSS della finestra (pt): quei valori vittoriano su
        app.setFont() e sul QSS globale, quindi qui vengono RISCALATI.
        Strategia: cattura una base a 100% e riscala con fattore level/100.
        """
        try:
            from PyQt6.QtGui import QFont
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            factor = max(0.5, min(2.0, level / 100.0))

            font_size = max(8, int(self.gui_settings.font_size * level / 100))
            font = QFont()
            font.setPointSize(font_size)
            app.setFont(font)

            # 1) Riscala i font-size negli stylesheet INLINE dei widget.
            #    La base 100% viene catturata al primo incontro (il valore
            #    scritto nel codice e' sempre a 100%); ogni zoom riscala
            #    SEMPRE dalla base con fattore assoluto level/100.
            if not hasattr(app, "_zoom_base_styles"):
                app._zoom_base_styles = {}
            for widget in app.allWidgets():
                try:
                    ss = widget.styleSheet()
                    base = app._zoom_base_styles.setdefault(id(widget), ss) or ""
                    if "font-size" not in base:
                        continue
                    new_ss = _zoom_scale_css(base, factor)
                    if new_ss != ss:
                        widget.setStyleSheet(new_ss)
                except Exception:
                    pass

            # 2) QSS della MAIN WINDOW (tema + window_chrome): qui vive il
            #    tema (dark.qss ecc. con font-size in pt). Il suo CSS vince
            #    a parita' di specificita' sul QSS app-level, quindi
            #    va riscalato LUI: sempre dall'originale, niente drift.
            if not hasattr(self, "_zoom_original_stylesheet"):
                self._zoom_original_stylesheet = self.styleSheet()
            self.setStyleSheet(
                _zoom_scale_css(self._zoom_original_stylesheet, factor)
                + "\n" + self._zoom_qss(font_size)
            )

            # 3) QSS app-level per i popup TOP-LEVEL (QMenu, tooltip di
            #    sistema) che NON ereditano il QSS della finestra: senza
            #    questo i menu contestuali restano al font base.
            app.setStyleSheet(self._zoom_qss(font_size))

            # 4) Forza repaint e polizia stile di tutti i widget
            for widget in app.allWidgets():
                try:
                    widget.font().setPointSize(font_size)
                    widget.update()
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                except Exception:
                    pass

            # Aggiorna larghezza minima pannello sinistro in base allo zoom,
            # così le etichette ("Lavori", "Svuota coda") non vengono tagliate.
            if hasattr(self, "drawer"):
                self.drawer.setMinimumWidth(max(260, int(300 * factor)))

            # Aggiorna tooltip pulsanti ed etichetta percentuale
            if hasattr(self, "_zoom_in_btn"):
                self._zoom_in_btn.setToolTip(f"Aumenta zoom (Ctrl++) — {level}%")
                self._zoom_out_btn.setToolTip(f"Riduci zoom (Ctrl+−) — {level}%")
                self._zoom_reset_btn.setToolTip(f"Reset vista (Ctrl+0) — {level}%")
            if hasattr(self, "_zoom_level_lbl"):
                self._zoom_level_lbl.setText(f"{level}%")
        except Exception as e:
            print(f"Errore applicazione zoom: {e}")

    def _zoom_qss(self, font_size: int) -> str:
        """QSS globale che estende il font-size ai widget senza stile inline."""
        return f"""
                QWidget {{ font-size: {font_size}px; }}
                QPushButton {{ font-size: {font_size}px; }}
                QLabel {{ font-size: {font_size}px; }}
                QTextEdit {{ font-size: {font_size}px; }}
                QPlainTextEdit {{ font-size: {font_size}px; }}
                QListWidget {{ font-size: {font_size}px; }}
                QTreeView {{ font-size: {font_size}px; }}
                QLineEdit {{ font-size: {font_size}px; }}
                QComboBox {{ font-size: {font_size}px; }}
                QSpinBox {{ font-size: {font_size}px; }}
                QSlider {{ font-size: {font_size}px; }}
                QProgressBar {{ font-size: {font_size}px; }}
                QTabBar::tab {{ font-size: {font_size}px; }}
                QHeaderView::section {{ font-size: {font_size}px; }}
            """

    def _rescale_missing_widgets(self):
        """Zoom: scala i widget creati DOPO l'ultimo zoom.

        I pannelli aperti dopo uno zoom (Impostazioni, Attori, Coda, sezioni
        CPU/GPU ricreate, dialog) nascono con gli stylesheet inline a base
        100%: senza questo passaggio restano al font piccolissimo finch'e
        l'utente non re-zooma. Passaggio leggero: tocca SOLO i widget nuovi
        (stili invariati non vengono riscritti, quindi zero flicker).
        """
        try:
            level = self.gui_settings.zoom_level
        except Exception:
            return
        if level == 100:
            return
        app = QApplication.instance()
        if app is None:
            return
        base_styles = getattr(app, "_zoom_base_styles", None)
        if base_styles is None:
            return  # zoom non ancora applicato: _apply_zoom gira all'avvio
        factor = max(0.5, min(2.0, level / 100.0))
        for widget in app.allWidgets():
            try:
                ss = widget.styleSheet()
                base = base_styles.setdefault(id(widget), ss) or ""
                if "font-size" not in base:
                    continue
                new_ss = _zoom_scale_css(base, factor)
                if new_ss != ss:
                    widget.setStyleSheet(new_ss)
            except Exception:
                pass

    def _send_command(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        project_path = self.get_current_project_path() if hasattr(self, "get_current_project_path") else None
        project_name = os.path.basename(project_path.rstrip("/")) if project_path else None
        try:
            from GUI.task_queue import add_task
            task = add_task(text, "", "", "code", project_path)
            task_id = task.get("id", "")
        except Exception as e:
            print(f"add_task fallito, fallback globale: {e}")
            try:
                task_id = add_task_to_db(text, project_path=project_path)
            except Exception as e2:
                self.statusBar().showMessage(f"❌ Errore aggiunta task: {e2}", 5000)
                return
        self.cmd_input.clear()
        # Feedback visivo: dove è stato salvato
        where = f"progetto '{project_name}'" if project_name else "coda globale"
        msg = f"✅ Task aggiunto a {where}"
        if task_id:
            msg += f"  (id: {task_id[:18]}…)"
        if not self._is_orchestrator_running():
            msg += "  ⚠ orchestratore NON attivo: il task resta in coda"
        else:
            msg += "  ▶ orchestratore attivo: in elaborazione"
        self.statusBar().showMessage(msg, 6000)
        print(msg)
        # Aggiorna la lista task del drawer/progetto attivo
        try:
            if hasattr(self, "drawer") and self.drawer is not None:
                self.drawer._force_refresh_tasks()
        except Exception as e:
            print(f"refresh task list fallito: {e}")
        # Aggiorna anche il pannello Coda Task del centro (se presente)
        try:
            scheduler = self.center.panel_pages.get("coda") if hasattr(self, "center") else None
            if scheduler is not None and hasattr(scheduler, "refresh"):
                scheduler.refresh()
        except Exception as e:
            print(f"refresh coda panel fallito: {e}")
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

        # Ridimensiona l'overlay editor in percentuale della finestra centrale
        # (come CreditsOverlay): non esce mai dai bordi, si adatta a massimizza/riduci.
        cw = self.centralWidget().size()
        ew = max(420, int(cw.width() * 0.55))
        eh = max(320, int(cw.height() * 0.55))
        self._editor_overlay.resize(ew, eh)
        self._editor_overlay.move(
            max(12, (cw.width() - ew) // 2),
            max(12, (cw.height() - eh) // 2),
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

    def _window_chrome(self):
        """Regole di SOLO layout (nessun colore) concatenate al QSS del tema.

        Il padding asimmetrico dei tab progetto lascia spazio alla × di
        chiusura: 15px tra testo e ×, 15px tra × e bordo destro. I colori
        arrivano dai temi GUI/theme/*.qss — qui solo geometria.
        """
        return """
        QTabBar::tab {
            border-bottom: 2px solid transparent;
            border-top-left-radius: 6px; border-top-right-radius: 6px;
            /* padding-right 30px: lascia spazio per la × con 15px a sinistra
               (tra testo e ×) + 15px a destra (tra × e bordo destro del tab). */
            padding: 10px 30px 10px 16px; margin-right: 2px; font-size: 12px;
            min-height: 22px;
        }
        QTabBar::close-button {
            subcontrol-position: right;
            padding: 0;
            margin: 0 15px 0 15px;
        }
        """


if __name__ == "__main__":
    # ── Crash handler: salva traceback su logs/crash.log prima di terminare ──
    import os as _os, traceback as _traceback
    from datetime import datetime as _datetime
    from pathlib import Path as _Path

    _crash_log_dir = _Path("logs")
    _crash_log_dir.mkdir(parents=True, exist_ok=True)
    _crash_log_path = _crash_log_dir / "crash.log"
    _old_excepthook = sys.excepthook

    def _crash_excepthook(_exc_type, _exc_value, _exc_tb):
        _ts = _datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _lines = [
            f"═════════════════════════════════════════════════════════════════════════════════",
            f"CRASH RILEVATO alle {_ts}",
            f"Tipo eccezione: {_exc_type.__name__ if _exc_type else 'Sconosciuto'}",
            f"Messaggio: {_exc_value}",
            f"",
            f"Traceback:",
        ]
        _lines.extend(_traceback.format_exception(_exc_type, _exc_value, _exc_tb))
        _lines.append(
            f"═════════════════════════════════════════════════════════════════════════════════"
        )
        _lines.append("")
        try:
            with open(_crash_log_path, "a", encoding="utf-8") as _f:
                _f.write("\n".join(_lines) + "\n")
        except Exception:
            pass
        try:
            _old_excepthook(_exc_type, _exc_value, _exc_tb)
        except Exception:
            pass

    sys.excepthook = _crash_excepthook

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ControlCenter()
    # Ponte remoto per simulare i pulsanti (tools/gui_remote.py).
    # Opt-out: env BYTE_SWARMY_REMOTE=0. Mai raise: fail-open.
    try:
        from GUI.remote_bridge import start_button_bridge
        start_button_bridge(w)
    except Exception as _e:      # la GUI parte comunque
        print(f"[remote-bridge] off: {_e}", file=sys.stderr)
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

    # ── Gestione graceful di Ctrl+C (SIGINT) ───────────────────────
    # Senza questo handler, Qt crasha con core dump quando riceve SIGINT
    # perché il signal arriva nel mezzo del ciclo eventi C++ di Qt e non
    # dà modo a Python/Qt di chiudere gracefully (file JSON potrebbero
    # restare aperti, SQLite lockato, PID file orfano). Con questo handler:
    #   - Primo SIGINT → QApplication.quit() → closeEvent su tutte le
    #     finestre → Qt salva stato, rilascia lock, chiude thread, exit 0
    #   - Secondo SIGINT → fallback a sys.exit(130) (default Unix)
    import signal as _signal
    _sigint_count = [0]

    def _sigint_handler(signum, frame):
        _sigint_count[0] += 1
        if _sigint_count[0] == 1:
            print("\n⚠️  Ctrl+C ricevuto — chiusura graceful della GUI...")
            print("   (premi di nuovo Ctrl+C per forzare l'uscita)")
            try:
                app.quit()
            except Exception:
                sys.exit(130)
        else:
            print("\n⚡ Uscita forzata")
            sys.exit(130)

    _signal.signal(_signal.SIGINT, _sigint_handler)

    # Timer necessario: Qt ha un ciclo eventi C++ che non torna mai al loop
    # Python se l'app è idle. Il timer forza Qt a tornare in Python ogni
    # 200ms, così il signal handler può essere eseguito immediatamente.
    from PyQt6.QtCore import QTimer as _QTimer
    _sigint_timer = _QTimer()
    _sigint_timer.start(200)
    _sigint_timer.timeout.connect(lambda: None)  # no-op

    w.show()
    sys.exit(app.exec())
