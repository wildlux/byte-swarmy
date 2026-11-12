"""audit_project_panel.py — Pannello "Audit Progetto" per la Plancia.

Permette di:
  - scegliere un progetto target dal ComboBox (auto-popolato da project/)
  - eseguire l'audit gate sul progetto selezionato
  - vedere la checklist delle categorie con status PASS/FAIL/SKIP
  - espandere ogni categoria per vedere i finding dettagliati
  - aprire il report HTML completo nel browser

L'audit gira in background (QThread) per non bloccare la GUI. Lo stato
dell'ultimo audit viene salvato in <project>/.audit_status.json così la
GUI può mostrarlo senza rilanciare ogni volta.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QComboBox, QMessageBox, QScrollArea, QSizePolicy, QGroupBox,
    QPlainTextEdit, QTreeWidget, QTreeWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from GUI.theme.theme import set_prop as _theme_prop
from GUI.theme.theme import set_banner as _theme_banner
from PyQt6.QtGui import QDesktopServices, QColor, QFont

# pyqtSignal è anche esportato come Signal per compatibilità
Signal = pyqtSignal

_BASE = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════
# Worker thread: esegue check_audit_gate in background
# ═══════════════════════════════════════════════════════════════

class GateWorker(QThread):
    """Esegue check_audit_gate in background, non blocca la GUI."""
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(dict)   # GateResult.to_dict()
    failed = pyqtSignal(str)

    def __init__(self, project_path: str, mode: str = "advisory", parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.mode = mode

    def run(self):
        try:
            self.progress.emit(f"🔍 Avvio audit gate su {Path(self.project_path).name}...")
            from CORE.audit_gate import check_audit_gate, save_gate_status
            result = check_audit_gate(self.project_path, mode=self.mode)
            # Salva lo stato per下次 apertura rapida
            save_gate_status(self.project_path, result)
            self.progress.emit("✓ Audit completato")
            self.finished_ok.emit(result.to_dict())
        except Exception as e:
            self.failed.emit(f"Errore audit: {e}")


# ═══════════════════════════════════════════════════════════════
# Pannello principale
# ═══════════════════════════════════════════════════════════════

class AuditProjectPanel(QWidget):
    """Pannello 'Audit Progetto' per la Plancia di byte-swarmy.

    Permette di puntare l'audit a un progetto specifico e vedere la
    checklist delle categorie con status PASS/FAIL (gate bloccante).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("audit_project_panel")
        self._worker: Optional[GateWorker] = None
        self._build_ui()
        self._refresh_projects()

    # ──────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header: pulsante Indietro + titolo
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>🔍 Audit Progetto</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        # Spiegazione
        expl = QLabel(
            "Esegue l'audit gate su un progetto target: variabili inutilizzate, "
            "codice morto, porte esposte, tunnel/reverse proxy, import banditi. "
            "Le categorie 🔒 bloccanti determinano il gate (PASS/FAIL)."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet("font-size:11px;")
        _theme_prop(expl, "role", "muted")
        outer.addWidget(expl)

        # Sezione scelta progetto + esecuzione
        exec_box = QGroupBox("🎯 Progetto target")
        exec_lay = QVBoxLayout(exec_box)
        exec_lay.setSpacing(8)
        exec_lay.setContentsMargins(14, 14, 14, 14)

        proj_row = QHBoxLayout()
        proj_row.setSpacing(8)
        proj_lbl = QLabel("Progetto:")
        proj_lbl.setStyleSheet("font-size:12px; font-weight:bold;")
        proj_row.addWidget(proj_lbl)
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(300)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        proj_row.addWidget(self.project_combo, stretch=1)

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setToolTip("Aggiorna lista progetti")
        self.refresh_btn.clicked.connect(self._refresh_projects)
        proj_row.addWidget(self.refresh_btn)
        exec_lay.addLayout(proj_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.run_btn = QPushButton("🔍 Esegui audit gate")
        _theme_prop(self.run_btn, "role", "start")
        self.run_btn.clicked.connect(self._on_run_audit)
        btn_row.addWidget(self.run_btn)

        self.open_html_btn = QPushButton("📂 Apri report HTML")
        self.open_html_btn.clicked.connect(self._on_open_html)
        btn_row.addWidget(self.open_html_btn)
        btn_row.addStretch()
        exec_lay.addLayout(btn_row)

        self.status_lbl = QLabel("Pronto. Seleziona un progetto e clicca 'Esegui audit gate'.")
        self.status_lbl.setStyleSheet("font-size:11px; font-style:italic;")
        _theme_prop(self.status_lbl, "role", "muted")
        self.status_lbl.setWordWrap(True)
        exec_lay.addWidget(self.status_lbl)

        outer.addWidget(exec_box)

        # Gate summary (badge grande PASS/FAIL) — bottoni colore dal tema
        self.gate_summary = QLabel("<i>Gate non ancora eseguito</i>")
        # RichText ESPlicito: il testo del risultato ha il tag <span> sulla
        # 3ª riga e l'euristica di Qt (mightBeRichText) guarda solo la 1ª —
        # senza questo, il markup veniva mostrato come testo letterale.
        self.gate_summary.setTextFormat(Qt.TextFormat.RichText)
        self.gate_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gate_summary.setStyleSheet(
            "padding:16px; font-size:16px; font-weight:bold;"
        )
        _theme_prop(self.gate_summary, "role", "muted")
        outer.addWidget(self.gate_summary)

        # Tree delle categorie con status
        cat_box = QGroupBox("📋 Categorie")
        cat_lay = QVBoxLayout(cat_box)
        cat_lay.setSpacing(8)
        cat_lay.setContentsMargins(14, 14, 14, 14)

        self.cat_tree = QTreeWidget()
        self.cat_tree.setHeaderLabels(["Categoria", "Status", "Critical", "Warning", "Descrizione"])
        self.cat_tree.setRootIsDecorated(True)
        self.cat_tree.setAlternatingRowColors(True)
        # stile (bg/border/selection/header) dal tema app-level
        header = self.cat_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        cat_lay.addWidget(self.cat_tree)

        outer.addWidget(cat_box, stretch=1)

    # ──────────────────────────────────────────────────────────────────
    # Stili: RIMOSSI gli inline light-only (white/#f8f9fa/#666). Lo stile
    # arriva dal tema app-level (QGroupBox/QTreeWidget/QPushButton[role]).
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # Handler
    # ──────────────────────────────────────────────────────────────────
    def _refresh_projects(self):
        """Popola il ComboBox con i progetti in project/ + byte-swarmy self."""
        self.project_combo.clear()
        # Aggiungi self-audit (byte-swarmy su se stesso)
        self.project_combo.addItem("🐝 byte-swarmy (self)", str(_BASE))
        # Aggiungi cartelle in project/
        projects_dir = _BASE / "project"
        if projects_dir.is_dir():
            try:
                entries = sorted(
                    e for e in os.listdir(projects_dir)
                    if os.path.isdir(projects_dir / e) and not e.startswith(".")
                )
            except OSError:
                entries = []
            for name in entries:
                self.project_combo.addItem(f"📁 {name}", str(projects_dir / name))

    def _on_project_changed(self, _idx: int):
        """Quando cambia il progetto selezionato, carica l'ultimo stato salvato."""
        path = self.project_combo.currentData()
        if not path:
            return
        from CORE.audit_gate import load_gate_status
        saved = load_gate_status(path)
        if saved is not None:
            self._display_result(saved.to_dict())
            self.status_lbl.setText(
                f"Ultimo audit: {saved.timestamp} (caricato da .audit_status.json)"
            )
        else:
            self.gate_summary.setText("<i>Nessun audit precedente. Clicca 'Esegui audit gate'.</i>")
            self.gate_summary.setStyleSheet(
                "padding:16px; font-size:16px; font-weight:bold;"
            )
            _theme_prop(self.gate_summary, "role", "muted")
            self.cat_tree.clear()
            self.status_lbl.setText(
                "Pronto. Seleziona un progetto e clicca 'Esegui audit gate'."
            )

    def _on_run_audit(self):
        """Esegue l'audit gate sul progetto selezionato (background thread)."""
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Audit in corso",
                                    "Un audit è già in esecuzione. Attendi il completamento.")
            return
        path = self.project_combo.currentData()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "Path non valido",
                                f"Il path del progetto non è valido: {path}")
            return
        # Disabilita pulsante
        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ Audit in corso...")
        self.status_lbl.setText(f"Avvio audit su {Path(path).name}...")
        self.status_lbl.setStyleSheet("font-size:11px; font-weight:bold;")
        _theme_banner(self.status_lbl, "info")
        self.cat_tree.clear()
        self.gate_summary.setText("<i>⏳ Audit in corso...</i>")
        self.gate_summary.setStyleSheet(
            "padding:16px; font-size:16px; font-weight:bold;"
        )
        _theme_banner(self.gate_summary, "info")

        # Leggi mode da config
        from CORE.audit_gate import load_gate_config
        cfg = load_gate_config()
        mode = cfg.get("mode", "advisory")

        # Crea worker
        self._worker = GateWorker(path, mode=mode, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, msg: str):
        self.status_lbl.setText(msg)

    def _on_finished(self, result_dict: dict):
        """Mostra i risultati quando l'audit finisce."""
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🔍 Esegui audit gate")
        self._display_result(result_dict)
        self.status_lbl.setText(
            f"✓ Audit completato — gate: {result_dict.get('gate', '?')}"
        )

    def _on_failed(self, msg: str):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🔍 Esegui audit gate")
        self.status_lbl.setText("✗ Audit fallito")
        self.status_lbl.setStyleSheet("font-size:11px; font-weight:bold;")
        _theme_banner(self.status_lbl, "error")
        self.gate_summary.setText(f"✗ Errore: {msg[:200]}")
        self.gate_summary.setStyleSheet(
            "padding:16px; font-size:14px; font-weight:bold;"
        )
        _theme_banner(self.gate_summary, "error")
        QMessageBox.critical(self, "Audit fallito", msg)

    def _display_result(self, result: dict):
        """Mostra il GateResult nella GUI (gate summary + tree categorie)."""
        gate = result.get("gate", "?")
        mode = result.get("mode", "?")
        crit = result.get("critical_count", 0)
        warn = result.get("warning_count", 0)
        total = result.get("total_findings", 0)

        # Gate summary (rich text: i \n verrebbero collassati → <br>)
        if gate == "PASS":
            self.gate_summary.setText(
                f"✓ GATE PASS<br>"
                f"Nessuna categoria bloccante con critical<br>"
                f"<span style='font-size:12px; font-weight:normal;'>"
                f"Totale: {total} finding (critical: {crit}, warning: {warn}, mode: {mode})"
                f"</span>"
            )
            self.gate_summary.setStyleSheet(
                "padding:16px; font-size:18px; font-weight:bold;"
            )
            _theme_banner(self.gate_summary, "ok")
        else:
            self.gate_summary.setText(
                f"✗ GATE FAIL<br>"
                f"Almeno una categoria bloccante ha critical da risolvere<br>"
                f"<span style='font-size:12px; font-weight:normal;'>"
                f"Totale: {total} finding (critical: {crit}, warning: {warn}, mode: {mode})"
                f"</span>"
            )
            self.gate_summary.setStyleSheet(
                "padding:16px; font-size:18px; font-weight:bold;"
            )
            _theme_banner(self.gate_summary, "error")

        # Tree categorie
        self.cat_tree.clear()
        for cat in result.get("categories", []):
            status = cat.get("status", "?")
            blocking = cat.get("blocking", False)
            icon = cat.get("icon", "")
            name = cat.get("name", cat.get("id", ""))
            lock = "🔒 " if blocking else "   "
            desc = cat.get("message", "") if status == "SKIP" else cat.get("description", "")

            # Icona status
            if status == "PASS":
                status_icon = "✓ PASS"
                color = QColor("#16a34a")
            elif status == "FAIL":
                status_icon = "✗ FAIL"
                color = QColor("#dc2626")
            else:  # SKIP
                status_icon = "– SKIP"
                color = QColor("#8f99ab")

            item = QTreeWidgetItem([
                f"{lock}{icon} {name}",
                status_icon,
                str(cat.get("critical", 0)),
                str(cat.get("warning", 0)),
                desc,
            ])
            # Colore status
            item.setForeground(1, color)
            # Bold per bloccanti
            if blocking:
                f = item.font(0)
                f.setBold(True)
                item.setFont(0, f)
            self.cat_tree.addTopLevelItem(item)

            # Aggiungi figli: i finding di questa categoria
            cat_id = cat.get("id", "")
            from tests.test_monthly_audit import _FINDING_TYPE_TO_CATEGORY
            cat_findings = [f for f in result.get("findings", [])
                            if _FINDING_TYPE_TO_CATEGORY.get(f.get("type", ""), "") == cat_id]
            for f in cat_findings[:30]:  # max 30 per categoria
                sev = f.get("severity", "info")
                loc = f"{f.get('file', '?')}:{f.get('line', 0)}"
                msg = f.get("message", "")[:120]
                child = QTreeWidgetItem([
                    f"  [{sev.upper()}] {loc}",
                    "",
                    "",
                    "",
                    msg,
                ])
                sev_color = {
                    "critical": QColor("#dc2626"),
                    "warning": QColor("#f59e0b"),
                    "info": QColor("#3b82f6"),
                }.get(sev, QColor("#8f99ab"))
                child.setForeground(0, sev_color)
                item.addChild(child)
            if len(cat_findings) > 30:
                more = QTreeWidgetItem([
                    f"  ... e altri {len(cat_findings) - 30} finding",
                    "", "", "", "",
                ])
                more.setForeground(0, QColor("#8f99ab"))
                item.addChild(more)

        # Espandi le categorie FAIL per evidenziare i problemi
        for i in range(self.cat_tree.topLevelItemCount()):
            item = self.cat_tree.topLevelItem(i)
            if "FAIL" in item.text(1):
                item.setExpanded(True)

    def _on_open_html(self):
        """Apre il report HTML dell'ultimo audit del progetto corrente."""
        path = self.project_combo.currentData()
        if not path:
            return
        # Cerca il report HTML in logs/audit/<name>_audit.html
        proj_name = Path(path).name
        html_path = _BASE / "logs" / "audit" / f"{proj_name}_audit.html"
        if not html_path.exists():
            # Fallback: latest.html
            html_path = _BASE / "logs" / "audit" / "latest.html"
        if not html_path.exists():
            QMessageBox.information(self, "Nessun report",
                                    "Nessun report HTML trovato. Esegui prima un audit.")
            return
        QDesktopServices.openUrl(f"file://{html_path}")

    def _back_to_main(self):
        """Torna alla plancia di controllo."""
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()
