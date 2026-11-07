# -*- coding: utf-8 -*-
"""
tests/test_keys.py — test sugli eventi da tastiera (tasti fisici simulati).

Verifica che ogni tasto con "evento fake" gestito dalla GUI risponda
correttamente:

1. Backspace su ricerca globale VUOTA → torna alla Plancia (back_to_main)
2. Backspace su ricerca globale CON TESTO → cancella carattere, non torna indietro
3. ESC sui Credits overlay → chiude l'overlay
4. ESC sull'editor overlay → chiude l'editor (closed.emit)
5. Invio su ricerca con un solo match → apre direttamente quel pannello
6. "/" → porta il focus sul campo comando in basso (cmd_input)

Esecuzione (offscreen, nessuna finestra visibile):
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_keys.py -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import QEvent, Qt as _Qt, QModelIndex  # noqa: E402
from PyQt6.QtGui import QKeyEvent  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402

from GUI.control_center import ControlCenter, FileEditorWidget  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv[:1] + ["test_keys"])

_WIN = None


def _window() -> ControlCenter:
    """Istanza singola condivisa tra i test."""
    global _WIN
    if _WIN is None:
        _WIN = ControlCenter()
        _WIN.show()
        _app.processEvents()
    return _WIN


def _key(key: _Qt.Key, modifiers=_Qt.KeyboardModifier.NoModifier) -> QKeyEvent:
    """Costruisce un QKeyEvent KeyPress da iniettare nell'event filter."""
    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)


class TestBackspaceOnEmptySearch(unittest.TestCase):
    """Backspace su ricerca vuota → torna alla Plancia."""

    def test_backspace_empty_search_goes_back(self):
        win = _window()
        win.center.open_panel("coda")  # esci dalla plancia
        _app.processEvents()
        self.assertEqual(win.center.main_stack.currentIndex(), 1)

        # focus sulla ricerca globale (vuota) + Backspace
        win.center.global_search.setFocus()
        _app.processEvents()
        ev = _key(_Qt.Key.Key_Backspace)
        win.center.eventFilter(win.center, ev)
        _app.processEvents()

        self.assertEqual(
            win.center.main_stack.currentIndex(), 0,
            "Backspace su ricerca vuota deve tornare alla Plancia",
        )


class TestBackspaceOnNonEmptySearch(unittest.TestCase):
    """Backspace su ricerca con testo → cancella, non torna indietro."""

    def test_backspace_with_text_stays_on_panel(self):
        win = _window()
        win.center.open_panel("coda")
        _app.processEvents()
        self.assertEqual(win.center.main_stack.currentIndex(), 1)

        win.center.global_search.setFocus()
        win.center.global_search.setText("prova")
        _app.processEvents()

        # QTest.keyClick fa passare l'evento attraverso l'event filter
        # (che restituisce False con testo) e arriva al QLineEdit che cancella.
        QTest.keyClick(win.center.global_search, _Qt.Key.Key_Backspace)
        _app.processEvents()

        self.assertEqual(
            win.center.global_search.text(), "prov",
            "Backspace deve cancellare l'ultimo carattere",
        )
        self.assertEqual(
            win.center.main_stack.currentIndex(), 1,
            "Backspace con testo non deve tornare alla Plancia",
        )


class TestEscClosesCredits(unittest.TestCase):
    """ESC sui Credits overlay → chiude l'overlay."""

    def test_esc_closes_credits_overlay(self):
        win = _window()
        win._show_credits()
        _app.processEvents()
        self.assertIsNotNone(win._credits_overlay, "overlay crediti deve esistere")

        ev = _key(_Qt.Key.Key_Escape)
        win.center.eventFilter(win.center, ev)
        _app.processEvents()

        self.assertIsNone(
            win._credits_overlay, "ESC deve chiudere i ringraziamenti",
        )


class TestEscClosesEditor(unittest.TestCase):
    """ESC sull'editor overlay → chiude l'editor (closed.emit)."""

    def test_esc_closes_file_editor(self):
        win = _window()
        closed = []

        editor = FileEditorWidget("project/README.md", docked=False, parent=win)
        editor.closed.connect(lambda: closed.append(True))
        _app.processEvents()

        ev = _key(_Qt.Key.Key_Escape)
        editor.keyPressEvent(ev)
        _app.processEvents()

        self.assertTrue(closed, "ESC sull'editor deve emettere closed")


class TestEnterSingleMatchOpensPanel(unittest.TestCase):
    """Invio su ricerca con un solo match → apre quel pannello."""

    def test_enter_single_match_opens_panel(self):
        win = _window()
        win.center.back_to_main()
        _app.processEvents()
        self.assertEqual(win.center.main_stack.currentIndex(), 0)

        # "configurazione" matcha solo la card "Configurazione"
        win.center.global_search.setText("configurazione")
        _app.processEvents()

        QTest.keyClick(win.center.global_search, _Qt.Key.Key_Return)
        _app.processEvents()

        self.assertEqual(
            win.center.main_stack.currentIndex(), 1,
            "Invio con singolo match deve aprire il pannello dettaglio",
        )
        self.assertIs(
            win.center.detail_stack.currentWidget(),
            win.center.panel_pages["config"],
            "pannello aperto deve essere 'config'",
        )


class TestSlashFocusesCommandInput(unittest.TestCase):
    """"/" → focus sul campo comando in basso."""

    def test_slash_focuses_cmd_input(self):
        win = _window()
        win.center.back_to_main()
        _app.processEvents()

        QTest.keyClick(win, _Qt.Key.Key_Slash)
        _app.processEvents()

        self.assertTrue(
            win.cmd_input.hasFocus(),
            "'/' deve portare il focus sul campo comando",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
