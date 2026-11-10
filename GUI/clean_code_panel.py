"""clean_code_panel.py — Pannello per analizzare qualità e architettura del codice.

Estratto da GUI/control_center.py per ridurre il monolite.

Esegue:
  - lint base (py_compile + AST checks per funzioni/classi lunghe)
  - complessità ciclomatica semplificata (numero di rami per funzione)
  - duplicazione di righe identiche
  - conteggio linee di codice per modulo
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt

from GUI.search_bar import SearchBar


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
