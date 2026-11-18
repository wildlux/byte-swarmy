"""
resilience.py — Resilienza e recupero stato (Cycle 58, semplificazione #4).

Fusione di `CORE/exception_handler.py` e `CORE/state_recovery.py` in un unico
modulo di resilienza. Meno file, meno superficie di test, meno bug.

Solo due azioni sugli errori: retry o abort. Ripristino dello stato worker
dall'event store SQLite al riavvio.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

log = logging.getLogger("byte-swarmy.resilience")

# ---------------------------------------------------------------------------
# Gestione errori semplificata (2 categorie: retry o abort)
# ---------------------------------------------------------------------------

def should_retry(error: Exception, attempt: int, max_retries: int = 3) -> bool:
    """Decide se ritentare. Semplice: se non e' un errore di sicurezza,
    riprova fino a max_retries."""
    if attempt >= max_retries:
        return False

    error_str = str(error).lower()

    # Abort immediato: violazioni di sicurezza
    if any(w in error_str for w in ["sandbox", "blocked", "security", "denied"]):
        return False

    # Retry per tutto il resto (timeout, model unavailable, parse error)
    return True


def get_retry_delay(attempt: int) -> float:
    """Backoff semplice: 2^attempt secondi (cappato a 10s)."""
    return min(2 ** attempt, 10)


def log_error(error: Exception, context: str, attempt: int):
    """Log semplice dell'errore con azione consigliata."""
    action = "retry" if should_retry(error, attempt) else "abort"
    log.warning(f"[resilience] {context}: {error} -> {action} (attempt {attempt})")


# ---------------------------------------------------------------------------
# Ripristino stato worker dall'event store al riavvio
# ---------------------------------------------------------------------------

def recover_worker_state(memories: dict, config: dict, log: logging.Logger):
    """Ripristina lo stato dei worker dall'event store SQLite.

    Legge il log immutabile (memory_provider) e ricostruisce:
      - Ultimo task in esecuzione per ogni worker
      - Contesto della sessione precedente
      - Eventi non completati
    """
    state_dir = Path(config.get("paths", {}).get("state_dir", "state"))
    db_path = state_dir / "memory_events.db"

    if not db_path.exists():
        log.info("[resilience] no event store found, starting fresh")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        for agent_id, memory in memories.items():
            rows = conn.execute(
                "SELECT * FROM events WHERE agent_id = ? AND is_summary = 0 "
                "ORDER BY timestamp DESC LIMIT 20",
                (agent_id,)
            ).fetchall()

            if not rows:
                continue

            events = []
            for row in reversed(rows):
                try:
                    event = json.loads(row["data"])
                    events.append(event)
                except (json.JSONDecodeError, TypeError):
                    continue

            if events:
                for event in events:
                    try:
                        if hasattr(memory, 'add_event'):
                            memory.add_event(event)
                    except Exception:
                        pass

                log.info(f"[resilience] {agent_id}: recovered {len(events)} events")

        conn.close()
        log.info("[resilience] state recovery complete")
    except Exception as e:
        log.warning(f"[resilience] failed: {e}")


def get_last_task_for_worker(agent_id: str, config: dict) -> Optional[dict]:
    """Trova l'ultimo task eseguito da un worker."""
    state_dir = Path(config.get("paths", {}).get("state_dir", "state"))
    db_path = state_dir / "memory_events.db"

    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM events WHERE agent_id = ? AND event_type = 'task_start' "
            "ORDER BY timestamp DESC LIMIT 1",
            (agent_id,)
        ).fetchone()
        conn.close()

        if row:
            return json.loads(row["data"])
        return None
    except Exception:
        return None
