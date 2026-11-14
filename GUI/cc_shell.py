"""GUI/cc_shell.py — Shell della finestra: toolbar, command bar, menu, overlay.

Estratto da GUI/control_center.py (R3): metodi della classe ControlCenter
che costruiscono e gestiscono la "cornice" della finestra (menu ☰, credits,
barra comandi, tab progetti, chrome dei tab). Mixin: nessun cambiamento di
comportamento, i metodi restano sullo stesso oggetto ControlCenter.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QProgressBar,
    QPushButton, QWidget, QWidgetAction,
)

from GUI.credits_overlay import CreditsOverlay
from GUI.device_panel import DevicePanel
from GUI.project_tab_bar import ProjectTabBar

BASE_DIR = Path(__file__).parent.parent.resolve()


class ShellMixin:
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

        # ── Pannelli (menu hamburger come unico punto di ingresso) ─────
        panels_menu = menu.addMenu("📋 Pannelli")
        _panel_labels = {
            "coda": "📋 Coda task",
            "modelli": "🤖 Modelli",
            "config": "⚙️ Configurazione",
            "cicd": "🔄 CI/CD",
            "clean_code": "🧹 Clean code",
            "code_explorer": "🎮 Navigatore codice",
            "backup_logs": "💾 Backup code",
            "logs": "📜 Log",
            "integrity": "🧪 Integrità",
            "security": "🛡️ Sicurezza",
            "audit_project": "🔍 Audit progetto",
            "hardware": "🖥️ Hardware",
            "test": "🧪 Test suite",
        }
        for key, label in _panel_labels.items():
            act = QAction(label, self)
            act.triggered.connect(lambda _=False, k=key: self.center.open_panel(k))
            panels_menu.addAction(act)
        panels_menu.addSeparator()
        act_back = QAction("🏠 Indietro alla Plancia (Backspace)", self)
        act_back.triggered.connect(self.center.back_to_main)
        panels_menu.addAction(act_back)

        menu.addSeparator()

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

    def _update_live_activity(self):
        """Aggiorna la barra Live Activity leggendo state/streaming.txt."""
        try:
            from pathlib import Path
            p = Path("state/streaming.txt")
            txt = ""
            if p.exists():
                try:
                    txt = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    txt = ""
            last = ""
            for line in reversed(txt.splitlines()):
                if line.strip():
                    last = line.strip()
                    break
            if last:
                if len(last) > 120:
                    last = last[:117] + "…"
                self.live_activity_label.setText(last)
            else:
                self.live_activity_label.setText("In attesa di un task…")
        except Exception:
            pass

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

    def _window_chrome(self):
        """Regole di SOLO layout (nessun colore) concatenate al QSS del tema.

        Tab progetto MINIMALI: padding ridotto, font 11px, altezza compatta.
        Il padding-right lascia il posto alla × di chiusura (margine 4px per
        lato attorno all'icona ~16px). I colori arrivano dai temi
        GUI/theme/*.qss — qui solo geometria (concatenata DOPO il tema:
        vince su padding/font/min-height).
        """
        return """
        QTabBar::tab {
            border-bottom: 2px solid transparent;
            border-top-left-radius: 6px; border-top-right-radius: 6px;
            padding: 4px 20px 4px 12px;
            margin-right: 2px; font-size: 11px;
            min-height: 16px;
        }
        QTabBar::close-button {
            subcontrol-position: right;
            padding: 0;
            margin: 0;
            width: 14px; height: 14px;
        }
        """

