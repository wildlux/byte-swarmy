"""
evaluator.py — Valutazione dell'output generato dai modelli SML.
"""
from __future__ import annotations

import re


class Evaluator:
    """Valuta se l'output generato da un modello soddisfa i criteri di un task."""

    @staticmethod
    def valida_json(output: str) -> bool:
        match = re.search(r"\{[\s\S]*\}", output)
        if not match:
            return False
        try:
            import json as _json
            _json.loads(match.group(0))
            return True
        except Exception:
            return False

    @staticmethod
    def valida_codice_python(output: str) -> bool:
        return "def " in output and "return" in output

    @staticmethod
    def valida_assert(output: str) -> bool:
        return "assert" in output

    @staticmethod
    def valida_task(task_id: str, output: str) -> bool:
        if task_id == "somma_interi":
            return Evaluator.valida_codice_python(output) and Evaluator.valida_assert(output)
        if task_id == "safe_path":
            return "return" in output and ("True" in output or "False" in output)
        if task_id == "refactoring":
            return output.count("def ") >= 2
        return bool(output and len(output.strip()) > 10)

    @classmethod
    def punteggio(cls, task_id: str, output: str) -> float:
        if cls.valida_task(task_id, output):
            return 1.0
        punteggio = 0.0
        if "def " in output:
            punteggio += 0.3
        if "return" in output:
            punteggio += 0.3
        if "assert" in output:
            punteggio += 0.2
        if "isinstance" in output or "if not" in output:
            punteggio += 0.2
        return min(punteggio, 1.0)

__all__ = ["Evaluator"]
