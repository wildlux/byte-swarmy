"""Pannello Plancia — grafico dei miglioramenti (DOCS/MIGLIORAMENTI.md).

Mostra DOCS/grafici/miglioramenti.svg (generato deterministicamente da
tools/gen_grafici.py) dentro un QScrollArea con QSvgWidget.

🆕 Cycle 85e — regola di parità GUI: il pannello ha back_btn per tornare
alla Plancia (stesso pattern di hardware_panel/test_suite_panel).
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class ImprovementsPanel(QWidget):
    """Grafico dei miglioramenti implementati (SVG vettoriale)."""

    SVG_RELPATH = Path("DOCS") / "grafici" / "miglioramenti.svg"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._svg_path = self._resolve_svg_path()
        self._build_ui()
        self._load_svg()

    # ------------------------------------------------------------------
    def _resolve_svg_path(self) -> Path:
        """Path dell'SVG: relativo alla root del repo (padre di GUI/)."""
        here = Path(__file__).resolve().parent.parent
        return here / self.SVG_RELPATH

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header: back (parità GUI) + rigenera (deterministico, zero LLM)
        head = QHBoxLayout()
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet("color: #64748b; font-size: 11px;")
        head.addWidget(self._status)
        self.btn_regen = QPushButton("🔄 Rigenera")
        self.btn_regen.setToolTip(
            "Rigenera l'SVG con tools/gen_grafici.py "
            "(deterministico, zero LLM)")
        self.btn_regen.clicked.connect(self._regenerate)
        head.addWidget(self.btn_regen)
        layout.addLayout(head)

        # ScrollArea con SVG a dimensione naturale
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._scroll)

    def _load_svg(self) -> None:
        """Carica l'SVG; fallback onesto se manca."""
        if self._svg_path.exists():
            self._svg = QSvgWidget(str(self._svg_path))
            size = self._svg.renderer().defaultSize()
            self._svg.setFixedSize(size.width(), size.height())
            self._scroll.setWidget(self._svg)
            self._status.setText(
                f"{self._svg_path.relative_to(self._svg_path.parents[2])} "
                f"({size.width()}×{size.height()})")
        else:
            self._svg = None
            msg = QLabel(
                "SVG non trovato: DOCS/grafici/miglioramenti.svg\n"
                "Premi 🔄 Rigenera (esegue tools/gen_grafici.py, zero LLM)")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll.setWidget(msg)
            self._status.setText("⚠ SVG mancante")

    # ------------------------------------------------------------------
    def _regenerate(self) -> None:
        """Rigenera l'SVG con lo script deterministico (fail-open)."""
        import subprocess
        import sys
        root = self._svg_path.parents[2]
        script = root / "tools" / "gen_grafici.py"
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=30, cwd=str(root),
            )
            if proc.returncode == 0:
                self._load_svg()  # ricarica dopo la rigenerazione
            else:
                self._status.setText(
                    f"⚠ errore: {proc.stderr.strip()[:120]}")
        except Exception as e:
            self._status.setText(f"⚠ errore: {e}")

    def _back_to_main(self):
        """Torna alla plancia di controllo (walk-up sul parent tree)."""
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()
