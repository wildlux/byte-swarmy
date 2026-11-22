"""Template PyQt6 — finestra minima (E3 / py-gui-scaffold).

Copiare e sostituire i valori marcati `# SLOT:`. Non inventare nuove API:
verificare ogni simbolo con `api_lookup('PyQt6.QtWidgets', simbolo,
strict=True)` prima di usarlo. Nessun timestamp: il template è deterministico.
"""
# SLOT: titolo della finestra
TITLE = "Titolo"
# SLOT: dimensioni iniziali (larghezza, altezza)
WIDTH, HEIGHT = 640, 480

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow


def build_window():
    """Costruisce la finestra senza mostrarla (testabile offscreen)."""
    win = QMainWindow()
    win.setWindowTitle(TITLE)
    win.resize(WIDTH, HEIGHT)
    win.setCentralWidget(QLabel(TITLE))
    return win


if __name__ == "__main__":
    app = QApplication([])
    window = build_window()
    window.show()
    app.exec()
