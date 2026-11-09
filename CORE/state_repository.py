"""
state_repository.py — Accesso centralizzato ai file JSON di stato.

Motivazione: oggi lettura/scrittura JSON sono sparsi in molti moduli
(``settings_store.py``, ``hf_weights.py``, ``benchmark.py``,
``control_center.py``), ognuno con il proprio ``open(...)``,
``os.makedirs(...)``, ``try/except`` e gestione errori leggermente diversa.

Questo modulo incapsula il boilerplate comune:
  - ``load_json(rel_path, default)`` — legge un file JSON, ritorna
    ``default`` se mancante o corrotto (mai eccezione).
  - ``save_json(rel_path, data)`` — scrive JSON indentato, crea le
    directory genitori se necessario, ritorna True/False.
  - ``exists(rel_path)`` / ``remove(rel_path)``.

Tutti i path sono relativi alla root del progetto (dove si trova
questo modulo → ``CORE/`` → root = padre di ``CORE/``).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

# Root del progetto: CORE/state_repository.py → padre di CORE/
BASE_DIR = Path(__file__).resolve().parent.parent

# Subdirectory di stato già usate dal progetto
STATE_DIR = BASE_DIR / "state"
CONFIG_DIR = BASE_DIR / "CONFIG"


class StateRepository:
    """Repository per file JSON di stato dell'applicazione."""

    def __init__(self, base_dir: Path = BASE_DIR):
        self.base = base_dir

    # ------------------------------------------------------------------
    # Operazioni base
    # ------------------------------------------------------------------
    def load_json(
        self, rel_path: str, default: Optional[Any] = None
    ) -> Any:
        """Carica un file JSON.

        Ritorna ``default`` se il file non esiste, è illeggibile o contiene
        JSON non valido. Non solleva mai eccezioni.
        """
        path = self.base / rel_path
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return default

    def save_json(self, rel_path: str, data: Any) -> bool:
        """Salva dati in formato JSON (indentato, UTF-8).

        Crea le directory genitori se mancanti. Ritorna True se ok.
        """
        path = self.base / rel_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except OSError:
            return False

    def exists(self, rel_path: str) -> bool:
        return (self.base / rel_path).exists()

    def remove(self, rel_path: str) -> bool:
        """Rimuove un file. Ritorna True se esistente e rimosso."""
        path = self.base / rel_path
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Comodità per sottodirectory standard
    # ------------------------------------------------------------------
    def state_path(self, name: str) -> Path:
        return STATE_DIR / name

    def config_path(self, name: str) -> Path:
        return CONFIG_DIR / name


# Istanza di comodo per l'uso diretto (import e usa)
default_repo = StateRepository()


def load_json(rel_path: str, default: Optional[Any] = None) -> Any:
    """Wrapper modulare su ``default_repo.load_json``."""
    return default_repo.load_json(rel_path, default)


def save_json(rel_path: str, data: Any) -> bool:
    """Wrapper modulare su ``default_repo.save_json``."""
    return default_repo.save_json(rel_path, data)
