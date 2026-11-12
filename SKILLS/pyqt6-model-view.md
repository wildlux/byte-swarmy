---
id: pyqt6-model-view
title: PyQt6 model-view (QAbstractTableModel) (single file)
keywords: model, view, QAbstractTableModel, QTableView, QAbstractListModel, QListView, QSortFilterProxyModel, modello, vista, tabella, lista
---
# Recipe: PyQt6 model-view (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import sys
from PyQt6.QtWidgets import QApplication, QTableView, QWidget, QVBoxLayout
from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QColor


class {{ MODEL NAME }}(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data or []

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._data[0]) if self._data else 0

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._data[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return f"Col {section}"
        return None


def main():
    app = QApplication(sys.argv)
    model = {{ MODEL NAME }}([["a", "b"], ["c", "d"]])
    view = QTableView()
    view.setModel(model)
    view.show()
    print("ROWS=2")
    print("COLS=2")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library + PyQt6 only.
- ALWAYS import from PyQt6.QtWidgets, PyQt6.QtCore, PyQt6.QtGui.
- NEVER use PyQt5 or PySide2 — only PyQt6.
- QAbstractTableModel requires: rowCount, columnCount, data, headerData.
- The entry point is `QApplication(sys.argv)` then `view.show()` then `sys.exit(0)` for test mode.
- In test mode (no display), call sys.exit(0) after showing.
- Replace EVERY {{...}} placeholder with real code.