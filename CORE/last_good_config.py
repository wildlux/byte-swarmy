"""
CORE/last_good_config.py — Ultima configurazione LLM valida (rollback).

Salva in `state/last_good_config.json` l'ultima configurazione di parametri
LLM (temperature, top_p, top_k, repeat_penalty, num_ctx, num_predict, seed)
che ha portato un task al completamento con successo (audit APPROVE).

Quando una nuova configurazione fallisce (task in `failed_definitivamente`
o loop persistente), il sistema può tornare all'ultima configurazione nota
come buona, evitando di restare bloccato in zone che producono ripetizioni.

Struttura del file JSON:
{
  "worker_coder": {"temperature": 0.1, "top_p": 0.8, ...},
  "worker_general": {...},
  "planner": {...},
  "orchestrator": {...}
}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# Percorso del file di persistenza (rispetto alla root del repo)
STATE_DIR = Path(__file__).resolve().parent.parent / "state"
LAST_GOOD_FILE = STATE_DIR / "last_good_config.json"

# Chiavi dei parametri LLM che tracciamo
PARAM_KEYS = (
    "temperature",
    "top_p",
    "top_k",
    "repeat_penalty",
    "repeat_last_n",
    "num_ctx",
    "num_predict",
    "seed",
)


def _load_json(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        # Non bloccare l'esecuzione se non riusciamo a scrivere lo stato
        import logging
        logging.getLogger("byte-swarmy.last_good").debug(
            f"last_good_config save failed: {e}"
        )


class LastGoodConfig:
    """
    Gestisce l'ultima configurazione LLM nota come buona per ogni model_key.

    Uso tipico nell'orchestratore:
        lgc = LastGoodConfig()
        # Quando un task completa con successo:
        lgc.save("worker_coder", used_params)
        # Quando un task fallisce definitivamente:
        good = lgc.load("worker_coder")   # -> dict o None
    """

    def __init__(self, state_file: Path = LAST_GOOD_FILE):
        self.state_file = state_file
        self._cache: dict = {}

    def _reload(self) -> dict:
        self._cache = _load_json(self.state_file)
        return self._cache

    def save(self, model_key: str, params: dict) -> None:
        """Salva `params` come ultima configurazione buona per `model_key`.

        Tieni solo le chiavi LLM note; ignora il resto.
        """
        clean = {}
        for key in PARAM_KEYS:
            if key in params and params[key] is not None:
                try:
                    if key in ("top_k", "repeat_last_n", "num_ctx", "num_predict", "seed"):
                        clean[key] = int(params[key])
                    else:
                        clean[key] = float(params[key])
                except (TypeError, ValueError):
                    continue
        if not clean:
            return
        self._reload()
        self._cache[model_key] = clean
        _save_json(self.state_file, self._cache)

    def load(self, model_key: str) -> Optional[dict]:
        """Ritorna l'ultima configurazione buona per `model_key`, o None."""
        self._reload()
        return self._cache.get(model_key)

    def has(self, model_key: str) -> bool:
        """True se esiste un'ultima configurazione buona per `model_key`."""
        return self.load(model_key) is not None

    def clear(self, model_key: Optional[str] = None) -> None:
        """Rimuove l'ingresso per `model_key`, o tutto se None."""
        self._reload()
        if model_key is None:
            self._cache = {}
        else:
            self._cache.pop(model_key, None)
        _save_json(self.state_file, self._cache)


# Istanza singleton usata dall'orchestratore
last_good_config = LastGoodConfig()

__all__ = ["LastGoodConfig", "last_good_config", "LAST_GOOD_FILE", "PARAM_KEYS"]
