"""
ensemble_runner.py — Esegue lo stesso task su più modelli SML e combina i risultati.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from OLLAMA_SML_AGENT.sml_tester import _chiamata_ollama

OLLAMA_HOST = "http://localhost:11434"


class EnsembleRunner:
    """Esegue lo stesso task su più modelli SML e combina i risultati."""

    def __init__(self, modelli: list[str]):
        self.modelli = modelli

    def esegui_su_tutti(self, task: str, system_prompt: str) -> dict:
        risultati = {}
        for modello in self.modelli:
            try:
                output = _chiamata_ollama(
                    modello,
                    task,
                    system=system_prompt,
                    num_predict=512,
                    temperature=0.2,
                )
                risultati[modello] = {
                    "output": output,
                    "lunghezza": len(output),
                    "valido": bool(output.strip() and len(output.strip()) > 10),
                }
            except Exception as e:
                risultati[modello] = {
                    "output": "",
                    "lunghezza": 0,
                    "valido": False,
                    "errore": str(e),
                }
        return risultati

    def vota(self, risultati: dict) -> dict:
        validi = [(m, r) for m, r in risultati.items() if r.get("valido")]
        if not validi:
            return {
                "vincitore": None,
                "motivo": "Nessun modello ha prodotto output valido",
                "tutti": risultati,
            }
        migliore = max(validi, key=lambda x: x[1]["lunghezza"])
        return {
            "vincitore": migliore[0],
            "output": migliore[1]["output"],
            "lunghezza": migliore[1]["lunghezza"],
            "tutti_i_risultati": risultati,
        }

__all__ = ["EnsembleRunner"]
