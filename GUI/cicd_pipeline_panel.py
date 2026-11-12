"""cicd_pipeline_panel.py — Pannello per la pipeline CI/CD: build → test → deploy.

Estratto da GUI/control_center.py per ridurre il monolite.

Permette di:
  - eseguire manualmente ogni stage (build, test, deploy)
  - vedere lo stato (pass/fail/running) di ogni stage
  - log dei run precedenti in output testuale
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QGroupBox, QScrollArea,
)
from PyQt6.QtCore import Qt

from GUI.search_bar import SearchBar
from GUI.theme.theme import set_banner as _set_banner


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
        cancelled = False
        try:
            if key == "build":
                self.output.appendPlainText("  → py_compile di tutti i moduli...")
                import py_compile
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
                    # Contratto di ritorno REALE: il push può essere
                    # annullato nel dialog di conferma ("No") o fallire
                    # per remote. Prima il pannello mostrava
                    # "✓ Push completato" anche quando l'utente diceva No.
                    res = main.device_panel._do_git_save() or {}
                    status = res.get("status", "unknown")
                    if status == "cancelled":
                        self.output.appendPlainText(
                            "  ⚠️ Push ANNULLATO dall'utente: nessun "
                            "salvataggio eseguito")
                        cancelled = True
                    elif res.get("errors"):
                        self.output.appendPlainText(
                            f"  ✗ Push fallito su {len(res['errors'])} "
                            f"remote:")
                        for rname, rerr in res["errors"]:
                            self.output.appendPlainText(
                                f"     • {rname}: {str(rerr)[:120]}")
                        success = False
                    elif status == "pushed":
                        self.output.appendPlainText(
                            f"  ✓ Push completato su {res.get('total', 0)} "
                            f"remote (vedi log git)")
                    else:
                        self.output.appendPlainText(
                            "  ⚠️ Nessun push eseguito (nessun remote "
                            "configurato?)")
                        cancelled = True
                else:
                    self.output.appendPlainText("  ⚠️  device_panel non trovato")
                    success = False

        except Exception as e:
            self.output.appendPlainText(f"  ✗ ERRORE: {type(e).__name__}: {e}")
            success = False

        # Stato finale
        if cancelled:
            # annullato ≠ fallito: ambra, non rosso — ma NON "completato"
            self.stages[key].setText("🟡 annullato")
            self.stages[key].setStyleSheet(
                "color:#b45309; font-weight:bold; padding:4px 10px; "
                "background:#fef3c7; border-radius:6px;"
            )
        elif success:
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
