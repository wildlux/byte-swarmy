---
id: pyqt6-gui-window
title: PyQt6 desktop GUI window (single file)
keywords: gui, finestra, window, pyqt, qt, interfaccia, grafica, desktop, pulsante, pulsanti, bottone, bottoni, click, clic, label, campo, testo, form, app grafica
---
# Recipe: PyQt6 desktop window

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders.
3. Wire the widgets inside the {{ LOGIC }} section only.
4. Call lint_code("main.py") to verify it compiles.
5. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import sys

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
)


def main():
    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("{{ WINDOW TITLE }}")
    lay = QVBoxLayout(win)
    # {{ WIDGETS: add QLabel / QLineEdit / QPushButton as needed }}
    # {{ LOGIC: connect button.clicked to a function that updates a QLabel }}

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. PyQt6 widgets only.
- Use app.exec() — NEVER app.exec_().
- Call win.show() BEFORE app.exec().
- NO external assets, NO .ui files, NO threads, NO stylesheets unless asked.

DONE WHEN:
- project/main.py exists and lint_code passes.
- Launching it would open the window with the requested widgets.
