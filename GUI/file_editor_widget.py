"""
GUI/file_editor_widget.py — Editor di file dockabile con salvataggio e rinomina.

Estratto da GUI/control_center.py (classe FileEditorWidget).
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout,
)

# _click_log è definito in control_center.py; lo importiamo in modo
# sicuro per evitare dipendenze circolari. Se non disponibile, si usa un no-op.
try:
    from GUI.control_center import _click_log  # type: ignore
except Exception:  # pragma: no cover
    def _click_log(*args, **kwargs):  # type: ignore
        pass


class FileEditorWidget(QFrame):
    """Editor di file con header (nome, dock, salva, chiudi) e area di testo.

    Segnali:
        closed()           — l'editor è stato chiuso (ESC o ✕).
        dock_requested()   — richiesto aggancio al pannello principale.
        undock_requested() — richiesto sgancio dal pannello principale.
    """

    closed = pyqtSignal()
    dock_requested = pyqtSignal()
    undock_requested = pyqtSignal()

    def __init__(self, file_path, docked=False, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._docked = docked
        self.setObjectName("editor_widget")

        if not docked:
            self.setMinimumSize(420, 320)
            self.setStyleSheet("QFrame#editor_widget { border-radius:12px; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # ── Header: solo icona + nome file (i pulsanti stanno in basso) ──
        head = QHBoxLayout()
        head.addWidget(QLabel(f"<b>📝</b>"))

        # Nome file modificabile (QLineEdit invece di QLabel statico)
        self.file_name_edit = QLineEdit(os.path.basename(file_path))
        self.file_name_edit.setObjectName("editor_filename")
        self.file_name_edit.setMinimumWidth(220)
        self.file_name_edit.setStyleSheet(
            "QLineEdit#editor_filename { font-weight:bold; font-size:12px; "
            "border:1px solid #363d4a; border-radius:4px; padding:2px 8px; "
            "background:#f8fafc; }"
            "QLineEdit#editor_filename:focus { border-color:#5b92ff; }"
        )
        self.file_name_edit.returnPressed.connect(self._rename_file)
        head.addWidget(self.file_name_edit)
        head.addStretch()
        lay.addLayout(head)

        self.path_lbl = QLabel(file_path)
        self.path_lbl.setStyleSheet("font-size:10px; font-family:monospace;")
        lay.addWidget(self.path_lbl)

        self.editor = QTextEdit()
        self.editor.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; font-size:12px; padding:8px;"
        )
        # ESC chiude l'editor anche quando il focus è sul campo di testo
        self.editor.installEventFilter(self)
        lay.addWidget(self.editor)

        # ── Barra pulsanti in basso: Salva / Dock / Chiudi ──
        foot = QHBoxLayout()
        foot.addStretch()  # pulsanti allineati a destra

        save_btn = QPushButton("💾 Salva")
        save_btn.setObjectName("primary_btn")
        save_btn.setMinimumHeight(28)
        save_btn.clicked.connect(self._save)
        foot.addWidget(save_btn)

        self.dock_btn = QPushButton("📌 Dock" if not docked else "📌 Undock")
        self.dock_btn.setMinimumHeight(28)
        self.dock_btn.setObjectName("dock_btn")
        self.dock_btn.setStyleSheet(
            "QPushButton#dock_btn { background:#2563eb; color:white; border-radius:4px; font-size:11px; padding:0 10px; border:none; }"
            "QPushButton#dock_btn:hover { background:#1d4ed8; }"
        )
        self.dock_btn.clicked.connect(self._on_dock_toggle)
        foot.addWidget(self.dock_btn)

        close_btn = QPushButton("✕ Chiudi")
        close_btn.setObjectName("editor_close_btn")
        close_btn.setMinimumHeight(28)
        close_btn.setStyleSheet(
            "QPushButton#editor_close_btn { background:#e2e8f0; color:#1f2430; "
            "border:none; border-radius:4px; font-size:11px; padding:0 10px; }"
            "QPushButton#editor_close_btn:hover { background:#fecaca; color:#991b1b; }"
        )
        close_btn.clicked.connect(self.closed.emit)
        foot.addWidget(close_btn)
        lay.addLayout(foot)

        self.status = QLabel("Pronto")
        self.status.setStyleSheet("font-size:11px;")
        lay.addWidget(self.status)

        self._load_file()

    def eventFilter(self, obj, event):
        if obj is self.editor and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.closed.emit()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """ESC chiude l'editor overlay."""
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
            return
        super().keyPressEvent(event)

    def _on_dock_toggle(self):
        if self._docked:
            self.undock_requested.emit()
        else:
            self.dock_requested.emit()

    def _rename_file(self):
        """Rinomina il file aperto quando l'utente preme Invio sul nome."""
        import shutil

        new_name = self.file_name_edit.text().strip()
        if not new_name or new_name == os.path.basename(self.file_path):
            return

        # Sanitizza: niente path traversal
        new_name = os.path.basename(new_name.replace("/", os.sep).replace("\\", os.sep))
        if not new_name or new_name in (".", ".."):
            QMessageBox.warning(self, "Nome non valido", "Inserisci un nome di file valido.")
            self.file_name_edit.setText(os.path.basename(self.file_path))
            return

        dir_path = os.path.dirname(self.file_path)
        new_path = os.path.join(dir_path, new_name)

        if os.path.exists(new_path):
            ans = QMessageBox.question(
                self, "Esiste già",
                f"Il file '{new_name}' esiste già.\nSovrascrivere?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                self.file_name_edit.setText(os.path.basename(self.file_path))
                return

        try:
            os.rename(self.file_path, new_path)
            self.file_path = new_path
            # Aggiorna il path mostrato sotto l'header
            try:
                self.path_lbl.setText(new_path)  # type: ignore[attr-defined]
            except Exception:
                pass
            self.status.setText(f"Rinominato in '{new_name}'")
            _click_log(
                "filemanager", "rinomina",
                self.parent().get_current_project_path() if self.parent() else "",
                f"{os.path.basename(self.file_path)} → {new_name}",
            )
            # Refresh del file tree per far apparire il nuovo nome
            try:
                if self.parent() and hasattr(self.parent(), 'drawer'):
                    self.parent().drawer._refresh_file_tree()  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile rinominare il file:\n{e}")
            self.file_name_edit.setText(os.path.basename(self.file_path))

    def _load_file(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                self.editor.setPlainText(f.read())
            self.status.setText(
                f"Caricato · {len(self.editor.toPlainText())} caratteri"
            )
        except Exception as e:
            self.editor.setPlainText(f"[Errore lettura: {e}]")
            self.status.setText("Errore")

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.status.setText(
                f"✓ Salvato · {len(self.editor.toPlainText())} caratteri"
            )
        except Exception as e:
            self.status.setText(f"✕ Errore: {e}")
