"""
watchdog.py — System Supervisor for BYTE-SWARMY
Monitora l'orchestratore e lo riavvia istantaneamente in caso di crash.
"""

from __future__ import annotations
import signal
import subprocess
import time
import sys
import logging
from pathlib import Path

# Configurazione minima
ORCHESTRATOR_CMD = [sys.executable, "-m", "CORE.orchestrator"]
LOG_FILE = Path("logs/watchdog.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Orchestratore figlio corrente: serve al gestore SIGTERM per non
# lasciarlo ORFANO quando il lanciatore ferma il watchdog (byte-swarm.sh
# stop manda SIGTERM al pid del watchdog, non al figlio).
_current_process: subprocess.Popen | None = None


def _handle_term(signum, frame) -> None:
    """SIGTERM: ferma anche l'orchestratore figlio, poi esci.

    Senza questo, fermare il watchdog (byte-swarm.sh stop) lascia
    l'orchestratore vivo orfano → al prossimo start due orchestratori
    concurrenti sulla stessa coda.
    """
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
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("watchdog")

def run_orchestrator():
    """Avvia l'orchestratore e monitora il suo stato."""
    while True:
        logger.info("Avvio dell'orchestratore...")
        try:
            # Avvia l'orchestratore come sottoprocesso
            process = subprocess.Popen(
                ORCHESTRATOR_CMD,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            # Registrato per _handle_term: il SIGTERM al watchdog deve
            # fermare ANCHE questo figlio.
            globals()["_current_process"] = process

            # Monitora l'output in tempo reale per loggare eventuali crash
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                # Loggiamo l'output dell'orchestratore per debug
                if "ERROR" in line or "Exception" in line or "SyntaxError" in line:
                    logger.error(f"Rilevato errore nell'orchestratore: {line.strip()}")

            return_code = process.wait()
            if return_code == 0:
                logger.info("L'orchestratore è stato terminato correttamente.")
                sys.exit(0)
            else:
                logger.warning(f"L'orchestratore è crashato con codice {return_code}. Riavvio in corso...")

        except Exception as e:
            logger.error(f"Errore critico durante l'esecuzione dell'orchestratore: {e}")

        time.sleep(1) # Evita loop infiniti a velocità massima in caso di errori fatali immediati

if __name__ == "__main__":
    logger.info("=== BYTE-SWARMY System Watchdog Attivo ===")
    try:
        run_orchestrator()
    except KeyboardInterrupt:
        logger.info("Watchdog fermato dall'utente.")
        sys.exit(0)
