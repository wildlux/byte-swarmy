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
from GUI.task_queue import (
    log_user_action as _log_user_action,
    pause_task as _pause_task,
    resume_single_task as _resume_single_task,
    stop_task as _stop_task,
    restart_task as _restart_task,
)

# ════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════
# TRACCIAMENTO CLICK GUI (file manager + task) — sempre attivo
# ════════════════════════════════════════════════════════════════
_CLICK_COUNT = 0



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



# ── R3: metodi di ControlCenter divisi per area in mixin (comportamento
# invariato: i metodi restano sullo stesso oggetto ControlCenter). ──────
from GUI.cc_shell import ShellMixin
from GUI.cc_orchestrator import OrchestratorMixin
from GUI.cc_zoom import ZoomMixin, _ZoomEventFilter, _zoom_scale_css
from GUI.cc_editor_overlay import EditorOverlayMixin
from GUI.cc_debug_bar import DebugBarMixin
from GUI.cc_shutdown import ShutdownMixin


class ControlCenter(
    ShellMixin,
    OrchestratorMixin,
    ZoomMixin,
    EditorOverlayMixin,
    DebugBarMixin,
    ShutdownMixin,
    QMainWindow,
):
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

        # ── Live Activity (in alto): stato del task in corso + token stream ──
        self.live_activity_bar = QFrame()
        self.live_activity_bar.setObjectName("live_activity_bar")
        self.live_activity_bar.setMinimumHeight(26)
        self.live_activity_bar.setMaximumHeight(30)
        _la_lay = QHBoxLayout(self.live_activity_bar)
        _la_lay.setContentsMargins(10, 2, 10, 2)
        _la_lay.setSpacing(8)
        _la_title = QLabel("🔴 Live Activity")
        _la_title.setObjectName("live_activity_title")
        _la_title.setStyleSheet("font-weight:bold; font-size:11px;")
        _la_lay.addWidget(_la_title)
        self.live_activity_label = QLabel("In attesa di un task…")
        self.live_activity_label.setObjectName("live_activity_label")
        self.live_activity_label.setStyleSheet("font-size:11px;")
        _la_lay.addWidget(self.live_activity_label, stretch=1)
        root.addWidget(self.live_activity_bar)

        self._live_activity_timer = QTimer(self)
        self._live_activity_timer.timeout.connect(self._update_live_activity)
        self._live_activity_timer.start(500)
        self._update_live_activity()

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
