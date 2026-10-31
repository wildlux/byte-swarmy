"""
exception_handler.py — Gestione errori semplificata (2 categorie).

Solo due azioni: retry o abort. Niente classificazioni complesse.
Un LLM locale non ha bisogno di 5 livelli di error handling.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("byte-swarmy.exceptions")


def should_retry(error: Exception, attempt: int, max_retries: int = 3) -> bool:
    """Decide se ritentare. Semplice: se non e' un errore di sicurezza,
    riprova fino a max_retries."""
    if attempt >= max_retries:
        return False
    
    error_str = str(error).lower()
    
    # Abort immediato: violazioni di sicurezza
    if any(w in error_str for w in ["sandbox", "blocked", "security", "denied"]):
        return False
    
    # Retry per tutto il resto (timeout, model unavailable, parse error)
    return True


def get_retry_delay(attempt: int) -> float:
    """Backoff semplice: 2^attempt secondi."""
    return min(2 ** attempt, 10)  # max 10 secondi


def log_error(error: Exception, context: str, attempt: int):
    """Log semplice dell'errore."""
    action = "retry" if should_retry(error, attempt) else "abort"
    log.warning(f"[exception] {context}: {error} -> {action} (attempt {attempt})")
