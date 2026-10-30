"""
exception_handler.py — Policy centralizzata per gestione errori LLM/tool.

Classifica gli errori in categorie e fornisce azioni raccomandate:
- MODEL_UNAVAILABLE: retry con backoff
- MODEL_TIMEOUT: riduci parametri (meno token, meno contesto)
- TOOL_ERROR: cambia approccio (non ripetere)
- SANDBOX_VIOLATION: rifiuta task
- PARSE_ERROR: ripeti con prompt più semplice
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

log = logging.getLogger("byte-swarmy.exceptions")


class ErrorType(Enum):
    MODEL_UNAVAILABLE = "model_unavailable"
    MODEL_TIMEOUT = "model_timeout"
    TOOL_ERROR = "tool_error"
    SANDBOX_VIOLATION = "sandbox_violation"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorReport:
    error_type: ErrorType
    message: str
    action: str  # "retry" | "abort" | "simplify" | "pivot"
    retry_after_sec: int = 0
    context: dict = None


class ExceptionHandler:
    """Gestisce centralmente le eccezioni di LLM e tool."""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.error_history = []
    
    def classify(self, error: Exception, context: str = "") -> ErrorReport:
        """Classifica un errore e raccomanda un'azione."""
        error_str = str(error).lower()
        
        if "timed out" in error_str or "timeout" in error_str:
            return ErrorReport(
                ErrorType.MODEL_TIMEOUT,
                str(error),
                "simplify",
                retry_after_sec=5,
                context={"source": context}
            )
        elif "unreachable" in error_str or "connection" in error_str:
            return ErrorReport(
                ErrorType.MODEL_UNAVAILABLE,
                str(error),
                "retry",
                retry_after_sec=10,
                context={"source": context}
            )
        elif "sandbox" in error_str or "blocked" in error_str:
            return ErrorReport(
                ErrorType.SANDBOX_VIOLATION,
                str(error),
                "abort",
                context={"source": context}
            )
        elif "json" in error_str or "parse" in error_str:
            return ErrorReport(
                ErrorType.PARSE_ERROR,
                str(error),
                "simplify",
                retry_after_sec=0,
                context={"source": context}
            )
        elif "tool" in error_str or "unknown tool" in error_str:
            return ErrorReport(
                ErrorType.TOOL_ERROR,
                str(error),
                "pivot",
                context={"source": context}
            )
        else:
            return ErrorReport(
                ErrorType.UNKNOWN,
                str(error),
                "retry",
                retry_after_sec=5,
                context={"source": context}
            )
    
    def should_retry(self, report: ErrorReport, attempt: int) -> bool:
        """Decide se ritentare in base al tipo di errore e al tentativo."""
        if attempt >= self.max_retries:
            return False
        if report.action == "abort":
            return False
        return True
    
    def get_retry_delay(self, report: ErrorReport, attempt: int) -> int:
        """Backoff esponenziale."""
        base = report.retry_after_sec or 5
        return base * (2 ** (attempt - 1))
    
    def record(self, task_id: str, report: ErrorReport):
        """Registra l'errore nello storico."""
        self.error_history.append({
            "task_id": task_id,
            "type": report.error_type.value,
            "message": report.message[:200],
            "action": report.action,
            "timestamp": time.time(),
        })
        # Mantieni solo gli ultimi 50
        self.error_history = self.error_history[-50:]
    
    def get_error_stats(self) -> dict:
        """Statistiche errori per diagnostica."""
        from collections import Counter
        types = Counter(e["type"] for e in self.error_history)
        actions = Counter(e["action"] for e in self.error_history)
        return {
            "total": len(self.error_history),
            "by_type": dict(types),
            "by_action": dict(actions),
        }


# Singleton
_handler: Optional[ExceptionHandler] = None

def get_handler() -> ExceptionHandler:
    global _handler
    if _handler is None:
        _handler = ExceptionHandler()
    return _handler


def safe_call(fn: Callable, *args, context: str = "", **kwargs):
    """Wrapper che cattura eccezioni e le classifica.
    
    Usage:
        result = safe_call(self.models.call, model_key="worker", 
                          prompt=p, context="worker_step_1")
    """
    handler = get_handler()
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        report = handler.classify(e, context)
        log.warning(f"[exception] {context}: {report.error_type.value} -> {report.action}")
        handler.record(context, report)
        raise
