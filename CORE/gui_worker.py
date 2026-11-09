"""
gui_worker.py — Classe base per i worker QThread della GUI.

Motivazione: nella GUI ci sono diversi worker (audit, download pesi HF,
harness weight-space, …) che ripetono lo stesso schema:
  - segnali progress / finished_ok / failed
  - flag di cancel
  - run() con try/except che emette failed su eccezione

Questa classe base incapsula il boilerplate comune. Ogni worker concreto
implementa solo `_execute()` e i segnali specifici aggiuntivi.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal as Signal


class BaseWorker(QThread):
    """Worker in background che non blocca la GUI.

    Segnali comuni:
      - progress(str): messaggio di stato da mostrare all'utente
      - finished_ok(object): risultato dell'esecuzione (dict, str, …)
      - failed(str): messaggio di errore in caso di fallimento
    """

    progress = Signal(str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = False

    def cancel(self):
        """Richiede l'annullamento (cooperativo: il worker deve controllare _cancel)."""
        self._cancel = True

    def is_cancelled(self) -> bool:
        return self._cancel

    def run(self):
        """Esegue _execute() in un try/except centrale."""
        try:
            self._execute()
        except Exception as e:  # noqa: BLE001 — il worker non deve mai crashare la GUI
            self.failed.emit(str(e))

    # ------------------------------------------------------------------
    # Sottoclasse: implementare qui la logica reale.
    # ------------------------------------------------------------------
    def _execute(self):
        raise NotImplementedError("implementare _execute() nella sottoclasse")
