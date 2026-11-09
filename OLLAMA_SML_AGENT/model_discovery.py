"""
model_discovery.py — Scoperta automatica dei modelli Ollama disponibili.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Optional

from OLLAMA_SML_AGENT.config import OLLAMA_HOST, DEFAULT_SML_MODELS


def scopri_modelli_ollama(host: str = f"{OLLAMA_HOST}/api/tags") -> list[dict]:
    """Restituisce la lista dei modelli disponibili su Ollama."""
    try:
        req = urllib.request.Request(host, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Impossibile contattare Ollama su {host}: {e}")
        return []

    modelli = []
    for m in data.get("models", []):
        dettagli = m.get("details", {}) or {}
        modelli.append({
            "nome": m.get("name", ""),
            "dimensione": m.get("size", 0),
            "quantizzazione": dettagli.get("quantization_level", "sconosciuta"),
            "famiglia": dettagli.get("family", "sconosciuta"),
            "parametri": dettagli.get("parameter_size", "sconosciuto"),
            "context_length": dettagli.get("context_length", "sconosciuto"),
        })
    return modelli


def filtra_modelli_piccoli(modelli: list[dict], max_parametri: str = "7B") -> list[dict]:
    """Filtra i modelli sotto una certa soglia di parametri."""
    soglia_map = {
        "0.5B": 0.5, "1B": 1.0, "1.3B": 1.3, "1.5B": 1.5,
        "1.7B": 1.7, "2B": 2.0, "3B": 3.0, "4B": 4.0, "7B": 7.0,
    }
    soglia_val = soglia_map.get(max_parametri, 7.0)
    risultanti = []
    for m in modelli:
        try:
            val = float(str(m.get("parametri", "0B")).replace("B", ""))
            if val <= soglia_val:
                risultanti.append(m)
        except ValueError:
            continue
    return risultanti


def stampa_modelli(modelli: list[dict]) -> None:
    """Stampa tabella dei modelli scoperti."""
    if not modelli:
        print("Nessun modello trovato.")
        return
    print(f"\n{'Modello':<30} {'Parametri':<12} {'Quantizzazione':<15} {'Dimensione':<12}")
    print("-" * 70)
    for m in modelli:
        dim_gb = m.get("dimensione", 0) / (1024 * 1024 * 1024)
        print(f"{m['nome']:<30} {m.get('parametri', '?'):<12} "
              f"{m.get('quantizzazione', '?'):<15} {dim_gb:.2f} GB")
    print()

__all__ = ["scopri_modelli_ollama", "filtra_modelli_piccoli"]
