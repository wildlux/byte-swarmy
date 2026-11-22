"""Template PyQt6 — worker in QThread con chiusura pulita (E3 / py-gui-scaffold).

Copiare e sostituire i valori marcati `# SLOT:`. Regola: il worker è un
QObject spostato nel thread; il segnale di fine ferma il thread e aggiorna
la GUI solo tramite segnale (mai toccare widget dal thread di lavoro).
"""
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal

# SLOT: messaggio emesso a fine lavoro
DONE_MESSAGE = "ok"


class Worker(QObject):
    """Lavoro CPU: nessun widget, solo segnali."""

    done = pyqtSignal(str)

    def run(self):
        self.done.emit(DONE_MESSAGE)


class Controller(QObject):
    """Avvia il worker e riporta il risultato via segnale."""

    finished = pyqtSignal(str)

    def start(self):
        self.thread = QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.done.connect(self.finished.emit)
        # DirectConnection: quit() deve girare nel thread worker, altrimenti
        # resta in coda al main loop e wait() non termina mai.
        self.worker.done.connect(
            self.thread.quit, Qt.ConnectionType.DirectConnection)
        self.thread.start()
        return self.thread
