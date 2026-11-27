"""Pannello Plancia — grafico dei miglioramenti (RAG/DOCS/MIGLIORAMENTI.md).

Mostra RAG/DOCS/grafici/miglioramenti.svg (generato deterministicamente da
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

    SVG_RELPATH = Path("RAG") / "DOCS" / "grafici" / "miglioramenti.svg"

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
                "SVG non trovato: RAG/DOCS/grafici/miglioramenti.svg\n"
                "Premi 🔄 Rigenera (esegue tools/gen_grafici.py, zero LLM)")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll.setWidget(msg)
            self._status.setText("⚠ SVG mancante")

    # ------------------------------------------------------------------
    def _regenerate(self) -> None:
        """Rigenera l'SVG con lo script deterministico e mostra l'esito.

        Prima del Cycle 94 il pulsante sembrava non fare nulla: lo script
        girava, ma i dati erano hard-coded e lo status veniva subito
        sovrascritto dal solo percorso file. Ora riportiamo se il contenuto
        è cambiato, quanti byte sono stati scritti e un eventuale errore.
        """
        import hashlib
        import subprocess
        import sys
        import time

        root = self._svg_path.parents[2]
        script = root / "tools" / "gen_grafici.py"
        before = (self._svg_path.read_bytes()
                  if self._svg_path.exists() else b"")
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=30, cwd=str(root),
            )
        except Exception as e:
            self._status.setText(f"⚠ errore: {e}")
            return

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:120]
            self._status.setText(
                f"⚠ errore (exit {proc.returncode}): {detail}")
            return

        after = (self._svg_path.read_bytes()
                 if self._svg_path.exists() else b"")
        if not after:
            self._status.setText("⚠ errore: SVG non scritto")
            return
        changed = (hashlib.sha256(after).digest()
                   != hashlib.sha256(before).digest())
        self._load_svg()  # ricarica dopo la rigenerazione
        message = ("✅ SVG aggiornato" if changed
                   else "✅ SVG identico (nessun dato cambiato)")
        self._status.setText(
            f"{message} · {time.strftime('%H:%M:%S')} · {len(after)} byte")

    def _back_to_main(self):
        """Torna alla plancia di controllo (walk-up sul parent tree)."""
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()
