#!/usr/bin/env python3
"""Entry point per byte-swarmy."""
import sys
import os
import traceback
from datetime import datetime
from pathlib import Path


def _install_crash_handler():
    """Installa un excepthook che salva il traceback su logs/crash.log
    prima che il programma termini per un'eccezione non gestita."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    crash_log = log_dir / "crash.log"

    _old_hook = sys.excepthook

    def _crash_handler(exc_type, exc_value, exc_tb):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"════════════════════════════════════════════════════════════════════════════════",
            f"CRASH RILEVATO alle {ts}",
            f"Tipo eccezione: {exc_type.__name__ if exc_type else 'Sconosciuto'}",
            f"Messaggio: {exc_value}",
            f"",
            f"Traceback:",
        ]
        lines.extend(traceback.format_exception(exc_type, exc_value, exc_tb))
        lines.append(
            f"═════════════════════════════════════════════════════════════════════════════════"
        )
        lines.append("")
        try:
            with open(crash_log, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass
        # Chiama l'excepthook originale di Python
        try:
            _old_hook(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _crash_handler


_install_crash_handler()

from CORE.orchestrator import main

if __name__ == "__main__":
    sys.exit(main())
