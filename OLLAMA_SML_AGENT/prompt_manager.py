"""
prompt_manager.py — Gestione delle versioni di prompt per l'ottimizzazione.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from OLLAMA_SML_AGENT.config import PROMPT_DIR


class PromptManager:
    """Gestisce diverse versioni di prompt per l'ottimizzazione."""

    def __init__(self):
        self.dir = PROMPT_DIR

    def carica(self, nome_file: str) -> str:
        path = self.dir / nome_file
        if not path.exists():
            raise FileNotFoundError(f"Prompt non trovato: {path}")
        return path.read_text(encoding="utf-8")

    def salva(self, nome_file: str, contenuto: str) -> None:
        path = self.dir / nome_file
        path.write_text(contenuto, encoding="utf-8")

    def lista(self) -> list[str]:
        return sorted([f.name for f in self.dir.glob("*.txt")])

__all__ = ["PromptManager"]
