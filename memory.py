"""
memory.py — AgentMemory class
Tre buffer su disco: short_term, working, long_term.
Niente stato in RAM oltre al necessario. Compattazione automatica.
"""

from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any


class AgentMemory:
    """
    Memoria di un agente. Stato persistente su disco.

    - short_term: deque in RAM di eventi recenti (task corrente). Max 4096 token stimati.
    - working:    file JSON, eventi sessione. Compattato dopo N eventi.
    - long_term:  file JSON con riassunti storici.
    """

    SHORT_TERM_MAX_EVENTS = 20
    SHORT_TERM_MAX_TOKENS = 4096
    WORKING_MAX_EVENTS = 50

    def __init__(self, agent_id: str, state_dir: Path, model_client, logger):
        self.agent_id = agent_id
        self.state_dir = state_dir
        self.models = model_client
        self.log = logger

        self.dir = state_dir / "agents" / agent_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.working_file = self.dir / "working.json"
        self.long_term_file = self.dir / "long_term.json"
        self.heartbeat_file = self.dir / "heartbeat.json"

        self.short_term: deque = deque(maxlen=self.SHORT_TERM_MAX_EVENTS)
        self.working: list = self._load(self.working_file, default=[])
        self.long_term: list = self._load(self.long_term_file, default=[])

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def add_event(self, event: dict) -> None:
        """Aggiunge un evento a short_term e working."""
        event = {**event, "ts": time.time(), "agent": self.agent_id}
        self.short_term.append(event)
        self.working.append(event)
        self._save(self.working_file, self.working)
        self.heartbeat()

        # Compatta working se troppo lungo
        if len(self.working) >= self.WORKING_MAX_EVENTS:
            self.compact()

    def heartbeat(self) -> None:
        """Scrive timestamp su file per health check."""
        self.heartbeat_file.write_text(json.dumps({"ts": time.time()}))

    def is_alive(self, timeout: int) -> bool:
        """True se l'heartbeat è recente."""
        if not self.heartbeat_file.exists():
            return False
        try:
            data = json.loads(self.heartbeat_file.read_text())
            return (time.time() - data.get("ts", 0)) < timeout
        except Exception:
            return False

    def build_context(self, max_tokens: int = 3500) -> str:
        """Costruisce il contesto per la prossima chiamata LLM.
        Ordine: long_term (riassunto) + working recente + short_term vivo.
        """
        parts = []

        # 1. Riassunto storico (long_term)
        if self.long_term:
            recent_summary = self.long_term[-3:]
            parts.append("## PAST SUMMARY\n" + "\n".join(
                f"- {e.get('summary', str(e))}" for e in recent_summary
            ))

        # 2. Eventi working recenti (ultimi 10)
        if self.working:
            recent = self.working[-10:]
            parts.append("## RECENT SESSION EVENTS\n" + "\n".join(
                f"- [{e.get('ts', 0):.0f}] {e.get('type', '?')}: {e.get('content', '')[:200]}"
                for e in recent
            ))

        # 3. Short term (tutto)
        if self.short_term:
            parts.append("## CURRENT TASK CONTEXT\n" + "\n".join(
                f"- {e.get('type', '?')}: {e.get('content', '')[:300]}"
                for e in self.short_term
            ))

        ctx = "\n\n".join(parts)
        # Stima token ~ 4 char
        if len(ctx) > max_tokens * 4:
            ctx = ctx[-(max_tokens * 4):]
        return ctx

    def compact(self) -> None:
        """Compatta la memoria working in un riassunto che va in long_term.
        Usa l'LLM orchestratore (modello piccolo, economico)."""
        if not self.working:
            return

        self.log.info(f"[{self.agent_id}] compacting memory ({len(self.working)} events)")

        # Prendi gli ultimi 50 eventi per il riassunto
        events_to_summarize = self.working[-self.WORKING_MAX_EVENTS:]
        events_text = "\n".join(
            f"- {e.get('type', '?')}: {e.get('content', '')[:200]}"
            for e in events_to_summarize
        )

        prompt = (
            "Sei un sistema di compattazione memoria. Riassumi in massimo 300 token "
            "gli eventi seguenti, preservando: decisioni chiave, errori, file modificati, "
            "risultati. Non aggiungere commenti.\n\n"
            f"EVENTI:\n{events_text}\n\nRIASSUNTO:"
        )

        try:
            summary = self.models.call(
                model_key="orchestrator",
                prompt=prompt,
                max_tokens=300,
            ).strip()
        except Exception as e:
            self.log.error(f"compaction failed: {e}")
            summary = f"(compaction failed at {time.time()})"

        self.long_term.append({
            "ts": time.time(),
            "summary": summary,
            "events_compacted": len(events_to_summarize),
        })
        self._save(self.long_term_file, self.long_term)

        # Tieni solo gli ultimi 10 eventi working
        self.working = self.working[-10:]
        self._save(self.working_file, self.working)

        self.log.info(f"[{self.agent_id}] memory compacted, summary saved")

    def reset_short_term(self) -> None:
        """Pulisce short_term (all'inizio di un nuovo task)."""
        self.short_term.clear()

    # ------------------------------------------------------------------
    # Utility interne
    # ------------------------------------------------------------------

    def _load(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text())
        except Exception:
            return default

    def _save(self, path: Path, data: Any) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.replace(path)
