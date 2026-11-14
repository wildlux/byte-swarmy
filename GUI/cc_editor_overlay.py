"""GUI/cc_editor_overlay.py — Editor file overlay/docked.

Estratto da GUI/control_center.py (R3): apertura editor flottante,
dock/undock nella colonna centrale. Mixin: comportamento invariato.
"""

from __future__ import annotations

from GUI.file_editor_widget import FileEditorWidget


class EditorOverlayMixin:
    def _show_file_editor(self, file_path):
        if self._editor_docked:
            self._editor_docked.file_path = file_path
            self._editor_docked._load_file()
            self.center.code_explorer.load_file(file_path)
            return

        if self._editor_overlay:
            self._editor_overlay.close()
            self._editor_overlay.deleteLater()

        self._editor_overlay = FileEditorWidget(file_path, docked=False, parent=self.centralWidget())
        self._editor_overlay.closed.connect(self._close_overlay)
        self._editor_overlay.dock_requested.connect(lambda: self._dock_editor(file_path))

        # Ridimensiona l'overlay editor in percentuale della finestra centrale
        # (come CreditsOverlay): non esce mai dai bordi, si adatta a massimizza/riduci.
        cw = self.centralWidget().size()
        ew = max(420, int(cw.width() * 0.55))
        eh = max(320, int(cw.height() * 0.55))
        self._editor_overlay.resize(ew, eh)
        self._editor_overlay.move(
            max(12, (cw.width() - ew) // 2),
            max(12, (cw.height() - eh) // 2),
        )
        self._editor_overlay.show()
        self._editor_overlay.raise_()

        self.center.code_explorer.load_file(file_path)

    def _close_overlay(self):
        if self._editor_overlay:
            self._editor_overlay.deleteLater()
            self._editor_overlay = None

    def _dock_editor(self, file_path):
        self._close_overlay()
        self._editor_docked = FileEditorWidget(file_path, docked=True)
        self._editor_docked.closed.connect(self._undock_editor)
        self._editor_docked.undock_requested.connect(lambda: self._undock_editor_to_float(file_path))
        self.center.attach_editor_column(self._editor_docked)

    def _undock_editor(self):
        if self._editor_docked:
            self.center.detach_editor_column()
            self._editor_docked.deleteLater()
            self._editor_docked = None

    def _undock_editor_to_float(self, file_path):
        self.center.detach_editor_column()
        self._editor_docked.deleteLater()
        self._editor_docked = None
        self._show_file_editor(file_path)
