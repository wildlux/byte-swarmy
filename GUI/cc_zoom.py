"""GUI/cc_zoom.py — Zoom dell'interfaccia (Ctrl++ / Ctrl+- / Ctrl+0).

Estratto da GUI/control_center.py (R3): riscalatura font-size, shortcut
da tastiera ed event filter globale. Mixin: comportamento invariato.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

_ZOOM_FS_RE = re.compile(r"(font-size\s*:\s*)(\d+(?:\.\d+)?)\s*(px|pt)")


def _zoom_scale_css(css: str, factor: float) -> str:
    """Riscala i font-size (px e pt) di un CSS con il fattore indicato."""
    def _scale(m):
        try:
            n = float(m.group(2)) * factor
        except Exception:
            n = float(m.group(2))
        n = max(6.0, n)
        return f"{m.group(1)}{n:.2f}{m.group(3)}"
    return _ZOOM_FS_RE.sub(_scale, css)


class _ZoomEventFilter(QObject):
    """Event filter globale per catturare Ctrl++ / Ctrl+-- / Ctrl+0
    anche quando il focus è su un widget figlio (QLineEdit, QTextEdit, ecc.)."""

    def __init__(self, window):
        super().__init__()
        self.window = window

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent, Qt
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier:
                if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                    self.window._zoom_in()
                    return True
                if key == Qt.Key.Key_Minus:
                    self.window._zoom_out()
                    return True
                if key == Qt.Key.Key_0:
                    self.window._zoom_reset()
                    return True
        return super().eventFilter(obj, event)


class ZoomMixin:
    def keyPressEvent(self, event):
        """Intercetta scorciatoie da tastiera per zoom e altre azioni."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeySequence
        key = event.key()
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._zoom_in()
                event.accept()
                return
            if key == Qt.Key.Key_Minus:
                self._zoom_out()
                event.accept()
                return
            if key == Qt.Key.Key_0:
                self._zoom_reset()
                event.accept()
                return
        super().keyPressEvent(event)

    def _persist_zoom(self, level: int):
        """Salva il livello zoom in CONFIG/settings.json (best effort)."""
        try:
            from GUI import settings_store as _settings_store_mod
            _settings_store_mod.set_zoom_level(level)
        except Exception:
            pass

    def _zoom_in(self):
        """Aumenta lo zoom dell'interfaccia."""
        try:
            print(f"DEBUG _zoom_in chiamato, livello attuale: {self.gui_settings.zoom_level}")
            new_level = min(200, self.gui_settings.zoom_level + 10)
            self.gui_settings.zoom_level = new_level
            self._persist_zoom(new_level)
            self._apply_zoom(new_level)
            print(f"DEBUG zoom applicato: {new_level}%")
        except Exception as e:
            print(f"Errore zoom in: {e}")

    def _zoom_out(self):
        """Riduce lo zoom dell'interfaccia."""
        try:
            new_level = max(50, self.gui_settings.zoom_level - 10)
            self.gui_settings.zoom_level = new_level
            print(f"DEBUG _zoom_out → {new_level}%")
            self._persist_zoom(new_level)
            self._apply_zoom(new_level)
            print(f"DEBUG zoom applicato: {new_level}%")
        except Exception as e:
            print(f"Errore zoom out: {e}")

    def _zoom_reset(self):
        """Reset zoom al valore default."""
        try:
            self.gui_settings.zoom_level = 100
            print("DEBUG _zoom_reset → 100%")
            self._persist_zoom(100)
            self._apply_zoom(100)
            print("DEBUG zoom applicato: 100%")
        except Exception as e:
            print(f"Errore zoom reset: {e}")

    def _apply_zoom(self, level: int):
        """Applica il livello zoom a tutta l'interfaccia.

        Il font-size e' hard-coded in decine di stylesheet inline per-widget
        (px) e nel tema QSS della finestra (pt): quei valori vittoriano su
        app.setFont() e sul QSS globale, quindi qui vengono RISCALATI.
        Strategia: cattura una base a 100% e riscala con fattore level/100.
        """
        try:
            from PyQt6.QtGui import QFont
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            factor = max(0.5, min(2.0, level / 100.0))

            font_size = max(8, int(self.gui_settings.font_size * level / 100))
            font = QFont()
            font.setPointSize(font_size)
            app.setFont(font)

            # 1) Riscala i font-size negli stylesheet INLINE dei widget.
            #    La base 100% viene catturata al primo incontro (il valore
            #    scritto nel codice e' sempre a 100%); ogni zoom riscala
            #    SEMPRE dalla base con fattore assoluto level/100.
            if not hasattr(app, "_zoom_base_styles"):
                app._zoom_base_styles = {}
            for widget in app.allWidgets():
                try:
                    ss = widget.styleSheet()
                    base = app._zoom_base_styles.setdefault(id(widget), ss) or ""
                    if "font-size" not in base:
                        continue
                    new_ss = _zoom_scale_css(base, factor)
                    if new_ss != ss:
                        widget.setStyleSheet(new_ss)
                except Exception:
                    pass

            # 2) QSS della MAIN WINDOW (tema + window_chrome): qui vive il
            #    tema (dark.qss ecc. con font-size in pt). Il suo CSS vince
            #    a parita' di specificita' sul QSS app-level, quindi
            #    va riscalato LUI: sempre dall'originale, niente drift.
            if not hasattr(self, "_zoom_original_stylesheet"):
                self._zoom_original_stylesheet = self.styleSheet()
            self.setStyleSheet(
                _zoom_scale_css(self._zoom_original_stylesheet, factor)
                + "\n" + self._zoom_qss(font_size)
            )

            # 3) QSS app-level per i popup TOP-LEVEL (QMenu, tooltip di
            #    sistema) che NON ereditano il QSS della finestra: senza
            #    questo i menu contestuali restano al font base.
            app.setStyleSheet(self._zoom_qss(font_size))

            # 4) Forza repaint e polizia stile di tutti i widget
            for widget in app.allWidgets():
                try:
                    widget.font().setPointSize(font_size)
                    widget.update()
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                except Exception:
                    pass

            # Aggiorna larghezza minima pannello sinistro in base allo zoom,
            # così le etichette ("Lavori", "Svuota coda") non vengono tagliate.
            if hasattr(self, "drawer"):
                self.drawer.setMinimumWidth(max(260, int(300 * factor)))

            # Aggiorna tooltip pulsanti ed etichetta percentuale
            if hasattr(self, "_zoom_in_btn"):
                self._zoom_in_btn.setToolTip(f"Aumenta zoom (Ctrl++) — {level}%")
                self._zoom_out_btn.setToolTip(f"Riduci zoom (Ctrl+−) — {level}%")
                self._zoom_reset_btn.setToolTip(f"Reset vista (Ctrl+0) — {level}%")
            if hasattr(self, "_zoom_level_lbl"):
                self._zoom_level_lbl.setText(f"{level}%")
        except Exception as e:
            print(f"Errore applicazione zoom: {e}")

    def _zoom_qss(self, font_size: int) -> str:
        """QSS globale che estende il font-size ai widget senza stile inline."""
        return f"""
                QWidget {{ font-size: {font_size}px; }}
                QPushButton {{ font-size: {font_size}px; }}
                QLabel {{ font-size: {font_size}px; }}
                QTextEdit {{ font-size: {font_size}px; }}
                QPlainTextEdit {{ font-size: {font_size}px; }}
                QListWidget {{ font-size: {font_size}px; }}
                QTreeView {{ font-size: {font_size}px; }}
                QLineEdit {{ font-size: {font_size}px; }}
                QComboBox {{ font-size: {font_size}px; }}
                QSpinBox {{ font-size: {font_size}px; }}
                QSlider {{ font-size: {font_size}px; }}
                QProgressBar {{ font-size: {font_size}px; }}
                QTabBar::tab {{ font-size: {font_size}px; }}
                QHeaderView::section {{ font-size: {font_size}px; }}
            """

    def _rescale_missing_widgets(self):
        """Zoom: scala i widget creati DOPO l'ultimo zoom.

        I pannelli aperti dopo uno zoom (Impostazioni, Attori, Coda, sezioni
        CPU/GPU ricreate, dialog) nascono con gli stylesheet inline a base
        100%: senza questo passaggio restano al font piccolissimo finch'e
        l'utente non re-zooma. Passaggio leggero: tocca SOLO i widget nuovi
        (stili invariati non vengono riscritti, quindi zero flicker).
        """
        try:
            level = self.gui_settings.zoom_level
        except Exception:
            return
        if level == 100:
            return
        app = QApplication.instance()
        if app is None:
            return
        base_styles = getattr(app, "_zoom_base_styles", None)
        if base_styles is None:
            return  # zoom non ancora applicato: _apply_zoom gira all'avvio
        factor = max(0.5, min(2.0, level / 100.0))
        for widget in app.allWidgets():
            try:
                ss = widget.styleSheet()
                base = base_styles.setdefault(id(widget), ss) or ""
                if "font-size" not in base:
                    continue
                new_ss = _zoom_scale_css(base, factor)
                if new_ss != ss:
                    widget.setStyleSheet(new_ss)
            except Exception:
                pass
