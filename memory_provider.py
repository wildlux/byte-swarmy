"""
memory_provider.py — Memory Backend Abstraction
Definisce l'interfaccia per i diversi backend di memoria (JSON, Redis, DB).
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
import json
import time
from typing import Any, List, Dict, Optional

class MemoryProvider(ABC):
    """Interfaccia astratta per i provider di memoria degli agenti."""

    @abstractmethod
    def save_event(self, agent_id: str, event: Dict[str, Any]) -> None:
        \"\"\"Salva un singolo evento nella memoria dell'agente.\"\"\"
        pass

    @abstractmethod
    def get_events(self, agent_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        \"\"\"Recupera gli eventi della memoria dell'agente.\"\"\"
        pass

    @abstractmethod
    def clear_short_term(self, agent_id: str) -> None:
        \"\"\"Pulisce la memoria a breve termine.\"\"\"
        pass

    @abstractmethod
    def compact_memory(self, agent_id: str, summary: str) -> None:
        \"\"\"Archivia la memoria corrente e inserisce un riassunto (compaction).\"\"\"
        pass


class JSONMemoryProvider(MemoryProvider):
    \"\"\"
    Implementazione originale basata su file JSON.
    Mantiene la retrocompatibilità con il formato esistente.
    \"\"\"

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.agents_dir = state_dir / \"agents\"
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def _get_agent_dir(self, agent_id: str) -> Path:
        d = self.agents_dir / agent_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _read_file(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding=\"utf-8\"))
        except Exception:
            return []

    def _write_file(self, path: Path, data: List[Dict]) -> None:
        tmp = path.with_suffix(\".tmp\")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding=\"utf-8\")
        tmp.replace(path)

    def save_event(self, agent_id: str, event: Dict[str, Any]) -> None:
        # Determina se l'evento va in working o short_term (per semplicità qui usiamo working)
        # In AgentMemory la logica di smistamento rimane, qui scriviamo il dato.
        dir_path = self._get_agent_dir(agent_id)
        file_path = dir_path / \"working.json\"
        
        data = self._read_file(file_path)
        data.append(event)
        self._write_file(file_path, data)

    def get_events(self, agent_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        dir_path = self._get_agent_dir(agent_id)
        file_path = dir_path / \"working.json\"
        data = self._read_file(file_path)
        return data[-limit:] if limit else data

    def clear_short_term(self, agent_id: str) -> None:
        # In JSON, short_term era spesso in RAM. 
        # Se vogliamo persisterla, usiamo un file separate.
        dir_path = self._get_//agent_dir(agent_id)
        st_path = dir_path / \"short_term.json\"
        if st_path.exists():
            st_path.unlink()

    def compact_memory(self, agent_id: str, summary: str) -> None:
        dir_path = self._get_agent_dir(agent_id)
        working_path = dir_path / \"working.json\"
        long_term_path = dir_path / \"long_term.json\"
        
        # Salva l'attuale working in long_term
        current_working = self._read_file(working_path)
        lt_data = self._read_file(long_term_path)
        lt_data.append({
            \"timestamp\": time.time(),
            \"summary\": summary,
            \"events_count\": len(current_working)
        })
        self._write_file(long_term_path, lt_data)
        
        # Svuota working
        self._write_file(working_path, [])
