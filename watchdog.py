"""
watchdog.py — System Supervisor for BYTE-SWARMY
Monitora l'orchestratore e lo riavvia istantaneamente in caso di crash.
"""

from __future__ import annotations
import subprocess
import time
import sys
import logging
from pathlib import Path

# Configurazione minima
ORCHESTRATOR_CMD = [sys.executable, "orchestrator.py"]
LOG_FILE = Path("logs/watchdog.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

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
    \"\"\"Avvia l'orchestratore e monitora il suo stato.\"\"\"
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

if __name__ == \"__main__\":
    logger.info(\"=== BYTE-SWARMY System Watchdog Attivo ===\")
    try:
        run_orchestrator()
    except KeyboardInterrupt:
        logger.info(\"Watchdog fermato dall'utente.\")
        sys.exit(0)
