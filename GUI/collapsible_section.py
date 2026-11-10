"""
GUI/collapsible_section.py — Sezione collassabile riutilizzabile.

Estratto da GUI/control_center.py (classe CollapsibleSection).
Una sezione con header cliccabile che mostra/nasconde il contenuto.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class CollapsibleSection(QFrame):
    """Sezione con header cliccabile che mostra/nasconde il contenuto.

    Segnale:
        toggled(bool) — emesso quando lo stato cambia per azione utente.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, title, icon="📁", parent=None):
        super().__init__(parent)
        self.setObjectName("collapsible_section")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.header = QFrame()
        self.header.setObjectName("section_header")
        # Altezza minima su tutti gli header: uniformità visiva tra le sezioni
        # collassabili. minHeight invece di setFixedHeight così non si
        # comprimono a 0 quando la finestra si restringe.
        self.header.setMinimumHeight(40)
        header_lay = QHBoxLayout(self.header)
        header_lay.setContentsMargins(14, 6, 14, 6)
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
        header_lay.addWidget(self.toggle_btn, alignment=Qt.AlignmentFlag.AlignTop)

        lay.addWidget(self.header)

        self.content = QWidget()
        self.content.setStyleSheet("border-bottom-left-radius:8px; border-bottom-right-radius:8px;")
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(12, 6, 12, 6)
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
