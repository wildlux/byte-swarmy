"""
state_recovery.py — Ripristino stato worker dall'event store al riavvio.

Legge il log immutabile SQLite (memory_provider) e ricostruisce:
- Ultimo task in esecuzione per ogni worker
- Contesto della sessione precedente
- Eventi non completati

Usage (in orchestrator.py __init__):
    from CORE.state_recovery import recover_worker_state
    recover_worker_state(self.memories, self.config, self.log)
"""
from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional


def recover_worker_state(memories: dict, config: dict, log: logging.Logger):
    """Ripristina lo stato dei worker dall'event store.
    
    Args:
        memories: dict di AgentMemory per worker
        config: config dict
        log: logger
    """
    state_dir = Path(config.get("paths", {}).get("state_dir", "state"))
    db_path = state_dir / "memory_events.db"
    
    if not db_path.exists():
        log.info("[state_recovery] no event store found, starting fresh")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        # Per ogni worker, carica gli ultimi eventi non riassunti
        for agent_id, memory in memories.items():
            rows = conn.execute(
                "SELECT * FROM events WHERE agent_id = ? AND is_summary = 0 "
                "ORDER BY timestamp DESC LIMIT 20",
                (agent_id,)
            ).fetchall()
            
            if not rows:
                continue
            
            # Ricostruisci il contesto
            events = []
            for row in reversed(rows):
                try:
                    event = json.loads(row["data"])
                    events.append(event)
                except (json.JSONDecodeError, TypeError):
                    continue
            
            if events:
                # Aggiungi gli eventi alla memoria short-term
                for event in events:
                    try:
                        if hasattr(memory, 'add_event'):
                            memory.add_event(event)
                    except Exception:
                        pass
                
                log.info(f"[state_recovery] {agent_id}: recovered {len(events)} events")
        
        conn.close()
        log.info("[state_recovery] state recovery complete")
    except Exception as e:
        log.warning(f"[state_recovery] failed: {e}")


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
