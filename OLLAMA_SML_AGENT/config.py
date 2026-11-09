"""
config.py — Configurazione centrale per l'ottimizzatore SML.

Contiene costanti, percorsi e parametri di default usati dai moduli
dell'ottimizzatore di modelli linguistici piccoli (SML).
"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OLLAMA_HOST = "http://localhost:11434"

AGENT_DIR = BASE_DIR / "OLLAMA_SML_AGENT"
PROMPT_DIR = AGENT_DIR / "prompts"
CACHE_DIR = AGENT_DIR / "cache"
FEEDBACK_DIR = AGENT_DIR / "feedback"
RESULTS_DIR = AGENT_DIR / "results"
ENSEMBLE_DIR = AGENT_DIR / "ensemble"
LOGBOOK_DIR = AGENT_DIR / "logbook"

for d in (PROMPT_DIR, CACHE_DIR, FEEDBACK_DIR, RESULTS_DIR, ENSEMBLE_DIR, LOGBOOK_DIR):
    d.mkdir(parents=True, exist_ok=True)

DEFAULT_TASKS = [
    {
        "id": "somma_interi",
        "task": 'Crea una funzione Python che sommi due numeri interi con type hints.',
        "tipo": "coding",
    },
]

DEFAULT_SML_MODELS = [
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "deepseek-coder:1.3b",
    "qwen3:1.7b",
    "qwen2.5:3b",
    "qwen3:4b",
]

DEFAULT_PARAMS = {
    "temperature": 0.1,
    "num_predict": 512,
    "num_ctx": 2048,
    "repeat_penalty": 1.15,
    "seed": 42,
}

__all__ = [
    "BASE_DIR",
    "OLLAMA_HOST",
    "AGENT_DIR",
    "PROMPT_DIR",
    "CACHE_DIR",
    "FEEDBACK_DIR",
    "RESULTS_DIR",
    "ENSEMBLE_DIR",
    "LOGBOOK_DIR",
    "DEFAULT_TASKS",
    "DEFAULT_SML_MODELS",
    "DEFAULT_PARAMS",
]
