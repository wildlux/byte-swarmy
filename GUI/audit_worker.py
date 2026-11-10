"""
GUI/audit_worker.py — Worker thread per l'audit mensile del software.

Estratto da GUI/settings_panel.py per ridurre il monolite.

Lancia tests/test_monthly_audit.py --json in un subprocess, parsifica
il JSON risultante e emette segnali per aggiornare la GUI in tempo reale.
Non blocca mai il thread principale della GUI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal as Signal


class AuditWorker(QThread):
    """Esegue l'audit mensile in background."""

    progress = Signal(str)        # messaggio di stato (es. "Avvio audit...")
    finished_ok = Signal(dict)    # report dict (summary + findings)
    failed = Signal(str)          # messaggio di errore

    def __init__(self, root_dir: str, parent=None):
        super().__init__(parent)
        self.root_dir = root_dir
        self._proc: Optional[subprocess.Popen] = None

    def run(self):
        try:
            self.progress.emit("🔍 Avvio audit mensile in background...")
            cmd = [sys.executable, "tests/test_monthly_audit.py", "--json"]
            self._proc = subprocess.Popen(
                cmd,
                cwd=self.root_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = self._proc.communicate(timeout=120)
            if self._proc.returncode != 0 and not stdout.strip():
                self.failed.emit(f"Audit fallito (exit {self._proc.returncode}):\n{stderr[:500]}")
                return
            # Parse JSON
            try:
                report = json.loads(stdout)
            except json.JSONDecodeError as e:
                self.failed.emit(f"Risposta non valida dal test:\n{stdout[:300]}\n\nErrore: {e}")
                return
            self.progress.emit("✓ Audit completato")
            self.finished_ok.emit(report)
        except subprocess.TimeoutExpired:
            self.failed.emit("Audit timeout (>120s). Possibile loop infinito.")
        except FileNotFoundError:
            self.failed.emit("Python non trovato. Verifica l'installazione.")
        except Exception as e:
            self.failed.emit(f"Errore inatteso: {e}")

    def cancel(self):
        """Cancella l'audit (se in corso)."""
        if self._proc and self._proc.poll() is None:
            self._proc.kill()
        self.requestInterruption()
