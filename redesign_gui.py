#!/usr/bin/env python3
"""
redesign_gui.py — Restyle della GUI principale.

Cosa cambia:
1. Toggle button unico per Avvia/Ferma Orchestratore (cambia testo + colore)
2. Toolbar più compatta con temperatura CPU/GPU colorata
3. Live Activity Panel affiancato a destra della tabella task (2 colonne)
4. Status bar semplificata con indicatori colorati
5. Tema moderno con icone emoji coerenti
"""
import re
import shutil
from pathlib import Path

GUI_FILE = Path("gui.py")
BACKUP = Path("gui.py.bak.redesign")


def main():
    if not GUI_FILE.exists():
        print(f"❌ {GUI_FILE} non trovato")
        return 1

    content = GUI_FILE.read_text()

    shutil.copy2(GUI_FILE, BACKUP)
    print(f"✓ Backup: {BACKUP}")

    modifications = []

    # ====================================================================
    # 1. Aggiungi STYLESHEET moderno (sostituisce quello esistente)
    # ====================================================================
    new_stylesheet = '''    STYLESHEET = """
    QMainWindow, QWidget {
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'Segoe UI', 'Ubuntu', sans-serif;
        font-size: 10pt;
    }
    QMainWindow { background-color: #1a1a1a; }
    QTabWidget::pane {
        border: 1px solid #333;
        background-color: #1a1a1a;
        border-top: 2px solid #007acc;
    }
    QTabBar::tab {
        background: #252525;
        color: #999;
        padding: 8px 18px;
        border: 1px solid #333;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background: #007acc;
        color: #fff;
        border-color: #007acc;
    }
    QTabBar::tab:hover:!selected {
        background: #2d2d2d;
        color: #ccc;
    }
    QPushButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #444;
        padding: 6px 14px;
        border-radius: 4px;
        min-height: 24px;
    }
    QPushButton:hover { background-color: #383838; border-color: #555; }
    QPushButton:pressed { background-color: #404040; }
    QPushButton:disabled { color: #666; background-color: #252525; }
    QPushButton#toggleOrchestrator {
        background-color: #28a745;
        color: white;
        font-weight: bold;
        border: none;
        padding: 8px 16px;
        min-width: 200px;
    }
    QPushButton#toggleOrchestrator:hover { background-color: #218838; }
    QPushButton#toggleOrchestrator[data-running="true"] {
        background-color: #dc3545;
    }
    QPushButton#toggleOrchestrator[data-running="true"]:hover {
        background-color: #c82333;
    }
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background-color: #252525;
        color: #e0e0e0;
        border: 1px solid #333;
        padding: 5px;
        border-radius: 3px;
        selection-background-color: #007acc;
    }
    QLineEdit:focus { border: 1px solid #007acc; }
    QTableWidget {
        background-color: #1f1f1f;
        gridline-color: #333;
        border: 1px solid #333;
        selection-background-color: #264f78;
        alternate-background-color: #252525;
    }
    QTableWidget::item { padding: 4px; }
    QHeaderView::section {
        background-color: #2d2d2d;
        color: #aaa;
        padding: 6px;
        border: none;
        border-bottom: 2px solid #007acc;
        font-weight: bold;
    }
    QGroupBox {
        font-weight: bold;
        border: 1px solid #333;
        border-radius: 4px;
        margin-top: 1.5ex;
        padding-top: 1.2ex;
        background-color: #1f1f1f;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #007acc;
    }
    QScrollBar:vertical {
        background: #1a1a1a; width: 10px; border: none;
    }
    QScrollBar::handle:vertical {
        background: #444; min-height: 25px; border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover { background: #555; }
    QStatusBar {
        background-color: #007acc;
        color: white;
        font-weight: bold;
    }
    QStatusBar QLabel { color: white; padding: 0 8px; }
    QToolBar {
        background-color: #252525;
        border-bottom: 1px solid #333;
        spacing: 4px;
        padding: 4px;
    }
    QToolBar QToolButton {
        background: transparent;
        color: #e0e0e0;
        padding: 6px 10px;
        border-radius: 3px;
    }
    QToolBar QToolButton:hover { background: #383838; }
    QLabel#tempIndicator {
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 11pt;
        font-weight: bold;
        padding: 4px 10px;
        border-radius: 3px;
    }
    QSplitter::handle { background-color: #333; }
    QSplitter::handle:hover { background-color: #007acc; }
    """'''

    # Sostituisci lo stylesheet esistente
    pattern_stylesheet = re.compile(
        r'    STYLESHEET\s*=\s*"""[\s\S]*?"""',
        re.DOTALL
    )
    if pattern_stylesheet.search(content):
        content = pattern_stylesheet.sub(new_stylesheet, content, count=1)
        modifications.append("✓ Stylesheet moderno applicato")

    # ====================================================================
    # 2. Aggiungi metodo _build_toolbar nuovo (con toggle + temp indicator)
    # ====================================================================
    new_toolbar = '''    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        # 🆕 Toggle button unico (Avvia/Ferma)
        self.btn_toggle_orch = QPushButton("▶  Avvia Orchestratore")
        self.btn_toggle_orch.setObjectName("toggleOrchestrator")
        self.btn_toggle_orch.setCheckable(True)
        self.btn_toggle_orch.clicked.connect(self._on_toggle_orchestrator)
        toolbar.addWidget(self.btn_toggle_orch)

        toolbar.addSeparator()

        # 🆕 Indicatori temperatura CPU/GPU
        self.temp_cpu_label = QLabel("CPU: --°C")
        self.temp_cpu_label.setObjectName("tempIndicator")
        toolbar.addWidget(self.temp_cpu_label)

        self.temp_gpu_label = QLabel("GPU: --°C")
        self.temp_gpu_label.setObjectName("tempIndicator")
        toolbar.addWidget(self.temp_gpu_label)

        toolbar.addSeparator()

        # Pulsante esci
        self.act_quit = QAction("✕  Esci", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)
        toolbar.addAction(self.act_quit)

    def _on_toggle_orchestrator(self) -> None:
        """Toggle: avvia o ferma l'orchestratore con un solo pulsante."""
        if self.orchestrator.is_running():
            self.orchestrator.stop()
            self.btn_toggle_orch.setChecked(False)
            self.btn_toggle_orch.setText("▶  Avvia Orchestratore")
            self.status_bar.showMessage("○ Orchestratore fermato", 2000)
        else:
            ok = self.orchestrator.start()
            if ok:
                self.btn_toggle_orch.setChecked(True)
                self.btn_toggle_orch.setText("■  Ferma Orchestratore")
                self.status_bar.showMessage("● Orchestratore avviato", 2000)
            else:
                self.btn_toggle_orch.setChecked(False)
                self.status_bar.showMessage("❌ Avvio fallito", 3000)
        self._update_toolbar_state()

    def _update_toolbar_state(self) -> None:
        """Aggiorna lo stato del toggle button."""
        running = self.orchestrator.is_running()
        if running:
            self.btn_toggle_orch.setChecked(True)
            self.btn_toggle_orch.setText("■  Ferma Orchestratore")
            self.btn_toggle_orch.setProperty("data-running", "true")
        else:
            self.btn_toggle_orch.setChecked(False)
            self.btn_toggle_orch.setText("▶  Avvia Orchestratore")
            self.btn_toggle_orch.setProperty("data-running", "false")
        # Forza refresh stile
        self.btn_toggle_orch.style().unpolish(self.btn_toggle_orch)
        self.btn_toggle_orch.style().polish(self.btn_toggle_orch)'''

    # Sostituisci il vecchio _build_toolbar
    pattern_toolbar = re.compile(
        r'    def _build_toolbar\(self\) -> None:.*?self\.act_quit\.triggered\.connect\(self\.close\)\s*\n\s*toolbar\.addAction\(self\.act_quit\)',
        re.DOTALL
    )
    if pattern_toolbar.search(content):
        content = pattern_toolbar.sub(new_toolbar, content, count=1)
        modifications.append("✓ Toolbar con toggle + indicatori temperatura")

    # ====================================================================
    # 3. Aggiungi _update_status_bar nuovo (con temperatura colorata)
    # ====================================================================
    new_statusbar = '''    def _update_status_bar(self) -> None:
        running = self.orchestrator.is_running()
        if running:
            pid = self.orchestrator.pid()
            status_text = f"● Orchestratore ATTIVO (PID {pid})"
        else:
            status_text = "○ Orchestratore fermato"
        self.status_bar.showMessage(status_text)
        # Aggiorna indicatori temperatura nella toolbar
        self._update_temp_indicators()
        self._update_toolbar_state()

    def _update_temp_indicators(self) -> None:
        """Aggiorna le label temperatura CPU/GPU con colori semantici."""
        cpu_temp = 0.0
        gpu_temp = 0.0
        # CPU temp da timestral
        if self.timestral:
            try:
                advice = self.timestral.get_advice()
                if advice.sample:
                    cpu_temp = advice.sample.cpu_temp_max
                    gpu_temp = getattr(advice.sample, 'gpu_temp', 0.0) or 0.0
            except Exception:
                pass
        # Fallback: leggi nvidia-smi per GPU
        if gpu_temp == 0.0:
            try:
                import subprocess
                r = subprocess.run(
                    ["nvidia-smi", "--query-gpu=temperature.gpu",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and r.stdout.strip():
                    gpu_temp = float(r.stdout.strip().split()[0])
            except Exception:
                pass

        self._set_temp_label(self.temp_cpu_label, "CPU", cpu_temp, is_gpu=False)
        self._set_temp_label(self.temp_gpu_label, "GPU", gpu_temp, is_gpu=True)

    def _set_temp_label(self, label, name: str, temp: float, is_gpu: bool) -> None:
        """Imposta il testo e colore di una label temperatura."""
        if temp <= 0:
            label.setText(f"{name}: --°C")
            label.setStyleSheet("background-color: #444; color: #999;")
            return
        label.setText(f"{name}: {temp:.0f}°C")
        # Soglie (GPU più alta di CPU)
        if is_gpu:
            warm, hot, crit = 70, 80, 90
        else:
            warm, hot, crit = 60, 75, 90
        if temp >= crit:
            label.setStyleSheet("background-color: #dc3545; color: white;")
        elif temp >= hot:
            label.setStyleSheet("background-color: #fd7e14; color: white;")
        elif temp >= warm:
            label.setStyleSheet("background-color: #ffc107; color: black;")
        else:
            label.setStyleSheet("background-color: #28a745; color: white;")'''

    # Sostituisci vecchio _update_status_bar
    pattern_statusbar = re.compile(
        r'    def _update_status_bar\(self\) -> None:.*?self\.act_stop\.setEnabled\(not running\)',
        re.DOTALL
    )
    if pattern_statusbar.search(content):
        content = pattern_statusbar.sub(new_statusbar, content, count=1)
        modifications.append("✓ Status bar con temperatura colorata")

    # ====================================================================
    # 4. Layout 2 colonne in TaskQueueTab (tabella + live activity affiancati)
    # ====================================================================
    old_layout = '''        # Tabella
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["🆔 ID", "🚦 Stato", "📝 Titolo", "🛠️ Tipo", "🔄 Tentativi", "🌐 Sorgente"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)'''

    new_layout = '''        # 🆕 Layout 2 colonne: tabella task | live activity panel
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Colonna sinistra: tabella task
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["🆔 ID", "🚦 Stato", "📝 Titolo", "🛠️ Tipo", "🔄 Tentativi", "🌐 Sorgente"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        left_layout.addWidget(self.table)
        splitter.addWidget(left_widget)

        # Colonna destra: live activity panel (già esistente)
        splitter.addWidget(self.live_activity)

        # Proporzioni: 65% tabella, 35% activity
        splitter.setSizes([650, 350])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        layout.addWidget(splitter, stretch=1)'''

    if old_layout in content:
        content = content.replace(old_layout, new_layout, 1)
        modifications.append("✓ Layout 2 colonne: tabella | live activity")
    else:
        print("⚠  Pattern layout 2 colonne non trovato (forse già modificato)")

    # ====================================================================
    # 5. Rimuovi il Live Activity Panel dal vecchio posto (era sopra la tabella)
    # ====================================================================
    # Ora è dentro lo splitter, rimuovilo dalla posizione originale
    old_live = '''        # 🆕 Live Activity Panel
        self.live_activity = LiveActivityPanel()
        layout.addWidget(self.live_activity)

'''
    if old_live in content:
        content = content.replace(old_live, '''        # 🆕 Live Activity Panel (creato qui, inserito nello splitter sotto)
        self.live_activity = LiveActivityPanel()

''', 1)
        modifications.append("✓ Live Activity spostato nello splitter destro")

    # ====================================================================
    # 6. Aggiungi import QSize se manca
    # ====================================================================
    if "QSize" not in content:
        content = content.replace(
            "from PyQt6.QtGui import (\n    QAction, QFont, QColor, QTextCursor, QPixmap, QIcon\n)",
            "from PyQt6.QtGui import (\n    QAction, QFont, QColor, QTextCursor, QPixmap, QIcon, QSize\n)",
            1
        )
        modifications.append("✓ Import QSize aggiunto")

    # Salva
    GUI_FILE.write_text(content)

    # Verifica sintassi
    try:
        compile(content, "gui.py", "exec")
        print("✓ Verifica sintassi OK")
    except SyntaxError as e:
        print(f"❌ Errore sintassi: {e}")
        shutil.copy2(BACKUP, GUI_FILE)
        return 1

    print()
    for m in modifications:
        print(m)
    print()
    print("=" * 60)
    print("✓ REDESIGN COMPLETATO")
    print("=" * 60)
    print()
    print("Cosa è cambiato:")
    print("  1. Toggle button unico per Avvia/Ferma Orchestratore")
    print("  2. Indicatori temperatura CPU/GPU nella toolbar (verde/arancio/rosso)")
    print("  3. Layout 2 colonne: tabella task | live activity panel")
    print("  4. Status bar semplificata")
    print("  5. Tema moderno dark con accenti blu")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*gui' 2>/dev/null; sleep 1")
    print("  ./avvia.sh --gui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
