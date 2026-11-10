"""
CreditsOverlay — overlay modale con i ringraziamenti del progetto.

Estratto da GUI/control_center.py (riga ~121-601).
"""

import os

from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QPalette, QPixmap, QDesktopServices

from GUI.theme import theme as _T
from GUI import settings_store


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
            self._theme = settings_store.get_theme()
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
        title.setMinimumHeight(28)
        self._colored.append(
            (title, "font-size: 22px; color: {color}; font-weight: bold;",
             "#4ade80"))
        lay.addWidget(title)

        subtitle = QLabel("Autonomous Multi-Agent System")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 12px; font-style: italic;")
        subtitle.setMinimumHeight(16)
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
        credits_title.setMinimumHeight(26)
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
                candidate = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "IMG", logo_file,
                )
                if os.path.exists(candidate):
                    logo_path = candidate

            if logo_path:
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
        tech_title.setMinimumHeight(20)
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
        final_msg.setMinimumHeight(18)
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
