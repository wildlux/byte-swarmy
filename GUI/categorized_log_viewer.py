"""
GUI/categorized_log_viewer.py — Visualizzatore log a schede categorizzate.

Estratto da GUI/control_center.py (classe CategorizedLogViewer).
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QStackedWidget, QTabBar, QTextEdit, QVBoxLayout,
)

from GUI.gui_backend import get_logs


class CategorizedLogViewer(QFrame):
    """Visualizzatore log con schede per categoria.

    Mostra i log di sistema (attualmente solo "byteswarm"; Ollama è stato
    spostato nel pannello Modelli → Attori).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("log_viewer")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Fix: la scheda "🦙 Ollama" è stata spostata nel pannello
        # Modelli → Attori (per verificare se Ollama funziona su quel PC).
        # Qui resta solo la scheda "🐝 ByteSwarm GUI" — il diario di bordo
        # del sistema.
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
