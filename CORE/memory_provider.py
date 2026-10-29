"""
memory_provider.py — Memory Backend Abstraction
Definisce l'interfaccia per i diversi backend di memoria (JSON, SQLite, Redis).
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
import json
import time
import sqlite3
from typing import Any, List, Dict, Optional

class MemoryProvider(ABC):
    """Interfaccia astratta per i provider di memoria degli agenti."""

    @abstractmethod
    def save_event(self, agent_id: str, event: Dict[str, Any]) -> None:
        """Salva un singolo evento nella memoria dell'agente."""
        pass

    @abstractmethod
    def get_events(self, agent_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Recupera gli eventi della memoria dell'agente."""
        pass

    @abstractmethod
    def clear_short_term(self, agent_id: str) -> None:
        """Pulisce la memoria a breve termine."""
        pass

    @abstractmethod
    def compact_memory(self, agent_id: str, summary: str) -> None:
        """Archivia la memoria corrente e inserisce un riassunto (compaction)."""
        pass


class SQLiteMemoryProvider(MemoryProvider):
    """
    Implementazione basata su SQLite per Event Sourcing.
    Garantisce ACID compliance e accessi efficienti per l'estrazione di contesti.
    """

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.db_path = state_dir / "memory_event_store.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    ts REAL NOT NULL,
                    type TEXT,
                    content TEXT,
                    metadata TEXT,
                    is_summary BOOLEAN DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_ts ON events(agent_id, ts)")
            conn.commit()

    def save_event(self, agent_id: str, event: Dict[str, Any]) -> None:
        # Event Sourcing: ogni evento è un record immutabile
        content = event.get("content", "")
        type_ = event.get("type", "event")
        ts = event.get("ts", time.time())
        
        # Metadata salvati come JSON
        meta = {k: v for k, v in event.items() if k not in ("content", "type", "ts")}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO events (agent_id, ts, type, content, metadata) VALUES (?, ?, ?, ?, ?)",
                (agent_id, ts, type_, content, json.dumps(meta))
            )
            conn.commit()

    def get_events(self, agent_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM events WHERE agent_id = ? AND is_summary = 0 ORDER BY ts ASC"
            params = [agent_id]
            if limit:
                query += f" LIMIT {int(limit)}"
            
            rows = conn.execute(query, params).fetchall()
            
            events = []
            for row in rows:
                event = dict(row)
                meta = json.loads(event.pop("metadata", "{}"))
                event.update(meta)
                # Rimuoviamo ID interno al DB
                event.pop("id", None)
                event.pop("is_summary", None)
                events.append(event)
            return events

    def clear_short_term(self, agent_id: str) -> None:
        # In Event Sourcing, non cancelliamo i dati, ma potremmo marcare 
        # l'inizio di una nuova sessione. Per ora lasciamo vuoto per compatibilità.
        pass

    def compact_memory(self, agent_id: str, summary: str) -> None:
        # Salva il riassunto come un evento speciale
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO events (agent_id, ts, type, content, is_summary) VALUES (?, ?, ?, ?, ?)",
                (agent_id, time.time(), "summary", summary, 1)
            )
            conn.commit()


class JSONMemoryProvider(MemoryProvider):
    """
    Implementazione basata su file JSON per retrocompatibilità.
    """

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.agents_dir = state_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def _get_agent_dir(self, agent_id: str) -> Path:
        d = self.agents_dir / agent_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _read_file(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_file(self, path: Path, data: List[Dict]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def save_event(self, agent_id: str, event: Dict[str, Any]) -> None:
        dir_path = self._get_agent_dir(agent_id)
        file_path = dir_path / "working.json"
        data = self._read_file(file_path)
        data.append(event)
        self._write_file(file_path, data)

    def get_events(self, agent_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        dir_path = self._get_agent_dir(agent_id)
        file_path = dir_path / "working.json"
        data = self._read_file(file_path)
        return data[-limit:] if limit else data

    def clear_short_term(self, agent_id: str) -> None:
        dir_path = self._get_agent_dir(agent_id)
        st_path = dir_path / "short_term.json"
        if st_path.exists():
            st_path.unlink()

    def compact_memory(self, agent_id: str, summary: str) -> None:
        dir_path = self._get_agent_dir(agent_id)
        working_path = dir_path / "working.json"
        long_term_path = dir_path / "long_term.json"
        current_working = self._read_file(working_path)
        lt_data = self._read_file(long_term_path)
        lt_data.append({
            "timestamp": time.time(),
            "summary": summary,
            "events_count": len(current_working)
        })
        self._write_file(long_term_path, lt_data)
        self._write_file(working_path, [])
