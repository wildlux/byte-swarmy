#!/usr/bin/env python3
"""
live_log_viewer.py - Mostra i log di byte-swarmy in tempo reale.
Utile per capire cosa sta facendo l'orchestratore mentre la GUI sembra ferma.
"""
from __future__ import annotations

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer


class LiveLogViewer(QMainWindow):
    def __init__(self, log_path: str = "logs/byte-swarmy.log"):
        super().__init__()
        self.setWindowTitle("BYTE-SWARMY - Log in tempo reale")
        self.setGeometry(100, 100, 1000, 700)

        self.log_path = Path(log_path)
        self.file_position = 0

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Header
        header = QHBoxLayout()
        self.status_label = QLabel(f"Monitoraggio: {self.log_path}")
        self.status_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.status_label)
        header.addStretch()

        self.auto_scroll_btn = QPushButton("Auto-scroll: ON")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.clicked.connect(self.toggle_auto_scroll)
        header.addWidget(self.auto_scroll_btn)

        self.clear_btn = QPushButton("Cancella visuale")
        self.clear_btn.clicked.connect(self.clear_view)
        header.addWidget(self.clear_btn)

        layout.addLayout(header)

        # Area testo
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet(
            "QTextEdit {"
            "  font-family: 'Courier New', monospace;"
            "  font-size: 11px;"
            "  background-color: #1e1e1e;"
            "  color: #d4d4d4;"
            "}"
        )
        layout.addWidget(self.text_edit)

        # Timer per aggiornamento ogni 500ms
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_new_lines)
        self.timer.start(500)

        # Carica contenuto esistente
        self.load_existing()

    def load_existing(self):
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="replace")
            self.text_edit.setPlainText(content)
            self.file_position = self.log_path.stat().st_size
            self.text_edit.verticalScrollBar().setValue(
                self.text_edit.verticalScrollBar().maximum()
            )
        except FileNotFoundError:
            self.text_edit.setPlainText(f"File di log non trovato: {self.log_path}")
        except Exception as e:
            self.text_edit.setPlainText(f"Errore: {e}")

    def check_new_lines(self):
        try:
            current_size = self.log_path.stat().st_size
            if current_size < self.file_position:
                self.load_existing()
                return
            if current_size > self.file_position:
                with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self.file_position)
                    new_content = f.read()
                    self.file_position = f.tell()
                if new_content:
                    self.text_edit.appendPlainText(new_content)
                    if self.auto_scroll_btn.isChecked():
                        self.text_edit.verticalScrollBar().setValue(
                            self.text_edit.verticalScrollBar().maximum()
                        )
        except Exception:
            pass

    def toggle_auto_scroll(self):
        self.auto_scroll_btn.setText(
            "Auto-scroll: ON" if self.auto_scroll_btn.isChecked() else "Auto-scroll: OFF"
        )

    def clear_view(self):
        self.text_edit.clear()
        self.file_position = 0


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LiveLogViewer()
    window.show()
    sys.exit(app.exec())