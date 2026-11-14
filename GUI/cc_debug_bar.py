"""GUI/cc_debug_bar.py — Barra di debug GUI (widget sotto il mouse).

Estratto da GUI/control_center.py (R3): attivazione/disattivazione della
barra info-widget e timer di aggiornamento. Mixin: comportamento invariato.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QLabel


class DebugBarMixin:
    def _on_gui_debug_changed(self, enabled: bool):
        """Attiva/disattiva la barra di debug info-widget (delega da CenterArea)."""
        self._gui_debug = bool(enabled)
        if self._gui_debug:
            self._install_debug_bar()
        else:
            self._remove_debug_bar()

    def _install_debug_bar(self):
        """Aggiunge la barra copiabile in basso alla statusBar."""
        if self._debug_label is not None:
            return
        self._debug_label = QLabel(
            "Debug GUI attivo — passa il mouse su un elemento per vedere classe e gerarchia"
        )
        self._debug_label.setObjectName("debug_status_label")
        self._debug_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._debug_label.setToolTip(
            "Testo selezionabile e copiabile. Incollalo quando segnali un bug allo sviluppatore."
        )
        self._debug_label.setStyleSheet(
            "QLabel#debug_status_label { "
            "border:1px solid; border-radius:4px; padding:4px 8px; "
            "font-family:'JetBrains Mono','Consolas',monospace; font-size:11px; "
            "}"
        )
        self._debug_label.setWordWrap(True)
        self._debug_label.setMaximumWidth(700)
        self.statusBar().addPermanentWidget(self._debug_label)
        # Timer che controlla periodicamente il widget sotto il mouse
        self._debug_timer = QTimer(self)
        self._debug_timer.timeout.connect(self._debug_timer_tick)
        self._debug_timer.start(200)

    def _remove_debug_bar(self):
        """Rimuove la barra di debug e ferma il timer."""
        if hasattr(self, '_debug_timer') and self._debug_timer is not None:
            self._debug_timer.stop()
            self._debug_timer = None
        if self._debug_label is not None:
            try:
                self.statusBar().removeWidget(self._debug_label)
            except Exception:
                pass
            self._debug_label.deleteLater()
            self._debug_label = None

    def _debug_timer_tick(self):
        """Tick periodico: aggiorna la barra con il widget sotto il mouse."""
        if not self._gui_debug or self._debug_label is None:
            return
        widget = QApplication.widgetAt(QCursor.pos())
        if widget is not None:
            self._update_debug_bar(widget)
        else:
            self._debug_label.setText("")

    def _widget_info_text(self, widget) -> str:
        """Costruisce il testo informativo su un widget (classe, gerarchia, stack)."""
        import inspect, os as _os
        lines = []
        cls = widget.__class__
        lines.append(f"Widget sotto il mouse:")
        lines.append(f"  Classe: {cls.__name__}")
        mro = [c.__name__ for c in cls.__mro__]
        lines.append(f"  MRO: {' → '.join(mro)}")
        oname = widget.objectName()
        lines.append(f"  objectName: '{oname}'")
        geo = widget.geometry()
        lines.append(
            f"  Geometria: x={geo.x()} y={geo.y()} w={geo.width()} h={geo.height()}"
        )
        # Gerarchia genitori
        parts = []
        w = widget
        while w is not None:
            name = w.objectName() or w.__class__.__name__
            parts.append(f"{w.__class__.__name__}#{name}")
            w = w.parentWidget()
        lines.append(f"  Gerarchia: {' > '.join(reversed(parts))}")
        # Stack trace (frame utili, salta i primi 3 di questo metodo/eventFilter)
        try:
            stack = inspect.stack()
            relevant = []
            for frame in stack[3:9]:
                fname = _os.path.basename(frame.filename)
                relevant.append(f"    {fname}:{frame.lineno} in {frame.function}")
            if relevant:
                lines.append(f"  Stack chiamate (ultimi):")
                lines.extend(relevant)
        except Exception:
            pass
        return "\n".join(lines)

    def _update_debug_bar(self, widget):
        """Aggiorna il testo della barra di debug con info sul widget."""
        if self._debug_label is None:
            return
        try:
            text = self._widget_info_text(widget)
            self._debug_label.setText(text)
        except Exception as e:
            self._debug_label.setText(f"Errore lettura widget: {e}")
