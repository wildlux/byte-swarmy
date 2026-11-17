# PyQt6 — cheat sheet (byte-swarmy)

## App minima
```python
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton

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

## Widget comuni
- `QLabel(text)` — testo statico
- `QPushButton(text)` — pulsante; `.clicked.connect(fn)`
- `QLineEdit()` — campo testo; `.text()` per leggere
- `QSpinBox()` / `QDoubleSpinBox()` — numerico
- `QComboBox()` — dropdown; `.addItem()`, `.currentText()`
- `QCheckBox(text)` — checkbox; `.isChecked()`
- `QTableWidget(rows, cols)` — tabella
- `QTextEdit()` — testo multilinea

## Layout
- `QVBoxLayout` / `QHBoxLayout` — verticali/orizzontali
- `QGridLayout` — griglia
- `QFormLayout` — etichetta+campo
- `layout.addWidget(w)` / `layout.addLayout(l)`

## Segnali
```python
btn.clicked.connect(handler)          # click
line_edit.textChanged.connect(fn)     # cambio testo
combo.currentIndexChanged.connect(fn)  # cambio selezione
```

## Threading (NON bloccare la GUI)
```python
from PyQt6.QtCore import QThread, pyqtSignal

class Worker(QThread):
    done = pyqtSignal(str)
    def run(self):
        # lavoro pesante qui
        self.done.emit("fatto")

w = Worker()
w.done.connect(lambda r: label.setText(r))
w.start()
```
MAI chiamare `time.sleep` o loop pesanti nel thread GUI.

## Dialog
```python
from PyQt6.QtWidgets import QMessageBox
QMessageBox.information(parent, "Titolo", "Messaggio")
QMessageBox.warning(parent, "Titolo", "Attenzione")
```

## Offscreen (per i test)
```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
app = QApplication([])
```

## Errori comuni
- Dimenticare `app.exec()` → la finestra non appare
- Bloccare il thread GUI → finestra "non risponde"
- `QApplication` creato due volte → crash
- Usare `sys.exit(app.exec())` (non `app.exec_()` — deprecato su PyQt6)
