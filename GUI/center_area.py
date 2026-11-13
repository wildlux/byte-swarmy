"""center_area.py — Area centrale del Control Center (plancia + log + stack).

Estratto da GUI/control_center.py per ridurre il monolite.
"""

from __future__ import annotations

import os
import json
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QScrollArea,
    QLineEdit, QComboBox, QPushButton, QLabel, QFrame, QSizePolicy,
    QMessageBox, QFileDialog, QInputDialog, QSplitter, QListWidget,
    QListWidgetItem, QTextEdit, QPlainTextEdit, QCheckBox, QGroupBox,
    QGridLayout, QScrollArea as _QScrollArea,
)
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPalette, QBrush
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QUrl

from GUI.collapsible_section import CollapsibleSection
from GUI.categorized_log_viewer import CategorizedLogViewer
from GUI.plancia_card import PlanciaCard
from GUI.code_explorer import CodeExplorer
from GUI.backup_code_logs import BackupCodeLogs
from GUI.integrity_tests_panel import IntegrityTestsPanel
from GUI.software_security_panel import SoftwareSecurityPanel
from GUI.panels import wrap_in_panel_page, build_plancia_cards, build_tools_cards, build_scheduler_page, build_actors_page, build_config_page, build_cicd_page, build_clean_code_page
from GUI.theme.theme import set_prop as _set_prop, set_banner as _set_banner

from CORE.constants import BTN_TRANSPARENT_STYLE, BTN_TRANSPARENT_DANGER_STYLE


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
        main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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
        from PyQt6.QtWidgets import QLineEdit as _QLineEdit, QComboBox as _QComboBox
        self.global_search = _QLineEdit()
        self.global_search.setPlaceholderText(
            "🔍 Cerca tra le card…  (es. \"task\", \"git\", \"ci/cd\", \"sicurezza\")"
        )
        self.global_search.setStyleSheet(
            "QLineEdit { padding:6px 12px; border-radius:8px; font-size:12px; }"
        )
        self.global_search.textChanged.connect(self._on_global_search)
        self.global_search.returnPressed.connect(self._on_global_search_enter)

        # Filtro categorie accanto alla ricerca (evita il "▼ vuoto")
        self.search_category = _QComboBox()
        self.search_category.addItem("Tutte le categorie")
        self.search_category.addItem("Plancia — task & coda")
        self.search_category.addItem("Strumenti — analisi progetto")
        self.search_category.setMinimumWidth(150)
        self.search_category.setToolTip("Filtra le card per categoria")
        self.search_category.setStyleSheet(
            "QComboBox { padding:4px 8px; border-radius:6px; font-size:11px; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox::down-arrow { image: none; border: none; }"
        )
        self.search_category.currentIndexChanged.connect(self._on_global_search)

        # Nella riga del titolo "Plancia di controllo" (sempre visibile,
        # anche a sezione collassata) invece di occupare una riga intera.
        self.plancia_section.add_header_widget(
            self.search_category, max_width=150, min_width=120, stretch=0)
        self.plancia_section.add_header_widget(
            self.global_search, max_width=700, min_width=360, stretch=2)

        cards_container, self.cards = build_plancia_cards(self.open_panel)
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

        tools_container, self.tools_cards = build_tools_cards(
            self.open_panel, self.log_viewer, self.code_explorer, self.backup_logs,
            self.integrity_panel, self.security_panel
        )
        self.plancia_section.add_widget(tools_container)

        main_lay.addWidget(self.plancia_section)

        main_scroll.setWidget(main_widget)
        self.main_stack.addWidget(main_scroll)

        self.detail_stack = QStackedWidget()
        self.panel_pages = {}
        # Pannello "coda" → TaskSchedulerPanel (Code Task con orari)
        scheduler_page = build_scheduler_page(self.main_win.get_current_project_path)
        self.panel_pages["coda"] = scheduler_page
        self.detail_stack.addWidget(scheduler_page)

        # Pannello "modelli" → ActorsPanel (3 attori: LLM + Decision + Timestral)
        actors_page = build_actors_page()
        self.panel_pages["modelli"] = actors_page
        self.detail_stack.addWidget(actors_page)

        # Pannello "config" → SettingsPanel interattivo (tema, lingua, Git)
        config_page = build_config_page(self._apply_theme_live, self._on_gui_debug_changed)
        self.panel_pages["config"] = config_page
        self.detail_stack.addWidget(config_page)

        # Pannello "cicd" → CICDPipelinePanel (pipeline build/test/deploy)
        cicd_page = build_cicd_page()
        self.panel_pages["cicd"] = cicd_page
        self.detail_stack.addWidget(cicd_page)

        # Pannello "clean_code" → CleanCodePanel (lint, complexity, architettura)
        clean_code_page = build_clean_code_page()
        self.panel_pages["clean_code"] = clean_code_page
        self.detail_stack.addWidget(clean_code_page)

        # ── 5 pannelli strumenti di analisi ────────────────────────────
        # Ognuno dei 5 widget istanziati sopra viene avvolto in una pagina
        # con header "← Indietro alla Plancia (Backspace)" + titolo, poi aggiunto al
        # detail_stack. La key deve combaciare con quella usata nelle
        # PlanciaCard della tools_grid (vedi tool_card_configs sopra).
        self.panel_pages["code_explorer"] = wrap_in_panel_page(
            "🎮 Navigatore di codice Interattivo", self.code_explorer, self.back_to_main
        )
        self.detail_stack.addWidget(self.panel_pages["code_explorer"])

        self.panel_pages["backup_logs"] = wrap_in_panel_page(
            "💾 Backup Code — Git Logs", self.backup_logs, self.back_to_main
        )
        self.detail_stack.addWidget(self.panel_pages["backup_logs"])

        self.panel_pages["logs"] = wrap_in_panel_page(
            "📜 Log — Diario di Bordo", self.log_viewer, self.back_to_main
        )
        self.detail_stack.addWidget(self.panel_pages["logs"])

        self.panel_pages["integrity"] = wrap_in_panel_page(
            "🧪 Test di integrità del software", self.integrity_panel, self.back_to_main
        )
        self.detail_stack.addWidget(self.panel_pages["integrity"])

        self.panel_pages["security"] = wrap_in_panel_page(
            "🛡️ Sicurezza del software & anti-manomissione", self.security_panel, self.back_to_main
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

        # Pannello "test" → TestSuitePanel (runner per-file con timeout)
        from GUI.test_suite_panel import TestSuitePanel
        self.panel_pages["test"] = TestSuitePanel()
        self.detail_stack.addWidget(self.panel_pages["test"])

        self.main_stack.addWidget(self.detail_stack)

        root.addWidget(self.main_stack, stretch=1)

    def open_panel(self, key):
        if key in self.panel_pages:
            self.main_stack.setCurrentIndex(1)
            self.detail_stack.setCurrentWidget(self.panel_pages[key])
            # Refresh della lista task quando si apre il pannello Coda,
            # così mostra sempre i task del progetto corrente
            if key == "coda":
                self.panel_pages["coda"].refresh()

    def _on_global_search(self, text: str):
        """Filtra le card (plancia + strumenti) in base al testo cercato.

        Non nasconde nulla: tutte le card restano visibili per preservare
        la memoria visiva. Quelle che matchano vengono evidenziate
        (bordo accent + sfondo leggero), le altre restano in opacità ridotta.
        """
        query = text.strip().lower()
        category = self.search_category.currentText() if hasattr(self, "search_category") else "Tutte le categorie"
        all_cards = list(self.cards.items()) + list(self.tools_cards.items())
        for key, card in all_cards:
            # Filtro per categoria selezionata
            if category != "Tutte le categorie":
                is_plancia = key in self.cards
                is_plancia_cat = category == "Plancia — task & coda"
                if is_plancia_cat != is_plancia:
                    card.setVisible(False)
                    continue
            card.setVisible(True)
        # Forza aggiornamento layout griglia per far sparire le card nascoste
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
            self.updateGeometry()
        except Exception:
            pass

        for key, card in all_cards:
            card.setVisible(True)
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
            # Backspace o Control+W → Indietro alla Plancia
            # (solo fuori dagli editor, oppure dentro un QLineEdit di ricerca vuoto).
            is_ctrl_w = key == Qt.Key.Key_W and bool(
                event.modifiers() & Qt.KeyboardModifier.ControlModifier
            )
            if key == Qt.Key.Key_Backspace or is_ctrl_w:
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
        # Dopo il cambio tema, il QSS della finestra e' tornato a 100% base:
        # aggiorna la base dello zoom e ri-applica lo zoom corrente, altrimenti
        # i font-size del tema non scalati "resettano" lo zoom visivo.
        try:
            if hasattr(main, "gui_settings"):
                main._zoom_original_stylesheet = main.styleSheet()
                main._apply_zoom(main.gui_settings.zoom_level)
            else:
                main._zoom_original_stylesheet = main.styleSheet()
        except Exception as e:
            print(f"[tema] riapplica zoom dopo cambio tema fallito: {e}")
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

    # ═════════════════════════════════════════════════════════════
    # DEBUG GUI — barra info-widget sotto il mouse
    # (implementazione in ControlCenter: la barra vive nella statusBar
    # del QMainWindow, qui — QWidget — non esiste statusBar())
    # ═════════════════════════════════════════════════════════════
    def _on_gui_debug_changed(self, enabled: bool):
        """Delega l'attivazione/disattivazione alla finestra principale."""
        self.main_win._on_gui_debug_changed(enabled)


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
