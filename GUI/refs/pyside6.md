# PySide6 — cheat sheet (byte-swarmy)

PySide6 è il binding ufficiale Qt (LGPL). **API quasi identica a PyQt6**
ma con differenze importanti su segnali, licenza e strumenti.

## App minima
```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton

app = QApplication(sys.argv)
win = QMainWindow()
central = QWidget()
win.setCentralWidget(central)
lay = QVBoxLayout(central)
label = QLabel("0")
btn = QPushButton("Incrementa")
lay.addWidget(label)
lay.addWidget(btn)
win.show()
sys.exit(app.exec())
```

## Differenze chiave vs PyQt6

| Aspetto | PyQt6 | PySide6 |
|---|---|---|
| Licenza | GPL/Commercial | LGPL (più permissiva) |
| Segnali custom | `pyqtSignal` | `Signal` (da `PySide6.QtCore`) |
| Slot | `pyqtSlot` | `Slot` |
| Enum | `Qt.AlignmentFlag.AlignCenter` | `Qt.AlignmentFlag.AlignCenter` (stesso) |
| `app.exec()` | `app.exec()` (no underscore) | `app.exec()` (stesso) |
| Designer | Qt Designer (ui→py con pyuic6) | Qt Designer (ui→py con pyside6-uic) |
| Threading | `QThread` + `pyqtSignal` | `QThread` + `Signal` |
| Wheel Python 3.14 | Sì (PyQt6>=6.6) | Verificare disponibilità |

## Segnali custom (PySide6)
```python
from PySide6.QtCore import QObject, Signal, Slot

class Worker(QObject):
    done = Signal(str)          # <-- Signal, non pyqtSignal
    @Slot()
    def run(self):
        self.done.emit("fatto")
```

## Threading
```python
from PySide6.QtCore import QThread, Signal

class Worker(QThread):
    done = Signal(str)
    def run(self):
        self.done.emit("fatto")

w = Worker()
w.done.connect(lambda r: label.setText(r))
w.start()
```

## Tool di conversione UI
- `pyside6-uic form.ui -o form_ui.py` (invece di `pyuic6`)
- `pyside6-rcc resources.qrc -o resources_rc.py`

## Offscreen (test)
```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
app = QApplication([])
```

## Errori comuni (specifici PySide6)
- Usare `pyqtSignal`/`pyqtSlot` → non esistono in PySide6 (usa `Signal`/`Slot`)
- Importare `PyQt6` invece di `PySide6` → ModuleNotFoundError
- Mescolare PyQt6 e PySide6 nello stesso progetto → conflitti ABI
- `app.exec_()` deprecato → usa `app.exec()`

## Quando scegliere PySide6 vs PyQt6
- **PySide6**: licenza LGPL (app commerciali senza fee), binding ufficiale Qt
- **PyQt6**: più maturo, community più ampia, già usato in byte-swarmy (VENTOLA)
- **Regola byte-swarmy**: PyQt6 di default (ha wheel per Python 3.14, PySide6 no al momento)
