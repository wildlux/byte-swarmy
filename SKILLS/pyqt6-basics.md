---
id: pyqt6-basics
title: PyQt6 basic app (single file)
keywords: pyqt6, qt, gui, finestra, window, widget, app, QApplication, QMainWindow, QPushButton, QLabel, qthread, qthreadpool, thread
---
# Recipe: PyQt6 basic app (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel,
)
from PyQt6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("{{ TITLE }}")
        self.setGeometry(100, 100, 400, 300)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.label = QLabel("{{ INITIAL TEXT }}")
        layout.addWidget(self.label)

        btn = QPushButton("{{ BUTTON TEXT }}")
        btn.clicked.connect(self.on_click)
        layout.addWidget(btn)

    def on_click(self):
        self.label.setText("{{ CLICKED TEXT }}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    # In test mode, exit immediately
    print("{{ MARKER }}=ok")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library + PyQt6 only.
- ALWAYS import from PyQt6.QtWidgets, PyQt6.QtCore, PyQt6.QtGui.
- NEVER use `from PyQt5` or `from PySide2` — only PyQt6.
- The entry point is `QApplication(sys.argv)` then `window.show()` then `sys.exit(app.exec())`.
- In test mode (no display), call sys.exit(0) after showing.
- Replace EVERY {{...}} placeholder with real code.