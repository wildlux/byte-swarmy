"""Test per lo zoom interfaccia (zoom_in, zoom_out, zoom_reset, keyPressEvent)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

from GUI.control_center import ControlCenter


class TestZoom:
    """Test dello zoom interfaccia."""

    def setup_method(self):
        """Crea un QApplication e una finestra ControlCenter per ogni test."""
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        self.window = ControlCenter()
        self.window.show()

    def teardown_method(self):
        """Chiude la finestra dopo ogni test.

        NB: processEvents serve a eseguire il deleteLater schedulato da
        closeEvent — senza event loop attivo i widget della finestra
        chiusa resterebbero in QApplication.allWidgets() e ogni _apply_zoom
        dei test successivi rallenterebbe (unpolish/polish cumulativo).
        """
        self.window.close()
        QApplication.processEvents()
        self.window = None

    def _get_font_size(self) -> int:
        """Ritorna la dimensione font corrente dell'applicazione."""
        return self.app.font().pointSize()

    def test_zoom_in_aumenta_font(self):
        """zoom_in deve aumentare il font size dell'applicazione."""
        iniziale = self._get_font_size()
        self.window._zoom_in()
        attuale = self._get_font_size()
        assert attuale > iniziale, f"zoom_in non ha aumentato il font: {iniziale} -> {attuale}"
        assert self.window.gui_settings.zoom_level > 100

    def test_zoom_out_diminuisce_font(self):
        """zoom_out deve diminuire il font size dell'applicazione."""
        self.window._zoom_in()  # assicura spazio per diminuire
        prima = self._get_font_size()
        self.window._zoom_out()
        dopo = self._get_font_size()
        assert dopo < prima, f"zoom_out non ha diminuito il font: {prima} -> {dopo}"
        assert self.window.gui_settings.zoom_level < 200

    def test_zoom_reset_ripristina_100(self):
        """zoom_reset deve riportare il font alla dimensione di default."""
        self.window._zoom_in()
        self.window._zoom_in()
        self.window._zoom_reset()
        assert self.window.gui_settings.zoom_level == 100
        assert self._get_font_size() == max(8, int(self.window.gui_settings.font_size * 100 / 100))

    def test_zoom_limite_massimo_200(self):
        """zoom_in non deve superare il 200%."""
        self.window.gui_settings.zoom_level = 190
        self.window._zoom_in()
        assert self.window.gui_settings.zoom_level == 200

    def test_zoom_limite_minimo_50(self):
        """zoom_out non deve scendere sotto il 50%."""
        self.window.gui_settings.zoom_level = 55
        self.window._zoom_out()
        assert self.window.gui_settings.zoom_level == 50

    def test_keypress_ctrl_plus_chiamata_zoom_in(self):
        """Ctrl++ deve chiamare _zoom_in tramite keyPressEvent."""
        self.window.gui_settings.zoom_level = 100
        from PyQt6.QtGui import QKeyEvent
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Plus,
            Qt.KeyboardModifier.ControlModifier,
            "+",
        )
        self.window.keyPressEvent(event)
        assert self.window.gui_settings.zoom_level > 100

    def test_keypress_ctrl_minus_chiamata_zoom_out(self):
        """Ctrl+- deve chiamare _zoom_out tramite keyPressEvent."""
        self.window.gui_settings.zoom_level = 120
        from PyQt6.QtGui import QKeyEvent
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Minus,
            Qt.KeyboardModifier.ControlModifier,
            "-",
        )
        self.window.keyPressEvent(event)
        assert self.window.gui_settings.zoom_level < 120

    def test_keypress_ctrl_0_chiamata_zoom_reset(self):
        """Ctrl+0 deve chiamare _zoom_reset tramite keyPressEvent."""
        self.window.gui_settings.zoom_level = 150
        from PyQt6.QtGui import QKeyEvent
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_0,
            Qt.KeyboardModifier.ControlModifier,
            "0",
        )
        self.window.keyPressEvent(event)
        assert self.window.gui_settings.zoom_level == 100

    def test_apply_zoom_modifica_font_app(self):
        """_apply_zoom deve modificare il font dell'applicazione QApplication."""
        self.window._apply_zoom(150)
        attuale = self._get_font_size()
        atteso = max(8, int(self.window.gui_settings.font_size * 150 / 100))
        assert attuale == atteso, f"font non applicato: {attuale} != {atteso}"

    def test_pulsanti_zoom_esistono(self):
        """I pulsanti fisici zoom devono esistere dopo l'avvio."""
        assert hasattr(self.window, "_zoom_in_btn")
        assert hasattr(self.window, "_zoom_out_btn")
        assert hasattr(self.window, "_zoom_reset_btn")

    def test_gui_settings_caricata(self):
        """Le preferenze GUI devono essere caricate da config.toml."""
        assert self.window.gui_settings.theme in ("dark", "light")
        assert self.window.gui_settings.zoom_level > 0
        assert self.window.gui_settings.font_size > 0
