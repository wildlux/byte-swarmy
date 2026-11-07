"""Widget SearchBar — barra di ricerca con evidenziazione per QPlainTextEdit.

Usa QTextEdit.ExtraSelection per evidenziare le occorrenze della parola
chiave cercata, senza modificare il testo. Include:
  - Campo di testo con placeholder
  - Pulsante ✕ per cancellare
  - Contatore "X/Y risultati" (match totali / caratteri evidenziati)
  - Navigazione tra i match con Enter (successivo/precedente)

Compatibile con qualsiasi QPlainTextEdit o QTextEdit. Per QListWidget
usare un approccio diverso (filter, non highlight).
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTextEdit,  # serve per QTextEdit.ExtraSelection (classe annidata)
)
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QTextCursor, QTextDocument,
)
from PyQt6.QtCore import Qt


class SearchBar(QWidget):
    """Barra di ricerca con evidenziazione per QPlainTextEdit/QTextEdit.

    Uso:
        bar = SearchBar(self.output, parent=self)
        lay.addWidget(bar)

    Quando l'utente digita, evidenzia tutte le occorrenze in giallo.
    Enter va al match successivo, Shift+Enter al precedente.
    """

    def __init__(self, target_edit, parent=None, placeholder: str = None):
        """
        Args:
            target_edit: il QPlainTextEdit o QTextEdit su cui cercare
            parent: widget parent
            placeholder: testo placeholder (default generico)
        """
        super().__init__(parent)
        self.target = target_edit
        self._matches: list[QTextCursor] = []
        self._current_match: int = -1

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            placeholder or "🔍 Cerca nel contenuto…  (Enter = successivo, Shift+Enter = precedente)"
        )
        # font inline only — bg/border/colore dal tema app-level
        self.input.setStyleSheet("font-size:12px;")
        # Campo ricerca minimo ~30 caratteri (non collassa sotto quella soglia)
        self.input.setMinimumWidth(320)
        self.input.textChanged.connect(self._on_text_changed)
        self.input.returnPressed.connect(self._on_enter)
        lay.addWidget(self.input, stretch=1)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(30, 30)
        self.clear_btn.setToolTip("Cancella ricerca")
        # stile default dal tema (QPushButton)
        self.clear_btn.clicked.connect(self.clear)
        lay.addWidget(self.clear_btn)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("font-size:11px; padding:0 4px;")
        from GUI.theme.theme import set_prop as _tp
        _tp(self.count_lbl, "role", "muted")
        self.count_lbl.setMinimumWidth(80)
        self.count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.count_lbl)

    # ──────────────────────────────────────────────────────────────────
    # Handler
    # ──────────────────────────────────────────────────────────────────
    def _on_text_changed(self, text: str):
        query = text.strip()
        if not query:
            self._clear_highlights()
            self._matches = []
            self._current_match = -1
            self.count_lbl.setText("")
            return
        self._search(query)

    def _on_enter(self):
        """Enter = match successivo, Shift+Enter = precedente."""
        # In PyQt6, QLineEdit non ha modifiers(); usiamo QGuiApplication
        from PyQt6.QtGui import QGuiApplication
        mods = QGuiApplication.keyboardModifiers()
        if mods & Qt.KeyboardModifier.ShiftModifier:
            self._goto_match(self._current_match - 1)
        else:
            self._goto_match(self._current_match + 1)

    # ──────────────────────────────────────────────────────────────────
    # Ricerca + evidenziazione
    # ──────────────────────────────────────────────────────────────────
    def _search(self, query: str):
        """Trova tutte le occorrenze di query e le evidenzia."""
        doc = self.target.document()
        cursor = QTextCursor(doc)
        new_matches: list[QTextCursor] = []
        # find() ritorna un nuovo cursor con la selezione, o invalido
        flags = QTextDocument.FindFlag(0)
        while not cursor.isNull():
            cursor = doc.find(query, cursor, flags)
            if cursor.isNull():
                break
            new_matches.append(QTextCursor(cursor))

        self._matches = new_matches
        self._apply_highlights()

        if new_matches:
            self._current_match = 0
            self._goto_match(0)
            self.count_lbl.setText(
                f"<b style='color:#16a34a;'>1</b>/{len(new_matches)}"
            )
        else:
            self._current_match = -1
            self.count_lbl.setText(
                f"<b style='color:#dc2626;'>0</b> risultati"
            )

    def _apply_highlights(self):
        """Evidenzia tutti i match con setExtraSelections (non modifica il testo)."""
        # Formato per i match non correnti (giallo chiaro)
        fmt_all = QTextCharFormat()
        fmt_all.setBackground(QColor("#fef08a"))  # giallo chiaro
        # Formato per il match corrente (arancione)
        fmt_current = QTextCharFormat()
        fmt_current.setBackground(QColor("#fb923c"))  # arancione
        fmt_current.setForeground(QColor("#ffffff"))

        selections = []
        for i, cursor in enumerate(self._matches):
            # ExtraSelection è una classe annidata di QTextEdit in PyQt6
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt_current if i == self._current_match else fmt_all
            selections.append(sel)
        self.target.setExtraSelections(selections)

    def _goto_match(self, idx: int):
        """Scorre fino al match indicato e lo marca come corrente."""
        if not self._matches:
            return
        # Wrap around
        n = len(self._matches)
        idx = idx % n
        self._current_match = idx
        self._apply_highlights()
        cursor = self._matches[idx]
        # Scorri la vista sul cursore
        self.target.setTextCursor(cursor)
        self.target.ensureCursorVisible()
        self.count_lbl.setText(
            f"<b style='color:#16a34a;'>{idx + 1}</b>/{n}"
        )

    def _clear_highlights(self):
        """Rimuove tutte le evidenziazioni."""
        self.target.setExtraSelections([])

    # ──────────────────────────────────────────────────────────────────
    # API pubblica
    # ──────────────────────────────────────────────────────────────────
    def clear(self):
        """Cancella la ricerca."""
        self.input.clear()
        self.input.setFocus()

    def reapply(self):
        """Riapplica la ricerca corrente (utile dopo che il contenuto è cambiato).

        Chiamare questo metodo dopo che il target_edit è stato modificato
        (es. dopo self.output.clear() + appendPlainText(...)).
        """
        text = self.input.text().strip()
        if text:
            self._search(text)


def make_search_bar(target_edit, parent=None, placeholder: str = None) -> SearchBar:
    """Factory function: crea una SearchBar per il target indicato.

    Uso:
        from GUI.search_bar import make_search_bar
        bar = make_search_bar(self.output, parent=self)
        lay.addWidget(bar)
        # Salva il riferimento se vuoi riapplicare dopo aver aggiornato il contenuto:
        self.search_bar = bar
    """
    return SearchBar(target_edit, parent=parent, placeholder=placeholder)
