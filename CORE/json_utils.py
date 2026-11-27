"""CORE/json_utils.py — Estrazione JSON da output LLM (helper condiviso).

Riduce la duplicazione tra generic_planner e worker.
"""
from __future__ import annotations

import ast
import json
import re


def extract_json_object(raw: str) -> dict | None:
    """Estrae il primo oggetto JSON da `raw`.

    Prova json.loads; se fallisce (modelli piccoli emettono dict
    Python-style con apici singoli), normalizza true/false/null e
    riprova con ast.literal_eval. Ritorna None se non trova nulla.
    """
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    candidate = m.group(0)
    try:
        data = json.loads(candidate)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        fixed = re.sub(
            r"\b(true|false|null)\b",
            lambda mm: {"true": "True", "false": "False", "null": "None"}[mm.group(1)],
            candidate,
        )
        data = ast.literal_eval(fixed)
        return data if isinstance(data, dict) else None
    except (ValueError, SyntaxError):
        return None
PY
.venv/bin/python -m py_compile CORE/json_utils.py && echo "COMPILE_OK"