"""watchdog.py — System Supervisor for BYTE-SWARMY
Monitora l'orchestratore e lo riavvia in caso di crash, con backoff
escalato (1→2→4→…→60s), reset dopo un run sano (≥60s) e allerta
dopo 5 riavvii consecutivi. (Robustezza #1)
"""

from __future__ import annotations
import signal
import subprocess
import time
import sys
import logging
import logging.handlers
from pathlib import Path

# Configurazione minima
ORCHESTRATOR_CMD = [sys.executable, "-m", "CORE.orchestrator"]
LOG_FILE = Path("logs/watchdog.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Orchestratore figlio corrente: serve al gestore SIGTERM per non
# lasciarlo ORFANO quando il lanciatore ferma il watchdog.
_current_process: subprocess.Popen | None = None

# Costanti esposte per i test (e per tuning futuro).
BACKOFF_BASE_SEC = 1
BACKOFF_CAP_SEC = 60
HEALTHY_RUN_SEC = 60.0
ALERT_AFTER_RESTARTS = 5

# Hook di test: se non None, il watchdog esce dopo N riavvii (permette di
# simulare crash senza loop infinito). In produzione resta None.
_MAX_RESTARTS: int | None = None


def backoff_for(restart_count: int, base: int = BACKOFF_BASE_SEC,
                cap: int = BACKOFF_CAP_SEC) -> int:
    """Backoff escalato: 1, 2, 4, 8, … fino a `cap`.

    `restart_count` è il numero di riavvii *consecutivi* già tentati
    (1 = primo crash). Un valore <= 0 restituisce `base`.
    """
    if restart_count <= 0:
        return base
    return min(cap, base * (2 ** (restart_count - 1)))


def healthy_reset(ran_for_seconds: float,
                  threshold: float = HEALTHY_RUN_SEC) -> bool:
    """True se il processo ha girato abbastanza a lungo da azzerare il
    contatore di riavvii consecutivi."""
    return ran_for_seconds >= threshold


def _handle_term(signum, frame) -> None:
    """SIGTERM: ferma anche l'orchestratore figlio, poi esci."""
    p = _current_process
    if p is not None and p.poll() is None:
        try:
            p.terminate()
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()
        except Exception:
            pass
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _handle_term)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(levelname)s: %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("watchdog")


def run_orchestrator():
    """Avvia l'orchestratore e monitora il suo stato.

    Backoff escalato, reset dopo run sano, allerta dopo 5 riavvii.
    """
    restarts = 0
    last_start = time.time()
    while True:
        logger.info("Avvio dell'orchestratore...")
        try:
            process = subprocess.Popen(
                ORCHESTRATOR_CMD,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            globals()["_current_process"] = process
            last_start = time.time()

            while True:
                line = process.stdout.readline()
                if not line:
                    break
                if "ERROR" in line or "Exception" in line or "SyntaxError" in line:
                    logger.error(f"Rilevato errore nell'orchestratore: {line.strip()}")

            return_code = process.wait()
            ran_for = time.time() - last_start

            if return_code == 0:
                logger.info("L'orchestratore è stato terminato correttamente.")
                sys.exit(0)

            if healthy_reset(ran_for):
                restarts = 0

            restarts += 1
            if restarts >= ALERT_AFTER_RESTARTS:
                logger.error(
                    f"ALERT: {restarts} riavvii consecutivi dell'orchestratore "
                    f"(ultimo exit={return_code}). Possibile poison crash.")

            delay = backoff_for(restarts)
            logger.warning(
                f"L'orchestratore è crashato con codice {return_code} dopo "
                f"{ran_for:.1f}s. Riavvio in {delay}s (riavvio #{restarts}).")

            if _MAX_RESTARTS is not None and restarts >= _MAX_RESTARTS:
                logger.error("Watchdog: limite riavvii di test raggiunto, esco.")
                sys.exit(1)

            time.sleep(delay)
            last_start = time.time()

        except Exception as e:
            logger.error(f"Errore critico durante l'esecuzione dell'orchestratore: {e}")
            restarts += 1
            delay = backoff_for(restarts)
            if _MAX_RESTARTS is not None and restarts >= _MAX_RESTARTS:
                logger.error("Watchdog: limite riavvii di test raggiunto, esco.")
                sys.exit(1)
            time.sleep(delay)
            last_start = time.time()

if __name__ == "__main__":
    logger.info("=== BYTE-SWARMY System Watchdog Attivo ===")
    try:
        run_orchestrator()
    except KeyboardInterrupt:
        logger.info("Watchdog fermato dall'utente.")
        sys.exit(0)
