"""
auto_optimizer.py — Motore di ottimizzazione principale per un singolo modello SML.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from OLLAMA_SML_AGENT.config import BASE_DIR, DEFAULT_PARAMS
from OLLAMA_SML_AGENT.prompt_manager import PromptManager
from OLLAMA_SML_AGENT.evaluator import Evaluator

from CORE.sml_database import (
    init_db,
    aggiungi_modello,
    get_modello_id,
    salva_parametri,
    salva_risultato,
    salva_benchmark,
)
from OLLAMA_SML_AGENT.sml_tester import _chiamata_ollama, _leggi_system_prompt
from OLLAMA_SML_AGENT.logbook import salva_tentativo


class AutoOptimizer:
    """Motore di ottimizzazione automatica per un singolo modello SML."""

    def __init__(self, modello: str):
        self.modello = modello
        self.pm = PromptManager()
        self.evaluator = Evaluator()
        init_db()
        self.modello_id = get_modello_id(modello)
        if self.modello_id is None:
            self.modello_id = aggiungi_modello(
                modello, quantizzazione="sconosciuta", dimensione_gb=0.0
            )

    def testa_singolo(self, task: str, system_prompt: str, num_tentativi: int = 3) -> dict:
        prompt_attuale = system_prompt
        tentativi = []

        for tentativo in range(1, num_tentativi + 1):
            try:
                output = _chiamata_ollama(
                    self.modello,
                    task,
                    system=prompt_attuale,
                    num_predict=DEFAULT_PARAMS["num_predict"],
                    temperature=DEFAULT_PARAMS["temperature"],
                    num_ctx=DEFAULT_PARAMS["num_ctx"],
                    repeat_penalty=DEFAULT_PARAMS["repeat_penalty"],
                    seed=DEFAULT_PARAMS["seed"],
                )
            except Exception as e:
                tentativi.append({
                    "tentativo": tentativo,
                    "esito": "errore",
                    "errore": str(e),
                    "output": "",
                })
                continue

            valido = self.evaluator.valida_task("somma_interi", output)
            punteggio = self.evaluator.punteggio("somma_interi", output)

            salva_tentativo(
                modello=self.modello,
                quantizzazione="sconosciuta",
                dimensione_gb=0.0,
                prompt_versione="v3.1",
                livello=tentativo,
                prompt_inviato=prompt_attuale,
                output_grezzo=output,
                output_parsato=None,
                esito="promosso" if valido else "bocciato",
                punteggio=punteggio,
                errore=None if valido else "Output non soddisfa i criteri",
                note_miglioramento=None,
            )

            tentativi.append({
                "tentativo": tentativo,
                "esito": "promosso" if valido else "bocciato",
                "punteggio": punteggio,
                "output": output[:200],
            })

            if valido:
                return {
                    "modello": self.modello,
                    "task": task,
                    "esito": "successo",
                    "tentativo": tentativo,
                    "output": output,
                }

            prompt_attuale = self.pm.carica("system_prompt.txt")

        return {
            "modello": self.modello,
            "task": task,
            "esito": "fallito_dopo_tutti_i_tentativi",
            "tentativi": tentativi,
        }

__all__ = ["AutoOptimizer"]
