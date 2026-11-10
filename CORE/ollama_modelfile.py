"""
CORE/ollama_modelfile.py — Lettura parametri effettivi dal Modelfile di Ollama.

Ollama scarica i modelli da Hugging Face ma può applicare parametri diversi
(nel Modelfile) rispetto a quelli dichiarati sulla scheda HF. Per evitare di
partire da valori sbagliati, leggiamo i PARAMETER effettivi con:

    ollama show --modelfile <nome-modello>

Questi valori diventano il "punto fisso" di partenza; l'ottimizzatore può
esplorare solo in un intorno limitato (es. temperatura ±0.2, penalità 1.05-1.2).

Se Ollama non è disponibile o il modello non è caricato, ritorna {} e il
sistema cade sui valori di default di config.toml.
"""

from __future__ import annotations

import re
import subprocess
from typing import Optional

# Chiavi PARAMETER che cerchiamo nel Modelfile
PARAM_RE = re.compile(
    r"^\s*PARAMETER\s+("
    r"temperature|top_p|top_k|repeat_penalty|repeat_last_n|"
    r"num_ctx|num_predict|seed"
    r")\s+(.+?)\s*$",
    re.IGNORECASE,
)


def _parse_value(raw: str):
    """Converte il valore stringa di un PARAMETER in int/float/str."""
    raw = raw.strip().strip('"').strip("'")
    # Intero
    try:
        return int(raw)
    except ValueError:
        pass
    # Float
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def get_modelfile_params(model_name: str, timeout: int = 10) -> dict:
    """
    Legge i PARAMETER effettivi dal Modelfile di Ollama per `model_name`.

    Esegue `ollama show --modelfile <model_name>` e estrae le coppie
    PARAMETER chiave valore.

    Ritorna:
        dict con le chiavi trovate (es. {"temperature": 0.7, "repeat_penalty": 1.1}),
        oppure {} se Ollama non è disponibile, il modello non esiste o
        non ci sono PARAMETER dichiarati.
    """
    if not model_name:
        return {}
    try:
        result = subprocess.run(
            ["ollama", "show", "--modelfile", model_name],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return {}
        output = result.stdout or ""
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # Ollama non installato o non risponde: usa i default di config
        return {}

    params: dict = {}
    for line in output.splitlines():
        m = PARAM_RE.match(line)
        if not m:
            continue
        key = m.group(1).lower()
        val = _parse_value(m.group(2))
        params[key] = val

    return params


def get_modelfile_param(model_name: str, key: str, default=None):
    """Ritorna un singolo parametro dal Modelfile, o `default` se assente."""
    params = get_modelfile_params(model_name)
    return params.get(key, default)


__all__ = ["get_modelfile_params", "get_modelfile_param"]
