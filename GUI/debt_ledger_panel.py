"""debt_ledger_panel.py — Pannello "Registro del debito tecnico" per la Plancia.

Grafico del debt ledger (CORE/debt_ledger.py): la coda di rifattorizzazioni/
ottimizzazioni tracciata in SQLite con verifica anti-stantio (file_hash).

Permette di (REGOLA DI PARITÀ: ogni funzione del ledger è usufruibile
dalla GUI — niente API che esistono solo da terminale):
  - `stats`  → etichetta della coda (done · open · stale)
  - `list`   → tabella item: id, stato, priorità, tipo, sforzo, file, titolo
  - `add`    → dialog di registrazione (tipo, file, titolo, perché, prio, sforzo)
  - `next`   → 🎯 Prossimo: l'item torna dalla query, marcato in_progress
               e selezionato (mai "un'idea": il lavoro arriva dal ledger)
  - `mark`   → ▶ In corso / ✅ Fatto sull'item selezionato
  - `context`→ 🔍 Contesto: simboli del file dal code_map (fail-open)
  - refresh a bottone (NESSUN timer nuovo: il heartbeat unico della GUI
    è sacro, Cycle 63 — aggiornamento solo on-demand)

Usa l'API direttamente (import CORE.debt_ledger), zero subprocess, zero
Ollama: la pianificazione del debito è lavoro freddo per definizione.
Fail-open: senza DB (coda vuota) mostra lo stato e basta, mai crash.
"""


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from CORE import debt_ledger as dl

_STATUS_COLORS = {
    "open": "#2563eb",
    "in_progress": "#d97706",
    "verify": "#7c3aed",
    "done": "#16a34a",
    "stale": "#6b7280",
}
_KIND_ICONS = {"refactor": "🔧", "optimization": "⚡", "test": "🧪",
               "docs": "📝"}


class _AddItemDialog(QDialog):
    """Dialog di registrazione: i 6 campi dell'item, validati dal modulo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuovo item — registro del debito")
        self.setMinimumWidth(420)
        form = QFormLayout(self)

        self.kind = QComboBox()
        self.kind.addItems([f"{_KIND_ICONS.get(k, '')} {k}" for k in dl.KINDS])
        form.addRow("Tipo", self.kind)

        self.file = QLineEdit()
        self.file.setPlaceholderText("es. CORE/worker.py")
        form.addRow("File", self.file)

        self.title = QLineEdit()
        self.title.setPlaceholderText("Cosa va rifattorizzato")
        form.addRow("Titolo", self.title)

        self.rationale = QLineEdit()
        self.rationale.setPlaceholderText("Perché / dove l'hai visto")
        form.addRow("Perché", self.rationale)

        self.priority = QSpinBox()
        self.priority.setRange(1, 3)
        self.priority.setValue(2)
        self.priority.setToolTip("1 = urgente, 2 = media, 3 = bassa")
        form.addRow("Priorità", self.priority)

        self.effort = QComboBox()
        self.effort.addItems(dl.EFFORTS)
        form.addRow("Sforzo", self.effort)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        kind_txt = self.kind.currentText().split(" ", 1)[-1].strip()
        return {
            "kind": kind_txt,
            "file_path": self.file.text().strip(),
            "title": self.title.text().strip(),
            "rationale": self.rationale.text().strip(),
            "priority": self.priority.value(),
            "effort": self.effort.currentText().strip(),
        }


class DebtLedgerPanel(QWidget):
    """Coda del debito tecnico: lista, stats, add/progress/done on-demand."""

    def __init__(self, project_root=None, parent=None):
        super().__init__(parent)
        # project_root=None → il default del modulo (repo byte-swarmy).
        # Parametrizzabile per i test (root temporanea).
        self.project_root = project_root
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 🆕 Cycle 85: regola di parità GUI — back_btn per tornare alla
        # Plancia (stesso pattern di hardware_panel/test_suite_panel).
        head = QHBoxLayout()
        head.addStretch()
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        layout.addLayout(head)

        # Riga stats + azioni
        top = QHBoxLayout()
        self.stats_label = QLabel("coda: —")
        self.stats_label.setStyleSheet(
            "font-weight: 600; font-size: 14px;")
        top.addWidget(self.stats_label)
        top.addStretch()

        self.btn_add = QPushButton("➕ Nuovo item")
        self.btn_add.clicked.connect(self._add_item)
        top.addWidget(self.btn_add)

        self.btn_next = QPushButton("🎯 Prossimo")
        self.btn_next.clicked.connect(self._pick_next)
        self.btn_next.setToolTip("next() del ledger: l'item torna dalla "
                                 "query, marcato in corso e selezionato")
        top.addWidget(self.btn_next)

        self.btn_progress = QPushButton("▶ In corso")
        self.btn_progress.clicked.connect(
            lambda: self._mark_selected("in_progress"))
        top.addWidget(self.btn_progress)

        self.btn_done = QPushButton("✅ Fatto")
        self.btn_done.clicked.connect(lambda: self._mark_selected("done"))
        top.addWidget(self.btn_done)

        self.btn_context = QPushButton("🔍 Contesto")
        self.btn_context.clicked.connect(self._show_context)
        self.btn_context.setToolTip("Simboli del file dal code_map "
                                    "(per riusare le API esistenti)")
        top.addWidget(self.btn_context)

        self.btn_refresh = QPushButton("🔄 Aggiorna")
        self.btn_refresh.clicked.connect(self.refresh)
        top.addWidget(self.btn_refresh)
        layout.addLayout(top)

        # Tabella item
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["#", "Stato", "Prio", "Tipo", "Sforzo", "File", "Titolo"])
        self.table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        hint = QLabel("Un item per sessione, stadiale: seleziona → ▶ In "
                      "corso → lavora → ✅ Fatto. Gli item su file "
                      "modificati diventano stale da soli (anti-stantio).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

    # ------------------------------------------------------------------
    def _back_to_main(self):
        """Torna alla plancia di controllo (walk-up sul parent tree).

        Stesso pattern di hardware_panel/test_suite_panel: la regola di
        parità GUI (Cycle 70) esige che ogni pannello abbia una via di
        ritorno esplicita alla Plancia.
        """
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()

    def refresh(self) -> None:
        """Rilegge stats + item dal ledger (nessun timer: solo on-demand)."""
        try:
            st = dl.stats(self.project_root)
            items = dl.list_items(self.project_root, limit=200)
        except Exception:
            st, items = {}, []
        parts = [f"{k} {v}" for k, v in sorted(st.items())] or ["vuota"]
        self.stats_label.setText("coda:  " + " · ".join(parts))

        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            status = it.get("status", "")
            values = [
                f"#{it.get('id', '')}",
                status,
                f"p{it.get('priority', '')}",
                f"{_KIND_ICONS.get(it.get('kind', ''), '')} "
                f"{it.get('kind', '')}",
                it.get("effort", ""),
                it.get("file_path", ""),
                it.get("title", ""),
            ]
            for c, text in enumerate(values):
                cell = QTableWidgetItem(str(text))
                if c == 1 and status in _STATUS_COLORS:
                    cell.setForeground(QColor(_STATUS_COLORS[status]))
                if c in (0, 2, 4):
                    cell.setTextAlignment(
                        int(Qt.AlignmentFlag.AlignCenter))
                self.table.setItem(r, c, cell)

    # ------------------------------------------------------------------
    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        cell = self.table.item(row, 0)
        if cell is None:
            return None
        try:
            return int(str(cell.text()).lstrip("#"))
        except ValueError:
            return None

    def _mark_selected(self, status: str) -> None:
        item_id = self._selected_id()
        if item_id is None:
            return
        try:
            dl.mark(self.project_root, item_id, status)
        except ValueError:
            return
        self.refresh()

    # ------------------------------------------------------------------
    def _select_item(self, item_id: int) -> None:
        """Seleziona e scorre alla riga dell'item (per il 🎯 Prossimo)."""
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, 0)
            if cell and str(cell.text()).lstrip("#") == str(item_id):
                self.table.setCurrentCell(r, 0)
                self.table.scrollToItem(cell)
                return

    def _pick_next(self) -> None:
        """🎯 next() del ledger — REGOLA: il lavoro arriva dalla query,
        mai da un'idea. L'item scelto viene marcato in_progress e
        selezionato, pronto per lo stadio di lavoro."""
        try:
            item = dl.next(self.project_root)
        except Exception:
            item = None
        if not item:
            self.stats_label.setText("coda:  vuota (nessun item valido)")
            return
        try:
            dl.mark(self.project_root, item["id"], "in_progress")
        except ValueError:
            pass
        self.refresh()
        self._select_item(item["id"])

    def _context_text(self) -> str | None:
        """Testo del contesto code_map per l'item selezionato (fail-open).

        None = nessuna selezione, item assente o nessun simbolo: il
        pannello mostra un messaggio, mai crash.
        """
        item_id = self._selected_id()
        if item_id is None:
            return None
        try:
            it = dl.get(self.project_root, item_id)
        except Exception:
            return None
        if not it:
            return None
        syms = dl.context_for_file(self.project_root,
                                   it.get("file_path", ""))
        if not syms:
            return None
        lines = [f"{s.get('kind', '')} {s.get('qualname') or s.get('name', '')}"
                 f"  (linea {s.get('line', '?')})" for s in syms]
        return (f"{it.get('file_path', '')} — {len(syms)} simboli dal "
                f"code_map:\n" + "\n".join(lines))

    def _show_context(self) -> None:
        text = self._context_text()
        if text:
            QMessageBox.information(self, "Contesto code_map", text)
        else:
            QMessageBox.information(
                self, "Contesto code_map",
                "Nessun simbolo: seleziona un item, oppure il code_map "
                "non copre ancora questo file (rebuild quando serve).")

    def _add_item(self) -> None:
        dlg = _AddItemDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["file_path"] or not v["title"]:
            return  # campi minimi mancanti: silenzioso, la GUI non urla
        try:
            dl.add(self.project_root, v["kind"], v["file_path"],
                   v["title"], v["rationale"], v["priority"], v["effort"])
        except ValueError:
            return
        self.refresh()
