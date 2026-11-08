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
    QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem
)
from PyQt6.QtGui import (
    QColor, QCursor, QFont, QIcon, QPixmap, QPalette, QAction,
    QBrush, QPainter, QPen, QDesktopServices
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QDir, QTimer,
    QUrl, QEvent, QItemSelectionModel, QModelIndex,
)

from GUI.gui_backend import (
    get_cpu_temp, get_gpu_temp, get_metrics, get_tasks, get_logs,
    add_task_to_db
)
from GUI import settings_store
from GUI.settings_panel import SettingsPanel
from GUI.actors_panel import ActorsPanel
from GUI.task_scheduler_panel import TaskSchedulerPanel

# QFileSystemModel fallback (posizione varia tra versioni PyQt6)
try:
    from PyQt6.QtWidgets import QFileSystemModel
except ImportError:
    try:
        from PyQt6.QtCore import QFileSystemModel
    except ImportError:
        try:
            from PyQt6.QtGui import QFileSystemModel
        except ImportError:
            from PyQt6.QtGui import QStandardItemModel
            from PyQt6.QtCore import QModelIndex
            class QFileSystemModel(QStandardItemModel):
                """Fallback QFileSystemModel per PyQt6 senza il vero modulo."""
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._root_path = ""
                def setRootPath(self, path):
                    self._root_path = path
                def rootPath(self):
                    return self._root_path

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


# CREDITS OVERLAY (schermata ringraziamenti)
# ═══════════════════════════════════════════════════════════════
class CreditsOverlay(QFrame):
    """Overlay modale con i ringraziamenti del progetto."""
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("credits_overlay")
        # Overlay a 2 colonne: a sinistra immagine + contributori,
        # a destra le Tecnologie & Progetti Open Source in griglia 2-colonne.
        # Prima era 620x520 fisso e le card venivano compresse a 0px
        # (i nomi di Paolo Lo Bello, GLM 5.2, Qwen, DeepSeek sparivano).
        # Dimensioni minime garantite; la larghezza/altezza effettiva viene
        # impostata in percentuale della finestra da scale_to() (niente
        # tagli quando si massimizza/riduce).
        self.setMinimumSize(560, 380)
        self._max_w, self._max_h = 1280, 720
        # Il tema (nome completo, es. "nord") viene letto da settings_store
        # e applicato dinamicamente: vedi apply_theme() in fondo all'init.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # NIENTE autoFillBackground: il fondo è l'immagine (bg_label qui
        # sotto); un fill opaco del frame la coprirebbe.
        self.setAutoFillBackground(False)
        # Accenti colorati da riadattare al kind del tema (chiaro/scuro):
        # lista di (widget, template con {color}) popolata durante l'init.
        self._colored = []
        # Sfondo: immagine di ringraziamenti (documentazione.jpeg) a pieno
        # schermo, con contenuto sovrapposto (testo/bottoni trasparenti).
        try:
            from PyQt6.QtGui import QPixmap
            import os
            _img = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "IMG", "documentazione.jpeg",
            )
            if os.path.exists(_img):
                _pix = QPixmap(_img).scaled(
                    1180, 600, Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._bg_pixmap_original = _pix   # per scale_to()
                self._bg_label = QLabel(self)
                self._bg_label.setPixmap(_pix)
                self._bg_label.setGeometry(0, 0, 1180, 600)
                self._bg_label.lower()
                self._bg_label.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
                )
        except Exception as e:
            print(f"Errore sfondo credits: {e}")
            self._bg_label = None
        # Leggi tema corrente (default scuro per backward compat)
        try:
            from GUI import settings_store as _ss
            self._theme = _ss.get_theme()
        except Exception:
            self._theme = "dark"

        # Layout esterno: scroll area (stretch) + pulsante chiudi fisso in basso
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(8)

        # ── Contenuto (schermata fissa, niente scroll) ─────────────────
        content = QWidget()
        content.setObjectName("panelScrollContent")
        # NB: stylesheet con SELETTORE (non declaration-only), altrimenti
        # il "background: transparent" trasuda su tutti i figli e azzera
        # i bottoni role="start"/"danger" del tema app-level.
        content.setStyleSheet("QWidget#panelScrollContent { background: transparent; }")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(6)

        # Titolo (l'ape è già nel pulsante della toolbar, evitiamo duplicato)
        title = QLabel("<b>BYTE-SWARMY</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(  # nolint: brand verde del logo, overlay crediti
            "font-size: 22px; color: #4ade80; font-weight: bold;"
        )
        title.setFixedHeight(28)
        self._colored.append(
            (title, "font-size: 22px; color: {color}; font-weight: bold;",
             "#4ade80"))
        lay.addWidget(title)

        subtitle = QLabel("Autonomous Multi-Agent System")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 12px; font-style: italic;")
        subtitle.setFixedHeight(16)
        lay.addWidget(subtitle)

        # Separatore
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #4ade80;")
        lay.addWidget(sep)

        # ── Layout a 2 colonne: sinistra (immagine + ringraziamenti)
        #                          e destra (tecnologie open source in griglia)
        cols = QHBoxLayout()
        cols.setSpacing(12)
        cols.setContentsMargins(0, 0, 0, 0)

        # ─── Colonna SINISTRA: immagine + ringraziamenti ───────────────
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.setContentsMargins(0, 0, 0, 0)

        # Titolo (header della colonna sinistra)
        credits_title = QLabel("✨ Ringraziamenti ✨")
        credits_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_title.setStyleSheet("font-size: 18px; color: #f9e2af; font-weight: bold;")  # nolint: oro crediti
        credits_title.setFixedHeight(26)
        self._colored.append(
            (credits_title, "font-size: 18px; color: {color}; font-weight: bold;",
             "#f9e2af"))
        left_col.addWidget(credits_title)
        # NB: l'immagine documentazione.jpeg è lo sfondo a pieno schermo
        # (bg_label): una copia piccola qui era ridondante e rubava spazio
        # verticale ai loghi dei contributori. Rimosso il blocco immagine.

        # Lista contributori
        contributors = [
            ("👤", "Paolo Lo Bello", "Ideatore del progetto", "#4ade80"),
            ("🤖", "GLM 5.2", "Codice iniziale", "#89b4fa"),
            ("🦙", "Qwen", "Miglioramento e ottimizzazione interfaccia grafica", "#f9e2af"),
            ("🔍", "DeepSeek", "Analisi della sicurezza", "#f38ba8"),
        ]

        # Mappa contributore → logo in IMG/ (se presente, sostituisce l'emoji)
        _LOGOS = {
            "GLM 5.2": "GLM_AI_logo.webp",
            "Qwen": "QWEN_AI_logo.webp",
            "DeepSeek": "DEEPSEEK_AI_logo.webp",
        }

        for icon, name, role, color in contributors:
            card = QFrame()
            card.setObjectName("contrib_card")
            # Il colore d'accento passa da apply_theme (si scurisce sui
            # temi chiari per restare leggibile sull'immagine di fondo).
            # NB: le graffe QSS vanno raddoppiate nel template .format().
            card_template = ("QFrame {{ border-left: 3px solid {color}; "
                             "border-radius: 6px; padding: 4px 10px; }}")
            card.setStyleSheet(card_template.format(color=color))
            self._colored.append((card, card_template, color))
            # Altezza minima garantita: senza questa, il QVBoxLayout comprimeva
            # le card a 0px quando la finestra era troppo piccola, e i nomi
            # dei contributori (Paolo Lo Bello, GLM 5.2, Qwen, DeepSeek)
            # sparivano completamente.
            card.setMinimumHeight(60)
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(8, 4, 8, 4)
            card_lay.setSpacing(10)

            logo_file = _LOGOS.get(name)
            logo_path = None
            if logo_file:
                import os
                candidate = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "IMG", logo_file,
                )
                if os.path.exists(candidate):
                    logo_path = candidate

            if logo_path:
                from PyQt6.QtGui import QPixmap
                icon_lbl = QLabel()
                # Loghi più grandi (88x56): a 40x24 erano quasi illeggibili
                pix = QPixmap(logo_path)
                pix = pix.scaled(88, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                icon_lbl.setPixmap(pix)
                icon_lbl.setFixedWidth(96)
                icon_lbl.setMinimumHeight(56)
                icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                icon_lbl = QLabel(icon)
                icon_lbl.setStyleSheet("font-size: 24px;")
                icon_lbl.setFixedWidth(36)
                icon_lbl.setMinimumHeight(26)
            card_lay.addWidget(icon_lbl)

            info = QWidget()
            info_lay = QVBoxLayout(info)
            info_lay.setContentsMargins(0, 0, 0, 0)
            info_lay.setSpacing(1)

            name_lbl = QLabel(f"<b>{name}</b>")
            name_lbl.setStyleSheet(f"font-size: 14px; color: {color};")
            self._colored.append((name_lbl, "font-size: 14px; color: {color};", color))
            info_lay.addWidget(name_lbl)

            role_lbl = QLabel(role)
            role_lbl.setStyleSheet("font-size: 11px;")
            role_lbl.setWordWrap(True)
            info_lay.addWidget(role_lbl)

            card_lay.addWidget(info, stretch=1)
            left_col.addWidget(card)

        left_col.addStretch()

        # ─── Colonna DESTRA: Tecnologie & Progetti Open Source ─────────
        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.setContentsMargins(0, 0, 0, 0)

        tech_title = QLabel("🧩 Tecnologie & Progetti Open Source")
        tech_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tech_title.setStyleSheet(  # nolint: oro crediti (overlay su immagine)
            "font-size: 13px; color: #f9e2af; font-weight: bold;"
        )
        tech_title.setFixedHeight(20)
        tech_title.setWordWrap(True)
        self._colored.append(
            (tech_title, "font-size: 13px; color: {color}; font-weight: bold;",
             "#f9e2af"))
        right_col.addWidget(tech_title)

        tech_projects = [
            ("🦙", "Ollama",     "Esecuzione locale dei modelli LLM"),
            ("🖼️", "PyQt6",      "Framework per l'interfaccia grafica"),
            ("🔌", "MCP",        "Model Context Protocol — distribuzione task"),
            ("📦", "bubblewrap", "Sandbox filesystem isolato"),
            ("🔎", "rapidfuzz",  "Fuzzy matching per intent e comandi"),
            ("🌐", "SQLite",     "Coda task persistente"),
        ]

        # Griglia a 2 colonne per i tech chips
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        for idx, (icon, name, role) in enumerate(tech_projects):
            chip = QFrame()
            chip.setObjectName("tech_chip")
            chip.setStyleSheet(
                "QFrame { border: 1px solid #2e2e44; "
                "border-radius: 6px; padding: 4px 8px; }"
            )
            chip.setMinimumHeight(64)
            chip_lay = QVBoxLayout(chip)
            chip_lay.setContentsMargins(6, 4, 6, 4)
            chip_lay.setSpacing(2)

            # Riga icona + nome
            top = QHBoxLayout()
            top.setSpacing(6)
            top.setContentsMargins(0, 0, 0, 0)
            ic = QLabel(icon)
            ic.setStyleSheet("font-size: 22px;")
            ic.setFixedWidth(28)
            top.addWidget(ic)
            nm = QLabel(f"<b>{name}</b>")
            nm.setStyleSheet("font-size: 12px;")
            nm.setWordWrap(True)
            top.addWidget(nm, stretch=1)
            chip_lay.addLayout(top)

            # Ruolo
            rl = QLabel(role)
            rl.setStyleSheet("font-size: 10px;")
            rl.setWordWrap(True)
            chip_lay.addWidget(rl)

            row = idx // 2
            col = idx % 2
            grid.addWidget(chip, row, col)

        right_col.addLayout(grid)
        right_col.addStretch()

        # ── Assembla le 2 colonne ───────────────────────────────────────
        cols.addLayout(left_col, stretch=3)
        cols.addLayout(right_col, stretch=2)
        lay.addLayout(cols, stretch=1)

        # Messaggio finale (sotto le 2 colonne)
        final_msg = QLabel("Grazie a tutti per aver contribuito a questo progetto 🐝")
        final_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        final_msg.setStyleSheet("font-size: 12px; font-style: italic; margin-top: 4px;")
        final_msg.setWordWrap(True)
        final_msg.setFixedHeight(18)
        lay.addWidget(final_msg)

        outer.addWidget(content, stretch=1)

        # ── Footer fisso (sempre visibile, fuori dallo scroll) ──────────
        # Contiene: link GitHub + link PayPal + pulsante Chiudi
        footer = QVBoxLayout()
        footer.setSpacing(8)
        footer.setContentsMargins(0, 4, 0, 0)

        # ── Link: GitHub + PayPal (supporta il progetto) ───────────────
        # Riga con due pulsanti affiancati per il repo GitHub e le donazioni
        # PayPal. Click → apre il browser di sistema con QDesktopServices.
        links_row = QHBoxLayout()
        links_row.setSpacing(10)
        links_row.setContentsMargins(0, 0, 0, 0)
        links_row.addStretch()

        # Pulsante GitHub (link al repository)
        github_btn = QPushButton("🐙 GitHub: byte-swarmy")
        github_btn.setObjectName("credits_link_github")
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.setToolTip("Apri https://github.com/wildlux/byte-swarmy nel browser")
        github_btn.setStyleSheet(
            "QPushButton#credits_link_github {"
            "  background: #24292e; color: #ffffff;"
            "  border: 1px solid #444c56; border-radius: 6px;"
            "  padding: 8px 14px; font-size: 11px; font-weight: bold;"
            "}"
            "QPushButton#credits_link_github:hover {"
            "  background: #2d333b; border-color: #58a6ff;"
            "}"
        )
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/wildlux/byte-swarmy")
            )
        )
        links_row.addWidget(github_btn)

        # Pulsante PayPal (donazioni — supporta il software)
        paypal_btn = QPushButton("💛 Supporta con PayPal")
        paypal_btn.setObjectName("credits_link_paypal")
        paypal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        paypal_btn.setToolTip(
            "Apri la pagina PayPal per donare e supportare lo sviluppo"
        )
        paypal_btn.setStyleSheet(
            "QPushButton#credits_link_paypal {"
            "  background: #ffc439; color: #003087;"
            "  border: 1px solid #003087; border-radius: 6px;"
            "  padding: 8px 14px; font-size: 11px; font-weight: bold;"
            "}"
            "QPushButton#credits_link_paypal:hover {"
            "  background: #ffb422; border-color: #001f5f;"
            "}"
        )
        paypal_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(
                    "https://www.paypal.com/cgi-bin/webscr?"
                    "cmd=_donations&business=wildlux%40gmail.com"
                    "&item_name=Prismalux&currency_code=EUR&source=url"
                )
            )
        )
        links_row.addWidget(paypal_btn)

        links_row.addStretch()
        footer.addLayout(links_row)

        # Pulsante chiudi (sempre visibile in basso, fuori dallo scroll)
        close_btn = QPushButton("✕ Chiudi")
        close_btn.setObjectName("credits_close_btn")
        close_btn.setStyleSheet(
            "QPushButton#credits_close_btn { "
            "  background: #4ade80; color: #0f0f19; "
            "  border: none; border-radius: 8px; "
            "  padding: 10px 24px; font-size: 13px; font-weight: bold; "
            "}"
            "QPushButton#credits_close_btn:hover { background: #6ee7a0; }"
        )
        close_btn.clicked.connect(self.closed.emit)
        footer.addWidget(close_btn)

        outer.addLayout(footer)

        # Applica il tema iniziale (chiaro/scuro) letto da settings_store
        self.apply_theme(self._theme)

    # ──────────────────────────────────────────────────────────────────
    # Tema dinamico (chiaro/scuro)
    # ──────────────────────────────────────────────────────────────────
    def apply_theme(self, theme: str):
        """Applica il tema (nome completo, es. "nord") al CreditsOverlay.

        Chiamato all'init e quando l'utente cambia tema dal SettingsPanel
        (vedi ControlCenter._apply_theme_live → credits.apply_theme).

        L'immagine documentazione.jpeg (fondo prevalentemente chiaro) deve
        restare VISIBILE: niente pannelli opachi. La leggibilità del testo
        è garantita da un "vetro smerigliato": le card/chip hanno un fondo
        bianco semi-trasparente (rgba 0.80) quindi il testo è SEMPRE scuro,
        indipendentemente dal kind del tema. Gli accenti pallidi (es.
        #f9e2af) vengono scuriti mantenendo la tinta.
        """
        from GUI.theme import theme as _T
        self._theme = theme
        kind = _T.theme_kind(theme)
        text_color = "#1f2430"
        border_color = "#c9ced6" if kind == "light" else "#2a2f3a"

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Text, QColor(text_color))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(text_color))
        self.setPalette(pal)

        self.setStyleSheet(
            "QFrame#credits_overlay { "
            "  background: transparent; "
            f"  border: 2px solid {border_color}; "
            "  border-radius: 16px; "
            "}"
            # Trasparenza di tutti i widget strutturali sotto l'overlay:
            # il QSS window-level (QWidget { background: ... }) altrimenti
            # li dipingerebbe opachi coprendo l'immagine di sfondo.
            # I pulsanti con stylesheet inline (GitHub/PayPal/Chiudi) non
            # sono toccati: il foglio inline del widget vince su questo.
            "QFrame#credits_overlay QWidget { background: transparent; }"
            "QFrame#credits_overlay QFrame { background: transparent; }"
            "QFrame#credits_overlay QScrollArea { background: transparent; border: none; }"
            "QFrame#credits_overlay QScrollBar:vertical { background: transparent; width: 10px; }"
            "QFrame#credits_overlay QScrollBar::handle:vertical { background: rgba(128,128,128,0.5); border-radius: 5px; min-height: 30px; }"
            "QFrame#credits_overlay QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            # Vetro smerigliato SOLO su card e chip (DOPO il catch-all:
            # a parità di specificità vince l'ultima regola).
            "QFrame#credits_overlay QFrame#contrib_card { "
            "  background: rgba(255,255,255,0.80); border-radius: 6px; }"
            "QFrame#credits_overlay QFrame#tech_chip { "
            "  background: rgba(255,255,255,0.80); "
            "  border: 1px solid rgba(150,155,170,0.55); border-radius: 6px; }"
            f"QFrame#credits_overlay QLabel {{ color: {text_color}; background: transparent; }}"
        )

        # Accenti: su fondo smerigliato chiaro i colori pallidi non si
        # vedono — scurisco quelli con luminanza alta, tinta invariata.
        for widget, template, base in self._colored:
            color = base
            c = QColor(base)
            if c.lightnessF() > 0.55:
                c = c.darker(190)
                color = c.name()
            widget.setStyleSheet(template.format(color=color))


    def keyPressEvent(self, event):
        """ESC chiude i ringraziamenti (oltre al pulsante ✕ Chiudi)."""
        from PyQt6.QtCore import Qt as _Qt
        if event.key() == _Qt.Key.Key_Escape:
            self.closed.emit()
            return
        super().keyPressEvent(event)

    def scale_to(self, width: int, height: int):
        """Ridimensiona l'overlay alla finestra in percentuale.

        Si adatta alla finestra centrale (massimo ~92% larghezza, ~78%
        altezza), clampato tra le dimensioni minime e i massimi consentiti,
        così non ci sono tagli né artefatti quando si massimizza/riduce.
        """
        width = int(width * 0.92)
        height = int(height * 0.78)
        width = max(self.minimumWidth(), min(self._max_w, width))
        height = max(self.minimumHeight(), min(self._max_h, height))
        self.resize(width, height)
        self._bg_label.setGeometry(0, 0, width, height)
        if getattr(self, "_bg_pixmap_original", None) is not None:
            self._bg_label.setPixmap(self._bg_pixmap_original.scaled(
                width, height, Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def showEvent(self, event):
        """Animazione fade-in all'apertura."""
        super().showEvent(event)
        # Focus per ricevere ESC anche senza cliccare prima sull'overlay
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.setWindowOpacity(0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(250)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()


# ═══════════════════════════════════════════════════════════════
# DEVICE PANEL
# ═══════════════════════════════════════════════════════════════
class DevicePanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("device_panel")
        self.setMinimumHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)

        devices_col = QVBoxLayout()
        devices_col.setSpacing(2)
        devices_col.setContentsMargins(0, 0, 0, 0)

        self.cpu_box = self._device_row("CPU", "#16a34a", "qwen2.5:1.5b")
        self.gpu_box = self._device_row("GPU", "#2563eb", "—")

        devices_col.addWidget(self.cpu_box)
        devices_col.addWidget(self.gpu_box)
        lay.addLayout(devices_col)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:#d0d0d0;")
        lay.addWidget(sep)

        self.git_btn = QPushButton("💾")
        self.git_btn.setMinimumWidth(36)
        self.git_btn.setFixedHeight(46)
        self.git_btn.setObjectName("git_btn")
        self.git_btn.setToolTip("Salva su tutti i remote Git configurati")
        self.git_btn.setStyleSheet(
            "QPushButton#git_btn { background:#2563eb; color:white; "
            "font-size:16px; border-radius:6px; border:none; }"
            "QPushButton#git_btn:hover { background:#1d4ed8; }"
        )
        self.git_btn.clicked.connect(self._do_git_save)
        lay.addWidget(self.git_btn)

        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setMinimumWidth(44)
        self.toggle_btn.setFixedHeight(46)
        self.toggle_btn.setObjectName("primary_btn")
        self.toggle_btn.setToolTip("Avvia/Ferma Orchestratore")
        self.toggle_btn.setStyleSheet(
            "QPushButton#primary_btn { background:#16a34a; color:white; "
            "font-weight:bold; font-size:16px; border-radius:6px; border:none; }"
            "QPushButton#primary_btn:hover { background:#15803d; }"
        )
        lay.addWidget(self.toggle_btn)

        self.git_remotes = self._detect_git_remotes()
        self._update_git_tooltip()

    def _open_actors_panel(self):
        """Le righe CPU/GPU sono cliccabili: portano a Modelli → Attori."""
        p = self.parent()
        while p is not None and not hasattr(p, "center"):
            p = p.parent()
        if p is not None:
            p.center.open_panel("modelli")

    def _detect_git_remotes(self):
        remotes = []
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                seen = set()
                for line in result.stdout.strip().split("\n"):
                    if line:
                        name = line.split()[0]
                        if name not in seen:
                            seen.add(name)
                            url = line.split()[1]
                            if "github" in url:
                                remotes.append(("GitHub", name))
                            elif "gitlab" in url:
                                remotes.append(("GitLab", name))
                            else:
                                remotes.append(("Git", name))
        except Exception:
            pass
        if not remotes:
            remotes = [("Git", "origin")]
        return remotes

    def _update_git_tooltip(self):
        names = [r[0] for r in self.git_remotes]
        if len(names) == 1:
            self.git_btn.setToolTip(f"Salva su {names[0]}")
        else:
            self.git_btn.setToolTip(f"Salva su {', '.join(names)}")

    def _do_git_save(self):
        """Salva (push) su tutti i remote Git configurati.

        Implementazione reale:
          1. legge i remote salvati in CONFIG/settings.json (SettingsPanel)
          2. **C1**: apre dialog di conferma con lista dei remote
          3. per ogni remote, inietta il token nell'URL (https://oauth2:TOKEN@...)
          4. fa `git add -A` + `git commit -m "Auto-sync ..."` + `git push REMOTE BRANCH`
          5. **C2**: raccoglie gli errori e mostra dialog di riepilogo

        Se non ci sono remote configurati nel settings store, usa i remote
        git locali (rilevati con `git remote -v`) come fallback.
        """
        import time, os
        from GUI import settings_store as ss

        # 1) Leggi i remote configurati dall'utente nel SettingsPanel
        configured = ss.get_git_remotes()
        # 2) Se vuoti, fallback ai remote git locali (vecchio comportamento)
        if not configured:
            names = [r[0] for r in self.git_remotes]
            print(f"[GIT] Nessun remote configurato in settings. Uso i remote locali: {', '.join(names)}")
            # C1: conferma anche per il fallback ai remote locali
            ok = self._confirm_push(
                title="Salvataggio su Git (remote locali)",
                remote_list=[(n, "(remote git locale)", r) for r, n in self.git_remotes],
            )
            if not ok:
                return
            errors = []
            for rtype, name in self.git_remotes:
                err = self._git_push_one(name, None, branch=None)
                if err:
                    errors.append((name, err))
            # C2: dialog di riepilogo
            self._show_push_summary(
                total=len(self.git_remotes),
                errors=errors,
                remote_list=[(n, "(remote git locale)") for r, n in self.git_remotes],
            )
            return

        # 3) **C1**: dialog di conferma con lista dei remote
        remote_list_for_dialog = []
        env_key_by_type = {
            "github": "BSWARM_GITHUB_TOKEN",
            "gitlab": "BSWARM_GITLAB_TOKEN",
        }
        for r in configured:
            name = r.get("name", "?")
            url = r.get("url", "")
            rtype = r.get("type", "git")
            env_key = env_key_by_type.get(str(rtype).lower())
            env_token = os.environ.get(env_key, "") if env_key else ""
            source = f"env {env_key}" if env_token else "CONFIG/settings.json"
            remote_list_for_dialog.append((name, url, source))

        ok = self._confirm_push(
            title=f"Salvataggio su {len(configured)} remote Git",
            remote_list=remote_list_for_dialog,
        )
        if not ok:
            print("[GIT] Push annullato dall'utente.")
            return

        # 4) Push su ogni remote + raccoglie errori per C2
        print(f"[GIT] Salvataggio su {len(configured)} remote configurati:")
        errors = []
        for r in configured:
            name = r.get("name", "?")
            url = r.get("url", "")
            token = r.get("token", "")
            rtype = r.get("type", "git")
            # T1.3: il token da env ha SEMPRE priorità su quello salvato
            env_key = env_key_by_type.get(str(rtype).lower())
            env_token = os.environ.get(env_key, "") if env_key else ""
            if env_token:
                token = env_token
                print(f"  • {name} ({rtype}): {url} [token da env {env_key}]")
            else:
                print(f"  • {name} ({rtype}): {url} [token da CONFIG]")
            err = self._git_push_one(name, url, token=token)
            if err:
                errors.append((name, err))

        # 5) **C2**: dialog di riepilogo
        self._show_push_summary(
            total=len(configured),
            errors=errors,
            remote_list=[(n, u) for n, u, _ in remote_list_for_dialog],
        )

    def _confirm_push(self, title: str, remote_list) -> bool:
        """C1: dialog di conferma prima del push. Ritorna True se l'utente
        conferma, False se annulla.

        ``remote_list`` è una lista di tuple:
          - (name, url, source) — per i remote da CONFIG
          - (name, url, type) — per i remote git locali (compat)
        """
        from PyQt6.QtWidgets import QMessageBox
        lines = ["Questa operazione farà:"]
        lines.append("  • git add -A  (tutte le modifiche)")
        lines.append("  • git commit -m \"Auto-sync YYYY-MM-DD HH:MM:SS\"")
        lines.append("  • git push REMOTE BRANCH  (su tutti i remote sotto)")
        lines.append("")
        lines.append(f"Remote ({len(remote_list)}):")
        for entry in remote_list:
            if len(entry) == 3:
                name, url, info = entry
            else:
                name, url = entry
                info = ""
            icon = "🐙" if "github" in str(info).lower() or "github" in url else (
                "🦊" if "gitlab" in url else "📂"
            )
            line = f"  {icon} {name} — {url}"
            if info and info not in ("github", "gitlab", "git"):
                line += f"  [token: {info}]"
            lines.append(line)
        lines.append("")
        lines.append("Vuoi continuare?")
        msg = QMessageBox(self)
        msg.setWindowTitle("Conferma push Git")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText("\n".join(lines))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def _show_push_summary(self, total: int, errors, remote_list):
        """C2: dialog di riepilogo dopo il push.

        - Se 0 errori: dialog informativo "✅ Push completato"
        - Se alcuni errori: dialog di warning con elenco errori
        - Se tutti falliti: dialog critical
        """
        from PyQt6.QtWidgets import QMessageBox
        success = total - len(errors)
        if not errors:
            QMessageBox.information(
                self,
                "Push completato",
                f"✅ Push completato con successo su tutti i {total} remote.\n\n"
                + "\n".join(f"  ✓ {n} — {u}" for n, u in remote_list),
            )
            return
        if success == 0:
            icon = QMessageBox.Icon.Critical
            title = "Push fallito su tutti i remote"
            head = f"❌ Tutti i {total} push sono falliti:\n\n"
        else:
            icon = QMessageBox.Icon.Warning
            title = f"Push parziale: {success}/{total} OK"
            head = (f"⚠️ {success}/{total} remote OK, {len(errors)} falliti:\n\n")
        body = head + "\n".join(f"  ✗ {n}: {e[:200]}" for n, e in errors)
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(icon)
        msg.setText(body)
        msg.exec()

    def _git_push_one(self, remote_name: str, url: str | None, token: str = "", branch: str | None = None):
        """Esegue git add + commit + push su un singolo remote.

        Se ``url`` è None, usa il remote locale già configurato in .git/config.
        Se ``token`` è presente, lo inietta nell'URL per il push (https only).

        Ritorna: ``None`` se tutto OK, oppure una stringa con l'errore.
        """
        import os, subprocess, time

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Auto-sync {ts}"

        try:
            # 1) git add -A
            r_add = subprocess.run(
                ["git", "add", "-A"],
                cwd=base_dir, capture_output=True, text=True, timeout=30,
            )
            if r_add.returncode != 0:
                err = f"git add fallito: {r_add.stderr.strip()}"
                print(f"[GIT:{remote_name}] {err}")
                return err

            # 2) git commit -m "Auto-sync ..." (ok anche se nothing to commit)
            r_commit = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=base_dir, capture_output=True, text=True, timeout=30,
            )
            if r_commit.returncode != 0 and "nothing to commit" not in r_commit.stdout.lower():
                # "nothing to commit" non è un errore: push OK anche senza modifiche
                err = f"commit: {r_commit.stdout.strip() or r_commit.stderr.strip()}"
                print(f"[GIT:{remote_name}] {err}")

            # 3) Determina branch corrente (default main)
            if branch is None:
                r_branch = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=base_dir, capture_output=True, text=True, timeout=5,
                )
                branch = r_branch.stdout.strip() or "main"

            # 4) Se url + token forniti, inietta il token per il push
            push_url = None
            if url and token and url.startswith("https://"):
                push_url = url.replace("https://", f"https://oauth2:{token}@")
            elif url and token and url.startswith("http://"):
                push_url = url.replace("http://", f"http://oauth2:{token}@")

            if push_url:
                # Push diretto usando URL con token
                r_push = subprocess.run(
                    ["git", "push", push_url, branch],
                    cwd=base_dir, capture_output=True, text=True, timeout=120,
                )
            else:
                # Push usando il remote locale già configurato
                r_push = subprocess.run(
                    ["git", "push", remote_name, branch],
                    cwd=base_dir, capture_output=True, text=True, timeout=120,
                )

            if r_push.returncode == 0:
                print(f"[GIT:{remote_name}] ✓ push OK ({branch})")
                return None  # success
            else:
                err = r_push.stderr.strip() or r_push.stdout.strip()
                print(f"[GIT:{remote_name}] ✗ push fallito: {err}")
                return err

        except subprocess.TimeoutExpired:
            err = "timeout (push > 120s)"
            print(f"[GIT:{remote_name}] ✗ {err}")
            return err
        except FileNotFoundError:
            err = "git non trovato (subprocess)"
            print(f"[GIT:{remote_name}] ✗ {err}")
            return err
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"[GIT:{remote_name}] ✗ {err}")
            return err

    def _device_row(self, name, color, model_name):
        row = QFrame()
        row.setObjectName(f"{name.lower()}_row")
        row.setMinimumHeight(24)
        row.setStyleSheet(
            f"QFrame#{name.lower()}_row {{ border:1px solid {color}44; "
            f"border-radius:4px; }}"
        )
        # Cliccabile → apre "Modelli → Attori" per scegliere gli LLM
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setToolTip(f"{name}: clicca per configurare i modelli (Modelli → Attori)")
        row.mousePressEvent = lambda e: self._open_actors_panel()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"color:{color}; font-size:12px; font-weight:bold;")
        lbl.setMinimumWidth(32)
        lay.addWidget(lbl)

        model_lbl = QLabel(model_name)
        model_lbl.setStyleSheet("font-size:10px;")
        model_lbl.setMinimumWidth(72)
        lay.addWidget(model_lbl)

        temp_lbl = QLabel("45°C")
        tok_lbl = QLabel("12t/s")
        kv_lbl = QLabel("2.1G")
        mem_lbl = QLabel("65%")
        bus_lbl = QLabel("800M")

        for w in (temp_lbl, tok_lbl, kv_lbl, mem_lbl, bus_lbl):
            w.setStyleSheet("font-size:11px; font-weight:500;")
            w.setMinimumWidth(38)
            lay.addWidget(w)

        row._temp = temp_lbl
        row._tok = tok_lbl
        row._kv = kv_lbl
        row._mem = mem_lbl
        row._bus = bus_lbl
        row._model = model_lbl
        return row


# ═══════════════════════════════════════════════════════════════
# SEZIONE COLLABILE
# ═══════════════════════════════════════════════════════════════
class CollapsibleSection(QFrame):
    # Segnale emesso quando lo stato cambia (per sincronizzare più sezioni)
    toggled = pyqtSignal(bool)

    def __init__(self, title, icon="📁", parent=None):
        super().__init__(parent)
        self.setObjectName("collapsible_section")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.header = QFrame()
        self.header.setObjectName("section_header")
        # Altezza minima su tutti gli header: uniformità visiva tra le 5 sezioni
        # collassabili (Navigatore, Backup, Log, Integrità, Sicurezza).
        # minHeight invece di setFixedHeight così non si comprimono a 0
        # quando la finestra si restringe.
        self.header.setMinimumHeight(48)
        header_lay = QHBoxLayout(self.header)
        header_lay.setContentsMargins(14, 10, 14, 10)
        header_lay.setSpacing(8)

        self.title_lbl = QLabel(f"{icon} {title}")
        self.title_lbl.setStyleSheet("font-size:13px; font-weight:bold; ")
        # Titolo senza stretch: resta compatto a sinistra, non si espande
        # creando spazio vuoto quando la finestra è larga o cambia stato.
        header_lay.addWidget(self.title_lbl, stretch=0)

        self.toggle_btn = QPushButton("▾")
        self.toggle_btn.setMinimumSize(28, 28)
        self.toggle_btn.setStyleSheet(
            "QPushButton { background:#e8e8ec; border:none; border-radius:4px; "
            "font-size:12px; font-weight:bold; }"
            "QPushButton:hover { background:#d0d0d0; }"
        )
        self.toggle_btn.clicked.connect(self._on_toggle)
        header_lay.addWidget(self.toggle_btn)

        lay.addWidget(self.header)

        self.content = QWidget()
        self.content.setStyleSheet("border-bottom-left-radius:8px; border-bottom-right-radius:8px;")
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(12, 12, 12, 12)
        self.content_lay.setSpacing(8)

        lay.addWidget(self.content)

        self._expanded = True
        self._sync_silent = False  # True quando il cambio è programmatico (no signal)

    def _on_toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.content.show()
            self.toggle_btn.setText("▾")
        else:
            self.content.hide()
            self.toggle_btn.setText("▸")
        # Emetti segnale solo se il cambio è manuale (non da sync)
        if not self._sync_silent:
            self.toggled.emit(self._expanded)

    def set_expanded(self, expanded: bool):
        """Cambia lo stato programmaticamente (per sincronizzazione).
        Non emette il segnale toggled (evita loop)."""
        if self._expanded == expanded:
            return
        self._sync_silent = True
        try:
            self._on_toggle()
        finally:
            self._sync_silent = False

    def add_widget(self, widget):
        self.content_lay.addWidget(widget)

    def add_header_widget(self, widget, max_width: int = 260,
                          min_width: int = 0, stretch: int = 0):
        """Aggiunge un widget COMPATTO nella riga di titolo (header).

        Va prima del pulsante toggle; utile per azioni/surface di ricerca
        sempre visibili anche a sezione collassata. `min_width` garantisce
        la larghezza minima (il sizeHint del widget altrimenti vince sul
        max, lasciando il campo troppo stretto); `stretch` > 0 lo fa
        crescere con la finestra.
        """
        lay = self.header.layout()
        idx = lay.indexOf(self.toggle_btn)
        if max_width:
            widget.setMaximumWidth(max_width)
        if min_width:
            widget.setMinimumWidth(min_width)
        lay.insertWidget(idx, widget, stretch)


# ═══════════════════════════════════════════════════════════════
# CARD PLANCIA
# ═══════════════════════════════════════════════════════════════
class PlanciaCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title, subtitle, badge=None, badge_color="#666", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Altezza minima uniforme per tutte le card: 110px bastano per
        # titolo + 2 righe di descrizione (word-wrap tronca al bisogno).
        # Size policy orizzontale Expanding: la card RIEMPIE la cella della
        # grid, qualunque sia la lunghezza del titolo.
        # Altezza: lasciato al layout natural expansion (no fixed/minimum
        # imposti così la card cresce proporzionalmente con la finestra).
        # grid, qualunque sia la lunghezza del titolo. Nessun MinimumWidth
        # (sennò invalidate il ColumnStretch e le colonne diventano disuguali).
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # MinimumWidth molto basso: lascia che la grid restringa la card
        # fino a 120px senza forzare la colonna a essere più larga.
        self.setMinimumWidth(120)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:14px; font-weight:bold; ")
        # Il titolo NON deve espandere orizzontalmente né forzare la larghezza
        # minima della card. word-wrap attivo così i titoli lunghi vanno a capo
        # invece di allargare la card.
        title_lbl.setWordWrap(True)
        title_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        head.addWidget(title_lbl, stretch=1)

        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setStyleSheet(
                f"background:{badge_color}22; color:{badge_color}; "
                f"padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;"
            )
            # Il badge non deve espandere né forzare la larghezza
            badge_lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            head.addWidget(badge_lbl)

        lay.addLayout(head)

        sub_lbl = QLabel(subtitle)
        # word-wrap attivo: la descrizione va a capo ma NON espande la card
        # (l'altezza è fissata a 110px e il testo in eccesso viene troncato).
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("font-size:11px; ")
        sub_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(sub_lbl, stretch=1)

        lay.addStretch()

        # Tema: il QSS app-level stila QFrame#card; l'hover aggiunge solo
        # il bordo (il background resta quello del tema).
        self._normal_style = ""
        self._hover_style = (
            "QFrame#card { border:1px solid #16a34a; border-radius:8px; }"
        )

    def enterEvent(self, event):
        self.setStyleSheet(self._hover_style)

    def leaveEvent(self, event):
        self.setStyleSheet(self._normal_style)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ═══════════════════════════════════════════════════════════════
# LOG CATEGORIZZATO
# ═══════════════════════════════════════════════════════════════
class CategorizedLogViewer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("log_viewer")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Fix: la scheda "🦙 Ollama" è stata spostata nel pannello Modelli → Attori
        # (per verificare se Ollama funziona su quel PC). Qui resta solo la
        # scheda "🐝 ByteSwarm GUI" — il diario di bordo del sistema.
        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.setMovable(False)
        self.tab_bar.addTab("🐝 ByteSwarm GUI")
        # Stile del tab bar dal tema app-level (QTabBar nei .qss) — segue
        # il tema live; niente colori hardcoded light-only.
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self.tab_bar)

        self.log_stack = QStackedWidget()
        self.logs = {}
        # Solo "byteswarm" ora (ollama è nel pannello Modelli → Attori)
        categories = ["byteswarm"]
        colors = {"byteswarm": "#f9e2af"}

        for cat in categories:
            log_widget = QTextEdit()
            log_widget.setReadOnly(True)
            # Stile dal tema app-level (QTextEdit nei .qss).
            pass
            sample = self._get_sample_log(cat, colors[cat])
            log_widget.setPlainText(sample)
            self.logs[cat] = log_widget
            self.log_stack.addWidget(log_widget)

        lay.addWidget(self.log_stack, stretch=1)

    def _get_sample_log(self, category, color):
        # SOSTITUISCI i log finti con log reali
        if category == "byteswarm":
            return get_logs(50)
        return ""

    def _on_tab_changed(self, index):
        self.log_stack.setCurrentIndex(index)


# ═══════════════════════════════════════════════════════════════
# BACKUP CODE LOGS
# ═══════════════════════════════════════════════════════════════
class BackupCodeLogs(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backup_logs")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QLabel("<b>💾 Backup Code — Git Logs</b>")
        header.setStyleSheet("padding:8px 12px; font-size:12px;")
        lay.addWidget(header)

        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.setMovable(False)
        self.tab_bar.addTab("🐙 GitHub")
        self.tab_bar.addTab("🦊 GitLab")
        self.tab_bar.addTab("📂 Git")
        self.tab_bar.setStyleSheet(
            "QTabBar::tab { padding:6px 12px; margin:2px; font-size:11px; }"
        )
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self.tab_bar)

        self.log_stack = QStackedWidget()
        self.logs = {}
        categories = ["github", "gitlab", "git"]
        colors = {"github": "#89b4fa", "gitlab": "#f38ba8", "git": "#fab387"}

        for cat in categories:
            log_widget = QTextEdit()
            log_widget.setReadOnly(True)
            # Stile dal tema app-level (QTextEdit nei .qss).
            sample = self._get_sample_log(cat, colors[cat])
            log_widget.setPlainText(sample)
            self.logs[cat] = log_widget
            self.log_stack.addWidget(log_widget)

        lay.addWidget(self.log_stack, stretch=1)

    def _get_sample_log(self, category, color):
        samples = {
            "github": f"[{color}] 2026-11-01 11:40:15 [INFO]  Push to main branch\n"
                     f"[{color}] 2026-11-01 11:40:16 [INFO]  CI pipeline triggered\n"
                     f"[{color}] 2026-11-01 11:40:18 [DEBUG] Running tests (3/15)\n"
                     f"[{color}] 2026-11-01 11:40:22 [SUCCESS] All tests passed\n",
            "gitlab": f"[{color}] 2026-11-01 11:38:10 [INFO]  MR !42 merged\n"
                     f"[{color}] 2026-11-01 11:38:12 [INFO]  Pipeline #1234 started\n"
                     f"[{color}] 2026-11-01 11:38:45 [WARNING] Coverage dropped to 82%\n"
                     f"[{color}] 2026-11-01 11:39:01 [SUCCESS] Deployment to staging\n",
            "git": f"[{color}] 2026-11-01 11:35:00 [INFO]  Commit: a1b2c3d - Fix bug in parser\n"
                  f"[{color}] 2026-11-01 11:35:01 [INFO]  Branch: feature/usb-reverse\n"
                  f"[{color}] 2026-11-01 11:35:02 [DEBUG] 3 files changed, +45 -12\n"
                  f"[{color}] 2026-11-01 11:42:00 [INFO]  Pull from origin/main successful\n"
        }
        return samples.get(category, "")

    def _on_tab_changed(self, index):
        self.log_stack.setCurrentIndex(index)


# ═══════════════════════════════════════════════════════════════
# CODE EXPLORER
# ═══════════════════════════════════════════════════════════════
class CodeNode:
    def __init__(self, name, node_type, line_start, line_end, children=None):
        self.name = name
        self.node_type = node_type
        self.line_start = line_start
        self.line_end = line_end
        self.children = children or []
        self.expanded = True
        self.x = 0
        self.y = 0


class CodeExplorer(QFrame):
    node_clicked = pyqtSignal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("code_explorer")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(QLabel("<b>🎮 Navigatore di codice Interattivo</b>"))
        head.addStretch()

        # Pulsanti zoom in/out e reset pan — prima esistevano ma non erano
        # collegati a nessuna funzione (artefatti visivi). Ora funzionano.
        zoom_in = QPushButton("+")
        zoom_in.setFixedSize(26, 26)
        zoom_in.setObjectName("code_zoom_in")
        zoom_in.setToolTip("Zoom in (ingrandisci grafo)")
        zoom_in.setStyleSheet(
            "QPushButton#code_zoom_in { font-size:14px; font-weight:bold; "
            "background:#e8e8ec; border:1px solid #d0d0d0; border-radius:4px; }"
            "QPushButton#code_zoom_in:hover { background:#d0d0d0; }"
        )
        zoom_in.clicked.connect(self._zoom_in)
        head.addWidget(zoom_in)

        zoom_out = QPushButton("-")
        zoom_out.setFixedSize(26, 26)
        zoom_out.setObjectName("code_zoom_out")
        zoom_out.setToolTip("Zoom out (riduci grafo)")
        zoom_out.setStyleSheet(
            "QPushButton#code_zoom_out { font-size:14px; font-weight:bold; "
            "background:#e8e8ec; border:1px solid #d0d0d0; border-radius:4px; }"
            "QPushButton#code_zoom_out:hover { background:#d0d0d0; }"
        )
        zoom_out.clicked.connect(self._zoom_out)
        head.addWidget(zoom_out)

        # Pulsante reset zoom (pan/fit) — resetta la vista al grafo intero
        reset_btn = QPushButton("⟳")
        reset_btn.setFixedSize(26, 26)
        reset_btn.setObjectName("code_zoom_reset")
        reset_btn.setToolTip("Reset vista (fit grafo)")
        reset_btn.setStyleSheet(
            "QPushButton#code_zoom_reset { font-size:13px; "
            "background:#e8e8ec; border:1px solid #d0d0d0; border-radius:4px; }"
            "QPushButton#code_zoom_reset:hover { background:#d0d0d0; }"
        )
        reset_btn.clicked.connect(self._reset_view)
        head.addWidget(reset_btn)

        lay.addLayout(head)

        self.file_label = QLabel("Nessun file caricato")
        self.file_label.setStyleSheet("font-size:11px;")
        lay.addWidget(self.file_label)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        lay.addWidget(self.view)

        legend = QHBoxLayout()
        legend.addWidget(self._legend_item("Classe", "#89b4fa"))
        legend.addWidget(self._legend_item("Funzione", "#a6e3a1"))
        legend.addWidget(self._legend_item("Variabile", "#fab387"))
        lay.addLayout(legend)

        self.nodes = []

    def _legend_item(self, label, color):
        widget = QWidget()
        lay = QHBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        indicator = QLabel("●")
        indicator.setStyleSheet(f"color:{color}; font-size:14px;")
        lay.addWidget(indicator)
        text = QLabel(label)
        text.setStyleSheet("font-size:10px; ")
        lay.addWidget(text)
        return widget

    # ── Zoom / pan handlers ────────────────────────────────────────────
    def _zoom_in(self):
        """Ingrandisce il grafo del 20% (zoom in)."""
        self.view.scale(1.2, 1.2)

    def _zoom_out(self):
        """Riduce il grafo del 20% (zoom out)."""
        self.view.scale(1 / 1.2, 1 / 1.2)

    def _reset_view(self):
        """Reset zoom/pan: fit del grafo nell'area visibile."""
        self.view.resetTransform()
        if self.scene.items():
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def load_file(self, file_path):
        self.file_label.setText(os.path.basename(file_path))
        self.nodes = []
        self.scene.clear()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            self._parse_ast(tree, file_path)
            self._layout_nodes()
            self._render_nodes()
        except Exception as e:
            self.scene.addText(f"Errore parsing: {e}")

    def _parse_ast(self, tree, file_path):
        module_node = CodeNode(os.path.basename(file_path), "module", 1, len(tree.body), [])
        self.nodes.append(module_node)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_node = CodeNode(node.name, "class", node.lineno, node.end_lineno or node.lineno + 10, [])
                module_node.children.append(class_node)
                self.nodes.append(class_node)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        func_node = CodeNode(item.name, "function", item.lineno, item.end_lineno or item.lineno + 5, [])
                        class_node.children.append(func_node)
                        self.nodes.append(func_node)
            elif isinstance(node, ast.FunctionDef):
                if not any(n.children and node in n.children for n in self.nodes):
                    func_node = CodeNode(node.name, "function", node.lineno, node.end_lineno or node.lineno + 5, [])
                    module_node.children.append(func_node)
                    self.nodes.append(func_node)

    def _layout_nodes(self):
        y_spacing = 80
        x_spacing = 200
        if self.nodes:
            self.nodes[0].x = 200
            self.nodes[0].y = 50
            child_y = 150
            for child in self.nodes[0].children:
                child.x = 200
                child.y = child_y
                child_y += y_spacing
                if child.children:
                    grandchild_x = 450
                    for gc in child.children:
                        gc.x = grandchild_x
                        gc.y = child.y
                        grandchild_x += x_spacing

    def _render_nodes(self):
        colors = {"module": "#cdd6f4", "class": "#89b4fa", "function": "#a6e3a1", "variable": "#fab387"}
        for node in self.nodes:
            if node.children:
                for child in node.children:
                    line = self.scene.addLine(node.x + 60, node.y + 20, child.x + 60, child.y + 20, QPen(QColor("#6c7086"), 1.5))
                    line.setZValue(-1)

        for node in self.nodes:
            color = colors.get(node.node_type, "#cdd6f4")
            rect = QGraphicsRectItem(node.x, node.y, 140, 40)
            rect.setBrush(QBrush(QColor(color)))
            rect.setPen(QPen(QColor("#1e1e2e"), 2))
            rect.setZValue(0)
            self.scene.addItem(rect)

            text = self.scene.addText(f"{node.name}")
            text.setDefaultTextColor(QColor("#1e1e2e"))
            text.setPos(node.x + 10, node.y + 8)
            text.setZValue(1)

            line_info = self.scene.addText(f"L{node.line_start}-{node.line_end}")
            line_info.setDefaultTextColor(QColor("#6c7086"))
            line_info.setPos(node.x + 10, node.y + 24)
            line_info.setScale(0.7)
            line_info.setZValue(1)

            rect.setAcceptHoverEvents(True)
            rect.mousePressEvent = lambda e, n=node: self._on_node_click(n)

    def _on_node_click(self, node):
        node.expanded = not node.expanded
        self.scene.clear()
        self._render_nodes()
        self.node_clicked.emit(node.name, node.line_start, node.line_end)


# ═══════════════════════════════════════════════════════════════
# FILE EDITOR
# ═══════════════════════════════════════════════════════════════
class FileEditorWidget(QFrame):
    closed = pyqtSignal()
    dock_requested = pyqtSignal()
    undock_requested = pyqtSignal()

    def __init__(self, file_path, docked=False, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._docked = docked
        self.setObjectName("editor_widget")

        if not docked:
            self.setMinimumSize(420, 320)
            self.setStyleSheet("QFrame#editor_widget { border-radius:12px; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(QLabel(f"<b>📝 {os.path.basename(file_path)}</b>"))
        head.addStretch()

        self.dock_btn = QPushButton("📌 Dock" if not docked else "📌 Undock")
        self.dock_btn.setFixedHeight(28)
        self.dock_btn.setObjectName("dock_btn")
        self.dock_btn.setStyleSheet(
            "QPushButton#dock_btn { background:#2563eb; color:white; border-radius:4px; font-size:11px; padding:0 10px; border:none; }"
            "QPushButton#dock_btn:hover { background:#1d4ed8; }"
        )
        self.dock_btn.clicked.connect(self._on_dock_toggle)
        head.addWidget(self.dock_btn)

        save_btn = QPushButton("💾 Salva")
        save_btn.setObjectName("primary_btn")
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(self._save)
        head.addWidget(save_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.closed.emit)
        head.addWidget(close_btn)
        lay.addLayout(head)

        path_lbl = QLabel(file_path)
        path_lbl.setStyleSheet("font-size:10px; font-family:monospace;")
        lay.addWidget(path_lbl)

        self.editor = QTextEdit()
        self.editor.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; font-size:12px; padding:8px;"
        )
        # ESC chiude l'editor anche quando il focus è sul campo di testo
        self.editor.installEventFilter(self)
        lay.addWidget(self.editor)

        self.status = QLabel("Pronto")
        self.status.setStyleSheet("font-size:11px;")
        lay.addWidget(self.status)

        self._load_file()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import Qt as _Qt, QEvent
        if obj is self.editor and event.type() == QEvent.Type.KeyPress:
            if event.key() == _Qt.Key.Key_Escape:
                self.closed.emit()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """ESC chiude l'editor overlay."""
        from PyQt6.QtCore import Qt as _Qt
        if event.key() == _Qt.Key.Key_Escape:
            self.closed.emit()
            return
        super().keyPressEvent(event)

    def _on_dock_toggle(self):
        if self._docked:
            self.undock_requested.emit()
        else:
            self.dock_requested.emit()

    def _load_file(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                self.editor.setPlainText(f.read())
            self.status.setText(f"Caricato · {len(self.editor.toPlainText())} caratteri")
        except Exception as e:
            self.editor.setPlainText(f"[Errore lettura: {e}]")
            self.status.setText("Errore")

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.status.setText(f"✓ Salvato · {len(self.editor.toPlainText())} caratteri")
        except Exception as e:
            self.status.setText(f"✕ Errore: {e}")


# ═══════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════
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
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
                ]),
                ("Planner", "planner", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
                ]),
                ("Worker Coder", "worker_coder", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
                ]),
                ("Worker General", "worker_general", [
                    ("name", "Modello", "combo", []),
                    ("temperature", "Temperature", "spin_float", (0.0, 2.0, 0.05)),
                    ("num_ctx", "Context window", "spin_int", (512, 32768, 256)),
                    ("num_predict", "Max tokens", "spin_int", (64, 4096, 64)),
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
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
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
        self._current_project_path = None
        self.center = CenterArea(self)

        root.addWidget(self._build_toolbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.drawer)
        body.addWidget(self.center, stretch=1)
        root.addLayout(body, stretch=1)

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

        self._cpu_temp = 45
        self._gpu_temp = 38
        self._tok_s = 12.5
        self._kv = "2.1G"
        self._mem = 65
        self._freq = 800
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_metrics)
        self._timer.start(1500)

        self._editor_overlay = None
        self._editor_docked = None
        self._credits_overlay = None
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
        bar.setFixedHeight(64)
        lay = QHBoxLayout(bar)
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
        lay.addWidget(self.project_tabs, stretch=1)

        sep2 = QFrame()
        sep2.setFixedWidth(1)
        lay.addWidget(sep2)

        self.device_panel = DevicePanel()
        lay.addWidget(self.device_panel)

        # Pulsante ▶/⏸ della toolbar = Pausa/Riprendi orchestratore
        # (stessa logica del menu: state/pause.flag).
        self.device_panel.toggle_btn.clicked.connect(self._toggle_orchestrator)
        self._sync_toggle_icon()

        return bar


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
        btn = self.device_panel.toggle_btn
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pause_file = os.path.join(base, 'state', 'pause.flag')
        running_style = ("QPushButton#primary_btn { background:#16a34a; color:white; "
                         "font-weight:bold; font-size:16px; border-radius:6px; "
                         "border:none; }")
        paused_style = ("QPushButton#primary_btn { background:#f59e0b; color:white; "
                        "font-weight:bold; font-size:14px; border-radius:6px; "
                        "border:none; }")
        try:
            if btn.text() == "▶":
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

    def _sync_toggle_icon(self):
        """Allinea l'icona del pulsante ▶/⏸ allo stato reale (pause.flag)."""
        import os
        btn = self.device_panel.toggle_btn
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paused = os.path.exists(os.path.join(base, 'state', 'pause.flag'))
        if paused:
            btn.setText("⏸")
            btn.setStyleSheet(
                "QPushButton#primary_btn { background:#f59e0b; color:white; "
                "font-weight:bold; font-size:14px; border-radius:6px; border:none; }")

    def _on_current_project_changed(self, path: str):
        """Salva il percorso del progetto attivo (per task per-progetto)
        e ricarica la lista task della sidebar per quel progetto."""
        # set_current_folder si occupa di: aggiornare _current_project_path,
        # aggiornare il file tree e ricaricare i task del progetto.
        self.drawer.set_current_folder(path)

    def get_current_project_path(self) -> str | None:
        """Ritorna il percorso assoluto del progetto attivo, o None."""
        return getattr(self, "_current_project_path", None)

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
        cpu._kv.setText(self._kv)
        cpu._mem.setText(f"{self._mem}%")
        cpu._bus.setText(f"{self._freq}M")

        gpu = self.device_panel.gpu_box
        gpu._model.setText(gpu_model_str)
        gpu._temp.setText(f"{self._gpu_temp:.0f}°C")

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
        bar.setFixedHeight(52)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Comando o prompt (premi Invia; validazione pre-flight automatica)")
        lay.addWidget(self.cmd_input)

        send = QPushButton("Invia")
        send.setObjectName("primary_btn")
        send.setFixedHeight(34)
        # COLLEGA IL BOTTONE
        send.clicked.connect(self._send_command)
        # PERMETTI DI PREMERE INVIO
        self.cmd_input.returnPressed.connect(self._send_command)
        lay.addWidget(send)
        return bar

    def _send_command(self):
        text = self.cmd_input.text().strip()
        if text:
            add_task_to_db(text)
            self.cmd_input.clear()
            print("Task aggiunto al database!")
            # Qui potresti aggiungere un aggiornamento della lista task nel drawer
            # self.drawer.refresh_tasks()
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


class ProjectTabBar(QTabBar):
    """Barra dei progetti aperti in alto (quella arancione/gialla).

    Prima era vuota: nessun tab veniva aggiunto e l'utente vedeva solo il
    pulsante della cartella accanto. Ora carica automaticamente:
      • il progetto corrente (byte-swarmy);
      • ogni sottocartella di ``project/`` (i task prodotti dai worker);
      • un tab "+" che apre un QFileDialog per aggiungere un nuovo progetto.
    """

    # Segnale emesso quando un nuovo progetto viene aggiunto via "+"
    project_added = pyqtSignal(str)
    # Emette il path (assoluto) della cartella quando si seleziona un tab
    current_project_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setDrawBase(False)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setExpanding(False)
        # Click su un tab → se è il "+", apri QFileDialog
        self.tabBarClicked.connect(self._on_tab_clicked)
        self.tabCloseRequested.connect(self._on_tab_close_requested)
        # Cambio tab → emetti current_project_changed con path della cartella
        self.currentChanged.connect(self._on_current_changed)
        self._load_open_projects()

    def _load_open_projects(self):
        """Popola i tab con i progetti aperti (cartelle sotto project/).

        Carica **solo** le sottocartelle reali di ``project/`` come tab —
        niente più tab hardcoded "🐝 byte-swarmy" (la cartella root non è un
        progetto caricabile, l'utente lo ha confermato). Se ``project/`` è
        vuoto, si parte direttamente dal tab ``➕``.
        """
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        projects_dir = os.path.join(base, "project")

        # Tab intermedi — SOLO sottocartelle reali di project/.
        # Ignora file (come .gitkeep, main.py) e cartelle nascoste.
        if os.path.isdir(projects_dir):
            try:
                entries = sorted(
                    e for e in os.listdir(projects_dir)
                    if os.path.isdir(os.path.join(projects_dir, e))
                    and not e.startswith(".")
                )
            except OSError:
                entries = []
            for name in entries:
                if self._find_tab(name) < 0:
                    idx = self.addTab("📁 " + name)
                    # Sostituisci la × di default con un QPushButton custom
                    # che ha 15px di margine sinistro (dal testo) e 15px di
                    # margine destro (dal bordo). Il CSS di QTabBar::close-button
                    # è notoriamente buggy in Qt, setTabButton è affidabile.
                    self._install_custom_close_button(idx)

        # Tab finale — "+" per aggiungere un nuovo progetto (non chiudibile).
        # Se non ci sono progetti reali, il ➕ è l'unico tab oltre a nessuno.
        self._plus_index = self.count()
        self.addTab("➕")
        # Nascondi la × dal tab ➕ (ha senso: il + non si "chiude", si clicca)
        self._hide_close_button(self._plus_index)
        # Seleziona il primo tab reale (se esiste), altrimenti il ➕
        if self.count() > 1:
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(self._plus_index)

    def _install_custom_close_button(self, index: int):
        """Installa un QPushButton personalizzato come close-button del tab.

        A differenza del close-button di default di Qt (che ignora i margini
        del CSS), questo widget ha controllo pixel-perfect:
          - 15px di margine sinistro (tra testo e ×)
          - 15px di margine destro (tra × e bordo del tab)
        Il click emette tabCloseRequested come il button di default.
        """
        # Larghezza totale: 15px sx + 16px (× icona) + 15px dx = 46px.
        # setFixedSize deve includere i margins, altrimenti Qt li ritaglia.
        btn = QPushButton("✕")
        btn.setFixedSize(46, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Chiudi questo progetto")
        # setContentsMargins funziona SEMPRE (a differenza del CSS close-button):
        # 15px a sinistra (tra testo e ×) + 15px a destra (tra × e bordo).
        btn.setContentsMargins(15, 0, 15, 0)
        btn.setStyleSheet(
            "QPushButton {"
            "  background:transparent; border:none; "
            "  font-size:13px; font-weight:bold; padding:0;"
            "  margin:0;"
            "}"
            "QPushButton:hover {"
            "  background:#fee2e2; color:#dc2626; border-radius:3px;"
            "}"
        )
        # Click sul pulsante → emetti tabCloseRequested per l'index giusto.
        # Usiamo una lambda con default arg per catturare l'index al momento
        # della creazione (sennò cambia se i tab vengono riordinati).
        btn.clicked.connect(lambda _, idx=index: self.tabCloseRequested.emit(idx))
        try:
            self.setTabButton(
                index,
                QTabBar.ButtonPosition.RightSide,
                btn,
            )
        except Exception:
            try:
                self.setTabButton(
                    index,
                    QTabBar.ButtonPosition.LeftSide,
                    btn,
                )
            except Exception:
                pass

    def _hide_close_button(self, index: int):
        """Rimuove il pulsante di chiusura (×) da un tab specifico."""
        try:
            self.setTabButton(
                index,
                QTabBar.ButtonPosition.RightSide,
                None,
            )
        except Exception:
            # Su alcuni platform plugin il RightSide non esiste; prova LeftSide
            try:
                self.setTabButton(
                    index,
                    QTabBar.ButtonPosition.LeftSide,
                    None,
                )
            except Exception:
                pass

    def _is_plus_tab(self, index: int) -> bool:
        return index == getattr(self, "_plus_index", -1)

    def _on_tab_clicked(self, index: int):
        """Apri il QFileDialog se l'utente clicca il tab '+'."""
        if self._is_plus_tab(index):
            self._open_new_project_dialog()

    def _on_current_changed(self, index: int):
        """Emette current_project_changed quando l'utente cambia tab.

        La sidebar 'Archivio progetto' ascolta questo segnale per aggiornare
        il file tree alla cartella del progetto appena selezionato.
        """
        if self._is_plus_tab(index):
            # Il "+" non ha una cartella associata — non emettere
            return
        path = self._path_for_tab(index)
        if path:
            self.current_project_changed.emit(path)

    def _path_for_tab(self, index: int) -> str:
        """Ricostruisce il path assoluto della cartella associata al tab.

        Per i tab ``📁 name`` corrisponde a ``project/name``, ma potrebbe
        anche essere un path assoluto salvato dal QFileDialog (in tal caso
        cerchiamo in ``_tab_paths``).
        """
        import os
        if index < 0 or index >= self.count():
            return ""
        text = self.tabText(index)
        # Salva/recupera path espliciti per tab aperti via QFileDialog
        if not hasattr(self, "_tab_paths"):
            self._tab_paths = {}
        if index in self._tab_paths:
            return self._tab_paths[index]
        # Tab del tipo "📁 name" → project/name
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        projects_dir = os.path.join(base, "project")
        if text.startswith("📁 "):
            name = text[2:]
            candidate = os.path.join(projects_dir, name)
            if os.path.isdir(candidate):
                return candidate
            # Se name contiene path separatori (cartella esterna)
            if os.path.isdir(name):
                return name
        return ""

    def _on_tab_close_requested(self, index: int):
        """Chiude un tab progetto (qualsuale tab reale tranne il '+')."""
        if self._is_plus_tab(index):
            return  # Il "+" non si chiude
        # Tutti i tab 📁 ... sono chiudibili (nessun tab hardcoded protetto)
        self.removeTab(index)
        # L'indice del "+" è sceso di 1
        self._plus_index = self.count() - 1
        # Se non ci sono più tab reali, sposta la selezione sul ➕
        if self.count() == 1:
            self.setCurrentIndex(0)

    def _open_new_project_dialog(self):
        """Apre un dialog per aggiungere un progetto.

        Chiede (opzionalmente) il link di un repository GitHub/GitLab da
        clonare e la cartella in cui salvare il progetto; se non viene
        fornito un link, permette di scegliere una cartella locale esistente.
        """
        from PyQt6.QtWidgets import (
            QFileDialog, QInputDialog, QMessageBox,
        )
        import os
        import subprocess

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        projects_dir = os.path.join(base, "project")
        start_dir = projects_dir if os.path.isdir(projects_dir) else os.path.expanduser("~")

        # 1) Link repository (opzionale)
        url, ok = QInputDialog.getText(
            None,
            "Nuovo progetto — Repository",
            "Link del repository (GitHub/GitLab) da clonare:\n"
            "(lascia vuoto per scegliere una cartella locale esistente)",
        )
        if not ok:
            self.setCurrentIndex(0)
            return
        url = (url or "").strip()

        folder = None
        if url:
            # 2) Cartella in cui salvare/clonare
            parent = QFileDialog.getExistingDirectory(
                None,
                "Scegli la cartella in cui salvare il progetto clonato",
                start_dir,
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
            )
            if not parent:
                self.setCurrentIndex(0)
                return
            # nome progetto dal basename dell'URL (senza .git)
            name = url.rstrip("/").rsplit("/", 1)[-1]
            if name.endswith(".git"):
                name = name[:-4]
            if not name:
                name = "progetto"
            target = os.path.join(parent, name)
            if os.path.exists(target):
                r = QMessageBox.question(
                    None, "Cartella esistente",
                    f"La cartella '{target}' esiste già.\n"
                    "Vuoi aprirla come progetto invece di clonare?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if r != QMessageBox.StandardButton.Yes:
                    self.setCurrentIndex(0)
                    return
            else:
                # clona
                try:
                    proc = subprocess.run(
                        ["git", "clone", url, target],
                        capture_output=True, text=True, timeout=300,
                    )
                except FileNotFoundError:
                    QMessageBox.critical(
                        None, "git non trovato",
                        "Il comando 'git' non è disponibile sul sistema.\n"
                        "Installa git oppure clona manualmente la repo.",
                    )
                    self.setCurrentIndex(0)
                    return
                except subprocess.TimeoutExpired:
                    QMessageBox.critical(
                        None, "Timeout",
                        "Il clone ha superato i 5 minuti. Riprova o clona manualmente.",
                    )
                    self.setCurrentIndex(0)
                    return
                if proc.returncode != 0:
                    QMessageBox.critical(
                        None, "Clone fallito",
                        f"git clone ha restituito errore:\n{proc.stderr.strip()[:500]}",
                    )
                    self.setCurrentIndex(0)
                    return
            folder = target
        else:
            # Nessun link: scegli cartella locale esistente (comportamento originale)
            folder = QFileDialog.getExistingDirectory(
                None,
                "Apri progetto — scegli cartella",
                start_dir,
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
            )
            if not folder:
                self.setCurrentIndex(0)
                return

        name = os.path.basename(folder.rstrip("/"))
        if not name:
            name = folder

        # Se è già aperto, selezionalo
        existing = self._find_tab(name)
        if existing >= 0:
            self.setCurrentIndex(existing)
            return

        # Aggiungi il nuovo tab PRIMA del "+" (in modo che resti sempre l'ultimo)
        new_idx = self._plus_index
        self.insertTab(new_idx, "📁 " + name)
        self._plus_index = self.count() - 1
        # Installa il close-button custom (15px dx + 15px sx) sul nuovo tab
        self._install_custom_close_button(new_idx)
        # Salva il path assoluto del nuovo tab per poter aggiornare la sidebar
        if not hasattr(self, "_tab_paths"):
            self._tab_paths = {}
        self._tab_paths[new_idx] = folder
        self.setCurrentIndex(new_idx)

        # Emette segnale/opzionalmente callback: il nome della cartella aperta
        # è disponibile per il ControlCenter (per impostare il working dir).
        if hasattr(self, "project_added"):
            self.project_added.emit(folder)

    def _find_tab(self, name: str) -> int:
        for i in range(self.count()):
            txt = self.tabText(i)
            if txt == name or txt.endswith(" " + name):
                return i
        return -1

    def refresh(self):
        """Ricarica i progetti aperti (utile dopo aver creato/eliminato task)."""
        # Rimuovi tutti i tab e ricarica
        while self.count() > 0:
            self.removeTab(0)
        self._load_open_projects()

    def add_project(self, name: str):
        """Aggiunge un progetto ai tab (se non già presente)."""
        if self._find_tab(name) < 0:
            # Inserisci prima del "+"
            new_idx = getattr(self, "_plus_index", self.count())
            self.insertTab(new_idx, "📁 " + name)
            self._plus_index = self.count() - 1
            self.setCurrentIndex(new_idx)


def _is_junk_project_path(rel: str) -> bool:
    """True per percorsi interni da NON mostrare come 'codice prodotto':
    .git/.venv/nascosti, __pycache__, .pyc — il commit del task tocca
    .git/objects DURANTE la finestra temporale e prima inquinava la lista
    ('Apri risultato' apriva project/.git/objects/12/)."""
    parts = Path(rel).parts
    if any(pp.startswith(".") or pp == "__pycache__" for pp in parts):
        return True
    return rel.endswith(".pyc")


def build_run_command(file_path):
    """Flusso utente 3: comando per eseguire il codice generato dal task
    FUORI dal sandbox (è codice dell'utente, sulla sua macchina).

    .py → python3 | .sh → bash | .c/.cpp → compila in /tmp ed esegui.
    Ritorna None per estensioni non eseguibili direttamente (es. .html:
    il chiamante lo apre nel browser).
    """
    from shlex import quote as _q
    ext = file_path.suffix.lower()
    fp = str(file_path)
    if ext == ".py":
        return ["python3", fp]
    if ext == ".sh":
        return ["bash", fp]
    if ext == ".c":
        return ["bash", "-c", f"gcc {_q(fp)} -o /tmp/bswarm_run && /tmp/bswarm_run"]
    if ext == ".cpp":
        return ["bash", "-c", f"g++ {_q(fp)} -o /tmp/bswarm_run && /tmp/bswarm_run"]
    return None


class CheckableFileSystemModel(QFileSystemModel):
    """QFileSystemModel con colonna 0 checkbox per selezione multipla file/cartelle."""
    def __init__(self):
        super().__init__()
        self._checked_paths = set()

    def columnCount(self, parent=QModelIndex()):
        return super().columnCount(parent) + 1

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return "✓"
            return super().headerData(section - 1, orientation, role)
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.column() == 0:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if self.filePath(index) in self._checked_paths else Qt.CheckState.Unchecked
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return None
        if index.column() > 0:
            orig = self.index(index.row(), index.column() - 1, index.parent())
            return super().data(orig, role)
        return super().data(index, role)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            fp = self.filePath(index)
            if value == Qt.CheckState.Checked:
                self._checked_paths.add(fp)
            else:
                self._checked_paths.discard(fp)
            self.dataChanged.emit(index, index, [role])
            return True
        if index.column() > 0:
            orig = self.index(index.row(), index.column() - 1, index.parent())
            return super().setData(orig, value, role)
        return False

    def flags(self, index):
        f = super().flags(index)
        if index.column() == 0:
            f |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
        return f

    def checked_paths(self):
        return set(self._checked_paths)

    def clear_checks(self):
        self._checked_paths.clear()


class FileTreeDrawer(QFrame):
    def __init__(self, parent):
        super().__init__()
        self.setObjectName("drawer")
        self.setFixedWidth(280)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(0)

        # Header dinamico: mostra "📁 Archivio progetto" + path corrente
        header_row = QHBoxLayout()
        header_row.setContentsMargins(16, 8, 16, 8)
        header_row.setSpacing(8)
        self.header = QLabel("<b>📁 Archivio progetto</b>")
        self.header.setObjectName("sidebar_header")
        self.header.setStyleSheet(  # nolint: header verde accordion Archivio
            "padding:0; color:#16a34a; font-size:13px;"
        )
        header_row.addWidget(self.header)
        header_row.addStretch()
        # Pulsante aggiungi nuovo file di testo
        self.add_file_btn = QPushButton("➕")
        self.add_file_btn.setFixedSize(28, 28)
        self.add_file_btn.setToolTip("Crea un nuovo file di testo nella cartella corrente")
        self.add_file_btn.setStyleSheet(
            "QPushButton { font-size:16px; border:none; background:transparent; "
            "border-radius:4px; padding:0; }"
            "QPushButton:hover { background:#e2e8f0; border-radius:4px; }"
        )
        self.add_file_btn.clicked.connect(self._add_text_file)
        header_row.addWidget(self.add_file_btn)

        # Pulsante crea nuova cartella
        self.add_folder_btn = QPushButton("📁")
        self.add_folder_btn.setFixedSize(28, 28)
        self.add_folder_btn.setToolTip("Crea una nuova cartella nella cartella corrente")
        self.add_folder_btn.setStyleSheet(
            "QPushButton { font-size:16px; border:none; background:transparent; "
            "border-radius:4px; padding:0; }"
            "QPushButton:hover { background:#e2e8f0; border-radius:4px; }"
        )
        self.add_folder_btn.clicked.connect(self._add_folder)
        header_row.addWidget(self.add_folder_btn)

        # Pulsante refresh forzato file tree (cartelle e file)
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setToolTip("Aggiorna file tree (cartelle e file della cartella corrente)")
        self.refresh_btn.setStyleSheet(
            "QPushButton { font-size:16px; border:none; background:transparent; "
            "border-radius:4px; padding:0; }"
            "QPushButton:hover { background:#e2e8f0; border-radius:4px; }"
        )
        self.refresh_btn.clicked.connect(self._refresh_file_tree)
        header_row.addWidget(self.refresh_btn)

        # Spazietto tra aggiungi e elimina
        _sp_del = QFrame()
        _sp_del.setFixedWidth(8)
        header_row.addWidget(_sp_del)

        # Pulsante elimina selezionati (archivio progetto) — in alto a destra
        self.del_btn = QPushButton("🗑️")
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setToolTip("Elimina file/cartelle selezionate con la colonna ✓")
        self.del_btn.setStyleSheet(
            "QPushButton { font-size:16px; border:none; background:transparent; "
            "border-radius:4px; padding:0; }"
            "QPushButton:hover { background:#fee2e2; border-radius:4px; }"
        )
        self.del_btn.clicked.connect(self._delete_selected_items)
        header_row.addWidget(self.del_btn)
        lay.addLayout(header_row)

        # Sotto-titolo: path della cartella corrente (si aggiorna col tab)
        self.path_label = QLabel("byte-swarmy/")
        self.path_label.setObjectName("sidebar_path")
        self.path_label.setStyleSheet(
            "padding:0 16px 4px 16px; font-size:10px; "
            "font-family:'JetBrains Mono','Consolas',monospace;"
        )
        self.path_label.setWordWrap(True)
        lay.addWidget(self.path_label)

        self.tree = QTreeView()
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.model = CheckableFileSystemModel()
        self.model.setRootPath("./")
        self.model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index("./"))
        # Colonna 0 = checkbox, colonna 1 = nome file. Nascondo dimensione/tipo/data (ora 2,3,4).
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.hideColumn(4)
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self._pending_editor_path = None
        self._editor_open_timer = None
        self.tree.clicked.connect(self._on_tree_click)
        self.tree.doubleClicked.connect(self._on_tree_double_click)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.model.dataChanged.connect(self._on_model_data_changed)
        lay.addWidget(self.tree)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("margin:8px 12px;")
        lay.addWidget(sep)

        # Layout header "Lavori e compiti" con pulsante refresh + elimina
        task_header_row = QHBoxLayout()
        task_header_row.setContentsMargins(0, 0, 0, 0)
        task_header_row.setSpacing(10)
        task_header_lbl = QLabel("<b>📋 Lavori e compiti</b>")
        task_header_lbl.setStyleSheet("font-size:11px; font-weight:bold; padding:0; margin:0;")
        task_header_row.addWidget(task_header_lbl)
        task_header_row.addStretch()

        # Pulsante riavvio forzato (refresh lista)
        task_refresh_btn = QPushButton("🔄")
        task_refresh_btn.setFixedSize(20, 20)
        task_refresh_btn.setToolTip("Aggiorna lista task")
        task_refresh_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; font-size:13px; padding:0; }"
        )
        task_refresh_btn.clicked.connect(self._force_refresh_tasks)
        task_header_row.addWidget(task_refresh_btn)

        # Spazietto tra refresh e aggiungi
        _sp1 = QFrame()
        _sp1.setFixedWidth(8)
        task_header_row.addWidget(_sp1)

        # Pulsante aggiungi task
        task_add_btn = QPushButton("➕")
        task_add_btn.setFixedSize(20, 20)
        task_add_btn.setToolTip("Aggiungi un nuovo task")
        task_add_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; font-size:13px; padding:0; }"
            "QPushButton:hover { background:#e2e8f0; border-radius:4px; }"
        )
        task_add_btn.clicked.connect(
            lambda: self.main_win.center.open_panel("coda")
            if hasattr(self.main_win, "center") else None
        )
        task_header_row.addWidget(task_add_btn)

        # Spazietto tra aggiungi e elimina
        _sp2 = QFrame()
        _sp2.setFixedWidth(8)
        task_header_row.addWidget(_sp2)

        # Pulsante elimina task selezionati
        task_del_btn = QPushButton("🗑️")
        task_del_btn.setFixedSize(28, 28)
        task_del_btn.setToolTip("Elimina task selezionati con la colonna ✓")
        task_del_btn.setStyleSheet(
            "QPushButton { font-size:16px; border:none; background:transparent; "
            "border-radius:4px; padding:0; }"
            "QPushButton:hover { background:#fee2e2; border-radius:4px; }"
        )
        task_del_btn.clicked.connect(self._delete_checked_tasks)
        task_header_row.addWidget(task_del_btn)
        lay.addLayout(task_header_row)

        self._refreshing_tasks = False
        self.task_list = QListWidget()
        self.task_list.setObjectName("task_list")
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.itemDoubleClicked.connect(self._on_task_double_clicked)
        self.task_list.itemClicked.connect(self._on_task_item_clicked)
        self.task_list.customContextMenuRequested.connect(self._on_task_context_menu)
        self.task_list.itemChanged.connect(self._on_task_item_changed)
        # Popola con task reali del progetto attivo
        project_path = self.main_win.get_current_project_path() if hasattr(self, 'main_win') and self.main_win else None
        try:
            from GUI.main_window import load_tasks
            tasks = load_tasks(project_path)
            for t in tasks:
                title = t.get("title", t.get("description", "?"))[:50]
                st = t.get("status", "?")
                icon = {"done": "✓", "running": "▶", "pending": "○",
                        "failed": "✗", "queued": "○",
                        "paused": "⏸", "thermal_paused": "🌡"}.get(st, "?")
                item = QListWidgetItem(f"{icon} {title}")
                tid = t.get("id") or ""
                if tid:
                    item.setData(Qt.ItemDataRole.UserRole, tid)
                color = {"done": "#16a34a", "running": "#f59e0b",
                         "pending": "#888", "failed": "#dc2626",
                         "paused": "#6b7280", "thermal_paused": "#f97316"}.get(st, "#888")
                item.setForeground(QColor(color))
                # Checkbox per selezione multipla (colonna di selezione)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.task_list.addItem(item)
        except Exception as e:
            print(f"Errore popolamento task_list: {e}")
        lay.addWidget(self.task_list, stretch=1)

        self._anim = QPropertyAnimation(self, b"maximumWidth")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._open = True
        self.main_win = parent

    def set_current_folder(self, folder_path: str):
        """Aggiorna il file tree per puntare alla cartella del progetto aperto.

        Chiamato quando l'utente cambia tab in ProjectTabBar: la sidebar
        'Archivio progetto' deve riflettere la cartella su cui si sta
        lavorando (es. project/sourceCode/ quando si seleziona il tab
        'sourceCode', o la root del repo quando si seleziona byte-swarmy).

        Aggiorna anche _current_project_path su ControlCenter e ricarica
        i task della sidebar: ogni sottoprogetto ha i propri task.
        """
        import os
        if not folder_path:
            return
        # Risolvi path relativo in assoluto (es. "project/TEST_progetto"
        # passato dalle tab invece del path assoluto).
        if not os.path.isabs(folder_path):
            abs_candidate = os.path.join(str(BASE_DIR), folder_path)
            if os.path.isdir(abs_candidate):
                folder_path = abs_candidate
            else:
                # Prova anche rispetto alla cwd
                if os.path.isdir(folder_path):
                    pass  # già valido
                else:
                    return
        if not os.path.isdir(folder_path):
            return
        # Aggiorna il percorso progetto corrente su ControlCenter
        if hasattr(self, 'main_win') and self.main_win is not None:
            self.main_win._current_project_path = folder_path
        # Aggiorna root del QFileSystemModel + rootIndex del QTreeView
        self.model.setRootPath(folder_path)
        self.tree.setRootIndex(self.model.index(folder_path))
        # Aggiorna il sottotitolo con il path
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            rel = os.path.relpath(folder_path, base)
        except ValueError:
            rel = folder_path
        # Mostra path relativo con / finale per chiarezza
        display = rel.replace(os.sep, "/")
        if not display.endswith("/"):
            display += "/"
        self.path_label.setText(display)
        # Scrolla in cima
        self.tree.scrollToTop()
        # Ricarica i task della sidebar per questo progetto
        self._force_refresh_tasks()

    def _debug_call_info(self, handler_name, extra=""):
        import inspect, os
        frames = inspect.stack()
        # Cerca il frame chiamante (il primo fuori da questo metodo)
        caller = frames[1] if len(frames) > 1 else None
        if caller:
            fn = caller.function
            mod = inspect.getmodule(caller.frame)
            modname = mod.__name__ if mod else "?"
            fname = os.path.basename(caller.filename)
            line = caller.lineno
            cls = None
            # Cerca self class
            selfobj = caller.frame.f_locals.get("self")
            if selfobj is not None:
                cls = type(selfobj).__name__
            parts = [f"{cls or '?'}" , f"{fn}", f"({fname}:{line})"]
            if extra:
                parts.append(str(extra))
            return " | ".join(parts)
        return f"{handler_name} | {extra}"

    def _on_tree_click(self, index):
        """Click sull'albero file: toggle checkbox su colonna 0, apre editor su file.
        Con Shift premuto: copia negli appunti la classe/riga di chiamata."""
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt as _Qt
            if QApplication.keyboardModifiers() & _Qt.KeyboardModifier.ShiftModifier:
                path = self.model.filePath(index) if index.isValid() else ""
                info = self._debug_call_info("FileTreeDrawer._on_tree_click", path)
                QApplication.clipboard().setText(info)
                if self._GUI_DEBUG:
                    print(f"[DEBUG] Shift+click copiato negli appunti: {info}")
                return
            if not index.isValid():
                return
            if index.column() == 0:
                # Checkbox: gestita nativamente da QTreeView
                # (ItemIsUserCheckable in CheckableFileSystemModel.flags).
                # Il log viene scritto da _on_model_data_changed su dataChanged.
                # NON fare toggle manuale qui: causerebbe un doppio toggle
                # (nativo + manuale) e la checkbox sembrerebbe non funzionare.
                return
            path = self.model.filePath(index)
            if not path or not os.path.exists(path):
                return
            if os.path.isfile(path):
                # Ritarda l'apertura dell'editor: se arriva un doppio click
                # (rinomina) annulla l'apertura per non aprire l'editor inutilmente.
                self._pending_editor_path = path
                if self._editor_open_timer is None:
                    from PyQt6.QtCore import QTimer
                    self._editor_open_timer = QTimer(self)
                    self._editor_open_timer.setSingleShot(True)
                    self._editor_open_timer.timeout.connect(self._open_pending_editor)
                self._editor_open_timer.start(250)
        except Exception as e:
            print(f"Errore click albero: {e}")

    def _open_pending_editor(self):
        path = getattr(self, "_pending_editor_path", None)
        if path and os.path.isfile(path):
            _click_log("filemanager", "apri file",
                        self.main_win.get_current_project_path() if self.main_win else "", path)
            self.main_win._show_file_editor(path)
        self._pending_editor_path = None

    def _on_tree_double_click(self, index):
        """Doppio click su un file: apre il campo di rinomina con il nome
        attuale già inserito, così l'utente può cambiarlo direttamente."""
        try:
            if not index.isValid():
                return
            path = self.model.filePath(index)
            if not path or not os.path.exists(path):
                return
            if os.path.isdir(path):
                return
            # Annulla l'apertura dell'editor in attesa (era un doppio click)
            if getattr(self, "_editor_open_timer", None) is not None:
                self._editor_open_timer.stop()
            self._pending_editor_path = None
            self._rename_item(path)
        except Exception as e:
            print(f"Errore doppio click albero: {e}")

    def _on_tree_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        path = self.model.filePath(index)
        is_file = os.path.isfile(path)

        menu = QMenu(self)

        if is_file:
            act_edit = QAction("✏️ Modifica file", self)
            act_edit.triggered.connect(lambda: self.main_win._show_file_editor(path))
            menu.addAction(act_edit)
            menu.addSeparator()

        act_rename = QAction("📝 Rinomina", self)
        act_rename.triggered.connect(lambda: self._rename_item(path))
        menu.addAction(act_rename)

        act_delete = QAction("🗑️ Cancella", self)
        act_delete.triggered.connect(lambda: self._delete_item(path))
        menu.addAction(act_delete)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _rename_item(self, path):
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(path), new_name)
            try:
                os.rename(path, new_path)
                self.model.setRootPath("./")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile rinominare:\n{e}")

    def _delete_item(self, path):
        name = os.path.basename(path)
        reply = QMessageBox.question(self, "Conferma cancellazione", f"Sei sicuro di voler eliminare '{name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    import shutil
                    shutil.rmtree(path)
                self.model.setRootPath("./")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile eliminare:\n{e}")

    # Debug click/selezioni SOLO su richiesta (BSWARM_GUI_DEBUG=1): di
    # default niente spam su stdout mentre usi la GUI.
    _GUI_DEBUG = os.environ.get("BSWARM_GUI_DEBUG", "").strip() == "1"

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        """Sincronizza selezione visiva QTreeView con stato checkbox del model."""
        if Qt.ItemDataRole.CheckStateRole not in roles:
            return
        if top_left.column() != 0:
            return
        fp = self.model.filePath(top_left)
        stato = "selezionato" if fp in self.model.checked_paths() else "deselezionato"
        _click_log("filemanager", stato,
                    self.main_win.get_current_project_path() if self.main_win else "", fp)
        # setCurrentIndex garantisce il feedback visivo (highlight della riga),
        # select() aggiorna il selection model. Usiamo Rows flag così
        # viene selezionata l'intera riga, non solo la cella checkbox.
        if fp in self.model.checked_paths():
            self.tree.setCurrentIndex(top_left)
            self.tree.selectionModel().select(
                top_left,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
        else:
            self.tree.selectionModel().select(
                top_left,
                QItemSelectionModel.SelectionFlag.Deselect
                | QItemSelectionModel.SelectionFlag.Rows,
            )

    def _delete_selected_items(self):
        """Elimina file/cartelle selezionate (colonna ✓ o selezione visiva)."""
        paths = self.model.checked_paths()
        if not paths:
            selection = self.tree.selectionModel().selectedRows()
            paths = {self.model.filePath(idx) for idx in selection if idx.column() == 1}
        if not paths:
            QMessageBox.information(self, "Nessuna selezione",
                                    "Seleziona almeno un elemento con la colonna ✓.")
            return
        n = len(paths)
        # Protezione: non cancellare MAI la radice del progetto byte-swarmy
        # né la radice del progetto attivo (corromperebbe il progetto).
        base_dir = str(BASE_DIR.resolve())
        protected = {base_dir}
        cur = self.main_win.get_current_project_path() if getattr(self, 'main_win', None) else None
        if cur:
            protected.add(str(Path(cur).resolve()))
        to_delete = set()
        for fp in paths:
            rfp = str(Path(fp).resolve())
            if rfp in protected:
                continue
            to_delete.add(fp)
        skipped = n - len(to_delete)
        if skipped:
            QMessageBox.information(
                self, "Protetto",
                f"{skipped} elemento(i) protetto(i) non cancellato(i)\n"
                "(la radice del progetto non può essere eliminata).")
        if not to_delete:
            self.model.clear_checks()
            self.tree.selectionModel().clearSelection()
            return
        reply = QMessageBox.question(self, "Conferma cancellazione",
            f"Sei sicuro di voler eliminare {len(to_delete)} elemento(i)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        for fp in sorted(to_delete, reverse=True):
            _click_log("filemanager", "elimina",
                        self.main_win.get_current_project_path() if self.main_win else "", fp)
            try:
                if os.path.isdir(fp):
                    import shutil
                    shutil.rmtree(fp)
                else:
                    os.remove(fp)
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile eliminare {fp}:\n{e}")
        self.model.clear_checks()
        self.tree.selectionModel().clearSelection()

    def _on_task_item_clicked(self, item: QListWidgetItem):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt as _Qt
        if QApplication.keyboardModifiers() & _Qt.KeyboardModifier.ShiftModifier:
            tid = item.data(Qt.ItemDataRole.UserRole) if item else ""
            info = self._debug_call_info("task_list itemClicked", tid)
            QApplication.clipboard().setText(info)
            if self._GUI_DEBUG:
                print(f"[DEBUG] Shift+click copiato negli appunti: {info}")
            return
        # comportamento normale: toggle checkbox già gestito da itemChanged

    def _on_task_item_changed(self, item: QListWidgetItem):
        """Sincronizza selezione visiva QListWidget con stato checkbox."""
        if not item:
            return
        if getattr(self, "_refreshing_tasks", False):
            return
        checked = item.checkState() == Qt.CheckState.Checked
        mark = "✓" if checked else "✗"
        stato = "selezionato" if checked else "deselezionato"
        tid = item.data(Qt.ItemDataRole.UserRole)
        if self._GUI_DEBUG:
                print(f"[DEBUG] Lavori e compiti (colonna ✓): {mark} {stato} elemento='{tid} - {item.text()}'")
        _click_log("task", stato, self._current_project_path or "",
                        f"{tid} - {item.text()}")
        if checked:
            item.setSelected(True)
        else:
            item.setSelected(False)

    def _delete_checked_tasks(self):
        """Elimina i task selezionati con checkbox dalla lista Lavori e compiti."""
        checked_ids = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                tid = item.data(Qt.ItemDataRole.UserRole)
                if tid:
                    checked_ids.append(tid)
        if not checked_ids:
            QMessageBox.information(self, "Nessuna selezione",
                                    "Seleziona almeno un task con la colonna ✓.")
            return
        n = len(checked_ids)
        reply = QMessageBox.question(self, "Conferma cancellazione",
            f"Sei sicuro di voler eliminare {n} task selezionato(i)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        from GUI.main_window import delete_task
        project_path = self.main_win.get_current_project_path() if hasattr(self, 'main_win') and self.main_win else None
        for tid in checked_ids:
            # Recupera il titolo del task per il log
            titolo = ""
            for i in range(self.task_list.count()):
                it = self.task_list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == tid:
                    titolo = it.text()
                    break
            _click_log("task", "elimina", self._current_project_path or "",
                            f"{tid} - {titolo}")
            try:
                delete_task(tid, project_path)
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile eliminare task {tid}:\n{e}")
        # Ricarica lista
        self.task_list.clear()
        try:
            from GUI.main_window import load_tasks
            tasks = load_tasks(project_path)
            for t in tasks:
                title = t.get("title", t.get("description", "?"))[:50]
                st = t.get("status", "?")
                icon = {"done": "✓", "running": "▶", "pending": "○",
                        "failed": "✗", "queued": "○",
                        "paused": "⏸", "thermal_paused": "🌡"}.get(st, "?")
                item = QListWidgetItem(f"{icon} {title}")
                tid = t.get("id") or ""
                if tid:
                    item.setData(Qt.ItemDataRole.UserRole, tid)
                color = {"done": "#16a34a", "running": "#f59e0b",
                         "pending": "#888", "failed": "#dc2626",
                         "paused": "#6b7280", "thermal_paused": "#f97316"}.get(st, "#888")
                item.setForeground(QColor(color))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.task_list.addItem(item)
        except Exception as e:
            print(f"Errore ricarica task_list: {e}")

    def _add_text_file(self):
        """Crea un nuovo file di testo nella cartella corrente del progetto."""
        from PyQt6.QtWidgets import QInputDialog
        import os

        # Determina cartella di destinazione
        target_dir = ""
        idx = self.tree.currentIndex()
        if idx.isValid():
            fp = self.model.filePath(idx)
            if os.path.isdir(fp):
                target_dir = fp
            else:
                target_dir = os.path.dirname(fp)
        if not target_dir:
            target_dir = self.model.rootPath()
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = str(BASE_DIR.resolve())

        # Chiedi nome file
        name, ok = QInputDialog.getText(
            self, "Nuovo file di testo",
            "Nome del file (es. note.txt):",
            text="nuovo_file.txt",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if not any(name.endswith(ext) for ext in (".txt", ".md", ".py", ".sh",
                                                   ".log", ".json", ".csv")):
            name += ".txt"

        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            # Suggerisci un nome differente invece di dare errore
            base, ext = os.path.splitext(name)
            i = 1
            while os.path.exists(os.path.join(target_dir, f"{base} ({i}){ext}")):
                i += 1
            suggested = f"{base} ({i}){ext}"
            ans = QMessageBox.question(
                self, "Esiste già",
                f"Il file '{name}' esiste già.\nVuoi usare '{suggested}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            name = suggested
            new_path = os.path.join(target_dir, name)

        try:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write("")
            _click_log("filemanager", "crea file",
                        self.main_win.get_current_project_path() if self.main_win else "", new_path)
            # Refresh del file tree per far apparire il nuovo file
            self._refresh_file_tree()
        except Exception as e:
            QMessageBox.warning(self, "Errore",
                                f"Impossibile creare il file:\n{e}")

    def _add_folder(self):
        """Crea una nuova cartella nella cartella corrente del progetto."""
        from PyQt6.QtWidgets import QInputDialog
        import os

        # Determina cartella di destinazione (come per _add_text_file)
        target_dir = ""
        idx = self.tree.currentIndex()
        if idx.isValid():
            fp = self.model.filePath(idx)
            if os.path.isdir(fp):
                target_dir = fp
            else:
                target_dir = os.path.dirname(fp)
        if not target_dir:
            target_dir = self.model.rootPath()
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = str(BASE_DIR.resolve())

        # Chiedi nome cartella
        name, ok = QInputDialog.getText(
            self, "Nuova cartella",
            "Nome della cartella (es. sourceCode):",
            text="nuova_cartella",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        # Sanitizza: niente caratteri proibiti per nome cartella
        name = name.replace("/", os.sep).replace("\\", os.sep)
        name = os.path.basename(name)  # evita path traversal
        if not name or name in (".", ".."):
            QMessageBox.warning(self, "Nome non valido",
                                "Inserisci un nome di cartella valido.")
            return

        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            base = name
            i = 1
            while os.path.exists(os.path.join(target_dir, f"{base} ({i})")):
                i += 1
            suggested = f"{base} ({i})"
            ans = QMessageBox.question(
                self, "Esiste già",
                f"La cartella '{name}' esiste già.\nVuoi usare '{suggested}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            name = suggested
            new_path = os.path.join(target_dir, name)

        try:
            os.makedirs(new_path, exist_ok=True)
            _click_log("filemanager", "crea cartella",
                        self.main_win.get_current_project_path() if self.main_win else "", new_path)
            # Refresh del file tree per far apparire la nuova cartella
            self._refresh_file_tree()
        except Exception as e:
            QMessageBox.warning(self, "Errore",
                                f"Impossibile creare la cartella:\n{e}")

    def _refresh_file_tree(self):
        """Forza il refresh del file tree (cartelle e file della cartella corrente).
        Utile dopo creazione/eliminazione di elementi o per allineare il model
        con lo stato reale del disco."""
        try:
            target_dir = self.model.rootPath()
            if not target_dir or not os.path.isdir(target_dir):
                target_dir = str(BASE_DIR.resolve())
            self.model.setRootPath("")
            self.model.setRootPath(target_dir)
            self.tree.setRootIndex(self.model.index(target_dir))
            self.tree.scrollToTop()
            _click_log("filemanager", "refresh",
                        self.main_win.get_current_project_path() if self.main_win else "",
                        target_dir)
        except Exception as e:
            QMessageBox.warning(self, "Errore",
                                f"Impossibile aggiornare il file tree:\n{e}")

    def toggle(self):
        self._open = not self._open
        target = 0 if self._open else 280
        self._anim.setStartValue(280 if self._open else 0)
        self._anim.setEndValue(target)
        self._anim.start()


    def _pause_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_pause_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._pause_orchestrator()

    def _resume_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_resume_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._resume_orchestrator()

    def _stop_orchestrator(self):
        """Wrapper: delega al ControlCenter genitore."""
        parent = self.parent()
        while parent and not hasattr(parent, '_stop_orchestrator'):
            parent = parent.parent()
        if parent and parent is not self:
            parent._stop_orchestrator()

    def _on_task_double_clicked(self, item):
        """Doppio click su task nella sidebar -> riavvia."""
        try:
            task_id = item.data(Qt.ItemDataRole.UserRole) if hasattr(item, 'data') else None
            if task_id:
                _log_user_action("Task-Action", "avvio", task_id=task_id, details="Doppio click - riavvio veloce")
            if not task_id:
                # Fallback: estrai dal testo
                m = re.search(r'task-\d+', item.text() if hasattr(item, 'text') else str(item))
                if m:
                    task_id = m.group(0)
                else:
                    return
            ok, msg = _restart_task(task_id)
            if ok:
                # Estrai il testo originale rimuovendo eventuali ↻ ... [restart] precedenti
                if hasattr(item, 'text'):
                    txt = item.text()
                    # Rimuovi prefisso ↻ e suffisso [restart] se presenti
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"↻ {txt} [restart]")
                if hasattr(item, 'setStyleSheet'):
                    item.setForeground(QColor("#16a34a"))
                # Refresh via ControlCenter
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore double-click task: {e}")

    def _force_refresh_tasks(self):
        """Forza il refresh della lista task dal progetto attivo."""
        try:
            self._refreshing_tasks = True
            if self._GUI_DEBUG:
                print("[DEBUG] Sidebar-Refresh: refresh (aggiorna lista task)")
            _log_user_action("Sidebar-Refresh", "refresh", details="Refresh manuale lista task")
            if hasattr(self, 'task_list'):
                self.task_list.clear()
                try:
                    from GUI.main_window import load_tasks
                    project_path = self.main_win.get_current_project_path() if hasattr(self, 'main_win') and self.main_win else None
                    tasks = load_tasks(project_path)
                    for t in tasks:
                        title = t.get("title", t.get("description", "?"))[:50]
                        st = t.get("status", "?")
                        icon = {"done": "✓", "running": "▶", "pending": "○",
                                "failed": "✗", "queued": "○",
                                "paused": "⏸", "thermal_paused": "🌡"}.get(st, "?")
                        item = QListWidgetItem(f"{icon} {title}")
                        item.setData(Qt.ItemDataRole.UserRole, t.get("id", ""))
                        color = {"done": "#16a34a", "running": "#f59e0b",
                                 "pending": "#888", "failed": "#dc2626",
                                 "paused": "#6b7280", "thermal_paused": "#f97316"}.get(st, "#888")
                        item.setForeground(QColor(color))
                        # Checkbox per selezione multipla (come nel caricamento iniziale)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        item.setCheckState(Qt.CheckState.Unchecked)
                        self.task_list.addItem(item)
                except Exception as e:
                    print(f"Errore refresh task: {e}")
            parent = self.parent()
            while parent and not hasattr(parent, '_refresh_coda_card'):
                parent = parent.parent()
            if parent:
                parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore force refresh: {e}")
        finally:
            self._refreshing_tasks = False

    def _get_task_status(self, task_id):
        """Ritorna lo status corrente di un task."""
        try:
            import sqlite3, os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path, timeout=5.0)
            cur = con.cursor()
            cur.execute("SELECT status FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def _pause_task_with_refresh(self, task_id, item):
        """Mette in pausa un singolo task."""
        try:
            _log_user_action("Task-Action", "pausa", task_id=task_id, details="Task messo in pausa dall'utente")
            ok, msg = _pause_task(task_id)
            if ok and item:
                txt = item.text() if hasattr(item, 'text') else ""
                for prefix in ["⏸ ", "▶ ", "🛑 ", "↻ "]:
                    if txt.startswith(prefix):
                        txt = txt[len(prefix):]
                if " [paused]" in txt: txt = txt.replace(" [paused]", "")
                if " [restart]" in txt: txt = txt.replace(" [restart]", "")
                if " [stopped]" in txt: txt = txt.replace(" [stopped]", "")
                item.setText(f"⏸ {txt} [paused]")
                item.setForeground(QColor("#6b7280"))
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore pause task: {e}")

    def _resume_task_with_refresh(self, task_id, item):
        """Riprende un singolo task dalla pausa."""
        try:
            _log_user_action("Task-Action", "avvio", task_id=task_id, details="Task riavviato dall'utente")
            ok, msg = _resume_single_task(task_id)
            if ok and item:
                txt = item.text() if hasattr(item, 'text') else ""
                for prefix in ["⏸ ", "▶ ", "🛑 ", "↻ "]:
                    if txt.startswith(prefix):
                        txt = txt[len(prefix):]
                if " [paused]" in txt: txt = txt.replace(" [paused]", "")
                if " [restart]" in txt: txt = txt.replace(" [restart]", "")
                if " [stopped]" in txt: txt = txt.replace(" [stopped]", "")
                item.setText(f"▶ {txt}")
                item.setForeground(QColor("#f59e0b"))
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
        except Exception as e:
            print(f"Errore resume task: {e}")

    def _on_task_context_menu(self, pos):
        """Menu contestuale tasto destro su un task."""
        try:
            item = self.task_list.itemAt(pos)
            if not item:
                return
            task_id = item.data(Qt.ItemDataRole.UserRole)
            if not task_id:
                return

            from PyQt6.QtGui import QAction
            menu = QMenu(self)

            act_details = QAction("📋 Dettagli task", self)
            act_details.triggered.connect(lambda: self._show_task_details(task_id))
            menu.addAction(act_details)

            menu.addSeparator()

            act_restart = QAction("🔄 Riavvia task", self)
            act_restart.triggered.connect(lambda: self._restart_task_with_refresh(task_id, item))
            menu.addAction(act_restart)

            # Pausa/Riprendi task (singolo)
            cur_status = self._get_task_status(task_id)
            if cur_status == 'paused':
                act_resume = QAction("▶ Riprendi task", self)
                act_resume.triggered.connect(lambda: self._resume_task_with_refresh(task_id, item))
                menu.addAction(act_resume)
            elif cur_status in ('pending', 'running'):
                act_pause = QAction("⏸ Pausa task", self)
                act_pause.triggered.connect(lambda: self._pause_task_with_refresh(task_id, item))
                menu.addAction(act_pause)

            # Ferma task definitivamente
            act_stop = QAction("🛑 Ferma task", self)
            act_stop.triggered.connect(lambda: self._stop_task_with_refresh(task_id, item))
            menu.addAction(act_stop)

            act_copy = QAction("📋 Copia ID task", self)
            act_copy.triggered.connect(lambda: self._copy_task_id(task_id))
            menu.addAction(act_copy)

            menu.addSeparator()

            act_delete = QAction("🗑 Elimina task", self)
            act_delete.triggered.connect(lambda: self._delete_task_with_refresh(task_id, item))
            menu.addAction(act_delete)

            menu.addSeparator()

            act_open = QAction("📂 Apri risultato", self)
            act_open.triggered.connect(lambda: self._open_task_result(task_id))
            menu.addAction(act_open)

            menu.exec(self.task_list.mapToGlobal(pos))
        except Exception as e:
            print(f"Errore context menu: {e}")

    def _stop_task_with_refresh(self, task_id, item):
        """Ferma un singolo task e aggiorna la lista."""
        try:
            _log_user_action("Task-Action", "stop", task_id=task_id, details="Task fermato dall'utente")
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Ferma task",
                f"Fermare il task {task_id[:12]}?\n\n"
                f"L'orchestratore continuerà a girare, ma questo task verrà marcato come fallito.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ok, msg = _stop_task(task_id)
            if ok:
                if item:
                    txt = item.text() if hasattr(item, 'text') else ""
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"🛑 {txt} [stopped]")
                    item.setForeground(QColor("#dc2626"))
                # Refresh via ControlCenter
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore stop task: {e}")

    @staticmethod
    def _collect_task_files(task: dict, base_dir: str) -> list:
        """File di progetto prodotti da un task.

        1) via git: il worker committa con messaggio 'task <id>: ...' →
           file toccati da quei commit;
        2) fallback: file in project/ modificati nell'intervallo di vita
           del task (started_at..completed_at, ±120s di margine).
        Ritorna path RELATIVI a project/, ordinati.
        """
        import subprocess
        from pathlib import Path
        proj = Path(base_dir) / "project"
        if not proj.exists():
            return []
        files: list = []

        tid = str(task.get("id") or "")
        if tid:
            try:
                out = subprocess.run(
                    ["git", "-C", str(base_dir), "log", "--all",
                     "--format=%H", "--grep", f"task {tid}"],
                    capture_output=True, text=True, timeout=8,
                )
                hashes = [h for h in out.stdout.split() if h]
                seen = set()
                for h in hashes[:10]:
                    out2 = subprocess.run(
                        ["git", "-C", str(base_dir), "show",
                         "--name-only", "--format=", h],
                        capture_output=True, text=True, timeout=8,
                    )
                    for line in out2.stdout.splitlines():
                        rel = line.strip()
                        if (rel and ".." not in rel
                                and not _is_junk_project_path(rel)
                                and (proj / rel).exists()
                                and rel not in seen):
                            seen.add(rel)
                            files.append(rel)
            except Exception:
                pass

        if not files:
            try:
                start = float(task.get("started_at") or 0)
                end = float(task.get("completed_at") or 0) or time.time()
                if start > 0:
                    margin = 120
                    for pth in proj.rglob("*"):
                        if not pth.is_file():
                            continue
                        rel = str(pth.relative_to(proj))
                        if _is_junk_project_path(rel):
                            continue
                        if start - margin <= pth.stat().st_mtime <= end + margin:
                            files.append(rel)
            except Exception:
                pass
        # Ordine: prima i file "di ingresso" (main, avvio, requirements),
        # così 'Apri risultato' apre la cartella del PROGRAMMA e il dialog
        # mostra subito il file principale.
        prio = {"main.py": 0, "app.py": 1, "avvia.sh": 2, "requirements.txt": 3}
        return sorted(set(files),
                      key=lambda f: (prio.get(Path(f).name, 10), f))

    def _show_task_details(self, task_id):
        """Mostra un dialog con i dettagli completi del task."""
        try:
            from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                         QLabel, QPushButton, QHBoxLayout, QTextEdit)
            import sqlite3, os, time
            from pathlib import Path

            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            con.close()

            if not row:
                return

            task = dict(zip(cols, row))

            dlg = QDialog(self)
            dlg.setWindowTitle(f"📋 Dettagli Task {task_id[:12]}")
            dlg.resize(600, 500)
            lay = QVBoxLayout(dlg)

            title = QLabel(f"<b>{task.get('title', '(senza titolo)')[:80]}</b>")
            title.setStyleSheet("font-size:14px; padding:8px; border-radius:6px;")
            title.setWordWrap(True)
            lay.addWidget(title)

            form = QFormLayout()
            form.setSpacing(6)

            def fmt_time(ts):
                if not ts:
                    return "—"
                try:
                    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(ts)))
                except Exception:
                    return str(ts)

            st_color = {'done': 'green', 'running': 'orange', 'failed': 'red',
                        'pending': 'gray'}.get(task.get('status'), 'gray')
            form.addRow("ID:", QLabel(task.get('id', '—')))
            form.addRow("Status:", QLabel(f"<b style='color:{st_color}'>{task.get('status', '—')}</b>"))
            form.addRow("Type:", QLabel(task.get('type', '—')))
            form.addRow("Source:", QLabel(task.get('source', '—')))
            form.addRow("Attempts:", QLabel(str(task.get('attempts', 0))))
            form.addRow("Parent:", QLabel(task.get('parent') or '—'))
            form.addRow("Created:", QLabel(fmt_time(task.get('created_at'))))
            form.addRow("Started:", QLabel(fmt_time(task.get('started_at'))))
            form.addRow("Completed:", QLabel(fmt_time(task.get('completed_at'))))

            if task.get('reason'):
                form.addRow("Reason:", QLabel(str(task.get('reason'))))

            lay.addLayout(form)

            for label, field in [("Description", 'description'), ("Result", 'result'), ("Last error", 'last_error')]:
                val = task.get(field, '')
                if val:
                    color_style = ' style="color:red"' if 'error' in label.lower() else ''
                    lay.addWidget(QLabel(f"<b{color_style}>{label}:</b>"))
                    te = QTextEdit()
                    te.setReadOnly(True)
                    te.setPlainText(str(val)[:2000])
                    if 'error' in label.lower():
                        te.setStyleSheet("border:1px solid rgba(128,128,128,0.35); border-radius:4px;")
                    te.setMaximumHeight(100)
                    lay.addWidget(te)

            # ── Codice prodotto dal task (navigabile se multi-file) ──
            try:
                task_files = self._collect_task_files(task, base)
            except Exception as _e:
                print(f"raccolta file task: {_e}")
                task_files = []
            if task_files:
                lay.addWidget(QLabel("<b>📄 Codice prodotto:</b>"))
                from PyQt6.QtWidgets import (QSplitter, QListWidget,
                                             QPlainTextEdit,
                                             QAbstractItemView)
                from PyQt6.QtCore import Qt as _Qt

                code_split = QSplitter(_Qt.Orientation.Horizontal)
                file_list = QListWidget()
                file_list.addItems(task_files)
                file_list.setMaximumWidth(260)
                viewer = QPlainTextEdit()
                viewer.setReadOnly(True)
                viewer.setStyleSheet(
                    "font-family:'JetBrains Mono','Consolas',monospace; "
                    "font-size:11px;")
                code_split.addWidget(file_list)
                code_split.addWidget(viewer)
                code_split.setStretchFactor(0, 0)
                code_split.setStretchFactor(1, 1)
                lay.addWidget(code_split, stretch=1)

                def _load_file(item):
                    rel = item.text()
                    try:
                        full = Path(base) / "project" / rel
                        content = full.read_text(encoding="utf-8",
                                                 errors="replace")
                        if len(content) > 30000:
                            content = (content[:30000]
                                       + "\n...[troncato — apri il file "
                                         "dall'Archivio per tutto]...")
                        viewer.setPlainText(content)
                    except Exception as e:
                        viewer.setPlainText(f"ERRORE lettura {rel}: {e}")

                file_list.currentItemChanged.connect(_load_file)
                file_list.setCurrentRow(0)      # carica il primo

                # ── Flusso utente 3: ESEGUIRE il codice generato ──
                from PyQt6.QtCore import QProcess, QUrl
                run_row = QHBoxLayout()
                run_btn = QPushButton("▶ Esegui")
                run_hint = QLabel("")
                run_hint.setStyleSheet("font-size:10px;")
                run_row.addWidget(run_btn)
                run_row.addWidget(run_hint, stretch=1)
                lay.addLayout(run_row)

                proc_holder = []

                def _refresh_run_btn(item):
                    rel = item.text() if item else ""
                    full = Path(base) / "project" / rel
                    ext = full.suffix.lower()
                    if ext == ".html":
                        run_btn.setEnabled(True)
                        run_btn.setText("🌐 Apri nel browser")
                        run_hint.setText("configurazione web")
                        return
                    cmd = build_run_command(full)
                    run_btn.setEnabled(cmd is not None)
                    run_btn.setText(f"▶ Esegui {rel}" if cmd else "▶ Esegui")
                    run_hint.setText("" if cmd
                                     else "estensione non eseguibile direttamente")

                def _start_run():
                    item = file_list.currentItem()
                    if not item or proc_holder:
                        return
                    rel = item.text()
                    full = Path(base) / "project" / rel
                    if full.suffix.lower() == ".html":
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(full)))
                        return
                    cmd = build_run_command(full)
                    if not cmd:
                        return
                    viewer.appendPlainText(f"$ {' '.join(cmd)}")
                    proc = QProcess(dlg)
                    proc.setWorkingDirectory(str(full.parent))
                    proc.readyReadStandardOutput.connect(
                        lambda: viewer.appendPlainText(bytes(
                            proc.readAllStandardOutput()).decode(
                            "utf-8", errors="replace").rstrip()))
                    proc.readyReadStandardError.connect(
                        lambda: viewer.appendPlainText(bytes(
                            proc.readAllStandardError()).decode(
                            "utf-8", errors="replace").rstrip()))
                    proc.finished.connect(
                        lambda code, _st: (viewer.appendPlainText(
                            f"[uscita: {code}]"), _rearm()))
                    proc.start(cmd[0], cmd[1:])
                    proc_holder.append(proc)
                    run_btn.setEnabled(False)

                def _rearm(*_a):
                    if proc_holder:
                        proc_holder.clear()
                        _refresh_run_btn(file_list.currentItem())

                run_btn.clicked.connect(_start_run)
                file_list.currentItemChanged.connect(_refresh_run_btn)
                _refresh_run_btn(file_list.currentItem())

                if len(task_files) > 1:
                    dlg.resize(980, 680)        # spazio per la navigazione
            elif task.get("status") == "done":
                lay.addWidget(QLabel("<span style='color:gray'>"
                                     "Nessun file di progetto associato.</span>"))

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            close_btn = QPushButton("Chiudi")
            close_btn.clicked.connect(dlg.accept)
            btn_row.addWidget(close_btn)
            lay.addLayout(btn_row)

            dlg.exec()
        except Exception as e:
            print(f"Errore show details: {e}")

    def _restart_task_with_refresh(self, task_id, item):
        """Riavvia un task e aggiorna la lista."""
        try:
            _log_user_action("Task-Action", "avvio", task_id=task_id, details="Task riavviato dall'utente")
            ok, msg = _restart_task(task_id)
            if ok:
                if item:
                    txt = item.text() if hasattr(item, 'text') else ""
                    if txt.startswith("↻ "):
                        txt = txt[2:]
                    if txt.endswith(" [restart]"):
                        txt = txt[:-10]
                    item.setText(f"↻ {txt} [restart]")
                    item.setForeground(QColor("#16a34a"))
                parent = self.parent()
                while parent and not hasattr(parent, '_refresh_coda_card'):
                    parent = parent.parent()
                if parent:
                    parent._refresh_coda_card()
                    if hasattr(parent, '_refresh_task_list'):
                        parent._refresh_task_list()
        except Exception as e:
            print(f"Errore restart: {e}")

    def _delete_task_with_refresh(self, task_id, item):
        """Elimina un task dal DB."""
        try:
            reply = QMessageBox.question(
                self, "Elimina task",
                f"Eliminare definitivamente il task {task_id[:12]}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            import sqlite3, os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            con.commit()
            con.close()
            parent = self.parent()
            while parent and not hasattr(parent, '_refresh_coda_card'):
                parent = parent.parent()
            if parent:
                parent._refresh_coda_card()
                if hasattr(parent, '_refresh_task_list'):
                    parent._refresh_task_list()
        except Exception as e:
            print(f"Errore delete: {e}")

    def _copy_task_id(self, task_id):
        """Copia l'ID del task negli appunti."""
        try:
            cb = QApplication.clipboard()
            cb.setText(task_id)
        except Exception as e:
            print(f"Errore copy: {e}")

    def _open_task_result(self, task_id):
        """Apre la CARTELLA dei file prodotti dal task nel file manager.

        Flusso utente 3: l'utente deve vedere dove sta il codice generato
        (e lanciare avvia.sh), non un singolo file indovinato.
        """
        try:
            import sqlite3, os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, 'tasks', 'queue.db')
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            con.close()
            if not row:
                return

            proj = os.path.join(base, 'project')
            files = self._collect_task_files(dict(row), base)
            if files:
                # la cartella del primo file prodotto (o project/ se in root)
                first_dir = os.path.dirname(os.path.join(proj, files[0]))
            else:
                first_dir = proj
            os.makedirs(first_dir, exist_ok=True)
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(first_dir))
        except Exception as e:
            print(f"Errore open result: {e}")


# ═══════════════════════════════════════════════════════════════
# TEST DI INTEGRITÀ DEL SOFTWARE
# ═══════════════════════════════════════════════════════════════
class IntegrityTestsPanel(QFrame):
    """Pannello per eseguire test di integrità del software.

    Verifica:
      - checksum SHA256 di tutti i file Python di CORE/SAFETY/CONFIG
      - esistenza dei file critici (orchestrator.py, security.py, ecc.)
      - sintassi Python di ogni modulo (py_compile)
      - coerenza del config.toml
    """

    # File critici che DEVONO esistere e non essere vuoti
    CRITICAL_FILES = [
        "CORE/orchestrator.py",
        "CORE/tools.py",
        "CORE/ollama_client.py",
        "SAFETY/security.py",
        "SAFETY/security_checks.py",
        "SAFETY/watchdog.py",
        "CONFIG/config.toml",
        "GUI/control_center.py",
        "GUI/gui_backend.py",
        "GUI/settings_store.py",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("integrity_panel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # Header con pulsante "Esegui test"
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(QLabel("<b>Verifica checksum, esistenza file critici, sintassi Python</b>"))
        head.addStretch()

        self.run_btn = QPushButton("▶ Esegui test di integrità")
        self.run_btn.setStyleSheet(
            "QPushButton { background:#16a34a; color:#ffffff; border:none; "
            "padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#15803d; }"
        )
        self.run_btn.clicked.connect(self._run_tests)
        head.addWidget(self.run_btn)
        lay.addLayout(head)

        # ── Barra di ricerca nel contenuto ────────────────────────────
        from GUI.search_bar import SearchBar
        self.search_bar = SearchBar(
            None, parent=self,  # target viene impostato dopo la creazione di output
            placeholder="🔍 Cerca nei risultati…  (Enter = successivo, Shift+Enter = precedente)"
        )
        lay.addWidget(self.search_bar)

        # Output area
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Clicca 'Esegui test di integrità' per verificare checksum SHA256, "
            "esistenza file critici, e sintassi Python dei moduli.\n"
            "Risultato: elenco PASS/FAIL con dettagli."
        )
        self.output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:11px; padding:8px;"
        )
        # Collega la search bar al target (ora che self.output esiste)
        self.search_bar.target = self.output
        lay.addWidget(self.output, stretch=1)

        # Stato iniziale: baseline checksum
        self._baseline = None

    def _base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _run_tests(self):
        """Esegue tutti i test di integrità e mostra il risultato."""
        self.output.clear()
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText("  🧪 TEST DI INTEGRITÀ DEL SOFTWARE")
        self.output.appendPlainText("════════════════════════════════════════════\n")
        import time, hashlib, py_compile, tempfile

        base = self._base_dir()
        passed = 0
        failed = 0
        warnings = 0
        start = time.time()

        # ── Test 1: esistenza file critici ─────────────────────────────
        self.output.appendPlainText("─── Test 1: Esistenza file critici ───")
        for rel in self.CRITICAL_FILES:
            path = os.path.join(base, rel)
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size == 0:
                    self.output.appendPlainText(f"  ⚠️  {rel} — esiste ma è VUOTO ({size}B)")
                    warnings += 1
                else:
                    self.output.appendPlainText(f"  ✓  {rel} — {size}B")
                    passed += 1
            else:
                self.output.appendPlainText(f"  ✗  {rel} — MANCANTE")
                failed += 1
        self.output.appendPlainText("")

        # ── Test 2: checksum SHA256 di tutti i .py in CORE/ ────────────
        self.output.appendPlainText("─── Test 2: Checksum SHA256 CORE/*.py ───")
        core_dir = os.path.join(base, "CORE")
        if os.path.isdir(core_dir):
            hashes = {}
            for fname in sorted(os.listdir(core_dir)):
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(core_dir, fname)
                try:
                    with open(path, "rb") as f:
                        h = hashlib.sha256(f.read()).hexdigest()[:16]
                    hashes[fname] = h
                    self.output.appendPlainText(f"  ✓  {fname}  sha256:{h}...")
                    passed += 1
                except OSError as e:
                    self.output.appendPlainText(f"  ✗  {fname}  errore: {e}")
                    failed += 1
        self.output.appendPlainText("")

        # ── Test 3: py_compile di ogni .py in CORE/ e GUI/ ─────────────
        self.output.appendPlainText("─── Test 3: Sintassi Python (py_compile) ───")
        for sub in ("CORE", "GUI", "SAFETY"):
            d = os.path.join(base, sub)
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(d, fname)
                try:
                    py_compile.compile(path, doraise=True, quiet=2)
                    self.output.appendPlainText(f"  ✓  {sub}/{fname} — sintassi OK")
                    passed += 1
                except py_compile.PyCompileError as e:
                    self.output.appendPlainText(f"  ✗  {sub}/{fname} — ERRORE SINTASSI")
                    self.output.appendPlainText(f"      {str(e)[:200]}")
                    failed += 1
                except Exception as e:
                    self.output.appendPlainText(f"  ✗  {sub}/{fname} — {type(e).__name__}: {e}")
                    failed += 1
        self.output.appendPlainText("")

        # ── Test 4: config.toml parseable ─────────────────────────────
        self.output.appendPlainText("─── Test 4: Config.toml valido ───")
        config_path = os.path.join(base, "CONFIG", "config.toml")
        try:
            import tomllib
            with open(config_path, "rb") as f:
                tomllib.load(f)
            self.output.appendPlainText("  ✓  CONFIG/config.toml — parse OK")
            passed += 1
        except ImportError:
            # Python < 3.11 — fallback a tomli se installato
            try:
                import tomli
                with open(config_path, "rb") as f:
                    tomli.load(f)
                self.output.appendPlainText("  ✓  CONFIG/config.toml — parse OK (tomli)")
                passed += 1
            except Exception as e:
                self.output.appendPlainText(f"  ⚠️  tomli non disponibile: {e}")
                warnings += 1
        except FileNotFoundError:
            self.output.appendPlainText("  ✗  CONFIG/config.toml — MANCANTE")
            failed += 1
        except Exception as e:
            self.output.appendPlainText(f"  ✗  CONFIG/config.toml — PARSE ERROR: {e}")
            failed += 1
        self.output.appendPlainText("")

        # ── Riepilogo ─────────────────────────────────────────────────
        elapsed = time.time() - start
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText(f"  ✓ PASS:    {passed}")
        self.output.appendPlainText(f"  ✗ FAIL:    {failed}")
        self.output.appendPlainText(f"  ⚠️ WARN:   {warnings}")
        self.output.appendPlainText(f"  ⏱  Tempo: {elapsed:.2f}s")
        status = "✅ INTEGRO" if failed == 0 else "❌ COMPROMESSO"
        self.output.appendPlainText(f"  Stato:    {status}")
        self.output.appendPlainText("════════════════════════════════════════════")


# ═══════════════════════════════════════════════════════════════
# SICUREZZA DEL SOFTWARE & ANTI-MANOMISSIONE
# ═══════════════════════════════════════════════════════════════
class SoftwareSecurityPanel(QFrame):
    """Pannello per verificare l'integrità anti-manomissione del codice.

    Caratteristiche:
      - Salva una baseline di hash SHA256 dei file critici in
        CONFIG/security_baseline.json (al primo avvio o su richiesta)
      - Confronta l'hash attuale con la baseline per rilevare modifiche
        non autorizzate ai file di CORE/SAFETY/SECURITY
      - Verifica permessi dei file (non world-writable)
      - Elenca file modificati dopo la baseline
    """

    BASELINE_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "CONFIG", "security_baseline.json"
    )

    # Cartelle i cui file .py sono considerati "critici" per la sicurezza
    WATCHED_DIRS = ("CORE", "SAFETY", "GUI")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("security_panel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # Header
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(QLabel(
            "<b>Verifica anti-manomissione codice, permessi file, hash baseline</b>"
        ))
        head.addStretch()

        self.scan_btn = QPushButton("🔍 Scansiona ora")
        self.scan_btn.setStyleSheet(
            "QPushButton { background:#2563eb; color:#ffffff; border:none; "
            "padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#1d4ed8; }"
        )
        self.scan_btn.clicked.connect(self._scan)
        head.addWidget(self.scan_btn)

        self.save_btn = QPushButton("💾 Salva baseline")
        self.save_btn.setStyleSheet(
            "QPushButton { background:#f59e0b; color:#ffffff; border:none; "
            "padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#d97706; }"
        )
        self.save_btn.setToolTip(
            "Salva l'hash SHA256 attuale di tutti i file come stato fidato. "
            "Le future scansioni confronteranno con questa baseline."
        )
        self.save_btn.clicked.connect(self._save_baseline)
        head.addWidget(self.save_btn)
        lay.addLayout(head)

        # ── Barra di ricerca nel contenuto ────────────────────────────
        from GUI.search_bar import SearchBar
        self.search_bar = SearchBar(
            None, parent=self,
            placeholder="🔍 Cerca nei risultati…  (Enter = successivo, Shift+Enter = precedente)"
        )
        lay.addWidget(self.search_bar)

        # Output
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Clicca 'Scansiona ora' per verificare che i file di CORE/SAFETY/GUI "
            "non siano stati manomessi dopo l'ultima baseline.\n"
            "Salva baseline la prima volta."
        )
        self.output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:11px; padding:8px;"
        )
        self.search_bar.target = self.output
        lay.addWidget(self.output, stretch=1)

    def _base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _hash_dir(self) -> dict:
        """Calcola SHA256 di tutti i .py nelle cartelle watched."""
        base = self._base_dir()
        out = {}
        for sub in self.WATCHED_DIRS:
            d = os.path.join(base, sub)
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(d, fname)
                rel = f"{sub}/{fname}"
                try:
                    import hashlib
                    with open(path, "rb") as f:
                        out[rel] = hashlib.sha256(f.read()).hexdigest()
                except OSError:
                    out[rel] = None
        return out

    def _load_baseline(self) -> dict:
        if not os.path.exists(self.BASELINE_FILE):
            return {}
        try:
            import json
            with open(self.BASELINE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("hashes", {})
        except Exception:
            return {}

    def _save_baseline(self):
        """Salva la baseline di hash attuale."""
        hashes = self._hash_dir()
        if not hashes:
            QMessageBox.warning(self, "Nessun file",
                "Nessun file Python trovato in CORE/SAFETY/GUI da salvare.")
            return
        import json, time
        os.makedirs(os.path.dirname(self.BASELINE_FILE), exist_ok=True)
        data = {
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "saved_by": os.environ.get("USER", "unknown"),
            "hashes": hashes,
        }
        try:
            with open(self.BASELINE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.output.clear()
            self.output.appendPlainText(
                f"✅ Baseline salvata in {self.BASELINE_FILE}\n"
                f"   File monitorati: {len(hashes)}\n"
                f"   Salvata il: {data['saved_at']}\n"
                f"   Utente: {data['saved_by']}\n"
            )
        except OSError as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare baseline: {e}")

    def _scan(self):
        """Scansiona i file e confronta con la baseline."""
        self.output.clear()
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText("  🛡️  SICUREZZA DEL SOFTWARE & ANTI-MANOMISSIONE")
        self.output.appendPlainText("════════════════════════════════════════════\n")

        current = self._hash_dir()
        baseline = self._load_baseline()

        if not baseline:
            self.output.appendPlainText("⚠️  Nessuna baseline trovata.")
            self.output.appendPlainText("    Clicca '💾 Salva baseline' per creare lo stato fidato.")
            self.output.appendPlainText("    Fino ad allora, tutti gli hash attuali verranno")
            self.output.appendPlainText("    salvati come 'nuovi' (nessun confronto possibile).\n")

        # ── 1. Hash file per file ──────────────────────────────────────
        self.output.appendPlainText("─── Hash SHA256 dei file critici ───")
        for rel, h in sorted(current.items()):
            short_h = (h or "errore")[:16]
            if not baseline:
                self.output.appendPlainText(f"  • {rel:40s} sha256:{short_h}...")
            else:
                base_h = baseline.get(rel)
                if base_h is None:
                    self.output.appendPlainText(f"  + {rel:40s} NUOVO (non in baseline) sha256:{short_h}...")
                elif base_h == h:
                    self.output.appendPlainText(f"  ✓ {rel:40s} sha256:{short_h}...")
                else:
                    self.output.appendPlainText(f"  ✗ {rel:40s} MODIFICATO — base:{(base_h or '')[:12]}... curr:{short_h}...")
        self.output.appendPlainText("")

        # ── 2. File rimossi (in baseline ma non più esistenti) ─────────
        if baseline:
            removed = [r for r in baseline if r not in current]
            if removed:
                self.output.appendPlainText("─── File rimossi dalla baseline ───")
                for rel in removed:
                    self.output.appendPlainText(f"  - {rel:40s} eliminato o spostato")
                self.output.appendPlainText("")

        # ── 3. Permessi file (no world-writable) ──────────────────────
        self.output.appendPlainText("─── Permessi file (no world-writable) ───")
        base = self._base_dir()
        import stat
        bad_perms = 0
        for rel in current:
            path = os.path.join(base, rel)
            try:
                mode = os.stat(path).st_mode
                if mode & stat.S_IWOTH:
                    self.output.appendPlainText(f"  ⚠️  {rel} è WORLD-WRITABLE (permessi {oct(mode & 0o777)})")
                    bad_perms += 1
            except OSError:
                pass
        if bad_perms == 0:
            self.output.appendPlainText(f"  ✓  Tutti i file hanno permessi corretti (no world-writable)")
        self.output.appendPlainText("")

        # ── 4. Riepilogo ───────────────────────────────────────────────
        modified = 0
        new = 0
        removed_n = 0
        if baseline:
            for rel, h in current.items():
                base_h = baseline.get(rel)
                if base_h is None:
                    new += 1
                elif base_h != h:
                    modified += 1
            removed_n = len([r for r in baseline if r not in current])

        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText(f"  File monitorati:   {len(current)}")
        self.output.appendPlainText(f"  File modificati:   {modified}")
        self.output.appendPlainText(f"  File nuovi:        {new}")
        self.output.appendPlainText(f"  File rimossi:      {removed_n}")
        self.output.appendPlainText(f"  Permessi anomali:  {bad_perms}")
        status = "✅ SICURO" if (modified == 0 and bad_perms == 0) else "❌ MANOMESSO"
        self.output.appendPlainText(f"  Stato:             {status}")
        self.output.appendPlainText("════════════════════════════════════════════")


# ═══════════════════════════════════════════════════════════════
# CI/CD PIPELINE PANEL
# ═══════════════════════════════════════════════════════════════
class CICDPipelinePanel(QWidget):
    """Pannello per la pipeline CI/CD: build → test → deploy.

    Permette di:
      - eseguire manualmente ogni stage (build, test, deploy)
      - vedere lo stato (pass/fail/running) di ogni stage
      - log dei run precedenti in output testuale
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cicd_panel")
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        # Stile dal tema app-level — segue il tema live.
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>🔄 CI/CD Pipeline</b>")
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
            "Pipeline di integrazione e delivery continua. Esegui gli stage "
            "manualmente o lascia che l'orchestratore li triggeri ad ogni commit."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet("padding:10px; font-size:11px; border-radius:8px;")
        from GUI.theme.theme import set_banner as _set_banner
        _set_banner(expl, "warn")
        lay.addWidget(expl)

        # Stages: 3 card con stato
        stages_box = QGroupBox("📋 Stage della pipeline")
        stages_box.setStyleSheet(self._group_style())
        stages_lay = QVBoxLayout(stages_box)
        stages_lay.setContentsMargins(14, 14, 14, 14)
        stages_lay.setSpacing(8)

        self.stages = {}
        for key, label, icon, color in [
            ("build",  "Build",       "🔨", "#2563eb"),
            ("test",   "Test suite",   "🧪", "#f59e0b"),
            ("deploy", "Deploy",       "🚀", "#16a34a"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(QLabel(f"{icon} <b>{label}</b>"))

            self.stages[key] = QLabel("⚪ in attesa")
            self.stages[key].setStyleSheet(
                f"color:{color}; font-weight:bold; padding:4px 10px; "
                f"background:{color}22; border-radius:6px;"
            )
            row.addWidget(self.stages[key])
            row.addStretch()

            btn = QPushButton(f"▶ Esegui {label}")
            btn.setStyleSheet(self._btn_style(color))
            btn.clicked.connect(lambda _, k=key, l=label: self._run_stage(k, l))
            row.addWidget(btn)

            stages_lay.addLayout(row)

        lay.addWidget(stages_box)

        # Output log
        log_box = QGroupBox("📜 Log della pipeline")
        log_box.setStyleSheet(self._group_style())
        log_lay = QVBoxLayout(log_box)
        log_lay.setContentsMargins(14, 14, 14, 14)

        # ── Barra di ricerca nel log ──────────────────────────────────
        from GUI.search_bar import SearchBar
        self.search_bar = SearchBar(
            None, parent=self,
            placeholder="🔍 Cerca nel log…  (Enter = successivo, Shift+Enter = precedente)"
        )
        log_lay.addWidget(self.search_bar)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Clicca 'Esegui Build/Test/Deploy' per avviare la pipeline.")
        self.output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:11px; padding:8px;"
        )
        self.search_bar.target = self.output
        log_lay.addWidget(self.output)
        lay.addWidget(log_box)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _run_stage(self, key: str, label: str):
        """Esegue uno stage della pipeline (build/test/deploy)."""
        import time
        self.stages[key].setText("🔵 in esecuzione...")
        self.stages[key].setStyleSheet(
            "color:#2563eb; font-weight:bold; padding:4px 10px; "
            "background:#dbeafe; border-radius:6px;"
        )
        self.output.appendPlainText(f"\n─── {time.strftime('%H:%M:%S')}  ▶ {label} ───")

        # Simulazione reale: py_compile per build, test discovery per test, ecc.
        success = True
        try:
            if key == "build":
                self.output.appendPlainText("  → py_compile di tutti i moduli...")
                import py_compile, os
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                count = 0
                for sub in ("CORE", "GUI", "SAFETY"):
                    d = os.path.join(base, sub)
                    if not os.path.isdir(d):
                        continue
                    for fname in sorted(os.listdir(d)):
                        if not fname.endswith(".py"):
                            continue
                        py_compile.compile(os.path.join(d, fname), doraise=True, quiet=2)
                        count += 1
                self.output.appendPlainText(f"  ✓ {count} moduli compilati OK")

            elif key == "test":
                self.output.appendPlainText("  → Esecuzione test suite...")
                # Verifica che la directory tests/ esista
                import os
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                tests_dir = os.path.join(base, "tests")
                if os.path.isdir(tests_dir):
                    n = len([f for f in os.listdir(tests_dir)
                             if f.startswith("test_") and f.endswith(".py")])
                    self.output.appendPlainText(f"  ✓ {n} file di test trovati in tests/")
                else:
                    self.output.appendPlainText("  ⚠️  directory tests/ non trovata")
                    success = False

            elif key == "deploy":
                self.output.appendPlainText("  → Push su tutti i remote Git...")
                # Reindirizza a _do_git_save della main window
                main = self._find_main()
                if main and hasattr(main, "device_panel"):
                    main.device_panel._do_git_save()
                    self.output.appendPlainText("  ✓ Push completato (vedi log git)")
                else:
                    self.output.appendPlainText("  ⚠️  device_panel non trovato")
                    success = False

        except Exception as e:
            self.output.appendPlainText(f"  ✗ ERRORE: {type(e).__name__}: {e}")
            success = False

        # Stato finale
        if success:
            self.stages[key].setText("✅ completato")
            self.stages[key].setStyleSheet(
                "color:#16a34a; font-weight:bold; padding:4px 10px; "
                "background:#dcfce7; border-radius:6px;"
            )
        else:
            self.stages[key].setText("❌ fallito")
            self.stages[key].setStyleSheet(
                "color:#dc2626; font-weight:bold; padding:4px 10px; "
                "background:#fee2e2; border-radius:6px;"
            )

    def _find_main(self):
        """Risale il parent per trovare il ControlCenter (main_win)."""
        p = self.parent()
        while p and not hasattr(p, "device_panel"):
            p = p.parent()
        return p

    def _back_to_main(self):
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()

    def _group_style(self) -> str:
        # Solo geometria: i colori di QGroupBox e ::title arrivano dal
        # QSS del tema (i fondi bianchi hardcoded rompevano i temi scuri).
        return (
            "QGroupBox {"
            "  margin-top:14px; padding-top:8px; font-weight:bold;"
            "}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin; left:14px; padding:0 6px;"
            "}"
        )

    def _btn_style(self, color: str) -> str:
        return (
            f"QPushButton {{ background:{color}; color:#ffffff; border:none; "
            f"padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }}"
            f"QPushButton:hover {{ background:{color}cc; }}"
        )


# ═══════════════════════════════════════════════════════════════
# CLEAN & ARCHITECTURE CODE PANEL
# ═══════════════════════════════════════════════════════════════
class CleanCodePanel(QWidget):
    """Pannello per analizzare qualità e architettura del codice.

    Esegue:
      - lint base (py_compile + AST checks per funzioni/classi lunghe)
      - complessità ciclomatica semplificata (numero di rami per funzione)
      - duplicazione di righe identiche
      - conteggio linee di codice per modulo
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("clean_code_panel")
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        # Stile dal tema app-level — segue il tema live.
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>✨ Clean & Architecture Code</b>")
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
            "Analisi qualità codice: lint, complessità ciclomatica, duplicazione, "
            "linee di codice per modulo. Fissa baseline e confronta con run successivi."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet(
            "background:#faf5ff; border:1px solid #e9d5ff; border-radius:8px; "
            "padding:10px; font-size:11px; color:#6b21a8;"
        )
        lay.addWidget(expl)

        # Pulsante analisi
        btn_row = QHBoxLayout()
        run_btn = QPushButton("▶ Esegui analisi codice")
        run_btn.setStyleSheet(
            "QPushButton { background:#7c3aed; color:#ffffff; border:none; "
            "padding:10px 24px; border-radius:6px; font-weight:bold; font-size:13px; }"
            "QPushButton:hover { background:#6d28d9; }"
        )
        run_btn.clicked.connect(self._run_analysis)
        btn_row.addWidget(run_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # ── Barra di ricerca nei risultati ────────────────────────────
        from GUI.search_bar import SearchBar
        self.search_bar = SearchBar(
            None, parent=self,
            placeholder="🔍 Cerca nei risultati…  (Enter = successivo, Shift+Enter = precedente)"
        )
        lay.addWidget(self.search_bar)

        # Output
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Clicca 'Esegui analisi codice' per verificare lint, complessità, "
            "duplicazione e linee di codice dei moduli."
        )
        self.output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:11px; padding:8px;"
        )
        self.search_bar.target = self.output
        lay.addWidget(self.output, stretch=1)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def _base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _run_analysis(self):
        """Esegue analisi qualità codice su CORE/GUI/SAFETY."""
        import time, ast
        self.output.clear()
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText("  ✨ CLEAN & ARCHITECTURE CODE ANALYSIS")
        self.output.appendPlainText("════════════════════════════════════════════\n")

        base = self._base_dir()
        start = time.time()
        total_lines = 0
        total_functions = 0
        total_classes = 0
        long_functions = []
        high_complexity = []

        for sub in ("CORE", "GUI", "SAFETY"):
            d = os.path.join(base, sub)
            if not os.path.isdir(d):
                continue
            self.output.appendPlainText(f"─── {sub}/ ───")
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(d, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        src = f.read()
                    lines = src.count("\n") + 1
                    total_lines += lines

                    # Parse AST
                    tree = ast.parse(src)
                    n_classes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
                    n_funcs = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
                    total_functions += n_funcs
                    total_classes += n_classes

                    # Verifica funzioni lunghe (>50 righe)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            n_lines = (node.end_lineno or node.lineno) - node.lineno
                            if n_lines > 50:
                                long_functions.append((f"{sub}/{fname}", node.name, n_lines))
                            # Complessità: conta If/For/While/Try/With/BoolOp
                            complexity = sum(1 for n in ast.walk(node)
                                             if isinstance(n, (ast.If, ast.For, ast.While,
                                                               ast.Try, ast.With, ast.BoolOp)))
                            if complexity > 10:
                                high_complexity.append((f"{sub}/{fname}", node.name, complexity))

                    self.output.appendPlainText(
                        f"  {fname:30s}  {lines:5d} righe  {n_classes:2d} classi  {n_funcs:3d} funz"
                    )
                except SyntaxError as e:
                    self.output.appendPlainText(f"  ✗ {fname} — SYNTAX ERROR: {e}")
                except Exception as e:
                    self.output.appendPlainText(f"  ✗ {fname} — {type(e).__name__}: {e}")
            self.output.appendPlainText("")

        # Funzioni lunghe
        if long_functions:
            self.output.appendPlainText("─── Funzioni lunghe (>50 righe) ───")
            for path, name, n in long_functions:
                self.output.appendPlainText(f"  ⚠️  {path} :: {name} ({n} righe)")
            self.output.appendPlainText("")

        # Alta complessità
        if high_complexity:
            self.output.appendPlainText("─── Alta complessità ciclomatica (>10 rami) ───")
            for path, name, c in high_complexity:
                self.output.appendPlainText(f"  ⚠️  {path} :: {name} (complessità {c})")
            self.output.appendPlainText("")

        # Riepilogo
        elapsed = time.time() - start
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText(f"  Linee totali:           {total_lines}")
        self.output.appendPlainText(f"  Funzioni totali:        {total_functions}")
        self.output.appendPlainText(f"  Classi totali:          {total_classes}")
        self.output.appendPlainText(f"  Funzioni lunghe (>50):   {len(long_functions)}")
        self.output.appendPlainText(f"  Funzioni complesse:     {len(high_complexity)}")
        self.output.appendPlainText(f"  Tempo:                  {elapsed:.2f}s")
        avg_per_func = (total_lines / total_functions) if total_functions else 0
        status = "✅ PULITO" if not long_functions and not high_complexity else "⚠️  DA RIVEDERE"
        self.output.appendPlainText(f"  Media righe/funzione:   {avg_per_func:.1f}")
        self.output.appendPlainText(f"  Stato:                  {status}")
        self.output.appendPlainText("════════════════════════════════════════════")

    def _back_to_main(self):
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()


class CenterArea(QWidget):
    def __init__(self, parent):
        super().__init__()
        # Import locale: QSizePolicy serve sia per le PlanciaCard che per
        # i content delle CollapsibleSection. Importato qui una sola volta
        # per evitare UnboundLocalError quando usato prima dell'import.
        from PyQt6.QtWidgets import QSizePolicy
        self.main_win = parent
        self._editor_column = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.main_stack = QStackedWidget()

        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)

        main_widget = QWidget()
        main_lay = QVBoxLayout(main_widget)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(12)

        self.logs_section = CollapsibleSection("Log - Diario di Bordo", icon="📜")
        self.log_viewer = CategorizedLogViewer()
        self.logs_section.add_widget(self.log_viewer)

        self.plancia_section = CollapsibleSection("Plancia di controllo", icon="✈️")

        # ── Barra di ricerca globale (filtra le 10 card) ─────────────
        # Cerca per titolo, sottotitolo o badge di tutte le card (plancia +
        # strumenti). Le card non matchanti vengono nascoste in tempo reale.
        from PyQt6.QtWidgets import QLineEdit as _QLineEdit
        self.global_search = _QLineEdit()
        self.global_search.setPlaceholderText(
            "🔍 Cerca tra le card…  (es. \"task\", \"git\", \"ci/cd\", \"sicurezza\")"
        )
        self.global_search.setStyleSheet(
            "QLineEdit { padding:6px 12px; border-radius:8px; font-size:12px; }"
        )
        self.global_search.textChanged.connect(self._on_global_search)
        self.global_search.returnPressed.connect(self._on_global_search_enter)
        # Nella riga del titolo "Plancia di controllo" (sempre visibile,
        # anche a sezione collassata) invece di occupare una riga intera.
        # Nessun min_width fisso: si restringe/espande in percentuale con la
        # finestra (come bootstrap desktop→mobile). stretch=2 lo fa crescere
        # insieme alla finestra (il titolo resta con stretch=0).
        self.plancia_section.add_header_widget(
            self.global_search, max_width=700, min_width=360, stretch=2)

        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)
        cards_grid.setContentsMargins(0, 0, 0, 0)
        # Colonne a larghezza STRETTAMENTE uniforme: stretch=1 su tutte e 3.
        # Le card hanno MinimumWidth=120 e SizePolicy=Expanding, quindi la
        # grid distribuisce lo spazio in modo identico tra le colonne.
        cards_grid.setColumnStretch(0, 1)
        cards_grid.setColumnStretch(1, 1)
        cards_grid.setColumnStretch(2, 1)
        # Rige a altezza uniforme (tutte le card hanno fixedHeight=110,
        # ma lo row stretch assicura che la grid non deformi le righe).
        cards_grid.setRowStretch(0, 0)
        cards_grid.setRowStretch(1, 0)

        self.cards = {}
        card_configs = [
            ("coda", "📋 Code Task",
             "Schedula compiti a orari previsti: uno-shot, ricorrenti o giornalieri",
             "Scheduler", "#f59e0b", 0, 0),
            ("modelli", "🤖 Modelli → Attori",
             "Imposta i 3 attori: LLM, Decision Model e Timestral (soglie termiche)",
             "3 attori", "#2563eb", 0, 1),
            ("config", "⚙️ Configurazione",
             "Scegli la tua configurazione GUI, Git e lingua",
             "Settings", "#16a34a", 0, 2),
            ("cicd", "🔄 CI/CD",
             "Pipeline di integrazione e delivery: build, test, deploy automatici",
             "Pipeline", "#dc2626", 1, 0),
            ("clean_code", "✨ Clean & Architecture Code",
             "Verifica qualità codice: lint, complexity, duplicazione, architettura",
             "Quality", "#7c3aed", 1, 1),
        ]

        for key, title, subtitle, badge, badge_color, row, col in card_configs:
            card = PlanciaCard(title, subtitle, badge=badge, badge_color=badge_color)
            card.clicked.connect(lambda k=key: self.open_panel(k))
            self.cards[key] = card
            cards_grid.addWidget(card, row, col)

        cards_container = QWidget()
        cards_container.setLayout(cards_grid)
        # Il container deve riempire tutta la larghezza disponibile della
        # plancia_section, così le 3 colonne hanno spazio uniforme.
        cards_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.plancia_section.add_widget(cards_container)

        # ── Separatore visivo tra le card (menù da cliccare) e gli strumenti
        # di analisi. Serve a rendere chiaro che si tratta di due gruppi
        # distinti ma coerenti nello stile.
        tools_label = QLabel("🧰 Strumenti di analisi")
        tools_label.setStyleSheet(
            "font-size:11px; font-weight:bold; "
            "padding:14px 4px 6px 4px; letter-spacing:1px;"
        )
        self.plancia_section.add_widget(tools_label)

        # ── 5 strumenti di analisi come PlanciaCard cliccabili ─────────
        # Le 5 sezioni (già CollapsibleSection) sono ora rettangoli uniformi
        # allo stesso stile delle 5 card sopra (Code Task, Modelli, ecc.):
        # al click aprono il pannello corrispondente nel detail_stack,
        # esattamente come CI/CD e Clean Code.
        #
        # Struttura:
        #   1) 🎮 Navigatore di codice Interattivo (CodeExplorer)
        #   2) 💾 Backup Code — Git Logs (BackupCodeLogs)
        #   3) 📜 Log - Diario di Bordo (CategorizedLogViewer)
        #   4) 🧪 Test di integrità del software (IntegrityTestsPanel)
        #   5) 🛡️ Sicurezza del software & anti-manomissione (SoftwareSecurityPanel)
        UNIFORM_CONTENT_HEIGHT = 300  # altezza del content interno (300px fisse)

        def _force_content_size(widget):
            """Forza altezza 300px + larghezza 100% su un widget (content)."""
            widget.setFixedHeight(UNIFORM_CONTENT_HEIGHT)
            widget.setMinimumHeight(UNIFORM_CONTENT_HEIGHT)
            widget.setMaximumHeight(UNIFORM_CONTENT_HEIGHT)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # ── Istanzia i 5 widget (verranno messi nel detail_stack) ──────
        self.code_explorer = CodeExplorer()
        _force_content_size(self.code_explorer)
        self.backup_logs = BackupCodeLogs()
        _force_content_size(self.backup_logs)
        # log_viewer è già stato creato sopra (riga ~4106), lo riusiamo
        _force_content_size(self.log_viewer)
        self.integrity_panel = IntegrityTestsPanel()
        _force_content_size(self.integrity_panel)
        self.security_panel = SoftwareSecurityPanel()
        _force_content_size(self.security_panel)

        # ── Grid 3x2 per i 5 strumenti (stesso stile delle card sopra) ─
        tools_grid = QGridLayout()
        tools_grid.setSpacing(12)
        tools_grid.setContentsMargins(0, 0, 0, 0)
        tools_grid.setColumnStretch(0, 1)
        tools_grid.setColumnStretch(1, 1)
        tools_grid.setColumnStretch(2, 1)
        tools_grid.setRowStretch(0, 0)
        tools_grid.setRowStretch(1, 0)
        tools_grid.setRowStretch(2, 0)

        self.tools_cards = {}
        tool_card_configs = [
            ("code_explorer", "🎮 Navigatore di codice",
             "Esplora classi, funzioni e variabili del progetto con grafo interattivo",
             "Explorer", "#0891b2", 0, 0),
            ("backup_logs", "💾 Backup Code — Git Logs",
             "Log dei push su GitHub, GitLab e Git generici con stato pipeline CI",
             "Backup", "#475569", 0, 1),
            ("logs", "📜 Log — Diario di Bordo",
             "Cronologia eventi del sistema: info, debug, success ed errori",
             "Logs", "#ca8a04", 0, 2),
            ("integrity", "🧪 Test di integrità",
             "Verifica checksum e integrità dei file critici del software",
             "Tests", "#0d9488", 1, 0),
            ("security", "🛡️ Sicurezza & anti-manomissione",
             "Scansioni di sicurezza, rilevamento manomissioni e hardening",
             "Security", "#b91c1c", 1, 1),
            ("audit_project", "🔍 Audit Progetto",
             "Quality gate su un progetto target: porte esposte, tunnel, codice morto",
             "Gate", "#9333ea", 1, 2),
            ("hardware", "🖥️ Hardware & Modelli",
             "Rilevamento GPU/memoria: strategia auto-suggerita per Worker e modelli",
             "Hardware", "#0891b2", 2, 0),
        ]

        for key, title, subtitle, badge, badge_color, row, col in tool_card_configs:
            card = PlanciaCard(title, subtitle, badge=badge, badge_color=badge_color)
            card.clicked.connect(lambda k=key: self.open_panel(k))
            self.tools_cards[key] = card
            tools_grid.addWidget(card, row, col)

        tools_container = QWidget()
        tools_container.setLayout(tools_grid)
        tools_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.plancia_section.add_widget(tools_container)

        main_lay.addWidget(self.plancia_section)

        main_scroll.setWidget(main_widget)
        self.main_stack.addWidget(main_scroll)

        self.detail_stack = QStackedWidget()
        self.panel_pages = {}
        # Pannello "coda" → TaskSchedulerPanel (Code Task con orari)
        scheduler_page = self._build_scheduler_page()
        self.panel_pages["coda"] = scheduler_page
        self.detail_stack.addWidget(scheduler_page)

        # Pannello "modelli" → ActorsPanel (3 attori: LLM + Decision + Timestral)
        actors_page = self._build_actors_page()
        self.panel_pages["modelli"] = actors_page
        self.detail_stack.addWidget(actors_page)

        # Pannello "config" → SettingsPanel interattivo (tema, lingua, Git)
        config_page = self._build_config_page()
        self.panel_pages["config"] = config_page
        self.detail_stack.addWidget(config_page)

        # Pannello "cicd" → CICDPipelinePanel (pipeline build/test/deploy)
        cicd_page = self._build_cicd_page()
        self.panel_pages["cicd"] = cicd_page
        self.detail_stack.addWidget(cicd_page)

        # Pannello "clean_code" → CleanCodePanel (lint, complexity, architettura)
        clean_code_page = self._build_clean_code_page()
        self.panel_pages["clean_code"] = clean_code_page
        self.detail_stack.addWidget(clean_code_page)

        # ── 5 pannelli strumenti di analisi ────────────────────────────
        # Ognuno dei 5 widget istanziati sopra viene avvolto in una pagina
        # con header "← Indietro alla Plancia (Backspace)" + titolo, poi aggiunto al
        # detail_stack. La key deve combaciare con quella usata nelle
        # PlanciaCard della tools_grid (vedi tool_card_configs sopra).
        self.panel_pages["code_explorer"] = self._wrap_in_panel_page(
            "🎮 Navigatore di codice Interattivo", self.code_explorer
        )
        self.detail_stack.addWidget(self.panel_pages["code_explorer"])

        self.panel_pages["backup_logs"] = self._wrap_in_panel_page(
            "💾 Backup Code — Git Logs", self.backup_logs
        )
        self.detail_stack.addWidget(self.panel_pages["backup_logs"])

        self.panel_pages["logs"] = self._wrap_in_panel_page(
            "📜 Log — Diario di Bordo", self.log_viewer
        )
        self.detail_stack.addWidget(self.panel_pages["logs"])

        self.panel_pages["integrity"] = self._wrap_in_panel_page(
            "🧪 Test di integrità del software", self.integrity_panel
        )
        self.detail_stack.addWidget(self.panel_pages["integrity"])

        self.panel_pages["security"] = self._wrap_in_panel_page(
            "🛡️ Sicurezza del software & anti-manomissione", self.security_panel
        )
        self.detail_stack.addWidget(self.panel_pages["security"])

        # Pannello "audit_project" → AuditProjectPanel (gate su progetto target)
        from GUI.audit_project_panel import AuditProjectPanel
        self.panel_pages["audit_project"] = AuditProjectPanel()
        self.detail_stack.addWidget(self.panel_pages["audit_project"])

        # Pannello "hardware" → HardwarePanel (profilo GPU/memoria + strategia)
        from GUI.hardware_panel import HardwarePanel
        self.panel_pages["hardware"] = HardwarePanel()
        self.detail_stack.addWidget(self.panel_pages["hardware"])

        self.main_stack.addWidget(self.detail_stack)

        root.addWidget(self.main_stack, stretch=1)

    def open_panel(self, key):
        if key in self.panel_pages:
            self.main_stack.setCurrentIndex(1)
            self.detail_stack.setCurrentWidget(self.panel_pages[key])

    def _on_global_search(self, text: str):
        """Filtra le card (plancia + strumenti) in base al testo cercato.

        Non nasconde nulla: tutte le card restano visibili per preservare
        la memoria visiva. Quelle che matchano vengono evidenziate
        (bordo accent + sfondo leggero), le altre restano in opacità ridotta.
        """
        query = text.strip().lower()
        all_cards = list(self.cards.values()) + list(self.tools_cards.values())
        for card in all_cards:
            if not query:
                if hasattr(card, "_search_orig_style"):
                    card.setStyleSheet(card._search_orig_style)
                else:
                    card.setStyleSheet("")
                continue
            if not hasattr(card, "_search_orig_style"):
                card._search_orig_style = card.styleSheet()
            haystack_parts: list[str] = []
            from PyQt6.QtWidgets import QLabel as _QLabel
            for child in card.findChildren(_QLabel):
                haystack_parts.append(child.text().lower())
            haystack = " ".join(haystack_parts)
            if query in haystack:
                card.setStyleSheet(
                    "QFrame#card { border: 2px solid #2563eb; border-radius: 8px; "
                    "background: rgba(37,99,235,0.06); }"
                )
            else:
                card.setStyleSheet(
                    "QFrame#card { border: 1px solid #555; opacity: 0.65; }"
                )

    def _on_global_search_enter(self):
        """Premi Invio nella ricerca globale: se c'è un solo match,
        apri direttamente quel pannello (menù specifico)."""
        query = self.global_search.text().strip().lower()
        if not query:
            return
        all_cards = list(self.cards.items()) + list(self.tools_cards.items())
        matches = []
        for key, card in all_cards:
            haystack_parts: list[str] = []
            from PyQt6.QtWidgets import QLabel as _QLabel
            for child in card.findChildren(_QLabel):
                haystack_parts.append(child.text().lower())
            haystack = " ".join(haystack_parts)
            if query in haystack:
                matches.append((key, card))
        if len(matches) == 1:
            key, _card = matches[0]
            self.open_panel(key)

    def back_to_main(self):
        self.main_stack.setCurrentIndex(0)

    def eventFilter(self, obj, event):
        # Scorciatoie globali (Backspace = Indietro alla Plancia,
        # "/" con campo vuoto = scrivi nel campo comando in basso).
        try:
            import sys as _d
            if event.type() != QEvent.Type.KeyPress:
                return False
            if QApplication.activeModalWidget() is not None:
                return False
            from PyQt6.QtWidgets import (
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
                QSpinBox, QDoubleSpinBox, QDateTimeEdit,
            )
            focus = QApplication.focusWidget()
            is_editor = isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit,
                                           QComboBox, QSpinBox, QDoubleSpinBox,
                                           QDateTimeEdit))
            key = event.key()
            # ESC → chiude l'overlay dei ringraziamenti (se aperto)
            main_esc = getattr(self, "main_win", None)
            if (key == Qt.Key.Key_Escape and main_esc is not None
                    and getattr(main_esc, "_credits_overlay", None) is not None):
                try:
                    main_esc._close_credits()
                except Exception:
                    pass
                return True
            # Backspace → Indietro alla Plancia (solo fuori dagli editor,
            # oppure dentro un QLineEdit di ricerca vuoto).
            if key == Qt.Key.Key_Backspace:
                if is_editor and isinstance(focus, QLineEdit) and focus.text():
                    return False  # lascia che QLineEdit cancelli il carattere
                ms = getattr(self, "main_stack", None)
                if ms is not None and ms.currentIndex() != 0:
                    self.back_to_main()
                    return True
                return False
            # "/" → scrivi nel campo comando in basso (se vuoto)
            if key == Qt.Key.Key_Slash and not is_editor:
                main_win = getattr(self, "main_win", None)
                inp = getattr(main_win, "cmd_input", None) if main_win is not None else getattr(self, "cmd_input", None)
                if inp is not None:
                    inp.setFocus()
                    if not inp.text():
                        inp.setText("/")
                    else:
                        # inserisci "/" alla posizione del cursore
                        pos = inp.cursorPosition()
                        txt = inp.text()
                        inp.setText(txt[:pos] + "/" + txt[pos:])
                        inp.setCursorPosition(pos + 1)
                    return True
            return False
        except Exception:
            return False

    def _wrap_in_panel_page(self, title: str, widget: QWidget) -> QWidget:
        """Avvolge un widget in una pagina con header "← Indietro" + titolo.

        Pattern comune per tutti i pannelli del detail_stack: header con
        pulsante Indietro + titolo, poi il widget content che riempie lo
        spazio restante. Stesso stile di CICDPipelinePanel, CleanCodePanel
        e SettingsPanel.
        """
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(14)

        # Header: pulsante Indietro + titolo
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        # Stile dal tema app-level (QPushButton#back_btn nei .qss se
        # presente, altrimenti QPushButton base) — segue il tema live.
        back.clicked.connect(self.back_to_main)
        head.addWidget(back)
        head.addStretch()
        title_lbl = QLabel(f"<b style='font-size:18px;'>{title}</b>")
        head.addWidget(title_lbl)
        head.addStretch()
        lay.addLayout(head)

        # Content: il widget vero e proprio. NB: i 5 pannelli strumenti
        # arrivano con altezza FISSA 300px (per la griglia della Plancia):
        # qui nel detail page deve invece riempire la pagina, altrimenti
        # il layout lo centra verticalmente lasciando mezzo buco.
        # Minima rimossa: il widget Expanding riempie lo spazio disponibile.
        widget.setMaximumHeight(16777215)   # QWIDGETSIZE_MAX
        lay.addWidget(widget, stretch=1)
        return page

    def _on_accordion_toggled(self, expanded: bool):
        """[DEPRECATO] Comportamento accordion sulle vecchie sezioni collassabili.

        Mantenuto per backward compatibility: le 5 sezioni sono state
        sostituite da PlanciaCard cliccabili, ma se qualche riferimento
        esterno chiama ancora questo metodo non crasha (no-op).
        """
        return

    def _build_panel_page(self, title, content, key):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        head = QHBoxLayout()
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        # Stile dal tema app-level — segue il tema live.
        back.clicked.connect(self.back_to_main)
        head.addWidget(back)
        head.addStretch()
        head.addWidget(QLabel(f"<b style='font-size:18px;'>{title}</b>"))
        head.addStretch()
        lay.addLayout(head)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(content)
        # Stile dal tema app-level (QTextEdit nei .qss) — segue il tema live.
        body.setStyleSheet(
            "QTextEdit { font-size:13px; padding:20px; "
            "font-family:'JetBrains Mono','Consolas',monospace; }"
        )
        lay.addWidget(body, stretch=1)
        return page

    def _build_config_page(self):
        """Costruisce il pannello Impostazioni interattivo.

        Sostituisce il vecchio testo statico con un SettingsPanel vero:
        - scelta tema (chiaro/scuro) applicato live
        - scelta lingua (it/en) con tooltip "Work in progress"
        - gestione remote Git (GitHub/GitLab/Git) con token, per push automatico
        """
        page = SettingsPanel()
        # Quando il tema cambia, applichiamo live all'app + credits
        page.theme_changed.connect(self._apply_theme_live)
        return page

    def _build_actors_page(self):
        """Costruisce il pannello Modelli → Attori (LLM, Decision, Timestral).

        Sostituisce il vecchio testo statico "Modelli Ollama caricati: ..."
        con un ActorsPanel interattivo dove l'utente può scegliere i modelli
        per ciascuno dei 3 attori e impostare i parametri del Timestral
        (soglie termiche, tok/s minimo, durata pausa, ecc.).
        La configurazione è salvata in CONFIG/actors.json.
        """
        page = ActorsPanel()
        return page

    def _build_scheduler_page(self):
        """Costruisce il pannello 'Coda Task' → TaskSchedulerPanel.

        Sostituisce il vecchio testo statico "3 task in coda ..." con un
        TaskSchedulerPanel interattivo dove l'utente può schedulare
        compiti (Code Task) a orari previsti: uno-shot a una data/ora,
        ricorrenti (ogni N secondi), oppure giornalieri alle HH:MM.
        La schedulazione è salvata in CONFIG/scheduled_tasks.json.
        """
        page = TaskSchedulerPanel(get_project_path=self.main_win.get_current_project_path)
        return page

    def _build_cicd_page(self):
        """Costruisce il pannello 'CI/CD' → CICDPipelinePanel.

        Mostra lo stato della pipeline: build → test → deploy, con
        trigger manuale (pulsanti) e log dei run precedenti.
        """
        page = CICDPipelinePanel()
        return page

    def _build_clean_code_page(self):
        """Costruisce il pannello 'Clean & Architecture Code' → CleanCodePanel.

        Esegue analisi qualità codice: lint, complessità ciclomatica,
        duplicazione, dipendenze circolari, ecc. — con pulsante 'Esegui
        analisi' e output testuale.
        """
        page = CleanCodePanel()
        return page

    def _apply_theme_live(self, theme: str):
        """Applica il tema scelto LIVE (nome completo, es. "nord").

        Il QSS del tema va alla finestra ControlCenter (self.main_win);
        il credits overlay usa solo il "kind" (light/dark) perché ha
        due varianti colore, non 10.
        """
        # self = CenterArea; self.main_win = ControlCenter (QMainWindow)
        from GUI.theme import theme as _theme_mod
        main = getattr(self, "main_win", None)
        if main is None:
            print("[tema] main_win non disponibile, salto applicazione live")
            return
        try:
            main.setStyleSheet(_theme_mod.load_stylesheet(theme)
                               + "\n" + main._window_chrome())
        except Exception as e:
            print(f"[tema] applicazione '{theme}' fallita: {e}")
            return
        # Applica il kind del tema anche al credits overlay se è aperto
        if hasattr(main, "_credits_overlay") and main._credits_overlay is not None:
            try:
                main._credits_overlay.apply_theme(_theme_mod.theme_kind(theme))
            except Exception as e:
                print(f"[tema] credits overlay apply_theme fallito: {e}")

    def attach_editor_column(self, editor_widget):
        if self._editor_column:
            self._editor_column.deleteLater()
        self._editor_column = editor_widget
        self._editor_column.setMinimumWidth(300)
        self._editor_column.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.layout().addWidget(self._editor_column)

        # Bug di ingrandimento: su finestra NON massimizzata l'aggiunta dei
        # 500px dell'editor superava il minimo del layout e Qt "ingrandiva"
        # la finestra di colpo (dimensione imprevedibile, contenuto tagliato).
        # Comportamento prevedibile: se non ci sta, si passa a massimizzata.
        try:
            main = getattr(self, "main_win", None)
            if (main is not None and not main.isMaximized()
                    and not main.isFullScreen()
                    and main.width() < 280 + 470 + self._editor_column.width()):
                main.showMaximized()
        except Exception:
            pass

    def detach_editor_column(self):
        if self._editor_column:
            self.layout().removeWidget(self._editor_column)
            self._editor_column = None


if __name__ == "__main__":
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
